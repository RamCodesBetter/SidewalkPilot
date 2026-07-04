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

SidewalkPilot-v3.1 is the Series 3 **hybrid** steering model — the same architecture as **v3.1b**, trained on the same 50,684-image real sidewalk dataset. It maps a `320x180` OpenCV BGR frame to a steering angle (plus a throttle output) using a **classification + within-bucket offset** head on the `SidewalkPilotV3` backbone, for Jetson (ONNX/TensorRT) deployment.

**`v3.1` is the FINAL checkpoint (epoch 26 of 26); `v3.1b` is the BEST-validation checkpoint (epoch 19).** They are the same head and data, but **`v3.1b` is recommended** — `v3.1` overtrained slightly past the best epoch, so it is a **little more jittery and higher-error**. Use `v3.1b` unless you specifically want the final-epoch weights (e.g. to study overfitting).

The field test (2026-07-03 night) was run on **`v3.1b`**; `v3.1` shares its behavior but is expected to be marginally worse on the same failure modes.

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

Nine class logits let the model **commit** to a steering zone (never averaging to the middle); the nine per-bucket offsets place the exact angle inside the chosen zone. See `SidewalkPilot-v3.1b` for the full rationale.

## Specific Improvements (vs v3.0 / v3.0b regression)

- **9-way classifier + per-bucket offset** replaces the single-number regressor → commits to turns instead of collapsing to center.
- Full steering distribution restored: exact-bucket agreement **59.1%** (v3.0: 24.2%), median AE **3.2°** (v3.0: ~13°).
- Trained on the clean **50,684-image** real dataset (not tilted-camera v3.0 data).

## Specific Issues Observed / Remaining

- **More jittery / higher-error than `v3.1b`** — this is the final epoch, slightly past the best-validation point. Prefer `v3.1b`.
- **Raw steering is blocky** (classifier flips between buckets frame-to-frame) → needs temporal smoothing (EMA) in the runtime.
- **Mean MAE (~16°) is inflated by wrong-bucket picks** on ambiguous frames; median is `3.2°`.
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
| `3.1` | **Hybrid classify + within-bucket-offset head** on a clean real dataset | 50,684 photos (2026-07-02, 2 manual runs) | full steering distribution restored; final epoch — a little jittery |
| `3.1b` | Best checkpoint of the v3.1 run | same v3.1 training run | **recommended** — drove the sidewalk at night; smoother + lower-error than v3.1 |

The Series-3 leap is `3.0b -> 3.1`: swapping the single-number **regressor** (which averaged to center and killed the turn tails) for the **hybrid classifier + offset** (which commits to turns).

## Evaluation Summary

All four Series-3 checkpoints on the **same** current `50,684`-image set (fit-check; this set differs from the older `3,517`-image set the v3.0 card reports):

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2 deg | Within 5 deg | Within 10 deg | Within 20 deg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `3.0` | `SidewalkPilot-v3.0.onnx` | `90.284%` | `17.488` | `12.935` | `157.122` | `+0.605` | `4266 / 50684` | `10494 / 50684` | `20150 / 50684` | `34895 / 50684` |
| `3.0b` | `SidewalkPilot-v3.0b.onnx` | `90.638%` | `16.852` | `12.233` | `153.385` | `-0.517` | `4461 / 50684` | `11002 / 50684` | `21249 / 50684` | `36161 / 50684` |
| `3.1` **(this model)** | `SidewalkPilot-v3.1.onnx` | `91.112%` | `15.998` | `3.162` | `178.941` | `+4.859` | `23607 / 50684` | `26709 / 50684` | `31712 / 50684` | `36337 / 50684` |
| `3.1b` | `SidewalkPilot-v3.1b.onnx` | `92.123%` | `14.179` | `2.540` | `178.915` | `+2.325` | `24387 / 50684` | `27244 / 50684` | `32557 / 50684` | `37360 / 50684` |

**Steering-bucket agreement (the real growth metric):** `3.0` 24.2% → `3.0b` 25.0% → `3.1` **59.1%** → `3.1b` 59.8% exact bucket. Note the **median AE collapse** at 3.1 (`~13°` → `~3°`) — the hybrid nails the bulk of frames; the mean MAE stays ~16° because a minority of wrong-bucket picks are large. **`v3.1b` is the recommended checkpoint** (lower MAE, smoother).

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

## Current Version Snapshot

- **Model:** `3.1` (final checkpoint, epoch 26)
- **Checkpoint:** `SidewalkPilot-v3.1.onnx`
- **Full score:** `91.112%` · **MAE:** `15.998` deg · **Median AE:** `3.162` deg
- **Verdict:** works, but **`v3.1b` is preferred** (smoother, lower error). Keep `v3.1` as the final-epoch reference.

## Intended Use

- RC car autonomy experiments · sidewalk/path steering research · Jetson (ONNX/TensorRT) inference · overfitting / final-vs-best comparison.

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

Same head as `v3.1b` but slightly overtrained: blockier/higher-error steering, needs temporal smoothing. Fails under orange lamppost lighting, untested in shadows, daytime not field-verified, throttle unusable. No braking/reverse/confidence/obstacle outputs. Prefer `v3.1b`.

## Safety Recommendation

Do not use this model alone to control a robot. LiDAR has priority and can override steering or hard-brake; a human kill switch is required for any autonomous motion.

## Model Card Contact

Ram Shreyas Naik Sabavat
