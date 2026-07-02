#!/usr/bin/env python3
"""ff_calibrate.py -- measure LFF / RFF (the direction-dependent straight-angle
feed-forwards) from real driving data.

*** THIS DRIVES THE CAR AUTONOMOUSLY. ***
Because the steering has hysteresis, the servo angle that makes the car go STRAIGHT
(yaw = 0) differs by which way the wheels last came from. This tool measures both:

  For each approach (LEFT = seat wheels at servo 0, RIGHT = seat at servo 180):
    - seat the wheels from that side (roll with servo at the extreme, briefly),
    - then hold a few near-center angles and record the steady curvature
      (curvature = yaw_rate / speed, deg/m),
    - fit curvature vs angle (a line near center) and solve curvature = 0.
  The zero-crossing seated-from-LEFT  = LFF; seated-from-RIGHT = RFF.

Segmented for a short runway: one (approach, angle) per 'go' burst; reposition
between; the points pool and get fit at the end.

SAFETY (same as pid_autotune): needs the Xbox controller (ANY button / steer-stick
aborts the burst; Ctrl-C aborts all); per-burst timeout; motors cut + wheels centered
on EVERY exit. Open, flat area -- the seating turns the car hard each burst.

Run on the Pi INSTEAD of `car`:
    python3 ~/rc_car_code/code/test_files/ff_calibrate.py
    python3 ~/rc_car_code/code/test_files/ff_calibrate.py --angles 106,112,118   # fewer bursts
"""
import argparse
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "controller", "current"))

from rc_car_app.hardware import Hardware                       # noqa: E402
from rc_car_app.yaw_pid import ImuReader                       # noqa: E402
from rc_car_app import config as C                             # noqa: E402

try:
    import pygame                                              # noqa: E402
except Exception:
    pygame = None


def pulses_to_mps(pulses, seconds):
    if seconds <= 0:
        return 0.0
    return ((pulses / seconds) / C.PULSES_PER_REVOLUTION) * C.WHEEL_CIRCUMFERENCE_CM / 100.0


def fit_zero(points):
    """Least-squares line through (angle, curvature); return angle where curvature=0."""
    n = len(points)
    if n < 2:
        return None
    sx = sum(a for a, _ in points)
    sy = sum(c for _, c in points)
    sxx = sum(a * a for a, _ in points)
    sxy = sum(a * c for a, c in points)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        return None
    m = (n * sxy - sx * sy) / denom
    b = (sy - m * sx) / n
    if abs(m) < 1e-6:
        return None
    return -b / m


def _stop(hardware):
    hardware.motor_left_fwd.value = 0
    hardware.motor_left_bwd.value = 0
    hardware.motor_right_fwd.value = 0
    hardware.motor_right_bwd.value = 0


def _drive_forward(hardware, pwm):
    pwm = max(0.0, min(1.0, pwm))
    hardware.motor_left_fwd.value = 0
    hardware.motor_right_bwd.value = 0
    hardware.motor_right_fwd.value = max(0.0, min(1.0, pwm * C.RIGHT_MOTOR_PWM_SCALE))
    hardware.motor_left_bwd.value = max(0.0, min(1.0, pwm * C.LEFT_MOTOR_PWM_SCALE))


def _abort_requested():
    if pygame is None:
        return False
    for event in pygame.event.get():
        if event.type == pygame.JOYBUTTONDOWN:
            return True
        if event.type == pygame.JOYAXISMOTION and event.axis == C.STEERING_AXIS:
            if abs(event.value) > max(0.25, C.STEERING_DEADZONE):
                return True
    return False


def measure_point(hardware, imu, pulse, center, approach, angle, args):
    """Seat from `approach`, hold `angle`, return (curvature_deg_per_m, aborted)."""
    seat_servo = 0.0 if approach == "left" else 180.0
    yaws, pulse0, tmeas0, aborted = [], None, None, None
    t0 = time.time()
    try:
        while True:
            now = time.time()
            el = now - t0
            if _abort_requested():
                aborted = "controller"; break
            if el > args.seg_max_sec:
                aborted = "timeout"; break
            _drive_forward(hardware, args.throttle)
            if el < args.seat_sec:
                hardware.steering_servo.value = seat_servo          # seat wheels from this side
            else:
                hardware.steering_servo.value = angle               # hold the test angle
                if el >= args.seat_sec + args.settle_sec:           # after settle -> measure
                    if pulse0 is None:
                        pulse0, tmeas0 = pulse["n"], now
                    yaws.append(imu.get_yaw())
                    if now - tmeas0 >= args.hold_sec:
                        break
            time.sleep(1.0 / 50.0)
    except KeyboardInterrupt:
        aborted = "ctrl-c"
    finally:
        _stop(hardware)
        hardware.steering_servo.value = center
        time.sleep(0.2)
        _stop(hardware)
    if aborted:
        return None, aborted
    if not yaws or pulse0 is None:
        return None, None
    mean_yaw = sum(yaws) / len(yaws)
    speed = pulses_to_mps(pulse["n"] - pulse0, time.time() - tmeas0)
    if speed < 0.15:
        print(f"    too slow ({speed:.2f} m/s) to measure -- skipped")
        return None, None
    curv = mean_yaw / speed
    print(f"    {approach:>5} @ {angle:5.0f}:  curvature {curv:+6.1f} deg/m  "
          f"(yaw {mean_yaw:+5.1f} dps @ {speed:.2f} m/s)")
    return curv, None


def main():
    ap = argparse.ArgumentParser(description="Measure LFF/RFF straight-angle feed-forwards from driving data")
    ap.add_argument("--angles", default="104,108,112,116,120", help="near-center test angles to sweep")
    ap.add_argument("--throttle", type=float, default=0.65, help="motor pwm (0..1); won't move below ~0.55")
    ap.add_argument("--seat-sec", type=float, default=0.7, help="roll at the extreme to seat the wheels")
    ap.add_argument("--settle-sec", type=float, default=0.5, help="let yaw settle after moving to the test angle")
    ap.add_argument("--hold-sec", type=float, default=1.0, help="measurement window at the test angle")
    ap.add_argument("--seg-max-sec", type=float, default=15.0, help="per-burst hard timeout")
    args = ap.parse_args()

    try:
        angles = [float(x) for x in args.angles.split(",") if x.strip()]
    except ValueError:
        raise SystemExit(f"bad --angles: {args.angles}")
    if len(angles) < 2:
        raise SystemExit("need at least 2 angles to fit a line")

    center = float(C.STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0

    if pygame is None:
        raise SystemExit("pygame unavailable -- refusing to drive without a takeover controller.")
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        raise SystemExit("No joystick -- refusing to drive without a takeover controller.")
    pygame.joystick.Joystick(0).init()

    pulse = {"n": 0}
    hardware = Hardware(lambda: pulse.__setitem__("n", pulse["n"] + 1))
    imu = ImuReader(C.STEERING_YAW_PID_PORT, C.STEERING_YAW_PID_BAUD,
                    axis=C.STEERING_YAW_PID_AXIS, sign=C.STEERING_YAW_PID_YAW_SIGN)
    imu.start()

    print("Waiting for IMU...", flush=True)
    t_wait = time.time()
    while not imu.is_fresh() and time.time() - t_wait < 5.0:
        time.sleep(0.05)
    if not imu.is_fresh():
        imu.stop(); pygame.quit()
        raise SystemExit("IMU not streaming (check /dev/ttyAMA3) -- aborting, nothing moved.")

    plan = [("left", a) for a in angles] + [("right", a) for a in angles]
    left_pts, right_pts = [], []
    aborted_all = None
    print(f"\nFF calibration: {len(plan)} short bursts (seat + hold). Type 'go' to run each,")
    print("'skip' to skip one, 'done' to finish early. Controller in hand (any input aborts).")
    try:
        for i, (approach, angle) in enumerate(plan, 1):
            print(f"\n--- {i}/{len(plan)}: reposition car; it will SEAT {approach.upper()} "
                  f"then HOLD {angle:.0f}. ---")
            try:
                ans = input("go / skip / done? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "done"
            if ans == "done":
                break
            if ans == "skip":
                continue
            if ans != "go":
                print("  (not 'go' -- skipping)")
                continue
            curv, ab = measure_point(hardware, imu, pulse, center, approach, angle, args)
            if ab == "ctrl-c":
                aborted_all = "ctrl-c"; break
            if curv is not None:
                (left_pts if approach == "left" else right_pts).append((angle, curv))
    finally:
        _stop(hardware)
        hardware.steering_servo.value = center
        time.sleep(0.2)
        _stop(hardware)
        imu.stop()
        try:
            hardware.cleanup()
        except Exception:
            pass
        pygame.quit()

    if aborted_all:
        print(f"\nABORTED ({aborted_all}) -- motors cut, wheels centered. No result.")
        return

    lff = fit_zero(left_pts)
    rff = fit_zero(right_pts)
    print("\n=== FF calibration result ===")
    print(f"  LEFT-approach points:  {[(a, round(c, 1)) for a, c in left_pts]}")
    print(f"  RIGHT-approach points: {[(a, round(c, 1)) for a, c in right_pts]}")
    if lff is None or rff is None:
        print("  Not enough clean points on one side -- run more bursts (need >=2 per side).")
        return

    def _sane(x):
        return 60.0 <= x <= 160.0
    print(f"  LFF (seated-from-left  straight angle) = {lff:.1f} deg"
          + ("" if _sane(lff) else "   <-- looks off, re-check"))
    print(f"  RFF (seated-from-right straight angle) = {rff:.1f} deg"
          + ("" if _sane(rff) else "   <-- looks off, re-check"))

    print(f"\n  >>> LFF = {lff:.1f}    RFF = {rff:.1f} <<<")
    print("  Paste these to me and I'll wire them into the runtime (and drop the +10 bump).")


if __name__ == "__main__":
    main()
