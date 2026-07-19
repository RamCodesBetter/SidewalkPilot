# Environment Setup

This page explains how each SidewalkPilot machine is prepared for its role: the Jetson Orin Nano inference host, Raspberry Pi 5 controller, Zero 2 W dashboard receiver, and Mac and NVIDIA PC workstations. The goal is a repeatable setup that brings a new device online without guessing at paths or ports.

## How It Works

The runtime discovers most of its layout from the repository itself and a small set of optional environment overrides, so setup is mostly "put the repo in the right place and connect the hardware."

- **Project and output paths** are resolved in `config.py`. `PROJECT_ROOT` is four levels above `rc_car_app/config.py`; photos default to `PROJECT_ROOT/media/photos`, while CSV logs independently default to `~/logs`. `RC_CAR_PHOTO_DIR` and `RC_CAR_LOG_DIR` can override those defaults.
- **Model directory:** `vision.py` registers selectable versions on the Raspberry Pi 5. The Jetson Orin Nano inference server resolves the corresponding file from `code/ai_models` (overridable with `RC_CAR_AI_MODELS_DIR`). Series 1/2 use `SidewalkPilot-v<version>.pth`; Series 3/4 use `SidewalkPilot-v<version>.onnx`.
- **Dashboard transport** defaults to UDP over the USB Ethernet gadget. The relevant config keys are `HUB75_DASHBOARD_TRANSPORT` (`udp`), `HUB75_DASHBOARD_HOST` (`192.168.10.2`), and `HUB75_DASHBOARD_UDP_PORT` (`8765`).

Per-machine setup:

| Machine | Role | Setup essentials |
|---|---|---|
| Jetson Orin Nano | AI Model Manager for every steering-model family | PyTorch and ONNX Runtime GPU dependencies, PTH and ONNX model files, and the headless inference service; reachable at `10.42.0.2:8770` over direct Ethernet |
| Raspberry Pi 5 | Controller: Xbox controller, camera, LiDAR, GPS, Hall-effect wheel-speed sensor, servo, motors, logging, and telemetry | Repository cloned, Python dependencies (`gpiozero`, `adafruit-servokit`, `picamera2`, `pyserial`, `opencv`, `torch`), USB `usb0` at `192.168.10.1/24`, and I2C enabled for the PCA9685 at `0x40` |
| Zero 2 W | Dashboard receiver over USB Ethernet | Repo synced (not a git checkout — populated by rsync/scp), `rpi-rgb-led-matrix` bindings built, USB `usb0` at `192.168.10.2/24`, valid `/etc/machine-id` |
| Mac and NVIDIA PC | Git, sync, photo pull, training | Git access, rsync, and training dependencies for the trainers under `code/ai_models_datasets/` |

## Why This Choice

- Deriving paths from the repo location means a fresh checkout works without hand-editing constants, and the same code runs on the Raspberry Pi 5 and in a laptop simulation fallback (the hardware layer degrades to dummy devices when GPIO/I2C is absent).
- Environment overrides cover the few values that legitimately differ by host (log, photo, and model directories) without requiring many command-line flags. Behavioral toggles remain in configuration rather than prompting the operator at run time.
- Fixed USB Ethernet addresses (`.1` Raspberry Pi 5, `.2` Zero 2 W) keep dashboard routing independent of Wi-Fi and mDNS.

## Verification

```bash
# Any dev host: confirm the runtime modules import/compile cleanly
python3 -m py_compile code/controller/current/rc_car.py code/controller/current/z2w_dashboard.py
python3 -m compileall code/controller/current/rc_car_app

# Raspberry Pi 5 / Zero 2 W: confirm the USB link addresses
ip -br addr show usb0
cat /sys/class/net/usb0/carrier
```

A healthy Raspberry Pi 5 controller prints `Hub75 dashboard telemetry transport: UDP (192.168.10.2:8765).` on startup, and the PCA9685 line `Using PCA9685 steering servo at 0x40, channel 0.` once I2C is up.

## Failure and Recovery

- **Runtime drops to "simulation mode"**: `hardware.py` caught a GPIO/I2C init error and swapped in dummy devices. Check wiring, I2C enablement, and that no other process holds the bus.
- **Zero 2 W boots then hangs headless**: a missing `/etc/machine-id` triggers the systemd first-boot wizard. Regenerate the machine-id.
- **Model not found:** confirm that the version is registered in `STEERING_MODEL_VERSIONS` on the Raspberry Pi 5 and that its matching PTH or ONNX file exists under `code/ai_models` on the Jetson Orin Nano (or set `RC_CAR_AI_MODELS_DIR`).

## Evidence to Attach

- Compile / import log
- `ip -br addr show usb0` output on both devices
- Controller startup lines (transport + servo)

## Related Pages

- [Mac and PC Sync](mac-pc-sync.md)
- [Mac-to-PC Sync Runbook](../runbooks/sync-day/mac-to-pc.md)
- [MkDocs Site Publishing](../publishing/mkdocs-site.md)
