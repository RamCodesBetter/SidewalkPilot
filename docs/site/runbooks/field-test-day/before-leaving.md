# Before Leaving

Before Leaving is the packing-and-readiness runbook run at home, before the car ever reaches the test route. It exists so nothing that can only be fixed at a bench is discovered in the field. Follow it in order; every step ends with a physical check or a pass/fail.

## Preconditions

- A test route is chosen. For AI/manual navigation segments, the route must already exist in `code/controller/current/rc_car_app/trossachs_nav_graph.json`; the current route manager uses GPS/odometry state with A* over that graph. The separate compass hardware is not an active route-planning input.
- The steering model to run is decided (see `model-selection.md`). Series 1/2 checkpoints in `code/ai_models/` run on the Raspberry Pi 5; Series 3 and live-supported v4.0 ONNX models run on the Jetson Orin Nano at `10.42.0.2:8770`. v3.4 is the current default. v4.1 models must not be field-tested until live integration and bench replay are complete.
- The latest code is on the Raspberry Pi 5. The Raspberry Pi 5's `~/rc_car_code` is the git repo; the Zero 2 W's copy is synced by rsync/scp and is not a repo, so a code change only takes effect after each device re-imports it.

## Steps

1. Charge and pack the 3S LiPo that powers the drive motors, plus the Raspberry Pi 5/electronics power. Do the full battery inspection in `battery-check.md` before loading anything. Evidence: measured pack voltage.
2. Pack the Xbox controller and confirm it is charged/paired. The runtime hard-exits at startup with `!!! WARNING: No joystick detected` if pygame sees zero joysticks (`rc_car_app/runtime.py`, `pygame.joystick.get_count() == 0`), so a dead controller means no run.
3. Confirm the sensor harness is intact: LiDAR (Youyeetoo FHL-LD19, USB `/dev/ttyUSB0` via CP2102, 230400 baud), GPS (BN880 on `/dev/ttyAMA0`, 9600), hall sensor (GPIO24), servo ribbon to the PCA9685 (I2C `0x40`, channel 0), and the motor leads to the AT8236 (GPIO 19/20 right, 25/13 left). Evidence: visual/tug check of each connector.
4. Confirm the Raspberry Pi Camera Module 3 Wide is seated and its ribbon is locked. The current camera integration and all 81,237 Series 3/4 images use this Raspberry Pi 5 camera path; a loose ribbon breaks capture and model input.
5. Pack the Zero 2 W dashboard and the USB Ethernet cable. The dashboard is USB-only: Raspberry Pi 5 `usb0` is `192.168.10.1`, Zero 2 W `usb0` is `192.168.10.2`, telemetry is UDP to `192.168.10.2:8765`. Use the known working port and power arrangement; `-110`/`-62` enumeration errors indicate a failed USB transaction but do not by themselves prove whether the cause is power, cable, port, or gadget state.
6. Clear space on the Raspberry Pi 5 for the run's output. Each run writes a CSV to `~/logs/log_YYYYMMDD_HHMMSS.csv` by default (or under `RC_CAR_LOG_DIR`) and photos to `media/photos/YYYY_MM_DD_run_N/` with a per-run JSON label file. Confirm free disk in both locations.
7. Bring the takeover plan: confirm the Xbox controller is connected and keep it in reach before any autonomous motion.

## Stop condition

Abort the trip if the LiPo will not reach a safe field voltage, the controller will not charge/pair, the camera ribbon is damaged, or the drive-motor / servo harness is compromised. These cannot be fixed on the route.

## Evidence

- Pack list checked off
- LiPo voltage reading (from `battery-check.md`)
- Photo of the connector/harness state before departure

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
