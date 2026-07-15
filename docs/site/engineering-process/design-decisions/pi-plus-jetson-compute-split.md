# Pi 5 + Jetson Compute Split

This page records the decision to run the controller on the **Raspberry Pi 5** *and* the
steering model on the **Jetson Orin Nano ("Jon")**, instead of using a single computer.

## How it works

- The **Pi 5** owns all real-time I/O and control: joystick, camera capture, LiDAR, GPS,
  hall sensor, PCA9685 steering, motor PWM, safety arbitration, logging, and the dashboard
  link.
- The **Jetson** runs only the steering neural network (ONNX) and returns a steering angle
  + throttle over the network (Jon at `10.42.0.2:8770`).
- The Pi 5 fuses the Jetson's command with LiDAR safety and GPS navigation before moving
  any wheel.

## Why this choice

- **Pi owns real-time I/O.** The Pi 5 already runs all GPIO, sensors, motors, steering,
  LiDAR, and GPS reliably; the Jetson isn't as clean for that hardware wiring.
- **Reuse the established platform.** The Pi was already the working, fully-wired base — faster
  and cheaper to add a Jetson than to re-wire the whole car onto the Jetson.
- **Jetson = GPU for the heavy model.** Series 3/4 ONNX inference uses the Jetson GPU through ONNX Runtime/CUDA, leaving the Pi focused on hardware control.
- **Camera lock-in.** The camera (Raspberry Pi Camera Module 3 Wide) is not compatible with
  the Jetson Orin Nano, and the entire 81,237-image Series 3/4 dataset was captured with it. No good
  alternative wide camera existed (the options were narrow or ultra-wide, wrong quality), so
  moving to a Jetson-only rig would have invalidated the dataset. The Pi stays as the camera
  host.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Jetson only | one board; GPU sits with compute | Requires replacing the established Pi camera/GPIO/sensor integration and moving final actuator authority |
| Pi 5 only | established GPIO/sensor integration; simple | Does not provide the selected GPU inference path for Series 3/4 |
| **Pi 5 + Jetson (chosen)** | Pi keeps current I/O + the wide camera; Jetson adds GPU for the heavy model | two boards to manage + a network hop for inference |

## Capture and inference path

- The Pi captures the frame via **Picamera2** in OpenCV BGR (`_PiCameraCapture`,
  `code/controller/current/rc_car_app/vision.py`), resizes/normalizes it, and
  sends it to **Jon at `10.42.0.2:8770`**. Jon runs `SidewalkPilotV3` (ONNX) and
  returns the 19-number hybrid vector, which the Pi decodes to a steering
  angle + throttle and then fuses with LiDAR safety and GPS navigation before
  writing to the servo/motors.
- **Speed motivation:** Series 1/2 (`SteeringAutonomyV2`, ~0.67M params, 200x66)
  ran locally on the Pi. Series 3 (`SidewalkPilotV3`,
  ~5.53M params, 320x180) is ~8x the parameters at higher resolution and is far
  is substantially larger and uses the dedicated Jetson path, leaving the Pi's CPU free for I/O. Exact throughput should be reported from the runtime telemetry for the tested model and software build rather than treated as a fixed architecture constant.
- **Failure behavior:** the model is one input to a safety-arbitrated loop, not
  the loop itself. LiDAR/AEB and manual override sit above it, and a stale or
  low-confidence model result triggers a safety stop rather than a blind command
  (see the LiDAR-priority decision).

## Related pages

- `start-here/system-at-a-glance.md`
- `autonomy-stack/architecture/layered-autonomy.md`
- `hardware/compute.md`
