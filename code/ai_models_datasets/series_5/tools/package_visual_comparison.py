#!/usr/bin/env python3
"""Package original, GSAM 2, SAM 3 and AI-authored polygon masks for offline review."""

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw

from evaluate_class1_corrections import safe_file, read_mask
from label_grounded_sam2 import digest_json, save_mask, sha256, utc_now, verify_record, write_json
from prepare_random_comparison import validate_random_selection

HERE = Path(__file__).resolve().parent


def rasterize(entry, size):
    width, height = size
    canvas = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(canvas)
    for key, value in (("sidewalk", 1), ("exclude", 0), ("uncertain", 255)):
        if not isinstance(entry.get(key), list):
            raise ValueError("Missing polygon group")
        for polygon in entry[key]:
            if not isinstance(polygon, list) or len(polygon) < 3:
                raise ValueError("Polygon needs at least three vertices")
            for point in polygon:
                if (not isinstance(point, list) or len(point) != 2
                        or any(type(v) is not int for v in point)
                        or not 0 <= point[0] < width or not 0 <= point[1] < height):
                    raise ValueError("Polygon coordinate outside original image")
            draw.polygon([tuple(p) for p in polygon], fill=value)
    if not isinstance(entry.get("notes"), str):
        raise ValueError("Missing annotation notes")
    return np.array(canvas)


def encode_labels(mask):
    flat = np.asarray(mask).ravel()
    if not len(flat) or not np.isin(flat, (0, 1, 255)).all():
        raise ValueError("Expected binary labels and optional uncertainty")
    starts = np.r_[0, np.flatnonzero(flat[1:] != flat[:-1]) + 1]
    lengths = np.diff(np.r_[starts, len(flat)])
    return np.column_stack((flat[starts], lengths)).ravel().tolist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("selection", "annotations", "gsam2", "sam3", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--review-only", choices=("codex",), help="Keep reference panels visible but rate only Codex")
    args = parser.parse_args()
    selection = validate_random_selection(args.selection)
    source, out = Path(selection["source"]), args.output.resolve()
    protected = [source, args.selection.parent, args.annotations.parent, args.gsam2, args.sam3]
    if out.exists() or any(out == p.resolve() or out in p.resolve().parents or p.resolve() in out.parents for p in protected):
        raise ValueError("Use a new output directory separate from inputs")
    annotations = json.loads(args.annotations.read_text())
    if (annotations.get("schema") != "sidewalkpilot-ai-visual-polygons-v1"
            or annotations.get("review_status") != "unreviewed"
            or [a["id"] for a in annotations["entries"]] != list(range(1, len(selection["images"]) + 1))):
        raise ValueError("Incomplete or invalid AI annotation set")
    manifest2 = json.loads((args.gsam2 / "manifest.json").read_text())
    config3 = json.loads((args.sam3 / "config.json").read_text())
    selection_hash = sha256(args.selection)
    if (manifest2["images"] != selection["images"] or manifest2["contract"]["selection_sha256"] != selection_hash
            or config3["selection_sha256"] != selection_hash or config3["model"] != "facebook/sam3"):
        raise ValueError("Model predictions use different images or methods")
    out.mkdir(parents=True)
    for folder in ("images", "masks", "provenance"):
        (out / folder).mkdir()
    inputs = [args.selection, args.annotations, args.gsam2 / "manifest.json", args.sam3 / "config.json", Path(__file__)]
    hashes = {str(p.resolve()): sha256(p) for p in inputs}
    manifest = {"schema": "sidewalkpilot-three-method-comparison-v1", "created_utc": utc_now(),
                "count": len(selection["images"]), "selection_sha256": selection_hash,
                "seed": selection["seed"], "source_count": selection["source_count"], "sampling": selection["sampling"],
                "methods": {"gsam2": "GSAM 2", "sam3": "SAM 3", "codex": "Codex visual annotation"},
                "review_methods": [args.review_only] if args.review_only else ["gsam2", "sam3", "codex"],
                "annotation_revision": annotations.get("revision", 1),
                "annotation_method": annotations["method"], "annotation_policy": annotations["policy"],
                "annotation_sha256": sha256(args.annotations), "review_status": "unreviewed",
                "scope": "Visual class-1 comparison, not an accuracy benchmark. Named methods are not blinded. AI polygons are not human ground truth. No model retraining or full-dataset labeling.",
                "frames": []}
    for number, (frame, annotation) in enumerate(zip(selection["frames"], annotations["entries"]), 1):
        if frame["size"] != annotations["coordinate_space"]:
            raise ValueError("Polygon canvas dimensions differ from source")
        name = frame["image"]
        record2_path = args.gsam2 / "records" / (Path(name).stem + ".json")
        record3_path = args.sam3 / "records" / f"{number:02d}.json"
        record2, record3 = [json.loads(p.read_text()) for p in (record2_path, record3_path)]
        verify_record(args.gsam2, record2, source)
        for record in (record2, record3):
            if any(record[k] != frame[k] for k in ("image", "source_sha256", "size")):
                raise ValueError("Source identities differ")
        hashes.update({str(p.resolve()): sha256(p) for p in (record2_path, record3_path, source / name)})
        source_relative = f"images/{number:02d}.jpg"
        shutil.copy2(source / name, out / source_relative)
        masks = {}
        for method, root, relative, expected in (
                ("gsam2", args.gsam2, record2["mask"], record2["mask_sha256"]),
                ("sam3", args.sam3, record3["instance_union"]["path"], record3["instance_union"]["sha256"])):
            path = safe_file(root, relative)
            if sha256(path) != expected:
                raise ValueError("Frozen prediction hash differs")
            hashes[str(path)] = expected
            masks[method] = read_mask(path, tuple(reversed(frame["size"])), (1, 255))
        masks["codex"] = rasterize(annotation, frame["size"])
        result = {"id": f"image-{number:02d}", "name": name, "image": source_relative,
                  "size": frame["size"], "source_sha256": frame["source_sha256"], "annotation_notes": annotation["notes"], "methods": {}}
        for method, mask in masks.items():
            path = out / "masks" / f"{number:02d}-{method}.png"
            save_mask(path, mask)
            # Model 255 is unassigned, not claimed uncertain; retain raw PNG IDs.
            displayed = mask if method == "codex" else (mask == 1).astype(np.uint8)
            result["methods"][method] = {"mask": str(path.relative_to(out)), "sha256": sha256(path),
                                         "positive_pixels": int((mask == 1).sum()),
                                         "uncertain_pixels": int((mask == 255).sum()) if method == "codex" else 0,
                                         "unassigned_pixels": int((mask == 255).sum()) if method != "codex" else 0,
                                         "rle": encode_labels(displayed)}
        manifest["frames"].append(result)
    manifest["package_id"] = digest_json(manifest)
    write_json(out / "manifest.json", manifest)
    (out / "data.js").write_text("window.COMPARISON_DATA = " + json.dumps(manifest, separators=(",", ":")) + ";\n")
    for name in ("comparison.html", "comparison.js", "comparison.css", "lucide.min.js", "LUCIDE-LICENSE.txt"):
        shutil.copy2(HERE / "review" / name, out / ("index.html" if name == "comparison.html" else name))
    for path, name in ((args.selection, "selection.json"), (args.annotations, "ai-polygons.json"),
                       (args.gsam2 / "manifest.json", "gsam2-manifest.json"),
                       (args.sam3 / "config.json", "sam3-config.json"), (Path(__file__), Path(__file__).name)):
        shutil.copy2(path, out / "provenance" / name)
    (out / "READ-ME.txt").write_text("""SidewalkPilot: original / GSAM 2 / SAM 3 / Codex visual annotations

Open index.html in Chrome or Edge. No installation, server or folder selection.
Enter or Right arrow: next image. Left arrow: previous image.
Click a model heading to select it. 1 = correct, 2 = needs correction,
3 = uncertain for the selected method. Rating does not auto-advance.
After Needs correction, choose 1 = minor (barely any fixes), 2 = moderate
(several areas), or 3 = major (large changes/redraw). Esc closes without
changing the level. Click Needs correction again to change its level.
Older reviews without correction levels remain valid; levels are not inferred.
Use grid/columns/focus layout, Source/Overlay/Mask, opacity and shared zoom.
At increased zoom, scrolling any panel synchronizes the others.
Export downloads sidewalkpilot-three-method-review.json. Browser-only storage
is not a backup. Import validates source and mask identities for this package.

Green: proposed sidewalk. Amber hatching: Codex uncertain pixels.
In mask-only mode, black means non-highlighted; model black is unassigned,
not independently verified non-sidewalk. Original is always the untouched photo.
All three methods are unverified. None is presented as ground truth.

Annotation method and revision history are recorded in manifest.json and
provenance/ai-polygons.json. No GSAM/SAM predictions seeded the Codex polygons.
Polygons are approximate and may miss fine edges or tiny debris.
Their uncertainty bands are explicit; they are not automatically better labels.
The same 30 uniformly sampled filenames are used by all three methods.
Sampling seed and source hashes, raw mask PNGs, polygon coordinates, model
configuration and package integrity hashes are included.

This named comparison is not blinded or an independent accuracy study.
No source images, previous human corrections or reviews were changed.
""", encoding="ascii")
    if args.review_only:
        with (out / "READ-ME.txt").open("a") as stream:
            stream.write("\nThis round rates only Codex masks: 30 ratings, not 90. GSAM 2 and SAM 3\n"
                         "remain visible for reference only. Prior-round reviews are not imported\n"
                         "into changed masks. The new package has separate browser review storage.\n")
    for path, expected in hashes.items():
        if sha256(Path(path)) != expected:
            raise ValueError("Input changed while packaging")
    write_json(out / "integrity-check.json", {"input_sha256": hashes,
               "files_sha256": {str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    print(json.dumps({"output": str(out), "count": manifest["count"], "package_id": manifest["package_id"]}, indent=2))


if __name__ == "__main__":
    main()
