#!/usr/bin/env python3
"""Export frozen 5.A predictions and an offline viewer for one saved partition."""

import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from package_visual_comparison import encode_labels
from prepare_reviewed_dataset import safe_file
from series_5_a_sidewalkpilot_trainer import (
    HERE, SidewalkDataset, autocast, load_checkpoint, load_partition, select_precision,
)

VIEWER_ASSETS = ("model.html", "model.js", "model_metrics.js", "model.css", "comparison.css", "lucide.min.js", "LUCIDE-LICENSE.txt")


def copy_viewer_assets(root):
    for name in VIEWER_ASSETS:
        shutil.copy2(HERE / "review" / name, root / ("index.html" if name == "model.html" else name))


def refresh_viewer_assets(root):
    """Refresh only the UI of a verified package, preserving review/mask identities."""
    root = Path(root).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema") != "sidewalkpilot-model-review-v1":
        raise ValueError("Not a model-review package")
    integrity = json.loads((root / "integrity-check.json").read_text())
    files = integrity["files_sha256"]
    for name, expected in files.items():
        if sha256(safe_file(root, name)) != expected:
            raise ValueError(f"Package file changed: {name}")
    copy_viewer_assets(root)
    for name in VIEWER_ASSETS:
        target = "index.html" if name == "model.html" else name
        files[target] = sha256(root / target)
    write_json(root / "integrity-check.json", integrity)
    return {"package_id": manifest["package_id"], "refreshed_assets": len(VIEWER_ASSETS)}


def check_destination(output, dataset, checkpoint, split):
    output = output.resolve()
    if output.exists() or any(output == p.resolve() or output in p.resolve().parents
                              or p.resolve() in output.parents for p in (dataset, checkpoint, split)):
        raise ValueError("Use a new viewer directory separate from the dataset and input files")


def validate_identity(state, identity):
    if state["data_identity"] != identity:
        raise ValueError("Checkpoint dataset/split identity differs")
    if state["config"]["smoke_only"]:
        raise ValueError("A smoke checkpoint is not a trained model for review")


def mask_record(path, root, labels):
    return {"path": str(path.relative_to(root)), "sha256": sha256(path),
            "positive_pixels": int((labels == 1).sum()),
            "ignored_pixels": int((labels == 255).sum()), "rle": encode_labels(labels)}


@torch.inference_mode()
def package(args):
    dataset, output = args.dataset.resolve(), args.output.resolve()
    check_destination(output, dataset, args.checkpoint, args.split)
    rows = load_partition(dataset, args.split)[args.partition]
    model, state = load_checkpoint(args.checkpoint)
    identity = {"manifest_sha256": sha256(dataset / "manifest.json"), "split_sha256": sha256(args.split)}
    validate_identity(state, identity)
    checkpoint_hash = sha256(args.checkpoint)
    device = torch.device(args.device)
    precision = select_precision(args.precision, device)
    model.to(device).eval()
    cfg = state["config"]
    data = SidewalkDataset(dataset, rows, (cfg["width"], cfg["height"]), original_targets=True)
    manifest = {
        "schema": "sidewalkpilot-model-review-v1", "created_utc": utc_now(),
        "model_name": cfg["model_name"], "checkpoint_epoch": state["epoch"],
        "checkpoint_sha256": checkpoint_hash, "data_identity": identity,
        "partition": args.partition, "count": len(rows), "precision": precision,
        "input_size": [cfg["width"], cfg["height"]], "metrics_computed": False,
        "test_predictions_generated": args.partition == "test",
        "scope": "Development visual review, not an independent final test or an accuracy score. Future tuning based on these images makes them development data.",
        "prediction_policy": "Raw native-resolution argmax after bilinear logits resize. No component filter, mask corrections, or reference-guided inference.",
        "reference_policy": "0: reviewed background; 1: reviewed sidewalk; 255: unknown/ignored, never background. Positive-only references cannot establish false positives or IoU.",
        "generator_sha256": sha256(Path(__file__)), "frames": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only a complete package, without ever modifying frozen labels or model files.
    with tempfile.TemporaryDirectory(prefix=".model-review-", dir=output.parent) as temporary:
        root = Path(temporary) / "package"
        for folder in ("images", "predictions", "references", "provenance"):
            (root / folder).mkdir(parents=True)
        for index, row in enumerate(rows):
            tensor, target, _, _ = data[index]
            with autocast(device, precision):
                logits = model(tensor.unsqueeze(0).to(device))["out"]
            prediction = F.interpolate(logits.float(), size=target.shape, mode="bilinear",
                                       align_corners=False).argmax(1)[0].cpu().numpy().astype(np.uint8)
            name = f"{index + 1:03d}"
            image_path = root / "images" / (name + Path(row["image"]).suffix)
            reference_path = root / "references" / (name + ".png")
            mask_path = root / "predictions" / (name + ".png")
            shutil.copy2(safe_file(dataset, row["image"]), image_path)
            shutil.copy2(safe_file(dataset, row["mask"]), reference_path)
            if sha256(image_path) != row["source_sha256"] or sha256(reference_path) != row["mask_sha256"]:
                raise ValueError("Source image or reference changed during export")
            Image.fromarray(prediction).save(mask_path)
            prediction_record = mask_record(mask_path, root, prediction)
            # A blob download avoids file:// download restrictions without re-encoding label IDs.
            prediction_record["png_base64"] = base64.b64encode(mask_path.read_bytes()).decode("ascii")
            manifest["frames"].append({
                "id": row["id"], "name": row["source_name"], "image": str(image_path.relative_to(root)),
                "size": [target.shape[1], target.shape[0]], "source_sha256": row["source_sha256"],
                "recording_run": row["recording_run"], "supervision": row["supervision"],
                "prediction": prediction_record,
                "reference": mask_record(reference_path, root, target.numpy()),
            })
            print(f"Predicted {index + 1}/{len(rows)}: {row['source_name']}", flush=True)
        manifest["binary_references"] = sum(row["supervision"] == "binary-reference" for row in rows)
        manifest["partial_references"] = len(rows) - manifest["binary_references"]
        manifest["package_id"] = digest_json(manifest)
        write_json(root / "manifest.json", manifest)
        (root / "data.js").write_text("window.MODEL_REVIEW_DATA = " + json.dumps(manifest, separators=(",", ":")) + ";\n")
        copy_viewer_assets(root)
        shutil.copy2(args.split, root / "provenance" / "split.json")
        write_json(root / "provenance" / "training-config.json", cfg)
        (root / "READ-ME.txt").write_text(
            "SidewalkPilot / 5.A development partition viewer\n\n"
            "Open index.html directly. Keep its companion folders beside it. No server or internet needed.\n"
            "Enter / Right: next image. Left: previous. 1: correct. 2: needs correction. 3: uncertain.\n"
            "After 2, choose 1: minor, 2: moderate, or 3: major. Escape cancels. Ratings do not advance.\n"
            "Notes and ratings are local browser data. Export review JSON for a portable backup.\n"
            "Import only accepts reviews matching this package, source images, and predicted masks.\n"
            "Reference is optional. Green means sidewalk; amber means unknown/ignored, not background.\n"
            "Most references are positive-only and cannot measure false positives.\n"
            "Zoom is shared, and scrolling one panel synchronizes the others. Download mask saves IDs 0/1.\n\n"
            "Predictions are from the frozen checkpoint, without editing, filtering, or retraining.\n"
            "Review ratings do not modify source masks, training labels, or checkpoint files.\n"
            "The saved test partition was held out from this training run. These previously reviewed\n"
            "examples are development data, not an untouched final research test set. Any future\n"
            "model changes based on this review must acknowledge that test-set feedback.\n"
            "No numerical test metrics or W&B uploads are performed by this package command.\n", encoding="ascii")
        if (sha256(args.checkpoint) != checkpoint_hash or sha256(args.split) != identity["split_sha256"]
                or sha256(dataset / "manifest.json") != identity["manifest_sha256"]):
            raise ValueError("Inputs changed during prediction")
        write_json(root / "integrity-check.json", {"files_sha256": {
            str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}})
        root.rename(output)
    return {"output": str(output), "images": len(rows), "checkpoint_epoch": state["epoch"],
            "package_id": manifest["package_id"], "metrics_computed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("dataset", "split", "checkpoint", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--partition", choices=("validation", "test"), default="test")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--precision", choices=("auto", "fp32", "fp16", "bf16"), default="auto")
    print(json.dumps(package(parser.parse_args()), indent=2))


if __name__ == "__main__":
    main()
