"""The unified viewer must export exact class IDs, including ignored pixels."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ai_models_datasets/series_5/tools"))
from workspace import activate
activate()
import package_model_lab as review


class ModelReviewTests(unittest.TestCase):
    def test_mask_record_preserves_ignore_and_exact_rle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            labels = np.array([[0, 1, 255], [255, 255, 1]], dtype=np.uint8)
            path = root / "mask.png"
            Image.fromarray(labels).save(path)
            result = review.mask_record(path, root, labels)
            restored = np.repeat(result["rle"][::2], result["rle"][1::2]).reshape(labels.shape)
            np.testing.assert_array_equal(restored, labels)
            self.assertEqual(result["positive_pixels"], 2)
            self.assertEqual(result["ignored_pixels"], 3)
            with self.assertRaises(ValueError):
                review.mask_record(path, root, np.array([[2]], dtype=np.uint8))
