# Limits

This page states the operating envelope and fault-handling behavior of the SidewalkPilot car: what the platform is allowed to do, what it does when a sensor or model fails, and where those limits live in the code. Every field claim elsewhere in these docs should be read against these limits and stop conditions.

## Operating envelope

The car is a small RC platform (Yahboom Ackermann 520M chassis) driven under constant human line-of-sight supervision, with an Xbox controller in hand. It is not designed or permitted to run unattended. Concretely:

- **Speed stays conservative by operating procedure and throttle policy, not an enforced mph cap.** `MAX_AUTONOMOUS_SPEED_MPH = 3.2` is declared but not wired into a final measured-speed governor. The current LiDAR policy can cap forward throttle when AEB is enabled; physical speed still depends on payload, surface, battery, and motor response.
- **Steering is bounded.** Logical steering is `0` (left) to `180` (right), centered at `90`, mapped to the PCA9685 servo in `hardware.py`; the runtime clamps servo degrees before every write (`clamp_servo_degrees`). LiDAR never supplies a steering command.
- **Autonomy is opt-in, per drive.** The car boots in gear `P` (park) with `autonomous_mode = False`. Autonomy engages only after the operator presses A (`AUTONOMY_TOGGLE_BUTTON = 0` in Pygame's zero-based numbering) and the camera/vision processor exists. The live result is then checked every tick; an unavailable Jetson Orin Nano/model result requests a hard stop rather than making the toggle itself prove readiness. Reverse (`R`) bypasses forward AEB by design so the operator can back out manually.

## Fault handling (detection to response)

The runtime hard-stops autonomous motion when the camera/model result is unavailable. LiDAR is different: serial errors trigger reconnect attempts, but an empty or stale scan is not currently a fail-closed stop. The autonomous control path in `apply_autonomous_controls` (`runtime.py`) checks:

| Hazard / limit | Detection | Response | Where |
|---|---|---|---|
| Obstacle very close in center corridor | Enabled AEB and center clearance `<= LIDAR_OVERRIDE_EMERGENCY_STOP_M` (1.05 m) | zero throttle and full brake, reason `lidar_emergency` / `aeb_stop` | `lidar_avoidance.evaluate`, `update_gpio` |
| Obstacle in governed center range | Center clearance between 1.65 m and 1.05 m with AEB enabled | Reduce reference throttle from 100% to 60%, then hold 60%; no steering change | `lidar_avoidance.governor_target` |
| Camera model missing | `webcam_vision is None` | Hard stop, reason `model_unavailable` | `apply_autonomous_controls` |
| Stale model input/result | Local Raspberry Pi 5 frame older than 0.75 s, or matching Jetson Orin Nano result unavailable/older than 0.25 s | Treat as unavailable/low confidence and hard stop | `apply_autonomous_controls` |
| Low model confidence | confidence `< LOW_CAMERA_CONFIDENCE` (0.25) | Hard stop, reason `model_low_confidence` | `apply_autonomous_controls` |
| Obstacle while driving (any mode except R) | `is_stop_brake_condition` true and AEB enabled | Automatic Emergency Braking: full active brake, reason `aeb_stop` | `update_gpio` |
| LiDAR disconnect | serial read error | Background reader keeps retrying with backoff (1.5 s to 10 s); it does not block the control loop or dashboard | `lidar.py` (`maybe_reconnect`) |

The design bias is to stop autonomous motion when the model or camera is unavailable instead of coasting on stale data. When AEB is enabled, a LiDAR stop request overrides forward throttle; it does not alter the model's steering command.

## Manual override and stop

While the controller is connected and the main loop is responsive, manual input has priority over model steering. In `runtime.py`, any of these operator inputs cancels autonomy through `cancel_autonomous_mode`:

- Turning the steering axis past a small deadzone.
- Pressing the gas (cancels and returns manual throttle).
- Pressing the brake.

The quit path is the quit button (`QUIT_BUTTON = 15`) or `Ctrl-C`, which sets `shutdown_flag`. A normal exit attempts to write a final log row, stop sensor/camera workers, send a linked-shutdown packet to the Zero 2 W dashboard, and call `hardware.cleanup()`. A forced process kill, controller disconnect, hardware fault, or power-stage fault may bypass that sequence. The operating rule is that a human types "go," keeps the controller ready, and remains able to cut power.

## Series 3 note

Series 3/4 move steering inference to the Jetson Orin Nano over direct Ethernet. A missing or stale Jetson Orin Nano result resolves to a hard stop in `apply_autonomous_controls`, while LiDAR AEB still arbitrates locally on the Raspberry Pi 5. The Jetson Orin Nano client runs in a worker, so connection timeouts do not block controller input or GPIO updates. There is no enforced final mph speed cap; the current autonomy throttle and LiDAR governor are the active motion limits.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
