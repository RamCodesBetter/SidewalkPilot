# Manual Override

Manual override is the primary operational control layer. While the Xbox
controller is connected and the Raspberry Pi 5 loop is responsive, operator input can cancel
autonomy and the Share button can request shutdown. Physical power cutoff remains
necessary for faults that prevent software input processing.

## Hazard

Autonomous mode (camera model steering) or a navigation route could command a path
the operator judges unsafe (a bad steering angle, driving toward a person, entering
a road). The software override reduces this risk only while the controller is connected
and the Raspberry Pi 5 event loop remains responsive; it is not a substitute for physical power control.

## Detection and trigger

The main loop watches the Xbox controller (pygame) every iteration. Autonomous mode
is cancelled by `cancel_autonomous_mode()` when the loop processes any of these:

- **Steering input** with `abs(value) > 0.1` (`STEERING_AXIS`).
- **Gas** with `throttle > 0.05` (`THROTTLE_AXIS`).
- **Brake** pressed (`BRAKE_AXIS`); brake also cancels an active navigation route.

Pressing the autonomy toggle (`AUTONOMY_TOGGLE_BUTTON = 0`) turns autonomous mode
off directly. Any of these also cancels cruise control. Navigation "AUTO" segments
are cancelled by the same operator inputs via `navigation_manual_input_should_cancel`.

## Response

`cancel_autonomous_mode()` sets `autonomous_mode = False`, zeroes throttle and motor
PWM, clears brake state, re-centers steering, and resets the cruise PID. Control
returns to the operator's live stick and trigger inputs on a subsequent loop
iteration.

The quit path is separate and final: `QUIT_BUTTON = 15` (or a pygame `QUIT` event)
sets `shutdown_flag`, which breaks the main loop and runs the ordered teardown at
exit, sending a dashboard shutdown, stopping sensors/camera, and cleaning up GPIO
(`dashboard_sender.send_shutdown()`, `hardware.cleanup()`).

## Stop condition and who triggers it

The operator triggers override. In the implemented arbitration order, manual
input takes priority over model steering but not over enabled AEB; an AEB
hard-stop can still hold the car under a manual forward-throttle command. This
ordering does not cover a disconnected controller or failed control process.

## Evidence

- Code: `runtime.py` — `cancel_autonomous_mode`, the `JOYAXISMOTION`/`JOYBUTTONDOWN`
  handlers, `shutdown_flag`, and the `finally` teardown.
- Config: `config.py` — `AUTONOMY_TOGGLE_BUTTON`, `QUIT_BUTTON`, `STEERING_AXIS`,
  `THROTTLE_AXIS`, `BRAKE_AXIS`.
- Field evidence: the operator uses manual takeover during supervised runs; a
  labeled, timed override-latency test has not yet been preserved.

## Series 3 note

Series 3 moves steering inference to the Jetson Orin Nano, but override still lives on
the Raspberry Pi 5 in the same loop and is unchanged: the Raspberry Pi 5 owns the controller and the motors,
so operator override does not depend on the model host being reachable.

## Fault Responses

| Fault | Current behavior | Remaining limitation |
|---|---|---|
| Enabled AEB emergency threshold | Forward throttle is removed and brake requested | Configured threshold is not measured stopping-distance proof |
| Stale camera/Jetson Orin Nano result | Autonomous path requests a stop instead of replaying indefinitely | Process-wide faults can still affect response timing |
| Stale or empty LiDAR scan | Reader retries; intervention becomes unavailable | This is fail-open for obstacle intervention and must be visible to operator |
| Dashboard telemetry loss | Driving continues; display shows stale/no link or exits by policy | Dashboard is observability, not a motion interlock |
| GPS loss | Route guidance cannot update reliably | Manual control remains; GPS loss is not a camera-steering stop by itself |
| Controller/process failure | Software override may be unavailable | Operator requires independent physical power cutoff |

Fault handling must be tested with wheels unloaded before intentional disconnect tests on the ground.

## Related pages

- [Safety Overview](../safety-overview.md)
- [Field Testing](../../testing/field-testing/overview.md)
- [Decision Priority](../../autonomy-stack/architecture/decision-priority.md)
