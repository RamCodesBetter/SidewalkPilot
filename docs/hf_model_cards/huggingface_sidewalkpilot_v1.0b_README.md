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

# SidewalkPilot-v1.0b

SidewalkPilot-v1.0b is a PyTorch steering model for a small autonomous RC car. It takes a full camera frame as input and predicts a steering servo angle from `0` to `180` degrees.

The model is used for camera-based sidewalk/path following. In the full RC car stack, LiDAR runs above the model as a safety layer for obstacle avoidance, LiDAR override steering, and hard braking.

This is a best-checkpoint (`b`) variant from the same training version.

## Model Details

- **Developed by:** Ram Shreyas Naik Sabavat
- **Model type:** CNN steering regression model
- **Library:** PyTorch
- **License:** Apache 2.0
- **Checkpoint:** `SidewalkPilot-v1.0b.pth`
- **Checkpoint created:** 2026-04-24 10:05 PM America/Los_Angeles
- **Input:** Full camera frame, resized/normalized before inference
- **Evaluation input format:** `200x66`, OpenCV BGR
- **Output:** Steering servo angle from `0` to `180`

## Specific Improvements

- Saved the best checkpoint from the same v1.0 baseline run: `SidewalkPilot-v1.0b.pth`.
- Kept the same raw BGR `200x66` inference path as v1.0, giving a direct final-vs-best comparison.
- Matched the initial baseline family closely enough to confirm the v1.0 run was stable, not a one-off checkpoint.

## Specific Issues Observed / Remaining

- Did not beat v1.0 final on the expanded evaluation set.
- Full-set MAE stayed around the same weak baseline level as v1.0 instead of solving the large failure subsets.
- Kept the same early weaknesses: curved curb, driveway, shadow, and hard-turn cases remained unreliable.

## Output Meaning

| Output | Meaning |
|---:|---|
| `0` | full left |
| `90` | straight |
| `180` | full right |

## Evaluation Setup

- **Eval set:** `1,287` images
- **Failed samples:** `0`
- **Corrections included:** `564`
- **Input format:** `200x66`, OpenCV BGR
- **Output scale:** servo angle `0..180`
- **Error unit:** servo degrees
- **Score formula:** `max(0, 100 * (1 - absolute_error / 180))`

## Version Update Categories

| Version | Main update category | Data/status | Result |
|---|---|---|---|
| `1.0` | Baseline steering | `initial mixed sidewalk/CARLA set` | complete |
| `1.0b` | Best-checkpoint variant of baseline | `same v1.0 training run` | complete |

## Evaluation Summary

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2° | Within 5° | Within 10° | Within 20° |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `1.0` | `SidewalkPilot-v1.0.pth` | `88.339%` | `20.990` | `9.934` | `151.830` | `-7.262` | `202 / 1287` | `423 / 1287` | `648 / 1287` | `869 / 1287` |
| `1.0b` | `SidewalkPilot-v1.0b.pth` | `88.292%` | `21.075` | `10.234` | `152.629` | `-6.691` | `179 / 1287` | `410 / 1287` | `640 / 1287` | `866 / 1287` |

Negative signed error means the model is left-biased on average.

## Prediction Distribution

| Model | Pred Min | Pred Max | Pred Mean | Pred Median | Pred P05 | Pred P25 | Pred P75 | Pred P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `1.0` | `8.459` | `174.146` | `89.579` | `89.676` | `37.520` | `68.904` | `108.229` | `145.649` |
| `1.0b` | `9.009` | `173.933` | `90.149` | `89.734` | `38.399` | `70.772` | `108.074` | `144.783` |

## Ranking

| Rank In This Card | Model | Checkpoint | Score | MAE | Median AE | Max AE | Within 5° | Within 10° | Signed Error |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `1` | `1.0` | `SidewalkPilot-v1.0.pth` | `88.339%` | `20.990` | `9.934` | `151.830` | `423 / 1287` | `648 / 1287` | `-7.262` |
| `2` | `1.0b` | `SidewalkPilot-v1.0b.pth` | `88.292%` | `21.075` | `10.234` | `152.629` | `410 / 1287` | `640 / 1287` | `-6.691` |

## Field Case Comparison

| Model | D26 curves/shadows MAE | D27 curved curb MAE | D28 driveway MAE | D29 driveway/shadow MAE | 20260502_12 shadow MAE | 20260502_19 hard/curb/smooth MAE |
|---|---:|---:|---:|---:|---:|---:|
| `1.0` | `44.12` | `53.69` | `56.18` | `37.44` | `29.57` | `29.57` |
| `1.0b` | `42.85` | `54.06` | `57.52` | `37.39` | `29.16` | `29.76` |

## Current Version Snapshot

- **Model:** `1.0b`
- **Checkpoint:** `SidewalkPilot-v1.0b.pth`
- **Checkpoint created:** 2026-04-24 10:05 PM America/Los_Angeles
- **Full score:** `88.292%`
- **MAE:** `21.075` servo degrees
- **Median AE:** `10.234` servo degrees
- **Rank in this card:** `2` of `2` checkpoints

## Intended Use

This model is intended for:

- RC car autonomy experiments
- Sidewalk/path steering research
- Raspberry Pi robotics projects
- Small-scale computer vision control systems
- Testing steering regression from camera images

## Out-of-Scope Use

This model is not intended for:

- Real cars
- Public road vehicles
- Human transportation
- Safety-critical systems
- Fully autonomous deployment without external safety layers

## System Context

The full RC car autonomy stack uses layered control:

```text
camera frame
-> resize/normalize image
-> PyTorch steering model
-> predicted servo angle (0-180)
-> runtime decision logic
-> LiDAR safety override when triggered
-> final steering/throttle/brake command
-> servo + motor controller
```

LiDAR runs as a higher-priority safety layer:

```text
LiDAR clear
-> use model steering

LiDAR obstacle
-> LiDAR override mode

LiDAR blocked/too close
-> hard brake
```

The model handles normal path following, while LiDAR handles obstacle avoidance and emergency behavior.

## Training Data

The model was trained on camera images collected from the RC car driving in sidewalk-like environments. Labels represent steering servo angles from `0` to `180` degrees.

Detailed dataset composition belongs in the dataset README, not this model card.

## Preprocessing

During inference/evaluation, the pipeline:

1. Captures the full camera frame.
2. Resizes the image to `200x66`.
3. Uses OpenCV BGR image ordering.
4. Normalizes pixel values with `(x / 255 - 0.5) / 0.5`.
5. Runs the PyTorch model.
6. Clamps the output to `0..180`.

The model sees the whole frame, not a cropped region.

## Limitations

SidewalkPilot models can fail when lighting, sidewalk shape, camera angle, shadows, driveway cuts, curved curbs, hard turns, or curb-hugging cases differ from the training data.

The model does not understand obstacles by itself and is not a standalone safety system.

Use with external safety logic, manual override, and obstacle detection.

## Safety Recommendation

Do not use this model alone to control a robot. In the original project, LiDAR has priority over the model and can override steering or trigger hard braking.

## Model Card Contact

Ram Shreyas Naik Sabavat
