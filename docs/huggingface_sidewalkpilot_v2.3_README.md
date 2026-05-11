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

# SidewalkPilot-v2.3

SidewalkPilot-v2.3 is a PyTorch steering model for a small autonomous RC car. It predicts a steering servo angle from `0` to `180` degrees and was trained after removing horizontal flip augmentation from the v2.2 training direction.

This checkpoint belongs to **Series 2 raw-BGR**. It uses the raw-BGR path, not the legacy v2.0 HSV/CLAHE preprocessing path.

## Model Details

- **Developed by:** Ram Shreyas Naik Sabavat
- **Model type:** CNN steering regression model
- **Library:** PyTorch
- **License:** Apache 2.0
- **Checkpoint:** `SidewalkPilot-v2.3.pth`
- **Checkpoint created:** 2026-05-09 08:50 PM America/Los_Angeles
- **Input:** Full OpenCV BGR camera frame
- **Preprocessing:** `BGR -> resize 200x66 -> normalize`
- **Output:** Steering servo angle from `0` to `180`
- **Series:** `2.x`
- **Output scale:** approximately `5..175`

## Specific Improvements

- Removed horizontal flip augmentation because the real RC car does not experience mirrored road-edge geometry the same way as a flipped image.
- Kept the raw-BGR Series 2 inference path instead of the legacy v2.0 CLAHE path.
- Became the strongest offline Series 2 checkpoint before the D0510 field-run merge: `2.726` MAE on the `1,464`-label evaluation set.
- Used shadow/domain augmentation while keeping flip, HSV, and CLAHE probabilities at `0.0` for the trained image path.

## Specific Issues Observed / Remaining

- Field testing showed failures on turns, right-side road-edge driving, and driveway transitions.
- These failures produced the D0510 v2.3 field-run images that were merged into the dataset after this checkpoint was trained.
- Shadow-specific field behavior has not been measured for this checkpoint yet.
- The offline MAE improvement did not solve the right-side road-edge and driveway behavior in the real car.

## Output Meaning

| Output | Meaning |
|---:|---|
| `0` | full left |
| `90` | straight |
| `180` | full right |

## Evaluation Setup

- **Eval set:** `1464` images
- **Failed samples:** `0`
- **Corrections included at evaluation time:** `1464`
- **Input format:** `200x66`, OpenCV BGR
- **Output scale:** servo angle `0..180`
- **Error unit:** servo degrees
- **Score formula:** `max(0, 100 * (1 - absolute_error / 180))`
- **Dataset note:** D0510 v2.3 field-run images were merged after this evaluation set was generated.

## Version Update Categories

| Version | Main update category | Data/status | Result |
|---|---|---|---|
| `1.7b` | Known-good field rollback | photo_20260429 | 0.6 mi, 0 overtakes |
| `1.8` | Mainly shadow fixes | photo_20260502_12 | strong shadow subset improvement |
| `1.9` | Right hard turns, small curb hugging, smoother drive | photo_20260502_19 | best Series 1 field-relevant baseline |
| `2.0` | First HSV/CLAHE Series 2 model | D0503 harsh sidewalk + Series 2 preprocessing | legacy CLAHE baseline; failed 8pm field test |
| `2.0b` | Best checkpoint from v2.0 training | same v2.0 training run | best checkpoint; failed 8pm field test |
| `2.1` | Raw-BGR augmentation Series 2 model | CARLA + real + corrections, no runtime CLAHE | returned newer Series 2 to raw BGR |
| `2.1b` | Best checkpoint from v2.1 training | same v2.1 training run | slightly stronger v2.1 checkpoint offline |
| `2.2` | D0328/D0329 relabel + stronger augmentation | First Dataset relabel + shadow/domain augmentation | strong offline result; field failed by entering grass after about 5 seconds |
| `2.2b` | Best checkpoint from v2.2 training | same v2.2 training run | best offline; field failed by entering grass after about 5 seconds |
| `2.3` | No-flip raw-BGR Series 2 training | 1,464-label set before D0510 field capture; flip probability 0.0 | best offline before D0510 merge; field failed on turns, right-side road-edge driving, and driveways |

## Evaluation Summary

| Model | Checkpoint | Full Score | MAE | Median AE | Max AE | Signed Error | Within 2° | Within 5° | Within 10° | Within 20° |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2.0` | `SidewalkPilot-v2.0.pth` | `93.727%` | `11.292` | `4.931` | `149.967` | `-2.598` | `464 / 1464` | `741 / 1464` | `938 / 1464` | `1179 / 1464` |
| `2.0b` | `SidewalkPilot-v2.0b.pth` | `93.712%` | `11.318` | `4.990` | `149.489` | `-2.565` | `459 / 1464` | `735 / 1464` | `932 / 1464` | `1179 / 1464` |
| `2.1` | `SidewalkPilot-v2.1.pth` | `93.523%` | `11.659` | `5.392` | `156.367` | `-0.984` | `325 / 1464` | `660 / 1464` | `953 / 1464` | `1187 / 1464` |
| `2.1b` | `SidewalkPilot-v2.1b.pth` | `93.564%` | `11.585` | `5.425` | `155.585` | `-0.988` | `325 / 1464` | `657 / 1464` | `954 / 1464` | `1188 / 1464` |
| `2.2` | `SidewalkPilot-v2.2.pth` | `97.654%` | `4.223` | `3.304` | `35.452` | `0.250` | `479 / 1464` | `984 / 1464` | `1350 / 1464` | `1454 / 1464` |
| `2.2b` | `SidewalkPilot-v2.2b.pth` | `97.665%` | `4.203` | `3.240` | `41.550` | `0.083` | `498 / 1464` | `1000 / 1464` | `1343 / 1464` | `1453 / 1464` |
| `2.3` | `SidewalkPilot-v2.3.pth` | `98.486%` | `2.726` | `1.882` | `25.110` | `0.043` | `757 / 1464` | `1203 / 1464` | `1432 / 1464` | `1461 / 1464` |

Negative signed error means the model is left-biased on average.

## Prediction Distribution

| Model | Pred Min | Pred Max | Pred Mean | Pred Median | Pred P05 | Pred P25 | Pred P75 | Pred P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `2.0` | `5.000` | `175.000` | `93.704` | `90.196` | `36.160` | `72.589` | `111.827` | `171.222` |
| `2.0b` | `5.000` | `175.000` | `93.737` | `90.271` | `35.872` | `72.557` | `111.818` | `171.282` |
| `2.1` | `5.000` | `175.000` | `95.318` | `91.842` | `39.995` | `74.877` | `110.875` | `172.394` |
| `2.1b` | `5.000` | `175.000` | `95.314` | `91.836` | `40.192` | `75.044` | `111.065` | `172.318` |
| `2.2` | `5.000` | `175.000` | `96.551` | `92.195` | `43.114` | `80.315` | `105.170` | `174.594` |
| `2.2b` | `5.000` | `175.000` | `96.385` | `91.773` | `42.876` | `79.957` | `105.083` | `174.677` |
| `2.3` | `5.000` | `175.000` | `96.345` | `91.488` | `45.723` | `80.446` | `103.326` | `174.805` |

## Ranking

| Rank In This Card | Model | Checkpoint | Score | MAE | Median AE | Max AE | Within 5° | Within 10° | Signed Error |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| `1` | `2.3` | `SidewalkPilot-v2.3.pth` | `98.486%` | `2.726` | `1.882` | `25.110` | `1203 / 1464` | `1432 / 1464` | `0.043` |
| `2` | `2.2b` | `SidewalkPilot-v2.2b.pth` | `97.665%` | `4.203` | `3.240` | `41.550` | `1000 / 1464` | `1343 / 1464` | `0.083` |
| `3` | `2.2` | `SidewalkPilot-v2.2.pth` | `97.654%` | `4.223` | `3.304` | `35.452` | `984 / 1464` | `1350 / 1464` | `0.250` |
| `4` | `2.0` | `SidewalkPilot-v2.0.pth` | `93.727%` | `11.292` | `4.931` | `149.967` | `741 / 1464` | `938 / 1464` | `-2.598` |
| `5` | `2.0b` | `SidewalkPilot-v2.0b.pth` | `93.712%` | `11.318` | `4.990` | `149.489` | `735 / 1464` | `932 / 1464` | `-2.565` |
| `6` | `2.1b` | `SidewalkPilot-v2.1b.pth` | `93.564%` | `11.585` | `5.425` | `155.585` | `657 / 1464` | `954 / 1464` | `-0.988` |
| `7` | `2.1` | `SidewalkPilot-v2.1.pth` | `93.523%` | `11.659` | `5.392` | `156.367` | `660 / 1464` | `953 / 1464` | `-0.984` |

## Field Case Comparison

| Model | D0328 First Dataset MAE | D0329 First Dataset MAE | D0425 street MAE | D0426 curves/shadows MAE | D0427 curved curb MAE | D0429 driveway/shadow MAE | D0502_12 shadow MAE | D0502_19 hard/curb/smooth MAE | D0503 harsh sidewalk MAE | D0506 8pm MAE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2.0` | `17.969` | `20.509` | `2.707` | `2.028` | `2.573` | `1.688` | `2.349` | `2.257` | `1.663` | `35.998` |
| `2.0b` | `18.092` | `20.539` | `2.688` | `2.024` | `2.565` | `1.702` | `2.318` | `2.247` | `1.660` | `35.795` |
| `2.1` | `19.698` | `20.132` | `3.692` | `3.256` | `3.893` | `3.317` | `4.136` | `3.621` | `2.467` | `3.598` |
| `2.1b` | `19.653` | `19.958` | `3.647` | `3.187` | `3.813` | `3.327` | `4.098` | `3.636` | `2.420` | `3.636` |
| `2.2` | `3.839` | `3.619` | `5.420` | `4.700` | `5.660` | `4.392` | `5.685` | `4.739` | `3.531` | `2.505` |
| `2.2b` | `3.812` | `3.559` | `5.460` | `4.967` | `5.611` | `4.376` | `5.668` | `4.716` | `3.499` | `2.624` |
| `2.3` | `2.385` | `2.511` | `3.304` | `3.045` | `3.459` | `2.538` | `3.228` | `3.069` | `2.375` | `3.710` |

## Current Version Snapshot

- **Model:** `2.3`
- **Checkpoint:** `SidewalkPilot-v2.3.pth`
- **Checkpoint created:** 2026-05-09 08:50 PM America/Los_Angeles
- **Full score:** `98.486%`
- **MAE:** `2.726` servo degrees
- **Median AE:** `1.882` servo degrees
- **Rank in this card:** `1` of `7` listed checkpoints

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

Detailed dataset composition belongs in the dataset README, not this model card.

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

SidewalkPilot-v2.3 can fail when lighting, sidewalk shape, camera angle, shadows, driveway cuts, curved curbs, grass edges, road-edge position, or evening conditions differ from the training data.

Field testing showed failures on turns, right-side road-edge driving, and driveway transitions. Shadow-specific field behavior has not been measured for this checkpoint yet.

The model does not understand obstacles by itself and is not a standalone safety system.

## Safety Recommendation

Do not use this model alone to control a robot. In the original project, LiDAR has priority over the model and can override steering or trigger hard braking.

## Model Card Contact

Ram Shreyas Naik Sabavat
