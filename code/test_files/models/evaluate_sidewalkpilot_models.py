#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import math
import re
import sys
from collections import Counter
from io import BytesIO
from pathlib import Path

import cv2
import matplotlib
import numpy as np
import torch
import torch.nn as nn
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]            # code/test_files/models -> repo root
MODELS_DIR = REPO_ROOT / "code" / "ai_models"
CORRECTIONS_PATH = REPO_ROOT / "code" / "ai_models_datasets" / "series_1_and_2" / "steering_corrections.json"
S12_DATASET_DIR = REPO_ROOT / "code" / "ai_models_datasets" / "series_1_and_2" / "sidewalkpilot_dataset"
DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_JSON_OUT = DOCS_DIR / "steering_eval_current_labels.json"
DEFAULT_PDF_OUT = DOCS_DIR / "steering_model_report.pdf"

WIDTH = 200
HEIGHT = 66
SERIES_1_SCALE_DEG = 86.0
SERIES_2_SCALE_DEG = 85.0
MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>\d+\.\d+b?)\.pth$")

# Series 3 (heavy SidewalkPilotV3, 320x180). Series 1/2 use their original
# corrected real-image evaluation set; Series 3 uses its own collected dataset.
S3_WIDTH = 320
S3_HEIGHT = 180
S3_DATASET_DIR = REPO_ROOT / "code" / "ai_models_datasets" / "series_3_and_4" / "sidewalkpilot_dataset"
S3_TRAINER_PATH = REPO_ROOT / "code" / "ai_models_datasets" / "series_3_and_4" / "series_3_sidewalkpilot_trainer.py"
S4_COMMON_PATH = REPO_ROOT / "code" / "ai_models_datasets" / "series_3_and_4" / "series_4_common.py"
S3_MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>3\.\d+b?)\.pth$")
S4_MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>4\.(?:0|1)[acfgpr])\.(?P<ext>onnx|pt|pth)$")
S4_SUFFIX_ORDER = {"p": 0, "r": 1, "f": 2, "g": 3, "a": 4, "c": 5}


def report_checkpoint_path(path):
    """Return a portable checkpoint path without exposing a workstation home path."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return resolved.name

BUCKETS = [
    ("HL 0-45", 0.0, 45.0),
    ("L 45-75", 45.0, 75.0),
    ("SL 75-85", 75.0, 85.0),
    ("ST 85-95", 85.0, 95.0),
    ("SR 95-105", 95.0, 105.0),
    ("R 105-135", 105.0, 135.0),
    ("HR 135-180", 135.0, 180.0),
]

# The 9 real model steering classes (STEER_CLASS_BINS in the Series-3 trainer) -- used for
# the 9x9 confusion heatmap. Short labels keep the grid readable.
BUCKETS9 = [
    ("HL", 0.0, 45.0), ("L", 45.0, 60.0), ("L+", 60.0, 75.0),
    ("SL", 75.0, 85.0), ("ST", 85.0, 95.0), ("SR", 95.0, 105.0),
    ("R", 105.0, 120.0), ("R+", 120.0, 135.0), ("HR", 135.0, 180.0),
]


def bucket9_index(value):
    for i, (_, lo, hi) in enumerate(BUCKETS9):
        if lo <= value < hi:
            return i
    return len(BUCKETS9) - 1


# Official source code = D{MMDD}_{HH} (run start hour, 24h).
SOURCE_PURPOSES = {
    "D0328_17": "First dataset relabel, March 28",
    "D0329_15": "First dataset relabel, March 29",
    "D0425_14": "Street test",
    "D0426_18": "Curves and shadows",
    "D0427_18": "Curved curb",
    "D0429_19": "Driveway and shadow",
    "D0502_12": "Shadow fix set",
    "D0502_19": "Hard turns, curb hugging, smoothness",
    "D0503_17": "Harsh sidewalk",
    "D0506_20": "8pm sidewalk failure set",
    "D0510_18": "v2.3 field-failure run 1: turns, road-right driving, driveways",
    "D0510_19": "v2.3 field-failure run 2 (short)",
    "D0510_20": "v2.3 field-failure run 3: turns, road-right driving, driveways",
    "D0629_17": "Series 3 collected run (camera tilted, poor image quality)",
    "D0702_16": "Series 3 July 2 base set: two manual field runs, 50,684 images",
    "D0707_16": "Bright-sun HARD/diagonal shadows across the sidewalk (v3.2 shadow-robustness batch)",
    "D0712_15": "Series 3 manual field collection, July 12 run 1",
    "D0712_16": "Series 3 manual field collection, July 12 run 2 (103-frame bad segment removed)",
}


class SteeringAutonomyV2(nn.Module):
    def __init__(self, output_scale_deg):
        super().__init__()
        self.output_scale_deg = float(output_scale_deg)
        self.backbone = nn.Sequential(
            nn.Conv2d(3, 24, 5, stride=2),
            nn.BatchNorm2d(24),
            nn.ELU(inplace=True),
            nn.Conv2d(24, 36, 5, stride=2),
            nn.BatchNorm2d(36),
            nn.ELU(inplace=True),
            nn.Conv2d(36, 48, 5, stride=2),
            nn.BatchNorm2d(48),
            nn.ELU(inplace=True),
            nn.Conv2d(48, 64, 3, stride=1),
            nn.BatchNorm2d(64),
            nn.ELU(inplace=True),
            nn.Conv2d(64, 64, 3, stride=1),
            nn.BatchNorm2d(64),
            nn.ELU(inplace=True),
        )
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d((4, 8)),
            nn.Flatten(),
            nn.Linear(64 * 4 * 8, 256),
            nn.ELU(inplace=True),
            nn.Dropout(p=0.10),
            nn.Linear(256, 64),
            nn.ELU(inplace=True),
            nn.Linear(64, 1),
            nn.Tanh(),
        )

    def forward(self, x):
        x = self.backbone(x)
        return 90.0 + self.output_scale_deg * self.head(x)


def version_key(version):
    match = re.fullmatch(r"(?P<major>\d+)\.(?P<minor>\d+)(?P<suffix>[a-z]?)", version)
    if match is None:
        raise ValueError(f"Invalid SidewalkPilot version: {version}")
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    suffix = match.group("suffix")
    if major == 4:
        suffix_rank = S4_SUFFIX_ORDER.get(suffix, -1)
    else:
        suffix_rank = 1 if suffix == "b" else 0
    return major, minor, suffix_rank


def discover_models(models_dir):
    """Series 1/2 checkpoints only (SteeringAutonomyV2 arch). Series 3 is handled
    separately by evaluate_series3()."""
    models = []
    for path in sorted(models_dir.glob("SidewalkPilot-v*.pth")):
        match = MODEL_RE.match(path.name)
        if match and series_for_version(match.group("version")) in {1, 2}:
            models.append((match.group("version"), path))
    return sorted(models, key=lambda item: version_key(item[0]))


def series_for_version(version):
    if version.startswith("4."):
        return 4
    if version.startswith("3."):
        return 3
    return 2 if version.startswith("2.") else 1


def preprocessing_for_version(version):
    if version.startswith(("3.", "4.")):
        return "raw BGR 320x180"
    return "HSV/CLAHE -> BGR" if version in {"2.0", "2.0b"} else "raw BGR"


def scale_for_version(version):
    return SERIES_2_SCALE_DEG if series_for_version(version) == 2 else SERIES_1_SCALE_DEG


def dataset_key(source):
    """Official source code = D{MMDD}_{HH} (run start hour, 24h). Hours derived from the
    correction images' photo_YYYYMMDD_HHMMSS timestamps."""
    source = str(source or "").lower()
    if "0328" in source:
        return "D0328_17"
    if "0329" in source:
        return "D0329_15"
    if "0425" in source:
        return "D0425_14"
    if "0426" in source:
        return "D0426_18"
    if "0427" in source:
        return "D0427_18"
    if "0429" in source:
        return "D0429_19"
    if "0502_19" in source:
        return "D0502_19"
    if "0502" in source:
        return "D0502_12"
    if "0503" in source:
        return "D0503_17"
    if "0506" in source:
        return "D0506_20"
    if "0510" in source and "run_2" in source:
        return "D0510_19"
    if "0510" in source and "run_3" in source:
        return "D0510_20"
    if "0510" in source:
        return "D0510_18"
    return str(source or "unknown")


def clamp_servo(value):
    return float(max(0.0, min(180.0, float(value))))


def label_to_servo(value):
    value = float(value)
    if 0.0 <= value <= 180.0:
        return clamp_servo(value)
    return clamp_servo((max(-1.0, min(1.0, value)) + 1.0) * 90.0)


def resolve_image_path(corrections_path, item, dataset_dir):
    raw = item.get("image") or item.get("image_path") or item.get("path") or item.get("file")
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_absolute() and path.is_file():
        return path
    candidates = [
        corrections_path.parent / path,
        dataset_dir / path,
        dataset_dir / path.name,
        REPO_ROOT / path,
        REPO_ROOT / "code" / "ai_models_datasets" / "series_1_and_2" / path,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_samples(corrections_path, dataset_dir):
    items = json.loads(corrections_path.read_text())
    if not isinstance(items, list):
        raise ValueError(f"{corrections_path} must contain a list")

    samples = []
    missing = []
    for index, item in enumerate(items):
        img_path = resolve_image_path(corrections_path, item, dataset_dir)
        if img_path is None:
            missing.append((index, item.get("image")))
            continue
        try:
            steer = label_to_servo(item.get("steering", item.get("steer", item.get("control_steer"))))
        except (TypeError, ValueError):
            continue
        source = item.get("source", "unknown")
        samples.append(
            {
                "image": str(img_path),
                "label_image": item.get("image", str(img_path)),
                "steering": steer,
                "source": source,
                "dataset": dataset_key(source),
            }
        )

    if missing:
        examples = ", ".join(str(value) for _, value in missing[:5])
        raise FileNotFoundError(f"{len(missing)} correction images were missing. Examples: {examples}")
    if not samples:
        raise FileNotFoundError("No usable correction samples found")
    return samples


def apply_clahe_to_bgr(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h_channel, s_channel, v_channel = cv2.split(hsv)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_v = clahe.apply(v_channel)
    return cv2.cvtColor(cv2.merge((h_channel, s_channel, enhanced_v)), cv2.COLOR_HSV2BGR)


def preprocess_frame(frame):
    img = cv2.resize(frame, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)
    img = img.astype(np.float32) / 255.0
    img = (img - 0.5) / 0.5
    return np.transpose(img, (2, 0, 1))


def load_tensors(samples, progress_label="images"):
    raw_tensors = []
    clahe_tensors = []
    targets = []
    for index, sample in enumerate(samples, start=1):
        frame = cv2.imread(sample["image"], cv2.IMREAD_COLOR)
        if frame is None:
            raise FileNotFoundError(sample["image"])
        raw_tensors.append(preprocess_frame(frame))
        clahe_tensors.append(preprocess_frame(apply_clahe_to_bgr(frame)))
        targets.append(sample["steering"])
        if index % 250 == 0 or index == len(samples):
            print(f"[{progress_label}] loaded={index}/{len(samples)}", flush=True)

    return (
        torch.from_numpy(np.stack(raw_tensors)).float(),
        torch.from_numpy(np.stack(clahe_tensors)).float(),
        np.array(targets, dtype=np.float32),
    )


def load_model(path, version, device):
    checkpoint = torch.load(path, map_location=device)
    state = checkpoint
    if isinstance(checkpoint, dict):
        for key in ("model_state_dict", "state_dict", "model"):
            if key in checkpoint and isinstance(checkpoint[key], dict):
                state = checkpoint[key]
                break
    state = {key.removeprefix("module."): value for key, value in state.items()}
    model = SteeringAutonomyV2(scale_for_version(version)).to(device)
    model.load_state_dict(state, strict=True)
    model.eval()
    return model


def run_model(model, inputs, batch_size, device):
    preds = []
    with torch.no_grad():
        for start in range(0, len(inputs), batch_size):
            batch = inputs[start : start + batch_size].to(device, non_blocking=True)
            pred = torch.clamp(model(batch), 0.0, 180.0)
            preds.append(pred.cpu().numpy().reshape(-1))
    return np.concatenate(preds).astype(np.float32)


def bucket_index(value):
    value = clamp_servo(value)
    for index, (_, lo, hi) in enumerate(BUCKETS):
        if index == len(BUCKETS) - 1:
            if lo <= value <= hi:
                return index
        elif lo <= value < hi:
            return index
    return len(BUCKETS) - 1


def bucket_counts(values):
    counts = Counter(bucket_index(value) for value in values)
    return {name: int(counts[index]) for index, (name, _, _) in enumerate(BUCKETS)}


def bucket_summary(preds, targets):
    pred_indices = np.array([bucket_index(value) for value in preds], dtype=np.int32)
    target_indices = np.array([bucket_index(value) for value in targets], dtype=np.int32)
    exact = int((pred_indices == target_indices).sum())
    off_by_one = int((np.abs(pred_indices - target_indices) <= 1).sum())
    confusion = {}
    for row_index, (row_name, _, _) in enumerate(BUCKETS):
        row = {}
        mask = target_indices == row_index
        for col_index, (col_name, _, _) in enumerate(BUCKETS):
            row[col_name] = int((pred_indices[mask] == col_index).sum())
        confusion[row_name] = row
    # 9-class confusion (the real model buckets) for the PDF heatmap
    confusion9 = {}
    p9 = np.array([bucket9_index(v) for v in preds], dtype=np.int32)
    t9 = np.array([bucket9_index(v) for v in targets], dtype=np.int32)
    for ri, (rn, _, _) in enumerate(BUCKETS9):
        m = t9 == ri
        confusion9[rn] = {cn: int((p9[m] == ci).sum()) for ci, (cn, _, _) in enumerate(BUCKETS9)}
    count = max(1, len(targets))
    class_totals = np.bincount(t9, minlength=len(BUCKETS9))
    class_exact = np.bincount(t9[t9 == p9], minlength=len(BUCKETS9))
    nonempty = class_totals > 0
    macro_exact = float(np.mean(class_exact[nonempty] / class_totals[nonempty])) if nonempty.any() else 0.0
    straight_index = next(i for i, (name, _, _) in enumerate(BUCKETS9) if name == "ST")
    turn_mask = t9 != straight_index
    turn_count = max(1, int(turn_mask.sum()))
    straight_mask = t9 == straight_index
    straight_count = max(1, int(straight_mask.sum()))
    turn_exact = int((p9[turn_mask] == t9[turn_mask]).sum())
    turn_near = int((np.abs(p9[turn_mask] - t9[turn_mask]) <= 1).sum())
    turn_detected = int((p9[turn_mask] != straight_index).sum())
    straight_exact = int((p9[straight_mask] == straight_index).sum())
    return {
        "prediction_bucket_counts": bucket_counts(preds),
        "ground_bucket_counts": bucket_counts(targets),
        "bucket_agreement": {
            "exact_bucket_count": exact,
            "exact_bucket_percent": exact * 100.0 / count,
            "off_by_one_bucket_count": off_by_one,
            "off_by_one_bucket_percent": off_by_one * 100.0 / count,
        },
        "bucket_confusion_ground_rows_pred_cols": confusion,
        "bucket9_confusion_ground_rows_pred_cols": confusion9,
        "selection_metrics": {
            "balanced_9_bucket_exact_percent": macro_exact * 100.0,
            "turn_detection_recall_percent": turn_detected * 100.0 / turn_count,
            "turn_exact_bucket_recall_percent": turn_exact * 100.0 / turn_count,
            "turn_within_one_bucket_recall_percent": turn_near * 100.0 / turn_count,
            "straight_exact_bucket_recall_percent": straight_exact * 100.0 / straight_count,
            "turn_count": int(turn_mask.sum()),
            "straight_count": int(straight_mask.sum()),
        },
    }


def metric_block(preds, targets):
    preds = np.asarray(preds, dtype=np.float32)
    targets = np.asarray(targets, dtype=np.float32)
    ae = np.abs(preds - targets)
    signed = preds - targets
    count = int(len(targets))
    if count == 0:
        return {
            "count": 0,
            "mae": None,
            "median_ae": None,
            "max_ae": None,
            "signed_error": None,
            "within_2": 0,
            "within_5": 0,
            "within_10": 0,
            "within_20": 0,
            "pred_min": None,
            "pred_max": None,
            "pred_mean": None,
            "pred_median": None,
            "pred_p05": None,
            "pred_p25": None,
            "pred_p75": None,
            "pred_p95": None,
            "target_mean": None,
            "score": None,
        }
    mae = float(ae.mean())
    return {
        "count": count,
        "mae": mae,
        "median_ae": float(np.median(ae)),
        "max_ae": float(ae.max()),
        "signed_error": float(signed.mean()),
        "within_2": int((ae <= 2.0).sum()),
        "within_5": int((ae <= 5.0).sum()),
        "within_10": int((ae <= 10.0).sum()),
        "within_20": int((ae <= 20.0).sum()),
        "pred_min": float(preds.min()),
        "pred_max": float(preds.max()),
        "pred_mean": float(preds.mean()),
        "pred_median": float(np.median(preds)),
        "pred_p05": float(np.percentile(preds, 5)),
        "pred_p25": float(np.percentile(preds, 25)),
        "pred_p75": float(np.percentile(preds, 75)),
        "pred_p95": float(np.percentile(preds, 95)),
        "target_mean": float(targets.mean()),
        "score": float(100.0 - (mae / 180.0 * 100.0)),
    }


def evaluate_models(
    samples,
    raw_inputs,
    clahe_inputs,
    targets,
    models,
    batch_size,
    device,
    evaluation_dataset="Series 1/2 corrected real images",
    log_prefix="eval",
):
    datasets = [sample["dataset"] for sample in samples]
    sources = [sample["source"] for sample in samples]
    results = {}

    for version, path in models:
        print(f"[{log_prefix}] model={version} checkpoint={path.name}", flush=True)
        model = load_model(path, version, device)
        inputs = clahe_inputs if version in {"2.0", "2.0b"} else raw_inputs
        preds = run_model(model, inputs, batch_size, device)

        by_dataset = {}
        for dataset_name in sorted(set(datasets)):
            indices = [i for i, value in enumerate(datasets) if value == dataset_name]
            by_dataset[dataset_name] = metric_block(preds[indices], targets[indices])

        by_source = {}
        for source_name in sorted(set(sources)):
            indices = [i for i, value in enumerate(sources) if value == source_name]
            by_source[source_name] = metric_block(preds[indices], targets[indices])

        bucket_data = bucket_summary(preds, targets)
        results[version] = {
            "checkpoint": report_checkpoint_path(path),
            "series": series_for_version(version),
            "preprocessing": preprocessing_for_version(version),
            "output_head": "1 continuous steering output",
            "evaluation_dataset": evaluation_dataset,
            "output_scale_deg": scale_for_version(version),
            "overall": metric_block(preds, targets),
            "by_dataset": by_dataset,
            "by_source": by_source,
            **bucket_data,
        }

        overall = results[version]["overall"]
        print(
            f"[{log_prefix}] done model={version} mae={overall['mae']:.3f} "
            f"median={overall['median_ae']:.3f} within5={overall['within_5']}/{overall['count']}",
            flush=True,
        )

    return results


def _run_date_mmdd(run_name):
    """2026_05_10_run_1 -> '0510'."""
    m = re.search(r"\d{4}_(\d{2})_(\d{2})", str(run_name))
    return f"{m.group(1)}{m.group(2)}" if m else str(run_name)


def _image_hour(image_name):
    """...photo_20260510_201230.jpg -> 20 (24h)."""
    m = re.search(r"_(\d{8})_(\d{2})\d{4}", str(image_name))
    return int(m.group(2)) if m else 0


def _s3_source_labels(samples):
    """Apply the original D-code convention to Series 3 runs: D{MMDD} for a single
    run that day, D{MMDD}_{HH} (run start hour, 24h) when a day has multiple runs."""
    from collections import defaultdict
    run_hour = {}
    run_date = {}
    date_runs = defaultdict(set)
    for s in samples:
        run = s["run"]
        run_date[run] = s["date"]
        run_hour[run] = min(run_hour.get(run, 99), s["hour"])
        date_runs[s["date"]].add(run)
    labels = {}
    for run, date in run_date.items():
        labels[run] = f"D{date}_{run_hour[run]:02d}"   # always DMMDD_HH (run start hour, 24h)
    return labels


def _load_s3_module():
    """Load the Series 3 trainer module and its hybrid decode constants."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("s3_trainer_for_eval", S3_TRAINER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_s4_module():
    """Load the shared Series 4 data/architecture module from its trainer directory."""
    import importlib.util

    trainer_dir = str(S4_COMMON_PATH.parent)
    if trainer_dir not in sys.path:
        sys.path.insert(0, trainer_dir)
    module_name = "series_4_common_for_eval"
    spec = importlib.util.spec_from_file_location(module_name, S4_COMMON_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _decode_s3_steering(out, s3mod):
    """Decode a Series 3 model output batch -> steering degrees [0..180]. Handles BOTH
    the legacy 2-output unit-control head (v3.0/3.0b) and the v3.1+ hybrid head
    (NUM_STEER_CLASSES class logits + within-bucket offsets + 1 throttle)."""
    out = np.asarray(out, dtype=np.float32)
    k = int(getattr(s3mod, "NUM_STEER_CLASSES", 0) or 0)
    if k and out.ndim == 2 and out.shape[1] == 2 * k + 1:
        logits = out[:, 0:k]
        offset = 1.0 / (1.0 + np.exp(-out[:, k:2 * k]))          # sigmoid -> 0..1 fraction
        cls = np.argmax(logits, axis=1)                          # which bucket
        lo = np.asarray(s3mod._STEER_BIN_LO, dtype=np.float32)[cls]
        hi = np.asarray(s3mod._STEER_BIN_HI, dtype=np.float32)[cls]
        chosen = offset[np.arange(len(cls)), cls]               # offset for the picked bucket
        return np.clip(lo + chosen * (hi - lo), 0.0, 180.0)
    u0 = np.clip(out[:, 0], -1.0, 1.0)                          # legacy 2-output unit control
    return np.clip(90.0 + 90.0 * u0, 0.0, 180.0)


def evaluate_series3(models_dir, device, batch_size, versions=None):
    """Evaluate Series 3 (SidewalkPilotV3) checkpoints on the S3 dataset and return
    results entries shaped like the Series 1/2 ones (steering decoded to 0..180),
    plus the per-image samples (source/dataset) for report context. Returns ({}, [])
    if there are no S3 models or no S3 dataset yet."""
    labels_path = S3_DATASET_DIR / "labels.json"
    # accept .onnx (current artifact scheme) as well as .pt/.pth; one file per version,
    # onnx preferred > pt > pth.
    _any = re.compile(r"^SidewalkPilot-v(?P<version>3\.\d+b?)\.(?P<ext>onnx|pt|pth)$")
    by_ver = {}
    for p in sorted(models_dir.glob("SidewalkPilot-v3*")):
        m = _any.match(p.name)
        if not m:
            continue
        rank = {"onnx": 0, "pt": 1, "pth": 2}[m.group("ext")]
        v = m.group("version")
        if v not in by_ver or rank < by_ver[v][0]:
            by_ver[v] = (rank, p)
    wanted = set(versions) if versions else None
    s3_paths = [by_ver[v][1] for v in sorted(by_ver) if wanted is None or v in wanted]
    if not s3_paths or not labels_path.is_file():
        return {}, []

    s3mod = _load_s3_module()
    SidewalkPilotV3 = s3mod.SidewalkPilotV3
    labels = json.loads(labels_path.read_text())

    # Evaluate on the FULL dataset. Frames are stored as uint8 (below) so all 81k fit (~14 GB)
    # rather than the ~56 GB a float32 stack needs; each batch is normalized on the fly at inference.
    items = sorted(labels.items())

    tensors, targets, samples = [], [], []
    for name, label in items:
        frame = cv2.imread(str(S3_DATASET_DIR / name), cv2.IMREAD_COLOR)
        if frame is None:
            continue
        steer = label.get("steering") if isinstance(label, dict) else label
        if steer is None:
            continue
        img = cv2.resize(frame, (S3_WIDTH, S3_HEIGHT), interpolation=cv2.INTER_AREA)  # S3 uint8 HWC BGR
        tensors.append(np.transpose(img, (2, 0, 1)))                                  # S3 uint8 CHW (normalized per-batch)
        targets.append(label_to_servo(steer))
        run = str(name).split("__")[0]
        img_part = str(name).split("__", 1)[1] if "__" in str(name) else str(name)
        samples.append({"run": run, "date": _run_date_mmdd(run), "hour": _image_hour(img_part)})

    if not tensors:
        return {}, []

    # D-code source naming, D{MMDD}_{HH} (run start hour) per the original convention
    run_labels = _s3_source_labels(samples)
    for s in samples:
        s["dataset"] = s["source"] = run_labels[s["run"]]

    inputs_u8 = np.stack(tensors)                      # (N,3,180,320) uint8 (~14 GB for 81k) -- S3 models
    del tensors
    targets = np.array(targets, dtype=np.float32)
    datasets = [s["dataset"] for s in samples]
    sources = [s["source"] for s in samples]
    print(f"[eval.s3] dataset images={len(samples)} (full, uint8) | models={len(s3_paths)}", flush=True)

    def _norm_batch(u8):                               # uint8 (n,3,H,W) -> normalized float32
        x = u8.astype(np.float32) / 255.0
        return (x - 0.5) / 0.5

    results = {}
    for path in s3_paths:
        version = _any.match(path.name).group("version")
        print(f"[eval] model={version} checkpoint={path.name}", flush=True)
        preds = []
        if path.suffix.lower() == ".onnx":
            import onnxruntime as ort
            if device.type == "cuda" and "CUDAExecutionProvider" not in ort.get_available_providers():
                raise RuntimeError(
                    "--device cuda requested, but ONNX Runtime does not provide "
                    "CUDAExecutionProvider. Install/use onnxruntime-gpu before evaluating Series 3."
                )
            providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider")
                         if p in ort.get_available_providers()] or ["CPUExecutionProvider"]
            sess = ort.InferenceSession(str(path), providers=providers)
            print(f"[eval] model={version} ONNX providers={sess.get_providers()}", flush=True)
            iname = sess.get_inputs()[0].name
            for start in range(0, len(inputs_u8), batch_size):
                batch = _norm_batch(inputs_u8[start:start + batch_size])
                out = sess.run(None, {iname: batch})[0]
                preds.append(_decode_s3_steering(out, s3mod))
        else:
            model = SidewalkPilotV3().to(device)
            checkpoint = torch.load(path, map_location=device)
            state = checkpoint
            if isinstance(checkpoint, dict):
                for key in ("model_state_dict", "state_dict", "model"):
                    if key in checkpoint and isinstance(checkpoint[key], dict):
                        state = checkpoint[key]
                        break
            state = {key.removeprefix("module."): value for key, value in state.items()}
            model.load_state_dict(state, strict=True)
            model.eval()
            with torch.no_grad():
                for start in range(0, len(inputs_u8), batch_size):
                    batch = torch.from_numpy(_norm_batch(inputs_u8[start:start + batch_size]))
                    out = model(batch.to(device, non_blocking=True)).cpu().numpy()
                    preds.append(_decode_s3_steering(out, s3mod))
        preds = np.concatenate(preds).astype(np.float32)

        by_dataset = {}
        for name in sorted(set(datasets)):
            idx = [i for i, v in enumerate(datasets) if v == name]
            by_dataset[name] = metric_block(preds[idx], targets[idx])
        by_source = {}
        for name in sorted(set(sources)):
            idx = [i for i, v in enumerate(sources) if v == name]
            by_source[name] = metric_block(preds[idx], targets[idx])

        results[version] = {
            "checkpoint": report_checkpoint_path(path),
            "series": 3,
            "preprocessing": "raw BGR 320x180",
            "output_head": ("2 continuous controls (steering + throttle)"
                            if version in {"3.0", "3.0b"}
                            else "19 hybrid outputs (9 classes + 9 offsets + throttle)"),
            "evaluation_dataset": "Series 3 collected real images",
            "output_scale_deg": None,           # 2-output unit controls, no fixed scale
            "overall": metric_block(preds, targets),
            "by_dataset": by_dataset,
            "by_source": by_source,
            **bucket_summary(preds, targets),
        }
        overall = results[version]["overall"]
        print(f"[eval] done model={version} mae={overall['mae']:.3f} "
              f"median={overall['median_ae']:.3f} within5={overall['within_5']}/{overall['count']}",
              flush=True)

    return results, samples


def _discover_series34_paths(models_dir, versions=None):
    """Prefer ONNX artifacts and return separate Series 3 and Series 4 path lists."""
    wanted = set(versions) if versions else None
    patterns = {
        3: re.compile(r"^SidewalkPilot-v(?P<version>3\.\d+b?)\.(?P<ext>onnx|pt|pth)$"),
        4: S4_MODEL_RE,
    }
    discovered = {3: {}, 4: {}}
    rank = {"onnx": 0, "pt": 1, "pth": 2}
    for path in sorted(models_dir.glob("SidewalkPilot-v*")):
        for series, pattern in patterns.items():
            match = pattern.match(path.name)
            if match is None:
                continue
            version = match.group("version")
            if wanted is not None and version not in wanted:
                break
            candidate = (rank[match.group("ext")], path)
            if version not in discovered[series] or candidate[0] < discovered[series][version][0]:
                discovered[series][version] = candidate
            break
    return {
        series: [entries[version][1] for version in sorted(entries, key=version_key)]
        for series, entries in discovered.items()
    }


def load_series34_validation_data():
    """Build one held-out temporal subset shared by every Series 3 and Series 4 model."""
    s4mod = _load_s4_module()
    frames = s4mod.load_frames([S3_DATASET_DIR.resolve()])
    split_by_frame, _ = s4mod.frozen_series3_split(frames, 0.10, 100)
    temporal, stats = s4mod.build_temporal_samples(
        frames,
        split_by_frame,
        history_steps=3,
        future_steps=3,
        max_gap_sec=0.25,
    )
    validation = [sample for sample in temporal if sample.split == "val"]
    if not validation:
        raise ValueError("Series 3/4 temporal validation subset is empty.")

    tensors = []
    histories = []
    targets = []
    samples = []
    for index, sample in enumerate(validation, start=1):
        frame = cv2.imread(str(sample.anchor.path), cv2.IMREAD_COLOR)
        if frame is None:
            raise FileNotFoundError(sample.anchor.path)
        image = s4mod.S3.resize_image_uint8(frame, S3_WIDTH, S3_HEIGHT, 0.0)
        tensors.append(np.transpose(image, (2, 0, 1)))
        histories.append(sample.history)
        targets.append(sample.targets[0])
        image_name = sample.anchor.path.name
        run = image_name.split("__", 1)[0]
        image_part = image_name.split("__", 1)[1] if "__" in image_name else image_name
        samples.append({
            "run": run,
            "date": _run_date_mmdd(run),
            "hour": _image_hour(image_part),
            "image": str(sample.anchor.path),
            "steering": float(sample.targets[0]),
        })
        if index % 500 == 0 or index == len(validation):
            print(f"[images.s34] loaded={index}/{len(validation)}", flush=True)

    run_labels = _s3_source_labels(samples)
    for sample in samples:
        sample["dataset"] = sample["source"] = run_labels[sample["run"]]

    inputs_u8 = np.stack(tensors)
    history_values = np.asarray(histories, dtype=np.float32)
    current_targets = np.asarray(targets, dtype=np.float32)
    hold_last_mae = float(np.mean(np.abs(history_values[:, -1] - current_targets)))
    print(
        f"[eval.s34] common validation images={len(samples)} hold_last_mae={hold_last_mae:.3f} "
        f"sequence_stats={stats}",
        flush=True,
    )
    return {
        "inputs_u8": inputs_u8,
        "histories": history_values,
        "targets": current_targets,
        "samples": samples,
        "hold_last_mae": hold_last_mae,
    }


def _normalized_image_batch(inputs_u8, start, stop):
    batch = inputs_u8[start:stop].astype(np.float32) / 255.0
    return (batch - 0.5) / 0.5


def _onnx_session(path, device):
    import onnxruntime as ort

    available = ort.get_available_providers()
    if device.type == "cuda" and "CUDAExecutionProvider" not in available:
        raise RuntimeError(
            "--device cuda requested, but ONNX Runtime does not provide CUDAExecutionProvider. "
            "Install onnxruntime-gpu before running the report."
        )
    providers = [
        provider
        for provider in ("CUDAExecutionProvider", "CPUExecutionProvider")
        if provider in available and (device.type == "cuda" or provider == "CPUExecutionProvider")
    ] or ["CPUExecutionProvider"]
    session = ort.InferenceSession(str(path), providers=providers)
    print(f"[eval] model={path.stem.removeprefix('SidewalkPilot-v')} ONNX providers={session.get_providers()}", flush=True)
    return session


def _decode_s4_current(output, s3mod):
    output = np.asarray(output, dtype=np.float32)
    if output.ndim != 3 or output.shape[2] != 18:
        raise ValueError(f"Unexpected Series 4 output shape: {output.shape}")
    current = output[:, 0, :]
    logits = current[:, :9]
    offsets = 1.0 / (1.0 + np.exp(-current[:, 9:18]))
    classes = np.argmax(logits, axis=1)
    lows = np.asarray(s3mod._STEER_BIN_LO, dtype=np.float32)[classes]
    highs = np.asarray(s3mod._STEER_BIN_HI, dtype=np.float32)[classes]
    chosen = offsets[np.arange(len(classes)), classes]
    return np.clip(lows + chosen * (highs - lows), 0.0, 180.0)


def _series34_result(path, version, series, preds, data, output_head):
    targets = data["targets"]
    samples = data["samples"]
    datasets = [sample["dataset"] for sample in samples]
    sources = [sample["source"] for sample in samples]
    by_dataset = {}
    for name in sorted(set(datasets)):
        indices = [index for index, value in enumerate(datasets) if value == name]
        by_dataset[name] = metric_block(preds[indices], targets[indices])
    by_source = {}
    for name in sorted(set(sources)):
        indices = [index for index, value in enumerate(sources) if value == name]
        by_source[name] = metric_block(preds[indices], targets[indices])
    return {
        "checkpoint": report_checkpoint_path(path),
        "series": series,
        "preprocessing": "raw BGR 320x180",
        "output_head": output_head,
        "evaluation_dataset": "Series 3/4 frozen temporal validation subset",
        "output_scale_deg": None,
        "hold_last_mae_deg": data["hold_last_mae"],
        "overall": metric_block(preds, targets),
        "by_dataset": by_dataset,
        "by_source": by_source,
        **bucket_summary(preds, targets),
    }


def evaluate_series34(models_dir, device, batch_size, versions=None, data=None):
    """Evaluate Series 3 and 4 on one sequence-valid held-out set for direct comparison."""
    paths = _discover_series34_paths(models_dir, versions)
    if not paths[3] and not paths[4]:
        return {}, []
    if data is None:
        data = load_series34_validation_data()
    s3mod = _load_s3_module()
    results = {}

    for path in paths[3]:
        if path.suffix.lower() != ".onnx":
            raise RuntimeError(f"Series 3 report evaluation requires ONNX: {path}")
        version = re.match(r"^SidewalkPilot-v(.+)\.onnx$", path.name).group(1)
        print(f"[eval] model={version} checkpoint={path.name}", flush=True)
        session = _onnx_session(path, device)
        image_name = session.get_inputs()[0].name
        predictions = []
        for start in range(0, len(data["inputs_u8"]), batch_size):
            batch = _normalized_image_batch(data["inputs_u8"], start, start + batch_size)
            output = session.run(None, {image_name: batch})[0]
            predictions.append(_decode_s3_steering(output, s3mod))
        preds = np.concatenate(predictions).astype(np.float32)
        output_head = (
            "2 continuous controls (steering + throttle)"
            if version in {"3.0", "3.0b"}
            else "19 hybrid outputs (9 classes + 9 offsets + throttle)"
        )
        results[version] = _series34_result(path, version, 3, preds, data, output_head)
        overall = results[version]["overall"]
        print(f"[eval] done model={version} mae={overall['mae']:.3f} median={overall['median_ae']:.3f}", flush=True)

    for path in paths[4]:
        if path.suffix.lower() != ".onnx":
            raise RuntimeError(f"Series 4 report evaluation requires ONNX: {path}")
        match = S4_MODEL_RE.match(path.name)
        version = match.group("version")
        print(f"[eval] model={version} checkpoint={path.name}", flush=True)
        session = _onnx_session(path, device)
        input_defs = session.get_inputs()
        image_def = next(item for item in input_defs if item.name == "image" or len(item.shape) == 4)
        history_defs = [item for item in input_defs if item.name != image_def.name]
        predictions = []
        horizon_count = None
        for start in range(0, len(data["inputs_u8"]), batch_size):
            stop = min(start + batch_size, len(data["inputs_u8"]))
            feeds = {image_def.name: _normalized_image_batch(data["inputs_u8"], start, stop)}
            if history_defs:
                feeds[history_defs[0].name] = data["histories"][start:stop]
            output = session.run(None, feeds)[0]
            horizon_count = int(output.shape[1])
            predictions.append(_decode_s4_current(output, s3mod))
        preds = np.concatenate(predictions).astype(np.float32)
        contract = "PCF" if history_defs and horizon_count > 1 else ("PC" if history_defs else "CF")
        output_head = f"{contract}: {horizon_count} x 18 hybrid steering outputs"
        results[version] = _series34_result(path, version, 4, preds, data, output_head)
        overall = results[version]["overall"]
        print(f"[eval] done model={version} mae={overall['mae']:.3f} median={overall['median_ae']:.3f}", flush=True)

    return results, data["samples"]


def fmt_num(value, digits=2):
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits=3):
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}%"


def paragraph(text, style):
    return Paragraph(str(text), style)


def table_style(header_color=colors.HexColor("#1f2937"), zebra=True):
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if zebra:
        commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]))
    return TableStyle(commands)


def add_rank_coloring(table, rows, mae_col, score_col=None):
    commands = []
    for row_index in range(1, len(rows)):
        try:
            mae = float(rows[row_index][mae_col])
        except (TypeError, ValueError):
            continue
        if mae <= 5.0:
            fill = colors.HexColor("#dcfce7")
        elif mae <= 10.0:
            fill = colors.HexColor("#fef9c3")
        elif mae <= 20.0:
            fill = colors.HexColor("#ffedd5")
        else:
            fill = colors.HexColor("#fee2e2")
        commands.append(("BACKGROUND", (mae_col, row_index), (mae_col, row_index), fill))
        if score_col is not None:
            commands.append(("BACKGROUND", (score_col, row_index), (score_col, row_index), fill))
    table.setStyle(TableStyle(commands))


def _table_number(value):
    text = str(value).strip()
    if text.endswith("%"):
        text = text[:-1]
    return float(text)


def add_metric_gradients(table, rows, column_rules):
    """Apply an independent red-yellow-green scale to each metric column.

    Rules are "high" (larger is better), "low" (smaller is better), or "zero"
    (smaller absolute value is better). Each table is scaled independently so
    values from different evaluation datasets are never compared by color.
    """
    commands = []
    cmap = plt.get_cmap("RdYlGn")
    for column, rule in column_rules.items():
        parsed = []
        for row_index in range(1, len(rows)):
            try:
                value = _table_number(rows[row_index][column])
            except (TypeError, ValueError):
                continue
            score = value if rule == "high" else (-abs(value) if rule == "zero" else -value)
            parsed.append((row_index, score))
        if not parsed:
            continue
        lo = min(score for _, score in parsed)
        hi = max(score for _, score in parsed)
        span = hi - lo
        for row_index, score in parsed:
            fraction = 0.5 if span == 0 else (score - lo) / span
            red, green, blue, _ = cmap(fraction)
            # Pastel fill keeps black table text readable while retaining the full gradient.
            mix = 0.58
            fill = colors.Color(
                1.0 - mix * (1.0 - red),
                1.0 - mix * (1.0 - green),
                1.0 - mix * (1.0 - blue),
            )
            commands.append(("BACKGROUND", (column, row_index), (column, row_index), fill))
    table.setStyle(TableStyle(commands))


def rank_versions(results, versions):
    return sorted(
        versions,
        key=lambda version: (
            -results[version]["selection_metrics"]["balanced_9_bucket_exact_percent"],
            -results[version]["selection_metrics"]["turn_within_one_bucket_recall_percent"],
            results[version]["overall"]["mae"],
        ),
    )


def ranking_rows(results, ranked):
    rows = [["Rank", "Model", "Checkpoint filename", "Prep", "Bal9", "Turn exact", "Turn +/-1", "ST exact", "MAE", "Med", "Signed"]]
    for rank, version in enumerate(ranked, start=1):
        overall = results[version]["overall"]
        selection = results[version]["selection_metrics"]
        rows.append(
            [
                str(rank),
                version,
                Path(results[version]["checkpoint"]).name,
                results[version]["preprocessing"],
                fmt_pct(selection["balanced_9_bucket_exact_percent"], 1),
                fmt_pct(selection["turn_exact_bucket_recall_percent"], 1),
                fmt_pct(selection["turn_within_one_bucket_recall_percent"], 1),
                fmt_pct(selection["straight_exact_bucket_recall_percent"], 1),
                fmt_num(overall["mae"]),
                fmt_num(overall["median_ae"]),
                fmt_num(overall["signed_error"]),
            ]
        )
    return rows


def build_line_chart(results, title, versions):
    xs = list(range(len(versions)))
    maes = [results[v]["overall"]["mae"] for v in versions]
    fig, ax = plt.subplots(figsize=(9.2, 3.2), dpi=170)
    ax.plot(xs, maes, marker="o", linewidth=2.0, color="#2563eb")
    ax.set_title(title)
    ax.set_ylabel("MAE (servo deg)")
    ax.set_xticks(xs)
    ax.set_xticklabels(versions, rotation=60, ha="right", fontsize=7)
    ax.grid(True, axis="y", alpha=0.25)
    best_index = int(np.argmin(maes))
    ax.scatter([best_index], [maes[best_index]], color="#16a34a", s=55, zorder=3)
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


def build_bar_chart(results, title, versions):
    maes = [results[v]["overall"]["mae"] for v in versions]
    # Smooth red->green gradient by MAE: best (lowest MAE) = green, worst = red, with the
    # full red-orange-yellow-green ramp in between (instead of 4 discrete tiers).
    lo, hi = min(maes), max(maes)
    rng = (hi - lo) or 1.0
    cmap = plt.get_cmap("RdYlGn_r")   # _r so LOW value -> green, HIGH -> red
    colors_by_value = [cmap((value - lo) / rng) for value in maes]
    fig, ax = plt.subplots(figsize=(9.2, 3.4), dpi=170)
    ax.bar(versions, maes, color=colors_by_value)
    ax.set_title(title)
    ax.set_ylabel("MAE (servo deg)")
    ax.tick_params(axis="x", labelrotation=60, labelsize=7)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


def make_table(rows, col_widths=None, repeat_rows=1, header_color=colors.HexColor("#1f2937")):
    table = Table(rows, colWidths=col_widths, repeatRows=repeat_rows)
    table.setStyle(table_style(header_color=header_color))
    return table


def build_pdf(results, samples, s34_samples, pdf_out):
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCenter",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        fontSize=18,
        leading=22,
        spaceAfter=10,
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor("#111827"), spaceBefore=8)
    normal = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=8.5, leading=11)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=7, leading=9)

    versions = sorted(results, key=version_key)
    series1 = [version for version in versions if series_for_version(version) == 1]
    series2 = [version for version in versions if series_for_version(version) == 2]
    series3 = [version for version in versions if series_for_version(version) == 3]
    series4 = [version for version in versions if series_for_version(version) == 4]
    series12 = series1 + series2
    historical12 = {
        version: results[version].get("historical_evaluation", results[version])
        for version in series12
    }
    ranked12 = rank_versions(historical12, series12)
    ranked = rank_versions(results, versions)
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    doc = SimpleDocTemplate(
        str(pdf_out),
        pagesize=landscape(letter),
        rightMargin=0.35 * inch,
        leftMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch,
        title="SidewalkPilot Steering Model Report",
    )
    story = []
    story.append(paragraph("SidewalkPilot Steering Model Report", title_style))
    story.append(paragraph("Common challenge-set current-label offline evaluation", h2))
    story.append(
        paragraph(
            f"Generated {generated}. Every checkpoint is ranked on the same {len(s34_samples):,}-image frozen temporal "
            "validation subset from the shared 81,237-frame dataset. Series 1/2 images are resized to their required 200x66 "
            "input and use their original model-specific preprocessing; Series 3/4 use 320x180. The original "
            f"{len(samples):,}-image Series 1/2 evaluation is retained as a separate historical table, but it is not used for "
            "cross-generation ranking. Each Series 4 generation uses paired experiment names: p/r for PC, f/g for CF, "
            "and a/c for PCF (final/best respectively).",
            normal,
        )
    )
    if ranked:
        best = ranked[0]
        lowest_mae = min(ranked, key=lambda version: results[version]["overall"]["mae"])
        metrics = results[best]["selection_metrics"]
        story.append(paragraph(
            f"All-series class-balanced leader on the shared challenge set: {best}, with Bal9 "
            f"{metrics['balanced_9_bucket_exact_percent']:.1f}%, turn exact "
            f"{metrics['turn_exact_bucket_recall_percent']:.1f}%, and turn +/-1 "
            f"{metrics['turn_within_one_bucket_recall_percent']:.1f}%. Lowest shared-set MAE: {lowest_mae} at "
            f"{results[lowest_mae]['overall']['mae']:.3f} deg.", normal))
    story.append(
        paragraph(
            "Series 1 uses raw BGR and output scale 86. Series 2 uses output scale 85; v2.0/v2.0b use legacy HSV/CLAHE "
            "preprocessing, while v2.1 and newer use raw BGR. Series 1/2 produce one continuous steering value. Series 3.0 "
            "and 3.0b produce two continuous values (steering and throttle). Series 3.1 and newer produce 19 raw values: "
            "9 steering-class logits, 9 within-class offsets, and throttle. Series 4 removes throttle and emits one or four "
            "18-value hybrid steering horizons; PC/PCF also consume three previous targets. Every architecture is decoded to "
            "current steering degrees before the common metrics are calculated.",
            normal,
        )
    )

    source_groups = (
        ("Series 1/2 Historical", samples),
        ("All-Series Shared Challenge", s34_samples),
    )
    for label, group_samples in source_groups:
        source_counts = Counter(sample["dataset"] for sample in group_samples)
        source_rows = [["Source", "Count", "Purpose"]]
        for source_name in sorted(source_counts):
            source_rows.append([source_name, str(source_counts[source_name]), SOURCE_PURPOSES.get(source_name, "")])
        story.append(KeepTogether([
            Spacer(1, 0.08 * inch),
            paragraph(f"{label} Evaluation Sources", h2),
            make_table(
                source_rows,
                col_widths=[1.0 * inch, 0.7 * inch, 7.2 * inch],
                header_color=colors.HexColor("#334155"),
            ),
        ]))

    story.append(Spacer(1, 0.16 * inch))
    ranking_groups = (
        ("Series 1/2 Historical", historical12, ranked12),
        ("All-Series Shared Challenge", results, ranked),
    )
    for group_index, (label, ranking_results, group) in enumerate(ranking_groups):
        if not group:
            continue
        if group_index:
            story.append(PageBreak())
        rank_rows = ranking_rows(ranking_results, group)
        story.append(paragraph(f"{label} Class-Balanced Model Ranking", h2))
        story.append(paragraph(
            "Ranked by macro-average exact recall across the 9 steering buckets, then turn within-one-bucket recall, then MAE. "
            "Each metric column has its own red-yellow-green scale: green means better within this table. Signed error is "
            "greenest nearest zero. Only the shared-challenge table supports cross-series comparison.", small))
        rank_table = make_table(
            rank_rows,
            col_widths=[0.34 * inch, 0.43 * inch, 1.45 * inch, 1.0 * inch, 0.48 * inch, 0.62 * inch, 0.62 * inch, 0.55 * inch, 0.47 * inch, 0.47 * inch, 0.5 * inch],
            header_color=colors.HexColor("#0f766e"),
        )
        add_metric_gradients(
            rank_table,
            rank_rows,
            {4: "high", 5: "high", 6: "high", 7: "high", 8: "low", 9: "low", 10: "zero"},
        )
        story.append(rank_table)
        story.append(Spacer(1, 0.16 * inch))

    story.append(PageBreak())
    growth_rows = [["Model", "Checkpoint filename", "Series", "Eval set", "Prep", "Scale", "MAE", "Median", "Signed", "<=2", "<=5", "<=20", "Pred mean"]]
    for version in versions:
        overall = results[version]["overall"]
        growth_rows.append(
            [
                version,
                Path(results[version]["checkpoint"]).name,
                str(results[version]["series"]),
                "Shared",
                results[version]["preprocessing"],
                (f"{results[version]['output_scale_deg']:.0f}"
                 if results[version]["output_scale_deg"] is not None else "-"),
                fmt_num(overall["mae"]),
                fmt_num(overall["median_ae"]),
                fmt_num(overall["signed_error"]),
                str(overall["within_2"]),
                str(overall["within_5"]),
                str(overall["within_20"]),
                fmt_num(overall["pred_mean"]),
            ]
        )
    story.append(paragraph("Chronological Model Growth", h2))
    story.append(paragraph(
        "Every row uses the same 6,952-anchor shared challenge set, so the metrics are directly comparable across series.", small))
    growth_table = make_table(
        growth_rows,
        col_widths=[0.42 * inch, 1.45 * inch, 0.4 * inch, 0.48 * inch, 0.95 * inch, 0.4 * inch, 0.45 * inch, 0.45 * inch, 0.48 * inch, 0.42 * inch, 0.42 * inch, 0.47 * inch, 0.54 * inch],
        header_color=colors.HexColor("#1d4ed8"),
    )
    story.append(growth_table)

    story.append(PageBreak())
    subset_groups = (
        ("Series 1/2 Historical", historical12, ranked12),
        ("All-Series Shared Challenge", results, ranked),
    )
    for label, subset_results, group in subset_groups:
        if not group:
            continue
        dataset_names = sorted({name for version in group for name in subset_results[version]["by_dataset"]})
        subset_rows = [["Model"] + dataset_names]
        for version in group:
            row = [version]
            for dataset_name in dataset_names:
                block = subset_results[version]["by_dataset"].get(dataset_name)
                row.append(fmt_num(block["mae"]) if block else "-")
            subset_rows.append(row)
        story.append(paragraph(f"{label} Field-Case / Subset MAE", h2))
        story.append(paragraph("Lower is better. All rows in this table use the same evaluation dataset.", small))
        subset_col_widths = [0.48 * inch] + [min(0.78, 9.0 / max(1, len(dataset_names))) * inch for _ in dataset_names]
        subset_table = make_table(subset_rows, col_widths=subset_col_widths, header_color=colors.HexColor("#7c2d12"))
        story.append(subset_table)
        story.append(Spacer(1, 0.14 * inch))

    story.append(PageBreak())
    dist_rows = [["Model", "Pred min", "P05", "P25", "Median", "P75", "P95", "Pred max", "Pred mean", "Target mean"]]
    for version in ranked:
        overall = results[version]["overall"]
        dist_rows.append(
            [
                version,
                fmt_num(overall["pred_min"]),
                fmt_num(overall["pred_p05"]),
                fmt_num(overall["pred_p25"]),
                fmt_num(overall["pred_median"]),
                fmt_num(overall["pred_p75"]),
                fmt_num(overall["pred_p95"]),
                fmt_num(overall["pred_max"]),
                fmt_num(overall["pred_mean"]),
                fmt_num(overall["target_mean"]),
            ]
        )
    story.append(paragraph("Prediction Distribution", h2))
    story.append(make_table(dist_rows, col_widths=[0.5 * inch] + [0.72 * inch] * 9, header_color=colors.HexColor("#6d28d9")))

    bucket_rows = [["Model"] + [name for name, _, _ in BUCKETS] + ["Exact", "Off by <=1"]]
    for version in ranked:
        agreement = results[version]["bucket_agreement"]
        row = [version]
        row.extend(str(results[version]["prediction_bucket_counts"][name]) for name, _, _ in BUCKETS)
        row.append(f"{agreement['exact_bucket_percent']:.1f}%")
        row.append(f"{agreement['off_by_one_bucket_percent']:.1f}%")
        bucket_rows.append(row)
    story.append(Spacer(1, 0.1 * inch))
    story.append(paragraph("Prediction Buckets vs Ground", h2))
    story.append(paragraph("Bucket columns show prediction counts; exact/off-by-one compare prediction bucket against ground bucket.", small))
    story.append(make_table(bucket_rows, col_widths=[0.5 * inch] + [0.65 * inch] * 7 + [0.6 * inch, 0.75 * inch], header_color=colors.HexColor("#be123c")))

    story.append(PageBreak())
    story.append(paragraph("Shared Challenge-Set Graphs", h2))
    graph_specs = [
        ("Graph 1: Series 1 on shared challenge set", series1, build_line_chart),
        ("Graph 2: Series 2 on shared challenge set", series2, build_line_chart),
    ]
    if series3:
        graph_specs.append(("Graph 3: Series 3 on shared challenge set", series3, build_line_chart))
    if series4:
        graph_specs.append(("Graph 4: Series 4 on shared challenge set", series4, build_line_chart))
    graph_specs.append((
        f"Graph {len(graph_specs) + 1}: All series MAE (shared set; green=lower, red=higher)",
        versions,
        build_bar_chart,
    ))
    for title, chart_versions, chart_fn in graph_specs:
        if not chart_versions:
            continue
        image_data = chart_fn(results, title, chart_versions)
        story.append(KeepTogether([
            paragraph(title, h2),
            Image(image_data, width=9.1 * inch, height=3.1 * inch),
        ]))

    # Keep the confusion-matrix section bounded to the eight newest hybrid checkpoints.
    recent_hybrid = sorted(
        (v for v in versions if results[v].get("series") in {3, 4}
         and "bucket9_confusion_ground_rows_pred_cols" in results[v]),
        key=version_key, reverse=True)[:8]
    if recent_hybrid:
        story.append(PageBreak())
        story.append(paragraph("Steering-Bucket Confusion (9-class) - latest Series 3/4 models", h2))
        story.append(paragraph(
            "Rows = the TRUE steering bucket, columns = the model's PREDICTED bucket. "
            "Green diagonal = correct; red off-diagonal = confusion. Shading = share of that true "
            "bucket (each row sums to ~100%). Buckets: HL 0-45, L 45-60, L+ 60-75, SL 75-85, "
            "ST 85-95, SR 95-105, R 105-120, R+ 120-135, HR 135-180.", small))
        labels9 = [name for name, _, _ in BUCKETS9]
        for version in recent_hybrid:
            conf = results[version]["bucket9_confusion_ground_rows_pred_cols"]
            grand = max(1, sum(sum(conf[r].values()) for r in labels9))
            exact9 = sum(conf[labels9[i]][labels9[i]] for i in range(9))
            near9 = sum(conf[labels9[i]][labels9[j]] for i in range(9) for j in range(9) if abs(i - j) <= 1)
            data = [["T\\P"] + labels9]
            tstyle = [
                ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ]
            for ri, rname in enumerate(labels9):
                vals = [conf[rname][cn] for cn in labels9]
                total = max(1, sum(vals))
                data.append([rname] + [str(v) if v else "·" for v in vals])
                for ci, v in enumerate(vals):
                    frac = v / total
                    tr, tg, tb = (0.13, 0.60, 0.30) if ci == ri else (0.85, 0.20, 0.20)
                    cell = (ci + 1, ri + 1)
                    tstyle.append(("BACKGROUND", cell, cell,
                                   colors.Color(1 + frac * (tr - 1), 1 + frac * (tg - 1), 1 + frac * (tb - 1))))
                    if frac > 0.55:
                        tstyle.append(("TEXTCOLOR", cell, cell, colors.white))
            table = Table(data, colWidths=[0.8 * inch] + [0.66 * inch] * 9, repeatRows=1)
            table.setStyle(TableStyle(tstyle))
            story.append(KeepTogether([
                Spacer(1, 0.08 * inch),
                paragraph(
                    f"v{version} &nbsp;&middot;&nbsp; exact bucket {exact9 * 100.0 / grand:.0f}% "
                    f"&nbsp;&middot;&nbsp; within one bucket {near9 * 100.0 / grand:.0f}%", normal),
                table,
            ]))

    story.append(PageBreak())
    story.append(paragraph("Notes", h2))
    notes = [
        f"All {len(results)} checkpoints in this report were evaluated on the same {len(s34_samples):,} sequence-valid frozen validation anchors, so the top-level cross-series metrics are directly comparable.",
        f"The original {len(samples):,}-image Series 1/2 evaluation is retained under historical_evaluation in the JSON and in explicitly historical PDF tables.",
        "Series 2 v2.0/v2.0b used their required HSV/CLAHE preprocessing; all other Series 1/2 models used raw BGR.",
        "MAE and within-degree counts can reward straight collapse. Use the class-balanced and turn-recall columns for selection, with MAE as supporting evidence.",
        "Offline MAE does not prove real-world reliability. The car can still fail on lighting, turns, driveways, road-edge ambiguity, speed, and sensor conditions.",
        "The shared-set comparison measures each complete checkpoint and training pipeline. It does not isolate architecture from differences in training data or augmentation.",
        "Historical checkpoint source mixes are not inferred from trainer defaults. A model should be called CARLA-assisted only when its saved command, run configuration, or source-count log proves that CARLA roots were used.",
        "The Series 3/4 report set is held out by the frozen 100-frame window split and requires three valid previous and three valid future frames without split crossings or timestamp gaps.",
        f"The shared source dataset contains 81,237 curated real field frames across five manual-driving runs from July 2 through July 12, 2026; {len(s34_samples):,} anchors satisfy the common report contract.",
        "The hold-last baseline repeats the most recent previous target. It is a persistence reference for Series 4 history models, not a deployed controller behavior.",
        "Series 3 throttle labels are near-constant at full throttle, so this report evaluates steering only; throttle control remains disabled pending varied-throttle data.",
        "The July 13 field comparison selected v3.4 from the cases presented. A later supervised comparison found v4.0f viable but not clearly better than v3.4; v4.0p/v4.0r/v4.0a/v4.0c repeatedly held prior steering predictions and were not drivable. The v4.1 checkpoints are offline-only pending runtime integration and field testing.",
    ]
    for note in notes:
        story.append(paragraph(f"- {note}", normal))

    doc.build(story)


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate SidewalkPilot steering checkpoints and regenerate the PDF report.")
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--corrections", type=Path, default=CORRECTIONS_PATH)
    parser.add_argument("--s12-dataset-dir", type=Path, default=S12_DATASET_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--pdf-out", type=Path, default=DEFAULT_PDF_OUT)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--versions", nargs="*", help="Optional versions to evaluate, such as 2.4 2.4b. Default: all discovered models.")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.device == "cuda":
        device = torch.device("cuda")
    elif args.device == "cpu":
        device = torch.device("cpu")
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"[start] device={device}", flush=True)
    models = discover_models(args.models_dir)
    if args.versions:
        wanted = set(args.versions)
        models = [(version, path) for version, path in models if version in wanted]

    results = {}
    historical_results = {}
    samples = []
    if models:
        samples = load_samples(args.corrections, args.s12_dataset_dir)
        raw_inputs, clahe_inputs, targets = load_tensors(samples, "images.historical")
        historical_results = evaluate_models(
            samples,
            raw_inputs,
            clahe_inputs,
            targets,
            models,
            args.batch_size,
            device,
            evaluation_dataset="Series 1/2 corrected real images (historical)",
            log_prefix="eval.historical",
        )
        del raw_inputs, clahe_inputs, targets

    s34_data = load_series34_validation_data()
    if models:
        challenge_samples = s34_data["samples"]
        raw_inputs, clahe_inputs, targets = load_tensors(challenge_samples, "images.challenge.s12")
        challenge_results = evaluate_models(
            challenge_samples,
            raw_inputs,
            clahe_inputs,
            targets,
            models,
            args.batch_size,
            device,
            evaluation_dataset="Series 3/4 frozen temporal validation subset (200x66 input)",
            log_prefix="eval.challenge.s12",
        )
        del raw_inputs, clahe_inputs, targets
        for version, result in challenge_results.items():
            result["historical_evaluation"] = historical_results[version]
        results.update(challenge_results)

    s34_results, s34_samples = evaluate_series34(
        args.models_dir,
        device,
        args.batch_size,
        versions=wanted if args.versions else None,
        data=s34_data,
    )
    if not s34_samples:
        s34_samples = s34_data["samples"]
    results.update(s34_results)
    print(
        f"[start] models={len(results)} s12_samples={len(samples)} s34_samples={len(s34_samples)}",
        flush=True,
    )

    if not results:
        raise FileNotFoundError(f"No SidewalkPilot checkpoints found in {args.models_dir}")

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.pdf_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(results, indent=2) + "\n")
    build_pdf(results, samples, s34_samples, args.pdf_out)
    print(f"[done] wrote {args.json_out}", flush=True)
    print(f"[done] wrote {args.pdf_out}", flush=True)


if __name__ == "__main__":
    main()
