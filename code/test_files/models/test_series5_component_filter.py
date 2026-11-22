import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ai_models_datasets/series_5'))
from component_filter import largest_component
from package_component_review import select_cases


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

    def test_targeted_selection_preserves_case_ids_and_controls(self):
        pairs = [dict(id=f'pair-{i:03d}', source_name=f'{i}.jpg') for i in range(1, 41)]
        trials = {p['source_name']:dict(removed_pixels=i if i < 30 else 0)
                  for i,p in enumerate(pairs, 1)}
        ratings = {p['id']:dict(decision='correct' if i % 2 else 'needs_correction', correction_level=3)
                   for i,p in enumerate(pairs, 1)}
        selected, reasons = select_cases(pairs, trials, ratings)
        self.assertEqual((selected,reasons), select_cases(pairs,trials,ratings))
        self.assertEqual(selected[0]['id'], 'pair-008')
        self.assertEqual(len({p['id'] for p in selected}), 20)
        self.assertEqual(sum(trials[p['source_name']]['removed_pixels'] == 0 for p in selected), 4)
        self.assertEqual(sum(r == 'previously accepted mask changed; regression control'
                             for r in reasons.values()), 4)
        with self.assertRaises(ValueError):
            select_cases(pairs[:5], trials, ratings)


if __name__ == '__main__':
    unittest.main()
