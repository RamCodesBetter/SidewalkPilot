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
import series_5_b_sidewalkpilot_trainer as previous
import segmentation_losses
import checkpoint_names
import boundary_metrics
import campaign10k

DEFAULTS = read_json(workspace.CONFIGS / "series_5_c_config.json")


def load_partition(dataset, split):
    manifest = read_json(dataset / "manifest.json")
    if manifest.get("schema") == "sidewalkpilot-campaign10k-v1":
        return campaign10k.load(dataset, split)
    if manifest.get("schema") == "sidewalkpilot-mixed-pseudo-dataset-v1":
        return load_mixed_partition(dataset, split)
    return base.load_partition(dataset, split)


def run_training(args, variant="5.C"):
    if args.precision != "fp32":
        raise ValueError("5.C is FP32 only")
    # A setup smoke check may use old development labels; the full 5.C run may not.
    manifest = read_json(args.dataset / "manifest.json")
    campaign = manifest.get("schema") == "sidewalkpilot-campaign10k-v1"
    if variant == "5.E" and not campaign:
        raise ValueError("5.E requires the shared campaign-only split")
    if campaign and args.loss != "focal":
        raise ValueError("Campaign-only comparison uses focal loss; no reviewed Dice targets")
    if not args.smoke and (not campaign and manifest.get("schema") != "sidewalkpilot-mixed-pseudo-dataset-v1"
                           or manifest.get("accepted_pseudo", 0) < 10000):
        raise ValueError("Full 5.C training needs a frozen 10,000-label pseudo dataset; current labels are not ready")
    if args.loss not in ("focal", "focal-dice"):
        raise ValueError("Unknown 5.C loss")
    if args.loss == "focal-dice" and args.dice_weight <= 0:
        raise ValueError("focal-dice requires a positive Dice weight")
    loss_function = segmentation_losses.ReviewedFocalLoss(
        gamma=args.focal_gamma, background_weight=args.background_weight,
        sidewalk_weight=args.sidewalk_weight, class_weight_cap=args.class_weight_cap,
        dice_weight=args.dice_weight if args.loss == "focal-dice" else 0.0)
    args.model_name = variant
    args.experiment = DEFAULTS["experiment"].replace("5.C",variant)
    args.training_policy = {
        "version": "5.C-convnext-unet-fp32-focal-v2",
        "loss": args.loss, "focal_gamma": args.focal_gamma,
        "requested_class_weights": [args.background_weight, args.sidewalk_weight],
        "class_weight_cap": args.class_weight_cap,
        "class_weights": list(loss_function.class_weights),
        "dice_weight": loss_function.dice_weight, "dice_smooth": loss_function.dice_smooth,
        "dice_scope": "mean of both classes, per reviewed image; ignore unknown pixels; no weak Dice",
        "human_references_per_batch": 4,
        "weak_loss_weight": args.partial_weight, "require_live_wandb": True,
        "batch_log_interval": 20,
        "scope": "Binary development; restores focal baseline/optional Dice, not final split/warmup/safety-score recipe",
        "entrypoint_sha256": sha256(Path(__file__)),
        "model_sha256": sha256(Path(model_definition.__file__)),
        "base_trainer_sha256": sha256(Path(base.__file__)),
        "sampler_sha256": sha256(Path(previous.__file__)),
        "loss_sha256": sha256(Path(segmentation_losses.__file__)),
        "checkpoint_names": checkpoint_names.checkpoint_names(args.model_name),
        "smart_selection": checkpoint_names.SMART_RULE,
        "boundary_tolerance_px": boundary_metrics.RADIUS,
        "boundary_metrics_sha256": sha256(Path(boundary_metrics.__file__)),
        "checkpoint_naming_sha256": sha256(Path(checkpoint_names.__file__)),
    }
    if campaign:
        args.training_policy.update(campaign_only=True, human_references_per_batch=0,
            encoder_frozen_epochs=2 if variant=="5.E" else 0,
            scope="8000/1000/1000; validation and test quantify agreement with original SAM 3 pseudo-labels.",
            sampler_sha256=sha256(Path(campaign10k.__file__)))
    result = base.train(args, partition_loader=load_partition, sampler_class=campaign10k.CampaignSampler if campaign else previous.ScreenedBatchSampler,
                        loss_function=loss_function, model_definition=model_definition)
    if not args.smoke and result["status"] == "complete":
        result["checkpoint_selection"] = checkpoint_names.publish_completed_run(args.output, args.model_name)
    return result


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
    for key in ("backbone_lr", "head_lr", "weight_decay", "partial_weight", "focal_gamma",
                "background_weight", "sidewalk_weight", "class_weight_cap", "dice_weight"):
        training.add_argument("--" + key.replace("_", "-"), type=float, default=DEFAULTS[key])
    training.add_argument("--workers", type=int, default=2)
    training.add_argument("--loss", choices=("focal", "focal-dice"), default=DEFAULTS["loss"])
    training.add_argument("--weights", choices=("imagenet", "none"), default="imagenet")
    training.add_argument("--resume", action="store_true")
    training.add_argument("--smoke", action="store_true")
    training.add_argument("--wandb", action=argparse.BooleanOptionalAction, default=True)
    return result


def main(variant="5.C"):
    args = parser().parse_args()
    if args.command == "train":
        result = run_training(args,variant)
    elif args.command == "evaluate":
        result = base.evaluate_checkpoint(args, model_definition=model_definition, partition_loader=load_partition)
    else:
        result = base.predict(args, model_definition=model_definition)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
