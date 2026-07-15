# Manual Override

Manual override is the primary operational control layer. While the Xbox
controller is connected and the Pi loop is responsive, operator input can cancel
autonomy and the Share button can request shutdown. Physical power cutoff remains
necessary for faults that prevent software input processing.

## Hazard

Autonomous mode (camera model steering) or a navigation route could command a path
the operator judges unsafe (a bad steering angle, driving toward a person, entering
a road). The software override reduces this risk only while the controller is connected
and the Pi event loop remains responsive; it is not a substitute for physical power control.

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

Series 3 moves steering inference to the Jetson (Jon), but override still lives on
the Pi in the same loop and is unchanged: the Pi owns the controller and the motors,
so operator override does not depend on the model host being reachable.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
