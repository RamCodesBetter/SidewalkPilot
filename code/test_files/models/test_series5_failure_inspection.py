#!/usr/bin/env python3
"""Keep diagnostic grouping and overlap distinct from correctness."""

from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools"))
from workspace import activate
activate()
from inspect_paired_failures import detection_summary, mask_diagnostics, review_group


class FailureInspectionTests(unittest.TestCase):
    def test_review_groups(self):
        self.assertEqual(review_group("needs_correction", "needs_correction"), "both_need_correction")
        self.assertEqual(review_group("needs_correction", "correct"), "sam3_only_correct")
        self.assertEqual(review_group("correct", "needs_correction"), "gsam2_only_correct")
        self.assertEqual(review_group("correct", "correct"), "both_correct")
        self.assertEqual(review_group("uncertain", "correct"), "other")

    def test_mask_overlap_is_not_accuracy(self):
        a = np.array([[True, False], [True, False]])
        b = np.array([[True, True], [False, False]])
        result = mask_diagnostics(a, b)
        self.assertAlmostEqual(result["intermodel_iou_not_accuracy"], 1 / 3)
        self.assertEqual(result["gsam2_only_pixels"], 1)
        self.assertEqual(result["sam3_only_pixels"], 1)
        self.assertEqual(result["gsam2_coverage"], .5)

    def test_empty_and_shape_mismatch(self):
        empty = np.zeros((2, 2), dtype=bool)
        self.assertIsNone(mask_diagnostics(empty, empty)["intermodel_iou_not_accuracy"])
        with self.assertRaises(ValueError):
            mask_diagnostics(empty, np.zeros((3, 2), dtype=bool))

    def test_detection_and_quality_gate_are_separate(self):
        self.assertEqual(detection_summary([])["gsam2_detections"], 0)
        result = detection_summary([{"accepted": False, "detector_score": .9, "sam_quality": .3}])
        self.assertEqual(result["gsam2_detections"], 1)
        self.assertEqual(result["gsam2_accepted"], 0)
        self.assertIsNone(result["gsam2_max_accepted_quality"])


if __name__ == "__main__":
    unittest.main()
