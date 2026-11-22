#!/usr/bin/env python3
"""Run six frozen native SAM prompt recipes on the existing ten-frame audit."""

import argparse
from pathlib import Path
import subprocess
import sys

from compare_sam31_sidewalk import COMMIT, REVISION, SAM3_REVISION
from compare_sam3_sidewalk import output_path, validate_inputs
from label_grounded_sam2 import sha256, utc_now, write_json

PROMPTS = ("sidewalk", "sidewalk pavement", "concrete sidewalk")
THRESHOLD = .4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-root", type=Path, default=Path.home() / "sidewalkpilot-labels")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approval-status", choices=("confirmed", "not-confirmed"), required=True)
    args = parser.parse_args()
    root = args.labels_root.resolve()
    audit = root / "implementation-audit-v17"
    selection = validate_inputs(audit)
    out = output_path(args.output, [Path(selection["source"]), Path(selection["baseline"]), audit,
                                   root / "sam3-diagnostic-v18", root / "sam31-image-diagnostic-v20"])
    runner = Path(__file__).with_name("compare_sam31_sidewalk.py")
    cache = Path.home() / ".cache/huggingface/hub"
    snapshot = cache / "models--facebook--sam3/snapshots" / SAM3_REVISION
    common = [sys.executable, str(runner), "--audit", str(audit),
              "--source-code", str(root / "sam3-diagnostic-v18/dependencies/sam3"),
              "--runtime", str(root / "sam31-image-diagnostic-v20/runtime"),
              "--hf-runtime", str(root / "sam3-diagnostic-v18/runtime"),
              "--hf-snapshot", str(snapshot),
              "--sam3-results", str(root / "sam3-diagnostic-v18/results"),
              "--approval-status", args.approval_status, "--score-threshold", str(THRESHOLD)]
    recipes = []
    for model in ("sam3", "sam31"):
        checkpoint = (snapshot / "sam3.pt" if model == "sam3" else
                      cache / "models--facebook--sam3.1/snapshots" / REVISION / "sam3.1_multiplex.pt")
        for index, prompt in enumerate(PROMPTS, 1):
            key = f"{model}-p{index}"
            command = [*common, "--checkpoint", str(checkpoint), "--output", str(out / key), "--prompt", prompt]
            if model == "sam3":
                command.append("--native-sam3-control")
            recipes.append({"key": key, "model": model, "prompt": prompt, "command": command})
    out.mkdir(parents=True)
    plan = {"created_utc": utc_now(), "recipes": recipes, "score_threshold": THRESHOLD,
            "mask_threshold": .5, "official_source_commit": COMMIT,
            "selection_sha256": sha256(audit / "comparison/selection.json"),
            "runner_sha256": sha256(runner), "sweep_runner_sha256": sha256(Path(__file__)),
            "scope": "Same ten development images, six fixed recipes. No reference pixels supplied to inference.",
            "status": "running"}
    write_json(out / "sweep.json", plan)
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    for recipe in recipes:
        print(f'START {recipe["key"]}: {recipe["prompt"]}', flush=True)
        with (out / f'{recipe["key"]}.log').open("w") as log:
            result = subprocess.run(recipe["command"], stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            plan.update(status="failed", failed_recipe=recipe["key"], exit_code=result.returncode)
            write_json(out / "sweep.json", plan)
            raise SystemExit(f'Failed {recipe["key"]}; see {out / (recipe["key"] + ".log")}')
        print(f'COMPLETE {recipe["key"]}', flush=True)
    validate_inputs(audit)
    plan.update(status="complete", finished_utc=utc_now())
    write_json(out / "sweep.json", plan)


if __name__ == "__main__":
    main()
