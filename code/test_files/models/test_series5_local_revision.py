import copy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'ai_models_datasets/series_5/tools'))
from workspace import activate
activate()
from package_local_mask_revision import apply_edits, flagged_ids, revision_inventory


class LocalRevisionTests(unittest.TestCase):
    def test_locality_and_original_unchanged(self):
        original = np.zeros((10, 12), dtype=np.uint8)
        output, report = apply_edits(original, [dict(rectangle=[2, 3, 5, 7], value=1, reason='Known pavement')])
        self.assertEqual(report['changed_pixels'], 12)
        self.assertEqual(report['outside_effective_regions'], 0)
        self.assertEqual(int(original.sum()), 0)
        self.assertTrue((output[3:7, 2:5] == 1).all())
        output[3:7, 2:5] = 0
        self.assertFalse(output.any())

    def test_conditional_patch_preserves_uncertainty(self):
        original = np.zeros((6, 6), dtype=np.uint8)
        original[2, 2] = 255
        output, report = apply_edits(original, [dict(rectangle=[0, 0, 6, 6], value=1, only_values=[0], reason='Fill missing interior')])
        self.assertEqual(output[2, 2], 255)
        self.assertEqual(report['changed_pixels'], 35)

    def test_polygon_and_order(self):
        original = np.zeros((6, 6), dtype=np.uint8)
        output, _ = apply_edits(original, [
            dict(polygon=[[1, 1], [4, 1], [4, 4], [1, 4]], value=255, reason='Blurred boundary'),
            dict(rectangle=[2, 2, 4, 4], value=1, reason='Readable interior')])
        self.assertEqual(output[1, 1], 255)
        self.assertEqual(output[2, 2], 1)
        self.assertEqual(output[0, 0], 0)

    def test_invalid_edits_rejected(self):
        valid = dict(rectangle=[1, 1, 3, 3], value=1, reason='Visible pavement')
        for changes in (dict(value=2), dict(value=True), dict(reason=''), dict(only_values=[]),
                        dict(only_values=[7]), dict(rectangle=[0, 0, 99, 2]),
                        dict(polygon=[[1, 1], [3, 1], [3, 3]])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                apply_edits(np.zeros((6, 6), dtype=np.uint8), [dict(valid, **changes)])

    def test_invalid_baseline_rejected(self):
        with self.assertRaises(ValueError):
            apply_edits(np.full((6, 6), 2, dtype=np.uint8), [])

    def fixture(self):
        frames = [dict(id=f'image-{n}', source_sha256=f's{n}', methods={'codex': {'sha256': f'm{n}'}}) for n in range(3)]
        parent = dict(package_id='p', frames=frames)
        review = dict(schema='sidewalkpilot-three-method-review-v1', package_id='p', review_methods=['codex'], reviews={
            f'image-{n}': dict(source_sha256=f's{n}', methods={'codex': dict(sha256=f'm{n}', decision=decision)})
            for n, decision in enumerate(('correct', 'needs_correction', 'uncertain'))})
        return parent, review

    def test_only_flagged_ids(self):
        parent, review = self.fixture()
        self.assertEqual(flagged_ids(parent, review), ['image-1', 'image-2'])

    def test_wrong_or_incomplete_review_rejected(self):
        parent, source = self.fixture()
        for kind in ('package', 'source', 'mask', 'incomplete', 'unreviewed'):
            review = copy.deepcopy(source)
            if kind == 'package': review['package_id'] = 'other'
            if kind == 'source': review['reviews']['image-1']['source_sha256'] = 'wrong'
            if kind == 'mask': review['reviews']['image-1']['methods']['codex']['sha256'] = 'wrong'
            if kind == 'incomplete': del review['reviews']['image-1']
            if kind == 'unreviewed': review['reviews']['image-1']['methods']['codex']['decision'] = 'unreviewed'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                flagged_ids(parent, review)

    def subset_fixture(self):
        full, review = self.fixture()
        review['reviews']['image-0']['notes'] = 'Accepted with a retained note'
        inherited = {'image-0': dict(rating=review['reviews']['image-0'], review_package_id='old', review_sha256='h')}
        subset = dict(full, frames=full['frames'][1:])
        current = copy.deepcopy(review)
        del current['reviews']['image-0']
        inventory = dict(revision_package_id='p', count=3, frames=full['frames'])
        return subset, current, inventory, inherited

    def test_subset_preserves_prior_acceptance_and_notes(self):
        parent, review, inventory, inherited = self.subset_fixture()
        frames, ratings, origins = revision_inventory(parent, review, 'new-hash', inventory, inherited)
        self.assertEqual(len(frames), 3)
        self.assertEqual(ratings['image-0']['notes'], 'Accepted with a retained note')
        self.assertEqual(origins['image-0']['review_package_id'], 'old')
        self.assertEqual(origins['image-1']['review_sha256'], 'new-hash')
        ratings['image-0']['notes'] = 'changed copy'
        self.assertNotEqual(inherited['image-0']['rating']['notes'], 'changed copy')

    def test_invalid_carry_forward_rejected(self):
        for kind in ('mask', 'source', 'unaccepted', 'missing', 'identity', 'visible', 'duplicate'):
            parent, review, inventory, inherited = self.subset_fixture()
            if kind == 'mask': inherited['image-0']['rating']['methods']['codex']['sha256'] = 'wrong'
            if kind == 'source': inherited['image-0']['rating']['source_sha256'] = 'wrong'
            if kind == 'unaccepted': inherited['image-0']['rating']['methods']['codex']['decision'] = 'needs_correction'
            if kind == 'missing': inherited = {}
            if kind == 'identity': inventory['revision_package_id'] = 'wrong'
            if kind == 'visible':
                inventory['frames'] = copy.deepcopy(inventory['frames'])
                inventory['frames'][1]['source_sha256'] = 'changed'
            if kind == 'duplicate': inventory['frames'] = inventory['frames'] + [inventory['frames'][0]]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                revision_inventory(parent, review, 'new-hash', inventory, inherited)

    def test_full_inventory_still_supported(self):
        parent, review = self.fixture()
        frames, ratings, origins = revision_inventory(parent, review, 'hash')
        self.assertEqual(frames, parent['frames'])
        self.assertEqual(len(ratings), 3)
        self.assertEqual(origins['image-2']['review_sha256'], 'hash')


if __name__ == '__main__':
    unittest.main()
