# Preflight Checklist

The preflight checklist is the fixed set of checks I run before every autonomous field test, so a run fails for a *real* reason (the model, the route) and not because the LiDAR wasn't spinning or the controller wasn't paired. It exists because early runs wasted field time on avoidable setup faults, and because the car can move motors — nothing autonomous should start until manual override and the kill path are confirmed live.

## Procedure

Run on the Raspberry Pi 5 from `code/controller/current`. The checklist maps directly to the subsystems `runtime.py` starts.

### 1. Power and controller

- Xbox controller is paired *before* launch. If no joystick is detected, `runtime.py` prints `!!! WARNING: No joystick detected` and `sys.exit(1)` — the run never starts.
- 3S LiPo charged; motor driver (Yahboom AT8236) powered.
- Kill switch confirmed: quit is controller button `15` (`QUIT_BUTTON`); any steer/gas/brake input cancels autonomy. Verify the takeover works while the car is on a stand *before* it's on the ground.

### 2. Sensors reporting

- **Camera/model:** Raspberry Pi Camera Module 3 Wide via Picamera2 opens and the selected model returns fresh results. Local analysis uses a 0.75-second frame guard; Series 3/4 require a matching Jetson Orin Nano result no more than 0.25 seconds old.
- **LiDAR (FHL-LD19):** motor spinning, points arriving. If disconnected the runtime keeps retrying and reports `NONE`/zero points; do not start an autonomous run with no LiDAR (AEB is your safety net). Baud `230400`; the runtime prefers the CP2102 by-id path and normally falls back to `/dev/ttyUSB0` (formerly GPIO UART `/dev/ttyAMA2`).
- **GPS (BN880) on `/dev/ttyAMA0`, 9600:** only required if the route uses GPS navigation segments; a fix is needed before an `AUTO`/`MNUL` A* route.
- **Hall sensor (GPIO24):** pulses when a wheel turns, so speed and cruise control read non-zero.

### 3. Dashboard link

- Zero 2 W dashboard shows telemetry, not `NO LINK`. USB Ethernet: Raspberry Pi 5 `192.168.10.1`, Zero 2 W `192.168.10.2`, UDP `8765`. This is how I watch drive mode, AEB state, and steering while the car drives away from me.

### 4. Model and safety arming

- Launch with the intended version: run `car`, then select `<version>` on the dashboard model page (e.g. `car` followed by dashboard model selection). Series 3 versions resolve on Jetson Orin Nano.
- Confirm the model actually loaded (dashboard model page / startup log), not a silent fallback.
- **AEB armed:** confirm `AEB:ON` on the dashboard (toggle is button `14`). AEB limits throttle in the governed center range and applies a hard brake at the emergency distance; it never steers.
- Gear starts in `P`; shift to `D` only when you're ready to drive.

## Pass / fail

- **Pass:** every item above green — controller paired, camera fresh, LiDAR spinning, dashboard linked, correct model loaded, AEB armed, override tested.
- **Fail (do not drive autonomously):** no joystick, stale/blank camera, LiDAR silent, dashboard `NO LINK`, or manual takeover not confirmed.

## Field note

The single most common preflight catch is a `NO LINK` dashboard from a USB carrier-up-but-ARP-dead state. Front-load that check: `ip -br addr show usb0`, `cat /sys/class/net/usb0/carrier`, and a ping across the link before blaming the run.

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
