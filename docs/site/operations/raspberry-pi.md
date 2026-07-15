# Raspberry Pi 5

The Raspberry Pi 5 owns camera capture, controller input, sensor reads, final safety arbitration, actuator output, logging, and dashboard telemetry.

## Current Interfaces

| Subsystem | Interface |
|---|---|
| Steering | PCA9685 at I2C `0x40`, channel `0`, 50 Hz |
| Motors | Yahboom AT8236 on configured GPIO PWM outputs |
| Hall sensor | GPIO `24` |
| Camera | Camera Module 3 Wide through Picamera2, `1280x720` BGR capture |
| LiDAR | LD19 through CP2102 USB serial, normally `/dev/ttyUSB0`, 230400 baud |
| GPS | BN880 serial data on `/dev/ttyAMA0`, 9600 baud |
| Dashboard | UDP `192.168.10.2:8765` over the dedicated `usb0` link |
| Jetson Orin Nano | Direct Ethernet to `10.42.0.2:8770` |

## Start

Put the car on a stand or otherwise prevent unexpected motion, connect the controller, then run:

```bash
cd ~/rc_car_code/code/controller/current
car
```

`rc_car.py` intentionally has no `--model` flag. Select models on the dashboard, or set `RC_CAR_STEERING_MODEL` before startup. The default is v3.4.

## Verify

Check the startup log for joystick, PCA9685/GPIO, LiDAR, GPS, camera, Jetson Orin Nano, and dashboard status. A missing optional sensor may not stop manual control, but it changes what can be tested safely; record the degraded state rather than treating the run as fully representative.

The Raspberry Pi 5 keeps local manual control responsive while camera transmission and Jetson Orin Nano inference run asynchronously. It accepts only fresh results for the currently selected model.
