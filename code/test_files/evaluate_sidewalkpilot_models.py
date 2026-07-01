#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import math
import re
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
REPO_ROOT = SCRIPT_DIR.parents[1]            # code/test_files -> repo root
MODELS_DIR = REPO_ROOT / "code" / "ai_models"
CORRECTIONS_PATH = REPO_ROOT / "code" / "ai_models_datasets" / "series_1_and_2" / "steering_corrections.json"
DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_JSON_OUT = DOCS_DIR / "steering_eval_current_labels.json"
DEFAULT_PDF_OUT = DOCS_DIR / "steering_model_report.pdf"

WIDTH = 200
HEIGHT = 66
SERIES_1_SCALE_DEG = 86.0
SERIES_2_SCALE_DEG = 85.0
MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>\d+\.\d+b?)\.pth$")

# Series 3 (heavy 2-output SidewalkPilotV3, 320x180). Evaluated on its OWN dataset
# (the new collected runs), not the Series 1/2 correction label set — so its rows
# are folded into the same report with that caveat noted.
S3_WIDTH = 320
S3_HEIGHT = 180
S3_DATASET_DIR = REPO_ROOT / "code" / "ai_models_datasets" / "series_3" / "sidewalkpilot_dataset"
S3_TRAINER_PATH = REPO_ROOT / "code" / "ai_models_datasets" / "series_3" / "sidewalkpilot_trainer.py"
S3_MODEL_RE = re.compile(r"^SidewalkPilot-v(?P<version>3\.\d+b?)\.pth$")

BUCKETS = [
    ("HL 0-45", 0.0, 45.0),
    ("L 45-75", 45.0, 75.0),
    ("SL 75-85", 75.0, 85.0),
    ("ST 85-95", 85.0, 95.0),
    ("SR 95-105", 95.0, 105.0),
    ("R 105-135", 105.0, 135.0),
    ("HR 135-180", 135.0, 180.0),
]

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
    suffix = 1 if version.endswith("b") else 0
    base = version[:-1] if suffix else version
    major, minor = base.split(".")
    return int(major), int(minor), suffix


def discover_models(models_dir):
    """Series 1/2 checkpoints only (SteeringAutonomyV2 arch). Series 3 is handled
    separately by evaluate_series3()."""
    models = []
    for path in sorted(models_dir.glob("SidewalkPilot-v*.pth")):
        match = MODEL_RE.match(path.name)
        if match and not match.group("version").startswith("3."):
            models.append((match.group("version"), path))
    return sorted(models, key=lambda item: version_key(item[0]))


def series_for_version(version):
    if version.startswith("3."):
        return 3
    return 2 if version.startswith("2.") else 1


def preprocessing_for_version(version):
    if version.startswith("3."):
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


def resolve_image_path(corrections_path, item):
    raw = item.get("image") or item.get("image_path") or item.get("path") or item.get("file")
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_absolute() and path.is_file():
        return path
    candidates = [
        corrections_path.parent / path,
        REPO_ROOT / path,
        REPO_ROOT / "code" / "ai_models_datasets" / "series_1_and_2" / path,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_samples(corrections_path):
    items = json.loads(corrections_path.read_text())
    if not isinstance(items, list):
        raise ValueError(f"{corrections_path} must contain a list")

    samples = []
    missing = []
    for index, item in enumerate(items):
        img_path = resolve_image_path(corrections_path, item)
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


def load_tensors(samples):
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
            print(f"[images] loaded={index}/{len(samples)}", flush=True)

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
    count = max(1, len(targets))
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


def evaluate_models(samples, raw_inputs, clahe_inputs, targets, models, batch_size, device):
    datasets = [sample["dataset"] for sample in samples]
    sources = [sample["source"] for sample in samples]
    results = {}

    for version, path in models:
        print(f"[eval] model={version} checkpoint={path.name}", flush=True)
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
            "checkpoint": str(path.resolve()),
            "series": series_for_version(version),
            "preprocessing": preprocessing_for_version(version),
            "output_scale_deg": scale_for_version(version),
            "overall": metric_block(preds, targets),
            "by_dataset": by_dataset,
            "by_source": by_source,
            **bucket_data,
        }

        overall = results[version]["overall"]
        print(
            f"[eval] done model={version} mae={overall['mae']:.3f} "
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


def _load_s3_arch():
    """Load SidewalkPilotV3 from the series_3 trainer without a sys.path name clash
    (both series have a sidewalkpilot_trainer.py)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("s3_trainer_for_eval", S3_TRAINER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SidewalkPilotV3


def evaluate_series3(models_dir, device, batch_size):
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
    s3_paths = [by_ver[v][1] for v in sorted(by_ver)]
    if not s3_paths or not labels_path.is_file():
        return {}, []

    SidewalkPilotV3 = _load_s3_arch()
    labels = json.loads(labels_path.read_text())

    tensors, targets, samples = [], [], []
    for name, label in labels.items():
        frame = cv2.imread(str(S3_DATASET_DIR / name), cv2.IMREAD_COLOR)
        if frame is None:
            continue
        steer = label.get("steering") if isinstance(label, dict) else label
        if steer is None:
            continue
        img = cv2.resize(frame, (S3_WIDTH, S3_HEIGHT), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        tensors.append(np.transpose(img, (2, 0, 1)))
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

    inputs_np = np.stack(tensors).astype(np.float32)   # for onnxruntime
    inputs = torch.from_numpy(inputs_np)               # for torch
    targets = np.array(targets, dtype=np.float32)
    datasets = [s["dataset"] for s in samples]
    sources = [s["source"] for s in samples]
    print(f"[eval.s3] dataset images={len(samples)}", flush=True)

    results = {}
    for path in s3_paths:
        version = _any.match(path.name).group("version")
        print(f"[eval] model={version} checkpoint={path.name}", flush=True)
        preds = []
        if path.suffix.lower() == ".onnx":
            import onnxruntime as ort
            providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider")
                         if p in ort.get_available_providers()] or ["CPUExecutionProvider"]
            sess = ort.InferenceSession(str(path), providers=providers)
            iname = sess.get_inputs()[0].name
            for start in range(0, len(inputs_np), batch_size):
                out = sess.run(None, {iname: inputs_np[start:start + batch_size]})[0]
                u0 = np.clip(out[:, 0], -1.0, 1.0)            # decode steering control -> 0..180
                preds.append(np.clip(90.0 + 90.0 * u0, 0.0, 180.0))
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
                for start in range(0, len(inputs), batch_size):
                    out = model(inputs[start:start + batch_size].to(device, non_blocking=True)).cpu().numpy()
                    u0 = np.clip(out[:, 0], -1.0, 1.0)        # decode steering control -> 0..180
                    preds.append(np.clip(90.0 + 90.0 * u0, 0.0, 180.0))
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
            "checkpoint": str(path.resolve()),
            "series": 3,
            "preprocessing": "raw BGR 320x180",
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
    colors_by_value = ["#22c55e" if value <= 5 else "#eab308" if value <= 10 else "#f97316" if value <= 20 else "#ef4444" for value in maes]
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


def build_pdf(results, samples, s3_samples, pdf_out):
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
    ranked = sorted(versions, key=lambda version: results[version]["overall"]["mae"])
    series1 = [version for version in versions if series_for_version(version) == 1]
    series2 = [version for version in versions if series_for_version(version) == 2]
    series3 = [version for version in versions if series_for_version(version) == 3]
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
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
    story.append(paragraph("Combined current-label offline evaluation", h2))
    story.append(
        paragraph(
            f"Generated {generated}. All available SidewalkPilot steering checkpoints are evaluated on the same active correction set: "
            f"{len(samples):,} labeled images from steering_corrections.json. Active checkpoint naming is SidewalkPilot-vX.Y.pth "
            "for final checkpoints and SidewalkPilot-vX.Yb.pth for best checkpoints.",
            normal,
        )
    )
    best_text = (
        f"Best offline checkpoint on this label set: {best} ({Path(results[best]['checkpoint']).name}) "
        f"with MAE {results[best]['overall']['mae']:.3f}, median AE {results[best]['overall']['median_ae']:.3f}, "
        f"score {results[best]['overall']['score']:.3f}%."
    )
    if second:
        best_text += (
            f" Second: {second} ({Path(results[second]['checkpoint']).name}) "
            f"with MAE {results[second]['overall']['mae']:.3f}."
        )
    story.append(paragraph(best_text, normal))
    story.append(
        paragraph(
            "Series 1 uses raw BGR and output scale 86. Series 2 uses output scale 85; v2.0/v2.0b use legacy HSV/CLAHE "
            "preprocessing, while v2.1 and newer use raw BGR. Series 3 is the heavy 2-output (steering+throttle) "
            "SidewalkPilotV3 at 320x180, evaluated on its OWN collected dataset "
            f"({len(s3_samples):,} images) rather than the Series 1/2 correction set, so its steering MAE is comparable "
            "in unit (servo degrees) but measured on a different set. These are offline decision comparisons; field "
            "reliability still has to be proven on the car.",
            normal,
        )
    )

    source_counts = Counter(sample["dataset"] for sample in samples)
    source_counts.update(sample["dataset"] for sample in s3_samples)
    source_rows = [["Source", "Count", "Purpose"]]
    for source_name in sorted(source_counts):
        source_rows.append([source_name, str(source_counts[source_name]), SOURCE_PURPOSES.get(source_name, "")])
    story.append(Spacer(1, 0.08 * inch))
    story.append(paragraph("Active Correction Sources", h2))
    story.append(make_table(source_rows, col_widths=[1.0 * inch, 0.7 * inch, 7.2 * inch], header_color=colors.HexColor("#334155")))

    rank_rows = [["Rank", "Model", "Checkpoint filename", "Prep", "MAE", "Med", "Max", "Signed", "<=5", "<=10", "Score"]]
    for rank, version in enumerate(ranked, start=1):
        overall = results[version]["overall"]
        rank_rows.append(
            [
                str(rank),
                version,
                Path(results[version]["checkpoint"]).name,
                results[version]["preprocessing"],
                fmt_num(overall["mae"]),
                fmt_num(overall["median_ae"]),
                fmt_num(overall["max_ae"]),
                fmt_num(overall["signed_error"]),
                f"{overall['within_5']}/{overall['count']}",
                f"{overall['within_10']}/{overall['count']}",
                fmt_pct(overall["score"]),
            ]
        )
    story.append(Spacer(1, 0.1 * inch))
    story.append(paragraph("Combined Model Ranking", h2))
    rank_table = make_table(
        rank_rows,
        col_widths=[0.35 * inch, 0.45 * inch, 1.55 * inch, 1.05 * inch, 0.5 * inch, 0.5 * inch, 0.5 * inch, 0.55 * inch, 0.75 * inch, 0.75 * inch, 0.6 * inch],
        header_color=colors.HexColor("#0f766e"),
    )
    add_rank_coloring(rank_table, rank_rows, mae_col=4, score_col=10)
    story.append(rank_table)

    story.append(PageBreak())
    growth_rows = [["Model", "Checkpoint filename", "Series", "Prep", "Scale", "MAE", "Median", "Signed", "<=2", "<=5", "<=20", "Pred mean"]]
    for version in versions:
        overall = results[version]["overall"]
        growth_rows.append(
            [
                version,
                Path(results[version]["checkpoint"]).name,
                str(results[version]["series"]),
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
    growth_table = make_table(
        growth_rows,
        col_widths=[0.45 * inch, 1.55 * inch, 0.45 * inch, 1.05 * inch, 0.42 * inch, 0.48 * inch, 0.48 * inch, 0.5 * inch, 0.45 * inch, 0.45 * inch, 0.5 * inch, 0.58 * inch],
        header_color=colors.HexColor("#1d4ed8"),
    )
    add_rank_coloring(growth_table, growth_rows, mae_col=5)
    story.append(growth_table)

    story.append(PageBreak())
    # union of every model's subset keys: Series 1/2 datasets + Series 3 (S3:*) datasets.
    dataset_names = sorted({name for version in versions for name in results[version]["by_dataset"]})
    subset_rows = [["Model"] + dataset_names]
    for version in ranked:
        row = [version]
        for dataset_name in dataset_names:
            block = results[version]["by_dataset"].get(dataset_name)
            row.append(fmt_num(block["mae"]) if block else "-")
        subset_rows.append(row)
    story.append(paragraph("Field-Case / Subset MAE", h2))
    story.append(paragraph("Lower is better. '-' = model not evaluated on that subset (Series 1/2 vs Series 3 use "
                           "different datasets). D0510 combines the three v2.3 field-failure runs; S3:* are Series 3 runs.", small))
    subset_col_widths = [0.48 * inch] + [0.7 * inch for _ in dataset_names]
    subset_table = make_table(subset_rows, col_widths=subset_col_widths, header_color=colors.HexColor("#7c2d12"))
    story.append(subset_table)

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
    story.append(paragraph("Graphs", h2))
    graph_specs = [
        ("Graph 1: Series 1 all models", series1, build_line_chart),
        ("Graph 2: Series 2 all models", series2, build_line_chart),
    ]
    if series3:
        graph_specs.append(("Graph 3: Series 3 all models", series3, build_line_chart))
    graph_specs.append((f"Graph {len(graph_specs) + 1}: Combined all models", versions, build_bar_chart))
    for title, chart_versions, chart_fn in graph_specs:
        if not chart_versions:
            continue
        story.append(paragraph(title, h2))
        image_data = chart_fn(results, title, chart_versions)
        story.append(Image(image_data, width=9.1 * inch, height=3.1 * inch))

    story.append(PageBreak())
    story.append(paragraph("Notes", h2))
    notes = [
        "The combined table is useful for model-selection decisions, but Series 2 v2.0/v2.0b used different preprocessing from the raw-BGR models.",
        "The current active label set includes D0510 field-failure images, so these numbers are not directly comparable to older 1,464-label reports.",
        "Offline MAE does not prove real-world reliability. The car can still fail on lighting, turns, driveways, road-edge ambiguity, speed, and sensor conditions.",
        "v2.4 and v2.4b were trained with the D0510 correction data; low same-dataset error may include train/evaluation overlap and should be treated as a fit check, not final field proof.",
        "Series 3 (v3.x) is evaluated on its own 320x180 collected dataset (sidewalkpilot_dataset), not the Series 1/2 "
        "correction label set, so its MAE is same-unit but not measured on identical images — treat cross-series ranking "
        "as indicative, not exact. Series 3 also predicts throttle, which was near-constant 1.0 in the collected runs.",
        "Series 3 numbers include train/evaluation overlap (the models were trained on this dataset), so they are a fit "
        "check, not held-out generalization.",
    ]
    for note in notes:
        story.append(paragraph(f"- {note}", normal))

    doc.build(story)


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate SidewalkPilot steering checkpoints and regenerate the PDF report.")
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--corrections", type=Path, default=CORRECTIONS_PATH)
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

    models = discover_models(args.models_dir)
    if args.versions:
        wanted = set(args.versions)
        models = [item for item in models if item[0] in wanted]
    if not models:
        raise FileNotFoundError(f"No SidewalkPilot model checkpoints found in {args.models_dir}")

    print(f"[start] device={device}", flush=True)
    print(f"[start] models={len(models)} corrections={args.corrections}", flush=True)
    samples = load_samples(args.corrections)
    print(f"[start] samples={len(samples)}", flush=True)
    raw_inputs, clahe_inputs, targets = load_tensors(samples)
    results = evaluate_models(samples, raw_inputs, clahe_inputs, targets, models, args.batch_size, device)

    # Series 3 (separate arch + own dataset), folded into the same report.
    s3_results, s3_samples = evaluate_series3(args.models_dir, device, args.batch_size)
    results.update(s3_results)
    if s3_results:
        print(f"[start] series3 models={len(s3_results)} s3_samples={len(s3_samples)}", flush=True)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.pdf_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(results, indent=2) + "\n")
    build_pdf(results, samples, s3_samples, args.pdf_out)
    print(f"[done] wrote {args.json_out}", flush=True)
    print(f"[done] wrote {args.pdf_out}", flush=True)


if __name__ == "__main__":
    main()
