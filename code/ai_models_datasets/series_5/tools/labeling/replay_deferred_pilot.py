"""Trace the existing detector on the frozen deferred pilot. No ledger writes."""
import argparse
from collections import Counter
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

import run_single_corridor_campaign as campaign
from deferred_pilot import build


def geometry(fg):
    h, w = fg.shape
    _, lab, stats, _ = cv2.connectedComponentsWithStats(fg.astype("uint8"), connectivity=8)
    ids, hits = np.unique(lab[int(.9*h):, int(.35*w):int(.65*w)], return_counts=True)
    anchors = [i for i, n in zip(ids, hits) if i and n > .003*h*w]
    if len(anchors) != 1:
        return "No single near-camera anchor", None
    area = int(stats[anchors[0], cv2.CC_STAT_AREA])
    if not .15 <= area / fg.size <= .94:
        return "Anchored region outside 15-94% coverage", None
    return None, int(fg.sum()) - area


def replay(detector, photo, stem, out):
    rgb = np.asarray(photo)
    prompts, pair, final = [], {}, {}
    def overlay(mask, suffix):
        img = rgb.copy()
        img[mask] = .55 * img[mask] + .45 * np.array([0, 210, 150])
        name = f"{stem}-{suffix}.jpg"
        Image.fromarray(img).save(out/name, quality=92)
        return name

    select, compare, prepare = campaign.instance, campaign.filter_masks, campaign.prepare_target
    def instance(masks, scores, threshold):
        idx = len(prompts)
        info = dict(prompt=campaign.PROMPTS[idx], threshold=threshold, candidates=[])
        prompts.append(info)
        for n, (raw, score) in enumerate(zip(masks, scores)):
            fg = raw.reshape(raw.shape[-2:]).astype(bool)
            check, extra = geometry(fg)
            reason = ("Score below prompt threshold" if score < threshold else check or
                      ("Too many detached pixels" if extra > 128*fg.size/(1280*720)
                       else "Eligible for instance selection"))
            info["candidates"].append(dict(score=score, area=float(fg.mean()), gate=reason,
                 detached=extra, overlay=overlay(fg, f"{idx}-{n}")))
        picked, reason = select(masks, scores, threshold)
        info["decision"] = reason or "selected"
        return picked, reason

    def filtered(*args):
        mask, detail = compare(*args)
        pair.update(detail)
        pair["overlay"] = overlay(mask == 1, "consensus")
        return mask, detail

    def prepared(*args):
        result = prepare(*args)
        labels = result[0]
        fg = labels == 1
        check, extra = geometry(fg)
        final.update(anchor=check, detached=extra, background=float((labels==0).mean()),
                     overlay=overlay(fg, "final"))
        return result

    with ExitStack() as stack:
        for key, fn in [("instance",instance), ("filter_masks",filtered), ("prepare_target",prepared)]:
            stack.enter_context(patch.object(campaign, key, fn))
        labels, reasons, _ = detector.predict(photo)
    if reasons == ["no_confident_anchored_instance"]:
        gates = sorted({c["gate"] for c in prompts[-1]["candidates"]})
        explanation = "; ".join(gates) or "No proposal above the 0.40 detector cutoff"
    elif reasons == ["invalid_final_corridor"]:
        explanation = "; ".join(x for x in [final["anchor"], "Detached final pixels" if final["detached"] else None,
                           "Under 3% known background" if final["background"] < .03 else None] if x)
    elif reasons == ["competing_sidewalk_instances"]:
        explanation = "Two eligible regions disagree (instance IoU below 0.90)"
    else:
        explanation = "; ".join(r.replace("_", " ") for r in reasons) or "Passed on replay only"
    return dict(prompts=prompts, pair=pair, final=final, reasons=reasons, explanation=explanation)


def run(history, out):
    screen = history/"series5-df-screen"
    pilot = campaign.read_json(screen/"deferred-pass1-pilot.json")
    if pilot != build(history, pilot["seed"]) or len(pilot["sample"]) != 30:
        raise ValueError("Pilot no longer matches the frozen deferred records")
    policy = campaign.read_json(history/"strict-pass-10000/policy.json")["contract"]
    inventory = history/"series5-5CD-labeling/manifest.json"
    if campaign.sha256(inventory) != policy["inventory"]:
        raise ValueError("Source inventory changed")
    for name, digest in policy["code"].items():
        if campaign.sha256(campaign.workspace.source_path(name)) != digest:
            raise ValueError(f"Detector source changed: {name}")
    source = Path(campaign.read_json(inventory)["source"])
    if out.exists() or out.resolve().is_relative_to(screen.resolve()):
        raise ValueError("Use a new diagnostic directory outside screening")
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    cv2.setNumThreads(1)
    detector = campaign.Detector()
    frames = []
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        root = Path(tmp)/"viewer"
        root.mkdir()
        for i,row in enumerate(pilot["sample"],1):
            image = campaign.safe_file(source,row["image"])
            if campaign.sha256(image) != row["id"]:
                raise ValueError("Photo identity changed")
            stem = f"{i:02d}"
            shutil.copyfile(image, root/(stem+".jpg"))
            with Image.open(image) as im:
                record = replay(detector, im.convert("RGB"), stem, root)
            frames.append(dict(**record, id=row["id"], original=stem+".jpg", name=row["image"],
                               original_reasons=row["reasons"]))
            print(f"{i}/30: {record['explanation']}",flush=True)
        manifest = dict(stage="diagnosis_only", pilot_sha256=campaign.sha256(screen/"deferred-pass1-pilot.json"),
                        identity=pilot["screening_identity"], runtime=detector.runtime, frames=frames)
        campaign.write_json(root/"diagnostics.json",manifest)
        (root/"data.js").write_text("const frames="+json.dumps(frames)+";")
        shutil.copyfile(campaign.workspace.source_path("deferred-diagnostics.html"),root/"index.html")
        root.rename(out)
    print(Counter(f["explanation"] for f in frames))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    run(args.history,args.output)
