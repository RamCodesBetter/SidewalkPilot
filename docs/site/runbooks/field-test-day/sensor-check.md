# Sensor Check

Sensor Check is the pre-motion runbook for confirming that sensors required by the intended test are reporting plausible live values rather than defaults. A passing spot check is necessary but does not prove fault-free behavior for the whole drive. This matters because an empty LiDAR scan maps to maximum-clearance values, while an unavailable or stale model produces a zero-confidence autonomous stop request.

## Preconditions

- The controller is up and all subsystems logged as started (`start-procedure.md`).
- The car is stationary and, ideally, wheels off the ground for the drive baseline.
- The dashboard is linked so readings can be watched live, or the CSV log is open.

## Steps

1. LiDAR points: confirm the scan is live, not stale. The parser marks a scan stale after `SCAN_STALE_SEC = 1.0` s and then returns an empty list. Watch the dashboard LiDAR page or the CSV column `Number of LiDAR Points in Scan` — it must be non-zero. Wave a hand in front and confirm `LiDAR Front Distance (m)` drops. Evidence: non-zero point count and a front distance that tracks a real obstacle.
2. LiDAR direction/AEB arbitration: confirm the direction arrow reacts. `determine_turn_direction` returns `STOP_WARNING` under the stop threshold and `WARN_WARNING` under the warn threshold, and only points with confidence ≥ 150 count. AEB is armed by default (`Metrics.aeb_enabled = True`) and, in gear D, brakes hard when a stop condition is seen. Evidence: front distance under threshold flips the dashboard alert to `STOP`/`WARN`.
3. Camera / model: confirm frames are flowing and the selected model produces changing steering results. Local Pi analysis has a 0.75-second frame guard; the live Series 3/4 path accepts only a matching Jetson result no more than 0.25 seconds old. Either stale condition requests a hard stop. Accepted neural results currently report confidence `1.0`, so confidence distinguishes unavailable/stale output but is not a calibrated scene-quality score. Evidence: fresh timestamps/inference rate and steering output that changes with the view.
4. GPS: confirm a fix if the run uses navigation. `GpsReader` reads `$GxGGA` sentences on `/dev/ttyAMA0` at 9600; check `fix` and `sats`. No fix is acceptable for manual-only driving but blocks A* navigation and crosswalk handoff. Evidence: fix true and satellite count.
5. Hall / speed: roll the wheels by hand (or the lifted drive baseline) and confirm speed appears. Pulses come from GPIO24; the CSV `Current Speed (MPH)` and `Time Since Last Hall Sensor Pulse (s)` should update. No pulses means cruise control will refuse to engage (`try_toggle_cruise_control` needs speed > 0.1 mph).
6. Steering and IMU: command a small left and right and confirm the wheels track. Logical steering is `0=left, 90=center, 180=right`, mapped to the PCA9685 in `hardware.py`. With the checked-in `straight` yaw mode, confirm startup reports `Yaw-rate PID steering ENABLED`, yaw telemetry changes with rotation, and the controller reports fresh data before attributing a result to closed-loop correction. Evidence: wheels move both directions, return near center, and the IMU stream is fresh.
7. Turn signals / dashboard fields: toggle the D-pad and hazard button and confirm the dashboard reflects it, verifying the telemetry path (`runtime` → `hub75_dashboard.py` serializer → `z2w_dashboard.py` renderer) is intact end to end.

## Stop condition

Do not begin the powered field test if a sensor required by that test fails its live check, if steering does not track, or if the operator-cancel path fails. GPS is not required for a manual-only bench drive, but it is required before attributing results to route navigation.

## Evidence

- Live LiDAR point count and a front-distance reaction
- Camera confidence and steering-bias readings
- GPS fix/sat count; hall-sensor speed reading; servo left/center/right check

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
