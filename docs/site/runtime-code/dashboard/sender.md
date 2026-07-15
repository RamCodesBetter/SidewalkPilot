# Dashboard Sender

`code/controller/current/rc_car_app/hub75_dashboard.py` serializes dashboard state. The live runtime wraps it with `AsyncDashboardSender` in `runtime.py`, keeping DNS, JSON encoding, socket writes, and shutdown retries outside the 60 Hz control loop.

## Live Configuration

| Setting | Default |
|---|---|
| Transport | UDP |
| Target | `192.168.10.2` |
| Port | `8765` |
| Send interval | `0.1 s` |
| Linked shutdown | enabled |

Environment overrides are `RC_CAR_DASHBOARD_TRANSPORT`, `RC_CAR_DASHBOARD_HOST`, `RC_CAR_DASHBOARD_UDP_PORT`, and `RC_CAR_DASHBOARD_SHUTDOWN_ON_EXIT`.

## Latest-Payload Behavior

The main loop calls `AsyncDashboardSender.send()` with current state. That method replaces the pending argument snapshot and returns immediately. The worker sends at the configured rate. If several 60 Hz updates occur between 10 Hz transmissions, only the newest survives; stale dashboard packets never form a backlog.

Transient notification rows use a small FIFO because notifications, unlike state, must not disappear merely because another state update arrived.

## Failure Behavior

UDP is intentionally connectionless. A successful `sendto()` proves only that the local kernel accepted the datagram, not that the Zero 2 W rendered it. Link health is verified with `ping`, receiver service status, and the display's `NO LINK`/`STALE` states.

```bash
ping -c 3 192.168.10.2
journalctl -u sidewalkpilot-rpi-car.service -n 80 -l --no-pager
```

The USB link is the only live dashboard route. Wi-Fi is not a telemetry fallback.
