# PID Cruise Control

PID Cruise Control is the closed-loop speed regulator that holds a target mph by adjusting motor PWM. It runs on the Raspberry Pi 5 inside `update_gpio` in `code/controller/current/rc_car_app/runtime.py`, using the gains defined in `code/controller/current/rc_car_app/config.py`. It reuses the smoothed speed from the hall sensor (see the Speed From Hall Pulses page) as its feedback signal.

## How it works

A PID controller drives a measured value toward a setpoint by summing three terms of the error `e = setpoint - measured`:

- **P (proportional)** reacts to the present error.
- **I (integral)** accumulates past error to erase steady-state offset.
- **D (derivative)** reacts to how fast the error is changing, damping overshoot.

Cruise control is only active in gear `D`, with no brake, once the driver toggles it on (controller button in `CRUISE_TOGGLE_BUTTONS = (4,)`). On enable, the target is captured from the current smoothed speed (`state["cc_target_speed"] = metrics.smoothed_speed_mph`), and the dashboard notification `CC:ON` is queued. Each loop tick the `state["cc_active"]` branch runs:

```
error   = cc_target_speed - smoothed_speed_mph
p_term  = KP * error
pid_integral_error += error * dt
pid_integral_error  = clamp(pid_integral_error, -10, 10)   # anti-windup
i_term  = KI * pid_integral_error
d_term  = KD * (error - pid_previous_error) / dt           # dt > 0
pid_output = p_term + i_term + d_term
desired_pwm = clamp(pid_output, 0.0, 1.0)
```

The gains are `KP = 0.50`, `KI = 0.08`, `KD = 0.005`. The output is clamped to `[0.0, 1.0]` because PWM is a normalized throttle and the car cannot brake with negative PWM here. The integrator is clamped to `+/-10` for anti-windup so a long uphill or a stall cannot build an enormous accumulated term that then overshoots badly when the error clears.

Cruise disengages and the PID state (`pid_integral_error`, `pid_previous_error`, `pid_output`) is reset to zero whenever: the brake is pressed, the driver nudges throttle (throttle cancel), autonomous mode takes over, or the gear leaves `D`. The `+/- 0.1 mph` target trim on the D-pad calls `queue_cc_adjust_notification`.

| Concept field | Value in this project |
|---|---|
| Setpoint | `cc_target_speed` (mph), captured on enable, trimmable +/- 0.1 |
| Measured | `metrics.smoothed_speed_mph` from hall sensor EMA |
| Gains | `KP = 0.50`, `KI = 0.08`, `KD = 0.005` |
| Output | `desired_pwm` clamped to `[0.0, 1.0]` |
| Anti-windup | integral clamped to `[-10, 10]` |
| Runtime use | `state["cc_active"]` branch of `update_gpio` in `runtime.py` |

## Why this choice

Open-loop throttle does not hold a speed: the same PWM gives different mph on a slope, on grass, or as the LiPo sags. A PID loop closes that gap using the same smoothed hall-sensor speed the dashboard already shows, so the car maintains a chosen pace hands-off for cleaner, more consistent data collection. The gains are deliberately gentle (small `KI`, tiny `KD`) because the plant is a small, light RC car where aggressive gains would oscillate. Resetting all PID state on every disengage path prevents stale integral/derivative history from kicking the throttle when cruise is re-enabled, and the throttle-cancel behavior keeps the human override immediate and intuitive.

## Worked example

Target `2.0 mph`, current smoothed speed `1.6 mph`, `dt = 0.016 s` (about a 60 Hz tick), starting from a cleared integrator and `pid_previous_error = 0`:

- `error = 2.0 - 1.6 = 0.4`
- `p_term = 0.50 * 0.4 = 0.20`
- `pid_integral_error = 0 + 0.4 * 0.016 = 0.0064` -> `i_term = 0.08 * 0.0064 ~= 0.0005`
- `d_term = 0.005 * (0.4 - 0.0) / 0.016 = 0.005 * 25 = 0.125`
- `pid_output = 0.20 + 0.0005 + 0.125 ~= 0.326` -> `desired_pwm ~= 0.33`

So the controller commands about 33% throttle to close a 0.4 mph gap on the first tick, with the integral term still near zero and only building if the error persists.

## What can go wrong

- **Integral windup.** Without the `+/-10` clamp, a sustained inability to reach speed (stall, steep hill) would inflate `pid_integral_error` and cause a large overshoot when the load clears. The clamp bounds that.
- **`dt = 0` division.** The derivative divides by `dt`; the code guards with `d_term = ... if dt > 0 else 0.0`.
- **Bad feedback.** If the hall sensor stops reporting, cruise is refused at enable time (`smoothed_speed_mph <= 0.1`), so the loop never runs on a dead sensor.
- **Gain retuning.** These gains are tuned for this car's mass and motor. On a different chassis or battery state they may need re-tuning; too-high `KP`/`KD` will oscillate the throttle audibly.

## Related pages

- `research-and-math/machine-learning/regression-framing.md`
- `ai-and-models/training-pipeline/overview.md`
- `autonomy-stack/navigation/overview.md`
