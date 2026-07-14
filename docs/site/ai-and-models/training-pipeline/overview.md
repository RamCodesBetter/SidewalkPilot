# Training Pipeline Overview

SidewalkPilot training begins with a supervised field drive and ends only after an exported ONNX model passes offline and physical-car review.

## Pipeline

```text
manual/supervised drive
  -> JPEG frames + absolute steering/throttle labels
  -> integrity and class-balance audit
  -> time-window train/validation split
  -> weighted sampling + image augmentation
  -> CUDA training on RTX 6000 Ada
  -> final and best-validation checkpoints
  -> ONNX export
  -> compatible-dataset evaluation and PDF report
  -> Jetson deployment
  -> supervised field comparison
```

## Series-Specific Trainers

| Family | Trainer | Input | Output contract |
|---|---|---|---|
| Series 1/2 | `code/ai_models_datasets/series_1_and_2/sidewalkpilot_trainer.py` | 200x66 | Direct steering/control regression |
| Series 3 | `code/ai_models_datasets/series_3/sidewalkpilot_trainer.py` | 320x180 | v3.0 two outputs; v3.1+ 19-value hybrid head |

Series 1/2 models are evaluated on their compatible Series 1/2 data. They cannot consume the Series 3 19-value contract. Series 3 models are evaluated on the current 81,237-image Series 3 corpus.

## Labels

Training records use physical values:

- steering: absolute servo convention from 0 to 180 degrees;
- throttle: absolute 0-to-100 capture convention, converted to 0-to-1 by the trainer.

Runtime reference throttle is different. The car does not physically move below roughly 55%, so policy maps a useful reference range onto the physical range. Historical photo labels stay absolute so data collection remains honest and reversible.

Series 3 requires both a steering and throttle field in each accepted label, even when a run trains with `--throttle-loss-weight 0.0`.

## Split Integrity

Consecutive driving frames are near-duplicates. Randomly distributing individual images would leak almost the same scene into both training and validation.

The Series 3 trainer instead assigns time windows to training or validation, reserving approximately 10% by default. This preserves the temporal order and makes the validation stretch meaningfully different from the images used to update weights.

## Sampling And Augmentation

The trainer can apply:

- steering-bucket weighted sampling;
- focal/class weighting for the hybrid classes;
- horizontal flip augmentation or deterministic balance flipping;
- brightness, HSV, and CLAHE variants;
- synthetic diagonal shadow bands;
- CARLA-domain randomization for samples explicitly tagged as CARLA;
- separate real, CARLA, and correction sample weights.

More augmentation is not automatically better. v3.3/v3.3b increased shadow-hardening pressure but regressed on the physical car. v3.4 is evidence that augmentation must preserve the features needed for ordinary turns.

## Series 3 Hybrid Loss

For v3.1 and later, the 19-value output is decoded into:

- a nine-way steering class;
- an offset within the selected class;
- optional throttle.

Training combines focal classification loss, class-local offset loss, steering-magnitude weighting, and optional Smooth L1 throttle loss. The current steering-focused runs use throttle weight zero because the collected throttle distribution does not support a useful learned-throttle claim.

## Typical Steering-Focused Command

From `code/ai_models_datasets/series_3/`:

```bash
python3 sidewalkpilot_trainer.py \
  --roots sidewalkpilot_dataset \
  --model-version 3.0 \
  --epochs 35 \
  --flip-aug-probability 0.5 \
  --throttle-loss-weight 0.0 \
  --keep-pth
```

This is a documented training pattern, not a claim that every Series 3 release used identical flags. A release is exactly reproducible only when its W&B configuration, dataset snapshot, and artifact hash are preserved together.

Important defaults in the current trainer include batch size 256, learning rate `3e-4`, weight decay `3e-4`, 320x180 input, 50,000 weighted samples per epoch, 10% validation, and ONNX opset 17.

## Checkpoints And Export

Training produces two paired artifacts:

- regular: final epoch;
- `b`: best validation checkpoint.

Both are exported to ONNX. PTH files are removed unless `--keep-pth` is specified. TensorRT build flags remain available, but current Jetson throughput is sufficient to run the ONNX models directly; quantization is not required for the present operating target.

## Evaluation And Promotion

The evaluator at `code/test_files/evaluate_sidewalkpilot_models.py` produces the cross-model report. Current ranking considers:

- balanced nine-class accuracy;
- turn exact and turn within one class;
- straight exact accuracy;
- mean and median absolute error;
- signed error and confusion patterns.

Field promotion then checks the model on ordinary left/right turns and the failure condition it was designed to improve. See [Model Iteration Method](../../engineering-process/iteration-records/model-iteration-method.md) and [Series 3 Results](../model-zoo/series-3.md).
