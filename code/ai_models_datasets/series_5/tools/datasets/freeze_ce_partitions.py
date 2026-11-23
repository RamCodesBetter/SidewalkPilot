"""Freeze C/E membership before annotation. Never invent missing reference masks."""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
import tempfile

import cv2
import numpy as np


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp(row):
    stem = Path(row["image"]).stem.split("photo_")[-1]
    return (datetime.strptime(stem, "%Y%m%d_%H%M%S_%f") - datetime(1970, 1, 1)).total_seconds()


def phash(path):
    gray = cv2.imread(str(path), cv2.IMREAD_REDUCED_GRAYSCALE_8)
    if gray is None:
        raise ValueError(f"Unreadable image: {path}")
    low = cv2.dct(cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype("float32"))[:8, :8]
    bits = low > np.median(low.ravel()[1:])
    return int.from_bytes(np.packbits(bits).tobytes(), "big")


class SimilarityIndex:
    """Within four changed bits, at least one of five disjoint chunks matches."""
    def __init__(self):
        self.bins = defaultdict(set)

    def keys(self, h):
        return [(i, (h >> (13*i)) & 8191) for i in range(5)]

    def add(self, h):
        for k in self.keys(h):
            self.bins[k].add(h)

    def near(self, h):
        return any((h ^ v).bit_count() <= 4 for k in self.keys(h) for v in self.bins.get(k, ()))


def freeze(root, dest, seed):
    if dest.exists():
        raise FileExistsError(dest)
    inv = read(root/"series5-5CD-labeling/manifest.json")
    archive = root/"strict-pass-10000"
    campaign = read(archive/"manifest.json")
    baseline = root/"reviewed-class1-dataset"
    old = read(root/"series5-5.A-training/split.json")
    known = {r["id"]: r for r in read(baseline/"manifest.json")["records"] if r["included"]}
    inventory = {r["id"]: r for r in inv["frames"]}
    src = Path(inv["source"])
    if src != Path(campaign["source"]):
        raise ValueError("Source roots differ")
    parts = {"train": [], "validation": [], "test": []}
    training_ids = set()
    overlaps = SimilarityIndex()
    def member(i, part, mask=None, mask_hash=None, kind=None):
        r = inventory[i]
        days = {a["day"] for a in r["aliases"]} | {r["day"]}
        if not days <= set(old["days"][part]) or digest(src/r["image"]) != i:
            raise ValueError(f"Group or source identity mismatch: {i}")
        if mask is not None and digest(mask) != mask_hash:
            raise ValueError(f"Mask identity mismatch: {i}")
        return dict(id=i, image=r["image"], recording_run=r["recording_run"],
                    mask=str(mask) if mask else None, mask_sha256=mask_hash,
                    supervision=kind or "reference-pending")

    for r in campaign["records"]:
        parts["train"].append(member(r["id"], "train", archive/r["candidates"], r["mask_sha256"], "pseudo-binary"))
    for i in old["partitions"]["train"]:
        r = known[i]
        parts["train"].append(member(i, "train", baseline/r["mask"], r["mask_sha256"], r["supervision"]))
    for r in parts["train"]:
        training_ids.add(r["id"])
        overlaps.add(phash(src/r["image"]))
    if len(campaign["records"]) != 10000 or len(training_ids) != len(parts["train"]):
        raise ValueError("Expected 10,000 original candidates and no duplicate training IDs")
    target = round(len(training_ids)/8)
    # Treat every photo packaged in a known review viewer as exposed, even if never opened.
    exposed = {i for ids in old["partitions"].values() for i in ids}
    exposed.update(r["id"] for r in inv["frames"] if r["existing_review"])
    for entry in root.rglob("index.html"):
        images = entry.parent/"images"
        if images.is_dir():
            exposed.update(digest(p) for p in images.iterdir() if p.suffix.lower() in {".jpg",".jpeg",".png"})
    seen_times = defaultdict(list)
    for i in exposed & inventory.keys():
        r = inventory[i]
        seen_times[r["recording_run"]].append(timestamp(r))
    for times in seen_times.values():
        times.sort()
    rng = random.Random(seed)
    excluded = Counter()
    for part in ("validation", "test"):
        pool = [r for r in inv["frames"] if r["day"] in old["days"][part]
                and all(a["day"] in old["days"][part] for a in r["aliases"])]
        rng.shuffle(pool)
        old_val = set(old["partitions"]["validation"])
        if part == "validation":
            pool.sort(key=lambda r: r["id"] not in old_val)
        else:
            for i in exposed & inventory.keys():
                if inventory[i]["day"] in old["days"]["test"]:
                    overlaps.add(phash(src/inventory[i]["image"]))
        hashes = []
        for r in pool:
            i = r["id"]
            if part == "test":
                t = timestamp(r)
                times = seen_times[r["recording_run"]]
                pos = bisect_left(times, t-3)
                if i in exposed or (pos < len(times) and times[pos] <= t+3):
                    excluded["known_exposure_or_neighbour"] += 1
                    continue
            h = phash(src/r["image"])
            if overlaps.near(h):
                excluded[part+"_perceptual_neighbour"] += 1
                continue
            label = known.get(i) if part == "validation" else None
            parts[part].append(member(i,part,baseline/label["mask"],label["mask_sha256"],label["supervision"])
                               if label else member(i,part))
            hashes.append(h)
            if len(hashes) == target:
                break
        if len(hashes) != target:
            raise ValueError(f"Not enough eligible {part} images")
        for h in hashes:
            overlaps.add(h)
    counts = {k:len(v) for k,v in parts.items()}
    assert len({r["id"] for rows in parts.values() for r in rows}) == sum(counts.values())
    summary = dict(counts=counts, seed=seed, days=old["days"], source=str(src),
                   exclusions=dict(excluded), known_exposed_ids=len(exposed),
                   references={p:dict(Counter(r["supervision"] for r in v)) for p,v in parts.items()},
                   policy="Separate recording days and aliases; cross-partition 64-bit DCT pHash Hamming <=4 excluded. Known test exposures and +/-3s excluded. Not a guarantee of unseen geography. Null masks are pending, never background.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        out = Path(tmp)/"split"
        out.mkdir()
        summary["partition_sha256"] = {}
        for k,v in parts.items():
            path = out/(k+".json")
            path.write_text(json.dumps(v,indent=2)+"\n")
            summary["partition_sha256"][k] = digest(path)
        (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
        out.rename(dest)
    print(json.dumps(summary,indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("history",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--seed",type=int,default=20261122)
    args = p.parse_args()
    freeze(args.history.resolve(),args.output.resolve(),args.seed)
