# SidewalkPilot

SidewalkPilot is a solo-built autonomous RC-car research platform that uses a camera model to steer along sidewalks while a separate LiDAR layer can slow or stop the vehicle. The project began in early April 2025 after a smaller Raspberry Pi Pico project. It grew from a drivable RC chassis into a complete hardware, data, model, deployment, and safety system.

It is a real, working vehicle rather than a simulation-only demonstration. The Jetson Orin
Nano is the AI brain for every live-selectable steering-model family: Series 1/2 run through
PyTorch CUDA and Series 3/4 run through ONNX Runtime CUDA. It turns camera frames into
steering predictions. The Raspberry Pi 5 is the hardware and safety
controller, and the Zero 2 W drives a live 64x32 dashboard. Without a fresh Jetson Orin Nano result,
current autonomy stops rather than driving on a stale prediction. An Xbox controller remains
the manual takeover and shutdown interface.

> SidewalkPilot is a supervised research and learning project. It is not presented as certified or approved for unattended or public-road operation, and it is not a finished autonomous vehicle.

## Current Result

The field-selected steering model is **SidewalkPilot v3.4**. In the July 13, 2026 comparison, it completed every shadow case presented during the run and handled the normal left and right turns included in that test. This mattered because sharp tree shadows had repeatedly caused earlier models to follow the shadow edge instead of the sidewalk.

The result is supported by two different kinds of evidence:

- [Offline model evaluation](model-evaluation/offline-evaluation/overview.md) compares all 52 Series 1-4 checkpoints on the same frozen 6,952-frame challenge set from the 81,237-image Series 3/4 dataset.
- [Field evaluation](model-evaluation/field-evaluation/overview.md) records the qualitative v3.3 through v3.4b comparison and its evidence limits.

Offline scores did not choose the winner by themselves. v3.4b had a slightly lower mean absolute error, but v3.4 had stronger balanced turn behavior and won on the physical car.

## What the Car Does

1. The Raspberry Pi Camera Module 3 Wide captures a forward sidewalk view.
2. The Raspberry Pi 5 submits the newest frame to a background Jetson Orin Nano client so connection and inference waits do not run in the controller loop.
3. The Jetson Orin Nano runs the selected model on its GPU and returns a steering prediction.
4. The Raspberry Pi 5 applies steering, throttle policy, manual takeover, and LiDAR emergency braking.
5. The Zero 2 W displays steering, model, navigation, camera, temperature, and LiDAR telemetry over a dedicated USB network.
6. During operator-enabled collection runs, camera frames and logical steering/absolute throttle labels are saved for the next training iteration.

Read [Project Overview](start-here/project-overview.md) for the full component map or [Data Flow](autonomy-stack/architecture/data-flow.md) for the runtime path.

## The Engineering Journey

SidewalkPilot progressed through four model families, multiple sensor transports, steering calibration experiments, dashboard-link failures, and repeated field-to-dataset cycles. Series 4 now compares causal steering history and future-target supervision without replacing the field-selected v3.4 baseline. Important lessons include:

- A low average steering error can hide a model that predicts straight too often.
- An offline-promising model or augmentation change can still regress on the physical car.
- A safety feature should not steer around an obstacle when it cannot see the sidewalk boundary.
- Network and sensor work must remain outside the manual-control loop.
- Hardware field testing remains the final promotion gate, even after a model wins offline.

The full sequence is in the [Build Timeline](start-here/build-timeline.md) and [Model Iteration Method](engineering-process/iteration-records/model-iteration-method.md).

## Reader Paths

- **Media and public readers:** [5-Minute Technical Tour](portfolio-evidence/reader-paths/5-minute-technical-tour.md), then [Build Timeline](start-here/build-timeline.md).
- **Technical reviewers:** [5-Minute Technical Tour](portfolio-evidence/reader-paths/5-minute-technical-tour.md), then [Evidence Map](portfolio-evidence/reader-paths/evidence-map.md).
- **Builders:** [Project Overview](start-here/project-overview.md), [Runtime Loop](runtime-code/runtime-loop.md), and [Computer Operations](operations/nvidia-pc.md).
- **Safety reviewers:** [Safety Overview](safety-case/safety-overview.md), [LiDAR AEB](autonomy-stack/lidar-safety/aeb.md), and [Research Scope and Limits](safety-and-ethics/research-scope.md).

## Public Project Links

- [GitHub](https://github.com/RamCodesBetter/SidewalkPilot)
- [Hugging Face models and datasets](https://huggingface.co/ram-shreyas-naik-sabavat)
- [YouTube](https://www.youtube.com/@SidewalkPilot)
- [Project status](start-here/current-status.md)
