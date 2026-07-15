# Quantization-Aware Training

Quantization-aware training (QAT) simulates reduced-precision arithmetic during training so a model can adapt to quantization error.

## SidewalkPilot Status

QAT is not implemented in the current Series 3 or Series 4 trainers. No QAT checkpoint, TensorRT INT8 engine, offline comparison, or field result is claimed.

QAT would only be justified after a reproducible post-training quantization experiment showed a useful performance gain and an unacceptable accuracy loss. It is therefore a possible follow-up, not part of the current pipeline.

## Evidence Required Before Adoption

1. A fixed FP32 ONNX baseline.
2. A documented calibrated INT8 baseline on Jon.
3. An identical held-out evaluation for FP32, PTQ, and QAT.
4. Latency, memory, and power measurements.
5. Field retests for turns and harsh shadows.

Without those comparisons, describing QAT as an improvement would be speculative.
