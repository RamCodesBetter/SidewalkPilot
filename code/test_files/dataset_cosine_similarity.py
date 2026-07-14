#!/usr/bin/env python3
"""dataset_cosine_similarity.py -- how redundant is the Series-3 dataset, in the MODEL's eyes?

Embeds every image with the SidewalkPilotV3 *backbone* (global-avg-pooled 160-d vector),
L2-normalizes, and finds each image's top-K cosine-nearest look-alikes on the GPU. Writes a
self-contained HTML viewer (base64 thumbnails) with:
  * diversity stats: near-duplicate %, mean top-1 similarity, a top-1-similarity histogram;
  * galleries: the MOST-duplicated anchors, a RANDOM sample, and the MOST-unique anchors,
    each row = the anchor + its nearest neighbours with cosine score + steering label.

"Similar in the model's eyes" == redundant for training -- this is the picture behind the
overfitting story (few unique scenes, many near-identical frames re-sampled).

The best S3 model (v3.2b) is onnx-only, so the backbone is loaded from the newest available
SidewalkPilotV3 .pth (default 3.1b -- same architecture, representative feature space).

Usage:
    python3 dataset_cosine_similarity.py                      # all 57k, writes html next to this file
    python3 dataset_cosine_similarity.py --limit 2000         # quick smoke test
    python3 dataset_cosine_similarity.py --model 3.1 --topk 8 --dup-threshold 0.98
"""
import argparse
import base64
import importlib.util
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

REPO = Path(__file__).resolve().parents[2]                      # code/test_files -> repo root
S3 = REPO / "code" / "ai_models_datasets" / "series_3_and_4"
DEFAULT_DATASET = S3 / "sidewalkpilot_dataset"
TRAINER = S3 / "series_3_sidewalkpilot_trainer.py"
MODELS_DIR = REPO / "code" / "ai_models"
W, H = 320, 180                                                 # SidewalkPilotV3 input


def _load_trainer():
    spec = importlib.util.spec_from_file_location("s3trainer", TRAINER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_backbone(model_version, device):
    """SidewalkPilotV3 backbone with weights from SidewalkPilot-v<version>.pth."""
    net = _load_trainer().SidewalkPilotV3()
    path = MODELS_DIR / f"SidewalkPilot-v{model_version}.pth"
    if not path.is_file():
        raise SystemExit(f"[cos] no {path.name} (S3 .pth). 3.2/3.2b are onnx-only; pass --model 3.1b or 3.1.")
    try:
        ckpt = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
    state = ckpt
    if isinstance(ckpt, dict):
        for k in ("model_state_dict", "state_dict", "model"):
            if k in ckpt and isinstance(ckpt[k], dict):
                state = ckpt[k]
                break
    state = {k.removeprefix("module."): v for k, v in state.items()}
    missing, unexpected = net.load_state_dict(state, strict=False)
    bb_missing = [k for k in missing if k.startswith("backbone.")]
    if bb_missing:
        raise SystemExit(f"[cos] backbone weights didn't load from {path.name}: missing {bb_missing[:4]}...")
    print(f"[cos] backbone loaded from {path.name} (unused head keys: {len(unexpected)})", flush=True)
    backbone = net.backbone.to(device).eval()
    return backbone


def load_index(dataset_dir, limit):
    labels = json.loads((dataset_dir / "labels.json").read_text())
    names = []
    steers = []
    for name, label in labels.items():
        steer = label.get("steering") if isinstance(label, dict) else label
        if steer is None:
            continue
        names.append(name)
        steers.append(float(steer))
    if limit:
        names, steers = names[:limit], steers[:limit]
    return names, np.array(steers, dtype=np.float32)


@torch.no_grad()
def embed_all(backbone, dataset_dir, names, device, batch_size):
    embs = np.zeros((len(names), 160), dtype=np.float32)
    keep = np.ones(len(names), dtype=bool)
    buf, idx = [], []
    t0 = time.time()

    def flush():
        if not buf:
            return
        x = torch.from_numpy(np.stack(buf)).to(device, non_blocking=True)
        v = backbone(x).mean(dim=(2, 3))                       # GAP -> [B,160]
        v = torch.nn.functional.normalize(v, dim=1)
        embs[idx] = v.cpu().numpy()
        buf.clear()
        idx.clear()

    for i, name in enumerate(names):
        img = cv2.imread(str(dataset_dir / name), cv2.IMREAD_COLOR)
        if img is None:
            keep[i] = False
            continue
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        img = (img - 0.5) / 0.5
        buf.append(np.transpose(img, (2, 0, 1)))
        idx.append(i)
        if len(buf) >= batch_size:
            flush()
        if (i + 1) % 5000 == 0:
            r = (i + 1) / max(1e-6, time.time() - t0)
            print(f"[cos] embedded {i+1}/{len(names)}  ({r:.0f} img/s)", flush=True)
    flush()
    print(f"[cos] embedded {int(keep.sum())} images in {time.time()-t0:.0f}s "
          f"({int((~keep).sum())} unreadable)", flush=True)
    return embs, keep


@torch.no_grad()
def knn(embs, device, topk, chunk=4096):
    """Top-K cosine neighbours (self excluded). embs already L2-normalized."""
    E = torch.from_numpy(embs).to(device)                      # [N,160]
    n = E.shape[0]
    nn_idx = np.zeros((n, topk), dtype=np.int64)
    nn_sim = np.zeros((n, topk), dtype=np.float32)
    for s in range(0, n, chunk):
        e = min(s + chunk, n)
        sims = E[s:e] @ E.T                                    # [c,N]
        for r in range(e - s):
            sims[r, s + r] = -2.0                              # mask self
        vals, ids = torch.topk(sims, topk, dim=1)
        nn_idx[s:e] = ids.cpu().numpy()
        nn_sim[s:e] = vals.cpu().numpy()
        print(f"[cos] knn {e}/{n}", flush=True)
    return nn_idx, nn_sim


def thumb_b64(dataset_dir, name, width):
    img = cv2.imread(str(dataset_dir / name), cv2.IMREAD_COLOR)
    if img is None:
        return ""
    h, w = img.shape[:2]
    img = cv2.resize(img, (width, max(1, int(h * width / w))), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
    return base64.b64encode(jpg.tobytes()).decode("ascii") if ok else ""


def pick_anchors(top1, n_dup, n_rand, n_uniq, seed=0):
    order = np.argsort(-top1)                                  # most similar first
    dup = order[:n_dup].tolist()
    uniq = order[::-1][:n_uniq].tolist()
    rng = np.random.default_rng(seed)
    mid = order[n_dup:len(order) - n_uniq]
    rand = rng.choice(mid, size=min(n_rand, len(mid)), replace=False).tolist() if len(mid) else []
    return dup, rand, uniq


def build_html(out, dataset_dir, names, steers, nn_idx, nn_sim, top1, dup_thr,
               anchors, thumb_w, model_version):
    n = len(names)
    dup_frac = float((top1 >= dup_thr).mean())
    # histogram of top-1 similarity
    edges = np.linspace(0.5, 1.0, 11)
    hist, _ = np.histogram(np.clip(top1, 0.5, 1.0), bins=edges)
    hmax = max(1, hist.max())

    need = set()
    for group in anchors.values():
        for a in group:
            need.add(a)
            need.update(int(j) for j in nn_idx[a])
    print(f"[cos] rendering {len(need)} thumbnails...", flush=True)
    tb = {a: thumb_b64(dataset_dir, names[a], thumb_w) for a in need}

    def cell(i, sim=None, is_anchor=False):
        cls = "cell anchor" if is_anchor else "cell"
        cap = f"{sim*100:.1f}%" if sim is not None else "ANCHOR"
        steer = steers[i]
        return (f'<div class="{cls}"><img src="data:image/jpeg;base64,{tb.get(i,"")}"/>'
                f'<div class="cap">{cap}</div><div class="st">steer {steer:.0f}&deg;</div></div>')

    def gallery(title, subtitle, ids):
        rows = []
        for a in ids:
            row = cell(a, is_anchor=True) + "".join(
                cell(int(j), float(s)) for j, s in zip(nn_idx[a], nn_sim[a]))
            rows.append(f'<div class="row">{row}</div>')
        return f'<h2>{title}</h2><p class="sub">{subtitle}</p>{"".join(rows)}'

    bars = "".join(
        f'<div class="bar"><span class="lab">{edges[i]:.2f}</span>'
        f'<div class="fill" style="width:{hist[i]/hmax*100:.1f}%"></div>'
        f'<span class="cnt">{hist[i]}</span></div>' for i in range(len(hist)))

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>SidewalkPilot dataset — cosine similarity</title>
<style>
 body{{background:#0e1116;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}}
 h1{{margin:0 0 4px}} h2{{margin:28px 0 2px;border-top:1px solid #263041;padding-top:18px}}
 .sub{{color:#8b98a9;margin:0 0 12px;font-size:13px}}
 .stats{{display:flex;gap:28px;flex-wrap:wrap;margin:14px 0 8px}}
 .stat{{background:#161b22;border:1px solid #263041;border-radius:8px;padding:10px 16px}}
 .stat b{{font-size:24px;display:block}} .stat span{{color:#8b98a9;font-size:12px}}
 .hist{{max-width:520px;margin:10px 0}}
 .bar{{display:flex;align-items:center;gap:8px;margin:2px 0;font-size:11px}}
 .bar .lab{{width:34px;color:#8b98a9;text-align:right}} .bar .cnt{{color:#8b98a9}}
 .fill{{height:12px;background:linear-gradient(90deg,#2f81f7,#f7768e);border-radius:3px;min-width:1px}}
 .row{{display:flex;gap:8px;overflow-x:auto;padding:8px;background:#12161d;border-radius:8px;margin:8px 0}}
 .cell{{flex:0 0 auto;text-align:center;font-size:11px}}
 .cell img{{width:{thumb_w}px;border-radius:5px;display:block;border:2px solid transparent}}
 .cell.anchor img{{border-color:#f7768e}}
 .cap{{font-weight:600;margin-top:3px}} .st{{color:#8b98a9}}
</style></head><body>
<h1>SidewalkPilot dataset — cosine similarity</h1>
<p class="sub">Embedding: SidewalkPilotV3 (v{model_version}) backbone, global-avg-pooled 160-d, L2-normalized ·
 {n:,} images · near-duplicate threshold cos &ge; {dup_thr:.2f}</p>
<div class="stats">
 <div class="stat"><b>{n:,}</b><span>images embedded</span></div>
 <div class="stat"><b>{dup_frac*100:.1f}%</b><span>have a near-dup (cos&ge;{dup_thr:.2f})</span></div>
 <div class="stat"><b>{float(top1.mean()):.3f}</b><span>mean top-1 cosine</span></div>
 <div class="stat"><b>{float(np.median(top1)):.3f}</b><span>median top-1 cosine</span></div>
</div>
<div class="hist"><div class="sub">top-1 similarity distribution</div>{bars}</div>
{gallery("Most duplicated", "Highest top-1 similarity — the redundant frames the sampler keeps re-showing.", anchors["dup"])}
{gallery("Random sample", "A neutral cross-section of the dataset.", anchors["rand"])}
{gallery("Most unique", "Lowest top-1 similarity — the rarest scenes (what the model sees least).", anchors["uniq"])}
</body></html>"""
    out.write_text(html)
    print(f"[cos] wrote {out}  ({out.stat().st_size/1e6:.1f} MB)", flush=True)
    return dup_frac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--model", default="3.1b", help="SidewalkPilotV3 .pth version for the backbone (3.1b/3.1)")
    ap.add_argument("--topk", type=int, default=6)
    ap.add_argument("--dup-threshold", type=float, default=0.97)
    ap.add_argument("--dup-anchors", type=int, default=60)
    ap.add_argument("--rand-anchors", type=int, default=60)
    ap.add_argument("--uniq-anchors", type=int, default=30)
    ap.add_argument("--thumb-width", type=int, default=150)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--limit", type=int, default=0, help="embed only the first N images (smoke test)")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "dataset_cosine_similarity.html")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    device = torch.device(args.device)
    print(f"[cos] device={device}  dataset={args.dataset}", flush=True)
    backbone = build_backbone(args.model, device)
    names, steers = load_index(args.dataset, args.limit)
    print(f"[cos] {len(names)} labelled images", flush=True)

    embs, keep = embed_all(backbone, args.dataset, names, device, args.batch_size)
    names = [names[i] for i in range(len(names)) if keep[i]]
    steers = steers[keep]
    embs = embs[keep]

    nn_idx, nn_sim = knn(embs, device, args.topk)
    top1 = nn_sim[:, 0]
    dup, rand, uniq = pick_anchors(top1, args.dup_anchors, args.rand_anchors, args.uniq_anchors)
    anchors = {"dup": dup, "rand": rand, "uniq": uniq}
    build_html(args.out, args.dataset, names, steers, nn_idx, nn_sim, top1,
               args.dup_threshold, anchors, args.thumb_width, args.model)


if __name__ == "__main__":
    main()
