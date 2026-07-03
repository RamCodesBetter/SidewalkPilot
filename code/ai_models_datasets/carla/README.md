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

CARLA-simulator-generated steering + throttle frames used to **assist** the SidewalkPilot **Series 1/2** models — blended with real RC-car photos and **down-weighted** vs real (0.6 vs 2.0). This is **synthetic** data rendered in the CARLA driving simulator, not real field capture.

**Series 3 does NOT use this dataset** — the Series 3 line is trained on **real RC-car photos only**. This CARLA set is kept/published for the CARLA-assisted Series 1/2 history and for optional future sim2real experiments.

| Resource | Link |
|---|---|
| GitHub repository | `https://github.com/RamCodesBetter/SidewalkPilot` |
| Hugging Face dataset | `https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_carla` |
| Real datasets | `SidewalkPilot_v1_and_v2` (real S1/2) · `SidewalkPilot_v3` (real S3) |

## Dataset Contents

| File or folder | What it contains |
|---|---|
| `images/` | 50,000 rendered CARLA frames (PNG) |
| `labels.json` | list of per-frame labels (`image`, `steering`, `throttle`, + sim telemetry) |
| `telemetry.json` | extra per-frame simulator telemetry |

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
| `applied_steer` | number | normalized steering actually applied in the sim |
| `lateral_error` | number | cross-track error in the sim |
| `heading_error` | number | heading error in the sim |

The SidewalkPilot trainer only reads `image` / `steering` / `throttle`; the rest is sim telemetry kept for analysis.

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

## How It's Used In Training

The SidewalkPilot trainers auto-tag any dataset root whose folder name contains `carla` / `synthetic` / `sim` / `dataset_l2` as `source="carla"`, then:

- **down-weight** it (`--carla-sample-weight 0.6`) vs real data (`2.0`), and
- apply **CARLA domain-randomization augmentation** (`--carla-domain-randomize-probability 0.70`).

Blend it with a real dataset by listing it in `--roots`, e.g.:

```bash
python3 sidewalkpilot_trainer.py --roots <real_dataset> carla_dataset --model-version <ver>
```

Series 1/2 models were trained this way (real + CARLA). **Series 3 omits it (real-only).**

## Intended Scope

Synthetic sim2real *assist* data — not real field data, and not a standalone training set. Use it **blended with, and down-weighted vs, real captures**. Do not present CARLA predictions as real-world field performance.
