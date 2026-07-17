# Decision Priority

Decision Priority is the exact order in which SidewalkPilot resolves competing
commands on a single control tick. It is the concrete implementation of the
layered-autonomy idea: when the human, the LiDAR safety layer, the navigation
manager, and the steering model all want something different, this ordering
decides who actually moves the servo and motors.

## How it works

The priority chain is enforced in two functions in
`code/controller/current/rc_car_app/runtime.py`: `apply_autonomous_controls(...)`
(which decides the autonomous steering/throttle intent) and `update_gpio(...)`
(which arbitrates AEB and writes hardware). The chain, highest priority first:

1. **Human / manual override.** In the `pygame` event loop, any steering input
   with `abs(value) > 0.1`, any throttle `> 0.05`, or any brake press calls
   `cancel_autonomous_mode(...)` and, where wired, route cancellation. The change
   takes effect when the Raspberry Pi 5 loop processes the event; it depends on a connected
   controller and responsive process.
2. **Center-corridor emergency stop.** With AEB enabled, a valid point at or
   inside `LIDAR_OVERRIDE_EMERGENCY_STOP_M = 1.05 m` requests a hard stop before
   model inference is used for motion.
3. **Model availability gate.** If there is no emergency stop, the camera model
   gets a vote. Local Raspberry Pi 5 analysis uses a 0.75-second frame-age guard; a Jetson Orin Nano result
   must be no more than `JETSON_RESULT_MAX_AGE_SEC = 0.25 s` old and match the selected
   model. Confidence must be ≥ `LOW_CAMERA_CONFIDENCE` (0.25). If the model is
   unavailable, stale, or below the configured confidence threshold, the runtime requests a hard stop with reason
   `model_unavailable` or `model_low_confidence`. Accepted neural results currently use confidence `1.0`, so this gate is not a calibrated scene-uncertainty detector.
4. **Model steering command.** The model's steering angle becomes the servo target
   and is mapped to `target_heading_deg` (clamped to `MAX_TARGET_HEADING_DEG = 60°`).
   LiDAR never replaces this steering value.
5. **LiDAR throttle cap.** With AEB enabled, center clearance governs the forward
   target: 100% at 1.65 m, linearly down to 60% reference at 1.25 m, held to
   1.05 m. The model's throttle output is not used.
6. **AEB re-check + hardware write.** Back in `update_gpio`, if AEB is armed and
   `is_stop_brake_condition(...)` is true, it forces brake with `AEB_BRAKE_RATE`
   and overrides the throttle to zero. Then the rate-limited PWM and servo values
   are written to hardware — the last, lowest-priority step.

The important asymmetry is now between axes: the model owns lateral control and
LiDAR owns only its configured longitudinal cap/stop. The same LiDAR policy object
is reused through the control tick.

## Why this choice

The human can cancel autonomy, a stale model cannot continue driving, and the
center-corridor policy can cap or stop forward motion without creating a second
steering controller. Telemetry exposes model state, clearance, AEB state, and the
chosen LiDAR action. This ordering is inspectable, but quantitative stopping and
detection coverage still require controlled tests.

## Priority table

| Priority | Decision | Trigger | Constant / code |
|---:|---|---|---|
| 1 | Manual override | stick/throttle/brake input | `cancel_autonomous_mode` |
| 2 | Emergency hard stop | enabled AEB and center clearance <= 1.05 m | `LIDAR_OVERRIDE_EMERGENCY_STOP_M` |
| 3 | Model gate | fresh matching result + conf >= 0.25 | 0.75 s local frame guard; `JETSON_RESULT_MAX_AGE_SEC = 0.25` |
| 4 | Model steering | mapped heading | `MAX_TARGET_HEADING_DEG` 60° |
| 5 | LiDAR throttle cap | enabled AEB and center clearance < 1.65 m | `LIDAR_GOV_*` |
| 6 | AEB + hardware | armed AEB, then final write | `AEB_BRAKE_RATE` 10.0 |

## Related pages

- `autonomy-stack/architecture/data-flow.md`
- `autonomy-stack/lidar-safety/overview.md`
- `autonomy-stack/lidar-safety/aeb.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
