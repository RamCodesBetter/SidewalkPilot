# PCA9685 Servo

The `PCA9685SteeringServo` class in `code/controller/current/rc_car_app/hardware.py` drives the Ackermann steering servo through a PCA9685 16-channel PWM board over I2C. It is the one place that converts a logical steering command into a real servo pulse, including the center-trim compensation that keeps the wheels pointed straight when the runtime commands "center."

## How it works

At construction the class opens I2C on `board.SCL`/`board.SDA` (via `busio.I2C`) and creates an Adafruit `ServoKit(channels=16, ...)` at the configured address and frequency. It then selects one channel and configures its pulse range:

- I2C address `PCA9685_I2C_ADDRESS` = `0x40`, channel `PCA9685_SERVO_CHANNEL` = `0`.
- PWM frequency `PCA9685_FREQUENCY_HZ` = `50` Hz (standard hobby-servo rate).
- Pulse width range `set_pulse_width_range(1000, 2000)` µs (`STEERING_SERVO_MIN_PULSE_US` / `STEERING_SERVO_MAX_PULSE_US`).
- `actuation_range` = `180` degrees (`STEERING_SERVO_ACTUATION_RANGE_DEG`).

The servo exposes a single `value` property. The runtime writes a logical angle over the actuation range: `0` = left, `90` = center, `180` = right. The setter clamps that request, maps it into the characterized reference range, applies the center trim, and writes the resulting physical angle to `self._servo.angle`. `_value` retains the clamped logical request, so the runtime, logs, and dashboard report command intent rather than the compensated physical output.

### Center trim math

`apply_steering_center_trim_degrees` implements the hardware-side compensation. Given the logical angle, the 180-degree actuation range, and the trim constants, it:

1. Clamps the logical request to `0..180` and computes its normalized displacement from center.
2. Maps the left and right halves linearly into the reference limits `48.812..90` and `90..131.188` degrees.
3. Adds the center offset. The checked-in default is `17 / 90 = 0.188888...`, which adds 17 physical degrees.
4. Applies a near-center preload only when its window is greater than zero. Both preload values are currently zero, so this path is disabled.
5. Clamps the physical result to `0..180`.

Current live trim constants in `config.py`:

| Constant | Value | Meaning |
|---|---|---|
| `STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG` | `48.812` | Reference output for logical full-left before center trim |
| `STEERING_SERVO_REFERENCE_RIGHT_LIMIT_DEG` | `131.188` | Reference output for logical full-right before center trim |
| `STEERING_SERVO_CENTER_OFFSET` | `0.188888...` | Checked-in +17-degree center trim; an environment variable or `steering_tune.json` can override it |
| `STEERING_SERVO_CENTER_PRELOAD` | `0.0` | Near-center preload is disabled |
| `STEERING_SERVO_CENTER_PRELOAD_WINDOW` | `0.0` | Near-center preload window is disabled |

With the checked-in defaults, logical center `90` writes physical angle `107`. Logical full-left and full-right write approximately `65.812` and `148.188` after the +17-degree trim. These are software commands, not direct measurements of wheel angle. Bench work also observed direction-dependent return behavior, but the branch does not contain a traceable record supporting one exact hysteresis angle.

## Why this choice

- Putting trim in the servo layer keeps logical steering (`0/90/180`) clean for the model and training labels; the model does not receive servo-specific compensation as an input.
- A dedicated pulse range and 50 Hz frequency match the servo's spec and give repeatable end-to-end travel.
- Reading back `_value` (the commanded raw, not the trimmed physical) means logs and the z2w dashboard report what the driver/model intended.

## Failure symptom

If the PCA9685 dependencies (`board`, `busio`, `adafruit_servokit`) are missing or the board is not on I2C `0x40`, construction raises, `Hardware.__init__` catches it, prints `Error initializing GPIO: ...; Running in simulation mode.`, and installs a `DummyServo`. The wheels then never move even though the runtime keeps writing `steering_servo.value`. Confirm with `i2cdetect` that `0x40` is present.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
