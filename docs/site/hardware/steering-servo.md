# Steering Servo

Steering is done by a single servo that turns the Ackermann linkage. The Raspberry Pi 5
does not drive the servo directly; it sends the servo's PWM through a PCA9685 Servo
Controller over I2C. This is how the steering model's selected angle reaches the steering servo.

## Parts (Amazon)

- [HiLetGo PCA9685 Servo Controller](https://www.amazon.com/dp/B01D1D0CX2?psc=1&ref=cm_sw_r_apin_ct_VRQ3EQR6JZNW89DSFF2X_1&ref_=cm_sw_r_apin_ct_VRQ3EQR6JZNW89DSFF2X_1&social_share=cm_sw_r_apin_ct_VRQ3EQR6JZNW89DSFF2X_1) — $8.99

## Wiring and settings

From `config.py` / `hardware.py`:

| Setting | Value |
|---|---|
| Bus | I2C, address `0x40` |
| Servo channel | `0` |
| PWM frequency | `50 Hz` |
| Pulse range | `1000-2000 us` |
| Actuation range | `180 deg` |

## How it works

- Logical steering is `0` = left, `90` = center, `180` = right. The runtime thinks and logs
  in these logical/reference degrees; the model and training labels never see raw servo
  values.
- `hardware.py` first maps the logical `0..180` range onto the current reference endpoints
  (`48.812..131.188`), then applies the current `+12` degree center trim before writing the
  physical command through `adafruit_servokit`. Center preload is present as a code path
  but both preload constants are currently zero.
- The runtime clamps the logical target, stores it for logs/dashboard use, and snaps commands
  within 0.5 degrees of logical center to exactly 90 before the hardware mapping. With the
  current settings, logical center 90 produces a physical command near 102 degrees.
- Bench work observed direction-dependent return behavior: the wheels did not always return
  to the same physical center after approaching from opposite directions. The runtime now
  includes an experimental IMU yaw-rate correction path in default `straight` mode; field
  claims still require telemetry showing that it engaged. No exact hysteresis angle is
  claimed without the corresponding measurement artifact.

## Hysteresis and Pull Diagnosis

The same logical center can settle differently after a left approach versus a right approach.
Possible contributors include joint play, linkage flex, servo return behavior, vehicle load,
surface conditions, or unequal motor force. The software keeps these controls separate:

- Servo trim changes front-wheel angle.
- Left/right motor scale changes drive force; both current scales are `1.0`.
- Experimental yaw feedback changes steering from measured rotation.

When the car pulls, repeat the test on the same surface, payload, tire state, battery state,
and throttle. Verify physical wheel center from both approach directions before changing a
motor scale. Change one control at a time so one fault is not hidden by compensating for it
elsewhere. A planned pass-through-versus-flick-to-center test remains useful because joystick
history may affect how the linkage returns even when the final command is 90.

## Why this choice

- The PCA9685 Servo Controller generates the 50 Hz servo pulse in dedicated hardware and offloads pulse
  timing from the Raspberry Pi 5. This reduces dependence on control-loop timing, but does not remove
  power, I2C, calibration, servo, or linkage sources of jitter.
- Keeping all servo-specific compensation in the mapping layer keeps the logical steering
  labels clean for training and for the dashboard.

## Verify before a run

- Bench tests: `code/test_files/steering/pca9685_servo_test.py` sweeps the servo, and
  `code/test_files/steering/calibrate_servo.py` helps set the center trim.
- Failure symptoms: the servo not moving at all can come from I2C, servo power, pulse
  configuration, wiring, or the servo/linkage itself (confirm whether `0x40` is visible).
  An off-center rest position can come from trim, linkage, installation, or directional
  hysteresis; it should not be assigned to one cause without a bench check.
  Do not finalize trim constants unless the exact number has been characterized.

## Related pages

- [Hardware Build Overview](build-overview.md)
- [Bench Tests](../testing/bench-tests/overview.md)
- [Hardware Class](../runtime-code/hardware/hardware-class.md)
- [IMU](imu.md)
