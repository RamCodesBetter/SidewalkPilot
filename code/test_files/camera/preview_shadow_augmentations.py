#!/usr/bin/env python3
"""preview_shadow_augmentations.py -- see the 5 shadow augmentations on real photos.

Picks N random photos from the Series 3 dataset and, for EACH photo, shows the
original next to the 5 individual shadow augmentations the trainer rolls inside
apply_shadow_stress_augmentation():

  1 mixed_lighting        2 diagonal_shadow    3 tree_shadow
  4 sidewalk_edge_shadow  5 patchy_concrete

Each augmentation is applied to a FRESH copy of the original (not stacked), so you
see exactly what each one does on its own. Saves a single grid image:
N rows (one per photo) x 6 columns (original + 5 augs) -> e.g. 3 photos = 18 tiles.

Run on the training PC (where the dataset + trainer live):
    python3 code/test_files/camera/preview_shadow_augmentations.py
    python3 code/test_files/camera/preview_shadow_augmentations.py --count 3 --output /tmp/shadow_augs.jpg
    python3 code/test_files/camera/preview_shadow_augmentations.py --seed 7

These are the SAME functions used during training, imported from the trainer, so the
preview can never drift from what the model actually sees.
"""
import argparse
import random
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
SERIES3_DIR = REPO_ROOT / "code" / "ai_models_datasets" / "series_3_and_4"
DEFAULT_DATASET = SERIES3_DIR / "sidewalkpilot_dataset"
sys.path.insert(0, str(SERIES3_DIR))

from series_3_sidewalkpilot_trainer import (  # noqa: E402
    resize_image_uint8,
    apply_mixed_lighting,
    apply_diagonal_shadow_band,
    apply_tree_shadow_pattern,
    apply_sidewalk_road_edge_shadow,
    apply_patchy_concrete_texture,
)

# (label, function) in the same order/priority the trainer rolls them.
SHADOW_AUGS = [
    ("1 mixed_lighting", apply_mixed_lighting),
    ("2 diagonal_shadow", apply_diagonal_shadow_band),
    ("3 tree_shadow", apply_tree_shadow_pattern),
    ("4 sidewalk_edge", apply_sidewalk_road_edge_shadow),
    ("5 patchy_concrete", apply_patchy_concrete_texture),
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def draw_label(img, text):
    out = img.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(out, text, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def make_grid(rows_of_images):
    """rows_of_images: list of rows, each a list of same-size BGR tiles."""
    h, w = rows_of_images[0][0].shape[:2]
    cols = max(len(r) for r in rows_of_images)
    grid = np.full((len(rows_of_images) * h, cols * w, 3), 32, dtype=np.uint8)
    for r, row in enumerate(rows_of_images):
        for c, tile in enumerate(row):
            grid[r * h:(r + 1) * h, c * w:(c + 1) * w] = tile
    return grid


def parse_args():
    p = argparse.ArgumentParser(description="Preview the 5 shadow augmentations on random Series 3 photos.")
    p.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="dataset dir to sample from")
    p.add_argument("--count", type=int, default=3, help="how many random photos (rows)")
    p.add_argument("--output", type=Path, default=Path("/tmp/series3_shadow_augs.jpg"))
    p.add_argument("--width", type=int, default=320)
    p.add_argument("--height", type=int, default=180)
    p.add_argument("--seed", type=int, default=None, help="reproducible photo pick + augmentations")
    return p.parse_args()


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    paths = [p for p in args.dataset.rglob("*") if p.suffix.lower() in IMAGE_EXTS]
    if len(paths) < args.count:
        raise SystemExit(f"only {len(paths)} images found under {args.dataset} (need {args.count})")
    picks = random.sample(paths, args.count)

    rows = []
    for path in picks:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            continue
        base = resize_image_uint8(img, args.width, args.height, 0.0)
        row = [draw_label(base, f"original  {path.name[:22]}")]
        for label, fn in SHADOW_AUGS:
            aug = fn(base.copy())
            row.append(draw_label(np.clip(aug, 0, 255).astype(np.uint8), label))
        rows.append(row)

    if not rows:
        raise SystemExit("no readable images picked")
    grid = make_grid(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), grid):
        raise SystemExit(f"failed to write {args.output}")
    print(f"wrote {args.output}  ({len(rows)} photos x {1 + len(SHADOW_AUGS)} tiles)")


if __name__ == "__main__":
    main()
