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

SidewalkPilot Series 3 is the dataset for the Jetson-only heavy model series. Series 3.x changes the learning target from steering-only control to joint steering and throttle control. The dataset pairs real field images with a logical steering servo label (degrees) and the throttle command at each frame, so a model can learn to map a camera frame to a `[steering, throttle]` command.

Aggregate (2026-07-02 through 2026-07-12): 81,237 manually-driven sidewalk frames captured across five runs, decode-verified and curated. All labels are raw human stick commands (imitation learning), never autonomous/model-predicted — Series 3 must not be seeded with old Series 2.x model-predicted labels.

**Not CARLA-assisted.** Series 3 models are trained on **real RC-car photos only** — no CARLA / simulator frames. (The CARLA synthetic dataset is published separately as `SidewalkPilot_carla`; it was only used to assist the earlier CARLA-assisted Series 1/2 models.)

Project code and documentation are maintained in the GitHub repo:

| Resource | Link |
|---|---|
| GitHub repository | `https://github.com/RamCodesBetter/SidewalkPilot` |
| Hugging Face dataset | `https://huggingface.co/datasets/ram-shreyas-naik-sabavat/SidewalkPilot_v3` |
| Hugging Face model namespace | `https://huggingface.co/ram-shreyas-naik-sabavat` |

## Dataset Contents

| File or folder | What it contains |
|---|---|
| `sidewalkpilot_dataset/` | JPG field images plus `labels.json` (the labels the trainer loads) |
| `sidewalkpilot_dataset/labels.json` | Dict-style `image -> {steering, throttle}` for every frame (the sole label file) |
| `sidewalkpilot_trainer.py` | Series 3 training, ONNX export, and TensorRT build script |

## Current Size

| Item | Count |
|---|---:|
| JPG images | 81,237 |
| Steering/throttle label entries | 81,237 |
| Label sources | 5 human-driving runs (2026-07-02 through 2026-07-12) |
| Steering range | 0 to 180 degrees (logical; 90 = straight) |
| Throttle range | 0.00 to 1.00 |

## Label Format

The labels live in `sidewalkpilot_dataset/labels.json` as a dict mapping each image filename to its steering and throttle. This is the file the trainer loads (via `--roots sidewalkpilot_dataset`).

| Field | Type | Meaning |
|---|---|---|
| image filename key | string | Captured image filename |
| `steering` | number | Logical steering servo angle in degrees (0-180) |
| `throttle` | number | Forward motor command (0.00-1.00) |

Example entry:

```json
{
  "2026_07_02_run_2__photo_20260702_170623_008443.jpg": {
    "steering": 90,
    "throttle": 1.0
  }
}
```

`labels.json` is the single source of labels for this dataset; there is no separate corrections/override file.

## Steering Label Meaning

The steering label is a logical servo angle in degrees.

| Steering value | Meaning |
|---:|---|
| 0 | Hard left |
| 90 | Straight / center |
| 180 | Hard right |

## Throttle Label Meaning

The throttle label is the forward motor command used by the car at the frame.

| Throttle value | Meaning |
|---:|---|
| 0.00 | Stop |
| 1.00 | Full forward |

Reverse is not a Series 3 model output. Braking, stopping, and reverse behavior remain runtime/safety responsibilities.

## Steering Distribution

The nine buckets below are the model's steering classes (`STEER_CLASS_BINS`).

| Steering bucket | Count | Share |
|---|---:|---:|
| HL  0-45 hard left     |    691 |  0.9% |
| L   45-60 left         |  1,027 |  1.3% |
| L+  60-75 left         |  2,683 |  3.3% |
| SL  75-85 soft left    |  4,199 |  5.2% |
| ST  85-95 straight     | 53,910 | 66.4% |
| SR  95-105 soft right  |  2,795 |  3.4% |
| R   105-120 right      |  3,899 |  4.8% |
| R+  120-135 right      |  4,061 |  5.0% |
| HR  135-180 hard right |  7,972 |  9.8% |

Grouped: **left 10.6%, straight 66.4%, right 23.1%.** The set is center-heavy and skews right of center: the car has a mechanical left-pull, so straight driving needed a slight right hold. Horizontal-flip augmentation (mirror the image and set the new label to `180 - steering`) symmetrizes left/right, and class-balanced sampling counters center dominance.

## Throttle Distribution

| Throttle bucket | Count | Share |
|---|---:|---:|
| 1.00 full forward | 77,082 | 94.9% |
| 0.95-0.999        |  2,914 |  3.6% |
| 0.50-0.95         |    494 |  0.6% |
| 0.01-0.50         |    231 |  0.3% |
| 0.00 stop         |    516 |  0.6% |

Throttle is effectively constant (~95% at full) because these batches were driven flat-out. There is almost no throttle variance, so the throttle head cannot learn meaningful throttle control from this data alone — treat it as a steering dataset until varied-throttle runs are added.

## Source Breakdown

| Source | Count | Purpose |
|---|---:|---|
| `2026_07_02_run_1` |  6,685 | Manual human driving, 2026-07-02 run 1 (crash-truncated tail removed) |
| `2026_07_02_run_2` | 43,999 | Manual human driving, 2026-07-02 run 2 (main capture) |
| `2026_07_07_run_1` |  6,524 | Manual human driving, 2026-07-07 |
| `2026_07_12_run_1` |  2,102 | Manual human driving, 2026-07-12 run 1 |
| `2026_07_12_run_2` | 21,927 | Manual human driving, 2026-07-12 run 2 (103-frame segment culled) |

## Image Sizes

| Resolution | Count |
|---|---:|
| 1280 x 720 | 81,237 |

The training pipeline resizes images (Series 3 default input `320x180`) before training/inference.

## Data Quality and Known Limitations

- Full Pillow decode-verify pass; 154 empty crash-tail frames removed, 3,143 frames culled from selected time ranges. No corrupt/truncated frames remain.
- **Throttle is near-constant** (see Throttle Distribution) — not learnable from this batch; needs varied-throttle runs.
- **Steering is center-heavy and right-skewed** (see Steering Distribution) — use horizontal-flip augmentation + class-balanced sampling.
- Consecutive frames (8-10 fps) are near-duplicates; split train/val **by time segment, not randomly**, to avoid leakage inflating validation scores.

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
  --model-version 3.0 \
  --export-onnx
```

Jetson TensorRT INT8 build flow:

```bash
python3 sidewalkpilot_trainer.py \
  --roots sidewalkpilot_dataset \
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

## Evaluation Use

Series 3 evaluation should compare joint steering/throttle prediction quality. Common metrics include:

| Metric | Meaning |
|---|---|
| Steering MAE | Mean absolute steering error in degrees |
| Throttle MAE | Mean absolute throttle-command error |
| Signed steering error | Directional steering bias |
| Signed throttle error | Over-driving or under-driving bias |
| Field subset metrics | Metrics grouped by route, lighting, source, or capture mode |

## Augmentation Preview

Use the test helper to preview Series 3 augmentation variations before training:

```bash
python3 ../../test_files/preview_series3_augmentations.py \
  sidewalkpilot_dataset/<example>.jpg \
  --output /tmp/series3_augmentations.jpg
```

## Intended Scope

This dataset supports the Series 3 Jetson-only research direction for SidewalkPilot. It is meant for heavy custom CNN regression models deployed through ONNX/TensorRT with INT8 optimization when calibration data is available.

The dataset should be updated only with synchronized image, steering, and throttle labels from smooth human driving or controlled CARLA collection.
