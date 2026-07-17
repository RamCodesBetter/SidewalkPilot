# Runtime Configuration

This page documents the steering-servo constants in `code/controller/current/rc_car_app/config.py` and how `code/controller/current/rc_car_app/hardware.py` turns a logical steering command into a real PCA9685 Servo Controller pulse. Logical steering is `0 = left`, `90 = center`, `180 = right`; the servo is on the PCA9685 Servo Controller at I2C `0x40`, channel `0`, running at 50 Hz.

`config.py` is also the central source for subsystem flags, GPIO assignments, LiDAR thresholds, dashboard transport, controller indices, model defaults, and CSV settings. Values below describe the checked-in branch; environment variables and local tuning files can override selected settings.

## How it works

The servo is driven through the Adafruit `ServoKit` on the PCA9685. `config.py` sets the electrical envelope and the center trim, and `hardware.py`'s `PCA9685SteeringServo` applies them.

| Constant | Value | Meaning |
|---|---|---|
| `PCA9685_FREQUENCY_HZ` | `50` | Servo PWM frequency |
| `STEERING_SERVO_MIN_PULSE_US` | `1000` | Pulse width at the `0` (full-left) end |
| `STEERING_SERVO_MAX_PULSE_US` | `2000` | Pulse width at the `180` (full-right) end |
| `STEERING_SERVO_ACTUATION_RANGE_DEG` | `180` | Full logical/servo travel; center is `90` |
| `STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG` | `48.812` | Reference full-left angle before center trim |
| `STEERING_SERVO_REFERENCE_RIGHT_LIMIT_DEG` | `131.188` | Reference full-right angle before center trim |
| `STEERING_SERVO_CENTER_OFFSET` | `0.133333...` | Checked-in +12-degree center trim; environment or saved tuning can override it |
| `STEERING_SERVO_CENTER_PRELOAD` | `0.0` | Near-center preload is disabled |
| `STEERING_SERVO_CENTER_PRELOAD_WINDOW` | `0.0` | Near-center preload window is disabled |
| `STEERING_CENTER_SNAP_DEG` | `0.5` | Logical commands less than 0.5 degrees from center snap to `90` |

The trim math lives in `apply_steering_center_trim_degrees()`. It clamps logical input to `0..180`, maps the two halves into the characterized `48.812..131.188` reference range, adds `center_offset * 90`, and clamps the physical result to `0..180`. The generic preload code remains available, but its value and window are both zero. With the checked-in +12-degree trim, logical center `90` writes physical angle `102`; the two logical endpoints write approximately `60.812` and `143.188`. The model and CSV labels remain in logical `0..180` units.

## Why this choice

The project has observed direction-dependent steering return and left/right asymmetry. Isolating the reference range and center trim lets those mappings be tuned without changing the model or its labels. `RC_CAR_STEERING_SERVO_CENTER_OFFSET` and an optional `steering_tune.json` entry named `trim_delta_deg` can override the checked-in trim; no saved tuning file is checked into this branch.

Two motor-scale constants sit next to the servo block for a related reason:

- `LEFT_MOTOR_PWM_SCALE = 1.0` and `RIGHT_MOTOR_PWM_SCALE = 1.0`. Both are neutral today. Changing them is one possible motor-balance experiment, not proof that an observed pull originates in the motors.

Steering-trim constants and yaw-controller gains are hardware calibration values. Record the test condition and resulting number before changing them.

## Failure symptom

If the PCA9685 or its I2C/servo dependencies are missing, `PCA9685SteeringServo.__init__` raises `PCA9685 servo dependencies are unavailable` (or an I2C error). `hardware.py` retries up to four times, then falls back to a `DummyServo` and prints `Error initializing GPIO: ... Running in simulation mode.` — the wheels then never move even though steering values still update on the dashboard. On a clean boot the expected line is `Using PCA9685 steering servo at 0x40, channel 0.`

## GPIO and Hardware Addresses

| Device | Checked-in assignment |
|---|---|
| Right motor forward/backward | BCM 19 / 20 |
| Left motor forward/backward | BCM 25 / 13 |
| Hall-effect wheel sensor | BCM 24 |
| PCA9685 Servo Controller | I2C `0x40`, channel 0 |

Motor outputs use 1 kHz PWM. Both motor scale factors are currently `1.0`.

## Camera and Safety Flags

The Raspberry Pi Camera Module is enabled at camera index 0 with a 180-degree mounting transform. The active LiDAR center corridor has a `0.254 m` half-width. Governor boundaries are `1.65 m` for full reference throttle, `1.25 m` for minimum moving reference throttle, and `1.05 m` for emergency stop. The minimum moving reference command is 60%, mapped onto the physical motor range beginning at 55% PWM. LiDAR does not steer.

Constants that remain in the file are not automatically active. In particular, old autonomous cruise/turn PWM and camera blend values are legacy unless a current runtime call site uses them.

## Dashboard and Logging

Dashboard telemetry uses UDP over USB Ethernet to `192.168.10.2:8765` at a nominal 10 Hz. The fixed USB address is the live route; Wi-Fi/mDNS is not a fallback. Linked shutdown is enabled.

Runtime CSV files are timestamped per process and written at a nominal `0.1 s` interval. Rows are flushed immediately. Steering labels/logs remain logical degrees, while throttle labels use absolute physical PWM. The exact header in `config.py` is authoritative because columns evolve with the runtime.

## Related pages

- [Runtime Loop](../runtime-loop.md)
- [Wiring and Pin Map](../../hardware/wiring/pin-map.md)
- [Bench Tests](../../testing/bench-tests/overview.md)
