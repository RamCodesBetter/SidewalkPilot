#!/usr/bin/env python3
"""Sampling, binary-mask and blinded-review identity safeguards."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"))
from prepare_paired_review import dhash, image_names, near_time, quotas, timestamp
from package_paired_review import encode_binary
from score_paired_review import score


class SamplingTests(unittest.TestCase):
    def test_guard_inclusive_and_both_neighbors(self):
        for value in (5, 10, 15, 25, 30, 35):
            self.assertTrue(near_time(value, [10, 30]))
        for value in (4.9, 15.1, 24.9, 35.1):
            self.assertFalse(near_time(value, [10, 30]))
        self.assertFalse(near_time(1, []))

    def test_timestamp_and_exact_filename_extraction(self):
        a = "2026_07_02_run_1__photo_20260702_163034_981296.jpg"
        b = a.replace("163034", "163040")
        self.assertAlmostEqual(timestamp(b) - timestamp(a), 6)
        self.assertEqual(list(image_names({a: ["unrelated", "images/" + b]})), [a, b])

    def test_quotas_preserve_total(self):
        q = quotas({"a": range(20), "b": range(70), "c": range(10)}, 11)
        self.assertEqual(sum(q.values()), 11)
        self.assertEqual(q, {"a": 2, "b": 8, "c": 1})

    def test_hash_identical_image(self):
        image = Image.fromarray(np.arange(81, dtype=np.uint8).reshape(9, 9))
        self.assertEqual(dhash(image), dhash(image.copy()))

    def test_rle_roundtrip_including_empty_positive_mask(self):
        for mask in (np.zeros((3, 4)), np.ones((3, 4)), np.eye(4), np.array([[1, 1, 0, 0, 1]])):
            rle = encode_binary(mask)
            decoded, value = [], rle["first"]
            for length in rle["lengths"]:
                decoded.extend([value] * length); value = 1 - value
            np.testing.assert_array_equal(decoded, mask.ravel())
        with self.assertRaises(ValueError):
            encode_binary(np.array([[255]]))


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"package_id": "package", "selection_sha256": "selection", "pairs": [
            {"id": "pair-001", "source_name": "one.jpg", "candidates": {"A": {"mask_sha256": "a"}, "B": {"mask_sha256": "b"}}}]}
        self.mapping = {"selection_sha256": "selection", "pairs": {"pair-001": {"image": "one.jpg", "A": "sam3", "B": "gsam2"}}}
        self.review = {"kind": "sidewalkpilot-paired-review-v1", "package_id": "package", "selection_sha256": "selection",
                       "review_scope": {"kind": "class", "class_ids": [1]}, "complete": True, "decisions": {}}

    def test_missing_decisions_are_not_correct_despite_claimed_completion(self):
        result = score(self.manifest, self.mapping, self.review)
        self.assertFalse(result["complete"])
        self.assertEqual(result["methods"]["sam3"]["marked_correct_fraction_of_all_images"], 0)

    def test_mapping_not_side_determines_method(self):
        self.review["decisions"] = {"pair-001": {
            "A": {"decision": "correct", "mask_sha256": "a", "notes": "", "effort": "none"},
            "B": {"decision": "needs_correction", "mask_sha256": "b", "notes": "edge", "effort": "minor"}}}
        result = score(self.manifest, self.mapping, self.review)
        self.assertTrue(result["complete"])
        self.assertEqual(result["methods"]["sam3"]["counts"]["correct"], 1)
        self.assertEqual(result["methods"]["gsam2"]["counts"]["needs_correction"], 1)
        bad = deepcopy(self.review); bad["decisions"]["pair-001"]["A"]["mask_sha256"] = "other"
        with self.assertRaises(ValueError):
            score(self.manifest, self.mapping, bad)

    def test_foreign_package_and_unknown_pair_rejected(self):
        bad = deepcopy(self.review); bad["package_id"] = "other"
        with self.assertRaises(ValueError):
            score(self.manifest, self.mapping, bad)

    def test_automatic_repair_names_and_measured_inspection_are_separate(self):
        self.mapping['method_names'] = ['baseline', 'bounded_sam2']
        self.mapping['pairs']['pair-001'].update(A='bounded_sam2', B='baseline')
        self.review['inspection_active_seconds'] = {'pair-001': {'A': 3.5, 'B': 2.}}
        result = score(self.manifest, self.mapping, self.review)
        self.assertEqual(result['methods']['bounded_sam2']['inspection_active_seconds'], 3.5)
        self.assertFalse(result['complete'])
        self.assertEqual(result['methods']['baseline']['marked_correct_fraction_of_all_images'], 0)

    def test_invalid_timings_and_mapping_identity_rejected(self):
        for timing in ({'bad': {}}, {'pair-001': {'C': 3}}, {'pair-001': {'A': -1}},
                       {'pair-001': {'A': float('nan')}}, {'pair-001': {'A': True}}):
            bad = deepcopy(self.review)
            bad['inspection_active_seconds'] = timing
            with self.assertRaises(ValueError):
                score(self.manifest, self.mapping, bad)
        mapping = {**self.mapping, 'package_id': 'other'}
        with self.assertRaises(ValueError):
            score(self.manifest, mapping, self.review)

    def test_correction_levels_and_legacy_unspecified_levels(self):
        self.review['decisions'] = {'pair-001': {
            'A': {'decision':'needs_correction', 'mask_sha256':'a', 'notes':'', 'effort':'minor', 'correction_level':2},
            'B': {'decision':'needs_correction', 'mask_sha256':'b', 'notes':'', 'effort':'major'}}}
        result = score(self.manifest, self.mapping, self.review)
        self.assertEqual(result['methods']['sam3']['correction_levels'], {'moderate':1})
        self.assertEqual(result['methods']['gsam2']['correction_levels'], {'not_specified':1})
        self.assertEqual(result['methods']['sam3']['estimated_effort'], {'minor':1})

    def test_invalid_severity_or_level_on_correct_rejected(self):
        for state, level in [('needs_correction', 0), ('needs_correction', 4),
                             ('needs_correction', '1'), ('needs_correction', True),
                             ('correct', 1), ('uncertain', 2), ('unreviewed', 3)]:
            bad = deepcopy(self.review)
            bad['decisions'] = {'pair-001': {'A': {'decision':state, 'mask_sha256':'a',
                                'notes':'', 'effort':'not_estimated', 'correction_level':level}}}
            with self.assertRaises(ValueError):
                score(self.manifest, self.mapping, bad)
        bad = deepcopy(self.review); bad["decisions"] = {"fake": {}}
        with self.assertRaises(ValueError):
            score(self.manifest, self.mapping, bad)


if __name__ == "__main__":
    unittest.main()
