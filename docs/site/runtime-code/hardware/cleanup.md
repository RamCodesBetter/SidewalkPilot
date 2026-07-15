# Cleanup

`Hardware.cleanup()` in `code/controller/current/rc_car_app/hardware.py` is the normal shutdown path for physical devices on the Raspberry Pi 5 controller. It is called when GPIO initialization fails and during the runtime's normal exit sequence. It attempts to stop motor outputs and release the servo, but it cannot run after every possible power, process, or hardware failure.

## How it works

`cleanup()` walks the devices in a deliberate order:

1. Drive motors first. For each of the four PWM channels (`motor_left_fwd`, `motor_left_bwd`, `motor_right_fwd`, `motor_right_bwd`) it sets `device.value = 0` (stop the wheels) and then `device.close()` (release the GPIO). Motors are stopped before anything else so the car is not driving during the rest of teardown.
2. Hall sensor. `hall_sensor.close()` releases the input pin.
3. Steering servo last. It recenters by writing `steering_servo.value = STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0` (i.e. `90`, logical center), sleeps 0.05 s to let the servo reach center, then calls `close()`. On the real `PCA9685SteeringServo`, `close()` sets `self._servo.angle = None`, which stops sending a PWM pulse so the servo is no longer actively held.

Every step is wrapped in its own `try/except` that swallows errors. That is intentional: shutdown must finish even if one device is already gone or in "simulation mode" with dummy objects. The dummy classes (`DummyPWM`, `DummyDigitalInput`, `DummyServo`) implement the same `.value` / `.close()` shape, so `cleanup()` runs identically whether or not real hardware came up.

`runtime.run()` calls `hardware.cleanup()` in its exit path after stopping the LiDAR, camera, GPS, and dashboard, giving a clean, ordered teardown of the whole controller.

## Why this choice

- Stopping motors before releasing pins reduces the chance of leaving a drive command active during an orderly teardown.
- Recentering the servo before closing leaves the wheels straight for the next run and avoids parking the linkage against a hard stop.
- Per-device `try/except` makes cleanup idempotent and crash-tolerant — it is the same routine used in the init-failure fallback, so it must tolerate partially constructed or dummy devices.

## What it does

| Step | Action | Purpose |
|---|---|---|
| 1 | 4× motor `value = 0`, then `close()` | Stop wheels, release motor pins |
| 2 | `hall_sensor.close()` | Release GPIO 24 input |
| 3 | Servo `value = 90` (center), sleep 0.05 s, `close()` | Recenter wheels, then drop the PWM pulse |

## Failure symptom

If `cleanup()` is skipped (e.g. the process is `kill -9`'d rather than exiting through the loop), the last-written motor PWM and the servo pulse can persist — the car may keep creeping or the wheels stay turned until power is cut. The correct shutdown is to quit the controller through its normal exit (or Ctrl-C), which runs this path. The linked shutdown decision also has quitting the Raspberry Pi 5 controller tell the Zero 2 W dashboard receiver to stop.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
