# Dashboard Receiver

`code/controller/current/z2w_dashboard.py` runs on the Raspberry Pi Zero 2 W. It receives controller JSON, retains the last value for every field, and renders the current page with `rpi-rgb-led-matrix`.

## Normal Service

```bash
sudo systemctl status sidewalkpilot-z2w-dashboard.service -l --no-pager
journalctl -u sidewalkpilot-z2w-dashboard.service -n 80 -l --no-pager
ss -lunp | grep 8765
```

Expected startup output includes:

```text
Dashboard receiver listening on UDP 0.0.0.0:8765
```

## Receiver States

- Before the first payload, the panel displays `NO LINK` after three seconds.
- Four seconds after the last received payload, it displays `STALE`.
- `--idle-exit-sec 0` keeps the service waiting indefinitely for reconnection.
- An explicit `shutdown` payload exits cleanly for linked controller/dashboard shutdown.

Malformed JSON is ignored. A socket or serial exception is logged, followed by a one-second retry. Brightness changes are applied directly to the matrix driver; page transitions are rendered horizontally or vertically according to the controller's transition field.

## Production Transport

The receiver binds UDP on all local interfaces but production packets arrive on USB Ethernet at `192.168.10.2:8765`. Binding `0.0.0.0` does not mean Wi-Fi fallback is configured; routing on the Pi 5 still targets the fixed USB address.

See [Zero 2 W Dashboard](../../operations/zero-2w-dashboard.md) for permanent link installation and recovery.
