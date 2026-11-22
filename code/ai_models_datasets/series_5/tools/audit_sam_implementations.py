#!/usr/bin/env python3
"""Fixed ten-frame implementation comparison; never overwrites reviewed labels."""

import argparse
import ast
from collections import Counter
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

from diagnose_reviews import focus_overlay, review_rows
from label_assisted_pilot import refinement_seed
from label_grounded_sam2 import sha256, verify_record, write_json, utc_now
from sam_point_diagnostic import MODEL, REVISION, choose_mask, validate_points

# Fixed before inference: eight rejected cases and two accepted controls, all five runs.
INDICES = (1, 3, 4, 7, 10, 11, 14, 16, 18, 19)
REASONS = (
    'foreground fragmentation', 'right pavement boundary', 'accepted control',
    'road ahead / spill', 'shadow and foreground gap', 'human shadow / driveway',
    'left foreground fragmentation', 'accepted control', 'bright sidewalk / glare',
    'dappled shadows / pavement boundary',
)


def agreement(a, b):
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    if a.shape != b.shape or a.ndim != 2:
        raise ValueError('Expected equally sized two-dimensional masks')
    union = int(np.count_nonzero(a | b))
    return {'iou': float(np.count_nonzero(a & b) / union) if union else None,
            'different_pixels': int(np.count_nonzero(a != b)), 'total_pixels': int(a.size)}


def selected_pixels(masks, scores, points, labels):
    selected, consistent = choose_mask(masks, scores, points, labels)
    raw_best = int(np.argmax(scores))
    gated = masks[selected] if selected is not None else np.zeros_like(masks[0], dtype=bool)
    return gated, {'selected': selected, 'point_consistent': consistent,
                   'raw_best': raw_best, 'scores': [float(v) for v in scores]}


def check_weights(original, converted, converter_path):
    import torch

    # Execute only the upstream pure key-mapping definition, not its converter CLI.
    tree = ast.parse(converter_path.read_text())
    nodes = [n for n in tree.body if
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'KEYS_TO_MODIFY_MAPPING' for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name == 'replace_keys')]
    if len(nodes) != 2:
        raise ValueError('Unexpected upstream conversion helper structure')
    namespace = {'re': re, 'torch': torch}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(converter_path), 'exec'), namespace)
    mapped = namespace['replace_keys'](original, None)
    missing = [key for key in converted if key not in mapped]
    unequal = [key for key, value in converted.items() if key in mapped and not torch.equal(value.cpu(), mapped[key].cpu())]
    report = {'image_model_tensors': len(converted), 'missing': missing, 'unequal': unequal,
              'upstream_conversion_sha256': sha256(converter_path),
              'unused_original_video_keys': sorted(set(mapped) - set(converted))}
    if missing or unequal:
        raise ValueError('Checkpoints do not match: ' + json.dumps(report))
    return report


def save_variant(out, prefix, masks, scores, points, labels, logits):
    gated, detail = selected_pixels(masks, scores, points, labels)
    mask_paths = []
    for i, mask in enumerate(masks):
        relative = f'masks/{prefix}-{i}.png'
        Image.fromarray(np.where(mask, 1, 255).astype(np.uint8)).save(out / relative)
        mask_paths.append({'path': relative, 'sha256': sha256(out / relative)})
    detail['masks'] = mask_paths
    detail['low_res_logits'] = f'logits/{prefix}.npz'
    np.savez_compressed(out / detail['low_res_logits'], logits=logits)
    detail['low_res_logits_sha256'] = sha256(out / detail['low_res_logits'])
    detail['class_1_pixels'] = int(gated.sum())
    return gated, detail


def make_panel(path, image, views, heading):
    columns = 3
    width, height = 640, 390
    sheet = Image.new('RGB', (columns * width, ((len(views) + 2) // 3) * height + 28), 'white')
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 6), heading, fill='black')
    for i, (label, mask) in enumerate(views):
        x, y = (i % columns) * width, (i // columns) * height + 28
        draw.text((x + 8, y + 4), label, fill='black')
        view = image if mask is None else focus_overlay(image, np.where(mask, 1, 255))
        sheet.paste(view.resize((640, 360)), (x, y + 26))
    sheet.save(path, quality=93)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory')
    manifest, reviews = review_rows(args.pilot, args.review)
    if len(manifest['images']) != 20:
        parser.error('Expected the reviewed 20-image correction diagnostic')
    source = Path(manifest['contract']['source'])
    frames = []
    for index, reason in zip(INDICES, REASONS):
        name = manifest['images'][index-1]
        record = json.loads((args.pilot / 'records' / (Path(name).stem + '.json')).read_text())
        verify_record(args.pilot, record, source)
        if record['prompt'] is None:
            raise ValueError('Matched point comparison requires existing explicit prompts')
        frames.append({'prior_index': index, 'image': name, 'reason': reason,
                       'review': reviews[index-1]['decision'], 'record': record})
    if Counter(f['review'] for f in frames) != {'needs_correction': 8, 'correct': 2}:
        raise ValueError('Unexpected review selection')
    out = args.output.resolve()
    if source == out or source in out.parents or out in source.parents:
        raise ValueError('Output must be outside the source tree')
    out.mkdir()
    for directory in ('masks', 'logits', 'panels', 'records'):
        (out / directory).mkdir()
    selection = {'created_utc': utc_now(), 'baseline': str(args.pilot),
                 'baseline_manifest_sha256': sha256(args.pilot / 'manifest.json'),
                 'review_sha256': sha256(args.review), 'source': str(source),
                 'images': [f['image'] for f in frames], 'frames': frames,
                 'scope': 'Purposive implementation audit, not an accuracy estimate. No new annotations or weight updates.',
                 'excluded': 'The two abstained frames have no point prompts and cannot enter a matched-prompt comparison.'}
    write_json(out / 'selection.json', selection)
    sys.path[:0] = [str(args.dependencies / 'python'), str(args.dependencies / 'sam2')]
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from transformers import Sam2Model, Sam2Processor

    torch.set_num_threads(4)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    checkpoint = args.dependencies / 'sam2.1_hiera_large.pt'
    processor = Sam2Processor.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
    hf = Sam2Model.from_pretrained(MODEL, revision=REVISION, local_files_only=True).eval()
    original_weights = torch.load(checkpoint, map_location='cpu', weights_only=True)['model']
    weight_report = check_weights(original_weights, hf.state_dict(), args.dependencies / 'convert_sam2_video_to_hf.py')
    write_json(out / 'weight-check.json', weight_report)
    del original_weights
    hf = hf.to('cuda')
    native = build_sam2('configs/sam2.1/sam2.1_hiera_l.yaml', str(checkpoint), device='cuda', apply_postprocessing=True)
    predictor = SAM2ImagePredictor(native, max_hole_area=0, max_sprinkle_area=0)
    config = {'model': MODEL, 'revision': REVISION, 'official_checkpoint_sha256': sha256(checkpoint),
              'official_git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.dependencies/'sam2', text=True).strip(),
              'runner_sha256': sha256(Path(__file__)), 'dtype': 'float32', 'autocast': False,
              'torch_cuda_matmul_allow_tf32': torch.backends.cuda.matmul.allow_tf32,
              'torch_cudnn_allow_tf32': torch.backends.cudnn.allow_tf32,
              'official_single_mask_dynamic_fallback': native.sam_mask_decoder.dynamic_multimask_via_stability,
              'hf_single_mask_dynamic_fallback': hf.mask_decoder.dynamic_multimask_via_stability,
              'threshold': 0.0, 'hole_filling': False, 'minimum_quality': .7,
              'packages': {p: importlib.metadata.version(p) for p in ('torch','torchvision','transformers','numpy','Pillow')},
              'helper_sha256': {p: sha256(Path(__file__).parent / p) for p in ('label_grounded_sam2.py','label_assisted_pilot.py','sam_point_diagnostic.py')}}
    write_json(out / 'config.json', config)
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    results = []
    with torch.inference_mode():
        for number, frame in enumerate(frames, 1):
            name, record = frame['image'], frame['record']
            with Image.open(source / name) as handle:
                image = handle.convert('RGB')
            with Image.open(args.pilot / record['mask']) as handle:
                reviewed = np.asarray(handle) == 1
            points, labels = validate_points(record['prompt'], image.width, image.height)
            inputs = processor(images=image, input_points=[[points]], input_labels=[[labels]], return_tensors='pt').to('cuda')
            native_pixels = predictor._transforms(np.asarray(image)).unsqueeze(0).to('cuda')
            transformed_points = predictor._transforms.transform_coords(torch.tensor(points, device='cuda', dtype=torch.float32), True, (image.height, image.width))
            tensor_diff = (inputs.pixel_values - native_pixels).abs()
            preprocessing = {'image_max_abs_difference': float(tensor_diff.max()), 'image_mean_abs_difference': float(tensor_diff.mean()),
                             'point_max_abs_difference': float((inputs.input_points[0,0] - transformed_points).abs().max())}
            predictor.set_image(np.asarray(image))
            variants, arrays, all_masks = {}, {}, {}
            # One-variable comparisons: engine; resize order; then mask-output mode.
            for multi in (True, False):
                suffix = 'multi' if multi else 'single'
                for engine in ('hf_native', 'official_native', 'hf_official_pixels'):
                    key = engine + '_' + suffix
                    if engine == 'official_native':
                        masks, scores, logits = predictor.predict(point_coords=np.asarray(points, dtype=np.float32), point_labels=np.asarray(labels), multimask_output=multi)
                    else:
                        values = dict(inputs)
                        if engine == 'hf_official_pixels':
                            values['pixel_values'] = native_pixels
                        result = hf(**values, multimask_output=multi)
                        masks = processor.post_process_masks(result.pred_masks.cpu(), inputs.original_sizes.cpu())[0].numpy().reshape(-1, image.height, image.width).astype(bool)
                        scores = result.iou_scores.cpu().numpy().ravel()
                        logits = result.pred_masks[0,0].cpu().numpy()
                    arrays[key], variants[key] = save_variant(out, f'{number:02d}-{key}', masks, scores, points, labels, logits)
                    all_masks[key] = masks
            # Reproduce the delivered bounded feedback policy separately from raw parity.
            result = hf(**inputs, multimask_output=True)
            trace = []
            for step in range(4):
                masks = processor.post_process_masks(result.pred_masks.cpu(), inputs.original_sizes.cpu())[0].numpy().reshape(-1, image.height, image.width).astype(bool)
                scores = result.iou_scores.cpu().numpy().ravel()
                selected, _ = choose_mask(masks, scores, points, labels)
                seed, violations = refinement_seed(masks, scores, points, labels)
                trace.append({'step': step, 'selected': selected, 'point_violations': violations})
                if selected is not None or step == 3 or seed is None:
                    break
                result = hf(**inputs, input_masks=result.pred_masks[:,0,seed:seed+1].detach(), multimask_output=True)
            arrays['hf_delivered_policy'], variants['hf_delivered_policy'] = save_variant(out, f'{number:02d}-hf_delivered_policy', masks, scores, points, labels, result.pred_masks[0,0].cpu().numpy())
            pairwise = {}
            for first, second in (
                ('hf_native_multi','official_native_multi'), ('hf_official_pixels_multi','official_native_multi'),
                ('hf_native_single','official_native_single'), ('hf_official_pixels_single','official_native_single'),
                ('hf_native_multi','hf_native_single'), ('official_native_multi','official_native_single'),
            ):
                pairwise[first + '__' + second] = agreement(arrays[first], arrays[second])
            raw_parity = {}
            for suffix in ('multi','single'):
                for first in ('hf_native','hf_official_pixels'):
                    raw_parity[first+'_'+suffix] = [agreement(a,b) for a,b in zip(all_masks[first+'_'+suffix], all_masks['official_native_'+suffix])]
            result_row = {'image': name, 'prior_index': frame['prior_index'], 'reviewed_status': frame['review'],
                          'source_sha256': record['source_sha256'], 'preprocessing': preprocessing, 'variants': variants,
                          'gated_mask_agreement': pairwise, 'raw_candidate_agreement_with_official': raw_parity,
                          'delivered_reproduction': agreement(arrays['hf_delivered_policy'], reviewed), 'feedback_trace': trace}
            verify_record(args.pilot, record, source)
            write_json(out / 'records' / f'{number:02d}.json', result_row)
            views = [('SOURCE', None), ('REVIEWED v16: '+frame['review'], reviewed),
                     ('HF native / multi, initial', arrays['hf_native_multi']),
                     ('OFFICIAL native / multi', arrays['official_native_multi']),
                     ('HF with official pixels / multi', arrays['hf_official_pixels_multi']),
                     ('OFFICIAL native / single', arrays['official_native_single'])]
            make_panel(out / 'panels' / f'{number:02d}.jpg', image, views, f'{number:02d} / original diagnostic {frame["prior_index"]}: {name}')
            results.append(result_row)
            print(json.dumps({'image': number, 'prior_index': frame['prior_index'], 'preprocessing': preprocessing,
                              'native_multi_agreement': pairwise['hf_native_multi__official_native_multi'],
                              'matched_pixels_multi_agreement': pairwise['hf_official_pixels_multi__official_native_multi'],
                              'reproduction': result_row['delivered_reproduction']}), flush=True)
    write_json(out / 'summary.json', {'images': results, 'count': len(results),
               'note': 'All IoUs are output agreement, NOT ground-truth accuracy. No new human decisions. No automatic winner selected.'})
    print(str(out), flush=True)


if __name__ == '__main__':
    main()
