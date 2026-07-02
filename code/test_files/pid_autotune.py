#!/usr/bin/env python3
"""pid_autotune.py -- relay (Astrom-Hagglund) auto-tuner for SidewalkPilot's yaw loop.

*** THIS DRIVES THE CAR AUTONOMOUSLY. ***
It rolls forward at a fixed throttle and runs a RELAY on the IMU yaw rate -- steer a
fixed amount left/right depending on which way the car is rotating. That induces a
steady weave (a limit cycle); from the weave's amplitude (a) and period (Tu) it
computes the ultimate gain  Ku = 4d/(pi*a)  and prints Ziegler-Nichols PID gains.

Because the runtime loop is speed-normalized (correction scaled by REF_SPEED/speed),
the gains are reported scaled to REF_SPEED so they drop straight into config/TUNE.

SAFETY
  * Needs a FLAT, OPEN, ~10-20 m clear stretch -- the car weaves as it rolls.
  * Keep the Xbox controller IN HAND: ANY button, or the steer stick past deadzone,
    aborts instantly. Ctrl-C aborts. There is a hard timeout.
  * On EVERY exit path the motors are cut and the wheels centered.
  * There is NO LiDAR/AEB in this standalone tool -- open area + finger on the
    controller is the safety net. Modest throttle by default.

Run on the Pi INSTEAD of `car` (it owns the hardware):
    python3 ~/rc_car_code/code/test_files/pid_autotune.py
"""
import argparse
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "controller", "current"))

from rc_car_app.hardware import Hardware                       # noqa: E402
from rc_car_app.yaw_pid import ImuReader, YawController        # noqa: E402
from rc_car_app import config as C                             # noqa: E402

try:
    import pygame                                              # noqa: E402
except Exception:
    pygame = None


def pulses_to_mps(pulses, seconds):
    if seconds <= 0:
        return 0.0
    rev_per_s = (pulses / seconds) / C.PULSES_PER_REVOLUTION
    return rev_per_s * C.WHEEL_CIRCUMFERENCE_CM / 100.0        # cm -> m


def analyze(samples, relay_deg, discard_cycles=2):
    """samples: [(t, yaw_dps)]. Returns {a, Tu, Ku, cycles} from the limit cycle, or None.
    Pure function -- unit-testable without hardware."""
    crossings, peaks, cur_peak, prev = [], [], 0.0, None
    for t, y in samples:
        if prev is not None and ((prev < 0.0) != (y < 0.0)):
            crossings.append(t)
            peaks.append(cur_peak)
            cur_peak = 0.0
        cur_peak = max(cur_peak, abs(y))
        prev = y
    d0 = 2 * discard_cycles                                    # drop transient (2 crossings/cycle)
    if len(crossings) < d0 + 3:
        return None
    use_cross, use_peaks = crossings[d0:], peaks[d0:]
    half_periods = [use_cross[i + 1] - use_cross[i] for i in range(len(use_cross) - 1)]
    if not half_periods or not use_peaks:
        return None
    a = sum(use_peaks) / len(use_peaks)
    if a <= 0.0:
        return None
    Tu = 2.0 * (sum(half_periods) / len(half_periods))
    Ku = 4.0 * relay_deg / (math.pi * a)
    return {"a": a, "Tu": Tu, "Ku": Ku, "cycles": len(half_periods) / 2.0}


def _stop(hardware):
    hardware.motor_left_fwd.value = 0
    hardware.motor_left_bwd.value = 0
    hardware.motor_right_fwd.value = 0
    hardware.motor_right_bwd.value = 0


def _drive_forward(hardware, pwm):
    # exact runtime pattern: forward = right_fwd + left_bwd (motors wired opposite)
    pwm = max(0.0, min(1.0, pwm))
    hardware.motor_left_fwd.value = 0
    hardware.motor_right_bwd.value = 0
    hardware.motor_right_fwd.value = max(0.0, min(1.0, pwm * C.RIGHT_MOTOR_PWM_SCALE))
    hardware.motor_left_bwd.value = max(0.0, min(1.0, pwm * C.LEFT_MOTOR_PWM_SCALE))


def _abort_requested():
    """True if the driver touches the controller (any button, or steer stick past
    deadzone) -- the human-takeover kill."""
    if pygame is None:
        return False
    for event in pygame.event.get():
        if event.type == pygame.JOYBUTTONDOWN:
            return True
        if event.type == pygame.JOYAXISMOTION and event.axis == C.STEERING_AXIS:
            if abs(event.value) > max(0.25, C.STEERING_DEADZONE):
                return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Relay auto-tune the yaw PID by driving the car")
    ap.add_argument("--relay-deg", type=float, default=15.0, help="servo deg off center each way (d)")
    ap.add_argument("--throttle", type=float, default=0.5, help="motor pwm for the test roll (0..1)")
    ap.add_argument("--settle-sec", type=float, default=3.0, help="spin-up/transient to discard")
    ap.add_argument("--max-sec", type=float, default=40.0, help="hard timeout")
    ap.add_argument("--target-cycles", type=float, default=8.0, help="stop after this many oscillations")
    args = ap.parse_args()

    center = float(C.STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    ff = YawController(mode="straight",
                       curvature_coeffs=C.STEERING_YAW_PID_CURVATURE_COEFFS,
                       center_deg=center,
                       actuation_range_deg=float(C.STEERING_SERVO_ACTUATION_RANGE_DEG)).ff_center
    ref_speed = float(C.STEERING_YAW_PID_REF_SPEED_MPS)

    # --- controller (required: it's the kill switch) ---
    if pygame is None:
        raise SystemExit("pygame unavailable -- refusing to drive without a takeover controller.")
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        raise SystemExit("No joystick -- refusing to drive without a takeover controller.")
    js = pygame.joystick.Joystick(0)
    js.init()

    pulse = {"n": 0}
    hardware = Hardware(lambda: pulse.__setitem__("n", pulse["n"] + 1))
    imu = ImuReader(C.STEERING_YAW_PID_PORT, C.STEERING_YAW_PID_BAUD,
                    axis=C.STEERING_YAW_PID_AXIS, sign=C.STEERING_YAW_PID_YAW_SIGN)
    imu.start()

    print(f"FF center = {ff:.1f} deg, relay d = {args.relay_deg} deg, throttle = {args.throttle}, "
          f"REF_SPEED = {ref_speed} m/s")
    print("Waiting for IMU...", flush=True)
    t_wait = time.time()
    while not imu.is_fresh() and time.time() - t_wait < 5.0:
        time.sleep(0.05)
    if not imu.is_fresh():
        imu.stop(); pygame.quit()
        raise SystemExit("IMU not streaming (check /dev/ttyAMA3) -- aborting, nothing moved.")

    print(">>> Type 'go' + Enter to DRIVE (anything else aborts). Keep the controller in hand. <<<", flush=True)
    try:
        answer = input("go? ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer != "go":
        imu.stop()
        try:
            hardware.cleanup()
        except Exception:
            pass
        pygame.quit()
        raise SystemExit("Not confirmed ('go' not typed) -- nothing moved.")

    samples = []
    aborted = None
    t0 = time.time()
    pulse_start = None
    try:
        while True:
            now = time.time()
            elapsed = now - t0
            if _abort_requested():
                aborted = "controller"; break
            if elapsed > args.max_sec:
                aborted = "timeout"; break

            _drive_forward(hardware, args.throttle)
            yaw = imu.get_yaw()                                  # + = right (runtime convention)
            # corrective relay -> stable limit cycle: rotating right -> steer left, & vice-versa
            hardware.steering_servo.value = (ff - args.relay_deg) if yaw > 0 else (ff + args.relay_deg)

            if elapsed >= args.settle_sec:
                if pulse_start is None:
                    pulse_start = pulse["n"]; t_collect0 = now
                samples.append((now, yaw))
                res = analyze(samples, args.relay_deg)
                if res and res["cycles"] >= args.target_cycles:
                    break
            time.sleep(1.0 / 50.0)
    except KeyboardInterrupt:
        aborted = "ctrl-c"
    finally:
        _stop(hardware)
        hardware.steering_servo.value = center
        time.sleep(0.2)
        _stop(hardware)
        v_test = pulses_to_mps(pulse["n"] - (pulse_start or pulse["n"]),
                               (time.time() - t_collect0) if pulse_start is not None else 0.0)
        imu.stop()
        try:
            hardware.cleanup()
        except Exception:
            pass
        pygame.quit()

    if aborted:
        print(f"\nABORTED ({aborted}) -- motors cut, wheels centered. No gains computed.")
        return

    res = analyze(samples, args.relay_deg)
    if not res:
        print("\nNo clean limit cycle found. Try a larger --relay-deg (e.g. 20-25) or more space.")
        return

    Ku, Tu = res["Ku"], res["Tu"]
    scale = (v_test / ref_speed) if (v_test > 0.05 and ref_speed > 0) else 1.0

    def zn(kp, ki, kd):
        return (round(kp * scale, 3), round(ki * scale, 3), round(kd * scale, 3))

    no_overshoot = zn(0.20 * Ku, 0.40 * Ku / Tu, 0.0666 * Ku * Tu)
    classic = zn(0.60 * Ku, 1.20 * Ku / Tu, 0.075 * Ku * Tu)
    pi_only = zn(0.45 * Ku, 0.54 * Ku / Tu, 0.0)

    print("\n=== relay auto-tune result ===")
    print(f"  oscillation amplitude a = {res['a']:.1f} dps,  period Tu = {Tu:.2f} s,  cycles = {res['cycles']:.1f}")
    print(f"  ultimate gain Ku = {Ku:.3f}   (at measured test speed {v_test:.2f} m/s)")
    if abs(scale - 1.0) > 0.05:
        print(f"  gains scaled by v_test/REF = {scale:.2f} so they apply at REF_SPEED {ref_speed} m/s")
    print("  suggested gains  (kP, kI, kD):")
    print(f"    no-overshoot (recommended for a car): {no_overshoot}")
    print(f"    PI only (smoothest, no D noise)     : {pi_only}")
    print(f"    classic ZN (aggressive)             : {classic}")
    print("  Enter kP/kI/kD on the TUNE page (or config.py). Start with no-overshoot;")
    print("  if it still weaves, drop kP ~20%. These transfer across speeds (speed-norm).")


if __name__ == "__main__":
    main()
