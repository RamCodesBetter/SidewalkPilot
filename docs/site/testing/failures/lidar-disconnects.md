# LiDAR Disconnects

The LiDAR supplies the center-corridor automatic emergency braking (AEB) policy. It can cap forward throttle or request a stop, but it does not steer. A link drop removes that coverage until data returns.

## The Hardware and the Failure

The unit is a Youyeetoo FHL-LD19, currently on USB `/dev/ttyUSB0` through a CP2102 USB-to-UART adapter at 230400 baud (it previously ran on `/dev/ttyAMA2`). USB descriptor-read errors (`-110` and device-not-accepting-address) were observed on this platform, but an error code alone does not identify whether the cause was a cable, port, power condition, adapter, or device.

## What the runtime does about it

The LiDAR reader in `code/controller/current/rc_car_app/lidar.py` is built to survive this without blocking the driving loop:

- **It runs on its own daemon thread** (`LidarParser._run`). Expected reader exceptions are caught in that worker, so the controller loop does not directly wait on serial reads; this is not a guarantee against every process or hardware fault.
- **On a fault it self-heals.** `mark_fault` closes the port and schedules a reconnect; `maybe_reconnect` retries with a backoff that grows from `RECONNECT_INTERVAL_SEC = 1.5` s up to `RECONNECT_INTERVAL_MAX_SEC = 10.0` s, and it re-resolves the port each time (`resolve_lidar_serial_port` scans `/dev/serial/by-id/*CP2102*`, `*Silicon_Labs*`, then `/dev/ttyUSB*`/`/dev/ttyACM*`), so it recovers even if the device re-enumerates on a new node.
- **Stale scans are treated as no data, safely.** `get_latest_scan` returns an empty list once the newest scan is older than `SCAN_STALE_SEC = 1.0` s. Downstream, `determine_turn_direction` on an empty scan returns clear/`MAX_LIDAR_RANGE_M`, so a dropped LiDAR does **not** phantom-brake the car — but it also means AEB coverage is genuinely gone during the gap. That is the safety trade to be aware of.

## The Trade to Watch

A disconnect currently fails *open* with respect to AEB rather than phantom-stopping. That means the safety layer is unavailable until reconnect. The dashboard indication and preflight check are operational mitigations, not substitutes for fail-closed sensor-health logic.

## Debug order when LiDAR shows none/zero

Follow the hardware playbook, not guesswork: stop the car service so there is only one reader, then confirm the port and raw bytes.

```bash
# Raspberry Pi 5
sudo systemctl stop sidewalkpilot-rpi-car.service
stty -F /dev/ttyUSB0 230400 raw -echo
timeout 5s cat /dev/ttyUSB0 | hexdump -C
```

Check enumeration, cable/port, exclusive ownership of the serial device, and baud (`230400`). The former GPIO-UART motor-enable instructions do not apply to the current CP2102 USB path.

## Test setup

- **Setup:** Raspberry Pi 5 controller, FHL-LD19 on `/dev/ttyUSB0` (CP2102), branch `lidar-aeb-v2`.
- **Procedure:** run the car, then physically unplug/replug the LiDAR USB mid-run and watch the log for the reconnect messages and the dashboard LiDAR field.
- **Pass/warn/fail for reconnect behavior:** pass = the worker reports loss, the dashboard indicates missing data, and the stream reconnects without an observed controller-loop pause; warn = delayed reconnect; fail = crash or sustained controller-loop pause. This test does not make fail-open motion safe.
- **Evidence to attach (planned):** runtime log showing `mark_fault`/reconnect, dashboard capture of the LiDAR field, `hexdump` of raw bytes after replug.

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
