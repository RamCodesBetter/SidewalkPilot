#!/usr/bin/env python3
"""Capped class-1 diagnostic: pretrained semantic cues, optionally refined with SAM 2."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
from scipy import ndimage

from label_grounded_sam2 import save_mask, save_overlay, sha256, utc_now, validate_selection, verify_record, write_json

HERE = Path(__file__).resolve().parent
MODEL = "nvidia/segformer-b5-finetuned-cityscapes-1024-1024"
REVISION = "2c6f153e4c23c229e2fa2b188eb250607e030cd8"
SAM = "facebook/sam2.1-hiera-large"
SAM_REVISION = "665f8e2ad61cf5f53d65644ff27c8ee525124610"


def interior_points(region, count=6):
    distance = ndimage.distance_transform_edt(region)
    yy, xx = np.indices(region.shape)
    points = []
    for _ in range(count):
        y, x = np.unravel_index(distance.argmax(), distance.shape)
        if distance[y, x] <= 0:
            break
        points.append([int(x), int(y)])
        distance[(xx - x) ** 2 + (yy - y) ** 2 < (min(region.shape) / 6) ** 2] = 0
    return points


def semantic_seed(probabilities, threshold):
    if probabilities.shape[0] != 19 or not 0 < threshold <= 1:
        raise ValueError("Expected 19 Cityscapes probability maps and a valid threshold")
    winner = probabilities.argmax(axis=0)
    return (winner == 1) & (probabilities[1] >= threshold)


def refine_with_sam(image, seed, probabilities, processor, model, torch):
    components, count = ndimage.label(seed)
    areas = np.bincount(components.ravel()); areas[0] = 0
    ids = sorted(range(1, count + 1), key=lambda i: -areas[i])[:3]
    output = seed.copy()
    detail = []
    image_input = processor(images=image, return_tensors="pt").to("cuda")
    embeddings = model.get_image_embeddings(image_input.pixel_values)
    confident_other = (probabilities.argmax(axis=0) != 1) & (probabilities.max(axis=0) >= .8)
    for component_id in ids:
        component = components == component_id
        if component.mean() < .005:
            continue
        positive = interior_points(component)
        ring = ndimage.binary_dilation(component, iterations=32) & confident_other
        negative = interior_points(ring, 6)
        points = positive + negative
        prompts = processor(original_sizes=image_input.original_sizes, input_points=[[points]],
                            input_labels=[[[1] * len(positive) + [0] * len(negative)]], return_tensors="pt").to("cuda")
        result = model(image_embeddings=embeddings, input_points=prompts.input_points,
                       input_labels=prompts.input_labels, multimask_output=True)
        masks = processor.post_process_masks(result.pred_masks.cpu(), image_input.original_sizes.cpu())[0].numpy().reshape(-1, image.height, image.width).astype(bool)
        quality = result.iou_scores.cpu().numpy().ravel()
        agreement = [float(np.count_nonzero(m & component) / max(1, np.count_nonzero(m | component))) for m in masks]
        eligible = [i for i in range(len(masks)) if quality[i] >= .7 and agreement[i] >= .5]
        selected = max(eligible, key=lambda i: agreement[i]) if eligible else None
        if selected is not None:
            output[component] = False
            output |= masks[selected] & ~confident_other
        detail.append({"positive_points": positive, "negative_points": negative, "sam_quality": quality.tolist(),
                       "agreement_with_semantic_component": agreement, "selected": selected})
    return output, detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sam-refine", action="store_true")
    parser.add_argument("--threshold", type=float, default=.65)
    args = parser.parse_args()
    baseline = json.loads((args.pilot / "manifest.json").read_text())
    selection = json.loads(args.selection.read_text())
    names = validate_selection(selection, baseline["images"], len(selection["images"]))
    if not 0 < len(names) <= 20 or not 0 < args.threshold <= 1:
        parser.error("This separate diagnostic is capped at 20 images; threshold must be in (0,1]")
    if selection.get("baseline_manifest_sha256") != sha256(args.pilot / "manifest.json"):
        parser.error("Selection does not match the reviewed baseline")
    source = Path(baseline["contract"]["source"])
    if args.output.exists():
        parser.error("Use a new output directory; diagnostics are never overwritten")
    if sha256(source / "labels.json") != baseline["contract"]["steering_labels_sha256"]:
        parser.error("Source steering labels changed")
    import torch
    from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation

    torch.set_num_threads(4)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    processor = SegformerImageProcessor.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
    model = SegformerForSemanticSegmentation.from_pretrained(MODEL, revision=REVISION, local_files_only=True).to("cuda").eval()
    if model.config.id2label[1] != "sidewalk" or model.config.id2label[0] != "road":
        raise ValueError("Unexpected semantic class mapping")
    sam_processor = sam = None
    if args.sam_refine:
        from transformers import Sam2Model, Sam2Processor
        sam_processor = Sam2Processor.from_pretrained(SAM, revision=SAM_REVISION, local_files_only=True)
        sam = Sam2Model.from_pretrained(SAM, revision=SAM_REVISION, local_files_only=True).to("cuda").eval()
    taxonomy = json.loads((args.pilot / "taxonomy.json").read_text())
    config = {"method": "SegFormer semantic cues + SAM 2 refinement" if sam is not None else "SegFormer semantic cues only",
              "model": MODEL, "revision": REVISION, "sidewalk_threshold": args.threshold,
              "resize": {"height": 1024, "width": 1024}, "sam": SAM if sam is not None else None,
              "sam_revision": SAM_REVISION if sam is not None else None,
              "scope": "Class 1 only. All non-selected pixels are ignore 255, NOT background or verified other classes.",
              "semantic_mapping": model.config.id2label, "processor": processor.to_dict(),
              "sources": ["https://huggingface.co/" + MODEL, "https://github.com/NVlabs/SegFormer/blob/master/LICENSE", "https://huggingface.co/docs/transformers/model_doc/sam2"],
              "license_note": "SegFormer model card refers to the NVIDIA research/evaluation-only license. No publication or commercial use is performed.",
              "refinement": {"min_component_fraction": .005, "max_components": 3, "positive_points": 6,
                             "negative_points": 6, "negative_ring_iterations": 32, "min_sam_quality": .7,
                             "min_semantic_agreement": .5, "confident_other_threshold": .8} if sam is not None else None}
    contract = {**{k:baseline["contract"][k] for k in ("source", "source_count", "source_names_sha256", "steering_labels_sha256")},
                "count": len(names), "config": config, "taxonomy": taxonomy, "selection_sha256": sha256(args.selection),
                "runner_file": Path(__file__).name, "runner_sha256": sha256(Path(__file__)),
                "helper_files_sha256": {"label_grounded_sam2.py": sha256(HERE / "label_grounded_sam2.py")},
                "packages": {p:importlib.metadata.version(p) for p in ("torch", "transformers", "numpy", "Pillow", "scipy")}}
    args.output.mkdir(parents=True)
    for folder in ("masks", "overlays", "records", "semantic_cues"):
        (args.output / folder).mkdir()
    write_json(args.output / "manifest.json", {"created_utc": utc_now(), "contract": contract, "images": names,
               "sampling": "purposive diagnostic subset of previously reviewed images", "purpose": "development comparison; not a held-out test or approved replacement labeling method"})
    for name, value in (("taxonomy.json", taxonomy), ("label_config.json", config), ("selection.json", selection)):
        write_json(args.output / name, value)
    (args.output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (args.output / "label_grounded_sam2.py").write_bytes((HERE / "label_grounded_sam2.py").read_bytes())
    records = []
    with torch.inference_mode():
        for index, name in enumerate(names, 1):
            started = time.monotonic()
            old = json.loads((args.pilot / "records" / (Path(name).stem + ".json")).read_text())
            verify_record(args.pilot, old, source)
            with Image.open(source / name) as raw:
                image = raw.convert("RGB")
            inputs = processor(images=image, return_tensors="pt").to("cuda")
            logits = model(**inputs).logits
            logits = torch.nn.functional.interpolate(logits, size=(image.height, image.width), mode="bilinear", align_corners=False)
            probabilities = logits.softmax(dim=1)[0].cpu().numpy()
            seed = semantic_seed(probabilities, args.threshold)
            pixels, detail = refine_with_sam(image, seed, probabilities, sam_processor, sam, torch) if sam is not None else (seed, [])
            mask = np.where(pixels, 1, 255).astype(np.uint8)
            if sha256(source / name) != old["source_sha256"]:
                raise ValueError("Source changed during inference")
            stem = Path(name).stem
            mask_name, overlay_name = f"masks/{stem}.png", f"overlays/{stem}.jpg"
            save_mask(args.output / mask_name, mask)
            save_overlay(args.output / overlay_name, image, mask, taxonomy)
            cue_name = f"semantic_cues/{stem}.png"
            save_mask(args.output / cue_name, probabilities.argmax(axis=0).astype(np.uint8))
            record = {"image": name, "source_sha256": old["source_sha256"], "size": [image.width, image.height],
                      "mask": mask_name, "overlay": overlay_name, "mask_sha256": sha256(args.output / mask_name),
                      "overlay_sha256": sha256(args.output / overlay_name),
                      "pixel_counts": {"1": int(pixels.sum()), "255": int((~pixels).sum())},
                      "labeled_fraction": float(pixels.mean()), "qa_flags": ["class_1_only_diagnostic; all_other_pixels_ignored"],
                      "review_status": "unreviewed", "created_utc": utc_now(), "seconds": round(time.monotonic() - started, 3),
                      "semantic_cue": cue_name, "semantic_cue_sha256": sha256(args.output / cue_name),
                      "sam_refinement": detail, "detections": [], "unmapped_detections": [], "detections_truncated": False}
            write_json(args.output / "records" / (stem + ".json"), record)
            records.append(record)
            print(f"[{index}/{len(names)}] {record['seconds']}s class1={pixels.mean():.1%} {name}", flush=True)
    if sha256(source / "labels.json") != contract["steering_labels_sha256"]:
        raise ValueError("Source steering labels changed during inference")
    write_json(args.output / "summary.json", {"completed": len(records), "reviewed": 0, "status": "class-1 diagnostic only; human review pending",
               "seconds": sum(r["seconds"] for r in records), "note": "Semantic probabilities and coverage are not correctness measurements. Other 11 classes were not labeled by this diagnostic."})


if __name__ == "__main__":
    main()
