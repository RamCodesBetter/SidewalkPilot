#!/usr/bin/env python3
"""Check frozen-model packaging, mask identity, and test-partition isolation."""

import base64
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools"))
import package_model_review as review


class ModelReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset = self.root / "dataset"
        self.dataset.mkdir()

    def fixture(self):
        (self.dataset / "manifest.json").write_text('{}')
        split, checkpoint = self.root / "split.json", self.root / "best.pt"
        split.write_text('{"test": ["a"]}')
        checkpoint.write_bytes(b'checkpoint fixture, mocked loader')
        labels = np.array([[1, 1, 255, 255]] * 4, dtype=np.uint8)
        Image.fromarray(np.full((4, 4, 3), 120, dtype=np.uint8)).save(self.dataset / "a.jpg")
        Image.fromarray(labels).save(self.dataset / "a.png")
        row = {"id": "a", "source_name": "a.jpg", "image": "a.jpg", "mask": "a.png",
               "source_sha256": review.sha256(self.dataset / "a.jpg"),
               "mask_sha256": review.sha256(self.dataset / "a.png"),
               "recording_run": "2026_07_07_run_1", "supervision": "sidewalk-positive-only"}
        identity = {"manifest_sha256": review.sha256(self.dataset / "manifest.json"),
                    "split_sha256": review.sha256(split)}
        state = {"data_identity": identity, "epoch": 8,
                 "config": {"model_name": "5.A", "width": 4, "height": 4, "smoke_only": False}}
        args = SimpleNamespace(dataset=self.dataset, split=split, checkpoint=checkpoint,
                               output=self.root / "viewer", partition="test", device="cpu", precision="fp32")

        class Model(torch.nn.Module):
            def forward(self, image):
                logits = torch.zeros((1, 2, 2, 2))
                logits[:, 1, :, 1] = 3
                return {"out": logits}

        return args, row, state, Model()

    def test_output_protects_dataset_and_inputs(self):
        args, _, _, _ = self.fixture()
        for output in (self.dataset, self.dataset / "viewer", self.root, args.checkpoint, args.split):
            with self.subTest(output=output), self.assertRaises(ValueError):
                review.check_destination(output, self.dataset, args.checkpoint, args.split)

    def test_reject_smoke_or_changed_split(self):
        _, _, state, _ = self.fixture()
        review.validate_identity(state, state["data_identity"])
        with self.assertRaisesRegex(ValueError, "identity differs"):
            review.validate_identity(state, {})
        state["config"]["smoke_only"] = True
        with self.assertRaisesRegex(ValueError, "smoke checkpoint"):
            review.validate_identity(state, state["data_identity"])

    def test_mask_record_preserves_ignore_and_exact_rle(self):
        args, _, _, _ = self.fixture()
        labels = np.array([[0, 1, 255], [255, 255, 1]], dtype=np.uint8)
        path = self.root / "mask.png"
        Image.fromarray(labels).save(path)
        result = review.mask_record(path, self.root, labels)
        restored = np.repeat(result["rle"][::2], result["rle"][1::2]).reshape(labels.shape)
        np.testing.assert_array_equal(restored, labels)
        self.assertEqual(result["positive_pixels"], 2)
        self.assertEqual(result["ignored_pixels"], 3)
        with self.assertRaises(ValueError):
            review.mask_record(path, self.root, np.array([[2]], dtype=np.uint8))

    def test_package_is_prediction_only_and_keeps_references(self):
        args, row, state, model = self.fixture()
        original = {p: review.sha256(p) for p in self.root.rglob('*') if p.is_file()}
        with mock.patch.object(review, "load_partition", return_value={"test": [row], "train": []}) as load, \
             mock.patch.object(review, "load_checkpoint", return_value=(model, state)):
            result = review.package(args)
        load.assert_called_once_with(self.dataset, args.split)
        manifest = json.loads((args.output / "manifest.json").read_text())
        self.assertEqual(result["images"], 1)
        self.assertEqual(manifest["partial_references"], 1)
        self.assertEqual(manifest["binary_references"], 0)
        self.assertFalse(manifest["metrics_computed"])
        self.assertTrue(manifest["test_predictions_generated"])
        self.assertEqual(manifest["checkpoint_epoch"], 8)
        self.assertEqual(manifest["frames"][0]["id"], row["id"])
        prediction = np.array(Image.open(args.output / "predictions/001.png"))
        self.assertEqual(prediction.shape, (4, 4))
        self.assertEqual(set(np.unique(prediction)), {0, 1})
        self.assertEqual(base64.b64decode(manifest["frames"][0]["prediction"]["png_base64"]),
                         (args.output / "predictions/001.png").read_bytes())
        self.assertEqual(review.sha256(args.output / "references/001.png"), row["mask_sha256"])
        for path, expected in original.items():
            self.assertEqual(review.sha256(path), expected)
        self.assertFalse(list(args.output.rglob('*.pt')))
        for name, expected in json.loads((args.output / "integrity-check.json").read_text())["files_sha256"].items():
            self.assertEqual(review.sha256(args.output / name), expected)
        preserved = {name: review.sha256(args.output / name) for name in
                     ("manifest.json", "data.js", "predictions/001.png", "references/001.png", "images/001.jpg")}
        user_review = args.output / "my-review.json"
        user_review.write_text('{"notes": "Keep this review"}')
        refreshed = review.refresh_viewer_assets(args.output)
        self.assertEqual(refreshed["package_id"], manifest["package_id"])
        for name, expected in preserved.items():
            self.assertEqual(review.sha256(args.output / name), expected)
        self.assertEqual(user_review.read_text(), '{"notes": "Keep this review"}')
        (args.output / "predictions/001.png").write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, "Package file changed"):
            review.refresh_viewer_assets(args.output)
        with self.assertRaises(ValueError):
            review.package(args)

    def test_changed_source_fails_without_publishing_partial_viewer(self):
        args, row, state, model = self.fixture()
        row["source_sha256"] = 'changed'
        with mock.patch.object(review, "load_partition", return_value={"test": [row]}), \
             mock.patch.object(review, "load_checkpoint", return_value=(model, state)), \
             self.assertRaisesRegex(ValueError, "changed during export"):
            review.package(args)
        self.assertFalse(args.output.exists())


if __name__ == "__main__":
    unittest.main()
