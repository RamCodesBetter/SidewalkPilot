#!/usr/bin/env python3
"""Select a fresh, balanced pilot and contact sheets for explicit point annotation."""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import random

from PIL import Image, ImageDraw

from label_grounded_sam2 import DEFAULT_SOURCE, digest_json, sha256, utc_now, write_json


def frame_time(name):
    return datetime.strptime(name.split("__photo_", 1)[1].removesuffix(".jpg"), "%Y%m%d_%H%M%S_%f").timestamp()


def fresh_selection(names, excluded, per_run=40, seed=20261025, gap_seconds=2):
    if type(per_run) is not int or per_run < 1 or gap_seconds < 0 or not names or len(set(names)) != len(names):
        raise ValueError("Require unique source names, a positive per-run quota, and nonnegative spacing")
    groups, old_times = defaultdict(list), defaultdict(list)
    for name in sorted(names):
        groups[name.split("__", 1)[0]].append(name)
    for name in excluded:
        old_times[name.split("__", 1)[0]].append(frame_time(name))
    for values in old_times.values():
        values.sort()
    rng = random.Random(seed)
    selected = []
    for run, frames in sorted(groups.items()):
        previous = old_times[run]
        eligible = []
        for name in frames:
            value = frame_time(name)
            i = bisect_left(previous, value)
            if not any(abs(value - v) <= gap_seconds for v in previous[max(0, i-1):i+1]):
                eligible.append(name)
        if len(eligible) < per_run:
            raise ValueError(f"Not enough fresh images in {run}")
        chosen_times = []
        for index in range(per_run):
            candidates = eligible[index * len(eligible) // per_run:(index + 1) * len(eligible) // per_run]
            rng.shuffle(candidates)
            choice = next((n for n in candidates if all(abs(frame_time(n) - t) > gap_seconds for t in chosen_times)), None)
            if choice is None:
                raise ValueError(f"Cannot satisfy spacing in temporal bin {run}/{index}")
            selected.append(choice)
            chosen_times.append(frame_time(choice))
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--prior-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    names = sorted(p.name for p in source.glob("*.jpg"))
    if set(names) != set(json.loads((source / "labels.json").read_text())):
        raise ValueError("JPEGs and original steering labels differ")
    excluded, manifests = set(), {}
    for path in sorted(args.prior_root.glob("series5-*/manifest.json")):
        excluded.update(json.loads(path.read_text())["images"])
        manifests[str(path)] = sha256(path)
    selected = fresh_selection(names, excluded)
    if len(selected) != 200 or len(set(selected)) != 200 or set(selected) & excluded:
        raise ValueError("Expected 200 new images from five runs")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "sheets").mkdir()
    selection = {"created_utc": utc_now(), "source": str(source), "source_count": len(names),
                 "source_names_sha256": digest_json(names), "steering_labels_sha256": sha256(source / "labels.json"),
                 "images": selected, "source_sha256": {n: sha256(source / n) for n in selected},
                 "sampling": "40 frames per recording run; seeded temporal-bin selection; >2 seconds from prior used frames and other selected frames within a run",
                 "seed": 20261025, "excluded_manifest_sha256": manifests, "excluded_names": sorted(excluded),
                 "gap_seconds": 2, "purpose": "Fresh balanced assisted class-1 pilot; same recording runs, not an independent environment or automatic-performance test",
                 "annotation_coordinates": "Integer normalized coordinates from 0 to 1000 on each image; x horizontal, y vertical",
                 "annotation_author": "AI assistant after inspecting source contact sheets; human review remains required"}
    write_json(args.output / "selection.json", selection)
    for start in range(0, len(selected), 8):
        sheet = Image.new("RGB", (1280, 1568), "white")
        draw = ImageDraw.Draw(sheet)
        for offset, name in enumerate(selected[start:start+8]):
            x, y = (offset % 2) * 640, (offset // 2) * 392
            with Image.open(source / name) as raw:
                preview = raw.convert("RGB").resize((640, 360))
            sheet.paste(preview, (x, y+32))
            draw.text((x+8, y+5), f"{start+offset+1:03d}  {name}", fill="black")
            for fraction in (.25, .5, .75):
                px, py = x + round(640*fraction), y+32+round(360*fraction)
                draw.line((px, y+32, px, y+391), fill=(180,180,180), width=1)
                draw.line((x, py, x+639, py), fill=(180,180,180), width=1)
        sheet.save(args.output / "sheets" / f"{start//8+1:02d}.jpg", quality=95)
    print(json.dumps({"images": len(selected), "excluded_prior_images": len(excluded), "output": str(args.output)}))


if __name__ == "__main__":
    main()
