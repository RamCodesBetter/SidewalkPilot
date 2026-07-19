# Model Deployment Overview

The current heavy-model deployment path is:

```text
PyTorch training checkpoint
  -> FP32 ONNX export
  -> copy ONNX to Jetson Orin Nano
  -> ONNX Runtime with CUDA
  -> decoded steering returned to Raspberry Pi 5
```

The Raspberry Pi 5 remains responsible for the camera, steering servo and motor control, result freshness, manual override, and LiDAR safety. The Jetson Orin Nano runs the steering models and returns their predictions.

## Model Contracts

| Family | ONNX input | ONNX output |
|---|---|---|
| Series 3 v3.0 | image | `[batch,2]` |
| Series 3 v3.1+ | image | `[batch,19]` |
| Series 4 PC | image + `target_history[batch,3]` | `[batch,1,18]` |
| Series 4 CF | image | `[batch,4,18]` |
| Series 4 PCF | image + `target_history[batch,3]` | `[batch,4,18]` |

The server inspects input names and output shapes rather than assigning a contract from the filename alone.

## GPU Selection

Series 1/2 run through PyTorch CUDA. Series 3/4 run through ONNX Runtime's CUDA provider. CPU execution remains available only for diagnosis; a field launch should confirm that the Jetson Orin Nano GPU path loaded.

## Export and Verification

Before field use, each model must load with the expected input names and output shape, return finite steering values, and pass a complete Raspberry Pi 5-to-Jetson Orin Nano response test. The deployed filename and version must match. The current field path uses FP32 models; TensorRT, FP16, and INT8 are not active.

See [Jetson Orin Nano Runtime](jetson-runtime.md) and [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md).
