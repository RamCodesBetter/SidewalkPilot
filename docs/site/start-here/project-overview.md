# Project Overview

SidewalkPilot is a full-stack autonomy project built around a Yahboom Ackermann 520M RC chassis. It combines a learned camera-steering model, deterministic safety controls, GPS route logic, physical motor and servo control, data collection, offline evaluation, and a separate telemetry display.

The project is deliberately split into three computers so each has a clear responsibility.

| Manager | Hardware | Responsibility |
|---|---|---|
| Major System Manager | Raspberry Pi 5 | Controller input, camera, LiDAR, GPS, motor PWM, steering servo, logs, safety arbitration |
| AI Model Manager | NVIDIA Jetson Orin Nano | Receives the newest camera frame, runs ONNX inference, returns a steering result |
| Display System Manager | Raspberry Pi Zero 2 W | Receives USB-network telemetry and renders the Waveshare 64x32 HUB75 dashboard |

The Raspberry Pi remains authoritative. The Jetson proposes steering; it does not directly operate the servo. The Zero 2 W observes the system; it does not control motion.

## Runtime Architecture

The control path is:

```text
Xbox controller ----------------------------+
Pi Camera -> Raspberry Pi -> Jetson model --+--> arbitration -> servo and motors
LiDAR --------------------------------------+         |
GPS and hall sensor ------------------------+         +--> logs and photos
                                                      +--> Zero 2 W dashboard
```

Manual input is sampled in the Raspberry Pi loop. Camera transmission and Jetson inference run in a background worker so an offline Jetson cannot freeze steering. LiDAR has its own reader and decision path. Dashboard transmission is also asynchronous.

See [Runtime Loop](../runtime-code/runtime-loop.md) and [Data Flow](../autonomy-stack/architecture/data-flow.md) for exact timing and ownership.

## Learned Steering

The model family has evolved in three stages:

- **Series 1:** a compact 200x66 camera model established that image-to-steering learning could control the car.
- **Series 2:** retained direct steering regression while refining the data and testing HSV/CLAHE preprocessing for difficult lighting.
- **Series 3:** moved to 320x180 input and a larger network. v3.0 used separate steering and throttle outputs; v3.1 and later use a 19-value hybrid output containing nine steering-class logits, nine class-local regression offsets, and one throttle value.

The current physical-car selection is **v3.4**, not the checkpoint with the lowest raw mean error. The project uses balanced steering metrics and field behavior because a dataset dominated by straight frames can reward a model that avoids turning.

Read [Series 3 Model Zoo](../ai-and-models/model-zoo/series-3.md) and the [Model Claim](../portfolio-evidence/claims-and-proof/model-claim.md).

## Safety Architecture

LiDAR is intentionally a longitudinal safety layer. It watches one center corridor and can:

- leave throttle unchanged when clear;
- progressively reduce reference throttle from 100% to 60%;
- hold the 60% reference command near an obstacle;
- command a hard brake inside the emergency boundary.

It cannot choose left or right steering. Earlier lane-based swerve logic was removed because LiDAR obstacle points do not identify the sidewalk boundary; a swerve away from an obstacle could send the car into grass, a curb, or another hazard.

The AEB control can be disabled for controlled testing, and that setting gates intervention in both manual and autonomous modes. Sensor freshness must still be monitored because an enabled indicator alone does not prove valid LiDAR data.

## Data And Training

Driving sessions save camera images with absolute physical steering and throttle labels. Training uses time-grouped splits so adjacent video-like frames do not leak between training and validation. Series 3 applies lighting, color, flip, and synthetic-shadow augmentation, then evaluates exact steering classes, adjacent classes, error magnitude, and signed bias.

The current Series 3 comparison uses **81,237 real labeled images**. Models and dataset repositories are published on [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat), while training runs are recorded through [Weights & Biases](https://wandb.ai/Sidewalk-Pilot/SidewalkPilot/table?nw=nwusersidewalkpilot).

## Physical Hardware

Major hardware includes:

- Raspberry Pi Camera Module 3 Wide;
- Youyeetoo FHL-LD19 360-degree LiDAR through a CP2102 USB adapter;
- BN880 GPS and HMC5883L compass;
- PCA9685 steering-servo driver;
- Yahboom AT8236 motor controller;
- hall-effect wheel-speed sensor;
- Xbox Wireless Controller;
- Waveshare 64x32 RGB LED matrix;
- separate compute, motor, and display power systems with conversion and protection hardware.

The detailed component map is in [System At A Glance](system-at-a-glance.md).

## Repository Map

| Path | Purpose |
|---|---|
| `code/controller/current/` | Production Raspberry Pi, Jetson, and Zero 2 W runtime |
| `code/controller/current/rc_car_app/` | Runtime modules for config, hardware, LiDAR, navigation, telemetry, and vision |
| `code/ai_models_datasets/` | Series-specific trainers, metadata, and local datasets |
| `code/ai_models/` | Deployable PTH and ONNX model artifacts |
| `code/test_files/` | Hardware, sensor, steering, network, and model bench tools |
| `docs/site/` | This MkDocs knowledge base |
| `docs/steering_model_report.pdf` | Generated cross-model evaluation report |
| `trossachs_navigation_app/` | Companion navigation application |

## What Is Demonstrated And What Is Not

Demonstrated: physical camera steering, supervised autonomous field runs, manual takeover, model switching, camera and label collection, Jetson inference, LiDAR slowdown/braking logic, GPS/navigation software, and a live external dashboard.

Not demonstrated as a general claim: unattended operation, unrestricted sidewalks, reliable pedestrian negotiation, public-road legality, operation in all weather or lighting, or safety certification.

Continue with the [Build Timeline](build-timeline.md) for how these pieces developed.
