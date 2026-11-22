"""Automatic repairs must be bounded, reproducible, and independent of references."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parents[2] / 'ai_models_datasets/series_5/tools'
sys.path.insert(0, str(HERE))
from automatic_repair import (automatic_prompts, bounded_merge, iou, regions,
                              run, validate_config, validate_run_record)
from label_grounded_sam2 import save_mask, sha256
from prepare_automatic_repair_review import choose_frames, collect_history
from evaluate_automatic_repair import metrics
from PIL import Image


class AutomaticRepairTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((HERE / 'automatic_repair_config.json').read_text())
        self.base = np.zeros((100, 160), bool)
        self.base[25:90, 35:125] = True

    def test_invalid_configuration(self):
        for key, value in [('grid_cells_per_axis', 1), ('minimum_sam_quality', 1),
                           ('maximum_change_fraction', -1), ('boundary_pixels_at_720p', 0)]:
            cfg = {**self.cfg, key: value}
            with self.assertRaises(ValueError):
                validate_config(cfg)

    def test_prompts_are_deterministic_and_disjoint(self):
        prompts, _, _ = automatic_prompts(self.base, self.cfg)
        self.assertEqual(prompts, automatic_prompts(self.base.copy(), self.cfg)[0])
        self.assertEqual(len(prompts), 2)
        for row in prompts:
            self.assertEqual(len(row['points']), len(set(map(tuple, row['points']))))
            self.assertEqual(set(row['labels']), {0, 1})
            for (x, y), value in zip(row['points'], row['labels']):
                self.assertEqual(bool(self.base[y, x]), bool(value))
        self.assertNotEqual(prompts[0], prompts[1])

    def test_empty_and_full_masks_do_not_supply_two_sided_prompts(self):
        for mask in (np.zeros_like(self.base), np.ones_like(self.base)):
            self.assertEqual(automatic_prompts(mask, self.cfg)[0], [])

    def test_narrow_agreed_edge_changes_are_allowed(self):
        candidate = self.base.copy()
        candidate[30:70, 34] = True
        result, report = bounded_merge(self.base, [candidate, candidate], self.cfg)
        self.assertEqual(report['action'], 'bounded_repair_proposal')
        self.assertEqual(report['changed_pixels'], 40)
        np.testing.assert_array_equal(result, candidate)

    def test_no_single_pass_correction(self):
        result, report = bounded_merge(self.base, [~self.base], self.cfg)
        self.assertEqual(report['action'], 'deferred')
        np.testing.assert_array_equal(result, self.base)

    def test_disagreement_does_not_change_pixel(self):
        candidate = self.base.copy()
        candidate[30:70, 34] = True
        result, _ = bounded_merge(self.base, [candidate, self.base], self.cfg)
        np.testing.assert_array_equal(result, self.base)

    def test_deep_interior_and_large_holes_preserved(self):
        base = self.base.copy()
        base[45:55, 60:70] = False
        candidate = base.copy()
        candidate[45:55, 60:70] = True
        candidate[60:64, 80:84] = False
        result, _ = bounded_merge(base, [candidate, candidate], self.cfg)
        self.assertFalse(result[50, 65])
        self.assertTrue(result[61, 81])
        allowed, _, _, protected = regions(base, self.cfg)
        np.testing.assert_array_equal(result[~allowed], base[~allowed])
        np.testing.assert_array_equal(result[protected], base[protected])

    def test_thin_hole_needs_model_consensus(self):
        base = self.base.copy()
        base[45, 60:65] = False
        candidate = base.copy()
        candidate[45, 60:65] = True
        result, report = bounded_merge(base, [candidate, candidate], self.cfg)
        self.assertEqual(report['changed_pixels'], 5)
        np.testing.assert_array_equal(result, candidate)

    def test_large_changes_rollback(self):
        result, report = bounded_merge(self.base, [~self.base, ~self.base], self.cfg)
        self.assertEqual(report['action'], 'deferred')
        self.assertIn('large_candidate_geometry_change', report['flags'])
        np.testing.assert_array_equal(result, self.base)

    def test_outside_edit_budget_defers_otherwise_valid_edge_repair(self):
        candidate = self.base.copy()
        candidate[:10, :10] = True
        candidate[30:70, 34] = True
        result, report = bounded_merge(self.base, [candidate, candidate], self.cfg)
        self.assertIn('large_change_outside_allowed_region', report['flags'])
        self.assertGreater(report['proposed_changed_pixels'], 0)
        np.testing.assert_array_equal(result, self.base)

    def test_large_pass_disagreement_defers_without_applying_changes(self):
        first, second = self.base.copy(), self.base.copy()
        first[25:28, 35:125] = False
        first[40:45, 34] = second[40:45, 34] = True
        result, report = bounded_merge(self.base, [first, second], self.cfg)
        self.assertIn('point_pass_disagreement', report['flags'])
        self.assertGreater(report['proposed_changed_pixels'], 0)
        np.testing.assert_array_equal(result, self.base)

    def test_edit_budget_defers_even_when_passes_agree(self):
        candidate = self.base.copy()
        candidate[23:92, 33:127] = True
        result, report = bounded_merge(self.base, [candidate, candidate], self.cfg)
        self.assertIn('change_budget_exceeded', report['flags'])
        self.assertEqual(report['pass_disagreement_pixels'], 0)
        np.testing.assert_array_equal(result, self.base)

    def test_merge_never_mutates_inputs(self):
        candidate = self.base.copy()
        candidate[30:70, 34] = True
        original, expected = self.base.copy(), candidate.copy()
        result, _ = bounded_merge(self.base, [candidate, candidate], self.cfg)
        result[:] = False
        np.testing.assert_array_equal(self.base, original)
        np.testing.assert_array_equal(candidate, expected)

    def test_no_blanket_fill_or_uncertainty_relabel(self):
        base = self.base.copy()
        base[45, 60:65] = False
        result, report = bounded_merge(base, [base, base], self.cfg)
        self.assertEqual(report['changed_pixels'], 0)
        np.testing.assert_array_equal(result, base)
        with self.assertRaises(ValueError):
            bounded_merge(np.full((5, 5), 255, np.uint8), [], self.cfg)

    def test_reference_free_signature_and_shape_checks(self):
        import inspect
        self.assertEqual(list(inspect.signature(bounded_merge).parameters), ['proposal', 'candidates', 'cfg'])
        with self.assertRaises(ValueError):
            bounded_merge(self.base, [np.zeros((2, 2)), self.base], self.cfg)
        self.assertEqual(iou(np.zeros((2, 2)), np.zeros((2, 2))), 1)

    def test_resume_detects_changed_identity_and_masks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_mask(root / 'mask.png', self.base.astype(np.uint8))
            frame = dict(image='source.jpg', source_sha256='source')
            record = dict(**frame, contract_sha256='contract',
                          baseline=dict(path='mask.png', sha256=sha256(root / 'mask.png')),
                          repaired=dict(path='mask.png', sha256=sha256(root / 'mask.png')))
            validate_run_record(root, record, frame, 'contract')
            with self.assertRaises(ValueError):
                validate_run_record(root, record, frame, 'changed')
            save_mask(root / 'mask.png', (~self.base).astype(np.uint8))
            with self.assertRaises(ValueError):
                validate_run_record(root, record, frame, 'contract')

    def test_ignore_reference_pixels_not_scored_as_background(self):
        reference = np.array([[1, 255], [0, 1]], dtype=np.uint8)
        result = metrics(np.array([[1, 1], [255, 1]], dtype=np.uint8), reference)
        self.assertEqual(result['iou'], 1.)
        self.assertEqual(result['valid_pixels'], 3)

    def test_fresh_selection_excludes_old_neighbors_and_duplicate_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = [f'2026_07_02_run_1__photo_20260702_{t}_000000.jpg'
                     for t in ('120000', '120003', '120020', '120040')]
            names.append('2026_07_02_run_2__photo_20260702_130000_000000.jpg')
            rng = np.random.default_rng(12)
            for name in names:
                Image.fromarray(rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)).save(root / name)
            (root / names[2]).write_bytes((root / names[0]).read_bytes())
            selected, _, shortages, _ = choose_frames(root, names, {names[0]}, 2, 7)
            self.assertEqual({f['image'] for f in selected}, {names[3], names[4]})
            self.assertTrue(shortages)

    def test_history_includes_context_and_archived_mac_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = {'2026_07_02_run_1__photo_20260702_120000_000000.jpg',
                     '2026_07_02_run_2__photo_20260702_130000_000000.jpg'}
            (root / 'context-manifest.json').write_text(json.dumps({'path': '/data/' + sorted(names)[0]}))
            (root / 'exclusions.json').write_text(json.dumps({'mac_images': [sorted(names)[1]]}))
            excluded, evidence = collect_history(root, names)
            self.assertEqual(excluded, names)
            self.assertEqual(len(evidence), 2)

    def test_runner_resumes_without_inference_and_rejects_changed_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            Image.new('RGB', (12, 10), 'gray').save(source / 'one.jpg')
            frame = dict(image='one.jpg', source_sha256=sha256(source / 'one.jpg'), size=[12, 10])
            selection = root / 'selection.json'
            selection.write_text(json.dumps(dict(source=str(source), frames=[frame], images=['one.jpg'], purpose='unit test')))
            args = SimpleNamespace(selection=selection, output=root / 'out', config=None, grounding_config=None)
            frozen = dict(repair={}, grounding={})
            model = SimpleNamespace(torch=SimpleNamespace(cuda=SimpleNamespace(synchronize=lambda: None)),
                                    label=lambda image: (np.ones((10, 12), np.uint8), {}))
            detail = dict(action='unchanged_proposal', flags=[], changed_pixels=0)
            with patch('automatic_repair.recipe', return_value=frozen), patch('automatic_repair.GroundedSam2', return_value=model) as load, patch('automatic_repair.repair', return_value=(np.ones((10, 12), bool), detail)):
                run(args)
                self.assertEqual(load.call_count, 1)
                run(args)
                self.assertEqual(load.call_count, 1)
            with patch('automatic_repair.recipe', return_value={**frozen, 'changed': True}):
                with self.assertRaises(ValueError):
                    run(args)
            (args.output / 'repaired/one.png').write_bytes(b'corrupted')
            with patch('automatic_repair.recipe', return_value=frozen):
                with self.assertRaises(ValueError):
                    run(args)


if __name__ == '__main__':
    unittest.main()
