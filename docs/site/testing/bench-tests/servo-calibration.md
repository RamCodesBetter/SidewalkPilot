# Servo Calibration

Servo calibration is the step-and-find-the-endpoints test: I nudge the steering servo in tiny increments while watching the physical wheels, so I can pin down where true center, the usable endpoints, and any dead zone actually are. There are two related utilities for this, and they operate on the same PCA9685 servo (I2C `0x40`, channel `0`, `50 Hz`, `1000-2000 us`, `180` degree range).

## How it works

- `code/test_files/steering/calibrate_servo.py` is a keyboard offset finder. It brings up a small pygame window and drives the PCA9685 servo through Adafruit `ServoKit`, mapping a normalized value in `[-1, 1]` onto the `0-180` degree range. Pressing `A` adds and `D` subtracts a step (`ADJUSTMENT_STEP = 0.01`) to the center offset, clamped to `[-1, 1]`; `Q` quits. When it exits it prints the final offset it landed on. If the PCA9685 dependencies are missing it drops into a dummy-servo simulation mode so the key logic can still be exercised.
- `code/test_files/steering/pca9685_servo_test.py` is the companion sweep test (see `servo.md`): it sweeps `--min-angle` to `--max-angle` by `--step` (default `1.0` degree, `0.03 s` delay) so I can watch the endpoints and confirm the servo reaches them cleanly before I hunt for center.
- Together they answer: where is mechanical center, are both endpoints reachable without buzzing, and how large is the smallest reliable step.

## Command

Run on the Pi 5, wheels off the ground:

```bash
# offset / center finder (A = +0.01, D = -0.01, Q = quit)
python3 code/test_files/steering/calibrate_servo.py

# endpoint sweep
python3 code/test_files/steering/pca9685_servo_test.py --min-angle 0 --max-angle 180 --step 1
```

## Pass / warn / fail

- Pass: I can settle the wheels visibly straight and read back a repeatable offset; both endpoints are reached without stall or buzz.
- Warn: endpoints buzz or the servo hunts at rest — pulse-width range or supply, not code.
- Fail: no motion or an I2C open error — check `0x40`, channel `0`, wiring, and 5V.

## Why it matters

- Calibration is where I separate mechanical facts (center, endpoints, backlash) from the logical `0=left / 90=center / 180=right` convention the model and logs use. Physical compensation belongs in the runtime mapping layer, not in the model labels — this test just measures the raw servo so I know what that mapping has to correct for.
- These are calibration utilities, and they write raw servo values rather than replaying the complete runtime reference mapping. `config.py` currently has a checked-in +12-degree trim (`STEERING_SERVO_CENTER_OFFSET = 12/90`) plus reference limits `48.812` and `131.188`; an environment variable or untracked `steering_tune.json` can override the trim on a device.

## Related pages

- `testing/bench-tests/servo.md`
- `runtime-code/hardware/pca9685-servo.md`
- `hardware/steering-servo.md`
