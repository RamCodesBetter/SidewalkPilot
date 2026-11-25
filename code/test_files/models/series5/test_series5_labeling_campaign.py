import fcntl
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ai_models_datasets/series_5/tools"))
from workspace import activate, source_path
activate()
import label_series5_campaign as campaign
from label_grounded_sam2 import digest_json, sha256, write_json
from prepare_reviewed_dataset import read_json
from pseudo_mask_filter import POLICY


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.dataset, self.seed = [self.root / n for n in ("source", "dataset", "seed")]
        for p in (self.source, self.dataset, self.seed):
            p.mkdir()
        self.frames = []
        for n, day in enumerate(["2026_07_02"] * 6 + ["2026_07_07", "2026_07_12"]):
            path = self.source / f"{day}_run_1__photo_{n}.jpg"
            Image.new("RGB", (100, 100), (n * 20, 40, 100)).save(path)
            h = sha256(path)
            self.frames.append(dict(id=h, source_sha256=h, image=path.name,
                                    recording_run=day + "_run_1"))
        # Reviewed training images must not be counted twice toward the new-label target.
        write_json(self.dataset / "manifest.json", {"records": [
            dict(id=self.frames[5]["id"], source_name=self.frames[5]["image"])]})
        self.split = self.root / "split.json"
        write_json(self.split, dict(manifest_sha256=sha256(self.dataset / "manifest.json"),
                   days=dict(train=["2026_07_02"], validation=["2026_07_12"], test=["2026_07_07"])))
        self.selection = self.root / "seed-selection.json"
        selection = dict(schema="sidewalkpilot-pseudo-selection-v1", source=str(self.source), count=2,
                         frames=self.frames[:2], allowed_days=["2026_07_02"],
                         baseline_manifest_sha256=sha256(self.dataset / "manifest.json"),
                         baseline_split_sha256=sha256(self.split))
        selection["selection_id"] = digest_json(selection)
        write_json(self.selection, selection)
        self.make_run(self.selection, self.seed)
        self.exclusions = self.root / "exclusions.json"
        write_json(self.exclusions, dict(run_contract_sha256=read_json(self.seed / "manifest.json")["contract_sha256"],
                                        records=[dict(id=self.frames[0]["id"], reason="true driveway")]))
        self.output = self.root / "campaign"

    def make_run(self, selection_path, output, limit=0):
        selection = read_json(selection_path)
        contract = dict(policy=POLICY, runtime={"test": True}, selection_sha256=sha256(selection_path),
                        runner_sha256=sha256(source_path('label_series5_pseudo.py')),
                        filter_sha256=sha256(source_path('pseudo_mask_filter.py')))
        ch = digest_json(contract)
        for name in ("records", "raw", "masks"):
            (output / name).mkdir(exist_ok=True, parents=True)
        write_json(output / "manifest.json", dict(contract=contract, contract_sha256=ch, selection=str(selection_path)))
        rows = selection["frames"][:limit or None]
        for frame in rows:
            labels = np.zeros((100, 100), dtype=np.uint8)
            labels[:, 20:80] = 1
            relative = f"masks/{frame['id']}.png"
            Image.fromarray(labels).save(output / relative)
            asset = dict(path=relative, sha256=sha256(output / relative))
            write_json(output / "records" / (frame["id"] + ".json"), dict(
                frame=frame, contract_sha256=ch, mask=asset, raw=[asset, asset], size=[100, 100],
                filter={"accepted_for_pseudo_training": True, "reasons": []}))
        write_json(output / "status.json", dict(status="complete" if len(rows) == len(selection["frames"])
                   else "pilot-complete", processed=len(rows)))

    def prepare(self, target=2):
        return campaign.prepare(SimpleNamespace(output=self.output, source=self.source, dataset=self.dataset,
            seed_run=self.seed, split=self.split, exclusions=self.exclusions, target=target, batch_size=3, seed=123))

    def job(self, pilot_limit=0, max_batches=0):
        args = SimpleNamespace(campaign=self.output, pilot_limit=pilot_limit,
                               max_batches=max_batches, minimum_free_gb=0)
        def fake_label(args):
            self.make_run(args.selection, args.output, args.limit)
        with patch.object(campaign.labeler, "run", side_effect=fake_label):
            return campaign.execute(args)

    def test_all_sources_screened_but_only_unreviewed_training_day_enters_target(self):
        self.prepare()
        summary = self.job()
        self.assertEqual(summary["processed"], 8)
        self.assertEqual(summary["training_accepted"], 4)
        self.assertEqual(summary["deferred"], 1)
        self.assertEqual(summary["five_d_status"], "needs_correction")
        snapshot = read_json(self.output / "5.C-candidate-snapshot.json")
        eligible = {f["id"] for f in self.frames[1:5]}
        self.assertTrue(set(snapshot["ids"]) <= eligible)
        self.assertEqual(snapshot["count"], 2)
        self.assertFalse(summary["models_trained"])
        queue = read_json(self.output / "correction-queue.json")["records"]
        self.assertEqual(queue[0]["reasons"], ["prior_visual_exclusion"])

    def test_exhaustion_is_not_reported_as_target_success(self):
        self.prepare(target=10000)
        summary = self.job()
        self.assertEqual(summary["five_c_status"], "needs_correction_pool_exhausted")
        self.assertEqual(summary["training_shortfall"], 9996)
        self.assertFalse((self.output / "5.C-candidate-snapshot.json").exists())

    def test_resume_never_duplicates_counts_or_reruns_finished_batches(self):
        self.prepare()
        first = self.job()
        with patch.object(campaign.labeler, "run", side_effect=AssertionError("unexpected rerun")):
            args = SimpleNamespace(campaign=self.output, pilot_limit=0, max_batches=0, minimum_free_gb=0)
            second = campaign.execute(args)
        self.assertEqual(first["processed"], second["processed"])
        self.assertEqual(first["training_accepted"], second["training_accepted"])

    def test_partial_batch_resume(self):
        self.prepare()
        first = self.job(pilot_limit=1)
        self.assertEqual(first["processed"], 3)
        self.assertEqual(first["state"], "paused_after_bounded_run")
        self.assertEqual(self.job()["processed"], 8)

    def test_changed_seed_asset_rejected(self):
        self.prepare()
        path = next((self.seed / "masks").glob("*.png"))
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "asset changed"):
            self.job()

    def test_changed_target_rejected(self):
        self.prepare()
        self.job()
        next((self.output / "targets").glob("*.png")).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "target changed"):
            self.job()

    def test_post_preparation_background_check_can_defer_a_mask(self):
        frame = self.frames[1]
        mask_path = self.seed / "masks" / (frame["id"] + ".png")
        labels = np.ones((100, 100), dtype=np.uint8)
        labels[:10, :10] = 0
        Image.fromarray(labels).save(mask_path)
        record_path = self.seed / "records" / (frame["id"] + ".json")
        record = read_json(record_path)
        record["mask"]["sha256"] = sha256(mask_path)
        for raw in record["raw"]:
            raw["sha256"] = sha256(mask_path)
        write_json(record_path, record)
        self.prepare()
        self.job()
        item = read_json(self.output / "items" / (frame["id"] + ".json"))
        self.assertFalse(item["accepted_screen"])
        self.assertIn("insufficient_background_after_target_preparation", item["reasons"])
        self.assertIsNone(item["target"])

    def test_baseline_split_changes_rejected(self):
        self.prepare()
        write_json(self.split, {})
        with self.assertRaisesRegex(ValueError, "Frozen input changed"):
            self.job()

    def test_duplicate_source_counted_once_and_alias_preserved(self):
        duplicate = self.source / "2026_07_02_run_1__photo_duplicate.jpg"
        duplicate.write_bytes((self.source / self.frames[0]["image"]).read_bytes())
        prepared = self.prepare()
        self.assertEqual(prepared["unique_images"], 8)
        self.assertEqual(prepared["files"], 9)
        summary = self.job()
        self.assertEqual(summary["processed"], 8)
        self.assertEqual(summary["files_covered"], 9)

    def test_duplicate_on_held_out_day_cannot_enter_training(self):
        duplicate = self.source / "2026_07_07_run_1__photo_duplicate.jpg"
        duplicate.write_bytes((self.source / self.frames[1]["image"]).read_bytes())
        self.prepare()
        self.job()
        candidates = read_json(self.output / "training-candidates.json")
        self.assertNotIn(self.frames[1]["id"], {r["id"] for r in candidates["records"]})

    def test_single_writer_lock(self):
        self.prepare()
        with (self.output / "worker.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "already owns"):
                self.job()


if __name__ == "__main__":
    unittest.main()
