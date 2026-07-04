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

# SidewalkPilot-v3.1b

SidewalkPilot-v3.1b is the **recommended Series 3 checkpoint** and the first Series 3 model to actually drive the car in the field. It maps a single `320x180` OpenCV BGR camera frame to a steering angle (plus a throttle output), using a new **hybrid classification + regression steering head** on the `SidewalkPilotV3` backbone, intended for Jetson (ONNX/TensorRT) deployment.

It replaces the Series 3 **regression** head (v3.0/3.0b), which collapsed toward the mean (~97°) and refused to commit to turns. v3.1b instead **commits to real turns** while staying precise on straights.

**Field-validated (2026-07-03, ~9:00–9:45 pm):** drove a sidewalk cleanly at night. It should also handle **normal daylight** (most of its training data is daytime/dusk) — but that has **not been field-verified yet**, and it is **untested in strong shadows**. Known failure: **orange sodium-vapor lamppost light** falling on the sidewalk (a color/lighting case it never saw in training).

## Model Details

- **Developed by:** Ram Shreyas Naik Sabavat
- **Model type:** hybrid steering **classifier + within-bucket offset regressor** (+ throttle head), `SidewalkPilotV3`
- **Library:** PyTorch (exported to ONNX)
- **License:** Apache 2.0
- **Checkpoint:** `SidewalkPilot-v3.1b.pth` / `SidewalkPilot-v3.1b.onnx` (FP32; **best-validation** checkpoint, epoch 19 of 26)
- **Checkpoint created:** 2026-07-03 America/Los_Angeles
- **Input:** Full OpenCV BGR camera frame
- **Preprocessing:** `BGR -> resize 320x180 -> normalize (x/255 - 0.5) / 0.5`
- **Output:** a **19-number vector** = `9 steering-class logits` + `9 within-bucket offsets` + `1 throttle`
- **Series:** `3.x` (Jetson heavy)

## The 19-output hybrid head (how it decodes)

Instead of regressing one steering number (which averages ambiguous frames to the center), the head answers two questions:

1. **Which of 9 steering zones?** — 9 class logits → softmax → `argmax` picks one bucket.
2. **Where inside that zone?** — 9 offset values (one specialist per bucket); take the chosen bucket's offset.

```
buckets:  0-45 HL | 45-60 L | 60-75 L | 75-85 SL | 85-95 straight | 95-105 SR | 105-120 R | 120-135 R | 135-180 HR
decode:   cls  = argmax(logits[0:9])
          off  = sigmoid(offset[cls])                 # 0..1 fraction into the bucket
          steering = bucket_low[cls] + off * (bucket_high[cls] - bucket_low[cls])   # 0..180
          throttle = sigmoid(logit[18])               # trained OFF -> ignore
```

Nine logits (not one number) let the model represent "it's one of the extremes, not the middle," so it can **commit** to a sharp turn instead of hedging. Per-bucket offsets keep the exact angle sharp. This is a standard coarse-to-fine / per-class-regression design.

## Specific Improvements (vs v3.0 / v3.0b regression)

- Replaced the single-number steering regressor with a **9-way classifier + per-bucket offset** → the model **commits to turns** instead of collapsing to center. This fixed the Series 3 "dead-tails" problem.
- **Full steering distribution restored:** exact-bucket agreement **59.8%** (v3.0: 24.2%), median AE **2.5°** (v3.0: ~13°), within-5° on **54%** of frames (v3.0: 21%).
- **First Series 3 checkpoint to drive on the car** (field-validated at night).
- Trained on a clean **50,684-image** real dataset (not the tilted-camera v3.0 data).

## Specific Issues Observed / Remaining

- **Fails under orange lamppost light** on the sidewalk — a color/lighting case out of distribution (HSV/color augmentation was off for this run).
- **Raw steering is blocky/jittery** — the classifier flips between adjacent buckets frame-to-frame on ambiguous frames, causing whole-bucket jumps. Mitigated with **temporal smoothing (EMA)** in the runtime.
- **Mean MAE (~14°) is dragged up by a minority of wrong-bucket picks** on ambiguous frames; the **median is 2.5°**, so most frames are tight.
- **Throttle head not usable** — training throttle was near-constant full, so no signal.
- **Untested in strong shadows; daytime not yet field-verified.**
- The evaluation below is a **fit-check** (run on the full training set, so it includes train/eval overlap), **not** held-out generalization. The honest held-out (time-split) steering MAE during training was ~14–16°.

## Output Meaning

| Output | Meaning |
|---:|---|
| steering `0` | full left |
| steering `90` | straight |
| steering `180` | full right |
| throttle `0` | stop |
| throttle `1` | full forward (not usable in this checkpoint) |

## Evaluation Setup

- **Eval set:** `50,684` labeled images (Series 3 dataset, 2026-07-02 manual-driving runs)
- **Failed samples:** `0`
- **Input format:** `320x180`, OpenCV BGR
- **Error unit:** servo degrees (steering)
- **Score formula:** `max(0, 100 * (1 - absolute_error / 180))`
- **Caveat:** fit-check (trained on this data), not held-out field proof.

## Evaluation Summary

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2 deg | Within 5 deg | Within 10 deg | Within 20 deg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `3.1b` | `SidewalkPilot-v3.1b.onnx` | `92.123%` | `14.179` | `2.540` | `178.915` | `+2.325` | `24387 / 50684` | `27244 / 50684` | `32557 / 50684` | `37360 / 50684` |

**Steering-bucket agreement:** exact bucket `59.8%`, off-by-one bucket `77.1%`.

## Prediction Distribution

| Model | Pred Min | Pred Max | Pred Mean | Pred Median | Target Mean |
|---|---:|---:|---:|---:|---:|
| `3.1b` | `1.085` | `179.063` | `99.089` | `90.110` | `96.764` |

## Field Verdict

- **2026-07-03, ~9:00–9:45 pm (night):** drove the sidewalk **cleanly**.
- **Failure mode:** orange sodium-vapor lamppost light on the sidewalk (color OOD).
- **Expected but unverified:** normal daylight (most training data is daytime/dusk).
- **Untested:** strong shadows.
- **Raw output was blocky** (argmax bucket flips) → temporal smoothing added in the runtime.

## Current Version Snapshot

- **Model:** `3.1b` (best-validation checkpoint, epoch 19)
- **Checkpoint:** `SidewalkPilot-v3.1b.onnx`
- **Full score:** `92.123%` · **MAE:** `14.179` deg · **Median AE:** `2.540` deg
- **Verdict:** **recommended** Series 3 checkpoint. Field-drove at night; smoother and lower-error than the `v3.1` final checkpoint.

## Intended Use

- RC car autonomy experiments · sidewalk/path steering research · Jetson (ONNX/TensorRT) inference · small-scale image-to-control CV.

## Out-of-Scope Use

- Real cars · public-road vehicles · human transportation · safety-critical systems · fully autonomous deployment without external safety layers.

## System Context

```text
Pi camera frame
-> Pi sends the JPEG frame to the Jetson ("Jon")
-> Jon: resize/normalize -> SidewalkPilotV3 (ONNX) -> 19-vector
        -> decode: argmax bucket + sigmoid offset -> steering ; sigmoid -> throttle
-> Pi receives (steering, throttle)
-> temporal smoothing (EMA) -> runtime decision logic
-> LiDAR safety override when triggered
-> final steering/throttle/brake command -> servo + motor controller
```

## Training Data

`50,684` real RC-car sidewalk photos captured 2026-07-02 across two manual-driving runs, decode-verified and curated. Labels are logical steering `0..180` (`90` = straight) and throttle (near-constant `1.0`). The set is center-heavy and skews right (the car has a mechanical left-pull, so straight driving needed a slight right hold). **No CARLA / synthetic data** — Series 3 is trained on real photos only.

## Preprocessing

```text
camera frame in OpenCV BGR
-> resize to 320x180
-> normalize with (x / 255 - 0.5) / 0.5
-> SidewalkPilotV3 (ONNX) -> 19-vector
-> decode: argmax(9 logits)=bucket, sigmoid(offset[bucket]) -> steering 0..180 ; sigmoid(throttle) -> 0..1
```

## Limitations

Steering is precise on straights/gentle turns but its raw per-frame output is blocky (bucket flips) and needs temporal smoothing. It fails under orange lamppost lighting, is untested in shadows, and its daytime behavior is not yet field-verified. The throttle head has no usable signal. It does not predict braking, reverse, confidence, obstacle presence, or out-of-distribution frames.

## Safety Recommendation

Do not use this model alone to control a robot. In the project, LiDAR has priority over the model and can override steering or trigger hard braking, and a human kill switch is required for any autonomous motion.

## Model Card Contact

Ram Shreyas Naik Sabavat
