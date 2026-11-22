#!/usr/bin/env python3
"""Pair frozen 5.A viewer predictions with 5.B on the identical held-out images."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import base64
import json
from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

HERE = _workspace.TOOLS

from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from package_model_review import check_destination, mask_record, validate_identity
from prepare_reviewed_dataset import safe_file
from prepare_series5_pseudo_dataset import load_mixed_partition
from series_5_a_sidewalkpilot_trainer import SidewalkDataset, autocast, load_checkpoint

ASSETS = ('beta.html', 'beta.js', 'beta.css', 'comparison.css', 'model_metrics.js',
          'lucide.min.js', 'LUCIDE-LICENSE.txt')


def verified_baseline(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest.get('schema') != 'sidewalkpilot-model-review-v1' or manifest.get('model_name') != '5.A':
        raise ValueError('Expected the frozen 5.A model-review package')
    integrity = json.loads((root / 'integrity-check.json').read_text())['files_sha256']
    required = {'manifest.json', 'provenance/training-config.json'}
    for frame in manifest['frames']:
        required.update((frame['image'], frame['prediction']['path'], frame['reference']['path']))
    if not required <= integrity.keys():
        raise ValueError('Incomplete baseline integrity record')
    for name, expected in integrity.items():
        if sha256(safe_file(root, name)) != expected:
            raise ValueError(f'Baseline package changed: {name}')
    config = json.loads((root / 'provenance/training-config.json').read_text())
    if config.get('smoke_only') or config.get('model_name') != '5.A':
        raise ValueError('Expected a trained 5.A checkpoint')
    return manifest


def matched_rows(baseline, partitions):
    rows = partitions[baseline['partition']]
    by_id = {row['id']: row for row in rows}
    frames = baseline['frames']
    if len(frames) != len(rows) or {f['id'] for f in frames} != set(by_id):
        raise ValueError('Comparison partitions differ')
    result = []
    for frame in frames:
        row = by_id[frame['id']]
        if (frame['source_sha256'] != row['source_sha256']
                or frame['reference']['sha256'] != row['mask_sha256']
                or frame['supervision'] != row['supervision'] or frame['size'] != row['size']):
            raise ValueError('Comparison source or reference differs')
        result.append(row)
    return result


@torch.inference_mode()
def package(args):
    baseline_root, dataset, output = args.baseline.resolve(), args.dataset.resolve(), args.output.resolve()
    check_destination(output, dataset, args.checkpoint, args.split)
    if output == baseline_root or output in baseline_root.parents or baseline_root in output.parents:
        raise ValueError('Keep the original viewer separate')
    baseline = verified_baseline(baseline_root)
    rows = matched_rows(baseline, load_mixed_partition(dataset, args.split))
    model, state = load_checkpoint(args.checkpoint)
    identity = {'manifest_sha256': sha256(dataset/'manifest.json'), 'split_sha256': sha256(args.split)}
    validate_identity(state, identity)
    cfg = state['config']
    if cfg['model_name'] != '5.B':
        raise ValueError('Expected model 5.B')
    device = torch.device(args.device)
    if device.type == 'cpu' and cfg['precision'] != 'fp32':
        raise ValueError('Use CUDA to preserve the checkpoint inference precision')
    torch.set_num_threads(8)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model.to(device).eval()
    data = SidewalkDataset(dataset, rows, (cfg['width'], cfg['height']), original_targets=True)
    manifest = {
        'schema': 'sidewalkpilot-beta-comparison-v1', 'created_utc': utc_now(),
        'partition': baseline['partition'], 'count': len(rows), 'baseline_package_id': baseline['package_id'],
        'models': {
            'a': {'name': '5.A', 'checkpoint_sha256': baseline['checkpoint_sha256'],
                  'epoch': baseline['checkpoint_epoch'], 'input_size': baseline['input_size'],
                  'precision': baseline['precision'], 'data_identity': baseline['data_identity']},
            'b': {'name': '5.B', 'checkpoint_sha256': sha256(args.checkpoint), 'epoch': state['epoch'],
                  'input_size': [cfg['width'], cfg['height']], 'precision': cfg['precision'], 'data_identity': identity},
        },
        'scope': 'Previously reviewed development test images, not an untouched final research test. '
                 'Future changes based on this review must acknowledge test-set feedback.',
        'prediction_policy': 'Frozen checkpoints; original-resolution bilinear logits followed by argmax. '
                             'No filtering, edits, or reference-guided inference. 5.A predictions are copied unchanged.',
        'metric_policy': 'Per-image metrics on known reference pixels only. Positive-only references '
                         'provide known-sidewalk recall, not precision or F1. No W&B upload.',
        'generator_sha256': sha256(Path(__file__)), 'frames': [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.beta-comparison-', dir=output.parent) as temporary:
        root = Path(temporary)/'package'
        for folder in ('images', 'references', 'predictions/a', 'predictions/b', 'provenance'):
            (root/folder).mkdir(parents=True)
        for i, (row, old) in enumerate(zip(rows, baseline['frames'])):
            tensor, target, _, _ = data[i]
            with autocast(device, cfg['precision']):
                logits = model(tensor.unsqueeze(0).to(device))['out']
            if not torch.isfinite(logits).all():
                raise ValueError('Non-finite prediction')
            predicted = F.interpolate(logits.float(), size=target.shape, mode='bilinear', align_corners=False)
            predicted = predicted.argmax(1)[0].cpu().numpy().astype(np.uint8)
            name = f'{i+1:03d}'
            source = root/'images'/(name+Path(old['image']).suffix)
            reference = root/'references'/(name+'.png')
            shutil.copy2(safe_file(baseline_root, old['image']), source)
            shutil.copy2(safe_file(baseline_root, old['reference']['path']), reference)
            if sha256(source) != row['source_sha256'] or sha256(reference) != row['mask_sha256']:
                raise ValueError('Source or reference changed during export')
            records = {}
            for side in ('a', 'b'):
                dest = root/'predictions'/side/(name+'.png')
                if side == 'a':
                    shutil.copy2(safe_file(baseline_root, old['prediction']['path']), dest)
                    if sha256(dest) != old['prediction']['sha256']:
                        raise ValueError('5.A prediction changed')
                    with Image.open(dest) as image:
                        labels = np.array(image)
                else:
                    labels = predicted
                    Image.fromarray(labels).save(dest)
                if labels.shape != tuple(target.shape) or not set(np.unique(labels)) <= {0, 1}:
                    raise ValueError('Invalid binary prediction')
                records[side] = {**mask_record(dest, root, labels),
                                 'png_base64': base64.b64encode(dest.read_bytes()).decode('ascii')}
            manifest['frames'].append({
                'id': row['id'], 'name': row['source_name'], 'size': old['size'],
                'image': str(source.relative_to(root)), 'source_sha256': row['source_sha256'],
                'supervision': row['supervision'], 'recording_run': row['recording_run'],
                'predictions': records, 'reference': mask_record(reference, root, target.numpy()),
            })
            print(f'Paired {i+1}/{len(rows)}: {row["source_name"]}', flush=True)
        manifest['binary_references'] = sum(r['supervision'] == 'binary-reference' for r in rows)
        manifest['partial_references'] = len(rows)-manifest['binary_references']
        manifest['package_id'] = digest_json(manifest)
        write_json(root/'manifest.json', manifest)
        (root/'data.js').write_text('window.BETA_COMPARISON_DATA = '+json.dumps(manifest, separators=(',', ':'))+';\n')
        for name in ASSETS:
            shutil.copy2(HERE/'review'/name, root/('index.html' if name == 'beta.html' else name))
        shutil.copy2(args.split, root/'provenance/split.json')
        write_json(root/'provenance/5.B-training-config.json', cfg)
        shutil.copy2(baseline_root/'provenance/training-config.json', root/'provenance/5.A-training-config.json')
        (root/'READ-ME.txt').write_text(
            'SidewalkPilot / Original + 5.A + 5.B\n\n'
            'Open index.html directly. Keep companion files together; no server or internet required.\n'
            'Enter/Right: next image. Left: previous. A/B: select model.\n'
            '1: correct. 2: needs correction, then 1/2/3: minor/moderate/major. 3: uncertain.\n'
            'Auto-advance moves A to B, then to A on the next image. Toggle it off to stay in place.\n'
            'Ratings and notes are browser-local; export JSON for a portable backup.\n'
            'Import requires matching package, source, model, and prediction identities.\n'
            'The separate 5.A viewer and its ratings are not changed. No masks are modified by reviews.\n'
            'Green = sidewalk. Reference amber = unknown/ignored, not background.\n'
            'Positive-only references have no valid P or F1; their recall covers known sidewalk only.\n'
            'These are development test images. Reviewing them does not create independent accuracy evidence.\n',
            encoding='ascii')
        if (sha256(args.checkpoint) != manifest['models']['b']['checkpoint_sha256']
                or sha256(args.split) != identity['split_sha256']
                or sha256(dataset/'manifest.json') != identity['manifest_sha256']):
            raise ValueError('Inputs changed during export')
        write_json(root/'integrity-check.json', {'files_sha256': {
            str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob('*')) if p.is_file()}})
        root.rename(output)
    return {'output': str(output), 'images': len(rows), 'package_id': manifest['package_id']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('baseline', 'dataset', 'split', 'checkpoint', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    print(json.dumps(package(parser.parse_args()), indent=2))
