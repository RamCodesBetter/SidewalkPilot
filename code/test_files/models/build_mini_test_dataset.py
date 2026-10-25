#!/usr/bin/env python3
"""Build the compact real-image mini dataset used for device timing tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path

import cv2


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = (
    REPO_ROOT
    / "code"
    / "ai_models_datasets"
    / "series_3_and_4"
    / "sidewalkpilot_dataset"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "mini_test_dataset"
STEERING_BINS = (
    ("hard_left_0_45", 0.0, 45.0),
    ("left_45_60", 45.0, 60.0),
    ("left_60_75", 60.0, 75.0),
    ("soft_left_75_85", 75.0, 85.0),
    ("straight_85_95", 85.0, 95.0),
    ("soft_right_95_105", 95.0, 105.0),
    ("right_105_120", 105.0, 120.0),
    ("right_120_135", 120.0, 135.0),
    ("hard_right_135_180", 135.0, 180.0),
)


def steering_bucket(value: float) -> int:
    steering = min(180.0, max(0.0, float(value)))
    for index, (_name, lower, upper) in enumerate(STEERING_BINS):
        if lower <= steering < upper or (
            index == len(STEERING_BINS) - 1 and steering == upper
        ):
            return index
    return len(STEERING_BINS) - 1


def evenly_spaced(
    items: list[dict[str, object]], count: int
) -> list[dict[str, object]]:
    if len(items) < count:
        raise ValueError(f"need {count} candidates, found {len(items)}")
    if count == 1:
        return [items[len(items) // 2]]
    indices = [round(i * (len(items) - 1) / (count - 1)) for i in range(count)]
    return [items[index] for index in indices]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_candidates(dataset: Path) -> dict[int, list[dict[str, object]]]:
    label_path = dataset / "labels.json"
    try:
        labels = json.loads(label_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read {label_path}: {exc}") from exc
    if not isinstance(labels, dict):
        raise SystemExit("Expected labels.json to contain a filename-to-label mapping.")

    by_run: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for filename, payload in labels.items():
        if not isinstance(payload, dict) or "steering" not in payload:
            continue
        path = dataset / filename
        if not path.is_file():
            continue
        run_name = filename.split("__photo_", 1)[0]
        by_run[run_name].append((filename, float(payload["steering"])))

    by_bucket: dict[int, list[dict[str, object]]] = defaultdict(list)
    for run_name, frames in sorted(by_run.items()):
        frames.sort(key=lambda item: item[0])
        for index in range(3, len(frames)):
            filename, steering = frames[index]
            history = [frames[index - offset][1] for offset in (3, 2, 1)]
            bucket = steering_bucket(steering)
            by_bucket[bucket].append(
                {
                    "source_file": filename,
                    "run": run_name,
                    "target_steering": steering,
                    "target_history": history,
                    "bucket_index": bucket,
                    "bucket_name": STEERING_BINS[bucket][0],
                }
            )
    return by_bucket


def build(args: argparse.Namespace) -> None:
    dataset = args.dataset.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output.exists():
        if not args.force:
            raise SystemExit(
                f"Output already exists: {output}; pass --force to rebuild."
            )
        shutil.rmtree(output)
    output.mkdir(parents=True)

    candidates = load_candidates(dataset)
    manifest_records: list[dict[str, object]] = []
    for bucket_index, (bucket_name, _lower, _upper) in enumerate(STEERING_BINS):
        selected = evenly_spaced(candidates[bucket_index], args.per_bucket)
        for sample_index, record in enumerate(selected):
            source = dataset / str(record["source_file"])
            image = cv2.imread(str(source), cv2.IMREAD_COLOR)
            if image is None:
                raise SystemExit(f"Could not decode source image: {source}")
            resized = cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)
            filename = f"b{bucket_index}_{sample_index:02d}.jpg"
            destination = output / filename
            if not cv2.imwrite(
                str(destination),
                resized,
                [int(cv2.IMWRITE_JPEG_QUALITY), args.jpeg_quality],
            ):
                raise SystemExit(f"Could not write mini test image: {destination}")
            manifest_records.append(
                {
                    **record,
                    "file": filename,
                    "sha256": file_sha256(destination),
                }
            )

    manifest = {
        "schema_version": 1,
        "description": (
            "A 180-image mini test dataset sampled from the separate original "
            "81,237-image Series 3/4 model-training snapshot for Raspberry Pi 5 and Jetson Orin Nano "
            "inference-speed tests. This is not the training dataset."
        ),
        "dataset_role": "mini inference-speed test dataset",
        "is_training_dataset": False,
        "selection": "deterministic chronological spacing within each steering bucket",
        "source_dataset": "SidewalkPilot-v3-and-v4",
        "image_width": 320,
        "image_height": 180,
        "jpeg_quality": args.jpeg_quality,
        "images_per_bucket": args.per_bucket,
        "image_count": len(manifest_records),
        "steering_bins": [
            {"name": name, "lower": lower, "upper": upper}
            for name, lower, upper in STEERING_BINS
        ],
        "records": manifest_records,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    total_bytes = sum(path.stat().st_size for path in output.iterdir())
    print(
        f"wrote {len(manifest_records)} real sidewalk images to {output} "
        f"({total_bytes / (1024 * 1024):.2f} MiB)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--per-bucket", type=int, default=20)
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.per_bucket < 1:
        parser.error("--per-bucket must be positive")
    if not 1 <= args.jpeg_quality <= 100:
        parser.error("--jpeg-quality must be between 1 and 100")
    build(args)


if __name__ == "__main__":
    main()
