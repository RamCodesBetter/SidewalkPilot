#!/usr/bin/env python3
"""Build an offline blinded A/B reviewer without publishing the private assignment."""

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from compare_sam3_sidewalk import output_path
from label_grounded_sam2 import digest_json, sha256, utc_now, verify_record, write_json
from prepare_paired_review import validate_selection

HERE = _workspace.TOOLS


def encode_binary(mask):
    flat = np.asarray(mask, dtype=np.uint8).ravel()
    if not len(flat) or not np.isin(flat, [0, 1]).all():
        raise ValueError("Binary mask required")
    changes = np.flatnonzero(flat[1:] != flat[:-1]) + 1
    return {"first": int(flat[0]), "lengths": np.diff(np.r_[0, changes, len(flat)]).tolist()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("selection", "mapping", "gsam2", "sam3", "output", "baseline-gsam2", "baseline-sam3"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    selection = validate_selection(args.selection)
    source = Path(selection["source"])
    mapping = json.loads(args.mapping.read_text())
    selection_hash = sha256(args.selection)
    if mapping["selection_sha256"] != selection_hash:
        raise ValueError("Assignment belongs to another selection")
    cfg2 = json.loads((args.gsam2 / "manifest.json").read_text())
    cfg3 = json.loads((args.sam3 / "config.json").read_text())
    base2 = json.loads((args.baseline_gsam2 / "manifest.json").read_text())["contract"]
    base3 = json.loads((args.baseline_sam3 / "config.json").read_text())
    if (cfg2["images"] != selection["images"] or cfg2["contract"]["selection_sha256"] != selection_hash
            or any(cfg2["contract"][k] != base2[k] for k in ("config", "taxonomy", "runner_sha256", "packages"))):
        raise ValueError("GSAM 2 recipe changed from the frozen baseline")
    fields = ("model", "revision", "checkpoint_sha256", "official_source_commit", "prompt", "score_threshold",
              "mask_threshold", "weight_dtype", "autocast", "tf32", "use_fa3", "use_rope_real",
              "supervise_joint_box_scores", "packages", "load_report", "official_file_sha256")
    if cfg3["selection_sha256"] != selection_hash or any(cfg3[k] != base3[k] for k in fields):
        raise ValueError("SAM 3 recipe changed from concrete-sidewalk / 0.4")
    if json.loads((args.sam3 / "summary.json").read_text())["count"] != 200:
        raise ValueError("SAM 3 run incomplete")
    out = output_path(args.output, [source, args.selection, args.mapping, args.gsam2, args.sam3])
    out.mkdir(parents=True)
    for folder in ("images", "masks"):
        (out / folder).mkdir()
    manifest = {"kind": "sidewalkpilot-paired-class1-v1", "created_utc": utc_now(), "count": 200,
                "selection_sha256": selection_hash, "review_scope": {"kind": "class", "class_ids": [1]}, "pairs": []}
    audit = {"selection_sha256": selection_hash, "mapping_sha256": sha256(args.mapping),
             "gsam2_manifest_sha256": sha256(args.gsam2 / "manifest.json"),
             "sam3_config_sha256": sha256(args.sam3 / "config.json"), "input_sha256": {}}
    for i, frame in enumerate(selection["frames"], 1):
        key, name = f"pair-{i:03d}", frame["image"]
        assignment = mapping["pairs"][key]
        if assignment["image"] != name or sorted(assignment[s] for s in ("A", "B")) != ["gsam2", "sam3"]:
            raise ValueError("Invalid paired assignment")
        row2 = json.loads((args.gsam2 / "records" / (Path(name).stem + ".json")).read_text())
        row3 = json.loads((args.sam3 / "records" / f"{i:02d}.json").read_text())
        verify_record(args.gsam2, row2, source)
        for row in (row2, row3):
            if any(row[k] != frame[k] for k in ("image", "size", "source_sha256")):
                raise ValueError("Source identity changed between pipelines")
        paths = {"gsam2": (args.gsam2 / row2["mask"], row2["mask_sha256"]),
                 "sam3": (args.sam3 / row3["instance_union"]["path"], row3["instance_union"]["sha256"])}
        pair = {"id": key, "source_name": name, "image": f"images/{i:03d}.jpg",
                "source_sha256": frame["source_sha256"], "size": frame["size"], "candidates": {}}
        shutil.copy2(source / name, out / pair["image"])
        for side in ("A", "B"):
            path, digest = paths[assignment[side]]
            if sha256(path) != digest:
                raise ValueError("Prediction hash changed")
            with Image.open(path) as image:
                mask = np.asarray(image)
            if mask.shape != tuple(reversed(frame["size"])) or not np.isin(mask, [1, 255]).all():
                raise ValueError("Unexpected class-1 proposal format")
            relative = f"masks/{i:03d}-{side}.png"
            shutil.copy2(path, out / relative)
            pair["candidates"][side] = {"id": f"{key}-{side}", "mask_sha256": digest,
                                        "mask": relative, "rle": encode_binary(mask == 1)}
            audit["input_sha256"][str(path)] = digest
        manifest["pairs"].append(pair)
    manifest["package_id"] = digest_json(manifest)
    write_json(out / "manifest.json", manifest)
    (out / "data.js").write_text("window.PAIRED_DATA = " + json.dumps(manifest, separators=(",", ":")) + ";\n")
    for name in ("paired.html", "paired.js", "paired.css", "lucide.min.js", "LUCIDE-LICENSE.txt"):
        shutil.copy2(HERE / "review" / name, out / ("index.html" if name == "paired.html" else name))
    (out / "READ-ME.txt").write_text(
        "SidewalkPilot: fresh paired class-1 review\n\n"
        "Open index.html. No server, installation or folder upload is needed.\n"
        "A/B identities vary per image and the private mapping is not in this package.\n"
        "1 = correct, 2 = needs correction, 3 = uncertain for the selected A or B mask.\n"
        "After needs correction, 1/2/3 select minor/moderate/major before switching candidates.\n"
        "A decision selects the other unreviewed mask; after both decisions the next image opens.\n"
        "Enter = next image without assigning decisions. Left arrow = previous image.\n"
        "Finishing A always selects B. Auto next image controls moving ahead after B.\n"
        "Click A or B to select a mask and add effort estimates or notes.\n"
        "Use Source/Overlay/Mask, opacity and zoom to inspect edges.\n"
        "Export decisions with the download icon: sidewalkpilot-paired-review.json.\n"
        "Browser saving is local to this package. Export regularly; imports validate the package and mask hashes.\n\n"
        "Rubric: visible sidewalk includes its shadows and its continuous path across driveways.\n"
        "Adjoining driveway/road areas, grass and actual occluding objects are not sidewalk.\n"
        "Meaningful omissions, spillover or holes require correction. Minor edge jaggedness alone need not fail.\n"
        "Use uncertain when the source itself does not support a confident boundary decision.\n"
        "An empty mask can be correct if the source genuinely contains no visible sidewalk.\n"
        "Judge both masks independently using the same standard. Neither may be correct.\n"
        "Effort is an optional estimate, not measured correction time. No pixel editing occurs here.\n\n"
        "These are unreviewed class-1 proposals, not verified twelve-class labels.\n"
        "Unhighlighted pixels are not verified background. Review acceptance is not pixel IoU.\n"
        "The 200 images exclude known earlier pilots, temporal neighbors and close dHash matches.\n"
        "This duplicate-reduced development sample is not an IID estimate for all 81,237 images.\n")
    audit["package_id"] = manifest["package_id"]
    write_json(args.mapping.parent / "package-audit.json", audit)
    print(json.dumps({"package": str(out), "pairs": 200, "masks": 400, "package_id": manifest["package_id"]}))


if __name__ == "__main__":
    main()
