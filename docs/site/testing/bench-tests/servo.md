# Servo

The servo bench test is the lowest-level steering check: does the PCA9685 actually drive the steering servo through its full range. It runs `code/test_files/steering/pca9685_servo_test.py`, a minimal script that opens the PCA9685 over I2C and sweeps one channel back and forth until Ctrl-C. I run this first whenever I suspect the servo, the I2C bus, or the wiring, because it removes the model, the runtime, and the joystick from the picture entirely — if the sweep is smooth here, the hardware path is good.

## How it works

- It opens the PCA9685 through Adafruit `ServoKit` on I2C address `0x40` at `50 Hz`, sets the pulse-width range to `1000-2000 us`, and sets an actuation range of `180` degrees. These electrical constants match the runtime, but the sweep writes raw angles and does not apply the runtime's reference limits, +17-degree trim, or IMU correction.
- It sweeps the servo from `--min-angle` (default `0`) up to `--max-angle` (default `180`) by `--step` degrees (default `1.0`) with a `--delay` (default `0.03 s`) between steps, then sweeps back down, looping forever. Each angle it commands is printed.
- On Ctrl-C it sets the servo angle to `None` (releases the channel) and prints `done`.

## Command

Run on the Raspberry Pi 5, wheels off the ground:

```bash
python3 code/test_files/steering/pca9685_servo_test.py
# narrow the sweep or slow it down:
python3 code/test_files/steering/pca9685_servo_test.py --channel 0 --min-angle 60 --max-angle 120 --step 2 --delay 0.05
```

## Pass / warn / fail

- Pass: the front wheels sweep smoothly across the commanded range and return; printed angles match the physical motion.
- Warn: motion is jittery or the endpoints buzz — usually pulse-width limits or a weak 5V rail, not code.
- Fail: no motion or an I2C error on open — check the PCA9685 wiring, the `0x40` address, and 5V/GND before blaming anything upstream.

## Why this choice

- Reusing the same PCA9685 electrical constants checks the low-level path. Driving still requires separate validation of the runtime mapping and loaded steering behavior.
- Keeping this as a pure sweep with no dependencies on the model or joystick makes a servo/I2C fault trivially isolatable.

## Evidence to attach

- Command output (the stream of `angle=` lines)
- A short clip of the wheels sweeping
- Note of any endpoint buzz or dead zone

## Related pages

- `testing/bench-tests/servo-calibration.md`
- `testing/bench-tests/steering-trim-tuner.md`
- `hardware/steering-servo.md`
