# Model Export

Series 3 and Series 4 trainers export both final and best-validation checkpoints to ONNX automatically. The live Jetson Orin Nano runtime consumes those FP32 ONNX files directly.

## Export Rules

- Plain Series 3 versions are final-epoch checkpoints; the `b` versions are best-validation checkpoints.
- Series 4 names encode architecture and checkpoint role: `p/f/a` are final, while `r/g/c` are their best-validation partners.
- Use `--keep-pth` only when a PyTorch checkpoint is needed for analysis, resuming, or another training experiment. Otherwise, successful ONNX export removes the corresponding `.pth`.
- Keep model names on the `SidewalkPilot-v<version>.onnx` convention.

## Validation Before Deployment

1. Check the ONNX graph loads.
2. Run a smoke inference with the model's real input contract.
3. Run the shared evaluator and preserve its JSON/PDF output.
4. Add the version to `STEERING_MODEL_VERSIONS` if it is not already registered.
5. Copy the ONNX artifact to Jetson Orin Nano's `code/ai_models/` directory.
6. Restart the Jetson Orin Nano service and Raspberry Pi 5 controller.
7. Confirm the startup log reports the intended version and a GPU provider.
8. Conduct a controlled field test before changing the live default or publishing a field verdict.

## Series 4 Contract Check

Series 4 PC and PCF models require a three-value steering-target history. The Jetson Orin Nano runtime owns that history and resets it on model load/switch, reconnect, and manual/status-only periods. CF models use only the image. All three families return multiple horizon predictions where applicable; live control decodes horizon zero.

TensorRT, FP16, and INT8 are optional future experiments. They are not required by this deployment runbook.
