#!/usr/bin/env python3
"""Validate pixel-reference exports and evaluate frozen GSAM 2 diagnostic outputs."""

import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw

from audit_sam_implementations import INDICES
from label_grounded_sam2 import compose_mask, sha256, utc_now, verify_record, write_json


def decode_runs(runs, shape):
    size = int(np.prod(shape))
    if not isinstance(runs, list) or not runs or len(runs) % 2 or len(runs) > size * 2:
        raise ValueError("Invalid reference pixel runs")
    pixels = np.empty(size, dtype=np.uint8)
    offset = 0
    for value, count in zip(runs[::2], runs[1::2]):
        if type(value) is not int or value not in (0, 1, 255) or type(count) is not int or count <= 0 or offset + count > size:
            raise ValueError("Invalid reference pixel run")
        pixels[offset:offset + count] = value
        offset += count
    if offset != size:
        raise ValueError("Incomplete reference pixel runs")
    return pixels.reshape(shape)


def metric_counts(prediction, reference):
    if prediction.dtype != np.bool_ or prediction.shape != reference.shape or reference.ndim != 2:
        raise ValueError("Expected aligned binary prediction and 2D reference")
    if not np.isin(reference, (0, 1, 255)).all():
        raise ValueError("Invalid reference labels")
    positive, negative = reference == 1, reference == 0
    return {"tp": int(np.count_nonzero(prediction & positive)),
            "fp": int(np.count_nonzero(prediction & negative)),
            "fn": int(np.count_nonzero(~prediction & positive)),
            "tn": int(np.count_nonzero(~prediction & negative)),
            "ignored": int(np.count_nonzero(reference == 255))}


def ratios(counts):
    tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
    return {"iou": tp / (tp + fp + fn) if tp + fp + fn else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def metrics(prediction, reference):
    counts = metric_counts(prediction, reference)
    return {**counts, **ratios(counts)}


def candidate_diagnostics(candidates, reference):
    scored = [(detection, metrics(mask, reference)) for detection, mask in candidates]
    scored = [(d, s) for d, s in scored if s["iou"] is not None]
    if not scored:
        return None
    best_score = max(s["iou"] for _, s in scored)
    tied = [(d, s) for d, s in scored if abs(s["iou"] - best_score) <= 1e-12]
    detection, scores = tied[0]
    class1 = [s["iou"] for d, s in scored if d["class_id"] == 1]
    best_class1 = max(class1) if class1 else None
    return {"candidate": detection["raw_sam_mask"], "assigned_class": detection["class_id"],
            "phrase": detection["phrase"], "metrics": scores,
            "equally_best_class_ids": sorted({d["class_id"] for d, _ in tied}),
            "best_class1_iou": best_class1,
            "class1_iou_gap": best_score - best_class1 if best_class1 is not None else None,
            "note": "Representative candidate may tie across class IDs; do not count it as a unique wrong-class assignment."}


def read_mask(path, shape, allowed):
    with Image.open(path) as image:
        result = np.array(image)
    if result.shape != tuple(shape) or not np.isin(result, allowed).all():
        raise ValueError(f"Invalid mask dimensions/IDs: {path}")
    return result


def safe_file(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Expected a relative asset path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Invalid asset path")
    return path


def load_references(path, selection, include_drafts):
    value = json.loads(path.read_text())
    baseline = Path(selection["baseline"])
    manifest = json.loads((baseline / "manifest.json").read_text())
    key = "sp-review:" + manifest["created_utc"] + ":" + manifest["contract"]["source_names_sha256"]
    if value.get("schema") != "sidewalkpilot-class1-corrections-v1" or value.get("dataset_key") != key:
        raise ValueError("Correction export belongs to another dataset/schema")
    if value.get("annotation_scope") != {"kind": "binary_class_reference", "positive_class_id": 1, "not_a_12_class_mask": True}:
        raise ValueError("Expected binary class-1 references")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) != len(selection["images"]):
        raise ValueError("Expected all ten audit references")
    if any(not isinstance(e, dict) or not isinstance(e.get("image"), str) for e in entries):
        raise ValueError("Invalid reference entry")
    by_name = {e["image"]: e for e in entries}
    if len(by_name) != len(entries) or set(by_name) != set(selection["images"]):
        raise ValueError("Reference images must exactly match the fixed audit selection")
    result = []
    for frame in selection["frames"]:
        row, record = by_name[frame["image"]], frame["record"]
        if row.get("source_sha256") != record["source_sha256"] or row.get("base_mask_sha256") != record["mask_sha256"] or row.get("size") != record["size"]:
            raise ValueError("Reference source/proposal hash or dimensions differ")
        if row.get("status") not in ("draft", "reviewed"):
            raise ValueError("Invalid reference status")
        if row["status"] != "reviewed" and not include_drafts:
            raise ValueError("Export contains drafts; explicit --include-drafts required for provisional analysis")
        for key in ("created_utc", "updated_utc"):
            if not isinstance(row.get(key), str):
                raise ValueError("Missing reference timestamp")
            datetime.fromisoformat(row[key].replace("Z", "+00:00"))
        if not isinstance(row.get("notes"), str) or not isinstance(row.get("seed"), str):
            raise ValueError("Missing annotation provenance")
        pixels = decode_runs(row.get("pixels_rle"), tuple(reversed(record["size"])))
        if hashlib.sha256(pixels.tobytes()).hexdigest() != row.get("pixels_sha256"):
            raise ValueError("Corrected pixel hash does not match")
        verify_record(baseline, record, Path(selection["source"]))
        result.append((frame, row, pixels))
    return value, result


def automatic_masks(audit, number, frame, shape, cfg, taxonomy):
    root = audit / "automatic-stages"
    path = root / "records" / f"{number:02d}.json"
    row = json.loads(path.read_text())
    if row["image"] != frame["image"] or row["source_sha256"] != frame["record"]["source_sha256"]:
        raise ValueError("Automatic-stage image mismatch")
    raw, accepted = np.zeros(shape, bool), np.zeros(shape, bool)
    candidates, all_masks, hashes = [], [], {str(path.relative_to(audit)): sha256(path)}
    for detection in row["detections"]["detections"]:
        path = safe_file(root, detection["raw_sam_mask"])
        if sha256(path) != detection["raw_sam_mask_sha256"]:
            raise ValueError("Saved SAM candidate hash changed")
        hashes[str(path.relative_to(audit))] = sha256(path)
        cid = detection["class_id"]
        mask = read_mask(path, shape, (cid, 255)) == cid
        all_masks.append((detection, mask))
        if cid == 1:
            raw |= mask
            if detection["accepted"]:
                accepted |= mask
        if detection["accepted"]:
            candidates.append((cid, mask, detection["detector_score"] * min(detection["sam_quality"], 1.0)))
    composed = compose_mask(candidates, shape, taxonomy, cfg["class_conflict_margin"], cfg["overlap_mode"])
    for kind, expected in (("raw-sidewalk-union", raw), ("accepted-sidewalk-union", accepted), ("composed", composed)):
        path = root / "masks" / f"{number:02d}-{kind}.png"
        actual = read_mask(path, shape, (*range(12), 255))
        if not np.array_equal(actual if kind == "composed" else actual == 1, expected):
            raise ValueError("Saved stage mask differs from reconstructed candidates")
        hashes[str(path.relative_to(audit))] = sha256(path)
    return {"automatic_raw_union": raw, "automatic_accepted_union": accepted, "automatic_composed": composed == 1}, composed, all_masks, hashes


def overlay(image, labels):
    rgb = np.array(image, dtype=np.float32)
    for value, color in ((1, (50, 197, 144)), (255, (237, 182, 73))):
        hit = labels == value
        rgb[hit] = .55 * rgb[hit] + .45 * np.asarray(color)
    return Image.fromarray(rgb.astype(np.uint8))


def panel(path, image, reference, predictions, heading):
    views = [("SOURCE", image), ("USER REFERENCE (export status: draft unless noted)", overlay(image, reference))]
    for key in ("assisted_v16", "automatic_raw_union", "automatic_composed"):
        score = metrics(predictions[key], reference)["iou"]
        label = f"{key}: IoU {score:.3f}" if score is not None else f"{key}: IoU undefined"
        views.append((label, overlay(image, predictions[key].astype(np.uint8))))
    error = np.array(image, dtype=np.float32)
    for hit, color in (((reference == 1) & ~predictions["automatic_composed"], (255, 163, 48)),
                       ((reference == 0) & predictions["automatic_composed"], (234, 62, 147))):
        error[hit] = .35 * error[hit] + .65 * np.asarray(color)
    views.append(("COMPOSED ERRORS: orange=missed, pink=extra", Image.fromarray(error.astype(np.uint8))))
    canvas = Image.new("RGB", (1280, 1180), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 5), heading, fill="black")
    for i, (label, view) in enumerate(views):
        x, y = i % 2 * 640, 28 + i // 2 * 384
        draw.text((x + 8, y + 4), label, fill="black")
        canvas.paste(view.resize((640, 360)), (x, y + 24))
    canvas.save(path, quality=94)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corrections", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True, help="Frozen taxonomy used by the automatic-stage audit")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-drafts", action="store_true")
    parser.add_argument("--completion-note", default="")
    args = parser.parse_args()
    selection_path = args.audit / "comparison" / "selection.json"
    selection = json.loads(selection_path.read_text())
    if tuple(f["prior_index"] for f in selection["frames"]) != INDICES or selection["images"] != [f["image"] for f in selection["frames"]]:
        raise ValueError("Unexpected audit selection")
    baseline, source = Path(selection["baseline"]), Path(selection["source"])
    if sha256(baseline / "manifest.json") != selection["baseline_manifest_sha256"]:
        raise ValueError("Baseline manifest changed")
    config = json.loads((args.audit / "automatic-stages" / "config.json").read_text())
    taxonomy_path = args.taxonomy
    if config["selection_sha256"] != sha256(selection_path) or config["taxonomy_sha256"] != sha256(taxonomy_path):
        raise ValueError("Stage trace inputs do not match")
    if config["labeler_sha256"] != sha256(Path(__file__).with_name("label_grounded_sam2.py")):
        raise ValueError("Composition helper changed since audit")
    export, references = load_references(args.corrections, selection, args.include_drafts)
    out = args.output.resolve()
    if out.exists():
        raise ValueError("Use a new output directory")
    for protected in (source, baseline, args.audit, args.corrections):
        protected = protected.resolve()
        if out == protected or out in protected.parents or protected in out.parents:
            raise ValueError("Keep output separate from input assets")
    out.mkdir(parents=True)
    for folder in ("references", "panels", "records"):
        (out / folder).mkdir()
    shutil.copy2(args.corrections, out / "original-corrections.json")
    shutil.copy2(Path(__file__), out / Path(__file__).name)
    hashes = {str(selection_path): sha256(selection_path), str(args.corrections): sha256(args.corrections),
              str(taxonomy_path): sha256(taxonomy_path), str(baseline / "manifest.json"): sha256(baseline / "manifest.json")}
    report = {"created_utc": utc_now(), "exported_utc": export["exported_utc"],
              "export_status_counts": dict(Counter(r[1]["status"] for r in references)),
              "completion_note": args.completion_note, "original_statuses_modified": False,
              "provisional": any(r[1]["status"] != "reviewed" for r in references),
              "scope": "Ten purposive development frames, not an independent accuracy estimate. References were edited from assisted-v16 proposals, which may bias comparison toward that baseline.",
              "prediction_policy": "Only class 1 predicts sidewalk. Other IDs, including predicted ignore=255, are not positive. Only reference=255 is excluded; missed sidewalk in unassigned predictions remains a false negative.",
              "oracle_note": "Best single candidate selected using the reference is diagnostic only, not an executable automatic policy or a measured improvement.",
              "runner_sha256": sha256(Path(__file__)), "images": []}
    taxonomy = json.loads(taxonomy_path.read_text())
    for number, (frame, row, reference) in enumerate(references, 1):
        shape = reference.shape
        predictions, composed, candidates, candidate_hashes = automatic_masks(args.audit, number, frame, shape, config["automatic_recipe"], taxonomy)
        hashes.update({str(args.audit / k): v for k, v in candidate_hashes.items()})
        base_path = safe_file(baseline, frame["record"]["mask"])
        predictions["assisted_v16"] = read_mask(base_path, shape, (1, 255)) == 1
        hashes[str(base_path)] = sha256(base_path)
        hashes[str(source / frame["image"])] = frame["record"]["source_sha256"]
        best = candidate_diagnostics(candidates, reference)
        lost = predictions["automatic_accepted_union"] & ~predictions["automatic_composed"]
        reference_path = out / "references" / (Path(frame["image"]).stem + ".png")
        Image.fromarray(reference).save(reference_path)
        summary = {"image": frame["image"], "prior_index": frame["prior_index"], "export_status": row["status"],
                   "reference": {"path": str(reference_path.relative_to(out)), "sha256": sha256(reference_path), "pixels_sha256": row["pixels_sha256"],
                                 "positive_pixels": int((reference == 1).sum()), "negative_pixels": int((reference == 0).sum()), "uncertain_pixels": int((reference == 255).sum())},
                   "changed_from_seed_pixels": int(np.count_nonzero(reference != predictions["assisted_v16"].astype(np.uint8))),
                   "added_sidewalk_pixels": int(np.count_nonzero((reference == 1) & ~predictions["assisted_v16"])),
                   "removed_sidewalk_pixels": int(np.count_nonzero((reference == 0) & predictions["assisted_v16"])),
                   "metrics": {k: metrics(v, reference) for k, v in predictions.items()},
                   "composition_lost_true_sidewalk": int(np.count_nonzero(lost & (reference == 1))),
                   "composition_removed_false_sidewalk": int(np.count_nonzero(lost & (reference == 0))),
                   "composed_unassigned_valid_pixels": int(np.count_nonzero((composed == 255) & (reference != 255))),
                   "oracle_best_single_any_class": best}
        write_json(out / "records" / f"{number:02d}.json", {**summary, "annotation": {k:v for k,v in row.items() if k != "pixels_rle"}})
        with Image.open(source / frame["image"]) as image:
            panel(out / "panels" / f"{number:02d}.jpg", image.convert("RGB"), reference, predictions,
                  f'{number:02d} / prior {frame["prior_index"]}: {frame["image"]} / {row["status"]}')
        report["images"].append(summary)
    aggregate = {}
    for variant in report["images"][0]["metrics"]:
        scores = [r["metrics"][variant] for r in report["images"]]
        total = {k: sum(s[k] for s in scores) for k in ("tp", "fp", "fn", "tn", "ignored")}
        aggregate[variant] = {"micro": {**total, **ratios(total)},
                              "macro_iou": float(np.mean([s["iou"] for s in scores if s["iou"] is not None])) if any(s["iou"] is not None for s in scores) else None}
    report["aggregate"] = aggregate
    for path, expected in hashes.items():
        if sha256(Path(path)) != expected:
            raise ValueError("Input changed during evaluation")
    report["input_sha256"] = hashes
    write_json(out / "report.json", report)
    with (out / "per-image.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "prior_index", "export_status", "variant", "tp", "fp", "fn", "tn", "ignored", "iou", "precision", "recall", "f1"])
        writer.writeheader()
        for row in report["images"]:
            for variant, values in row["metrics"].items():
                writer.writerow({"image": row["image"], "prior_index": row["prior_index"], "export_status": row["export_status"], "variant": variant, **values})
    print(json.dumps({"output": str(out), "images": len(references), "statuses": report["export_status_counts"], "provisional": report["provisional"], "aggregate": aggregate}, indent=2))


if __name__ == "__main__":
    main()
