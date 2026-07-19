# Training Pipeline Overview

SidewalkPilot training begins with a supervised field drive and ends only after an exported ONNX model passes offline and physical-car review.

## Pipeline

[![SidewalkPilot training and evaluation flow from field data and CARLA-assisted Series 1 and 2 data through family-specific trainers, GPU training, ONNX export, offline evaluation, and supervised field comparison](../../assets/diagrams/training-evaluation.svg)](../../assets/diagrams/training-evaluation.svg)

*Training and evaluation flow. Open the [full-size SVG](../../assets/diagrams/training-evaluation.svg) or the [editable draw.io source](../../assets/diagrams/training-evaluation.drawio).*

## Series-Specific Trainers

| Family | Trainer | Input | Output contract |
|---|---|---|---|
| Series 1/2 | `code/ai_models_datasets/series_1_and_2/sidewalkpilot_trainer.py` | 200x66 | One direct steering-regression value |
| Series 3 | `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py` | 320x180 | v3.0 two outputs; v3.1+ 19-value hybrid head |
| Series 4 PC | `series_4_0pr_sidewalkpilot_trainer.py`, `series_4_1pr_sidewalkpilot_trainer.py` | image + three previous targets | one 18-value current steering horizon |
| Series 4 CF | `series_4_0fg_sidewalkpilot_trainer.py`, `series_4_1fg_sidewalkpilot_trainer.py` | image | four 18-value current/future steering horizons |
| Series 4 PCF | `series_4_0ac_sidewalkpilot_trainer.py`, `series_4_1ac_sidewalkpilot_trainer.py` | image + three previous targets | four 18-value current/future steering horizons |

Each family still needs its own preprocessing and output decoder. The common evaluator provides those adapters and scores all 52 checkpoints on the same frozen 6,952-frame Series 3/4 challenge subset. Series 3 and experimental Series 4 train on the same 81,237-image dataset.

## Series 4 Temporal Comparison

Series 4 removes throttle learning and keeps the Series 3 visual backbone and nine steering bins. Every horizon is 18 values: nine class logits plus nine class-local offsets. Previous-target history is a causal runtime input for PC/PCF; future targets are training supervision for CF/PCF and are never runtime inputs.

The model names form six final/validation-selected pairs:

| W&B run | Final epoch | Best validation |
|---|---|---|
| `4.0pr` | `4.0p` | `4.0r` |
| `4.0fg` | `4.0f` | `4.0g` |
| `4.0ac` | `4.0a` | `4.0c` |
| `4.1pr` | `4.1p` | `4.1r` |
| `4.1fg` | `4.1f` | `4.1g` |
| `4.1ac` | `4.1a` | `4.1c` |

All six Series 4 runs completed 25 epochs and logged to the same W&B project. The twelve model names identify the final and validation-selected model from each run.

## Labels

Training records use physical values:

- Steering: logical target from 0 to 180 degrees;
- Throttle: absolute physical PWM fraction from 0.0 to 1.0.

Runtime reference throttle is different. The car does not physically move below roughly 55%, so policy maps a useful reference range onto the physical range. Historical photo labels stay absolute so data collection remains honest and reversible.

Series 3 requires both a steering and throttle field in each accepted label, even when a run trains with `--throttle-loss-weight 0.0`.

## Split Integrity

Consecutive driving frames are near-duplicates. Randomly distributing individual images would leak almost the same scene into both training and validation.

The trainer sorts images by path and groups them into 100-frame windows. Each window, including the final partial window when present, goes to training or validation, with approximately 10% reserved for validation by default. This keeps most neighboring frames together, although one capture run can still contribute different windows to both sets.

## Sampling and Augmentation

The v3.4 and Series 4 runs used class-weighted focal loss, deterministic left and right balance flipping, lighting and color augmentation, and synthetic diagonal shadow bands.

More augmentation is not automatically better. v3.3/v3.3b increased shadow-hardening pressure but performed worse on the physical car. v3.4 shows why augmentation changes must still be tested on ordinary turns.

The 81,237-image dataset used for the current Series 3 and Series 4 runs contains real field images only. These runs did not use CARLA images or source weighting. Their samplers selected 50,000 examples per epoch without steering-bucket reweighting.

## Series 3 Hybrid Loss

For v3.1 and later, the 19-value output is decoded into:

- A nine-way steering class;
- An offset within the selected class;
- Optional throttle.

Training combines focal-weighted classification loss, Smooth L1 loss for the true class's local offset, and optional Smooth L1 throttle loss. Current steering-focused runs set throttle loss to zero because 95.51% of the 81,237 throttle labels are full throttle. That distribution cannot teach useful variable-speed control.

## Typical Steering-Focused Command

From `code/ai_models_datasets/series_3_and_4/`:

```bash
python3 series_3_sidewalkpilot_trainer.py \
  --roots sidewalkpilot_dataset \
  --model-version 3.0 \
  --epochs 35 \
  --flip-aug-probability 0.5 \
  --throttle-loss-weight 0.0 \
  --keep-pth
```

This is a documented training pattern, not a claim that every Series 3 release used identical flags. Reproducing a release requires its W&B configuration, dataset version, and exact model file.

The trainer uses AdamW. Important defaults include batch size 256, learning rate `3e-4`, weight decay `3e-4`, 320x180 input, 50,000 sampler draws per epoch, 10% validation, and ONNX opset 17.

## Checkpoints and Export

Training produces two paired models:

- Regular: final epoch;
- Paired suffix (`b`, or Series 4 `r/g/c`): the validation-selected model from that run.

Both are exported to ONNX. PTH files are removed unless `--keep-pth` is specified. Recent runtime telemetry measured approximately 30 inference results per second on the Jetson Orin Nano, near the 30 FPS camera target; the exact rate depends on the selected model, software build, and power mode. The active field runtime does not require TensorRT or quantization.

## Evaluation and Promotion

The evaluator at `code/test_files/models/evaluate_sidewalkpilot_models.py` produces the cross-checkpoint report. Current ranking considers:

- Balanced nine-class accuracy;
- Turn exact and turn within one class;
- Straight exact accuracy;
- Mean and median absolute error;
- Signed error and confusion patterns.

Field promotion then checks the model on ordinary left and right turns and the failure condition it was designed to improve. See [Model Iteration Method](../../engineering-process/iteration-records/model-iteration-method.md) and [Series 3 Results](../model-zoo/series-3.md).
