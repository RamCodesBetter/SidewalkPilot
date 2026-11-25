#!/usr/bin/env python3
"""Sampling, binary-mask and blinded-review identity safeguards."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ai_models_datasets/series_5/tools"))
from workspace import activate
activate()
from prepare_paired_review import dhash, image_names, near_time, quotas, timestamp


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


if __name__ == "__main__":
    unittest.main()
