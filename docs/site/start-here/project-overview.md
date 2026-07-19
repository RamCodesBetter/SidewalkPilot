# Project Overview

SidewalkPilot is a full-stack autonomy project built around a Yahboom Ackermann 520M RC
chassis. Its Jetson Orin Nano AI brain runs the current camera-steering models, while separate
hardware, safety, navigation, data, evaluation, and telemetry systems turn those predictions
into a supervised physical-car experiment.

The project is deliberately split into three computers so each has a clear responsibility.

| Role | Device | Responsibility |
|---|---|---|
| AI Model Manager | Jetson Orin Nano | Receives the newest camera frame, runs Series 1/2 with PyTorch CUDA or Series 3/4 with ONNX Runtime CUDA, and returns a steering result |
| Hardware and Safety Controller | Raspberry Pi 5 | Controller input, camera, LiDAR, GPS, motor PWM, steering servo, logs, and safety arbitration |
| Display Controller | Zero 2 W | Receives USB-network telemetry and renders the Waveshare 64x32 HUB75 dashboard |

The Jetson Orin Nano is required for the current self-driving path. It runs all model families on
its GPU: Series 1/2 through PyTorch CUDA and Series 3/4 through ONNX Runtime CUDA. The Raspberry
Pi 5 rejects missing or stale results and remains the final hardware and safety controller; the
Zero 2 W observes the system and does not control motion.

## Runtime Architecture

The control path is:

```text
Xbox controller ----------------------------+
Raspberry Pi Camera Module 3 Wide -> Raspberry Pi 5 -> Jetson Orin Nano model --+--> arbitration -> servo and motors
LiDAR --------------------------------------+         |
GPS and Hall-effect wheel-speed sensor -----+         +--> logs and photos
                                                      +--> Zero 2 W dashboard
```

The Raspberry Pi 5 reads manual controls continuously. A separate worker sends camera frames to the Jetson Orin Nano, so a powered-off Jetson Orin Nano does not pause manual steering while the worker waits for a connection. LiDAR independently limits throttle or requests braking, and dashboard updates also run outside the controller loop. This design removed the pauses observed in one physical retest, but a formal worst-case latency has not been measured.

See [Runtime Loop](../runtime-code/runtime-loop.md) and [Data Flow](../autonomy-stack/architecture/data-flow.md) for implementation timing and ownership.

## Learned Steering

The model family has evolved in four stages:

- **Series 1:** a compact 200x66 camera model established that image-to-steering learning could control the car.
- **Series 2:** retained direct steering regression while refining the data and testing HSV/CLAHE preprocessing for difficult lighting.
- **Series 3:** moved to 320x180 input and a larger network. v3.0 used separate steering and throttle outputs; v3.1 and later use a 19-value hybrid output containing nine steering-class logits, nine class-local regression offsets, and one throttle value.
- **Series 4:** keeps the Series 3 visual backbone, removes throttle learning, and compares image-only future supervision against causal three-target steering history. Six v4.0 models are runtime-supported and field-tested; six corrected v4.1 models are trained and evaluated offline but not yet integrated.

The current physical-car selection is **v3.4**, not the checkpoint with the lowest raw mean error. The project uses balanced steering metrics and field behavior because a dataset dominated by straight frames can reward a model that avoids turning.

Read the [Series 3 Model Zoo](../ai-and-models/model-zoo/series-3.md), [Series 4 Model Zoo](../ai-and-models/model-zoo/series-4.md), and [Evidence Map](../portfolio-evidence/reader-paths/evidence-map.md).

## Safety Architecture

LiDAR is intentionally a longitudinal safety layer. It watches one center corridor and can:

- Leave throttle unchanged when clear.
- Progressively reduce reference throttle from 100% to 60%.
- Hold the 60% reference command near an obstacle.
- Command a hard brake inside the emergency boundary.

It cannot choose left or right steering because LiDAR obstacle points do not identify the sidewalk boundary; a distance return alone cannot establish that either side is safe sidewalk rather than grass, a curb, or another hazard.

The AEB toggle controls all LiDAR slowdown and braking. When AEB is off, LiDAR does not change the car's motion in manual or autonomous mode. Before a run, the operator must confirm that the LiDAR is connected and updating.

## Data and Training

Driving sessions save camera images with logical `0..180` steering labels and absolute physical throttle fractions. The trainer sorts the images by path and groups them into 100-frame windows. Each window goes entirely into training or validation, which keeps most neighboring frames together. One capture run can still appear in both sets. Series 3 and 4 training applies lighting, color, flip, and synthetic-shadow augmentation, then evaluates exact steering classes, adjacent classes, error magnitude, and signed bias.

Series 3 and 4 use the same **81,237 real labeled images** and split procedure. The generated report adapts all four architecture families and scores all 52 checkpoints on a common 6,952-frame challenge subset. Series 1-3 and Series 4.0 model repositories, plus the datasets, are published on [Hugging Face](https://huggingface.co/ram-shreyas-naik-sabavat). The v4.1 models remain local while integration and field testing are pending. Training runs are recorded in the project's configured experiment tracker.

## Physical Hardware

| Function | Hardware and connection | Current role |
|---|---|---|
| Forward vision | Raspberry Pi Camera Module 3 Wide through Picamera2 | Captures 1280x720 BGR frames before model-specific preprocessing |
| Obstacle distance | FHL-LD19 through a CP2102 UART-to-USB Adapter | Supplies center-corridor clearance for slowdown and emergency braking |
| Position | BN880 GPS through Raspberry Pi 5 UART | Supplies route and position updates |
| Compass heading | HMC5883L-compatible magnetometer through I2C | Bench-tested; not fused into the live navigation controller |
| Motion sensing | XIAO MG24 Sense through UART | Experimental yaw-control input |
| Wheel speed | Hall-effect wheel-speed sensor through Raspberry Pi 5 GPIO | Supplies pulse-based speed and distance |
| Steering | High-torque servo through the PCA9685 Servo Controller | Receives the final Raspberry Pi 5 steering command |
| Drive | Yahboom AT8236 Motor Controller and JGB37-520 DC motors (12 V, 550 RPM) | Receives final throttle, direction, and brake outputs and produces wheel thrust |
| Human control | Xbox Wireless Controller through Bluetooth | Manual driving, takeover, braking, and shutdown |
| Telemetry | Waveshare 64x32 HUB75 panel on the Zero 2 W | Displays state received over the dedicated USB network |

The car uses separate compute, motor, and display power systems with conversion and protection hardware. Component specifications, wiring, and calibration are documented under [Hardware](../hardware/build-overview.md).

## Control Priority

The system does not average competing commands. Shutdown and braking take priority over enabled LiDAR intervention, which takes priority over the selected manual or autonomous motion command. Dashboard updates and logging do not control motion. The complete ordering is documented in [Decision Priority](../autonomy-stack/architecture/decision-priority.md).

## Fast Health Check

On the Jetson Orin Nano, verify the inference service and GPU:

```bash
ss -ltnp | grep 8770
pgrep -af jetson_inference_server.py
nvidia-smi
```

On the Raspberry Pi 5, verify the controller service, recent log, and direct Jetson Orin Nano link:

```bash
sudo systemctl status sidewalkpilot-rpi-car.service -l --no-pager
journalctl -u sidewalkpilot-rpi-car.service -n 100 -l --no-pager
ping -c 3 10.42.0.2
```

On the Zero 2 W, verify the dashboard service:

```bash
sudo systemctl status sidewalkpilot-z2w-dashboard.service -l --no-pager
journalctl -u sidewalkpilot-z2w-dashboard.service -n 100 -l --no-pager
```

## Repository Map

| Path | Purpose |
|---|---|
| `code/controller/current/` | Live Jetson Orin Nano, Raspberry Pi 5, and Zero 2 W runtime |
| `code/controller/current/rc_car_app/` | Runtime modules for config, hardware, LiDAR, navigation, telemetry, and vision |
| `code/ai_models_datasets/` | Series-specific trainers, metadata, and local datasets |
| `code/ai_models/` | Local/Hugging Face PTH and ONNX models; binaries are ignored by Git |
| `code/test_files/` | Hardware, sensor, steering, network, and model bench tools |
| `docs/site/` | This MkDocs knowledge base |
| `docs/steering_model_report.pdf` | Generated cross-model evaluation report |

## What Is Demonstrated and What Is Not

### Demonstrated

- Camera-based steering on the physical car during supervised field runs.
- Manual takeover and shutdown through the Xbox controller.
- Model selection, camera capture, label collection, and Jetson Orin Nano inference.
- LiDAR center-corridor slowdown and emergency-braking logic in software and bench tests; a preserved physical stopping-distance result remains open.
- GPS route-planning software and a live external dashboard.

### Not Demonstrated

- Unattended operation.
- Reliable operation on every sidewalk or in every lighting and weather condition.
- Autonomous negotiation around pedestrians or through crosswalks.
- Public-road legality or safety certification.

Continue with the [Build Timeline](build-timeline.md) for how these pieces developed.
