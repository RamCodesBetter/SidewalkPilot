# SidewalkPilot

SidewalkPilot is a solo-built autonomous RC-car research platform that uses a camera model to steer along sidewalks while a separate LiDAR layer can slow or stop the vehicle. The project began in early April 2025 after a smaller Raspberry Pi Pico project. It grew from a drivable RC chassis into a complete hardware, data, model, deployment, and safety system.

It is a real, working vehicle rather than a simulation-only demonstration. A Raspberry Pi 5 operates the hardware and safety loop, an NVIDIA Jetson Orin Nano runs neural-network inference, and a Raspberry Pi Zero 2 W drives a live 64x32 dashboard. An Xbox controller remains the manual takeover and shutdown interface.

> SidewalkPilot is a supervised research and learning project. It is not presented as certified or approved for unattended or public-road operation, and it is not a finished autonomous vehicle.

## Current Result

The field-selected steering model is **SidewalkPilot v3.4**. In the July 13, 2026 comparison, it completed every shadow case presented during the run and handled the normal left and right turns included in that test. This mattered because sharp tree shadows had repeatedly caused earlier models to follow the shadow edge instead of the sidewalk.

The result is supported by two different kinds of evidence:

- [Offline model evaluation](model-evaluation/offline-evaluation/overview.md) compares all 46 Series 1-4 checkpoints on the same frozen 6,952-frame challenge set from the 81,237-image Series 3/4 dataset.
- [Field evaluation](portfolio-evidence/claims-and-proof/model-claim.md) records the qualitative v3.3 through v3.4b comparison and its evidence limits.

Offline scores did not choose the winner by themselves. v3.4b had a slightly lower mean absolute error, but v3.4 had stronger balanced turn behavior and won on the physical car.

## What the Car Does

1. The Pi Camera captures a forward sidewalk view.
2. The Raspberry Pi 5 submits the newest frame to a background Jetson client so connection and inference waits do not run in the controller loop.
3. The Jetson runs the selected ONNX model and returns a steering prediction.
4. The Raspberry Pi applies steering, throttle policy, manual takeover, and LiDAR emergency braking.
5. The Zero 2 W displays steering, model, navigation, camera, temperature, and LiDAR telemetry over a dedicated USB network.
6. Camera frames and absolute steering/throttle labels are saved for the next training iteration.

Read [System at a Glance](start-here/system-at-a-glance.md) for the full component map or [Data Flow](autonomy-stack/architecture/data-flow.md) for the runtime path.

## The Engineering Journey

SidewalkPilot progressed through four model families, multiple sensor transports, steering calibration experiments, dashboard-link failures, and repeated field-to-dataset cycles. Series 4 now compares causal steering history and future-target supervision without replacing the field-selected v3.4 baseline. Important lessons include:

- A low average steering error can hide a model that predicts straight too often.
- An offline-promising model or augmentation change can still regress on the physical car.
- A safety feature should not steer around an obstacle when it cannot see the sidewalk boundary.
- Network and sensor work must remain outside the manual-control loop.
- Hardware field testing remains the final promotion gate, even after a model wins offline.

The full sequence is in the [Build Timeline](start-here/build-timeline.md) and [Model Iteration Method](engineering-process/iteration-records/model-iteration-method.md).

## Reader Paths

- **Media and public readers:** [30 Second Overview](portfolio-evidence/reader-paths/30-second-overview.md), then [Build Timeline](start-here/build-timeline.md).
- **Technical reviewers:** [5 Minute Technical Tour](portfolio-evidence/reader-paths/5-minute-technical-tour.md), then [Evidence Map](portfolio-evidence/reader-paths/evidence-map.md).
- **Builders:** [Project Overview](start-here/project-overview.md), [Runtime Loop](runtime-code/runtime-loop.md), and [Zero 2 W Dashboard](operations/zero-2w-dashboard.md).
- **Safety reviewers:** [Safety Overview](safety-case/safety-overview.md), [LiDAR AEB](autonomy-stack/lidar-safety/aeb.md), and [Project Limits](safety-and-ethics/limits.md).

## Public Project Links

- [GitHub](https://github.com/RamCodesBetter/SidewalkPilot)
- [Hugging Face models and datasets](https://huggingface.co/ram-shreyas-naik-sabavat)
- [YouTube](https://www.youtube.com/@SidewalkPilot)
- [Weights & Biases](https://wandb.ai/Sidewalk-Pilot/SidewalkPilot/table?nw=nwusersidewalkpilot)
- [Project status](start-here/current-status.md)
