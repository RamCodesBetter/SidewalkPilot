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

# SidewalkPilot-v2.4

SidewalkPilot-v2.4 is a PyTorch steering regression model for a small autonomous RC car. It predicts a steering servo angle from `0` to `180` degrees from a single OpenCV BGR camera frame.

This checkpoint belongs to **Series 2 raw-BGR**. It keeps the v2.1+ raw-BGR inference path and was trained after the D0510 field-failure images from the v2.3 tests were merged into the Series 1/2 dataset.

## Model Details

- **Developed by:** Ram Shreyas Naik Sabavat
- **Model type:** CNN steering regression model
- **Library:** PyTorch
- **License:** Apache 2.0
- **Checkpoint:** `SidewalkPilot-v2.4.pth`
- **Checkpoint file timestamp:** 2026-05-19 11:28 PM America/Los_Angeles
- **Input:** Full OpenCV BGR camera frame
- **Preprocessing:** `BGR -> resize 200x66 -> normalize`
- **Output:** Steering servo angle from `0` to `180`
- **Series:** `2.x`
- **Output scale:** approximately `5..175`

## Specific Improvements

- Trained after merging the D0510 v2.3 field-run images into the labeled dataset.
- Reduced the D0510 dataset MAE from `4.419` on v2.3 to `3.153` on v2.4.
- Reduced the current evaluation max absolute error from `74.412` on v2.3 to `35.268` on v2.4.
- Kept the raw-BGR inference path and did not return to the legacy v2.0 HSV/CLAHE runtime path.
- Became the second-best Series 2 checkpoint on the current `2,224`-label evaluation set, behind v2.4b.

## Specific Issues Observed / Remaining

- v2.4 improves the D0510 failure set but does not make Series 2 fully reliable in field driving.
- It remains a steering-only behavioral-cloning model, so it does not predict throttle or confidence.
- It still depends on dataset coverage for lighting, driveway transitions, grass edges, shadows, curved curbs, and road-edge position.
- The model does not understand obstacles by itself; LiDAR or another safety layer must remain higher priority.

## Output Meaning

| Output | Meaning |
|---:|---|
| `0` | full left |
| `90` | straight |
| `180` | full right |

## Evaluation Setup

- **Eval set:** `2,224` labeled images
- **Failed samples:** `0`
- **Input format:** `200x66`, OpenCV BGR
- **Output scale:** servo angle `0..180`
- **Error unit:** servo degrees
- **Score formula:** `max(0, 100 * (1 - absolute_error / 180))`
- **Dataset note:** evaluation includes D0510 v2.3 field-run images merged after the v2.3 cards were written.

## Version Update Categories

| Version | Main update category | Data/status | Result |
|---|---|---|---|
| `2.0` | First HSV/CLAHE Series 2 model | D0503 harsh sidewalk + Series 2 preprocessing | legacy CLAHE baseline; failed 8pm field test |
| `2.0b` | Best checkpoint from v2.0 training | same v2.0 training run | best checkpoint; failed 8pm field test |
| `2.1` | Raw-BGR augmentation Series 2 model | CARLA + real + corrections, no runtime CLAHE | returned newer Series 2 to raw BGR |
| `2.1b` | Best checkpoint from v2.1 training | same v2.1 training run | slightly stronger v2.1 checkpoint offline |
| `2.2` | D0328/D0329 relabel + stronger augmentation | First Dataset relabel + shadow/domain augmentation | strong offline result; field failed by entering grass after about 5 seconds |
| `2.2b` | Best checkpoint from v2.2 training | same v2.2 training run | best offline; field failed by entering grass after about 5 seconds |
| `2.3` | No-flip raw-BGR Series 2 training | 1,464-label set before D0510 field capture | best offline before D0510 merge; field failed on turns, right-side road-edge driving, and driveways |
| `2.3b` | Best checkpoint from v2.3 training | same v2.3 training run | second-best offline before D0510 merge |
| `2.4` | D0510 field-failure merge | current 2,224-label set with D0510 included | reduced D0510 error and max-error risk versus v2.3 |

## Evaluation Summary

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2 deg | Within 5 deg | Within 10 deg | Within 20 deg |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2.0` | `SidewalkPilot-v2.0.pth` | `93.820%` | `11.124` | `5.089` | `149.967` | `-2.626` | `609 / 2224` | `1068 / 2224` | `1441 / 2224` | `1838 / 2224` |
| `2.0b` | `SidewalkPilot-v2.0b.pth` | `93.817%` | `11.130` | `5.075` | `149.489` | `-2.620` | `600 / 2224` | `1065 / 2224` | `1436 / 2224` | `1838 / 2224` |
| `2.1` | `SidewalkPilot-v2.1.pth` | `93.998%` | `10.804` | `5.829` | `156.367` | `-1.147` | `477 / 2224` | `981 / 2224` | `1481 / 2224` | `1867 / 2224` |
| `2.1b` | `SidewalkPilot-v2.1b.pth` | `94.029%` | `10.747` | `5.790` | `155.585` | `-1.124` | `478 / 2224` | `978 / 2224` | `1489 / 2224` | `1867 / 2224` |
| `2.2` | `SidewalkPilot-v2.2.pth` | `96.289%` | `6.680` | `4.259` | `82.025` | `-0.224` | `594 / 2224` | `1238 / 2224` | `1802 / 2224` | `2094 / 2224` |
| `2.2b` | `SidewalkPilot-v2.2b.pth` | `96.289%` | `6.679` | `4.225` | `81.599` | `-0.461` | `612 / 2224` | `1254 / 2224` | `1785 / 2224` | `2094 / 2224` |
| `2.3` | `SidewalkPilot-v2.3.pth` | `98.164%` | `3.305` | `1.932` | `74.412` | `0.008` | `1130 / 2224` | `1768 / 2224` | `2102 / 2224` | `2194 / 2224` |
| `2.3b` | `SidewalkPilot-v2.3b.pth` | `98.104%` | `3.412` | `2.049` | `72.656` | `0.409` | `1088 / 2224` | `1743 / 2224` | `2107 / 2224` | `2195 / 2224` |
| `2.4` | `SidewalkPilot-v2.4.pth` | `98.176%` | `3.284` | `2.457` | `35.268` | `-0.228` | `958 / 2224` | `1724 / 2224` | `2130 / 2224` | `2218 / 2224` |

Negative signed error means the model is left-biased on average.

## Prediction Distribution

| Model | Pred Min | Pred Max | Pred Mean | Pred Median | Pred P05 | Pred P25 | Pred P75 | Pred P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `2.3` | `5.000` | `175.000` | `96.330` | `93.637` | `58.413` | `83.261` | `103.241` | `164.996` |
| `2.3b` | `5.000` | `175.000` | `96.731` | `93.984` | `58.649` | `83.543` | `104.039` | `164.766` |
| `2.4` | `5.000` | `175.000` | `96.094` | `93.077` | `57.468` | `82.188` | `103.477` | `164.709` |

## Ranking

| Rank In This Card | Model | Checkpoint | Score | MAE | Median AE | Max AE | Within 5 deg | Within 10 deg | Signed Error |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `1` | `2.4` | `SidewalkPilot-v2.4.pth` | `98.176%` | `3.284` | `2.457` | `35.268` | `1724 / 2224` | `2130 / 2224` | `-0.228` |
| `2` | `2.3` | `SidewalkPilot-v2.3.pth` | `98.164%` | `3.305` | `1.932` | `74.412` | `1768 / 2224` | `2102 / 2224` | `0.008` |
| `3` | `2.3b` | `SidewalkPilot-v2.3b.pth` | `98.104%` | `3.412` | `2.049` | `72.656` | `1743 / 2224` | `2107 / 2224` | `0.409` |
| `4` | `2.2b` | `SidewalkPilot-v2.2b.pth` | `96.289%` | `6.679` | `4.225` | `81.599` | `1254 / 2224` | `1785 / 2224` | `-0.461` |
| `5` | `2.2` | `SidewalkPilot-v2.2.pth` | `96.289%` | `6.680` | `4.259` | `82.025` | `1238 / 2224` | `1802 / 2224` | `-0.224` |
| `6` | `2.1b` | `SidewalkPilot-v2.1b.pth` | `94.029%` | `10.747` | `5.790` | `155.585` | `978 / 2224` | `1489 / 2224` | `-1.124` |
| `7` | `2.1` | `SidewalkPilot-v2.1.pth` | `93.998%` | `10.804` | `5.829` | `156.367` | `981 / 2224` | `1481 / 2224` | `-1.147` |
| `8` | `2.0` | `SidewalkPilot-v2.0.pth` | `93.820%` | `11.124` | `5.089` | `149.967` | `1068 / 2224` | `1441 / 2224` | `-2.626` |
| `9` | `2.0b` | `SidewalkPilot-v2.0b.pth` | `93.817%` | `11.130` | `5.075` | `149.489` | `1065 / 2224` | `1436 / 2224` | `-2.620` |

## Field Case Comparison

| Model | D0328 First Dataset MAE | D0329 First Dataset MAE | D0425 street MAE | D0426 curves/shadows MAE | D0427 curved curb MAE | D0429 driveway/shadow MAE | D0502_12 shadow MAE | D0502_19 hard/curb/smooth MAE | D0503 harsh sidewalk MAE | D0506 8pm MAE | D0510 v2.3 field-run MAE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2.3` | `2.385` | `2.511` | `3.304` | `3.045` | `3.459` | `2.538` | `3.228` | `3.069` | `2.375` | `3.710` | `4.419` |
| `2.3b` | `2.454` | `2.569` | `3.409` | `3.149` | `3.425` | `2.516` | `3.460` | `3.227` | `2.496` | `4.004` | `4.549` |
| `2.4` | `3.143` | `2.959` | `4.091` | `3.970` | `4.122` | `2.480` | `4.658` | `3.597` | `2.845` | `2.477` | `3.153` |

## Current Version Snapshot

- **Model:** `2.4`
- **Checkpoint:** `SidewalkPilot-v2.4.pth`
- **Checkpoint file timestamp:** 2026-05-19 11:28 PM America/Los_Angeles
- **Full score:** `98.176%`
- **MAE:** `3.284` servo degrees
- **Median AE:** `2.457` servo degrees
- **Rank in this card:** `1` of `9` listed checkpoints

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

v2.4 uses the Series 1/2 dataset after the D0510 v2.3 field-run images were merged. Those D0510 images came from field failures around turns, right-side road-edge driving, and driveway transitions.

## Preprocessing

During inference/evaluation, the Series 2 raw-BGR pipeline is:

```text
camera frame in OpenCV BGR
-> resize to 200x66
-> normalize with (x / 255 - 0.5) / 0.5
-> PyTorch steering model
-> servo angle
```

Do not use the v2.0 HSV/CLAHE preprocessing path with this checkpoint. The model expects the same raw-BGR tensor path used by the runtime for v2.1 and newer.

## Limitations

SidewalkPilot-v2.4 can fail when lighting, sidewalk shape, camera angle, shadows, driveway cuts, curved curbs, grass edges, road-edge position, or evening conditions differ from the training data.

The model predicts steering only. It does not predict throttle, reverse, braking, confidence, obstacle presence, or whether the frame is out-of-distribution.

## Safety Recommendation

Do not use this model alone to control a robot. In the original project, LiDAR has priority over the model and can override steering or trigger hard braking.

## Model Card Contact

Ram Shreyas Naik Sabavat
