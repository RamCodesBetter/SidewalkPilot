#!/usr/bin/env python3
"""Train model 5.A, a reviewed/partial-label binary Series 5 beta baseline."""

import argparse
from collections import Counter
from contextlib import nullcontext
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

from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from prepare_reviewed_dataset import read_json, safe_file, verify_dataset


HERE = Path(__file__).resolve().parent
DEFAULTS = read_json(HERE / "series_5_a_config.json")
ARCHITECTURE = "lraspp_mobilenet_v3_large"
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
PARTITIONS = ("train", "validation", "test")


def recording_day(row):
    return row["recording_run"].rsplit("_run_", 1)[0]


def validate_split(manifest, split, manifest_hash):
    if split.get("schema") != "sidewalkpilot-binary-day-split-v1" or split["manifest_sha256"] != manifest_hash:
        raise ValueError("Split does not belong to this dataset manifest")
    usable = {row["id"]: row for row in manifest["records"] if row["included"]}
    partitions, seen_ids, seen_days = {}, set(), set()
    for name in PARTITIONS:
        ids = split["partitions"][name]
        if not ids or len(set(ids)) != len(ids) or seen_ids.intersection(ids) or not set(ids) <= usable.keys():
            raise ValueError("Empty, duplicate, overlapping, or unknown split images")
        rows = [usable[identifier] for identifier in ids]
        days = {recording_day(row) for row in rows}
        if seen_days & days or days != set(split["days"][name]):
            raise ValueError("Recording day leaks across partitions or differs from declared days")
        references = [row for row in rows if row["supervision"] == "binary-reference"]
        if not references or any(sum(row["pixel_counts"].get(label, 0) for row in references) == 0 for label in ("0", "1")):
            raise ValueError("Every partition needs reviewed positive AND negative reference pixels")
        partitions[name] = rows
        seen_ids.update(ids)
        seen_days.update(days)
    if seen_ids != usable.keys():
        raise ValueError("Split does not cover all usable images")
    return partitions


def create_split(dataset, output, days):
    dataset, output = Path(dataset).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(dataset):
        raise ValueError("Use a new split file outside the verified dataset")
    verify_dataset(dataset)
    manifest = read_json(dataset / "manifest.json")
    split = {
        "schema": "sidewalkpilot-binary-day-split-v1", "created_utc": utc_now(),
        "manifest_sha256": sha256(dataset / "manifest.json"), "days": days,
        "partitions": {name: sorted(row["id"] for row in manifest["records"]
                                    if row["included"] and recording_day(row) in days[name]) for name in PARTITIONS},
        "purpose": "Development baseline only; not the submitted study's final 80/10/10 split.",
        "limitations": "Same-day runs stay together. Different days may revisit the same route; visual/geographic independence is not established. These labels were already reviewed during development.",
    }
    partitions = validate_split(manifest, split, split["manifest_sha256"])
    split["summary"] = {name: {"images": len(rows), "fraction": len(rows) / sum(map(len, partitions.values())),
                               "binary_references": sum(row["supervision"] == "binary-reference" for row in rows),
                               "recording_runs": sorted({row["recording_run"] for row in rows})}
                        for name, rows in partitions.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, split)
    return split["summary"]


def load_partition(dataset, split_path):
    verify_dataset(dataset)
    manifest, split = read_json(dataset / "manifest.json"), read_json(split_path)
    return validate_split(manifest, split, sha256(dataset / "manifest.json"))


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
def evaluate(model, dataset, rows, size, device, precision, preview_dir=None, limit=0):
    model.eval()
    data = SidewalkDataset(dataset, rows, size, original_targets=True)
    counts = torch.zeros((2, 2), dtype=torch.int64)
    reference_images, partial_images, partial_tp, partial_total = 0, 0, 0, 0
    per_image = []
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
        if strong:
            current = confusion_counts(prediction, target)
            counts += current
            reference_images += 1
            per_image.append({"id": rows[index]["id"], **confusion_metrics(current)})
            if preview_dir and reference_images <= 4:
                save_preview(safe_file(dataset, rows[index]["image"]), prediction.numpy(), target.numpy(),
                             preview_dir / f"{reference_images:02d}.jpg")
        else:
            partial_images += 1
            positive = target == 1
            partial_total += int(positive.sum())
            partial_tp += int(((prediction == 1) & positive).sum())
    return {
        "binary_reference": {"images": reference_images, **confusion_metrics(counts)},
        "partial_labels": {"images": partial_images, "known_sidewalk_pixels": partial_total,
                           "known_sidewalk_recall_only": partial_tp / partial_total if partial_total else None,
                           "warning": "Positive-only masks cannot measure false positives, IoU, precision, or F1."},
        "per_binary_reference_image": per_image,
        "evaluation_resolution": "Original reference resolution; bilinear logits resize before argmax; ignored pixels excluded.",
        "limitations": "Development labels, not independent test ground truth. Only binary references select checkpoints.",
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
    sys.path.insert(0, str(HERE.parents[1] / "series_3_and_4"))
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
            totals, steps, updates = np.zeros(3), 0, 0
            for images, targets, strong, _ in loader:
                images, targets, strong = images.to(device), targets.to(device), strong.to(device)
                if not (strong & (targets != 255).flatten(1).any(1)).any():
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
                interval = cfg.get("training_policy", {}).get("batch_log_interval", 0)
                if tracker and interval and (steps == 1 or steps % interval == 0):
                    tracker.run.log({"train_step": epoch * len(sampler) + steps,
                                     "batch/loss": float(loss.detach()),
                                     "batch/binary_loss": float(binary_loss.detach()),
                                     "batch/weak_loss": float(partial_loss.detach()),
                                     "batch/epoch_progress": epoch + steps / len(sampler)})
                if steps == 1 or steps % 20 == 0:
                    print(f"epoch={epoch + 1} step={steps}/{len(sampler)} loss={float(loss.detach()):.4f}", flush=True)
                if args.smoke and (updates >= 2 or steps >= 10):
                    break
            if updates == 0 or (args.smoke and updates < 2):
                raise RuntimeError("Insufficient successful optimizer updates; not saving a misleading checkpoint")
            report = evaluate(model, dataset, validation_rows, size, device, precision,
                              preview_dir=output / f"validation-epoch-{epoch + 1:03d}", limit=2 if args.smoke else 0)
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
            history.append(row)
            scheduler.step()
            state = {"schema": "sidewalkpilot-series5-binary-checkpoint-v1", "config": cfg, "data_identity": identity,
                     "model": model.state_dict(), "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict(),
                     "scaler": scaler.state_dict(), "epoch": epoch + 1, "best_iou": best_iou,
                     "stale_epochs": stale, "history": history}
            if improved:
                atomic_checkpoint(output / "best.pt", state)
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
                      device, precision, preview_dir=args.output / "previews")
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


def main():
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


if __name__ == "__main__":
    main()
