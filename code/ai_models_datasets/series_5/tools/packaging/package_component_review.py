#!/usr/bin/env python3
"""Package a targeted before/after component-filter diagnostic, not a fresh audit."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import json
from pathlib import Path
import random
import shutil

import numpy as np
from PIL import Image

from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from package_paired_review import encode_binary
from score_paired_review import score

HERE = _workspace.TOOLS


def select_cases(pairs, trials, ratings, seed=20261114):
    selected, reasons = [], {}
    def add(rows, limit, reason):
        added = 0
        for row in rows:
            if row['id'] not in reasons:
                selected.append(row)
                reasons[row['id']] = reason
                added += 1
                if added == limit:
                    break
    changed = [p for p in pairs if trials[p['source_name']]['removed_pixels']]
    unchanged = [p for p in pairs if not trials[p['source_name']]['removed_pixels']]
    if len(changed) < 16 or len(unchanged) < 4:
        raise ValueError('This diagnostic needs 16 changed and 4 unchanged cases')
    add([p for p in changed if p['id'] == 'pair-008'], 1, 'student-reported speck')
    ordered = sorted(changed, key=lambda p:(-trials[p['source_name']]['removed_pixels'], p['id']))
    add(ordered, 4, 'largest deletions; inspect for lost sidewalk')
    add([p for p in ordered if ratings[p['id']]['decision'] == 'correct'], 4,
        'previously accepted mask changed; regression control')
    add([p for p in ordered if ratings[p['id']].get('correction_level') == 3], 4,
        'previous major failure; check whether large errors remain')
    pool = changed.copy()
    random.Random(seed).shuffle(pool)
    if len(selected) < 16:
        add(pool, 16-len(selected), 'random additional changed case')
    random.Random(seed+1).shuffle(unchanged)
    add(unchanged, 4, 'unchanged control')
    assert len(selected) == 20
    return selected, reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('trial', 'package', 'review', 'mapping', 'output', 'private'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--method', choices=('baseline', 'repaired'), default='baseline')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or args.private.exists() or args.private.resolve().is_relative_to(out):
        raise ValueError('Use new paths and keep private assignments outside the viewer')
    tracked = {}
    for root in (args.package, args.trial):
        integrity = json.loads((root / 'integrity-check.json').read_text())
        for name, expected in integrity['files_sha256'].items():
            path = root / name
            if sha256(path) != expected:
                raise ValueError('Frozen input changed: ' + str(path))
            tracked[path] = expected
    manifest = json.loads((args.package / 'manifest.json').read_text())
    mapping = json.loads(args.mapping.read_text())
    review = json.loads(args.review.read_text())
    if not score(manifest, mapping, review)['complete']:
        raise ValueError('Expected the completed parent review')
    experiment = json.loads((args.trial / 'manifest.json').read_text())
    trials = {r['image']:r['methods'][args.method] for r in experiment['rows']}
    before_method = 'baseline' if args.method == 'baseline' else 'bounded_sam2'
    before_sides = {p['id']:next(s for s in ('A','B') if mapping['pairs'][p['id']][s] == before_method)
                    for p in manifest['pairs']}
    ratings = {p['id']:review['decisions'][p['id']][before_sides[p['id']]] for p in manifest['pairs']}
    selected, reasons = select_cases(manifest['pairs'], trials, ratings)
    private = dict(method_names=['before','largest_component'], input_method=before_method,
                   parent_review_sha256=sha256(args.review), parent_mapping_sha256=sha256(args.mapping),
                   trial_manifest_sha256=sha256(args.trial / 'manifest.json'),
                   selection_reasons=reasons, pairs={})
    public = dict(kind='sidewalkpilot-paired-class1-v1', created_utc=utc_now(), count=len(selected),
                  review_scope=dict(kind='class', class_ids=[1]),
                  title='Largest-region diagnostic',
                  sampling='Targeted previously reviewed development subset: 16 changed plus 4 unchanged controls; not a fresh accuracy sample',
                  selection_sha256=digest_json(dict(source_ids=[p['id'] for p in selected],
                      trial_sha256=sha256(args.trial / 'manifest.json'), method=args.method, seed=20261114)),
                  parent_package_id=manifest['package_id'], pairs=[])
    swaps = [False]*10 + [True]*10
    random.Random(20261114+2).shuffle(swaps)
    (out / 'images').mkdir(parents=True)
    (out / 'masks').mkdir()
    for i, (original, swap) in enumerate(zip(selected, swaps), 1):
        pair = dict(id=f'pair-{i:03d}', source_pair_id=original['id'], source_name=original['source_name'],
                    image=f'images/{i:03d}.jpg', source_sha256=original['source_sha256'],
                    size=original['size'], candidates={})
        shutil.copy2(args.package / original['image'], out / pair['image'])
        before = original['candidates'][before_sides[original['id']]]
        after = trials[original['source_name']]
        if before['mask_sha256'] != after['before_sha256']:
            raise ValueError('Trial does not match reviewed input mask')
        paths = {'before':args.package / before['mask'], 'largest_component':args.trial / after['path']}
        methods = ['largest_component', 'before'] if swap else ['before', 'largest_component']
        private['pairs'][pair['id']] = dict(image=pair['source_name'], source_pair_id=original['id'],
                                           **dict(zip(('A','B'), methods)))
        for side, method in zip(('A','B'), methods):
            path = out / 'masks' / f'{i:03d}-{side}.png'
            shutil.copy2(paths[method], path)
            labels = np.array(Image.open(path))
            if not np.isin(labels, [1,255]).all() or labels.shape != tuple(reversed(pair['size'])):
                raise ValueError('Invalid candidate labels or shape')
            pair['candidates'][side] = dict(id=pair['id']+'-'+side, mask_sha256=sha256(path),
                mask=str(path.relative_to(out)), rle=encode_binary(labels == 1))
        public['pairs'].append(pair)
    public['package_id'] = digest_json(public)
    private.update(package_id=public['package_id'], selection_sha256=public['selection_sha256'])
    write_json(args.private, private)
    write_json(out / 'manifest.json', public)
    (out / 'data.js').write_text('window.PAIRED_DATA = ' + json.dumps(public, separators=(',', ':')) + ';\n')
    for name in ('paired.html','paired.js','paired.css','lucide.min.js','LUCIDE-LICENSE.txt'):
        shutil.copy2(HERE / 'review' / name, out / ('index.html' if name == 'paired.html' else name))
    (out / 'READ-ME.txt').write_text('''SidewalkPilot: largest-component diagnostic (20 images)

Open index.html. These are 16 changed cases and 4 unchanged controls selected
from the completed 200-image review. The original sample ID appears above each
image. A/B assignments are randomized; judge both masks independently.
The first pair is original sample 008, which contained the reported speck.

1 = correct; 2 = needs correction, followed by 1/2/3 for minor/moderate/major;
3 outside that dialog = uncertain. Finishing A selects B. Auto next image
advances after B. Enter skips without rating. Export sidewalkpilot-paired-review.json.
New candidates start unrated; the original 400 ratings are archived unchanged.

This is a removal-only largest-connected-region experiment. It does not fill
holes, repair missing sidewalk or remove errors connected to the main region.
It may delete legitimate disconnected sidewalk. This targeted repeat review
does not establish a new full-dataset acceptance rate. No masks are auto-approved.
''')
    for path, expected in tracked.items():
        if sha256(path) != expected:
            raise ValueError('Input changed during packaging')
    write_json(out / 'integrity-check.json', dict(package_id=public['package_id'],
        files_sha256={str(p.relative_to(out)):sha256(p) for p in sorted(out.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(output=str(out), count=len(selected), package_id=public['package_id'],
                         source_ids=[p['id'] for p in selected]), indent=2))


if __name__ == '__main__':
    main()
