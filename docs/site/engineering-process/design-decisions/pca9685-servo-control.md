# PCA9685 Servo Controller

This page records the decision to drive the Ackermann steering servo through a
**PCA9685 Servo Controller over I2C** instead of generating the servo pulse
directly from a Raspberry Pi 5 GPIO pin.

## Decision

The steering servo is wired to a PCA9685 Servo Controller at I2C address `0x40`, channel `0`,
running at 50 Hz, and is driven through the Adafruit `ServoKit` abstraction. The
Raspberry Pi 5 never toggles the servo signal line itself; it writes an angle to the
PCA9685 Servo Controller, which owns the pulse-width generation in dedicated hardware. The exact
configuration lives in `code/controller/current/rc_car_app/config.py`:

- `PCA9685_I2C_ADDRESS = 0x40`, `PCA9685_SERVO_CHANNEL = 0`, `PCA9685_FREQUENCY_HZ = 50`
- Pulse range `STEERING_SERVO_MIN_PULSE_US = 1000` to `STEERING_SERVO_MAX_PULSE_US = 2000`
- `STEERING_SERVO_ACTUATION_RANGE_DEG = 180`

The wrapper class `PCA9685SteeringServo` in
`code/controller/current/rc_car_app/hardware.py` wraps the board and exposes a
simple `value` setter in the logical `0..180` degree space (`0` = left,
`90` = center, `180` = right). Any real-hardware center/trim compensation is
applied inside that layer by `apply_steering_center_trim_degrees(...)`, so the
rest of the runtime and the training labels only ever deal with clean logical
degrees.

## Alternatives Considered

| Option | Pros | Cons |
|---|---|---|
| Direct Raspberry Pi 5 GPIO PWM (software or hardware PWM pin) | One fewer board; no I2C dependency | The Raspberry Pi 5's software PWM jitters under CPU load, causing servo twitch, and competes with the other GPIO/PWM users on the Raspberry Pi 5 (four motor pins and the Hall-effect wheel-speed sensor) |
| **PCA9685 Servo Controller over I2C (chosen)** | dedicated 50 Hz pulse generation reduces dependence on Raspberry Pi 5 loop timing; frees Raspberry Pi 5 GPIO; reuses the Adafruit `ServoKit` library | one extra board + I2C, power, calibration, and servo dependencies |

## Reason

The Raspberry Pi 5 is already running a 60 Hz software control loop that consumes the
latest LiDAR, GPS, camera, and hall-sensor state while updating motor PWM. A software-timed servo
pulse on that same CPU jitters whenever the loop is busy, and steering jitter is
directly visible and bad for both driving and clean training data. Offloading
the pulse to the PCA9685's own timer removes that class of problem entirely, and
it follows the project rule to lean on existing, proven libraries rather than
reinvent servo timing.

## How to Know It Worked (Test Gate)

- `code/test_files/steering/pca9685_servo_test.py` and `code/test_files/steering/calibrate_servo.py`
  drive the servo through its range on the bench with no runtime attached.
- On the car, a centered logical command (`90`) should hold a steady physical
  center with no visible twitch even while the rest of the control loop is busy.
- If the board is missing or I2C fails, `Hardware.__init__` catches the error
  and falls back to a `DummyServo` so the controller still boots (simulation
  mode) instead of crashing.

## Related Pages

- [Steering Servo](../../hardware/steering-servo.md)
- [Failures and Lessons](../../testing/failures/overview.md)
- [Next Steps](../../roadmap/next-steps.md)
