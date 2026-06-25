#!/usr/bin/env python3
"""
joystick_velocity_test.py  –  Live steering-axis speed meter

Move the steering stick and it prints the current axis value and how fast it's
moving, in axis-units per second (the same number the flick threshold uses).
Use it to feel out the speed difference between a slow deliberate move and a
quick release/flick.

Run on the Pi over SSH (no display needed); reads the stick only, no servo:
    python3 code/test_files/joystick_velocity_test.py            # axis 0
    python3 code/test_files/joystick_velocity_test.py --axis 0

Share button (15) or Ctrl-C to quit.
"""

import argparse
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError as exc:
    print(f"pygame unavailable: {exc}")
    raise SystemExit(1)

STEERING_AXIS = 0
QUIT_BUTTON = 15
FLICK_REFERENCE = 5.0   # runtime's release threshold (axis/s), for reference


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--axis", type=int, default=STEERING_AXIS, help=f"joystick axis index (default {STEERING_AXIS})")
    return p.parse_args()


def main():
    args = parse_args()
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No joystick detected. Connect the Xbox controller and retry.")
        raise SystemExit(1)
    joy = pygame.joystick.Joystick(0)
    joy.init()
    print(f"Controller: {joy.get_name()}   axis {args.axis}")
    print(f"Move the stick. Speed shown in axis-units/sec "
          f"(runtime treats >= {FLICK_REFERENCE:.0f}/s as a release flick).")
    print("Share button or Ctrl-C to quit.\n")

    prev_v = joy.get_axis(args.axis)
    prev_t = time.time()
    peak = 0.0

    try:
        while True:
            pygame.event.pump()
            v = float(joy.get_axis(args.axis))
            t = time.time()
            dt = t - prev_t
            speed = abs(v - prev_v) / dt if dt > 1e-4 else 0.0
            if speed > peak:
                peak = speed
            tag = "FLICK" if speed >= FLICK_REFERENCE else "slow "
            # carriage return keeps it on one updating line
            print(f"\raxis={v:+.3f}   speed={speed:6.1f}/s  [{tag}]   peak={peak:6.1f}/s   ",
                  end="", flush=True)
            prev_v, prev_t = v, t
            if joy.get_numbuttons() > QUIT_BUTTON and joy.get_button(QUIT_BUTTON):
                break
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass

    print(f"\n\nPeak speed seen: {peak:.1f}/s")
    pygame.quit()


if __name__ == "__main__":
    main()
