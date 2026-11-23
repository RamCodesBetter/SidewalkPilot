#!/usr/bin/env python3
"""Verify tracking defaults, backward compatibility, identity and metric replay."""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2] / "ai_models_datasets"
sys.path.insert(0, str(ROOT / "series_3_and_4"))
sys.path.insert(0, str(ROOT / "series_5" / "tools"))
sys.path.insert(0, str(ROOT / "series_5"))
from workspace import activate
activate()
from wandb_logger import WandbLogger
from series_5_a_sidewalkpilot_trainer import main, start_wandb


class FakeSummary(dict):
    def update(self, d):
        return super().update(d)


class FakeRun:
    def __init__(self, resumed=False, epoch=0):
        self.resumed = resumed
        self.summary = FakeSummary(epoch=epoch)
        self.settings = SimpleNamespace(mode="online")
        self.url = "https://wandb.ai/Sidewalk-Pilot/SidewalkPilot/runs/fake"
        self.logs, self.definitions, self.exits = [], [], []

    def log(self, payload):
        self.logs.append(payload)
        self.summary.update(payload)

    def define_metric(self, *args, **kwargs):
        self.definitions.append((args, kwargs))

    def finish(self, exit_code=0):
        self.exits.append(exit_code)


class WandbTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.cfg = {"model_name": "5.A", "smoke_only": True}
        self.identity = {"manifest_sha256": "manifest", "split_sha256": "split"}
        self.metadata = {"parameters": 3218308, "device": "gpu", "steps_per_epoch": 55}
        self.partitions = {"train": [{"supervision": "binary-reference"}, {"supervision": "sidewalk-positive-only"}]}
        self.run = FakeRun()
        self.sdk = SimpleNamespace(init=mock.Mock(return_value=self.run))
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.dict(sys.modules, {"wandb": self.sdk}))
        stack.enter_context(mock.patch.dict(os.environ, {"WANDB_DISABLED": ""}))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def start(self, history=()):
        return start_wandb(self.output, self.cfg, self.identity, self.metadata, self.partitions, history)

    def test_legacy_calls_keep_project_and_optional_tracking(self):
        logger = WandbLogger("old-model", {"series": 4})
        self.sdk.init.assert_called_once_with(entity="Sidewalk-Pilot", project="SidewalkPilot", name="old-model", config={"series": 4})
        logger.push(1, {"loss": 0.5, "missing": None})
        self.assertEqual(self.run.logs, [{"loss": 0.5, "epoch": 1.0}])
        logger.finish()
        self.assertEqual(self.run.exits, [0])

    def test_cli_enables_tracking_by_default_with_local_opt_out(self):
        command = ["trainer", "train", "--dataset", "data", "--split", "split.json", "--output", "run"]
        for extra, expected in (([], True), (["--no-wandb"], False), (["--wandb"], True)):
            with mock.patch.object(sys, "argv", command + extra), mock.patch("series_5_a_sidewalkpilot_trainer.train", return_value={}) as train:
                main()
                self.assertEqual(train.call_args.args[0].wandb, expected)

    def test_legacy_init_failure_is_optional_required_failure_is_not(self):
        self.sdk.init.side_effect = RuntimeError("network down")
        self.assertFalse(WandbLogger("legacy").enabled)
        with self.assertRaisesRegex(RuntimeError, "connection failed"):
            WandbLogger("5.A", required=True)

    def test_disabled_required_tracking_fails_without_connecting(self):
        with mock.patch.dict(os.environ, {"WANDB_DISABLED": "1"}):
            self.assertFalse(WandbLogger("legacy").enabled)
            with self.assertRaisesRegex(RuntimeError, "no-wandb"):
                WandbLogger("5.A", required=True)
        self.sdk.init.assert_not_called()

    def test_metrics_only_settings_group_tags_and_receipt(self):
        self.start()
        options = self.sdk.init.call_args.kwargs
        self.assertEqual(options["group"], "5.A")
        self.assertEqual(options["job_type"], "smoke-test")
        self.assertIn("smoke", options["tags"])
        self.assertFalse(options["save_code"])
        self.assertTrue(options["settings"]["disable_git"])
        receipt = json.loads((self.output / "wandb-run.json").read_text())
        self.assertEqual(receipt["url"], self.run.url)
        self.assertEqual(receipt["id"], options["id"])
        self.assertEqual(receipt["model_name"], "5.A")
        self.assertFalse(self.run.summary["media_uploaded"])
        self.assertFalse(self.run.summary["checkpoints_uploaded"])

    def test_resume_reuses_id_and_replays_only_unlogged_epochs(self):
        initial = self.start()
        first_id = self.sdk.init.call_args.kwargs["id"]
        initial.finish()
        resumed = FakeRun(resumed=True, epoch=1)
        self.sdk.init.return_value = resumed
        tracker = self.start([{"epoch": 1, "loss": 0.7}, {"epoch": 2, "loss": 0.6}])
        self.assertEqual(self.sdk.init.call_args.kwargs["id"], first_id)
        self.assertEqual(resumed.logs, [{"epoch": 2.0, "loss": 0.6}])
        tracker.push(2, {"loss": 0.6})
        self.assertEqual(len(resumed.logs), 1)

    def test_cloud_run_missing_replays_all_local_history(self):
        self.start([{"epoch": 1, "loss": 0.7}, {"epoch": 2, "loss": 0.6}])
        self.assertEqual(len(self.run.logs), 2)

    def test_identity_mismatch_rejected_before_connection(self):
        self.start()
        self.sdk.init.reset_mock()
        self.identity["split_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "different model settings or data"):
            self.start()
        self.sdk.init.assert_not_called()

    def test_failed_connection_keeps_same_identity_for_retry(self):
        self.sdk.init.side_effect = RuntimeError("network down")
        with self.assertRaises(RuntimeError):
            self.start()
        first_id = json.loads((self.output / "wandb-run.json").read_text())["id"]
        self.sdk.init.side_effect = None
        self.start()
        self.assertEqual(first_id, self.sdk.init.call_args.kwargs["id"])

    def test_metric_failure_raises_only_for_required_tracking(self):
        self.run.log = mock.Mock(side_effect=RuntimeError("log failed"))
        self.assertFalse(WandbLogger("legacy").push(1, {"loss": 0.5}))
        with self.assertRaisesRegex(RuntimeError, "metric logging failed"):
            WandbLogger("5.A", required=True).push(1, {"loss": 0.5})

    def test_failed_backfill_finishes_run_as_failed(self):
        self.run.log = mock.Mock(side_effect=RuntimeError("log failed"))
        with self.assertRaises(RuntimeError):
            self.start([{"epoch": 1, "loss": 0.5}])
        self.assertEqual(self.run.exits, [1])

    def test_5b_live_policy_rejects_offline_mode(self):
        self.cfg.update(model_name="5.B", training_policy={"require_live_wandb": True})
        self.run.settings.mode = "offline"
        with self.assertRaisesRegex(RuntimeError, "live online"):
            self.start()
        self.assertEqual(self.run.exits, [1])

    def test_5b_batch_metrics_use_training_step(self):
        self.cfg.update(model_name="5.B", training_policy={"require_live_wandb": True})
        self.start()
        self.assertIn((("batch/*",), {"step_metric": "train_step"}), self.run.definitions)


if __name__ == "__main__":
    unittest.main()
