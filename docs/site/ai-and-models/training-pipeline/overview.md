# Training Pipeline Overview

SidewalkPilot training begins with a supervised field drive and ends only after an exported ONNX model passes offline and physical-car review.

## Pipeline

```text
manual/supervised drive
  -> JPEG frames + absolute steering/throttle labels
  -> integrity and class-balance audit
  -> family-specific train/validation split
  -> weighted sampling + image augmentation
  -> CUDA training on RTX 6000 Ada
  -> final and best-validation checkpoints
  -> ONNX export
  -> common challenge-set evaluation and PDF report
  -> Jetson Orin Nano deployment
  -> supervised field comparison
```

## Series-Specific Trainers

| Family | Trainer | Input | Output contract |
|---|---|---|---|
| Series 1/2 | `code/ai_models_datasets/series_1_and_2/sidewalkpilot_trainer.py` | 200x66 | One direct steering-regression value |
| Series 3 | `code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py` | 320x180 | v3.0 two outputs; v3.1+ 19-value hybrid head |
| Series 4 PC | `code/ai_models_datasets/series_3_and_4/series_4_0pr_sidewalkpilot_trainer.py` | image + three previous targets | one 18-value current steering horizon |
| Series 4 CF | `code/ai_models_datasets/series_3_and_4/series_4_0fg_sidewalkpilot_trainer.py` | image | four 18-value current/future steering horizons |
| Series 4 PCF | `code/ai_models_datasets/series_3_and_4/series_4_0ac_sidewalkpilot_trainer.py` | image + three previous targets | four 18-value current/future steering horizons |

Each family still needs its own preprocessing and output decoder. The common evaluator provides those adapters and scores all 52 checkpoints on the same frozen 6,952-frame Series 3/4 challenge subset. Series 3 and experimental Series 4 train on the same 81,237-image dataset.

## Series 4 Temporal Comparison

Series 4 removes throttle learning and keeps the Series 3 visual backbone and nine steering bins. Every horizon is 18 values: nine class logits plus nine class-local offsets. Previous-target history is a causal runtime input for PC/PCF; future targets are training supervision for CF/PCF and are never runtime inputs.

The model names form three final/best pairs:

| W&B run | Final epoch | Best validation |
|---|---|---|
| `4.0pr` | `4.0p` | `4.0r` |
| `4.0fg` | `4.0f` | `4.0g` |
| `4.0ac` | `4.0a` | `4.0c` |

All three completed 25 epochs and logged into the same W&B project as v3.4. This creates three comparable runs, while the six model names identify the final and best artifact from each run.

## Labels

Training records use physical values:

- Steering: absolute servo convention from 0 to 180 degrees;
- Throttle: absolute physical PWM fraction from 0.0 to 1.0.

Runtime reference throttle is different. The car does not physically move below roughly 55%, so policy maps a useful reference range onto the physical range. Historical photo labels stay absolute so data collection remains honest and reversible.

Series 3 requires both a steering and throttle field in each accepted label, even when a run trains with `--throttle-loss-weight 0.0`.

## Split Integrity

Consecutive driving frames are near-duplicates. Randomly distributing individual images would leak almost the same scene into both training and validation.

The Series 3/4 trainer instead assigns path-sorted 100-sample windows to training or validation, reserving approximately 10% by default. This reduces adjacent-frame leakage. It is not a run-group split and should not be described as complete isolation between capture runs.

## Sampling and Augmentation

The trainer can apply:

- Steering-bucket weighted sampling;
- Focal/class weighting for the hybrid classes;
- Horizontal flip augmentation or deterministic balance flipping;
- Brightness, HSV, and CLAHE variants;
- Synthetic diagonal shadow bands;
- CARLA-domain randomization for samples explicitly tagged as CARLA;
- Separate real, CARLA, and correction sample weights.

More augmentation is not automatically better. v3.3/v3.3b increased shadow-hardening pressure but regressed on the physical car. v3.4 is evidence that augmentation must preserve the features needed for ordinary turns.

## Series 3 Hybrid Loss

For v3.1 and later, the 19-value output is decoded into:

- A nine-way steering class;
- An offset within the selected class;
- Optional throttle.

Training combines focal-weighted classification loss, Smooth L1 loss for the true class's local offset, and optional Smooth L1 throttle loss. Bucket/source weighting happens in the sampler rather than through an active steering-magnitude loss multiplier. The current steering-focused runs use throttle weight zero because the collected throttle distribution does not support a useful learned-throttle claim.

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

This is a documented training pattern, not a claim that every Series 3 release used identical flags. A release is exactly reproducible only when its W&B configuration, dataset snapshot, and artifact hash are preserved together.

Important defaults in the current trainer include batch size 256, learning rate `3e-4`, weight decay `3e-4`, 320x180 input, 50,000 weighted samples per epoch, 10% validation, and ONNX opset 17.

## Checkpoints and Export

Training produces two paired artifacts:

- Regular: final epoch;
- `b`: best validation checkpoint.

Both are exported to ONNX. PTH files are removed unless `--keep-pth` is specified. TensorRT build flags remain available, but current Jetson Orin Nano throughput is sufficient to run the ONNX models directly; quantization is not required for the present operating target.

## Evaluation and Promotion

The evaluator at `code/test_files/models/evaluate_sidewalkpilot_models.py` produces the cross-model report. Current ranking considers:

- Balanced nine-class accuracy;
- Turn exact and turn within one class;
- Straight exact accuracy;
- Mean and median absolute error;
- Signed error and confusion patterns.

Field promotion then checks the model on ordinary left/right turns and the failure condition it was designed to improve. See [Model Iteration Method](../../engineering-process/iteration-records/model-iteration-method.md) and [Series 3 Results](../model-zoo/series-3.md).
