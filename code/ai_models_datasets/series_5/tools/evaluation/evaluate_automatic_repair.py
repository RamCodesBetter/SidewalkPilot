#!/usr/bin/env python3
"""Compare completed inference with student-accepted development masks afterwards."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from label_grounded_sam2 import sha256, utc_now, write_json


def metrics(prediction, reference):
    prediction, reference = np.asarray(prediction), np.asarray(reference)
    if prediction.shape != reference.shape or not np.isin(reference, [0, 1, 255]).all():
        raise ValueError('Invalid reference shape or labels')
    valid = reference != 255
    yes, expected = prediction == 1, reference == 1
    tp = int(np.count_nonzero(valid & yes & expected))
    fp = int(np.count_nonzero(valid & yes & ~expected))
    fn = int(np.count_nonzero(valid & ~yes & expected))
    return dict(iou=tp / (tp + fp + fn) if tp + fp + fn else 1.,
                precision=tp / (tp + fp) if tp + fp else None,
                recall=tp / (tp + fn) if tp + fn else None,
                tp=tp, fp=fp, fn=fn, valid_pixels=int(valid.sum()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--acceptance', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    acceptance = json.loads(args.acceptance.read_text())
    package = Path(acceptance['package_path'])
    rows = []
    run_manifest = json.loads((args.run / 'manifest.json').read_text())
    predictions = {}
    for path in (args.run / 'records').glob('*.json'):
        record = json.loads(path.read_text())
        if record['source_sha256'] in predictions:
            raise ValueError('Duplicate source identity')
        if record['contract_sha256'] != run_manifest['contract_sha256']:
            raise ValueError('Inference contract differs')
        predictions[record['source_sha256']] = record
    for accepted in acceptance['frames']:
        if accepted['status'] != 'student_accepted':
            raise ValueError('Unaccepted development reference')
        reference_path = package / accepted['mask']
        if sha256(reference_path) != accepted['mask_sha256']:
            raise ValueError('Accepted mask changed')
        reference = np.array(Image.open(reference_path))
        record = predictions[accepted['source_sha256']]
        scores = {}
        for method in ('baseline', 'repaired'):
            path = args.run / record[method]['path']
            if sha256(path) != record[method]['sha256']:
                raise ValueError('Prediction changed')
            scores[method] = metrics(np.array(Image.open(path)), reference)
        rows.append(dict(id=accepted['id'], image=record['image'], **scores,
                         delta_iou=scores['repaired']['iou'] - scores['baseline']['iou'],
                         changed_pixels=record['repair']['changed_pixels'], action=record['repair']['action']))
    if len(rows) != 30 or len(predictions) != 30:
        raise ValueError('Expected all 30 development images')
    means = {k: float(np.mean([r[k]['iou'] for r in rows])) for k in ('baseline', 'repaired')}
    report = dict(created_utc=utc_now(), count=30, mean_iou=means,
                  improved=sum(r['delta_iou'] > 1e-12 for r in rows),
                  regressed=sum(r['delta_iou'] < -1e-12 for r in rows),
                  unchanged=sum(abs(r['delta_iou']) <= 1e-12 for r in rows),
                  largest_regression=min(r['delta_iou'] for r in rows),
                  development_gate=means['repaired'] >= means['baseline'] and all(r['delta_iou'] >= -.005 for r in rows),
                  gate_rule='Mean development IoU must not decrease; no single-image drop greater than 0.005. A pass permits fresh diagnostic review, not production promotion.',
                  acceptance_sha256=sha256(args.acceptance), run_manifest_sha256=sha256(args.run / 'manifest.json'),
                  rows=rows, note='Agreement with repeatedly edited student-accepted development masks, not independent ground truth or fresh accuracy. Ignore-255 reference pixels excluded. References are read only by this post-inference evaluator.')
    write_json(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
