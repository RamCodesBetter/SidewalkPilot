# I2C

This page documents the I2C bus on the Raspberry Pi 5 and the single device on it: the PCA9685 PWM driver that positions the steering servo.

## What is on the bus

| Field | Value |
|---|---|
| Part | HiLetGo PCA9685 16-channel 12-bit PWM driver |
| Role | Generates the 50 Hz servo pulse that drives the Ackermann steering servo |
| Bus | I2C bus 1 (Raspberry Pi 5 `SDA1` / `SCL1`, the default `board.SDA` / `board.SCL`) |
| Address | `0x40` |
| Channel | `0` (of the 16 PWM outputs) |
| Frequency | 50 Hz |
| Pulse range | 1000-2000 us, actuation range 180 deg |

## How it works

The runtime opens the bus with Adafruit's `busio.I2C(board.SCL, board.SDA)` and drives the board through `adafruit_servokit.ServoKit`, targeting address `0x40` and servo channel `0` at 50 Hz. All of these come from constants in `rc_car_app/config.py` (`PCA9685_I2C_ADDRESS`, `PCA9685_SERVO_CHANNEL`, `PCA9685_FREQUENCY_HZ`, `STEERING_SERVO_MIN_PULSE_US`, `STEERING_SERVO_MAX_PULSE_US`, `STEERING_SERVO_ACTUATION_RANGE_DEG`) and are consumed by `PCA9685SteeringServo` in `rc_car_app/hardware.py`.

Logical steering is `0 = left`, `90 = center`, `180 = right`. The hardware layer maps that logical angle to a servo pulse and applies a small center trim (`STEERING_SERVO_CENTER_OFFSET`, `STEERING_SERVO_CENTER_PRELOAD`, `STEERING_SERVO_CENTER_PRELOAD_WINDOW`) before writing the pulse. The I2C bus only carries the servo command; the servo is powered separately (see power wiring), and the PCA9685 is the only I2C peripheral on the Raspberry Pi 5 in the current build.

## Why this choice

Offloading servo timing to a dedicated PWM chip keeps precise 50 Hz pulses off the Raspberry Pi 5's software-timed GPIO, which is busy with the control loop, camera, and sensors. It also isolates steering electrically from the motor GPIO. Documenting the bus separately matters because a steering fault can look like a model failure: if the servo does not move, the first check is whether `0x40` still enumerates on the bus, not whether the model output is wrong.

## Test

Verify the device enumerates before any drive test:

```bash
# Raspberry Pi 5
i2cdetect -y 1        # expect 0x40 to appear
```

Bench servo motion is covered by `code/test_files/steering/pca9685_servo_test.py` and `code/test_files/steering/calibrate_servo.py`.

Failure symptoms: if `0x40` is missing from `i2cdetect`, check SDA/SCL wiring and the PCA9685's own logic power. `hardware.py` retries device init up to four times on a temporarily-busy bus, then falls back to simulation mode and prints an initialization error rather than moving the servo.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
