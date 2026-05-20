#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from sidewalkpilot_trainer import (
    DEVICE,
    SidewalkPilotV3,
    SteeringDataset,
    decode_controls,
    load_correction_items,
    load_state_dict_for_model,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODELS_DIR = REPO_ROOT / "code" / "ai_models"
DEFAULT_JSON_OUT = REPO_ROOT / "docs" / "sidewalkpilot_v3_eval.json"
MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>3\.\d+[a-z]?)\.pth$")


def version_key(version):
    suffix = version[-1] if version[-1].isalpha() else ""
    base = version[:-1] if suffix else version
    major, minor = base.split(".")
    suffix_rank = 0 if not suffix else ord(suffix) - ord("a") + 1
    return int(major), int(minor), suffix_rank


def discover_models(models_dir, versions=None):
    wanted = set(versions or [])
    models = []
    for path in sorted(Path(models_dir).glob("SidewalkPilot-v3*.pth")):
        match = MODEL_RE.match(path.name)
        if not match:
            continue
        version = match.group("version")
        if wanted and version not in wanted:
            continue
        models.append((version, path))
    return sorted(models, key=lambda item: version_key(item[0]))


def metric_block(values):
    values = np.asarray(values, dtype=np.float32)
    if values.size == 0:
        return {"mae": None, "median_ae": None, "max_ae": None, "signed_error": None}
    return {
        "mae": float(np.mean(np.abs(values))),
        "median_ae": float(np.median(np.abs(values))),
        "max_ae": float(np.max(np.abs(values))),
        "signed_error": float(np.mean(values)),
    }


def evaluate_model(model, loader, device):
    pred_steering = []
    target_steering = []
    pred_throttle = []
    target_throttle = []

    model.eval()
    with torch.no_grad():
        for images, targets in loader:
            images = images.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)
            preds = torch.clamp(model(images), -1.0, 1.0)
            p_steer, p_throttle = decode_controls(preds)
            t_steer, t_throttle = decode_controls(targets)
            pred_steering.append(p_steer.cpu().numpy().reshape(-1))
            target_steering.append(t_steer.cpu().numpy().reshape(-1))
            pred_throttle.append(p_throttle.cpu().numpy().reshape(-1))
            target_throttle.append(t_throttle.cpu().numpy().reshape(-1))

    pred_steering = np.concatenate(pred_steering)
    target_steering = np.concatenate(target_steering)
    pred_throttle = np.concatenate(pred_throttle)
    target_throttle = np.concatenate(target_throttle)
    steering_error = pred_steering - target_steering
    throttle_error = pred_throttle - target_throttle

    return {
        "count": int(target_steering.size),
        "steering": {
            **metric_block(steering_error),
            "pred_min": float(pred_steering.min()),
            "pred_max": float(pred_steering.max()),
            "pred_mean": float(pred_steering.mean()),
            "target_min": float(target_steering.min()),
            "target_max": float(target_steering.max()),
            "target_mean": float(target_steering.mean()),
        },
        "throttle": {
            **metric_block(throttle_error),
            "pred_min": float(pred_throttle.min()),
            "pred_max": float(pred_throttle.max()),
            "pred_mean": float(pred_throttle.mean()),
            "target_min": float(target_throttle.min()),
            "target_max": float(target_throttle.max()),
            "target_mean": float(target_throttle.mean()),
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate SidewalkPilot Series 3 steering+throttle checkpoints.")
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--corrections", nargs="*", default=[str(SCRIPT_DIR / "steering_corrections.json")])
    parser.add_argument("--roots", nargs="*", default=[])
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=180)
    parser.add_argument("--crop-top-ratio", type=float, default=0.0)
    parser.add_argument("--versions", nargs="*", default=None)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.device == "cuda":
        device = torch.device("cuda")
    elif args.device == "cpu":
        device = torch.device("cpu")
    else:
        device = torch.device(DEVICE)

    models = discover_models(args.models_dir, args.versions)
    if not models:
        raise FileNotFoundError(f"No Series 3 checkpoints found in {args.models_dir}")

    correction_items = load_correction_items(args.corrections)
    dataset = SteeringDataset(
        args.roots,
        correction_items,
        width=args.width,
        height=args.height,
        crop_top_ratio=args.crop_top_ratio,
        augment=False,
        scan_log_every=1000,
        stage_name="eval.v3",
    )
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
    )

    results = {
        "input_size": {"width": args.width, "height": args.height},
        "sample_count": len(dataset),
        "source_counts": dict(sorted(Counter(dataset.sources).items())),
        "models": {},
    }

    for version, path in models:
        print(f"[eval] model={version} checkpoint={path}", flush=True)
        model = SidewalkPilotV3().to(device)
        model.load_state_dict(load_state_dict_for_model(path, device), strict=True)
        results["models"][version] = {
            "checkpoint": str(path.resolve()),
            **evaluate_model(model, loader, device),
        }
        steering = results["models"][version]["steering"]
        throttle = results["models"][version]["throttle"]
        print(
            f"[eval] done model={version} steering_mae={steering['mae']:.3f} "
            f"throttle_mae={throttle['mae']:.4f}",
            flush=True,
        )

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"[done] wrote {args.json_out}", flush=True)


if __name__ == "__main__":
    main()
