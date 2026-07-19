# Project Contributions and Scope

This page separates project-specific work from established machine-learning and robotics
patterns. It does not claim that a familiar technique becomes a new invention because it
was implemented on SidewalkPilot.

## 1. Failure-driven sidewalk dataset and test loop

**Status: implemented, with bounded field evidence.** The project collects its own
camera/control data, identifies failure conditions, adds targeted examples, retrains, and
returns to the car for comparison. The July 13 test recorded v3.4 as the best of the four
Series 3 candidates tested in normal turns and the shadow cases presented that day.

This is a project contribution because the dataset, hardware integration, failure clips,
and iteration record were produced for this car. It is not evidence that v3.4 is universally
shadow-robust; the route identifier, quantitative takeover count, and repeated-trial record
for that comparison were not preserved.

## 2. Hybrid steering head applied to sidewalk driving

**Status: implemented in v3.1 through v3.4b.** `SidewalkPilotV3` predicts nine steering-class
logits, nine local offsets, and throttle. Combining a discrete choice with a continuous
offset is an established modeling pattern. The project-specific design choice is applying
that pattern to a steering dataset where straight-heavy labels can hide weak turn recall.

The architecture is therefore described as an application and engineering experiment, not
as a new class-plus-offset algorithm.

## 3. Series 4 temporal experiments

**Status: v4.0 field-tested; v4.1 evaluated offline.** Series 4 compares causal history,
future supervision, and combined past/current/future targets while keeping the image
backbone and 18-value steering head comparable. Future targets are training supervision,
not unavailable future inputs at deployment.

The v4.0 comparison demonstrated why closed-loop testing matters: PC/PCF ranked strongly
offline but echoed earlier predictions on the car. Image-only v4.0f was viable and mixed
against v3.4. The six v4.1 models test corrections to that failure and remain pending live
integration and field testing.

## 4. Integrated Jetson Orin Nano, Raspberry Pi 5, sensors, and dashboard

**Status: implemented engineering.** The Raspberry Pi 5 owns controller input, sensors, steering/motor output,
logging, and dashboard telemetry. Jetson Orin Nano performs Series 3/4 ONNX inference over direct
Ethernet. The Zero 2 W renders the USB-linked dashboard. Splitting real-time I/O from heavier
inference is an established systems pattern; the contribution is the working integration
and debugging record on this vehicle.

## 5. Evaluation beyond MAE

**Status: implemented evaluation practice.** The report reads MAE alongside Bal9, turn
exact, turn +/-1, straight exact, signed error, and confusion matrices. Macro recall and
class-aware evaluation are standard methods. Their value here is practical: they expose
straight collapse that one aggregate error number can conceal.

## Evidence standard

- **Implemented** means the code or artifact exists.
- **Offline result** means it was measured on the stated frozen evaluation set.
- **Field observation** means it occurred in a bounded physical test.
- **Planned** means it is not complete and is not presented as a result.

## Related pages

- `research-context/related-work.md`
- `engineering-process/iteration-records/turn-vs-shadow-tradeoff.md`
- `model-evaluation/comparisons/mae-vs-turn-capability.md`
