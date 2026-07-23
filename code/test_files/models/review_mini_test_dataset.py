#!/usr/bin/env python3
"""Review mini-test images one at a time in macOS Preview."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET_DIR = SCRIPT_DIR / "mini_test_dataset"
DEFAULT_OUTPUT = DEFAULT_DATASET_DIR / "manual_review.csv"
OUTPUT_FIELDS = [
    "file",
    "source_file",
    "bucket_index",
    "bucket_name",
    "original_steering",
    "decision",
    "corrected_steering",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Open each mini-test image in macOS Preview and record keep, "
            "drop, or corrected-steering decisions."
        )
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help=f"Mini dataset directory (default: {DEFAULT_DATASET_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Review CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Start from the first image and replace any existing review CSV.",
    )
    return parser.parse_args()


def load_records(dataset_dir: Path) -> list[dict]:
    manifest_path = dataset_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text())
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"{manifest_path} does not contain a records list")

    missing = [
        str(dataset_dir / record["file"])
        for record in records
        if not (dataset_dir / record["file"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} manifest images are missing; first: {missing[0]}"
        )
    return records


def load_existing(output: Path) -> list[dict[str, str]]:
    if not output.is_file():
        return []
    with output.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows and list(rows[0]) != OUTPUT_FIELDS:
        raise ValueError(f"{output} has an unexpected column layout")
    return rows


def save_rows(output: Path, rows: list[dict[str, object]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)


def open_in_preview(image_path: Path) -> None:
    subprocess.run(
        ["open", "-a", "Preview", str(image_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.15)


def close_front_preview_document() -> None:
    script = (
        'tell application "Preview"\n'
        "  if (count of documents) > 0 then close front document\n"
        "end tell"
    )
    subprocess.run(
        ["osascript", "-e", script],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def copy_to_clipboard(output: Path) -> None:
    if not output.is_file():
        return
    with output.open("rb") as handle:
        subprocess.run(["pbcopy"], stdin=handle, check=True)


def prompt_for_decision() -> tuple[str, str] | None:
    while True:
        raw = input(
            "Enter=keep | d=drop | 0-180=correct steering | q=save and quit: "
        ).strip()
        if not raw:
            return "keep", ""
        if raw.lower() == "d":
            return "drop", ""
        if raw.lower() == "q":
            return None
        try:
            steering = float(raw)
        except ValueError:
            print("Invalid input. Enter nothing, d, q, or a number from 0 to 180.")
            continue
        if not 0.0 <= steering <= 180.0:
            print("Steering must be between 0 and 180.")
            continue
        displayed = str(int(steering)) if steering.is_integer() else str(steering)
        return "fix", displayed


def main() -> int:
    args = parse_args()
    if platform.system() != "Darwin":
        print("This viewer requires macOS because it uses Preview and pbcopy.", file=sys.stderr)
        return 2

    dataset_dir = args.dataset_dir.expanduser().resolve()
    output = args.output.expanduser().resolve()
    records = load_records(dataset_dir)
    rows = [] if args.restart else load_existing(output)
    if len(rows) > len(records):
        raise ValueError(f"{output} has more rows than the manifest")

    start = len(rows)
    if start:
        print(f"Resuming at image {start + 1}/{len(records)} from {output}")

    try:
        for index in range(start, len(records)):
            record = records[index]
            image_path = dataset_dir / record["file"]
            original = float(record["target_steering"])
            original_text = str(int(original)) if original.is_integer() else str(original)

            open_in_preview(image_path)
            print()
            print(
                f"[{index + 1}/{len(records)}] {record['file']} | "
                f"{record['bucket_name']} | original steering={original_text}"
            )
            decision = prompt_for_decision()
            close_front_preview_document()
            if decision is None:
                break

            action, corrected = decision
            rows.append(
                {
                    "file": record["file"],
                    "source_file": record["source_file"],
                    "bucket_index": record["bucket_index"],
                    "bucket_name": record["bucket_name"],
                    "original_steering": original_text,
                    "decision": action,
                    "corrected_steering": corrected,
                }
            )
            save_rows(output, rows)
    except (EOFError, KeyboardInterrupt):
        print()
        close_front_preview_document()
    finally:
        if rows:
            save_rows(output, rows)
            copy_to_clipboard(output)

    print(f"Saved {len(rows)}/{len(records)} decisions to {output}")
    if rows:
        print("Copied the complete review CSV to the clipboard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
