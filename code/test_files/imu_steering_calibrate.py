#!/usr/bin/env python3
"""
imu_steering_calibrate.py  –  Measure steering curvature vs servo angle with the IMU

For each servo angle it drives the car FORWARD at full throttle, reads the
filtered yaw rate (from the MG24 on /dev/ttyAMA3) and the wheel speed (hall
sensor), and logs curvature = yaw_rate / speed. From that you get:
  - TRUE CENTER  = the servo angle where curvature crosses 0 (goes straight)
  - LEFT/RIGHT deltas = the asymmetry around center.

  *** THE CAR DRIVES ITSELF in short full-speed bursts. Put it on the floor with
      a few metres of clear space, stay ready, and Ctrl-C stops everything. ***

WHY a both-ways sweep (the important bit):
  The steering linkage has BACKLASH (slop). If you reset to one side before every
  hop you reverse direction each time, and the slop eats every small move -- servo
  0 and servo 15 read the same ("0->0->15 isn't doing shii"). The fix is to move
  MONOTONICALLY and never reverse mid-sweep:
      UP-sweep   0 ->15->...->180   (always moving RIGHT -> slop seated right)
      DOWN-sweep 180->...->15-> 0   (always moving LEFT  -> slop seated left)
  Center read on the way up vs the way down differs by the slop; the gap between
  the two zero-crossings IS the hysteresis band, and the two centers are the real
  left-approach / right-approach centers. The servo HOLDS its position between
  hops, so each hop is a small same-direction step from the previous angle.

Run on the Pi (car service stopped so it doesn't fight the servo/motors):
    sudo systemctl stop sidewalkpilot-rpi-car.service
    python3 code/test_files/imu_steering_calibrate.py --port /dev/ttyAMA3
    # safe first pass with NO motors (just servo + yaw plumbing):
    python3 code/test_files/imu_steering_calibrate.py --port /dev/ttyAMA3 --dry-run

Note: finding TRUE CENTER (curvature = 0) does NOT depend on the speed scale, so
even if the hall calibration is a bit off, the zero-crossing is still correct.
"""

import argparse
import collections
import math
import sys
import time
from pathlib import Path

try:
    import serial  # pyserial
except ImportError:
    print("pyserial missing -> pip install pyserial"); raise SystemExit(1)

try:
    from gpiozero import PWMOutputDevice, DigitalInputDevice, Device
    try:
        from gpiozero.pins.lgpio import LGPIOFactory
        Device.pin_factory = LGPIOFactory()
    except Exception:
        pass
except ImportError:
    print("gpiozero missing"); raise SystemExit(1)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controller" / "current"))
from rc_car_app.config import (
    MOTOR_LEFT_FWD_PIN, MOTOR_LEFT_BWD_PIN, MOTOR_RIGHT_FWD_PIN, MOTOR_RIGHT_BWD_PIN,
    HALL_SENSOR_GPIO_PIN, WHEEL_DIAMETER_CM, PULSES_PER_REVOLUTION,
    PCA9685_FREQUENCY_HZ, PCA9685_I2C_ADDRESS, PCA9685_SERVO_CHANNEL,
    STEERING_SERVO_ACTUATION_RANGE_DEG, STEERING_SERVO_MAX_PULSE_US, STEERING_SERVO_MIN_PULSE_US,
)
from rc_car_app.hardware import PCA9685SteeringServo

DIST_PER_PULSE_M = (math.pi * (WHEEL_DIAMETER_CM / 100.0)) / PULSES_PER_REVOLUTION  # both-edge count
CENTER = STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", default="/dev/ttyAMA3", help="IMU UART port")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--axis", type=int, default=2, help="yaw axis 0=X 1=Y 2=Z (default 2)")
    p.add_argument("--throttle", type=float, default=1.0, help="motor duty for the whole test (default 1.0 = FULL)")
    p.add_argument("--angles", default="0,15,30,45,60,75,90,105,120,135,150,165,180", help="base servo angles (a sweep is built from these)")
    p.add_argument("--sweep", choices=["both", "up", "down"], default="both",
                   help="both = up 0->180 then down 180->0 (measures the hysteresis band, default); "
                        "up = ascending only; down = descending only")
    p.add_argument("--settle", type=float, default=0.5, help="s to reach steady turn before measuring")
    p.add_argument("--window", type=float, default=1.0, help="s to average yaw+speed per angle")
    p.add_argument("--seat", type=float, default=2.0, help="s to let the servo fully reach the target before launch")
    p.add_argument("--median", type=int, default=5)
    p.add_argument("--ema", type=float, default=0.3)
    p.add_argument("--trim", type=float, default=12.0, help="+D center trim baked into the servo mapping")
    p.add_argument("--out", default="imu_calib.csv")
    p.add_argument("--resume", action="store_true", help="load --out CSV and only run hops not already in it")
    p.add_argument("--dry-run", action="store_true", help="NO motors — just sweep servo + read yaw")
    return p.parse_args()


def build_hops(base, sweep):
    """Return an ordered list of (angle, pass) hops. pass is 'up' or 'dn'.
    Both-ways sweeps up then back down so each angle is approached monotonically
    from each side -> slop stays seated in the sweep direction."""
    asc = sorted(set(base))
    if sweep == "up":
        return [(a, "up") for a in asc]
    if sweep == "down":
        return [(a, "dn") for a in reversed(asc)]
    # both: up 0->180, then down 165->0 (skip the top angle, we just measured it)
    ups = [(a, "up") for a in asc]
    downs = [(a, "dn") for a in reversed(asc[:-1])]
    return ups + downs


def zero_cross(pts):
    """First servo angle where avg_yaw crosses 0, linear-interp. pts = [(angle, yaw)]."""
    pts = sorted(pts)
    for (a1, y1), (a2, y2) in zip(pts, pts[1:]):
        if (y1 <= 0 <= y2) or (y2 <= 0 <= y1):
            return a1 + (0 - y1) * (a2 - a1) / (y2 - y1) if y2 != y1 else a1
    return None


def main():
    args = parse_args()
    base = [float(a) for a in args.angles.split(",") if a.strip()]
    hops = build_hops(base, args.sweep)

    # --- hardware ---
    center_offset = args.trim / (STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0)
    servo = PCA9685SteeringServo(
        channel=PCA9685_SERVO_CHANNEL, address=PCA9685_I2C_ADDRESS, frequency_hz=PCA9685_FREQUENCY_HZ,
        min_pulse_us=STEERING_SERVO_MIN_PULSE_US, max_pulse_us=STEERING_SERVO_MAX_PULSE_US,
        actuation_range_deg=STEERING_SERVO_ACTUATION_RANGE_DEG,
        center_offset=center_offset, center_preload=0.0, center_preload_window=0.0,
    )
    lf = PWMOutputDevice(MOTOR_LEFT_FWD_PIN);  lb = PWMOutputDevice(MOTOR_LEFT_BWD_PIN)
    rf = PWMOutputDevice(MOTOR_RIGHT_FWD_PIN); rb = PWMOutputDevice(MOTOR_RIGHT_BWD_PIN)

    pulse_count = {"n": 0}
    hall = DigitalInputDevice(HALL_SENSOR_GPIO_PIN, pull_up=True)
    hall.when_activated = lambda: pulse_count.__setitem__("n", pulse_count["n"] + 1)
    hall.when_deactivated = lambda: pulse_count.__setitem__("n", pulse_count["n"] + 1)

    ser = serial.Serial(args.port, args.baud, timeout=0.2)
    time.sleep(0.3); ser.reset_input_buffer()

    def motors_stop():                  # coast / release the brake (all inputs low)
        for d in (lf, lb, rf, rb): d.value = 0.0
    def motors_forward(duty):           # forward = right FWD + left BWD (left motor is mirror-mounted) — matches runtime
        lf.value = 0.0; rb.value = 0.0; rf.value = duty; lb.value = duty
    def motors_brake():                 # AT8236 hard brake: all four inputs HIGH clamps the motor outputs low
        for d in (lf, lb, rf, rb): d.value = 1.0

    med = collections.deque(maxlen=max(1, args.median))
    ema = {"v": 0.0}
    def read_yaw():
        """One filtered yaw sample (median + EMA, NO deadband — we want the small
        near-center values too). Returns None if no fresh line."""
        line = ser.readline().decode("utf-8", "ignore").strip()
        if not line or line == "READY" or line.startswith("ERR"):
            return None
        parts = line.split(",")
        if len(parts) != 3:
            return None
        try:
            v = float(parts[args.axis])
        except (ValueError, IndexError):
            return None
        med.append(v)
        s = sorted(med); m = s[len(s) // 2]
        ema["v"] = args.ema * m + (1.0 - args.ema) * ema["v"]
        return ema["v"]

    motors_stop()
    servo.value = CENTER

    # confirm IMU is actually streaming before we ever touch the motors
    print("Checking IMU stream...")
    got = None
    t0 = time.time()
    while time.time() - t0 < 3.0:
        got = read_yaw()
        if got is not None:
            break
    if got is None:
        print("No IMU data on", args.port, "- fix that before calibrating. Aborting (motors never armed).")
        motors_stop()
        return
    print("IMU OK.")

    if not args.dry_run:
        print("\n*** Per-hop GO (small-room friendly): position the car + clear ahead, type GO,"
              " it does ONE full-speed burst, stops, then waits for GO again. Ctrl-C stops anytime. ***")
        print(f"Sweep: {args.sweep}  ({len(hops)} hops). The servo HOLDS between hops so each step is"
              " a small same-direction move -- DON'T hand-twist the wheels between hops.")
    else:
        print("DRY RUN: motors stay OFF; it just sweeps the servo through every hop.")

    def measure(ang, pass_tag):
        """One hop at servo `ang`: move DIRECTLY from the previous angle (no reset),
        drive, measure yaw+speed, hard-brake. Returns (ang, yaw, speed, curv, pass)."""
        med.clear(); ema["v"] = 0.0                   # fresh filter for this hop
        # MONOTONIC approach: move straight from wherever the servo is (the previous
        # hop's angle) to the target. The sweep order keeps the move in one direction,
        # so the backlash stays seated and small steps actually register. (Resetting to
        # a fixed side every hop reversed direction and the slop ate the small moves.)
        motors_stop()
        target = max(0.0, min(STEERING_SERVO_ACTUATION_RANGE_DEG, ang))
        servo.value = target
        time.sleep(args.seat)                         # let the servo FULLY reach the target before launch
        if not args.dry_run:
            motors_forward(args.throttle)             # full speed for the whole burst
        # SETTLE: keep READING the IMU (don't just sleep) so the serial buffer stays
        # drained and the filter tracks the LIVE turn -- otherwise stale launch-phase
        # lines pile up and the window averages garbage.
        t_settle = time.time() + args.settle
        while time.time() < t_settle:
            read_yaw()
        ser.reset_input_buffer()                      # drop any leftover backlog -> measure fresh
        yaw_sum, n = 0.0, 0
        p_start = pulse_count["n"]
        t_end = time.time() + args.window
        while time.time() < t_end:
            y = read_yaw()
            if y is not None:
                yaw_sum += y; n += 1
        pulses = pulse_count["n"] - p_start
        if not args.dry_run:
            motors_brake(); time.sleep(0.3)           # HARD BRAKE so it doesn't coast into a wall
        motors_stop()                                 # release the brake
        avg_yaw = (yaw_sum / n) if n else 0.0
        speed = (pulses * DIST_PER_PULSE_M) / args.window      # m/s
        curv = (avg_yaw / speed) if speed > 0.05 else float("nan")  # deg per metre
        print(f"  [{pass_tag}] servo {ang:5.1f}  yaw={avg_yaw:+6.1f} deg/s  speed={speed:4.2f} m/s  "
              f"curvature={curv:+7.1f} deg/m")
        time.sleep(0.3)                               # already braked; brief pause
        return (ang, avg_yaw, speed, curv, pass_tag)

    results = [None] * len(hops)
    if args.resume and Path(args.out).exists():
        rows = []
        for ln in Path(args.out).read_text().splitlines()[1:]:   # skip header
            cols = ln.split(",")
            if len(cols) < 4:
                continue
            try:
                sv, yw, sp, cv = (float(c) for c in cols[:4])
            except ValueError:
                continue
            ps = cols[4].strip() if len(cols) > 4 else ""
            rows.append([sv, yw, sp, cv, ps, False])     # last = "used"
        loaded = 0
        for idx, (a, pt) in enumerate(hops):
            for r in rows:
                if not r[5] and abs(a - r[0]) < 0.51 and (r[4] == "" or r[4] == pt):
                    results[idx] = (a, r[1], r[2], r[3], pt); r[5] = True; loaded += 1; break
        print(f"Resumed {loaded} hop(s) from {args.out}; only the missing ones will run.")
    try:
        i = 0
        while i < len(hops):
            ang, pt = hops[i]
            if results[i] is not None:                # already measured (resumed) -> skip
                i += 1; continue
            if args.dry_run:
                results[i] = measure(ang, pt); i += 1; continue
            prev = f"{hops[i-1][0]:.0f}" if i > 0 else "-"
            resp = input(f"\nReposition car + clear ahead. GO for [{pt}] servo {ang:.0f}  "
                         f"(hop {i+1}/{len(hops)}; REDO = redo prev servo {prev}, Q = finish): ").strip().lower()
            if resp == "go":
                results[i] = measure(ang, pt); i += 1
            elif resp == "redo" or resp.startswith("redo "):
                parts = resp.split()
                target = None
                if len(parts) > 1:
                    try:
                        target = float(parts[1])
                    except ValueError:
                        target = None
                if target is not None:
                    # redo a SPECIFIC angle: redo the most recent ALREADY-DONE hop at that angle
                    idx = next((j for j in range(i - 1, -1, -1)
                                if results[j] is not None and abs(hops[j][0] - target) < 0.51), None)
                    if idx is None:
                        print(f"  no measured hop at servo {target:.0f} to redo yet.")
                    else:
                        print(f"  redoing [{hops[idx][1]}] servo {hops[idx][0]:.0f} ...")
                        results[idx] = measure(hops[idx][0], hops[idx][1])
                elif i > 0:
                    # bare "redo" -> redo the previous hop
                    print(f"  redoing [{hops[i-1][1]}] servo {hops[i-1][0]:.0f} ...")
                    results[i - 1] = measure(hops[i - 1][0], hops[i - 1][1])
                else:
                    print("  nothing to redo yet.")
            elif resp in ("q", "quit", "done", "finish", "exit", "stop"):
                print("Finishing with the hops done so far."); break
            else:
                print("  ? type 'go', 'redo', or 'q' — a typo won't quit/lose progress.")
    except KeyboardInterrupt:
        print("\nSTOPPED.")
    finally:
        try:
            motors_brake(); time.sleep(0.3)   # hard emergency brake on finish / Ctrl-C
        except Exception:
            pass
        motors_stop(); servo.value = CENTER
        try: servo.close()
        except Exception: pass

    # write CSV (in sweep order, with the up/dn pass tag)
    done = [r for r in results if r is not None]
    with open(args.out, "w") as f:
        f.write("servo_logical_deg,avg_yaw_dps,speed_mps,curvature_deg_per_m,pass\n")
        for ang, yaw, sp, cv, pt in done:
            f.write(f"{ang:.1f},{yaw:.3f},{sp:.3f},{cv:.3f},{pt}\n")
    print(f"\nwrote {args.out}")

    # TRUE CENTER = where avg_yaw crosses 0, computed SEPARATELY for each sweep
    # direction. The two differ by the steering backlash; the gap is the hysteresis.
    up_pts = [(a, y) for a, y, _, _, pt in done if pt == "up"]
    dn_pts = [(a, y) for a, y, _, _, pt in done if pt == "dn"]
    c_up = zero_cross(up_pts)
    c_dn = zero_cross(dn_pts)
    if c_up is not None:
        print(f"UP-sweep   center (yaw=0): servo ~= {c_up:.1f}   (delta {c_up - CENTER:+.1f} from commanded {CENTER:.0f})")
    if c_dn is not None:
        print(f"DOWN-sweep center (yaw=0): servo ~= {c_dn:.1f}   (delta {c_dn - CENTER:+.1f} from commanded {CENTER:.0f})")
    if c_up is not None and c_dn is not None:
        mid = (c_up + c_dn) / 2.0
        print(f"HYSTERESIS band = {abs(c_up - c_dn):.1f} deg of servo slop.  Mid-center ~= {mid:.1f} "
              f"-> good PID setpoint; the loop holds yaw=0 across the slop.")
    elif c_up is None and c_dn is None:
        print("No yaw zero-crossing found — widen --angles around center.")


if __name__ == "__main__":
    main()
