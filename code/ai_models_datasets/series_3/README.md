---
pretty_name: SidewalkPilot Series 3 Steering and Throttle Dataset
size_categories:
- n<1K
tags:
- robotics
- autonomous-driving
- rc-car
- computer-vision
- steering-regression
- throttle-regression
- sidewalk-navigation
- pytorch
---

# SidewalkPilot Series 3 Steering and Throttle Dataset

SidewalkPilot Series 3 is the empty seed dataset for the Jetson-only heavy model series. Series 3.x changes the learning target from steering-only control to joint steering and throttle control.

The dataset is intentionally empty until new smooth human-driving captures and controlled CARLA samples are collected. Series 3 should not be seeded with autonomous/model-predicted labels from the old Series 2.x runs.

Project code and documentation are maintained in the GitHub repo:

| Resource | Link |
|---|---|
| GitHub repository | `https://github.com/RamCodesBetter/SidewalkPilot` |
| Hugging Face dataset | `https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v3` |
| Hugging Face model namespace | `https://huggingface.co/ram-shreyas-naik-sabavat` |

## Dataset Contents

| File or folder | What it contains |
|---|---|
| `sidewalkpilot_dataset/` | Empty image folder reserved for Series 3 captures |
| `steering_corrections.json` | Empty list-style correction file for merged Series 3 labels |
| `sidewalkpilot_trainer.py` | Series 3 training, ONNX export, and TensorRT build script |

## Current Size

| Item | Count |
|---|---:|
| JPG images | 0 |
| Steering/throttle label entries | 0 |
| Label sources | 0 |
| Steering range | 0 to 180 degrees |
| Throttle range | 0.00 to 1.00 |

## Label Format

`steering_corrections.json` starts as an empty JSON list:

```json
[]
```

During Series 3 data collection, raw photo-run label files are saved separately as dict-style JSON files named like `2026_05_20_run_1.json`. Those files map each captured image to the final steering and throttle commands at that frame.

| Field | Type | Meaning |
|---|---|---|
| image filename key | string | Captured image filename |
| `steering` | number | Final steering servo angle in degrees |
| `throttle` | number | Final forward motor command |

Example entry:

```json
{
  "photo_20260520_123456.jpg": {
    "steering": 92,
    "throttle": 0.37
  }
}
```

When run data is promoted into `steering_corrections.json`, it may be converted into the trainer's list-style correction format.

## Steering Label Meaning

The steering label is a servo angle in degrees.

| Steering value | Meaning |
|---:|---|
| 0 | Hard left |
| 90 | Straight / center |
| 180 | Hard right |

## Throttle Label Meaning

The throttle label is the final forward motor command used by the car at the frame.

| Throttle value | Meaning |
|---:|---|
| 0.00 | Stop |
| 1.00 | Full forward |

Reverse is not a Series 3 model output. Braking, stopping, and reverse behavior remain runtime/safety responsibilities.

## Planned Data Sources

| Source | Status | Purpose |
|---|---|---|
| Smooth human driving | Planned | Main real-world imitation-learning labels |
| CARLA 50k with shadows | Planned | Controlled synthetic shadow and route coverage |
| Data augmentation | Planned | Training-time robustness, not stored as fake raw labels |

Old Series 2.x autonomous/model-predicted labels are not valid Series 3 training labels.

## Basic Loading Example

```python
from pathlib import Path
import json

dataset_root = Path("sidewalkpilot_dataset")
labels = json.loads(Path("steering_corrections.json").read_text())

if labels:
    first = labels[0]
    image_path = dataset_root / Path(first["image"]).name
    steering_degrees = float(first["steering"])
    throttle = float(first["throttle"])

    print(image_path, steering_degrees, throttle)
```

## Training Use

The labels are intended for the SidewalkPilot Series 3 trainer. The training target is:

```text
image -> [steering, throttle]
```

Labels are stored in physical units. The trainer normalizes steering and throttle internally to the `tanh` range before loss calculation.

Series 3 defaults to `320x180` model input size. Throttle is required for every Series 3 training label; samples without throttle are skipped as bad labels.

Typical local training flow:

```bash
python3 sidewalkpilot_trainer.py \
  --roots sidewalkpilot_dataset \
  --corrections steering_corrections.json \
  --model-version 3.0 \
  --export-onnx
```

Jetson TensorRT INT8 build flow:

```bash
python3 sidewalkpilot_trainer.py \
  --roots sidewalkpilot_dataset \
  --corrections steering_corrections.json \
  --model-version 3.0 \
  --export-onnx \
  --build-tensorrt \
  --trt-precision int8
```

The trainer outputs normalized control vectors:

```text
control_norm[0] = steering tanh output, -1.0 to 1.0
control_norm[1] = throttle tanh output, -1.0 to 1.0
```

Exact training commands may differ depending on CARLA data, source weighting, shadow augmentation, ONNX export, TensorRT conversion, and INT8 calibration.

## Augmentation Preview

Use the test helper to preview Series 3 augmentation variations before training:

```bash
python3 ../../test_files/preview_series3_augmentations.py \
  sidewalkpilot_dataset/example.jpg \
  --output /tmp/series3_augmentations.jpg
```

## Evaluation Use

Series 3 evaluation should compare joint steering/throttle prediction quality. Common metrics should include:

| Metric | Meaning |
|---|---|
| Steering MAE | Mean absolute steering error in degrees |
| Throttle MAE | Mean absolute throttle-command error |
| Signed steering error | Directional steering bias |
| Signed throttle error | Over-driving or under-driving bias |
| Field subset metrics | Metrics grouped by route, lighting, source, or capture mode |

## Intended Scope

This dataset supports the Series 3 Jetson-only research direction for SidewalkPilot. It is meant for heavy custom CNN regression models deployed through ONNX/TensorRT with INT8 optimization when calibration data is available.

The dataset should be updated only with synchronized image, steering, and throttle labels from smooth human driving or controlled CARLA collection.
