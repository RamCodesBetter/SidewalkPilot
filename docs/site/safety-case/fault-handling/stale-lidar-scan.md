# Stale LiDAR Scan

The LiDAR is SidewalkPilot's obstacle sensor and the input to AEB. If its serial
link drops or the scan goes old, the runtime must not keep trusting the last good
scan, that would be a phantom "clear ahead". This page documents how a stale or
missing scan is detected and what the car does.

## Hazard

The FHL-LD19 LiDAR (CP2102 USB serial, 230400 baud) can disconnect (bad cable,
brownout, unplugged adapter) or fall behind. A stale scan reported as fresh would let
AEB and the LiDAR throttle governor act on obstacles that have moved or vanished.

## Detection

Two independent mechanisms in `lidar.py`:

- **Staleness gate.** `get_latest_scan()` returns an empty list if the newest
  completed scan is older than `SCAN_STALE_SEC = 1.0`. The runtime therefore sees
  "no points", not old points.
- **Reconnect loop.** The reader thread catches serial errors, disconnects, and
  retries with backoff (`RECONNECT_INTERVAL_SEC = 1.5` up to
  `RECONNECT_INTERVAL_MAX_SEC = 10.0`), auto-resolving the CP2102 port. This runs on
  a daemon thread, keeping normal serial waits outside the driving loop.

Per-point quality is also filtered: points with `confidence < 150` or zero distance
are discarded before any distance is computed.

## Response

With an empty scan, `determine_turn_direction()` returns the neutral arrow and
`MAX_LIDAR_RANGE_M = 12.0` for all sectors, so no false close obstacle is invented.
The consequence depends on mode:

- In **manual** driving, the operator retains full control; only the LiDAR-derived
  AEB and governed slowdown are unavailable until the scan returns.
- In **autonomous** mode, losing LiDAR removes the obstacle safety net. The camera
  model still steers, but the LiDAR governor/AEB arbitration has nothing to act on,
  so the car should be driven manually until LiDAR reconnects. Treating "no LiDAR"
  as "safe to drive autonomously" is a known limitation, marked **planned** for a
  stricter autonomous-mode gate.

## Stop condition and who triggers it

The staleness gate is automatic (1.0 s). It does not by itself brake the car; it
removes LiDAR obstacle data so AEB cannot fire on ghosts. The operator or the
camera-confidence hard-stop remain the active stop conditions when LiDAR is down.

## Evidence

- Code: `lidar.py` — `SCAN_STALE_SEC`, `get_latest_scan`, `_run`/`mark_fault`/
  `maybe_reconnect`, confidence filter (`< 150`).
- Runtime: `runtime.py` prints "LiDAR reader running in background; runtime will keep
  retrying if disconnected."
- Field evidence: reconnect-without-loop-stall is observed on runs; a timed
  disconnect/recovery clip is **planned / not-yet-captured**.

## Series 3 note

LiDAR handling is unchanged by Series 3; it runs on the Pi and feeds the same AEB
arbitration regardless of where the steering model runs.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
