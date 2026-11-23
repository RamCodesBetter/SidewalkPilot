#!/usr/bin/env python3
"""Move complete local review bundles into the organized layout, without deletion."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

REVIEW_FOLDERS = (
    "5.a-test", "5.a-vs-5.b", "before-after", "correction-results", "failure-analysis",
    "implementation-audit", "method-comparison", "paired-review", "random-30-comparison",
    "reference-comparison", "targeted-corrections",
)
LEGACY_ITEMS = (
    "images", "masks", "overlays", "records", "CORRECTIONS.txt", "READ-ME.txt",
    "correction-selection.json", "integrity-check.json", "manifest.json", "package.json",
    "selection.json", "summary.json", "visual-qa.json",
)
SCHEMA = "sidewalkpilot-workspace-layout-v1"


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def snapshot(path):
    if path.is_symlink():
        raise ValueError(f"Refusing to move a symlink: {path}")
    if path.is_file():
        return {".": digest(path)}
    files = {}
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise ValueError(f"Refusing nested symlink: {item}")
        if item.is_file() and item.name != ".DS_Store":
            files[item.relative_to(path).as_posix()] = digest(item)
    return files


def safe_destination(root, relative):
    target = root / relative
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Destination escapes the workspace: {target}")
    for item in (target, *target.parents):
        if item == root:
            break
        if item.is_symlink():
            raise ValueError(f"Destination contains a symlink: {item}")
    return target


def plan(root):
    mapping = [(name, f"reviews/{name}") for name in REVIEW_FOLDERS]
    mapping += [(name, f"reviews/legacy-class1/{name}") for name in LEGACY_ITEMS]
    mapping += [("5.c-architecture", "docs/5.c-architecture")]
    moves = []
    for old, new in mapping:
        source, target = root / old, safe_destination(root, new)
        if not source.exists() and not source.is_symlink():
            continue
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Both old and new paths exist; refusing to merge: {source} -> {target}")
        moves.append(dict(old=old, new=new, files=snapshot(source)))
    return moves


def organize(root, apply=False):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Workspace must be a directory")
    moves = plan(root)
    result = dict(schema=SCHEMA, root=str(root), moved_items=len(moves),
                  verified_files=sum(len(item["files"]) for item in moves), applied=False)
    if not apply:
        result["moves"] = [{"from": row["old"], "to": row["new"]} for row in moves]
        return result
    journal = root / "workspace-migration.json"
    if journal.is_symlink():
        raise ValueError("Migration journal must not be a symlink")
    temporary = journal.with_suffix(".tmp")
    if temporary.exists() or temporary.is_symlink():
        raise FileExistsError(f"Inspect an interrupted migration journal before continuing: {temporary}")
    for name in ("reviews", "docs"):
        target = safe_destination(root, name)
        if target.exists() and not target.is_dir():
            raise FileExistsError(f"Workspace category is not a directory: {target}")
    history = json.loads(journal.read_text()) if journal.exists() else {"schema": SCHEMA, "runs": []}
    if history.get("schema") != SCHEMA or not isinstance(history.get("runs"), list):
        raise ValueError("Existing migration journal has an unexpected format")
    completed = []
    try:
        for row in moves:
            target = safe_destination(root, row["new"])
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"Destination appeared during migration: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            (root / row["old"]).rename(target)
            completed.append(row)
            if snapshot(target) != row["files"]:
                raise RuntimeError(f"File contents changed during migration: {target}")
    except Exception:
        for row in reversed(completed):
            (root / row["new"]).rename(root / row["old"])
        raise
    for name in ("reviews", "docs"):
        safe_destination(root, name).mkdir(exist_ok=True)
    # The root taxonomy was tracked source; keep a copy with the legacy data too.
    legacy = root / "reviews/legacy-class1"
    extras = []
    if legacy.is_dir():
        assets = [(root / "tools/configs/taxonomy.json", legacy / "taxonomy.json")]
        assets += [(root / "tools/review" / name, legacy / name) for name in
                   ("index.html", "corrections.css", "corrections.js", "lucide.min.js", "LUCIDE-LICENSE.txt")]
        for source, target in assets:
            if source.is_file() and not target.exists():
                safe_destination(root, target.relative_to(root))
                shutil.copy2(source, target)
                if digest(source) != digest(target):
                    raise RuntimeError(f"Copy verification failed: {target}")
                extras.append(str(target.relative_to(root)))
    if moves or extras:
        history["runs"].append(dict(at=datetime.now(timezone.utc).isoformat(), moves=moves, copied=extras))
        with temporary.open("x") as handle:
            json.dump(history, handle, indent=2)
            handle.write("\n")
        temporary.replace(journal)
    result.update(applied=True, copied=extras)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--apply", action="store_true", help="Without this flag, print a verified dry-run plan")
    args = parser.parse_args()
    print(json.dumps(organize(args.root, args.apply), indent=2))


if __name__ == "__main__":
    main()
