"""Build a reproducible diagnostic queue without changing any screening decision."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random


def build(history, seed=20261124):
    full = history / "series5-df-screen"
    progress = json.loads((full / "progress.json").read_text())
    if progress["unscreened"] or progress["state"] != "requires_repair":
        raise ValueError("Full screening is not complete")
    groups = defaultdict(list)
    seen = set()
    for root, identity in [(history / "strict-pass-10000", json.loads(
            (history / "strict-pass-10000/policy.json").read_text())["identity"]),
            (full, progress["identity"])]:
        for path in sorted((root / "loops").glob("*.json")):
            receipt = json.loads(path.read_text())
            if receipt["identity"] != identity:
                raise ValueError(f"Incompatible receipt: {path}")
            for row in receipt["records"]:
                if row["id"] in seen or row["status"] not in ("candidate", "deferred"):
                    raise ValueError("Duplicate or unrecognized screening decision")
                seen.add(row["id"])
                if row["status"] == "deferred":
                    groups[tuple(sorted(row["reasons"]))].append(row)
    if sum(map(len, groups.values())) != progress["needs_repair"] or len(seen) != progress["unique"]:
        raise ValueError("Receipt totals disagree with screen progress")
    rng = random.Random(seed)
    samples = {}
    for key, records in sorted(groups.items()):
        rows = sorted(records, key=lambda r:r["id"])
        rng.shuffle(rows)
        samples[key] = iter(rows)
    pilot = []
    while len(pilot) < min(30, progress["needs_repair"]):
        for it in samples.values():
            row = next(it, None)
            if row and len(pilot) < 30:
                pilot.append(row)
    return dict(stage="diagnosis_only", seed=seed, screening_identity=progress["identity"],
                reason_groups={" + ".join(k):len(v) for k,v in sorted(groups.items())},
                sample=pilot)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build(args.history)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
