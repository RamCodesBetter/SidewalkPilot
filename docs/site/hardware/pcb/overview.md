# Custom PCB Overview

The custom Raspberry Pi 5 breakout PCB is my planned replacement for the breadboard-and-jumper wiring that currently connects every sensor and actuator to the Raspberry Pi 5. It is **DESIGNED ONLY** right now: the board has been laid out but it has **not been ordered and not been fabricated**, so nothing on the car runs on it yet. On top of that, the current layout is already outdated. I moved several pins around in the runtime after the board was drawn, so the design's GPIO map no longer matches `config.py`. A new revision with the corrected GPIO is planned before I ever send anything to a fab house.

## How it works

Today the whole car is wired point-to-point: the Xbox-controller-driven Raspberry Pi 5 fans out to a PCA9685 servo driver over I2C, to a Yahboom AT8236 H-bridge over four GPIO motor pins, to a hall sensor, and to serial devices (LiDAR, GPS, IMU) over UART / USB. Every one of those connections is a jumper wire on a breadboard.

The PCB collapses that harness into one board that seats on the Raspberry Pi 5 header. Instead of individual jumpers, each subsystem gets a dedicated footprint and a fixed trace back to the correct Raspberry Pi 5 pin:

- The **PCA9685** servo driver breaks out on the I2C bus (`0x40`, channel 0).
- The **AT8236 motor driver** takes the four motor GPIOs (right fwd/bwd, left fwd/bwd).
- The **hall sensor**, **LiDAR**, **GPS/compass**, and **IMU** each get a labeled connector.
- Power and ground rails are shared instead of daisy-chained through the breadboard.

The intent is that the pin assignments on the board are the *same* logical assignments the runtime already uses, so no code changes are needed when the harness is swapped for the board.

## Why it matters

Breadboard and jumper wiring is a known reliability risk on a moving platform. A loose connection can resemble a software failure: a sensor drops, the servo twitches, or a motor stops. A correctly designed and fabricated board could reduce movable jumper connections and make the harness easier to inspect, but connectors, solder joints, power integrity, and an incorrect pin map would remain failure modes. The current unbuilt PCB does not improve the car's present safety or reliability.

The trade-off is commitment: a PCB freezes the pinout. That is exactly why the board is still design-only. My runtime pin assignments are still moving (I re-pinned after the first layout), so committing copper now would just bake in a stale map. I would rather fabricate once, against a finalized GPIO map, than respin a board.

## Current status

- **Design state:** laid out, DESIGNED ONLY.
- **Fab state:** not ordered, not fabricated, not on the car (planned).
- **GPIO map:** the drawn revision is **outdated** and does not match the current `config.py` pins; a corrected revision is planned before fabrication (planned / not-yet-done).
- **Source of truth for pins:** `code/controller/current/rc_car_app/config.py` — not the board — until a matching revision is drawn.

Until the board exists, the [Pin Map](../wiring/pin-map.md) and the runtime config remain the authoritative wiring reference.

## Related pages

- `hardware/wiring/pin-map.md`
- `hardware/build-overview.md`
- `hardware/pcb/gpio-mapping.md`
