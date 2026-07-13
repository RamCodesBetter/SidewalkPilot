#!/usr/bin/env python3
"""check_dataset_frames.py — decode-verify + basic quality scan of a SidewalkPilot
Series-3 dataset folder. READ-ONLY: it reports problems and never deletes anything.

Per-frame flags:
  corrupt      -> PIL cannot even parse the header (verify() raised)
  truncated    -> header ok but full decode failed (partial/cut-off JPEG)
  size:WxH     -> resolution is not 1280x720
  black        -> mean luma < 8  (near-black frame)
  white        -> mean luma > 247 (blown-out / overexposed)
  tiny         -> file smaller than 1 KB

Also cross-checks the image set against labels.json (orphan images / orphan labels).

Usage:
  python3 code/test_files/check_dataset_frames.py \
      code/ai_models_datasets/series_3/sidewalkpilot_dataset
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageStat, ImageFile

# Make truncated JPEGs RAISE instead of silently loading a partial image, so we can flag them.
ImageFile.LOAD_TRUNCATED_IMAGES = False


def check_one(path):
    """Return (path, [flags]). Empty flag list == clean frame."""
    flags = []
    # 1) header parse / corruption
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception:
        return (path, ["corrupt"])
    # 2) full decode (catches truncation verify() misses) + measure
    try:
        with Image.open(path) as im:
            im.load()
            w, h = im.size
            mean_luma = ImageStat.Stat(im.convert("L")).mean[0]
    except Exception:
        return (path, ["truncated"])
    # 3) cheap quality gates
    if (w, h) != (1280, 720):
        flags.append(f"size:{w}x{h}")
    if mean_luma < 8:
        flags.append("black")
    elif mean_luma > 247:
        flags.append("white")
    try:
        if os.path.getsize(path) < 1024:
            flags.append("tiny")
    except OSError:
        flags.append("missing")
    return (path, flags)


def main():
    ap = argparse.ArgumentParser(description="Decode-verify + quality scan a dataset image folder")
    ap.add_argument("folder", help="folder of *.jpg (plus labels.json)")
    ap.add_argument("--workers", type=int, default=min(16, (os.cpu_count() or 4)))
    ap.add_argument("--show", type=int, default=10, help="example filenames to print per category")
    args = ap.parse_args()

    folder = Path(args.folder)
    jpgs = sorted(str(p) for p in folder.glob("*.jpg"))
    if not jpgs:
        sys.exit(f"no jpgs found in {folder}")
    print(f"scanning {len(jpgs):,} jpgs in {folder} with {args.workers} workers...", flush=True)

    cats = defaultdict(list)
    bad_frames = set()
    clean = 0
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for path, flags in ex.map(check_one, jpgs, chunksize=64):
            done += 1
            if flags:
                bad_frames.add(path)
                for f in flags:
                    cats[f.split(":")[0]].append(path)
            else:
                clean += 1
            if done % 10000 == 0:
                print(f"  {done:,}/{len(jpgs):,}...", file=sys.stderr, flush=True)

    print(f"\n=== RESULTS ({len(jpgs):,} frames) ===")
    print(f"  CLEAN:            {clean:,}")
    print(f"  FLAGGED (unique): {len(bad_frames):,}")
    for k in sorted(cats, key=lambda k: -len(cats[k])):
        print(f"    {k:<10} {len(cats[k]):>6,}")
        for p in cats[k][:args.show]:
            print(f"        {os.path.basename(p)}")

    lbl = folder / "labels.json"
    if lbl.is_file():
        labels = json.load(open(lbl))
        disk = {os.path.basename(p) for p in jpgs}
        lset = set(labels.keys())
        print(f"\n=== labels.json vs disk ===")
        print(f"  label entries: {len(lset):,}    disk jpgs: {len(disk):,}")
        print(f"  images with NO label:  {len(disk - lset):,}")
        print(f"  labels with NO image:  {len(lset - disk):,}")
        for k in list(disk - lset)[:args.show]:
            print(f"      (no label) {k}")
        for k in list(lset - disk)[:args.show]:
            print(f"      (no image) {k}")


if __name__ == "__main__":
    main()
