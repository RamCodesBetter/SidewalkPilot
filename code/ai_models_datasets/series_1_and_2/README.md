---
pretty_name: SidewalkPilot Series 1 and 2 Steering Dataset
size_categories:
- 1K<n<10K
tags:
- robotics
- autonomous-driving
- rc-car
- computer-vision
- steering-regression
- sidewalk-navigation
- pytorch
---

# SidewalkPilot Series 1 and 2 Steering Dataset

SidewalkPilot Series 1 and 2 is the finalized camera-to-steering dataset for the baseline and failure/iteration model series. The dataset pairs real field images with steering servo labels in degrees, so a model can learn to map a camera frame to a steering command.

Project code and documentation are maintained in the GitHub repo:

| Resource | Link |
|---|---|
| GitHub repository | `https://github.com/RamCodesBetter/SidewalkPilot` |
| Hugging Face dataset | `https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v1_and_v2` |
| Hugging Face model namespace | `https://huggingface.co/ram-shreyas-naik-sabavat` |

## Dataset Contents

| File or folder | What it contains |
|---|---|
| `sidewalkpilot_dataset/` | JPG field images used for steering training and evaluation |
| `steering_corrections.json` | Steering labels, source names, and repeat weights for each labeled image |
| `sidewalkpilot_trainer.py` | Training script used with the labeled image dataset |

## Current Size

| Item | Count |
|---|---:|
| JPG images | 2,224 |
| Steering label entries | 2,224 |
| Label sources | 13 |
| Steering range | 0 to 180 degrees |

## Label Format

`steering_corrections.json` is a JSON list. Each entry points to one image and stores the steering target used for training.

| Field | Type | Meaning |
|---|---|---|
| `image` | string | Relative image path used by the training code |
| `steering` | number | Servo angle label in degrees |
| `repeat` | integer | Training repeat/weight value for that sample |
| `source` | string | Dataset source or field-test group for the image |

Example entry:

```json
{
  "image": "sidewalkpilot_dataset/photo_20260425_145756.jpg",
  "steering": 110.0,
  "repeat": 50,
  "source": "D0425_street_test"
}
```

## Steering Label Meaning

The steering label is a servo angle in degrees.

| Steering value | Meaning |
|---:|---|
| 0 | Hard left |
| 90 | Straight / center |
| 180 | Hard right |

## Steering Distribution

| Steering bucket | Count |
|---|---:|
| 0-45 hard left | 69 |
| 45-75 left | 128 |
| 75-85 soft left | 281 |
| 85-95 straight | 678 |
| 95-105 soft right | 547 |
| 105-135 right | 311 |
| 135-180 hard right | 199 |

## Source Breakdown

| Source | Count | Purpose |
|---|---:|---|
| `D0328_first_dataset_relabel` | 315 | First dataset relabel |
| `D0329_first_dataset_relabel` | 413 | First dataset relabel |
| `D0425_street_test` | 65 | Street test images |
| `D0426_curves_shadows` | 53 | Curves and shadow cases |
| `D0427_curved_curb` | 72 | Curved curb behavior |
| `D0429_driveway_shadow_fix` | 53 | Driveway and shadow cases |
| `D0502_shadow_fix` | 154 | Shadow robustness |
| `D0502_19_hard_turn_curb_smoothness_fix` | 156 | Hard turns, curb hugging, and smoothness |
| `D0503_harsh_sidewalk` | 159 | Harsh sidewalk surface cases |
| `D0506_8pm_sidewalk` | 24 | Evening / low-light sidewalk cases |
| `D0510_v2_3_run_1` | 167 | SidewalkPilot v2.3 field-run capture, run 1 |
| `D0510_v2_3_run_2` | 8 | SidewalkPilot v2.3 field-run capture, run 2 |
| `D0510_v2_3_run_3` | 585 | SidewalkPilot v2.3 field-run capture, run 3 |

## Image Sizes

| Resolution | Count |
|---|---:|
| 1280 x 720 | 1,496 |
| 1920 x 1080 | 413 |
| 320 x 240 | 315 |

The training pipeline resizes images before inference/training, so mixed capture resolutions are expected.

## Basic Loading Example

```python
from pathlib import Path
import json

dataset_root = Path("sidewalkpilot_dataset")
labels = json.loads(Path("steering_corrections.json").read_text())

first = labels[0]
image_name = Path(first["image"]).name
image_path = dataset_root / image_name
steering_degrees = float(first["steering"])

print(image_path, steering_degrees)
```

## Training Use

The labels are intended for the SidewalkPilot steering trainer. The current training setup uses the image folder plus `steering_corrections.json` as the correction/label source.

Typical local training flow:

```bash
python3 sidewalkpilot_trainer.py \
  --roots sidewalkpilot_dataset \
  --corrections steering_corrections.json \
  --model-version 2.4
```

Exact training commands may differ depending on whether CARLA data, source weighting, shadow augmentation, or other augmentation settings are being used.

## Evaluation Use

The dataset is used to compare SidewalkPilot model checkpoints on the same labeled image set. Common metrics include:

| Metric | Meaning |
|---|---|
| MAE | Mean absolute steering error in degrees |
| Median AE | Median absolute steering error in degrees |
| Max AE | Largest steering error in degrees |
| Signed Error | Directional bias of model predictions |
| Within 2 / 5 / 10 / 20 degrees | Count of predictions inside each tolerance band |
| Subset MAE | MAE grouped by field-test source |

## Intended Scope

This dataset supports the closed Series 1.x and 2.x research cycle. Series 1.x was the baseline working series, while Series 2.x pushed the same steering-only architecture to its limits and recorded the failure/iteration data used to design Series 3.x.

This dataset is finalized for the Series 1/2 Hugging Face release. New steering+throttle data should go into the separate Series 3 dataset instead.
