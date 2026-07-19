# 5 Minute Technical Tour

This path gives a technical or media reviewer enough context to describe SidewalkPilot accurately without reading the whole repository.

## 1. One Vehicle, Three Computers

The Jetson Orin Nano runs the neural network over private Ethernet. The Raspberry Pi 5 owns controller input, sensors, safety decisions, steering hardware, motors, and logging. The Zero 2 W renders the external dashboard over a dedicated USB network.

This is a responsibility split, not three boards doing the same job. The display has no motion-command path. Jetson Orin Nano connection and inference work use a background latest-frame worker, so the controller loop does not intentionally wait for each request; this is not a worst-case real-time guarantee.

Read: [System at a Glance](../../start-here/system-at-a-glance.md) and [Jetson Orin Nano Inference Link](../../autonomy-stack/camera-steering/jetson-inference-link.md).

## 2. The Model Journey

Series 1 proved that a compact CNN could map a 200x66 camera frame to steering. Series 2 refined the data and tested fixed CLAHE lighting preprocessing. Series 3 moved to 320x180 on Jetson Orin Nano and, from v3.1, used nine steering classes plus continuous offsets. v3.4 became the field winner after handling the tested harsh shadows that earlier models followed as fake sidewalk edges.

Series 4 changes the temporal contract while keeping the same 81,237-image dataset and visual backbone. PC uses the previous three target commands; CF learns current plus three future targets from the image; PCF combines both. The v4.0 PC/PCF models led offline but echoed previous predictions on the car. Image-only v4.0f was viable and complementary with v3.4, but did not replace it. Six v4.1 correction models are now trained and evaluated offline; live integration and physical testing remain.

Read: [Model Zoo](../../ai-and-models/model-zoo/overview.md) and [Series 4 Temporal Experiments](../../ai-and-models/architecture/series-4-plan.md).

## 3. The Data and Evaluation Loop

Manual drives save camera frames with logical `0..180` steering labels and absolute physical throttle fractions. The Series 3/4 split assigns path-sorted 100-sample windows to one side of the split, which reduces adjacent-frame leakage. It is not a capture-run-group split and does not prove complete route isolation. A common evaluator now runs all 52 checkpoints on the same 6,952-frame challenge subset.

Bal9 averages exact recall across nine steering classes with equal class weight. It prevents 4,741 straight frames from hiding failures in rare turns. MAE remains useful, but it is secondary to class balance, turns, signed bias, and field behavior.

Read: [Bal9](../../model-evaluation/offline-evaluation/bal9.md), [Offline Evaluation](../../model-evaluation/offline-evaluation/overview.md), and [Model Iteration Method](../../engineering-process/iteration-records/model-iteration-method.md).

## 4. Safety Is Separate from Steering

The learned model controls autonomous steering. LiDAR does not choose a left/right path. It watches one center corridor and can reduce throttle or hard-brake. Earlier LiDAR swerve logic was removed because obstacle points cannot prove that adjacent ground is safe sidewalk rather than grass, curb, or another hazard.

Read: [LiDAR Overview](../../autonomy-stack/lidar-safety/overview.md) and [Why LiDAR Does Not Steer](../../autonomy-stack/lidar-safety/override-steering.md).

## 5. A Failure That Changed the Architecture

Manual steering once ran smoothly for several seconds, paused, then resumed. `jstest` showed instant controller input, so Bluetooth was not the root cause. The application was blocking on network and recurring system work. Jetson Orin Nano I/O moved to a latest-frame worker; file scans and temperature subprocesses left the control path. The physical car was then retested with Jetson Orin Nano powered off and the delay disappeared.

This is representative of the project: measure the boundary, identify the actual bottleneck, change ownership, and verify on hardware.

## 6. Current Evidence and Limits

- v3.4 has a bounded qualitative field result.
- v4.0 has training, ONNX, CUDA runtime, common offline evidence, and a bounded field result; v4.1 has no field result yet.
- LiDAR center-braking has automated tests; the latest policy still needs a preserved physical test record.
- No claim is made for public-road, unattended, or unrestricted pedestrian operation.

Verify: [Evidence Map](evidence-map.md), [GitHub](https://github.com/RamCodesBetter/SidewalkPilot), and [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat).
