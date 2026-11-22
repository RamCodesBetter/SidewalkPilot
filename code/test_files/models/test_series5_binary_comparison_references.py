#!/usr/bin/env python3
"""Viewer reference derivation must not silently promote unknowns to reviewed truth."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

import test_series5_beta_comparison as fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'ai_models_datasets/series_5'))
import derive_beta_references as references


class BinaryComparisonReferencesTests(unittest.TestCase):
    def test_explicit_background_assumption_preserves_sidewalk_and_input(self):
        labels = np.array([[1, 255, 0], [255, 1, 255]], dtype=np.uint8)
        original = labels.copy()
        result, count = references.derive(labels)
        self.assertEqual(count, 3)
        np.testing.assert_array_equal(result, [[1, 0, 0], [0, 1, 0]])
        np.testing.assert_array_equal(labels, original)
        binary = np.array([[0, 1]], dtype=np.uint8)
        result, count = references.derive(binary)
        self.assertEqual(count, 0)
        np.testing.assert_array_equal(result, binary)

    def test_invalid_inputs_rejected(self):
        for value in (np.array([1], dtype=np.uint8), np.array([[2]], dtype=np.uint8),
                      np.array([[1]], dtype=np.float32)):
            with self.assertRaises(ValueError):
                references.derive(value)

    def test_export_keeps_originals_and_reviews_compatible(self):
        fixture = fixtures.BetaComparisonTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.run_package()
        source, output = fixture.args.output, fixture.root/'binary-comparison'
        original = {p: references.sha256(p) for p in fixture.root.rglob('*') if p.is_file()}
        old = json.loads((source/'manifest.json').read_text())
        result = references.build(source, output)
        self.assertEqual(result['derived_binary'], 1)
        self.assertEqual(result['preserved_binary'], 0)
        self.assertEqual(result['assumed_background_pixels'], 8)
        manifest = json.loads((output/'manifest.json').read_text())
        self.assertEqual(manifest['compatible_review_package_ids'], [old['package_id']])
        self.assertNotEqual(manifest['package_id'], old['package_id'])
        frame = manifest['frames'][0]
        self.assertEqual(frame['supervision'], 'sidewalk-positive-only')
        self.assertEqual(frame['reference'], old['frames'][0]['reference'])
        self.assertEqual(frame['predictions'], old['frames'][0]['predictions'])
        self.assertEqual(frame['comparison_reference']['kind'], 'derived-binary-reference')
        self.assertFalse(frame['comparison_reference']['background_independently_reviewed'])
        with Image.open(output/frame['comparison_reference']['path']) as image:
            np.testing.assert_array_equal(np.array(image), np.array([[1, 1, 0, 0]]*4))
        for p, expected in original.items():
            self.assertEqual(references.sha256(p), expected)
        for name, expected in json.loads((output/'integrity-check.json').read_text())['files_sha256'].items():
            self.assertEqual(references.sha256(output/name), expected)
        with self.assertRaises(ValueError):
            references.build(source, output)
        (source/'references/001.png').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'Source package changed'):
            references.build(source, fixture.root/'should-not-exist')


if __name__ == '__main__':
    unittest.main()
