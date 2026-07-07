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

**Field-validated at night (2026-07-03, ~9:00–9:45 pm)** and in **daylight (2026-07-04, 10:30 am–12:15 pm)**. It drives **very well in cloudy/overcast daylight**, but in **bright sunlight with hard, dark shadows it fails** — it **follows the shadows**: the sharp light↔dark color transitions confuse the model, so it locks onto one region and drives **either only on the bright sidewalk or only inside the dark shadow**, steering along the shadow's edge instead of the real sidewalk. Other known failure: **orange sodium-vapor lamppost light** on the sidewalk at night (a color/lighting case it never saw in training).

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
- **First Series 3 checkpoint to drive on the car** (field-validated at night and in daylight).
- Trained on a clean **50,684-image** real dataset (not the tilted-camera v3.0 data).

## Specific Issues Observed / Remaining

- **Fails under orange lamppost light** on the sidewalk — a color/lighting case out of distribution (HSV/color augmentation was off for this run).
- **Raw steering is blocky/jittery** — the classifier flips between adjacent buckets frame-to-frame on ambiguous frames, causing whole-bucket jumps. Mitigated with **temporal smoothing (EMA)** in the runtime.
- **Mean MAE (~14°) is dragged up by a minority of wrong-bucket picks** on ambiguous frames; the **median is 2.5°**, so most frames are tight.
- **Throttle head not usable** — training throttle was near-constant full, so no signal.
- **Cloudy/overcast daylight works very well** — daytime field-verified 2026-07-04, 10:30 am–12:15 pm.
- **Fails in bright sunlight with hard shadows — follows the shadows.** The sharp light↔dark color transitions confuse the model; it locks onto one region and drives **either only on the bright sidewalk or only inside the dark shadow**, steering along the shadow's edge instead of the real sidewalk (tested 2026-07-04).
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

## Version Update Categories

| Version | Main update category | Data/status | Result |
|---|---|---|---|
| `3.0` | First Series 3 steering+throttle **regression** | tilted-camera dataset (poor quality) | high MAE, dead turn tails; not field-usable |
| `3.0b` | Best checkpoint of the v3.0 run | same v3.0 training run | same regression limits |
| `3.1` | **Hybrid classify + within-bucket-offset head** on a clean real dataset | 50,684 photos (2026-07-02, 2 manual runs) | full steering distribution restored; final epoch — a little jittery |
| `3.1b` | Best checkpoint of the v3.1 run | same v3.1 training run | **recommended** — drove at night + cloudy daylight; follows the shadows in bright sun; smoother + lower-error than v3.1 |

The Series-3 leap is `3.0b -> 3.1`: swapping the single-number **regressor** (which averaged to center and killed the turn tails) for the **hybrid classifier + offset** (which commits to turns).

## Evaluation Summary

All four Series-3 checkpoints on the **same** current `50,684`-image set (fit-check; note this differs from the older `3,517`-image set the v3.0 card reports):

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2 deg | Within 5 deg | Within 10 deg | Within 20 deg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `3.0` | `SidewalkPilot-v3.0.onnx` | `90.284%` | `17.488` | `12.935` | `157.122` | `+0.605` | `4266 / 50684` | `10494 / 50684` | `20150 / 50684` | `34895 / 50684` |
| `3.0b` | `SidewalkPilot-v3.0b.onnx` | `90.638%` | `16.852` | `12.233` | `153.385` | `-0.517` | `4461 / 50684` | `11002 / 50684` | `21249 / 50684` | `36161 / 50684` |
| `3.1` | `SidewalkPilot-v3.1.onnx` | `91.112%` | `15.998` | `3.162` | `178.941` | `+4.859` | `23607 / 50684` | `26709 / 50684` | `31712 / 50684` | `36337 / 50684` |
| `3.1b` **(this model)** | `SidewalkPilot-v3.1b.onnx` | `92.123%` | `14.179` | `2.540` | `178.915` | `+2.325` | `24387 / 50684` | `27244 / 50684` | `32557 / 50684` | `37360 / 50684` |

**Steering-bucket agreement (the real growth metric):** `3.0` 24.2% → `3.0b` 25.0% → `3.1` 59.1% → `3.1b` **59.8%** exact bucket. Note the **median AE collapse** at 3.1 (`~13°` → `~3°`) — the hybrid nails the bulk of frames; the mean MAE stays ~14–16° because a minority of wrong-bucket picks are large.

## Ranking

| Rank | Model | Checkpoint | Score | MAE | Median AE | Exact bucket | Signed Error |
|---:|---|---|---:|---:|---:|---:|---:|
| `1` | `3.1b` | `SidewalkPilot-v3.1b.onnx` | `92.123%` | `14.179` | `2.540` | `59.8%` | `+2.325` |
| `2` | `3.1` | `SidewalkPilot-v3.1.onnx` | `91.112%` | `15.998` | `3.162` | `59.1%` | `+4.859` |
| `3` | `3.0b` | `SidewalkPilot-v3.0b.onnx` | `90.638%` | `16.852` | `12.233` | `25.0%` | `-0.517` |
| `4` | `3.0` | `SidewalkPilot-v3.0.onnx` | `90.284%` | `17.488` | `12.935` | `24.2%` | `+0.605` |

## Prediction Distribution

Watch `Pred Min` — the regression heads never dip below ~20° (they can't reach a real hard-left), while the hybrid heads reach ~1° (full range = live tails):

| Model | Pred Min | Pred Max | Pred Mean | Pred Median | Target Mean |
|---|---:|---:|---:|---:|---:|
| `3.0` | `24.219` | `172.370` | `97.369` | `97.147` | `96.764` |
| `3.0b` | `20.663` | `170.127` | `96.247` | `96.248` | `96.764` |
| `3.1` | `1.059` | `179.246` | `101.623` | `89.994` | `96.764` |
| `3.1b` | `1.085` | `179.063` | `99.089` | `90.110` | `96.764` |

## Field Verdict

- **2026-07-03, ~9:00–9:45 pm (night):** drove the sidewalk **cleanly**.
- **2026-07-04, 10:30 am–12:15 pm (daylight):** **cloudy/overcast conditions drive very well**; daytime field-verified.
- **Failure mode (night):** orange sodium-vapor lamppost light on the sidewalk (color OOD).
- **Failure mode (bright sun + hard shadows, 2026-07-04):** **follows the shadows** — the light↔dark color transitions confuse the model, so it locks onto one region and drives **either only on the bright sidewalk or only inside the dark shadow** instead of the real sidewalk.
- **Raw output was blocky** (argmax bucket flips) → temporal smoothing added in the runtime.

## Current Version Snapshot

- **Model:** `3.1b` (best-validation checkpoint, epoch 19)
- **Checkpoint:** `SidewalkPilot-v3.1b.onnx`
- **Full score:** `92.123%` · **MAE:** `14.179` deg · **Median AE:** `2.540` deg
- **Verdict:** **recommended** Series 3 checkpoint. Field-drove at night (2026-07-03) and in daylight (2026-07-04) — very good in cloudy daylight; smoother and lower-error than the `v3.1` final checkpoint. Known failures: orange lamppost light, and following the shadows in bright sun (drives only the bright sidewalk or only the dark shadow).

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

Steering is precise on straights/gentle turns but its raw per-frame output is blocky (bucket flips) and needs temporal smoothing. It fails under orange lamppost lighting, and in bright sunlight with hard shadows it follows the shadows — the light↔dark color transitions confuse it, so it tracks only the bright sidewalk or only the dark shadow; cloudy/overcast daylight works well (field-verified 2026-07-04). The throttle head has no usable signal. It does not predict braking, reverse, confidence, obstacle presence, or out-of-distribution frames.

## Safety Recommendation

Do not use this model alone to control a robot. In the project, LiDAR has priority over the model and can override steering or trigger hard braking, and a human kill switch is required for any autonomous motion.

## Model Card Contact

Ram Shreyas Naik Sabavat
