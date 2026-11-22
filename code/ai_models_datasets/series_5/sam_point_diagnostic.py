#!/usr/bin/env python3
"""Small SAM 2 point-prompt diagnostic, explicitly assisted rather than automatic."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw

from label_grounded_sam2 import save_mask, save_overlay, sha256, utc_now, validate_selection, verify_record, write_json

HERE = Path(__file__).resolve().parent
MODEL = "facebook/sam2.1-hiera-large"
REVISION = "665f8e2ad61cf5f53d65644ff27c8ee525124610"


def validate_points(prompt, width, height):
    points, labels = [], []
    for field, value in (("positive", 1), ("negative", 0)):
        group = prompt.get(field)
        if not isinstance(group, list) or not group:
            raise ValueError("Both positive and negative point lists are required")
        for point in group:
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(coordinate) is not int for coordinate in point)
                    or not 0 <= point[0] < width or not 0 <= point[1] < height):
                raise ValueError("Points must be integer pixels inside the original image")
            points.append(point)
            labels.append(value)
    if len({tuple(point) for point in points}) != len(points):
        raise ValueError("Duplicate or contradictory points")
    return points, labels


def choose_mask(masks, qualities, points, labels, minimum_quality=.7):
    masks, qualities = np.asarray(masks, dtype=bool), np.asarray(qualities)
    if masks.ndim != 3 or qualities.shape != (len(masks),):
        raise ValueError("Expected one quality score per two-dimensional mask")
    consistent = [all(bool(mask[y, x]) == bool(label) for (x, y), label in zip(points, labels)) for mask in masks]
    eligible = [i for i, score in enumerate(qualities) if np.isfinite(score) and score >= minimum_quality and consistent[i]]
    selected = max(eligible, key=lambda i: qualities[i]) if eligible else None
    return selected, consistent


def restrict_shadow_additions(baseline, candidate, polygons):
    """Add SAM-supported sidewalk only inside explicitly annotated shadow regions."""
    if baseline.shape != candidate.shape or baseline.ndim != 2:
        raise ValueError("Baseline and candidate must be equally sized 2D masks")
    if not set(np.unique(baseline)) <= {1, 255} or not set(np.unique(candidate)) <= {1, 255}:
        raise ValueError("Shadow diagnostics must contain only class 1 and ignore")
    height, width = baseline.shape
    region = Image.new("1", (width, height))
    draw = ImageDraw.Draw(region)
    if not isinstance(polygons, list) or not polygons:
        raise ValueError("Explicit shadow polygons are required")
    for polygon in polygons:
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ValueError("Each shadow polygon needs at least three pixel coordinates")
        for point in polygon:
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(coordinate) is not int for coordinate in point)
                    or not 0 <= point[0] < width or not 0 <= point[1] < height):
                raise ValueError("Shadow polygon coordinates must be inside the image")
        draw.polygon([tuple(point) for point in polygon], fill=1)
    output = baseline.copy()
    additions = np.asarray(region, dtype=bool) & (baseline == 255) & (candidate == 1)
    output[additions] = 1
    return output, int(additions.sum())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads((args.pilot / "manifest.json").read_text())
    selection = json.loads(args.selection.read_text())
    names = validate_selection(selection, baseline["images"], len(selection["images"]))
    if not 0 < len(names) <= 20 or args.output.exists():
        parser.error("Use a new directory and at most 20 images; no full-dataset labeling")
    if selection.get("baseline_manifest_sha256") != sha256(args.pilot / "manifest.json"):
        parser.error("Selection does not match the reviewed baseline")
    if not selection.get("annotation_author") or set(selection.get("prompts", {})) != set(names):
        parser.error("Record the annotation author and explicit prompts for every selected image")
    repairs = selection.get("repair_regions", {})
    if not isinstance(repairs, dict) or not set(repairs) <= set(names):
        parser.error("Shadow repairs must reference selected images")
    source = Path(baseline["contract"]["source"])
    if sha256(source / "labels.json") != baseline["contract"]["steering_labels_sha256"]:
        parser.error("Source steering labels changed")
    old_records, point_inputs = {}, {}
    for name in names:
        old = json.loads((args.pilot / "records" / (Path(name).stem + ".json")).read_text())
        verify_record(args.pilot, old, source)
        with Image.open(source / name) as raw:
            point_inputs[name] = validate_points(selection["prompts"][name], raw.width, raw.height)
        old_records[name] = old

    import torch
    from transformers import Sam2Model, Sam2Processor

    torch.set_num_threads(4)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    processor = Sam2Processor.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
    model = Sam2Model.from_pretrained(MODEL, revision=REVISION, local_files_only=True).to("cuda").eval()
    taxonomy = json.loads((args.pilot / "taxonomy.json").read_text())
    config = {"method": "AI-assisted per-image point prompts + SAM 2; not automatic labeling",
              "model": MODEL, "revision": REVISION, "dtype": "float32", "multimask_output": True,
              "selection_rule": "Highest SAM quality among masks satisfying every point and quality >= 0.7; otherwise all ignore",
              "minimum_quality": .7, "annotation_author": selection["annotation_author"],
              "scope": "Class 1 only. Other pixels are ignore 255, not verified background or other classes.",
              "source": "https://huggingface.co/docs/transformers/model_doc/sam2"}
    if repairs:
        config["shadow_repair"] = "Preserve baseline labels everywhere; add SAM-supported class 1 only inside explicit AI-annotated shadow polygons"
        config["baseline_manifest_sha256"] = selection["baseline_manifest_sha256"]
        config["annotation_rule"] = selection.get("annotation_rule")
    contract = {**{k: baseline["contract"][k] for k in ("source", "source_count", "source_names_sha256", "steering_labels_sha256")},
                "count": len(names), "config": config, "taxonomy": taxonomy, "selection_sha256": sha256(args.selection),
                "runner_file": Path(__file__).name, "runner_sha256": sha256(Path(__file__)),
                "helper_files_sha256": {"label_grounded_sam2.py": sha256(HERE / "label_grounded_sam2.py")},
                "packages": {p: importlib.metadata.version(p) for p in ("torch", "transformers", "numpy", "Pillow")}}
    args.output.mkdir(parents=True)
    for folder in ("masks", "overlays", "records"):
        (args.output / folder).mkdir()
    write_json(args.output / "manifest.json", {"created_utc": utc_now(), "contract": contract, "images": names,
               "sampling": selection["purpose"], "purpose": "Assisted diagnostic, not automatic performance evaluation",
               "annotation_scope": {"kind": "class", "class_ids": [1], "other_pixels": "ignore"}})
    for name, value in (("taxonomy.json", taxonomy), ("label_config.json", config)):
        write_json(args.output / name, value)
    # Keep exact source bytes so the selection hash remains valid in a portable package.
    (args.output / "selection.json").write_bytes(args.selection.read_bytes())
    for name in (Path(__file__).name, "label_grounded_sam2.py"):
        (args.output / name).write_bytes((HERE / name).read_bytes())
    records = []
    with torch.inference_mode():
        for index, name in enumerate(names, 1):
            started = time.monotonic()
            points, labels = point_inputs[name]
            with Image.open(source / name) as raw:
                image = raw.convert("RGB")
            inputs = processor(images=image, input_points=[[points]], input_labels=[[labels]], return_tensors="pt").to("cuda")
            result = model(**inputs, multimask_output=True)
            masks = processor.post_process_masks(result.pred_masks.cpu(), inputs.original_sizes.cpu())[0].numpy().reshape(-1, image.height, image.width).astype(bool)
            qualities = result.iou_scores.cpu().numpy().ravel()
            selected, consistent = choose_mask(masks, qualities, points, labels)
            pixels = masks[selected] if selected is not None else np.zeros((image.height, image.width), dtype=bool)
            mask = np.where(pixels, 1, 255).astype(np.uint8)
            repair = None
            if name in repairs:
                old = old_records[name]
                with Image.open(args.pilot / old["mask"]) as raw:
                    before = np.asarray(raw).copy()
                mask, added = restrict_shadow_additions(before, mask, repairs[name])
                repair = {"baseline_mask_sha256": old["mask_sha256"], "polygons": repairs[name],
                          "added_class_1_pixels": added, "removed_class_1_pixels": 0,
                          "method": config["shadow_repair"]}
                pixels = mask == 1
            if sha256(source / name) != old_records[name]["source_sha256"]:
                raise ValueError("Source image changed during inference")
            stem = Path(name).stem
            mask_name, overlay_name = f"masks/{stem}.png", f"overlays/{stem}.jpg"
            save_mask(args.output / mask_name, mask)
            save_overlay(args.output / overlay_name, image, mask, taxonomy)
            record = {"image": name, "source_sha256": old_records[name]["source_sha256"], "size": [image.width, image.height],
                      "mask": mask_name, "overlay": overlay_name, "mask_sha256": sha256(args.output / mask_name),
                      "overlay_sha256": sha256(args.output / overlay_name), "pixel_counts": {"1": int(pixels.sum()), "255": int((~pixels).sum())},
                      "labeled_fraction": float(pixels.mean()), "review_status": "unreviewed", "created_utc": utc_now(),
                      "seconds": round(time.monotonic() - started, 3), "qa_flags": ["AI_assisted_points", "class_1_only_diagnostic"] + ([] if selected is not None else ["no_eligible_mask"]),
                      "prompt": selection["prompts"][name], "sam_quality_estimates": qualities.tolist(),
                      "point_consistent": consistent, "selected_candidate": selected,
                      "detections": [], "unmapped_detections": [], "detections_truncated": False}
            if repair is not None:
                record["shadow_repair"] = repair
                record["qa_flags"].append("AI_annotated_shadow_repair_regions")
            write_json(args.output / "records" / (stem + ".json"), record)
            records.append(record)
            print(f"[{index}/{len(names)}] {record['seconds']}s selected={selected} class1={pixels.mean():.1%} {name}", flush=True)
    if sha256(source / "labels.json") != contract["steering_labels_sha256"]:
        raise ValueError("Source steering labels changed during inference")
    write_json(args.output / "summary.json", {"completed": len(records), "reviewed": 0,
               "status": "AI-assisted class-1 diagnostic; human review pending", "seconds": sum(r["seconds"] for r in records),
               "note": "SAM scores and point consistency are not ground-truth accuracy. No other classes were labeled."})


if __name__ == "__main__":
    main()
