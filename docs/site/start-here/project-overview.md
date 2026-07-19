# Project Overview

SidewalkPilot is a full-stack autonomy project built around a Yahboom Ackermann 520M RC chassis. It combines a learned camera-steering model, deterministic safety controls, GPS route logic, physical motor and servo control, data collection, offline evaluation, and a separate telemetry display.

The project is deliberately split into three computers so each has a clear responsibility.

| Manager | Hardware | Responsibility |
|---|---|---|
| AI Model Manager | Jetson Orin Nano | Receives the newest camera frame, runs ONNX inference, returns a steering result |
| Major System Manager | Raspberry Pi 5 | Controller input, camera, LiDAR, GPS, motor PWM, steering servo, logs, safety arbitration |
| Display System Manager | Zero 2 W | Receives USB-network telemetry and renders the Waveshare 64x32 HUB75 dashboard |

The Raspberry Pi 5 remains authoritative. The Jetson Orin Nano proposes steering; it does not directly operate the servo. The Zero 2 W observes the system; it does not control motion.

## Runtime Architecture

The control path is:

```text
Xbox controller ----------------------------+
Raspberry Pi Camera -> Raspberry Pi -> Jetson Orin Nano model --+--> arbitration -> servo and motors
LiDAR --------------------------------------+         |
GPS and hall sensor ------------------------+         +--> logs and photos
                                                      +--> Zero 2 W dashboard
```

Manual input is sampled in the Raspberry Pi 5 loop. Camera transmission and Jetson Orin Nano inference run in a background worker, so normal connection waits to an offline Jetson Orin Nano are not performed in the controller loop. LiDAR has its own reader and decision path. Dashboard transmission is also asynchronous. This reduces coupling but is not a formal worst-case latency guarantee.

See [Runtime Loop](../runtime-code/runtime-loop.md) and [Data Flow](../autonomy-stack/architecture/data-flow.md) for exact timing and ownership.

## Learned Steering

The model family has evolved in four stages:

- **Series 1:** a compact 200x66 camera model established that image-to-steering learning could control the car.
- **Series 2:** retained direct steering regression while refining the data and testing HSV/CLAHE preprocessing for difficult lighting.
- **Series 3:** moved to 320x180 input and a larger network. v3.0 used separate steering and throttle outputs; v3.1 and later use a 19-value hybrid output containing nine steering-class logits, nine class-local regression offsets, and one throttle value.
- **Series 4:** keeps the Series 3 visual backbone, removes throttle learning, and compares image-only future supervision against causal three-target steering history. Series 4.0 was field-tested; Series 4.1 retrains the same contracts to address the observed steering-history echo.

The current physical-car selection is **v3.4**, not the checkpoint with the lowest raw mean error. The project uses balanced steering metrics and field behavior because a dataset dominated by straight frames can reward a model that avoids turning.

Read the [Series 3 Model Zoo](../ai-and-models/model-zoo/series-3.md), [Series 4 Model Zoo](../ai-and-models/model-zoo/series-4.md), and the [Model Claim](../portfolio-evidence/claims-and-proof/model-claim.md).

## Safety Architecture

LiDAR is intentionally a longitudinal safety layer. It watches one center corridor and can:

- Leave throttle unchanged when clear.
- Progressively reduce reference throttle from 100% to 60%.
- Hold the 60% reference command near an obstacle.
- Command a hard brake inside the emergency boundary.

It cannot choose left or right steering. Earlier lane-based swerve logic was removed because LiDAR obstacle points do not identify the sidewalk boundary; a swerve away from an obstacle could send the car into grass, a curb, or another hazard.

The AEB toggle controls all LiDAR slowdown and braking. When AEB is off, LiDAR does not change the car's motion in manual or autonomous mode. Before a run, the operator must confirm that the LiDAR is connected and updating.

## Data and Training

Driving sessions save camera images with logical `0..180` steering labels and absolute physical throttle fractions. The trainer sorts the images by path and groups them into 100-frame windows. Each window goes entirely into training or validation, which keeps most neighboring frames together. One capture run can still appear in both sets. Series 3/4 apply lighting, color, flip, and synthetic-shadow augmentation, then evaluate exact steering classes, adjacent classes, error magnitude, and signed bias.

Series 3 and 4 use the same **81,237 real labeled images** and split procedure. The generated report adapts all four architecture families and scores all 52 checkpoints on a common 6,952-frame challenge subset. Model repositories through Series 4.0 and the datasets are published on [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat). Training runs are recorded in the project's configured experiment tracker.

## Physical Hardware

Major hardware includes:

- Raspberry Pi Camera Module 3 Wide.
- Youyeetoo FHL-LD19 360-degree LiDAR through a CP2102 USB adapter.
- BN880 GPS and HMC5883L compass.
- PCA9685 Servo Controller.
- Yahboom AT8236 motor controller.
- Hall-effect wheel-speed sensor.
- Xbox Wireless Controller.
- Waveshare 64x32 RGB LED matrix.
- Separate compute, motor, and display power systems with conversion and protection hardware.

The detailed component map is in [System at a Glance](system-at-a-glance.md).

## Repository Map

| Path | Purpose |
|---|---|
| `code/controller/current/` | Live Jetson Orin Nano, Raspberry Pi 5, and Zero 2 W runtime |
| `code/controller/current/rc_car_app/` | Runtime modules for config, hardware, LiDAR, navigation, telemetry, and vision |
| `code/ai_models_datasets/` | Series-specific trainers, metadata, and local datasets |
| `code/ai_models/` | Local/Hugging Face PTH and ONNX artifacts; binaries are ignored by Git |
| `code/test_files/` | Hardware, sensor, steering, network, and model bench tools |
| `docs/site/` | This MkDocs knowledge base |
| `docs/steering_model_report.pdf` | Generated cross-model evaluation report |

## What Is Demonstrated and What Is Not

### Demonstrated

- Camera-based steering on the physical car during supervised field runs.
- Manual takeover and shutdown through the Xbox controller.
- Model selection, camera capture, label collection, and Jetson Orin Nano inference.
- LiDAR slowdown and emergency braking in the center corridor.
- GPS route-planning software and a live external dashboard.

### Not Demonstrated

- Unattended operation.
- Reliable operation on every sidewalk or in every lighting and weather condition.
- Autonomous negotiation around pedestrians or through crosswalks.
- Public-road legality or safety certification.

Continue with the [Build Timeline](build-timeline.md) for how these pieces developed.
