#!/usr/bin/env python3
"""Adopt explicitly reviewed local repairs and package a frozen 30-image pilot."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

from evaluate_class1_corrections import safe_file
from hybrid_repair_pilot import load_plan, merge_local, rectangle, render
from label_grounded_sam2 import digest_json, save_mask, sha256, utc_now, write_json
from package_visual_comparison import encode_labels, rasterize

HERE = _workspace.TOOLS


def polygon_region(points, size):
    return rasterize({'sidewalk':[points], 'exclude':[], 'uncertain':[], 'notes':''}, size).astype(bool)


def guarded_region(region, interior, pixels):
    if type(pixels) is not int or pixels < 0 or region.shape != interior.shape:
        raise ValueError('Invalid interior guard')
    # A coarse polygon protects existing interior pixels; it does not supply labels.
    return region & (distance_transform_edt(interior) <= pixels)


def reconstruct(baseline, record, decision, guard, run):
    size = [baseline.shape[1], baseline.shape[0]]
    if len(record['operations']) != len(decision['operations']):
        raise ValueError('Every operation needs an explicit adoption decision')
    output = baseline.copy()
    allowed = np.zeros(baseline.shape, dtype=bool)
    changes = []
    for step, choice in zip(record['operations'], decision['operations']):
        if type(choice.get('accept')) is not bool or not choice.get('reason'):
            raise ValueError('Missing adoption decision or explanation')
        if not choice['accept']:
            changes.append(0)
            continue
        if not step['eligible']:
            raise ValueError('Cannot adopt an ineligible candidate')
        op = step['operation']
        region = rectangle(op['region'], size)
        if 'guard_pixels' in choice:
            if op['kind'] != 'sam' or op['mode'] != 'replace':
                raise ValueError('Interior guards apply only to edge replacement')
            region = guarded_region(region, guard, choice['guard_pixels'])
        before = output.copy()
        if op['kind'] == 'paint':
            output[region] = op['value']
        else:
            path = safe_file(run, step['candidate'])
            if sha256(path) != step['candidate_sha256']:
                raise ValueError('Candidate changed after inference')
            with Image.open(path) as im:
                local = np.asarray(im)
            crop = op.get('crop', [0,0,*size])
            if local.shape != (crop[3]-crop[1],crop[2]-crop[0]) or not np.isin(local,[0,1]).all():
                raise ValueError('Invalid candidate pixels or dimensions')
            mask = np.zeros(baseline.shape,dtype=bool)
            mask[crop[1]:crop[3],crop[0]:crop[2]] = local
            output = merge_local(output,mask,region,op['mode'])
        if not np.array_equal(output[~region], before[~region]):
            raise ValueError('Repair escaped its effective region')
        allowed |= region
        changes.append(int((before!=output).sum()))
    for edit in decision['direct_edits']:
        if not edit.get('reason') or edit.get('value') not in (0,1,255):
            raise ValueError('Invalid explicit fallback edit')
        if ('rectangle' in edit) == ('polygon' in edit):
            raise ValueError('Choose one edit shape')
        region = rectangle(edit['rectangle'], size) if 'rectangle' in edit else polygon_region(edit['polygon'], size)
        output[region] = edit['value']
        allowed |= region
    if not np.array_equal(output[~allowed],baseline[~allowed]):
        raise ValueError('Changes outside approved regions')
    return output, {'changed_pixels':int((output!=baseline).sum()),
                    'outside_effective_regions':0,'operation_changed_pixels':changes,
                    'effective_region_pixels':int(allowed.sum())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('package','plan','run','guard','decisions','output'):
        parser.add_argument('--'+key,required=True,type=Path)
    parser.add_argument('--preview-only',action='store_true')
    args = parser.parse_args()
    parent, plan = load_plan(args.package,args.plan)
    config = json.loads((args.run/'config.json').read_text())
    decisions = json.loads(args.decisions.read_text())
    guard = json.loads(args.guard.read_text())
    if (config['parent_package_id']!=parent['package_id'] or config['plan_sha256']!=sha256(args.plan)
            or decisions.get('schema')!='sidewalkpilot-hybrid-adoption-v1'
            or decisions['parent_package_id']!=parent['package_id']
            or decisions['run_config_sha256']!=sha256(args.run/'config.json')
            or decisions['guard_sha256']!=sha256(args.guard)
            or [d['id'] for d in decisions['frames']]!=[f['id'] for f in parent['frames']]
            or [a['id'] for a in guard['entries']]!=list(range(1,parent['count']+1))):
        raise ValueError('Adoption inputs do not match the frozen sample')
    if args.output.exists():
        raise ValueError('Choose a new output directory; preserve old packages')
    hashes = {}
    def track(path, expected=None):
        actual = sha256(path)
        if expected is not None and actual != expected:
            raise ValueError('Frozen input changed: '+str(path))
        hashes[str(path.resolve())] = actual
    for path, expected in config['input_sha256'].items():
        track(Path(path),expected)
    for path in (args.guard,args.decisions,args.run/'config.json',args.run/'summary.json',Path(__file__),_workspace.source_path('package_visual_comparison.py')):
        track(path)
    args.output.mkdir(parents=True)
    for name in ('images','masks','provenance','preview'):
        (args.output/name).mkdir()
    manifest = {k:copy.deepcopy(parent[k]) for k in ('schema','count','selection_sha256','seed','source_count','sampling')}
    manifest.update(created_utc=utc_now(),parent_package_id=parent['package_id'],
        methods={'gsam2':'GSAM 2','sam3':'SAM 3','codex':'GSAM 2 + assisted repairs'},
        review_methods=['codex'],annotation_revision=4,annotation_heading='Hybrid repair notes',
        uncertain_label='Hybrid uncertain',annotation_sha256=sha256(args.decisions),
        annotation_method='Frozen GSAM 2 proposals; AI-authored point-guided SAM 2 candidates; explicit adoption and localized fallback edits. Prior AI polygons protect interior pixels, not independent ground truth.',
        annotation_policy=parent['annotation_policy'],review_status='unreviewed',
        scope='Development pilot on the same previously inspected 30 images. Not a held-out accuracy benchmark or fully automatic labeling pipeline. No full-dataset run.',frames=[])
    reports=[]
    for number,(frame,row,choice,annotation) in enumerate(zip(parent['frames'],plan['frames'],decisions['frames'],guard['entries']),1):
        record_path=args.run/'records'/f'{number:02}.json'
        record=json.loads(record_path.read_text())
        track(record_path,choice['record_sha256'])
        if (record['id']!=frame['id'] or record['source_sha256']!=frame['source_sha256']
                or record['baseline_sha256']!=frame['methods']['gsam2']['sha256']
                or [s['operation'] for s in record['operations']]!=row['operations']):
            raise ValueError('Record identity or operation mismatch')
        for step in record['operations']:
            if step['candidate']:
                track(safe_file(args.run,step['candidate']),step['candidate_sha256'])
        source=safe_file(args.package,frame['image'])
        track(source,frame['source_sha256'])
        raw={}
        for method in ('gsam2','sam3'):
            path=safe_file(args.package,frame['methods'][method]['mask'])
            track(path,frame['methods'][method]['sha256'])
            with Image.open(path) as im:
                raw[method]=np.array(im)
            if raw[method].shape!=tuple(reversed(frame['size'])) or not np.isin(raw[method],[0,1,255]).all():
                raise ValueError('Invalid frozen reference')
        interior=rasterize(dict(annotation,exclude=[],uncertain=[]),frame['size']).astype(bool)
        baseline=(raw['gsam2']==1).astype(np.uint8)
        raw['codex'],report=reconstruct(baseline,record,choice,interior,args.run)
        if row['action']=='keep' and report['changed_pixels']:
            raise ValueError('A kept image was changed')
        report.update(id=frame['id'],action='kept' if not report['changed_pixels'] else 'locally_repaired',
            uncertainty_pixels=int((raw['codex']==255).sum()),
            adopted_operations=sum(c['accept'] for c in choice['operations']),
            rejected_operations=sum(not c['accept'] for c in choice['operations']),
            note=choice['notes'])
        reports.append(report)
        result={k:copy.deepcopy(frame[k]) for k in ('id','name','image','size','source_sha256')}
        result.update(annotation_notes=report['action'].replace('_',' ').capitalize()+'. '+choice['notes'],methods={})
        shutil.copy2(source,args.output/frame['image'])
        for method,mask in raw.items():
            path=args.output/'masks'/f'{number:02}-{method}.png'
            if method=='codex':
                save_mask(path,mask)
            else:
                shutil.copy2(args.package/frame['methods'][method]['mask'],path)
            displayed=mask if method=='codex' else (mask==1).astype(np.uint8)
            result['methods'][method]={'mask':str(path.relative_to(args.output)),'sha256':sha256(path),
                'positive_pixels':int((mask==1).sum()),'uncertain_pixels':int((mask==255).sum()) if method=='codex' else 0,
                'unassigned_pixels':int((mask==255).sum()) if method!='codex' else 0,'rle':encode_labels(displayed)}
        manifest['frames'].append(result)
        with Image.open(source) as im:
            render(im,raw['codex'],args.output/'preview'/f'{number:02}.jpg')
    summary={'images':len(reports),'kept':sum(r['action']=='kept' for r in reports),
        'repaired':sum(r['action']=='locally_repaired' for r in reports),
        'adopted_operations':sum(r['adopted_operations'] for r in reports),
        'rejected_operations':sum(r['rejected_operations'] for r in reports),
        'outside_effective_regions':sum(r['outside_effective_regions'] for r in reports),
        'timing':json.loads((args.run/'summary.json').read_text()),'reports':reports}
    write_json(args.output/'adoption-report.json',summary)
    if not args.preview_only:
        manifest['package_id']=digest_json(manifest)
        write_json(args.output/'manifest.json',manifest)
        (args.output/'data.js').write_text('window.COMPARISON_DATA = '+json.dumps(manifest,separators=(',',':'))+';\n')
        for name in ('comparison.html','comparison.js','comparison.css','lucide.min.js','LUCIDE-LICENSE.txt'):
            p=HERE/'review'/name
            track(p)
            shutil.copy2(p,args.output/('index.html' if name=='comparison.html' else name))
        for path,name in ((args.plan,'repair-plan.json'),(args.decisions,'adoption-decisions.json'),
                (args.guard,'interior-guard-polygons.json'),(args.package/'manifest.json','parent-manifest.json')):
            shutil.copy2(path,args.output/'provenance'/name)
        shutil.copytree(args.run,args.output/'provenance'/'inference-run')
        for filename in ('hybrid_repair_pilot.py','sam_point_diagnostic.py','label_assisted_pilot.py',
                         'label_grounded_sam2.py','package_visual_comparison.py',Path(__file__).name):
            shutil.copy2(_workspace.source_path(filename),args.output/'provenance'/filename)
        (args.output/'READ-ME.txt').write_text('''SidewalkPilot: same 30 images, model-first hybrid pilot

Open index.html. No installation or server is required.
Original, GSAM 2 and SAM 3 are unchanged references. Rate only
"GSAM 2 + assisted repairs". 1 = correct; 2 = needs correction,
then 1/2/3 = minor/moderate/major; 3 = uncertain; Enter = next.
Export your review JSON after finishing. Old-package ratings are separate.

Green is proposed sidewalk, amber is explicit uncertainty (255).
Raw GSAM/SAM 255 means unassigned, not verified background. Hybrid 0 is
provisional non-sidewalk, not independently verified ground truth.
Cracks, slab joints, stains and cast shadows remain sidewalk; visible
occluding objects do not. Include the sidewalk corridor through driveways,
not the adjoining driveway. Ambiguous boundaries remain for review.

These are GSAM 2-seeded proposals, NOT independent Codex polygon labels.
AI-assisted local point prompts generated SAM 2 candidates. Each operation
has an explicit adopt/reject decision, with localized fallback edits.
Prior AI polygons were used as coarse interior guards, not pixel references.
Guards prevent boundary repairs from changing deep-interior pixels. They
do not make either the old or new outlines correct. Keep/repaired describes
processing, not a human correctness rating. No mask is certified correct.

The internal key "codex" is retained for compatibility with the review
export format; manifest.methods gives its actual hybrid method name.
Plan, candidates, adoption decisions, input hashes and run timing are in
provenance. GPU inference timing excludes manual planning/review time,
which was not measured. This is not a fully automated 81k-image pipeline,
a blinded comparison, or a held-out accuracy evaluation. These same images
have been inspected repeatedly during development. Nothing was retrained.
''')
    for path,expected in hashes.items():
        if sha256(Path(path))!=expected:
            raise ValueError('Input changed while packaging')
    write_json(args.output/'integrity-check.json',{'input_sha256':hashes,
        'files_sha256':{str(p.relative_to(args.output)):sha256(p) for p in sorted(args.output.rglob('*')) if p.is_file()}})
    print(json.dumps({k:v for k,v in summary.items() if k not in ('reports','timing')},indent=2))


if __name__=='__main__':
    main()
