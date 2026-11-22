#!/usr/bin/env python3
"""Removal-only largest-component experiment; preserve frozen inputs and review status."""
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

POLICY = dict(version='largest-sidewalk-component-v1', connectivity=8,
              tie_policy='defer and preserve all components',
              empty_policy='preserve empty mask and flag',
              removal_label=255, fills_holes=False, adds_sidewalk=False,
              scope='Unverified class-1 proposals, not a traversability or safety filter')


def largest_component(mask):
    mask = np.asarray(mask)
    if mask.ndim != 2 or mask.size == 0 or not np.isin(mask, [0, 1]).all():
        raise ValueError('Expected a nonempty 2D binary mask')
    mask = mask.astype(bool)
    labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=np.uint8))
    sizes = np.bincount(labels.ravel())[1:]
    result = mask.copy()
    flags = []
    if not count:
        flags.append('no_sidewalk')
    else:
        winners = np.flatnonzero(sizes == sizes.max()) + 1
        if len(winners) > 1:
            flags.append('tied_largest_components')
        else:
            result = labels == winners[0]
    removed = mask & ~result
    assert not (result & ~mask).any()
    return result, dict(components_before=int(count),
                       component_sizes=sorted(map(int, sizes), reverse=True),
                       removed_pixels=int(removed.sum()),
                       removed_fraction_of_image=float(removed.mean()),
                       removed_fraction_of_positive=float(removed.sum() / mask.sum()) if mask.any() else 0.,
                       action='deferred' if flags else ('largest_component_only' if removed.any() else 'unchanged'),
                       flags=flags)


def experiment(run, output, acceptance=None):
    # Inference uses only saved predictions; references are opened for scoring afterwards.
    from PIL import Image
    from automatic_repair import validate_run_record
    from evaluate_automatic_repair import metrics
    from label_grounded_sam2 import digest_json, save_mask, sha256, utc_now, write_json

    run, output = run.resolve(), output.resolve()
    manifest = json.loads((run / 'manifest.json').read_text())
    selection = json.loads((run / 'selection.json').read_text())
    source = Path(selection['source']).resolve()
    if output.exists() or any(output == p or output.is_relative_to(p) or p.is_relative_to(output)
                              for p in (run, source)):
        raise ValueError('Use a new output directory separate from inputs')
    if (not 0 < len(selection['frames']) <= 200
            or digest_json(manifest['contract']) != manifest['contract_sha256']
            or sha256(run / 'selection.json') != manifest['contract']['selection_sha256']):
        raise ValueError('Invalid frozen input selection or contract')
    records, tracked = [], {}
    for frame in selection['frames']:
        record_path = run / 'records' / (Path(frame['image']).stem + '.json')
        record = json.loads(record_path.read_text())
        validate_run_record(run, record, frame, manifest['contract_sha256'])
        if sha256(source / frame['image']) != frame['source_sha256']:
            raise ValueError('Source image changed')
        for method in ('baseline', 'repaired'):
            tracked[run / record[method]['path']] = record[method]['sha256']
        tracked[record_path] = sha256(record_path)
        records.append(record)
    if len({r['source_sha256'] for r in records}) != len(records):
        raise ValueError('Duplicate source identity')
    tracked[run / 'manifest.json'] = sha256(run / 'manifest.json')
    tracked[run / 'selection.json'] = sha256(run / 'selection.json')
    output.mkdir(parents=True)
    contract = dict(policy=POLICY, code_sha256=sha256(Path(__file__)),
                    input_manifest_sha256=sha256(run / 'manifest.json'),
                    selection_sha256=sha256(run / 'selection.json'))
    rows = []
    for number, record in enumerate(records, 1):
        row = dict(image=record['image'], source_sha256=record['source_sha256'], size=record['size'], methods={})
        for method in ('baseline', 'repaired'):
            before = np.array(Image.open(run / record[method]['path']))
            if before.shape != tuple(reversed(record['size'])) or not np.isin(before, [1, 255]).all():
                raise ValueError('Unexpected input mask labels or shape')
            keep, detail = largest_component(before == 1)
            after = before.copy()
            after[(before == 1) & ~keep] = 255
            path = output / 'masks' / method / (Path(record['image']).stem + '.png')
            path.parent.mkdir(parents=True, exist_ok=True)
            save_mask(path, after)
            row['methods'][method] = dict(**detail, before_path=record[method]['path'],
                                         before_sha256=record[method]['sha256'],
                                         path=str(path.relative_to(output)), sha256=sha256(path),
                                         positive_pixels=int(keep.sum()), review_status='unreviewed')
        rows.append(row)
        print(f'[{number}/{len(records)}] largest-component candidates saved', flush=True)
    report = dict(created_utc=utc_now(), contract=contract, contract_sha256=digest_json(contract),
                  input_run=str(run), source=str(source), count=len(rows), rows=rows,
                  review_status='No new human ratings or automatic acceptance',
                  purpose='Development reanalysis of existing images, not a fresh random accuracy audit')
    totals = {method:dict(changed=sum(r['methods'][method]['removed_pixels'] > 0 for r in rows),
                         removed_pixels=sum(r['methods'][method]['removed_pixels'] for r in rows),
                         actions=dict(Counter(r['methods'][method]['action'] for r in rows)))
              for method in ('baseline', 'repaired')}
    if acceptance:
        accepted = json.loads(acceptance.read_text())
        references = {f['source_sha256']: f for f in accepted['frames']}
        if set(references) != {r['source_sha256'] for r in rows}:
            raise ValueError('References must match exactly this development selection')
        scored = []
        for row in rows:
            reference = references[row['source_sha256']]
            ref_path = Path(accepted['package_path']) / reference['mask']
            if reference['status'] != 'student_accepted' or sha256(ref_path) != reference['mask_sha256']:
                raise ValueError('Accepted reference changed')
            tracked[ref_path] = reference['mask_sha256']
            labels = np.array(Image.open(ref_path))
            score_row = dict(id=reference['id'], image=row['image'], methods={})
            for method, candidate in row['methods'].items():
                before = np.array(Image.open(run / candidate['before_path']))
                after = np.array(Image.open(output / candidate['path']))
                removed = (before == 1) & (after != 1)
                prior, following = metrics(before, labels), metrics(after, labels)
                score_row['methods'][method] = dict(before=prior, after=following,
                    delta_iou=following['iou'] - prior['iou'],
                    removed_reference_sidewalk=int((removed & (labels == 1)).sum()),
                    removed_reference_non_sidewalk=int((removed & (labels == 0)).sum()))
            scored.append(score_row)
        for method in totals:
            values = [r['methods'][method] for r in scored]
            totals[method].update(mean_iou_before=float(np.mean([r['before']['iou'] for r in values])),
                mean_iou_after=float(np.mean([r['after']['iou'] for r in values])),
                improved=sum(r['delta_iou'] > 1e-12 for r in values),
                regressed=sum(r['delta_iou'] < -1e-12 for r in values),
                unchanged=sum(abs(r['delta_iou']) <= 1e-12 for r in values),
                largest_regression=min(r['delta_iou'] for r in values),
                removed_reference_sidewalk=sum(r['removed_reference_sidewalk'] for r in values),
                removed_reference_non_sidewalk=sum(r['removed_reference_non_sidewalk'] for r in values))
        write_json(output / 'development-evaluation.json', dict(acceptance_sha256=sha256(acceptance),
            totals=totals, rows=scored, note='Agreement with repeatedly corrected development references, not independent accuracy'))
    for path, expected in tracked.items():
        if sha256(path) != expected:
            raise ValueError('Frozen input changed during the experiment')
    write_json(output / 'manifest.json', report)
    write_json(output / 'summary.json', dict(count=len(rows), methods=totals))
    write_json(output / 'integrity-check.json', dict(input_sha256={str(p):h for p,h in tracked.items()},
        files_sha256={str(p.relative_to(output)):sha256(p) for p in sorted(output.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(count=len(rows), methods=totals), indent=2))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('run', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--acceptance', type=Path)
    args = parser.parse_args()
    experiment(args.run, args.output, args.acceptance)
