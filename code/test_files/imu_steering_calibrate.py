#!/usr/bin/env python3
"""
imu_steering_calibrate.py  –  Measure steering curvature vs servo angle with the IMU

For each servo angle it drives the car FORWARD at a fixed low throttle, reads the
filtered yaw rate (from the MG24 on /dev/ttyAMA3) and the wheel speed (hall
sensor), and logs curvature = yaw_rate / speed. From that you get:
  - TRUE CENTER  = the servo angle where curvature crosses 0 (goes straight)
  - LEFT/RIGHT deltas = the asymmetry around center.

  *** THE CAR DRIVES ITSELF in short forward bursts. Put it on the floor with a
      few metres of clear space, stay ready, and Ctrl-C stops everything. ***

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
    p.add_argument("--throttle", type=float, default=0.3, help="CRUISE duty once rolling (default 0.3)")
    p.add_argument("--kick", type=float, default=0.5, help="KICKSTART duty to break stiction (default 0.5)")
    p.add_argument("--kick-time", type=float, default=0.3, help="seconds at kick duty before dropping to cruise (default 0.3)")
    p.add_argument("--angles", default="60,75,85,90,95,105,120", help="logical servo angles to test")
    p.add_argument("--settle", type=float, default=0.8, help="s to reach steady turn before measuring")
    p.add_argument("--window", type=float, default=1.5, help="s to average yaw+speed per angle")
    p.add_argument("--median", type=int, default=5)
    p.add_argument("--ema", type=float, default=0.3)
    p.add_argument("--trim", type=float, default=12.0, help="+D center trim baked into the servo mapping")
    p.add_argument("--out", default="imu_calib.csv")
    p.add_argument("--dry-run", action="store_true", help="NO motors — just sweep servo + read yaw")
    return p.parse_args()


def main():
    args = parse_args()
    angles = [float(a) for a in args.angles.split(",") if a.strip()]

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

    def motors_stop():
        for d in (lf, lb, rf, rb): d.value = 0.0
    def motors_forward(duty):
        lb.value = 0.0; rb.value = 0.0; lf.value = duty; rf.value = duty

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
        print("\n*** CAR WILL DRIVE FORWARD in short bursts. Clear ~3 m, stay ready. ***")
        if input('Type GO to start (anything else aborts): ').strip() != "GO":
            print("Aborted."); motors_stop(); return
    else:
        print("DRY RUN: motors stay OFF (curvature will read ~0 since the car isn't moving).")

    results = []
    try:
        for ang in angles:
            motors_stop(); servo.value = CENTER; time.sleep(0.4)
            servo.value = max(0.0, min(STEERING_SERVO_ACTUATION_RANGE_DEG, ang))
            if not args.dry_run:
                motors_forward(args.kick)                 # kickstart: break stiction (~0.5)
                time.sleep(args.kick_time)
                motors_forward(args.throttle)             # drop to cruise (~0.3) once rolling
            time.sleep(args.settle)                       # reach steady turn at cruise speed

            yaw_sum, n = 0.0, 0
            p_start = pulse_count["n"]
            t_end = time.time() + args.window
            while time.time() < t_end:
                y = read_yaw()
                if y is not None:
                    yaw_sum += y; n += 1
            pulses = pulse_count["n"] - p_start
            motors_stop()

            avg_yaw = (yaw_sum / n) if n else 0.0
            speed = (pulses * DIST_PER_PULSE_M) / args.window     # m/s
            curv = (avg_yaw / speed) if speed > 0.05 else float("nan")  # deg per metre
            results.append((ang, avg_yaw, speed, curv))
            print(f"  servo {ang:5.1f}  yaw={avg_yaw:+6.1f} deg/s  speed={speed:4.2f} m/s  "
                  f"curvature={curv:+7.1f} deg/m")
            time.sleep(1.0)                               # let it coast/stop
    except KeyboardInterrupt:
        print("\nSTOPPED.")
    finally:
        motors_stop(); servo.value = CENTER
        try: servo.close()
        except Exception: pass

    # write CSV + a quick center estimate
    with open(args.out, "w") as f:
        f.write("servo_logical_deg,avg_yaw_dps,speed_mps,curvature_deg_per_m\n")
        for ang, yaw, sp, cv in results:
            f.write(f"{ang:.1f},{yaw:.3f},{sp:.3f},{cv:.3f}\n")
    print(f"\nwrote {args.out}")

    # true center = where avg_yaw crosses 0 (linear interp between the two angles that straddle it)
    pts = [(a, y) for a, y, _, _ in results]
    pts.sort()
    center_est = None
    for (a1, y1), (a2, y2) in zip(pts, pts[1:]):
        if (y1 <= 0 <= y2) or (y2 <= 0 <= y1):
            center_est = a1 + (0 - y1) * (a2 - a1) / (y2 - y1) if y2 != y1 else a1
            break
    if center_est is not None:
        print(f"Estimated TRUE CENTER (yaw=0): servo ~= {center_est:.1f}  "
              f"(commanded center is {CENTER:.0f}; delta {center_est - CENTER:+.1f} deg)")
    else:
        print("No yaw zero-crossing in the tested range — widen --angles around center.")


if __name__ == "__main__":
    main()
