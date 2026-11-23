#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parents[2] / "ai_models_datasets" / "series_5" / "tools"
sys.path.insert(0, str(HERE))
from workspace import activate, source_path
activate()
from compare_class1_methods import aggregate, checked_asset, check_identity
from evaluate_class1_corrections import metrics
from label_grounded_sam2 import sha256, build_caption, compose_mask


class MethodComparisonTests(unittest.TestCase):
    def test_sidewalk_first_is_one_concept_without_reference_inputs(self):
        config = json.loads((source_path('label_config_sidewalk_first.json')).read_text())
        taxonomy = json.loads((source_path('taxonomy.json')).read_text())
        self.assertEqual(config["prompt_groups"], [[1]])
        self.assertEqual(config["diagnostic_class_ids"], [1])
        self.assertEqual(config["prompt_overrides"], {"1": ["sidewalk"]})
        caption, spans = build_caption([{**taxonomy["classes"][1], "prompts": config["prompt_overrides"]["1"]}])
        self.assertEqual(caption, "sidewalk.")
        self.assertEqual({s[0] for s in spans}, {1})
        mask = np.array([[True, False, True]])
        output = compose_mask([(1, mask, .8)], mask.shape, taxonomy, .05)
        np.testing.assert_array_equal(output, [[1, 255, 1]])

    def test_failures_stay_in_mean_and_empty_is_undefined(self):
        ref = np.array([[1, 0]], np.uint8)
        good = metrics(ref == 1, ref)
        failed = metrics(np.zeros(ref.shape, bool), ref)
        result = aggregate([{"metrics": {"test": good}}, {"metrics": {"test": failed}}])["test"]
        self.assertEqual(result["macro_iou"], .5)
        self.assertEqual(result["micro"]["fn"], 1)
        self.assertEqual(result["images"], 2)
        empty = metrics(np.zeros(ref.shape, bool), np.full(ref.shape, 255, np.uint8))
        self.assertIsNone(aggregate([{"metrics": {"test": empty}}])["test"]["macro_iou"])

    def test_missing_method_rejected(self):
        with self.assertRaises(ValueError):
            aggregate([{"metrics": {"a": {}}}, {"metrics": {"b": {}}}])

    def test_hash_shape_ids_and_identity_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "mask.png"
            Image.fromarray(np.array([[1, 255]], np.uint8)).save(path)
            entry = {"path": "mask.png", "sha256": sha256(path)}
            hashes = {}
            np.testing.assert_array_equal(checked_asset(root, entry, (1, 2), hashes), [[True, False]])
            self.assertEqual(len(hashes), 1)
            with self.assertRaises(ValueError):
                checked_asset(root, entry, (2, 1), {})
            with self.assertRaises(ValueError):
                checked_asset(root, {**entry, "sha256": "bad"}, (1, 2), {})
            Image.fromarray(np.array([[1, 0]], np.uint8)).save(path)
            with self.assertRaises(ValueError):
                checked_asset(root, {**entry, "sha256": sha256(path)}, (1, 2), {})
        frame = {"image": "one.jpg", "record": {"source_sha256": "abc", "size": [2, 1]}}
        record = {"image": "one.jpg", "source_sha256": "abc", "size": [2, 1]}
        check_identity(record, frame)
        for replacement in ({"image": "two.jpg"}, {"source_sha256": "bad"}, {"size": [1, 2]}):
            with self.assertRaises(ValueError):
                check_identity({**record, **replacement}, frame)


if __name__ == "__main__":
    unittest.main()
