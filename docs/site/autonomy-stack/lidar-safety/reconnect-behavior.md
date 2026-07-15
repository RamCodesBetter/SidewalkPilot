# Reconnect Behavior

The LiDAR is on a USB serial link, and USB links drop — a bumped cable, a re-enumeration, a
power blip. The reader must survive that without crashing the car controller or freezing the
main loop. This page documents how `LidarParser` in
`code/controller/current/rc_car_app/lidar.py` finds the port, retries, and fails
open with respect to obstacle intervention.

## How it works

**Port resolution.** `SERIAL_PORT` defaults to `"auto"`. `resolve_lidar_serial_port()`
scans candidates in order: `/dev/serial/by-id/*CP2102*`, `/dev/serial/by-id/*Silicon_Labs*`,
the known LD19 by-id path, then `/dev/ttyUSB*` and `/dev/ttyACM*`. It returns the first one
that exists and is readable/writable. If none is ready it returns `None`. (Auto-resolution is
why the same code works whether the adapter enumerates as `ttyUSB0` or a stable by-id path.)

**Background thread.** `start()` launches a daemon thread running `_run()`, which loops
`_read_data_once()` every `READ_LOOP_SLEEP_SEC = 0.01`. Any exception in the loop is caught,
logged, and turned into a fault (`mark_fault`) rather than killing the thread. Because it is a
separate daemon thread, keeping normal serial reconnect waits outside the main driving loop.

**Fault + backoff.** On a serial error, `mark_fault()` closes the port, clears the buffer, and
records the time. `maybe_reconnect()` then waits `reconnect_interval` before retrying. The
interval starts at `RECONNECT_INTERVAL_SEC = 1.5` and multiplies by 1.5 on each failed attempt
up to `RECONNECT_INTERVAL_MAX_SEC = 10.0` (exponential backoff), then resets to 1.5 on a
successful connect. Reconnect log spam is throttled: `log_connect_status()` only reprints the
same message every `RECONNECT_LOG_INTERVAL_SEC = 15.0` seconds.

**Stale-data behavior.** `get_latest_scan()` returns an empty list if the newest scan
is older than `SCAN_STALE_SEC = 1.0` second. When the runtime gets an empty scan it sets all
sector distances to `MAX_LIDAR_RANGE_M` and `direction_arrow` to blank — i.e. a disconnected
LiDAR reads as "no obstacle seen," not a phantom stop. This is a deliberate decision: LiDAR
absence must not block basic driving or photo collection, so the retry happens in the
background. It also means stale LiDAR is not fail-closed; autonomous operation must stop by
operator action if scan health is lost.

## Why this choice

Field hardware can disconnect, so the reader is built to retry without blocking normal input
processing. Backoff avoids
hammering a missing port; log throttling keeps the journal readable during a long outage;
auto-resolution avoids hardcoding a device path that changes between boots. Running the reader
on its own thread reduces control-loop coupling. It does not prove that every USB or driver
failure is contained, and it does not preserve AEB coverage while scans are absent.

## Key constants

| Constant | Value | Meaning |
|---|---|---|
| `RECONNECT_INTERVAL_SEC` | 1.5 s | Base retry interval |
| `RECONNECT_INTERVAL_MAX_SEC` | 10.0 s | Backoff ceiling |
| `RECONNECT_LOG_INTERVAL_SEC` | 15.0 s | Reconnect-log throttle |
| `READ_LOOP_SLEEP_SEC` | 0.01 s | Reader loop sleep |
| `SCAN_STALE_SEC` | 1.0 s | Stale-scan cutoff (empty scan -> no obstacle intervention) |

Note: `--no-lidar` was tested and removed; the runtime is expected to tolerate LiDAR
disconnects by retrying, not by a disable flag.

## Related pages

- `autonomy-stack/architecture/layered-autonomy.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
