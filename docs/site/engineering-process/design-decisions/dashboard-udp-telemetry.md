# Dashboard UDP Telemetry

This page records the decision to send dashboard telemetry from the Raspberry Pi 5 to the
Zero 2 W over **UDP across a USB Ethernet gadget link**, instead of a serial
cable or a Wi-Fi/mDNS connection.

## Decision

The Raspberry Pi 5 controller sends a JSON telemetry packet roughly every 100 ms to the
Zero 2 W dashboard receiver over UDP. The transport is fixed to the USB Ethernet
gadget between the two boards:

- Raspberry Pi 5 `usb0` = `192.168.10.1`, Zero 2 W `usb0` = `192.168.10.2`
- Dashboard UDP target = `192.168.10.2:8765`

The sender is `Hub75DashboardSender` in
`code/controller/current/rc_car_app/hub75_dashboard.py`; the defaults live in
`config.py`:

```python
HUB75_DASHBOARD_TRANSPORT = "udp"            # default
HUB75_DASHBOARD_HOST = "192.168.10.2"
HUB75_DASHBOARD_UDP_PORT = 8765
HUB75_DASHBOARD_SEND_INTERVAL_SEC = 0.1
```

Each packet is one line of JSON (`json.dumps(payload) + "\n"`) carrying speed,
gear, turn signals, servo angle, throttle/brake percent, drive mode, LiDAR
points, camera pixels, CPU temp, nav status, and so on. The Zero 2 W renders it in
`z2w_dashboard.py`.

## Alternatives considered

| Option | Pros | Cons |
|---|---|---|
| Serial cable (`/dev/ttyACM0`) | dead simple, no networking | a second dedicated cable; the transport is retained as a fallback but not the default |
| Wi-Fi + mDNS (`zero2w.local`) | no cable at all | flaky and slow to resolve; competes for the air and adds latency/dropouts; explicitly removed as a default |
| **UDP over USB Ethernet gadget (chosen)** | one cable provides a dedicated IP link; fixed numeric target avoids mDNS; no delivery handshake | the USB gadget link needs keeper/recovery tooling, and UDP does not confirm that the Zero 2 W rendered a packet |

## Reason

UDP fits a replaceable display feed because it has no acknowledgement or retransmission
contract; a lost datagram can be replaced by the next update. `runtime.py` wraps the
transport in `AsyncDashboardSender`. The controller replaces one pending state snapshot,
while the worker performs JSON serialization and `sendto()`. This prevents stale state
packets from forming a backlog. It is still not a hard-real-time guarantee, and a successful
UDP send proves only that the local kernel accepted the datagram.

Pinning it to the USB Ethernet gadget with static IPs (`.1` / `.2`) removes Wi-Fi
fallback and mDNS resolution from the dashboard path. Wi-Fi/`zero2w.local`
fallback was deliberately removed and must not be re-added unless Ram explicitly asks.

## How to know it worked (test gate)

- The car log should print `Hub75 dashboard telemetry sending UDP to
  192.168.10.2:8765.` (if it says `zero2w.local`, stale code/env is active).
- On the Zero 2 W, `ss -lunp | grep 8765` shows the receiver listening.
- `NO LINK` on the display means the receiver is alive but no packets arrived
  recently — check `usb0` carrier, ARP, and ping both ways.
- `code/test_files/setup/install_usb_dashboard_link.sh` installs the static IPs
  plus the keeper service used for the project's ARP/USB recovery procedure.

## Related pages

- `engineering-process/design-decisions/pi-plus-jetson-compute-split.md`
- `testing/failures/overview.md`
- `roadmap/next-steps.md`
