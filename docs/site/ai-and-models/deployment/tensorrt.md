# TensorRT

TensorRT can compile an ONNX graph into a device-specific engine, fuse compatible operations, select kernels, and optionally use FP16 or INT8. It is an optimization option, not SidewalkPilot's current runtime.

## Current Project State

- Live Series 3/4 inference uses FP32 ONNX Runtime with CUDA on Jetson Orin Nano.
- No TensorRT engine is required to meet the current inference target.
- The older Python INT8 builder and TensorRT recipe are not present in the current repository tree.
- No current accuracy, latency, power, or field result is attributed to TensorRT.

## What a Future TensorRT Experiment Must Record

1. Exact ONNX artifact hash and model contract.
2. JetPack, CUDA, TensorRT, and hardware versions.
3. Engine precision and build command.
4. Calibration data identity for INT8.
5. ONNX Runtime versus TensorRT latency distributions, not only averages.
6. Bal9, turn, straight, MAE, median, and signed-error changes.
7. Physical field comparison before promotion.

Serialized engines should be built on the target Jetson Orin Nano because they depend on the hardware and software stack. This is background engineering guidance, not evidence that SidewalkPilot currently deploys one.

See [Deployment Overview](overview.md) and [INT8 PTQ](int8-ptq.md).
