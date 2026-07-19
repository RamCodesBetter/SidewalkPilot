# Training Scripts

Series 3 and Series 4 share the `code/ai_models_datasets/series_3_and_4/` dataset workspace but use one Series 3 trainer and six Series 4 wrappers.

| Family | Trainer | Output pair |
|---|---|---|
| Series 3 | `series_3_sidewalkpilot_trainer.py` | requested version + `b` best checkpoint |
| Series 4.0 PC | `series_4_0pr_sidewalkpilot_trainer.py` | `4.0p` + `4.0r` |
| Series 4.0 CF | `series_4_0fg_sidewalkpilot_trainer.py` | `4.0f` + `4.0g` |
| Series 4.0 PCF | `series_4_0ac_sidewalkpilot_trainer.py` | `4.0a` + `4.0c` |
| Series 4.1 PC | `series_4_1pr_sidewalkpilot_trainer.py` | `4.1p` + `4.1r` |
| Series 4.1 CF | `series_4_1fg_sidewalkpilot_trainer.py` | `4.1f` + `4.1g` |
| Series 4.1 PCF | `series_4_1ac_sidewalkpilot_trainer.py` | `4.1a` + `4.1c` |

## Shared Training Behavior

- Input images are `320x180` BGR tensors normalized to `[-1,1]`.
- The current dataset contains 81,237 labeled real driving frames.
- Training uses a time-aware split, augmentation, AdamW, gradient clipping, and per-epoch validation. Series 3 uses bucket-weighted sampling; the recorded Series 4 runs set steering-balance power to zero and move class pressure into the loss.
- The July 2026 Series 4.0 and Series 4.1 experiments used 25 epochs for each PC, CF, and PCF run.
- Both final and best checkpoints are exported to ONNX.
- Weights & Biases receives step and epoch telemetry for comparing all six Series 4 runs.

The Series 3 defaults include batch size 256, 50,000 weighted samples per epoch, seed 42, 10% validation, and ONNX opset 17. Record the actual command for every model rather than assuming defaults were unchanged.

## Current Deployment Boundary

Training runs on the NVIDIA workstation. ONNX inference runs on Jetson Orin Nano. The checked-in Series 3 trainer retains optional `trtexec` flags, but no current deployment or performance claim depends on TensorRT.

## Evidence

- The seven trainer entrypoints above;
- `code/test_files/models/test_series_4_common.py` for Series 4 data/contract checks;
- `code/test_files/models/evaluate_sidewalkpilot_models.py` for the shared report; and
- The named Weights & Biases runs and ONNX models.
