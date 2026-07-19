# Troubleshooting

The consolidated failure playbook for SidewalkPilot: the dashboard link, the controller, sensors, and the USB gadget. Each entry names the machine, the check, what it can break, and how to confirm the fix. The guiding rule is prove, do not assume — grep the value across every layer and observe the wire before forming a theory.

## Dashboard Shows `NO LINK`

`NO LINK` means the Zero 2 W receiver is alive but has not received a packet recently. Work outward from the sender:

1. **Raspberry Pi 5 — controller running?** Confirm the controller process is up and printed its UDP transport line.
2. **Zero 2 W — receiver listening?** `ss -lunp | grep 8765` should show exactly one listener.
3. **Both — USB up?** `ip -br addr show usb0` (Raspberry Pi 5 `.1`, Zero 2 W `.2`) and `cat /sys/class/net/usb0/carrier`.
4. **Ping both ways**: `ping -c 3 192.168.10.2` from the Raspberry Pi 5, `ping -c 3 192.168.10.1` from the Zero 2 W.
5. **Carrier `1` but ping fails** — the classic ARP/USB stall. Restart the USB keeper, or run the USB hard-reset sequence on both devices.

## Controller Exits Immediately

- If the log says "No joystick detected," connect the Xbox controller before starting the controller.
- If it drops to "Running in simulation mode," `hardware.py` caught a GPIO/I2C init error and swapped in dummy devices — check wiring, I2C enablement, and bus contention.

## LiDAR Reads None or Zero

- Confirm the LiDAR is present: the FHL-LD19 is currently on USB `/dev/ttyUSB0` via a CP2102 UART-to-USB Adapter at `230400` baud (it was previously GPIO UART `/dev/ttyAMA2`).
- Confirm the LiDAR motor is spinning.
- Stop any second reader before a raw serial test — two readers on one port is a common cause.

## GPS Permission Denied

- The error looks like permission denied on `/dev/ttyAMA0`. Confirm the serial console is freed on that UART and check group membership / port ownership.
- Do not confuse the GPS port (`/dev/ttyAMA0`, `9600`) with the LiDAR port.

## USB Enumeration Errors on the Zero 2 W

- `-110`/`-62` or "device descriptor read" errors establish an enumeration failure; they do not identify power, cable, port, host, or device as the cause. Reproduce with the known working power arrangement, data cable, and host port before replacing hardware.
- If the Zero 2 W is not reachable over the dedicated USB link, repair that link before continuing dashboard debugging; the current dashboard has no Wi-Fi fallback.

## Zero 2 W Boots Then Hangs Headless

- A missing `/etc/machine-id` runs the systemd first-boot wizard, which stalls a headless boot. Regenerate the machine-id.

## Why This Discipline

Repeatable, machine-labeled checks reduce accidental branch leaks, sync damage, and deployment confusion. They also prevent a common failure: asserting a cause before tracing the data. When a value is wrong on the wire, search for that value across **every** file first (configuration, runtime, serializer, and renderer), read each complete file rather than one matching line, check which process is actually running (`pgrep -af`, `/proc/PID/cwd`), and instrument the complete data path before declaring the issue fixed.

## Failure and Recovery Quick Table

| Symptom | Machine | First decisive check |
|---|---|---|
| `NO LINK` | Zero 2 W | `ss -lunp \| grep 8765`, then ping both ways |
| Carrier 1, ping fails | Both | Restart USB keeper / hard reset |
| Controller exits | Raspberry Pi 5 | Look for "No joystick detected" |
| "Simulation mode" | Raspberry Pi 5 | GPIO/I2C wiring + bus contention |
| LiDAR none/zero | Raspberry Pi 5 | Motor spinning, single reader, port/baud |
| GPS denied | Raspberry Pi 5 | `/dev/ttyAMA0` console freed + group |
| USB `-110`/`-62` | Zero 2 W | Known working power/cable/port, then `dmesg` and `lsusb` |

## Evidence to Attach

- Command output for the failing check
- `ss`/`ip`/`ping` results
- Relevant startup lines from the affected process

## Related Pages

- [Mac and PC Sync](mac-pc-sync.md)
- [Mac-to-PC Sync Runbook](../runbooks/sync-day/mac-to-pc.md)
- [MkDocs Site Publishing](../publishing/mkdocs-site.md)
