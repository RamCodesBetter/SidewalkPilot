# PCB Schematic

The schematic captures which sensors and actuators connect to which Pi 5 pins and buses on the custom breakout board. It is the electrical intent behind the [GPIO map](gpio-mapping.md): the same subsystems that are currently jumper-wired on a breadboard, drawn as fixed nets. Like the rest of the PCB work it is **design-only** — the board is not fabricated — and the pin nets shown on the current designed revision are **outdated**, so the finalized schematic will be re-drawn against the runtime pinout before fab.

## How it works

The schematic groups the car into four electrical blocks, each hanging off the Pi 5 header:

- **Power / ground rails.** Shared 5V and ground distributed to the servo driver, motor driver, and sensors, instead of daisy-chaining through breadboard rails. The 3S LiPo drives the motor side; logic power comes from the Pi.
- **I2C bus.** SDA/SCL run to the PCA9685 servo driver at address `0x40`, which drives the steering servo on channel 0 at 50 Hz. Same bus can carry the HMC5883L compass block if broken out.
- **Motor-driver GPIO block.** Four direction/PWM nets to the Yahboom AT8236 H-bridge: right forward (GPIO 19), right backward (GPIO 20), left forward (GPIO 25), left backward (GPIO 13). The AT8236 output stage connects to the two drive motors.
- **Signal / serial block.** The hall sensor pulse input (GPIO 24), plus serial connectors for the LiDAR (CP2102 USB, 230400 baud), GPS (`/dev/ttyAMA0`, 9600 baud), and IMU (XIAO MG24 on `/dev/ttyAMA3`).

Each block is a net on the schematic that lands on the exact Pi pin the runtime already references, so swapping the breadboard for the board requires no code change. Full per-signal detail lives in the [GPIO Mapping](gpio-mapping.md) page; the schematic is where those signals become connected nets with power and ground.

## Why it matters

Drawing the schematic first is what turns a pile of jumper wires into something reproducible and reviewable. On a schematic I can see, before spending money on copper, whether a bus is overloaded, whether grounds are common, and whether the motor-driver power is isolated from Pi logic power — things that are invisible in a breadboard rat's nest and that show up as "random" faults in the field. It is also the artifact I can hand to someone reviewing the build for safety.

The cost is that a schematic freezes decisions. Because my runtime pinout moved after the first draw, the current schematic's nets are stale, and I would rather correct the drawing than fabricate a wrong board.

## Status

- **Schematic state:** drafted alongside the outdated board layout; nets do **not** all match the current runtime pins (planned re-draw).
- **Fab state:** not ordered, not fabricated (planned).
- **Authoritative wiring** until the board exists: `config.py` plus the [Pin Map](../wiring/pin-map.md) and [Signal Wiring](../wiring/signal-wiring.md) pages.

## Related pages

- `hardware/pcb/overview.md`
- `hardware/wiring/signal-wiring.md`
- `hardware/pcb/gpio-mapping.md`
