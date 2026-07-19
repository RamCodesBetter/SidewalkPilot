# PCB GPIO Mapping

This page documents the GPIO / pin assignments the custom PCB has to break out. Important caveat: the pinout drawn on the **current designed revision is OUTDATED**. I re-pinned parts of the runtime after the board was laid out, so the numbers below are the ones the software actually uses today (from `config.py`), and the *next* PCB revision will be re-drawn to match them. Until then, treat `config.py` as the source of truth and the current board layout as stale.

## How it works

The PCB does not invent a pinout; it hard-wires the pinout the runtime already expects. Every trace on the board must land on the exact Raspberry Pi 5 pin that `code/controller/current/rc_car_app/config.py` and the serial device modules reference, otherwise the software would need to change. The mapping below is read directly from the runtime source, not guessed.

### Motor driver (Yahboom AT8236 H-bridge, GPIO)

Read from `config.py`:

| Signal | GPIO (BCM) | Constant |
|---|---|---|
| Right motor forward | 19 | `MOTOR_RIGHT_FWD_PIN` |
| Right motor backward | 20 | `MOTOR_RIGHT_BWD_PIN` |
| Left motor forward | 25 | `MOTOR_LEFT_FWD_PIN` |
| Left motor backward | 13 | `MOTOR_LEFT_BWD_PIN` |

### Steering servo (PCA9685, I2C)

The steering servo is **not** on a bare GPIO; it connects through the PCA9685 Servo Controller, so the board only needs to break out the I2C bus to the controller:

| Item | Value | Constant |
|---|---|---|
| Bus | I2C (SDA/SCL) | `USE_PCA9685_SERVO` |
| Address | `0x40` | `PCA9685_I2C_ADDRESS` |
| Servo channel | 0 | `PCA9685_SERVO_CHANNEL` |
| PWM frequency | 50 Hz | `PCA9685_FREQUENCY_HZ` |

### Hall sensor (speed)

| Signal | GPIO (BCM) | Constant |
|---|---|---|
| Hall pulse input | 24 | `HALL_SENSOR_GPIO_PIN` |

### Serial devices (UART / USB)

These are read from the device modules, not `config.py`:

| Device | Port | Baud | Source |
|---|---|---|---|
| LiDAR (FHL-LD19 via CP2102) | `/dev/serial/by-id/...CP2102...` (USB) | 230400 | `lidar.py` (`DEFAULT_LIDAR_SERIAL_PORT`, `BAUD_RATE`) |
| GPS (BN880 + HMC5883L compass) | `/dev/ttyAMA0` | 9600 | `navigation.py` (`GPS_PORT`, `GPS_BAUD`) |
| IMU (Seeed XIAO MG24, 6-axis) | `/dev/ttyAMA3` (GPIO8/9) | 115200 | live yaw-rate reader/controller |

Note: the LiDAR currently enumerates as a **USB** CP2102 device (`/dev/ttyUSB0`), not a GPIO UART. An earlier build ran it on GPIO UART `/dev/ttyAMA2`; the board's LiDAR footprint should reflect whichever path is chosen at fab time.

## Why it matters

If the copper lands on the wrong pin, the fix is not a code edit — it is a new board. That is the whole reason this mapping is pulled straight from the runtime constants and why I refuse to fabricate against the stale layout. Getting the map exactly right on paper first is cheaper than a respin.

## Status

- The numbers above match the current software configuration. Physical continuity, voltage, and connector placement must still be checked on the actual harness.
- The **current PCB layout does not match them** — it is outdated (planned re-draw).
- The updated GPIO map for the next revision is **planned / not-yet-drawn**.

## Related pages

- `hardware/wiring/pin-map.md`
- `runtime-code/config/gpio-pins.md`
- `hardware/pcb/revisions.md`
