# Command Cookbook

Commands are machine-specific. Confirm the shell prompt before running anything that can move the car.

## Start and Inspect

| Machine | Command | Verification |
|---|---|---|
| Raspberry Pi 5 | `car` | Controller initialization completes; dashboard model page shows intended version |
| Zero 2 W | `dash` or its systemd unit | Exactly one UDP listener owns port 8765 |
| Raspberry Pi 5 | `sudo systemctl status sidewalkpilot-rpi-car.service -l --no-pager` | Unit state and current process |
| Zero 2 W | `sudo systemctl status sidewalkpilot-z2w-dashboard.service -l --no-pager` | Unit state and receiver process |
| Either USB endpoint | `ip -br addr show usb0` | Raspberry Pi 5 is `192.168.10.1/24`; Zero 2 W is `192.168.10.2/24` |
| Raspberry Pi 5 | `ping -c 3 192.168.10.2` | USB network reaches the dashboard |
| Zero 2 W | `ping -c 3 192.168.10.1` | Return path reaches the Raspberry Pi 5 |

The live controller has no `--model` flag. Select all Series 1-4 versions on the dashboard model page, or set `RC_CAR_STEERING_MODEL` before startup.

## Logs

```bash
journalctl -u sidewalkpilot-rpi-car.service -n 100 -l --no-pager
journalctl -u sidewalkpilot-z2w-dashboard.service -n 100 -l --no-pager
```

## Source Verification

```bash
python3 -m py_compile code/controller/current/rc_car.py \
  code/controller/current/z2w_dashboard.py \
  code/controller/current/rc_car_app/jetson_inference_server.py
python3 -m compileall code/controller/current/rc_car_app
```

## Failure Notes

- `NO LINK` means the display process has not received fresh telemetry. Check Raspberry Pi 5 process, USB address/carrier, ping, then the Zero 2 W receiver.
- “No joystick detected” means the required manual-control interface was unavailable.
- A source edit does not affect a running process until the owning process restarts.
- Do not start a second dashboard receiver while the systemd receiver already owns UDP 8765.

See [Troubleshooting](troubleshooting.md), [Field Test Day](../runbooks/field-test-day/before-leaving.md), and [Wiring and Pin Map](../hardware/wiring/pin-map.md).
