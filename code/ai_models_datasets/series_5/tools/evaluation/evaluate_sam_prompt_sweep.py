#!/usr/bin/env python3
"""Evaluate a frozen SAM prompt sweep without choosing prompts per reference image."""

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

from compare_class1_methods import aggregate, checked_asset, check_identity
from compare_sam31_sidewalk import CHECKPOINT_SHA256, SAM3_CHECKPOINT_SHA256, COMMIT
from compare_sam3_sidewalk import output_path, validate_inputs
from evaluate_class1_corrections import load_references, metrics, overlay, read_mask
from label_grounded_sam2 import sha256, utc_now, write_json
from run_sam_prompt_sweep import PROMPTS, THRESHOLD

MATCHED_FIELDS = ("selection_sha256", "official_source_commit", "score_threshold", "mask_threshold",
                  "weight_dtype", "autocast", "tf32", "use_fa3", "use_rope_real", "packages",
                  "sam3_config_sha256", "runner_sha256", "official_file_sha256")
BASELINES = ("gsam2_original_composed", "gsam2_sidewalk_first")


def validate_configs(plan, configs, selection_hash):
    expected = [(f"{model}-p{i}", prompt) for model in ("sam3", "sam31") for i, prompt in enumerate(PROMPTS, 1)]
    if (plan["status"] != "complete" or plan["score_threshold"] != THRESHOLD
            or plan["selection_sha256"] != selection_hash
            or [(r["key"], r["prompt"]) for r in plan["recipes"]] != expected
            or set(configs) != {key for key, _ in expected}):
        raise ValueError("Expected all six completed fixed recipes on the original image selection")
    first = configs[expected[0][0]]
    for key, prompt in expected:
        cfg = configs[key]
        control = key.startswith("sam3-")
        load = cfg["load_report"]
        if (cfg["prompt"] != prompt or cfg["score_threshold"] != THRESHOLD or cfg["mask_threshold"] != .5
                or cfg["model"] != ("facebook/sam3" if control else "facebook/sam3.1")
                or cfg["checkpoint_sha256"] != (SAM3_CHECKPOINT_SHA256 if control else CHECKPOINT_SHA256)
                or cfg["native_sam3_control"] is not control or cfg["official_source_commit"] != COMMIT
                or cfg["selection_sha256"] != selection_hash or cfg["runner_sha256"] != plan["runner_sha256"]
                or cfg["weight_dtype"] != "float32" or cfg["autocast"] != "bfloat16"
                or cfg["supervise_joint_box_scores"] is not (not control)
                or load["strict"] is not True or load["missing_detector_keys"] or load["unexpected_detector_keys"]):
            raise ValueError(f"Unexpected recipe or detector load: {key}")
        if any(cfg[field] != first[field] for field in MATCHED_FIELDS):
            raise ValueError("Runtime or preprocessing differs across prompt recipes")


def panel(path, image, reference, predictions, scores, labels, heading):
    views = [("SOURCE", image), ("USER REFERENCE (export status unchanged)", overlay(image, reference))]
    for key in ("gsam2_sidewalk_first", *labels):
        name = labels.get(key, "Revised automatic GSAM 2")
        value = scores[key]["iou"]
        label = f"{name} | IoU {value:.3f}" if value is not None else f"{name} | IoU undefined"
        views.append((label, overlay(image, predictions[key].astype(np.uint8))))
    canvas = Image.new("RGB", (1920, 1180), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 5), heading, fill="black")
    for i, (label, view) in enumerate(views):
        x, y = i % 3 * 640, 28 + i // 3 * 384
        draw.text((x + 8, y + 4), label, fill="black")
        canvas.paste(view.resize((640, 360)), (x, y + 24))
    canvas.save(path, quality=94)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("audit", "corrections", "baseline-comparison", "sweep", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--include-drafts", action="store_true")
    parser.add_argument("--completion-note", default="")
    args = parser.parse_args()
    selection = validate_inputs(args.audit)
    source = Path(selection["source"])
    hashes = {}

    def load(path):
        hashes[str(path)] = sha256(path)
        return json.loads(path.read_text())

    plan = load(args.sweep / "sweep.json")
    configs = {r["key"]: load(args.sweep / r["key"] / "config.json") for r in plan["recipes"]}
    selection_hash = sha256(args.audit / "comparison/selection.json")
    validate_configs(plan, configs, selection_hash)
    previous = load(args.baseline_comparison / "report.json")
    if len(previous["images"]) != len(selection["frames"]):
        raise ValueError("Wrong baseline image count")
    hashes[str(args.corrections)] = sha256(args.corrections)
    hashes[str(args.audit / "comparison/selection.json")] = selection_hash
    _, references = load_references(args.corrections, selection, args.include_drafts)
    out = output_path(args.output, [source, Path(selection["baseline"]), args.audit,
                                   args.corrections, args.sweep, args.baseline_comparison])
    out.mkdir(parents=True)
    for folder in ("panels", "references", "masks", "records", "recipes"):
        (out / folder).mkdir()
    shutil.copy2(args.corrections, out / "original-corrections.json")
    shutil.copy2(Path(__file__), out / Path(__file__).name)
    for key, cfg in configs.items():
        write_json(out / "recipes" / f"{key}.json", cfg)
    labels = {key: f'{"SAM 3" if key.startswith("sam3-") else "SAM 3.1"}: {cfg["prompt"]}'
              for key, cfg in configs.items()}
    report = {"created_utc": utc_now(), "evaluator_sha256": sha256(Path(__file__)), "labels": labels,
              "score_threshold": THRESHOLD, "mask_threshold": .5,
              "scope": "Ten purposive development images, not independent or full-dataset accuracy. No prompt selection per image.",
              "runtime": "Both native detectors use bfloat16 autocast and shared HF image pre/postprocessing. Not a video/tracking test.",
              "reference_note": "User corrections were seeded from assisted SAM 2 proposals; possible reference anchoring bias.",
              "export_status_counts": dict(Counter(a["status"] for _, a, _ in references)),
              "provisional": any(a["status"] != "reviewed" for _, a, _ in references),
              "completion_note": args.completion_note,
              "metric_policy": "Only reference 255 is ignored. Prediction 255 counts as non-sidewalk. Empty detections stay in the denominator.",
              "previous_0_5_results": {key: previous["aggregate"][key] for key in
                                       ("sam3_native_control", "sam31_instance_union", "sam3_instance_union")},
              "images": []}
    for number, (frame, annotation, ref) in enumerate(references, 1):
        prior = previous["images"][number - 1]
        old_ref = args.baseline_comparison / "references" / f"{number:02d}.png"
        if (prior["image"] != frame["image"] or prior["source_sha256"] != frame["record"]["source_sha256"]
                or sha256(old_ref) != prior["reference_sha256"]
                or not np.array_equal(read_mask(old_ref, ref.shape, (0, 1, 255)), ref)):
            raise ValueError("Baseline reference or source changed")
        hashes[str(old_ref)] = sha256(old_ref)
        hashes[str(source / frame["image"])] = frame["record"]["source_sha256"]
        predictions = {key: checked_asset(args.baseline_comparison, prior["predictions"][key], ref.shape, hashes)
                       for key in BASELINES}
        details, pixels_hash = {}, None
        for key in configs:
            root = args.sweep / key
            row = load(root / "records" / f"{number:02d}.json")
            check_identity(row, frame)
            if pixels_hash is not None and row["pixel_values_sha256"] != pixels_hash:
                raise ValueError("Preprocessed image pixels differ across prompt runs")
            pixels_hash = row["pixel_values_sha256"]
            predictions[key] = checked_asset(root, row["instance_union"], ref.shape, hashes)
            details[key] = {"instances": len(row["instances"]), "scores": row["instance_scores"],
                            "coverage": float(predictions[key].mean()), "forward_seconds": row["model_forward_seconds"]}
        Image.fromarray(ref).save(out / "references" / f"{number:02d}.png")
        saved = {}
        for key, mask in predictions.items():
            relative = f"masks/{number:02d}-{key}.png"
            Image.fromarray(np.where(mask, 1, 255).astype(np.uint8)).save(out / relative)
            saved[key] = {"path": relative, "sha256": sha256(out / relative), "review_status": "unreviewed"}
        row = {"image": frame["image"], "prior_index": frame["prior_index"], "annotation_status": annotation["status"],
               "source_sha256": frame["record"]["source_sha256"], "pixel_values_sha256": pixels_hash,
               "metrics": {key: metrics(mask, ref) for key, mask in predictions.items()},
               "details": details, "predictions": saved}
        report["images"].append(row)
        write_json(out / "records" / f"{number:02d}.json", row)
        with Image.open(source / frame["image"]) as image:
            panel(out / "panels" / f"{number:02d}.jpg", image.convert("RGB"), ref, predictions, row["metrics"], labels,
                  f'{number:02d}: {frame["image"]} | SAM score threshold 0.4 / development diagnostic only')
    report["aggregate"] = aggregate(report["images"])
    for key in configs:
        details = [r["details"][key] for r in report["images"]]
        report["aggregate"][key].update(images_with_detections=sum(d["instances"] > 0 for d in details),
                                       total_instances=sum(d["instances"] for d in details))
    for path, expected in hashes.items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"Input changed during evaluation: {path}")
    report["input_sha256"] = hashes
    write_json(out / "report.json", report)
    with (out / "per-image.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "method", "tp", "fp", "fn", "tn", "ignored", "iou", "precision", "recall", "f1"])
        writer.writeheader()
        for row in report["images"]:
            for key, score in row["metrics"].items():
                writer.writerow({"image": row["image"], "method": key, **score})
    lines = ["SidewalkPilot: three-prompt comparison", "", report["scope"], report["runtime"],
             "Score threshold: 0.4 for all six new runs. Mask threshold: 0.5.", "",
             "Method | Mean per-image IoU | Images with detections"]
    for key, values in report["aggregate"].items():
        name = labels.get(key, key)
        iou = values["macro_iou"]
        score = f"{100 * iou:.2f}%" if iou is not None else "undefined"
        count = values.get("images_with_detections", "not counted")
        lines.append(f"{name} | {score} | {count}")
    prior_scores = report["previous_0_5_results"]
    lines.extend(["", f'Earlier native sidewalk-only / threshold 0.5: SAM 3 {100 * prior_scores["sam3_native_control"]["macro_iou"]:.2f}%, '
                  f'SAM 3.1 {100 * prior_scores["sam31_instance_union"]["macro_iou"]:.2f}%.',
                  f'Earlier HF SAM 3 float32 / threshold 0.5: {100 * prior_scores["sam3_instance_union"]["macro_iou"]:.2f}%; '
                  "different runtime, retained separately.",
                  "Within the six new recipes only the model/prompt changes; threshold stays fixed.",
                  "Detection counts and pixel coverage are not accuracy or human acceptance rates.",
                  report["reference_note"], "Reference draft statuses are preserved; completion was reported in chat.",
                  "Inspect panels/01.jpg through 10.jpg before choosing a recipe for a fresh review sample.",
                  "No full-dataset labeling, reference replacement, model training or publication performed."])
    (out / "SUMMARY.txt").write_text("\n".join(lines) + "\n")
    print(json.dumps({"output": str(out), "aggregate": report["aggregate"]}, indent=2))


if __name__ == "__main__":
    main()
