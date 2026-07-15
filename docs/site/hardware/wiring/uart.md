# UART

This page documents the UART serial ports on the Raspberry Pi 5 and the devices attached to them: the GPS receiver, the IMU, and (historically) the LiDAR. The compass packaged on the BN880 is an I2C device, not part of the GPS UART stream.

## UART devices

| Device | Part | Port | Baud | Source |
|---|---|---|---|---|
| GPS receiver | BN880 | `/dev/ttyAMA0` | `9600` | `GPS_PORT` / `GPS_BAUD` in `rc_car_app/navigation.py` |
| IMU | Seeed XIAO MG24 Sense (6-axis) | `/dev/ttyAMA3` (Raspberry Pi 5 GPIO8/9) | `115200` | `STEERING_YAW_PID_PORT` / `STEERING_YAW_PID_BAUD` |
| LiDAR (former path) | Youyeetoo FHL-LD19 | `/dev/ttyAMA2` | `230400` | superseded — LiDAR now runs over USB/CP2102 |

## How it works

The GPS reader in `navigation.py` opens `/dev/ttyAMA0` at 9600 baud and parses GGA fixes for the route manager. The live navigation path does not read the board's magnetometer.

The IMU is a Seeed XIAO MG24 Sense mounted for closed-loop yaw-rate steering. Its firmware,
verifier, reader thread, and controller are implemented. The runtime defaults to
`STEERING_YAW_PID_MODE = "straight"` and falls back to open-loop steering if the IMU cannot
start or its samples are stale.

The LiDAR was originally a GPIO-UART device on `/dev/ttyAMA2` at 230400 baud (with a Raspberry Pi 5 UART overlay on GPIO4/5). It has since moved to a USB/CP2102 connection; see the USB wiring page. The `230400` baud and the FHL-LD19 packet format are unchanged, only the transport moved.

Because `/dev/ttyAMA0` is a real UART, the serial console must be freed from it or GPS reads fail with a permission/busy error. GPS is `/dev/ttyAMA0`; do not confuse it with the LiDAR's former `/dev/ttyAMA2`.

## Why this choice

Separate links let each serial device run at its own baud without sharing a byte stream: GPS is a 9600-baud NMEA stream, LiDAR is a 230400-baud USB-serial stream, and the IMU has its own GPIO UART. A failure can still affect shared power, USB, or process resources.

## Test

```bash
# Raspberry Pi 5 — GPS (stop the car service first to avoid two readers)
timeout 5s cat /dev/ttyAMA0        # expect NMEA sentences ($GPGGA, $GPRMC ...)

# Raspberry Pi 5 — raw LiDAR bytes when on GPIO UART (former path)
stty -F /dev/ttyAMA2 230400 raw -echo
timeout 5s cat /dev/ttyAMA2 | hexdump -C
```

GPS/compass bench checks live in `code/test_files/sensors/bn880_test.py`. An empty GPS stream can come from console ownership, permissions, another reader, wiring, or missing fixes. The old LiDAR UART commands are historical and do not test the current USB path.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
