#!/usr/bin/env python3
"""Bounded, AI-assisted SAM 2 repairs of frozen proposals; maximum 30 images."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw

from label_grounded_sam2 import save_mask, sha256, utc_now, write_json
from sam_point_diagnostic import MODEL, REVISION, choose_mask, validate_points
from label_assisted_pilot import refinement_seed


def rectangle(box, size):
    w, h = size
    if (not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box)
            or not 0 <= box[0] < box[2] <= w or not 0 <= box[1] < box[3] <= h):
        raise ValueError('Invalid half-open region rectangle')
    region = np.zeros((h, w), dtype=bool)
    region[box[1]:box[3], box[0]:box[2]] = True
    return region


def merge_local(baseline, candidate, region, mode):
    if baseline.shape != candidate.shape or baseline.shape != region.shape:
        raise ValueError('Mask/region dimensions differ')
    if not np.isin(baseline, [0, 1, 255]).all():
        raise ValueError('Expected proposal labels 0/1/255')
    output = baseline.copy()
    if mode == 'replace':
        output[region] = candidate[region].astype(np.uint8)
    elif mode == 'add':
        output[region & candidate] = 1
    elif mode == 'subtract':
        output[region & candidate] = 0
    else:
        raise ValueError('Unknown repair mode')
    assert np.array_equal(output[~region], baseline[~region])
    return output


def load_plan(package, plan_path):
    manifest = json.loads((package / 'manifest.json').read_text())
    plan = json.loads(plan_path.read_text())
    if (plan.get('schema') != 'sidewalkpilot-hybrid-plan-v1'
            or plan.get('parent_package_id') != manifest['package_id']
            or not 0 < len(manifest['frames']) <= 30
            or [r['id'] for r in plan['frames']] != [f['id'] for f in manifest['frames']]):
        raise ValueError('Plan does not match the frozen sample')
    for f, p in zip(manifest['frames'], plan['frames']):
        if p['action'] not in ('keep', 'correct', 'redo', 'uncertain') or not p['reason']:
            raise ValueError('Every action needs a reason')
        if p['action'] == 'keep' and p['operations']:
            raise ValueError('Keep must have no edits')
        if sha256(package / f['image']) != f['source_sha256']:
            raise ValueError('Source changed')
        path = package / f['methods']['gsam2']['mask']
        if sha256(path) != f['methods']['gsam2']['sha256']:
            raise ValueError('Baseline changed')
        for op in p['operations']:
            rectangle(op['region'], f['size'])
            if op['kind'] == 'sam':
                if op['mode'] not in ('replace', 'add', 'subtract'):
                    raise ValueError('Invalid SAM merge mode')
                crop = op.get('crop', [0, 0, *f['size']])
                rectangle(crop, f['size'])
                points, _ = validate_points(op, *f['size'])
                if any(not crop[0] <= x < crop[2] or not crop[1] <= y < crop[3] for x, y in points):
                    raise ValueError('Prompt outside crop')
                a, b, c, d = op['region']
                if not crop[0] <= a < c <= crop[2] or not crop[1] <= b < d <= crop[3]:
                    raise ValueError('Edit region outside inferred crop')
            elif op['kind'] == 'paint':
                if op.get('value') not in (0, 1, 255):
                    raise ValueError('Invalid direct edit')
            else:
                raise ValueError('Unknown operation')
    return manifest, plan


def render(source, labels, path):
    rgb = np.array(source.convert('RGB'))
    for value, color in ((1, [50,197,144]), (255, [237,182,73])):
        take = labels == value
        rgb[take] = .7 * rgb[take] + .3 * np.array(color)
    Image.fromarray(rgb).save(path, quality=95)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('package', 'plan', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    manifest, plan = load_plan(args.package, args.plan)
    if args.validate_only:
        print(json.dumps({'images':len(plan['frames']), 'operations':sum(len(p['operations']) for p in plan['frames'])}))
        return
    if args.output.exists():
        raise ValueError('Output must be a new directory; old runs are immutable')
    input_hashes = {str(p.resolve()):sha256(p) for p in (args.plan, args.package/'manifest.json', Path(__file__))}
    for name in ('label_grounded_sam2.py', 'sam_point_diagnostic.py', 'label_assisted_pilot.py'):
        p = _workspace.source_path(name)
        input_hashes[str(p)] = sha256(p)
    args.output.mkdir(parents=True)
    for folder in ('candidates', 'records', 'proposals', 'preview'):
        (args.output / folder).mkdir()
    import torch
    from transformers import Sam2Model, Sam2Processor
    torch.set_num_threads(4)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    started = time.monotonic()
    processor = Sam2Processor.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
    model = Sam2Model.from_pretrained(MODEL, revision=REVISION, local_files_only=True).to('cuda').eval()
    torch.cuda.synchronize()
    loading_seconds = time.monotonic() - started
    write_json(args.output / 'config.json', {'model':MODEL,'revision':REVISION,'dtype':'float32',
        'parent_package_id':manifest['package_id'], 'plan_sha256':sha256(args.plan),
        'method':'Frozen GSAM 2 proposals + explicitly localized AI-assisted SAM 2 repairs',
        'minimum_quality':.7,'maximum_calls_per_region':2,
        'candidate_choice':'Highest estimated quality satisfying all points; retry once with mask feedback if no eligible candidate. This is not visual approval.',
        'review_status':'Unreviewed AI-assisted proposals; final candidate adoption requires separate visual inspection',
        'input_sha256':input_hashes, 'model_load_seconds':loading_seconds,
        'pixel_policy':'Baseline class 1 becomes 1; unassigned becomes provisional 0, not verified background. Only explicitly marked ambiguity is 255.'})
    records = []
    with torch.inference_mode():
        for number, (frame, row) in enumerate(zip(manifest['frames'], plan['frames']), 1):
            image = Image.open(args.package / frame['image']).convert('RGB')
            original = np.asarray(Image.open(args.package / frame['methods']['gsam2']['mask']))
            output = (original == 1).astype(np.uint8)
            baseline = output.copy()
            allowed = np.zeros(output.shape, dtype=bool)
            started = time.monotonic()
            steps = []
            for index, op in enumerate(row['operations']):
                region = rectangle(op['region'], image.size)
                allowed |= region
                step = {'operation':op,'candidate':None,'eligible':False}
                if op['kind'] == 'paint':
                    output[region] = op['value']
                    step.update(eligible=True, direct_edit=True)
                else:
                    crop = op.get('crop', [0,0,*image.size])
                    source = image.crop(crop)
                    pts, labels = validate_points(op, *image.size)
                    pts = [[x-crop[0],y-crop[1]] for x,y in pts]
                    inputs = processor(images=source, input_points=[[pts]], input_labels=[[labels]], return_tensors='pt').to('cuda')
                    result = model(**inputs, multimask_output=True)
                    trace = []
                    for attempt in range(2):
                        masks = processor.post_process_masks(result.pred_masks.cpu(), inputs.original_sizes.cpu())[0].numpy().reshape(-1,source.height,source.width).astype(bool)
                        scores = result.iou_scores.cpu().numpy().ravel()
                        selected, consistent = choose_mask(masks, scores, pts, labels)
                        seed, violations = refinement_seed(masks, scores, pts, labels)
                        trace.append({'attempt':attempt,'scores':scores.tolist(),'point_consistent':consistent,
                                      'point_violations':violations,'selected':selected})
                        for k, candidate in enumerate(masks):
                            path = args.output / 'candidates' / f'{number:02}-{index:02}-a{attempt}-c{k}.png'
                            save_mask(path, candidate.astype(np.uint8))
                        if selected is not None or attempt == 1 or seed is None:
                            break
                        result = model(**inputs, input_masks=result.pred_masks[:,0,seed:seed+1].detach(), multimask_output=True)
                    step['trace'] = trace
                    if selected is not None:
                        predicted = np.zeros(output.shape,dtype=bool)
                        predicted[crop[1]:crop[3],crop[0]:crop[2]] = masks[selected]
                        output = merge_local(output,predicted,region,op['mode'])
                        path = f'candidates/{number:02}-{index:02}-a{attempt}-c{selected}.png'
                        step.update(eligible=True,candidate=path,candidate_sha256=sha256(args.output/path))
                    else:
                        step['pending_reason'] = 'No point-consistent eligible candidate; baseline retained in this region.'
                steps.append(step)
            torch.cuda.synchronize()
            elapsed = time.monotonic()-started
            assert np.array_equal(output[~allowed],baseline[~allowed])
            path = args.output / 'proposals' / f'{number:02}.png'
            save_mask(path,output)
            render(image,output,args.output/'preview'/f'{number:02}.jpg')
            record = {'id':frame['id'],'image':frame['name'],'source_sha256':frame['source_sha256'],
                'baseline_sha256':frame['methods']['gsam2']['sha256'],'action':row['action'],'reason':row['reason'],
                'operations':steps,'mask':str(path.relative_to(args.output)),'mask_sha256':sha256(path),
                'changed_pixels':int((output!=baseline).sum()),'outside_region_changes':0,
                'processing_seconds':elapsed,'review_status':'unreviewed','created_utc':utc_now()}
            write_json(args.output/'records'/f'{number:02}.json',record)
            records.append(record)
            print(f"[{number}/30] {row['action']} {elapsed:.2f}s, {record['changed_pixels']} changed pixels; {sum(not s['eligible'] for s in steps)} pending regions",flush=True)
    for path, expected in input_hashes.items():
        if sha256(Path(path)) != expected:
            raise ValueError('Inputs changed during inference')
    load_plan(args.package,args.plan)
    write_json(args.output/'summary.json',{'images':len(records),'processing_seconds':sum(r['processing_seconds'] for r in records),
        'model_load_seconds':loading_seconds,'manual_annotation_seconds':None,'human_review_seconds':None,
        'changed_images':sum(r['changed_pixels']>0 for r in records),'pending_regions':sum(not s['eligible'] for r in records for s in r['operations']),
        'note':'Processing timing excludes manual planning and subsequent visual review. No accuracy claim or full-dataset run.'})


if __name__ == '__main__':
    main()
