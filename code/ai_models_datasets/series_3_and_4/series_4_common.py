#!/usr/bin/env python3
"""Shared temporal training engine for the experimental SidewalkPilot Series 4 models."""

from __future__ import annotations

import argparse
import importlib.util
import math
import random
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODELS_DIR = REPO_ROOT / "code" / "ai_models"
SERIES3_TRAINER = SCRIPT_DIR / "series_3_sidewalkpilot_trainer.py"


def _load_series3_module():
    spec = importlib.util.spec_from_file_location("sidewalkpilot_series3_trainer", SERIES3_TRAINER)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load Series 3 trainer from {SERIES3_TRAINER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


S3 = _load_series3_module()


def _select_device() -> str:
    # The RTX workstation can briefly report CUDA unavailable while the driver
    # finishes initializing. Never silently launch a full training run on CPU.
    for _ in range(5):
        try:
            torch.empty(1, device="cuda")
            return "cuda"
        except (AssertionError, RuntimeError):
            pass
        time.sleep(0.25)
    return "cpu"


DEVICE = _select_device()
S3.DEVICE = DEVICE
NUM_STEER_CLASSES = S3.NUM_STEER_CLASSES
SERIES4_OUTPUTS_PER_HORIZON = 2 * NUM_STEER_CLASSES


CONTRACTS = {
    "pc": {"uses_history": True, "uses_future": False},
    "cf": {"uses_history": False, "uses_future": True},
    "pcf": {"uses_history": True, "uses_future": True},
}

_PHOTO_NAME_RE = re.compile(
    r"^(?P<run>.+)__photo_(?P<date>\d{8})_(?P<clock>\d{6})_(?P<micro>\d{6})\.(?:jpe?g|png)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FrameRecord:
    index: int
    path: Path
    steering: float
    source: str
    run_key: str
    timestamp: float | None


@dataclass(frozen=True)
class TemporalSample:
    anchor: FrameRecord
    history: tuple[float, ...]
    targets: tuple[float, ...]
    split: str


def parse_photo_identity(path: Path, root: Path) -> tuple[str, float | None]:
    match = _PHOTO_NAME_RE.match(path.name)
    if match is None:
        return f"{root.resolve()}::{path.parent.resolve()}", None
    stamp = datetime.strptime(
        match.group("date") + match.group("clock"), "%Y%m%d%H%M%S"
    ).timestamp()
    stamp += int(match.group("micro")) / 1_000_000.0
    return f"{root.resolve()}::{match.group('run')}", stamp


def discover_roots(raw_roots: Sequence[str] | None) -> list[Path]:
    if raw_roots:
        roots = []
        for raw in raw_roots:
            path = Path(raw).expanduser()
            candidates = [path] if path.is_absolute() else [Path.cwd() / path, SCRIPT_DIR / path]
            matched = next((candidate.resolve() for candidate in candidates if (candidate / "labels.json").is_file()), None)
            if matched is None:
                raise FileNotFoundError(f"Dataset root does not contain labels.json: {raw}")
            roots.append(matched)
        return roots

    default = SCRIPT_DIR / "sidewalkpilot_dataset"
    if (default / "labels.json").is_file():
        return [default.resolve()]
    raise FileNotFoundError(f"Shared Series 3/4 dataset not found at {default}")


def load_frames(roots: Sequence[Path], limit_frames: int = 0) -> list[FrameRecord]:
    frames: list[FrameRecord] = []
    missing = 0
    bad = 0
    for root in roots:
        items = S3.load_label_items(root / "labels.json")
        label_mode = S3.infer_label_mode(items)
        source = S3.source_name_for_root(root)
        for item in items:
            image_path = S3.resolve_image_path(root, item)
            if image_path is None:
                missing += 1
                continue
            try:
                steering = S3.label_to_servo(S3.get_raw_steering(item, None), label_mode)
            except (TypeError, ValueError):
                bad += 1
                continue
            run_key, timestamp = parse_photo_identity(image_path, root)
            frames.append(
                FrameRecord(
                    index=len(frames),
                    path=image_path.resolve(),
                    steering=float(steering),
                    source=source,
                    run_key=run_key,
                    timestamp=timestamp,
                )
            )
            if limit_frames > 0 and len(frames) >= limit_frames:
                break
        if limit_frames > 0 and len(frames) >= limit_frames:
            break
    if not frames:
        raise FileNotFoundError("No usable labeled frames were found.")
    print(f"[dataset] frames={len(frames)} missing={missing} bad={bad} runs={len({f.run_key for f in frames})}")
    return frames


def frozen_series3_split(
    frames: Sequence[FrameRecord], val_fraction: float = 0.10, window_size: int = 100
) -> tuple[dict[int, str], dict[str, int]]:
    """Reproduce the Series 3 path-sorted, strided 100-frame validation split."""
    order = sorted(range(len(frames)), key=lambda i: str(frames[i].path))
    count = len(order)
    window_size = max(1, int(window_size))
    num_windows = max(1, math.ceil(count / window_size))
    val_windows = max(1, round(num_windows * float(val_fraction)))
    stride = max(1, num_windows // val_windows)
    split_by_frame: dict[int, str] = {}
    for window_index in range(num_windows):
        split = "val" if window_index % stride == 0 else "train"
        for ordered_index in order[window_index * window_size : (window_index + 1) * window_size]:
            split_by_frame[frames[ordered_index].index] = split
    if len(set(split_by_frame.values())) < 2:
        cut = max(1, int(count * float(val_fraction)))
        split_by_frame = {frames[i].index: "train" for i in order[:-cut]}
        split_by_frame.update({frames[i].index: "val" for i in order[-cut:]})
    counts = Counter(split_by_frame.values())
    print(
        f"[split] frozen Series 3 split: train={counts['train']} val={counts['val']} "
        f"windows={num_windows}x{window_size} stride={stride}"
    )
    return split_by_frame, {"num_windows": num_windows, "window_size": window_size, "stride": stride}


def _window_has_bad_gap(frames: Sequence[FrameRecord], max_gap_sec: float) -> bool:
    if max_gap_sec <= 0:
        return False
    for left, right in zip(frames, frames[1:]):
        if left.timestamp is None or right.timestamp is None:
            continue
        gap = right.timestamp - left.timestamp
        if gap <= 0.0 or gap > max_gap_sec:
            return True
    return False


def build_temporal_samples(
    frames: Sequence[FrameRecord],
    split_by_frame: dict[int, str],
    history_steps: int,
    future_steps: int,
    max_gap_sec: float = 0.25,
) -> tuple[list[TemporalSample], dict[str, int]]:
    history_steps = max(0, int(history_steps))
    future_steps = max(0, int(future_steps))
    by_run: dict[str, list[FrameRecord]] = defaultdict(list)
    for frame in frames:
        by_run[frame.run_key].append(frame)

    samples: list[TemporalSample] = []
    rejected_split = 0
    rejected_gap = 0
    for run_frames in by_run.values():
        run_frames.sort(key=lambda frame: (frame.timestamp is None, frame.timestamp or 0.0, str(frame.path)))
        for anchor_pos in range(history_steps, len(run_frames) - future_steps):
            window = run_frames[anchor_pos - history_steps : anchor_pos + future_steps + 1]
            splits = {split_by_frame[frame.index] for frame in window}
            if len(splits) != 1:
                rejected_split += 1
                continue
            if _window_has_bad_gap(window, max_gap_sec):
                rejected_gap += 1
                continue
            anchor = run_frames[anchor_pos]
            history = tuple(frame.steering for frame in run_frames[anchor_pos - history_steps : anchor_pos])
            targets = tuple(frame.steering for frame in run_frames[anchor_pos : anchor_pos + future_steps + 1])
            samples.append(TemporalSample(anchor, history, targets, next(iter(splits))))

    counts = Counter(sample.split for sample in samples)
    stats = {
        "train": counts["train"],
        "val": counts["val"],
        "rejected_split": rejected_split,
        "rejected_gap": rejected_gap,
    }
    print(
        f"[sequence] history={history_steps} future={future_steps} train={counts['train']} "
        f"val={counts['val']} rejected_split={rejected_split} rejected_gap={rejected_gap}"
    )
    if not counts["train"] or not counts["val"]:
        raise ValueError("Temporal filtering left an empty train or validation split.")
    return samples, stats


def mirror_angles(values: np.ndarray) -> np.ndarray:
    return 180.0 - values


class Series4Dataset(Dataset):
    def __init__(
        self,
        samples: Sequence[TemporalSample],
        width: int = 320,
        height: int = 180,
        crop_top_ratio: float = 0.0,
        augment: bool = False,
        flip_probability: float = 0.0,
        shadow_probability: float = 0.6,
        hsv_probability: float = 0.0,
        clahe_probability: float = 0.0,
        history_noise_deg: float = 0.0,
        history_dropout_probability: float = 0.0,
        history_sequence_dropout_probability: float = 0.0,
        history_walk_noise_deg: float = 0.0,
    ):
        self.samples = list(samples)
        self.width = int(width)
        self.height = int(height)
        self.crop_top_ratio = float(crop_top_ratio)
        self.augment = bool(augment)
        self.flip_probability = float(np.clip(flip_probability, 0.0, 1.0))
        self.shadow_probability = float(np.clip(shadow_probability, 0.0, 1.0))
        self.hsv_probability = float(np.clip(hsv_probability, 0.0, 1.0))
        self.clahe_probability = float(np.clip(clahe_probability, 0.0, 1.0))
        self.history_noise_deg = max(0.0, float(history_noise_deg))
        self.history_dropout_probability = float(np.clip(history_dropout_probability, 0.0, 1.0))
        self.history_sequence_dropout_probability = float(
            np.clip(history_sequence_dropout_probability, 0.0, 1.0)
        )
        self.history_walk_noise_deg = max(0.0, float(history_walk_noise_deg))
        self.forced_flip = [False] * len(self.samples)

    def __len__(self) -> int:
        return len(self.samples)

    def current_target(self, index: int) -> float:
        target = self.samples[index].targets[0]
        return 180.0 - target if self.forced_flip[index] else target

    def apply_balance_flip(self, max_passes: int = 15) -> int:
        moved_total = 0
        for _ in range(max_passes):
            by_bucket: dict[int, list[int]] = defaultdict(list)
            for index in range(len(self.samples)):
                by_bucket[S3.steer_class_index(self.current_target(index))].append(index)
            moved = 0
            for left_class, right_class in ((0, 8), (1, 7), (2, 6), (3, 5)):
                left = by_bucket[left_class]
                right = by_bucket[right_class]
                difference = len(left) - len(right)
                if abs(difference) <= 1:
                    continue
                larger = left if difference > 0 else right
                for index in larger[: abs(difference) // 2]:
                    self.forced_flip[index] = not self.forced_flip[index]
                    moved += 1
            moved_total += moved
            if moved == 0:
                break
        self.flip_probability = 0.0
        print(f"[balance] deterministic sequence flips={moved_total}; random flip disabled")
        return moved_total

    def __getitem__(self, index: int):
        sample = self.samples[index]
        image = cv2.imread(str(sample.anchor.path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(sample.anchor.path)
        image = S3.resize_image_uint8(image, self.width, self.height, self.crop_top_ratio)

        history = np.asarray(sample.history, dtype=np.float32)
        targets = np.asarray(sample.targets, dtype=np.float32)

        if self.augment:
            should_flip = self.forced_flip[index]
            if not should_flip and (targets[0] < 85.0 or targets[0] >= 95.0):
                should_flip = random.random() < self.flip_probability
            if should_flip:
                image = cv2.flip(image, 1)
                history = mirror_angles(history)
                targets = mirror_angles(targets)

            original_current = float(targets[0])
            image, augmented_current = S3.augment_image(
                image,
                original_current,
                sample.anchor.source,
                self.shadow_probability,
                0.0,
                self.hsv_probability,
                self.clahe_probability,
            )
            steering_shift = float(augmented_current) - original_current
            if steering_shift:
                history = np.clip(history + steering_shift, 0.0, 180.0)
                targets = np.clip(targets + steering_shift, 0.0, 180.0)

            if (
                history.size
                and self.history_sequence_dropout_probability > 0.0
                and random.random() < self.history_sequence_dropout_probability
            ):
                history.fill(90.0)
            elif history.size and self.history_dropout_probability > 0.0:
                mask = np.random.random(history.shape) < self.history_dropout_probability
                previous = np.concatenate((history[:1], history[:-1]))
                history = np.where(mask, previous, history)
            if history.size and self.history_noise_deg > 0.0:
                noise = np.random.normal(0.0, self.history_noise_deg, history.shape)
                history = np.clip(history + noise, 0.0, 180.0)
            if history.size and self.history_walk_noise_deg > 0.0:
                increments = np.random.normal(0.0, self.history_walk_noise_deg, history.shape)
                history = np.clip(history + np.cumsum(increments), 0.0, 180.0)

        return (
            S3.image_to_tensor(image),
            torch.from_numpy(history.astype(np.float32, copy=False)),
            torch.from_numpy(targets.astype(np.float32, copy=False)),
        )


class SidewalkPilotV4(nn.Module):
    """Series 3 visual backbone with optional causal history fusion and horizon heads."""

    def __init__(
        self,
        history_steps: int,
        future_steps: int,
        history_representation: str = "absolute",
        history_fusion_mode: str = "full",
        history_logit_residual_scale: float = 0.35,
        history_offset_residual_scale: float = 0.35,
    ):
        super().__init__()
        self.history_steps = int(history_steps)
        self.future_steps = int(future_steps)
        self.history_representation = str(history_representation)
        self.history_fusion_mode = str(history_fusion_mode)
        self.history_logit_residual_scale = float(history_logit_residual_scale)
        self.history_offset_residual_scale = float(history_offset_residual_scale)
        if self.history_representation not in {"absolute", "delta_motion"}:
            raise ValueError(f"Unknown history representation: {self.history_representation}")
        if self.history_fusion_mode not in {"full", "bounded_residual"}:
            raise ValueError(f"Unknown history fusion mode: {self.history_fusion_mode}")
        if self.history_representation == "delta_motion" and self.history_steps < 3:
            raise ValueError("delta_motion history requires at least three previous targets")
        if self.history_fusion_mode == "bounded_residual" and not self.history_steps:
            raise ValueError("bounded_residual fusion requires target history")
        self.backbone = S3.SidewalkPilotV3().backbone
        self.image_encoder = nn.Sequential(
            nn.AdaptiveAvgPool2d((6, 10)),
            nn.Flatten(),
            nn.Linear(160 * 6 * 10, 512),
            nn.ELU(inplace=True),
            nn.Dropout(p=0.18),
            nn.Linear(512, 256),
            nn.ELU(inplace=True),
            nn.Dropout(p=0.12),
        )
        if self.history_steps and self.history_fusion_mode == "full":
            self.history_encoder = nn.Sequential(
                nn.Linear(self.history_steps, 32),
                nn.ELU(inplace=True),
                nn.Linear(32, 64),
                nn.ELU(inplace=True),
            )
            self.fusion = nn.Sequential(
                nn.Linear(320, 128),
                nn.ELU(inplace=True),
                nn.Dropout(p=0.12),
                nn.Linear(128, 64),
                nn.ELU(inplace=True),
            )
            self.history_residual_heads = None
        else:
            self.history_encoder = None
            self.fusion = nn.Sequential(nn.Linear(256, 64), nn.ELU(inplace=True))
            if self.history_steps:
                history_features = 3 if self.history_representation == "delta_motion" else self.history_steps
                self.history_encoder = nn.Sequential(
                    nn.Linear(history_features, 32),
                    nn.ELU(inplace=True),
                    nn.Linear(32, 64),
                    nn.ELU(inplace=True),
                )
                self.history_residual_heads = nn.ModuleList(
                    nn.Linear(64, SERIES4_OUTPUTS_PER_HORIZON)
                    for _ in range(self.future_steps + 1)
                )
            else:
                self.history_residual_heads = None
        self.horizon_heads = nn.ModuleList(
            nn.Linear(64, SERIES4_OUTPUTS_PER_HORIZON) for _ in range(self.future_steps + 1)
        )

    def history_features(self, target_history: torch.Tensor) -> torch.Tensor:
        if self.history_representation == "absolute":
            return (target_history - 90.0) / 90.0
        recent = target_history[:, -3:]
        first_delta = recent[:, 1] - recent[:, 0]
        second_delta = recent[:, 2] - recent[:, 1]
        acceleration = second_delta - first_delta
        return torch.stack((first_delta, second_delta, acceleration), dim=1) / 90.0

    def forward(self, image: torch.Tensor, target_history: torch.Tensor | None = None) -> torch.Tensor:
        visual = self.image_encoder(self.backbone(image))
        if self.history_steps and target_history is None:
            raise ValueError("This Series 4 model requires target_history.")
        if self.history_steps and self.history_fusion_mode == "full":
            fused = self.fusion(
                torch.cat((visual, self.history_encoder(self.history_features(target_history))), dim=1)
            )
        else:
            fused = self.fusion(visual)
        visual_outputs = torch.stack([head(fused) for head in self.horizon_heads], dim=1)
        if self.history_residual_heads is None:
            return visual_outputs
        history_embedding = self.history_encoder(self.history_features(target_history))
        residual = torch.stack(
            [head(history_embedding) for head in self.history_residual_heads], dim=1
        )
        logit_residual, offset_residual = split_hybrid_output(residual)
        bounded_residual = torch.cat(
            (
                torch.tanh(logit_residual) * self.history_logit_residual_scale,
                torch.tanh(offset_residual) * self.history_offset_residual_scale,
            ),
            dim=-1,
        )
        return visual_outputs + bounded_residual


def split_hybrid_output(output: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    return output[..., :NUM_STEER_CLASSES], output[..., NUM_STEER_CLASSES:]


def decode_hybrid(output: torch.Tensor) -> torch.Tensor:
    logits, offset_raw = split_hybrid_output(output)
    classes = torch.argmax(logits, dim=-1)
    offsets = torch.sigmoid(offset_raw).gather(-1, classes.unsqueeze(-1)).squeeze(-1)
    _, lows, highs = S3._steer_bins_on(output.device, output.dtype)
    return lows[classes] + offsets * (highs[classes] - lows[classes])


def decode_hybrid_soft(output: torch.Tensor) -> torch.Tensor:
    """Differentiable expected steering angle across all nine hybrid bins."""
    logits, offset_raw = split_hybrid_output(output)
    _, lows, highs = S3._steer_bins_on(output.device, output.dtype)
    angles = lows + torch.sigmoid(offset_raw) * (highs - lows)
    return (torch.softmax(logits, dim=-1) * angles).sum(dim=-1)


def temporal_hybrid_loss(
    output: torch.Tensor,
    targets: torch.Tensor,
    class_weights: torch.Tensor | None,
    offset_weight: float,
    focal_gamma: float,
    horizon_decay: float,
) -> tuple[torch.Tensor, dict[str, float]]:
    if output.shape[:2] != targets.shape:
        raise ValueError(f"Output horizons {tuple(output.shape[:2])} != targets {tuple(targets.shape)}")
    losses = []
    class_losses = []
    offset_losses = []
    horizon_weights = []
    for horizon in range(output.shape[1]):
        target = targets[:, horizon]
        true_class, true_offset = S3.steer_target_class_offset(target)
        logits, offset_raw = split_hybrid_output(output[:, horizon])
        cross_entropy = F.cross_entropy(logits, true_class, weight=class_weights, reduction="none")
        class_loss = (((1.0 - torch.exp(-cross_entropy)) ** float(focal_gamma)) * cross_entropy).mean()
        offset_prediction = torch.sigmoid(offset_raw).gather(1, true_class[:, None]).squeeze(1)
        offset_loss = F.smooth_l1_loss(offset_prediction, true_offset)
        weight = float(horizon_decay) ** horizon
        losses.append(weight * (class_loss + float(offset_weight) * offset_loss))
        class_losses.append(class_loss)
        offset_losses.append(offset_loss)
        horizon_weights.append(weight)
    total = torch.stack(losses).sum() / max(sum(horizon_weights), 1e-8)
    details = {
        "class_loss": float(torch.stack(class_losses).mean().detach().item()),
        "offset_loss": float(torch.stack(offset_losses).mean().detach().item()),
    }
    return total, details


def temporal_trajectory_loss(
    output: torch.Tensor,
    targets: torch.Tensor,
) -> torch.Tensor:
    """Match steering changes between future horizons, not only absolute angles."""
    if output.shape[1] < 2:
        return output.sum() * 0.0
    predicted = decode_hybrid_soft(output)
    predicted_deltas = (predicted[:, 1:] - predicted[:, :-1]) / 20.0
    target_deltas = (targets[:, 1:] - targets[:, :-1]) / 20.0
    return F.smooth_l1_loss(predicted_deltas, target_deltas)


def class_counts(dataset: Series4Dataset) -> list[int]:
    counts = [0] * NUM_STEER_CLASSES
    for index in range(len(dataset)):
        counts[S3.steer_class_index(dataset.current_target(index))] += 1
    return counts


def make_class_weights(dataset: Series4Dataset, power: float) -> tuple[torch.Tensor, list[int]]:
    counts = class_counts(dataset)
    nonzero = [count for count in counts if count]
    mean_count = float(np.mean(nonzero)) if nonzero else 1.0
    weights = [(mean_count / max(1, count)) ** float(power) for count in counts]
    return torch.tensor(weights, dtype=torch.float32, device=DEVICE), counts


def make_sampler(dataset: Series4Dataset, samples_per_epoch: int, balance_power: float):
    counts = class_counts(dataset)
    nonzero = [count for count in counts if count]
    median = float(np.median(nonzero)) if nonzero else 1.0
    weights = []
    for index, sample in enumerate(dataset.samples):
        bucket = S3.steer_class_index(dataset.current_target(index))
        balance = (median / max(1, counts[bucket])) ** float(balance_power)
        weights.append(balance * S3.source_weight(sample.anchor.source))
    count = int(samples_per_epoch) if int(samples_per_epoch) > 0 else len(dataset)
    return WeightedRandomSampler(weights, num_samples=count, replacement=True)


def build_loader(dataset, batch_size: int, workers: int, sampler=None, shuffle: bool = False):
    kwargs = {
        "dataset": dataset,
        "batch_size": int(batch_size),
        "num_workers": int(workers),
        "sampler": sampler,
        "shuffle": bool(shuffle and sampler is None),
        "pin_memory": DEVICE == "cuda",
        "drop_last": sampler is not None,
    }
    if workers > 0:
        kwargs.update(persistent_workers=True, prefetch_factor=2)
    return DataLoader(**kwargs)


def evaluate(
    model: SidewalkPilotV4,
    loader: DataLoader,
    class_weights: torch.Tensor,
    args,
) -> dict[str, float | list[float] | list[int]]:
    model.eval()
    loss_total = 0.0
    batches = 0
    predictions = []
    targets_all = []
    histories = []
    with torch.no_grad():
        for images, history, targets in loader:
            images = images.to(DEVICE, non_blocking=True)
            history = history.to(DEVICE, non_blocking=True)
            targets = targets.to(DEVICE, non_blocking=True)
            output = model(images, history)
            loss, _ = temporal_hybrid_loss(
                output,
                targets,
                class_weights,
                args.offset_loss_weight,
                args.focal_gamma,
                args.horizon_decay,
            )
            loss_total += float(loss.item())
            batches += 1
            predictions.append(decode_hybrid(output).cpu().numpy())
            targets_all.append(targets.cpu().numpy())
            if history.shape[1]:
                histories.append(history.cpu().numpy())

    predicted = np.concatenate(predictions, axis=0)
    actual = np.concatenate(targets_all, axis=0)
    current_predicted = predicted[:, 0]
    current_actual = actual[:, 0]
    errors = current_predicted - current_actual
    predicted_classes = np.asarray([S3.steer_class_index(value) for value in current_predicted])
    actual_classes = np.asarray([S3.steer_class_index(value) for value in current_actual])
    predicted_bucket_counts = np.bincount(
        predicted_classes, minlength=NUM_STEER_CLASSES
    ).astype(np.int64)
    target_bucket_counts = np.bincount(
        actual_classes, minlength=NUM_STEER_CLASSES
    ).astype(np.int64)
    bucket_recalls = np.zeros(NUM_STEER_CLASSES, dtype=np.float64)
    populated_buckets = target_bucket_counts > 0
    for class_index in np.flatnonzero(populated_buckets):
        mask = actual_classes == class_index
        bucket_recalls[class_index] = float(
            (predicted_classes[mask] == class_index).mean()
        )
    turn_mask = actual_classes != 4
    straight_mask = actual_classes == 4
    metrics: dict[str, float | list[float] | list[int]] = {
        "loss": loss_total / max(1, batches),
        "mae": float(np.mean(np.abs(errors))),
        "median_ae": float(np.median(np.abs(errors))),
        "signed_error": float(np.mean(errors)),
        "class_accuracy": float(np.mean(predicted_classes == actual_classes)),
        "balanced_9": (
            float(np.mean(bucket_recalls[populated_buckets]))
            if populated_buckets.any()
            else 0.0
        ),
        "turn_exact": float(np.mean(predicted_classes[turn_mask] == actual_classes[turn_mask])) if turn_mask.any() else 0.0,
        "turn_pm1": float(np.mean(np.abs(predicted_classes[turn_mask] - actual_classes[turn_mask]) <= 1)) if turn_mask.any() else 0.0,
        "straight_exact": float(np.mean(predicted_classes[straight_mask] == 4)) if straight_mask.any() else 0.0,
        "horizon_mae": [float(np.mean(np.abs(predicted[:, h] - actual[:, h]))) for h in range(predicted.shape[1])],
        "predicted_bucket_counts": predicted_bucket_counts.tolist(),
        "target_bucket_counts": target_bucket_counts.tolist(),
        "bucket_recalls": bucket_recalls.tolist(),
    }
    if predicted.shape[1] > 1:
        predicted_deltas = np.diff(predicted, axis=1)
        actual_deltas = np.diff(actual, axis=1)
        metrics["trajectory_delta_mae"] = float(
            np.mean(np.abs(predicted_deltas - actual_deltas))
        )
    if histories:
        history_values = np.concatenate(histories, axis=0)
        metrics["hold_last_mae"] = float(np.mean(np.abs(history_values[:, -1] - current_actual)))
    return metrics


def make_counterfactual_history(history: torch.Tensor) -> torch.Tensor:
    """Create plausible but image-independent trends for history robustness training."""
    if history.shape[1] < 3:
        raise ValueError("Counterfactual history requires at least three values.")
    batch_size = history.shape[0]
    base = 45.0 + 90.0 * torch.rand(batch_size, 1, device=history.device)
    magnitude = 4.0 + 12.0 * torch.rand(batch_size, 1, device=history.device)
    direction = torch.where(
        torch.rand(batch_size, 1, device=history.device) < 0.5,
        -torch.ones_like(magnitude),
        torch.ones_like(magnitude),
    )
    slope = magnitude * direction
    curvature = (torch.rand(batch_size, 1, device=history.device) - 0.5) * 8.0
    recent = torch.cat(
        (base - 2.0 * slope + curvature, base - slope, base), dim=1
    ).clamp(0.0, 180.0)
    if history.shape[1] == 3:
        return recent
    return torch.cat((history[:, :-3], recent), dim=1)


def evaluate_history_robustness(
    model: SidewalkPilotV4,
    loader: DataLoader,
    max_samples: int = 1024,
) -> dict[str, float]:
    if not model.history_steps:
        return {}
    model.eval()
    neutral_errors = []
    trend_spans = []
    flat_shift_spans = []
    seen = 0
    with torch.no_grad():
        for images, _, targets in loader:
            remaining = int(max_samples) - seen
            if remaining <= 0:
                break
            images = images[:remaining].to(DEVICE, non_blocking=True)
            targets = targets[:remaining].to(DEVICE, non_blocking=True)
            batch_size = images.shape[0]
            flat_low = torch.full(
                (batch_size, model.history_steps), 30.0, device=DEVICE
            )
            flat_high = torch.full_like(flat_low, 150.0)
            rising = torch.full_like(flat_low, 90.0)
            falling = torch.full_like(flat_low, 90.0)
            rising[:, -3:] = torch.tensor([60.0, 75.0, 90.0], device=DEVICE)
            falling[:, -3:] = torch.tensor([120.0, 105.0, 90.0], device=DEVICE)

            low_angle = decode_hybrid_soft(model(images, flat_low))[:, 0]
            high_angle = decode_hybrid_soft(model(images, flat_high))[:, 0]
            rising_angle = decode_hybrid_soft(model(images, rising))[:, 0]
            falling_angle = decode_hybrid_soft(model(images, falling))[:, 0]
            neutral_errors.append((low_angle - targets[:, 0]).abs().cpu().numpy())
            flat_shift_spans.append((low_angle - high_angle).abs().cpu().numpy())
            trend_spans.append((rising_angle - falling_angle).abs().cpu().numpy())
            seen += batch_size
    return {
        "neutral_history_mae": float(np.mean(np.concatenate(neutral_errors))),
        "flat_shift_span": float(np.mean(np.concatenate(flat_shift_spans))),
        "opposing_trend_span": float(np.mean(np.concatenate(trend_spans))),
    }


def build_closed_loop_segments(
    samples: Sequence[TemporalSample], max_gap_sec: float
) -> list[list[TemporalSample]]:
    by_run: dict[str, list[TemporalSample]] = defaultdict(list)
    for sample in samples:
        by_run[sample.anchor.run_key].append(sample)
    segments: list[list[TemporalSample]] = []
    for run_samples in by_run.values():
        run_samples.sort(
            key=lambda sample: (
                sample.anchor.timestamp is None,
                sample.anchor.timestamp or 0.0,
                str(sample.anchor.path),
            )
        )
        current: list[TemporalSample] = []
        previous: TemporalSample | None = None
        for sample in run_samples:
            split_here = False
            if previous is not None:
                left = previous.anchor.timestamp
                right = sample.anchor.timestamp
                if left is not None and right is not None:
                    gap = right - left
                    split_here = gap <= 0.0 or (
                        max_gap_sec > 0.0 and gap > max_gap_sec
                    )
            if split_here and current:
                segments.append(current)
                current = []
            current.append(sample)
            previous = sample
        if current:
            segments.append(current)
    return segments


def evaluate_closed_loop(
    model: SidewalkPilotV4,
    samples: Sequence[TemporalSample],
    width: int,
    height: int,
    crop_top_ratio: float,
    max_gap_sec: float,
) -> dict[str, float]:
    """Evaluate PC/PCF using each preceding prediction as the next history value."""
    if not model.history_steps:
        return {}
    segments = build_closed_loop_segments(samples, max_gap_sec)
    histories = [list(segment[0].history) for segment in segments]
    errors = []
    echo_hits = 0
    center_extreme = 0
    saturation = 0
    count = 0
    model.eval()
    with torch.no_grad():
        for position in range(max((len(segment) for segment in segments), default=0)):
            active = [index for index, segment in enumerate(segments) if position < len(segment)]
            if not active:
                continue
            image_tensors = []
            history_values = []
            active_samples = []
            for segment_index in active:
                sample = segments[segment_index][position]
                image = cv2.imread(str(sample.anchor.path), cv2.IMREAD_COLOR)
                if image is None:
                    raise FileNotFoundError(sample.anchor.path)
                image = S3.resize_image_uint8(image, width, height, crop_top_ratio)
                image_tensors.append(S3.image_to_tensor(image))
                history_values.append(histories[segment_index][-model.history_steps :])
                active_samples.append(sample)
            images = torch.stack(image_tensors).to(DEVICE, non_blocking=True)
            history = torch.tensor(history_values, dtype=torch.float32, device=DEVICE)
            predicted = decode_hybrid(model(images, history))[:, 0].cpu().numpy()
            for row, (segment_index, sample) in enumerate(zip(active, active_samples)):
                prediction = float(predicted[row])
                actual = float(sample.targets[0])
                previous_value = float(histories[segment_index][-1])
                errors.append(abs(prediction - actual))
                echo_hits += abs(prediction - previous_value) <= 5.0
                actual_class = S3.steer_class_index(actual)
                predicted_class = S3.steer_class_index(prediction)
                center_extreme += actual_class == 4 and predicted_class in {0, 1, 7, 8}
                saturation += prediction <= 5.0 or prediction >= 175.0
                histories[segment_index].append(prediction)
                count += 1
    return {
        "closed_loop_mae": float(np.mean(errors)),
        "closed_loop_median_ae": float(np.median(errors)),
        "closed_loop_echo_within_5": float(echo_hits / max(1, count)),
        "closed_loop_center_to_extreme": float(center_extreme / max(1, count)),
        "closed_loop_saturation": float(saturation / max(1, count)),
        "closed_loop_segments": float(len(segments)),
    }


def checkpoint_payload(model: SidewalkPilotV4, experiment: str, contract: str, args) -> dict:
    return {
        "model_state_dict": model.state_dict(),
        "series4_config": {
            "experimental": True,
            "experiment": experiment,
            "contract": contract,
            "history_steps": model.history_steps,
            "future_steps": model.future_steps,
            "history_representation": model.history_representation,
            "history_fusion_mode": model.history_fusion_mode,
            "history_logit_residual_scale": model.history_logit_residual_scale,
            "history_offset_residual_scale": model.history_offset_residual_scale,
            "width": int(args.width),
            "height": int(args.height),
        },
    }


def add_wandb_bucket_metrics(
    payload: dict[str, float],
    metrics: dict[str, float | list[float] | list[int]],
) -> None:
    for class_index, (bucket_name, _, _) in enumerate(S3.STEER_CLASS_BINS):
        # Keep the Series 3 names for direct cross-run W&B charts. Target
        # counts distinguish an absent validation class from prediction collapse.
        payload[f"bucket_{bucket_name}"] = metrics[
            "predicted_bucket_counts"
        ][class_index]
        payload[f"target_bucket_{bucket_name}"] = metrics[
            "target_bucket_counts"
        ][class_index]
        payload[f"recall_{bucket_name}"] = metrics["bucket_recalls"][class_index]


def load_checkpoint(path: Path, device: str = DEVICE) -> tuple[SidewalkPilotV4, dict]:
    payload = torch.load(path, map_location=device)
    if not isinstance(payload, dict) or "series4_config" not in payload:
        raise ValueError(f"Series 4 checkpoint metadata missing from {path}")
    config = payload["series4_config"]
    model = SidewalkPilotV4(
        config["history_steps"],
        config["future_steps"],
        history_representation=config.get("history_representation", "absolute"),
        history_fusion_mode=config.get("history_fusion_mode", "full"),
        history_logit_residual_scale=config.get("history_logit_residual_scale", 0.35),
        history_offset_residual_scale=config.get("history_offset_residual_scale", 0.35),
    ).to(device)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    model.eval()
    return model, config


def export_onnx(checkpoint_path: Path, output_path: Path, opset: int = 17) -> Path:
    if importlib.util.find_spec("onnx") is None:
        raise RuntimeError("ONNX export requires the 'onnx' Python package.")
    model, config = load_checkpoint(checkpoint_path)
    image = torch.zeros(1, 3, config["height"], config["width"], device=DEVICE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if config["history_steps"]:
        history = torch.full((1, config["history_steps"]), 90.0, device=DEVICE)
        inputs = (image, history)
        input_names = ["image", "target_history"]
        dynamic_axes = {
            "image": {0: "batch"},
            "target_history": {0: "batch"},
            "steering_raw": {0: "batch"},
        }
    else:
        inputs = image
        input_names = ["image"]
        dynamic_axes = {"image": {0: "batch"}, "steering_raw": {0: "batch"}}
    torch.onnx.export(
        model,
        inputs,
        str(output_path),
        export_params=True,
        opset_version=int(opset),
        do_constant_folding=True,
        input_names=input_names,
        output_names=["steering_raw"],
        dynamic_axes=dynamic_axes,
    )
    print(f"[export] {output_path} shape=[batch,{config['future_steps'] + 1},18]")
    return output_path


def build_parser(experiment: str, contract: str, final_version: str, best_version: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Experimental SidewalkPilot Series 4 {experiment} trainer ({contract})."
    )
    parser.add_argument("--roots", nargs="*", default=None)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=3e-4)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=180)
    parser.add_argument("--crop-top-ratio", type=float, default=0.0)
    parser.add_argument("--val-split", type=float, default=0.10)
    parser.add_argument("--split-window", type=int, default=100)
    parser.add_argument("--max-frame-gap-sec", type=float, default=0.25)
    parser.add_argument("--history-steps", type=int, default=3)
    parser.add_argument("--future-steps", type=int, default=3)
    parser.add_argument("--history-noise-deg", type=float, default=1.0)
    parser.add_argument("--history-dropout-probability", type=float, default=0.05)
    parser.add_argument("--history-sequence-dropout-probability", type=float, default=0.0)
    parser.add_argument("--history-walk-noise-deg", type=float, default=0.0)
    parser.add_argument("--history-logit-residual-scale", type=float, default=0.35)
    parser.add_argument("--history-offset-residual-scale", type=float, default=0.35)
    parser.add_argument("--counterfactual-every", type=int, default=0)
    parser.add_argument("--counterfactual-batch-fraction", type=float, default=0.25)
    parser.add_argument("--counterfactual-loss-weight", type=float, default=0.0)
    parser.add_argument("--history-consistency-weight", type=float, default=0.0)
    parser.add_argument("--closed-loop-selection-weight", type=float, default=0.0)
    parser.add_argument("--trajectory-delta-loss-weight", type=float, default=0.0)
    parser.add_argument("--horizon-decay", type=float, default=0.70)
    parser.add_argument("--offset-loss-weight", type=float, default=1.0)
    parser.add_argument("--focal-gamma", type=float, default=1.5)
    parser.add_argument("--class-weight-power", type=float, default=0.5)
    parser.add_argument("--sampler-balance-power", type=float, default=0.0)
    parser.add_argument("--samples-per-epoch", type=int, default=50000)
    parser.add_argument("--balance-flip", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--flip-aug-probability", type=float, default=0.0)
    parser.add_argument("--shadow-aug-probability", type=float, default=0.6)
    parser.add_argument("--hsv-aug-probability", type=float, default=0.0)
    parser.add_argument("--clahe-aug-probability", type=float, default=0.0)
    parser.add_argument("--log-every", type=int, default=50)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--limit-frames", type=int, default=0, help="smoke-test only; never use for a real model")
    parser.add_argument("--final-output", default=str(MODELS_DIR / f"SidewalkPilot-v{final_version}.pth"))
    parser.add_argument("--best-output", default=str(MODELS_DIR / f"SidewalkPilot-v{best_version}.pth"))
    parser.add_argument("--export-onnx", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--onnx-opset", type=int, default=17)
    parser.add_argument("--keep-pth", action="store_true")
    return parser


def run_fixed_experiment(
    experiment: str,
    contract: str,
    final_version: str,
    best_version: str,
    training_profile: str = "legacy",
) -> None:
    if contract not in CONTRACTS:
        raise ValueError(f"Unknown Series 4 contract: {contract}")
    parser = build_parser(experiment, contract, final_version, best_version)
    if training_profile == "history_robust":
        parser.set_defaults(
            history_noise_deg=4.0,
            history_dropout_probability=0.15,
            history_sequence_dropout_probability=0.10,
            history_walk_noise_deg=3.0,
            counterfactual_every=4,
            counterfactual_batch_fraction=0.25,
            counterfactual_loss_weight=0.35,
            history_consistency_weight=0.02,
            closed_loop_selection_weight=0.65,
        )
    elif training_profile == "future_trajectory":
        if contract != "cf":
            raise ValueError("future_trajectory profile requires the CF contract")
        parser.set_defaults(
            horizon_decay=0.55,
            trajectory_delta_loss_weight=0.15,
        )
    elif training_profile != "legacy":
        raise ValueError(f"Unknown Series 4 training profile: {training_profile}")
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
        torch.backends.cudnn.benchmark = True

    uses_history = CONTRACTS[contract]["uses_history"]
    uses_future = CONTRACTS[contract]["uses_future"]
    history_steps = max(1, args.history_steps) if uses_history else 0
    future_steps = max(1, args.future_steps) if uses_future else 0
    print(
        f"[start] EXPERIMENTAL Series 4 {experiment} contract={contract} device={DEVICE} "
        f"history={history_steps} current=1 future={future_steps} profile={training_profile} "
        f"final={final_version} best={best_version}"
    )

    roots = discover_roots(args.roots)
    frames = load_frames(roots, args.limit_frames)
    split_by_frame, _ = frozen_series3_split(frames, args.val_split, args.split_window)
    samples, sequence_stats = build_temporal_samples(
        frames, split_by_frame, history_steps, future_steps, args.max_frame_gap_sec
    )
    train_samples = [sample for sample in samples if sample.split == "train"]
    val_samples = [sample for sample in samples if sample.split == "val"]
    train_dataset = Series4Dataset(
        train_samples,
        args.width,
        args.height,
        args.crop_top_ratio,
        augment=True,
        flip_probability=args.flip_aug_probability,
        shadow_probability=args.shadow_aug_probability,
        hsv_probability=args.hsv_aug_probability,
        clahe_probability=args.clahe_aug_probability,
        history_noise_deg=args.history_noise_deg if uses_history else 0.0,
        history_dropout_probability=args.history_dropout_probability if uses_history else 0.0,
        history_sequence_dropout_probability=(
            args.history_sequence_dropout_probability if uses_history else 0.0
        ),
        history_walk_noise_deg=args.history_walk_noise_deg if uses_history else 0.0,
    )
    val_dataset = Series4Dataset(
        val_samples, args.width, args.height, args.crop_top_ratio, augment=False
    )
    if args.balance_flip:
        train_dataset.apply_balance_flip()
    class_weights, counts = make_class_weights(train_dataset, args.class_weight_power)
    print("[classes] current-target counts and weights:")
    for (name, _, _), count, weight in zip(S3.STEER_CLASS_BINS, counts, class_weights.tolist()):
        print(f"  {name}: n={count} weight={weight:.3f}")

    history_representation = (
        "delta_motion" if training_profile == "history_robust" else "absolute"
    )
    history_fusion_mode = (
        "bounded_residual" if training_profile == "history_robust" else "full"
    )
    model = SidewalkPilotV4(
        history_steps,
        future_steps,
        history_representation=history_representation,
        history_fusion_mode=history_fusion_mode,
        history_logit_residual_scale=args.history_logit_residual_scale,
        history_offset_residual_scale=args.history_offset_residual_scale,
    ).to(DEVICE)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    with torch.no_grad():
        image = torch.zeros(2, 3, args.height, args.width, device=DEVICE)
        history = torch.full((2, history_steps), 90.0, device=DEVICE)
        shape = tuple(model(image, history).shape)
    print(
        f"[model] parameters={parameter_count:,} output_shape={shape} "
        f"history_representation={history_representation} fusion={history_fusion_mode} "
        f"sequence_stats={sequence_stats}"
    )
    if args.audit_only:
        print("[audit] dataset, split, temporal windows, class balance, and model shape verified")
        return

    sampler = make_sampler(train_dataset, args.samples_per_epoch, args.sampler_balance_power)
    train_loader = build_loader(train_dataset, args.batch_size, args.workers, sampler=sampler)
    val_loader = build_loader(val_dataset, args.batch_size, max(0, args.workers // 2))
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, args.epochs))

    final_path = Path(args.final_output).expanduser()
    best_path = Path(args.best_output).expanduser()
    final_path.parent.mkdir(parents=True, exist_ok=True)
    best_path.parent.mkdir(parents=True, exist_ok=True)
    best_score = float("inf")
    best_mae = float("inf")
    best_epoch = 0
    start = time.time()
    global_step = 0
    last_stream_push = 0.0
    loss_ema = None

    try:
        from wandb_logger import WandbLogger

        tracker = WandbLogger(
            experiment,
            config={
                "experimental": True,
                "series": 4,
                "contract": contract,
                "training_profile": training_profile,
                "final_version": final_version,
                "best_version": best_version,
                "history_steps": history_steps,
                "future_steps": future_steps,
                "dataset_frames": len(frames),
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "samples_per_epoch": args.samples_per_epoch,
                "lr": args.lr,
                "weight_decay": args.weight_decay,
                "seed": args.seed,
                "width": args.width,
                "height": args.height,
                "parameter_count": parameter_count,
                "balance_flip": args.balance_flip,
                "shadow_aug_probability": args.shadow_aug_probability,
                "horizon_decay": args.horizon_decay,
                "max_frame_gap_sec": args.max_frame_gap_sec,
                "history_representation": history_representation,
                "history_fusion_mode": history_fusion_mode,
                "history_noise_deg": args.history_noise_deg,
                "history_dropout_probability": args.history_dropout_probability,
                "history_sequence_dropout_probability": args.history_sequence_dropout_probability,
                "history_walk_noise_deg": args.history_walk_noise_deg,
                "counterfactual_loss_weight": args.counterfactual_loss_weight,
                "history_consistency_weight": args.history_consistency_weight,
                "closed_loop_selection_weight": args.closed_loop_selection_weight,
                "trajectory_delta_loss_weight": args.trajectory_delta_loss_weight,
            },
        )
    except Exception as exc:
        print(f"[wandb] unavailable: {exc}")
        tracker = None

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()
        model.train()
        train_loss = 0.0
        for step, (images, history, targets) in enumerate(train_loader, start=1):
            images = images.to(DEVICE, non_blocking=True)
            history = history.to(DEVICE, non_blocking=True)
            targets = targets.to(DEVICE, non_blocking=True)
            output = model(images, history)
            loss, details = temporal_hybrid_loss(
                output,
                targets,
                class_weights,
                args.offset_loss_weight,
                args.focal_gamma,
                args.horizon_decay,
            )
            counterfactual_loss_value = 0.0
            consistency_loss_value = 0.0
            trajectory_loss_value = 0.0
            if (
                uses_history
                and args.counterfactual_every > 0
                and step % args.counterfactual_every == 0
            ):
                counterfactual_count = max(
                    1,
                    int(images.shape[0] * args.counterfactual_batch_fraction),
                )
                alternate_history = make_counterfactual_history(
                    history[:counterfactual_count]
                )
                alternate_output = model(
                    images[:counterfactual_count], alternate_history
                )
                counterfactual_loss, _ = temporal_hybrid_loss(
                    alternate_output,
                    targets[:counterfactual_count],
                    class_weights,
                    args.offset_loss_weight,
                    args.focal_gamma,
                    args.horizon_decay,
                )
                consistency_loss = F.smooth_l1_loss(
                    decode_hybrid_soft(alternate_output),
                    decode_hybrid_soft(output[:counterfactual_count]).detach(),
                )
                loss = (
                    loss
                    + args.counterfactual_loss_weight * counterfactual_loss
                    + args.history_consistency_weight * consistency_loss
                )
                counterfactual_loss_value = float(counterfactual_loss.detach().item())
                consistency_loss_value = float(consistency_loss.detach().item())
            if future_steps and args.trajectory_delta_loss_weight > 0.0:
                trajectory_loss = temporal_trajectory_loss(output, targets)
                loss = loss + args.trajectory_delta_loss_weight * trajectory_loss
                trajectory_loss_value = float(trajectory_loss.detach().item())
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip).item())
            optimizer.step()
            loss_value = float(loss.item())
            train_loss += loss_value
            global_step += 1
            loss_ema = (
                loss_value
                if loss_ema is None
                else 0.95 * loss_ema + 0.05 * loss_value
            )
            if (
                tracker is not None
                and tracker.enabled
                and time.time() - last_stream_push >= 5.0
            ):
                last_stream_push = time.time()
                tracker.push(
                    epoch,
                    {
                        "train_loss_live": loss_ema,
                        "lr": float(optimizer.param_groups[0]["lr"]),
                        "grad_norm": gradient_norm,
                        "counterfactual_loss_live": counterfactual_loss_value,
                        "history_consistency_loss_live": consistency_loss_value,
                        "trajectory_delta_loss_live": trajectory_loss_value,
                        "epoch": epoch,
                        "global_step": global_step,
                        "gpu_mem_gb": (
                            torch.cuda.memory_reserved() / 1e9
                            if torch.cuda.is_available()
                            else 0.0
                        ),
                    },
                )
            if step == 1 or step % args.log_every == 0:
                decoded = decode_hybrid(output.detach())[:, 0]
                print(
                    f"[train] epoch={epoch}/{args.epochs} step={step}/{len(train_loader)} "
                    f"loss={loss.item():.5f} cls={details['class_loss']:.5f} "
                    f"off={details['offset_loss']:.5f} grad={gradient_norm:.3f} "
                    f"cf={counterfactual_loss_value:.5f} cons={consistency_loss_value:.5f} "
                    f"traj={trajectory_loss_value:.5f} "
                    f"pred=[{decoded.min().item():.1f},{decoded.max().item():.1f}] "
                    f"elapsed={S3.fmt_time(time.time() - start)}"
                )
        scheduler.step()
        metrics = evaluate(model, val_loader, class_weights, args)
        robustness = evaluate_history_robustness(model, val_loader) if uses_history else {}
        closed_loop = (
            evaluate_closed_loop(
                model,
                val_samples,
                args.width,
                args.height,
                args.crop_top_ratio,
                args.max_frame_gap_sec,
            )
            if uses_history and args.closed_loop_selection_weight > 0.0
            else {}
        )
        metrics.update(robustness)
        metrics.update(closed_loop)
        average_train = train_loss / max(1, len(train_loader))
        horizon_text = ",".join(f"{value:.2f}" for value in metrics["horizon_mae"])
        print(
            f"[epoch] {epoch}/{args.epochs} train={average_train:.5f} val={metrics['loss']:.5f} "
            f"MAE={metrics['mae']:.3f} Med={metrics['median_ae']:.3f} Signed={metrics['signed_error']:.3f} "
            f"Bal9={metrics['balanced_9']:.3f} TurnExact={metrics['turn_exact']:.3f} "
            f"Turn+/-1={metrics['turn_pm1']:.3f} STExact={metrics['straight_exact']:.3f} "
            f"horizon_MAE=[{horizon_text}]"
        )
        if "trajectory_delta_mae" in metrics:
            print(
                f"[trajectory] delta_MAE={metrics['trajectory_delta_mae']:.3f} deg/step"
            )
        if robustness:
            print(
                f"[history] neutral_MAE={metrics['neutral_history_mae']:.3f} "
                f"flat_shift_span={metrics['flat_shift_span']:.4f} "
                f"opposing_trend_span={metrics['opposing_trend_span']:.3f}"
            )
        selection_score = float(metrics["mae"])
        if closed_loop:
            closed_weight = float(np.clip(args.closed_loop_selection_weight, 0.0, 1.0))
            selection_score = (
                (1.0 - closed_weight) * float(metrics["mae"])
                + closed_weight * float(metrics["closed_loop_mae"])
                + 0.10 * float(metrics["opposing_trend_span"])
            )
            print(
                f"[closed-loop] MAE={metrics['closed_loop_mae']:.3f} "
                f"Med={metrics['closed_loop_median_ae']:.3f} "
                f"echo5={metrics['closed_loop_echo_within_5']:.3f} "
                f"center_extreme={metrics['closed_loop_center_to_extreme']:.4f} "
                f"saturation={metrics['closed_loop_saturation']:.4f} "
                f"segments={int(metrics['closed_loop_segments'])} selection={selection_score:.3f}"
            )
        if selection_score < best_score:
            best_score = selection_score
            best_mae = float(metrics["mae"])
            best_epoch = epoch
            torch.save(checkpoint_payload(model, experiment, contract, args), best_path)
            print(
                f"[save] best {best_version}: epoch={epoch} MAE={best_mae:.3f} "
                f"selection={best_score:.3f} -> {best_path}"
            )
        if tracker is not None and tracker.enabled:
            wandb_metrics = {
                "train_loss": average_train,
                "val_loss": metrics["loss"],
                "steer_mae_deg": metrics["mae"],
                "class_acc": metrics["class_accuracy"],
                "median_ae_deg": metrics["median_ae"],
                "signed_error_deg": metrics["signed_error"],
                "balanced_9": metrics["balanced_9"],
                "turn_exact": metrics["turn_exact"],
                "turn_pm1": metrics["turn_pm1"],
                "straight_exact": metrics["straight_exact"],
                "selection_score": selection_score,
                "lr": float(optimizer.param_groups[0]["lr"]),
                "epoch_time_s": time.time() - epoch_start,
                "gpu_mem_gb": (
                    torch.cuda.memory_reserved() / 1e9
                    if torch.cuda.is_available()
                    else 0.0
                ),
            }
            for horizon, horizon_mae in enumerate(metrics["horizon_mae"]):
                name = "current" if horizon == 0 else f"future_{horizon}"
                wandb_metrics[f"horizon_{name}_mae_deg"] = horizon_mae
            if len(metrics["horizon_mae"]) > 1:
                wandb_metrics["future_mean_mae_deg"] = float(
                    np.mean(metrics["horizon_mae"][1:])
                )
                wandb_metrics["trajectory_delta_mae_deg"] = metrics[
                    "trajectory_delta_mae"
                ]
            if "hold_last_mae" in metrics:
                wandb_metrics["hold_last_mae_deg"] = metrics["hold_last_mae"]
                wandb_metrics["beats_hold_last"] = float(
                    metrics["mae"] < metrics["hold_last_mae"]
                    and (
                        not closed_loop
                        or metrics["closed_loop_mae"] < metrics["hold_last_mae"]
                    )
                )
            wandb_metrics.update(robustness)
            wandb_metrics.update(closed_loop)
            add_wandb_bucket_metrics(wandb_metrics, metrics)
            tracker.push(epoch, wandb_metrics)

    torch.save(checkpoint_payload(model, experiment, contract, args), final_path)
    print(f"[save] final {final_version}: {final_path}")
    print(
        f"[result] best {best_version}: epoch={best_epoch} "
        f"MAE={best_mae:.3f} selection={best_score:.3f}"
    )
    if tracker is not None:
        tracker.finish()

    exported = []
    if args.export_onnx:
        for checkpoint in (final_path, best_path):
            exported.append((checkpoint, export_onnx(checkpoint, checkpoint.with_suffix(".onnx"), args.onnx_opset)))
    if exported and not args.keep_pth:
        for checkpoint, onnx_path in exported:
            if onnx_path.is_file() and checkpoint.is_file():
                checkpoint.unlink()
                print(f"[cleanup] removed {checkpoint.name}; kept {onnx_path.name}")
    print(f"[done] experimental {experiment} total={S3.fmt_time(time.time() - start)}")
