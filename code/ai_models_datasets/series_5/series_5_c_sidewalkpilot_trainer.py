#!/usr/bin/env python3
"""5.C: ConvNeXt-Tiny / U-Net-style decoder, explicit FP32 only."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
TOOLS = HERE / "tools"
sys.path.insert(0, str(TOOLS))
import workspace
workspace.activate()

import convnext_tiny_unet as model_definition
from label_grounded_sam2 import sha256
from prepare_reviewed_dataset import read_json
from prepare_series5_pseudo_dataset import load_mixed_partition
import series_5_a_sidewalkpilot_trainer as base
from series_5_b_sidewalkpilot_trainer import ScreenedBatchSampler, conservative_loss

DEFAULTS = read_json(workspace.CONFIGS / "series_5_c_config.json")


def load_partition(dataset, split):
    manifest = read_json(dataset / "manifest.json")
    if manifest.get("schema") == "sidewalkpilot-mixed-pseudo-dataset-v1":
        return load_mixed_partition(dataset, split)
    return base.load_partition(dataset, split)


def run_training(args):
    if args.precision != "fp32":
        raise ValueError("5.C is FP32 only")
    # A setup smoke check may use old development labels; the full 5.C run may not.
    manifest = read_json(args.dataset / "manifest.json")
    if not args.smoke and (manifest.get("schema") != "sidewalkpilot-mixed-pseudo-dataset-v1"
                           or manifest.get("accepted_pseudo", 0) < 10000):
        raise ValueError("Full 5.C training needs a frozen 10,000-label pseudo dataset; current labels are not ready")
    args.model_name = DEFAULTS["model_name"]
    args.experiment = DEFAULTS["experiment"]
    args.training_policy = {
        "version": "5.C-convnext-unet-fp32-v1",
        "background_loss_weight": 2.0, "human_references_per_batch": 4,
        "weak_loss_weight": args.partial_weight, "require_live_wandb": True,
        "batch_log_interval": 20,
        "scope": "Architecture/precision change; uses the 5.B weak-label loss, not the entire final research training recipe",
        "entrypoint_sha256": sha256(Path(__file__)),
        "model_sha256": sha256(Path(model_definition.__file__)),
        "base_trainer_sha256": sha256(Path(base.__file__)),
    }
    return base.train(args, partition_loader=load_partition, sampler_class=ScreenedBatchSampler,
                      loss_function=conservative_loss, model_definition=model_definition)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    training = commands.add_parser("train")
    scoring = commands.add_parser("evaluate")
    prediction = commands.add_parser("predict")
    for command in (training, scoring, prediction):
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
        command.add_argument("--precision", choices=("fp32",), default="fp32")
    for command in (training, scoring):
        command.add_argument("--dataset", type=Path, required=True)
        command.add_argument("--split", type=Path, required=True)
    for command in (scoring, prediction):
        command.add_argument("--checkpoint", type=Path, required=True)
    scoring.add_argument("--partition", choices=("validation", "test"), default="validation")
    prediction.add_argument("--image", type=Path, required=True)
    for key in ("width", "height", "batch_size", "epochs", "patience", "seed"):
        training.add_argument("--" + key.replace("_", "-"), type=int, default=DEFAULTS[key])
    for key in ("backbone_lr", "head_lr", "weight_decay", "partial_weight"):
        training.add_argument("--" + key.replace("_", "-"), type=float, default=DEFAULTS[key])
    training.add_argument("--workers", type=int, default=2)
    training.add_argument("--weights", choices=("imagenet", "none"), default="imagenet")
    training.add_argument("--resume", action="store_true")
    training.add_argument("--smoke", action="store_true")
    training.add_argument("--wandb", action=argparse.BooleanOptionalAction, default=True)
    return result


def main():
    args = parser().parse_args()
    if args.command == "train":
        result = run_training(args)
    elif args.command == "evaluate":
        result = base.evaluate_checkpoint(args, model_definition=model_definition, partition_loader=load_partition)
    else:
        result = base.predict(args, model_definition=model_definition)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
