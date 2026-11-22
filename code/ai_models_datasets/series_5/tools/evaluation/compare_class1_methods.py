#!/usr/bin/env python3
"""Compare frozen class-1 development proposals against exported pixel references."""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw

from audit_sam_implementations import INDICES
from evaluate_class1_corrections import (
    automatic_masks, load_references, metrics, overlay, ratios, read_mask, safe_file,
)
from label_grounded_sam2 import sha256, utc_now, verify_record, write_json

HERE = _workspace.TOOLS


def aggregate(rows):
    variants = set(rows[0]["metrics"])
    if any(set(row["metrics"]) != variants for row in rows):
        raise ValueError("Every image must contain every method, including failures")
    result = {}
    for variant in sorted(variants):
        scores = [row["metrics"][variant] for row in rows]
        counts = {key: sum(s[key] for s in scores) for key in ("tp", "fp", "fn", "tn", "ignored")}
        defined = [s["iou"] for s in scores if s["iou"] is not None]
        result[variant] = {"images": len(scores), "defined_iou_images": len(defined),
                           "macro_iou": float(np.mean(defined)) if defined else None,
                           "micro": {**counts, **ratios(counts)}}
    return result


def checked_asset(root, entry, shape, hashes):
    path = safe_file(root, entry["path"])
    if sha256(path) != entry["sha256"]:
        raise ValueError(f"Prediction hash differs: {path}")
    hashes[str(path)] = entry["sha256"]
    return read_mask(path, shape, (1, 255)) == 1


def check_identity(record, frame):
    if (record["image"] != frame["image"] or record["source_sha256"] != frame["record"]["source_sha256"]
            or record["size"] != frame["record"]["size"]):
        raise ValueError("Predictions must use the same source image and dimensions")


def save_panel(path, image, reference, predictions, heading):
    views = [("SOURCE", image), ("USER REFERENCE: chat-complete, export remains draft", overlay(image, reference))]
    last = "sam31_instance_union" if "sam31_instance_union" in predictions else "sam3_semantic_secondary"
    sam3_key = "sam3_native_control" if "sam3_native_control" in predictions else "sam3_instance_union"
    for key in ("gsam2_original_composed", "gsam2_sidewalk_first", sam3_key, last):
        score = metrics(predictions[key], reference)["iou"]
        label = f"{key}: IoU {score:.3f}" if score is not None else f"{key}: IoU undefined"
        views.append((label, overlay(image, predictions[key].astype(np.uint8))))
    canvas = Image.new("RGB", (1280, 1180), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 5), heading, fill="black")
    for index, (label, view) in enumerate(views):
        x, y = index % 2 * 640, 28 + index // 2 * 384
        draw.text((x + 8, y + 4), label, fill="black")
        canvas.paste(view.resize((640, 360)), (x, y + 24))
    canvas.save(path, quality=94)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("audit", "taxonomy", "corrections", "gsam2", "sam3", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sam31", type=Path, help="Optional frozen SAM 3.1 per-frame detector result")
    parser.add_argument("--sam3-native-control", type=Path, help="Optional same-runtime native SAM 3 control")
    parser.add_argument("--include-drafts", action="store_true")
    parser.add_argument("--completion-note", default="")
    args = parser.parse_args()
    selection_path = args.audit / "comparison" / "selection.json"
    selection = json.loads(selection_path.read_text())
    if tuple(f["prior_index"] for f in selection["frames"]) != INDICES or selection["images"] != [f["image"] for f in selection["frames"]]:
        raise ValueError("Unexpected fixed audit selection")
    baseline, source = Path(selection["baseline"]), Path(selection["source"])
    if sha256(baseline / "manifest.json") != selection["baseline_manifest_sha256"]:
        raise ValueError("Assisted baseline manifest changed")
    paths = [selection_path, args.corrections, args.taxonomy, baseline / "manifest.json",
             args.audit / "automatic-stages" / "config.json", args.gsam2 / "manifest.json",
             args.sam3 / "config.json", _workspace.source_path('label_grounded_sam2.py'), _workspace.source_path('evaluate_class1_corrections.py')]
    hashes = {str(path): sha256(path) for path in paths}
    old_config = json.loads(paths[4].read_text())
    sam2_manifest = json.loads(paths[5].read_text())
    sam3_config = json.loads(paths[6].read_text())
    selection_hash = sha256(selection_path)
    sam31_config = None
    if args.sam31:
        config_path = args.sam31 / "config.json"
        sam31_config = json.loads(config_path.read_text())
        hashes[str(config_path)] = sha256(config_path)
        load = sam31_config["load_report"]
        if (sam31_config["model"] != "facebook/sam3.1" or sam31_config["selection_sha256"] != selection_hash
                or load["strict"] is not True or load["missing_detector_keys"] or load["unexpected_detector_keys"]):
            raise ValueError("Expected a strictly loaded SAM 3.1 detector on the same selection")
    control_config = None
    if args.sam3_native_control:
        path = args.sam3_native_control / "config.json"
        control_config = json.loads(path.read_text())
        hashes[str(path)] = sha256(path)
        load = control_config["load_report"]
        if (control_config["model"] != "facebook/sam3" or control_config.get("native_sam3_control") is not True
                or control_config["selection_sha256"] != selection_hash or load["strict"] is not True
                or load["missing_detector_keys"] or load["unexpected_detector_keys"]):
            raise ValueError("Expected strictly loaded native SAM 3 control on the same selection")
    if (old_config["selection_sha256"] != selection_hash or old_config["taxonomy_sha256"] != sha256(args.taxonomy)
            or old_config["labeler_sha256"] != sha256(_workspace.source_path('label_grounded_sam2.py'))
            or sam2_manifest["contract"]["selection_sha256"] != selection_hash
            or sam2_manifest["images"] != selection["images"] or sam3_config["selection_sha256"] != selection_hash):
        raise ValueError("Input recipes or selections do not match their provenance")
    export, references = load_references(args.corrections, selection, args.include_drafts)
    out = args.output.resolve()
    if out.exists():
        raise ValueError("Use a new output directory; existing comparisons are immutable")
    extras = [p for p in (args.sam31, args.sam3_native_control) if p is not None]
    for protected in (source, baseline, args.audit, args.corrections, args.gsam2, args.sam3, *extras):
        protected = protected.resolve()
        if out == protected or out in protected.parents or protected in out.parents:
            raise ValueError("Keep output separate from all input assets")
    out.mkdir(parents=True)
    for folder in ("panels", "references", "records", "masks"):
        (out / folder).mkdir()
    shutil.copy2(args.corrections, out / "original-corrections.json")
    shutil.copy2(Path(__file__), out / Path(__file__).name)
    write_json(out / "sam2-recipe.json", sam2_manifest["contract"])
    write_json(out / "sam3-recipe.json", sam3_config)
    if sam31_config is not None:
        write_json(out / "sam31-recipe.json", sam31_config)
    if control_config is not None:
        write_json(out / "sam3-native-recipe.json", control_config)
    report = {"created_utc": utc_now(), "runner_sha256": sha256(Path(__file__)),
              "scope": "Ten purposive development frames only, not held-out evaluation. No full-dataset labeling or training.",
              "reference_note": "References were edited from assisted-v16 predictions and may be biased toward them. Original export statuses remain unchanged.",
              "export_status_counts": dict(Counter(r[1]["status"] for r in references)),
              "provisional": any(r[1]["status"] != "reviewed" for r in references),
              "completion_note": args.completion_note,
              "metric_policy": "Only class 1 predicts sidewalk; prediction 255 is not positive and does not exclude errors. Only reference 255 is excluded. Empty failures remain in the mean.",
              "sam3_policy": "Instance union is primary. Ungated semantic head is secondary, not selected per image or substituted after seeing references.",
              "comparison_limit": "Compares pipelines, not isolated model architectures. Assistance, model thresholds, and workflows differ. No timing ranking across these runs.",
              "sam31_scope": "Per-frame detector only, not video tracking. Native model with shared HF image pre/postprocessing; implementation differences remain possible." if args.sam31 else None,
              "images": []}
    taxonomy = json.loads(args.taxonomy.read_text())
    for number, (frame, annotation, ref) in enumerate(references, 1):
        old, _, _, old_hashes = automatic_masks(args.audit, number, frame, ref.shape, old_config["automatic_recipe"], taxonomy)
        hashes.update({str(args.audit / k): value for k, value in old_hashes.items()})
        predictions = {"gsam2_original_raw_union": old["automatic_raw_union"],
                       "gsam2_original_composed": old["automatic_composed"]}
        base_path = safe_file(baseline, frame["record"]["mask"])
        predictions["sam2_assisted_baseline"] = read_mask(base_path, ref.shape, (1, 255)) == 1
        hashes[str(base_path)] = sha256(base_path)
        sam2_path = args.gsam2 / "records" / (Path(frame["image"]).stem + ".json")
        sam3_path = args.sam3 / "records" / f"{number:02d}.json"
        row2, row3 = (json.loads(p.read_text()) for p in (sam2_path, sam3_path))
        for record in (row2, row3):
            check_identity(record, frame)
        verify_record(args.gsam2, row2, source)
        predictions["gsam2_sidewalk_first"] = checked_asset(args.gsam2, {"path": row2["mask"], "sha256": row2["mask_sha256"]}, ref.shape, hashes)
        predictions["sam3_instance_union"] = checked_asset(args.sam3, row3["instance_union"], ref.shape, hashes)
        predictions["sam3_semantic_secondary"] = checked_asset(args.sam3, row3["semantic"], ref.shape, hashes)
        if args.sam31:
            sam31_path = args.sam31 / "records" / f"{number:02d}.json"
            row31 = json.loads(sam31_path.read_text())
            check_identity(row31, frame)
            predictions["sam31_instance_union"] = checked_asset(args.sam31, row31["instance_union"], ref.shape, hashes)
            hashes[str(sam31_path)] = sha256(sam31_path)
        if args.sam3_native_control:
            path = args.sam3_native_control / "records" / f"{number:02d}.json"
            control = json.loads(path.read_text())
            check_identity(control, frame)
            predictions["sam3_native_control"] = checked_asset(args.sam3_native_control, control["instance_union"], ref.shape, hashes)
            hashes[str(path)] = sha256(path)
        hashes.update({str(p): sha256(p) for p in (sam2_path, sam3_path)})
        hashes[str(source / frame["image"])] = frame["record"]["source_sha256"]
        reference_path = out / "references" / f"{number:02d}.png"
        Image.fromarray(ref).save(reference_path)
        saved = {}
        for method, mask in predictions.items():
            relative = f"masks/{number:02d}-{method}.png"
            Image.fromarray(np.where(mask, 1, 255).astype(np.uint8)).save(out / relative)
            saved[method] = {"path": relative, "sha256": sha256(out / relative), "review_status": "unreviewed"}
        row = {"image": frame["image"], "prior_index": frame["prior_index"], "source_sha256": frame["record"]["source_sha256"],
               "annotation_status": annotation["status"], "reference_sha256": sha256(reference_path),
               "metrics": {method: metrics(mask, ref) for method, mask in predictions.items()},
               "predictions": saved, "gsam2_qa_flags": row2["qa_flags"], "sam3_instance_count": len(row3["instances"])}
        report["images"].append(row)
        write_json(out / "records" / f"{number:02d}.json", row)
        with Image.open(source / frame["image"]) as image:
            save_panel(out / "panels" / f"{number:02d}.jpg", image.convert("RGB"), ref, predictions,
                       f'{number:02d} / prior {frame["prior_index"]}: {frame["image"]}')
    report["aggregate"] = aggregate(report["images"])
    for path, expected in hashes.items():
        if sha256(Path(path)) != expected:
            raise ValueError("Input changed during comparison")
    report["input_sha256"] = hashes
    write_json(out / "report.json", report)
    with (out / "per-image.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "method", "tp", "fp", "fn", "tn", "ignored", "iou", "precision", "recall", "f1"])
        writer.writeheader()
        for row in report["images"]:
            for method, scores in row["metrics"].items():
                writer.writerow({"image": row["image"], "method": method, **scores})
    print(json.dumps({"output": str(out), "aggregate": report["aggregate"]}, indent=2))


if __name__ == "__main__":
    main()
