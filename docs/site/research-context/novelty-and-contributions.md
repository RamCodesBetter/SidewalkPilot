# Project Contributions and Scope

This page separates project-specific work from established machine-learning and robotics
patterns. It does not claim that a familiar technique becomes a new invention because it
was implemented on SidewalkPilot.

## Related Work

The direct historical reference is NVIDIA's 2016 *End to End Learning for Self-Driving Cars*, which trains a convolutional network from road images paired with human steering commands. SidewalkPilot adopts that supervised camera-to-steering framing but does not reproduce the paper's vehicle, routes, dataset, compute, or validation protocol. Its results are therefore not compared numerically with PilotNet.

- [Bojarski et al., NVIDIA paper](https://images.nvidia.com/content/tegra/automotive/images/2016/solutions/pdf/end-to-end-dl-using-px.pdf)
- [arXiv record](https://arxiv.org/abs/1604.07316)

Commercial sidewalk robots provide problem-setting context, not a benchmark. This repository does not contain controlled sensor, cost, speed, or safety comparisons against commercial platforms and makes no claim of matching them.

## 1. Failure-Driven Sidewalk Dataset and Test Loop

**Status: implemented, with bounded field evidence.** The project collects its own
camera/control data, identifies failure conditions, adds targeted examples, retrains, and
returns to the car for comparison. The July 13 test recorded v3.4 as the best of the four
Series 3 candidates tested in normal turns and the shadow cases presented that day.

This is a project contribution because the dataset, hardware integration, failure clips,
and iteration record were produced for this car. It is not evidence that v3.4 is universally
shadow-robust; the route identifier, quantitative takeover count, and repeated-trial record
for that comparison were not preserved.

## 2. Hybrid Steering Head Applied to Sidewalk Driving

**Status: implemented in v3.1 through v3.4b.** `SidewalkPilotV3` predicts nine steering-class
logits, nine local offsets, and throttle. Combining a discrete choice with a continuous
offset is an established modeling pattern. The project-specific design choice is applying
that pattern to a steering dataset where straight-heavy labels can hide weak turn recall.

The architecture is therefore described as an application and engineering experiment, not
as a new class-plus-offset algorithm.

## 3. Series 4 Temporal Experiments

**Status: v4.0 field-tested; v4.1 evaluated offline.** Series 4 compares causal history,
future supervision, and combined past/current/future targets while keeping the image
backbone and 18-value steering head comparable. Future targets are training supervision,
not unavailable future inputs at deployment.

The v4.0 comparison demonstrated why closed-loop testing matters: PC/PCF ranked strongly
offline but echoed earlier predictions on the car. Image-only v4.0f was viable and mixed
against v3.4. The six v4.1 models test corrections to that failure and remain pending live
integration and field testing.

## 4. Integrated Jetson Orin Nano, Raspberry Pi 5, Sensors, and Dashboard

**Status: implemented engineering.** The Jetson Orin Nano runs every steering-model family on its GPU: Series 1/2 through PyTorch CUDA and Series 3/4 through ONNX Runtime CUDA. The Raspberry Pi 5 owns controller input, sensors, steering and motor output, logging, and dashboard telemetry. The Zero 2 W renders the USB-linked dashboard. Splitting hardware I/O from heavier
inference is an established systems pattern; the contribution is the working integration
and debugging record on this vehicle.

## 5. Evaluation Beyond MAE

**Status: implemented evaluation practice.** The report reads MAE alongside Bal9, turn
exact, turn +/-1, straight exact, signed error, and confusion matrices. Macro recall and
class-aware evaluation are standard methods. Their value here is practical: they expose
straight collapse that one aggregate error number can conceal.

## Evidence Standard

- **Implemented** means the code, model, or other stated evidence exists.
- **Offline result** means it was measured on the stated frozen evaluation set.
- **Field observation** means it occurred in a bounded physical test.
- **Planned** means it is not complete and is not presented as a result.

## Related Pages

- [Turn vs Shadow Tradeoff](../engineering-process/iteration-records/turn-vs-shadow-tradeoff.md)
- [Offline and Field Comparison](../model-evaluation/comparisons/offline-vs-field.md)
