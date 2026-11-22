#!/usr/bin/env python3
"""Freeze a uniform random image sample for named, three-method comparison."""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import shutil

from PIL import Image

from label_grounded_sam2 import DEFAULT_SOURCE, digest_json, sha256, utc_now, write_json


def random_names(names, count, seed):
    if not 0 < count <= min(len(names), 200) or len(set(names)) != len(names):
        raise ValueError("Expected unique source names and 1-200 selected images")
    return random.Random(seed).sample(sorted(names), count)


def validate_random_selection(path):
    value = json.loads(path.read_text())
    if value.get("kind") != "random-class1-comparison-v1":
        raise ValueError("Not a random comparison selection")
    source = Path(value["source"])
    names = sorted(p.name for p in source.glob("*.jpg"))
    if (value["images"] != random_names(names, value["count"], value["seed"])
            or len(names) != value["source_count"] or digest_json(names) != value["source_names_sha256"]
            or sha256(source / "labels.json") != value["steering_labels_sha256"]
            or [f["image"] for f in value["frames"]] != value["images"]):
        raise ValueError("Random selection or source inventory changed")
    for frame in value["frames"]:
        if sha256(source / frame["image"]) != frame["source_sha256"]:
            raise ValueError("Source image changed")
        with Image.open(source / frame["image"]) as image:
            if list(image.size) != frame["size"]:
                raise ValueError("Source dimensions changed")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.output.resolve()
    if out.exists() or source == out or source in out.parents or out in source.parents:
        raise ValueError("Use a new output directory outside the dataset")
    names = sorted(p.name for p in source.glob("*.jpg"))
    if set(names) != set(json.loads((source / "labels.json").read_text())):
        raise ValueError("Source inventory differs from steering-label keys")
    selected = random_names(names, args.count, args.seed)
    out.mkdir(parents=True)
    (out / "images").mkdir()
    frames = []
    for number, name in enumerate(selected, 1):
        with Image.open(source / name) as image:
            size = list(image.size)
        relative = f"images/{number:02d}.jpg"
        shutil.copy2(source / name, out / relative)
        frames.append({"image": name, "source_sha256": sha256(source / name), "size": size, "preview": relative})
    value = {"kind": "random-class1-comparison-v1", "created_utc": utc_now(), "count": args.count, "seed": args.seed,
             "source": str(source), "source_count": len(names), "source_names_sha256": digest_json(names),
             "steering_labels_sha256": sha256(source / "labels.json"), "images": selected, "frames": frames,
             "sampling": "Uniform random sample without replacement from sorted full source inventory; no exclusions, balancing, filtering or reselection after inspection.",
             "sample_runs": dict(Counter(n.split("__")[0] for n in selected)),
             "scope": "Class-1 method comparison; temporal neighbors may occur. AI-authored polygons are unverified annotations, not independent ground truth."}
    write_json(out / "selection.json", value)
    validate_random_selection(out / "selection.json")
    print(json.dumps({"selection": str(out / "selection.json"), "count": len(selected), "sample_runs": value["sample_runs"]}, indent=2))


if __name__ == "__main__":
    main()
