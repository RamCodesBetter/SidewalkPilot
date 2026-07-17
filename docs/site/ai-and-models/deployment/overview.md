# Model Deployment Overview

The current heavy-model deployment path is:

```text
PyTorch training checkpoint
  -> FP32 ONNX export
  -> copy ONNX to Jetson Orin Nano
  -> ONNX Runtime with CUDA
  -> decoded steering returned to Raspberry Pi 5
```

The Raspberry Pi 5 remains responsible for the camera, actuator control, result freshness, manual override, and LiDAR safety. Jetson Orin Nano is an inference service only.

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

## Export and Verification

Each model must export with the input names and output shape shown above, load in ONNX Runtime, and produce finite steering on a representative frame before deployment. Artifact hashes and the exact model/version pairing should be recorded. A successful export does not prove that the Raspberry Pi 5 and Jetson Orin Nano are using the same preprocessing or decoder, so an end-to-end fresh-response test is still required.

## Precision Experiments

FP32 stores each parameter in four bytes. FP16 can approximately halve weight storage and may improve GPU throughput; INT8 maps floating values to integer codes using a scale and zero point:

```text
q = clamp(round(x / scale) + zero_point)
x_approx = scale * (q - zero_point)
```

Quantization can change a winning steering class near a boundary. Any FP16, INT8 PTQ, QAT, or TensorRT experiment therefore needs representative calibration data, artifact hashes, on-device latency/power measurements, common-set evaluation, and a supervised field comparison. File size alone is not approval.

See [Jetson Orin Nano Runtime](jetson-runtime.md) and [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md).
