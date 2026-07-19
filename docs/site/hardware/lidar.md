# LiDAR

The LiDAR is a Youyeetoo FHL-LD19, a spinning 360-degree scanner used for the car's
safety layer: obstacle detection and automatic emergency braking (AEB). It is the
sensor that can cap forward throttle or stop the car when something enters the center
safety corridor. It does not override steering.

## Parts (Amazon)

- [Youyeetoo FHL-LD19 360 12M 30K Lux LiDAR](https://www.amazon.com/youyeetoo-D300-Resistant-Raspberry-Tutorial/dp/B0B1QCV4XR/ref=sr_1_1_sspa?crid=3PEW81EWE77M7&dib=eyJ2IjoiMSJ9.xRO1HLsQgyMGosjt-JLHK9NqlXmGjamO5bCBS0lTVvkKceKizVjNtRJ3cI42GtjPJxSbJA4rzaZDZM4Z43hq8VfxQSR5uKnsO5NMGsJTmzSih8dLVOIXbmJpmVdPm1Buyj2lSyYpqdF4PS0G0R8_dBrWu-5AYZNAj_wmSIGBrgeO_OGNC_uhA6_08faa9d5yj2dfggXqZCbPKTx8zgCmSA8voegwEa_e2ndl5pjxQNA.L1wKA35gI2jbHtEu054aB8yYEMsVkcJbPMc74HFGLcM&dib_tag=se&keywords=youyeetoo+lidar&qid=1779578773&sprefix=youyeetoo+lidar%2Caps%2C182&sr=8-1-spons&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&psc=1) — $71.90

## How It Works

- `lidar.py` reads the scanner over a serial port at `230400` baud. The current wiring is
  **USB via a CP2102 UART-to-USB Adapter** (`/dev/ttyUSB0`); an earlier setup ran it on the
  Raspberry Pi 5 GPIO UART at `/dev/ttyAMA2`. The port is auto-resolved, preferring the CP2102
  `by-id` path and falling back to `ttyUSB*`/`ttyACM*`.
- The parser decodes the LD19 packet format (47-byte packets, 12 measurement points each)
  into angle/distance/confidence points, with a max usable range of ~12 m.
- `lidar_avoidance.py` measures the nearest valid point in a center corridor. With AEB
  enabled, it allows full throttle at 1.65 m, reduces the reference target to 60% by
  1.25 m, holds to 1.05 m, then requests a hard stop. Left and right points are display
  telemetry and never produce steering.
- AEB is toggled by the driver and shown on the dashboard as `AEB:ON` / `AEB:OFF`. The
  reader reconnects on its own if the LiDAR drops, so a disconnect does not block driving
  or photo collection.

## Packet and Reconnect Details

The parser searches its byte buffer for header `0x54` and marker `0x2C`, then decodes the
little-endian start/end angles and twelve distance/confidence triples. Angles are interpolated
across the packet, including wraparound at 360 degrees. More than 500 accumulated points are
published as the latest full scan. A scan older than one second is returned as empty; that
prevents use of old points but does not prove the corridor is clear.

Serial ownership stays in a daemon thread. On a fault, the reader closes the device, clears
its buffer, and re-resolves the port. Retry delay starts at 1.5 seconds, increases by 1.5x to
a 10-second ceiling, and resets after a successful connection. Repeated status messages are
limited to once every 15 seconds. This recovery keeps serial waits outside the driving loop,
but AEB coverage is absent while valid scans are missing.

## Why This Choice

- A 360-degree scanner gives cheap, all-around distance sensing that the camera model cannot
  provide, which is what makes an independent safety/AEB layer possible.
- Keeping close-range slowdown and braking in LiDAR means those decisions use explicit
  distance thresholds rather than a learned output. Their real stopping performance still
  has to be measured under the intended payload and surface conditions.

## Verify Before a Run

- Bench test: `code/test_files/lidar/lidar_viewer.py` visualizes the live scan.
- Failure symptoms: if the dashboard shows `NONE`/`000`, stop the car service and check the
  raw port (`timeout 5s cat /dev/ttyUSB0 | hexdump -C`), confirm the motor is spinning, and
  confirm baud `230400`. Stop the controller before raw serial tests so two readers do not
  fight over the port.

## Related Pages

- [Hardware Build Overview](build-overview.md)
- [Bench Tests](../testing/bench-tests/overview.md)
- [Hardware Class](../runtime-code/hardware/hardware-class.md)
