#!/usr/bin/env python3
"""dataset_scene_tags.py -- semantic scene tags for the Series-3 dataset via zero-shot CLIP.

The SidewalkPilotV3 backbone clusters by *steering geometry* -- it can't see "wet" or
"orange leaves". This tags every image by APPEARANCE instead: CLIP (openai/clip-vit-base-
patch32) scores each image against ~two-dozen natural scene descriptions and assigns the
best-matching one (zero-shot, no training). Reports the count per tag + a sample gallery.

CLIP image embeddings are cached (dataset_clip_embeddings.npz) so you can edit TAGS and
re-run in seconds. Output: printed table + dataset_scene_tags.html (self-contained).

Usage:
    python3 code/test_files/data/dataset_scene_tags.py                 # all images
    python3 code/test_files/data/dataset_scene_tags.py --limit 3000    # quick pass
"""
import argparse
import base64
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch

import dataset_cosine_similarity as cos                        # reuse load_index / dataset path

CACHE = Path(__file__).resolve().parent / "dataset_clip_embeddings.npz"
CLIP_NAME = "openai/clip-vit-base-patch32"
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

# ~26 sidewalk scene descriptions (surface / lighting / vegetation / features). Edit freely.
TAGS = [
    "a bright white concrete sidewalk",
    "a dark gray asphalt path",
    "a wet sidewalk after rain",
    "a puddle of water on the path",
    "a cracked and patched sidewalk",
    "a brick or paver walkway",
    "a sidewalk in bright direct sunlight",
    "a sidewalk covered in dark tree shadows",
    "dappled sunlight through trees on the path",
    "a sidewalk on an overcast cloudy day",
    "a sidewalk at dusk or night",
    "orange autumn leaves covering the path",
    "leaves and debris scattered on the sidewalk",
    "a hedge or bushes overhanging the sidewalk",
    "green grass beside the sidewalk",
    "tall trees lining the sidewalk",
    "flowers or a garden next to the path",
    "snow or ice on the ground",
    "a driveway crossing the sidewalk",
    "the edge of a street with a curb",
    "a parked car next to the sidewalk",
    "a person walking on the sidewalk",
    "a fence running alongside the path",
    "a mailbox or utility pole beside the path",
    "a house or building beside the sidewalk",
    "an open grassy field or park",
    "a clean empty sidewalk going straight",
]


def load_clip(device):
    from transformers import CLIPModel, CLIPProcessor
    model = CLIPModel.from_pretrained(CLIP_NAME).to(device).eval()
    proc = CLIPProcessor.from_pretrained(CLIP_NAME, use_fast=True)
    return model, proc


def preprocess(img_bgr):
    rgb = cv2.cvtColor(cv2.resize(img_bgr, (224, 224), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    x = (rgb.astype(np.float32) / 255.0 - CLIP_MEAN) / CLIP_STD
    return np.transpose(x, (2, 0, 1))


@torch.no_grad()
def embed_images(model, dataset_dir, names, device, batch_size):
    import time
    embs = np.zeros((len(names), model.config.projection_dim), dtype=np.float32)
    keep = np.ones(len(names), dtype=bool)
    buf, idx = [], []
    t0 = time.time()

    def flush():
        if not buf:
            return
        px = torch.from_numpy(np.stack(buf)).to(device)
        f = model.get_image_features(pixel_values=px)
        f = torch.nn.functional.normalize(f, dim=1)
        embs[idx] = f.cpu().numpy()
        buf.clear(); idx.clear()

    for i, name in enumerate(names):
        im = cv2.imread(str(dataset_dir / name), cv2.IMREAD_COLOR)
        if im is None:
            keep[i] = False
            continue
        buf.append(preprocess(im)); idx.append(i)
        if len(buf) >= batch_size:
            flush()
        if (i + 1) % 5000 == 0:
            print(f"[clip] embedded {i+1}/{len(names)} ({(i+1)/max(1e-6,time.time()-t0):.0f} img/s)", flush=True)
    flush()
    print(f"[clip] embedded {int(keep.sum())} images in {time.time()-t0:.0f}s", flush=True)
    return embs, keep


@torch.no_grad()
def text_embeds(model, proc, tags, device):
    tok = proc(text=tags, return_tensors="pt", padding=True).to(device)
    t = torch.nn.functional.normalize(model.get_text_features(**tok), dim=1)
    return t.cpu().numpy()


def thumb_b64(dataset_dir, name, width=150):
    img = cv2.imread(str(dataset_dir / name), cv2.IMREAD_COLOR)
    if img is None:
        return ""
    h, w = img.shape[:2]
    img = cv2.resize(img, (width, max(1, int(h * width / w))), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
    return base64.b64encode(jpg.tobytes()).decode("ascii") if ok else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=cos.DEFAULT_DATASET)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--samples", type=int, default=8, help="sample thumbnails per tag in the HTML")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "dataset_scene_tags.html")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    device = torch.device(args.device)

    names, steers = cos.load_index(args.dataset, args.limit)
    model, proc = load_clip(device)

    if CACHE.is_file() and not args.no_cache:
        z = np.load(CACHE, allow_pickle=True)
        if len(z["names"]) == len(names):
            print(f"[clip] loaded cached image embeddings {z['embs'].shape}", flush=True)
            embs, names = z["embs"], list(z["names"])
        else:
            embs = None
    else:
        embs = None
    if embs is None:
        embs, keep = embed_images(model, args.dataset, names, device, args.batch_size)
        names = [names[i] for i in range(len(names)) if keep[i]]
        embs = embs[keep]
        np.savez(CACHE, embs=embs, names=np.array(names))
        print(f"[clip] cached -> {CACHE.name}", flush=True)
    names = np.array(names)

    txt = text_embeds(model, proc, TAGS, device)               # [T,512]
    scale = float(model.logit_scale.exp().item())
    sims = embs @ txt.T                                         # cosine [N,T]
    best = sims.argmax(1)
    probs = torch.softmax(torch.from_numpy(sims * scale), dim=1).numpy()
    conf = probs[np.arange(len(best)), best]

    rows = []
    for t in range(len(TAGS)):
        m = best == t
        n = int(m.sum())
        if not n:
            continue
        idx = np.where(m)[0]
        top = idx[np.argsort(-conf[idx])]                      # highest-confidence samples first
        rows.append({"tag": TAGS[t], "n": n, "conf": float(conf[idx].mean()),
                     "samples": [names[j] for j in top[:args.samples]]})
    rows.sort(key=lambda r: -r["n"])

    print(f"\n{'count':>7} {'avg%':>5}  scene tag")
    print("-" * 60)
    for r in rows:
        print(f"{r['n']:>7} {r['conf']*100:>4.0f}%  {r['tag']}", flush=True)
    print(f"\ntotal images: {len(names):,}  |  {len(TAGS)} candidate tags (top-1 assignment)", flush=True)

    # HTML
    secs = []
    for r in rows:
        thumbs = "".join(f'<img src="data:image/jpeg;base64,{thumb_b64(args.dataset, s)}"/>' for s in r["samples"])
        secs.append(f'<div class="tag"><div class="hd"><b>{r["tag"]}</b>'
                    f'<span class="n">{r["n"]:,} imgs &middot; avg {r["conf"]*100:.0f}%</span></div>'
                    f'<div class="imgs">{thumbs}</div></div>')
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>SidewalkPilot scene tags</title>
<style>
 body{{background:#0e1116;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}}
 h1{{margin:0 0 4px}} .sub{{color:#8b98a9;font-size:13px;margin:0 0 16px}}
 .tag{{background:#161b22;border:1px solid #263041;border-radius:8px;padding:10px 12px;margin:10px 0}}
 .hd{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}}
 .n{{color:#2f81f7;font-size:13px}} .imgs{{display:flex;gap:6px;overflow-x:auto}}
 .imgs img{{height:96px;border-radius:5px}}
</style></head><body>
<h1>SidewalkPilot dataset — scene tags (zero-shot CLIP)</h1>
<p class="sub">{CLIP_NAME} &middot; {len(names):,} images &middot; {len(TAGS)} tags, top-1 assignment &middot;
 sorted by count &middot; samples = highest-confidence per tag</p>
{"".join(secs)}</body></html>"""
    args.out.write_text(html)
    print(f"[clip] wrote {args.out} ({args.out.stat().st_size/1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
