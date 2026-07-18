# System Diagrams

This page is the top-level block diagram of SidewalkPilot: the three-device compute split, the sensors and actuators wired to each device, and the links that carry data between them. It is the anchor exhibit that every other diagram on this branch drills into.

## What the diagram shows

SidewalkPilot runs across three boards, each doing the job it is best at:

- **Jetson Orin Nano at `10.42.0.2:8770` — the AI brain.** Runs selected Series 3/4 FP32 ONNX models at 320x180 through ONNX Runtime CUDA. The Raspberry Pi 5 sends a camera frame and model selection; the Jetson Orin Nano returns decoded steering plus model/runtime telemetry. Current v3.4 and Series 4 autonomy require a fresh result from this path. Series 1/2 models (`SteeringAutonomyV2`, ~0.67M parameters, 200x66 input) can still load directly on the Raspberry Pi 5 inside `vision.py`.
- **Raspberry Pi 5 (`raspberrypi5`) — the hardware and safety controller.** Owns all real-time I/O. It reads the Xbox controller over pygame, captures frames from the Raspberry Pi Camera Module 3 Wide through Picamera2, reads the LiDAR, GPS, and hall sensor over serial/GPIO, drives the steering servo through the PCA9685 Servo Controller, drives the JGB37-520 DC motors (12 V, 550 RPM) through the AT8236 Motor Controller, writes CSV logs, and sends dashboard telemetry. The main loop lives in `code/controller/current/rc_car_app/runtime.py` and ticks at up to 60 Hz (`clock.tick(60)`).
- **Zero 2 W (`zero2w`) - the dashboard.** Receives telemetry over USB Ethernet and renders it on one HUB75 LED panel. Rendering code is `z2w_dashboard.py`.

## Links between devices

- **Raspberry Pi 5 <-> Jetson Orin Nano:** direct Ethernet request/response for the selected model. The exact returned contract depends on the model family; the Raspberry Pi 5 receives decoded steering and telemetry.
- **Raspberry Pi 5 <-> Zero 2 W:** USB Ethernet gadget. Raspberry Pi 5 is `192.168.10.1`, Zero 2 W is `192.168.10.2`, dashboard telemetry is UDP to `192.168.10.2:8765` at a `0.1 s` send interval (`HUB75_DASHBOARD_SEND_INTERVAL_SEC`). This is USB-only by decision; there is no Wi-Fi fallback. When the controller quits it tells the Zero 2 W to shut down (linked shutdown, `HUB75_DASHBOARD_IDLE_EXIT_SEC = 2.0`).
- **Telemetry out:** training runs report to Weights & Biases; every controller launch writes a local CSV; InfluxDB logging is optional and activates only when the Raspberry Pi 5 has a valid `~/.influxdb.json` configuration.

## Why this split

The Jetson Orin Nano supplies the GPU inference that makes the current Series 3/4 self-driving
path practical near the camera rate. The Raspberry Pi Camera Module 3 Wide remains connected
to the Raspberry Pi 5 because the current 81,237-image dataset was captured through that
camera path. Final actuator and AEB decisions remain on the Raspberry Pi 5.

## What this exhibit documents

The checked-in separation of responsibilities: AI and current autonomous steering inference
on the Jetson Orin Nano, hardware and safety control on the Raspberry Pi 5, and observability
on the Zero 2 W. It does not establish hard-real-time timing or fault tolerance for every link.

## System Architecture

[![SidewalkPilot system architecture showing the Jetson Orin Nano AI Model Manager, Raspberry Pi 5 hardware and safety controller, Zero 2 W display controller, sensors, controllers, actuators, and logs](../../assets/diagrams/system-architecture.svg)](../../assets/diagrams/system-architecture.svg)

*Compute, I/O, and device-link architecture. Open the [full-size SVG](../../assets/diagrams/system-architecture.svg) or the [editable draw.io source](../../assets/diagrams/system-architecture.drawio).*

Source anchors: `code/controller/current/rc_car_app/runtime.py`, `config.py`, `vision.py`, `jetson_inference_server.py`, `hub75_dashboard.py`, and `z2w_dashboard.py`.

## Runtime and Control Flow

[![SidewalkPilot runtime and control flow showing latest sensor values, Jetson Orin Nano inference, Raspberry Pi 5 arbitration, separate steering and motor paths, and telemetry](../../assets/diagrams/runtime-control.svg)](../../assets/diagrams/runtime-control.svg)

*Runtime command and safety flow. Open the [full-size SVG](../../assets/diagrams/runtime-control.svg) or the [editable draw.io source](../../assets/diagrams/runtime-control.drawio).*

Manual input cancels autonomy when processed. A fresh model proposal is required for autonomous steering. Enabled/fresh LiDAR can reduce forward throttle or request emergency braking, but it does not steer.

## Training and Evaluation Flow

[![SidewalkPilot training and evaluation flow showing datasets, model-family trainers, RTX 6000 Ada training, model artifacts, offline evaluation, and supervised field testing](../../assets/diagrams/training-evaluation.svg)](../../assets/diagrams/training-evaluation.svg)

*Training, export, and model-selection flow. Open the [full-size SVG](../../assets/diagrams/training-evaluation.svg) or the [editable draw.io source](../../assets/diagrams/training-evaluation.drawio).*

## Navigation Flow

[![SidewalkPilot navigation and crosswalk handoff flow showing the offline graph, GPS localization, A-star route, automatic sidewalk segments, and manual crossing segments](../../assets/diagrams/navigation-flow.svg)](../../assets/diagrams/navigation-flow.svg)

*Navigation and crosswalk handoff flow. Open the [full-size SVG](../../assets/diagrams/navigation-flow.svg) or the [editable draw.io source](../../assets/diagrams/navigation-flow.drawio).*

## Related pages

- [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md)
- [Reports and PDF](../../publishing/reports.md)
- [Evidence Tables](../tables/model-metrics-table.md)
