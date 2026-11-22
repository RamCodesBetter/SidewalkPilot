#!/usr/bin/env python3
"""Guard random selection and independently drawn polygon-mask semantics."""

from pathlib import Path
import random
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"))
from package_visual_comparison import encode_labels, rasterize
from prepare_random_comparison import random_names


class VisualComparisonTests(unittest.TestCase):
    def test_reproducible_uniform_sample_without_replacement(self):
        names = [f"frame{i:03}.jpg" for i in range(100)]
        selected = random_names(names, 30, 20261029)
        self.assertEqual(selected, random.Random(20261029).sample(sorted(names), 30))
        self.assertEqual(selected, random_names(list(reversed(names)), 30, 20261029))
        self.assertEqual(len(set(selected)), 30)
        self.assertNotEqual(selected, random_names(names, 30, 1))

    def test_invalid_samples_rejected(self):
        for names, count in ((["a", "a"], 1), (["a"], 0), (["a"], 2), (list(map(str, range(201))), 201)):
            with self.assertRaises(ValueError):
                random_names(names, count, 1)

    def test_polygon_exclusion_and_explicit_uncertainty(self):
        entry = {"sidewalk": [[[0, 0], [7, 0], [7, 7], [0, 7]]],
                 "exclude": [[[1, 1], [3, 1], [3, 3], [1, 3]]],
                 "uncertain": [[[2, 2], [4, 2], [4, 4], [2, 4]]], "notes": "test"}
        mask = rasterize(entry, (9, 9))
        self.assertEqual(mask.shape, (9, 9))
        self.assertEqual(mask[0, 0], 1)
        self.assertEqual(mask[1, 1], 0)
        self.assertEqual(mask[2, 2], 255)
        self.assertEqual(mask[8, 8], 0)
        np.testing.assert_array_equal(mask, rasterize(entry, (9, 9)))

    def test_invalid_polygons_rejected(self):
        for polygon in ([[0, 0], [1, 1]], [[0, 0], [1, 1], [9, 8]],
                        [[0, 0], [1, 1], [2.5, 3]], [[0, 0], [1, 1], [-1, 0]]):
            with self.assertRaises(ValueError):
                rasterize({"sidewalk": [polygon], "exclude": [], "uncertain": [], "notes": "x"}, (9, 9))

    def test_rle_round_trip_retains_uncertainty(self):
        for mask in (np.array([[0, 0, 1], [255, 255, 0]], dtype=np.uint8),
                     np.ones((8, 8), dtype=np.uint8), np.zeros((2, 3), dtype=np.uint8)):
            rle = encode_labels(mask)
            decoded = np.repeat(rle[::2], rle[1::2]).reshape(mask.shape)
            np.testing.assert_array_equal(decoded, mask)
        for invalid in (np.array([]), np.array([0, 2, 1])):
            with self.assertRaises(ValueError):
                encode_labels(invalid)


if __name__ == "__main__":
    unittest.main()
