# Training Scripts

Series 3 and Series 4 share the `code/ai_models_datasets/series_3_and_4/` dataset workspace but use four explicit trainers.

| Family | Trainer | Output pair |
|---|---|---|
| Series 3 | `series_3_sidewalkpilot_trainer.py` | requested version + `b` best checkpoint |
| Series 4 PC | `series_4_0pr_sidewalkpilot_trainer.py` | `4.0p` + `4.0r` |
| Series 4 CF | `series_4_0fg_sidewalkpilot_trainer.py` | `4.0f` + `4.0g` |
| Series 4 PCF | `series_4_0ac_sidewalkpilot_trainer.py` | `4.0a` + `4.0c` |

## Shared Training Behavior

- Input images are `320x180` BGR tensors normalized to `[-1,1]`.
- The current dataset contains 81,237 labeled real driving frames.
- Training uses a time-aware split, weighted sampling, augmentation, AdamW, gradient clipping, and per-epoch validation.
- The July 2026 Series 4 comparison used 25 epochs for each PC, CF, and PCF run.
- Both final and best checkpoints are exported to ONNX.
- Weights & Biases receives step and epoch telemetry for comparing the three runs.

The Series 3 defaults include batch size 256, 50,000 weighted samples per epoch, seed 42, 10% validation, and ONNX opset 17. Record the actual command for every model rather than assuming defaults were unchanged.

## Current Deployment Boundary

Training runs on the NVIDIA workstation. ONNX inference runs on Jon. The checked-in Series 3 trainer retains optional `trtexec` flags, but no current deployment or performance claim depends on TensorRT.

## Evidence

- The four trainers above;
- `code/test_files/models/test_series_4_common.py` for Series 4 data/contract checks;
- `code/test_files/models/evaluate_sidewalkpilot_models.py` for the shared report; and
- The named Weights & Biases runs and ONNX artifacts.
