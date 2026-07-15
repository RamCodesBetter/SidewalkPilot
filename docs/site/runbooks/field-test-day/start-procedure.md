# Start Procedure

Use this sequence for a controlled field test.

## Before Motion

1. Inspect steering linkage, wheels, wiring, batteries, and emergency-stop access.
2. Power the computers and confirm the Xbox controller is connected.
3. Confirm the Raspberry Pi 5–Zero 2 W USB network and Raspberry Pi 5–Jetson Orin Nano Ethernet link.
4. Keep the car lifted or physically restrained during startup checks.

## Start Services

On the Zero 2 W, confirm `sidewalkpilot-z2w-dashboard.service` is running. On Jetson Orin Nano, confirm the inference service is running. Then start the Raspberry Pi 5 controller:

```bash
cd ~/rc_car_code/code/controller/current
car
```

Do not append `--model`; the entrypoint does not accept that option. Select the intended model from the dashboard and verify the reported version before enabling autonomy.

## Required Checks

- Joystick input is immediate and the control map prints.
- GPIO/PCA9685 initialization succeeds.
- LiDAR connects on the expected USB serial device.
- Camera capture starts.
- Jetson Orin Nano responds with the selected model and a GPU provider.
- Dashboard values update instead of showing `NO LINK` or stale data.
- Steering and throttle respond correctly while the wheels are unloaded.

Abort the autonomous test if the selected model, safety sensor, controller, or required link is unavailable. Record every degraded subsystem in the run notes.
