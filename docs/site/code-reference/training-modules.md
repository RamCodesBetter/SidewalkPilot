# Training Modules

Training code is split between the early direct-regression family and the shared Series 3/4 dataset.

| Module | Role |
|---|---|
| `series_1_and_2/sidewalkpilot_trainer.py` | Trains the 672,877-parameter, 200x66 direct steering model |
| `series_3_and_4/series_3_sidewalkpilot_trainer.py` | Trains v3.0 regression and v3.1+ 19-value hybrid checkpoints; exports ONNX |
| `series_3_and_4/series_4_common.py` | Temporal-window construction, S4 architecture, loss, metrics, ONNX export, and shared run logic |
| `series_3_and_4/series_4_0pr_sidewalkpilot_trainer.py` | PC run: v4.0p final and v4.0r best-validation |
| `series_3_and_4/series_4_0fg_sidewalkpilot_trainer.py` | CF run: v4.0f final and v4.0g best-validation |
| `series_3_and_4/series_4_0ac_sidewalkpilot_trainer.py` | PCF run: v4.0a final and v4.0c best-validation |
| `series_3_and_4/wandb_logger.py` | W&B metric definitions and logging helper |
| `code/test_files/models/evaluate_sidewalkpilot_models.py` | Architecture-aware evaluator for all 46 checkpoints |
| `code/test_files/models/test_series_4_common.py` | Temporal-window and S4 contract regression tests |

## Contracts

| Family | Input | Output |
|---|---|---|
| Series 1/2 | 200x66 image | direct steering |
| Series 3 v3.0 | 320x180 image | steering/throttle regression |
| Series 3 v3.1+ | 320x180 image | 9 logits + 9 offsets + throttle |
| Series 4 PC | image + three previous targets | one 18-value steering horizon |
| Series 4 CF | image | four 18-value steering horizons |
| Series 4 PCF | image + three previous targets | four 18-value steering horizons |

All current S3/4 training uses the 81,237-image shared dataset. The trainer sorts paths, forms contiguous 100-sample windows, and assigns approximately every Nth window to validation. This reduces adjacent-frame leakage but is not a run-group split. S4 uses no learned throttle.

## Artifact Roles

Regular model names identify the final epoch. The paired alternate identifies the lowest selected validation checkpoint from the same run. For Series 4 those pairs are `p/r`, `f/g`, and `a/c`; an alternate is not automatically better in the field.

TensorRT/INT8 builder files described by older documentation are not present in the current tree. Current live inference uses FP32 ONNX Runtime with CUDA. Quantization remains an optional future optimization, not a completed deployment claim.

## Verification

```bash
python3 -m py_compile \
  code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py \
  code/ai_models_datasets/series_3_and_4/series_4_common.py \
  code/test_files/models/evaluate_sidewalkpilot_models.py
```

See [Training Pipeline](../ai-and-models/training-pipeline/overview.md) and [Series 4 Temporal Experiments](../ai-and-models/architecture/series-4-plan.md).
