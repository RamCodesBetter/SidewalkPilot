# Model Deployment Overview

The current heavy-model deployment path is:

```text
PyTorch training checkpoint
  -> FP32 ONNX export
  -> copy ONNX to Jetson Orin Nano
  -> ONNX Runtime with CUDA
  -> decoded steering returned to Raspberry Pi 5
```

The Raspberry Pi 5 remains responsible for the camera, steering/motor control, result freshness, manual override, and LiDAR safety. Jetson Orin Nano is the AI Model Manager and inference computer.

## Artifact Contracts

| Family | ONNX input | ONNX output |
|---|---|---|
| Series 3 v3.0 | image | `[batch,2]` |
| Series 3 v3.1+ | image | `[batch,19]` |
| Series 4 PC | image + `target_history[batch,3]` | `[batch,1,18]` |
| Series 4 CF | image | `[batch,4,18]` |
| Series 4 PCF | image + `target_history[batch,3]` | `[batch,4,18]` |

The server inspects input names and output shapes rather than assigning a contract from the filename alone.

## Provider Selection

CUDA is preferred when ONNX Runtime reports `CUDAExecutionProvider`; CPU remains a fallback for compatibility/testing. A partially installed TensorRT provider is not registered ahead of CUDA because provider initialization failure can cause an accidental CPU retry.

## TensorRT Status

TensorRT, FP16, and INT8 remain valid future optimization topics, but they are not the current live path. The old checked-in TensorRT builder described by earlier docs is no longer in the repository. No current field claim depends on a TensorRT engine or quantized model.

See [ONNX Export](onnx-export.md), [Jetson Orin Nano Runtime](jetson-runtime.md), and [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md).
