# Wiring and Pin Map

A consolidated reference for power domains, primary sensors, actuators, and inter-computer links.

## How it works

The Raspberry Pi 5 is the real-time I/O controller. Every actuator and sensor connects to it through one of four transport types: a raw GPIO line (motors, hall sensor), the I2C bus (servo driver via PCA9685), a UART port (GPS, IMU, and the LiDAR when run over GPIO), or USB (LiDAR in its current CP2102 configuration, dashboard USB Ethernet). The exact pin and port assignments live in `rc_car_app/config.py`, `rc_car_app/lidar.py`, and `rc_car_app/navigation.py`, so the table below is copied directly from those source files rather than from memory.

## Master pin / port table

| Subsystem | Part | Connection | Pin / address / port | Source constant |
|---|---|---|---|---|
| Steering servo | PCA9685 16-ch PWM driver → chassis servo | I2C bus 1 | address `0x40`, servo channel `0`, 50 Hz | `PCA9685_I2C_ADDRESS`, `PCA9685_SERVO_CHANNEL`, `PCA9685_FREQUENCY_HZ` |
| Right drive control (forward) | AT8236 H-bridge -> JGB37-520 DC motors (12 V, 550 RPM) | GPIO (BCM) | `GPIO 19` | `MOTOR_RIGHT_FWD_PIN` |
| Right drive control (backward) | AT8236 H-bridge -> JGB37-520 DC motors (12 V, 550 RPM) | GPIO (BCM) | `GPIO 20` | `MOTOR_RIGHT_BWD_PIN` |
| Left drive control (forward) | AT8236 H-bridge -> JGB37-520 DC motors (12 V, 550 RPM) | GPIO (BCM) | `GPIO 25` | `MOTOR_LEFT_FWD_PIN` |
| Left drive control (backward) | AT8236 H-bridge -> JGB37-520 DC motors (12 V, 550 RPM) | GPIO (BCM) | `GPIO 13` | `MOTOR_LEFT_BWD_PIN` |
| Hall / speed sensor | Wheel hall sensor | GPIO (BCM), pull-up | `GPIO 24` | `HALL_SENSOR_GPIO_PIN` |
| GPS | BN880 GPS receiver | UART | `/dev/ttyAMA0` @ `9600` | `GPS_PORT`, `GPS_BAUD` (`navigation.py`) |
| Compass (bench only) | BN880 HMC5883L-compatible magnetometer | I2C | Detected by `bn880_test.py`; not consumed by live navigation | bench utility only |
| IMU | Seeed XIAO MG24 Sense (6-axis) | UART, Raspberry Pi 5 GPIO8/9 | `/dev/ttyAMA3` @ `115200` | `STEERING_YAW_PID_PORT`, `STEERING_YAW_PID_BAUD` |
| LiDAR (current) | Youyeetoo FHL-LD19 via CP2102 adapter | USB serial | `/dev/ttyUSB0` @ `230400` (auto-resolved) | `lidar.py` `resolve_lidar_serial_port` |
| LiDAR (former) | Youyeetoo FHL-LD19 | GPIO UART | `/dev/ttyAMA2` @ `230400` | earlier config, now superseded |
| Dashboard link | Zero 2 W over USB Ethernet gadget | USB (usb0) | Raspberry Pi 5 `192.168.10.1`, Zero 2 W `192.168.10.2`, UDP `8765` | `HUB75_DASHBOARD_*` (`config.py`) |

Notes:

- Motor pins are driven as software PWM through `gpiozero.PWMOutputDevice` at 1 kHz (`hardware.py`).
- The IMU reader and yaw controller are implemented. The default `straight` mode only corrects near center and falls back to open loop if IMU data is unavailable.
- LiDAR now resolves its port automatically at startup, preferring a CP2102 `/dev/serial/by-id/*` symlink and falling back to `/dev/ttyUSB*`; the older GPIO-UART `/dev/ttyAMA2` path is documented for history.

## Why it matters

A consolidated pin map is a safety and debugging tool. Because motor pins move real wheels, an accidental mix-up between a motor line and a sensor line is not harmless. This table was checked against `config.py`, `lidar.py`, and `navigation.py`, but it is still maintained documentation and must be re-audited when wiring or constants change.

## Power Domains

| Domain | Source | Main load |
|---|---|---|
| Drive | OVONIC 3S 11.1 V, 5200 mAh LiPo | AT8236 and JGB37-520 DC motors (12 V, 550 RPM) |
| Jetson Orin Nano | INIU 27,000 mAh, 140 W bank | AI compute |
| Raspberry Pi 5 and Zero 2 W | INIU 10,000 mAh, 45 W bank | Control and dashboard computers |
| HUB75 display | OVONIC 2S 7.4 V, 5200 mAh LiPo through fused buck converter | LED matrix |

The steering servo uses the PCA9685 servo rail rather than a Raspberry Pi 5 GPIO pin. A 10,000 uF bulk capacitor is part of the power design. Separate supplies reduce shared voltage sag but do not eliminate grounding, converter, connector, or electromagnetic-coupling faults. Voltage must be checked under load.

## Bus Checks

```bash
i2cdetect -y 1
ip -br addr show usb0
ss -lunp | grep 8765
```

Expect the PCA9685 at `0x40`, the fixed USB-network addresses on the two dashboard computers, and the receiver listening on UDP 8765. UART device permissions and stable `/dev/serial/by-id` naming should be checked before field use.

## Related pages

- [Runtime Configuration](../../runtime-code/config/servo-settings.md)
- [Power](../power.md)
- [PCB Development](../pcb/overview.md)
