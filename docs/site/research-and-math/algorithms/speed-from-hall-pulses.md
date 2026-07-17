# Speed Measurement and Control

The Raspberry Pi 5 measures wheel speed from a Hall-effect sensor and can use that feedback for manual cruise control. The implementation is in `runtime.py`; constants are in `config.py`.

## Hall-Pulse Speed

The GPIO 24 callback only increments a pulse counter and records the latest pulse time. Approximately every `0.1 s`, `calculate_speed()` converts the counter difference into speed:

```text
pulses_per_second = pulses / elapsed
revolutions_per_second = pulses_per_second / 455
speed_cm_per_second = revolutions_per_second * (pi * 7.0 cm)
raw_mph = speed_cm_per_second * 0.0223694
```

An exponential moving average with `alpha = 0.2` smooths the reading. When motor PWM is effectively off and raw speed is below `0.2 mph`, the displayed value is forced to zero. Distance is integrated from the smoothed speed.

These constants depend on the actual encoder and wheel. A wrong pulse count or wheel diameter scales every speed result. A zero reading also cannot distinguish a stopped wheel from a failed sensor.

## PID Cruise Control

Manual cruise captures the current smoothed speed as its target and computes:

```text
error = target_mph - measured_mph
output = Kp * error + Ki * integral(error) + Kd * derivative(error)
```

Current gains are `Kp = 0.50`, `Ki = 0.08`, and `Kd = 0.005`. The integral is clamped to `[-10, 10]`, and motor output is clamped to `[0, 1]`. Cruise works only in drive, requires a valid nontrivial speed reading, and resets when braking, applying manual throttle, entering autonomous mode, or leaving drive.

Cruise control does not replace autonomous throttle policy, and current LiDAR braking distances do not scale from measured speed. Gains are specific to this chassis and must be retested after changes to mass, gearing, tires, or power.

See [Motors](../../hardware/motors.md) and [Runtime Configuration](../../runtime-code/config/servo-settings.md).
