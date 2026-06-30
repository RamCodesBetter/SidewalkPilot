#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from datetime import datetime
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
DEFAULT_PDF_OUT = REPO_ROOT / "docs" / "steering_model_report.pdf"
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
    parser.add_argument("--pdf-out", type=Path, default=DEFAULT_PDF_OUT)
    parser.add_argument("--no-pdf", action="store_true", help="skip the PDF report")
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

    if not args.no_pdf:
        build_pdf(results, args.pdf_out)
        print(f"[done] wrote {args.pdf_out}", flush=True)


def build_pdf(results, pdf_out):
    """Render the Series 3 steering+throttle report PDF from the eval results dict."""
    import io

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    models = results.get("models", {})
    # rank by steering MAE (lower is better)
    ranked = sorted(models.items(), key=lambda kv: kv[1]["steering"]["mae"])

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Title"], fontSize=18,
                                 textColor=colors.HexColor("#0f172a"))
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor("#111827"),
                        spaceBefore=8)
    normal = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=7.5, leading=10,
                           textColor=colors.HexColor("#475569"))

    def P(text, style=normal):
        return Paragraph(str(text), style)

    story = []
    story.append(P("SidewalkPilot Series 3 Steering + Throttle Model Report", title_style))
    story.append(P(f"Offline evaluation &mdash; generated {datetime.now():%Y-%m-%d %I:%M %p}", small))
    story.append(Spacer(1, 0.12 * inch))

    src = ", ".join(f"{k}={v}" for k, v in results.get("source_counts", {}).items()) or "n/a"
    isz = results.get("input_size", {})
    story.append(P("Evaluation Setup", h2))
    story.append(P(
        f"<b>Samples:</b> {results.get('sample_count', 0):,} &nbsp; "
        f"<b>Input:</b> {isz.get('width')}x{isz.get('height')} (BGR) &nbsp; "
        f"<b>Sources:</b> {src} &nbsp; <b>Outputs:</b> steering 0..180 + throttle 0..1 "
        f"(2-output unit controls). <b>Error unit:</b> servo degrees / throttle fraction."))
    story.append(P(
        "<b>Caveats:</b> evaluated on the collected run data (not a held-out split), so "
        "this reflects fit quality. Throttle was a near-constant 1.0 across this run, so "
        "throttle MAE is not a meaningful generalization signal yet.", small))
    story.append(Spacer(1, 0.12 * inch))

    if ranked:
        best_v, best_m = ranked[0]
        story.append(P(
            f"<b>Best checkpoint:</b> v{best_v} &mdash; steering MAE "
            f"{best_m['steering']['mae']:.3f}&deg; (median {best_m['steering']['median_ae']:.3f}&deg;)."))
        story.append(Spacer(1, 0.1 * inch))

    story.append(P("Model Ranking (lower steering MAE is better)", h2))
    header = ["Version", "Steering MAE", "Median AE", "Max AE", "Signed err",
              "Throttle MAE", "Pred mean", "Target mean"]
    rows = [header]
    for v, m in ranked:
        s, t = m["steering"], m["throttle"]
        rows.append([
            f"v{v}", f"{s['mae']:.3f}", f"{s['median_ae']:.3f}", f"{s['max_ae']:.2f}",
            f"{s['signed_error']:+.3f}", f"{t['mae']:.4f}",
            f"{s['pred_mean']:.1f}", f"{s['target_mean']:.1f}",
        ])
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#dcfce7")),  # best row
    ]))
    story.append(table)
    story.append(Spacer(1, 0.18 * inch))

    # steering MAE bar chart
    fig, ax = plt.subplots(figsize=(7.5, 2.6))
    vers = [f"v{v}" for v, _ in ranked]
    maes = [m["steering"]["mae"] for _, m in ranked]
    bars = ax.bar(vers, maes, color="#2563eb")
    ax.set_ylabel("Steering MAE (deg)")
    ax.set_title("Steering MAE by checkpoint (lower is better)")
    for b, mae in zip(bars, maes):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{mae:.2f}",
                ha="center", va="bottom", fontsize=8)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    story.append(Image(buf, width=7.5 * inch, height=2.6 * inch))

    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(pdf_out), pagesize=landscape(letter),
                      title="SidewalkPilot Series 3 Steering Model Report").build(story)


if __name__ == "__main__":
    main()
