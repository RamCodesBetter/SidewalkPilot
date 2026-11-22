#!/usr/bin/env python3
"""Export the reconciled class-1 inventory without inventing negative labels."""

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

import numpy as np
from PIL import Image

from evaluate_class1_corrections import decode_runs, safe_file
from label_grounded_sam2 import sha256, utc_now, write_json


POLICY = {
    "labels": {"0": "reviewed non-sidewalk", "1": "reviewed sidewalk", "255": "ignore"},
    "selection": "Prefer usable binary references, then usable class-1 proposals; newest accepted version within each tier.",
    "binary_conversion": "Preserve explicit binary references, including uncertain 255 pixels.",
    "class1_only_conversion": "Keep class 1; map every other ID to ignore 255, not background.",
    "split_status": "unsplit-development-pool",
    "evaluation": "Previously reviewed/tuned examples, not an independent test set or a measured accuracy result.",
    "training": "Partial labels require ignore_index=255 and negative supervision from binary references; do not train on positive-only masks alone.",
    "grouping": "Recording-run IDs are provided; near-duplicate frames and route overlap need checking before splitting.",
    "full_12_class_labels": False,
}


def read_json(path):
    return json.loads(Path(path).read_text())


def pixel_hash(pixels):
    return hashlib.sha256(pixels.tobytes()).hexdigest()


def pixel_counts(pixels):
    values, counts = np.unique(pixels, return_counts=True)
    return {str(int(value)): int(count) for value, count in zip(values, counts)}


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Review timestamps must include a timezone")
    return parsed


def selection_key(candidate):
    if candidate["decision"] != "correct":
        raise ValueError("Inventory contains a candidate that is not accepted")
    binary = candidate["scope"] == "binary-class1-reference"
    if not binary and candidate["scope"] != "class-1-only":
        raise ValueError("Unknown review scope")
    counts = candidate["pixel_counts"]
    usable = counts.get("1", 0) > 0 or (binary and counts.get("0", 0) > 0)
    return (usable, binary, timestamp(candidate["timestamp"]), candidate["mask_identity"])


def select_candidate(row):
    candidates = row["candidates"]
    if not candidates or len(candidates) != row["accepted_mask_versions"]:
        raise ValueError("Missing or inconsistent accepted candidates")
    for candidate in candidates:
        if any(candidate[key] != row[key] for key in ("source_sha256", "source_name")):
            raise ValueError("Candidate belongs to another source")
        selection_key(candidate)
    return max(candidates, key=selection_key)


def binary_labels(pixels, scope):
    if pixels.dtype != np.uint8 or pixels.ndim != 2:
        raise ValueError("Expected a 2D uint8 label mask")
    if scope == "binary-class1-reference":
        if not np.isin(pixels, (0, 1, 255)).all():
            raise ValueError("Binary reference has non-binary IDs")
        return pixels.copy(), "binary-reference"
    if scope != "class-1-only" or not np.isin(pixels, (*range(12), 255)).all():
        raise ValueError("Invalid class-1 proposal")
    return np.where(pixels == 1, 1, 255).astype(np.uint8), "sidewalk-positive-only"


class Inputs:
    def __init__(self, output):
        self.output = output
        self.hashes = {}

    def verify(self, path, expected=None):
        path = Path(path).resolve(strict=True)
        if path.is_relative_to(self.output):
            raise ValueError("Output overlaps an input")
        digest = sha256(path)
        if expected is not None and digest != expected:
            raise ValueError(f"Input SHA-256 mismatch: {path}")
        if path in self.hashes and digest != self.hashes[path]:
            raise ValueError(f"Input changed while exporting: {path}")
        self.hashes[path] = digest
        return path

    def recheck(self):
        for path, digest in list(self.hashes.items()):
            self.verify(path, digest)


def candidate_pixels(candidate, inputs):
    source = inputs.verify(candidate["source_path"], candidate["source_sha256"])
    with Image.open(source) as image:
        if list(image.size) != candidate["size"]:
            raise ValueError("Source dimensions changed")
    evidence = inputs.verify(candidate["evidence_path"], candidate["evidence_sha256"])
    if candidate["mask_path"] is not None:
        path = inputs.verify(candidate["mask_path"], candidate["mask_sha256"])
        if candidate["mask_identity"] != "file:" + candidate["mask_sha256"]:
            raise ValueError("Mask file identity mismatch")
        with Image.open(path) as image:
            pixels = np.array(image)
    else:
        export = read_json(evidence)
        if (export.get("schema") != "sidewalkpilot-class1-corrections-v1"
                or export.get("dataset_key") != candidate["package_id"]
                or export.get("annotation_scope") != {
                    "kind": "binary_class_reference", "positive_class_id": 1, "not_a_12_class_mask": True}):
            raise ValueError("Wrong correction export identity/scope")
        matches = [entry for entry in export["entries"]
                   if entry.get("source_sha256") == candidate["source_sha256"]
                   and entry.get("image") == candidate["source_name"]]
        if len(matches) != 1:
            raise ValueError("Expected exactly one matching correction")
        entry = matches[0]
        if (entry["status"] != "reviewed" or entry["size"] != candidate["size"]
                or entry["pixels_sha256"] != candidate["pixels_sha256"]
                or timestamp(entry["updated_utc"]) != timestamp(candidate["timestamp"])
                or candidate["scope"] != "binary-class1-reference"
                or candidate["mask_identity"] != "pixels:" + candidate["pixels_sha256"]):
            raise ValueError("Correction is not the accepted reviewed version")
        pixels = decode_runs(entry["pixels_rle"], tuple(reversed(candidate["size"])))
    if (pixels.dtype != np.uint8 or pixels.shape != tuple(reversed(candidate["size"]))
            or pixel_hash(pixels) != candidate["pixels_sha256"]
            or pixel_counts(pixels) != candidate["pixel_counts"]):
        raise ValueError("Accepted mask pixels/dimensions/counts changed")
    return pixels


def summarize(records):
    included = [row for row in records if row["included"]]
    return {
        "inventoried_images": len(records),
        "usable_images": len(included),
        "excluded_all_ignore": len(records) - len(included),
        "supervision": dict(sorted(Counter(row["supervision"] for row in included).items())),
        "binary_references_with_ignore": sum(row["supervision"] == "binary-reference"
                                             and row["pixel_counts"].get("255", 0) > 0 for row in included),
        "recording_runs": dict(sorted(Counter(row["recording_run"] for row in included).items())),
    }


def verify_dataset(root):
    root = Path(root).resolve(strict=True)
    expected = read_json(root / "checksums.json")
    actual_files = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    if actual_files != set(expected) | {"checksums.json"}:
        raise ValueError("Dataset file set differs from receipt")
    for relative, digest in expected.items():
        if sha256(safe_file(root, relative)) != digest:
            raise ValueError(f"Dataset checksum mismatch: {relative}")
    manifest = read_json(root / "manifest.json")
    if manifest["policy"] != POLICY:
        raise ValueError("Unknown dataset policy")
    records = manifest["records"]
    if len({row["source_sha256"] for row in records}) != len(records):
        raise ValueError("Duplicate source image")
    for row in records:
        source = safe_file(root, row["image"])
        mask = safe_file(root, row["mask"])
        if sha256(source) != row["source_sha256"] or sha256(mask) != row["mask_sha256"]:
            raise ValueError("Asset identity mismatch")
        with Image.open(source) as image:
            if list(image.size) != row["size"]:
                raise ValueError("Image dimensions changed")
        with Image.open(mask) as image:
            pixels = np.array(image)
        if (pixels.dtype != np.uint8 or pixels.shape != tuple(reversed(row["size"]))
                or not np.isin(pixels, (0, 1, 255)).all()
                or pixel_hash(pixels) != row["pixels_sha256"]
                or pixel_counts(pixels) != row["pixel_counts"]
                or bool(np.any(pixels != 255)) != row["included"]):
            raise ValueError("Exported supervision mismatch")
        if row["supervision"] == "sidewalk-positive-only" and np.any(pixels == 0):
            raise ValueError("Partial mask contains invented negatives")
    expected_ids = {"usable": [row["id"] for row in records if row["included"]],
                    "excluded": [row["id"] for row in records if not row["included"]]}
    if read_json(root / "index.json") != expected_ids or summarize(records) != manifest["summary"]:
        raise ValueError("Dataset index or summary mismatch")
    return manifest["summary"]


def prepare(inventory_path, output):
    inventory_path, output = Path(inventory_path).resolve(strict=True), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {output}")
    inputs = Inputs(output)
    inputs.verify(inventory_path)
    inventory = read_json(inventory_path)
    images = sorted(inventory["images"], key=lambda row: row["source_name"])
    if (not images or len({row["source_sha256"] for row in images}) != len(images)
            or len({row["source_name"] for row in images}) != len(images)
            or inventory["summary"]["unique_accepted_images"] != len(images)):
        raise ValueError("Empty, duplicate, or inconsistent inventory")
    selected, evidence_files = [], {}
    for row in images:
        selected.append((row, select_candidate(row)))
        for candidate in row["candidates"]:
            history = [{"path": candidate["evidence_path"], "sha256": candidate["evidence_sha256"]},
                       *candidate.get("evidence_history", [])]
            for evidence in history:
                path = inputs.verify(evidence["path"], evidence["sha256"])
                evidence_files[evidence["sha256"]] = path
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=output.name + ".building-", dir=output.parent) as temporary:
        staging = Path(temporary) / "dataset"
        for folder in ("images", "masks", "excluded/images", "excluded/masks", "provenance/evidence"):
            (staging / folder).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(inventory_path, staging / "provenance/inventory.json")
        for digest, path in evidence_files.items():
            shutil.copyfile(path, staging / "provenance/evidence" / (digest + ".json"))
        records = []
        for row, candidate in selected:
            match = re.fullmatch(r"(\d{4}_\d{2}_\d{2}_run_\d+)__photo_(\d{8}_\d{6}_\d{6})\.(?:jpg|jpeg|png)",
                                 row["source_name"], re.IGNORECASE)
            if match is None:
                raise ValueError(f"Cannot identify recording run: {row['source_name']}")
            pixels = candidate_pixels(candidate, inputs)
            labels, supervision = binary_labels(pixels, candidate["scope"])
            included = bool(np.any(labels != 255))
            prefix = "" if included else "excluded/"
            image_relative = prefix + "images/" + row["source_name"]
            mask_relative = prefix + "masks/" + Path(row["source_name"]).with_suffix(".png").name
            shutil.copyfile(candidate["source_path"], staging / image_relative)
            Image.fromarray(labels).save(staging / mask_relative)
            records.append({
                "id": row["source_sha256"], "source_sha256": row["source_sha256"],
                "source_name": row["source_name"], "recording_run": match[1], "frame_timestamp": match[2],
                "image": image_relative, "mask": mask_relative, "size": candidate["size"],
                "mask_sha256": sha256(staging / mask_relative), "pixels_sha256": pixel_hash(labels),
                "pixel_counts": pixel_counts(labels), "supervision": supervision, "included": included,
                "exclusion_reason": None if included else "all-ignore: no supervised pixels",
                "pixels_changed_to_ignore": int(np.count_nonzero((pixels != 255) & (labels == 255))),
                "accepted_candidate_count": len(row["candidates"]), "selected_candidate": candidate,
                "archived_evidence": "provenance/evidence/" + candidate["evidence_sha256"] + ".json",
            })
        inputs.recheck()
        manifest = {"schema": "sidewalkpilot-reviewed-class1-pool-v1", "created_utc": utc_now(),
                    "inventory_path": str(inventory_path), "inventory_sha256": inputs.hashes[inventory_path],
                    "exporter_sha256": sha256(Path(__file__)), "policy": POLICY,
                    "summary": summarize(records), "records": records}
        write_json(staging / "manifest.json", manifest)
        write_json(staging / "index.json", {
            "usable": [row["id"] for row in records if row["included"]],
            "excluded": [row["id"] for row in records if not row["included"]]})
        write_json(staging / "provenance/input-integrity.json", {
            "all_verified_unchanged": True, "files": {str(path): digest for path, digest in inputs.hashes.items()}})
        (staging / "READ-ME.txt").write_text(
            "SidewalkPilot reviewed class-1 development pool\n\n"
            + json.dumps(manifest["summary"], indent=2) + "\n\n"
            + "\n".join(f"{key}: {value}" for key, value in POLICY.items())
            + "\n\nUse manifest.json and index.json, not a recursive glob. Excluded all-ignore examples are archived separately.\n"
            + "No train/validation/test partition has been assigned, no model has been trained, and nothing has been uploaded.\n"
            + "Original files are unchanged. provenance/inventory.json retains all accepted alternatives and their evidence.\n")
        write_json(staging / "checksums.json", {
            str(path.relative_to(staging)): sha256(path) for path in sorted(staging.rglob("*")) if path.is_file()})
        verify_dataset(staging)
        if output.exists():
            raise FileExistsError(f"Output appeared during export: {output}")
        staging.rename(output)
    return manifest["summary"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--inventory", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("dataset", type=Path)
    args = parser.parse_args()
    result = prepare(args.inventory, args.output) if args.command == "build" else verify_dataset(args.dataset)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
