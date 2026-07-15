#!/usr/bin/env python3
"""
flick_detector_test.py  –  Guided steering "flick" speed calibrator

Run on the Pi 5 over SSH (no display needed). It walks you through N flicks:
hold the steering stick FULL LEFT, it prints "FLICK NOW", you snap it back to
center, and it measures how fast the stick sprang back. After N flicks it prints
the average flick speed and a recommended threshold to use in the runtime.

Why: when you release the stick it springs through 71,72,...,89 before center,
so the settle can grab the wrong release angle. A flick (release) is FAST;
deliberate steering is SLOW. This measures how fast a real flick is, so the
runtime can tell them apart and snapshot the angle you were actually holding.

Usage:
    python3 code/test_files/controller/flick_detector_test.py            # 5 flicks
    python3 code/test_files/controller/flick_detector_test.py --flicks 8

Controller does not move the servo here — it only reads the stick. Safe to run
with the car service stopped or running.
"""

import argparse
import os
import statistics
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError as exc:
    print(f"pygame unavailable: {exc}")
    raise SystemExit(1)

# ── runtime-matching constants ──────────────────────────────────────────────
STEERING_AXIS = 0
DEADZONE = 0.1            # |axis| <= 0.1 counts as center (same as runtime)
FULL_DEFLECT = 0.9       # |axis| >= 0.9 counts as "full left" to start a flick
ACTUATION_RANGE_DEG = 180.0
QUIT_BUTTON = 15

_GRN, _YEL, _CYN, _DIM, _RST = "\033[92m", "\033[93m", "\033[96m", "\033[2m", "\033[0m"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--flicks", type=int, default=5, help="how many flicks to measure (default 5)")
    p.add_argument("--axis", type=int, default=STEERING_AXIS, help=f"joystick axis index (default {STEERING_AXIS})")
    return p.parse_args()


def read_axis(joy, axis):
    pygame.event.pump()
    return float(joy.get_axis(axis))


def quit_pressed(joy):
    return joy.get_numbuttons() > QUIT_BUTTON and bool(joy.get_button(QUIT_BUTTON))


def main():
    args = parse_args()
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No joystick detected. Connect the Xbox controller and retry.")
        raise SystemExit(1)
    joy = pygame.joystick.Joystick(0)
    joy.init()

    print(f"Controller: {joy.get_name()}")
    print(f"Measuring {args.flicks} flicks on axis {args.axis}.  (Share button = quit early)\n")
    print("For each one: hold the stick FULL LEFT, wait for 'FLICK NOW', then")
    print("snap it back to center as you normally release.\n")

    peak_vels = []   # axis-units / second, peak instantaneous return speed
    avg_vels = []    # axis-units / second, averaged over the whole return

    try:
        for i in range(1, args.flicks + 1):
            # 1) wait until the stick is held full left
            print(f"Flick {i}/{args.flicks}: hold FULL LEFT ...", end="", flush=True)
            while read_axis(joy, args.axis) > -FULL_DEFLECT:
                if quit_pressed(joy):
                    raise KeyboardInterrupt
                time.sleep(0.005)
            print(f"  {_CYN}>>> FLICK NOW! <<<{_RST}")

            # 2) measure the spring-back from full-left until it reaches center
            samples = []
            t0 = time.time()
            prev_t, prev_v, peak = None, None, 0.0
            while True:
                v = read_axis(joy, args.axis)
                t = time.time()
                samples.append((t, v))
                if prev_t is not None:
                    dt = t - prev_t
                    if dt > 0:
                        peak = max(peak, abs(v - prev_v) / dt)
                prev_t, prev_v = t, v
                if abs(v) <= DEADZONE:        # reached center
                    break
                if t - t0 > 3.0:              # safety timeout
                    break
                if quit_pressed(joy):
                    raise KeyboardInterrupt
                time.sleep(0.002)

            t_first, v_first = samples[0]
            t_last, v_last = samples[-1]
            span = max(1e-4, t_last - t_first)
            avg = abs(v_first - v_last) / span
            peak_vels.append(peak)
            avg_vels.append(avg)
            print(f"   → returned in {span * 1000:4.0f} ms   "
                  f"avg {_YEL}{avg:5.1f}/s{_RST}   peak {_YEL}{peak:5.1f}/s{_RST}\n")
            time.sleep(0.4)                   # small gap before the next one
    except KeyboardInterrupt:
        print("\n(stopped early)")

    if not peak_vels:
        print("No flicks recorded.")
        pygame.quit()
        return

    mean_peak = statistics.mean(peak_vels)
    mean_avg = statistics.mean(avg_vels)
    slowest_peak = min(peak_vels)
    print("=" * 56)
    print(f"flicks measured     : {len(peak_vels)}")
    print(f"avg return speed    : {mean_avg:.1f}/s")
    print(f"avg peak speed      : {mean_peak:.1f}/s")
    print(f"slowest flick peak  : {slowest_peak:.1f}/s")
    # Threshold: comfortably below the slowest real flick, well above deliberate
    # steering. Half the slowest flick peak is a safe separator.
    recommend = max(1.0, round(slowest_peak * 0.5, 1))
    print(f"\n{_GRN}Recommended flick threshold for the runtime: ~{recommend}/s{_RST}")
    print("(real releases were faster than this; deliberate steering is slower)")
    print("Tell me this number and I'll wire it into the settle so it snapshots")
    print("the angle you were holding, not a spring-back value.")
    pygame.quit()


if __name__ == "__main__":
    main()
