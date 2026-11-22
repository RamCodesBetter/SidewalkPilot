#!/usr/bin/env python3
"""Capture detector, SAM, and class-composition stages on the fixed audit frames."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from audit_sam_implementations import make_panel
from label_grounded_sam2 import GroundedSam2, compose_mask, sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--taxonomy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text())
    if len(selection['images']) != 10 or args.output.exists():
        parser.error('Use exactly the fixed ten images and a new output directory')
    cfg = json.loads(args.config.read_text())
    taxonomy = json.loads(args.taxonomy.read_text())
    source = Path(selection['source'])
    out = args.output.resolve()
    if source == out or source in out.parents or out in source.parents:
        raise ValueError('Keep audit output outside the dataset')
    out.mkdir()
    for folder in ('records', 'masks', 'panels', 'raw'):
        (out / folder).mkdir()
    write_json(out / 'config.json', {'automatic_recipe': cfg, 'selection_sha256': sha256(args.selection),
               'taxonomy_sha256': sha256(args.taxonomy), 'runner_sha256': sha256(Path(__file__)),
               'labeler_sha256': sha256(Path(__file__).with_name('label_grounded_sam2.py')),
               'note': 'Stage tracing of the existing v5 automatic recipe on the audit images. Not a new full-pipeline accuracy comparison.'})
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    labeler = GroundedSam2(cfg, taxonomy)
    sam_batches, detector_groups = [], []
    current_image = None

    def capture_sam(module, inputs, output):
        masks = labeler.sam_processor.post_process_masks(output.pred_masks.cpu(), [[current_image.height, current_image.width]])[0]
        sam_batches.append((masks.numpy().reshape(-1, current_image.height, current_image.width).astype(bool),
                            output.iou_scores.cpu().numpy().ravel(), output.pred_masks.cpu().numpy()))

    def capture_detector(module, inputs, kwargs, output):
        result = labeler.detector_processor.post_process_grounded_object_detection(
            output, kwargs['input_ids'], threshold=cfg['box_threshold'], text_threshold=cfg['text_threshold'],
            target_sizes=[(current_image.height, current_image.width)])[0]
        detector_groups.append({'caption': labeler.detector_processor.tokenizer.decode(kwargs['input_ids'][0], skip_special_tokens=True),
                                'boxes': result['boxes'].cpu().tolist(), 'scores': result['scores'].cpu().tolist(),
                                'text_labels': result['text_labels'],
                                'raw_logits': output.logits.cpu().numpy(), 'raw_boxes': output.pred_boxes.cpu().numpy()})

    sam_hook = labeler.sam.register_forward_hook(capture_sam)
    detector_hook = labeler.detector.register_forward_hook(capture_detector, with_kwargs=True)
    summaries = []
    try:
        for number, frame in enumerate(selection['frames'], 1):
            name = frame['image']
            if sha256(source / name) != frame['record']['source_sha256']:
                raise ValueError('Source image changed')
            with Image.open(source / name) as handle:
                current_image = handle.convert('RGB')
            sam_batches.clear()
            detector_groups.clear()
            composed, meta = labeler.label(current_image)
            raw_masks = np.concatenate([b[0] for b in sam_batches]) if sam_batches else np.empty((0, current_image.height, current_image.width), dtype=bool)
            quality = np.concatenate([b[1] for b in sam_batches]) if sam_batches else np.array([])
            assert len(raw_masks) == len(meta['detections'])
            candidates = []
            raw_sidewalk = np.zeros(composed.shape, dtype=bool)
            accepted_sidewalk = raw_sidewalk.copy()
            for i, (detection, mask, q) in enumerate(zip(meta['detections'], raw_masks, quality)):
                assert abs(float(q) - detection['sam_quality']) < 1e-6
                path = f'masks/{number:02d}-candidate-{i:03d}.png'
                Image.fromarray(np.where(mask, detection['class_id'], 255).astype(np.uint8)).save(out / path)
                detection['raw_sam_mask'] = path
                detection['raw_sam_mask_sha256'] = sha256(out / path)
                if detection['class_id'] == 1:
                    raw_sidewalk |= mask
                    if detection['accepted']:
                        accepted_sidewalk |= mask
                if detection['accepted']:
                    candidates.append((detection['class_id'], mask, detection['detector_score'] * min(float(q),1.0)))
            reproduced = compose_mask(candidates, composed.shape, taxonomy, cfg['class_conflict_margin'], cfg['overlap_mode'])
            assert np.array_equal(reproduced, composed), 'Captured raw candidates must exactly reproduce the composed output'
            lost = accepted_sidewalk & (composed != 1)
            groups = []
            for group_index, group in enumerate(detector_groups):
                group = dict(group)
                path = f'raw/{number:02d}-grounding-{group_index}.npz'
                np.savez_compressed(out / path, logits=group.pop('raw_logits'), boxes=group.pop('raw_boxes'))
                group['raw_output'] = path
                group['raw_output_sha256'] = sha256(out / path)
                groups.append(group)
            boxes = current_image.copy()
            draw = ImageDraw.Draw(boxes)
            # Limit only the picture; the JSON retains every detection and candidate.
            for cid in (1, 2, 3):
                for detection in [d for d in meta['detections'] if d['class_id'] == cid][:3]:
                    box = detection['box']
                    color = {1: '#00a26f', 2: '#d03746', 3: '#3f69d2'}[cid]
                    draw.rectangle(box, outline=color, width=3)
                    draw.text((box[0]+4,box[1]+4), f'{cid}: {detection["phrase"]} {detection["detector_score"]:.2f}', fill=color, stroke_width=1, stroke_fill='white')
            boxes.save(out / 'panels' / f'{number:02d}-boxes.jpg', quality=93)
            for kind, mask in (('raw-sidewalk-union', raw_sidewalk), ('accepted-sidewalk-union', accepted_sidewalk), ('lost-in-composition', lost)):
                Image.fromarray(np.where(mask, 1, 255).astype(np.uint8)).save(out / 'masks' / f'{number:02d}-{kind}.png')
            Image.fromarray(composed).save(out / 'masks' / f'{number:02d}-composed.png')
            make_panel(out / 'panels' / f'{number:02d}.jpg', current_image,
                       [('SOURCE',None),('RAW CLASS-1 SAM UNION',raw_sidewalk),('AFTER QUALITY GATE',accepted_sidewalk),
                        ('AFTER ALL-CLASS COMPOSITION',composed==1),('CLASS-1 PIXELS REMOVED BY COMPOSITION',lost)],
                       f'{number:02d} / v16 index {frame["prior_index"]}: automatic v5 stage audit (not ground truth)')
            row = {'image': name, 'prior_index': frame['prior_index'], 'source_sha256': frame['record']['source_sha256'],
                   'detections': meta, 'standard_detector_postprocessing': groups,
                   'sidewalk_boxes': sum(d['class_id']==1 for d in meta['detections']),
                   'accepted_sidewalk_boxes': sum(d['class_id']==1 and d['accepted'] for d in meta['detections']),
                   'raw_sidewalk_pixels': int(raw_sidewalk.sum()), 'accepted_sidewalk_pixels': int(accepted_sidewalk.sum()),
                   'final_sidewalk_pixels': int((composed==1).sum()), 'pixels_lost_in_composition': int(lost.sum()),
                   'lost_pixels_destination': {str(int(v)): int(n) for v,n in zip(*np.unique(composed[lost], return_counts=True))},
                   'composition_reproduced': True}
            write_json(out / 'records' / f'{number:02d}.json', row)
            summaries.append({k:v for k,v in row.items() if k not in ('detections','standard_detector_postprocessing')})
            print(json.dumps(summaries[-1]), flush=True)
    finally:
        sam_hook.remove()
        detector_hook.remove()
    write_json(out / 'summary.json', {'images': summaries,
               'note': 'Removed pixels can reflect legitimate occlusion or incorrect competing labels. Counts alone cannot distinguish these. Model scores and coverage are not accuracy.'})


if __name__ == '__main__':
    main()
