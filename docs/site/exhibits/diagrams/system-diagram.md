# System Diagram

This page is the top-level block diagram of SidewalkPilot: the three-device compute split, the sensors and actuators wired to each device, and the links that carry data between them. It is the anchor exhibit that every other diagram on this branch drills into.

## What the diagram shows

SidewalkPilot runs across three boards, each doing the job it is best at:

- **Jetson Orin Nano at `10.42.0.2:8770` — the heavy model host.** Runs selected Series 3/4 FP32 ONNX models at 320x180 through ONNX Runtime CUDA. The Raspberry Pi 5 sends a camera frame and model selection; the Jetson Orin Nano returns decoded steering plus model/runtime telemetry. Series 1/2 models (`SteeringAutonomyV2`, ~0.67M parameters, 200x66 input) still load directly on the Raspberry Pi 5 inside `vision.py`.
- **Raspberry Pi 5 (`raspberrypi5`) — the controller.** Owns all real-time I/O. It reads the Xbox controller over pygame, captures frames from the Raspberry Pi Camera Module 3 Wide through Picamera2, reads the LiDAR, GPS, and hall sensor over serial/GPIO, drives the steering servo through a PCA9685, drives the two motors through the AT8236 H-bridge, writes CSV logs, and sends dashboard telemetry. The main loop lives in `code/controller/current/rc_car_app/runtime.py` and ticks at up to 60 Hz (`clock.tick(60)`).
- **Zero 2 W (`zero2w`) - the dashboard.** Receives telemetry over USB Ethernet and renders it on one HUB75 LED panel. Rendering code is `z2w_dashboard.py`.

## Links between devices

- **Raspberry Pi 5 <-> Jetson Orin Nano:** direct Ethernet request/response for the selected model. The exact returned contract depends on the model family; the Raspberry Pi 5 receives decoded steering and telemetry.
- **Raspberry Pi 5 <-> Zero 2 W:** USB Ethernet gadget. Raspberry Pi 5 is `192.168.10.1`, Zero 2 W is `192.168.10.2`, dashboard telemetry is UDP to `192.168.10.2:8765` at a `0.1 s` send interval (`HUB75_DASHBOARD_SEND_INTERVAL_SEC`). This is USB-only by decision; there is no Wi-Fi fallback. When the controller quits it tells the Zero 2 W to shut down (linked shutdown, `HUB75_DASHBOARD_IDLE_EXIT_SEC = 2.0`).
- **Telemetry out:** training runs report to Weights & Biases; every controller launch writes a local CSV; InfluxDB logging is optional and activates only when the Raspberry Pi 5 has a valid `~/.influxdb.json` configuration.

## Why this split

The Raspberry Pi Camera Module 3 Wide is connected to the Raspberry Pi 5, and the current 81,237-image Series 3/4 dataset was captured through the Raspberry Pi 5 camera path. Jetson Orin Nano supplies GPU inference without taking actuator authority. Final actuator and AEB decisions remain on the Raspberry Pi 5.

## What this exhibit documents

The checked-in separation of responsibilities: controller and actuator ownership on the Raspberry Pi 5, GPU inference on Jetson Orin Nano, and observability on the Zero 2 W. It does not establish hard-real-time timing or fault tolerance for every link.

## System block view

```text
Camera + controller + LiDAR + GPS + IMU + hall sensor
                         |
                         v
                  Raspberry Pi 5
               /         |          \
      private Ethernet   I/O     USB Ethernet
             /            |             \
            v             v              v
    Jetson Orin Nano   motors/servo   Zero 2 W -> HUB75
       FP32 ONNX       final control     dashboard
```

Source anchors: `code/controller/current/rc_car_app/runtime.py`, `config.py`, `vision.py`, `jetson_inference_server.py`, `hub75_dashboard.py`, and `z2w_dashboard.py`.

## Related pages

- `portfolio-evidence/reader-paths/evidence-map.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
