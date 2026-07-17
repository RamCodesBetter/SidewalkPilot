# Troubleshooting

The consolidated failure playbook for SidewalkPilot: the dashboard link, the controller, sensors, and the USB gadget. Each entry names the machine, the check, what it can break, and how to confirm the fix. The guiding rule is prove, do not assume — grep the value across every layer and observe the wire before forming a theory.

## Dashboard shows `NO LINK`

`NO LINK` means the Zero 2 W receiver is alive but has not received a packet recently. Work outward from the sender:

1. **Raspberry Pi 5 — controller running?** Confirm the controller process is up and printed its UDP transport line.
2. **Zero 2 W — receiver listening?** `ss -lunp | grep 8765` should show exactly one listener.
3. **Both — USB up?** `ip -br addr show usb0` (Raspberry Pi 5 `.1`, Zero 2 W `.2`) and `cat /sys/class/net/usb0/carrier`.
4. **Ping both ways**: `ping -c 3 192.168.10.2` from the Raspberry Pi 5, `ping -c 3 192.168.10.1` from the Zero 2 W.
5. **Carrier `1` but ping fails** — the classic ARP/USB stall. Restart the USB keeper, or run the USB hard-reset sequence on both devices.

## Controller exits immediately

- Almost always "No joystick detected." Connect the Xbox controller before starting the controller.
- If it drops to "Running in simulation mode," `hardware.py` caught a GPIO/I2C init error and swapped in dummy devices — check wiring, I2C enablement, and bus contention.

## LiDAR reads none / zero

- Confirm the LiDAR is present: the FHL-LD19 is currently on USB `/dev/ttyUSB0` via a CP2102 UART-to-USB Adapter at `230400` baud (it was previously GPIO UART `/dev/ttyAMA2`).
- Confirm the LiDAR motor is spinning.
- Stop any second reader before a raw serial test — two readers on one port is a common cause.

## GPS permission denied

- The error looks like permission denied on `/dev/ttyAMA0`. Confirm the serial console is freed on that UART and check group membership / port ownership.
- Do not confuse the GPS port (`/dev/ttyAMA0`, `9600`) with the LiDAR port.

## USB enumeration errors on the Zero 2 W

- `-110`/`-62` or "device descriptor read" errors establish an enumeration failure; they do not identify power, cable, port, host, or device as the cause. Reproduce with the known working power arrangement, data cable, and host port before replacing hardware.
- If the Zero 2 W is reachable over Wi-Fi but not USB, fix the dedicated USB path before continuing dashboard debugging.

## Zero 2 W boots then hangs headless

- A missing `/etc/machine-id` runs the systemd first-boot wizard, which stalls a headless boot. Regenerate the machine-id.

## Why this discipline

Repeatable, machine-labelled checks reduce accidental branch leaks, sync damage, and deployment confusion, and they stop the real failure mode: asserting a cause from the armchair. When a value is wrong on the wire, grep that value across **every** file first (config, runtime, serializer, renderer), read the whole file rather than a single grepped line, check which process is actually running (`pgrep -af`, `/proc/PID/cwd`), and instrument the data path end-to-end before declaring it fixed. A remembered case cost ~2.5 hours because a hardcoded literal in the serializer was assumed away instead of grepped.

## Failure and recovery quick table

| Symptom | Machine | First decisive check |
|---|---|---|
| `NO LINK` | Zero 2 W | `ss -lunp \| grep 8765`, then ping both ways |
| Carrier 1, ping fails | Both | Restart USB keeper / hard reset |
| Controller exits | Raspberry Pi 5 | Look for "No joystick detected" |
| "Simulation mode" | Raspberry Pi 5 | GPIO/I2C wiring + bus contention |
| LiDAR none/zero | Raspberry Pi 5 | Motor spinning, single reader, port/baud |
| GPS denied | Raspberry Pi 5 | `/dev/ttyAMA0` console freed + group |
| USB `-110`/`-62` | Zero 2 W | Known working power/cable/port, then `dmesg` and `lsusb` |

## Evidence to attach

- Command output for the failing check
- `ss`/`ip`/`ping` results
- Relevant startup lines from the affected process

## Related pages

- `operations/mac-pc-sync.md`
- `runbooks/sync-day/mac-to-pc.md`
- `publishing/mkdocs-site.md`
