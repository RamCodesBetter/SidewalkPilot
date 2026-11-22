#!/usr/bin/env python3
"""Validate and unblind an exported paired review; never promote masks automatically."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path


def score(manifest, mapping, review):
    if (review.get("kind") != "sidewalkpilot-paired-review-v1" or review.get("package_id") != manifest["package_id"]
            or review.get("selection_sha256") != manifest["selection_sha256"]
            or mapping["selection_sha256"] != manifest["selection_sha256"]
            or review.get("review_scope") != {"kind": "class", "class_ids": [1]}):
        raise ValueError("Package, selection or scope differs")
    decisions = review.get("decisions")
    if not isinstance(decisions, dict):
        raise ValueError("Invalid decisions")
    pairs = {p["id"]: p for p in manifest["pairs"]}
    if not pairs or len(pairs) != len(manifest["pairs"]):
        raise ValueError("Expected distinct review pairs")
    if mapping.get("package_id", manifest["package_id"]) != manifest["package_id"]:
        raise ValueError("Mapping belongs to another package")
    if set(decisions) - set(pairs):
        raise ValueError("Unknown review pairs")
    method_names = mapping.get("method_names", ["gsam2", "sam3"])
    if (not isinstance(method_names, list) or len(method_names) != 2
            or any(not isinstance(n, str) or not n for n in method_names) or len(set(method_names)) != 2):
        raise ValueError("Expected two distinct method identities")
    models = {name: Counter() for name in method_names}
    efforts = {name: Counter() for name in models}
    levels = {name: Counter() for name in models}
    timing = review.get("inspection_active_seconds", {})
    if not isinstance(timing, dict) or set(timing) - set(pairs):
        raise ValueError("Invalid timing identities")
    measured = {name: 0. for name in models}
    complete_pairs, concordance = 0, Counter()
    for key, pair in pairs.items():
        assignment = mapping["pairs"][key]
        if assignment["image"] != pair["source_name"] or sorted(assignment[s] for s in ("A", "B")) != sorted(models):
            raise ValueError("Private assignment does not match the pair")
        sides = decisions.get(key, {})
        if not isinstance(sides, dict) or set(sides) - {"A", "B"}:
            raise ValueError("Invalid side")
        actual = {}
        times = timing.get(key, {})
        if not isinstance(times, dict) or set(times) - {"A", "B"}:
            raise ValueError("Invalid timing sides")
        for side in ("A", "B"):
            record = sides.get(side)
            if record is None:
                state, effort = "unreviewed", "not_estimated"
                level = None
            else:
                if (record.get("mask_sha256") != pair["candidates"][side]["mask_sha256"]
                        or record.get("decision") not in ("unreviewed", "correct", "needs_correction", "uncertain")
                        or record.get("effort") not in ("not_estimated", "none", "minor", "major")
                        or not isinstance(record.get("notes"), str)):
                    raise ValueError("Invalid decision, notes, effort or mask identity")
                state, effort = record["decision"], record["effort"]
                level = record.get("correction_level")
                if level is not None and (state != 'needs_correction' or type(level) is not int or level not in (1, 2, 3)):
                    raise ValueError('Invalid correction level')
            model = assignment[side]
            seconds = times.get(side, 0.)
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError("Invalid inspection time")
            measured[model] += seconds
            models[model][state] += 1
            efforts[model][effort] += 1
            if state == 'needs_correction':
                levels[model][{1:'minor', 2:'moderate', 3:'major'}.get(level, 'not_specified')] += 1
            actual[model] = state
        if "unreviewed" not in actual.values():
            complete_pairs += 1
            concordance[','.join(f'{name}={actual[name]}' for name in method_names)] += 1
    count = len(pairs)
    return {"package_id": manifest["package_id"], "pairs": count, "complete_pairs": complete_pairs,
            "complete": complete_pairs == count,
            "methods": {name: {"counts": dict(values), "marked_correct_fraction_of_all_images": values["correct"] / count,
                               "estimated_effort": dict(efforts[name]),
                               "correction_levels": dict(levels[name]),
                               "inspection_active_seconds": measured[name] if "inspection_active_seconds" in review else None} for name, values in models.items()},
            "paired_decisions": dict(concordance),
            "note": "Human class-1 acceptance, not pixel IoU. Partial reviews do not establish a final rate. Effort is estimated; optional focused browser inspection time is not correction time. No masks are promoted."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "mapping", "review"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(score(*(json.loads(getattr(args, k).read_text()) for k in ("manifest", "mapping", "review"))), indent=2))


if __name__ == "__main__":
    main()
