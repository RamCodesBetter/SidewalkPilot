#!/usr/bin/env python3
"""Deterministic, bounded SAM 2 proposal repairs; no reference labels in inference."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
from collections import Counter
import fcntl
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
from scipy import ndimage

from label_grounded_sam2 import GroundedSam2, digest_json, save_mask, sha256, utc_now, write_json
from sam_point_diagnostic import choose_mask

HERE = _workspace.TOOLS
DEPENDENCIES = ('automatic_repair.py', 'label_grounded_sam2.py', 'sam_point_diagnostic.py')


def validate_config(cfg):
    for key in ('boundary_pixels_at_720p', 'core_pixels_at_720p', 'thin_hole_radius_at_720p',
                'grid_cells_per_axis'):
        if type(cfg[key]) is not int or cfg[key] <= 0:
            raise ValueError('Expected a positive integer: ' + key)
    for key in ('max_hole_fraction', 'minimum_sam_quality', 'minimum_proposal_agreement',
                'maximum_change_fraction', 'maximum_outside_change_fraction',
                'maximum_disagreement_fraction', 'minimum_coverage', 'maximum_coverage',
                'component_fraction'):
        if not isinstance(cfg[key], (int, float)) or not 0 < cfg[key] < 1:
            raise ValueError('Expected a fraction in (0,1): ' + key)
    if cfg['minimum_coverage'] >= cfg['maximum_coverage'] or not 2 <= cfg['grid_cells_per_axis'] <= 8:
        raise ValueError('Invalid coverage limits or insufficient point pool')
    if type(cfg['use_proposal_mask_feedback']) is not bool or not 0 < cfg['mask_feedback_logit'] <= 10:
        raise ValueError('Invalid mask feedback configuration')
    return cfg


def binary(value):
    value = np.asarray(value)
    if value.ndim != 2 or value.size == 0 or not np.isin(value, [0, 1, False, True]).all():
        raise ValueError('Expected a nonempty two-dimensional binary mask')
    return value.astype(bool)


def regions(proposal, cfg):
    proposal = binary(proposal)
    scale = min(proposal.shape) / 720
    band = max(1, round(cfg['boundary_pixels_at_720p'] * scale))
    core_radius = max(band + 1, round(cfg['core_pixels_at_720p'] * scale))
    inside = ndimage.distance_transform_edt(proposal)
    outside = ndimage.distance_transform_edt(~proposal)
    holes = ndimage.binary_fill_holes(proposal) & ~proposal
    hole_ids, count = ndimage.label(holes)
    thin_holes = np.zeros_like(proposal)
    for number, box in enumerate(ndimage.find_objects(hole_ids), 1):
        if box is None:
            continue
        component = hole_ids[box] == number
        if (component.sum() <= proposal.size * cfg['max_hole_fraction']
                and outside[box][component].max() <= max(1, cfg['thin_hole_radius_at_720p'] * scale)):
            thin_holes[box] |= component
    eligible = (proposal & (inside <= band)) | (~proposal & ~holes & (outside <= band)) | thin_holes
    positive = proposal & (inside >= core_radius)
    negative = ~proposal & ~holes & (outside >= core_radius)
    return eligible, positive, negative, holes & ~thin_holes


def automatic_prompts(proposal, cfg):
    eligible, positive, negative, protected = regions(proposal, cfg)
    # Distribute anchors across spatial cells rather than clustering at the deepest
    # foreground or distant sky. Negative points come from the exterior edge ring.
    exterior_distance = ndimage.distance_transform_edt(~proposal)
    negative &= exterior_distance <= max(4, cfg['core_pixels_at_720p'] * 4 * min(proposal.shape) / 720)
    pp, nn = grid_points(positive, cfg['grid_cells_per_axis']), grid_points(negative, cfg['grid_cells_per_axis'])
    if len(pp) < 4 or len(nn) < 4:
        return [], eligible, protected
    prompts = []
    for offset in (0, 1):
        positives, negatives = pp[offset::2], nn[offset::2]
        prompts.append(dict(points=positives + negatives, labels=[1] * len(positives) + [0] * len(negatives)))
    return prompts, eligible, protected


def grid_points(region, divisions=4):
    distance = ndimage.distance_transform_edt(region)
    height, width = region.shape
    points = []
    for row in range(divisions):
        for col in range(divisions):
            y0, y1 = row * height // divisions, (row + 1) * height // divisions
            x0, x1 = col * width // divisions, (col + 1) * width // divisions
            cell = distance[y0:y1, x0:x1]
            if cell.size and cell.max() > 0:
                y, x = np.unravel_index(cell.argmax(), cell.shape)
                points.append([int(x + x0), int(y + y0)])
    return points


def iou(left, right):
    left, right = binary(left), binary(right)
    if left.shape != right.shape:
        raise ValueError('Mask shapes differ')
    union = np.count_nonzero(left | right)
    return float(np.count_nonzero(left & right) / union) if union else 1.0


def bounded_merge(proposal, candidates, cfg):
    """Intersect two model edit proposals, then gate the complete bounded edit."""
    proposal = binary(proposal)
    allowed, _, _, protected = regions(proposal, cfg)
    if len(candidates) != 2:
        return proposal.copy(), dict(action='deferred', flags=['two_eligible_passes_required'], changed_pixels=0)
    first, second = (binary(c) for c in candidates)
    if first.shape != proposal.shape or second.shape != proposal.shape:
        raise ValueError('Candidate dimensions differ')
    agreement = [iou(proposal, c) for c in (first, second)]
    consensus_change = (first == second) & (first != proposal)
    outside = int(np.count_nonzero(consensus_change & ~allowed))
    disagreement = int(np.count_nonzero(first != second))
    change = consensus_change & allowed
    flags = []
    if min(agreement) < cfg['minimum_proposal_agreement']:
        flags.append('large_candidate_geometry_change')
    if outside / proposal.size > cfg['maximum_outside_change_fraction']:
        flags.append('large_change_outside_allowed_region')
    if disagreement / proposal.size > cfg['maximum_disagreement_fraction']:
        flags.append('point_pass_disagreement')
    if change.mean() > cfg['maximum_change_fraction']:
        flags.append('change_budget_exceeded')
    result = proposal.copy()
    if not flags:
        result[change] = first[change]
    assert np.array_equal(result[~allowed], proposal[~allowed])
    assert np.array_equal(result[protected], proposal[protected])
    return result, dict(
        action='deferred' if flags else ('bounded_repair_proposal' if change.any() else 'unchanged_proposal'),
        flags=flags, changed_pixels=int(np.count_nonzero(result != proposal)),
        proposed_changed_pixels=int(change.sum()), outside_candidate_changes=outside,
        pass_disagreement_pixels=disagreement, proposal_agreement=agreement,
        allowed_pixels=int(allowed.sum()), protected_hole_pixels=int(protected.sum()))


def image_flags(image, proposal, cfg):
    proposal = binary(proposal)
    gray = np.asarray(image.convert('L').resize((512, 288)), dtype=np.float32)
    variance = float(ndimage.laplace(gray).var())
    labels, count = ndimage.label(proposal)
    sizes = np.bincount(labels.ravel())[1:]
    significant = int(np.count_nonzero(sizes >= proposal.size * cfg['component_fraction']))
    flags = []
    if not cfg['minimum_coverage'] <= proposal.mean() <= cfg['maximum_coverage']:
        flags.append('unusual_coverage')
    if variance < cfg['minimum_blur_variance']:
        flags.append('blurred_source')
    if significant > 1:
        flags.append('multiple_large_components')
    return flags, dict(coverage=float(proposal.mean()), blur_variance=variance, significant_components=significant)


def repair(image, proposal, cfg, labeler):
    flags, qa = image_flags(image, proposal, cfg)
    prompts, _, _ = automatic_prompts(proposal, cfg)
    if not prompts or 'unusual_coverage' in flags:
        return proposal.copy(), dict(action='deferred', flags=flags + ['insufficient_seed_geometry'],
                                    changed_pixels=0, prompts=prompts, passes=[], image_qa=qa)
    torch, processor, model = labeler.torch, labeler.sam_processor, labeler.sam
    passes, candidates = [], []
    with torch.inference_mode():
        image_input = processor(images=image, return_tensors='pt').to('cuda')
        embeddings = model.get_image_embeddings(image_input.pixel_values)
        extra = {}
        if cfg['use_proposal_mask_feedback']:
            if tuple(image_input.pixel_values.shape[-2:]) != (1024, 1024):
                raise ValueError('Proposal mask feedback requires the pinned square 1024-pixel processor')
            prior = torch.from_numpy(proposal.astype(np.float32))[None, None].to('cuda')
            prior = torch.nn.functional.interpolate(prior, size=(256, 256), mode='bilinear', align_corners=False)
            extra['input_masks'] = (prior * 2 - 1) * cfg['mask_feedback_logit']
        for prompt in prompts:
            inputs = processor(original_sizes=image_input.original_sizes,
                               input_points=[[prompt['points']]], input_labels=[[prompt['labels']]],
                               return_tensors='pt').to('cuda')
            outputs = model(image_embeddings=embeddings, input_points=inputs.input_points,
                            input_labels=inputs.input_labels, multimask_output=True, **extra)
            masks = processor.post_process_masks(outputs.pred_masks.cpu(), image_input.original_sizes.cpu())[0]
            masks = masks.numpy().reshape(-1, image.height, image.width).astype(bool)
            qualities = outputs.iou_scores.cpu().numpy().ravel()
            selected, consistent = choose_mask(masks, qualities, prompt['points'], prompt['labels'], cfg['minimum_sam_quality'])
            passes.append(dict(quality=[float(q) if np.isfinite(q) else None for q in qualities],
                               point_consistent=consistent, selected=selected))
            if selected is not None:
                candidates.append(masks[selected])
    result, detail = bounded_merge(proposal, candidates, cfg)
    detail.update(prompts=prompts, passes=passes, image_qa=qa)
    detail['flags'] = list(dict.fromkeys(flags + detail['flags']))
    detail['priority'] = 'manual_review' if detail['flags'] else 'random_audit_eligible'
    return result, detail


def recipe(config_path, grounding_path):
    cfg = validate_config(json.loads(config_path.read_text()))
    grounded = json.loads(grounding_path.read_text())
    if grounded.get('diagnostic_class_ids') != [1] or grounded.get('prompt_groups') != [[1]]:
        raise ValueError('This runner requires the sidewalk-only grounding recipe')
    return dict(repair=cfg, grounding=grounded, taxonomy_sha256=sha256(_workspace.source_path('taxonomy.json')),
                code_sha256={n: sha256(_workspace.source_path(n)) for n in DEPENDENCIES},
                packages={n: importlib.metadata.version(n) for n in ('torch','torchvision','transformers','numpy','scipy','Pillow')})


def validate_run_record(root, record, frame, contract_hash):
    if (record['image'] != frame['image'] or record['source_sha256'] != frame['source_sha256']
            or record['contract_sha256'] != contract_hash):
        raise ValueError('Stored record identity changed')
    for key in ('baseline', 'repaired'):
        relative = record[key]['path']
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path) != record[key]['sha256']:
            raise ValueError('Stored prediction changed')


def run(args):
    selection = json.loads(args.selection.read_text())
    frames = selection['frames']
    source = Path(selection['source']).resolve()
    if (not 0 < len(frames) <= 200 or len({f['image'] for f in frames}) != len(frames)
            or selection['images'] != [f['image'] for f in frames]):
        raise ValueError('Expected 1-200 unique, ordered source frames')
    for frame in frames:
        path = (source / frame['image']).resolve()
        if not path.is_relative_to(source) or sha256(path) != frame['source_sha256']:
            raise ValueError('Source identity changed')
    frozen = recipe(args.config, args.grounding_config)
    if selection.get('recipe_sha256') and selection['recipe_sha256'] != digest_json(frozen):
        raise ValueError('Recipe changed after fresh sample selection')
    contract = dict(recipe=frozen, selection_sha256=sha256(args.selection), source=str(source),
                    purpose=selection['purpose'], images=selection['images'])
    contract_hash = digest_json(contract)
    out = args.output.resolve()
    if out == source or source in out.parents or out in source.parents:
        raise ValueError('Output must be separate from source')
    out.mkdir(parents=True, exist_ok=True)
    with (out / '.run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest_path = out / 'manifest.json'
        if manifest_path.exists():
            if json.loads(manifest_path.read_text())['contract'] != contract:
                raise ValueError('Resume contract changed; use a new directory')
            if sha256(out / 'selection.json') != contract['selection_sha256']:
                raise ValueError('Archived selection changed')
        else:
            if any(p.name != '.run.lock' for p in out.iterdir()):
                raise ValueError('Refusing nonempty output')
            for folder in ('baseline', 'repaired', 'records', 'provenance'):
                (out / folder).mkdir()
            write_json(manifest_path, dict(schema='sidewalkpilot-automatic-repair-run-v1', created_utc=utc_now(),
                       contract=contract, contract_sha256=contract_hash,
                       annotation_scope='Unreviewed class 1 proposals; 255 is unassigned, not verified background'))
            (out / 'selection.json').write_bytes(args.selection.read_bytes())
            for name in DEPENDENCIES:
                (out / 'provenance' / name).write_bytes((_workspace.source_path(name)).read_bytes())
            write_json(out / 'provenance' / 'recipe.json', frozen)
        records, model, load_seconds = [], None, 0
        for number, frame in enumerate(frames, 1):
            name = frame['image']
            record_path = out / 'records' / (Path(name).stem + '.json')
            if record_path.exists():
                record = json.loads(record_path.read_text())
                validate_run_record(out, record, frame, contract_hash)
                records.append(record)
                print(f'[{number}/{len(frames)}] verified cached {name}', flush=True)
                continue
            if model is None:
                started = time.perf_counter()
                model = GroundedSam2(frozen['grounding'], json.loads((_workspace.source_path('taxonomy.json')).read_text()))
                model.torch.cuda.synchronize()
                load_seconds = time.perf_counter() - started
            with Image.open(source / name) as raw:
                image = raw.convert('RGB')
            if list(image.size) != frame['size']:
                raise ValueError('Source size differs')
            started = time.perf_counter()
            base, grounding = model.label(image)
            model.torch.cuda.synchronize()
            baseline_seconds = time.perf_counter() - started
            started = time.perf_counter()
            result, detail = repair(image, base == 1, frozen['repair'], model)
            model.torch.cuda.synchronize()
            repair_seconds = time.perf_counter() - started
            if sha256(source / name) != frame['source_sha256']:
                raise ValueError('Source changed during processing')
            paths = {}
            for method, pixels in (('baseline', base == 1), ('repaired', result)):
                relative = f'{method}/{Path(name).stem}.png'
                save_mask(out / relative, np.where(pixels, 1, 255).astype(np.uint8))
                paths[method] = dict(path=relative, sha256=sha256(out / relative), positive_pixels=int(pixels.sum()))
            record = dict(image=name, source_sha256=frame['source_sha256'], size=frame['size'],
                          contract_sha256=contract_hash, created_utc=utc_now(), **paths,
                          grounding=grounding, repair=detail, baseline_seconds=baseline_seconds,
                          repair_seconds=repair_seconds, review_status='unreviewed')
            write_json(record_path, record)
            records.append(record)
            print(f'[{number}/{len(frames)}] {baseline_seconds + repair_seconds:.2f}s {detail["action"]} changed={detail["changed_pixels"]} {name}', flush=True)
        write_json(out / 'summary.json', dict(count=len(records), reviewed=0,
                   recipe_sha256=digest_json(frozen), model_load_seconds_this_invocation=load_seconds,
                   baseline_seconds=sum(r['baseline_seconds'] for r in records),
                   repair_seconds=sum(r['repair_seconds'] for r in records),
                   actions=dict(Counter(r['repair']['action'] for r in records)),
                   flags=dict(Counter(f for r in records for f in r['repair']['flags'])),
                   human_review_seconds=None, human_correction_seconds=None,
                   note='Automatic proposals only. CUDA timing includes synchronized inference and CPU repair logic; excludes model loading, disk writes, and human/AI development or review. No accuracy claim.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=_workspace.source_path('automatic_repair_config.json'))
    parser.add_argument('--grounding-config', type=Path, default=_workspace.source_path('label_config_sidewalk_first.json'))
    run(parser.parse_args())


if __name__ == '__main__':
    main()
