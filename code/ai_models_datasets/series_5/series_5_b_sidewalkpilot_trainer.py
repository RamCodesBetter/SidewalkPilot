#!/usr/bin/env python3
"""5.B: higher-resolution binary beta with screened weak positive/negative targets."""
import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F

from prepare_series5_pseudo_dataset import load_mixed_partition
from series_5_a_sidewalkpilot_trainer import MixedBatchSampler, train
from label_grounded_sam2 import sha256

TRAINING_POLICY = {
    "version": "5.B-screened-pseudo-v1",
    "background_loss_weight": 2.0,
    "human_references_per_batch": 4,
    "weak_loss_weight": 0.5,
    "require_live_wandb": True,
    "batch_log_interval": 20,
    "weak_supervision": "screened pseudo-binary and previous positive-only labels",
    "evaluation": "fixed 5.A development validation; no automatic test evaluation",
}


class ScreenedBatchSampler(MixedBatchSampler):
    def __init__(self, rows, batch_size, seed):
        super().__init__(rows, batch_size, seed)
        if batch_size < 8 or not self.partial:
            raise ValueError("5.B needs a batch of at least 8 and weak labels")
        self.strong_count = 4
        self.partial_count = batch_size - 4


def conservative_loss(logits, targets, strong, partial_weight=0.5):
    known = targets != 255
    weights = torch.where(targets == 0, 2.0, 1.0) * known
    ce = F.cross_entropy(logits.float(), targets, ignore_index=255, reduction="none")
    per_image = (ce * weights).flatten(1).sum(1) / weights.flatten(1).sum(1).clamp_min(1)
    valid = known.flatten(1).any(1)
    zero = logits.float().sum() * 0
    binary = per_image[strong & valid].mean() if (strong & valid).any() else zero
    weak = per_image[~strong & valid].mean() if (~strong & valid).any() else zero
    return binary + partial_weight * weak, binary, weak


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("dataset", "split", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    integers = dict(width=960, height=540, batch_size=16, epochs=20,
                    patience=5, seed=20261121, workers=2)
    floats = dict(backbone_lr=0.0001, head_lr=0.001, weight_decay=0.0001, partial_weight=0.5)
    for key, default in integers.items():
        parser.add_argument("--" + key.replace("_", "-"), type=int, default=default)
    for key, default in floats.items():
        parser.add_argument("--" + key.replace("_", "-"), type=float, default=default)
    parser.add_argument("--precision", choices=("auto", "fp32", "bf16", "fp16"), default="bf16")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--weights", choices=("imagenet", "none"), default="imagenet")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--wandb", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    args.model_name = "5.B"
    args.experiment = "series-5.B-screened-pseudo-development"
    args.training_policy = {
        **TRAINING_POLICY,
        "weak_loss_weight": args.partial_weight,
        "entrypoint_sha256": sha256(Path(__file__)),
        "dataset_loader_sha256": sha256(Path(__file__).with_name("prepare_series5_pseudo_dataset.py")),
    }
    result = train(args, partition_loader=load_mixed_partition,
                   sampler_class=ScreenedBatchSampler, loss_function=conservative_loss)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
