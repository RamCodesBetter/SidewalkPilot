#!/usr/bin/env python3
"""Package frozen raw/repair proposals in the established offline A/B reviewer."""
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

from automatic_repair import validate_run_record
from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from package_paired_review import encode_binary

HERE = _workspace.TOOLS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    args = parser.parse_args()
    out, run = args.output.resolve(), args.run.resolve()
    selection = json.loads((run / 'selection.json').read_text())
    manifest = json.loads((run / 'manifest.json').read_text())
    source = Path(selection['source'])
    if out.exists() or args.mapping.exists():
        raise FileExistsError('Use new viewer and mapping paths')
    if out == source or source in out.parents or out in source.parents or out == run or run in out.parents:
        raise ValueError('Viewer must be separate from sources and inference outputs')
    if args.mapping.resolve().is_relative_to(out):
        raise ValueError('Keep private method assignments outside the viewer')
    if (len(selection['frames']) != 200 or manifest['contract']['selection_sha256'] != sha256(run / 'selection.json')
            or digest_json(manifest['contract']['recipe']) != selection['recipe_sha256']):
        raise ValueError('Expected a complete, frozen fresh 200-image run')
    rows = []
    for frame in selection['frames']:
        record = json.loads((run / 'records' / (Path(frame['image']).stem + '.json')).read_text())
        validate_run_record(run, record, frame, manifest['contract_sha256'])
        if sha256(source / frame['image']) != frame['source_sha256']:
            raise ValueError('Source changed')
        rows.append(record)
    out.mkdir(parents=True)
    for folder in ('images', 'masks'):
        (out / folder).mkdir()
    swaps = [False] * 100 + [True] * 100
    random.Random(selection['seed'] + 1).shuffle(swaps)
    selection_hash = sha256(run / 'selection.json')
    public = dict(kind='sidewalkpilot-paired-class1-v1', created_utc=utc_now(), count=200,
                  selection_sha256=selection_hash, review_scope=dict(kind='class', class_ids=[1]), pairs=[])
    private = dict(selection_sha256=selection_hash, method_names=['baseline', 'bounded_sam2'],
                   run_manifest_sha256=sha256(run / 'manifest.json'), pairs={})
    for number, (frame, record, swap) in enumerate(zip(selection['frames'], rows, swaps), 1):
        key = f'pair-{number:03d}'
        methods = ['bounded_sam2', 'baseline'] if swap else ['baseline', 'bounded_sam2']
        private['pairs'][key] = dict(image=frame['image'], **dict(zip(('A', 'B'), methods)))
        pair = dict(id=key, source_name=frame['image'], image=f'images/{number:03d}.jpg',
                    source_sha256=frame['source_sha256'], size=frame['size'], candidates={})
        shutil.copy2(source / frame['image'], out / pair['image'])
        for side, method in zip(('A', 'B'), methods):
            prediction = record['baseline' if method == 'baseline' else 'repaired']
            path = run / prediction['path']
            mask = np.array(Image.open(path))
            if mask.shape != tuple(reversed(frame['size'])) or not np.isin(mask, [1, 255]).all():
                raise ValueError('Unexpected proposal format')
            relative = f'masks/{number:03d}-{side}.png'
            shutil.copy2(path, out / relative)
            pair['candidates'][side] = dict(id=f'{key}-{side}', mask_sha256=prediction['sha256'],
                                           mask=relative, rle=encode_binary(mask == 1))
        public['pairs'].append(pair)
    public['package_id'] = digest_json(public)
    private['package_id'] = public['package_id']
    write_json(args.mapping, private)
    write_json(out / 'manifest.json', public)
    (out / 'data.js').write_text('window.PAIRED_DATA = ' + json.dumps(public, separators=(',', ':')) + ';\n')
    for name in ('paired.html', 'paired.js', 'paired.css', 'lucide.min.js', 'LUCIDE-LICENSE.txt'):
        shutil.copy2(HERE / 'review' / name, out / ('index.html' if name == 'paired.html' else name))
    (out / 'READ-ME.txt').write_text('''SidewalkPilot: fresh 200-image class-1 A/B review

Open index.html. Method identities are randomized per image and are not included
in this folder. Judge both A and B independently; either, both, or neither can
be correct. Identical masks are intentional when a method keeps its proposal.

1 = correct; 2 = needs correction, followed by 1 = minor, 2 = moderate,
3 = major; 3 outside the correction dialog = uncertain. Candidate switching waits
for a correction level. Finishing A always selects B. Auto next image controls
moving ahead after B. Enter skips ahead without assigning a rating.
Click A or B to select a mask and add notes/effort estimates.
Export with the download icon to sidewalkpilot-paired-review.json.

Sidewalk includes ordinary cracks, joints, stains and shadows, and the pedestrian
corridor across driveways. Exclude road, actual adjoining driveway pavement,
raised curb faces and visible occluding vegetation/objects. Mark meaningful
omissions/spillover/holes as needing correction. Use uncertain for unreadable
source boundaries. Non-highlighted pixels are unassigned, not verified negatives.

Active inspection time is browser-estimated for the selected candidate while
the page is visible/focused; pauses beyond 60 seconds without interaction and
long suspended timer intervals are excluded. It is not measured correction time.
Effort estimates remain separate. This tool does not edit mask pixels.

This is a duplicate-reduced labeling-workflow review, not held-out model accuracy,
an IID estimate for all images, or a twelve-class evaluation. No masks are
automatically approved. The previously accepted 30 development masks are preserved.
''')
    integrity = {str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob('*')) if p.is_file()}
    write_json(out / 'integrity-check.json', dict(package_id=public['package_id'], files_sha256=integrity))
    print(json.dumps(dict(package_id=public['package_id'], images=200, masks=400,
                         verified_files=len(integrity), output=str(out))))


if __name__ == '__main__':
    main()
