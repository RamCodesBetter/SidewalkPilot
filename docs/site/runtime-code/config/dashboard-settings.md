# Dashboard Settings

This page documents the HUB75 dashboard-telemetry constants in `code/controller/current/rc_car_app/config.py`, the Pi-side sender `code/controller/current/rc_car_app/hub75_dashboard.py`, and the Zero-side receiver/renderer `code/controller/current/z2w_dashboard.py`. The link is USB Ethernet only: the Pi 5 sends UDP to the Zero 2 W.

## How it works

The Pi 5 is `192.168.10.1` and the Zero 2 W is `192.168.10.2` over the `usb0` gadget. The Pi packs a small JSON payload every send interval and sends it by UDP to `192.168.10.2:8765`; the Zero receives it and draws the current page on the LED panel.

| Constant | Value | Meaning |
|---|---|---|
| `ENABLE_HUB75_DASHBOARD_TELEMETRY` | `True` | Master switch for the sender |
| `HUB75_DASHBOARD_TRANSPORT` | `udp` | Transport; the current decision is UDP over USB Ethernet |
| `HUB75_DASHBOARD_HOST` | `192.168.10.2` | Zero 2 W USB address |
| `HUB75_DASHBOARD_UDP_PORT` | `8765` | UDP port the Zero receiver listens on |
| `HUB75_DASHBOARD_SERIAL_PORT` | `/dev/ttyACM0` | Fallback serial device (only if transport is `serial`) |
| `HUB75_DASHBOARD_BAUD_RATE` | `115200` | Serial baud, serial transport only |
| `HUB75_DASHBOARD_SEND_INTERVAL_SEC` | `0.1` | ~10 Hz payload rate |
| `HUB75_DASHBOARD_IDLE_EXIT_SEC` | `2.0` | Idle window before the link is treated as gone |
| `DASHBOARD_BRIGHTNESS_PERCENT_DEFAULT` | `80` | Startup panel brightness |
| `DASHBOARD_BRIGHTNESS_STEP_PERCENT` | `10` | Brightness step per adjustment |
| `DASHBOARD_PAGE_COUNT` | `17` | Highest valid internal page ID; page IDs are sparse |

The fixed numeric target keeps dashboard telemetry on the USB Ethernet gadget rather than a Wi-Fi/mDNS route or dedicated serial transport.

The highest page ID is threaded through every layer. `DASHBOARD_PAGE_COUNT = 17` in `config.py`, while `DASHBOARD_PAGE_COORDS` defines the visible two-dimensional grid. IDs are sparse because removed pages were not renumbered. Any page change must be updated in the controller grid, serializer clamp, and Zero renderer.

The sender also clamps the other payload fields defensively — `brightness_percent` and the various percent/confidence fields to `0..100`, `servo_deg` to `0..180`, `cpu_temp_c` to `0..99` — so a bad upstream value cannot corrupt the display packet.

## Why this choice

USB-only telemetry is a deliberate, standing decision based on the project's observed Wi-Fi/mDNS link problems. Wi-Fi fallback and the old `zero2w.local` hostname were intentionally removed and should not be re-added without an explicit decision. The serial path and its constants remain only as a non-default fallback.

## Failure symptom

`NO LINK` on the LED panel means the Zero receiver process is alive but has not received a packet recently — the render side is fine, the packets are not arriving. Typical causes: the Pi controller is not running, `usb0` shows carrier `1` but ARP/ping fails, or the sender never connected. On a healthy Pi boot the log prints `Hub75 dashboard telemetry sending UDP to 192.168.10.2:8765.`; if it instead prints a `zero2w.local` target, stale code or an env override is active. Debug order: car service up, Zero receiver listening on `8765`, `usb0` up with carrier, ping both ways, then read logs.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
