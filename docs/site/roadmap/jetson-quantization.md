# Jetson Orin Nano Quantization

Quantization is an optional future experiment, not part of the current vehicle deployment. The live Jetson Orin Nano path runs FP32 ONNX models through ONNX Runtime with CUDA.

## Current Status

- Series 3 and Series 4 trainers export FP32 ONNX artifacts.
- Jetson Orin Nano currently uses `CUDAExecutionProvider`, with CPU as a compatibility fallback.
- No FP16 or INT8 engine has been accepted through offline evaluation and a field retest.
- The former calibrated TensorRT builder described by older notes is not in the current repository.
- The Series 3 trainer still has an optional `--build-tensorrt` wrapper around `trtexec`, but that flag is not the live deployment recipe and does not supply a calibration dataset by itself.

## Required Experiment

If ONNX Runtime later becomes a measured bottleneck, test precision in this order:

1. Record the FP32 ONNX baseline on Jetson Orin Nano: model, provider, latency distribution, memory, power mode, and offline metrics.
2. Build an FP16 TensorRT engine on the target Jetson Orin Nano.
3. Re-run the same evaluator and a controlled field test.
4. Consider calibrated INT8 only if FP16 is still insufficient.

TensorRT engines are tied to the target GPU and software stack. Record the JetPack, CUDA, TensorRT, ONNX, and model revisions for every experiment.

## Acceptance Rule

Do not promote a lower-precision artifact from throughput alone. It must preserve the metrics used for model selection, especially Bal9, turn exact recall, turn +/-1 recall, straight recall, and steering error, and then pass a real-car retest.

## Related Pages

- [Deployment Overview](../ai-and-models/deployment/overview.md)
- [TensorRT](../ai-and-models/deployment/tensorrt.md)
- [INT8 PTQ](../ai-and-models/deployment/int8-ptq.md)
