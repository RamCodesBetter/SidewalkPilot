# Dashboard Telemetry Loss

The Zero 2 W dashboard is an observability device, not a control authority. Losing the
telemetry link does not intentionally change steering or motor state. Dashboard serialization
and transport run in a latest-payload worker rather than directly in the controller loop.

## Hazard

The dashboard link (Pi 5 `192.168.10.1` to Zero 2 W `192.168.10.2` over USB Ethernet,
UDP port 8765) can drop because of a cable, power, interface, or neighbor-resolution
failure. The architecture keeps this observability path outside routine actuator arbitration.

## Detection

- **Pi side:** `AsyncDashboardSender` accepts the newest state snapshot immediately and
  calls `Hub75DashboardSender` from its worker thread. `sendto()` failures are caught and
  logged. Sends are throttled to `HUB75_DASHBOARD_SEND_INTERVAL_SEC = 0.1`.
- **Zero side:** the receiver renders `NO LINK` when it is alive but has not received a
  packet recently, so a dropped link is visible on the panel.
- **USB link health** is checked with `ip -br addr show usb0`, `cat
  /sys/class/net/usb0/carrier`, `ip neigh show dev usb0`, and a ping both ways.

## Response

No dashboard payload is used to calculate steering, braking, or AEB. Packet loss therefore
does not intentionally change a motion command. Recovery is by the USB keeper/reset helpers
(`code/test_files/setup/install_usb_dashboard_link.sh`), not by anything in the driving loop.

Linked shutdown is preserved: when the controller quits, it calls
`dashboard_sender.send_shutdown()` so the Zero receiver is told to stop; the sender
also advertises an idle-exit window (`HUB75_DASHBOARD_IDLE_EXIT_SEC = 2.0`).

## Stop condition and who triggers it

None. Dashboard telemetry loss has no motion-response rule. The worker boundary prevents
routine UDP work from running in actuator arbitration, but it is not a measured hard-real-time
or process-isolation guarantee.

## Evidence

- Code: `hub75_dashboard.py` — UDP `_write_payload`, `send_shutdown`,
  `close`.
- Config: `config.py` — `HUB75_DASHBOARD_HOST/UDP_PORT/SEND_INTERVAL_SEC/IDLE_EXIT_SEC`,
  USB-only transport default.
- Ops: `code/test_files/setup/install_usb_dashboard_link.sh` (keeper + hard-reset recovery).
- Field observation: `NO LINK` rendering has been observed. A controlled loop-latency test
  during link failure is not preserved here.

## Series 3 note

Series 3 does not touch the dashboard link; telemetry is a Pi/Zero concern unrelated to
where the steering model runs.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
