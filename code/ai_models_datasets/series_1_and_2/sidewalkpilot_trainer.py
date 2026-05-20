#!/usr/bin/env python3
import argparse
import json
import math
import random
import time
from collections import Counter
from glob import glob
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, Subset, WeightedRandomSampler, random_split

torch.backends.cudnn.benchmark = True
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
SCRIPT_DIR = Path(__file__).resolve().parent


def clamp(x, lo=-1.0, hi=1.0):
    return float(max(lo, min(hi, float(x))))


def clamp_servo(x):
    return float(max(0.0, min(180.0, float(x))))


def label_to_servo(raw_steer, label_mode="auto"):
    raw_steer = float(raw_steer)
    if label_mode == "normalized":
        return clamp_servo((clamp(raw_steer) + 1.0) * 90.0)
    if label_mode == "servo":
        return clamp_servo(raw_steer)
    if 0.0 <= raw_steer <= 180.0:
        return clamp_servo(raw_steer)
    return clamp_servo((clamp(raw_steer) + 1.0) * 90.0)


def get_raw_steering(item, default=None):
    return item.get("steering", item.get("steer", item.get("control_steer", default)))


def infer_label_mode(items):
    values = []
    for item in items:
        raw = get_raw_steering(item, None)
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            pass

    if not values:
        return "normalized"

    values = np.array(values, dtype=np.float32)
    if float(values.min()) < 0.0 or float(np.max(np.abs(values))) <= 1.0:
        return "normalized"
    return "servo"


def convert_label_file_to_servo(label_path):
    with open(label_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = get_label_container(data)
    label_mode = infer_label_mode(items)

    converted = 0
    skipped_bad = 0
    already_servo = label_mode == "servo"

    if not already_servo:
        for item in items:
            if not isinstance(item, dict):
                skipped_bad += 1
                continue

            key = None
            for candidate in ("steering", "steer", "control_steer"):
                if candidate in item:
                    key = candidate
                    break

            if key is None:
                skipped_bad += 1
                continue

            try:
                item[key] = round(label_to_servo(float(item[key]), "normalized"), 6)
                converted += 1
            except (TypeError, ValueError):
                skipped_bad += 1

        write_json(label_path, data)

    print(
        f"[convert] file={label_path} mode_before={label_mode} "
        f"converted={converted} skipped_bad={skipped_bad} already_servo={already_servo}",
        flush=True,
    )
    return converted, skipped_bad, already_servo


def convert_roots_to_servo(roots):
    total_converted = 0
    total_bad = 0
    already_servo_files = 0

    print("[convert] converting labels to servo degrees: 0=left 90=straight 180=right", flush=True)
    for root in roots:
        label_path = Path(root) / "labels.json"
        converted, skipped_bad, already_servo = convert_label_file_to_servo(label_path)
        total_converted += converted
        total_bad += skipped_bad
        already_servo_files += int(already_servo)

    print(
        f"[convert] done files={len(roots)} converted={total_converted} "
        f"skipped_bad={total_bad} already_servo_files={already_servo_files}",
        flush=True,
    )


def fmt_time(seconds):
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def gpu_status():
    if DEVICE != "cuda":
        return "gpu=none"

    name = torch.cuda.get_device_name(0)
    allocated = torch.cuda.memory_allocated(0) / (1024 ** 3)
    reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
    return f"gpu={name} mem_alloc={allocated:.2f}GB mem_reserved={reserved:.2f}GB"


def discover_roots(explicit_roots=None):
    if explicit_roots:
        roots = []
        for raw_root in explicit_roots:
            candidate = Path(raw_root).expanduser()
            candidate_options = [candidate]
            if not candidate.is_absolute():
                candidate_options.append(SCRIPT_DIR / candidate)

            matched = None
            for option in candidate_options:
                if option.is_dir():
                    matched = option.resolve()
                    break

            if matched is not None:
                roots.append(matched)
        roots = [r for r in roots if r.is_dir()]
        if roots:
            return roots

    preferred = [
        "dataset_carla_steering",
        "dataset_carla_steering_town03",
        "dataset_carla_steering_town03_clear",
        "dataset_carla_steering_town04_cloudy",
        "dataset_carla_steering_town05_wet",
        "dataset_l2_realistic",
        "dataset_l2_balanced",
        "dataset_realistic",
        "dataset_balanced",
    ]

    roots = []
    for name in preferred:
        for candidate in (Path(name), SCRIPT_DIR / name):
            if candidate.is_dir() and (candidate / "labels.json").is_file():
                roots.append(candidate.resolve())
                break
    if roots:
        return roots

    candidates = []
    for p in glob(str(SCRIPT_DIR / "dataset*")):
        root = Path(p)
        if root.is_dir() and (root / "labels.json").is_file():
            candidates.append(root.resolve())

    if candidates:
        return sorted(candidates)

    recursive = []
    for label_path in SCRIPT_DIR.rglob("labels.json"):
        root = label_path.parent
        if root.is_dir():
            recursive.append(root.resolve())

    if recursive:
        return sorted(set(recursive))

    raise FileNotFoundError(f"No dataset folders found with labels.json inside {SCRIPT_DIR}.")


def load_label_items(label_path):
    if not label_path.is_file():
        return []

    with open(label_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        return get_label_container(data)
    except ValueError as exc:
        raise ValueError(f"{label_path} {exc}") from exc


def get_label_container(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("samples", "labels", "data"):
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError("labels.json must be a list or dict with samples/labels/data")


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_correction_items(correction_paths):
    items = []
    for raw_path in correction_paths or []:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.is_file():
            raise FileNotFoundError(f"Correction file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            if isinstance(data.get("samples"), list):
                data = data["samples"]
            else:
                data = [{"image": image, "steering": steering} for image, steering in data.items()]

        if not isinstance(data, list):
            raise ValueError(f"{path} must be a list, a samples dict, or an image-to-steering dict")

        for item in data:
            if not isinstance(item, dict):
                raise ValueError(f"{path} contains a non-object correction entry")
            item = dict(item)
            item["_correction_file"] = str(path)
            items.append(item)

    return items


def resolve_image_path(root, item):
    image_name = item.get("image") or item.get("filename") or item.get("file") or item.get("path")
    if not image_name:
        return None

    image_path = Path(image_name)
    if image_path.is_absolute() and image_path.exists():
        return image_path

    for candidate in (
        root / "images" / image_name,
        root / image_name,
        root / "rgb" / image_name,
        root / "camera" / image_name,
        SCRIPT_DIR / image_name,
    ):
        if candidate.exists():
            return candidate

    return None


def resize_image_uint8(img, width=160, height=120, crop_top_ratio=0.0):
    if crop_top_ratio > 0:
        crop_y = int(img.shape[0] * crop_top_ratio)
        img = img[crop_y:, :]

    return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)


def image_to_tensor(img):
    img = img.astype(np.float32) / 255.0
    img = (img - 0.5) / 0.5
    img = np.transpose(img, (2, 0, 1))
    return torch.from_numpy(img).float()


def preprocess_image(img, width=160, height=120, crop_top_ratio=0.0):
    return image_to_tensor(resize_image_uint8(img, width, height, crop_top_ratio))


def apply_camera_jitter(img, steer):
    height, width = img.shape[:2]
    shift_x = random.uniform(-0.08, 0.08) * width
    shift_y = random.uniform(-0.035, 0.035) * height
    angle = random.uniform(-3.0, 3.0)
    scale = random.uniform(0.96, 1.04)

    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle, scale)
    matrix[0, 2] += shift_x
    matrix[1, 2] += shift_y
    img = cv2.warpAffine(
        img,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )

    # If the camera is shifted right, the path appears left, so steer right.
    steer = clamp_servo(steer + (shift_x / max(1.0, width)) * 62.0)
    return img, steer


def apply_shadow(img):
    height, width = img.shape[:2]
    overlay = np.ones((height, width), dtype=np.float32)

    x1 = random.randint(-width // 2, width)
    x2 = random.randint(0, width + width // 2)
    polygon = np.array(
        [
            [x1, 0],
            [x2, 0],
            [x2 + random.randint(-width // 3, width // 3), height],
            [x1 + random.randint(-width // 3, width // 3), height],
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(overlay, [polygon], random.uniform(0.45, 0.78))
    return (img.astype(np.float32) * overlay[:, :, None]).clip(0, 255).astype(np.uint8)


def apply_glare(img):
    height, width = img.shape[:2]
    cx = random.randint(0, width - 1)
    cy = random.randint(0, max(1, int(height * 0.65)))
    radius = random.randint(max(8, width // 12), max(12, width // 4))

    yy, xx = np.ogrid[:height, :width]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    alpha = np.clip(1.0 - dist / max(1, radius), 0.0, 1.0) ** 2
    strength = random.uniform(35.0, 90.0)
    img = img.astype(np.float32) + alpha[:, :, None] * strength
    return np.clip(img, 0, 255).astype(np.uint8)


def apply_mixed_lighting(img):
    height, width = img.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    angle = random.uniform(-1.1, 1.1)
    axis = xx * math.cos(angle) + yy * math.sin(angle)
    center = random.uniform(float(axis.min()), float(axis.max()))
    transition = random.uniform(max(4.0, width * 0.05), max(8.0, width * 0.18))
    mask = np.clip((axis - center) / transition + 0.5, 0.0, 1.0)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=random.uniform(1.0, 3.0))

    img_f = img.astype(np.float32)
    shadow = img_f * random.uniform(0.45, 0.72)
    sun = img_f * random.uniform(1.10, 1.42) + random.uniform(4.0, 22.0)
    mixed = shadow * (1.0 - mask[:, :, None]) + sun * mask[:, :, None]

    if random.random() < 0.45:
        stripe_x = random.randint(0, max(0, width - 1))
        stripe_w = random.randint(max(4, width // 18), max(5, width // 6))
        x0 = max(0, stripe_x - stripe_w // 2)
        x1 = min(width, stripe_x + stripe_w // 2)
        mixed[:, x0:x1] *= random.uniform(0.48, 0.78)

    return np.clip(mixed, 0, 255).astype(np.uint8)


def apply_diagonal_shadow_band(img):
    height, width = img.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    angle = random.choice(
        [
            random.uniform(-0.95, -0.35),
            random.uniform(0.35, 0.95),
        ]
    )
    axis = xx * math.cos(angle) + yy * math.sin(angle)
    center = random.uniform(float(axis.min()), float(axis.max()))
    band_width = random.uniform(max(5.0, width * 0.08), max(8.0, width * 0.22))
    distance = np.abs(axis - center)
    mask = np.clip(1.0 - distance / band_width, 0.0, 1.0)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=random.uniform(2.0, 5.0))

    img_f = img.astype(np.float32)
    shadow_strength = random.uniform(0.38, 0.68)
    shadowed = img_f * shadow_strength
    out = img_f * (1.0 - mask[:, :, None]) + shadowed * mask[:, :, None]

    if random.random() < 0.35:
        bright_side = axis > center
        out[bright_side] = out[bright_side] * random.uniform(1.04, 1.22) + random.uniform(2.0, 12.0)

    return np.clip(out, 0, 255).astype(np.uint8)


def apply_tree_shadow_pattern(img):
    height, width = img.shape[:2]
    out = img.astype(np.float32)
    mask = np.zeros((height, width), dtype=np.float32)

    for _ in range(random.randint(3, 8)):
        x0 = random.randint(-width // 2, width)
        y0 = random.randint(-height // 4, height)
        x1 = x0 + random.randint(width // 5, width)
        y1 = y0 + random.randint(height // 4, height)
        thickness = random.randint(max(1, width // 80), max(2, width // 22))
        cv2.line(mask, (x0, y0), (x1, y1), random.uniform(0.35, 0.85), thickness, cv2.LINE_AA)

    for _ in range(random.randint(10, 26)):
        cx = random.randint(0, width - 1)
        cy = random.randint(0, height - 1)
        radius = random.randint(max(2, width // 80), max(4, width // 18))
        cv2.circle(mask, (cx, cy), radius, random.uniform(0.18, 0.55), -1, cv2.LINE_AA)

    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=random.uniform(1.0, 3.5))
    mask = np.clip(mask, 0.0, 0.92)
    shadow_strength = random.uniform(0.34, 0.72)
    out *= 1.0 - (mask[:, :, None] * shadow_strength)
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_sidewalk_road_edge_shadow(img):
    height, width = img.shape[:2]
    out = img.astype(np.float32)
    edge_x = random.choice(
        [
            random.randint(0, max(0, width // 3)),
            random.randint((2 * width) // 3, max((2 * width) // 3, width - 1)),
        ]
    )
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    slope = random.uniform(-0.28, 0.28)
    edge = edge_x + (yy - height * 0.5) * slope
    distance = xx - edge
    if random.random() < 0.5:
        mask = distance > 0
    else:
        mask = distance < 0

    softness = random.uniform(max(2.0, width * 0.025), max(5.0, width * 0.11))
    soft = np.clip(np.abs(distance) / softness, 0.0, 1.0)
    darken = (1.0 - soft) * random.uniform(0.18, 0.42)
    out[mask] *= random.uniform(0.45, 0.82)
    out *= 1.0 - darken[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def apply_patchy_concrete_texture(img):
    height, width = img.shape[:2]
    out = img.astype(np.float32)
    noise_small = np.random.normal(0.0, random.uniform(3.0, 12.0), (height, width, 1)).astype(np.float32)
    noise_large = np.random.normal(0.0, random.uniform(8.0, 22.0), (max(2, height // 8), max(2, width // 8), 1)).astype(np.float32)
    noise_large = cv2.resize(noise_large, (width, height), interpolation=cv2.INTER_CUBIC)
    if noise_large.ndim == 2:
        noise_large = noise_large[:, :, None]
    out += noise_small + noise_large

    if random.random() < 0.55:
        y0 = random.randint(int(height * 0.35), max(int(height * 0.35), height - 1))
        h = random.randint(max(2, height // 18), max(3, height // 5))
        out[y0 : min(height, y0 + h), :] *= random.uniform(0.78, 1.22)

    return np.clip(out, 0, 255).astype(np.uint8)


def apply_shadow_stress_augmentation(img):
    if random.random() < 0.65:
        img = apply_mixed_lighting(img)
    if random.random() < 0.65:
        img = apply_diagonal_shadow_band(img)
    if random.random() < 0.55:
        img = apply_tree_shadow_pattern(img)
    if random.random() < 0.45:
        img = apply_sidewalk_road_edge_shadow(img)
    if random.random() < 0.35:
        img = apply_patchy_concrete_texture(img)
    return img


def apply_bgr_channel_jitter(img):
    img = img.astype(np.float32)
    gains = np.array(
        [
            random.uniform(0.82, 1.18),
            random.uniform(0.82, 1.18),
            random.uniform(0.82, 1.18),
        ],
        dtype=np.float32,
    )
    bias = np.array(
        [
            random.uniform(-10.0, 10.0),
            random.uniform(-10.0, 10.0),
            random.uniform(-10.0, 10.0),
        ],
        dtype=np.float32,
    )
    img = img * gains.reshape(1, 1, 3) + bias.reshape(1, 1, 3)
    return np.clip(img, 0, 255).astype(np.uint8)


def apply_hsv_jitter(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = cv2.split(hsv)
    h = (h + random.uniform(-8.0, 8.0)) % 180.0
    s = np.clip(s * random.uniform(0.82, 1.18) + random.uniform(-8.0, 8.0), 0, 255)
    v = np.clip(v * random.uniform(0.82, 1.18) + random.uniform(-12.0, 12.0), 0, 255)
    hsv = cv2.merge((h, s, v)).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def apply_clahe_to_bgr(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    clip_limit = random.uniform(1.5, 2.5)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    v = clahe.apply(v)
    return cv2.cvtColor(cv2.merge((h, s, v)), cv2.COLOR_HSV2BGR)


def apply_carla_domain_randomization(img):
    img = img.astype(np.float32)

    contrast = random.uniform(0.70, 1.35)
    brightness = random.uniform(-34.0, 34.0)
    img = img * contrast + brightness
    img = np.clip(img, 0, 255).astype(np.uint8)

    if random.random() < 0.70:
        img = apply_bgr_channel_jitter(img)
    if random.random() < 0.60:
        img = apply_patchy_concrete_texture(img)
    if random.random() < 0.50:
        img = apply_tree_shadow_pattern(img)
    if random.random() < 0.35:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    if random.random() < 0.55:
        noise = np.random.normal(0.0, random.uniform(2.0, 8.0), img.shape).astype(np.float32)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return img


def apply_curved_curb_distractor(img):
    height, width = img.shape[:2]
    out = img.copy()
    center_x = random.choice(
        [
            random.randint(-width, width // 3),
            random.randint((2 * width) // 3, width * 2),
        ]
    )
    center_y = random.randint(int(height * 0.45), height * 2)
    radius = random.randint(max(width // 2, 1), max(width * 2, width // 2 + 1))
    start_angle = random.randint(190, 260)
    end_angle = random.randint(280, 355)
    color = random.randint(70, 185)
    thickness = random.randint(1, 3)

    overlay = out.copy()
    cv2.ellipse(
        overlay,
        (center_x, center_y),
        (radius, max(4, radius // random.randint(3, 7))),
        random.uniform(-8.0, 8.0),
        start_angle,
        end_angle,
        (color, color, color),
        thickness,
        lineType=cv2.LINE_AA,
    )

    if random.random() < 0.55:
        overlay = cv2.GaussianBlur(overlay, (3, 3), 0)

    return cv2.addWeighted(out, 0.72, overlay, 0.28, 0)


def apply_obstacle_occlusion(img):
    height, width = img.shape[:2]
    count = 1 if random.random() < 0.85 else 2
    img = img.copy()

    for _ in range(count):
        occ_w = random.randint(max(6, width // 16), max(8, width // 5))
        occ_h = random.randint(max(6, height // 12), max(8, height // 3))
        x = random.randint(0, max(0, width - occ_w))
        y = random.randint(int(height * 0.45), max(int(height * 0.45), height - occ_h))
        color = random.choice(
            [
                random.randint(15, 55),
                random.randint(80, 130),
                random.randint(170, 230),
            ]
        )
        patch = np.full((occ_h, occ_w, 3), color, dtype=np.uint8)
        if random.random() < 0.45:
            noise = np.random.normal(0, 12, patch.shape).astype(np.float32)
            patch = np.clip(patch.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        img[y : y + occ_h, x : x + occ_w] = patch

    return img


def apply_weather_haze(img):
    haze = np.full_like(img, random.randint(175, 230), dtype=np.uint8)
    alpha = random.uniform(0.08, 0.22)
    return cv2.addWeighted(img, 1.0 - alpha, haze, alpha, 0)


def apply_rain_streaks(img, drizzle=False):
    height, width = img.shape[:2]
    rain = np.zeros_like(img, dtype=np.uint8)
    drops = random.randint(45, 95) if drizzle else random.randint(95, 190)
    length_min, length_max = (4, 10) if drizzle else (8, 22)
    thickness = 1 if drizzle or random.random() < 0.85 else 2
    slant = random.randint(-5, 3)

    for _ in range(drops):
        x1 = random.randint(0, width - 1)
        y1 = random.randint(0, height - 1)
        length = random.randint(length_min, length_max)
        x2 = int(np.clip(x1 + slant + random.randint(-2, 2), 0, width - 1))
        y2 = int(np.clip(y1 + length, 0, height - 1))
        color = random.randint(155, 230)
        cv2.line(rain, (x1, y1), (x2, y2), (color, color, color), thickness)

    rain = cv2.GaussianBlur(rain, (3, 3), 0)
    alpha = random.uniform(0.18, 0.34) if drizzle else random.uniform(0.26, 0.48)
    img = cv2.addWeighted(img, 1.0, rain, alpha, 0)

    if not drizzle and random.random() < 0.45:
        img = cv2.GaussianBlur(img, (3, 3), 0)

    return img


def apply_raindrops_on_lens(img):
    height, width = img.shape[:2]
    out = img.copy()
    drops = random.randint(3, 9)

    for _ in range(drops):
        radius = random.randint(max(3, width // 70), max(5, width // 22))
        cx = random.randint(radius, max(radius, width - radius - 1))
        cy = random.randint(radius, max(radius, height - radius - 1))

        x0, x1 = max(0, cx - radius), min(width, cx + radius)
        y0, y1 = max(0, cy - radius), min(height, cy + radius)
        roi = out[y0:y1, x0:x1]
        if roi.size == 0:
            continue

        yy, xx = np.ogrid[y0:y1, x0:x1]
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        mask = (dist <= radius).astype(np.float32)
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(1.0, radius / 4.0))
        mask = np.clip(mask, 0.0, 1.0)

        blurred = cv2.GaussianBlur(roi, (0, 0), sigmaX=max(1.0, radius / 3.0))
        highlight = np.full_like(roi, random.randint(190, 245), dtype=np.uint8)
        drop = cv2.addWeighted(blurred, 0.78, highlight, 0.22, 0)
        out[y0:y1, x0:x1] = (
            roi.astype(np.float32) * (1.0 - mask[:, :, None] * 0.72)
            + drop.astype(np.float32) * (mask[:, :, None] * 0.72)
        ).clip(0, 255).astype(np.uint8)

    return out


def apply_wet_road_effect(img):
    height = img.shape[0]
    out = img.astype(np.float32)
    lower = slice(int(height * 0.50), height)
    out[lower] = out[lower] * random.uniform(0.72, 0.92) + random.uniform(8.0, 24.0)
    if random.random() < 0.60:
        reflection = cv2.flip(out[: int(height * 0.45)].astype(np.uint8), 0)
        reflection = cv2.resize(reflection, (img.shape[1], height - int(height * 0.50)))
        out[lower] = cv2.addWeighted(out[lower].astype(np.uint8), 0.82, reflection, 0.18, 0)
    return np.clip(out, 0, 255).astype(np.uint8)


def augment_image(
    img,
    steer,
    source="real",
    shadow_aug_probability=0.85,
    carla_domain_randomize_probability=0.70,
    hsv_aug_probability=0.0,
    clahe_aug_probability=0.0,
):
    img = img.astype(np.float32)

    hsv_prob = max(0.0, min(1.0, float(hsv_aug_probability)))
    clahe_prob = max(0.0, min(1.0, float(clahe_aug_probability)))

    if random.random() < hsv_prob:
        img = apply_hsv_jitter(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if random.random() < clahe_prob:
        img = apply_clahe_to_bgr(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if random.random() < 0.75:
        img, steer = apply_camera_jitter(np.clip(img, 0, 255).astype(np.uint8), steer)
        img = img.astype(np.float32)

    if random.random() < 0.90:
        contrast = random.uniform(0.60, 1.45)
        brightness = random.uniform(-38.0, 38.0)
        img = img * contrast + brightness

    if random.random() < 0.65:
        img = apply_bgr_channel_jitter(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if random.random() < 0.55:
        img = apply_mixed_lighting(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if random.random() < 0.35:
        img = apply_diagonal_shadow_band(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if random.random() < 0.30:
        img = apply_curved_curb_distractor(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if random.random() < 0.25:
        img = apply_shadow(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if random.random() < 0.12:
        img = apply_glare(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    source_lower = str(source).lower()
    shadow_prob = max(0.0, min(1.0, float(shadow_aug_probability)))
    if "correction" in source_lower or source_lower == "real":
        shadow_prob = min(1.0, shadow_prob * 1.25)
    if random.random() < shadow_prob:
        img = apply_shadow_stress_augmentation(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if "carla" in source_lower and random.random() < max(0.0, min(1.0, float(carla_domain_randomize_probability))):
        img = apply_carla_domain_randomization(np.clip(img, 0, 255).astype(np.uint8)).astype(np.float32)

    if random.random() < 0.35:
        noise = np.random.normal(0.0, random.uniform(2.0, 11.0), img.shape).astype(np.float32)
        img = img + noise

    if random.random() < 0.18:
        img = cv2.GaussianBlur(img, (3, 3), 0)

    return np.clip(img, 0, 255).astype(np.uint8), steer


def print_bucket_distribution(title, values):
    values = np.array(values, dtype=np.float32)
    buckets = [
        ("0_to_45_hard_left", values < 45.0),
        ("45_to_75_left", (values >= 45.0) & (values < 75.0)),
        ("75_to_85_soft_left", (values >= 75.0) & (values < 85.0)),
        ("85_to_95_straight", (values >= 85.0) & (values <= 95.0)),
        ("95_to_105_soft_right", (values > 95.0) & (values <= 105.0)),
        ("105_to_135_right", (values > 105.0) & (values <= 135.0)),
        ("135_to_180_hard_right", values > 135.0),
    ]
    print(title + ":")
    for label, mask in buckets:
        print(f"  {label}={int(mask.sum())}")


def summarize_array(values):
    values = np.array(values, dtype=np.float32)
    if values.size == 0:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "near_straight_85_95": 0,
        }
    return {
        "count": int(values.size),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "near_straight_85_95": int(((values >= 85.0) & (values <= 95.0)).sum()),
    }


def source_name_for_root(root):
    name = str(root).lower()
    synthetic_markers = ("carla", "dataset_l2", "synthetic", "sim")
    return "carla" if any(marker in name for marker in synthetic_markers) else "real"


class SteeringDataset(Dataset):
    def __init__(
        self,
        roots,
        correction_items=None,
        width=160,
        height=120,
        crop_top_ratio=0.0,
        augment=False,
        flip_aug_probability=0.0,
        shadow_aug_probability=0.85,
        carla_domain_randomize_probability=0.70,
        hsv_aug_probability=0.0,
        clahe_aug_probability=0.0,
        scan_log_every=1000,
        stage_name="dataset",
    ):
        self.width = width
        self.height = height
        self.crop_top_ratio = crop_top_ratio
        self.augment = augment
        self.flip_aug_probability = max(0.0, min(1.0, float(flip_aug_probability)))
        self.shadow_aug_probability = max(0.0, min(1.0, float(shadow_aug_probability)))
        self.carla_domain_randomize_probability = max(0.0, min(1.0, float(carla_domain_randomize_probability)))
        self.hsv_aug_probability = max(0.0, min(1.0, float(hsv_aug_probability)))
        self.clahe_aug_probability = max(0.0, min(1.0, float(clahe_aug_probability)))
        self.scan_log_every = max(1, int(scan_log_every))
        self.stage_name = stage_name
        self.samples = []
        self.targets = []
        self.sources = []
        correction_items = correction_items or []
        correction_image_paths = set()
        for item in correction_items:
            correction_file = Path(item.get("_correction_file", ".")).parent
            img_path = resolve_image_path(correction_file, item)
            if img_path is not None:
                correction_image_paths.add(str(img_path.resolve()))

        skipped_missing = 0
        skipped_bad = 0
        clipped_labels = 0
        skipped_overridden = 0

        for root in roots:
            root = Path(root)
            source_name = source_name_for_root(root)
            root_start = time.time()
            items = load_label_items(root / "labels.json")
            root_used = 0
            root_missing = 0
            root_bad = 0
            root_targets = []
            label_mode = infer_label_mode(items)

            print(
                f"[{self.stage_name}] scanning root={root} labels={len(items)} "
                f"label_mode={label_mode} output_scale=servo_degrees_0_180 augment={self.augment} "
                f"source={source_name} flip_aug_prob={self.flip_aug_probability:.2f} "
                f"shadow_aug_prob={self.shadow_aug_probability:.2f} "
                f"carla_domain_randomize_prob={self.carla_domain_randomize_probability:.2f} "
                f"hsv_aug_prob={self.hsv_aug_probability:.2f} "
                f"clahe_aug_prob={self.clahe_aug_probability:.2f}",
                flush=True,
            )

            for index, item in enumerate(items, start=1):
                img_path = resolve_image_path(root, item)
                if img_path is None:
                    skipped_missing += 1
                    root_missing += 1
                    continue
                if str(img_path.resolve()) in correction_image_paths:
                    skipped_overridden += 1
                    continue

                raw_steer = get_raw_steering(item, 0.0)
                try:
                    raw_steer = float(raw_steer)
                    steer = label_to_servo(raw_steer, label_mode)
                except (TypeError, ValueError):
                    skipped_bad += 1
                    root_bad += 1
                    continue

                if label_mode == "normalized" or abs(raw_steer - steer) > 1e-8:
                    clipped_labels += 1

                self.samples.append((img_path, steer))
                self.targets.append(steer)
                self.sources.append(source_name)
                root_targets.append(steer)
                root_used += 1

                if index % self.scan_log_every == 0 or index == len(items):
                    elapsed = time.time() - root_start
                    rate = index / max(elapsed, 1e-6)
                    target_summary = summarize_array(root_targets)
                    print(
                        f"[{self.stage_name}] root={root.name} scanned={index}/{len(items)} "
                        f"used={root_used} missing={root_missing} bad={root_bad} "
                        f"rate={rate:.1f}/s elapsed={fmt_time(elapsed)} "
                        f"target_mean={target_summary['mean']:.4f} "
                        f"target_range=[{target_summary['min']:.4f},{target_summary['max']:.4f}]",
                        flush=True,
                    )

            root_elapsed = time.time() - root_start
            print(
                f"[{self.stage_name}] root done={root.name} labels={len(items)} used={root_used} "
                f"missing={root_missing} bad={root_bad} elapsed={fmt_time(root_elapsed)}",
                flush=True,
            )

        correction_used = 0
        correction_missing = 0
        correction_bad = 0
        correction_label_mode = infer_label_mode(correction_items)
        if correction_items:
            print(
                f"[{self.stage_name}] loading corrections={len(correction_items)} "
                f"label_mode={correction_label_mode}",
                flush=True,
            )

        for item in correction_items:
            correction_file = Path(item.get("_correction_file", ".")).parent
            img_path = resolve_image_path(correction_file, item)
            if img_path is None:
                correction_missing += 1
                continue

            raw_steer = get_raw_steering(item, None)
            try:
                steer = label_to_servo(raw_steer, correction_label_mode)
            except (TypeError, ValueError):
                correction_bad += 1
                continue

            repeat = max(1, int(item.get("repeat", 6)))
            for _ in range(repeat):
                self.samples.append((img_path, steer))
                self.targets.append(steer)
                self.sources.append("correction")
            correction_used += repeat

        if correction_items:
            print(
                f"[{self.stage_name}] corrections used={correction_used} "
                f"missing={correction_missing} bad={correction_bad}",
                flush=True,
            )

        if not self.samples:
            raise FileNotFoundError("No usable samples found.")

        t = np.array(self.targets, dtype=np.float32)
        print(f"[{self.stage_name}] loaded samples: {len(self.samples)}")
        print(f"[{self.stage_name}] skipped missing images: {skipped_missing}")
        print(f"[{self.stage_name}] skipped bad labels: {skipped_bad}")
        print(f"[{self.stage_name}] skipped base labels overridden by corrections: {skipped_overridden}")
        print(f"[{self.stage_name}] normalized labels converted to servo degrees: {clipped_labels}")
        print(
            f"[{self.stage_name}] target range: min={t.min():.6f} max={t.max():.6f} "
            f"mean={t.mean():.6f} std={t.std():.6f}",
            flush=True,
        )
        print(f"[{self.stage_name}] target straight 85..95: {int(((t >= 85.0) & (t <= 95.0)).sum())}")
        print_bucket_distribution(f"{self.stage_name} target buckets", t)
        source_counts = Counter(self.sources)
        print(f"[{self.stage_name}] source counts:")
        for source_name, count in sorted(source_counts.items()):
            print(f"  {source_name}={count}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, steer = self.samples[idx]
        source = self.sources[idx]
        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(img_path)

        # Run augmentation at network input size, not full camera/JPG resolution.
        # This keeps oversampled training runs CPU-bound for less time.
        img = resize_image_uint8(img, self.width, self.height, self.crop_top_ratio)

        if self.augment:
            if random.random() < self.flip_aug_probability:
                img = cv2.flip(img, 1)
                steer = 180.0 - steer
            img, steer = augment_image(
                img,
                steer,
                source,
                self.shadow_aug_probability,
                self.carla_domain_randomize_probability,
                self.hsv_aug_probability,
                self.clahe_aug_probability,
            )

        img = image_to_tensor(img)
        steer = torch.tensor([clamp_servo(steer)], dtype=torch.float32)
        return img, steer


class SteeringAutonomyV2(nn.Module):
    def __init__(self):
        super().__init__()

        # Steering depends on where features are in the image, so keep a coarse
        # spatial grid instead of collapsing everything to a single global point.
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
        return 90.0 + 85.0 * self.head(x)


SERVO_BUCKETS = [
    ("hard_left_0_45", 0.0, 45.0),
    ("left_45_75", 45.0, 75.0),
    ("soft_left_75_85", 75.0, 85.0),
    ("straight_85_95", 85.0, 95.0),
    ("soft_right_95_105", 95.0, 105.0),
    ("right_105_135", 105.0, 135.0),
    ("hard_right_135_180", 135.0, 180.0),
]


def servo_bucket_index(steer):
    steer = clamp_servo(steer)
    for index, (_, lo, hi) in enumerate(SERVO_BUCKETS):
        if index == len(SERVO_BUCKETS) - 1:
            if lo <= steer <= hi:
                return index
        elif lo <= steer < hi:
            return index
    return len(SERVO_BUCKETS) - 1


def steering_magnitude_weight(steer):
    mag = abs(float(steer) - 90.0) / 90.0
    if mag < 0.03:
        return 0.9
    if mag < 0.10:
        return 1.0
    if mag < 0.25:
        return 1.4
    return 1.65


def source_weight(source, real_weight=2.0, carla_weight=0.6, correction_weight=3.0):
    source = str(source).lower()
    if source == "carla":
        return float(carla_weight)
    if source == "correction":
        return float(correction_weight)
    return float(real_weight)


def make_weighted_sampler(
    base_dataset,
    subset,
    samples_per_epoch=50000,
    real_weight=2.0,
    carla_weight=0.6,
    correction_weight=3.0,
):
    bucket_counts = [0 for _ in SERVO_BUCKETS]
    source_counts = Counter()
    for index in subset.indices:
        bucket_counts[servo_bucket_index(base_dataset.targets[index])] += 1
        source_counts[base_dataset.sources[index]] += 1

    nonzero_counts = [count for count in bucket_counts if count > 0]
    target_count = float(np.median(nonzero_counts)) if nonzero_counts else 1.0

    weights = []
    for index in subset.indices:
        steer = base_dataset.targets[index]
        bucket_index = servo_bucket_index(steer)
        bucket_count = max(1, bucket_counts[bucket_index])
        bucket_weight = target_count / float(bucket_count)
        sample_source_weight = source_weight(
            base_dataset.sources[index],
            real_weight,
            carla_weight,
            correction_weight,
        )
        weights.append(bucket_weight * steering_magnitude_weight(steer) * sample_source_weight)

    print("[sampler] servo bucket counts:")
    for (name, _, _), count in zip(SERVO_BUCKETS, bucket_counts):
        print(f"  {name}={count}")
    print("[sampler] source counts and weights:")
    for source_name, count in sorted(source_counts.items()):
        print(
            f"  {source_name}={count} weight={source_weight(source_name, real_weight, carla_weight, correction_weight):.3f}"
        )

    num_samples = int(samples_per_epoch)
    if num_samples <= 0:
        num_samples = len(weights)
    print(f"[sampler] samples_per_epoch={num_samples} base_train_samples={len(weights)}")
    return WeightedRandomSampler(weights, num_samples=num_samples, replacement=True)


def build_loader(dataset, batch_size, num_workers, shuffle=False, sampler=None, drop_last=False):
    kwargs = {
        "batch_size": batch_size,
        "shuffle": shuffle if sampler is None else False,
        "sampler": sampler,
        "num_workers": num_workers,
        "pin_memory": DEVICE == "cuda",
        "drop_last": drop_last,
    }
    if num_workers > 0:
        kwargs["persistent_workers"] = True
        kwargs["prefetch_factor"] = 2
    return DataLoader(dataset, **kwargs)


def evaluate(model, loader, loss_fn):
    model.eval()
    val_total = 0.0
    mae_total = 0.0
    count = 0
    pred_values = []
    target_values = []

    with torch.no_grad():
        for imgs, targets in loader:
            imgs = imgs.to(DEVICE, non_blocking=True)
            targets = targets.to(DEVICE, non_blocking=True)

            preds = model(imgs)
            preds = torch.clamp(preds, 0.0, 180.0)

            raw = loss_fn(preds, targets)
            target_turn = torch.abs(targets - 90.0) / 90.0
            weights = 1.0 + 2.0 * target_turn
            vloss = (raw * weights).mean()

            val_total += vloss.item()
            mae_total += torch.mean(torch.abs(preds - targets)).item()
            count += 1
            pred_values.append(preds.detach().cpu().numpy().reshape(-1))
            target_values.append(targets.detach().cpu().numpy().reshape(-1))

    pred_values = np.concatenate(pred_values) if pred_values else np.array([0.0], dtype=np.float32)
    target_values = np.concatenate(target_values) if target_values else np.array([0.0], dtype=np.float32)

    return {
        "loss": val_total / max(1, count),
        "mae": mae_total / max(1, count),
        "pred_min": float(pred_values.min()),
        "pred_max": float(pred_values.max()),
        "pred_mean": float(pred_values.mean()),
        "pred_straight_85_95": int(((pred_values >= 85.0) & (pred_values <= 95.0)).sum()),
        "pred_values": pred_values,
        "target_min": float(target_values.min()),
        "target_max": float(target_values.max()),
        "target_mean": float(target_values.mean()),
        "target_values": target_values,
    }


def train(roots, args):
    start_time = time.time()
    print("[start] train_autonomy_v2.py", flush=True)
    print(f"[start] device={DEVICE}", flush=True)
    print(f"[start] roots={[str(r) for r in roots]}", flush=True)
    correction_items = load_correction_items(args.corrections)
    if correction_items:
        print(f"[start] correction samples={len(correction_items)} files={args.corrections}", flush=True)
    print(
        f"[start] epochs={args.epochs} batch_size={args.batch_size} workers={args.workers} "
        f"lr={args.lr} weight_decay={args.weight_decay} grad_clip={args.grad_clip}",
        flush=True,
    )
    print(
        f"[start] augmentation shadow_prob={args.shadow_aug_probability:.2f} "
        f"flip_prob={args.flip_aug_probability:.2f} "
        f"carla_domain_randomize_prob={args.carla_domain_randomize_probability:.2f} "
        f"hsv_prob={args.hsv_aug_probability:.2f} "
        f"clahe_prob={args.clahe_aug_probability:.2f} "
        f"source_weights real={args.real_sample_weight:.2f} carla={args.carla_sample_weight:.2f} "
        f"correction={args.correction_sample_weight:.2f}",
        flush=True,
    )
    print(f"[start] {gpu_status()}", flush=True)

    base_dataset = SteeringDataset(
        roots,
        correction_items,
        args.width,
        args.height,
        args.crop_top_ratio,
        augment=False,
        flip_aug_probability=0.0,
        shadow_aug_probability=0.0,
        carla_domain_randomize_probability=0.0,
        hsv_aug_probability=0.0,
        clahe_aug_probability=0.0,
        scan_log_every=args.scan_log_every,
        stage_name="dataset.base",
    )

    n = len(base_dataset)
    val_size = max(1, int(args.val_split * n))
    train_size = max(1, n - val_size)

    gen = torch.Generator().manual_seed(args.seed)
    train_base_subset, val_subset = random_split(base_dataset, [train_size, val_size], generator=gen)

    augmented_dataset = SteeringDataset(
        roots,
        correction_items,
        args.width,
        args.height,
        args.crop_top_ratio,
        augment=True,
        flip_aug_probability=args.flip_aug_probability,
        shadow_aug_probability=args.shadow_aug_probability,
        carla_domain_randomize_probability=args.carla_domain_randomize_probability,
        hsv_aug_probability=args.hsv_aug_probability,
        clahe_aug_probability=args.clahe_aug_probability,
        scan_log_every=args.scan_log_every,
        stage_name="dataset.augmented",
    )
    train_subset = Subset(augmented_dataset, train_base_subset.indices)
    train_sampler = make_weighted_sampler(
        base_dataset,
        train_base_subset,
        args.samples_per_epoch,
        args.real_sample_weight,
        args.carla_sample_weight,
        args.correction_sample_weight,
    )

    train_loader = build_loader(
        train_subset,
        args.batch_size,
        args.workers,
        sampler=train_sampler,
        drop_last=True,
    )

    val_loader = build_loader(
        val_subset,
        args.batch_size,
        max(0, args.workers // 2),
        shuffle=False,
        drop_last=False,
    )

    model = SteeringAutonomyV2().to(DEVICE)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, args.epochs))
    loss_fn = nn.SmoothL1Loss(reduction="none")

    if args.final_output or args.best_output:
        final_path = Path(args.final_output or "SidewalkPilot.pth").expanduser()
        best_path = Path(args.best_output or "SidewalkPilot-best.pth").expanduser()
    elif args.model_version:
        safe_version = str(args.model_version).strip().replace("/", "_").replace("\\", "_")
        final_version = safe_version[:-1] if safe_version.endswith("b") else safe_version
        best_version = safe_version if safe_version.endswith("b") else f"{safe_version}b"
        final_path = Path(f"SidewalkPilot-v{final_version}.pth")
        best_path = Path(f"SidewalkPilot-v{best_version}.pth")
    else:
        best_path = Path("SidewalkPilot-best.pth")
        final_path = Path("SidewalkPilot.pth")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    best_path.parent.mkdir(parents=True, exist_ok=True)

    best_val = float("inf")
    loss_ema = None
    total_steps = max(1, args.epochs * len(train_loader))
    global_step = 0

    print("Device:", DEVICE)
    print(f"Train samples: {len(train_subset)} | Val samples: {len(val_subset)}")
    print("Roots:", [str(r) for r in roots])
    print(gpu_status())
    print(f"Train batches: {len(train_loader)} | Val batches: {len(val_loader)}")
    print(f"Total steps: {total_steps}")
    print(f"Final checkpoint: {final_path}")
    print(f"Best checkpoint: {best_path}")

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()
        model.train()
        train_total = 0.0

        for step, (imgs, targets) in enumerate(train_loader):
            batch_start = time.time()
            imgs = imgs.to(DEVICE, non_blocking=True)
            targets = targets.to(DEVICE, non_blocking=True)

            preds = model(imgs)
            preds = torch.clamp(preds, 0.0, 180.0)

            raw = loss_fn(preds, targets)
            target_turn = torch.abs(targets - 90.0) / 90.0
            pred_turn = torch.abs(preds - 90.0) / 85.0
            weights = 1.0 + 2.0 * target_turn
            regression_loss = (raw * weights).mean()
            oversteer_penalty = torch.mean(torch.relu(pred_turn - target_turn - 0.18) ** 2)
            left_drift_penalty = torch.mean(
                torch.relu(targets - 75.0) * torch.relu(75.0 - preds) / 180.0
            )
            saturation_penalty = torch.mean(torch.relu(pred_turn - 0.92) ** 2)
            loss = (
                regression_loss
                + 4.0 * oversteer_penalty
                + 2.0 * left_drift_penalty
                + 15.0 * saturation_penalty
            )

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip).item())
            optimizer.step()

            global_step += 1
            val = loss.item()
            train_total += val
            loss_ema = val if loss_ema is None else 0.95 * loss_ema + 0.05 * val

            if step % args.log_every == 0:
                batch_sec = time.time() - batch_start
                img_per_sec = imgs.size(0) / max(batch_sec, 1e-6)
                elapsed = time.time() - start_time
                steps_per_sec = global_step / max(elapsed, 1e-6)
                eta = (total_steps - global_step) / max(steps_per_sec, 1e-6)
                pred_min = float(preds.min().item())
                pred_max = float(preds.max().item())
                pred_mean = float(preds.mean().item())
                target_min = float(targets.min().item())
                target_max = float(targets.max().item())
                target_mean = float(targets.mean().item())
                lr = float(optimizer.param_groups[0]["lr"])

                print(
                    f"[train] epoch={epoch}/{args.epochs} step={step + 1}/{len(train_loader)} "
                    f"global={global_step}/{total_steps} loss={val:.6f} ema={loss_ema:.6f} "
                    f"lr={lr:.7f} grad={grad_norm:.4f} "
                    f"pred_deg=[{pred_min:.2f},{pred_max:.2f}] mean={pred_mean:.2f} "
                    f"target_deg=[{target_min:.2f},{target_max:.2f}] mean={target_mean:.2f} "
                    f"speed={img_per_sec:.1f} img/s elapsed={fmt_time(elapsed)} eta={fmt_time(eta)} "
                    f"{gpu_status()}",
                    flush=True,
                )

        scheduler.step()
        metrics = evaluate(model, val_loader, loss_fn)
        avg_train = train_total / max(1, len(train_loader))
        epoch_elapsed = time.time() - epoch_start
        total_elapsed = time.time() - start_time
        current_lr = float(optimizer.param_groups[0]["lr"])

        print(
            f"Epoch {epoch} DONE | "
            f"Train {avg_train:.6f} | Val {metrics['loss']:.6f} | "
            f"MAE_deg {metrics['mae']:.6f} | "
            f"PredDegRange [{metrics['pred_min']:.6f}, {metrics['pred_max']:.6f}] | "
            f"PredDegMean {metrics['pred_mean']:.6f} | "
            f"Pred straight 85..95 {metrics['pred_straight_85_95']} | "
            f"TargetDegRange [{metrics['target_min']:.6f}, {metrics['target_max']:.6f}] | "
            f"EpochTime {fmt_time(epoch_elapsed)} | Total {fmt_time(total_elapsed)}"
        )

        if epoch == 1 or epoch == args.epochs or epoch % args.bucket_every == 0:
            print_bucket_distribution("validation prediction buckets", metrics["pred_values"])
            print_bucket_distribution("validation target buckets", metrics["target_values"])

        if metrics["loss"] < best_val:
            best_val = metrics["loss"]
            torch.save(model.state_dict(), best_path)
            print("Saved best:", best_path)

    torch.save(model.state_dict(), final_path)
    print("Saved:", final_path)
    print("Saved best:", best_path)
    print(f"[done] total_time={fmt_time(time.time() - start_time)} best_val={best_val:.6f}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--val-split", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=200)
    parser.add_argument("--height", type=int, default=66)
    parser.add_argument("--crop-top-ratio", type=float, default=0.0)
    parser.add_argument("--log-every", type=int, default=50)
    parser.add_argument("--bucket-every", type=int, default=5)
    parser.add_argument("--scan-log-every", type=int, default=1000)
    parser.add_argument("--samples-per-epoch", type=int, default=50000)
    parser.add_argument("--corrections", nargs="*", default=None)
    parser.add_argument("--flip-aug-probability", type=float, default=0.0)
    parser.add_argument("--shadow-aug-probability", type=float, default=0.85)
    parser.add_argument("--carla-domain-randomize-probability", type=float, default=0.70)
    parser.add_argument("--hsv-aug-probability", type=float, default=0.0)
    parser.add_argument("--clahe-aug-probability", type=float, default=0.0)
    parser.add_argument("--real-sample-weight", type=float, default=2.0)
    parser.add_argument("--carla-sample-weight", type=float, default=0.6)
    parser.add_argument("--correction-sample-weight", type=float, default=3.0)
    parser.add_argument(
        "--model-version",
        default=None,
        help="version suffix for SidewalkPilot checkpoint names, e.g. 2.4 -> SidewalkPilot-v2.4.pth and SidewalkPilot-v2.4b.pth",
    )
    parser.add_argument("--final-output", default=None, help="explicit final checkpoint path")
    parser.add_argument("--best-output", default=None, help="explicit best checkpoint path")
    parser.add_argument("--convert-labels-to-servo", action="store_true")
    parser.add_argument("--roots", nargs="*", default=None)
    args = parser.parse_args()
    if str(args.model_version or "").strip() == "2.3" and args.flip_aug_probability != 0.0:
        print("[config] model-version 2.3 disables flip augmentation; forcing flip_prob=0.00", flush=True)
        args.flip_aug_probability = 0.0

    roots = discover_roots(args.roots)
    if args.convert_labels_to_servo:
        convert_roots_to_servo(roots)
        return

    train(roots=roots, args=args)


if __name__ == "__main__":
    main()
