"""Screen every distinct inventory image once; preserve strict passes and deferred cases."""
import argparse
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import random
import shutil

from run_single_corridor_campaign import (
    Detector, Image, cv2, digest_json, read_json, safe_file, sha256, utc_now, workspace, write_json,
)


def run(history, output, batch_size):
    previous = history / "strict-pass-10000"
    inventory = history / "series5-5CD-labeling/manifest.json"
    policy = read_json(previous / "policy.json")
    contract = policy["contract"]
    if sha256(inventory) != contract["inventory"] or digest_json(contract) != policy["identity"]:
        raise ValueError("Source inventory or previous contract changed")
    for name, expected in contract["code"].items():
        if sha256(workspace.source_path(name)) != expected:
            raise ValueError(f"Screening implementation changed: {name}")
    inv = read_json(inventory)
    frames = {r["id"]: r for r in inv["frames"]}
    if len(frames) != inv["count"]:
        raise ValueError("Duplicate inventory key")
    source = Path(inv["source"])
    output.mkdir(parents=True, exist_ok=True)
    lock = (output / "worker.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    mask_dir, loops = output / "masks", output / "loops"
    mask_dir.mkdir(exist_ok=True)
    loops.mkdir(exist_ok=True)
    identity = digest_json(dict(screen=policy["identity"], inventory=sha256(inventory), version=1))
    known, counts = set(), Counter()

    def register(entry, root):
        fid, status = entry["id"], entry["status"]
        if fid not in frames or fid in known or status not in ("candidate", "deferred"):
            raise ValueError(f"Invalid screening record: {fid}")
        if status == "candidate" and sha256(safe_file(root, entry["candidates"])) != entry["mask_sha256"]:
            raise ValueError(f"Changed mask: {fid}")
        known.add(fid)
        counts[status] += 1

    def publish(state):
        summary = dict(state=state, updated_utc=utc_now(), files=inv["file_count"], unique=len(frames),
                       screened=len(known), passed=counts["candidate"], needs_repair=counts["deferred"],
                       unscreened=len(frames)-len(known), new_loops=loop, identity=identity)
        write_json(output / "progress.json", summary)
        print(json.dumps(summary), flush=True)

    for path in sorted((previous / "loops").glob("*.json")):
        receipt = read_json(path)
        if receipt["identity"] != policy["identity"]:
            raise ValueError("Unexpected earlier loop")
        for entry in receipt["records"]:
            register(entry, previous)
    if counts["candidate"] != 10000:
        raise ValueError("Incomplete original campaign")
    loop = 0
    for path in sorted(loops.glob("*.json")):
        loop += 1
        receipt = read_json(path)
        if path.name != f"{loop:05d}.json" or receipt["identity"] != identity:
            raise ValueError("Incomplete or incompatible continuation")
        for entry in receipt["records"]:
            register(entry, output)
    pending = sorted(frames.keys()-known)
    random.Random(20261123).shuffle(pending)
    write_json(output / "sources.json", dict(inventory=str(inventory), original_loops=str(previous/"loops"),
               new_loops=str(loops), identity=identity, policy="Screening only. No split assignment or training."))
    publish("screening")
    try:
        detector = Detector() if pending else None
        for start in range(0, len(pending), batch_size):
            if shutil.disk_usage(output).free < 20*1024**3:
                raise OSError("Less than 20 GiB free")
            batch = []
            for fid in pending[start:start+batch_size]:
                r = frames[fid]
                photo = safe_file(source, r["image"])
                if sha256(photo) != fid:
                    raise ValueError(f"Source image changed: {fid}")
                with Image.open(photo) as im:
                    labels, reasons, detail = detector.predict(im.convert("RGB"))
                entry = dict(id=fid, image=r["image"], status="deferred", reasons=reasons, human_verified=False)
                if labels is not None:
                    dest = mask_dir / (fid+".png")
                    tmp = dest.with_suffix(".tmp.png")
                    if not cv2.imwrite(str(tmp), labels, [cv2.IMWRITE_PNG_COMPRESSION,3]):
                        raise OSError(tmp)
                    tmp.replace(dest)
                    entry.update(status="candidate", candidates=str(dest.relative_to(output)),
                                 mask_sha256=sha256(dest), **detail)
                batch.append(entry)
            loop += 1
            write_json(loops / f"{loop:05d}.json", dict(identity=identity, records=batch))
            for entry in batch:
                register(entry, output)
            publish("screening")
        publish("requires_repair" if counts["deferred"] else "screening_complete")
    except BaseException:
        publish("stopped")
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("history", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--batch-size", type=int, default=128)
    a = p.parse_args()
    if a.batch_size < 1:
        p.error("batch size must be positive")
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    cv2.setNumThreads(1)
    run(a.history.resolve(), a.output.resolve(), a.batch_size)
