#!/usr/bin/env python3
import argparse
import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
SERIES3_DIR = REPO_ROOT / "code" / "ai_models_datasets" / "series_3"
sys.path.insert(0, str(SERIES3_DIR))

from sidewalkpilot_trainer import augment_image, clamp_servo, clamp_throttle, resize_image_uint8  # noqa: E402


def draw_label(img, text):
    out = img.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 24), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def make_grid(images, columns):
    columns = max(1, int(columns))
    rows = int(math.ceil(len(images) / columns))
    height, width = images[0].shape[:2]
    grid = np.full((rows * height, columns * width, 3), 32, dtype=np.uint8)
    for index, image in enumerate(images):
        row = index // columns
        col = index % columns
        grid[row * height : (row + 1) * height, col * width : (col + 1) * width] = image
    return grid


def parse_args():
    parser = argparse.ArgumentParser(description="Preview Series 3 training augmentations for one input image.")
    parser.add_argument("image", type=Path, help="input image path")
    parser.add_argument("--output", type=Path, default=Path("/tmp/series3_augmentations.jpg"))
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=180)
    parser.add_argument("--crop-top-ratio", type=float, default=0.0)
    parser.add_argument("--steering", type=float, default=90.0)
    parser.add_argument("--throttle", type=float, default=0.35)
    parser.add_argument("--source", default="real", choices=["real", "carla", "correction"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--shadow-probability", type=float, default=0.85)
    parser.add_argument("--carla-domain-randomize-probability", type=float, default=0.70)
    parser.add_argument("--hsv-probability", type=float, default=0.0)
    parser.add_argument("--clahe-probability", type=float, default=0.0)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(args.image)

    steering = clamp_servo(args.steering)
    throttle = clamp_throttle(args.throttle)
    base = resize_image_uint8(image, args.width, args.height, args.crop_top_ratio)
    previews = [draw_label(base, f"original steer={steering:.1f} throttle={throttle:.2f}")]

    for index in range(max(0, int(args.count))):
        aug, aug_steering = augment_image(
            base.copy(),
            steering,
            source=args.source,
            shadow_aug_probability=args.shadow_probability,
            carla_domain_randomize_probability=args.carla_domain_randomize_probability,
            hsv_aug_probability=args.hsv_probability,
            clahe_aug_probability=args.clahe_probability,
        )
        previews.append(draw_label(aug, f"aug {index + 1:02d} steer={aug_steering:.1f} throttle={throttle:.2f}"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    grid = make_grid(previews, args.columns)
    if not cv2.imwrite(str(args.output), grid):
        raise RuntimeError(f"Failed to write {args.output}")
    print(args.output)


if __name__ == "__main__":
    main()
