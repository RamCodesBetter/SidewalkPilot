---
pretty_name: SidewalkPilot CARLA Synthetic Steering + Throttle Dataset
size_categories:
- 10K<n<100K
tags:
- robotics
- autonomous-driving
- rc-car
- computer-vision
- steering-regression
- throttle-regression
- carla
- synthetic
- sim2real
- pytorch
---

# SidewalkPilot CARLA Synthetic Dataset

CARLA-simulator-generated steering + throttle frames used to **assist the SidewalkPilot Series 1/2 models** — blended with real RC-car photos and **down-weighted** vs real. This is **synthetic** data rendered in the CARLA driving simulator, not real field capture.

**Series 3 does NOT use this dataset** — the Series 3 line is trained on **real RC-car photos only**. This CARLA set is kept for the CARLA-assisted Series 1/2 history and for optional future sim2real experiments.

| Resource | Link |
|---|---|
| GitHub repository | `https://github.com/RamCodesBetter/SidewalkPilot` |
| Hugging Face dataset | `https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_carla` |
| Real datasets | `SidewalkPilot_v1_and_v2` (real S1/2) · `SidewalkPilot_v3` (real S3) |

## How this data was generated

The frames were rendered in the **CARLA autonomous-driving simulator**. A vehicle was driven along road/lane routes by an **expert path-following controller** while a front-facing camera logged each frame together with the control the expert applied. Every frame therefore pairs a rendered image with a **clean expert steering + throttle label** plus the controller's tracking state — that's what makes it usable for imitation learning (image → control).

The per-frame telemetry (`speed`, `applied_steer`, `lateral_error`, `heading_error`) is the fingerprint of that setup: a controller tracking a reference path, logging how much steering/throttle it applied and how far off the path it was (cross-track + heading error). Coverage spanned multiple CARLA **towns and weather presets** — the source folders were named `dataset_carla_steering_town03_clear`, `..._town04_cloudy`, `..._town05_wet`, etc. — giving varied roads, lighting, and surface conditions the small early real datasets lacked.

> Project-specifics (CARLA version; exact town/weather split; capture resolution/fps; whether the expert was CARLA's built-in autopilot or a custom pure-pursuit/Stanley controller) belong to the SidewalkPilot generation setup. That generator is no longer in the repo (the old `generate_synthetic_sidewalks` helper was retired), so this set is preserved as the archived output.

## Dataset Contents

| File or folder | What it contains |
|---|---|
| `images/` | 50,000 rendered CARLA frames (PNG) |
| `labels.json` | list of per-frame labels (`image`, `steering`, `throttle`, + sim telemetry) |
| `telemetry.json` | extra per-frame simulator telemetry |
| `sidewalkpilot_carla_dataset.tar` | the full set packed as one tar (HF-friendly; extract to reconstruct `images/` + `labels.json`) |

## Current Size

| Item | Count |
|---|---:|
| PNG images | 50,000 |
| Label entries | 50,000 |
| Steering range | 0 to 180 degrees (logical; 90 = straight) |
| Throttle range | 0.00 to 1.00 |
| Source | CARLA simulator (synthetic) |

## Label Format

`labels.json` is a JSON **list**; each entry maps one frame in `images/` to its controls plus sim telemetry:

| Field | Type | Meaning |
|---|---|---|
| `image` | string | frame filename inside `images/` (e.g. `000000.png`) |
| `steering` | number | logical steering servo angle, 0–180 |
| `throttle` | number | forward motor command, 0.00–1.00 |
| `speed` | number | simulator speed (m/s) |
| `applied_steer` | number | normalized steering actually applied by the expert controller |
| `lateral_error` | number | cross-track error vs the reference path |
| `heading_error` | number | heading error vs the reference path |

The SidewalkPilot trainer only reads `image` / `steering` / `throttle`; the rest is kept for analysis.

Example entry:

```json
{
  "image": "000000.png",
  "steering": 90.477828,
  "throttle": 0.72,
  "speed": 0.49,
  "applied_steer": 0.00053,
  "lateral_error": 5.2e-08,
  "heading_error": -2.0e-07
}
```

## How it assisted the Series 1/2 models

Early Series 1/2 real datasets were small (a few thousand hand-labeled field photos) and thin on turns, shadows, and route variety. CARLA filled those gaps:

- **Volume + diversity:** 50k synthetic frames across towns/weather added far more steering angles and lighting conditions than the real set alone.
- **Blended, not dominant:** the trainer tags any root whose name contains `carla`/`synthetic`/`sim`/`dataset_l2` as `source="carla"` and **down-weights it (`--carla-sample-weight 0.6`) vs real (`2.0`)** — real data stays the anchor, CARLA is a supplement.
- **Sim2real via domain randomization:** CARLA frames get heavy augmentation (contrast, noise, blur, tree/edge shadows, texture — `--carla-domain-randomize-probability 0.70`) to bridge the render-vs-real gap so the model doesn't overfit the "clean sim look."
- **Documented in the model cards:** v1.0 = "initial mixed sidewalk/CARLA set"; v2.1 = "CARLA + real + corrections"; v2.2 = stronger shadow and CARLA/domain-randomization settings. It gave the baseline models turn + shadow coverage *before* enough real field data existed.

**Series 3 dropped it** — by then Ram had collected 50k+ real sidewalk photos, and Series 3 learns real-world steering+throttle directly (real-only).

## How It's Used In Training

Blend it with a real dataset by listing it in `--roots`, e.g.:

```bash
python3 sidewalkpilot_trainer.py --roots <real_dataset> carla_dataset --model-version <ver>
```

Series 1/2 models were trained this way (real + CARLA). Series 3 omits it.

## Intended Scope

Synthetic sim2real *assist* data — not real field data, and not a standalone training set. Use it **blended with, and down-weighted vs, real captures**. Do not present CARLA predictions as real-world field performance.
