#!/usr/bin/env python3
"""Combine frozen reviewed labels with screened, explicitly weak SAM 3 labels."""
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
import sys
import tempfile

import numpy as np
from PIL import Image


from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from label_series5_pseudo import load_selection
from prepare_reviewed_dataset import read_json, pixel_hash, pixel_counts, safe_file, verify_dataset
from series_5_a_sidewalkpilot_trainer import validate_split
from pseudo_training_targets import POLICY as TARGET_POLICY, prepare_target


def load_mixed_partition(dataset, split_path):
    dataset = Path(dataset).resolve()
    manifest = read_json(dataset / "manifest.json")
    if manifest.get("schema") != "sidewalkpilot-mixed-pseudo-dataset-v1":
        raise ValueError("Not a screened pseudo-label training dataset")
    checksums = read_json(dataset / "checksums.json")
    if {str(p.relative_to(dataset)) for p in dataset.rglob('*') if p.is_file()} != set(checksums) | {"checksums.json"}:
        raise ValueError("Unexpected dataset files")
    for name, expected in checksums.items():
        if sha256(safe_file(dataset, name)) != expected:
            raise ValueError("Dataset file changed")
    for row in manifest["records"]:
        image_path, mask_path = safe_file(dataset, row["image"]), safe_file(dataset, row["mask"])
        if row["id"] != row["source_sha256"] or sha256(image_path) != row["source_sha256"] or sha256(mask_path) != row["mask_sha256"]:
            raise ValueError("Dataset record identity mismatch")
        with Image.open(image_path) as image:
            if list(image.size) != row["size"]:
                raise ValueError("Image size mismatch")
        with Image.open(mask_path) as image:
            labels = np.array(image)
        if (labels.shape != tuple(reversed(row["size"])) or labels.dtype != np.uint8
                or not np.isin(labels, (0,1,255)).all() or pixel_hash(labels) != row["pixels_sha256"]
                or pixel_counts(labels) != row["pixel_counts"]):
            raise ValueError("Label data changed")
        if row["supervision"] == "sidewalk-positive-only" and (labels==0).any():
            raise ValueError("Invented human background")
        if row["supervision"] == "pseudo-binary" and not (labels==0).any():
            raise ValueError("Pseudo-label lacks negative supervision")
        if row["supervision"] not in ("binary-reference", "sidewalk-positive-only", "pseudo-binary"):
            raise ValueError("Unknown supervision source")
    split = read_json(split_path)
    parts = validate_split(manifest, split, sha256(dataset / "manifest.json"))
    base = read_json(dataset / "provenance/base-split.json")
    for part in ("validation", "test"):
        if split["partitions"][part] != base["partitions"][part] or any(r["supervision"]=="pseudo-binary" for r in parts[part]):
            raise ValueError("Evaluation split changed or contains pseudo-labels")
    if manifest.get('visual_excluded', 0):
        exclusions = read_json(dataset/'provenance/visual-exclusions.json')
        if {r['id'] for r in exclusions['records']} & {r['id'] for r in manifest['records']}:
            raise ValueError('Visually deferred image entered the dataset')
    return parts


def build(args):
    output = args.output.resolve()
    split_output = args.output_split.resolve()
    if output.exists() or args.output_split.exists():
        raise ValueError("Use new dataset and split paths")
    if any(output.is_relative_to(p.resolve()) or p.resolve().is_relative_to(output)
           for p in (args.dataset, args.run, args.selection)):
        raise ValueError("Output overlaps source data")
    if any(split_output.is_relative_to(p.resolve()) or p.resolve().is_relative_to(split_output)
           for p in (args.dataset, args.run, args.selection, args.split, output)):
        raise ValueError("Split output overlaps source data or output dataset")
    verify_dataset(args.dataset)
    base = read_json(args.dataset / "manifest.json")
    base_split = read_json(args.split)
    selection = load_selection(args.selection)
    run = read_json(args.run / "manifest.json")
    if run.get("schema") != "sidewalkpilot-sam3-pseudo-run-v1" or digest_json(run["contract"]) != run["contract_sha256"]:
        raise ValueError("Invalid labeling run contract")
    if (selection["baseline_manifest_sha256"] != sha256(args.dataset / "manifest.json")
            or selection["baseline_split_sha256"] != sha256(args.split)
            or run["contract"]["selection_sha256"] != sha256(args.selection)
            or selection["allowed_days"] != base_split["days"]["train"]
            or selection["purpose"] != "new training-only pseudo-labels"):
        raise ValueError("Pseudo selection is not bound to this training split")
    status = read_json(args.run / "status.json")
    if status["status"] != "complete" or status["processed"] != selection["count"]:
        raise ValueError("Labeling run is not complete")
    accepted = []
    seen = {r["id"] for r in base["records"]}
    for frame in selection["frames"]:
        record = read_json(args.run / "records" / (frame["id"]+".json"))
        if record["frame"] != frame or record["contract_sha256"] != run["contract_sha256"]:
            raise ValueError("Prediction identity differs")
        if record["filter"]["accepted_for_pseudo_training"]:
            if frame["id"] in seen:
                raise ValueError("Duplicate training/evaluation source")
            seen.add(frame["id"])
            accepted.append(record)
    if status["accepted_pseudo"] != len(accepted) or status["deferred"] != selection["count"] - len(accepted):
        raise ValueError("Labeling status counts differ from records")
    automatic_count = len(accepted)
    exclusion_path = getattr(args, 'visual_exclusions', None)
    exclusions = None
    if exclusion_path:
        exclusions = read_json(exclusion_path)
        if (exclusions.get('schema') != 'sidewalkpilot-pseudo-visual-exclusions-v1'
                or exclusions['run_contract_sha256'] != run['contract_sha256']):
            raise ValueError('Visual exclusions belong to a different run')
        ids = [r['id'] for r in exclusions['records']]
        if len(ids) != len(set(ids)) or not set(ids) <= {r['frame']['id'] for r in accepted}:
            raise ValueError('Unknown or duplicate visual exclusions')
        accepted = [r for r in accepted if r['frame']['id'] not in set(ids)]
    if len(accepted) < 100:
        raise ValueError("Fewer than 100 screened pseudo-labels; investigate before training")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pseudo-dataset-', dir=output.parent) as tmp:
        root = Path(tmp) / 'dataset'
        for name in ('images', 'masks', 'provenance'):
            (root / name).mkdir(parents=True)
        rows = []
        for row in base["records"]:
            if row["included"]:
                rows.append(copy.deepcopy(row))
                for key in ('image', 'mask'):
                    shutil.copy2(safe_file(args.dataset, row[key]), root / row[key])
        for record in accepted:
            frame = record['frame']
            image_path = safe_file(Path(selection['source']), frame['image'])
            mask_path=safe_file(args.run,record['mask']['path'])
            if sha256(image_path)!=frame['source_sha256'] or sha256(mask_path)!=record['mask']['sha256']:
                raise ValueError('Pseudo source or mask changed')
            image_name = 'images/' + frame['image']
            mask_name = 'masks/' + Path(frame['image']).stem + '.png'
            shutil.copy2(image_path, root / image_name)
            with Image.open(mask_path) as image:
                labels, target_detail = prepare_target(np.array(image))
            Image.fromarray(labels).save(root / mask_name)
            rows.append(dict(id=frame['id'],source_sha256=frame['source_sha256'],source_name=frame['image'],
                image=image_name,mask=mask_name,mask_sha256=sha256(root/mask_name),size=record['size'],
                pixels_sha256=pixel_hash(labels),pixel_counts=pixel_counts(labels),included=True,
                supervision='pseudo-binary',recording_run=frame['recording_run'],
                provenance=dict(kind='SAM 3 agreement pseudo-label, not human reviewed',
                    run_contract_sha256=run['contract_sha256'],filter=record['filter'],
                    source_pseudo_mask_sha256=record['mask']['sha256'],target_preparation=target_detail)))
        manifest=dict(schema='sidewalkpilot-mixed-pseudo-dataset-v1',created_utc=utc_now(),
            baseline_manifest_sha256=sha256(args.dataset/'manifest.json'),pseudo_run_contract=run['contract'],
            pseudo_training_target_policy=TARGET_POLICY,
            target_preparation_sha256=sha256(_workspace.source_path('pseudo_training_targets.py')),
            automatically_accepted=automatic_count,visual_excluded=automatic_count-len(accepted),
            selected_candidates=selection['count'],accepted_pseudo=len(accepted),deferred=selection['count']-len(accepted),
            policy='Human references unchanged; pseudo-background is an explicitly weak model target, not verified ground truth.',records=rows)
        write_json(root/'manifest.json',manifest)
        shutil.copy2(args.split,root/'provenance/base-split.json')
        shutil.copy2(args.run/'manifest.json',root/'provenance/pseudo-run.json')
        if exclusions is not None:
            write_json(root/'provenance/visual-exclusions.json', exclusions)
        write_json(root/'checksums.json',{str(p.relative_to(root)):sha256(p) for p in sorted(root.rglob('*')) if p.is_file()})
        split = copy.deepcopy(base_split)
        split['created_utc'] = utc_now()
        split['manifest_sha256'] = sha256(root / 'manifest.json')
        split['partitions']['train'] += [r['frame']['id'] for r in accepted]
        split['summary']={part:{'images':len(ids)} for part,ids in split['partitions'].items()}
        split['purpose']='5.B screened pseudo-label training; fixed 5.A development validation/test IDs'
        staged_split = Path(tmp) / 'split.json'
        write_json(staged_split, split)
        load_mixed_partition(root, staged_split)
        args.output_split.parent.mkdir(parents=True,exist_ok=True)
        root.rename(output)
        write_json(args.output_split, split)
    return {'dataset':str(output),'pseudo_labels':len(accepted),'deferred':selection['count']-len(accepted),
            'partitions':split['summary']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('dataset','split','selection','run','output','output-split'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--visual-exclusions', type=Path)
    print(json.dumps(build(parser.parse_args()),indent=2))
