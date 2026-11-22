#!/usr/bin/env python3
"""Package frozen GSAM 2 proposals for targeted pixel correction, without inference."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from label_grounded_sam2 import sha256, utc_now, verify_record, write_json
from score_paired_review import score

HERE = Path(__file__).resolve().parent
FAILURES = (1, 3, 44, 56, 58, 91, 118, 151, 159, 179, 193, 200)
CONTROL_SEED = "20261029"


def select_rows(rows):
    by_id = {r["pair"]: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError("Duplicate pairs")
    failures = [by_id[f"pair-{number:03d}"] for number in FAILURES]
    if any(r["gsam2_decision"] != "needs_correction" for r in failures):
        raise ValueError("Selected failure no longer matches the recorded review")
    controls = []
    for run in sorted({r["image"].split("__")[0] for r in rows}):
        eligible = [r for r in rows if r["image"].startswith(run + "__")
                    and r["group"] == "both_correct"
                    and r["gsam2_effort"] == r["sam3_effort"] == "none"]
        if not eligible:
            raise ValueError(f"No accepted no-effort control for {run}")
        controls.append(min(eligible, key=lambda r: hashlib.sha256((CONTROL_SEED + "|" + r["image"]).encode()).hexdigest()))
    return [("failure", r) for r in failures] + [("control", r) for r in controls]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inspection", "review", "mapping", "paired-package", "gsam2", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    hashes = {}

    def read(path):
        hashes[str(path)] = sha256(path)
        return json.loads(path.read_text())

    inspection = read(args.inspection)
    review = read(args.review)
    mapping = read(args.mapping)
    paired = read(args.paired_package / "manifest.json")
    result = score(paired, mapping, review)
    if not result["complete"] or inspection["review_score"] != result:
        raise ValueError("Inspection and completed review differ")
    for path, expected in inspection["input_sha256"].items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"Inspection source changed: {path}")
    paired_by_id = {p["id"]: p for p in paired["pairs"]}
    for row in inspection["rows"]:
        pair = paired_by_id[row["pair"]]
        if pair["source_name"] != row["image"]:
            raise ValueError("Inspection image differs")
        for side in ("A", "B"):
            method = mapping["pairs"][pair["id"]][side]
            decision = review["decisions"][pair["id"]][side]
            if any(row[method + "_" + field] != decision[field] for field in ("decision", "effort")):
                raise ValueError("Inspection decisions differ")
    chosen = select_rows(inspection["rows"])
    if len(chosen) != 17:
        raise ValueError("Expected 12 failure cases and five recording-run controls")
    original = read(args.gsam2 / "manifest.json")
    source = Path(original["contract"]["source"])
    out = args.output.resolve()
    roots = [source.resolve(), args.gsam2.resolve(), args.paired_package.resolve(), args.inspection.parent.resolve()]
    if out.exists() or any(out == root or root in out.parents or out in root.parents for root in roots):
        raise ValueError("Use a new package directory separate from all inputs")
    if sha256(source / "labels.json") != original["contract"]["steering_labels_sha256"]:
        raise ValueError("Original steering labels changed")
    out.mkdir(parents=True)
    for folder in ("images", "masks", "overlays", "records", "review", "provenance"):
        (out / folder).mkdir()
    selected = []
    for position, (role, row) in enumerate(chosen, 1):
        name = row["image"]
        record_path = args.gsam2 / "records" / (Path(name).stem + ".json")
        record = read(record_path)
        verify_record(args.gsam2, record, source)
        pair = paired_by_id[row["pair"]]
        side = next(s for s in ("A", "B") if mapping["pairs"][row["pair"]][s] == "gsam2")
        if record["source_sha256"] != pair["source_sha256"] or record["mask_sha256"] != pair["candidates"][side]["mask_sha256"]:
            raise ValueError("GSAM 2 proposal differs from the reviewed candidate")
        shutil.copy2(source / name, out / "images" / name)
        shutil.copy2(record_path, out / "records" / record_path.name)
        for field in ("mask", "overlay"):
            shutil.copy2(args.gsam2 / record[field], out / record[field])
        verify_record(out, record, out / "images")
        selected.append({"position": position, "pair": row["pair"], "role": role, "image": name,
                         "record": record, "prior_image_rating": row["gsam2_decision"],
                         "prior_estimated_effort": row["gsam2_effort"], "reference_status": "not_created"})
    created = utc_now()
    contract = {k: original["contract"][k] for k in ("source", "source_count", "source_names_sha256", "steering_labels_sha256", "taxonomy")}
    config = {"method": "Copy unchanged reviewed GSAM 2 proposals into an isolated pixel-correction workspace",
              "new_inference": False, "parent_config": original["contract"]["config"],
              "parent_manifest_sha256": sha256(args.gsam2 / "manifest.json"),
              "reference_policy": "All references begin as drafts. Image-level acceptance does not certify pixels. 0 means non-sidewalk only in binary references; 255 means uncertain."}
    contract.update(count=len(selected), config=config, runner_file=Path(__file__).name, runner_sha256=sha256(Path(__file__)))
    manifest = {"created_utc": created, "contract": contract, "images": [r["image"] for r in selected],
                "annotation_scope": {"kind": "class", "class_ids": [1]}, "review_label": "Targeted pixel corrections",
                "sampling": "12 purposive failures plus one seeded, both-accepted/no-effort control per recording run; not held-out evaluation",
                "source_review_sha256": sha256(args.review), "new_inference": False}
    key = "sp-review:" + created + ":" + contract["source_names_sha256"]
    write_json(out / "manifest.json", manifest)
    write_json(out / "taxonomy.json", contract["taxonomy"])
    write_json(out / "label_config.json", config)
    write_json(out / "correction-selection.json", {"schema": "sidewalkpilot-correction-selection-v1", "dataset_key": key, "images": manifest["images"]})
    write_json(out / "selection.json", {"kind": "sidewalkpilot-targeted-corrections-v1", "dataset_key": key,
               "control_seed": CONTROL_SEED, "failures": 12, "controls": 5, "frames": selected,
               "source_review_sha256": sha256(args.review), "baseline_manifest_sha256": sha256(args.gsam2 / "manifest.json"),
               "reference_initialization": "Editor uses class-1 proposal pixels as 1 and other pixels as unverified 0 until checked; no reviewed pixel annotations are prefilled.",
               "bias_note": "References are proposal-seeded and may have anchoring bias. Not an independent held-out test."})
    write_json(out / "summary.json", {"completed_proposals": 17, "human_pixel_references": 0,
               "status": "Awaiting student pixel corrections and explicit Reference checked confirmation"})
    shutil.copy2(Path(__file__), out / Path(__file__).name)
    for name in ("manifest.json", "label_config.json", "label_grounded_sam2.py"):
        shutil.copy2(args.gsam2 / name, out / "provenance" / ("gsam2-" + name))
    shutil.copy2(args.review, out / "provenance" / "original-paired-review.json")
    for name in ("index.html", "corrections.js", "corrections.css", "lucide.min.js", "LUCIDE-LICENSE.txt"):
        shutil.copy2(HERE / "review" / name, out / "review" / name)
        shutil.copy2(HERE / "review" / name, out / name)
    shutil.copy2(HERE / "review_masks.py", out / "review_masks.py")
    (out / "READ-ME.txt").write_text("""SidewalkPilot: targeted pixel corrections

17 images: 12 selected failures followed by five accepted controls, one per run.
All starting masks are unchanged GSAM 2 proposals. They are NOT pixel references.
Existing reviews and earlier corrections are separate and have not been reset.

1. Open index.html in Chrome or Edge.
2. Use Open folder and choose THIS Targeted-corrections folder (not its parent).
   The browser reads local files; this does not upload the dataset anywhere.
3. Click the pencil icon (Edit class 1 mask).
4. Correct each mask. In edit mode, 1 paints sidewalk, 2 paints non-sidewalk,
   and 3 marks uncertain pixels. Use the brush or polygon, and zoom for edges.
   Enter closes an unfinished polygon, otherwise it moves to the next image.
5. Check Reference checked only after inspecting the complete image.
   Controls also need inspection; do not change a correct mask just to make edits.
6. Click Export corrections and keep sidewalkpilot-class-1-corrections.json.
   Export periodically. Browser drafts alone are not a transferred reference set.

Pixel convention:
- Include visible sidewalk through shadows and across a clear driveway crossing.
- Exclude adjoining road/driveway outside that sidewalk corridor, grass and visible
  occluding objects. Do not paint imagined pavement underneath an object.
- Use uncertain (255) where you cannot establish the boundary from the image.
- Non-sidewalk (0) is a binary-reference label here, not a 12-class background label.

Review decisions and pixel corrections use different export buttons. Send the
CORRECTIONS export, not another correct/needs-correction review.

selection.json records original pair IDs and failure/control provenance. This is
a development set, not held-out evaluation. No training or new inference occurred.
""", encoding="ascii")
    for path, expected in hashes.items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"Input changed: {path}")
    write_json(out / "integrity-check.json", {"dataset_key": key, "input_sha256": hashes,
               "files_sha256": {str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()},
               "source_and_proposal_pixels_unchanged": True, "no_preapproved_pixel_references": True})
    print(json.dumps({"output": str(out), "count": len(selected), "dataset_key": key,
                      "controls": [r["pair"] for r in selected if r["role"] == "control"]}, indent=2))


if __name__ == "__main__":
    main()
