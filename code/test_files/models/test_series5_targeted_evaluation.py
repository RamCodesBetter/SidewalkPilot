#!/usr/bin/env python3
"""Protect targeted correction identity, grouping and ignored-pixel semantics."""

import copy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"))
from evaluate_class1_corrections import metrics
from evaluate_targeted_corrections import edit_counts, grouped_metrics, validate_pair, validate_selection


class TargetedEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"created_utc": "date", "contract": {"source_names_sha256": "hash"}, "images": ["a.jpg", "b.jpg"]}
        self.selection = {"kind": "sidewalkpilot-targeted-corrections-v1", "dataset_key": "sp-review:date:hash", "failures": 1, "controls": 1,
                          "frames": [{"position": 1, "image": "a.jpg", "pair": "pair-001", "role": "failure"},
                                     {"position": 2, "image": "b.jpg", "pair": "pair-083", "role": "control"}]}

    def test_selection_identity_order_and_roles(self):
        self.assertEqual(validate_selection(self.selection, self.manifest), "sp-review:date:hash")
        for field, value in (("image", "a.jpg"), ("pair", "pair-001"), ("position", 1), ("role", "failure")):
            selection = copy.deepcopy(self.selection)
            selection["frames"][1][field] = value
            with self.assertRaises(ValueError):
                validate_selection(selection, self.manifest)

    def test_wrong_dataset_rejected(self):
        self.selection["dataset_key"] = "wrong"
        with self.assertRaises(ValueError):
            validate_selection(self.selection, self.manifest)

    def test_pair_matches_original_identity_not_position(self):
        frame = {"position": 2, "pair": "pair-083", "image": "b.jpg", "record": {"source_sha256": "hash", "size": [3, 2]}}
        pair = {"id": "pair-083", "source_name": "b.jpg", "source_sha256": "hash", "size": [3, 2]}
        assignment = {"image": "b.jpg", "A": "sam3", "B": "gsam2"}
        validate_pair(frame, pair, assignment)
        pair["id"] = "pair-002"
        with self.assertRaises(ValueError):
            validate_pair(frame, pair, assignment)

    def test_reference_ignore_is_not_a_removed_pixel(self):
        prediction = np.array([[True, False, True, False]])
        reference = np.array([[0, 1, 255, 0]], dtype=np.uint8)
        self.assertEqual(edit_counts(prediction, reference), {"added_sidewalk_pixels": 1, "removed_sidewalk_pixels": 1,
                                                            "uncertain_pixels": 1, "changed_from_binary_seed_pixels": 3})

    def test_group_separation_and_empty_prediction_penalty(self):
        reference = np.ones((2, 2), dtype=np.uint8)
        good, empty = np.ones((2, 2), bool), np.zeros((2, 2), bool)
        rows = [{"role": "failure", "metrics": {"gsam2": metrics(empty, reference), "sam3": metrics(good, reference)}},
                {"role": "control", "metrics": {"gsam2": metrics(good, reference), "sam3": metrics(good, reference)}}]
        result = grouped_metrics(rows)
        self.assertEqual(result["failure"]["gsam2"]["macro_iou"], 0)
        self.assertEqual(result["control"]["gsam2"]["macro_iou"], 1)
        self.assertEqual(result["all"]["gsam2"]["macro_iou"], .5)
        with self.assertRaises(ValueError):
            grouped_metrics(rows[:1])
        with self.assertRaises(ValueError):
            grouped_metrics([])


if __name__ == "__main__":
    unittest.main()
