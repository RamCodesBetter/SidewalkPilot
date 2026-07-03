---
pretty_name: SidewalkPilot Series 3 Steering and Throttle Dataset
size_categories:
- 10K<n<100K
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

SidewalkPilot Series 3 is the dataset for the Jetson-only heavy model series. Series 3.x changes the learning target from steering-only control to joint steering and throttle control.

First real batch (2026-07-02): 50,684 manually-driven sidewalk frames over two runs, decode-verified and curated (see the 2026-07-02 Batch section below). All labels are raw human stick commands (imitation learning), never autonomous/model-predicted — Series 3 must not be seeded with old Series 2.x model-predicted labels.

Project code and documentation are maintained in the GitHub repo:

| Resource | Link |
|---|---|
| GitHub repository | `https://github.com/RamCodesBetter/SidewalkPilot` |
| Hugging Face dataset | `https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v3` |
| Hugging Face model namespace | `https://huggingface.co/ram-shreyas-naik-sabavat` |

## Dataset Contents

| File or folder | What it contains |
|---|---|
| `sidewalkpilot_dataset/` | 50,684 human-driving JPGs (2026-07-02) plus `labels.json`. Images are hosted on Hugging Face and gitignored in the repo; the label file is committed. |
| `sidewalkpilot_dataset/labels.json` | Dict-style `image -> {steering, throttle}` for all 50,684 frames. |
| `steering_corrections.json` | Empty list-style correction/override file (optional; not required for training). |
| `sidewalkpilot_trainer.py` | Series 3 training, ONNX export, and TensorRT build script |

## Current Size

| Item | Count |
|---|---:|
| JPG images | 50,684 |
| Steering/throttle label entries | 50,684 |
| Label sources | 2 human-driving runs (2026-07-02) |
| Steering range | 0 to 180 degrees (logical; 90 = straight) |
| Throttle range | 0.00 to 1.00 |

## 2026-07-02 Batch

The first real Series 3 batch: manual human driving on sidewalks / private test routes, captured continuously at ~8-10 fps across two runs, then quality-checked and curated.

| Property | Value |
|---|---|
| Frames | 50,684 (run_1: 6,685 + run_2: 43,999) |
| Capture | Manual human driving; continuous run-capture, ~8 fps effective |
| Labels | Raw human stick command per frame (imitation learning) |
| Steering balance | LEFT (<85) 8.4% · CENTER (85-95) 71% · RIGHT (>95) 20.5% |
| Throttle | ~96.6% at 1.00; effectively constant (driven flat-out) |
| QC | Full Pillow decode-verify; 154 empty crash-tail frames removed; 3,143 frames culled from selected time ranges |

Known limitations to account for in training:

- **Throttle is not learnable from this batch.** Throttle is ~constant (1.0), so the joint steering+throttle target has no throttle variance and the throttle head can only learn "full forward". Varied-throttle runs are needed before the throttle output is meaningful.
- **Steering is center-heavy (71%) and skews right (~2.4:1 over left).** The car has a mechanical left-pull, so straight driving needed a slight right hold. Use horizontal-flip augmentation (mirror image + negate steering) to symmetrize left/right, plus class-balanced sampling and/or a left-heavy top-up run to counter center dominance.
- Split train/val by **time segment, not randomly** — consecutive ~8 fps frames are near-duplicates, and a random split leaks them across train/val (inflated validation scores).

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
labels = json.loads((dataset_root / "labels.json").read_text())  # dict: image -> {steering, throttle}

first_image = next(iter(labels))
image_path = dataset_root / first_image
steering_degrees = float(labels[first_image]["steering"])
throttle = float(labels[first_image]["throttle"])

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
