#!/usr/bin/env python3
"""Build a portable, explicitly unreviewed pilot archive; never upload automatically."""

import argparse
import io
import json
from pathlib import Path
import tarfile

from label_grounded_sam2 import sha256, utc_now, verify_record

HERE = Path(__file__).resolve().parent


def safe_member(root, name):
    if not isinstance(name, str) or "\\" in name:
        raise ValueError("Invalid relative file name")
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Unsafe or missing file: {name}")
    return path


def package(dataset, destination, source=None):
    dataset, destination = dataset.resolve(), destination.resolve()
    if destination.exists():
        raise FileExistsError(f"Archive already exists: {destination}")
    manifest = json.loads((dataset / "manifest.json").read_text())
    source = (source or Path(manifest["contract"]["source"])).resolve()
    entries = {}
    runner = manifest["contract"].get("runner_file", "label_grounded_sam2.py")
    for name in ("manifest.json", "taxonomy.json", "label_config.json", "summary.json", runner):
        entries[name] = safe_member(dataset, name)
    for name in ("READ-ME.txt", "integrity-check.json", "visual-qa.json"):
        if (dataset / name).is_file():
            entries[name] = safe_member(dataset, name)
    comparison = dataset / "Before-after/comparison.json"
    if comparison.exists():
        report = json.loads(safe_member(dataset, "Before-after/comparison.json").read_text())
        if [row["image"] for row in report["images"]] != manifest["images"]:
            raise ValueError("Comparison must match the ordered package images")
        names = ["Before-after/comparison.json"]
        names += [f"Before-after/{i:02d}.jpg" for i in range(1, len(manifest["images"]) + 1)]
        names += [f"Before-after/sheet-{i}.jpg" for i in range(1, (len(manifest["images"]) + 3) // 4 + 1)]
        for name in names:
            entries[name] = safe_member(dataset, name)
    if sha256(entries[runner]) != manifest["contract"]["runner_sha256"]:
        raise ValueError("Archived runner does not match the generation manifest")
    for name, expected in manifest["contract"].get("helper_files_sha256", {}).items():
        entries[name] = safe_member(dataset, name)
        if sha256(entries[name]) != expected:
            raise ValueError("Archived helper does not match the generation manifest")
    if "selection_sha256" in manifest["contract"]:
        entries["selection.json"] = safe_member(dataset, "selection.json")
        if sha256(entries["selection.json"]) != manifest["contract"]["selection_sha256"]:
            raise ValueError("Diagnostic selection does not match the generation manifest")
    for name in manifest["images"]:
        if Path(name).name != name or not name.endswith(".jpg"):
            raise ValueError(f"Invalid image name: {name}")
        record_name = "records/" + Path(name).stem + ".json"
        record_file = safe_member(dataset, record_name)
        record = json.loads(record_file.read_text())
        if record["image"] != name:
            raise ValueError("Record/source identity mismatch")
        for field in ("mask", "overlay"):
            entries[record[field]] = safe_member(dataset, record[field])
        if "semantic_cue" in record:
            entries[record["semantic_cue"]] = safe_member(dataset, record["semantic_cue"])
            if sha256(entries[record["semantic_cue"]]) != record["semantic_cue_sha256"]:
                raise ValueError("Semantic cue changed since generation")
        entries["images/" + name] = safe_member(source, name)
        verify_record(dataset, record, source)
        entries[record_name] = record_file
    for name in ("review_masks.py", "review/index.html", "review/corrections.js", "review/corrections.css", "review/lucide.min.js", "review/LUCIDE-LICENSE.txt"):
        entries[name] = HERE / name
    information = {"kind": "unreviewed-development-pilot", "count": len(manifest["images"]),
                   "created_utc": utc_now(), "human_review_required": True,
                   "full_dataset": False, "source_pool_count": manifest["contract"]["source_count"],
                   "review_command": "python3 review_masks.py .",
                   "note": "Generated labels are not verified ground truth. See label_config.json for automatic or assisted provenance. No Hugging Face publication is performed by this packager.",
                   "files_sha256": {name: sha256(path) for name, path in entries.items()}}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("xb") as handle:
        with tarfile.open(fileobj=handle, mode="w") as archive:
            prefix = dataset.name
            def normalize(info):
                if not info.isfile():
                    raise ValueError("Archive accepts regular files only")
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                return info
            for name, path in sorted(entries.items()):
                archive.add(path, arcname=prefix + "/" + name, recursive=False, filter=normalize)
            data = (json.dumps(information, indent=2) + "\n").encode()
            info = tarfile.TarInfo(prefix + "/package.json")
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
    temporary.replace(destination)
    return {"archive": str(destination), "images": len(manifest["images"]),
            "bytes": destination.stat().st_size, "sha256": sha256(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.dataset, args.output, args.source), indent=2))


if __name__ == "__main__":
    main()
