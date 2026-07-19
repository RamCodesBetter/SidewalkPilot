# Custom PCB Overview

The custom Raspberry Pi 5 breakout PCB is my planned replacement for the breadboard-and-jumper wiring that currently connects the sensors, PCA9685 Servo Controller, and AT8236 Motor Controller to the Raspberry Pi 5. It is **DESIGN-ONLY** right now: the board has been laid out but has **not been ordered or fabricated**, so nothing on the car uses it. The current layout is also outdated. I changed several runtime pin assignments after drawing the board, so its GPIO map no longer matches `config.py`. I plan to correct the GPIO map in a new revision before sending the design for fabrication.

## How It Works

Today the Raspberry Pi 5 hardware path is wired point-to-point: it connects to a PCA9685 Servo Controller over I2C, a Yahboom AT8236 Motor Controller over four GPIO motor pins, a Hall-effect wheel-speed sensor, and serial devices over UART or USB. The current GPIO and I2C connections use jumper wires and a breadboard; USB devices use their own cables and adapters.

The PCB collapses that harness into one board that seats on the Raspberry Pi 5 header. Instead of individual jumpers, each subsystem gets a dedicated footprint and a fixed trace back to the correct Raspberry Pi 5 pin:

- The **PCA9685 Servo Controller** breaks out on the I2C bus (`0x40`, channel 0).
- The **AT8236 Motor Controller** takes the four motor GPIOs (right fwd/bwd, left fwd/bwd)
  and controls the JGB37-520 DC motors rated for 12 V and 550 RPM.
- The **Hall-effect wheel-speed sensor**, **LiDAR**, **GPS/compass**, and **IMU** each get a labeled connector.
- Power and ground rails are shared instead of daisy-chained through the breadboard.

The intent is that the pin assignments on the board are the *same* logical assignments the runtime already uses, so no code changes are needed when the harness is swapped for the board.

## Why It Matters

Breadboard and jumper wiring is a known reliability risk on a moving platform. A loose connection can resemble a software failure: a sensor drops, the servo twitches, or a motor stops. A correctly designed and fabricated board could reduce movable jumper connections and make the harness easier to inspect, but connectors, solder joints, power integrity, and an incorrect pin map would remain failure modes. The current unbuilt PCB does not improve the car's present safety or reliability.

The trade-off is commitment: a PCB freezes the pinout. That is why the board remains design-only. The runtime pin assignments changed after the first layout, so fabricating that revision would preserve a stale map. The next revision should use a finalized GPIO map before fabrication.

## Current Status

- **Design state:** laid out, DESIGNED ONLY.
- **Fab state:** not ordered, not fabricated, not on the car (planned).
- **GPIO map:** the drawn revision is **outdated** and does not match the current `config.py` pins; a corrected revision is planned before fabrication (planned / not-yet-done).
- **Source of truth for pins:** `code/controller/current/rc_car_app/config.py` — not the board — until a matching revision is drawn.

Until the board exists, the [Pin Map](../wiring/pin-map.md) and the runtime config remain the authoritative wiring reference.

## Required Electrical Blocks

The next schematic must cover:

- Shared and separated power/ground paths with reviewed voltage levels and current limits;
- I2C to the PCA9685 at `0x40`;
- Four AT8236 Motor Controller direction/PWM lines on BCM 19, 20, 25, and 13;
- Hall input on BCM 24;
- Connectors for GPS, IMU, LiDAR, and the dashboard/network arrangement selected for the final harness.

LiDAR currently uses a CP2102 UART-to-USB Adapter. A prior build used `/dev/ttyAMA2`; Rev B must not preserve that historical choice accidentally.

## Revision Record

| Revision | State | Runtime-pin match | Fabricated |
|---|---|---|---|
| Rev A | Designed draft | No; outdated | No |
| Rev B | Planned | Must match current runtime before release | No |

Before ordering Rev B, the runtime pinout must be frozen, the schematic and layout must be cross-checked against it, connector polarity and voltage must be reviewed, and continuity/power-up tests must be defined. A fabricated board will still require inspection and bench validation before controlling the car.

## Related Pages

- [Wiring and Pin Map](../wiring/pin-map.md)
- [Build Overview](../build-overview.md)
- [Next Steps](../../roadmap/next-steps.md)
