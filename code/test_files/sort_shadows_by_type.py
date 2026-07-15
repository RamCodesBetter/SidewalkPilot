#!/usr/bin/env python3
"""sort_shadows_by_type.py -- bucket a photo folder into shadow TYPES via zero-shot CLIP cosine.

Buckets every image into one of:
  * Tree shadow            (dappled leaf/branch shadows)
  * Line / lamppost shadow (thin straight pole/post shadows)
  * House shadow           (big solid building/wall shade)
  * No strong shadow / other  (competitor bucket so the 3 counts stay meaningful)

Each bucket is an ENSEMBLE of text prompts; CLIP image embeddings are matched to the
mean-prompt prototype by cosine similarity, top-1 wins. Reuses the CLIP loader/embedder/
thumbnailer from dataset_scene_tags.py so it can't drift. Image embeddings are cached per
folder (shadow_embeds_<folder>.npz) so re-running with new prompts is instant.

Output: printed counts + a self-contained, cloud-styled HTML gallery (samples per bucket).

    python3 sort_shadows_by_type.py --dataset /home/rsabavat/rc_car_code/media/photos/2026_07_07_run_1
    python3 sort_shadows_by_type.py --samples 30 --out /home/rsabavat/D0707_shadows.html
"""
import argparse
import base64
import sys
import time
from pathlib import Path

import numpy as np
import torch

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from dataset_scene_tags import load_clip, embed_images, text_embeds, thumb_b64  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

# Bucket -> ensemble of prompts. Edit freely; re-run is instant (embeddings cached).
BUCKETS = {
    "Tree shadow": [
        "a sidewalk covered in dappled tree shadows",
        "dappled sunlight and leaf shadows through trees on the pavement",
        "blotchy patchy shadows of tree leaves and branches on the ground",
    ],
    "Line / lamppost shadow": [
        "the long thin straight shadow of a lamppost or pole across the sidewalk",
        "a single narrow linear shadow cast by a street light pole on the path",
        "thin straight line shadows from posts or railings on the pavement",
    ],
    "House shadow": [
        "the large solid shadow of a house or building covering the sidewalk",
        "a big straight-edged building shadow shading the path",
        "the sidewalk in the cool shade of a house wall or fence",
    ],
    "No strong shadow / other": [
        "a sidewalk in even flat light with no strong shadows",
        "a plain evenly lit sidewalk on an overcast cloudy day",
    ],
}

# Cloud palette per bucket (accent color for the card).
ACCENTS = {
    "Tree shadow": "#3f8f5b",
    "Line / lamppost shadow": "#c9862b",
    "House shadow": "#6a6fb0",
    "No strong shadow / other": "#8aa0b3",
}


def class_prototypes(model, proc, device):
    """One L2-normalized prototype embedding per bucket = mean of its prompt embeddings."""
    labels = list(BUCKETS.keys())
    flat, spans = [], []
    for lab in labels:
        s = len(flat)
        flat.extend(BUCKETS[lab])
        spans.append((s, len(flat)))
    txt = text_embeds(model, proc, flat, device)                 # [P,512], already normalized
    protos = np.zeros((len(labels), txt.shape[1]), dtype=np.float32)
    for i, (a, b) in enumerate(spans):
        v = txt[a:b].mean(axis=0)
        protos[i] = v / (np.linalg.norm(v) + 1e-8)
    return labels, protos


def cloud_html(dataset_dir, labels, names, assign, sims, counts, samples):
    total = len(names)
    cards = []
    for ci, lab in enumerate(labels):
        idx = np.where(assign == ci)[0]
        # most representative first (highest cosine to this bucket)
        idx = idx[np.argsort(-sims[idx, ci])][:samples]
        thumbs = "".join(
            f'<img loading="lazy" src="data:image/jpeg;base64,{thumb_b64(dataset_dir, names[i])}">'
            for i in idx
        )
        pct = 100.0 * counts[ci] / max(1, total)
        cards.append(f"""
        <section class="cloud">
          <div class="cloud-head" style="--accent:{ACCENTS.get(lab,'#88a')}">
            <span class="dot"></span><h2>{lab}</h2>
            <span class="count">{counts[ci]:,}</span><span class="pct">{pct:.1f}%</span>
          </div>
          <div class="grid">{thumbs}</div>
        </section>""")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>D0707 — shadow types</title>
<style>
  :root{{font-family:-apple-system,Segoe UI,Roboto,sans-serif}}
  body{{margin:0;min-height:100vh;color:#2b3a4a;
    background:linear-gradient(180deg,#8ec9ff 0%,#bfe3ff 40%,#e9f6ff 100%);background-attachment:fixed}}
  .sky{{position:fixed;inset:0;overflow:hidden;z-index:0;pointer-events:none}}
  .puff{{position:absolute;background:#fff;border-radius:50%;filter:blur(6px);opacity:.75}}
  .p1{{width:220px;height:220px;left:6%;top:12%}} .p2{{width:160px;height:160px;left:70%;top:8%}}
  .p3{{width:300px;height:300px;left:38%;top:60%;opacity:.5}} .p4{{width:130px;height:130px;left:85%;top:55%}}
  .wrap{{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:34px 20px 80px}}
  header{{text-align:center;margin-bottom:26px}}
  h1{{font-size:30px;margin:0 0 6px;text-shadow:0 2px 10px rgba(255,255,255,.7)}}
  .sub{{opacity:.7;font-size:14px}}
  .cloud{{background:#fff;border-radius:30px;padding:18px 22px 24px;margin:22px 0;
    box-shadow:0 18px 45px rgba(90,140,200,.28),0 3px 0 rgba(255,255,255,.9) inset}}
  .cloud-head{{display:flex;align-items:center;gap:12px;margin-bottom:14px}}
  .cloud-head .dot{{width:14px;height:14px;border-radius:50%;background:var(--accent);
    box-shadow:0 0 0 5px color-mix(in srgb,var(--accent) 22%,transparent)}}
  .cloud-head h2{{font-size:20px;margin:0;flex:0 0 auto}}
  .cloud-head .count{{margin-left:auto;font-size:26px;font-weight:800;color:var(--accent)}}
  .cloud-head .pct{{font-size:14px;opacity:.6}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}}
  .grid img{{width:100%;border-radius:12px;display:block;box-shadow:0 4px 12px rgba(60,90,130,.2)}}
</style></head>
<body>
  <div class="sky"><div class="puff p1"></div><div class="puff p2"></div>
    <div class="puff p3"></div><div class="puff p4"></div></div>
  <div class="wrap">
    <header>
      <h1>☁️ D0707 — Shadow Types</h1>
      <div class="sub">{dataset_dir.name} &middot; {total:,} images &middot; zero-shot CLIP cosine (top-1) &middot;
        samples sorted by best match</div>
    </header>
    {''.join(cards)}
  </div>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path,
                    default=Path("/home/rsabavat/rc_car_code/media/photos/2026_07_07_run_1"))
    ap.add_argument("--out", type=Path, default=Path("/home/rsabavat/D0707_shadows.html"))
    ap.add_argument("--samples", type=int, default=30, help="thumbnails shown per bucket")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    device = torch.device(args.device)

    names = sorted(p.name for p in args.dataset.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if args.limit:
        names = names[: args.limit]
    if not names:
        raise SystemExit(f"no images under {args.dataset}")
    print(f"[shadow] {len(names)} images in {args.dataset.name}", flush=True)

    model, proc = load_clip(device)
    cache = _HERE / f"shadow_embeds_{args.dataset.name}.npz"
    if cache.is_file() and not args.no_cache:
        z = np.load(cache, allow_pickle=True)
        if len(z["names"]) == len(names) and list(z["names"]) == names:
            print(f"[shadow] loaded cached embeddings {z['embs'].shape}", flush=True)
            embs = z["embs"]
        else:
            embs = None
    else:
        embs = None
    if embs is None:
        embs, keep = embed_images(model, args.dataset, names, device, args.batch_size)
        names = [names[i] for i in range(len(names)) if keep[i]]
        embs = embs[keep]
        np.savez(cache, embs=embs, names=np.array(names))
        print(f"[shadow] cached -> {cache.name}", flush=True)

    labels, protos = class_prototypes(model, proc, device)
    sims = embs @ protos.T                                       # cosine [N,C]
    assign = sims.argmax(axis=1)
    counts = np.bincount(assign, minlength=len(labels))

    print("\n=== SHADOW-TYPE COUNTS (" + args.dataset.name + f", {len(names):,} imgs) ===")
    for ci, lab in enumerate(labels):
        print(f"  {lab:26s} {counts[ci]:6,d}  ({100.0*counts[ci]/max(1,len(names)):5.1f}%)")

    html = cloud_html(args.dataset, labels, list(names), assign, sims, counts, args.samples)
    args.out.write_text(html)
    print(f"\n[shadow] wrote {args.out} ({args.out.stat().st_size/1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
