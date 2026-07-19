# Jetson Orin Nano + Raspberry Pi 5 Compute Split

This page records the decision to run the controller on the **Raspberry Pi 5** *and* the
steering model on the **Jetson Orin Nano**, instead of using a single computer.

## How it works

- The **Raspberry Pi 5** owns all real-time I/O and control: joystick, camera capture, LiDAR, GPS,
  hall sensor, PCA9685 steering, motor PWM, safety arbitration, logging, and the dashboard
  link.
- The **Jetson Orin Nano** runs only the steering neural network (ONNX) and returns a steering angle
  + throttle over the network (Jetson Orin Nano at `10.42.0.2:8770`).
- The Raspberry Pi 5 fuses the Jetson Orin Nano's command with LiDAR safety and GPS navigation before moving
  any wheel.

## Why this choice

- **Raspberry Pi 5 owns real-time I/O.** The Raspberry Pi 5 already runs all GPIO, sensors, motors, steering,
  LiDAR, and GPS reliably; the Jetson Orin Nano isn't as clean for that hardware wiring.
- **Reuse the established platform.** The Raspberry Pi 5 was already the working, fully-wired base — faster
  and cheaper to add a Jetson Orin Nano than to re-wire the whole car onto the Jetson Orin Nano.
- **Jetson Orin Nano = GPU for the heavy model.** Series 3/4 ONNX inference uses the Jetson Orin Nano GPU through ONNX Runtime/CUDA, leaving the Raspberry Pi 5 focused on hardware control.
- **Camera lock-in.** The camera (Raspberry Pi Camera Module 3 Wide) is not compatible with
  the Jetson Orin Nano, and the entire 81,237-image Series 3/4 dataset was captured with it. No good
  alternative wide camera existed (the options were narrow or ultra-wide, wrong quality), so
  moving to a Jetson Orin Nano-only rig would have invalidated the dataset. The Raspberry Pi 5 stays as the camera
  host.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Jetson Orin Nano only | one board; GPU sits with compute | Requires replacing the established Raspberry Pi 5 camera/GPIO/sensor integration and moving final actuator authority |
| Raspberry Pi 5 only | established GPIO/sensor integration; simple | Does not provide the selected GPU inference path for Series 3/4 |
| **Jetson Orin Nano + Raspberry Pi 5 (chosen)** | Raspberry Pi 5 keeps current I/O + the wide camera; Jetson Orin Nano adds GPU for the heavy model | two boards to manage + a network hop for inference |

## Capture and inference path

- The Raspberry Pi 5 captures the frame via **Picamera2** in OpenCV BGR (`_PiCameraCapture`,
  `code/controller/current/rc_car_app/vision.py`), resizes/normalizes it, and
  sends it to **Jetson Orin Nano at `10.42.0.2:8770`**. Jetson Orin Nano runs `SidewalkPilotV3` (ONNX) and
  returns the 19-number hybrid vector, which the Raspberry Pi 5 decodes to a steering
  angle + throttle and then fuses with LiDAR safety and GPS navigation before
  writing to the servo/motors.
- **Speed motivation:** Series 1/2 (`SteeringAutonomyV2`, ~0.67M params, 200x66)
  ran locally on the Raspberry Pi 5. Series 3 (`SidewalkPilotV3`,
  ~5.53M params, 320x180) is ~8x the parameters at higher resolution and is far
  is substantially larger and uses the dedicated Jetson Orin Nano path, leaving the Raspberry Pi 5's CPU free for I/O. Exact throughput should be reported from the runtime telemetry for the tested model and software build rather than treated as a fixed architecture constant.
- **Failure behavior:** the model is one input to a safety-arbitrated loop, not
  the loop itself. LiDAR/AEB and manual override sit above it, and a stale or
  low-confidence model result triggers a safety stop rather than a blind command
  (see the LiDAR-priority decision).

## Related pages

- `start-here/system-at-a-glance.md`
- `autonomy-stack/architecture/layered-autonomy.md`
- `hardware/compute.md`
