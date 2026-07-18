# Compute

SidewalkPilot splits work across three computers. The Jetson Orin Nano is the AI brain for
current Series 3/4 self-driving; the other computers connect that intelligence to the physical
car and its display.

| Board | Current responsibility | Link |
|---|---|---|
| Jetson Orin Nano | AI Model Manager: Series 3/4 ONNX inference through ONNX Runtime, normally with CUDA | Direct Ethernet at `10.42.0.2:8770` |
| Raspberry Pi 5 | Camera capture, Xbox input, sensors, final safety arbitration, motors, steering, logs, and dashboard sender | Hardware buses, USB, Ethernet |
| Zero 2 W | Receives telemetry and renders the 64x32 HUB75 dashboard | USB Ethernet at `192.168.10.2:8765` |

## Why It Is Split

The Jetson Orin Nano supplies the GPU performance that makes the current 320x180 Series 3/4
models practical at the selected live rate. If its result is missing, stale, or for the wrong
model, current autonomy requests a stop. The Raspberry Pi 5 keeps the established Camera
Module 3 Wide, steering/motor, sensor, and safety integration, while the Zero 2 W isolates panel
rendering from the control loop.

Series 1/2 can run locally on the Raspberry Pi 5. Series 3/4 use the Jetson Orin Nano because
their larger 320x180 networks ran much more slowly on the Raspberry Pi 5 CPU, while the
Jetson Orin Nano GPU can run the selected models near the camera rate in the current deployment.
Exact inference rate remains runtime telemetry and should be reported with the model,
provider, software build, and power mode used for the measurement.

The Zero 2 W does not command the steering servo or motors. Losing the display removes observability but does not transfer control authority.
