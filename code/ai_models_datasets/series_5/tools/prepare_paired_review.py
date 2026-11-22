#!/usr/bin/env python3
"""Freeze a new, review-disjoint sample and a private balanced A/B assignment."""

import argparse
from bisect import bisect_left, insort
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import random
import re
import subprocess

import numpy as np
from PIL import Image

from label_grounded_sam2 import DEFAULT_SOURCE, digest_json, sha256, utc_now, write_json

IMAGE_PATTERN = re.compile(r"\d{4}_\d{2}_\d{2}_run_\d+__photo_\d{8}_\d{6}_\d{6}\.jpg")
GUARD_SECONDS = 5.0
HASH_DISTANCE = 4


def timestamp(name):
    return datetime.strptime(name.split("__photo_", 1)[1].removesuffix(".jpg"), "%Y%m%d_%H%M%S_%f").timestamp()


def near_time(value, ordered, gap=GUARD_SECONDS):
    index = bisect_left(ordered, value)
    return any(abs(value - ordered[i]) <= gap for i in (index - 1, index) if 0 <= i < len(ordered))


def dhash(image):
    pixels = np.asarray(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
    return int.from_bytes(np.packbits(pixels[:, 1:] > pixels[:, :-1]).tobytes(), "big")


def image_names(value):
    if isinstance(value, str):
        yield from IMAGE_PATTERN.findall(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from image_names(key)
            yield from image_names(item)
    elif isinstance(value, list):
        for item in value:
            yield from image_names(item)


def quotas(groups, count):
    total = sum(map(len, groups.values()))
    result = {run: count * len(items) // total for run, items in groups.items()}
    order = sorted(groups, key=lambda r: (-(count * len(groups[r]) % total), r))
    for run in order[:count - sum(result.values())]:
        result[run] += 1
    return result


def validate_selection(path):
    selection = json.loads(path.read_text())
    if selection.get("kind") != "paired-class1-review-selection-v1":
        raise ValueError("Not a paired review selection")
    source = Path(selection["source"])
    names = sorted(p.name for p in source.glob("*.jpg"))
    selected = selection["images"]
    if (len(selected) != 200 or len(set(selected)) != 200
            or not set(selected).issubset(names) or digest_json(names) != selection["source_names_sha256"]
            or sha256(source / "labels.json") != selection["steering_labels_sha256"]
            or [f["image"] for f in selection["frames"]] != selected):
        raise ValueError("Changed source pool or invalid selection")
    for frame in selection["frames"]:
        if sha256(source / frame["image"]) != frame["source_sha256"]:
            raise ValueError("Selected source image changed")
    return selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--history", type=Path, default=Path.home() / "sidewalkpilot-labels")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261027)
    parser.add_argument("--mac-host", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Selection output already exists")
    source, history = args.source.resolve(), args.history.resolve()
    names = sorted(p.name for p in source.glob("*.jpg"))
    if set(names) != set(json.loads((source / "labels.json").read_text())):
        raise ValueError("Steering labels and JPEG filenames differ")
    # Only prior manifests/review exports, not dependency trees or the full source labels.
    paths = set()
    for pattern in ("*/manifest.json", "*/selection.json", "*/*/selection.json",
                    "*/*/manifest.json", "*/*review*.json", "*/*corrections*.json"):
        paths.update(history.glob(pattern))
    excluded, provenance = set(), {}
    for path in sorted(paths):
        data = json.loads(path.read_text())
        found = set(image_names(data)) & set(names)
        if found:
            excluded.update(found)
            provenance[str(path)] = {"sha256": sha256(path), "source_images": len(found)}
    listing = subprocess.check_output(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                                       args.mac_host, "ls /Users/ramsabavat/Downloads/sidewalk_label_test"], text=True)
    mac_images = {match + ".jpg" for match in re.findall(
        r"(\d{4}_\d{2}_\d{2}_run_\d+__photo_\d{8}_\d{6}_\d{6})", listing)} & set(names)
    if len(mac_images) < 10:
        raise ValueError("Expected at least the ten previous Mac pilot images")
    excluded.update(mac_images)
    if len(excluded) < 200:
        raise ValueError("Prior review inventory unexpectedly small")
    groups, old_times = defaultdict(list), defaultdict(list)
    for name in names:
        groups[name.split("__", 1)[0]].append(name)
    for name in excluded:
        insort(old_times[name.split("__", 1)[0]], timestamp(name))
    previous_hashes = []
    for name in sorted(excluded):
        with Image.open(source / name) as image:
            previous_hashes.append(dhash(image))
    limits, rng, chosen, hashes, rejected = quotas(groups, 200), random.Random(args.seed), [], list(previous_hashes), Counter()
    available, chosen_times, shortages = {}, {}, {}
    for run, items in sorted(groups.items()):
        candidates = [n for n in items if n not in excluded and not near_time(timestamp(n), old_times[run])]
        print(json.dumps({"run": run, "time_eligible": len(candidates), "quota": limits[run]}), flush=True)
        rng.shuffle(candidates)
        available[run] = candidates
        times, selected = [], []
        for name in candidates:
            if len(selected) == limits[run]:
                break
            value = timestamp(name)
            if near_time(value, times):
                rejected["within_new_sample_time_guard"] += 1
                continue
            with Image.open(source / name) as image:
                descriptor, size = dhash(image), list(image.size)
            if any((descriptor ^ old).bit_count() <= HASH_DISTANCE for old in hashes):
                rejected["perceptual_near_duplicate"] += 1
                continue
            selected.append({"image": name, "source_sha256": sha256(source / name), "size": size,
                             "dhash64": f"{descriptor:016x}"})
            hashes.append(descriptor)
            insort(times, value)
        if len(selected) != limits[run]:
            shortages[run] = limits[run] - len(selected)
        chosen.extend(selected)
        chosen_times[run] = times
    # Preserve duplicate guards; redistribute exhausted-run slots, not near-duplicates.
    chosen_names = {f["image"] for f in chosen}
    for run in sorted(groups, key=lambda r: (-len(groups[r]), r)):
        for name in available[run]:
            if len(chosen) == 200:
                break
            if name in chosen_names or near_time(timestamp(name), chosen_times[run]):
                continue
            with Image.open(source / name) as image:
                descriptor, size = dhash(image), list(image.size)
            if any((descriptor ^ old).bit_count() <= HASH_DISTANCE for old in hashes):
                continue
            chosen.append({"image": name, "source_sha256": sha256(source / name), "size": size,
                           "dhash64": f"{descriptor:016x}"})
            chosen_names.add(name)
            hashes.append(descriptor)
            insort(chosen_times[run], timestamp(name))
    if len(chosen) != 200:
        raise ValueError("Cannot fill 200 without relaxing duplicate guards")
    rng.shuffle(chosen)
    args.output.mkdir(parents=True)
    exclusions = {"created_utc": utc_now(), "images": sorted(excluded), "prior_records": provenance,
                  "mac_images": sorted(mac_images), "mac_listing": listing}
    write_json(args.output / "exclusions.json", exclusions)
    selection = {"kind": "paired-class1-review-selection-v1", "created_utc": utc_now(),
                 "source": str(source), "source_count": len(names), "source_names_sha256": digest_json(names),
                 "steering_labels_sha256": sha256(source / "labels.json"), "seed": args.seed,
                 "images": [f["image"] for f in chosen], "frames": chosen,
                 "sample_runs": dict(Counter(f["image"].split("__", 1)[0] for f in chosen)),
                 "original_quotas": limits, "exhausted_run_shortages": shortages,
                 "prior_images_excluded": len(excluded), "guard_seconds": GUARD_SECONDS,
                 "dhash64_max_excluded_distance": HASH_DISTANCE, "rejections": dict(rejected),
                 "exclusions_sha256": sha256(args.output / "exclusions.json"), "runner_sha256": sha256(Path(__file__)),
                 "sampling": "Proportional original-run quotas; seeded candidate permutation; temporal/dHash rejection. Exhausted-run slots go to eligible runs in descending source size, with the same guards. Shuffled review order.",
                 "limits": "A fresh, duplicate-reduced development review, not an IID dataset accuracy estimate. Perceptual/time guards cannot exclude all semantically similar scenes."}
    write_json(args.output / "selection.json", selection)
    sides = [False] * 100 + [True] * 100
    rng.shuffle(sides)
    mapping = {f"pair-{i:03d}": {"image": f["image"], "A": "sam3" if swap else "gsam2",
                               "B": "gsam2" if swap else "sam3"}
               for i, (f, swap) in enumerate(zip(chosen, sides), 1)}
    write_json(args.output / "private-assignment.json", {"selection_sha256": sha256(args.output / "selection.json"), "pairs": mapping})
    print(json.dumps({"sample_runs": selection["sample_runs"], "excluded": len(excluded), "rejections": dict(rejected), "redistributed": shortages}, indent=2))


if __name__ == "__main__":
    main()
