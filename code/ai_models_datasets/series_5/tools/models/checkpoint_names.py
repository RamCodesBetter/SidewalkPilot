"""Publish named end/best snapshots without promoting incomplete training runs."""

import errno
import math
from pathlib import Path
import re
import shutil
from uuid import uuid4

from label_grounded_sam2 import write_json
from prepare_reviewed_dataset import read_json


def checkpoint_names(model_name):
    if not re.fullmatch(r"5\.(?:[A-Z]|[0-9]+)", model_name):
        raise ValueError("Expected a Series 5 base name such as 5.C or 5.0")
    return {"end": model_name, "best_iou": model_name + "b", "smart": model_name + "s"}


def snapshot(source, destination):
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        try:
            # Atomic checkpoint replacement leaves this inode intact; a symlink would move.
            temporary.hardlink_to(source)
        except OSError as error:
            if error.errno not in (errno.EXDEV, errno.ENOTSUP, errno.EPERM):
                raise
            shutil.copy2(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def publish_completed_run(output, model_name):
    output = Path(output)
    names = checkpoint_names(model_name)
    config = read_json(output / "config.json")
    status = read_json(output / "status.json")
    history = read_json(output / "history.json")
    if (config.get("model_name") != model_name or config.get("smoke_only") is not False
            or status.get("status") != "complete"):
        raise ValueError("Named checkpoints require a completed, non-smoke run of the matching model")
    if (not history or status.get("epochs_completed") != len(history)
            or [row["epoch"] for row in history] != list(range(1, len(history) + 1))
            or any(not math.isfinite(row["validation_sidewalk_iou"])
                   or not 0 <= row["validation_sidewalk_iou"] <= 1 for row in history)):
        raise ValueError("Incomplete or invalid epoch history")
    # max keeps the first tie, matching the trainer's strict-IoU-improvement rule.
    best = max(history, key=lambda row: row["validation_sidewalk_iou"])
    if status.get("best_validation_sidewalk_iou") != best["validation_sidewalk_iou"]:
        raise ValueError("Completed status and best-IoU history disagree")
    selections = {
        "end": ("last.pt", history[-1], "last completed epoch, including normal early stopping"),
        "best_iou": ("best.pt", best, "maximum validation sidewalk IoU; earliest epoch wins ties"),
    }
    for source, _, _ in selections.values():
        if not (output / source).is_file():
            raise FileNotFoundError(output / source)
    artifacts = {}
    for role, (source, row, criterion) in selections.items():
        filename = names[role] + ".pt"
        snapshot(output / source, output / filename)
        artifacts[role] = dict(model_name=names[role], filename=filename, source=source,
                               epoch=row["epoch"], criterion=criterion,
                               validation_sidewalk_iou=row["validation_sidewalk_iou"])
    artifacts["smart"] = dict(model_name=names["smart"], filename=None, status="reserved",
                               reason="Smart-selection criterion has not been defined or implemented")
    record = dict(schema="sidewalkpilot-checkpoint-selection-v1", model_name=model_name,
                  early_stopped=status.get("early_stopped", False), artifacts=artifacts,
                  selection_partition="validation", test_used_for_selection=False)
    write_json(output / "checkpoint-selection.json", record)
    return record
