# Quantization Math

This page explains the math behind a possible future INT8 experiment. SidewalkPilot currently runs FP32 ONNX through ONNX Runtime/CUDA; the equations below are educational context, not a completed deployment claim.

## Affine Quantization

A floating-point value `x` is approximated by an integer `q` plus a scale and zero point:

```text
q = clamp(round(x / scale) + zero_point)
x_hat = scale * (q - zero_point)
```

The approximation error is `x - x_hat`. A smaller scale gives finer resolution but covers a smaller range; a larger scale covers outliers but coarsens ordinary values.

## Symmetric and Asymmetric Forms

- Symmetric quantization fixes `zero_point = 0` and is common for zero-centered weights.
- Asymmetric quantization allows a nonzero zero point and can use the integer range more efficiently for one-sided activations.
- Per-tensor quantization uses one scale for a tensor.
- Per-channel quantization can preserve small filters when different output channels have very different ranges.

## Worked Example

For a symmetric range `[-2,+2]` mapped to signed values `[-127,127]`:

```text
scale = 2 / 127 = 0.01575
x = 0.734
q = round(0.734 / 0.01575) = 47
x_hat = 47 * 0.01575 = 0.740
absolute error = 0.006
```

Small errors accumulate across layers and can change the winning steering class near a boundary. That is why file size or synthetic throughput alone cannot approve quantization for this project.

## Evidence Needed Before Use

- Representative calibration data;
- Exact FP32/INT8 artifact hashes;
- Latency distribution and power measurement on Jon;
- Full common-subset metric comparison;
- Field test against the FP32 baseline.

See [INT8 PTQ](../../ai-and-models/deployment/int8-ptq.md) and [Model Selection Rubric](../../model-evaluation/comparisons/model-selection-rubric.md).
