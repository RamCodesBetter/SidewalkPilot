"""Stage fresh training-day frames, then screen final SAM masks for one connected sidewalk."""
import argparse
from collections import Counter
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import workspace
workspace.activate()
from label_grounded_sam2 import digest_json, sha256, write_json
from label_series5_pseudo import load_selection
from prepare_reviewed_dataset import read_json, safe_file
from pseudo_training_targets import prepare_target


def stage(campaign, out, count, previous=()):
    if count < 1 or out.exists():
        raise ValueError("Use a positive count and fresh output")
    manifest = read_json(campaign / "manifest.json")
    seen = set()
    for path in previous:
        prior = load_selection(path / "selection.json")
        if prior.get("campaign_id") != manifest["campaign_id"]:
            raise ValueError("Prior batch belongs to another campaign")
        seen.update(row["id"] for row in prior["frames"])
    frames = []
    for row in manifest["frames"]:
        if (row["id"] not in seen and row["training_eligible"] and not row["existing_review"]
                and not (campaign / "items" / (row["id"] + ".json")).exists()):
            frames.append({k: row[k] for k in ("id", "image", "source_sha256", "recording_run")})
            if len(frames) == count:
                break
    if len(frames) != count:
        raise ValueError("Insufficient fresh training frames")
    selection = dict(schema="sidewalkpilot-pseudo-selection-v1", source=manifest["source"],
                     campaign_id=manifest["campaign_id"], count=count, frames=frames,
                     allowed_days=manifest["train_days"], purpose="single sidewalk development batch")
    selection["selection_id"] = digest_json(selection)
    out.mkdir(parents=True)
    write_json(out / "selection.json", selection)


def screen(out):
    selection = load_selection(out / "selection.json")
    run = out / "proposals"
    manifest = read_json(run / "manifest.json")
    if (manifest["contract"]["selection_sha256"] != sha256(out / "selection.json")
            or read_json(run / "status.json")["status"] != "complete"):
        raise ValueError("Proposal run is incomplete or mismatched")
    masks = out / "single-sidewalk"
    masks.mkdir(exist_ok=False)
    rows, panels = [], []
    for index, frame in enumerate(selection["frames"], 1):
        record = read_json(run / "records" / (frame["id"] + ".json"))
        if record["frame"] != frame or record["contract_sha256"] != manifest["contract_sha256"]:
            raise ValueError("Prediction identity mismatch")
        reasons = list(record["filter"]["reasons"])
        row = dict(id=frame["id"], image=frame["image"], index=index, reasons=reasons, human_verified=False)
        if not reasons:
            path = safe_file(run, record["mask"]["path"])
            if sha256(path) != record["mask"]["sha256"]:
                raise ValueError("Mask changed")
            with Image.open(path) as im:
                labels, _ = prepare_target(np.asarray(im))
            fg = labels == 1
            _, components = ndimage.label(fg, structure=np.ones((3, 3)))
            if components != 1:
                reasons.append("final_sidewalk_component_count_not_one")
            if (labels == 0).mean() < manifest["contract"]["policy"]["minimum_negative_fraction"]:
                reasons.append("insufficient_background_after_preparation")
            if not reasons:
                target = masks / (frame["id"] + ".png")
                Image.fromarray(labels).save(target)
                row.update(mask=str(target.relative_to(out)), sha256=sha256(target))
                with Image.open(safe_file(Path(selection["source"]), frame["image"])) as im:
                    orig = im.convert("RGB")
                overlay = Image.composite(Image.blend(orig, Image.new("RGB", orig.size, "lime"), .38),
                                          orig, Image.fromarray(fg))
                pair = Image.new("RGB", (512, 164), "white")
                for j, view in enumerate((orig, overlay)):
                    view.thumbnail((256, 144))
                    pair.paste(view, (256*j, 18))
                ImageDraw.Draw(pair).text((3, 2), f"{index}: original | sidewalk candidate", fill="black")
                panels.append(pair)
        rows.append(row)
    for start in range(0, len(panels), 8):
        chunk = panels[start:start+8]
        sheet = Image.new("RGB", (512, 164*len(chunk)), "white")
        for j, pair in enumerate(chunk):
            sheet.paste(pair, (0, 164*j))
        sheet.save(out / f"inspect-{start//8+1}.jpg", quality=92)
    report = dict(processed=len(rows), candidates=len(panels), deferred=len(rows)-len(panels),
                  reasons=dict(Counter(r for row in rows for r in row["reasons"])), records=rows,
                  scope="Automatic pseudo-labels only; exactly one 8-connected foreground. 255 is unknown.")
    write_json(out / "screen.json", report)
    print({k:v for k,v in report.items() if k != "records"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("stage")
    select.add_argument("campaign", type=Path)
    select.add_argument("count", type=int)
    select.add_argument("--previous", action="append", default=[], type=Path)
    for p in (select, sub.add_parser("screen")):
        p.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.command == "stage":
        stage(args.campaign, args.out, args.count, args.previous)
    else:
        screen(args.out)
