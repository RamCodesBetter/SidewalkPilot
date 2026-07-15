# USB

This page documents the USB connections on the Raspberry Pi 5: the LiDAR in its current serial configuration, and the USB Ethernet gadget link that carries dashboard telemetry to the Zero 2 W.

## USB devices

| Device | Part | USB role | Endpoint |
|---|---|---|---|
| LiDAR | Youyeetoo FHL-LD19 via CP2102 USB-to-UART adapter | USB serial (CDC) | `/dev/ttyUSB0` @ `230400` (auto-resolved) |
| Dashboard link | Zero 2 W | USB Ethernet gadget (`usb0`) | Raspberry Pi 5 `192.168.10.1`, Zero 2 W `192.168.10.2`, UDP `8765` |

## How it works

**LiDAR over USB.** The FHL-LD19 connects through a Silicon Labs CP2102 USB-to-UART bridge and appears as a USB serial device. `rc_car_app/lidar.py` resolves the port automatically at startup: `resolve_lidar_serial_port` prefers a stable `/dev/serial/by-id/*CP2102*` / `*Silicon_Labs*` symlink, then falls back to `/dev/ttyUSB*` and `/dev/ttyACM*`, and only uses a fixed port if `RC_CAR_LIDAR_SERIAL_PORT` is set. Baud stays `230400`. This replaced the earlier GPIO-UART `/dev/ttyAMA2` path (see the UART page); the sensor and protocol are the same, only the transport moved to USB.

**Dashboard USB Ethernet.** The Raspberry Pi 5 and Zero 2 W are linked by a USB Ethernet gadget that exposes `usb0` on both ends with fixed addresses: Raspberry Pi 5 `192.168.10.1/24`, Zero 2 W `192.168.10.2/24`. The Raspberry Pi 5 sends dashboard telemetry as UDP to `192.168.10.2:8765` (`HUB75_DASHBOARD_HOST` / `HUB75_DASHBOARD_UDP_PORT` in `config.py`). This link is USB-only by current project decision, with no Wi-Fi fallback. A serial fallback over `/dev/ttyACM0` at 115200 exists in code but is not the active transport.

## Why this choice

USB gives the LiDAR a serial path with a stable by-id symlink, so the runtime can auto-detect it and retry after a disconnect in its reader thread. The USB Ethernet dashboard link provides a fixed point-to-point IP path, and keeping telemetry USB-only removes Wi-Fi and mDNS from that path.

## Test

```bash
# Raspberry Pi 5 — LiDAR port present and readable
ls -l /dev/serial/by-id/ | grep -i cp2102
ls -l /dev/ttyUSB*

# Raspberry Pi 5 — USB Ethernet link to the Zero 2 W
ip -br addr show usb0
cat /sys/class/net/usb0/carrier      # 1 = link up
ping -c 3 192.168.10.2               # from Raspberry Pi 5

# Zero 2 W — dashboard receiver listening
ss -lunp | grep 8765
```

Failure symptoms: a missing `/dev/ttyUSB0` means the expected adapter did not appear at that name; check the stable by-id path, `lsusb`, cable, host port, power, and adapter. Descriptor error `-110` records a USB timeout but does not identify which component caused it. On the dashboard link, carrier `1` with failed ping means the interface reports a physical link but IP/ARP traffic is not completing; the keeper service and `code/test_files/setup/install_usb_dashboard_link.sh` provide the project recovery path. `NO LINK` on the display means the receiver is alive but has not seen a recent packet.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
