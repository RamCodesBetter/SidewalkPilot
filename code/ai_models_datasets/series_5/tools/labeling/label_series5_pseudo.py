#!/usr/bin/env python3
"""Freeze a training-only sample, then resumably label it with pinned native SAM 3."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from pseudo_mask_filter import POLICY, filter_masks
from prepare_reviewed_dataset import read_json, safe_file

HERE = _workspace.TOOLS
ROOT = Path.home() / "sidewalkpilot-labels"


def prepare(args):
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Use a new selection file separate from source")
    base, split = read_json(args.dataset / "manifest.json"), read_json(args.split)
    if split["manifest_sha256"] != sha256(args.dataset / "manifest.json"):
        raise ValueError("Baseline split identity differs")
    excluded_names = {r["source_name"] for r in base["records"]}
    excluded_hashes = {r["source_sha256"] for r in base["records"]}
    groups = {}
    for path in sorted(source.glob("*.jpg")):
        run = path.name.split("__photo_")[0]
        if run.rsplit("_run_", 1)[0] in split["days"]["train"] and path.name not in excluded_names:
            groups.setdefault(run, []).append(path)
    total = sum(map(len, groups.values()))
    if not 1 <= args.count <= total:
        raise ValueError("Not enough eligible training-day images")
    rng = random.Random(args.seed)
    chosen = []
    ordered = sorted(groups)
    for j, run in enumerate(ordered):
        paths = groups[run]
        quota = round(args.count * len(paths) / total) if j < len(ordered)-1 else args.count-len(chosen)
        for k in range(quota):
            start, end = k*len(paths)//quota, (k+1)*len(paths)//quota
            chosen.append(paths[rng.randrange(start, end)])
    if args.references_only:
        train_ids = set(split["partitions"]["train"])
        chosen = [source / r["source_name"] for r in base["records"]
                  if r["id"] in train_ids and r["supervision"] == "binary-reference"]
    rows, seen = [], set() if args.references_only else set(excluded_hashes)
    for p in chosen:
        digest = sha256(p)
        if digest in seen:
            continue
        seen.add(digest)
        rows.append({"id": digest, "image": p.name, "source_sha256": digest,
                     "recording_run": p.name.split("__photo_")[0]})
    rng.shuffle(rows)
    result = {"schema": "sidewalkpilot-pseudo-selection-v1", "created_utc": utc_now(),
              "source": str(source), "seed": args.seed, "requested": len(chosen), "count": len(rows),
              "purpose": "training-reference diagnostic" if args.references_only else "new training-only pseudo-labels",
              "baseline_manifest_sha256": sha256(args.dataset / "manifest.json"),
              "baseline_split_sha256": sha256(args.split), "allowed_days": split["days"]["train"],
              "sampling": "Proportional recording-run quotas; seeded sample from equal chronological bins; all reviewed images and exact hashes excluded.",
              "frames": rows}
    result["selection_id"] = digest_json(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return {"selection": str(output), "count": len(rows), "days": result["allowed_days"]}


def load_selection(path):
    data = read_json(path)
    if (data.get("schema") != "sidewalkpilot-pseudo-selection-v1"
            or digest_json({k:v for k,v in data.items() if k != "selection_id"}) != data["selection_id"]
            or len({r["id"] for r in data["frames"]}) != data["count"]):
        raise ValueError("Invalid selection identity")
    if any(r["recording_run"].rsplit("_run_", 1)[0] not in data["allowed_days"] for r in data["frames"]):
        raise ValueError("Evaluation-day leakage")
    return data


def load_runtime():
    from compare_sam31_sidewalk import COMMIT, SAM3_REVISION, SAM3_CHECKPOINT_SHA256, load_detector
    source = ROOT / "sam3-diagnostic-v18/dependencies/sam3"
    runtime, hf_runtime = ROOT / "sam31-image-diagnostic-v20/runtime", ROOT / "sam3-diagnostic-v18/runtime"
    snapshot = Path.home() / ".cache/huggingface/hub/models--facebook--sam3/snapshots" / SAM3_REVISION
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"], text=True)
    if head != COMMIT or dirty or sha256(snapshot / "sam3.pt") != SAM3_CHECKPOINT_SHA256:
        raise ValueError("Pinned SAM source/checkpoint differs")
    sys.path[:0] = [str(runtime), str(hf_runtime), str(source)]
    import torch
    from transformers import Sam3Processor as HfProcessor
    from sam3.model.sam3_image_processor import Sam3Processor
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model, report = load_detector(source, snapshot / "sam3.pt", torch, native_sam3_control=True)
    processor = HfProcessor.from_pretrained(snapshot, local_files_only=True)
    native = Sam3Processor(model, device="cuda", confidence_threshold=POLICY["score_threshold"])
    return torch, model, processor, native, {"checkpoint_sha256": SAM3_CHECKPOINT_SHA256,
        "source_commit": COMMIT, "revision": SAM3_REVISION, "load_report": report,
        "precision": "bf16 autocast; FP32 weights", "preprocessing": "frozen HF SAM 3 processor"}


def panel(path, image, proposals, labels, detail):
    views = [np.array(image)]
    for mask in (*proposals, labels == 1):
        view = np.array(image).astype(np.float32)
        view[mask] = .55*view[mask] + .45*np.array([30,210,140])
        views.append(view.astype(np.uint8))
    sheet = Image.new("RGB", (1280, 768), "white")
    draw = ImageDraw.Draw(sheet)
    titles = ["Original", "SAM 3: concrete sidewalk", "SAM 3: sidewalk", "Consensus pseudo-label / " + ("candidate" if detail["accepted_for_pseudo_training"] else "DEFERRED")]
    for n, (view, title) in enumerate(zip(views, titles)):
        x, y = (n % 2)*640, (n // 2)*384
        sheet.paste(Image.fromarray(view).resize((640,360)), (x,y+24))
        draw.text((x+6,y+6), title, fill="black")
    sheet.save(path, quality=92)


def run(args):
    from compare_sam31_sidewalk import hf_outputs
    selection = load_selection(args.selection)
    source, output = Path(selection["source"]), args.output.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Output overlaps source")
    torch, model, processor, native, runtime = load_runtime()
    contract = {"selection_sha256": sha256(args.selection), "policy": POLICY,
                "runner_sha256": sha256(Path(__file__)), "filter_sha256": sha256(_workspace.source_path('pseudo_mask_filter.py')),
                "runtime": runtime}
    contract_hash = digest_json(contract)
    if output.exists():
        old = read_json(output / "manifest.json")
        if not args.resume or old["contract_sha256"] != contract_hash:
            raise ValueError("Existing run differs; use a new directory or matching --resume")
    else:
        for directory in ("records", "raw", "masks", "panels"):
            (output / directory).mkdir(parents=True)
        write_json(output / "manifest.json", {"schema": "sidewalkpilot-sam3-pseudo-run-v1", "created_utc": utc_now(),
                   "contract": contract, "contract_sha256": contract_hash, "selection": str(args.selection.resolve()),
                   "review_status": "Pseudo-labels, not human-accepted references"})
    rows = selection["frames"][:args.limit or None]
    accepted = 0
    reasons = Counter()
    began = time.monotonic()
    with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        text = {prompt: model.backbone.forward_text([prompt], device="cuda") for prompt in POLICY["prompts"]}
        for n, frame in enumerate(rows, 1):
            record_path = output / "records" / (frame["id"] + ".json")
            if record_path.exists():
                record = read_json(record_path)
                if record["contract_sha256"] != contract_hash or record["frame"] != frame:
                    raise ValueError("Resume record identity differs")
                for asset in [record["mask"], *record["raw"]]:
                    if sha256(safe_file(output, asset["path"])) != asset["sha256"]:
                        raise ValueError("Resume asset changed")
            else:
                path = safe_file(source, frame["image"])
                if sha256(path) != frame["source_sha256"]:
                    raise ValueError("Selected source changed")
                with Image.open(path) as handle:
                    image = handle.convert("RGB")
                pixels = processor(images=image, return_tensors="pt").pixel_values.to("cuda")
                backbone = model.backbone.forward_image(pixels)
                proposals, scores, raw_files = [], [], []
                for i, prompt in enumerate(POLICY["prompts"]):
                    features = dict(backbone)
                    features.update(text[prompt])
                    raw = model.forward_grounding(backbone_out=features, find_input=native.find_stage,
                        geometric_prompt=model._get_dummy_prompt(), find_target=None)
                    if any(not torch.isfinite(raw[key]).all().item() for key in ("pred_masks", "pred_logits", "presence_logit_dec")):
                        raise ValueError("Non-finite SAM output")
                    result = processor.post_process_instance_segmentation(hf_outputs(raw, model.supervise_joint_box_scores),
                        threshold=POLICY["score_threshold"], mask_threshold=POLICY["mask_threshold"],
                        target_sizes=[(image.height,image.width)])[0]
                    masks = result["masks"].cpu().numpy()
                    proposal = np.any(masks, axis=0) if len(masks) else np.zeros((image.height,image.width), dtype=bool)
                    if proposal.ndim == 3 and proposal.shape[0] == 1:
                        proposal = proposal[0]
                    score_list = result["scores"].cpu().tolist()
                    scores.append(max(score_list, default=0.0))
                    proposals.append(proposal)
                    relative = f"raw/{frame['id']}-{i}.png"
                    Image.fromarray(proposal.astype(np.uint8)).save(output / relative)
                    raw_files.append({"path": relative, "sha256": sha256(output / relative), "scores": score_list})
                labels, detail = filter_masks(*proposals, scores)
                relative = f"masks/{frame['id']}.png"
                Image.fromarray(labels).save(output / relative)
                record = {"frame": frame, "size": list(image.size), "contract_sha256": contract_hash,
                          "raw": raw_files, "mask": {"path": relative, "sha256": sha256(output / relative)},
                          "filter": detail, "created_utc": utc_now()}
                if n <= args.panels:
                    panel(output / "panels" / f"{n:04d}.jpg", image, proposals, labels, detail)
                write_json(record_path, record)
            accepted += record["filter"]["accepted_for_pseudo_training"]
            reasons.update(record["filter"]["reasons"])
            if n == 1 or n % 25 == 0 or n == len(rows):
                progress = {"processed": n, "selection_total": selection["count"], "accepted_pseudo": accepted,
                    "deferred": n-accepted, "reasons": dict(reasons), "elapsed_seconds": time.monotonic()-began}
                write_json(output / "progress.json", progress)
                print(json.dumps(progress), flush=True)
    write_json(output / "status.json", {"status": "complete" if len(rows) == selection["count"] else "pilot-complete", **progress})
    return progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("prepare")
    for name in ("source", "dataset", "split", "output"):
        select.add_argument("--"+name, type=Path, required=True)
    select.add_argument("--count", type=int, default=10000)
    select.add_argument("--seed", type=int, default=20261121)
    select.add_argument("--references-only", action="store_true")
    label = sub.add_parser("run")
    for name in ("selection", "output"):
        label.add_argument("--"+name, type=Path, required=True)
    label.add_argument("--limit", type=int, default=0)
    label.add_argument("--panels", type=int, default=40)
    label.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args) if args.command == "prepare" else run(args), indent=2))


if __name__ == "__main__":
    main()
