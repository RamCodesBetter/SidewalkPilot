# Signal Wiring

This page documents the control and data signals on the Raspberry Pi 5: the GPIO, I2C, and serial lines that carry commands to steering/motors and readings back from sensors. It is the counterpart to the power wiring page: here the concern is logic-level signals and pin assignments, not current delivery. For the full one-line-per-device list see the pin map.

## Signal lines

| Signal | Direction | Transport | Pin / port |
|---|---|---|---|
| Steering command | Raspberry Pi 5 → PCA9685 → servo | I2C bus 1 | address `0x40`, channel `0` |
| Motor drive (right fwd/bwd) | Raspberry Pi 5 → AT8236 | GPIO PWM @ 1 kHz | `GPIO 19` / `GPIO 20` |
| Motor drive (left fwd/bwd) | Raspberry Pi 5 → AT8236 | GPIO PWM @ 1 kHz | `GPIO 25` / `GPIO 13` |
| Wheel speed | hall sensor → Raspberry Pi 5 | GPIO digital in (pull-up) | `GPIO 24` |
| GPS fixes | BN880 → Raspberry Pi 5 | UART @ 9600 | `/dev/ttyAMA0` |
| IMU yaw rate | XIAO MG24 -> Raspberry Pi 5 | UART @ 115200, GPIO8/9 | `/dev/ttyAMA3` |
| LiDAR scan | FHL-LD19 → Raspberry Pi 5 | USB serial (CP2102) @ 230400 | `/dev/ttyUSB0` |
| Dashboard telemetry | Raspberry Pi 5 → Zero 2 W | USB Ethernet, UDP | `192.168.10.2:8765` |

## How it works

The Raspberry Pi 5 issues steering/motor signals and reads sensor signals over four transports. Steering goes out as an I2C command to the PCA9685 (logical `0=left`, `90=center`, `180=right`, mapped to a pulse in `hardware.py`). The four motor half-bridges are driven as software PWM at 1 kHz through `gpiozero.PWMOutputDevice` on GPIO 19/20 (right) and 25/13 (left); direction and speed are set by which pin gets the duty cycle. The hall sensor returns wheel pulses on GPIO 24 as a pull-up digital input, edge-counted for speed. GPS fixes arrive as NMEA on the UART, the LiDAR scan arrives as a 230400-baud binary stream over USB, and the Raspberry Pi 5 sends dashboard telemetry outward as UDP over the USB Ethernet link. The BN880 magnetometer is bench-tested over I2C but is not consumed by the live route manager.

All pin numbers are BCM and come straight from `rc_car_app/config.py`; the I2C and serial endpoints come from `config.py`, `lidar.py`, and `navigation.py`. The configured motor GPIO does not intentionally overlap the sensor UART/I2C assignments. A physical miswire can still connect unrelated lines, so the pin map must be checked before power is applied.

## Why this choice

Signal wiring is where a mistake is most likely to look like a software bug: a motor line miswired, a pull-up missing on the hall sensor, or a UART on the wrong port all present as "the code is broken." Documenting every signal line with its exact pin and its source constant makes the physical layer auditable, so debugging can start by proving the signal path (scope/print the value) instead of guessing at the model or control logic. It also keeps logic-level concerns separate from the power domains, which are handled on the power wiring page.

## Test

```bash
# Raspberry Pi 5 — I2C steering device present
i2cdetect -y 1                    # expect 0x40

# Raspberry Pi 5 — motor GPIO and hall input bench checks:
#   code/test_files/steering/servo_step_controller.py
#   code/test_files/sensors/hall_sensor_test.py
```

Failure symptoms narrow the search but do not prove one cause. For example, `0x40` with no servo motion leaves servo power, PWM calibration, linkage, and the servo itself to check; a motor with correct GPIO activity still leaves the driver, rail, wiring, and motor; a zero hall count leaves the sensor, pull-up, gap, wiring, and software configuration. Trace each signal end to end before assigning a cause.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
