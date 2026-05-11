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

# SidewalkPilot-v1.3b

SidewalkPilot-v1.3b is a PyTorch steering model for a small autonomous RC car. It takes a full camera frame as input and predicts a steering servo angle from `0` to `180` degrees.

The model is used for camera-based sidewalk/path following. In the full RC car stack, LiDAR runs above the model as a safety layer for obstacle avoidance, LiDAR override steering, and hard braking.

This is a best-checkpoint (`b`) variant from the same training version.

## Model Details

- **Developed by:** Ram Shreyas Naik Sabavat
- **Model type:** CNN steering regression model
- **Library:** PyTorch
- **License:** Apache 2.0
- **Checkpoint:** `SidewalkPilot-v1.3b.pth`
- **Checkpoint created:** 2026-04-26 04:50 PM America/Los_Angeles
- **Input:** Full camera frame, resized/normalized before inference
- **Evaluation input format:** `200x66`, OpenCV BGR
- **Output:** Steering servo angle from `0` to `180`

## Specific Improvements

- Saved the best checkpoint from the v1.3 smoothness/aggression run.
- Kept broad sidewalk steering functional enough for direct comparison with v1.3 final.
- Preserved the same raw-BGR Series 1 runtime path, so differences were checkpoint-only, not preprocessing changes.

## Specific Issues Observed / Remaining

- Worse than v1.3 final on full-set score and MAE.
- Driveway and curb-smoothness failure risk stayed visible in the subset tables.
- Best-checkpoint selection did not improve the specific failure that motivated later driveway data.

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
| `1.1` | Street-test correction pass | `manual street corrections` | complete |
| `1.1b` | Best checkpoint from street-correction pass | `same v1.1 training run` | complete |
| `1.2` | Best early field behavior | `no-weather tuning + manual corrections` | complete |
| `1.2b` | Best checkpoint from early field-behavior run | `same v1.2 training run` | complete |
| `1.3` | Smoothness / aggression tuning | `same dataset family` | complete |
| `1.3b` | Best checkpoint from smoothness/aggression run | `same v1.3 training run` | complete |

## Evaluation Summary

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2° | Within 5° | Within 10° | Within 20° |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `1.0` | `SidewalkPilot-v1.0.pth` | `88.339%` | `20.990` | `9.934` | `151.830` | `-7.262` | `202 / 1287` | `423 / 1287` | `648 / 1287` | `869 / 1287` |
| `1.0b` | `SidewalkPilot-v1.0b.pth` | `88.292%` | `21.075` | `10.234` | `152.629` | `-6.691` | `179 / 1287` | `410 / 1287` | `640 / 1287` | `866 / 1287` |
| `1.1` | `SidewalkPilot-v1.1.pth` | `92.372%` | `13.730` | `3.886` | `144.676` | `-6.197` | `434 / 1287` | `746 / 1287` | `916 / 1287` | `1044 / 1287` |
| `1.1b` | `SidewalkPilot-v1.1b.pth` | `92.372%` | `13.730` | `3.886` | `144.676` | `-6.197` | `434 / 1287` | `746 / 1287` | `916 / 1287` | `1044 / 1287` |
| `1.2` | `SidewalkPilot-v1.2.pth` | `93.634%` | `11.459` | `1.018` | `140.617` | `-5.314` | `748 / 1287` | `843 / 1287` | `945 / 1287` | `1058 / 1287` |
| `1.2b` | `SidewalkPilot-v1.2b.pth` | `93.585%` | `11.548` | `1.281` | `140.920` | `-5.296` | `712 / 1287` | `849 / 1287` | `948 / 1287` | `1068 / 1287` |
| `1.3` | `SidewalkPilot-v1.3.pth` | `93.502%` | `11.697` | `1.765` | `148.944` | `-5.557` | `670 / 1287` | `845 / 1287` | `955 / 1287` | `1069 / 1287` |
| `1.3b` | `SidewalkPilot-v1.3b.pth` | `93.223%` | `12.199` | `3.005` | `140.762` | `-5.423` | `483 / 1287` | `823 / 1287` | `961 / 1287` | `1070 / 1287` |

Negative signed error means the model is left-biased on average.

## Prediction Distribution

| Model | Pred Min | Pred Max | Pred Mean | Pred Median | Pred P05 | Pred P25 | Pred P75 | Pred P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `1.0` | `8.459` | `174.146` | `89.579` | `89.676` | `37.520` | `68.904` | `108.229` | `145.649` |
| `1.0b` | `9.009` | `173.933` | `90.149` | `89.734` | `38.399` | `70.772` | `108.074` | `144.783` |
| `1.1` | `4.000` | `176.000` | `90.643` | `89.761` | `37.944` | `72.754` | `106.427` | `152.011` |
| `1.1b` | `4.000` | `176.000` | `90.643` | `89.761` | `37.944` | `72.754` | `106.427` | `152.011` |
| `1.2` | `4.000` | `176.000` | `91.526` | `91.271` | `41.237` | `72.686` | `108.045` | `149.390` |
| `1.2b` | `4.000` | `176.000` | `91.544` | `91.210` | `40.153` | `72.763` | `107.837` | `149.399` |
| `1.3` | `4.000` | `176.000` | `91.283` | `90.486` | `40.523` | `73.660` | `106.509` | `149.883` |
| `1.3b` | `4.000` | `176.000` | `91.417` | `90.950` | `41.317` | `74.564` | `105.508` | `149.390` |

## Ranking

| Rank In This Card | Model | Checkpoint | Score | MAE | Median AE | Max AE | Within 5° | Within 10° | Signed Error |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `1` | `1.2` | `SidewalkPilot-v1.2.pth` | `93.634%` | `11.459` | `1.018` | `140.617` | `843 / 1287` | `945 / 1287` | `-5.314` |
| `2` | `1.2b` | `SidewalkPilot-v1.2b.pth` | `93.585%` | `11.548` | `1.281` | `140.920` | `849 / 1287` | `948 / 1287` | `-5.296` |
| `3` | `1.3` | `SidewalkPilot-v1.3.pth` | `93.502%` | `11.697` | `1.765` | `148.944` | `845 / 1287` | `955 / 1287` | `-5.557` |
| `4` | `1.3b` | `SidewalkPilot-v1.3b.pth` | `93.223%` | `12.199` | `3.005` | `140.762` | `823 / 1287` | `961 / 1287` | `-5.423` |
| `5` | `1.1` | `SidewalkPilot-v1.1.pth` | `92.372%` | `13.730` | `3.886` | `144.676` | `746 / 1287` | `916 / 1287` | `-6.197` |
| `6` | `1.1b` | `SidewalkPilot-v1.1b.pth` | `92.372%` | `13.730` | `3.886` | `144.676` | `746 / 1287` | `916 / 1287` | `-6.197` |
| `7` | `1.0` | `SidewalkPilot-v1.0.pth` | `88.339%` | `20.990` | `9.934` | `151.830` | `423 / 1287` | `648 / 1287` | `-7.262` |
| `8` | `1.0b` | `SidewalkPilot-v1.0b.pth` | `88.292%` | `21.075` | `10.234` | `152.629` | `410 / 1287` | `640 / 1287` | `-6.691` |

## Field Case Comparison

| Model | D26 curves/shadows MAE | D27 curved curb MAE | D28 driveway MAE | D29 driveway/shadow MAE | 20260502_12 shadow MAE | 20260502_19 hard/curb/smooth MAE |
|---|---:|---:|---:|---:|---:|---:|
| `1.0` | `44.12` | `53.69` | `56.18` | `37.44` | `29.57` | `29.57` |
| `1.0b` | `42.85` | `54.06` | `57.52` | `37.39` | `29.16` | `29.76` |
| `1.1` | `38.93` | `36.60` | `83.08` | `33.44` | `21.42` | `26.13` |
| `1.1b` | `38.93` | `36.60` | `83.08` | `33.44` | `21.42` | `26.13` |
| `1.2` | `36.54` | `31.76` | `64.48` | `25.38` | `20.86` | `22.74` |
| `1.2b` | `35.95` | `32.11` | `61.94` | `25.46` | `21.01` | `22.78` |
| `1.3` | `35.00` | `34.06` | `74.95` | `25.26` | `19.51` | `22.92` |
| `1.3b` | `34.10` | `35.63` | `71.75` | `24.12` | `19.66` | `22.96` |

## Current Version Snapshot

- **Model:** `1.3b`
- **Checkpoint:** `SidewalkPilot-v1.3b.pth`
- **Checkpoint created:** 2026-04-26 04:50 PM America/Los_Angeles
- **Full score:** `93.223%`
- **MAE:** `12.199` servo degrees
- **Median AE:** `3.005` servo degrees
- **Rank in this card:** `4` of `8` checkpoints

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
