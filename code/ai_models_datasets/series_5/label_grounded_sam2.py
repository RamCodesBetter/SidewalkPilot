#!/usr/bin/env python3
"""Resumable, review-gated Grounding DINO + SAM 2.1 pilot on existing images."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import random
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parent / "series_3_and_4" / "sidewalkpilot_dataset"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def validate_taxonomy(taxonomy):
    classes = taxonomy["classes"]
    if [c["id"] for c in classes] != list(range(12)) or taxonomy["ignore_id"] != 255:
        raise ValueError("Expected class IDs 0-11 and ignore ID 255")
    grouped = [c for group in taxonomy["prompt_groups"] for c in group]
    if sorted(grouped) != list(range(12)):
        raise ValueError("Every class must appear in exactly one prompt group")
    prompts = [p for c in classes for p in c["prompts"]]
    if len(prompts) != len(set(prompts)):
        raise ValueError("Prompts must map to one class")


def select_pilot(names, count, seed):
    """Proportional run quotas, one seeded random image per temporal bin."""
    names = sorted(names)
    if not 0 < count <= len(names):
        raise ValueError("Pilot count must be between 1 and source image count")
    groups = defaultdict(list)
    for name in names:
        groups[name.split("__", 1)[0]].append(name)
    quotas = {run: count * len(items) // len(names) for run, items in groups.items()}
    remaining = count - sum(quotas.values())
    order = sorted(groups, key=lambda r: (-(count * len(groups[r]) % len(names)), r))
    for run in order[:remaining]:
        quotas[run] += 1
    rng = random.Random(seed)
    selected = []
    for run, items in sorted(groups.items()):
        quota = quotas[run]
        for i in range(quota):
            selected.append(items[rng.randrange(i * len(items) // quota, (i + 1) * len(items) // quota)])
    rng.shuffle(selected)
    return selected


def validate_selection(selection, names, count):
    selected = selection.get("images")
    if (not isinstance(selected, list) or len(selected) != count
            or any(not isinstance(n, str) for n in selected)
            or len(set(selected)) != len(selected) or not set(selected).issubset(names)):
        raise ValueError("Selection must contain exactly count unique source image names")
    return selected


def map_phrase(phrase, classes):
    phrase = " ".join(re.findall(r"[a-z0-9]+", phrase.lower()))
    found = set()
    for cls in classes:
        for prompt in cls["prompts"]:
            if re.search(r"\b" + re.escape(prompt) + r"\b", phrase):
                found.add(cls["id"])
    return next(iter(found)) if len(found) == 1 else None


def build_caption(classes):
    caption, spans = "", []
    for cls in classes:
        for prompt in cls["prompts"]:
            start = len(caption)
            caption += prompt + ". "
            spans.append((cls["id"], prompt, start, start + len(prompt)))
    return caption.strip(), spans


def score_prompt_spans(probabilities, offsets, spans):
    """Aggregate each exact prompt's wordpiece tokens, without decoding class names."""
    scores, class_ids, phrases = [], [], []
    for cid, phrase, start, end in spans:
        tokens = [i for i, (a, b) in enumerate(offsets) if a < end and b > start and b > a]
        if not tokens:
            raise ValueError(f"Prompt has no token span: {phrase}")
        scores.append(probabilities[:, tokens].mean(axis=1))
        class_ids.append(cid)
        phrases.append(phrase)
    return np.stack(scores, axis=1), class_ids, phrases


def compose_mask(candidates, shape, taxonomy, margin, overlap_mode="confidence"):
    scores = np.full((12, *shape), -1.0, dtype=np.float32)
    for candidate in candidates:
        cid, pixels, score = candidate
        scores[cid][pixels] = np.maximum(scores[cid][pixels], score)
    output = np.full(shape, 255, dtype=np.uint8)
    groups = [list(range(12))]
    if overlap_mode == "legacy_layers":
        groups = [[c["id"] for c in taxonomy["classes"] if c["layer"] == layer]
                  for layer in sorted({c["layer"] for c in taxonomy["classes"]})]
    elif overlap_mode != "confidence":
        raise ValueError("Unsupported overlap mode")
    for ids in groups:
        subset = scores[ids]
        winner = subset.argmax(axis=0)
        best = subset.max(axis=0)
        covered = best >= 0
        local = np.asarray(ids, dtype=np.uint8)[winner]
        if len(ids) > 1:
            runner_up = np.partition(subset, -2, axis=0)[-2]
            local[(runner_up >= 0) & (best - runner_up <= margin)] = 255
        output[covered] = local[covered]
    return output


def save_mask(path, mask):
    temporary = path.with_suffix(".tmp")
    Image.fromarray(mask).save(temporary, format="PNG")
    temporary.replace(path)


def save_overlay(path, image, mask, taxonomy, caption="AUTOMATIC MASK - UNREVIEWED; hatching = ignore"):
    colors = np.full((256, 3), 232, dtype=np.uint8)
    for cls in taxonomy["classes"]:
        colors[cls["id"]] = cls["color"]
    raw = np.asarray(image, dtype=np.uint8)
    blended = (0.55 * raw + 0.45 * colors[mask]).astype(np.uint8)
    blended[mask == 255] = raw[mask == 255]
    # Sparse white hatching makes ignored pixels visible without hiding the scene.
    yy, xx = np.indices(mask.shape)
    hatch = (mask == 255) & ((xx + yy) % 24 < 2)
    blended[hatch] = (0.5 * raw[hatch] + 127).astype(np.uint8)
    panel = Image.new("RGB", (image.width * 2, image.height + 32), "white")
    panel.paste(image, (0, 32))
    panel.paste(Image.fromarray(blended), (image.width, 32))
    draw = ImageDraw.Draw(panel)
    draw.text((12, 8), "SOURCE", fill="black")
    draw.text((image.width + 12, 8), caption, fill="black")
    temporary = path.with_suffix(".tmp")
    panel.save(temporary, format="JPEG", quality=90)
    temporary.replace(path)


class GroundedSam2:
    def __init__(self, config, taxonomy):
        import torch
        from transformers import GroundingDinoForObjectDetection, GroundingDinoProcessor, Sam2Model, Sam2Processor

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required; refusing an accidental CPU labeling job")
        torch.set_num_threads(4)
        self.torch, self.config, self.taxonomy = torch, config, taxonomy
        common = {"local_files_only": True}
        self.detector_processor = GroundingDinoProcessor.from_pretrained(
            config["detector"], revision=config["detector_revision"], **common)
        self.detector = GroundingDinoForObjectDetection.from_pretrained(
            config["detector"], revision=config["detector_revision"], **common).to("cuda").eval()
        self.sam_processor = Sam2Processor.from_pretrained(
            config["segmenter"], revision=config["segmenter_revision"], **common)
        self.sam = Sam2Model.from_pretrained(
            config["segmenter"], revision=config["segmenter_revision"], **common).to("cuda").eval()

    def label(self, image):
        from torchvision.ops import batched_nms

        torch, cfg = self.torch, self.config
        detections, rejected = [], []
        with torch.inference_mode():
            for group in cfg.get("prompt_groups", self.taxonomy["prompt_groups"]):
                classes = [self.taxonomy["classes"][cid] for cid in group]
                classes = [{**c, "prompts": cfg.get("prompt_overrides", {}).get(str(c["id"]), c["prompts"])} for c in classes]
                caption, spans = build_caption(classes)
                inputs = self.detector_processor(images=image, text=caption, return_tensors="pt").to("cuda")
                if inputs["input_ids"].shape[-1] > 256:
                    raise ValueError("Grounding caption exceeds the detector token limit")
                raw = self.detector(**inputs)
                if cfg.get("class_assignment") == "prompt_token_scores":
                    from torchvision.ops import box_convert

                    tokens = self.detector_processor.tokenizer(caption, return_offsets_mapping=True)
                    if tokens["input_ids"] != inputs.input_ids[0].tolist():
                        raise ValueError("Caption tokenization differs from image processor input")
                    scores, class_ids, phrases = score_prompt_spans(
                        raw.logits[0].sigmoid().cpu().numpy(), tokens["offset_mapping"], spans)
                    boxes = box_convert(raw.pred_boxes[0], in_fmt="cxcywh", out_fmt="xyxy")
                    boxes = (boxes * torch.tensor([image.width, image.height] * 2, device="cuda")).cpu().tolist()
                    # Keep per-class alternatives so mask composition can mark close conflicts.
                    for cid in group:
                        columns = [i for i, value in enumerate(class_ids) if value == cid]
                        best = scores[:, columns].argmax(axis=1)
                        for row, column in enumerate(best):
                            column = columns[column]
                            score = float(scores[row, column])
                            if score <= cfg["box_threshold"]:
                                continue
                            box = [max(0, min(value, image.width if i % 2 == 0 else image.height)) for i, value in enumerate(boxes[row])]
                            if box[2] > box[0] and box[3] > box[1]:
                                detections.append({"class_id": cid, "box": box, "detector_score": score,
                                                   "phrase": phrases[column], "assignment": "mean prompt-token probability"})
                    continue
                result = self.detector_processor.post_process_grounded_object_detection(
                    raw, inputs.input_ids,
                    threshold=cfg["box_threshold"], text_threshold=cfg["text_threshold"],
                    target_sizes=[(image.height, image.width)])[0]
                for box, score, phrase in zip(result["boxes"].cpu().tolist(), result["scores"].cpu().tolist(), result["text_labels"]):
                    cid = map_phrase(phrase, classes)
                    box = [max(0, min(value, image.width if i % 2 == 0 else image.height)) for i, value in enumerate(box)]
                    if cid is None or box[2] <= box[0] or box[3] <= box[1]:
                        rejected.append({"phrase": phrase, "score": score, "box": box})
                    else:
                        detections.append({"class_id": cid, "box": box, "detector_score": score, "phrase": phrase})
            if detections:
                keep = batched_nms(torch.tensor([d["box"] for d in detections]),
                                   torch.tensor([d["detector_score"] for d in detections]),
                                   torch.tensor([d["class_id"] for d in detections]), cfg["box_nms_iou"])
                detections = [detections[i] for i in keep.tolist()]
            truncated = len(detections) > cfg["max_detections"]
            detections = detections[:cfg["max_detections"]]
            candidates = []
            if detections:
                sam_image = self.sam_processor(images=image, return_tensors="pt").to("cuda")
                embeddings = self.sam.get_image_embeddings(sam_image.pixel_values)
                batch_size = cfg["sam_box_batch"]
                for start in range(0, len(detections), batch_size):
                    batch = detections[start:start + batch_size]
                    prompts = self.sam_processor(original_sizes=sam_image.original_sizes,
                                                 input_boxes=[[d["box"] for d in batch]], return_tensors="pt").to("cuda")
                    result = self.sam(image_embeddings=embeddings, input_boxes=prompts.input_boxes, multimask_output=False)
                    masks = self.sam_processor.post_process_masks(result.pred_masks.cpu(), sam_image.original_sizes.cpu())[0]
                    quality = result.iou_scores.detach().cpu().reshape(-1).tolist()
                    masks = masks.numpy().reshape(len(batch), image.height, image.width)
                    for detection, pixels, q in zip(batch, masks, quality):
                        detection["sam_quality"] = q
                        detection["accepted"] = bool(np.isfinite(q) and q >= cfg["sam_quality_threshold"] and pixels.any())
                        if detection["accepted"]:
                            candidates.append((detection["class_id"], pixels.astype(bool), detection["detector_score"] * min(q, 1.0)))
            if "diagnostic_class_ids" in cfg:
                candidates = [c for c in candidates if c[0] in cfg["diagnostic_class_ids"]]
            mask = compose_mask(candidates, (image.height, image.width), self.taxonomy,
                                cfg["class_conflict_margin"], cfg.get("overlap_mode", "legacy_layers"))
        return mask, {"detections": detections, "unmapped_detections": rejected, "detections_truncated": truncated}


def verify_record(output, record, source):
    for key in ("mask", "overlay"):
        path = output / record[key]
        if not path.is_file() or sha256(path) != record[key + "_sha256"]:
            raise ValueError(f"Output changed or missing: {path}; use a new output directory")
    if sha256(source / record["image"]) != record["source_sha256"]:
        raise ValueError(f"Source changed: {record['image']}")


def run(args):
    taxonomy = json.loads(args.taxonomy.read_text())
    config = json.loads(args.config.read_text())
    validate_taxonomy(taxonomy)
    source, output = args.source.resolve(), args.output.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Output must be separate from the source image tree")
    if not 0 < args.count <= 200:
        raise ValueError("This pilot runner is capped at 200. Review before a full-dataset run.")
    names = sorted(p.name for p in source.glob("*.jpg"))
    labels_path = source / "labels.json"
    if not names or set(names) != set(json.loads(labels_path.read_text())):
        raise ValueError("Source JPEG names and steering label keys must match exactly")
    names_digest = digest_json(names)
    selection_path = getattr(args, "selection", None)
    selection = json.loads(selection_path.read_text()) if selection_path else None
    selected = validate_selection(selection, names, args.count) if selection is not None else select_pilot(names, args.count, args.seed)
    contract = {"source": str(source), "source_count": len(names), "source_names_sha256": names_digest,
                "steering_labels_sha256": sha256(labels_path), "count": args.count, "seed": args.seed,
                "taxonomy": taxonomy, "config": config, "runner_sha256": sha256(Path(__file__)),
                "packages": {p: importlib.metadata.version(p) for p in ("torch", "torchvision", "transformers", "Pillow", "numpy")}}
    if selection is not None:
        contract["selection_sha256"] = sha256(selection_path)
    output.mkdir(parents=True, exist_ok=True)
    with (output / ".label.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest_path = output / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if manifest["contract"] != contract:
                raise ValueError("Run contract changed. Use a new output directory; existing labels were not touched.")
        else:
            manifest = {"created_utc": utc_now(), "contract": contract, "images": selected,
                        "sampling": "explicit diagnostic selection; not an independent sample" if selection is not None else "proportional run quotas; seeded random frame per temporal bin; shuffled review order",
                        "sample_runs": dict(Counter(n.split("__", 1)[0] for n in selected)),
                        "purpose": "development pilot; not a held-out segmentation accuracy test"}
            if "diagnostic_class_ids" in config:
                manifest["annotation_scope"] = {"kind": "class", "class_ids": config["diagnostic_class_ids"], "other_pixels": "ignore"}
            write_json(manifest_path, manifest)
            write_json(output / "taxonomy.json", taxonomy)
            write_json(output / "label_config.json", config)
            (output / "label_grounded_sam2.py").write_bytes(Path(__file__).read_bytes())
            if selection is not None:
                write_json(output / "selection.json", selection)
        for folder in ("masks", "overlays", "records"):
            (output / folder).mkdir(exist_ok=True)
        print(json.dumps({"output": str(output), "sample_runs": manifest["sample_runs"]}), flush=True)
        if args.prepare_only:
            return
        labeler = None
        records = []
        for index, name in enumerate(manifest["images"]):
            stem = Path(name).stem
            record_path = output / "records" / (stem + ".json")
            if record_path.exists():
                record = json.loads(record_path.read_text())
                verify_record(output, record, source)
                records.append(record)
                print(f"[{index + 1}/{args.count}] verified existing {name}", flush=True)
                continue
            if labeler is None:
                print("Loading pinned Grounding DINO and SAM 2.1 weights on CUDA", flush=True)
                labeler = GroundedSam2(config, taxonomy)
            started = time.monotonic()
            before_hash = sha256(source / name)
            with Image.open(source / name) as raw:
                image = raw.convert("RGB")
            mask, detail = labeler.label(image)
            if sha256(source / name) != before_hash:
                raise RuntimeError(f"Source modified during processing: {name}")
            mask_name, overlay_name = f"masks/{stem}.png", f"overlays/{stem}.jpg"
            save_mask(output / mask_name, mask)
            save_overlay(output / overlay_name, image, mask, taxonomy)
            ids, counts = np.unique(mask, return_counts=True)
            coverage = float(np.mean(mask != 255))
            flags = []
            if coverage < 0.60:
                flags.append("low_label_coverage")
            if not np.any(mask == 1):
                flags.append("no_sidewalk_label; may be valid off-sidewalk image or detector failure")
            if detail["detections_truncated"]:
                flags.append("detection_limit_reached")
            record = {"image": name, "source_sha256": before_hash, "size": [image.width, image.height],
                      "mask": mask_name, "overlay": overlay_name, "mask_sha256": sha256(output / mask_name),
                      "overlay_sha256": sha256(output / overlay_name), "pixel_counts": dict(zip(map(str, ids), map(int, counts))),
                      "labeled_fraction": coverage, "qa_flags": flags, "review_status": "unreviewed",
                      "created_utc": utc_now(), "seconds": round(time.monotonic() - started, 3), **detail}
            write_json(record_path, record)
            records.append(record)
            write_json(output / "progress.json", {"completed": len(records), "total": args.count, "last_image": name, "updated_utc": utc_now()})
            print(f"[{index + 1}/{args.count}] {record['seconds']:.1f}s coverage={coverage:.1%} {name}", flush=True)
        if sha256(labels_path) != contract["steering_labels_sha256"]:
            raise RuntimeError("Source steering labels changed during the run")
        totals = Counter()
        support = Counter()
        for record in records:
            totals.update(record["pixel_counts"])
            support.update(record["pixel_counts"].keys())
        write_json(output / "summary.json", {"completed": len(records), "reviewed": 0,
                   "status": "automatic pilot complete; human review pending; full dataset not started",
                   "finished_utc": utc_now(), "pixel_counts": dict(totals), "image_support": dict(support),
                   "mean_labeled_fraction": float(np.mean([r["labeled_fraction"] for r in records])),
                   "seconds": sum(r["seconds"] for r in records),
                   "note": "Detection and SAM scores are model outputs, not calibrated correctness probabilities. Coverage is not accuracy."})
        print(f"Complete: {len(records)} unreviewed masks in {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, required=True, help="Separate versioned directory for this pilot")
    parser.add_argument("--taxonomy", type=Path, default=HERE / "taxonomy.json")
    parser.add_argument("--config", type=Path, required=True, help="Explicit labeling recipe; none is promoted for full-dataset use yet")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261025)
    parser.add_argument("--selection", type=Path, help="Explicit diagnostic JSON image list; must match --count")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        run(args)
    except (KeyboardInterrupt, Exception) as exc:
        print(f"Stopped: {type(exc).__name__}: {exc}. Completed records remain resumable with the same command.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
