#!/usr/bin/env python3
"""pid_autotune.py -- relay (Astrom-Hagglund) auto-tuner for SidewalkPilot's yaw loop.

*** THIS DRIVES THE CAR AUTONOMOUSLY. ***
It rolls forward at a fixed throttle and runs a RELAY on the IMU yaw rate -- steer a
fixed amount left/right depending on which way the car is rotating. That induces a
steady weave (a limit cycle); from the weave's amplitude (a) and period (Tu) it
computes the ultimate gain  Ku = 4d/(pi*sqrt(a^2 - eps^2))  and prints Ziegler-Nichols
gains. The relay uses a HYSTERESIS band eps (set from the yaw noise) so sensor jitter
can't fake a tiny fast cycle -- the car must truly swing past +/-eps before it flips.

SEGMENTED for a short runway: it runs in SHORT bursts. Drive a few oscillations, it
stops, you reposition the car, type 'go' again -- the cycles are POOLED across segments
until it has enough, then it computes. Type 'done' to finish early with what you have.

Because the runtime loop is speed-normalized (correction scaled by REF_SPEED/speed),
the gains are reported scaled to REF_SPEED so they drop straight into config/TUNE.

SAFETY
  * Each segment needs only a short clear stretch, but the car weaves as it rolls.
  * Keep the Xbox controller IN HAND: ANY button, or the steer stick past deadzone,
    aborts the segment instantly. Ctrl-C aborts everything. Per-segment hard timeout.
  * On EVERY exit path the motors are cut and the wheels centered.
  * NO LiDAR/AEB here -- open area + finger on the controller is the safety net.
    Throttle 0.85 by default (car won't move below ~0.55), so it rolls at a real pace.

Run on the Pi INSTEAD of `car` (it owns the hardware):
    python3 ~/rc_car_code/code/test_files/pid_autotune.py
    python3 ~/rc_car_code/code/test_files/pid_autotune.py --cycles-per-segment 2   # tiny space
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


def extract(samples, discard_cycles=1):
    """From one segment's [(t, yaw_dps)], return (peaks, half_periods) after dropping
    the relay transient. main() POOLS these across segments. Pure -- unit-testable."""
    crossings, peaks, cur_peak, prev = [], [], 0.0, None
    for t, y in samples:
        if prev is not None and ((prev < 0.0) != (y < 0.0)):
            crossings.append(t)
            peaks.append(cur_peak)
            cur_peak = 0.0
        cur_peak = max(cur_peak, abs(y))
        prev = y
    d0 = 2 * discard_cycles                                    # 2 crossings per cycle
    if len(crossings) < d0 + 2:
        return [], []
    use_cross, use_peaks = crossings[d0:], peaks[d0:]
    half_periods = [use_cross[i + 1] - use_cross[i] for i in range(len(use_cross) - 1)]
    return use_peaks, half_periods


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


def run_segment(hardware, imu, pulse, ff, center, args, eps, measure_noise, seg_num, need_cycles):
    """Drive ONE short burst. Returns dict(peaks, half_periods, eps, aborted, v_test)."""
    settle_yaws, samples = [], []
    relay_state, last_osc = 1, 0
    aborted, pulse_start, t_collect0 = None, None, None
    per_seg_target = max(1, min(int(args.cycles_per_segment), int(math.ceil(need_cycles))))
    print(f">>> Segment {seg_num} driving (~{per_seg_target} osc). "
          f"Grab stick / any button / Ctrl-C aborts. <<<", flush=True)
    t0 = time.time()
    try:
        while True:
            now = time.time()
            elapsed = now - t0
            if _abort_requested():
                aborted = "controller"; break
            if elapsed > args.seg_max_sec:
                aborted = "timeout"; break

            _drive_forward(hardware, args.throttle)
            yaw = imu.get_yaw()                                  # + = right (runtime convention)

            if elapsed < args.settle_sec:
                hardware.steering_servo.value = ff               # roll straight to settle
                if measure_noise:
                    settle_yaws.append(yaw)                      # sample the yaw NOISE (seg 1 only)
                time.sleep(1.0 / 50.0)
                continue

            if eps is None:                                      # set the hysteresis band once
                if args.hysteresis_dps > 0:
                    eps = args.hysteresis_dps
                else:
                    m = sum(settle_yaws) / len(settle_yaws) if settle_yaws else 0.0
                    sd = (math.sqrt(sum((y - m) ** 2 for y in settle_yaws) / len(settle_yaws))
                          if settle_yaws else 0.0)
                    eps = max(3.0, min(10.0, 4.0 * sd))
                print(f"  hysteresis eps = {eps:.1f} dps", flush=True)
            if pulse_start is None:
                pulse_start = pulse["n"]; t_collect0 = now

            # RELAY WITH HYSTERESIS: flip only once the car truly swings past +/-eps.
            if yaw > eps:
                relay_state = -1                                 # rotating right -> steer LEFT
            elif yaw < -eps:
                relay_state = 1                                  # rotating left  -> steer RIGHT
            hardware.steering_servo.value = ff + relay_state * args.relay_deg

            samples.append((now, yaw))
            _, hps = extract(samples)
            seg_cycles = len(hps) / 2.0
            if int(seg_cycles) > last_osc:
                last_osc = int(seg_cycles)
                print(f"    osc {last_osc}/{per_seg_target} (this segment)", flush=True)
            if seg_cycles >= per_seg_target:
                break
            time.sleep(1.0 / 50.0)
    except KeyboardInterrupt:
        aborted = "ctrl-c"
    finally:
        _stop(hardware)
        hardware.steering_servo.value = center
        time.sleep(0.2)
        _stop(hardware)

    peaks, hps = extract(samples)
    v_test = pulses_to_mps(pulse["n"] - (pulse_start if pulse_start is not None else pulse["n"]),
                           (time.time() - t_collect0) if t_collect0 is not None else 0.0)
    return {"peaks": peaks, "half_periods": hps, "eps": eps, "aborted": aborted, "v_test": v_test}


def main():
    ap = argparse.ArgumentParser(description="Relay auto-tune the yaw PID by driving the car (segmented)")
    ap.add_argument("--relay-deg", type=float, default=15.0, help="servo deg off center each way (d)")
    ap.add_argument("--hysteresis-dps", type=float, default=0.0, help="relay switch band (0 = auto from yaw noise)")
    ap.add_argument("--throttle", type=float, default=0.85, help="motor pwm (0..1); car won't move below ~0.55")
    ap.add_argument("--settle-sec", type=float, default=2.0, help="straight roll before each weave (transient)")
    ap.add_argument("--seg-max-sec", type=float, default=20.0, help="per-segment hard timeout")
    ap.add_argument("--target-cycles", type=float, default=10.0, help="TOTAL oscillations to pool across segments")
    ap.add_argument("--cycles-per-segment", type=int, default=3, help="oscillations per short burst (smaller = less space)")
    args = ap.parse_args()

    center = float(C.STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0
    ff = YawController(mode="straight",
                       curvature_coeffs=C.STEERING_YAW_PID_CURVATURE_COEFFS,
                       center_deg=center,
                       actuation_range_deg=float(C.STEERING_SERVO_ACTUATION_RANGE_DEG)).ff_center
    ref_speed = float(C.STEERING_YAW_PID_REF_SPEED_MPS)

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

    print(f"FF center = {ff:.1f} deg, relay d = {args.relay_deg} deg, throttle = {args.throttle}, "
          f"REF_SPEED = {ref_speed} m/s")
    print("Waiting for IMU...", flush=True)
    t_wait = time.time()
    while not imu.is_fresh() and time.time() - t_wait < 5.0:
        time.sleep(0.05)
    if not imu.is_fresh():
        imu.stop(); pygame.quit()
        raise SystemExit("IMU not streaming (check /dev/ttyAMA3) -- aborting, nothing moved.")

    print("\nSegmented auto-tune: short bursts with repositioning between. Type 'go' to run")
    print(f"a segment (~{args.cycles_per_segment} osc), 'done' to finish early. Controller in hand.")

    peaks_all, hps_all, v_tests = [], [], []
    eps = None
    seg = 0
    aborted_all = None
    try:
        while (len(hps_all) / 2.0) < args.target_cycles:
            seg += 1
            need = args.target_cycles - len(hps_all) / 2.0
            print(f"\n--- Segment {seg}: put the car at the start of your runway. "
                  f"Need ~{int(math.ceil(need))} more osc. ---")
            try:
                ans = input("go / done? ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "done"
            if ans == "done":
                break
            if ans != "go":
                print("  (not 'go' -- skipping)")
                seg -= 1
                continue
            r = run_segment(hardware, imu, pulse, ff, center, args,
                            eps=eps, measure_noise=(eps is None), seg_num=seg, need_cycles=need)
            eps = r["eps"] or eps
            if r["aborted"] == "ctrl-c":
                aborted_all = "ctrl-c"; break
            peaks_all.extend(r["peaks"])
            hps_all.extend(r["half_periods"])
            if r["v_test"] > 0.05:
                v_tests.append(r["v_test"])
            got = len(r["half_periods"]) / 2.0
            note = "  [you took over]" if r["aborted"] == "controller" else ""
            print(f"  segment {seg}: +{got:.1f} osc  (total {len(hps_all) / 2.0:.1f}/{int(args.target_cycles)}){note}")
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
        print(f"\nABORTED ({aborted_all}) -- motors cut, wheels centered. No gains computed.")
        return
    if len(hps_all) < 2 or not peaks_all:
        print("\nNot enough oscillations collected to compute gains. Run more segments "
              "or raise --relay-deg if the car barely rotated.")
        return

    a = sum(peaks_all) / len(peaks_all)
    Tu = 2.0 * (sum(hps_all) / len(hps_all))
    total_cycles = len(hps_all) / 2.0
    if eps is None or a <= eps:
        print(f"\nYaw swing (a={a:.1f} dps) didn't clearly exceed the hysteresis band (eps={eps}) "
              f"-> the car barely rotated. Increase --relay-deg (e.g. 25-35). No reliable Ku.")
        return
    Ku = 4.0 * args.relay_deg / (math.pi * math.sqrt(a * a - eps * eps))
    v_test = (sum(v_tests) / len(v_tests)) if v_tests else 0.0
    scale = (v_test / ref_speed) if (v_test > 0.05 and ref_speed > 0) else 1.0

    def zn(kp, ki, kd):
        return (round(kp * scale, 3), round(ki * scale, 3), round(kd * scale, 3))

    no_overshoot = zn(0.20 * Ku, 0.40 * Ku / Tu, 0.0666 * Ku * Tu)
    classic = zn(0.60 * Ku, 1.20 * Ku / Tu, 0.075 * Ku * Tu)
    pi_only = zn(0.45 * Ku, 0.54 * Ku / Tu, 0.0)

    print("\n=== relay auto-tune result (pooled over segments) ===")
    print(f"  amplitude a = {a:.1f} dps (hysteresis eps = {eps:.1f}),  period Tu = {Tu:.2f} s,  "
          f"pooled cycles = {total_cycles:.1f}")
    print(f"  ultimate gain Ku = {Ku:.3f}   (avg test speed {v_test:.2f} m/s)")
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
