# Speed from Hall Pulses

Speed From Hall Pulses explains how SidewalkPilot turns raw magnetic pulses from a wheel-mounted hall-effect sensor into a smoothed miles-per-hour reading. The math lives in `calculate_speed` in `code/controller/current/rc_car_app/runtime.py`; the constants are in `code/controller/current/rc_car_app/config.py`; the hall sensor is on GPIO 24.

## How it works

A hall-effect sensor on GPIO 24 fires once per magnet pass as the wheel turns. Every pulse triggers the `pulse_detected` callback wired in `run()`, which just increments `metrics.pulse_count` and stamps `metrics.last_pulse_time`. Counting is decoupled from measuring, so the interrupt work stays tiny.

`calculate_speed` samples that counter on a fixed cadence and converts pulse rate to speed:

- **Windowing.** It only recomputes when at least `0.1 s` has elapsed since the last calculation, giving a stable ~10 Hz measurement window regardless of loop jitter.
- **Pulse rate.** `pulses_in_interval = pulse_count - previous_pulse_count`, then `pulses_per_second = pulses_in_interval / elapsed`.
- **Revolutions.** `revs_per_second = pulses_per_second / PULSES_PER_REVOLUTION`, where `PULSES_PER_REVOLUTION = 455.0` (encoder disc / magnet count per wheel revolution).
- **Linear speed.** `speed_cm_per_sec = revs_per_second * WHEEL_CIRCUMFERENCE_CM`, where `WHEEL_CIRCUMFERENCE_CM = pi * WHEEL_DIAMETER_CM` and `WHEEL_DIAMETER_CM = 7.0`, so the circumference is about `21.99 cm`.
- **Unit convert.** `current_raw_mph = speed_cm_per_sec * CM_PER_SEC_TO_MPH`, with `CM_PER_SEC_TO_MPH = 0.0223694`.
- **Smoothing.** The raw reading is passed through an exponential moving average: `smoothed = alpha * raw + (1 - alpha) * smoothed`, with `SPEED_SMOOTHING_ALPHA = 0.2`. A hard zero-clamp forces `smoothed = 0` when the motor PWM is essentially off and raw speed is below 0.2 mph, so a stopped car reads exactly 0 instead of drifting on stale pulses. `total_distance_cm` is integrated from the smoothed speed each tick.

| Concept field | Value in this project |
|---|---|
| Input | Hall pulse count on GPIO 24 (`metrics.pulse_count`) |
| Window | Recompute every `>= 0.1 s` |
| Constants | `PULSES_PER_REVOLUTION = 455.0`, `WHEEL_DIAMETER_CM = 7.0`, `CM_PER_SEC_TO_MPH = 0.0223694`, `SPEED_SMOOTHING_ALPHA = 0.2` |
| Output | `metrics.current_raw_mph` and `metrics.smoothed_speed_mph` (mph) |
| Runtime use | `calculate_speed` in `runtime.py`, called each loop tick |

## Why this choice

Counting pulses in the callback and doing the arithmetic on a fixed window keeps the interrupt path cheap and reduces control-loop timing sensitivity. The EMA smooths the quantization noise from counting only a handful of pulses per 0.1-second window, so the dashboard and cruise controller receive a steadier value. The explicit zero-clamp avoids keeping a nonzero speed alive after pulses stop. Cruise control refuses to engage if `smoothed_speed_mph <= 0.1`; the current LiDAR braking distances are fixed configuration values and do not scale with measured speed.

## Worked example

Suppose 120 pulses arrive in a 0.10 s window:

- `pulses_per_second = 120 / 0.10 = 1200`
- `revs_per_second = 1200 / 455.0 ~= 2.637`
- `speed_cm_per_sec = 2.637 * (pi * 7.0) = 2.637 * 21.99 ~= 58.0 cm/s`
- `current_raw_mph = 58.0 * 0.0223694 ~= 1.30 mph`

If the previous smoothed value was `1.10 mph`, the new smoothed reading is `0.2 * 1.30 + 0.8 * 1.10 = 1.14 mph`, showing how the EMA eases toward the raw value rather than snapping.

## What can go wrong

- **Wrong `PULSES_PER_REVOLUTION`.** If the magnet/encoder count is mis-set, every speed reading scales by the same wrong factor; 455 must match the physical disc.
- **Wrong wheel diameter.** `WHEEL_DIAMETER_CM = 7.0` assumes a specific tire; a different wheel changes circumference and therefore mph linearly.
- **Sensor dropout.** If the hall sensor stops reporting, `current_raw_mph` falls to 0. Cruise-control engagement is rejected at low/absent speed, but a zero reading does not distinguish a stopped wheel from a failed sensor. Treat it as a sensor-health fault, not proof that the car is stationary.
- **Very short windows.** At low speed only a few pulses land per window, so quantization is coarse; the EMA is what makes that usable.

## Related pages

- `research-and-math/machine-learning/regression-framing.md`
- `ai-and-models/training-pipeline/overview.md`
- `autonomy-stack/navigation/overview.md`
