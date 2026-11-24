import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ai_models_datasets/series_5/tools'))
from workspace import activate
activate()
from component_filter import largest_component


class ComponentFilterTests(unittest.TestCase):
    def test_removes_islands_without_adding_or_mutating(self):
        mask = np.zeros((30, 40), bool)
        mask[10:28, 5:35] = True
        mask[3:5, 2:4] = True
        before = mask.copy()
        result, report = largest_component(mask)
        self.assertEqual(report['removed_pixels'], 4)
        self.assertEqual(report['components_before'], 2)
        self.assertFalse(result[3:5, 2:4].any())
        self.assertTrue(result[10:28, 5:35].all())
        self.assertFalse((result & ~mask).any())
        np.testing.assert_array_equal(mask, before)

    def test_holes_and_connected_branches_are_not_modified(self):
        mask = np.zeros((30, 40), bool)
        mask[5:28, 5:35] = True
        mask[10:15, 10:15] = False
        mask[20:23, 35:40] = True
        result, report = largest_component(mask)
        self.assertEqual(report['removed_pixels'], 0)
        np.testing.assert_array_equal(result, mask)

    def test_diagonal_connection_counts_as_one_component(self):
        mask = np.eye(10, dtype=bool)
        result, report = largest_component(mask)
        self.assertEqual(report['components_before'], 1)
        np.testing.assert_array_equal(result, mask)

    def test_tied_components_are_preserved(self):
        mask = np.zeros((10, 10), bool)
        mask[1:3, 1:3] = mask[7:9, 7:9] = True
        result, report = largest_component(mask)
        self.assertEqual(report['action'], 'deferred')
        self.assertIn('tied_largest_components', report['flags'])
        np.testing.assert_array_equal(result, mask)

    def test_empty_and_full(self):
        for value in (False, True):
            mask = np.full((8, 9), value, dtype=bool)
            result, report = largest_component(mask)
            np.testing.assert_array_equal(result, mask)
            self.assertEqual(report['removed_pixels'], 0)

    def test_invalid_labels_and_shapes(self):
        for mask in (np.zeros((0, 4)), np.zeros(5), np.zeros((1, 2, 3)),
                     np.full((2, 2), 255), np.full((2, 2), np.nan)):
            with self.assertRaises(ValueError):
                largest_component(mask)

    def test_idempotent(self):
        mask = np.zeros((20, 20), bool)
        mask[5:15, 5:15] = mask[1, 1] = True
        first, _ = largest_component(mask)
        second, report = largest_component(first)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(report['removed_pixels'], 0)

if __name__ == '__main__':
    unittest.main()
