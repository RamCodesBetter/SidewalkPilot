#!/usr/bin/env python3
"""
Quick steering label helper.

Prompts for a filename tag, opens each matching image, accepts a 0..180 label,
then prints the image order and label order for pasting into chat.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_IMAGE_DIR = (
    Path.home()
    / "Desktop/rc_car_code/code/ai_models_data"
    / "manual_sidewalk_detection_mixed.coco-segmentation/train"
)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open images matching a tag and label steering 0..180."
    )
    parser.add_argument(
        "--dir",
        default=str(DEFAULT_IMAGE_DIR),
        help=f"image directory (default: {DEFAULT_IMAGE_DIR})",
    )
    parser.add_argument("--tag", default=None, help="filename tag filter")
    parser.add_argument(
        "--output",
        default=None,
        help="optional JSON output path; default writes into code/test_files",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open images; useful for retyping labels from another viewer",
    )
    return parser.parse_args()


def find_images(image_dir: Path, tag: str) -> list[Path]:
    tag_lower = tag.lower()
    return sorted(
        p
        for p in image_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTS
        and tag_lower in p.name.lower()
    )


def open_image(path: Path) -> subprocess.Popen | None:
    if platform.system() == "Darwin":
        proc = subprocess.Popen(
            ["open", "-a", "Preview", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.20)
        focus_terminal()
        return proc
    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
        return None
    return subprocess.Popen(
        ["xdg-open", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def focus_terminal() -> None:
    if platform.system() != "Darwin":
        return
    script = """
    tell application "System Events"
        set frontApps to name of application processes whose frontmost is true
    end tell
    if frontApps contains "iTerm2" then
        tell application "iTerm2" to activate
    else if frontApps contains "Terminal" then
        tell application "Terminal" to activate
    else
        try
            tell application "iTerm2" to activate
        on error
            tell application "Terminal" to activate
        end try
    end if
    """
    subprocess.run(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def close_image() -> None:
    if platform.system() != "Darwin":
        return
    subprocess.run(
        ["osascript", "-e", 'tell application "Preview" to close front window'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def ask_label(index: int, total: int, path: Path) -> float | None:
    while True:
        raw = input(
            f"[{index}/{total}] {path.name} label 0..180 "
            "(enter=skip, q=quit): "
        ).strip()
        if raw.lower() in {"q", "quit", "exit"}:
            raise KeyboardInterrupt
        if raw == "":
            return None
        try:
            value = float(raw)
        except ValueError:
            print("Enter a number from 0 to 180.")
            continue
        if 0.0 <= value <= 180.0:
            return value
        print("Label must be from 0 to 180.")


def default_output_path(tag: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tag)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent / f"labels_{safe}_{stamp}.json"


def print_paste_blocks(rows: list[dict[str, object]]) -> None:
    images = [str(row["image"]) for row in rows]
    labels = [row["steering"] for row in rows]

    print("\nIMAGE ORDER:")
    print(" ".join(images))
    print("\nLABEL ORDER:")
    print(", ".join(f"{float(v):g}" for v in labels))
    print("\nJSON ENTRIES:")
    print(json.dumps(rows, indent=2))


def main() -> int:
    args = parse_args()
    image_dir = Path(args.dir).expanduser().resolve()
    if not image_dir.exists():
        print(f"Image directory does not exist: {image_dir}", file=sys.stderr)
        return 1

    tag = args.tag or input("Tag to filter images, example photo_20260502: ").strip()
    if not tag:
        print("No tag entered.", file=sys.stderr)
        return 1

    images = find_images(image_dir, tag)
    if not images:
        print(f"No images found in {image_dir} matching tag: {tag}")
        return 1

    print(f"Found {len(images)} images matching '{tag}'.")
    print("Type a steering label from 0 to 180 for each image.")
    print("Use Enter to skip an image, or q to stop early.\n")

    rows: list[dict[str, object]] = []
    try:
        for index, path in enumerate(images, 1):
            if not args.no_open:
                open_image(path)
                time.sleep(0.25)
                focus_terminal()
            label = ask_label(index, len(images), path)
            if not args.no_open:
                close_image()
                focus_terminal()
                time.sleep(0.10)
            if label is None:
                continue
            rows.append(
                {
                    "image": str(path),
                    "steering": label,
                }
            )
    except KeyboardInterrupt:
        if not args.no_open:
            close_image()
        print("\nStopped early.")

    if not rows:
        print("No labels entered.")
        return 0

    output = Path(args.output).expanduser() if args.output else default_output_path(tag)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2) + "\n")

    print_paste_blocks(rows)
    print(f"\nSaved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
