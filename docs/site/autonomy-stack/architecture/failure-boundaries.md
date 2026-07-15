# Failure Boundaries

The runtime contains explicit handling for several failures, but not every subsystem is fail-closed.

| Failure | Current response | Important limit |
|---|---|---|
| Jetson Orin Nano/model unavailable or result stale | Autonomous command is rejected and the autonomous path requests a stop | Manual control still depends on a healthy Raspberry Pi 5/controller path |
| Low model confidence | Autonomous path requests a stop | Confidence calibration is model-dependent |
| LiDAR serial disconnect | Reader retries in a background thread | An empty/stale scan does **not** prove the path is clear; do not start/continue an autonomous safety test without healthy points |
| Center obstacle at or inside 1.05 m with AEB enabled | zero throttle and full hard brake in forward drive | Stopping distance still depends on speed, payload, surface, power, and detection coverage |
| Servo write fault | Brake is forced and throttle is zeroed | Requires the fault to be detected by the write path |
| Dashboard link failure | Driving loop continues; display shows link failure when receiver is alive | Operator loses dashboard observability |
| Human takeover/quit | Autonomy is cancelled or shutdown begins | Measured end-to-end takeover latency is not claimed here |

The most important honest gap is LiDAR loss: reconnect is non-blocking, but the current center-corridor policy does not treat missing returns as a guaranteed emergency stop. Sensor health is therefore a preflight and operational gate.
