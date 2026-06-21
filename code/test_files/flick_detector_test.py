#!/usr/bin/env python3
"""
flick_detector_test.py  –  Steering flick pattern detector

Run on Pi 5 via SSH (no display needed) to calibrate the velocity threshold
that distinguishes a genuine stick-release flick from a slow sweep through center.

Usage:
    python3 code/test_files/flick_detector_test.py [--threshold 5.0] [--window 0.12]

What it measures:
    Each time the steering axis enters the deadzone from the left side it prints
    whether the move was a FLICK (fast snap-back) or SMOOTH (slow pass-through),
    along with the measured velocity so you can tune the threshold.

Output example:
    [FLICK ] vel=14.2/s  peak=-0.82  settle_deg=35.1  dt=58ms  → settle fires
    [SMOOTH] vel=1.1/s   peak=-0.82  settle_deg=35.1  dt=750ms → settle skipped
    [RIGHT ] vel=8.3/s   peak=+0.61  (from right – no settle)

At the end (Ctrl-C) prints a summary: total events, flick count, smooth count,
and the ratio. Adjust --threshold until the classification matches your feel.

Settle threshold reference (same as runtime STEERING_CENTER_SETTLE_RELEASE_MIN_DEG):
    12.0 logical degrees left of center = raw axis ~-0.22 before deadzone scaling.

Axis conventions (same as runtime):
    STEERING_AXIS  = 0
    DEADZONE       = 0.1  (values |v| <= 0.1 treated as center)
"""

import argparse
import collections
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError as exc:
    print(f"pygame unavailable: {exc}")
    raise SystemExit(1)

# ── runtime-matching constants ────────────────────────────────────────────────
STEERING_AXIS = 0
DEADZONE = 0.1
ACTUATION_RANGE_DEG = 180.0
# settle fires when last non-center servo was >= 12 deg left of center (90 deg)
SETTLE_MIN_LEFT_DEG = 12.0
# raw axis value that corresponds to SETTLE_MIN_LEFT_DEG  (approximate)
# servo_deg = ((scaled+1)/2)*180;  scaled = (|raw|-dz)/(1-dz) * sign
# 90 - 12 = 78 servo → scaled = (78-90)/90 = -0.133
# raw = -(0.133*(1-0.1) + 0.1) = -0.22
SETTLE_AXIS_THRESHOLD = -0.22

# ── tunable defaults ──────────────────────────────────────────────────────────
DEFAULT_FLICK_THRESHOLD = 5.0   # axis-units/second; adjust via --threshold
DEFAULT_VELOCITY_WINDOW = 0.12  # seconds of history used for velocity calc

# ── colours for terminal output ───────────────────────────────────────────────
_RED   = "\033[91m"
_GRN   = "\033[92m"
_YEL   = "\033[93m"
_CYN   = "\033[96m"
_DIM   = "\033[2m"
_RST   = "\033[0m"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--threshold", type=float, default=DEFAULT_FLICK_THRESHOLD,
                   help=f"Velocity threshold (axis/s) that separates FLICK from SMOOTH (default {DEFAULT_FLICK_THRESHOLD})")
    p.add_argument("--window", type=float, default=DEFAULT_VELOCITY_WINDOW,
                   help=f"Seconds of history used to compute velocity (default {DEFAULT_VELOCITY_WINDOW})")
    p.add_argument("--axis", type=int, default=STEERING_AXIS,
                   help=f"Joystick axis index (default {STEERING_AXIS})")
    return p.parse_args()


def axis_to_servo_deg(raw: float) -> float:
    mag = abs(raw)
    if mag <= DEADZONE:
        return ACTUATION_RANGE_DEG / 2.0
    scaled = (mag - DEADZONE) / (1.0 - DEADZONE)
    scaled = min(1.0, scaled)
    if raw < 0:
        scaled = -scaled
    return ((scaled + 1.0) / 2.0) * ACTUATION_RANGE_DEG


def main():
    args = parse_args()
    flick_threshold = args.threshold
    vel_window = args.window

    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No joystick detected. Connect Xbox controller and retry.")
        raise SystemExit(1)

    joy = pygame.joystick.Joystick(0)
    joy.init()
    print(f"Controller: {joy.get_name()}")
    print(f"Flick threshold : {flick_threshold:.1f} axis/s  "
          f"(edit with --threshold)")
    print(f"Velocity window : {vel_window*1000:.0f} ms  "
          f"(edit with --window)")
    print(f"Settle fires for: left turns > {SETTLE_MIN_LEFT_DEG:.0f}° from center "
          f"(axis <= {SETTLE_AXIS_THRESHOLD:.2f})")
    print()
    print(f"{'Event':8}  {'velocity':>10}  {'peak axis':>10}  {'settle deg':>11}  {'dt':>7}  result")
    print("─" * 70)

    # rolling buffer of (timestamp, raw_axis_value)
    history = collections.deque()
    last_raw = 0.0
    last_nonzero_time = None   # last time |raw| > DEADZONE
    last_nonzero_val  = 0.0
    peak_val          = 0.0    # most extreme raw value during current turn
    in_deadzone       = True

    stats = {"flick": 0, "smooth": 0, "right": 0, "total": 0}

    try:
        while True:
            pygame.event.pump()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise KeyboardInterrupt
                if event.type != pygame.JOYAXISMOTION:
                    continue
                if event.axis != args.axis:
                    continue

                now = time.time()
                raw = float(event.value)

                # maintain rolling velocity history
                history.append((now, raw))
                while history and now - history[0][0] > vel_window * 2:
                    history.popleft()

                currently_in_deadzone = abs(raw) <= DEADZONE

                if not currently_in_deadzone:
                    # track most extreme value during this turn segment
                    if in_deadzone:
                        # just left the deadzone – start a new segment
                        peak_val = raw
                    else:
                        if abs(raw) > abs(peak_val):
                            peak_val = raw
                    last_nonzero_time = now
                    last_nonzero_val  = raw
                    in_deadzone = False
                else:
                    # entered (or staying in) deadzone
                    if not in_deadzone and last_nonzero_time is not None:
                        # transition: non-zero → deadzone
                        dt = now - last_nonzero_time

                        # compute velocity over the last vel_window seconds
                        cutoff = now - vel_window
                        window_pts = [(t, v) for t, v in history if t >= cutoff]
                        if len(window_pts) >= 2:
                            t0, v0 = window_pts[0]
                            t1, v1 = window_pts[-1]
                            span = t1 - t0
                            vel = abs(v1 - v0) / span if span > 1e-6 else 0.0
                        else:
                            vel = abs(last_nonzero_val) / dt if dt > 1e-4 else 0.0

                        settle_deg = abs(axis_to_servo_deg(peak_val) - ACTUATION_RANGE_DEG / 2.0)
                        stats["total"] += 1

                        if peak_val > SETTLE_AXIS_THRESHOLD:
                            # came from right side – settle never fires
                            stats["right"] += 1
                            label = f"{_DIM}[RIGHT ]{_RST}"
                            result = f"{_DIM}(from right – no settle){_RST}"
                        elif settle_deg < SETTLE_MIN_LEFT_DEG:
                            # too close to center – settle won't fire regardless of speed
                            label = f"{_DIM}[SMALL ]{_RST}"
                            result = f"{_DIM}(< {SETTLE_MIN_LEFT_DEG:.0f}° threshold – settle off){_RST}"
                        elif vel >= flick_threshold:
                            stats["flick"] += 1
                            label = f"{_RED}[FLICK ]{_RST}"
                            result = f"{_RED}→ settle fires{_RST}"
                        else:
                            stats["smooth"] += 1
                            label = f"{_GRN}[SMOOTH]{_RST}"
                            result = f"{_GRN}→ settle skipped{_RST}"

                        print(
                            f"{label}  "
                            f"vel={_YEL}{vel:6.1f}/s{_RST}  "
                            f"peak={peak_val:+.3f}  "
                            f"settle_deg={settle_deg:5.1f}°  "
                            f"dt={dt*1000:4.0f}ms  "
                            f"{result}"
                        )

                    in_deadzone = True

                last_raw = raw

            time.sleep(0.002)

    except KeyboardInterrupt:
        pass

    print()
    print("─" * 70)
    left_total = stats["flick"] + stats["smooth"]
    print(f"Left releases : {left_total}   "
          f"FLICK={_RED}{stats['flick']}{_RST}  "
          f"SMOOTH={_GRN}{stats['smooth']}{_RST}  "
          f"RIGHT={_DIM}{stats['right']}{_RST}")
    if left_total > 0:
        rate = stats["flick"] / left_total * 100
        print(f"Flick detect rate: {rate:.0f}%  (threshold={flick_threshold:.1f}/s)")
        if rate < 70:
            print(f"  → threshold too high; try --threshold {max(1.0, flick_threshold - 1.0):.1f}")
        elif rate > 95:
            print(f"  → threshold may be too low; false positives possible; try --threshold {flick_threshold + 1.0:.1f}")
        else:
            print(f"  → threshold looks good.")
    pygame.quit()


if __name__ == "__main__":
    main()
