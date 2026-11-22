#!/usr/bin/env python3
"""A small SAM 3 -> explicit AI inspection/edit pilot, never automatic annotation."""
import argparse
import copy
import json
from pathlib import Path
import random
import shutil

import numpy as np
from PIL import Image, ImageDraw

from evaluate_class1_corrections import safe_file
from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from package_local_mask_revision import apply_edits
from package_paired_review import encode_binary

HERE = Path(__file__).resolve().parent
MODEL_REVISION = '3c879f39826c281e95690f02c7821c4de09afae7'
CHECKPOINT_SHA256 = '9999e2341ceef5e136daa386eecb55cb414446a00ac2b55eb2dfd2f7c3cf8c9e'


def load_selection(package):
    package = package.resolve()
    manifest = json.loads((package / 'manifest.json').read_text())
    content = {k:v for k,v in manifest.items() if k != 'package_id'}
    pairs = manifest.get('pairs', [])
    if (manifest.get('kind') != 'sidewalkpilot-paired-class1-v1'
            or not 0 < len(pairs) <= 30 or manifest.get('count') != len(pairs)
            or digest_json(content) != manifest.get('package_id')
            or len({p['id'] for p in pairs}) != len(pairs)
            or len({p['source_sha256'] for p in pairs}) != len(pairs)):
        raise ValueError('Expected an intact, distinct paired development pilot of at most 30 images')
    frames = []
    for pair in pairs:
        path = safe_file(package, pair['image'])
        with Image.open(path) as image:
            if sha256(path) != pair['source_sha256'] or list(image.size) != pair['size']:
                raise ValueError('Source image identity changed')
        frames.append({k:copy.deepcopy(pair[k]) for k in ('id','image','size','source_sha256','source_name')})
        frames[-1]['source_pair_id'] = pair.get('source_pair_id', pair['id'])
    return dict(source=str(package), parent_package_id=manifest['package_id'], frames=frames,
                images=[f['image'] for f in frames], count=len(frames),
                selection_sha256=sha256(package / 'manifest.json'),
                sampling='Repeated targeted development images; not a fresh random audit')


def load_inputs(package, sam3):
    selection = load_selection(package)
    config = json.loads((sam3 / 'config.json').read_text())
    summary = json.loads((sam3 / 'summary.json').read_text())
    if (config['model'] != 'facebook/sam3' or not config['native_sam3_control']
            or config.get('revision') != MODEL_REVISION or config.get('checkpoint_sha256') != CHECKPOINT_SHA256
            or config['prompt'] != 'concrete sidewalk' or config['score_threshold'] != .4
            or config['mask_threshold'] != .5 or not config['load_report']['strict']
            or config['selection_sha256'] != selection['selection_sha256']
            or summary['count'] != selection['count'] or len(summary['images']) != selection['count']):
        raise ValueError('Expected the complete pinned SAM 3 baseline on these exact images')
    rows = []
    for n, frame in enumerate(selection['frames'], 1):
        record = json.loads((sam3 / 'records' / f'{n:02d}.json').read_text())
        if (record != summary['images'][n-1] or any(record[k] != frame[k] for k in ('image','size','source_sha256'))):
            raise ValueError('SAM 3 result identity changed')
        path = safe_file(sam3, record['instance_union']['path'])
        labels = np.array(Image.open(path))
        if (sha256(path) != record['instance_union']['sha256'] or labels.shape != tuple(reversed(frame['size']))
                or not np.isin(labels, [1,255]).all()):
            raise ValueError('SAM 3 mask changed or invalid')
        rows.append((frame, record, labels))
    return selection, rows


def overlay(image, mask):
    pixels = np.array(image.convert('RGB')).copy()
    pixels[mask] = (pixels[mask] * .65 + np.array([35,225,140]) * .35).astype(np.uint8)
    return Image.fromarray(pixels)


def panel(image, before, after=None):
    views = [('Original', image), ('Raw SAM 3', overlay(image, before == 1))]
    if after is not None:
        views.append(('SAM 3 + AI edits / unreviewed', overlay(image, after == 1)))
    canvas = Image.new('RGB', (image.width * len(views), image.height + 32), 'white')
    draw = ImageDraw.Draw(canvas)
    for i, (title, view) in enumerate(views):
        draw.text((i*image.width+8,8), title, fill='black')
        canvas.paste(view, (i*image.width,32))
    return canvas


def revise(labels, decision):
    if decision.get('action') not in ('keep','correct','defer') or not decision.get('observation', '').strip():
        raise ValueError('Every image needs an explicit action and visual observation')
    edits = decision.get('edits', [])
    if (decision['action'] == 'correct') != bool(edits):
        raise ValueError('Only correct actions may contain edits; keep/defer preserve the raw mask')
    # 255 stays unassigned, not a verified negative. No geometry-only filter is run.
    output, report = apply_edits(labels, edits)
    if decision['action'] == 'correct' and not report['changed_pixels']:
        raise ValueError('Correction must actually change pixels')
    report['sidewalk_pixels_added'] = int(((output == 1) & (labels != 1)).sum())
    report['sidewalk_pixels_removed'] = int(((output != 1) & (labels == 1)).sum())
    return output, report


def build(package, sam3, out, edits=None, private=None):
    selection, rows = load_inputs(package, sam3)
    frozen = [package / 'manifest.json', sam3 / 'config.json', sam3 / 'summary.json']
    for n, (frame, record, _) in enumerate(rows, 1):
        frozen.extend((package / frame['image'], sam3 / 'records' / f'{n:02d}.json',
                       sam3 / record['instance_union']['path']))
    if edits:
        frozen.append(edits)
    input_hashes = {str(p.resolve()):sha256(p) for p in frozen}
    if out.exists() or any(out.resolve().is_relative_to(p.resolve()) or p.resolve().is_relative_to(out.resolve())
                           for p in (package, sam3)):
        raise ValueError('Use a new output path separate from all inputs')
    decisions = None
    if edits:
        plan = json.loads(edits.read_text())
        if (plan.get('schema') != 'sidewalkpilot-sam3-ai-edits-v1'
                or plan.get('parent_package_id') != selection['parent_package_id']
                or plan.get('sam3_config_sha256') != sha256(sam3 / 'config.json')
                or [f['id'] for f in plan['frames']] != [f['id'] for f in selection['frames']]):
            raise ValueError('Edits must identify exactly this selection and SAM 3 run')
        decisions = plan['frames']
        if (not private or private.exists()
                or any(private.resolve().is_relative_to(p.resolve()) for p in (out, package, sam3))):
            raise ValueError('Use a new private mapping outside the viewer')
    prepared = []
    for i, (frame, record, labels) in enumerate(rows):
        if decisions is not None:
            if decisions[i].get('raw_mask_sha256') != record['instance_union']['sha256']:
                raise ValueError('Edit targets another raw mask')
            corrected, report = revise(labels, decisions[i])
        else:
            corrected, report = None, None
        prepared.append((frame, record, labels, corrected, report))
    for folder in ('images','masks','panels','provenance'):
        (out / folder).mkdir(parents=True, exist_ok=True)
    write_json(out / 'provenance/selection.json', selection)
    shutil.copy2(sam3 / 'config.json', out / 'provenance/sam3-config.json')
    if edits:
        shutil.copy2(edits, out / 'provenance/ai-edits.json')
    shutil.copy2(Path(__file__), out / 'provenance/sam3_assisted_review.py')
    shutil.copy2(HERE / 'package_local_mask_revision.py', out / 'provenance/package_local_mask_revision.py')
    write_json(out / 'provenance/input-hashes.json', input_hashes)
    public = dict(kind='sidewalkpilot-paired-class1-v1', created_utc=utc_now(), count=len(rows),
                  review_scope=dict(kind='class',class_ids=[1]), title='SAM 3 + AI review',
                  sampling=selection['sampling'], selection_sha256=selection['selection_sha256'],
                  parent_package_id=selection['parent_package_id'], pairs=[])
    mapping = dict(method_names=['sam3_raw','sam3_ai_corrected'], selection_sha256=selection['selection_sha256'], pairs={})
    swaps = [i % 2 == 0 for i in range(len(rows))]
    random.Random(20261115).shuffle(swaps)
    reports = []
    for i, (frame, record, raw, corrected, report) in enumerate(prepared, 1):
        with Image.open(package / frame['image']) as im:
            image = im.convert('RGB')
        shutil.copy2(package / frame['image'], out / 'images' / f'{i:03d}.jpg')
        panel(image, raw, corrected).save(out / 'panels' / f'{i:03d}.jpg', quality=96)
        if corrected is None:
            continue
        pair = {k:copy.deepcopy(frame[k]) for k in ('id','source_pair_id','source_name','size','source_sha256')}
        pair.update(image=f'images/{i:03d}.jpg',candidates={})
        methods = ['sam3_raw','sam3_ai_corrected']
        if swaps[i-1]:
            methods.reverse()
        mapping['pairs'][pair['id']] = dict(image=pair['source_name'], **dict(zip(('A','B'), methods)))
        for side, method in zip(('A','B'), methods):
            path = out / 'masks' / f'{i:03d}-{side}.png'
            if method == 'sam3_raw' or decisions[i-1]['action'] in ('keep','defer'):
                shutil.copy2(sam3 / record['instance_union']['path'], path)
            else:
                Image.fromarray(corrected).save(path)
            values = np.array(Image.open(path))
            pair['candidates'][side] = dict(id=pair['id']+'-'+side,mask=str(path.relative_to(out)),
                                           mask_sha256=sha256(path),rle=encode_binary(values==1))
        public['pairs'].append(pair)
        reports.append(dict(id=pair['id'],action=decisions[i-1]['action'],**report))
    if decisions is not None:
        public['package_id'] = digest_json(public)
        mapping['package_id'] = public['package_id']
        write_json(private, mapping)
        write_json(out / 'manifest.json', public)
        write_json(out / 'provenance/edit-report.json', reports)
        (out / 'data.js').write_text('window.PAIRED_DATA = '+json.dumps(public,separators=(',',':'))+';\n')
        for name in ('paired.html','paired.js','paired.css','lucide.min.js','LUCIDE-LICENSE.txt'):
            shutil.copy2(HERE / 'review' / name, out / ('index.html' if name=='paired.html' else name))
        (out / 'READ-ME.txt').write_text('SAM 3 -> AI inspection and explicit local edits.\n'
            f'{len(rows)} previously viewed diagnostic images; not a new random sample.\n'
            'A/B assignment is randomized. Both start unreviewed. Source and raw masks are unchanged.\n'
            '1 correct; 2 needs correction then 1/2/3 severity; 3 uncertain; Enter skips.\n'
            'Finishing A selects B. Export sidewalkpilot-paired-review.json.\n'
            'These are AI-assisted proposals, not human reference labels. No SAM 2 or largest-component filter was used.\n')
    load_inputs(package, sam3)
    if any(sha256(Path(p)) != expected for p, expected in input_hashes.items()):
        raise ValueError('Frozen input changed during packaging; do not use this output')
    write_json(out / 'integrity-check.json', dict(files_sha256={str(p.relative_to(out)):sha256(p)
               for p in sorted(out.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(output=str(out),count=len(rows),reports=reports),indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('package','sam3','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--edits',type=Path)
    parser.add_argument('--private',type=Path)
    args = parser.parse_args()
    build(args.package,args.sam3,args.output,args.edits,args.private)


if __name__ == '__main__':
    main()
