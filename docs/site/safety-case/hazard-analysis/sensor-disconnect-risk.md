# Sensor Disconnect Risk

Sensor Disconnect Risk covers what happens when a sensor the autonomy loop depends
on drops out mid-run: the LiDAR (USB CP2102), the camera (Raspberry Pi Camera Module 3
Wide), the GPS (BN880), or the dashboard link. The desired behavior is a
detectable, bounded degradation. The current implementation does not meet that
goal uniformly: camera/model staleness requests a stop, while stale LiDAR data
removes the obstacle intervention unless the operator notices and stops the run.

## How it works

Slow camera/serial/network paths use dedicated workers or callbacks, but each device has a
different failure policy:

- **LiDAR disconnect.** `LidarParser` (`lidar.py`) runs a daemon reader thread with
  automatic reconnect: `maybe_reconnect()` retries on a back-off from
  `RECONNECT_INTERVAL_SEC` (1.5 s) up to `RECONNECT_INTERVAL_MAX_SEC` (10 s), and
  `resolve_lidar_serial_port(...)` re-scans `/dev/serial/by-id/*CP2102*` and
  `/dev/ttyUSB*`. `get_latest_scan()` returns an empty list if no scan is newer
  than `SCAN_STALE_SEC` (1.0 s). With no LiDAR, the runtime sets the direction
  arrow to blank and all distances to `MAX_LIDAR_RANGE_M` (12 m) — so the LiDAR
  *override* and *emergency stop* simply do not fire. **This is the important
  caveat: losing LiDAR removes the obstacle-stop layer, so autonomous driving
  should not continue without it; the driver must take manual control.**
- **Camera / model stale.** The local analysis path marks its camera frame stale after
  0.75 s. The remote Jetson Orin Nano path accepts only a matching result no more than
  `JETSON_RESULT_MAX_AGE_SEC` (0.25 s) old. An unavailable/stale result leaves confidence
  zero and requests an autonomous hard stop. `LOW_CAMERA_CONFIDENCE` is 0.25, but accepted
  fresh neural results currently report confidence 1.0; this gate does not detect an
  incorrect but fresh neural prediction.
- **GPS disconnect.** `GpsReader` (`navigation.py`) reads `/dev/ttyAMA0` at 9600 in
  its own thread. No fix means navigation reports `fix=False` and stays inactive;
  GPS loss only disables route/segment autonomy — it does not stop manual driving
  and is not in the emergency path.
- **Dashboard link loss.** Telemetry is sent best-effort over UDP through a latest-payload
  worker; the Zero 2 W renders `NO LINK` when no packets arrive. A dead
  dashboard is an observability loss, not a control loss.

## Why this choice

Sensors on hobby hardware can drop out. Reader work is isolated from the main
loop and known exceptions are caught and logged, reducing the chance that a
sensor retry blocks controller processing. That is not proof that every driver,
library, or hardware failure is contained. LiDAR especially requires operator
discipline: because a missing scan becomes maximum displayed clearance, preflight
and live telemetry must confirm that the sensor is producing data.

## Hazard record

| Sensor | Detection | Response |
|---|---|---|
| LiDAR (CP2102/USB) | Stale scan > 1.0 s; console reconnect logs; dashboard has no `LDR`/points | Auto-reconnect with back-off to 10 s; obstacle layer inactive → driver must go manual |
| Camera / model | Local frame > 0.75 s old, or matching Jetson Orin Nano result unavailable/>0.25 s old | Autonomous hard-stop request (`model_unavailable` / `model_low_confidence`) |
| GPS (BN880) | `fix=False`, low sats on nav page | Navigation stays inactive; manual driving unaffected |
| Dashboard (USB UDP) | Zero 2 W shows `NO LINK` | No dashboard data is used for motion; display observability is lost |

## Series 3 impact

Series 3/4 steering runs remotely on Jetson Orin Nano (`10.42.0.2:8770`). The current Raspberry Pi 5 client
uses a background latest-frame worker, and missing or late results are treated as
unavailable/stale by the autonomous control path. This code path is implemented;
a preserved physical disconnect test is still needed before claiming measured
stop behavior for a pulled Ethernet cable or powered-off Jetson Orin Nano.

## Evidence to attach

- LiDAR reconnect log excerpt (back-off retries)
- Clip of an autonomous hard-stop on a pulled camera / stale frame
- Dashboard `NO LINK` capture
- Manual-override note after a sensor drop

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
