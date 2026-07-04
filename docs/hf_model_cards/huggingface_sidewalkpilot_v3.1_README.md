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
- classification
- pytorch
- onnx
- jetson
- raspberry-pi
---

# SidewalkPilot-v3.1

SidewalkPilot-v3.1 is a Series 3 **hybrid** steering model. It maps a single `320x180` OpenCV BGR camera frame to a steering angle (plus a throttle output) using a **classification + within-bucket offset** head on the `SidewalkPilotV3` backbone, for Jetson (ONNX/TensorRT) deployment.

It replaces the Series 3 **regression** head (v3.0/3.0b), which collapsed toward the mean (~97°) and refused to commit to turns. This head instead **commits to real turns** while staying precise on straights.

`v3.1` is the **final checkpoint** of its training run (epoch 26 of 26). Because it trained slightly past the best-validation epoch, its raw steering is a **little jittery**. The Series-3 hybrid head was **field-validated at night** (drove the sidewalk; the one failure was orange sodium-vapor lamppost light on the sidewalk). It should also handle **normal daylight** (most training data) — **not yet field-verified** — and is **untested in strong shadows**.

## Model Details

- **Developed by:** Ram Shreyas Naik Sabavat
- **Model type:** hybrid steering **classifier + within-bucket offset regressor** (+ throttle head), `SidewalkPilotV3`
- **Library:** PyTorch (exported to ONNX)
- **License:** Apache 2.0
- **Checkpoint:** `SidewalkPilot-v3.1.pth` / `SidewalkPilot-v3.1.onnx` (FP32; **final** checkpoint, epoch 26 of 26)
- **Checkpoint created:** 2026-07-03 America/Los_Angeles
- **Input:** Full OpenCV BGR camera frame
- **Preprocessing:** `BGR -> resize 320x180 -> normalize (x/255 - 0.5) / 0.5`
- **Output:** a **19-number vector** = `9 steering-class logits` + `9 within-bucket offsets` + `1 throttle`
- **Series:** `3.x` (Jetson heavy)

## The 19-output hybrid head (how it decodes)

```
buckets:  0-45 HL | 45-60 L | 60-75 L | 75-85 SL | 85-95 straight | 95-105 SR | 105-120 R | 120-135 R | 135-180 HR
decode:   cls  = argmax(logits[0:9])
          off  = sigmoid(offset[cls])                 # 0..1 fraction into the bucket
          steering = bucket_low[cls] + off * (bucket_high[cls] - bucket_low[cls])   # 0..180
          throttle = sigmoid(logit[18])               # trained OFF -> ignore
```

Nine class logits let the model **commit** to a steering zone (never averaging to the middle); the nine per-bucket offsets place the exact angle inside the chosen zone. This is a standard coarse-to-fine / per-class-regression design.

## Specific Improvements (vs v3.0 / v3.0b regression)

- **9-way classifier + per-bucket offset** replaces the single-number regressor → commits to turns instead of collapsing to center. This fixed the Series 3 "dead-tails" problem.
- Full steering distribution restored: exact-bucket agreement **59.1%** (v3.0: 24.2%), median AE **3.2°** (v3.0: ~13°).
- Trained on a clean **50,684-image** real dataset (not the tilted-camera v3.0 data).

## Specific Issues Observed / Remaining

- **A little jittery** — this is the final epoch, trained slightly past the best-validation point.
- **Raw steering is blocky** (the classifier flips between buckets frame-to-frame on ambiguous frames) → mitigated with **temporal smoothing (EMA)** in the runtime.
- **Mean MAE (~16°) is inflated by wrong-bucket picks** on ambiguous frames; median is `3.2°` (most frames are tight).
- **Fails under orange lamppost light** (color OOD); **untested in shadows; daytime not field-verified.**
- **Throttle head not usable** (near-constant training throttle).
- Evaluation below is a **fit-check** (full training set, train overlap), not held-out.

## Output Meaning

| Output | Meaning |
|---:|---|
| steering `0` | full left |
| steering `90` | straight |
| steering `180` | full right |
| throttle `0` | stop |
| throttle `1` | full forward (not usable in this checkpoint) |

## Evaluation Setup

- **Eval set:** `50,684` labeled images (Series 3 dataset, 2026-07-02 runs)
- **Failed samples:** `0` · **Input:** `320x180` OpenCV BGR · **Error unit:** servo degrees
- **Score formula:** `max(0, 100 * (1 - absolute_error / 180))`
- **Caveat:** fit-check (trained on this data), not held-out.

## Version Update Categories

| Version | Main update category | Data/status | Result |
|---|---|---|---|
| `3.0` | First Series 3 steering+throttle **regression** | tilted-camera dataset (poor quality) | high MAE, dead turn tails; not field-usable |
| `3.0b` | Best checkpoint of the v3.0 run | same v3.0 training run | same regression limits |
| `3.1` | **Hybrid classify + within-bucket-offset head** on a clean real dataset | 50,684 photos (2026-07-02, 2 manual runs) | full steering distribution restored; final epoch (a little jittery) |

The Series-3 leap is `3.0b -> 3.1`: swapping the single-number **regressor** (which averaged to center and killed the turn tails) for the **hybrid classifier + offset** (which commits to turns).

## Evaluation Summary

Series-3 checkpoints up to `3.1`, all on the same current `50,684`-image set (fit-check; note this differs from the older `3,517`-image set the v3.0 card reports):

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2 deg | Within 5 deg | Within 10 deg | Within 20 deg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `3.0` | `SidewalkPilot-v3.0.onnx` | `90.284%` | `17.488` | `12.935` | `157.122` | `+0.605` | `4266 / 50684` | `10494 / 50684` | `20150 / 50684` | `34895 / 50684` |
| `3.0b` | `SidewalkPilot-v3.0b.onnx` | `90.638%` | `16.852` | `12.233` | `153.385` | `-0.517` | `4461 / 50684` | `11002 / 50684` | `21249 / 50684` | `36161 / 50684` |
| `3.1` **(this model)** | `SidewalkPilot-v3.1.onnx` | `91.112%` | `15.998` | `3.162` | `178.941` | `+4.859` | `23607 / 50684` | `26709 / 50684` | `31712 / 50684` | `36337 / 50684` |

**Steering-bucket agreement (the real growth metric):** `3.0` 24.2% → `3.0b` 25.0% → `3.1` **59.1%** exact bucket. Note the **median AE collapse** at 3.1 (`~13°` → `~3°`) — the hybrid nails the bulk of frames; the mean MAE stays ~16° because a minority of wrong-bucket picks are large.

## Ranking

| Rank | Model | Checkpoint | Score | MAE | Median AE | Exact bucket | Signed Error |
|---:|---|---|---:|---:|---:|---:|---:|
| `1` | `3.1` | `SidewalkPilot-v3.1.onnx` | `91.112%` | `15.998` | `3.162` | `59.1%` | `+4.859` |
| `2` | `3.0b` | `SidewalkPilot-v3.0b.onnx` | `90.638%` | `16.852` | `12.233` | `25.0%` | `-0.517` |
| `3` | `3.0` | `SidewalkPilot-v3.0.onnx` | `90.284%` | `17.488` | `12.935` | `24.2%` | `+0.605` |

## Prediction Distribution

Watch `Pred Min` — the regression heads never dip below ~20° (they can't reach a real hard-left), while this hybrid head reaches ~1° (full range = live tails):

| Model | Pred Min | Pred Max | Pred Mean | Pred Median | Target Mean |
|---|---:|---:|---:|---:|---:|
| `3.0` | `24.219` | `172.370` | `97.369` | `97.147` | `96.764` |
| `3.0b` | `20.663` | `170.127` | `96.247` | `96.248` | `96.764` |
| `3.1` | `1.059` | `179.246` | `101.623` | `89.994` | `96.764` |

## Current Version Snapshot

- **Model:** `3.1` (final checkpoint, epoch 26)
- **Checkpoint:** `SidewalkPilot-v3.1.onnx`
- **Full score:** `91.112%` · **MAE:** `15.998` deg · **Median AE:** `3.162` deg
- **Verdict:** the hybrid head works and commits to turns; this final-epoch checkpoint is slightly jittery, so pair it with runtime temporal smoothing.

## Intended Use

- RC car autonomy experiments · sidewalk/path steering research · Jetson (ONNX/TensorRT) inference · small-scale image-to-control CV.

## Out-of-Scope Use

- Real cars · public-road vehicles · human transportation · safety-critical systems · fully autonomous deployment without external safety layers.

## System Context

```text
Pi camera frame -> Pi sends JPEG to the Jetson ("Jon")
-> Jon: resize/normalize -> SidewalkPilotV3 (ONNX) -> 19-vector
        -> decode: argmax bucket + sigmoid offset -> steering ; sigmoid -> throttle
-> Pi receives (steering, throttle) -> temporal smoothing (EMA) -> runtime logic
-> LiDAR safety override -> final command -> servo + motor controller
```

## Training Data

`50,684` real RC-car sidewalk photos captured 2026-07-02 across two manual-driving runs, decode-verified and curated. Labels: logical steering `0..180` (`90` = straight), throttle near-constant `1.0`. Center-heavy, right-skewed (mechanical left-pull). **No CARLA / synthetic data** — real photos only.

## Preprocessing

```text
camera frame (OpenCV BGR) -> resize 320x180 -> (x/255 - 0.5)/0.5
-> SidewalkPilotV3 (ONNX) -> 19-vector
-> decode: argmax(9 logits)=bucket, sigmoid(offset[bucket]) -> steering 0..180 ; sigmoid(throttle) -> 0..1
```

## Limitations

Steering is precise on straights/gentle turns but its raw per-frame output is blocky (bucket flips) and needs temporal smoothing; this final-epoch checkpoint is slightly jittery. It fails under orange lamppost lighting, is untested in shadows, daytime is not field-verified, and the throttle head has no usable signal. No braking/reverse/confidence/obstacle outputs.

## Safety Recommendation

Do not use this model alone to control a robot. LiDAR has priority and can override steering or hard-brake; a human kill switch is required for any autonomous motion.

## Model Card Contact

Ram Shreyas Naik Sabavat
