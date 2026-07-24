# Wiring and Pin Map

A consolidated reference for power domains, primary sensors, steering/motor hardware, and inter-computer links.

## How It Works

The Raspberry Pi 5 is the hardware I/O and safety controller. Its sensors, Servo Controller, and Motor Controller connect through one of four transport types: raw GPIO lines (motors and Hall-effect wheel-speed sensor), I2C (PCA9685 Servo Controller), UART (GPS and IMU), or USB (LiDAR through its current CP2102 UART-to-USB Adapter and dashboard USB Ethernet). The exact pin and port assignments live in `rc_car_app/config.py`, `rc_car_app/lidar.py`, and `rc_car_app/navigation.py`, so the table below is copied directly from those source files rather than from memory.

## Master Pin and Port Table

| Subsystem | Part | Connection | Pin, address, or port | Source constant |
|---|---|---|---|---|
| Steering servo | PCA9685 Servo Controller -> chassis servo | I2C bus 1 | address `0x40`, servo channel `0`, 50 Hz | `PCA9685_I2C_ADDRESS`, `PCA9685_SERVO_CHANNEL`, `PCA9685_FREQUENCY_HZ` |
| Right drive control (forward) | AT8236 Motor Controller -> JGB37-520 DC motors (12 V, 550 RPM) | GPIO (BCM) | `GPIO 19` | `MOTOR_RIGHT_FWD_PIN` |
| Right drive control (backward) | AT8236 Motor Controller -> JGB37-520 DC motors (12 V, 550 RPM) | GPIO (BCM) | `GPIO 20` | `MOTOR_RIGHT_BWD_PIN` |
| Left drive control (forward) | AT8236 Motor Controller -> JGB37-520 DC motors (12 V, 550 RPM) | GPIO (BCM) | `GPIO 25` | `MOTOR_LEFT_FWD_PIN` |
| Left drive control (backward) | AT8236 Motor Controller -> JGB37-520 DC motors (12 V, 550 RPM) | GPIO (BCM) | `GPIO 13` | `MOTOR_LEFT_BWD_PIN` |
| Hall-effect wheel-speed sensor | Wheel-speed input | GPIO (BCM), pull-up | `GPIO 24` | `HALL_SENSOR_GPIO_PIN` |
| GPS | BN880 GPS receiver | UART | `/dev/ttyAMA0` @ `9600`; default 1 Hz (1,000 ms) fixes | `GPS_PORT`, `GPS_BAUD` (`navigation.py`) |
| Compass (bench only) | BN880 HMC5883L-compatible magnetometer | I2C | Detected by `bn880_test.py`; not consumed by live navigation | bench utility only |
| IMU | Seeed XIAO MG24 Sense (6-axis) | UART, Raspberry Pi 5 GPIO8/9 | `/dev/ttyAMA3` @ `115200` | `STEERING_YAW_PID_PORT`, `STEERING_YAW_PID_BAUD` |
| LiDAR (current) | Youyeetoo FHL-LD19 via CP2102 UART-to-USB Adapter | USB serial | `/dev/ttyUSB0` @ `230400` (auto-resolved); typical 10 Hz (100 ms) scans and 4,500 points/s | `lidar.py` `resolve_lidar_serial_port` |
| LiDAR (former) | Youyeetoo FHL-LD19 | GPIO UART | `/dev/ttyAMA2` @ `230400` | earlier config, now superseded |
| Dashboard link | Zero 2 W over USB Ethernet gadget | USB (usb0) | Raspberry Pi 5 `192.168.10.1`, Zero 2 W `192.168.10.2`, UDP `8765` | `HUB75_DASHBOARD_*` (`config.py`) |

Notes:

- Motor pins are driven as software PWM through `gpiozero.PWMOutputDevice` at 1 kHz (`hardware.py`).
- The IMU reader and yaw controller are implemented. The default `straight` mode only corrects near center and falls back to open loop if IMU data is unavailable.
- LiDAR now resolves its port automatically at startup, preferring the CP2102 UART-to-USB Adapter's `/dev/serial/by-id/*` symlink and falling back to `/dev/ttyUSB*`; the older GPIO-UART `/dev/ttyAMA2` path is documented for history.

## Why It Matters

A consolidated pin map is a safety and debugging tool. Because motor pins move real wheels, an accidental mix-up between a motor line and a sensor line is not harmless. This table was checked against `config.py`, `lidar.py`, and `navigation.py`, but it is still maintained documentation and must be re-audited when wiring or constants change.

## Power Domains

| Domain | Source | Main load |
|---|---|---|
| Drive | OVONIC 3S 11.1 V, 5200 mAh LiPo | AT8236 Motor Controller and JGB37-520 DC motors (12 V, 550 RPM) |
| Jetson Orin Nano | INIU 27,000 mAh, 140 W bank | AI Model Manager |
| Raspberry Pi 5 and Zero 2 W | INIU 10,000 mAh, 45 W bank | Control and dashboard computers |
| HUB75 display | OVONIC 2S 7.4 V, 5200 mAh LiPo through fused buck converter | LED matrix |

The steering servo uses the PCA9685 Servo Controller's servo rail rather than a Raspberry Pi 5 GPIO pin. Separate supplies reduce shared voltage sag but do not eliminate grounding, converter, connector, or electromagnetic-coupling faults. Voltage must be checked under load.

## Bus Checks

```bash
i2cdetect -y 1
ip -br addr show usb0
ss -lunp | grep 8765
```

Expect the PCA9685 Servo Controller at `0x40`, the fixed USB-network addresses on the two dashboard computers, and the receiver listening on UDP 8765. UART device permissions and stable `/dev/serial/by-id` naming should be checked before field use.

## Related Pages

- [Runtime Configuration](../../runtime-code/config/servo-settings.md)
- [Power](../power.md)
- [PCB Development](../pcb/overview.md)
