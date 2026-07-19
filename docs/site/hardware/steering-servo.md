# Steering Servo

Steering is done by a single servo that turns the Ackermann linkage. The Raspberry Pi 5 does not
drive the servo directly; it sends the servo's PWM through a PCA9685 16-channel PWM
controller over I2C. This is the hardware the steering model ultimately commands.

## Parts (Amazon)

- [HiLetGo PCA9685 16 Channel 12-Bit PWM Driver](https://www.amazon.com/dp/B01D1D0CX2?psc=1&ref=cm_sw_r_apin_ct_VRQ3EQR6JZNW89DSFF2X_1&ref_=cm_sw_r_apin_ct_VRQ3EQR6JZNW89DSFF2X_1&social_share=cm_sw_r_apin_ct_VRQ3EQR6JZNW89DSFF2X_1) — $8.99

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
  (`48.812..131.188`), then applies the current `+17` degree center trim before writing the
  physical command through `adafruit_servokit`. Center preload is present as a code path
  but both preload constants are currently zero.
- Bench work observed direction-dependent return behavior: the wheels did not always return
  to the same physical center after approaching from opposite directions. The runtime now
  includes an experimental IMU yaw-rate correction path in default `straight` mode; field
  claims still require telemetry showing that it engaged. No exact hysteresis angle is
  claimed without the corresponding measurement artifact.

## Why this choice

- The PCA9685 generates the 50 Hz servo pulse in dedicated hardware and offloads pulse
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

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
