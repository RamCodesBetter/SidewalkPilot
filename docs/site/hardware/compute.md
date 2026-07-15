# Compute

SidewalkPilot splits work across three computers.

| Board | Current responsibility | Link |
|---|---|---|
| Raspberry Pi 5 | Camera capture, Xbox input, sensors, final safety arbitration, motors, steering, logs, and dashboard sender | Hardware buses, USB, Ethernet |
| Jetson Orin Nano (Jon) | Series 3/4 ONNX inference through ONNX Runtime, normally with CUDA | Direct Ethernet at `10.42.0.2:8770` |
| Raspberry Pi Zero 2 W | Receives telemetry and renders the 64x32 HUB75 dashboard | USB Ethernet at `192.168.10.2:8765` |

## Why It Is Split

The Pi already owns the Camera Module 3 Wide and the complete actuator/sensor integration. Jon adds GPU inference without moving final control authority away from the Pi. The Zero isolates panel rendering from the control loop.

Series 1/2 can run locally on the Pi. Series 3/4 use Jon because they have larger `320x180` networks and the project has selected the Jetson GPU path for them. Inference rate is runtime telemetry, not a fixed claim; report it with the model, provider, software build, and power mode used for the measurement.

The Zero does not issue actuator commands. Losing the display removes observability but does not transfer control authority.
