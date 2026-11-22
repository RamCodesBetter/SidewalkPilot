#!/usr/bin/env python3
"""Screen the corpus resumably without weakening filters or leaking held-out days."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import random
import shutil
from types import SimpleNamespace

import numpy as np
from PIL import Image

import label_series5_pseudo as labeler
from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from prepare_reviewed_dataset import read_json, safe_file
from pseudo_mask_filter import POLICY
from pseudo_training_targets import POLICY as TARGET_POLICY, prepare_target

HERE = _workspace.TOOLS
SCHEMA = "sidewalkpilot-labeling-campaign-v1"


def code_hashes():
    names = [Path(__file__).name, "label_series5_pseudo.py", "pseudo_mask_filter.py",
             "pseudo_training_targets.py", "compare_sam31_sidewalk.py"]
    return {name: sha256(_workspace.source_path(name)) for name in names}


def frame_of(row):
    return {key: row[key] for key in ("id", "image", "source_sha256", "recording_run")}


def prepare(args):
    output, source = args.output.resolve(), args.source.resolve()
    if output.exists() or args.target < 1 or args.batch_size < 1:
        raise ValueError("Use a new output and positive target/batch size")
    inputs = [source, args.dataset.resolve(), args.seed_run.resolve()]
    if any(output.is_relative_to(p) or p.is_relative_to(output) for p in inputs):
        raise ValueError("Campaign output overlaps source artifacts")
    base_path = args.dataset / "manifest.json"
    base, split = read_json(base_path), read_json(args.split)
    if split["manifest_sha256"] != sha256(base_path):
        raise ValueError("Baseline split differs")
    train_days = set(split["days"]["train"])
    held_days = set(split["days"]["validation"] + split["days"]["test"])
    if train_days & held_days:
        raise ValueError("Training and held-out days overlap")
    reviewed = {r["id"] for r in base["records"]}
    reviewed_names = {r["source_name"] for r in base["records"]}
    seed_run = read_json(args.seed_run / "manifest.json")
    selection_path = Path(seed_run["selection"])
    selection = labeler.load_selection(selection_path)
    expected = {"policy": POLICY, "runner_sha256": sha256(_workspace.source_path('label_series5_pseudo.py')),
                "filter_sha256": sha256(_workspace.source_path('pseudo_mask_filter.py'))}
    if (digest_json(seed_run["contract"]) != seed_run["contract_sha256"]
            or any(seed_run["contract"].get(k) != v for k, v in expected.items())
            or seed_run["contract"]["selection_sha256"] != sha256(selection_path)
            or selection["baseline_manifest_sha256"] != sha256(base_path)
            or selection["baseline_split_sha256"] != sha256(args.split)
            or Path(selection["source"]).resolve() != source
            or read_json(args.seed_run / "status.json")["status"] != "complete"):
        raise ValueError("Seed run does not match the frozen pipeline/source/split")
    exclusions = read_json(args.exclusions)
    if exclusions["run_contract_sha256"] != seed_run["contract_sha256"]:
        raise ValueError("Exclusions belong to another run")
    excluded = {r["id"]: r["reason"] for r in exclusions["records"]}
    seed_frames = {r["id"]: r for r in selection["frames"]}
    if not set(excluded) <= seed_frames.keys():
        raise ValueError("Unknown visual exclusion")
    groups = {}
    for n, path in enumerate(sorted(source.glob("*.jpg")), 1):
        digest = sha256(path)
        run = path.name.split("__photo_")[0]
        day = run.rsplit("_run_", 1)[0]
        if day not in train_days | held_days:
            raise ValueError(f"Unassigned recording day: {day}")
        groups.setdefault(digest, []).append(dict(image=path.name, recording_run=run, day=day))
        if n % 10000 == 0:
            print(json.dumps({"inventory_hashed": n}), flush=True)
    if not groups or not seed_frames.keys() <= groups.keys():
        raise ValueError("Missing source images")
    rows = []
    for digest, aliases in groups.items():
        preferred = seed_frames.get(digest, {}).get("image", aliases[0]["image"])
        matching = [a for a in aliases if a["image"] == preferred]
        if not matching:
            raise ValueError("Seed source filename disappeared")
        row = dict(id=digest, source_sha256=digest, **matching[0], aliases=aliases,
                   training_eligible=all(a["day"] in train_days and a["image"] not in reviewed_names for a in aliases)
                   and digest not in reviewed, existing_review=digest in reviewed)
        if digest in seed_frames and frame_of(row) != seed_frames[digest]:
            raise ValueError("Seed image identity changed")
        rows.append(row)
    rng = random.Random(args.seed)
    fresh_train = [r for r in rows if r["training_eligible"] and r["id"] not in seed_frames]
    archive = [r for r in rows if not r["training_eligible"] and r["id"] not in seed_frames]
    rng.shuffle(fresh_train)
    rng.shuffle(archive)
    by_id = {r["id"]: r for r in rows}
    ordered = [by_id[r["id"]] for r in selection["frames"]] + fresh_train + archive
    manifest = dict(schema=SCHEMA, created_utc=utc_now(), source=str(source), seed=args.seed,
                    target=args.target, batch_size=args.batch_size, count=len(rows),
                    file_count=sum(map(len, groups.values())), frames=ordered,
                    seed_count=len(seed_frames), seed_run=str(args.seed_run.resolve()),
                    seed_contract_sha256=seed_run["contract_sha256"], runtime=seed_run["contract"]["runtime"],
                    train_days=sorted(train_days), held_out_days=sorted(held_days),
                    visual_exclusions=excluded, policy=POLICY, target_policy=TARGET_POLICY,
                    code_sha256=code_hashes(),
                    input_sha256={str(p.resolve()): sha256(p) for p in
                                  (base_path, args.split, selection_path, args.exclusions)},
                    scope="Automatic pseudo-label screening only. Held-out-day proposals are archive-only, never training or evaluation references. No model training or publication.",
                    failure_policy="Preserve failed cases for correction/review. Never relax checks, rerun identical prompts until lucky, or count unknown pixels as verified background.")
    manifest["campaign_id"] = digest_json(manifest)
    output.mkdir(parents=True)
    for folder in ("items", "targets", "batches"):
        (output / folder).mkdir()
    write_json(output / "manifest.json", manifest)
    return {"campaign": str(output), "unique_images": len(rows), "files": manifest["file_count"], "reuse": len(seed_frames),
            "new_training_candidates": len(fresh_train), "archive_only_candidates": len(archive)}


def load_campaign(root):
    manifest = read_json(root / "manifest.json")
    if (manifest.get("schema") != SCHEMA or
            digest_json({k: v for k, v in manifest.items() if k != "campaign_id"}) != manifest["campaign_id"]
            or manifest["code_sha256"] != code_hashes()):
        raise ValueError("Campaign identity or implementation changed")
    for path, expected in manifest["input_sha256"].items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"Frozen input changed: {path}")
    return manifest


def register_record(root, manifest, row, run, run_manifest):
    record_path = run / "records" / (row["id"] + ".json")
    item_path = root / "items" / (row["id"] + ".json")
    if item_path.exists():
        item = read_json(item_path)
        if (item["campaign_id"] != manifest["campaign_id"] or item["frame"] != row
                or sha256(record_path) != item["record_sha256"]):
            raise ValueError("Committed record changed")
        if item.get("target") and sha256(safe_file(root, item["target"]["path"])) != item["target"]["sha256"]:
            raise ValueError("Prepared target changed")
        return item
    record = read_json(record_path)
    if (record["frame"] != frame_of(row) or record["contract_sha256"] != run_manifest["contract_sha256"]
            or digest_json(run_manifest["contract"]) != run_manifest["contract_sha256"]
            or run_manifest["contract"]["policy"] != POLICY
            or run_manifest["contract"]["runtime"] != manifest["runtime"]):
        raise ValueError("Prediction contract differs")
    for asset in (record["mask"], *record["raw"]):
        if sha256(safe_file(run, asset["path"])) != asset["sha256"]:
            raise ValueError("Prediction asset changed")
    reasons = list(record["filter"]["reasons"])
    if record["filter"]["accepted_for_pseudo_training"] != (not reasons):
        raise ValueError("Inconsistent filter verdict")
    if row["id"] in manifest["visual_exclusions"]:
        reasons.append("prior_visual_exclusion")
    target = None
    if not reasons:
        with Image.open(safe_file(run, record["mask"]["path"])) as image:
            labels, detail = prepare_target(np.array(image))
        if labels.shape != tuple(reversed(record["size"])):
            raise ValueError("Target dimensions differ")
        if float((labels == 0).mean()) < POLICY["minimum_negative_fraction"]:
            reasons.append("insufficient_background_after_target_preparation")
        else:
            relative = "targets/" + row["id"] + ".png"
            temporary = root / (relative + ".tmp")
            Image.fromarray(labels).save(temporary, format="PNG")
            temporary.replace(root / relative)
            target = dict(path=relative, sha256=sha256(root / relative), preparation=detail,
                          source_mask_sha256=record["mask"]["sha256"],
                          labels={"0": "pseudo background", "1": "pseudo sidewalk", "255": "unknown"})
    item = dict(campaign_id=manifest["campaign_id"], frame=row, record=str(record_path),
                record_sha256=sha256(record_path), run_contract_sha256=run_manifest["contract_sha256"],
                accepted_screen=not reasons, reasons=reasons, target=target,
                training_eligible=row["training_eligible"], human_verified=False,
                prior_visual_exclusion=manifest["visual_exclusions"].get(row["id"]),
                filter=record["filter"], created_utc=utc_now())
    write_json(item_path, item)
    return item


def summarize(manifest, items, state):
    accepted = [i for i in items if i["accepted_screen"]]
    train = [i for i in accepted if i["training_eligible"]]
    remaining_train = sum(r["training_eligible"] for r in manifest["frames"]) - sum(i["training_eligible"] for i in items)
    target_met = len(train) >= manifest["target"]
    return dict(state=state, updated_utc=utc_now(), campaign_id=manifest["campaign_id"],
                corpus_unique_images=manifest["count"], corpus_files=manifest["file_count"],
                processed=len(items), pending=manifest["count"]-len(items),
                files_covered=sum(len(i["frame"]["aliases"]) for i in items),
                accepted_automatic=len(accepted), deferred=len(items)-len(accepted),
                training_accepted=len(train), training_pending=remaining_train,
                training_shortfall=max(0, manifest["target"]-len(train)),
                five_c_status="screened_candidates_ready_not_verified" if target_met else
                "needs_correction_pool_exhausted" if remaining_train == 0 else "collecting",
                five_d_status="screening" if len(items) < manifest["count"] else
                "needs_correction" if len(accepted) < manifest["count"] else "screened_not_human_verified",
                deferred_reasons=dict(Counter(r for i in items for r in i["reasons"])),
                models_trained=False, note="Automatic acceptance is not proof of accurate labels. No held-out-day image enters the 5.C list.")


def publish(root, manifest, items, state):
    summary = summarize(manifest, items, state)
    write_json(root / "progress.json", summary)
    write_json(root / "correction-queue.json", dict(campaign_id=manifest["campaign_id"],
               records=[dict(id=i["frame"]["id"], image=i["frame"]["image"],
                             training_eligible=i["training_eligible"], reasons=i["reasons"], record=i["record"])
                        for i in items if not i["accepted_screen"]]))
    accepted = [i for i in items if i["accepted_screen"] and i["training_eligible"]]
    write_json(root / "training-candidates.json", dict(campaign_id=manifest["campaign_id"],
               count=len(accepted), target=manifest["target"], human_verified=False,
               records=[dict(id=i["frame"]["id"], image=i["frame"]["image"], target=i["target"],
                             record=i["record"], record_sha256=i["record_sha256"]) for i in accepted]))
    if len(accepted) >= manifest["target"]:
        snapshot = dict(campaign_id=manifest["campaign_id"], count=manifest["target"],
                        status="screened pseudo-label candidates; requires quality audit before training",
                        ids=[i["frame"]["id"] for i in accepted[:manifest["target"]]])
        path = root / "5.C-candidate-snapshot.json"
        if path.exists() and read_json(path) != snapshot:
            raise ValueError("Frozen 5.C snapshot changed")
        write_json(path, snapshot)
    print(json.dumps(summary), flush=True)
    return summary


def batch_selection(root, manifest, number, rows):
    path = root / "batches" / f"{number:04d}-selection.json"
    if path.exists():
        result = labeler.load_selection(path)
        if result["frames"] != [frame_of(r) for r in rows]:
            raise ValueError("Frozen batch changed")
        return path
    result = dict(schema="sidewalkpilot-pseudo-selection-v1", created_utc=utc_now(),
                  source=manifest["source"], count=len(rows), requested=len(rows), seed=manifest["seed"],
                  allowed_days=sorted({r["day"] for r in rows}),
                  purpose="campaign proposals; training eligibility is recorded separately, held-out days are archive-only",
                  campaign_id=manifest["campaign_id"], frames=[frame_of(r) for r in rows])
    result["selection_id"] = digest_json(result)
    write_json(path, result)
    return path


def execute(args):
    root = args.campaign.resolve()
    with (root / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("A labeling worker already owns this campaign") from exc
        manifest = load_campaign(root)
        items = []
        try:
            seed_run = Path(manifest["seed_run"])
            seed_manifest = read_json(seed_run / "manifest.json")
            if seed_manifest["contract_sha256"] != manifest["seed_contract_sha256"]:
                raise ValueError("Seed contract changed")
            for row in manifest["frames"][:manifest["seed_count"]]:
                items.append(register_record(root, manifest, row, seed_run, seed_manifest))
            publish(root, manifest, items, "running")
            pending = manifest["frames"][manifest["seed_count"]:]
            completed_now = 0
            for start in range(0, len(pending), manifest["batch_size"]):
                rows = pending[start:start + manifest["batch_size"]]
                number = start // manifest["batch_size"] + 1
                selection = batch_selection(root, manifest, number, rows)
                output = root / "batches" / f"{number:04d}-run"
                status = read_json(output / "status.json") if (output / "status.json").exists() else {}
                if status.get("status") != "complete":
                    if shutil.disk_usage(root).free < args.minimum_free_gb * 1024**3:
                        raise RuntimeError("Low disk space; stopping before next batch")
                    write_json(root / "active-batch.json", dict(number=number, selection=str(selection),
                               output=str(output), started_utc=utc_now()))
                    labeler.run(SimpleNamespace(selection=selection, output=output, resume=output.exists(),
                                                limit=args.pilot_limit, panels=12))
                    status = read_json(output / "status.json")
                    completed_now += 1
                run_manifest = read_json(output / "manifest.json")
                if run_manifest["contract"]["selection_sha256"] != sha256(selection):
                    raise ValueError("Batch selection differs")
                for row in rows[:status["processed"]]:
                    items.append(register_record(root, manifest, row, output, run_manifest))
                publish(root, manifest, items, "running")
                if status["status"] != "complete" or (args.max_batches and completed_now >= args.max_batches):
                    return publish(root, manifest, items, "paused_after_bounded_run")
            return publish(root, manifest, items, "screening_complete")
        except BaseException as exc:
            write_json(root / "failure.json", dict(error=type(exc).__name__, detail=str(exc), updated_utc=utc_now()))
            # Do not replace the last good count with a partial resume scan.
            progress = read_json(root / "progress.json") if (root / "progress.json").exists() else {}
            write_json(root / "progress.json", {**progress, "state": "stopped_on_error", "error": str(exc), "updated_utc": utc_now()})
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    for name in ("source", "dataset", "split", "seed-run", "exclusions", "output"):
        prepare_parser.add_argument("--" + name, type=Path, required=True)
    prepare_parser.add_argument("--seed", type=int, default=20261121)
    prepare_parser.add_argument("--target", type=int, default=10000)
    prepare_parser.add_argument("--batch-size", type=int, default=1000)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--campaign", type=Path, required=True)
    run_parser.add_argument("--pilot-limit", type=int, default=0)
    run_parser.add_argument("--max-batches", type=int, default=0)
    run_parser.add_argument("--minimum-free-gb", type=float, default=20)
    args = parser.parse_args()
    if args.command == "run" and (args.pilot_limit < 0 or args.max_batches < 0 or args.minimum_free_gb < 0):
        parser.error("Limits must be nonnegative")
    result = prepare(args) if args.command == "prepare" else execute(args)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
