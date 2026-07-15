# Build Flags

This page documents the self-driving build flags at the top of `code/controller/current/rc_car_app/config.py`. These are the boolean and numeric switches that decide which subsystems the runtime brings up and how the autonomy stack behaves, without needing code changes elsewhere.

## How it works

The flags are read at import time and consumed by `hardware.py` (which peripherals to initialize), `vision.py` (camera path), and `runtime.py` (autonomy tuning). The core enable flags:

| Flag | Value | Effect |
|---|---|---|
| `ENABLE_HALL_SENSOR` | `True` | Bring up the GPIO 24 hall sensor for speed/odometry |
| `ENABLE_WEBCAM_VISION` | `True` | Enable the camera-to-steering vision path |
| `USE_PI_CAMERA` | `True` | Use the Raspberry Pi Camera Module (via Picamera2) rather than a USB webcam |
| `PI_CAMERA_NUM` | `0` | Which Raspberry Pi 5 camera to open |
| `PI_CAMERA_ROTATE_180` | `True` | Rotate the frame 180 deg (camera is mounted inverted) |

A second block contains current and legacy autonomy constants. Presence in `config.py` does
not mean every value still controls motion:

| Flag | Value | Runtime status |
|---|---|---|
| `MAX_TARGET_HEADING_DEG` | `60.0` | Active display/control-state heading clamp derived from steering |
| `LOW_CAMERA_CONFIDENCE` | `0.25` | Active gate, although accepted fresh ONNX results currently report confidence `1.0`; it mainly catches unavailable/stale results |
| `LIDAR_CORRIDOR_HALF_WIDTH_M` | `0.762` | Active half-width of the 5-foot dashboard preview |
| `LIDAR_CENTER_HALF_WIDTH_M` | `0.254` | Active half-width of the center safety corridor |
| `LIDAR_GOV_FULL_M` | `1.65` | Active full-throttle clearance boundary |
| `LIDAR_GOV_STOP_M` | `1.25` | Active boundary where the governor reaches its minimum moving target |
| `LIDAR_GOV_MIN_REFERENCE` | `0.60` | Active minimum non-emergency target on the useful throttle scale |
| `LIDAR_OVERRIDE_EMERGENCY_STOP_M` | `1.05` | Active center-corridor hard-stop boundary |
| `AUTONOMOUS_CRUISE_PWM`, `AUTONOMOUS_TURN_PWM`, `AUTONOMOUS_WARN_PWM` | `1.0`, `1.0`, `0.8` | Legacy values; current autonomous throttle comes from the LiDAR governor |
| `CAMERA_STEER_GAIN`, `CAMERA_TURN_BLEND` | `0.75`, `0.35` | Legacy values; current neural steering uses the decoded servo angle directly |
| `MAX_AUTONOMOUS_SPEED_MPH` | `3.2` | Declared but not enforced as a closed-loop speed cap |
| `HIGH_CAMERA_CONFIDENCE` | `0.60` | Declared but unused by the current runtime |
| `FORWARD_OBSTACLE_STOP_DISTANCE_M` | `0.5` | Legacy directional-display threshold, not the active AEB stop boundary |

The block also holds the LiDAR forward-scan window (`LIDAR_FORWARD_ANGLE_MIN_DEG = -75`, `..._MAX_DEG = 75`, `LIDAR_HEADING_WINDOW_DEG = 12`), confidence floor (`LIDAR_MIN_CONFIDENCE = 150`), and physical motor dead-zone boundary (`LIDAR_MIN_MOVE_PWM = 0.55`). The 60% reference governor target maps to 82% physical PWM. Runtime labels continue to store absolute physical throttle, not the reference value.

## Why this choice

Grouping these as flags at the top of `config.py` lets a subsystem be turned on or off, or an autonomy speed/threshold tuned, without editing the control loop or hardware layer. The named LiDAR and camera-confidence values also make the implemented behavior auditable. LiDAR does not steer: it caps forward throttle or requests a stop when AEB is enabled. `PI_CAMERA_ROTATE_180 = True` documents the physical mounting and must stay consistent with dataset preprocessing.

## Failure symptom

If `ENABLE_WEBCAM_VISION` or `USE_PI_CAMERA` does not match the hardware, camera startup can fail or select the wrong source. The autonomous path requests a stop when no fresh accepted model result is available. Turning `ENABLE_HALL_SENSOR` off removes pulse-based speed and odometry, so speed-dependent behavior and related logging lose that measurement. These flags change motion or observability and require bench verification after adjustment.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
