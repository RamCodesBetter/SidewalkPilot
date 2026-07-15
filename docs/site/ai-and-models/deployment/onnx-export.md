# ONNX Export

ONNX is the portable artifact format used by Jetson Orin Nano. Export occurs after training from the matching PyTorch architecture and checkpoint.

## Current Signatures

| Model | Inputs | Output |
|---|---|---|
| v3.0 | `image` | `[batch,2]` |
| v3.1+ | `image` | `[batch,19]` |
| v4 PC | `image`, `target_history` | `[batch,1,18]` |
| v4 CF | `image` | `[batch,4,18]` |
| v4 PCF | `image`, `target_history` | `[batch,4,18]` |

The batch dimension is dynamic. Image shape remains `3x180x320`; history shape is `[batch,3]`.

## Export Checks

1. Load the exact checkpoint into the matching architecture.
2. Set evaluation mode.
3. Export with named inputs/outputs and dynamic batch axes.
4. Run ONNX checker/signature inspection.
5. Compare a PyTorch output with ONNX Runtime on the same sample.
6. Record artifact SHA-256.
7. Run the common evaluator before deployment.

The current live path consumes FP32 ONNX through ONNX Runtime/CUDA. TensorRT conversion is not part of the required current export flow.

See [Deployment Overview](overview.md) and [Jetson Orin Nano Runtime](jetson-runtime.md).
