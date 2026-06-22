#!/usr/bin/env python3
"""
photo_run_to_dataset.py — assemble SidewalkPilot photo runs into Series 3 datasets.

The runtime writes each photo run's labels to media/photos/<run>/<run>.json as an
image->label dict:

    { "photo_20260620_225745.jpg": {"steering": 90, "throttle": 0.42}, ... }

The Series 3 trainer (code/ai_models_datasets/series_3/sidewalkpilot_trainer.py)
auto-discovers dataset*/ folders that each contain a labels.json + image files,
and its loader already accepts an image->label dict. So this tool just assembles
each run into a trainer-ready folder:

  media/photos/<run>/  ->  code/ai_models_datasets/series_3/dataset_real_<run>/
                            (images linked/copied + labels.json written)

Notes:
- Steering stays LOGICAL 0..180 (what the model trains on; trainer reads it as
  "servo" mode, no conversion). Throttle stays 0..1.
- Folder is named dataset_real_<run> so the trainer treats it as REAL data
  (weight 2.0), not carla/synthetic.
- Generated datasets are DATA, not source — they're gitignored, not committed.

Usage:
  python3 code/test_files/photo_run_to_dataset.py                 # all runs that have a label json
  python3 code/test_files/photo_run_to_dataset.py --runs media/photos/2026_06_20_run_1
  python3 code/test_files/photo_run_to_dataset.py --mode copy     # copy images (portable) instead of symlink
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PHOTOS_DIR = REPO / "media" / "photos"
DATASET_DIR = REPO / "code" / "ai_models_datasets" / "series_3"


def clamp_steer(value):
    return max(0.0, min(180.0, float(value)))


def clamp_throttle(value):
    return max(0.0, min(1.0, float(value)))


def find_label_json(run_dir):
    """Runtime writes <run>.json; fall back to any single *.json in the folder."""
    named = run_dir / f"{run_dir.name}.json"
    if named.is_file():
        return named
    jsons = sorted(run_dir.glob("*.json"))
    return jsons[0] if jsons else None


def convert_run(run_dir, mode):
    label_path = find_label_json(run_dir)
    if not label_path:
        return None  # no labels in this run -> skip silently (e.g. old photo runs)
    try:
        labels = json.loads(label_path.read_text())
    except Exception as exc:
        print(f"  [skip] {run_dir.name}: unreadable label json ({exc})")
        return None
    if not isinstance(labels, dict) or not labels:
        print(f"  [skip] {run_dir.name}: labels.json is not a non-empty image->label dict")
        return None

    out_dir = DATASET_DIR / f"dataset_real_{run_dir.name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_labels = {}
    linked = 0
    missing = 0
    for image_name, label in labels.items():
        src = run_dir / image_name
        if not src.is_file():
            missing += 1
            continue
        if isinstance(label, dict):
            steer = label.get("steering", label.get("steer"))
            throttle = label.get("throttle")
        else:
            steer = label
            throttle = None
        if steer is None:
            missing += 1
            continue
        record = {"steering": round(clamp_steer(steer), 2)}
        if throttle is not None:
            record["throttle"] = round(clamp_throttle(throttle), 4)

        dst = out_dir / image_name
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        if mode == "copy":
            shutil.copy2(src, dst)
        else:
            dst.symlink_to(os.path.relpath(src, out_dir))
        out_labels[image_name] = record
        linked += 1

    (out_dir / "labels.json").write_text(json.dumps(out_labels, indent=2) + "\n")
    print(f"  {run_dir.name}: {linked} labeled images, {missing} missing/unlabeled "
          f"-> {out_dir.relative_to(REPO)}")
    return linked


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--runs", nargs="*",
                        help="specific run dirs (default: every folder in media/photos that has a label json)")
    parser.add_argument("--mode", choices=["symlink", "copy"], default="symlink",
                        help="symlink (default; local, space-saving) or copy (portable across machines)")
    args = parser.parse_args()

    if args.runs:
        runs = [Path(r) if Path(r).is_absolute() else REPO / r for r in args.runs]
    elif PHOTOS_DIR.is_dir():
        runs = sorted(p for p in PHOTOS_DIR.iterdir() if p.is_dir())
    else:
        runs = []

    if not runs:
        print("No photo runs found.")
        return

    print(f"Assembling Series 3 datasets (mode={args.mode}):")
    total_images = 0
    runs_done = 0
    for run in runs:
        if not run.is_dir():
            print(f"  [skip] {run}: not a directory")
            continue
        count = convert_run(run, args.mode)
        if count:
            total_images += count
            runs_done += 1

    print(f"\nDone: {runs_done} run(s), {total_images} labeled images "
          f"-> {DATASET_DIR.relative_to(REPO)}/dataset_real_*")
    if not runs_done:
        print("(No runs had a label json — old runs predate label saving; new runs will have <run>.json.)")
    if args.mode == "symlink" and total_images:
        print("Note: symlinks are local — use --mode copy (or run this on the training machine) "
              "before syncing the dataset to the PC.")


if __name__ == "__main__":
    main()
