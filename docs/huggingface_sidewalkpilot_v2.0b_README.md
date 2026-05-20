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
- pytorch
- raspberry-pi
---

# SidewalkPilot-v2.0b

SidewalkPilot-v2.0b is the best-checkpoint variant of SidewalkPilot-v2.0. It is a PyTorch steering model for a small autonomous RC car and predicts a steering servo angle from `0` to `180` degrees.

This checkpoint belongs to **Series 2**, meaning it expects HSV/CLAHE brightness normalization before the CNN. It uses the HSV/CLAHE path, not the raw Series 1 BGR-only pipeline.

## Model Details

- **Developed by:** Ram Shreyas Naik Sabavat
- **Model type:** CNN steering regression model
- **Library:** PyTorch
- **License:** Apache 2.0
- **Checkpoint:** `SidewalkPilot-v2.0b.pth`
- **Checkpoint created:** 2026-05-05 06:35 PM America/Los_Angeles
- **Input:** Full OpenCV BGR camera frame
- **Preprocessing:** `BGR -> HSV -> CLAHE(V) -> BGR -> resize 200x66 -> normalize`
- **Output:** Steering servo angle from `0` to `180`
- **Series:** `2.x`
- **Output scale:** approximately `5..175`

## Specific Improvements

- Saved the best checkpoint from the v2.0 HSV/CLAHE training run.
- Used the same Series 2 HSV/CLAHE path as v2.0 for harsh-sidewalk and low-contrast lighting tests.
- Exposed the same field failure mode as v2.0 during the 8pm run, giving a matched final-vs-best comparison.

## Specific Issues Observed / Remaining

- Field tested around 8pm and failed to drive smoothly enough for deployment.
- Observed field failures: sidewalk swerving, road entry, and driveway entry.
- `photo_20260506` 8pm images were collected after this field test and merged afterward as `D0506_8pm_sidewalk`.
- Best-checkpoint selection did not solve the real 8pm lighting distribution shift.

## Output Meaning

| Output | Meaning |
|---:|---|
| `0` | full left |
| `90` | straight |
| `180` | full right |

## Evaluation Setup

- **Eval set:** `1,446` images
- **Failed samples:** `0`
- **Corrections included at evaluation time:** `723`
- **Input format:** `200x66`, OpenCV BGR after HSV/CLAHE preprocessing
- **Output scale:** servo angle `0..180`
- **Error unit:** servo degrees
- **Score formula:** `max(0, 100 * (1 - absolute_error / 180))`

## Version Update Categories

| Version | Main update category | Data/status | Result |
|---|---|---|---|
| `1.7b` | Known-good field rollback | `photo_20260429` | 0.6 mi, 0 overtakes |
| `1.8` | Mainly shadow fixes | `photo_20260502_12` | strong shadow subset improvement |
| `1.9` | Right hard turns, small curb hugging, smoother drive | `photo_20260502_19` | best Series 1 offline model |
| `2.0` | First HSV/CLAHE Series 2 model | `photo_20260503 harsh sidewalk + Series 2 preprocessing` | final checkpoint; failed 8pm field test |
| `2.0b` | Best checkpoint from v2.0 training | `same v2.0 training run` | best checkpoint; failed 8pm field test |

## Evaluation Summary

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2° | Within 5° | Within 10° | Within 20° |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2.0` | `SidewalkPilot-v2.0.pth` | `96.637%` | `6.053` | `3.092` | `84.335` | `-1.246` | `552 / 1446` | `904 / 1446` | `1183 / 1446` | `1360 / 1446` |
| `2.0b` | `SidewalkPilot-v2.0b.pth` | `96.637%` | `6.054` | `3.142` | `84.934` | `-1.214` | `544 / 1446` | `900 / 1446` | `1180 / 1446` | `1357 / 1446` |

Negative signed error means the model is left-biased on average.

## Prediction Distribution

| Model | Pred Min | Pred Max | Pred Mean | Pred Median | Pred P05 | Pred P25 | Pred P75 | Pred P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `2.0` | `5.000` | `175.000` | `93.942` | `90.517` | `36.168` | `72.603` | `112.267` | `171.486` |
| `2.0b` | `5.000` | `175.000` | `93.973` | `90.415` | `35.914` | `72.584` | `112.356` | `171.711` |

## Ranking

| Rank In This Card | Model | Checkpoint | Score | MAE | Median AE | Max AE | Within 5° | Within 10° | Signed Error |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `1` | `2.0` | `SidewalkPilot-v2.0.pth` | `96.637%` | `6.053` | `3.092` | `84.335` | `904 / 1446` | `1183 / 1446` | `-1.246` |
| `2` | `2.0b` | `SidewalkPilot-v2.0b.pth` | `96.637%` | `6.054` | `3.142` | `84.934` | `900 / 1446` | `1180 / 1446` | `-1.214` |

## Field Case Comparison

| Model | D26 curves/shadows MAE | D27 curved curb MAE | D28 driveway MAE | D29 driveway/shadow MAE | 20260502_12 shadow MAE | 20260502_19 hard/curb/smooth MAE | 20260503 harsh sidewalk MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| `2.0` | `2.028` | `2.574` | `3.358` | `1.688` | `2.349` | `2.256` | `1.663` |
| `2.0b` | `2.024` | `2.565` | `3.457` | `1.702` | `2.319` | `2.247` | `1.660` |

## Current Version Snapshot

- **Model:** `2.0b`
- **Checkpoint:** `SidewalkPilot-v2.0b.pth`
- **Checkpoint created:** 2026-05-05 06:35 PM America/Los_Angeles
- **Full score:** `96.637%`
- **MAE:** `6.054` servo degrees
- **Median AE:** `3.142` servo degrees
- **Rank in this card:** `2` of `2` listed checkpoints

## Intended Use

This model is intended for:

- RC car autonomy experiments
- Sidewalk/path steering research
- Raspberry Pi robotics projects
- Small-scale computer vision control systems
- Testing direct image-to-servo steering regression

## Out-of-Scope Use

This model is not intended for:

- Real cars
- Public road vehicles
- Human transportation
- Safety-critical systems
- Fully autonomous deployment without external safety layers

## System Context

```text
camera frame
-> HSV/CLAHE brightness normalization
-> resize/normalize image
-> PyTorch steering model
-> predicted servo angle
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

The model was trained on camera images collected from the RC car driving in sidewalk-like environments. Labels represent steering servo angles from `0` to `180` degrees.

Series 2 adds HSV/CLAHE preprocessing and targeted harsh-sidewalk corrections. The `photo_20260506` 8pm images were collected after this checkpoint and merged as an additional correction source.

## Preprocessing

During inference/evaluation, the Series 2 pipeline is:

```text
camera frame in OpenCV BGR
-> convert BGR to HSV
-> apply CLAHE to the V brightness channel
-> convert HSV back to BGR
-> resize to 200x66
-> normalize
-> PyTorch steering model
-> servo angle
```

Raw HSV is not the model input. The model still receives BGR-like tensors. Running this checkpoint on raw BGR without HSV/CLAHE creates a training/evaluation mismatch.

## Limitations

SidewalkPilot-v2.0b can fail when lighting, sidewalk shape, camera angle, shadows, driveway cuts, curved curbs, or evening conditions differ from the training data.

The model was field tested around 8pm and failed with swerving, road-entry, and driveway-entry behavior. It is not a replacement for a proven rollback checkpoint without retraining.

The model does not understand obstacles by itself and is not a standalone safety system.

## Safety Recommendation

Do not use this model alone to control a robot. In the original project, LiDAR has priority over the model and can override steering or trigger hard braking.

## Model Card Contact

Ram Shreyas Naik Sabavat
