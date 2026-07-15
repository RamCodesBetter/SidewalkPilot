# Test Gates

A test gate is the specific check that has to pass before I let a change count as "done." This page lists the gates I actually use, scaled to the risk of the change — a syntax check for a small edit, a hardware check when I touch a service, GPIO, USB, or the safety path. The rule is: match the smallest gate that proves the change, but never skip a hardware gate after touching hardware behavior.

## Code coherence gates

Every runtime code change has to compile before anything else:

```bash
python -m py_compile code/controller/current/rc_car.py code/controller/current/z2w_dashboard.py
python -m compileall code/controller/current/rc_car_app
```

Test utilities are mostly flat files in `code/test_files/`. Changed Python utilities get their own compile/test gate, and the USB dashboard installer gets a `bash -n` syntax gate.

## Subsystem gates

| Change area | Owning file | Gate to pass |
|---|---|---|
| Controller input / buttons | `runtime.py` | Buttons map correctly (compare to the pygame control printout) |
| Steering math | `hardware.py` (+ `config.py`) | Servo moves logically 0=left / 90=center / 180=right; compensation stays in the mapping layer |
| Model inference | `vision.py` (+ `config.py`) | Model loads, produces a steering angle, and confidence gating behaves |
| AEB / LiDAR | `lidar.py`, `lidar_avoidance.py`, and `runtime.py` | Center-corridor throttle/stop behavior, no steering command, graceful reconnect |
| Navigation | `navigation.py` + `trossachs_nav_graph.json` | A* returns a followable route with correct AI/manual segments |
| Zero 2 W display | `z2w_dashboard.py` + `hub75_dashboard.py` | New/changed value threaded through ALL layers (runtime → serializer → renderer), not just the draw function |
| Logs | `logging_utils.py` | CSV headers in `config.py` match the runtime row writes |

## Hardware gates (do not skip after touching hardware)

- **USB dashboard:** `ip -br addr show usb0`, `cat /sys/class/net/usb0/carrier`, `ip neigh show dev usb0`, then ping both ways (`192.168.10.2` from the Raspberry Pi 5, `192.168.10.1` from the Zero 2 W). Carrier `1` with a failed ping is the known ARP failure mode — recover with the keeper service.
- **LiDAR:** stop the car service first so there are not two readers, then check the current USB-serial stream:

```bash
sudo systemctl stop sidewalkpilot-rpi-car.service
stty -F /dev/ttyUSB0 230400 raw -echo
timeout 5s cat /dev/ttyUSB0 | hexdump -C
```

  Prefer the stable `/dev/serial/by-id/` CP2102 path when available. Stop every competing serial reader first.
- **Safety motion gate:** restrain or lift the wheels for initial actuator checks, keep the controller ready for takeover, and do not enable autonomy until the selected model and safety state are confirmed.

## Data gates

Before a photo batch joins a named dataset snapshot: count images/labels, flag corrupt or unreadable files, sample lighting/blur/exposure/angle/obstruction, report steering balance and source provenance, and document exclusions. Nothing is deleted without explicit review.

## Model gates

- **Do not use MAE alone.** Gate checkpoints on confusion balance, Bal9, turn capability, signed error, and field behavior because aggregate error can hide center collapse.
- Treat final and best-validation checkpoints as separate candidates. Do not assume either naming role wins in the field.
- A new model is not field-promoted until a documented real drive says so. v3.3/v3.3b were tested and regressed; v3.4 is the current field selection. Series 4 remains untested on the car.

## Why gates instead of "it ran once"

The 2026-07-11 dashboard bug (a hardcoded page-count clamp in the serializer that survived correct config, runtime, and renderer values) cost 2.5 hours precisely because the change was assumed done instead of proven end-to-end. The gate that would have caught it in 30 seconds — grep the magic value across every file, then watch it on the wire — is now a standing rule: prove the data path computed → serialized → on-wire → received → rendered, don't assert it.

## Related pages

- `engineering-process/design-decisions/b-checkpoints.md`
- `testing/failures/overview.md`
- `roadmap/next-steps.md`
