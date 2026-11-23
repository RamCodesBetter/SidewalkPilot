#!/usr/bin/env python3
"""Compare 5.A and 5.B on identical existing binary validation references only."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
import torch
import torch.nn.functional as F


from label_grounded_sam2 import sha256, utc_now, write_json
from prepare_reviewed_dataset import safe_file
from prepare_series5_pseudo_dataset import load_mixed_partition
from series_5_a_sidewalkpilot_trainer import (
    SidewalkDataset, autocast, confusion_counts, confusion_metrics,
    load_checkpoint, load_partition,
)


def format_scores(metrics):
    return '  '.join(f"{label} {metrics[key]:.4f}" if metrics[key] is not None else f"{label} N/A"
                     for label, key in (('P', 'precision'), ('R', 'recall'), ('F1', 'f1')))


@torch.inference_mode()
def compare(args):
    if args.output.exists():
        raise ValueError("Use a new comparison output directory")
    original = load_partition(args.original_dataset, args.original_split)
    mixed = load_mixed_partition(args.mixed_dataset, args.mixed_split)
    rows = [r for r in original['validation'] if r['supervision'] == 'binary-reference']
    mixed_by_id = {r['id']: r for r in mixed['validation']}
    for row in rows:
        other = mixed_by_id[row['id']]
        if any(other[k] != row[k] for k in ('mask_sha256', 'source_sha256', 'size', 'supervision')):
            raise ValueError('Validation reference changed between models')
    args.output.mkdir(parents=True)
    device = torch.device(args.device)
    torch.set_num_threads(8)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    reports = {}
    predictions = {}
    for name, checkpoint, dataset, split in (
        ('5.A', args.a, args.original_dataset, args.original_split),
        ('5.B', args.b, args.mixed_dataset, args.mixed_split),
    ):
        model, state = load_checkpoint(checkpoint)
        if state['data_identity'] != {'manifest_sha256': sha256(dataset/'manifest.json'), 'split_sha256': sha256(split)}:
            raise ValueError('Checkpoint is not bound to the supplied dataset and split')
        cfg = state['config']
        if cfg['smoke_only'] or cfg['model_name'] != name:
            raise ValueError('Expected a full-run checkpoint of the named model')
        model.to(device).eval()
        data = SidewalkDataset(args.original_dataset, rows, (cfg['width'], cfg['height']), original_targets=True)
        counts = torch.zeros((2, 2), dtype=torch.int64)
        scores = []
        predictions[name] = []
        for i in range(len(data)):
            image, target, _, _ = data[i]
            with autocast(device, cfg['precision']):
                logits = model(image.unsqueeze(0).to(device))['out']
            if not torch.isfinite(logits).all():
                raise ValueError('Non-finite checkpoint prediction')
            logits = F.interpolate(logits.float(), size=target.shape, mode='bilinear', align_corners=False)
            pred = logits.argmax(1)[0].cpu()
            current = confusion_counts(pred, target)
            counts += current
            scores.append({'id': rows[i]['id'], 'source_name': rows[i]['source_name'], **confusion_metrics(current)})
            predictions[name].append(pred.numpy().astype(np.uint8))
        reports[name] = {'checkpoint_sha256': sha256(checkpoint), 'epoch': state['epoch'],
                         'input_size': [cfg['width'], cfg['height']], 'images': len(rows),
                         'aggregate': confusion_metrics(counts), 'per_image': scores}
        del model
        if device.type == 'cuda':
            torch.cuda.empty_cache()
    for i, row in enumerate(rows):
        with Image.open(safe_file(args.original_dataset, row['image'])) as source:
            rgb = np.array(source.convert('RGB'))
        with Image.open(safe_file(args.original_dataset, row['mask'])) as source:
            target = np.array(source)
        sheet = Image.new('RGB', (1280, 784), 'white')
        draw = ImageDraw.Draw(sheet)
        panels = [('Original', None), ('Reference (amber: ignored)', target),
                  ('5.A', predictions['5.A'][i]), ('5.B', predictions['5.B'][i])]
        for n, (title, mask) in enumerate(panels):
            view = rgb.astype(np.float32).copy()
            if mask is not None:
                view[mask == 1] = .55 * view[mask == 1] + .45 * np.array([30, 210, 140])
                view[mask == 255] = .65 * view[mask == 255] + .35 * np.array([240, 180, 40])
            x, y = (n % 2) * 640, (n // 2) * 392
            draw.text((x + 8, y + 6), title, fill='black')
            if title in reports:
                metrics = reports[title]['per_image'][i]
                draw.text((x + 75, y + 6), format_scores(metrics), fill='black')
            sheet.paste(Image.fromarray(view.astype(np.uint8)).resize((640, 360)), (x, y + 28))
        sheet.save(args.output / f'{i + 1:02d}.jpg', quality=92)
    result = {'created_utc': utc_now(), 'partition': 'existing development validation', 'models': reports,
              'scope': 'Fixed binary references only; no test images. Checkpoint selection used these references, so this is not an independent accuracy estimate.',
              'mask_rule': 'Bilinear original-resolution logits, argmax, no largest-component or other prediction post-filter.'}
    write_json(args.output/'comparison.json', result)
    return {name: report['aggregate'] for name, report in reports.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original-dataset', 'original-split', 'mixed-dataset', 'mixed-split', 'a', 'b', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    print(json.dumps(compare(parser.parse_args()), indent=2))
