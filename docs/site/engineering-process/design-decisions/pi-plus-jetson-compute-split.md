# Jetson Orin Nano + Raspberry Pi 5 Compute Split

This page records the decision to use the **Jetson Orin Nano as the AI brain** and the
**Raspberry Pi 5 as the hardware and safety controller**, instead of forcing both jobs onto
one computer.

## How it works

- The **Jetson Orin Nano** runs the current Series 3/4 steering neural network through ONNX
  Runtime/CUDA and returns decoded steering plus runtime telemetry over private Ethernet at
  `10.42.0.2:8770`.
- The **Raspberry Pi 5** captures the camera frame and owns joystick input, LiDAR, GPS, hall
  sensing, PCA9685 steering, motor PWM, safety arbitration, logging, and the dashboard link.
- The Raspberry Pi 5 accepts only a fresh result for the selected model, combines it with
  LiDAR and operator safety rules, and then writes the physical outputs.

## Why this choice

- **Current autonomy needs the Jetson Orin Nano GPU.** The larger 320x180 Series 3/4 networks
  ran much more slowly on the Raspberry Pi 5 CPU. The Jetson Orin Nano GPU runs the selected
  model near the camera rate in the current deployment, making it the practical AI brain for
  v3.4 and Series 4.
- **Keep hardware and safety deterministic.** The Raspberry Pi 5 retains GPIO, sensors,
  motors, steering, LiDAR, GPS, logging, and final safety arbitration. A missing Jetson Orin Nano result
  therefore stops current autonomy instead of blocking manual control or writing hardware
  from the network process.
- **Reuse the established physical platform.** The Raspberry Pi 5 was already the working,
  fully wired camera and I/O base. Adding the Jetson Orin Nano preserved that integration while adding
  the GPU performance needed by the newer models.
- **Camera lock-in.** The camera (Raspberry Pi Camera Module 3 Wide) is not compatible with
  the Jetson Orin Nano, and the entire 81,237-image Series 3/4 dataset was captured with it. No good
  alternative wide camera existed (the options were narrow or ultra-wide, wrong quality), so
  moving to a Jetson Orin Nano-only rig would have invalidated the dataset. The Raspberry Pi 5 stays as the camera
  host.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Jetson Orin Nano only | one board; GPU sits with compute | Requires replacing the established Raspberry Pi 5 camera/GPIO/sensor integration and moving hardware I/O and safety control |
| Raspberry Pi 5 only | established GPIO/sensor integration; simple | Series 3/4 inference is too slow on its CPU for the selected live deployment |
| **Jetson Orin Nano + Raspberry Pi 5 (chosen)** | Jetson Orin Nano provides the AI performance; Raspberry Pi 5 keeps the wide camera, I/O, and safety control | two boards to manage + a network hop for inference |

## Capture and inference path

- The Raspberry Pi 5 captures the frame through **Picamera2** in OpenCV BGR
  (`_PiCameraCapture`, `code/controller/current/rc_car_app/vision.py`) and the background
  client sends its newest JPEG request to **Jetson Orin Nano at `10.42.0.2:8770`**. The
  Jetson Orin Nano performs model-specific resize/normalization, runs ONNX inference, decodes the
  output, and returns steering plus telemetry. The Raspberry Pi 5 then applies safety and
  writes the Servo Controller and Motor Controller.
- **Speed motivation:** Series 1/2 (`SteeringAutonomyV2`, ~0.67M parameters, 200x66)
  can run locally on the Raspberry Pi 5. Series 3/4 use substantially larger ~5.5M-parameter
  networks at 320x180. The dedicated Jetson Orin Nano path leaves the Raspberry Pi 5 CPU available for
  physical I/O while the GPU handles inference. Exact throughput should still be reported
  from runtime telemetry for the tested model, provider, software build, and power mode.
- **Failure behavior:** the model is one input to a safety-arbitrated loop, not
  the loop itself. LiDAR/AEB and manual override sit above it, and a stale or
  low-confidence model result triggers a safety stop rather than a blind command
  (see the LiDAR-priority decision).

## Related pages

- [Project Overview](../../start-here/project-overview.md)
- [Control Architecture and Runtime Data Flow](../../autonomy-stack/architecture/data-flow.md)
- [Compute Hardware](../../hardware/compute.md)
