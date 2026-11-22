#!/usr/bin/env python3
"""Exercise 5.A split isolation, partial supervision, architecture and checkpoints."""

import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools"))
from workspace import activate
activate()
from series_5_a_sidewalkpilot_trainer import (
    DEFAULTS, MixedBatchSampler, SidewalkDataset, atomic_checkpoint, confusion_counts,
    confusion_metrics, evaluate, load_checkpoint, make_model, segmentation_loss,
    select_precision, train, train_mode, training_config, validate_split,
)


class BinaryTrainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def split_fixture(self):
        rows = [{"id": str(i), "included": True, "recording_run": f"2026_07_{i + 1:02d}_run_1",
                 "supervision": "binary-reference", "pixel_counts": {"0": 10, "1": 20}} for i in range(3)]
        split = {"schema": "sidewalkpilot-binary-day-split-v1", "manifest_sha256": "fixed",
                 "partitions": {"train": ["0"], "validation": ["1"], "test": ["2"]},
                 "days": {"train": ["2026_07_01"], "validation": ["2026_07_02"], "test": ["2026_07_03"]}}
        return {"records": rows}, split

    def image_row(self, name, labels, kind="binary-reference"):
        labels = np.asarray(labels, dtype=np.uint8)
        Image.fromarray(np.repeat(labels[:, :, None], 3, axis=2)).save(self.root / (name + ".jpg"))
        Image.fromarray(labels).save(self.root / (name + ".png"))
        return {"id": name, "image": name + ".jpg", "mask": name + ".png", "supervision": kind}

    def test_complete_grouped_split(self):
        manifest, split = self.split_fixture()
        self.assertEqual(list(validate_split(manifest, split, "fixed")), ["train", "validation", "test"])

    def test_day_leak_rejected_even_for_different_runs(self):
        manifest, split = self.split_fixture()
        manifest["records"][1]["recording_run"] = "2026_07_01_run_2"
        split["days"]["validation"] = ["2026_07_01"]
        with self.assertRaisesRegex(ValueError, "day leaks"):
            validate_split(manifest, split, "fixed")

    def test_duplicate_unknown_excluded_missing_and_empty_splits_rejected(self):
        for ids in (["0"], ["1", "1"], ["missing"], []):
            manifest, split = self.split_fixture()
            split["partitions"]["validation"] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                validate_split(manifest, split, "fixed")
        manifest, split = self.split_fixture()
        manifest["records"][1]["included"] = False
        with self.assertRaises(ValueError):
            validate_split(manifest, split, "fixed")
        manifest, split = self.split_fixture()
        manifest["records"].append({**manifest["records"][0], "id": "unassigned"})
        with self.assertRaisesRegex(ValueError, "cover"):
            validate_split(manifest, split, "fixed")

    def test_split_hash_and_negative_supervision_required(self):
        manifest, split = self.split_fixture()
        with self.assertRaisesRegex(ValueError, "manifest"):
            validate_split(manifest, split, "changed")
        manifest["records"][0]["pixel_counts"] = {"1": 10, "255": 20}
        with self.assertRaisesRegex(ValueError, "negative"):
            validate_split(manifest, split, "fixed")

    def test_loader_nearest_masks_and_deterministic_augmentation(self):
        row = self.image_row("a", [[0, 1, 255], [1, 255, 0]])
        data = SidewalkDataset(self.root, [row], (6, 4), augment=True)
        first, second = data[(0, 72)], data[(0, 72)]
        torch.testing.assert_close(first[0], second[0])
        torch.testing.assert_close(first[1], second[1])
        self.assertEqual(set(first[1].flatten().tolist()), {0, 1, 255})
        self.assertEqual(tuple(first[0].shape), (3, 4, 6))
        native = SidewalkDataset(self.root, [row], (6, 4), original_targets=True)[0]
        self.assertEqual(tuple(native[1].shape), (2, 3))

    def test_sampler_has_negatives_in_every_batch_and_covers_partial_pool(self):
        rows = [{"supervision": "binary-reference"}] * 3 + [{"supervision": "sidewalk-positive-only"}] * 11
        sampler = MixedBatchSampler(rows, 8, 123)
        batches = list(sampler)
        self.assertEqual(batches, list(sampler))
        self.assertEqual(len(batches), 3)
        self.assertEqual({index for batch in batches for index, _ in batch if index >= 3}, set(range(3, 14)))
        for batch in batches:
            self.assertEqual(len(batch), 8)
            self.assertEqual(sum(index < 3 for index, _ in batch), 4)
        sampler.epoch = 1
        self.assertNotEqual(batches, list(sampler))

    def test_reference_only_sampler_and_invalid_settings(self):
        rows = [{"supervision": "binary-reference"}] * 5
        self.assertEqual(len(list(MixedBatchSampler(rows, 4, 1))), 2)
        for batch_size in (0, 1, 3):
            with self.assertRaises(ValueError):
                MixedBatchSampler(rows, batch_size, 1)
        with self.assertRaises(ValueError):
            MixedBatchSampler([{"supervision": "sidewalk-positive-only"}], 4, 1)

    def test_ignore_pixels_have_zero_loss_gradient(self):
        logits = torch.zeros(2, 2, 1, 3, requires_grad=True)
        targets = torch.tensor([[[0, 1, 255]], [[1, 255, 255]]])
        loss, binary, partial = segmentation_loss(logits, targets, torch.tensor([True, False]), 0.25)
        self.assertAlmostEqual(loss.item(), 1.25 * np.log(2), places=6)
        loss.backward()
        self.assertEqual(float(logits.grad[0, :, 0, 2].abs().sum()), 0)
        self.assertEqual(float(logits.grad[1, :, 0, 1:].abs().sum()), 0)
        self.assertGreater(float(logits.grad[0, :, 0, :2].abs().sum()), 0)

    def test_all_ignored_is_zero_not_nan(self):
        logits = torch.randn(2, 2, 2, 3, requires_grad=True)
        loss, _, _ = segmentation_loss(logits, torch.full((2, 2, 3), 255), torch.tensor([True, False]))
        self.assertEqual(loss.item(), 0)
        loss.backward()
        self.assertEqual(logits.grad.abs().sum().item(), 0)

    def test_partial_group_not_amplified_by_duplicate_examples(self):
        logits = torch.randn(2, 2, 1, 3)
        targets = torch.tensor([[[0, 1, 255]], [[1, 255, 255]]])
        base = segmentation_loss(logits, targets, torch.tensor([True, False]))[0]
        expanded = segmentation_loss(torch.cat((logits[:1], logits[1:].repeat(8, 1, 1, 1))),
                                     torch.cat((targets[:1], targets[1:].repeat(8, 1, 1))),
                                     torch.tensor([True] + [False] * 8))[0]
        torch.testing.assert_close(base, expanded)

    def test_metrics_ignore_unknown_pixels_and_count_false_positives(self):
        target = torch.tensor([[0, 0, 1, 1, 255]])
        prediction = torch.tensor([[0, 1, 0, 1, 1]])
        counts = confusion_counts(prediction, target)
        torch.testing.assert_close(counts, torch.ones((2, 2), dtype=torch.int64))
        metrics = confusion_metrics(counts)
        self.assertAlmostEqual(metrics["sidewalk_iou"], 1 / 3)
        self.assertEqual(metrics["f1"], 0.5)
        self.assertIsNone(confusion_metrics(torch.zeros((2, 2), dtype=torch.int64))["sidewalk_iou"])

    def test_evaluation_keeps_partial_metrics_separate(self):
        rows = [self.image_row("strong", [[0, 1, 255], [0, 1, 1]]),
                self.image_row("partial", [[255, 1, 255], [255, 1, 1]], "sidewalk-positive-only")]

        class AllSidewalk(torch.nn.Module):
            def forward(self, images):
                logits = torch.zeros(images.shape[0], 2, *images.shape[-2:])
                logits[:, 1] = 1
                return {"out": logits}

        result = evaluate(AllSidewalk(), self.root, rows, (6, 4), torch.device("cpu"), "fp32")
        self.assertEqual(result["binary_reference"]["images"], 1)
        self.assertAlmostEqual(result["binary_reference"]["sidewalk_iou"], 3 / 5)
        self.assertEqual(result["binary_reference"]["fp"], 2)
        self.assertEqual(result["partial_labels"]["known_sidewalk_recall_only"], 1)
        self.assertNotIn("precision", result["partial_labels"])

    def test_architecture_shape_parameter_count_and_backbone_bn(self):
        model = make_model("none")
        self.assertEqual(sum(p.numel() for p in model.parameters()), 3218308)
        train_mode(model)
        self.assertTrue(model.classifier.cbr[1].training)
        self.assertFalse(any(layer.training for layer in model.backbone.modules()
                             if isinstance(layer, torch.nn.modules.batchnorm._BatchNorm)))
        output = model(torch.randn(2, 3, 64, 96))["out"]
        self.assertEqual(tuple(output.shape), (2, 2, 64, 96))
        output.mean().backward()
        self.assertTrue(any(p.grad is not None for p in model.backbone.parameters()))

    def test_checkpoint_round_trip_no_download_and_uppercase_name(self):
        cfg = training_config(SimpleNamespace(**{**DEFAULTS, "smoke": True, "workers": 0}), "fp32")
        self.assertEqual(cfg["model_name"], "5.A")
        model = make_model("none").eval()
        path = self.root / "last.pt"
        atomic_checkpoint(path, {"schema": "sidewalkpilot-series5-binary-checkpoint-v1", "config": cfg,
                                 "model": model.state_dict()})
        restored, state = load_checkpoint(path)
        restored.eval()
        image = torch.randn(1, 3, 64, 96)
        with torch.inference_mode():
            torch.testing.assert_close(model(image)["out"], restored(image)["out"])
        self.assertFalse(path.with_suffix(".tmp").exists())

    def test_precision_and_configuration_checks(self):
        self.assertEqual(select_precision("auto", torch.device("cpu")), "fp32")
        for precision in ("fp16", "bf16", "wrong"):
            with self.assertRaises(ValueError):
                select_precision(precision, torch.device("cpu"))
        args = SimpleNamespace(**{**DEFAULTS, "smoke": False, "workers": 0})
        for key, value in (("batch_size", 3), ("partial_weight", float("nan")), ("backbone_lr", 0),
                           ("width", 1), ("epochs", 0)):
            invalid = copy.copy(args)
            setattr(invalid, key, value)
            with self.subTest(key=key), self.assertRaises(ValueError):
                training_config(invalid, "fp32")

    def test_interrupted_epoch_resume_matches_uninterrupted_training(self):
        labels = np.zeros((64, 96), dtype=np.uint8)
        labels[:, 48:] = 1
        strong = self.image_row("strong", labels)
        partial = self.image_row("partial", np.where(labels == 1, 1, 255), "sidewalk-positive-only")
        partitions = {"train": [strong, partial], "validation": [strong], "test": []}
        (self.root / "manifest.json").write_text("{}")
        (self.root / "split.json").write_text("{}")
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        args = SimpleNamespace(**{**DEFAULTS, "dataset": self.root, "split": self.root / "split.json",
                                  "output": Path(external.name) / "resumed", "device": "cpu", "precision": "fp32",
                                  "weights": "none", "width": 96, "height": 64, "batch_size": 2, "epochs": 2,
                                  "workers": 0, "resume": False, "smoke": False, "wandb": False})
        calls = 0

        def interrupted_evaluate(*positional, **keywords):
            nonlocal calls
            calls += 1
            if calls == 2:
                # Reproduce an interruption after preview directory creation.
                keywords["preview_dir"].mkdir()
                raise KeyboardInterrupt()
            return evaluate(*positional, **keywords)

        with mock.patch("series_5_a_sidewalkpilot_trainer.load_partition", return_value=partitions):
            with mock.patch("series_5_a_sidewalkpilot_trainer.evaluate", side_effect=interrupted_evaluate):
                with self.assertRaises(KeyboardInterrupt):
                    train(args)
            args.resume = True
            train(args)
            resumed, state = load_checkpoint(args.output / "last.pt")
            self.assertEqual(state["epoch"], 2)
            self.assertEqual(len(state["history"]), 2)
            args.resume, args.output = False, Path(external.name) / "continuous"
            train(args)
            continuous, other_state = load_checkpoint(args.output / "last.pt")
        for key, tensor in resumed.state_dict().items():
            torch.testing.assert_close(tensor, continuous.state_dict()[key], rtol=0, atol=0)
        self.assertEqual(state["best_iou"], other_state["best_iou"])


if __name__ == "__main__":
    unittest.main()
