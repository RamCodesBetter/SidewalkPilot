#!/usr/bin/env python3
"""5.B weak-label loss, balanced batches, and frozen evaluation checks."""
import copy
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ai_models_datasets/series_5'))
from label_grounded_sam2 import digest_json, sha256, write_json
from prepare_reviewed_dataset import pixel_hash, pixel_counts
from prepare_series5_pseudo_dataset import build, load_mixed_partition
from series_5_a_sidewalkpilot_trainer import DEFAULTS, train
from series_5_b_sidewalkpilot_trainer import ScreenedBatchSampler, conservative_loss, TRAINING_POLICY
from pseudo_training_targets import prepare_target


class PseudoTrainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'dataset'
        self.data.mkdir()

    def fixture(self):
        rows = []
        for i, (day, kind) in enumerate(((2, 'binary-reference'), (12, 'binary-reference'),
                                       (7, 'binary-reference'), (2, 'pseudo-binary'),
                                       (2, 'sidewalk-positive-only'))):
            labels = np.array([[0, 1, 255], [0, 1, 1]], dtype=np.uint8)
            if kind == 'sidewalk-positive-only':
                labels[labels == 0] = 255
            image_name, mask_name = f'{i}.png', f'{i}-mask.png'
            Image.fromarray(np.full((2, 3, 3), i * 40, dtype=np.uint8)).save(self.data / image_name)
            Image.fromarray(labels).save(self.data / mask_name)
            identifier = sha256(self.data / image_name)
            rows.append(dict(id=identifier, source_sha256=identifier, image=image_name, mask=mask_name,
                mask_sha256=sha256(self.data / mask_name), size=[3, 2], pixels_sha256=pixel_hash(labels),
                pixel_counts=pixel_counts(labels), included=True, supervision=kind,
                recording_run=f'2026_07_{day:02d}_run_1'))
        self.manifest = dict(schema='sidewalkpilot-mixed-pseudo-dataset-v1', records=rows)
        self.split = dict(schema='sidewalkpilot-binary-day-split-v1',
            partitions=dict(train=[rows[i]['id'] for i in (0, 3, 4)], validation=[rows[1]['id']], test=[rows[2]['id']]),
            days=dict(train=['2026_07_02'], validation=['2026_07_12'], test=['2026_07_07']))
        (self.data / 'provenance').mkdir()
        write_json(self.data / 'provenance/base-split.json', self.split)
        self.refresh()
        return rows

    def refresh(self):
        write_json(self.data / 'manifest.json', self.manifest)
        write_json(self.data / 'checksums.json', {str(p.relative_to(self.data)): sha256(p)
            for p in self.data.rglob('*') if p.is_file() and p.name != 'checksums.json'})
        self.split['manifest_sha256'] = sha256(self.data / 'manifest.json')
        write_json(self.root / 'split.json', self.split)

    def test_sampler_covers_all_weak_labels_and_keeps_four_references(self):
        rows = [{'supervision': 'binary-reference'}] * 7 + [{'supervision': 'pseudo-binary'}] * 17
        rows += [{'supervision': 'sidewalk-positive-only'}] * 4
        sampler = ScreenedBatchSampler(rows, 16, 93)
        batches = list(sampler)
        self.assertEqual(batches, list(sampler))
        self.assertEqual({i for batch in batches for i, _ in batch if i >= 7}, set(range(7, 28)))
        for batch in batches:
            self.assertEqual(sum(i < 7 for i, _ in batch), 4)
            self.assertEqual(len(batch), 16)
        sampler.epoch = 1
        self.assertNotEqual(batches, list(sampler))
        with self.assertRaises(ValueError):
            ScreenedBatchSampler(rows, 6, 1)

    def test_background_has_double_gradient_and_unknown_has_zero(self):
        logits = torch.zeros(1, 2, 1, 3, requires_grad=True)
        targets = torch.tensor([[[0, 1, 255]]])
        loss, binary, weak = conservative_loss(logits, targets, torch.tensor([True]))
        self.assertAlmostEqual(loss.item(), np.log(2), places=6)
        self.assertEqual(weak.item(), 0)
        loss.backward()
        gradient = logits.grad.abs().sum(1)[0, 0]
        self.assertAlmostEqual(gradient[0].item(), 2 * gradient[1].item())
        self.assertEqual(gradient[2].item(), 0)

    def test_weak_loss_half_weight_and_not_amplified_by_count(self):
        logits = torch.randn(2, 2, 1, 3)
        target = torch.tensor([[[0, 1, 255]], [[0, 1, 255]]])
        loss, binary, weak = conservative_loss(logits, target, torch.tensor([True, False]))
        torch.testing.assert_close(loss, binary + .5 * weak)
        repeated = conservative_loss(torch.cat((logits[:1], logits[1:].repeat(8, 1, 1, 1))),
            torch.cat((target[:1], target[1:].repeat(8, 1, 1))), torch.tensor([True] + [False] * 8))[0]
        torch.testing.assert_close(loss, repeated)

    def test_all_unknown_is_zero_loss_and_gradient(self):
        logits = torch.randn(2, 2, 2, 2, requires_grad=True)
        loss, _, _ = conservative_loss(logits, torch.full((2, 2, 2), 255), torch.tensor([True, False]))
        self.assertEqual(loss.item(), 0)
        loss.backward()
        self.assertEqual(logits.grad.abs().sum().item(), 0)

    def test_tiny_pseudo_negatives_become_unknown_not_sidewalk(self):
        labels = np.ones((100, 100), dtype=np.uint8)
        labels[:20] = 0
        labels[50:52, 30:40] = 0
        labels[80, 0:20] = 0
        labels[95:] = 255
        original = labels.copy()
        target, detail = prepare_target(labels)
        np.testing.assert_array_equal(labels, original)
        np.testing.assert_array_equal(target == 1, labels == 1)
        self.assertTrue((target[:20] == 0).all())
        self.assertTrue((target[50:52, 30:40] == 255).all())
        self.assertTrue((target[80, 0:20] == 255).all())
        self.assertEqual(detail['additional_ignored_negative_pixels'], 40)

    def test_large_disconnected_negative_regions_remain_background(self):
        labels = np.ones((100, 100), dtype=np.uint8)
        labels[:20] = 0
        labels[50:60, 20:40] = 0
        target, detail = prepare_target(labels)
        np.testing.assert_array_equal(target, labels)
        self.assertEqual(detail['additional_ignored_negative_pixels'], 0)

    def test_invalid_pseudo_target_rejected(self):
        for labels in (np.array([]), np.ones((2, 2, 2)), np.array([[3]])):
            with self.assertRaises(ValueError):
                prepare_target(labels)

    def test_mixed_loader_accepts_only_training_pseudo_labels(self):
        self.fixture()
        parts = load_mixed_partition(self.data, self.root / 'split.json')
        self.assertEqual([len(parts[p]) for p in ('train', 'validation', 'test')], [3, 1, 1])
        for part in ('validation', 'test'):
            self.assertTrue(all(r['supervision'] == 'binary-reference' for r in parts[part]))

    def test_evaluation_labels_cannot_be_reclassified_as_pseudo(self):
        self.fixture()
        self.manifest['records'][1]['supervision'] = 'pseudo-binary'
        self.refresh()
        with self.assertRaises(ValueError):
            load_mixed_partition(self.data, self.root / 'split.json')

    def test_evaluation_roster_cannot_change_even_with_matching_days(self):
        self.fixture()
        base = copy.deepcopy(self.split)
        base['partitions']['validation'] = ['different-reference']
        write_json(self.data / 'provenance/base-split.json', base)
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'Evaluation split changed'):
            load_mixed_partition(self.data, self.root / 'split.json')

    def test_positive_only_cannot_gain_background(self):
        self.fixture()
        self.manifest['records'][3]['supervision'] = 'sidewalk-positive-only'
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'Invented human background'):
            load_mixed_partition(self.data, self.root / 'split.json')

    def test_changed_assets_and_unexpected_files_rejected(self):
        self.fixture()
        (self.data / 'unexpected.txt').write_text('unexpected')
        with self.assertRaisesRegex(ValueError, 'Unexpected dataset files'):
            load_mixed_partition(self.data, self.root / 'split.json')
        (self.data / 'unexpected.txt').unlink()
        (self.data / '0-mask.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Dataset file changed'):
            load_mixed_partition(self.data, self.root / 'split.json')

    def test_export_rejects_split_inside_dataset_before_writing(self):
        args = SimpleNamespace(output=self.root/'out', output_split=self.root/'out/split.json',
            dataset=self.data, run=self.root/'run', selection=self.root/'selection.json', split=self.root/'split.json')
        with self.assertRaisesRegex(ValueError, 'Split output overlaps'):
            build(args)
        self.assertFalse(args.output.exists())

    def export_fixture(self, accepted_count=100):
        rows = self.fixture()
        # The baseline has no pseudo-labels. The export adds new training images.
        pseudo_id = rows[3]['id']
        self.manifest['records'].remove(rows[3])
        self.split['partitions']['train'].remove(pseudo_id)
        self.refresh()
        source, run = self.root/'source', self.root/'run'
        source.mkdir()
        (run/'records').mkdir(parents=True)
        (run/'masks').mkdir()
        frames = []
        mask = np.array([[0, 1, 255], [0, 1, 1]], dtype=np.uint8)
        for i in range(105):
            name = f'2026_07_02_run_1__new_{i}.png'
            pixels = np.arange(18, dtype=np.uint8).reshape(2, 3, 3) + i
            Image.fromarray(pixels).save(source/name)
            identifier = sha256(source/name)
            frames.append(dict(id=identifier, image=name, source_sha256=identifier,
                               recording_run='2026_07_02_run_1'))
            Image.fromarray(mask).save(run/'masks'/f'{identifier}.png')
        selection = dict(schema='sidewalkpilot-pseudo-selection-v1', count=len(frames), frames=frames,
                         source=str(source), allowed_days=['2026_07_02'],
                         purpose='new training-only pseudo-labels',
                         baseline_manifest_sha256=sha256(self.data/'manifest.json'),
                         baseline_split_sha256=sha256(self.root/'split.json'))
        selection['selection_id'] = digest_json(selection)
        write_json(self.root/'selection.json', selection)
        contract = dict(selection_sha256=sha256(self.root/'selection.json'))
        contract_hash = digest_json(contract)
        write_json(run/'manifest.json', dict(schema='sidewalkpilot-sam3-pseudo-run-v1',
                                            contract=contract, contract_sha256=contract_hash))
        for i, frame in enumerate(frames):
            relative = f"masks/{frame['id']}.png"
            write_json(run/'records'/f"{frame['id']}.json", dict(frame=frame, size=[3, 2],
                contract_sha256=contract_hash, mask=dict(path=relative, sha256=sha256(run/relative)),
                filter=dict(accepted_for_pseudo_training=i < accepted_count)))
        write_json(run/'status.json', dict(status='complete', processed=105,
                                          accepted_pseudo=accepted_count, deferred=105-accepted_count))
        return SimpleNamespace(output=self.root/'combined', output_split=self.root/'combined-split.json',
            dataset=self.data, split=self.root/'split.json', selection=self.root/'selection.json', run=run)

    def test_export_retains_only_accepted_training_labels_and_preserves_references(self):
        args = self.export_fixture()
        with mock.patch('prepare_series5_pseudo_dataset.verify_dataset'):
            result = build(args)
        self.assertEqual(result['pseudo_labels'], 100)
        self.assertEqual(result['deferred'], 5)
        parts = load_mixed_partition(args.output, args.output_split)
        self.assertEqual(len(parts['train']), 102)
        self.assertEqual(sum(r['supervision'] == 'pseudo-binary' for r in parts['train']), 100)
        for row in self.manifest['records']:
            self.assertEqual(sha256(self.data/row['mask']), sha256(args.output/row['mask']))

    def test_export_rejects_incomplete_run_without_publishing(self):
        args = self.export_fixture()
        write_json(args.run/'status.json', dict(status='pilot-complete', processed=105))
        with mock.patch('prepare_series5_pseudo_dataset.verify_dataset'):
            with self.assertRaisesRegex(ValueError, 'not complete'):
                build(args)
        self.assertFalse(args.output.exists())
        self.assertFalse(args.output_split.exists())

    def test_export_rejects_false_status_counts(self):
        args = self.export_fixture()
        write_json(args.run/'status.json', dict(status='complete', processed=105, accepted_pseudo=105, deferred=0))
        with mock.patch('prepare_series5_pseudo_dataset.verify_dataset'):
            with self.assertRaisesRegex(ValueError, 'counts differ'):
                build(args)
        self.assertFalse(args.output.exists())

    def test_visual_exclusion_is_preserved_and_kept_out_of_training(self):
        args = self.export_fixture(101)
        first = json.loads(args.selection.read_text())['frames'][0]
        contract = json.loads((args.run/'manifest.json').read_text())['contract_sha256']
        args.visual_exclusions = self.root/'exclusions.json'
        write_json(args.visual_exclusions, dict(schema='sidewalkpilot-pseudo-visual-exclusions-v1',
            run_contract_sha256=contract, records=[dict(id=first['id'], reason='ambiguous boundary')]))
        with mock.patch('prepare_series5_pseudo_dataset.verify_dataset'):
            result = build(args)
        self.assertEqual(result['pseudo_labels'], 100)
        parts = load_mixed_partition(args.output, args.output_split)
        self.assertNotIn(first['id'], [r['id'] for r in parts['train']])
        self.assertTrue((args.output/'provenance/visual-exclusions.json').exists())

    def test_export_rejects_changed_mask_without_publishing(self):
        args = self.export_fixture()
        first = json.loads(args.selection.read_text())['frames'][0]
        (args.run/'masks'/f"{first['id']}.png").write_bytes(b'changed')
        with mock.patch('prepare_series5_pseudo_dataset.verify_dataset'):
            with self.assertRaisesRegex(ValueError, 'mask changed'):
                build(args)
        self.assertFalse(args.output.exists())
        self.assertFalse(args.output_split.exists())

    def test_cpu_smoke_uses_5b_callbacks_and_keeps_test_unevaluated(self):
        self.fixture()
        args = SimpleNamespace(**{**DEFAULTS, 'dataset': self.data, 'split': self.root/'split.json',
            'output': self.root/'smoke', 'device': 'cpu', 'precision': 'fp32', 'weights': 'none',
            'width': 96, 'height': 64, 'batch_size': 8, 'epochs': 1, 'workers': 0,
            'resume': False, 'smoke': True, 'wandb': False, 'model_name': '5.B',
            'experiment': 'unit-test', 'training_policy': TRAINING_POLICY})
        # Ensure at least two batches for the two-update smoke contract.
        parts = load_mixed_partition(self.data, self.root/'split.json')
        parts['train'] = parts['train'][:1] + parts['train'][1:] * 5
        with mock.patch('series_5_a_sidewalkpilot_trainer.evaluate', return_value={
                'binary_reference': {'sidewalk_iou': .5, 'precision': .6, 'recall': .7, 'f1': .64}}) as evaluate:
            result = train(args, partition_loader=lambda *_: parts, sampler_class=ScreenedBatchSampler,
                           loss_function=conservative_loss)
        self.assertEqual(result['status'], 'smoke-complete')
        self.assertFalse(result['test_evaluated'])
        self.assertEqual(evaluate.call_args.args[2], parts['validation'])


if __name__ == '__main__':
    unittest.main()
