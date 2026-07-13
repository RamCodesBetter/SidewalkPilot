#!/usr/bin/env python3
"""hf_upload_dataset.py — push SidewalkPilot dataset artifacts to Hugging Face.

Auth (NO env vars): run `huggingface-cli login` (or `hf auth login`) ONCE with a WRITE
token from https://huggingface.co/settings/tokens. This script uses the cached token.
Install the CLI if missing:  pip install -U 'huggingface_hub[cli]'

Tar archives and label manifests are published at the dataset repo root. Extracting the
archive locally recreates the dataset folder expected by the trainer. __pycache__/artifacts
are skipped by default.

Examples (run from the repo root):

    # Series 3 loose upload (small datasets only)
  python3 code/test_files/hf_upload_dataset.py \
    --repo   ram-shreyas-naik-sabavat/SidewalkPilot_v3 \
    --folder code/ai_models_datasets/series_3

  # Series 1 & 2 is already published; re-push only if the local folder changed:
  python3 code/test_files/hf_upload_dataset.py \
    --repo   ram-shreyas-naik-sabavat/SidewalkPilot_v1_and_v2 \
    --folder code/ai_models_datasets/series_1_and_2
"""
import argparse
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Upload a dataset folder to a Hugging Face dataset repo")
    ap.add_argument("--repo", required=True, help="dataset repo id, e.g. user/SidewalkPilot_v3")
    ap.add_argument("--folder", help="local dataset folder for LOOSE upload (images + labels.json)")
    ap.add_argument("--tar", help="PREFERRED for big image sets: upload ONE tarball (1 commit). HF free "
                                  "tier caps ~128 commits/hour, so loose uploads of 50k+ files get "
                                  "throttled/killed. Pack the images into a tar and push that instead.")
    ap.add_argument("--tar-in-repo", help="repo path for --tar (default: tar basename at repo root)")
    ap.add_argument("--labels", help="labels.json to publish at repo root")
    ap.add_argument("--card", help="local README.md to publish as the dataset card (repo root)")
    ap.add_argument("--extra", nargs="*", default=[], help="extra files to upload to the repo root")
    ap.add_argument("--ignore", nargs="*", default=[], help="extra glob patterns to skip")
    ap.add_argument("--private", action="store_true", help="create the repo as private")
    args = ap.parse_args()

    ignore = ["**/__pycache__/**", "*.pyc", "**/.DS_Store", ".DS_Store",
              "*.pth", "*.onnx", "*.engine"] + list(args.ignore)

    try:
        from huggingface_hub import HfApi, whoami
    except ImportError:
        sys.exit("huggingface_hub missing:  pip install -U 'huggingface_hub[cli]'")

    try:
        who = whoami()
    except Exception:
        sys.exit("Not logged in. Run:  huggingface-cli login   (paste a WRITE token)")
    print(f"logged in as: {who.get('name', '?')}")

    if not args.folder and not args.tar:
        sys.exit("give either --tar (preferred for image sets) or --folder")

    api = HfApi()
    api.create_repo(args.repo, repo_type="dataset", exist_ok=True, private=args.private)

    if args.tar:
        tarp = Path(args.tar)
        if not tarp.is_file():
            sys.exit(f"no such tar: {tarp}")
        dest = args.tar_in_repo or tarp.name
        gb = tarp.stat().st_size / 1e9
        print(f"uploading tar {tarp} ({gb:.1f} GB) -> {dest}  (single commit)...")
        api.upload_file(path_or_fileobj=str(tarp), path_in_repo=dest,
                        repo_id=args.repo, repo_type="dataset")
        if args.labels:
            lp = Path(args.labels)
            if lp.is_file():
                api.upload_file(path_or_fileobj=str(lp), path_in_repo="labels.json",
                                repo_id=args.repo, repo_type="dataset")
                print("published labels.json -> labels.json")
            else:
                print(f"[skip] labels not found: {lp}")
    else:
        folder = Path(args.folder)
        if not folder.is_dir():
            sys.exit(f"no such folder: {folder}")
        print(f"uploading folder {folder} -> {args.repo}  (large; resumable; ignoring {ignore})...")
        api.upload_large_folder(repo_id=args.repo, repo_type="dataset", folder_path=str(folder),
                                ignore_patterns=ignore)

    if args.card and Path(args.card).is_file():
        api.upload_file(path_or_fileobj=args.card, path_in_repo="README.md",
                        repo_id=args.repo, repo_type="dataset")
        print("published dataset card -> README.md")

    for ex in args.extra:
        p = Path(ex)
        if p.is_file():
            api.upload_file(path_or_fileobj=str(p), path_in_repo=p.name,
                            repo_id=args.repo, repo_type="dataset")
            print(f"uploaded extra file -> {p.name}")
        else:
            print(f"[skip] extra file not found: {ex}")

    print(f"done: https://huggingface.co/datasets/{args.repo}")


if __name__ == "__main__":
    main()
