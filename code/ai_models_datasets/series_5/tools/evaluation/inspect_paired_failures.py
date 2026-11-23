#!/usr/bin/env python3
"""Build read-only diagnostics for a completed paired mask review; no inference."""

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

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from evaluate_class1_corrections import overlay
from label_grounded_sam2 import sha256, utc_now, write_json
from score_paired_review import score


def review_group(gsam2, sam3):
    if gsam2 == sam3 == "needs_correction":
        return "both_need_correction"
    if gsam2 == "needs_correction" and sam3 == "correct":
        return "sam3_only_correct"
    if gsam2 == "correct" and sam3 == "needs_correction":
        return "gsam2_only_correct"
    if gsam2 == sam3 == "correct":
        return "both_correct"
    return "other"


def mask_diagnostics(gsam2, sam3):
    if gsam2.shape != sam3.shape or gsam2.ndim != 2:
        raise ValueError("Mask shapes differ")
    union = int((gsam2 | sam3).sum())
    return {"gsam2_coverage": float(gsam2.mean()), "sam3_coverage": float(sam3.mean()),
            "intermodel_iou_not_accuracy": float((gsam2 & sam3).sum() / union) if union else None,
            "gsam2_only_pixels": int((gsam2 & ~sam3).sum()),
            "sam3_only_pixels": int((sam3 & ~gsam2).sum())}


def detection_summary(detections):
    accepted = [d for d in detections if d["accepted"]]
    return {"gsam2_detections": len(detections), "gsam2_accepted": len(accepted),
            "gsam2_rejected": len(detections) - len(accepted),
            "gsam2_max_detector_score": max((d["detector_score"] for d in detections), default=None),
            "gsam2_max_accepted_quality": max((d["sam_quality"] for d in accepted), default=None)}


def font(size):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def make_panel(image, predictions, row):
    width, height = image.size
    canvas = Image.new("RGB", (width * 3, height + 66), "white")
    draw = ImageDraw.Draw(canvas)
    views = [("SOURCE", image)]
    for name in ("gsam2", "sam3"):
        label = f'{name.upper()} | {row[name + "_decision"]} | effort: {row[name + "_effort"]}'
        views.append((label, overlay(image, predictions[name].astype(np.uint8))))
    for i, (label, view) in enumerate(views):
        draw.text((i * width + 10, 7), row["pair"] + " / " + label, font=font(22), fill="black")
        draw.text((i * width + 10, 38), row["image"], font=font(16), fill="black")
        canvas.paste(view, (i * width, 66))
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("package", "mapping", "review", "gsam2", "sam3", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    roots = [args.package.resolve(), args.gsam2.resolve(), args.sam3.resolve(), args.review.parent.resolve()]
    if out.exists() or any(out == root or root in out.parents or out in root.parents for root in roots):
        raise ValueError("Use a new output directory separate from inputs")
    hashes = {}

    def read_json(path):
        hashes[str(path)] = sha256(path)
        return json.loads(path.read_text())

    def checked(path, expected):
        if sha256(path) != expected:
            raise ValueError(f"Asset identity differs: {path}")
        hashes[str(path)] = expected

    manifest = read_json(args.package / "manifest.json")
    mapping = read_json(args.mapping)
    review = read_json(args.review)
    result = score(manifest, mapping, review)
    if not result["complete"]:
        raise ValueError("Complete the paired review before unblinded inspection")
    out.mkdir(parents=True)
    (out / "panels").mkdir()
    (out / "sheets").mkdir()
    rows, groups = [], {"both_need_correction": [], "sam3_only_correct": [], "rating_check": []}
    for number, pair in enumerate(manifest["pairs"], 1):
        sides = {method: side for side, method in mapping["pairs"][pair["id"]].items() if side in ("A", "B")}
        decisions = review["decisions"][pair["id"]]
        row = {"pair": pair["id"], "image": pair["source_name"]}
        masks = {}
        for method, side in sides.items():
            row.update({method + "_decision": decisions[side]["decision"], method + "_effort": decisions[side]["effort"]})
            asset = pair["candidates"][side]
            path = args.package / asset["mask"]
            checked(path, asset["mask_sha256"])
            with Image.open(path) as handle:
                values = np.array(handle)
            if values.shape != tuple(reversed(pair["size"])) or not set(np.unique(values)) <= {1, 255}:
                raise ValueError("Unexpected mask dimensions or class IDs")
            masks[method] = values == 1
        group = review_group(row["gsam2_decision"], row["sam3_decision"])
        row["group"] = group
        row.update(mask_diagnostics(masks["gsam2"], masks["sam3"]))
        g = read_json(args.gsam2 / "records" / (Path(pair["source_name"]).stem + ".json"))
        s = read_json(args.sam3 / "records" / f"{number:02d}.json")
        for record, method, expected in ((g, "gsam2", g["mask_sha256"]), (s, "sam3", s["instance_union"]["sha256"])):
            if (record["image"] != pair["source_name"] or record["source_sha256"] != pair["source_sha256"]
                    or expected != pair["candidates"][sides[method]]["mask_sha256"]):
                raise ValueError("Inference record identity differs")
        row.update(detection_summary(g["detections"]))
        row["sam3_instances"] = len(s["instances"])
        row["sam3_max_score"] = max(s["instance_scores"], default=None)
        row["rating_check"] = any(d["decision"] == "correct" and d["effort"] == "major" for d in decisions.values())
        path = args.package / pair["image"]
        checked(path, pair["source_sha256"])
        if group in groups or row["rating_check"]:
            with Image.open(path) as handle:
                image = handle.convert("RGB")
            if image.size != tuple(pair["size"]):
                raise ValueError("Source dimensions differ")
            relative = f'panels/{pair["id"]}.jpg'
            make_panel(image, masks, row).save(out / relative, quality=95)
            row["panel"] = relative
            if group in groups:
                groups[group].append(row)
            if row["rating_check"]:
                groups["rating_check"].append(row)
        else:
            row["panel"] = ""
        rows.append(row)
    sheets = {}
    for group, entries in groups.items():
        sheets[group] = []
        for offset in range(0, len(entries), 6):
            batch = entries[offset:offset + 6]
            sheet = Image.new("RGB", (1920, 32 + 393 * len(batch)), "white")
            ImageDraw.Draw(sheet).text((10, 6), f'{group} | source / revised GSAM 2 / SAM 3 | existing predictions, not references', font=font(17), fill="black")
            for i, row in enumerate(batch):
                with Image.open(out / row["panel"]) as panel:
                    sheet.paste(panel.resize((1920, 393), Image.Resampling.LANCZOS), (0, 32 + i * 393))
            relative = f"sheets/{group}-{offset // 6 + 1:02d}.jpg"
            sheet.save(out / relative, quality=94)
            sheets[group].append(relative)
    summary = {}
    for group in sorted({r["group"] for r in rows}):
        entries = [r for r in rows if r["group"] == group]
        summary[group] = {"count": len(entries),
                          "gsam2_zero_detections": sum(r["gsam2_detections"] == 0 for r in entries),
                          "gsam2_all_detections_rejected": sum(r["gsam2_detections"] > 0 and r["gsam2_accepted"] == 0 for r in entries),
                          "gsam2_multiple_accepted": sum(r["gsam2_accepted"] > 1 for r in entries),
                          "sam3_empty": sum(r["sam3_coverage"] == 0 for r in entries),
                          "gsam2_accepted_quality_ge_0_9": sum((r["gsam2_max_accepted_quality"] or 0) >= .9 for r in entries)}
    for path, digest in hashes.items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"Input changed during inspection: {path}")
    write_json(out / "report.json", {"created_utc": utc_now(), "review_score": result, "group_summary": summary,
               "rows": rows, "sheets": sheets, "input_sha256": hashes, "script_sha256": sha256(Path(__file__)),
               "note": "Existing predictions and student image ratings only. No new inference, mask changes, pixel ground truth, or revised acceptance claims. Intermodel overlap and confidence are not accuracy."})
    with (out / "per-image.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"output": str(out), "groups": summary, "sheets": sheets}, indent=2))


if __name__ == "__main__":
    main()
