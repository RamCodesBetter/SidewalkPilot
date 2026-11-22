#!/usr/bin/env python3
"""Run the official SAM 3.1 per-frame detector on the fixed ten-image audit."""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image

from audit_sam_implementations import make_panel
from compare_sam3_sidewalk import output_path, save_binary, union_instances, validate_inputs
from label_grounded_sam2 import sha256, utc_now, verify_record, write_json

COMMIT = "f1647e8d0c1d280991f4d1b7d974c2704537fe66"
REVISION = "daa63191845a41281374e725f4c9e51c7a824460"
CHECKPOINT_SHA256 = "0567debeec80ba4ac6369540c6c248025283cb3ff2b92827509e57e2b3541cb6"
SAM3_REVISION = "3c879f39826c281e95690f02c7821c4de09afae7"
SAM3_CHECKPOINT_SHA256 = "9999e2341ceef5e136daa386eecb55cb414446a00ac2b55eb2dfd2f7c3cf8c9e"


def detector_state(checkpoint):
    if "model" in checkpoint:
        checkpoint = checkpoint["model"]
    if not checkpoint or any(not k.startswith(("detector.", "tracker.")) for k in checkpoint):
        raise ValueError("Unexpected checkpoint root keys")
    detector = {k.removeprefix("detector."): v for k, v in checkpoint.items() if k.startswith("detector.")}
    if not detector:
        raise ValueError("Checkpoint has no detector tensors")
    return detector, sum(k.startswith("tracker.") for k in checkpoint)


def load_detector(source, checkpoint, torch, native_sam3_control=False):
    import sam3.model_builder as builder
    from sam3.model.sam3_multiplex_detector import Sam3MultiplexDetector
    from sam3.model.vl_combiner import SAM3VLBackboneTri

    # Same detector construction as the pinned official multiplex video builder.
    # Only the tracker/session layer is omitted for independent still images.
    if native_sam3_control:
        model = builder.build_sam3_image_model(device="cpu", load_from_HF=False, enable_inst_interactivity=False)
        # Retain the checkpoint's auxiliary neck for strict loading, without
        # constructing a tracker or using its outputs for image grounding.
        model.backbone.vision_backbone = builder._create_vision_backbone(enable_inst_interactivity=True)
    else:
        visual = builder._create_multiplex_tri_backbone(compile_mode=None, use_fa3=False, use_rope_real=False)
        text = builder._create_text_encoder(str(source / "sam3/assets/bpe_simple_vocab_16e6.txt.gz"))
        model = Sam3MultiplexDetector(
            num_feature_levels=1,
            backbone=SAM3VLBackboneTri(scalp=0, visual=visual, text=text),
            transformer=builder._create_sam3_transformer(use_fa3=False),
            segmentation_head=builder._create_segmentation_head(use_fa3=False),
            semantic_segmentation_head=None,
            input_geometry_encoder=builder._create_geometry_encoder(),
            use_early_fusion=True,
            use_dot_prod_scoring=True,
            dot_prod_scoring=builder._create_dot_product_scoring(),
            supervise_joint_box_scores=True,
            is_multiplex=True,
        )
    state, tracker_count = detector_state(torch.load(checkpoint, map_location="cpu", weights_only=True, mmap=True))
    # Do not silently initialize missing weights or load a SAM 3.0 fallback.
    model.load_state_dict(state, strict=True)
    report = {"strict": True, "detector_tensors": len(state), "tracker_tensors_not_used": tracker_count,
              "missing_detector_keys": [], "unexpected_detector_keys": []}
    return model.eval().to("cuda"), report


def hf_outputs(raw, joint_scores):
    from torchvision.ops import box_convert

    logits = raw["pred_logits"]
    if logits.ndim != 3 or logits.shape[-1] != 1:
        raise ValueError("Expected native detector B x Q x 1 logits")
    if type(joint_scores) is not bool:
        raise ValueError("Explicit joint-score policy required")
    # The multiplex detector applies presence once inside its logit head.
    # HF expects independent query logits; omit presence if it is already folded in.
    return SimpleNamespace(pred_logits=logits.squeeze(-1),
                           presence_logits=None if joint_scores else raw["presence_logit_dec"],
                           pred_masks=raw["pred_masks"],
                           pred_boxes=box_convert(raw["pred_boxes"], in_fmt="cxcywh", out_fmt="xyxy"))


def validate_prompt_settings(prompt, threshold):
    if not isinstance(prompt, str) or not prompt.strip() or prompt != prompt.strip():
        raise ValueError("Use a nonempty prompt without leading or trailing whitespace")
    if not 0 < threshold < 1:
        raise ValueError("Score threshold must be finite and strictly between zero and one")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("source-code", "runtime", "hf-runtime", "hf-snapshot", "checkpoint", "sam3-results", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--audit", type=Path)
    inputs.add_argument("--selection", type=Path, help="Frozen 200-image paired review selection")
    inputs.add_argument("--random-selection", type=Path, help="Frozen uniform random comparison selection (1-200 images)")
    inputs.add_argument("--review-package", type=Path, help="Reuse the source images in a frozen paired development pilot (at most 30)")
    parser.add_argument("--compact-output", action="store_true", help="Keep scores and masks, but omit dense raw mask logits")
    parser.add_argument("--approval-status", choices=("confirmed", "not-confirmed"), required=True)
    parser.add_argument("--native-sam3-control", action="store_true", help="Use the original SAM 3 checkpoint as a same-runtime control, not a SAM 3.1 result")
    parser.add_argument("--prompt", default="sidewalk")
    parser.add_argument("--score-threshold", type=float, default=.5)
    args = parser.parse_args()
    validate_prompt_settings(args.prompt, args.score_threshold)
    explicit_selection = bool(args.selection or args.random_selection or args.review_package)
    if args.review_package:
        from sam3_assisted_review import load_selection
        selection = load_selection(args.review_package)
        selection_path, baseline = args.review_package / "manifest.json", None
    elif args.random_selection:
        from prepare_random_comparison import validate_random_selection
        selection = validate_random_selection(args.random_selection)
        selection_path, baseline = args.random_selection, None
    elif args.selection:
        from prepare_paired_review import validate_selection
        selection = validate_selection(args.selection)
        selection_path, baseline = args.selection, None
    else:
        selection = validate_inputs(args.audit)
        selection_path, baseline = args.audit / "comparison/selection.json", Path(selection["baseline"])
    source = Path(selection["source"])
    out = output_path(args.output, [p for p in (source, baseline, args.audit, args.selection, args.random_selection, args.review_package,
                                              args.runtime, args.source_code, args.sam3_results) if p is not None])
    head = subprocess.check_output(["git", "-C", str(args.source_code), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(args.source_code), "status", "--porcelain", "--untracked-files=no"], text=True)
    expected_hash = SAM3_CHECKPOINT_SHA256 if args.native_sam3_control else CHECKPOINT_SHA256
    if head != COMMIT or dirty or sha256(args.checkpoint) != expected_hash:
        raise ValueError("Official source or checkpoint differs from the pinned diagnostic")
    old_config = json.loads((args.sam3_results / "config.json").read_text())
    for filename, digest in old_config["checkpoint_files"].items():
        if filename.endswith(".json") and sha256(args.hf_snapshot / filename) != digest:
            raise ValueError("SAM 3 processor configuration changed")
    sys.path[:0] = [str(args.runtime.resolve()), str(args.hf_runtime.resolve()), str(args.source_code.resolve())]
    import torch
    import transformers
    from transformers import Sam3Processor as HfProcessor
    from sam3.model.sam3_image_processor import Sam3Processor

    if transformers.__version__ != old_config["packages"]["transformers"] or not torch.cuda.is_available():
        raise RuntimeError("Expected the existing pinned SAM 3 preprocessing runtime and CUDA")
    torch.set_num_threads(4)
    model, load_report = load_detector(args.source_code, args.checkpoint, torch, args.native_sam3_control)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    processor = Sam3Processor(model, device="cuda", confidence_threshold=args.score_threshold)
    hf_processor = HfProcessor.from_pretrained(args.hf_snapshot, local_files_only=True)
    out.mkdir(parents=True, exist_ok=False)
    for directory in ("masks", "raw", "records", "panels"):
        (out / directory).mkdir()
    model_name = "facebook/sam3" if args.native_sam3_control else "facebook/sam3.1"
    config = {"created_utc": utc_now(), "model": model_name,
              "revision": SAM3_REVISION if args.native_sam3_control else REVISION,
              "checkpoint_sha256": expected_hash, "official_source_commit": COMMIT, "load_report": load_report,
              "prompt": args.prompt, "score_threshold": args.score_threshold, "mask_threshold": .5,
              "command": [sys.executable, *sys.argv],
              "weight_dtype": "float32", "autocast": "bfloat16", "tf32": False, "use_fa3": False, "use_rope_real": False,
              "selection_sha256": sha256(selection_path),
              "compact_output": args.compact_output,
              "runner_sha256": sha256(Path(__file__)),
              "official_file_sha256": {str(p.relative_to(args.source_code)): sha256(p) for p in (args.source_code / "sam3").rglob("*.py")},
              "preprocessing": "Exactly the pinned HF SAM 3 image processor used in v18; native official text encoder/tokenizer.",
              "postprocessing": "Native logits and center-format boxes adapted to the same HF SAM 3 postprocessor as v18, including sigmoid before mask resizing. Presence is applied exactly once according to supervise_joint_box_scores.",
              "supervise_joint_box_scores": model.supervise_joint_box_scores,
              "sam3_config_sha256": sha256(args.sam3_results / "config.json"),
              "packages": {p: importlib.metadata.version(p) for p in ("torch", "torchvision", "transformers", "numpy", "Pillow", "timm", "iopath", "einops")},
              "native_sam3_control": args.native_sam3_control,
              "scope": "Official per-frame detector only; no temporal propagation, tracker, video session, or multiplex speed benchmark. Every image starts fresh.",
              "comparison_limit": "Native official detector in bfloat16 autocast. Earlier HF SAM 3 used float32, prompt sidewalk and score threshold 0.5; runtime, prompt and threshold must be checked before comparing results.",
              "approval_status_reported_by_user": args.approval_status,
              "sources": ["https://huggingface.co/" + model_name, "https://github.com/facebookresearch/sam3/tree/" + COMMIT]}
    write_json(out / "config.json", config)
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    rows = []
    with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        for number, frame in enumerate(selection["frames"], 1):
            identity = frame if explicit_selection else frame["record"]
            if explicit_selection:
                if sha256(source / frame["image"]) != identity["source_sha256"]:
                    raise ValueError("Source image changed")
            else:
                verify_record(baseline, frame["record"], source)
            with Image.open(source / frame["image"]) as handle:
                image = handle.convert("RGB")
            inputs = hf_processor(images=image, text=args.prompt, return_tensors="pt")
            pixels = inputs.pixel_values.to("cuda")
            torch.cuda.synchronize()
            start = time.perf_counter()
            backbone = model.backbone.forward_image(pixels) if args.native_sam3_control else model.backbone.forward_image(
                pixels, need_interactive_out=False, need_propagation_out=False)
            state = {"original_height": image.height, "original_width": image.width, "backbone_out": backbone}
            state["backbone_out"].update(model.backbone.forward_text([args.prompt], device="cuda"))
            state["geometric_prompt"] = model._get_dummy_prompt()
            raw = model.forward_grounding(backbone_out=state["backbone_out"], find_input=processor.find_stage,
                                           geometric_prompt=state["geometric_prompt"], find_target=None)
            torch.cuda.synchronize()
            seconds = time.perf_counter() - start
            keys = ("pred_masks", "pred_boxes", "pred_logits", "presence_logit_dec")
            if not all(torch.isfinite(raw[k]).all().item() for k in keys):
                raise ValueError("Non-finite detector output")
            raw_arrays = {k: raw[k].detach().float().cpu().numpy() for k in keys
                          if not args.compact_output or k != "pred_masks"}
            result = hf_processor.post_process_instance_segmentation(
                hf_outputs(raw, joint_scores=model.supervise_joint_box_scores),
                threshold=args.score_threshold, mask_threshold=.5, target_sizes=[(image.height, image.width)],
            )[0]
            masks = result["masks"].cpu().numpy()
            union = union_instances(masks, (image.height, image.width))
            raw_path = f"raw/{number:02d}.npz"
            np.savez_compressed(out / raw_path, **raw_arrays)
            instances = [save_binary(out, f"{number:02d}-instance-{i:03d}", mask) for i, mask in enumerate(masks)]
            row = {"image": frame["image"], "prior_index": frame.get("prior_index"), "size": identity["size"],
                   "source_sha256": identity["source_sha256"], "model_forward_seconds": seconds,
                   "pixel_values_sha256": hashlib.sha256(inputs.pixel_values.numpy().tobytes()).hexdigest(),
                   "instance_scores": result["scores"].cpu().tolist(), "instances": instances,
                   "instance_union": save_binary(out, f"{number:02d}-instance-union", union),
                   "raw": {"path": raw_path, "sha256": sha256(out / raw_path)}, "review_status": "unreviewed"}
            views = [("SOURCE", None)]
            if args.audit:
                old = json.loads((args.sam3_results / "records" / f"{number:02d}.json").read_text())
                old_path = args.sam3_results / old["instance_union"]["path"]
                if old["image"] != frame["image"] or sha256(old_path) != old["instance_union"]["sha256"]:
                    raise ValueError("SAM 3 comparison output changed")
                with Image.open(old_path) as handle:
                    prior = np.asarray(handle) == 1
                row["sam3_mask_different_pixels"] = int(np.count_nonzero(union != prior))
                views.append(("SAM 3 / HF baseline, sidewalk / 0.5", prior))
            views.append((f'{model_name} / {args.prompt} / {args.score_threshold}', union))
            make_panel(out / "panels" / f"{number:02d}.jpg", image,
                       views,
                       f'{number:02d}: {frame["image"]} / NOT A VIDEO TRACKING TEST')
            write_json(out / "records" / f"{number:02d}.json", row)
            rows.append(row)
            print(json.dumps({"completed": number, "instances": len(instances), "sidewalk_pixels": int(union.sum()),
                              "different_from_sam3": row.get("sam3_mask_different_pixels")}), flush=True)
    if args.review_package:
        load_selection(args.review_package)
    elif args.random_selection:
        validate_random_selection(args.random_selection)
    elif args.selection:
        validate_selection(args.selection)
    else:
        validate_inputs(args.audit)
    write_json(out / "summary.json", {"count": len(rows), "images": rows, "note": "Unreviewed still-image detector proposals; no temporal SAM 3.1 test."})


if __name__ == "__main__":
    main()
