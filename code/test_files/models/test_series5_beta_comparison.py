#!/usr/bin/env python3
"""Paired export must preserve the baseline and reject mismatched references."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'ai_models_datasets/series_5/tools'))
import package_model_review as baseline_export
import package_beta_comparison as paired


class BetaComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dataset = self.root/'dataset'
        self.dataset.mkdir()
        (self.dataset/'manifest.json').write_text('{}')
        self.split, self.checkpoint = self.root/'split.json', self.root/'best.pt'
        self.split.write_text('{}')
        self.checkpoint.write_bytes(b'mocked checkpoint')
        Image.fromarray(np.full((4, 4, 3), 120, dtype=np.uint8)).save(self.dataset/'image.jpg')
        Image.fromarray(np.array([[1, 1, 255, 255]]*4, dtype=np.uint8)).save(self.dataset/'mask.png')
        self.row = {'id': 'image-id', 'size': [4, 4], 'source_name': 'image.jpg',
                    'image': 'image.jpg', 'mask': 'mask.png', 'recording_run': '2026_07_07_run_1',
                    'source_sha256': paired.sha256(self.dataset/'image.jpg'),
                    'mask_sha256': paired.sha256(self.dataset/'mask.png'), 'supervision': 'sidewalk-positive-only'}
        self.state = {'data_identity': {'manifest_sha256': paired.sha256(self.dataset/'manifest.json'),
                                       'split_sha256': paired.sha256(self.split)}, 'epoch': 8,
                      'config': {'model_name': '5.A', 'width': 4, 'height': 4, 'smoke_only': False, 'precision': 'fp32'}}

        class Model(torch.nn.Module):
            def forward(self, image):
                logits = torch.zeros((1, 2, 4, 4))
                logits[:, 1, :, 1:] = 3
                return {'out': logits}

        self.model = Model()
        self.baseline = self.root/'baseline'
        args = SimpleNamespace(dataset=self.dataset, split=self.split, checkpoint=self.checkpoint,
                               output=self.baseline, partition='test', device='cpu', precision='fp32')
        with mock.patch.object(baseline_export, 'load_partition', return_value={'test': [self.row]}), \
             mock.patch.object(baseline_export, 'load_checkpoint', return_value=(self.model, self.state)):
            baseline_export.package(args)
        self.args = SimpleNamespace(baseline=self.baseline, dataset=self.dataset, split=self.split,
                                    checkpoint=self.checkpoint, output=self.root/'paired', device='cpu')
        self.state_b = {**self.state, 'epoch': 10, 'config': {**self.state['config'], 'model_name': '5.B'}}

    def run_package(self):
        with mock.patch.object(paired, 'load_mixed_partition', return_value={'test': [self.row]}), \
             mock.patch.object(paired, 'load_checkpoint', return_value=(self.model, self.state_b)):
            return paired.package(self.args)

    def test_preserves_images_references_baseline_and_checkpoints(self):
        original = {p: paired.sha256(p) for p in self.root.rglob('*') if p.is_file()}
        result = self.run_package()
        self.assertEqual(result['images'], 1)
        manifest = json.loads((self.args.output/'manifest.json').read_text())
        self.assertEqual(manifest['partial_references'], 1)
        self.assertEqual(manifest['models']['b']['epoch'], 10)
        frame = manifest['frames'][0]
        for side in ('a', 'b'):
            labels = np.array(Image.open(self.args.output/frame['predictions'][side]['path']))
            np.testing.assert_array_equal(labels, np.array([[0, 1, 1, 1]]*4))
        self.assertEqual(frame['reference']['sha256'], self.row['mask_sha256'])
        for p, expected in original.items():
            self.assertEqual(paired.sha256(p), expected)
        for name, expected in json.loads((self.args.output/'integrity-check.json').read_text())['files_sha256'].items():
            self.assertEqual(paired.sha256(self.args.output/name), expected)
        self.assertFalse(list(self.args.output.rglob('*.pt')))
        with self.assertRaises(ValueError):
            self.run_package()

    def test_rejects_modified_baseline(self):
        (self.baseline/'predictions/001.png').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'Baseline package changed'):
            self.run_package()
        self.assertFalse(self.args.output.exists())

    def test_rejects_changed_reference_or_partition(self):
        baseline = paired.verified_baseline(self.baseline)
        for rows in ([], [{**self.row, 'mask_sha256': 'wrong'}], [{**self.row, 'id': 'other'}]):
            with self.assertRaises(ValueError):
                paired.matched_rows(baseline, {'test': rows})

    def test_rejects_smoke_and_wrong_model_or_identity(self):
        for change in ({'smoke_only': True}, {'model_name': '5.A'}):
            self.state_b['config'] = {**self.state_b['config'], **change}
            with self.assertRaises(ValueError):
                self.run_package()
            self.state_b['config'] = {**self.state['config'], 'model_name': '5.B'}
        self.state_b['data_identity'] = {}
        with self.assertRaises(ValueError):
            self.run_package()


if __name__ == '__main__':
    unittest.main()
