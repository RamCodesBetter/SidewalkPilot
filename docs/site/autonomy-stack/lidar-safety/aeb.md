# AEB

Automatic Emergency Braking (AEB) gates the center-corridor LiDAR intervention policy. When
enabled, LiDAR may progressively cap forward throttle and request a full brake at the
emergency boundary. The driver can toggle the policy.

## How it works

Each control-loop iteration evaluates the current scan once through
`lidar_avoidance.evaluate(scan, enabled=metrics.aeb_enabled)`. The result contains the
center clearance, throttle cap, occupancy, action, and stop request. The final brake check
is:

```
aeb_stop_active = metrics.aeb_enabled and gear_mode != "R" and is_stop_brake_condition(state)
```

`is_stop_brake_condition()` includes the policy's `lidar_emergency_stop` state. At or
inside 1.05 m in the center corridor, the policy sets that state and zero throttle.

When AEB is active the runtime forces `brake_force = 1.0`, sets the target PWM to `0.0`,
selects `AEB_BRAKE_RATE = 10.0`, sets `metrics.aeb_triggered = True`, and cancels cruise
control. Because the force is full scale, the hard-brake branch snaps motor PWM straight
to zero and commands H-bridge brake mode instead of using the ramp. The LiDAR policy has
already recorded `stop_reason = "lidar_emergency"`; the fallback `"aeb_stop"` value is
used only if the reason was empty. When the stop condition clears, `aeb_triggered` returns
to false.

AEB is suppressed in reverse (`gear_mode == "R"`) because the center-forward corridor does
not describe what is behind the car. There is no LiDAR steering override.

## Enabling / disabling

AEB defaults to enabled (`Metrics.aeb_enabled = True`). The driver toggles it with
controller button `AEB_TOGGLE_BUTTON = 14`; the change prints to the console and queues a
dashboard notification. The dashboard shows the state as `AEB:ON` / `AEB:OFF`.
`AEB_ACTIVATION_DELAY_SEC = 1.0` remains declared in `config.py`, but no current code reads
it. It therefore does not create an activation delay.

## Why this choice

AEB is outside the neural model so the configured intervention is explicit: progressive
slowdown followed by a close-range brake. It does not prove that all obstacles will be
detected or that 1.05 m is sufficient under every speed, surface, payload, and brake state;
those are field-test questions.

## Key constants

| Constant | Value | Meaning |
|---|---|---|
| `AEB_BRAKE_RATE` | 10.0 | Selected for AEB deceleration; full-force AEB takes the direct hard-brake branch |
| `AEB_ACTIVATION_DELAY_SEC` | 1.0 | Legacy, currently unused declaration |
| `AEB_TOGGLE_BUTTON` | 14 | Controller button to toggle AEB |
| `LIDAR_GOV_FULL_M` | 1.65 m | Full-throttle boundary |
| `LIDAR_GOV_STOP_M` | 1.25 m | Minimum governed-throttle boundary |
| `LIDAR_OVERRIDE_EMERGENCY_STOP_M` | 1.05 m | Emergency-brake boundary |

Field-test logs and video demonstrating an AEB stop are planned to be attached.

## Related pages

- `autonomy-stack/architecture/layered-autonomy.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
