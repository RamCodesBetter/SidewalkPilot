# Servo Settings

This page documents the steering-servo constants in `code/controller/current/rc_car_app/config.py` and how `code/controller/current/rc_car_app/hardware.py` turns a logical steering command into a real PCA9685 pulse. Logical steering is `0 = left`, `90 = center`, `180 = right`; the servo is on the PCA9685 at I2C `0x40`, channel `0`, running at 50 Hz.

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

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
