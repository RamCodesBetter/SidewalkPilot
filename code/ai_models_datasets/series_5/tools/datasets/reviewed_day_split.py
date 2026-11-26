"""Create and verify recording-day splits for the reviewed 5.A development dataset."""
from pathlib import Path

from prepare_reviewed_dataset import read_json, verify_dataset
from label_grounded_sam2 import sha256, utc_now, write_json


PARTITIONS = ("train", "validation", "test")


def recording_day(row):
    return row["recording_run"].rsplit("_run_", 1)[0]


def validate_split(manifest, split, manifest_hash):
    if split.get("schema") != "sidewalkpilot-binary-day-split-v1" or split["manifest_sha256"] != manifest_hash:
        raise ValueError("Split does not belong to this dataset manifest")
    usable = {row["id"]: row for row in manifest["records"] if row["included"]}
    partitions, seen_ids, seen_days = {}, set(), set()
    for name in PARTITIONS:
        ids = split["partitions"][name]
        if not ids or len(set(ids)) != len(ids) or seen_ids.intersection(ids) or not set(ids) <= usable.keys():
            raise ValueError("Empty, duplicate, overlapping, or unknown split images")
        rows = [usable[identifier] for identifier in ids]
        days = {recording_day(row) for row in rows}
        if seen_days & days or days != set(split["days"][name]):
            raise ValueError("Recording day leaks across partitions or differs from declared days")
        references = [row for row in rows if row["supervision"] == "binary-reference"]
        if not references or any(sum(row["pixel_counts"].get(label, 0) for row in references) == 0 for label in ("0", "1")):
            raise ValueError("Every partition needs reviewed positive AND negative reference pixels")
        partitions[name] = rows
        seen_ids.update(ids)
        seen_days.update(days)
    if seen_ids != usable.keys():
        raise ValueError("Split does not cover all usable images")
    return partitions


def create_split(dataset, output, days):
    dataset, output = Path(dataset).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(dataset):
        raise ValueError("Use a new split file outside the verified dataset")
    verify_dataset(dataset)
    manifest = read_json(dataset / "manifest.json")
    split = {
        "schema": "sidewalkpilot-binary-day-split-v1", "created_utc": utc_now(),
        "manifest_sha256": sha256(dataset / "manifest.json"), "days": days,
        "partitions": {name: sorted(row["id"] for row in manifest["records"]
                                    if row["included"] and recording_day(row) in days[name]) for name in PARTITIONS},
        "purpose": "Development baseline only; not the submitted study's final 80/10/10 split.",
        "limitations": "Same-day runs stay together. Different days may revisit the same route; visual/geographic independence is not established. These labels were already reviewed during development.",
    }
    partitions = validate_split(manifest, split, split["manifest_sha256"])
    split["summary"] = {name: {"images": len(rows), "fraction": len(rows) / sum(map(len, partitions.values())),
                               "binary_references": sum(row["supervision"] == "binary-reference" for row in rows),
                               "recording_runs": sorted({row["recording_run"] for row in rows})}
                        for name, rows in partitions.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, split)
    return split["summary"]


def load_partition(dataset, split_path):
    verify_dataset(dataset)
    manifest, split = read_json(dataset / "manifest.json"), read_json(split_path)
    return validate_split(manifest, split, sha256(dataset / "manifest.json"))
