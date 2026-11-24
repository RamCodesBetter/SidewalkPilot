"""Build one offline comparison from a reproducible sample of the frozen C/E test split."""
import argparse
import base64
import json
from pathlib import Path
import random
import re
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import workspace
workspace.activate()
import convnext_tiny_unet
from label_grounded_sam2 import digest_json, sha256, write_json
from package_visual_comparison import encode_labels
from prepare_reviewed_dataset import safe_file
from series_5_a_sidewalkpilot_trainer import SidewalkDataset, autocast, load_checkpoint


ASSETS = ("beta.html", "beta.js", "beta.css", "comparison.css", "model_metrics.js",
          "lucide.min.js", "LUCIDE-LICENSE.txt")


def mask_record(path, root, labels):
    return {"path": str(path.relative_to(root)), "sha256": sha256(path),
            "positive_pixels": int((labels == 1).sum()),
            "ignored_pixels": int((labels == 255).sum()), "rle": encode_labels(labels)}


def sample_rows(data, seed, count):
    split_path, manifest_path = data / "split.json", data / "manifest.json"
    split = json.loads(split_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if manifest["schema"] != "sidewalkpilot-campaign10k-v1" or sha256(manifest_path) != split["manifest_sha256"]:
        raise ValueError("Expected the bound campaign dataset and split")
    parts = split["partitions"]
    test = set(parts["test"])
    if len(test) != 1000 or len(parts["test"]) != 1000 or test.intersection(parts["train"]) or test.intersection(parts["validation"]):
        raise ValueError("Wrong or overlapping test partition")
    rows = {r["id"]: r for r in manifest["records"]}
    chosen = random.Random(seed).sample(sorted(test), count)
    return [rows[i] for i in chosen], dict(manifest_sha256=split["manifest_sha256"], split_sha256=sha256(split_path))


@torch.inference_mode()
def package(data, output, checkpoints, seed, count, device, df_split=None):
    if output.exists():
        raise FileExistsError(output)
    rows, identity = sample_rows(data, seed, count)
    df_identity = None
    if any(name[2:3] in ("D", "F") for name, _ in checkpoints):
        if df_split is None:
            raise ValueError("D/F comparison requires the training run's frozen --df-split")
        split = json.loads(df_split.read_text())
        df_identity = dict(manifest_sha256=split["manifest_sha256"], split_sha256=sha256(df_split))
        old = json.loads((data / "split.json").read_text())["partitions"]
        parts = {k:set(split["partitions"][k]) for k in ("train","validation","test")}
        if (any(not set(old[k]) <= parts[k] for k in parts) or parts["test"] & parts["train"]
                or parts["test"] & parts["validation"] or parts["train"] & parts["validation"]):
            raise ValueError("D/F split does not preserve the C/E partitions")
    frames = []
    manifest = dict(schema="sidewalkpilot-model-lab-v1", partition="test", count=count,
                    population=1000, seed=seed, data_identity=identity, models={}, frames=frames,
                    reference_policy="Original SAM 3 pseudo-labels. Ignore 255; never infer missing background.",
                    prediction_policy="Native-size bilinear logits then raw argmax; no filtering.")
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        root = Path(tmp) / "viewer"
        for i, r in enumerate(rows, 1):
            image, mask = safe_file(data, r["image"]), safe_file(data, r["mask"])
            if sha256(image) != r["id"] or sha256(mask) != r["mask_sha256"]:
                raise ValueError("Input pair changed")
            photo, ref = root / "images" / image.name, root / "references" / f"{i:03}.png"
            for src, dest in [(image, photo), (mask, ref)]:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
            with Image.open(ref) as im:
                labels = np.array(im)
                size = im.size
            with Image.open(photo) as im:
                if im.size != size or labels.ndim != 2 or not set(np.unique(labels)) <= {0, 1, 255}:
                    raise ValueError("Invalid reference")
            frames.append(dict(id=r["id"], source_sha256=r["id"], name=image.name, size=size,
                               image=str(photo.relative_to(root)), supervision=r["supervision"],
                               recording_run=r["recording_run"], reference=mask_record(ref, root, labels), predictions={}))
        for name, path in checkpoints:
            key = name.removeprefix("5.").lower()
            if not re.fullmatch(r"5\.[A-F](?:[bs])?", name) or key in manifest["models"]:
                raise ValueError(f"Invalid or duplicate checkpoint label {name}")
            convnext = name[2] in "CDEF"
            expected = df_identity if name[2] in "DF" else identity
            model, state = load_checkpoint(path, model_definition=convnext_tiny_unet if convnext else None)
            cfg = state["config"]
            if (cfg["smoke_only"] or cfg["model_name"] != name[:3] or
                    (convnext and (state["data_identity"] != expected or path.stem != name))):
                raise ValueError(f"Checkpoint identity mismatch: {path}")
            model.to(device).eval()
            size = [cfg["width"], cfg["height"]]
            dataset = SidewalkDataset(data, rows, size, original_targets=True)
            manifest["models"][key] = dict(name=name, epoch=state["epoch"], checkpoint_sha256=sha256(path),
                                           input_size=size, precision=cfg["precision"], data_identity=state["data_identity"])
            folder = root / "predictions" / key
            folder.mkdir(parents=True)
            for i, f in enumerate(frames):
                x, y, _, _ = dataset[i]
                with autocast(device, cfg["precision"]):
                    scores = model(x.unsqueeze(0).to(device))["out"]
                if not torch.isfinite(scores).all():
                    raise ValueError("Nonfinite logits")
                labels = F.interpolate(scores.float(), size=y.shape, mode="bilinear", align_corners=False)
                labels = labels.argmax(1)[0].cpu().numpy().astype(np.uint8)
                dest = folder / f"{i+1:03}.png"
                Image.fromarray(labels).save(dest)
                f["predictions"][key] = {**mask_record(dest, root, labels),
                    "png_base64": base64.b64encode(dest.read_bytes()).decode("ascii")}
            print(f"{name} epoch {state['epoch']}: {count} predictions", flush=True)
        manifest["package_id"] = digest_json(manifest)
        write_json(root / "manifest.json", manifest)
        (root / "data.js").write_text("window.BETA_COMPARISON_DATA="+json.dumps(manifest,separators=(",",":"))+";\n")
        for name in ASSETS:
            shutil.copyfile(workspace.TOOLS / "review" / name, root / ("index.html" if name=="beta.html" else name))
        root.rename(output)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dataset", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--checkpoint", nargs=2, action="append", required=True, metavar=("NAME","PATH"))
    p.add_argument("--seed", type=int, default=20261123)
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--df-split", type=Path)
    args = p.parse_args()
    package(args.dataset, args.output, [(n, Path(f)) for n,f in args.checkpoint],
            args.seed, args.count, torch.device("cuda"), args.df_split)
