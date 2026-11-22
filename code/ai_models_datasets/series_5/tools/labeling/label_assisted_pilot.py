#!/usr/bin/env python3
"""Generate at most 200 class-1 masks from explicit, per-image assisted points."""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
from collections import Counter
import fcntl
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from label_grounded_sam2 import (
    digest_json, save_mask, save_overlay, sha256, utc_now, validate_selection,
    validate_taxonomy, verify_record, write_json,
)
from sam_point_diagnostic import MODEL, REVISION, choose_mask, validate_points

HERE = _workspace.TOOLS


def refinement_seed(masks, qualities, points, labels):
    """Prefer fewer point violations, then higher SAM quality, for mask feedback."""
    masks, qualities = np.asarray(masks, dtype=bool), np.asarray(qualities)
    if masks.ndim != 3 or qualities.shape != (len(masks),):
        raise ValueError("Expected one score per 2D candidate mask")
    violations = [sum(bool(mask[y, x]) != bool(label) for (x, y), label in zip(points, labels)) for mask in masks]
    eligible = [i for i, q in enumerate(qualities) if np.isfinite(q)]
    best = min(eligible, key=lambda i: (violations[i], -qualities[i], i)) if eligible else None
    return best, violations


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_annotations(directory, count):
    annotations = {}
    for path in sorted(directory.glob("annotations-*.json")):
        batch = json.loads(path.read_text(), object_pairs_hook=unique_object)
        if not isinstance(batch, dict) or set(batch) & set(annotations):
            raise ValueError("Annotation batches must be objects with unique image indices")
        annotations.update(batch)
    if set(annotations) != {str(i) for i in range(1, count + 1)}:
        raise ValueError("Exactly one annotation or abstention is required for every selected image")
    return annotations


def pixel_prompt(annotation, width, height):
    if not isinstance(annotation, dict) or set(annotation) - {"p", "n", "abstain", "tags", "note"}:
        raise ValueError("Invalid annotation fields")
    if (not isinstance(annotation.get("tags", []), list)
            or any(not isinstance(t, str) for t in annotation.get("tags", []))
            or not isinstance(annotation.get("note", ""), str)):
        raise ValueError("Annotation tags and note must be text")
    if "abstain" in annotation:
        if (not isinstance(annotation["abstain"], str) or not annotation["abstain"].strip()
                or "p" in annotation or "n" in annotation):
            raise ValueError("An abstention needs a reason and must not also contain points")
        return None
    prompt = {}
    for key, target in (("p", "positive"), ("n", "negative")):
        values = annotation.get(key)
        if not isinstance(values, list) or not values:
            raise ValueError("Positive and negative normalized points are required")
        converted = []
        for pair in values:
            if (not isinstance(pair, list) or len(pair) != 2
                    or any(type(v) is not int or not 0 <= v <= 1000 for v in pair)):
                raise ValueError("Normalized point coordinates must be integers from 0 to 1000")
            converted.append([round(pair[0] * (width - 1) / 1000), round(pair[1] * (height - 1) / 1000)])
        prompt[target] = converted
    validate_points(prompt, width, height)
    return prompt


def validate_sources(selection):
    source = Path(selection["source"]).resolve()
    names = sorted(p.name for p in source.glob("*.jpg"))
    if (len(names) != selection["source_count"] or digest_json(names) != selection["source_names_sha256"]
            or sha256(source / "labels.json") != selection["steering_labels_sha256"]
            or set(names) != set(json.loads((source / "labels.json").read_text()))):
        raise ValueError("Source pool or original steering labels changed")
    selected = validate_selection(selection, names, len(selection["images"]))
    if not 0 < len(selected) <= 200 or set(selection["source_sha256"]) != set(selected):
        raise ValueError("This runner is capped at 200 individually hashed source images")
    if set(selected) & set(selection.get("excluded_names", [])):
        raise ValueError("Fresh pilot overlaps excluded images")
    for name in selected:
        if sha256(source / name) != selection["source_sha256"][name]:
            raise ValueError(f"Source image changed: {name}")
    return source, selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, default=_workspace.source_path('taxonomy.json'))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--refinement-steps", type=int, choices=range(4), default=0,
                        help="At most three mask-feedback passes, only if no candidate passes the point checks")
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text(), object_pairs_hook=unique_object)
    source, names = validate_sources(selection)
    annotations = load_annotations(args.annotations, len(names))
    prompts = {}
    for i, name in enumerate(names, 1):
        with Image.open(source / name) as image:
            prompts[name] = pixel_prompt(annotations[str(i)], image.width, image.height)
    if not selection.get("annotation_author"):
        raise ValueError("Annotation author must be disclosed")
    selection["annotations"] = {name: annotations[str(i)] for i, name in enumerate(names, 1)}
    selection["prompts"] = prompts
    selection["annotation_batch_sha256"] = {p.name: sha256(p) for p in sorted(args.annotations.glob("annotations-*.json"))}
    selection_bytes = (json.dumps(selection, indent=2) + "\n").encode()
    taxonomy = json.loads(args.taxonomy.read_text())
    validate_taxonomy(taxonomy)
    abstentions = sum(p is None for p in prompts.values())
    if args.validate_only:
        print(json.dumps({"images": len(names), "point_annotations": len(names) - abstentions,
                          "abstentions": abstentions, "source_hashes_valid": True}))
        return
    output = args.output.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Output must be separate from the source tree")
    config = {"method": "AI-assisted per-image points + SAM 2; no automatic text grounding",
              "model": MODEL, "revision": REVISION, "dtype": "float32", "multimask_output": True,
              "minimum_quality": .7,
              "max_refinement_steps": args.refinement_steps,
              "refinement_policy": "Only after no eligible mask: feed the candidate with fewest point violations (then highest quality) back to SAM; retain all point and quality requirements",
              "selection_rule": "Highest SAM quality satisfying every point and quality >= 0.7; otherwise all ignore",
              "annotation_author": selection["annotation_author"],
              "scope": "Class 1 only; all other pixels are ignore 255, not verified background",
              "shadow_rule": "Shadows remain the underlying sidewalk; actual occluding objects are excluded",
              "abstention_rule": "Ambiguous source frames remain in sample with all-ignore mask and reason"}
    helpers = ("label_grounded_sam2.py", "sam_point_diagnostic.py")
    contract = {**{k: selection[k] for k in ("source", "source_count", "source_names_sha256", "steering_labels_sha256")},
                "count": len(names), "config": config, "taxonomy": taxonomy,
                "selection_sha256": hashlib.sha256(selection_bytes).hexdigest(),
                "runner_file": Path(__file__).name, "runner_sha256": sha256(Path(__file__)),
                "helper_files_sha256": {n: sha256(_workspace.source_path(n)) for n in helpers},
                "packages": {p: importlib.metadata.version(p) for p in ("torch", "transformers", "numpy", "Pillow")}}
    if output.exists() and not args.resume:
        parser.error("Output exists; use a new directory or --resume with unchanged inputs")
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".label.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest_path = output / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if manifest["contract"] != contract or manifest["images"] != names:
                raise ValueError("Resume requires unchanged annotations, code, configuration and sources")
            if sha256(output / "selection.json") != contract["selection_sha256"]:
                raise ValueError("Archived selection changed")
        else:
            if any(p.name != ".label.lock" for p in output.iterdir()):
                raise ValueError("Refusing to initialize a nonempty output directory")
            for folder in ("masks", "overlays", "records"):
                (output / folder).mkdir()
            (output / "selection.json").write_bytes(selection_bytes)
            for name in (Path(__file__).name, *helpers):
                (output / name).write_bytes((_workspace.source_path(name)).read_bytes())
            write_json(output / "taxonomy.json", taxonomy)
            write_json(output / "label_config.json", config)
            write_json(manifest_path, {"created_utc": utc_now(), "contract": contract, "images": names,
                       "sampling": selection["sampling"], "purpose": selection["purpose"],
                       "review_label": selection.get("review_label", "Class 1 fresh pilot"),
                       "annotation_scope": {"kind": "class", "class_ids": [1], "other_pixels": "ignore"}})
        records, pending = [], []
        for i, name in enumerate(names, 1):
            record_path = output / "records" / (Path(name).stem + ".json")
            if record_path.exists():
                record = json.loads(record_path.read_text())
                if record["image"] != name or record["annotation"] != selection["annotations"][name]:
                    raise ValueError("Existing record identity or annotation changed")
                verify_record(output, record, source)
                records.append(record)
            else:
                pending.append((i, name))
        import torch
        from transformers import Sam2Model, Sam2Processor

        torch.set_num_threads(4)
        if any(prompts[name] is not None for _, name in pending):
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA required")
            processor = Sam2Processor.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
            model = Sam2Model.from_pretrained(MODEL, revision=REVISION, local_files_only=True).to("cuda").eval()
        with torch.inference_mode():
            for i, name in pending:
                started = time.monotonic()
                annotation, prompt = selection["annotations"][name], prompts[name]
                with Image.open(source / name) as raw:
                    image = raw.convert("RGB")
                pixels = np.zeros((image.height, image.width), dtype=bool)
                qualities, consistent, selected = [], [], None
                refinement_trace = []
                flags = ["AI_assisted_points", "class_1_only_pilot"]
                if prompt is None:
                    flags.append("annotation_abstention")
                else:
                    points, labels = validate_points(prompt, image.width, image.height)
                    inputs = processor(images=image, input_points=[[points]], input_labels=[[labels]], return_tensors="pt").to("cuda")
                    result = model(**inputs, multimask_output=True)
                    for step in range(args.refinement_steps + 1):
                        masks = processor.post_process_masks(result.pred_masks.cpu(), inputs.original_sizes.cpu())[0].numpy().reshape(-1, image.height, image.width).astype(bool)
                        qualities = result.iou_scores.cpu().numpy().ravel()
                        selected, consistent = choose_mask(masks, qualities, points, labels)
                        seed, violations = refinement_seed(masks, qualities, points, labels)
                        refinement_trace.append({"step": step, "point_violations": violations,
                                                 "qualities": [float(q) if np.isfinite(q) else None for q in qualities],
                                                 "selected_candidate": selected, "feedback_seed": seed})
                        if selected is not None or step == args.refinement_steps or seed is None:
                            break
                        # SAM consumes its low-resolution logits, not a hand-filled binary mask.
                        feedback = result.pred_masks[:, 0, seed:seed + 1].detach()
                        result = model(**inputs, input_masks=feedback, multimask_output=True)
                    if len(refinement_trace) > 1:
                        flags.append("iterative_SAM_mask_feedback")
                    qualities = [float(v) if np.isfinite(v) else None for v in qualities]
                    if selected is None:
                        flags.append("no_eligible_mask")
                    else:
                        pixels = masks[selected]
                if sha256(source / name) != selection["source_sha256"][name]:
                    raise ValueError(f"Source changed during inference: {name}")
                mask = np.where(pixels, 1, 255).astype(np.uint8)
                stem = Path(name).stem
                mask_name, overlay_name = f"masks/{stem}.png", f"overlays/{stem}.jpg"
                save_mask(output / mask_name, mask)
                save_overlay(output / overlay_name, image, mask, taxonomy,
                             caption="AI-ASSISTED CLASS 1 - UNREVIEWED; hatching = ignore")
                record = {"image": name, "source_sha256": selection["source_sha256"][name], "size": [image.width, image.height],
                          "mask": mask_name, "overlay": overlay_name, "mask_sha256": sha256(output / mask_name),
                          "overlay_sha256": sha256(output / overlay_name), "pixel_counts": {"1": int(pixels.sum()), "255": int((~pixels).sum())},
                          "labeled_fraction": float(pixels.mean()), "review_status": "unreviewed", "created_utc": utc_now(),
                          "seconds": round(time.monotonic() - started, 3), "qa_flags": flags,
                          "annotation": annotation, "prompt": prompt, "sam_quality_estimates": qualities,
                          "point_consistent": consistent, "selected_candidate": selected,
                          "refinement_trace": refinement_trace,
                          "detections": [], "unmapped_detections": [], "detections_truncated": False}
                write_json(output / "records" / (stem + ".json"), record)
                records.append(record)
                print(f"[{i}/{len(names)}] {record['seconds']}s selected={selected} class1={pixels.mean():.1%} {name}", flush=True)
        validate_sources(selection)
        totals = Counter(flag for record in records for flag in record["qa_flags"])
        write_json(output / "summary.json", {"completed": len(records), "reviewed": 0,
                   "status": "AI-assisted class-1 pilot; human review pending", "qa_flag_counts": dict(totals),
                   "sampling": selection["sampling"],
                   "seconds": sum(r["seconds"] for r in records),
                   "note": "SAM quality/point agreement are not accuracy. No other classes labeled."})
        print(json.dumps({"completed": len(records), "qa_flags": dict(totals), "output": str(output)}), flush=True)


if __name__ == "__main__":
    main()
