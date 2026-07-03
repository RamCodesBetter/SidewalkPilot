---
license: apache-2.0
language:
- en
library_name: pytorch
tags:
- rc_car
- robotics
- autonomous-driving
- sidewalk-navigation
- computer-vision
- steering
- throttle
- pytorch
- onnx
- jetson
- raspberry-pi
---

# SidewalkPilot-v3.0b

SidewalkPilot-v3.0b is the **best-checkpoint variant** of SidewalkPilot-v3.0, the first Series 3 model. Like v3.0, it predicts **both steering and throttle** from a single `320x180` OpenCV BGR camera frame using the heavier `SidewalkPilotV3` architecture intended for Jetson (ONNX/TensorRT) deployment.

**This checkpoint underperformed and is not field-usable** — and it actually scored slightly worse than v3.0. Its steering MAE is much higher than the Series 2 models, mainly because the Series 3 training images were captured with a **tilted camera**, so the data quality was poor. It is published for history/completeness, not as a recommended model.

## Model Details

- **Developed by:** Ram Shreyas Naik Sabavat
- **Model type:** CNN steering+throttle regression model (`SidewalkPilotV3`)
- **Library:** PyTorch (exported to ONNX)
- **License:** Apache 2.0
- **Checkpoint:** `SidewalkPilot-v3.0b.onnx` (FP32; the `.pth` master was removed after ONNX export)
- **Checkpoint created:** 2026-06-29 America/Los_Angeles
- **Input:** Full OpenCV BGR camera frame
- **Preprocessing:** `BGR -> resize 320x180 -> normalize (x/255 - 0.5) / 0.5`
- **Output:** two unit controls in `[-1, 1]` — steering (decoded to `0..180`) and throttle (decoded to `0..1`)
- **Series:** `3.x` (Jetson heavy)
- **Decode:** `steering = 90 + 90 * u0` ; `throttle = (u1 + 1) / 2`

## Specific Improvements

- Best checkpoint saved during the v3.0 training run (lowest validation loss).
- First SidewalkPilot line to jointly predict **steering AND throttle** (Series 1/2 were steering-only).
- New heavier `SidewalkPilotV3` backbone at `320x180`, exported to ONNX FP32 for Jetson ("Jon") inference.

## Specific Issues Observed / Remaining

- **Much worse steering MAE than Series 2** (`10.805` deg vs `3.265` deg for v2.4b) — and slightly worse than v3.0. Not field-usable.
- **Training images were captured with a TILTED CAMERA**, so framing/quality was poor and the image-to-label mapping was degraded.
- Throttle was near-constant `1.0` across the collected runs, so the throttle head has no meaningful signal yet.
- Evaluated on the Series 3 dataset (`320x180`), not the Series 1/2 correction set, so cross-series MAE is indicative, not identical-set.
- Includes train/evaluation overlap (trained on this dataset), so treat these numbers as a fit check, not held-out field proof.

## Output Meaning

| Output | Meaning |
|---:|---|
| steering `0` | full left |
| steering `90` | straight |
| steering `180` | full right |
| throttle `0` | stop |
| throttle `1` | full forward |

## Evaluation Setup

- **Eval set:** `3,517` labeled images (Series 3 dataset: `D0510_18` + `D0510_19` + `D0510_20` + `D0629_17`)
- **Failed samples:** `0`
- **Input format:** `320x180`, OpenCV BGR
- **Output:** steering `0..180` (+ throttle `0..1`)
- **Error unit:** servo degrees (steering)
- **Score formula:** `max(0, 100 * (1 - absolute_error / 180))`
- **Dataset note:** `D0629_17` (2,757 images) was captured with a tilted camera; image quality is poor.

## Version Update Categories

| Version | Main update category | Data/status | Result |
|---|---|---|---|
| `3.0` | First Series 3 steering+throttle model | tilted-camera Series 3 dataset (poor quality) | high MAE; not field-usable |
| `3.0b` | Best checkpoint from the v3.0 training run | same v3.0 training run | similar; slightly worse MAE than 3.0 |

## Evaluation Summary

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2 deg | Within 5 deg | Within 10 deg | Within 20 deg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `3.0` | `SidewalkPilot-v3.0.onnx` | `94.319%` | `10.225` | `7.802` | `87.389` | `+0.768` | `502 / 3517` | `1166 / 3517` | `2135 / 3517` | `3088 / 3517` |
| `3.0b` | `SidewalkPilot-v3.0b.onnx` | `93.997%` | `10.805` | `8.478` | `75.904` | `+1.682` | `475 / 3517` | `1105 / 3517` | `2019 / 3517` | `3015 / 3517` |

For reference, the best Series 2 model (v2.4b) scored `3.265` deg MAE on the Series 1/2 set — roughly 3x better than Series 3 here.

## Prediction Distribution

| Model | Pred Min | Pred Max | Pred Mean | Target Mean |
|---|---:|---:|---:|---:|
| `3.0` | `16.972` | `177.455` | `102.724` | `101.956` |
| `3.0b` | `14.399` | `174.533` | `103.637` | `101.956` |

## Ranking

| Rank In This Card | Model | Checkpoint | Score | MAE | Median AE | Max AE | Within 5 deg | Within 10 deg | Signed Error |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `1` | `3.0` | `SidewalkPilot-v3.0.onnx` | `94.319%` | `10.225` | `7.802` | `87.389` | `1166 / 3517` | `2135 / 3517` | `+0.768` |
| `2` | `3.0b` | `SidewalkPilot-v3.0b.onnx` | `93.997%` | `10.805` | `8.478` | `75.904` | `1105 / 3517` | `2019 / 3517` | `+1.682` |

## Field Case Comparison

| Model | D0510_18 MAE | D0510_19 MAE | D0510_20 MAE | D0629_17 MAE |
|---|---:|---:|---:|---:|
| `3.0` | `15.94` | `12.72` | `17.39` | `8.35` |
| `3.0b` | `16.06` | `12.31` | `16.19` | `9.34` |

## Current Version Snapshot

- **Model:** `3.0b`
- **Checkpoint:** `SidewalkPilot-v3.0b.onnx`
- **Checkpoint created:** 2026-06-29 America/Los_Angeles
- **Full score:** `93.997%`
- **MAE:** `10.805` servo degrees
- **Median AE:** `8.478` servo degrees
- **Rank in this card:** `2` of `2` listed checkpoints
- **Verdict:** not field-usable — high MAE from tilted-camera training data; slightly worse than v3.0.

## Intended Use

This model is intended for:

- RC car autonomy experiments
- Sidewalk/path steering + throttle research
- Jetson (ONNX/TensorRT) inference experiments
- Small-scale computer vision control systems
- Testing direct image-to-control regression

## Out-of-Scope Use

This model is not intended for:

- Real cars
- Public road vehicles
- Human transportation
- Safety-critical systems
- Fully autonomous deployment without external safety layers

## System Context

```text
Pi camera frame
-> Pi sends the JPEG frame to the Jetson ("Jon")
-> Jon: resize/normalize -> SidewalkPilotV3 (ONNX) -> (steering, throttle)
-> Pi receives (steering, throttle)
-> runtime decision logic
-> LiDAR safety override when triggered
-> final steering/throttle/brake command
-> servo + motor controller
```

LiDAR runs as a higher-priority safety layer:

```text
LiDAR clear -> use model steering
LiDAR obstacle -> LiDAR override mode
LiDAR blocked/too close -> hard brake
```

## Training Data

The Series 3 dataset was assembled from RC-car photo runs: the 05_10 v2.3 field-failure runs (`D0510_18/19/20`) plus a 06_29 run (`D0629_17`). Labels are logical steering `0..180` and throttle `0..1` (near-constant `1.0` in these runs). The 06_29 run was captured with a **tilted camera**, degrading image quality.

**No CARLA / synthetic data.** The entire Series 3 line is trained on **real RC-car photos only** — no CARLA or simulator frames. (Series 1/2, by contrast, were CARLA-assisted: real + CARLA synthetic blended.)

## Preprocessing

```text
camera frame in OpenCV BGR
-> resize to 320x180
-> normalize with (x / 255 - 0.5) / 0.5
-> SidewalkPilotV3 (ONNX)
-> [steering_unit, throttle_unit] in [-1, 1]
-> decode: steering = 90 + 90*u0, throttle = (u1 + 1)/2
```

## Limitations

SidewalkPilot-v3.0b has high steering error and is not field-usable (slightly worse than v3.0). It was trained on tilted-camera images, so image quality was poor. The throttle head has no meaningful signal (throttle was constant during data collection). It does not predict braking, reverse, confidence, obstacle presence, or out-of-distribution frames.

## Safety Recommendation

Do not use this model alone to control a robot. In the original project, LiDAR has priority over the model and can override steering or trigger hard braking.

## Model Card Contact

Ram Shreyas Naik Sabavat
