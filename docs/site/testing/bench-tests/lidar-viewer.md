# LiDAR Viewer

The LiDAR viewer checks whether the FHL-LD19 is streaming plausible distances before an AEB test. It runs `code/test_files/lidar/lidar_viewer.py`, a pygame scope that parses raw LD19 packets and plots returns on a polar grid. Clicking a plotted point displays its reported angle, distance, and confidence.

## How it works

- It opens the LiDAR serial port (`/dev/ttyUSB0` in the viewer, the CP2102 USB adapter) at `230400` baud and reassembles the LD19 protocol: it syncs on the `0x54` header, checks the `0x2C` length byte, and unpacks each `47`-byte packet into `12` measurement points, reading rotation speed, start/end angle, per-point distance (mm) and confidence.
- Each valid point (distance non-zero) is converted from polar to Cartesian and drawn green on an `800x800` window with range rings every `3 m` out to about `12 m`. Clicking near a point shows an info table with its angle, distance in mm and m, confidence, and X/Y.
- This is a raw scope: it does not apply the runtime's forward-window scoring or clearance logic. It is purely for confirming the sensor produces a clean, complete scan.

## Command

Stop the car service first so two readers don't fight over the port, then run on the Pi 5:

```bash
sudo systemctl stop sidewalkpilot-rpi-car.service
python3 code/test_files/lidar/lidar_viewer.py
```

If nothing streams, sanity-check the raw bytes:

```bash
timeout 5s cat /dev/ttyUSB0 | hexdump -C
```

## Pass / warn / fail

- Pass: a full ring of green points appears and updates smoothly; clicked distances match a tape measure to a nearby wall.
- Warn: sparse or partial scans; record confidence and verify the USB device, sensor power, and physical setup.
- Fail: no points and no bytes on the port. Check enumeration, exclusive port ownership, the serial path, and baud (`230400`).

## Why it matters

- LiDAR feeds AEB and can constrain forward motion, so a bench range check is a preflight requirement. It does not characterize stopping distance or detect every possible obstacle.
- Notes: the LiDAR path has moved between GPIO UART (`/dev/ttyAMA2`) and USB (`/dev/ttyUSB0` via a CP2102 adapter) during debugging — check which port is live before concluding the sensor is dead. The runtime tolerates LiDAR dropouts by retrying rather than blocking the driving loop; this viewer is only for confirming the hardware stream.

## Evidence to attach

- A screenshot of a full scan ring
- A clicked-point readout compared against a measured distance
- A note of the port and baud used

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
