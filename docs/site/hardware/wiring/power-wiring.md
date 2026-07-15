# Power Wiring

This page documents how power is distributed on the car: the separate power domains and which battery or bank feeds each subsystem. Power is kept deliberately separate from the signal wiring so that a high-current motor draw cannot brown out the compute or logic rails.

## Power domains

| Domain | Source | Feeds |
|---|---|---|
| Motor / drive | OVONIC 3S LiPo (11.1 V, 5200 mAh) | Yahboom AT8236 H-bridge → the four drive-motor half-bridges |
| Compute (Pi 5 + Zero) | INIU 10000 mAh 45 W power bank | Raspberry Pi 5 and Zero 2 W (Zero also has a data USB link to the Pi) |
| AI compute (Jon) | INIU 27000 mAh 140 W power bank via USB-C→barrel trigger cable | NVIDIA Jetson Orin Nano |
| LED display | OVONIC 2S LiPo (7.4 V, 5200 mAh) -> DROK DC buck converter, fused (ATC/ATO 10 A) | Waveshare 64x32 RGB LED matrix |

## How it works

The drive motors use a dedicated 3S LiPo through the AT8236 driver rather than drawing their load from a compute supply. The Pi 5 and Zero use a USB power bank; the Zero is also connected to the Pi by the dashboard's USB data link. Jon has a separate bank, and the LED display uses a 2S LiPo through a DROK buck converter and 10 A fuse. These separate supply paths reduce shared-load voltage sag, but grounds, cables, converters, and electromagnetic coupling still need measurement.

The steering servo is powered from the PCA9685's servo rail, not from a Pi GPIO pin. That wiring avoids sourcing servo current from GPIO, but only an under-load voltage measurement can establish how much servo current still couples into another rail. The power design includes a 10000 uF electrolytic capacitor for bulk buffering. Exact listed parts, capacities, and prices are in the hardware BOM table.

## Why this choice

Separating motor, compute, AI-compute, and display supplies is intended to reduce one load disturbing another. A previous Zero USB enumeration failure occurred during an unstable link/power setup; the later working arrangement used a stable external 5 V feed and USB for data. That observation does not isolate one electrical root cause or prove that resets are impossible. Each supply path still requires fuse, voltage, connector, and under-load checks.

## Test

```bash
# Pi 5 — check for undervoltage events on the compute rail
vcgencmd get_throttled            # 0x0 = no reported throttle/undervoltage flags

# Confirm the LED-display buck output before connecting the panel (multimeter):
#   expect ~5 V on the buck output feeding the matrix
```

Failure symptoms such as USB `-110` / `-62` errors can come from power, cable, connector, port, or gadget-enumeration faults. Check those possibilities rather than treating one symptom as proof of a specific cause. Motors twitching or the Pi rebooting under throttle warrants checking supply voltage and grounding under load.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
