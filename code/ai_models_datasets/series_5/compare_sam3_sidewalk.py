#!/usr/bin/env python3
"""Compare SAM 3 text-only proposals on the fixed ten-frame SAM 2 audit set."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image

from audit_sam_implementations import INDICES, agreement, make_panel
from label_grounded_sam2 import sha256, utc_now, verify_record, write_json

MODEL = "facebook/sam3"
REVISION = "3c879f39826c281e95690f02c7821c4de09afae7"
TRANSFORMERS_VERSION = "5.20.2"
PROMPT = "sidewalk"
SCORE_THRESHOLD = .5
MASK_THRESHOLD = .5


def binary_mask(mask, shape):
    mask = np.asarray(mask)
    if mask.ndim != 2 or mask.shape != tuple(shape) or not np.isin(mask, [0, 1]).all():
        raise ValueError("Expected a binary mask at original image dimensions")
    return mask.astype(bool)


def union_instances(masks, shape):
    masks = np.asarray(masks)
    if masks.ndim != 3:
        raise ValueError("Expected instance masks shaped N x height x width")
    # Transformers leaves an empty instance batch at the model's native resolution.
    if masks.shape[0] == 0:
        return np.zeros(shape, dtype=bool)
    if masks.shape[1:] != tuple(shape):
        raise ValueError("Expected instance masks at original image dimensions")
    if not np.isin(masks, [0, 1]).all():
        raise ValueError("Instance masks must be binary")
    return np.any(masks.astype(bool), axis=0)


def output_path(output, protected):
    output = output.resolve()
    if output.exists():
        raise ValueError("Use a new output directory; never replace prior results")
    for item in protected:
        item = item.resolve()
        if output == item or output in item.parents or item in output.parents:
            raise ValueError("Output must be separate from source and baseline trees")
    return output


def validate_inputs(audit):
    selection_path = audit / "comparison" / "selection.json"
    selection = json.loads(selection_path.read_text())
    frames = selection["frames"]
    if (tuple(f["prior_index"] for f in frames) != INDICES
            or selection["images"] != [f["image"] for f in frames]
            or len(set(selection["images"])) != 10):
        raise ValueError("Expected the unchanged, ordered ten-frame audit selection")
    source, baseline = Path(selection["source"]), Path(selection["baseline"])
    if sha256(baseline / "manifest.json") != selection["baseline_manifest_sha256"]:
        raise ValueError("Baseline manifest changed")
    automatic = audit / "automatic-stages"
    config = json.loads((automatic / "config.json").read_text())
    if config["selection_sha256"] != sha256(selection_path):
        raise ValueError("Automatic SAM 2 stage trace belongs to another selection")
    for number, frame in enumerate(frames, 1):
        name = frame["image"]
        if Path(name).name != name:
            raise ValueError("Source image must be a plain filename")
        verify_record(baseline, frame["record"], source)
        record = json.loads((automatic / "records" / f"{number:02d}.json").read_text())
        if record["image"] != name or record["source_sha256"] != frame["record"]["source_sha256"]:
            raise ValueError("Automatic SAM 2 record does not match source")
        shape = tuple(reversed(frame["record"]["size"]))
        raw_union = np.zeros(shape, dtype=bool)
        for detection in record["detections"]["detections"]:
            path = automatic / detection["raw_sam_mask"]
            if sha256(path) != detection["raw_sam_mask_sha256"]:
                raise ValueError("Automatic SAM 2 candidate changed")
            if detection["class_id"] == 1:
                with Image.open(path) as handle:
                    raw_union |= np.asarray(handle) == 1
        with Image.open(automatic / "masks" / f"{number:02d}-raw-sidewalk-union.png") as handle:
            if not np.array_equal(raw_union, np.asarray(handle) == 1):
                raise ValueError("Automatic SAM 2 raw union differs from its candidates")
    return selection


def save_binary(out, name, mask):
    relative = f"masks/{name}.png"
    Image.fromarray(np.where(mask, 1, 255).astype(np.uint8)).save(out / relative)
    return {"path": relative, "sha256": sha256(out / relative),
            "class_1_pixels": int(mask.sum()), "review_status": "unreviewed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approval-status", choices=("not-confirmed", "confirmed"), required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    selection = validate_inputs(args.audit)
    source, baseline = Path(selection["source"]), Path(selection["baseline"])
    out = output_path(args.output, [source, baseline, args.audit, args.runtime])
    if args.validate_only:
        print(json.dumps({"validated_images": 10, "prompt": PROMPT, "output": str(out),
                          "inference_performed": False, "approval_status": args.approval_status}))
        return

    # New Transformers dependencies live here; the existing CUDA Torch is reused.
    sys.path.insert(0, str(args.runtime.resolve()))
    import torch
    import transformers
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import GatedRepoError
    from transformers import Sam3Model, Sam3Processor

    if transformers.__version__ != TRANSFORMERS_VERSION:
        raise RuntimeError("Unexpected Transformers version; use the pinned audit runtime")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required for this diagnostic")
    try:
        snapshot = Path(snapshot_download(
            MODEL, revision=REVISION,
            allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "LICENSE*"],
        ))
    except GatedRepoError:
        parser.exit(2, "Official SAM 3 checkpoint access is not approved for the current HF login. No inference performed.\n")
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    processor = Sam3Processor.from_pretrained(snapshot, local_files_only=True)
    model = Sam3Model.from_pretrained(snapshot, local_files_only=True, dtype=torch.float32,
                                     attn_implementation="sdpa").eval().to("cuda")
    out.mkdir(parents=True, exist_ok=False)
    for directory in ("masks", "raw", "panels", "records"):
        (out / directory).mkdir()
    config = {
        "created_utc": utc_now(), "model": MODEL, "revision": REVISION,
        "prompt": PROMPT, "score_threshold": SCORE_THRESHOLD, "mask_threshold": MASK_THRESHOLD,
        "dtype": "float32", "autocast": False, "attention": "sdpa", "tf32": False,
        "approval_status_reported_by_user": args.approval_status,
        "selection_sha256": sha256(args.audit / "comparison" / "selection.json"),
        "runner_sha256": sha256(Path(__file__)),
        "helpers_sha256": {p: sha256(Path(__file__).with_name(p)) for p in
                           ("audit_sam_implementations.py", "label_grounded_sam2.py")},
        "checkpoint_files": {p.name: sha256(p) for p in snapshot.iterdir() if p.is_file()},
        "packages": {p: importlib.metadata.version(p) for p in
                     ("torch", "transformers", "huggingface-hub", "tokenizers", "numpy", "Pillow")},
        "primary_output": "Union of instance masks passing the fixed score threshold",
        "secondary_output": "Semantic head, retained separately without presence-score gating",
        "scope": "Class-1 proposals only, other pixels ignore 255. Fixed purposive development set; not an accuracy benchmark.",
        "comparison_limit": "Text-only SAM 3 versus prior Grounded SAM 2 and assisted-point SAM 2 workflows; not matched prompts or equal annotation effort.",
        "sources": ["https://huggingface.co/facebook/sam3", "https://huggingface.co/docs/transformers/model_doc/sam3"],
    }
    write_json(out / "config.json", config)
    write_json(out / "selection.json", selection)
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    rows = []
    with torch.inference_mode():
        for number, frame in enumerate(selection["frames"], 1):
            name = frame["image"]
            verify_record(baseline, frame["record"], source)
            with Image.open(source / name) as handle:
                image = handle.convert("RGB")
            shape = (image.height, image.width)
            inputs = processor(images=image, text=PROMPT, return_tensors="pt").to("cuda")
            torch.cuda.synchronize()
            started = time.perf_counter()
            outputs = model(**inputs)
            torch.cuda.synchronize()
            seconds = time.perf_counter() - started
            result = processor.post_process_instance_segmentation(
                outputs, threshold=SCORE_THRESHOLD, mask_threshold=MASK_THRESHOLD, target_sizes=[shape],
            )[0]
            masks = result["masks"].detach().cpu().numpy()
            union = union_instances(masks, shape)
            semantic = processor.post_process_semantic_segmentation(
                outputs, target_sizes=[shape], threshold=MASK_THRESHOLD,
            )[0].detach().cpu().numpy()
            semantic = binary_mask(semantic, shape)
            raw = {key: getattr(outputs, key).detach().float().cpu().numpy()
                   for key in ("pred_masks", "pred_boxes", "pred_logits", "presence_logits", "semantic_seg")}
            if not all(np.isfinite(value).all() for value in raw.values()):
                raise ValueError("Non-finite model output")
            raw_path = f"raw/{number:02d}.npz"
            np.savez_compressed(out / raw_path, **raw)
            with Image.open(baseline / frame["record"]["mask"]) as handle:
                reviewed = np.asarray(handle) == 1
            automatic = args.audit / "automatic-stages" / "masks"
            with Image.open(automatic / f"{number:02d}-raw-sidewalk-union.png") as handle:
                sam2_raw = np.asarray(handle) == 1
            with Image.open(automatic / f"{number:02d}-composed.png") as handle:
                sam2_final = np.asarray(handle) == 1
            instances = [save_binary(out, f"{number:02d}-instance-{i:03d}", binary_mask(mask, shape))
                         for i, mask in enumerate(masks)]
            row = {"image": name, "prior_index": frame["prior_index"], "source_sha256": frame["record"]["source_sha256"],
                   "size": [image.width, image.height], "model_forward_seconds": seconds,
                   "instance_scores": result["scores"].detach().cpu().tolist(),
                   "instance_boxes": result["boxes"].detach().cpu().tolist(), "instances": instances,
                   "instance_union": save_binary(out, f"{number:02d}-instance-union", union),
                   "semantic": save_binary(out, f"{number:02d}-semantic", semantic),
                   "raw": {"path": raw_path, "sha256": sha256(out / raw_path)},
                   "agreement_not_accuracy": {"union_vs_assisted_sam2": agreement(union, reviewed),
                                              "union_vs_automatic_sam2_raw": agreement(union, sam2_raw),
                                              "union_vs_semantic": agreement(union, semantic)},
                   "review_status": "unreviewed"}
            views = [("SOURCE", None), ("ASSISTED SAM 2 / previous: " + frame["review"], reviewed),
                     ("AUTOMATIC SAM 2 / raw sidewalk union", sam2_raw),
                     ("AUTOMATIC SAM 2 / after class merging", sam2_final),
                     ("SAM 3 / instance union / UNREVIEWED", union),
                     ("SAM 3 / semantic head / UNREVIEWED", semantic)]
            make_panel(out / "panels" / f"{number:02d}.jpg", image, views,
                       f'{number:02d} / prior diagnostic {frame["prior_index"]}: {name}')
            write_json(out / "records" / f"{number:02d}.json", row)
            rows.append(row)
            print(json.dumps({"completed": number, "instances": len(instances),
                              "union_pixels": int(union.sum()), "semantic_pixels": int(semantic.sum())}), flush=True)
    validate_inputs(args.audit)
    write_json(out / "summary.json", {"count": len(rows), "images": rows,
               "note": "Unreviewed proposals; no accuracy, acceptance rate, or winning model established."})
    print(str(out), flush=True)


if __name__ == "__main__":
    main()
