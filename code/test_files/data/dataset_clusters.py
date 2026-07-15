#!/usr/bin/env python3
"""dataset_clusters.py -- auto-discover the distinct scene clusters in the Series-3 dataset.

Reuses dataset_cosine_similarity's SidewalkPilotV3-backbone embeddings (160-d, L2-norm,
cached to dataset_embeddings.npz), then runs HDBSCAN (auto cluster count -- you don't pick
K; it also flags diffuse points as noise). For every cluster it prints + renders:
  * size (# images)
  * steering label: mean angle + the 7-bucket spread (HL/L/SL/ST/SR/R/HR)
  * top source runs (the D-code filename prefix)
  * a representative thumbnail (image nearest the cluster centroid)

Writes dataset_clusters.html (self-contained). Cluster count depends on --min-cluster-size.

Usage:
    python3 code/test_files/data/dataset_clusters.py                       # all images, min-cluster-size 50
    python3 code/test_files/data/dataset_clusters.py --min-cluster-size 30 --limit 5000
"""
import argparse
import base64
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch
from sklearn.cluster import HDBSCAN

import dataset_cosine_similarity as cos                        # reuse embed/backbone/index

CACHE = Path(__file__).resolve().parent / "dataset_embeddings.npz"
BUCKETS = [("HL", 0, 45), ("L", 45, 75), ("SL", 75, 85), ("ST", 85, 95),
           ("SR", 95, 105), ("R", 105, 135), ("HR", 135, 180)]


def get_embeddings(args, device):
    names, steers = cos.load_index(args.dataset, args.limit)       # cheap json read
    if CACHE.is_file() and not args.no_cache:
        z = np.load(CACHE, allow_pickle=True)
        if len(z["names"]) == len(names):                          # cache matches this request
            print(f"[clu] loaded cached embeddings: {z['embs'].shape}", flush=True)
            return z["embs"], list(z["names"]), z["steers"]
    backbone = cos.build_backbone(args.model, device)
    embs, keep = cos.embed_all(backbone, args.dataset, names, device, args.batch_size)
    names = [names[i] for i in range(len(names)) if keep[i]]
    steers, embs = steers[keep], embs[keep]
    np.savez(CACHE, embs=embs, names=np.array(names), steers=steers)
    print(f"[clu] cached embeddings -> {CACHE.name}", flush=True)
    return embs, names, steers


def bucket_str(steers_in_cluster):
    n = len(steers_in_cluster)
    parts = []
    for tag, lo, hi in BUCKETS:
        c = int(((steers_in_cluster >= lo) & (steers_in_cluster < hi)).sum())
        if c:
            parts.append(f"{tag}:{c}")
    return " ".join(parts), n


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
    ap.add_argument("--model", default="3.1b")
    ap.add_argument("--min-cluster-size", type=int, default=50)
    ap.add_argument("--min-samples", type=int, default=None)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "dataset_clusters.html")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    device = torch.device(args.device)

    embs, names, steers = get_embeddings(args, device)
    print(f"[clu] clustering {len(names)} points with HDBSCAN(min_cluster_size={args.min_cluster_size})...", flush=True)
    # embeddings are L2-normalized -> euclidean distance is monotonic in cosine distance
    labels = HDBSCAN(min_cluster_size=args.min_cluster_size, min_samples=args.min_samples,
                     metric="euclidean").fit_predict(embs)

    names = np.array(names)
    cluster_ids = sorted(set(labels) - {-1})
    noise = int((labels == -1).sum())
    print(f"\n[clu] {len(cluster_ids)} clusters found  |  {noise} noise (diffuse) points  "
          f"|  {len(names)} total\n", flush=True)

    rows = []
    for cid in cluster_ids:
        m = labels == cid
        idx = np.where(m)[0]
        centroid = embs[idx].mean(0)
        centroid /= (np.linalg.norm(centroid) + 1e-9)
        rep = idx[np.argmax(embs[idx] @ centroid)]                # medoid-ish = nearest to centroid
        bstr, size = bucket_str(steers[idx])
        top_runs = Counter(n.split("__")[0] for n in names[idx]).most_common(3)
        rows.append({"cid": cid, "size": size, "mean": float(steers[idx].mean()),
                     "buckets": bstr, "runs": top_runs, "rep": names[rep]})
    rows.sort(key=lambda r: -r["size"])

    print(f"{'#':>4} {'size':>6}  {'mean°':>6}  {'top run (n)':<20} steering buckets")
    print("-" * 78)
    for r in rows:
        run = f"{r['runs'][0][0]}({r['runs'][0][1]})" if r["runs"] else "-"
        print(f"{r['cid']:>4} {r['size']:>6}  {r['mean']:>6.1f}  {run:<20} {r['buckets']}", flush=True)
    print(f"\nnoise/diffuse (no cluster): {noise}", flush=True)

    # HTML
    cards = []
    for r in rows:
        runs = ", ".join(f"{run} ({c})" for run, c in r["runs"])
        cards.append(
            f'<div class="card"><img src="data:image/jpeg;base64,{thumb_b64(args.dataset, r["rep"])}"/>'
            f'<div class="meta"><b>cluster {r["cid"]}</b> &middot; <span class="sz">{r["size"]:,} imgs</span>'
            f'<div>mean steer {r["mean"]:.0f}&deg;</div><div class="bk">{r["buckets"]}</div>'
            f'<div class="run">{runs}</div></div></div>')
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>SidewalkPilot dataset clusters</title>
<style>
 body{{background:#0e1116;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}}
 h1{{margin:0 0 4px}} .sub{{color:#8b98a9;font-size:13px;margin:0 0 16px}}
 .grid{{display:flex;flex-wrap:wrap;gap:12px}}
 .card{{background:#161b22;border:1px solid #263041;border-radius:8px;padding:8px;width:170px}}
 .card img{{width:150px;border-radius:5px;display:block}}
 .meta{{font-size:11px;margin-top:5px}} .sz{{color:#2f81f7}} .bk{{color:#8b98a9;margin-top:3px}}
 .run{{color:#f7768e;margin-top:3px}}
</style></head><body>
<h1>SidewalkPilot dataset — scene clusters</h1>
<p class="sub">HDBSCAN(min_cluster_size={args.min_cluster_size}) on SidewalkPilotV3 (v{args.model}) backbone embeddings ·
 <b>{len(cluster_ids)} clusters</b> · {noise:,} diffuse/noise points · {len(names):,} images ·
 sorted by size · thumbnail = image nearest each cluster's centroid</p>
<div class="grid">{"".join(cards)}</div></body></html>"""
    args.out.write_text(html)
    print(f"[clu] wrote {args.out}  ({args.out.stat().st_size/1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
