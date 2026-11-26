#!/usr/bin/env python3
"""Series 5 training: networks, objectives, evaluation, training loop and fixed recipes."""

import argparse
from collections import Counter
from contextlib import nullcontext
from decimal import Decimal
import errno
import re
import shutil
from uuid import uuid4
from scipy.ndimage import binary_dilation, generate_binary_structure
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny
import csv
import json
import math
from pathlib import Path
import random
import sys
import time
import uuid

import numpy as np
from PIL import Image, ImageDraw
import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, Sampler
import torchvision
from torchvision.models import MobileNet_V3_Large_Weights
from torchvision.models.segmentation import lraspp_mobilenet_v3_large
from torchvision.transforms import functional as TVF

HERE = Path(__file__).resolve().parent
TOOLS = HERE / "tools"
sys.path.insert(0, str(TOOLS))
import workspace
workspace.activate()

from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from prepare_reviewed_dataset import read_json, safe_file
from reviewed_day_split import PARTITIONS, create_split, load_partition
import campaign10k


CONVNEXT_ARCHITECTURE = "convnext_tiny_unet"
ENCODER_CHANNELS = (96, 192, 384, 768)
DECODER_CHANNELS = (256, 128, 64, 32)


def configure_fp32():
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.set_float32_matmul_precision("highest")


def validate_precision(precision):
    if precision != "fp32":
        raise ValueError("ConvNeXt-Tiny U-Net requires explicit fp32; AMP/FP16/BF16 are disabled")


def config(weights):
    if weights not in ("imagenet", "none"):
        raise ValueError("Unknown initialization")
    return dict(architecture=CONVNEXT_ARCHITECTURE, num_classes=2,
                backbone_weights="ConvNeXt_Tiny_Weights.IMAGENET1K_V1" if weights == "imagenet" else None,
                encoder_channels=list(ENCODER_CHANNELS), decoder_channels=list(DECODER_CHANNELS),
                freeze_backbone_bn_statistics=False,
                precision_policy={"weights": "fp32", "inputs": "fp32", "logits": "fp32",
                                  "autocast": False, "tf32": False,
                                  "deployment": "FP32 reference; no reduced-precision engine built"})


def validate_state(state):
    cfg = state["config"]
    validate_precision(cfg["precision"])
    expected = config(cfg["weights"])
    if any(cfg.get(key) != value for key, value in expected.items()):
        raise ValueError("Checkpoint architecture/precision contract differs")
    if any(t.is_floating_point() and t.dtype != torch.float32 for t in state["model"].values()):
        raise ValueError("Checkpoint contains non-FP32 model tensors")


class ConvNeXtEncoder(nn.Module):
    def __init__(self, weights):
        super().__init__()
        self.features = convnext_tiny(weights=weights).features

    def forward(self, image):
        skips = []
        for index, layer in enumerate(self.features):
            image = layer(image)
            if index in (1, 3, 5, 7):
                skips.append(image)
        return skips


def conv_block(inputs, outputs):
    return nn.Sequential(
        nn.Conv2d(inputs, outputs, 3, padding=1, bias=False),
        nn.GroupNorm(8, outputs), nn.GELU(),
        nn.Conv2d(outputs, outputs, 3, padding=1, bias=False),
        nn.GroupNorm(8, outputs), nn.GELU(),
    )


class SkipBlock(nn.Module):
    def __init__(self, inputs, skip_channels, outputs):
        super().__init__()
        self.skip_projection = nn.Conv2d(skip_channels, outputs, 1)
        self.fusion = conv_block(inputs + outputs, outputs)

    def forward(self, value, skip):
        value = F.interpolate(value, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return self.fusion(torch.cat((value, self.skip_projection(skip)), dim=1))


class UNetDecoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.bottleneck = nn.Conv2d(768, 256, 1)
        self.up16 = SkipBlock(256, 384, 128)
        self.up8 = SkipBlock(128, 192, 64)
        self.up4 = SkipBlock(64, 96, 32)
        self.head = nn.Conv2d(32, 2, 1)

    def forward(self, features, size):
        low, middle, high, deepest = features
        value = self.up16(self.bottleneck(deepest), high)
        value = self.up8(value, middle)
        value = self.up4(value, low)
        return F.interpolate(self.head(value), size=size, mode="bilinear", align_corners=False)


class ConvNeXtTinyUNet(nn.Module):
    def __init__(self, weights="imagenet"):
        super().__init__()
        config(weights)
        pretrained = ConvNeXt_Tiny_Weights.IMAGENET1K_V1 if weights == "imagenet" else None
        self.backbone = ConvNeXtEncoder(pretrained)
        self.classifier = UNetDecoder()
        self.float()

    def forward(self, image):
        if image.ndim != 4 or image.shape[1] != 3 or min(image.shape[-2:]) < 32:
            raise ValueError("Expected NCHW RGB input with height and width at least 32")
        if image.dtype != torch.float32:
            raise ValueError("Input must be FP32, not silently converted")
        if any(p.dtype != torch.float32 for p in self.parameters()):
            raise ValueError("All model parameters must remain FP32")
        # A surrounding mixed-precision context must not change this model's contract.
        with torch.autocast(device_type=image.device.type, enabled=False):
            return {"out": self.classifier(self.backbone(image), image.shape[-2:])}


def make_convnext_model(weights="imagenet"):
    configure_fp32()
    return ConvNeXtTinyUNet(weights)


class ConvNeXtRecipe:
    ARCHITECTURE = CONVNEXT_ARCHITECTURE
    make_model = staticmethod(make_convnext_model)
    config = staticmethod(config)
    validate_state = staticmethod(validate_state)
    validate_precision = staticmethod(validate_precision)


class ReviewedFocalLoss:
    """Separate strong/weak image means, with optional reviewed-only soft Dice.

    Returns (total, strong objective, weak focal), matching the shared trainer.
    last_metrics contains detached scalar components for local/W&B logging.
    """

    def __init__(self, *, gamma=1.5, background_weight=2.0, sidewalk_weight=1.0,
                 class_weight_cap=4.0, dice_weight=0.0, dice_smooth=1e-6):
        values = dict(gamma=gamma, background_weight=background_weight,
                      sidewalk_weight=sidewalk_weight, class_weight_cap=class_weight_cap,
                      dice_weight=dice_weight, dice_smooth=dice_smooth)
        for name, value in values.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if min(background_weight, sidewalk_weight, class_weight_cap, dice_smooth) <= 0:
            raise ValueError("Class weights, cap, and Dice smoothing must be positive")
        self.gamma, self.dice_weight, self.dice_smooth = gamma, dice_weight, dice_smooth
        self.class_weights = (min(background_weight, class_weight_cap), min(sidewalk_weight, class_weight_cap))
        if min(self.class_weights) < torch.finfo(torch.float32).tiny:
            raise ValueError("Effective class weights must be representable as normal FP32 values")
        self.last_metrics = {}

    def __call__(self, logits, targets, strong, partial_weight=0.5):
        if not math.isfinite(partial_weight) or partial_weight < 0:
            raise ValueError("Weak-label weight must be finite and nonnegative")
        if logits.dtype != torch.float32:
            raise ValueError("5.C loss requires FP32 logits")
        if (logits.ndim != 4 or logits.shape[1] != 2
                or targets.shape != (logits.shape[0], *logits.shape[2:])
                or strong.shape != (logits.shape[0],) or strong.dtype != torch.bool):
            raise ValueError("Expected logits [N,2,H,W], targets [N,H,W], boolean strong [N]")
        known = targets != 255
        valid = known.flatten(1).any(1)
        zero = logits.sum() * 0
        weights = torch.where(targets == 0, self.class_weights[0], self.class_weights[1]) * known
        # p_t must come from UNWEIGHTED CE; class weighting is outside the focal factor.
        ce = F.cross_entropy(logits, targets, ignore_index=255, reduction="none")
        modulation = (-torch.expm1(-ce)).clamp_min(torch.finfo(logits.dtype).eps).pow(self.gamma)
        denominator = weights.flatten(1).sum(1).clamp_min(torch.finfo(logits.dtype).tiny)
        per_image = (weights * modulation * ce).flatten(1).sum(1) / denominator
        strong_focal = per_image[strong & valid].mean() if (strong & valid).any() else zero
        weak_focal = per_image[~strong & valid].mean() if (~strong & valid).any() else zero
        dice = zero
        if self.dice_weight and (strong & valid).any():
            selected = strong & valid
            selected_known = known[selected, None]
            probabilities = logits[selected].softmax(1) * selected_known
            labels = targets[selected].masked_fill(~known[selected], 0)
            reference = F.one_hot(labels, num_classes=2).permute(0, 3, 1, 2) * selected_known
            intersection = (probabilities * reference).sum((2, 3))
            denominator = probabilities.sum((2, 3)) + reference.sum((2, 3))
            dice = (1 - (2 * intersection + self.dice_smooth) / (denominator + self.dice_smooth)).mean()
        strong_objective = strong_focal + self.dice_weight * dice
        self.last_metrics = {"strong_focal": strong_focal.detach(), "weak_focal": weak_focal.detach(),
                             "strong_soft_dice": dice.detach(), "weighted_dice": (self.dice_weight * dice).detach()}
        return strong_objective + partial_weight * weak_focal, strong_objective, weak_focal


SMART_RULE = "Within 1 percentage point of maximum validation sidewalk IoU (inclusive); highest validation sidewalk precision, then higher IoU, then earliest epoch"


def eligible(iou, best):
    return Decimal(str(iou)) >= Decimal(str(best)) - Decimal("0.01")


def candidate_path(epoch):
    return f"smart-candidates/epoch-{epoch:03d}.pt"


def smart_epoch(history, best):
    candidates = [row for row in history if eligible(row["validation_sidewalk_iou"], best)
                  and row["validation_precision"] is not None]
    return max(candidates, key=lambda r: (r["validation_precision"], r["validation_sidewalk_iou"],
                                          -r["epoch"]), default=None)


def checkpoint_names(model_name):
    if not re.fullmatch(r"5\.(?:[A-Z]|[0-9]+)", model_name):
        raise ValueError("Expected a Series 5 base name such as 5.C or 5.0")
    return {"end": model_name, "best_iou": model_name + "b", "smart": model_name + "s"}


def snapshot(source, destination):
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        try:
            # Atomic checkpoint replacement leaves this inode intact; a symlink would move.
            temporary.hardlink_to(source)
        except OSError as error:
            if error.errno not in (errno.EXDEV, errno.ENOTSUP, errno.EPERM):
                raise
            shutil.copy2(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def publish_completed_run(output, model_name):
    output = Path(output)
    names = checkpoint_names(model_name)
    config = read_json(output / "config.json")
    status = read_json(output / "status.json")
    history = read_json(output / "history.json")
    if (config.get("model_name") != model_name or config.get("smoke_only") is not False
            or status.get("status") != "complete"):
        raise ValueError("Named checkpoints require a completed, non-smoke run of the matching model")
    if (not history or status.get("epochs_completed") != len(history)
            or [row["epoch"] for row in history] != list(range(1, len(history) + 1))
            or any(not math.isfinite(row["validation_sidewalk_iou"])
                   or not 0 <= row["validation_sidewalk_iou"] <= 1 for row in history)):
        raise ValueError("Incomplete or invalid epoch history")
    # max keeps the first tie, matching the trainer's strict-IoU-improvement rule.
    best = max(history, key=lambda row: row["validation_sidewalk_iou"])
    if status.get("best_validation_sidewalk_iou") != best["validation_sidewalk_iou"]:
        raise ValueError("Completed status and best-IoU history disagree")
    selections = {
        "end": ("last.pt", history[-1], "last completed epoch, including normal early stopping"),
        "best_iou": ("best.pt", best, "maximum validation sidewalk IoU; earliest epoch wins ties"),
    }
    smart_enabled = config.get("training_policy", {}).get("smart_selection") == SMART_RULE
    if smart_enabled:
        smart = smart_epoch(history, best["validation_sidewalk_iou"])
        if smart is not None:
            selections["smart"] = (candidate_path(smart["epoch"]), smart, SMART_RULE)
    for source, _, _ in selections.values():
        if not (output / source).is_file():
            raise FileNotFoundError(output / source)
    artifacts = {}
    for role, (source, row, criterion) in selections.items():
        filename = names[role] + ".pt"
        snapshot(output / source, output / filename)
        artifacts[role] = dict(model_name=names[role], filename=filename, source=source,
                               epoch=row["epoch"], criterion=criterion,
                               validation_sidewalk_iou=row["validation_sidewalk_iou"])
        if smart_enabled:
            artifacts[role].update(validation_precision=row["validation_precision"],
                                   validation_boundary_f1=row["validation_boundary_f1"])
    if "smart" not in artifacts:
        artifacts["smart"] = dict(model_name=names["smart"], filename=None,
                                  status="unavailable" if smart_enabled else "reserved",
                                  reason="No eligible epoch with defined precision" if smart_enabled
                                  else "This run did not enable precision-based selection")
    record = dict(schema="sidewalkpilot-checkpoint-selection-v1", model_name=model_name,
                  early_stopped=status.get("early_stopped", False), artifacts=artifacts,
                  selection_partition="validation", test_used_for_selection=False)
    write_json(output / "checkpoint-selection.json", record)
    return record


RADIUS = 2
_axis = np.arange(-RADIUS, RADIUS + 1)
_disk = _axis[:, None]**2 + _axis**2 <= RADIUS**2
_cross = generate_binary_structure(2, 1)


def boundary_counts(prediction, target):
    pred, ref = np.asarray(prediction), np.asarray(target)
    known = ref != 255

    def edge(labels):
        # Inner sidewalk edge only across an observed sidewalk/background pair.
        # Neither the image frame nor unknown pixels constitute background.
        return (labels == 1) & known & binary_dilation((labels == 0) & known, structure=_cross)

    p, r = edge(pred), edge(ref)
    return np.array([np.count_nonzero(p & binary_dilation(r, structure=_disk)), p.sum(),
                     np.count_nonzero(r & binary_dilation(p, structure=_disk)), r.sum()], dtype=np.int64)


def boundary_f1(counts):
    pm, pn, rm, rn = map(int, counts)
    if pn + rn == 0:
        return None
    return (2 * pm * rm / (pm * rn + rm * pn)) if pm and rm else 0.0


# Shared training loop and 5.A baseline
DEFAULTS = read_json(workspace.CONFIGS / "series_5_a_config.json")
ARCHITECTURE = "lraspp_mobilenet_v3_large"
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)


class SidewalkDataset(Dataset):
    def __init__(self, root, rows, size, augment=False, original_targets=False):
        self.root, self.rows, self.size = Path(root), rows, tuple(size)
        self.augment, self.original_targets = augment, original_targets

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        index, seed = index if isinstance(index, tuple) else (index, 0)
        row, rng = self.rows[index], random.Random(seed)
        with Image.open(safe_file(self.root, row["image"])) as source:
            image = source.convert("RGB").resize(self.size, Image.Resampling.BILINEAR)
        with Image.open(safe_file(self.root, row["mask"])) as source:
            mask = source.copy() if self.original_targets else source.resize(self.size, Image.Resampling.NEAREST)
        if self.augment:
            if rng.random() < 0.5:
                image, mask = TVF.hflip(image), TVF.hflip(mask)
            image = TVF.adjust_brightness(image, rng.uniform(0.8, 1.2))
            image = TVF.adjust_contrast(image, rng.uniform(0.85, 1.15))
            image = TVF.adjust_saturation(image, rng.uniform(0.9, 1.1))
        image = TVF.normalize(TVF.to_tensor(image), MEAN, STD)
        target = torch.from_numpy(np.array(mask, dtype=np.int64))
        return image, target, row["supervision"] == "binary-reference", index


class MixedBatchSampler(Sampler):
    """Visit each partial example; cycle references to supply negatives in every batch."""
    def __init__(self, rows, batch_size, seed):
        if batch_size < 2 or batch_size % 2:
            raise ValueError("Batch size must be positive, even, and at least two")
        self.strong = [i for i, row in enumerate(rows) if row["supervision"] == "binary-reference"]
        self.partial = [i for i, row in enumerate(rows) if row["supervision"] in ("sidewalk-positive-only", "pseudo-binary")]
        if not self.strong:
            raise ValueError("Training requires binary references, not positive-only labels")
        self.batch_size, self.seed, self.epoch = batch_size, seed, 0
        self.strong_count = batch_size // 2 if self.partial else batch_size
        self.partial_count = batch_size - self.strong_count

    def __len__(self):
        return max(math.ceil(len(self.strong) / self.strong_count),
                   math.ceil(len(self.partial) / self.partial_count) if self.partial else 0)

    def __iter__(self):
        rng = random.Random(self.seed + self.epoch)
        pools, offsets = {}, {}

        def take(kind, members, count):
            result = []
            for _ in range(count):
                if kind not in pools or offsets[kind] == len(pools[kind]):
                    pools[kind] = list(members)
                    rng.shuffle(pools[kind])
                    offsets[kind] = 0
                result.append(pools[kind][offsets[kind]])
                offsets[kind] += 1
            return result

        for _ in range(len(self)):
            batch = take("strong", self.strong, self.strong_count) + take("partial", self.partial, self.partial_count)
            rng.shuffle(batch)
            yield [(index, rng.getrandbits(32)) for index in batch]


def segmentation_loss(logits, targets, strong, partial_weight=0.25):
    if not math.isfinite(partial_weight) or partial_weight < 0:
        raise ValueError("Partial-label weight must be finite and nonnegative")
    # Normalize per image and per supervision group so 351 partial masks cannot drown out negatives.
    known = targets != 255
    counts = known.flatten(1).sum(1)
    ce = F.cross_entropy(logits.float(), targets, ignore_index=255, reduction="none")
    per_image = ce.flatten(1).sum(1) / counts.clamp_min(1)
    valid = counts > 0
    zero = logits.float().sum() * 0
    binary_loss = per_image[strong & valid].mean() if (strong & valid).any() else zero
    partial_loss = per_image[~strong & valid].mean() if (~strong & valid).any() else zero
    return binary_loss + partial_weight * partial_loss, binary_loss, partial_loss


def make_model(weights="imagenet"):
    if weights not in ("imagenet", "none"):
        raise ValueError("Unknown initialization")
    backbone = MobileNet_V3_Large_Weights.IMAGENET1K_V1 if weights == "imagenet" else None
    return lraspp_mobilenet_v3_large(weights=None, weights_backbone=backbone, num_classes=2)


def train_mode(model):
    model.train()
    # Small, oversampled batches should not overwrite pretrained backbone running statistics.
    for layer in model.backbone.modules():
        if isinstance(layer, nn.modules.batchnorm._BatchNorm):
            layer.eval()


def select_precision(requested, device):
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; refusing a silent CPU training fallback")
    if requested == "auto":
        return "bf16" if device.type == "cuda" and torch.cuda.is_bf16_supported() else ("fp16" if device.type == "cuda" else "fp32")
    if requested not in ("fp32", "fp16", "bf16"):
        raise ValueError("Unknown precision")
    if device.type != "cuda" and requested != "fp32":
        raise ValueError("This trainer supports CPU only in explicit FP32 mode")
    if requested == "bf16" and not torch.cuda.is_bf16_supported():
        raise ValueError("GPU does not support BF16")
    return requested


def autocast(device, precision):
    if precision == "fp32":
        return nullcontext()
    return torch.autocast(device_type=device.type, dtype=torch.bfloat16 if precision == "bf16" else torch.float16)


def confusion_counts(prediction, target):
    known = target != 255
    return torch.bincount((target[known] * 2 + prediction[known]).long(), minlength=4).reshape(2, 2).cpu()


def confusion_metrics(counts):
    tn, fp, fn, tp = counts.reshape(-1).tolist()

    def ratio(a, b):
        return a / b if b else None

    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp,
            "sidewalk_iou": ratio(tp, tp + fp + fn), "non_sidewalk_iou": ratio(tn, tn + fn + fp),
            "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn)}


def save_preview(source, prediction, reference, output):
    with Image.open(source) as image:
        rgb = np.array(image.convert("RGB"))
    panels = [rgb]
    for labels in (prediction, reference):
        overlay = rgb.astype(np.float32)
        hit = labels == 1
        overlay[hit] = overlay[hit] * 0.55 + np.array((30, 210, 140)) * 0.45
        uncertain = labels == 255
        overlay[uncertain] = overlay[uncertain] * 0.65 + np.array((240, 180, 40)) * 0.35
        panels.append(overlay.astype(np.uint8))
    sheet = Image.new("RGB", (1920, 388), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (panel, title) in enumerate(zip(panels, ("Original", "Prediction", "Reference: green sidewalk; amber ignored"))):
        draw.text((640 * i + 8, 8), title, fill="black")
        sheet.paste(Image.fromarray(panel).resize((640, 360)), (640 * i, 28))
    sheet.save(output)


@torch.inference_mode()
def evaluate(model, dataset, rows, size, device, precision, preview_dir=None, limit=0, *, boundaries=False, campaign_only=False):
    model.eval()
    data = SidewalkDataset(dataset, rows, size, original_targets=True)
    counts = torch.zeros((2, 2), dtype=torch.int64)
    reference_images, partial_images, partial_tp, partial_total = 0, 0, 0, 0
    per_image = []
    boundary_total = np.zeros(4, dtype=np.int64)
    if preview_dir:
        preview_dir.mkdir(parents=True, exist_ok=True)
    for index in range(len(data)):
        if limit and index >= limit:
            break
        image, target, strong, _ = data[index]
        with autocast(device, precision):
            logits = model(image.unsqueeze(0).to(device))["out"]
        logits = F.interpolate(logits.float(), size=target.shape, mode="bilinear", align_corners=False)
        prediction = logits.argmax(1)[0].cpu()
        if strong or (campaign_only and rows[index]["supervision"] == "pseudo-binary"):
            current = confusion_counts(prediction, target)
            counts += current
            reference_images += 1
            per_image.append({"id": rows[index]["id"], **confusion_metrics(current)})
            if boundaries:
                edge_counts = boundary_counts(prediction.numpy(), target.numpy())
                boundary_total += edge_counts
                per_image[-1]["boundary_f1"] = boundary_f1(edge_counts)
            if preview_dir and reference_images <= 4:
                save_preview(safe_file(dataset, rows[index]["image"]), prediction.numpy(), target.numpy(),
                             preview_dir / f"{reference_images:02d}.jpg")
        else:
            partial_images += 1
            positive = target == 1
            partial_total += int(positive.sum())
            partial_tp += int(((prediction == 1) & positive).sum())
    return {
        "binary_reference": {"images": reference_images, **confusion_metrics(counts),
                             **({"boundary_f1": boundary_f1(boundary_total),
                                 "boundary_tolerance_px": RADIUS} if boundaries else {})},
        "partial_labels": {"images": partial_images, "known_sidewalk_pixels": partial_total,
                           "known_sidewalk_recall_only": partial_tp / partial_total if partial_total else None,
                           "warning": "Positive-only masks cannot measure false positives, IoU, precision, or F1."},
        "per_binary_reference_image": per_image,
        "evaluation_resolution": "Original reference resolution; bilinear logits resize before argmax; ignored pixels excluded.",
        "limitations": ("Agreement with unverified SAM 3 pseudo-labels, not human ground truth." if campaign_only else
                        "Development labels, not independent test ground truth. Only binary references select checkpoints."),
    }


def atomic_checkpoint(path, state):
    temporary = path.with_suffix(".tmp")
    torch.save(state, temporary)
    temporary.replace(path)


def load_checkpoint(path, *, model_definition=None):
    state = torch.load(path, map_location="cpu", weights_only=True)
    architecture = model_definition.ARCHITECTURE if model_definition else ARCHITECTURE
    if state.get("schema") != "sidewalkpilot-series5-binary-checkpoint-v1" or state["config"]["architecture"] != architecture:
        raise ValueError("Not a supported Series 5 binary checkpoint")
    if model_definition:
        model_definition.validate_state(state)
    model = (model_definition.make_model if model_definition else make_model)("none")
    model.load_state_dict(state["model"], strict=True)
    return model, state


def save_history(output, history):
    write_json(output / "history.json", history)
    temporary = output / "history.csv.tmp"
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)
    temporary.replace(output / "history.csv")


def training_config(args, precision, *, model_definition=None):
    keys = ("width", "height", "batch_size", "epochs", "patience", "backbone_lr", "head_lr",
            "weight_decay", "partial_weight", "seed", "weights")
    cfg = {key: getattr(args, key) for key in keys}
    cfg.update(model_name=getattr(args, "model_name", DEFAULTS["model_name"]), architecture=ARCHITECTURE,
               experiment=getattr(args, "experiment", DEFAULTS["experiment"]), precision=precision,
               smoke_only=args.smoke, labels={"0": "non-sidewalk", "1": "sidewalk", "255": "ignore"},
               backbone_weights="MobileNet_V3_Large_Weights.IMAGENET1K_V1" if args.weights == "imagenet" else None,
               normalization={"mean": list(MEAN), "std": list(STD)}, freeze_backbone_bn_statistics=True)
    if model_definition:
        model_definition.validate_precision(precision)
        cfg.update(model_definition.config(args.weights))
    if getattr(args, "training_policy", None):
        cfg["training_policy"] = args.training_policy
    if min(cfg["width"], cfg["height"]) < 32 or cfg["epochs"] <= 0 or cfg["patience"] <= 0:
        raise ValueError("Invalid image size, epoch count, or patience")
    if cfg["batch_size"] < 2 or cfg["batch_size"] % 2 or args.workers < 0:
        raise ValueError("Use an even batch size >=2 and nonnegative worker count")
    for key in ("backbone_lr", "head_lr", "weight_decay", "partial_weight"):
        if not math.isfinite(cfg[key]) or cfg[key] < 0:
            raise ValueError(f"Invalid {key}")
    if min(cfg["backbone_lr"], cfg["head_lr"]) == 0:
        raise ValueError("Learning rates must be positive")
    return cfg


def start_wandb(output, cfg, identity, metadata, partitions, history):
    sys.path.insert(0, str(HERE.parent / "series_3_and_4"))
    from wandb_logger import WandbLogger

    receipt_path = output / "wandb-run.json"
    binding = {"model_name": cfg["model_name"], "entity": "Sidewalk-Pilot", "project": "SidewalkPilot",
               "config_sha256": digest_json(cfg), **identity}
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if any(receipt.get(key) != value for key, value in binding.items()):
            raise ValueError("W&B run belongs to different model settings or data")
    else:
        receipt = {"id": uuid.uuid4().hex[:8], **binding}
        # Persist identity before connecting so a retry cannot silently create a different run.
        write_json(receipt_path, receipt)
    counts = {name: {"images": len(rows), "binary_references": sum(row["supervision"] == "binary-reference" for row in rows)}
              for name, rows in partitions.items()}
    tracker = WandbLogger(
        f"{cfg['model_name']} - {output.name}", {**cfg, **identity, "split_counts": counts,
                                                "parameters": metadata["parameters"], "device": metadata["device"],
                                                "steps_per_epoch": metadata["steps_per_epoch"]},
        required=True, skip_logged_epochs=True, id=receipt["id"], resume="allow", group=cfg["model_name"],
        tags=["series-5", "beta", "binary", "smoke" if cfg["smoke_only"] else "training"],
        job_type="smoke-test" if cfg["smoke_only"] else "training", dir=str(output), save_code=False,
        settings={"disable_git": True, "save_code": False, "console": "off", "init_timeout": 30},
    )
    try:
        tracker.run.define_metric("epoch")
        tracker.run.define_metric("*", step_metric="epoch")
        if cfg.get("training_policy", {}).get("require_live_wandb"):
            if tracker.run.settings.mode != "online":
                raise RuntimeError("This run requires live online W&B, not offline logging")
            tracker.run.define_metric("train_step")
            tracker.run.define_metric("batch/*", step_metric="train_step")
        receipt.update(url=tracker.run.url, mode=tracker.run.settings.mode)
        write_json(receipt_path, receipt)
        tracker.run.summary.update({"model_name": cfg["model_name"], "smoke_only": cfg["smoke_only"],
                                    "evaluation_scope": "development-only", "media_uploaded": False, "checkpoints_uploaded": False})
        for row in history:
            if not tracker.push(row["epoch"], row):
                raise RuntimeError("Could not replay local history to W&B")
    except BaseException:
        tracker.finish(exit_code=1)
        raise
    return tracker


def train(args, *, partition_loader=None, sampler_class=None, loss_function=None, model_definition=None):
    dataset, output = args.dataset.resolve(), args.output.resolve()
    if output.is_relative_to(dataset) or (output.exists() and not args.resume):
        raise ValueError("Use a new run directory outside the verified dataset, or explicit --resume")
    partitions = (partition_loader or load_partition)(dataset, args.split)
    device = torch.device(args.device)
    precision = select_precision(args.precision, device)
    cfg = training_config(args, precision, model_definition=model_definition)
    smart_selection = cfg.get("training_policy", {}).get("smart_selection") == SMART_RULE
    model_factory = model_definition.make_model if model_definition else make_model
    identity = {"manifest_sha256": sha256(dataset / "manifest.json"), "split_sha256": sha256(args.split)}
    torch.manual_seed(args.seed)
    torch.set_num_threads(min(8, torch.get_num_threads()))
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    history, start_epoch, best_iou, stale = [], 0, -1.0, 0
    state = None
    if args.resume:
        if (output / "last.pt").is_file():
            model, state = load_checkpoint(output / "last.pt", model_definition=model_definition)
            if state["config"] != cfg or state["data_identity"] != identity:
                raise ValueError("Resume configuration, dataset, or split changed")
            history, start_epoch, best_iou, stale = state["history"], state["epoch"], state["best_iou"], state["stale_epochs"]
            save_history(output, history)
        else:
            runtime = read_json(output / "runtime.json")
            if ((output / "history.json").exists() or read_json(output / "config.json") != cfg
                    or any(runtime.get(key) != value for key, value in identity.items())):
                raise ValueError("Cannot restart an uncheckpointed run with changed settings/data or existing history")
            model = model_factory(args.weights)
            print("[resume] Retrying initialization before the first completed checkpoint", flush=True)
    else:
        model = model_factory(args.weights)
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "config.json", cfg)
        write_json(output / "split.json", read_json(args.split))
    model.to(device)
    optimizer = torch.optim.AdamW([
        {"params": model.backbone.parameters(), "lr": args.backbone_lr},
        {"params": model.classifier.parameters(), "lr": args.head_lr}], weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    scaler = torch.amp.GradScaler(device.type, enabled=precision == "fp16")
    if state is not None:
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        scaler.load_state_dict(state["scaler"])
    size = (args.width, args.height)
    sampler = (sampler_class or MixedBatchSampler)(partitions["train"], args.batch_size, args.seed)
    data = SidewalkDataset(dataset, partitions["train"], size, augment=True)
    loader = DataLoader(data, batch_sampler=sampler, num_workers=args.workers,
                        pin_memory=device.type == "cuda", persistent_workers=args.workers > 0)
    validation_rows = sorted(partitions["validation"], key=lambda row: row["supervision"] != "binary-reference")
    metadata = {**identity, "torch": str(torch.__version__), "torchvision": str(torchvision.__version__),
                "cuda_runtime": torch.version.cuda, "device": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
                "parameters": sum(p.numel() for p in model.parameters()), "precision": precision,
                "trainer_sha256": sha256(Path(__file__)), "config_sha256": digest_json(cfg),
                "steps_per_epoch": len(sampler), "created_utc": utc_now(),
                "purpose": "SMOKE TEST ONLY" if args.smoke else "Binary development baseline; no automatic test evaluation"}
    write_json(output / "runtime.json", metadata)
    print(json.dumps(metadata, indent=2), flush=True)
    tracker = None
    if args.wandb:
        tracker = start_wandb(output, cfg, identity, metadata, partitions, history)
    exit_code = 1
    try:
        final_epoch = min(args.epochs, 1) if args.smoke else args.epochs
        for epoch in range(start_epoch, final_epoch):
            if stale >= args.patience:
                break
            began = time.monotonic()
            torch.manual_seed(args.seed + epoch)
            sampler.epoch = epoch
            train_mode(model)
            policy = cfg.get("training_policy", {})
            if policy.get("campaign_only"):
                frozen = epoch < policy["encoder_frozen_epochs"]
                model.backbone.requires_grad_(not frozen)
                model.backbone.train(not frozen)
            totals, steps, updates = np.zeros(3), 0, 0
            component_totals = Counter()
            for images, targets, strong, _ in loader:
                images, targets, strong = images.to(device), targets.to(device), strong.to(device)
                if policy.get("campaign_only") and not (targets != 255).any():
                    raise ValueError("Campaign batch has no supervised pixels")
                if not policy.get("campaign_only") and not (strong & (targets != 255).flatten(1).any(1)).any():
                    raise ValueError("Batch has no usable binary reference pixels after resize")
                optimizer.zero_grad(set_to_none=True)
                with autocast(device, precision):
                    logits = model(images)["out"]
                    loss, binary_loss, partial_loss = (loss_function or segmentation_loss)(logits, targets, strong, args.partial_weight)
                if not torch.isfinite(loss):
                    raise RuntimeError("Non-finite loss; stopping without saving bad weights")
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                norm = nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                if precision != "fp16" and not torch.isfinite(norm):
                    raise RuntimeError("Non-finite gradients")
                previous_scale = scaler.get_scale()
                scaler.step(optimizer)
                scaler.update()
                updates += int(scaler.get_scale() >= previous_scale)
                totals += [float(loss.detach()), float(binary_loss.detach()), float(partial_loss.detach())]
                steps += 1
                components = {f"loss_{name}": float(value)
                              for name, value in getattr(loss_function, "last_metrics", {}).items()}
                component_totals.update(components)
                interval = cfg.get("training_policy", {}).get("batch_log_interval", 0)
                if tracker and interval and (steps == 1 or steps % interval == 0):
                    tracker.run.log({"train_step": epoch * len(sampler) + steps,
                                     "batch/loss": float(loss.detach()),
                                     "batch/binary_loss": float(binary_loss.detach()),
                                     "batch/weak_loss": float(partial_loss.detach()),
                                     "batch/epoch_progress": epoch + steps / len(sampler),
                                     **{f"batch/{name}": value for name, value in components.items()}})
                if steps == 1 or steps % 20 == 0:
                    print(f"epoch={epoch + 1} step={steps}/{len(sampler)} loss={float(loss.detach()):.4f}", flush=True)
                if args.smoke and (updates >= 2 or steps >= 10):
                    break
            if updates == 0 or (args.smoke and updates < 2):
                raise RuntimeError("Insufficient successful optimizer updates; not saving a misleading checkpoint")
            report = evaluate(model, dataset, validation_rows, size, device, precision,
                              preview_dir=output / f"validation-epoch-{epoch + 1:03d}", limit=2 if args.smoke else 0,
                              **({"boundaries": True} if smart_selection else {}),
                              **({"campaign_only": True} if policy.get("campaign_only") else {}))
            iou = report["binary_reference"]["sidewalk_iou"]
            if iou is None or not math.isfinite(iou):
                raise RuntimeError("Validation has no finite sidewalk IoU")
            improved = iou > best_iou
            best_iou, stale = (iou, 0) if improved else (best_iou, stale + 1)
            row = {"epoch": epoch + 1, "steps": steps, "optimizer_updates": updates, "skipped_updates": steps - updates,
                   "loss": float(totals[0] / steps),
                   "binary_loss": float(totals[1] / steps), "partial_loss": float(totals[2] / steps),
                   "validation_sidewalk_iou": iou, "validation_precision": report["binary_reference"]["precision"],
                   "validation_recall": report["binary_reference"]["recall"], "validation_f1": report["binary_reference"]["f1"],
                   "backbone_lr": optimizer.param_groups[0]["lr"], "head_lr": optimizer.param_groups[1]["lr"],
                   "elapsed_seconds": time.monotonic() - began}
            row.update({name: value / steps for name, value in component_totals.items()})
            if smart_selection:
                row["validation_boundary_f1"] = report["binary_reference"]["boundary_f1"]
            history.append(row)
            scheduler.step()
            state = {"schema": "sidewalkpilot-series5-binary-checkpoint-v1", "config": cfg, "data_identity": identity,
                     "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                     "scaler": scaler.state_dict(), "epoch": epoch + 1, "best_iou": best_iou,
                     "stale_epochs": stale, "history": history}
            if improved:
                atomic_checkpoint(output / "best.pt", state)
            if (smart_selection and not args.smoke and row["validation_precision"] is not None
                    and eligible(iou, best_iou)):
                candidate = output / candidate_path(epoch + 1)
                candidate.parent.mkdir(exist_ok=True)
                atomic_checkpoint(candidate, state)
                snapshot(candidate, output / "last.pt")
            else:
                atomic_checkpoint(output / "last.pt", state)
            write_json(output / f"validation-{epoch + 1:03d}.json", report)
            save_history(output, history)
            if tracker:
                tracker.push(epoch + 1, row)
            print(json.dumps(row), flush=True)
        status = {"status": "smoke-complete" if args.smoke else "complete", "epochs_completed": len(history),
                  "best_validation_sidewalk_iou": best_iou, "early_stopped": stale >= args.patience, "test_evaluated": False}
        write_json(output / "status.json", status)
        if tracker:
            tracker.run.summary.update(status)
        exit_code = 0
    except KeyboardInterrupt:
        exit_code = 130
        write_json(output / "status.json", {"status": "interrupted", "resume": "last.pt is the last completed epoch, not the interrupted batch"})
        raise
    finally:
        if tracker:
            tracker.finish(exit_code=exit_code)
    return {"run": str(output), "status": "smoke-complete" if args.smoke else "complete", "test_evaluated": False}


def evaluate_checkpoint(args, *, model_definition=None, partition_loader=None):
    partitions = (partition_loader or load_partition)(args.dataset.resolve(), args.split)
    model, state = load_checkpoint(args.checkpoint, model_definition=model_definition)
    identity = {"manifest_sha256": sha256(args.dataset / "manifest.json"), "split_sha256": sha256(args.split)}
    if identity != state["data_identity"]:
        raise ValueError("Checkpoint dataset/split identity differs")
    if args.partition == "test" and state["config"]["smoke_only"]:
        raise ValueError("A smoke checkpoint must not be evaluated as a test model")
    if args.output.exists() or args.output.resolve().is_relative_to(args.dataset.resolve()):
        raise ValueError("Use a new evaluation directory outside the dataset")
    device = torch.device(args.device)
    precision = select_precision(args.precision, device)
    if model_definition:
        model_definition.validate_precision(precision)
    args.output.mkdir(parents=True)
    cfg = state["config"]
    result = evaluate(model.to(device), args.dataset.resolve(), partitions[args.partition], (cfg["width"], cfg["height"]),
                      device, precision, preview_dir=args.output / "previews",
                      campaign_only=cfg.get("training_policy", {}).get("campaign_only", False),
                      boundaries=cfg.get("training_policy", {}).get("smart_selection") == SMART_RULE)
    result.update(partition=args.partition, checkpoint_sha256=sha256(args.checkpoint), precision=precision,
                  data_identity=identity, smoke_only=cfg["smoke_only"])
    write_json(args.output / "metrics.json", result)
    return result


@torch.inference_mode()
def predict(args, *, model_definition=None):
    if args.output.exists() or args.image.resolve().is_relative_to(args.output.resolve()):
        raise ValueError("Use a new prediction output directory")
    model, state = load_checkpoint(args.checkpoint, model_definition=model_definition)
    cfg, device = state["config"], torch.device(args.device)
    precision = select_precision(args.precision, device)
    if model_definition:
        model_definition.validate_precision(precision)
    with Image.open(args.image) as source:
        original = source.convert("RGB")
    tensor = TVF.normalize(TVF.to_tensor(original.resize((cfg["width"], cfg["height"]), Image.Resampling.BILINEAR)), MEAN, STD)
    model.to(device).eval()
    with autocast(device, precision):
        logits = model(tensor.unsqueeze(0).to(device))["out"]
    labels = F.interpolate(logits.float(), size=(original.height, original.width), mode="bilinear",
                           align_corners=False).argmax(1)[0].cpu().numpy().astype(np.uint8)
    args.output.mkdir(parents=True)
    Image.fromarray(labels).save(args.output / "mask.png")
    rgb = np.array(original, dtype=np.float32)
    rgb[labels == 1] = 0.55 * rgb[labels == 1] + 0.45 * np.array((30, 210, 140))
    Image.fromarray(rgb.astype(np.uint8)).save(args.output / "overlay.jpg")
    result = {"image_sha256": sha256(args.image), "checkpoint_sha256": sha256(args.checkpoint),
              "mask_sha256": sha256(args.output / "mask.png"), "precision": precision,
              "smoke_only": cfg["smoke_only"], "size": list(original.size),
              "warning": "Predicted pixels are not verified labels. No steering or metric-width calculation."}
    write_json(args.output / "prediction.json", result)
    return result


def run_a():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("split")
    prepare.add_argument("--dataset", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    for name in PARTITIONS:
        prepare.add_argument(f"--{name}-days", nargs="+", default=DEFAULTS[f"{name}_days"])
    training = commands.add_parser("train")
    scoring = commands.add_parser("evaluate")
    prediction = commands.add_parser("predict")
    for command in (training, scoring, prediction):
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
        command.add_argument("--precision", choices=("auto", "fp32", "fp16", "bf16"), default="auto")
    for command in (training, scoring):
        command.add_argument("--dataset", type=Path, required=True)
        command.add_argument("--split", type=Path, required=True)
    for command in (scoring, prediction):
        command.add_argument("--checkpoint", type=Path, required=True)
    scoring.add_argument("--partition", choices=("validation", "test"), default="validation")
    prediction.add_argument("--image", type=Path, required=True)
    for name in ("width", "height", "batch_size", "epochs", "patience", "seed"):
        training.add_argument("--" + name.replace("_", "-"), type=int, default=DEFAULTS[name])
    for name in ("backbone_lr", "head_lr", "weight_decay", "partial_weight"):
        training.add_argument("--" + name.replace("_", "-"), type=float, default=DEFAULTS[name])
    training.add_argument("--weights", choices=("imagenet", "none"), default="imagenet")
    training.add_argument("--workers", type=int, default=2)
    training.add_argument("--resume", action="store_true")
    training.add_argument("--smoke", action="store_true", help="Two update attempts and two validation references; not a trained model")
    training.add_argument("--wandb", action=argparse.BooleanOptionalAction, default=True,
                          help="Log metrics to Sidewalk-Pilot/SidewalkPilot (default on; --no-wandb keeps everything local)")
    args = parser.parse_args()
    if args.command == "split":
        result = create_split(args.dataset, args.output, {name: getattr(args, name + "_days") for name in PARTITIONS})
    elif args.command == "train":
        result = train(args)
    elif args.command == "evaluate":
        result = evaluate_checkpoint(args)
    else:
        result = predict(args)
    print(json.dumps(result, indent=2), flush=True)


# 5.B screened pseudo-label recipe
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


class CampaignSampler:
    def __init__(self, rows, batch_size, seed):
        self.n,self.batch_size,self.seed,self.epoch=len(rows),batch_size,seed,0

    def __len__(self):
        return (self.n+self.batch_size-1)//self.batch_size

    def __iter__(self):
        rng=random.Random(self.seed+self.epoch)
        ids=list(range(self.n))
        rng.shuffle(ids)
        for k in range(0,self.n,self.batch_size):
            yield [(i,rng.getrandbits(32)) for i in ids[k:k+self.batch_size]]


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


def run_b():
    from prepare_series5_pseudo_dataset import load_mixed_partition
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
        "dataset_loader_sha256": sha256(workspace.source_path("prepare_series5_pseudo_dataset.py")),
    }
    result = train(args, partition_loader=load_mixed_partition,
                   sampler_class=ScreenedBatchSampler, loss_function=conservative_loss)
    print(json.dumps(result, indent=2))


# 5.C and 5.E ConvNeXt recipes
CONVNEXT_DEFAULTS = read_json(workspace.CONFIGS / "series_5_c_config.json")


def load_convnext_partition(dataset, split):
    from prepare_series5_pseudo_dataset import load_mixed_partition
    manifest = read_json(dataset / "manifest.json")
    if manifest.get("schema") == "sidewalkpilot-campaign10k-v1":
        return campaign10k.load(dataset, split)
    if manifest.get("schema") == "sidewalkpilot-mixed-pseudo-dataset-v1":
        return load_mixed_partition(dataset, split)
    return load_partition(dataset, split)


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
    loss_function = ReviewedFocalLoss(
        gamma=args.focal_gamma, background_weight=args.background_weight,
        sidewalk_weight=args.sidewalk_weight, class_weight_cap=args.class_weight_cap,
        dice_weight=args.dice_weight if args.loss == "focal-dice" else 0.0)
    args.model_name = variant
    trainer_hash = sha256(Path(__file__))
    args.experiment = CONVNEXT_DEFAULTS["experiment"].replace("5.C",variant)
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
        "model_sha256": trainer_hash,
        "base_trainer_sha256": trainer_hash,
        "sampler_sha256": trainer_hash,
        "loss_sha256": trainer_hash,
        "boundary_metrics_sha256": trainer_hash,
        "checkpoint_naming_sha256": trainer_hash,
        "checkpoint_names": checkpoint_names(args.model_name),
        "smart_selection": SMART_RULE,
        "boundary_tolerance_px": RADIUS,
    }
    if campaign:
        args.training_policy.update(campaign_only=True, human_references_per_batch=0,
            encoder_frozen_epochs=2 if variant=="5.E" else 0,
            scope="8000/1000/1000; validation and test quantify agreement with original SAM 3 pseudo-labels.",
            dataset_loader_sha256=sha256(Path(campaign10k.__file__)))
    result = train(args, partition_loader=load_convnext_partition, sampler_class=CampaignSampler if campaign else ScreenedBatchSampler,
                        loss_function=loss_function, model_definition=ConvNeXtRecipe)
    if not args.smoke and result["status"] == "complete":
        result["checkpoint_selection"] = publish_completed_run(args.output, args.model_name)
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
        training.add_argument("--" + key.replace("_", "-"), type=int, default=CONVNEXT_DEFAULTS[key])
    for key in ("backbone_lr", "head_lr", "weight_decay", "partial_weight", "focal_gamma",
                "background_weight", "sidewalk_weight", "class_weight_cap", "dice_weight"):
        training.add_argument("--" + key.replace("_", "-"), type=float, default=CONVNEXT_DEFAULTS[key])
    training.add_argument("--workers", type=int, default=2)
    training.add_argument("--loss", choices=("focal", "focal-dice"), default=CONVNEXT_DEFAULTS["loss"])
    training.add_argument("--weights", choices=("imagenet", "none"), default="imagenet")
    training.add_argument("--resume", action="store_true")
    training.add_argument("--smoke", action="store_true")
    training.add_argument("--wandb", action=argparse.BooleanOptionalAction, default=True)
    return result


def run_convnext(variant="5.C"):
    args = parser().parse_args()
    if args.command == "train":
        result = run_training(args,variant)
    elif args.command == "evaluate":
        result = evaluate_checkpoint(args, model_definition=ConvNeXtRecipe, partition_loader=load_convnext_partition)
    else:
        result = predict(args, model_definition=ConvNeXtRecipe)
    print(json.dumps(result, indent=2))


def run_fixed_experiment(recipe):
    if recipe == "5.A":
        return run_a()
    if recipe == "5.B":
        return run_b()
    if recipe in ("5.C", "5.E"):
        return run_convnext(recipe)
    raise ValueError(f"Unknown training recipe: {recipe}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(usage="%(prog)s {5.A,5.B,5.C,5.E} [recipe options]")
    cli.add_argument("recipe", choices=("5.A", "5.B", "5.C", "5.E"))
    recipe = cli.parse_args(sys.argv[1:2]).recipe
    del sys.argv[1]
    run_fixed_experiment(recipe)
