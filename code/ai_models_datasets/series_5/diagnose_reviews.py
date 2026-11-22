#!/usr/bin/env python3
"""Validate a class-1 review, select diagnostic frames, and render paired comparisons."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from label_grounded_sam2 import sha256, verify_record, write_json


def review_rows(pilot, review):
    manifest = json.loads((pilot / "manifest.json").read_text())
    value = json.loads(review.read_text())
    expected = "sp-review:" + manifest["created_utc"] + ":" + manifest["contract"]["source_names_sha256"]
    if (value.get("schema") != "sidewalkpilot-mask-review-v2" or value.get("dataset_key") != expected
            or value.get("review_scope", {}).get("kind") != "class"
            or value["review_scope"].get("class_ids") != [1]):
        raise ValueError("Expected a matching class-1 review export")
    if set(value["decisions"]) != set(manifest["images"]):
        raise ValueError("Review must include exactly the pilot's images")
    source = Path(manifest["contract"]["source"])
    rows = []
    for name in manifest["images"]:
        entry = value["decisions"][name]
        if entry["decision"] not in ("correct", "needs_correction", "uncertain", "unreviewed"):
            raise ValueError("Invalid decision")
        record = json.loads((pilot / "records" / (Path(name).stem + ".json")).read_text())
        verify_record(pilot, record, source)
        if entry["mask_sha256"] != record["mask_sha256"]:
            raise ValueError("Review no longer matches mask")
        rows.append({"image": name, "run": name.split("__", 1)[0], "decision": entry["decision"],
                     "class_1_fraction": record["pixel_counts"].get("1", 0) / np.prod(record["size"]),
                     "accepted_class_1_candidates": sum(d["class_id"] == 1 and d.get("accepted", False) for d in record["detections"]),
                     "mask_sha256": record["mask_sha256"]})
    return manifest, rows


def select_diagnostics(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["run"]].append(row)
    selected = []
    for run, group in sorted(groups.items()):
        failed = sorted((r for r in group if r["decision"] == "needs_correction"), key=lambda r: (r["class_1_fraction"], r["image"]))
        good = sorted((r for r in group if r["decision"] == "correct"), key=lambda r: r["image"])
        if len(failed) < 3 or not good:
            raise ValueError(f"Need at least three flagged and one approved frame for {run}")
        for position, reason in ((0, "low class-1 coverage"), (len(failed) // 2, "middle class-1 coverage"), (-1, "high class-1 coverage")):
            selected.append({**failed[position], "selection_reason": reason})
        selected.append({**good[len(good) // 2], "selection_reason": "approved regression control"})
    return selected


def focus_overlay(image, mask):
    raw = np.asarray(image).copy()
    selected = mask == 1
    raw[selected] = (raw[selected] * .55 + np.array([38, 190, 148]) * .45).astype(np.uint8)
    return Image.fromarray(raw)


def compare(pilot, candidate, selection_path, output):
    selection = json.loads(selection_path.read_text())
    manifest = json.loads((pilot / "manifest.json").read_text())
    other = json.loads((candidate / "manifest.json").read_text())
    if selection["images"] != other["images"]:
        raise ValueError("Candidate must use the same ordered diagnostic image list")
    if selection.get("baseline_manifest_sha256") != sha256(pilot / "manifest.json"):
        raise ValueError("Selection must identify the reviewed baseline")
    previous_decisions = {row["image"]: row["decision"] for row in selection.get("examples", [])}
    source = Path(manifest["contract"]["source"])
    output.mkdir(parents=True, exist_ok=False)
    panels = []
    rows = []
    for number, name in enumerate(selection["images"], 1):
        old = json.loads((pilot / "records" / (Path(name).stem + ".json")).read_text())
        new = json.loads((candidate / "records" / (Path(name).stem + ".json")).read_text())
        verify_record(pilot, old, source)
        verify_record(candidate, new, source)
        with Image.open(source / name) as original:
            image = original.convert("RGB")
        with Image.open(pilot / old["mask"]) as raw:
            before = np.asarray(raw).copy()
        with Image.open(candidate / new["mask"]) as raw:
            after = np.asarray(raw).copy()
        if before.shape != after.shape:
            raise ValueError("Mask shapes differ")
        panel = Image.new("RGB", (1920, 412), "white")
        draw = ImageDraw.Draw(panel)
        prior = f" / previous review: {previous_decisions[name]}" if name in previous_decisions else ""
        draw.text((8, 6), f"{number:02d} {name}{prior}", fill="black")
        for column, (label, view) in enumerate((("SOURCE", image), ("BASELINE CLASS 1", focus_overlay(image, before)), ("CANDIDATE CLASS 1 - UNREVIEWED", focus_overlay(image, after)))):
            draw.text((column * 640 + 8, 28), label, fill="black")
            panel.paste(view.resize((640, 360)), (column * 640, 52))
        panel.save(output / f"{number:02d}.jpg", quality=92)
        panels.append(panel)
        union = np.count_nonzero((before == 1) | (after == 1))
        rows.append({"image": name, "before_class_1_fraction": float(np.mean(before == 1)),
                     "after_class_1_fraction": float(np.mean(after == 1)),
                     "class_1_agreement_iou": float(np.count_nonzero((before == 1) & (after == 1)) / union) if union else None})
    for start in range(0, len(panels), 4):
        sheet = Image.new("RGB", (1920, 412 * len(panels[start:start+4])), "white")
        for i, panel in enumerate(panels[start:start+4]):
            sheet.paste(panel, (0, i * 412))
        sheet.save(output / f"sheet-{start//4+1}.jpg", quality=92)
    write_json(output / "comparison.json", {"candidate": str(candidate), "images": rows,
               "note": "Coverage and agreement with flawed baseline are diagnostics, NOT accuracy. No candidate human decisions exist yet."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--selection", type=Path)
    args = parser.parse_args()
    if args.compare:
        if not args.selection:
            parser.error("--compare requires --selection")
        compare(args.pilot, args.compare, args.selection, args.output)
        return
    if not args.review:
        parser.error("--review is required when selecting diagnostics")
    manifest, rows = review_rows(args.pilot, args.review)
    examples = select_diagnostics(rows)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "selection.json", {"images": [r["image"] for r in examples], "examples": examples,
               "review_sha256": sha256(args.review), "baseline_manifest_sha256": sha256(args.pilot / "manifest.json"),
               "purpose": "Purposive development set, three coverage strata of failures and one approved control per recording run. Not an independent validation sample."})
    write_json(args.output / "review-audit.json", {"review_path": str(args.review), "review_sha256": sha256(args.review),
               "dataset_key": "sp-review:" + manifest["created_utc"] + ":" + manifest["contract"]["source_names_sha256"],
               "scope": "class 1 only", "counts": dict(Counter(r["decision"] for r in rows)), "images": rows})
    print(json.dumps({"counts": dict(Counter(r["decision"] for r in rows)), "diagnostic_images": len(examples), "output": str(args.output)}))


if __name__ == "__main__":
    main()
