#!/usr/bin/env python3
"""Evaluate a targeted correction export against the frozen paired-review masks."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import shutil

import numpy as np
from PIL import Image, ImageDraw

from compare_class1_methods import aggregate, checked_asset, check_identity
from evaluate_class1_corrections import load_references, metrics, overlay, safe_file
from label_grounded_sam2 import sha256, utc_now, write_json


def validate_selection(selection, manifest):
    key = "sp-review:" + manifest["created_utc"] + ":" + manifest["contract"]["source_names_sha256"]
    frames = selection["frames"]
    if (selection.get("kind") != "sidewalkpilot-targeted-corrections-v1"
            or selection.get("dataset_key") != key
            or [r["image"] for r in frames] != manifest["images"]
            or len(set(manifest["images"])) != len(frames)
            or len({r["pair"] for r in frames}) != len(frames)
            or [r["position"] for r in frames] != list(range(1, len(frames) + 1))
            or Counter(r["role"] for r in frames) != {"failure": selection["failures"], "control": selection["controls"]}
            or not selection["failures"] or not selection["controls"]):
        raise ValueError("Targeted selection identity/order/groups differ")
    return key


def validate_pair(frame, pair, assignment):
    record = frame["record"]
    if (pair["id"] != frame["pair"] or not re.fullmatch(r"pair-\d{3}", pair["id"])
            or pair["source_name"] != frame["image"] or assignment["image"] != frame["image"]
            or pair["source_sha256"] != record["source_sha256"] or pair["size"] != record["size"]
            or {assignment["A"], assignment["B"]} != {"gsam2", "sam3"}):
        raise ValueError("Paired source identity or assignment differs")


def edit_counts(prediction, reference):
    counts = metrics(prediction, reference)
    return {"added_sidewalk_pixels": counts["fn"], "removed_sidewalk_pixels": counts["fp"],
            "uncertain_pixels": counts["ignored"],
            "changed_from_binary_seed_pixels": int(np.count_nonzero(reference != prediction.astype(np.uint8)))}


def grouped_metrics(rows):
    if not rows or any(r["role"] not in ("failure", "control") for r in rows):
        raise ValueError("Expected nonempty failure/control rows")
    groups = {role: [r for r in rows if r["role"] == role] for role in ("failure", "control")}
    if not all(groups.values()):
        raise ValueError("Both failure and control groups are required")
    return {name: aggregate(group) for name, group in {**groups, "all": rows}.items()}


def error_view(image, prediction, reference):
    rgb = np.array(image, dtype=np.float32)
    for hit, color in (((reference == 0) & prediction, (238, 58, 145)),
                       ((reference == 1) & ~prediction, (255, 160, 40)),
                       (reference == 255, (130, 130, 130))):
        rgb[hit] = .35 * rgb[hit] + .65 * np.asarray(color)
    return Image.fromarray(rgb.astype(np.uint8))


def save_panel(path, image, reference, predictions, frame):
    views = [("SOURCE", image), ("YOUR REVIEWED REFERENCE: green=sidewalk, amber=uncertain", overlay(image, reference))]
    for method in ("gsam2", "sam3"):
        score = metrics(predictions[method], reference)["iou"]
        value = "undefined" if score is None else f"{score:.2%}"
        views.append((f"{method.upper()} frozen prediction / IoU {value}", overlay(image, predictions[method].astype(np.uint8))))
    for method in ("gsam2", "sam3"):
        views.append((f"{method.upper()}: pink=extra, orange=missed, gray=excluded", error_view(image, predictions[method], reference)))
    canvas = Image.new("RGB", (1280, 1180), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), f'{frame["position"]:02d} / {frame["pair"]} / {frame["role"]} / {frame["image"]}', fill="black")
    for index, (label, view) in enumerate(views):
        x, y = index % 2 * 640, 28 + index // 2 * 384
        draw.text((x + 8, y + 4), label, fill="black")
        canvas.paste(view.resize((640, 360)), (x, y + 24))
    canvas.save(path, quality=94)


def percent(value):
    return "undefined" if value is None else f"{value:.2%}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("corrections", "targeted-package", "paired-package", "mapping", "sam3", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    hashes = {}

    def read(path):
        path = path.resolve()
        hashes[str(path)] = sha256(path)
        return json.loads(path.read_text())

    root = args.targeted_package.resolve()
    integrity = read(root / "integrity-check.json")
    for relative, expected in integrity["files_sha256"].items():
        path = safe_file(root, relative)
        if sha256(path) != expected:
            raise ValueError(f"Targeted package changed: {relative}")
        hashes[str(path)] = expected
    selection = read(root / "selection.json")
    manifest = read(root / "manifest.json")
    key = validate_selection(selection, manifest)
    if key != integrity["dataset_key"]:
        raise ValueError("Integrity dataset key differs")
    export_hash = sha256(args.corrections)
    hashes[str(args.corrections.resolve())] = export_hash
    adapter = {**selection, "baseline": str(root), "source": str(root / "images"), "images": manifest["images"]}
    export, references = load_references(args.corrections, adapter, include_drafts=False)
    paired = read(args.paired_package / "manifest.json")
    mapping = read(args.mapping)
    sam3_config = read(args.sam3 / "config.json")
    if (paired["selection_sha256"] != mapping["selection_sha256"]
            or paired["selection_sha256"] != sam3_config["selection_sha256"]
            or sam3_config["model"] != "facebook/sam3"):
        raise ValueError("Paired selection/model provenance differs")
    by_pair = {p["id"]: p for p in paired["pairs"]}
    if len(by_pair) != len(paired["pairs"]):
        raise ValueError("Duplicate paired IDs")
    out = args.output.resolve()
    protected = (root, args.paired_package, args.mapping, args.sam3, args.corrections)
    if out.exists() or any(out == p.resolve() or out in p.resolve().parents or p.resolve() in out.parents for p in protected):
        raise ValueError("Use a new output directory separate from all inputs")
    out.mkdir(parents=True)
    for name in ("references", "panels", "records", "predictions", "provenance"):
        (out / name).mkdir()
    shutil.copy2(args.corrections, out / "original-corrections.json")
    shutil.copy2(root / "selection.json", out / "provenance" / "selection.json")
    shutil.copy2(root / "provenance" / "gsam2-manifest.json", out / "provenance" / "gsam2-manifest.json")
    shutil.copy2(args.sam3 / "config.json", out / "provenance" / "sam3-config.json")
    for name in (Path(__file__).name, "evaluate_class1_corrections.py", "compare_class1_methods.py", "label_grounded_sam2.py"):
        path = Path(__file__).with_name(name)
        hashes[str(path)] = sha256(path)
        shutil.copy2(path, out / "provenance" / name)
    rows = []
    for frame, annotation, reference in references:
        pair = by_pair[frame["pair"]]
        assignment = mapping["pairs"][frame["pair"]]
        validate_pair(frame, pair, assignment)
        # SAM 3 records use original pair numbers, not the reordered correction positions.
        sam3_record = read(args.sam3 / "records" / f'{int(pair["id"].split("-")[1]):02d}.json')
        check_identity(sam3_record, frame)
        predictions = {"gsam2": checked_asset(root, {"path": frame["record"]["mask"], "sha256": frame["record"]["mask_sha256"]}, reference.shape, hashes),
                       "sam3": checked_asset(args.sam3, sam3_record["instance_union"], reference.shape, hashes)}
        for side in ("A", "B"):
            candidate = pair["candidates"][side]
            mask = checked_asset(args.paired_package, {"path": candidate["mask"], "sha256": candidate["mask_sha256"]}, reference.shape, hashes)
            if not np.array_equal(mask, predictions[assignment[side]]):
                raise ValueError("Prediction pixels differ from original paired review")
        stem = f'{frame["position"]:02d}-{frame["pair"]}'
        ref_path = out / "references" / f"{stem}.png"
        Image.fromarray(reference).save(ref_path)
        for method, prediction in predictions.items():
            Image.fromarray(np.where(prediction, 1, 255).astype(np.uint8)).save(out / "predictions" / f"{stem}-{method}.png")
        row = {"position": frame["position"], "pair": frame["pair"], "role": frame["role"], "image": frame["image"],
               "export_status": annotation["status"], "source_sha256": frame["record"]["source_sha256"],
               "reference": {"path": str(ref_path.relative_to(out)), "sha256": sha256(ref_path), "pixels_sha256": annotation["pixels_sha256"],
                             "positive_pixels": int((reference == 1).sum()), "negative_pixels": int((reference == 0).sum()), "uncertain_pixels": int((reference == 255).sum())},
               "edits": edit_counts(predictions["gsam2"], reference), "metrics": {k: metrics(v, reference) for k, v in predictions.items()}}
        write_json(out / "records" / f"{stem}.json", {**row, "annotation": {k: v for k, v in annotation.items() if k != "pixels_rle"}})
        with Image.open(root / "images" / frame["image"]) as image:
            save_panel(out / "panels" / f"{stem}.jpg", image.convert("RGB"), reference, predictions, frame)
        rows.append(row)
    report = {"created_utc": utc_now(), "dataset_key": key, "export_sha256": export_hash,
              "exported_utc": export["exported_utc"], "statuses": dict(Counter(r["export_status"] for r in rows)),
              "scope": "Purposive development set: 12 selected failures and five accepted controls. Not a random sample or held-out test; no full-dataset accuracy estimate.",
              "reference_bias": "Student corrections were seeded from GSAM 2 proposals. Unchanged controls and proposal anchoring may favor GSAM 2. Reviewed status is not independent annotation validation.",
              "metric_policy": "Class 1 is sidewalk. Only reference 255 is excluded. Predicted 255 is negative, not excluded. Empty predictions remain in the results. Macro IoU averages defined per-image IoUs; micro pools pixels.",
              "new_inference": False, "training": False, "original_annotations_modified": False,
              "annotation_time": "Not measured; export/editor timestamps do not establish active correction time.",
              "rows": rows, "groups": grouped_metrics(rows), "input_sha256": hashes}
    for path, expected in hashes.items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"Input changed during evaluation: {path}")
    write_json(out / "report.json", report)
    with (out / "per-image.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["position", "pair", "role", "image", "method", "tp", "fp", "fn", "tn", "ignored", "iou", "precision", "recall", "f1"])
        writer.writeheader()
        for row in rows:
            for method, values in row["metrics"].items():
                writer.writerow({**{k: row[k] for k in ("position", "pair", "role", "image")}, "method": method, **values})
    lines = ["SidewalkPilot: targeted correction comparison", "", report["scope"], report["reference_bias"], "",
             "All 17 exports are marked reviewed; source, proposal and decoded pixel hashes verified.", "Original corrections and frozen predictions are unchanged. No inference or training.", ""]
    for group, methods in report["groups"].items():
        for method, value in methods.items():
            lines.append(f'{group:7} {method:5} n={value["images"]:2} mean IoU={percent(value["macro_iou"])} pooled precision={percent(value["micro"]["precision"])} recall={percent(value["micro"]["recall"])}')
    lines += ["", report["metric_policy"], "", "Open panels/ for source, reference, predictions and error overlays.",
              "references/: binary reference PNGs (0 non-sidewalk, 1 sidewalk, 255 uncertain).",
              "predictions/: frozen binary proposals (1 positive, 255 unassigned/non-positive).",
              "original-corrections.json: unchanged student export.", "No active annotation-time estimate was inferred."]
    (out / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    write_json(out / "integrity-check.json", {"files_sha256": {str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    print(json.dumps({"output": str(out), "statuses": report["statuses"], "groups": report["groups"]}, indent=2))


if __name__ == "__main__":
    main()
