#!/usr/bin/env python3
"""Steering settle "pushback" curve tool — calibrate, fit, simulate.

Three modes in one file:

  CALIBRATE (Pi only, moves the steering servo)
      For each release angle r in [0,15,30,45,60,75,90]:
        sweep a candidate pushback target 180 -> 90 (step 5). Each candidate:
        center -> go to release angle r -> kick to candidate for 0.3s (+17D
        trim) -> return to 90 -> hold ~3s so you can SEE if the wheel ended up
        straight. Press A to lock that candidate as the pushback for r and move
        on; if it reaches 90 with no press, it records (r, 90). Gives you the
        measured points (r, pushback).

  REGRESS
      Fit those points to a polynomial of the degree you choose
      (1=linear, 2=quadratic, 3=cubic, 4=quartic, ...). Prints the coefficients
      and R^2, and can load the fit straight into the simulator.

  SIMULATE
      p(r) = c0 + c1*r + c2*r^2 + ...  for any degree. Edit coefficients live
      (s/i for linear, a/b/c... for higher degrees, or c0/c1/... generic),
      see a table + ASCII plot of the resulting settle targets.

Run with no args for a menu. CALIBRATE moves STEERING ONLY (no motors) and
re-centers on exit. Stop the car service first so two processes don't both
drive the servo:
    sudo systemctl stop sidewalkpilot-rpi-car.service
SIMULATE/REGRESS need no hardware and run anywhere.
"""

import argparse
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame (no window)

CENTER = 90.0
SERVO_MIN = 0.0
SERVO_MAX = 180.0
TRIM_DELTA_DEG = 17.0          # active DELT center trim (applied as center trim)

RELEASE_ANGLES = [0, 15, 30, 45, 60, 75, 90]
CANDIDATE_START = 180.0
CANDIDATE_FLOOR = 90.0
CANDIDATE_STEP = 5.0
KICK_DURATION_SEC = 0.3
OBSERVE_SEC = 3.0
A_BUTTON = 0
QUIT_BUTTON = 15

DEFAULT_COEFFS = [160.0, -0.64]  # c0=intercept, c1=slope -> your starting line


# ---------------------------------------------------------------- polynomial
def poly_eval(coeffs, r):
    return sum(c * (r ** k) for k, c in enumerate(coeffs))


def settle_target(coeffs, r, clamp_left):
    """Servo target after clamping. clamp_left floors at center (no left kick)."""
    p = poly_eval(coeffs, r)
    lo = CENTER if clamp_left else SERVO_MIN
    return max(lo, min(SERVO_MAX, p))


def formula_str(coeffs):
    terms = []
    for k in range(len(coeffs) - 1, -1, -1):
        c = coeffs[k]
        if k == 0:
            terms.append(f"{c:g}")
        elif k == 1:
            terms.append(f"{c:g}*r")
        else:
            terms.append(f"{c:g}*r^{k}")
    return "p(r) = " + " + ".join(terms)


def letter_for_index(idx, degree):
    # highest power -> 'a'
    return chr(ord("a") + (degree - idx))


def index_for_letter(letter, degree):
    pos = ord(letter) - ord("a")     # 'a' = 0 = highest power
    idx = degree - pos
    return idx if 0 <= idx <= degree else None


# ---------------------------------------------------------------- regression
def polyfit(xs, ys, degree):
    """Least-squares polynomial fit via normal equations (no numpy)."""
    n = degree + 1
    if len(set(xs)) < n:
        raise ValueError(f"need at least {n} distinct r values for degree {degree}")
    A = [[sum(x ** (i + j) for x in xs) for j in range(n)] for i in range(n)]
    b = [sum(y * (x ** i) for x, y in zip(xs, ys)) for i in range(n)]
    return _gauss_solve(A, b)        # returns [c0, c1, ..., c_degree]


def _gauss_solve(A, b):
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("singular system (try a lower degree or more points)")
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for r in range(n):
            if r == col:
                continue
            f = M[r][col] / pv
            for c in range(col, n + 1):
                M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def r_squared(xs, ys, coeffs):
    mean = sum(ys) / len(ys)
    ss_tot = sum((y - mean) ** 2 for y in ys) or 1e-9
    ss_res = sum((y - poly_eval(coeffs, x)) ** 2 for x, y in zip(xs, ys))
    return 1.0 - ss_res / ss_tot


# ---------------------------------------------------------------- table/plot
def print_table(coeffs, clamp_left, step=15.0):
    print(f"\n  {formula_str(coeffs)}   clamp_left={'ON' if clamp_left else 'OFF'}")
    print("  released_r   raw p(r)   target    kick(deg)   dir")
    print("  " + "-" * 52)
    r = 0.0
    while r <= SERVO_MAX + 1e-9:
        p = poly_eval(coeffs, r)
        t = settle_target(coeffs, r, clamp_left)
        kick = t - CENTER
        d = "R" if kick > 0.5 else ("L" if kick < -0.5 else "-")
        tag = "  <- center" if abs(r - CENTER) < 1e-9 else (
            "  <- full left" if r == 0 else ("  <- full right" if r == SERVO_MAX else ""))
        print(f"   {r:6.1f}     {p:7.1f}   {t:6.1f}    {kick:+7.1f}     {d}{tag}")
        r += step


def print_plot(coeffs, clamp_left, width=56, height=17):
    xs = [SERVO_MAX * c / (width - 1) for c in range(width)]
    ys = [settle_target(coeffs, r, clamp_left) for r in xs]
    ymin, ymax = min(ys + [CENTER]), max(ys + [CENTER])
    if ymax - ymin < 1e-6:
        ymax = ymin + 1.0

    def row_for(v):
        return int(round((v - ymin) / (ymax - ymin) * (height - 1)))

    grid = [[" "] * width for _ in range(height)]
    cr = row_for(CENTER)
    if 0 <= cr < height:
        grid[height - 1 - cr] = ["."] * width
    for col, yv in enumerate(ys):
        grid[height - 1 - max(0, min(height - 1, row_for(yv)))][col] = "*"

    print("\n  target servo vs released r   (* = target, . = center 90)")
    print(f"  {ymax:6.1f} |" + "".join(grid[0]))
    for rrow in grid[1:-1]:
        print("         |" + "".join(rrow))
    print(f"  {ymin:6.1f} |" + "".join(grid[-1]))
    print("          +" + "-" * width)
    print(f"           r=0 (full left){' ' * (width - 28)}r=180 (full right)")


def print_coeffs(coeffs):
    deg = len(coeffs) - 1
    print("  " + formula_str(coeffs))
    parts = [f"{letter_for_index(k, deg)}(r^{k})={coeffs[k]:g}" for k in range(len(coeffs))]
    print("  " + ", ".join(parts))
    if deg == 1:
        print(f"  (linear aliases: s={coeffs[1]:g}, i={coeffs[0]:g})")


def show(coeffs, clamp_left):
    print_table(coeffs, clamp_left)
    print_plot(coeffs, clamp_left)


# ---------------------------------------------------------------- simulate
def simulate_repl(coeffs, clamp_left):
    coeffs = list(coeffs)
    print("\nSIMULATE. commands: deg <n> | <letter> <v> | s/i <v> | c<k> <v> | "
          "r <v> | clamp | coef | table | plot | q")
    show(coeffs, clamp_left)
    while True:
        try:
            line = input("\nsim> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return coeffs, clamp_left
        if not line:
            continue
        p = line.split()
        cmd = p[0].lower()
        deg = len(coeffs) - 1
        try:
            if cmd in ("q", "quit", "exit", "menu"):
                return coeffs, clamp_left
            elif cmd == "deg":
                new = int(p[1])
                if new < 1:
                    print("  degree must be >= 1"); continue
                coeffs = [coeffs[k] if k < len(coeffs) else 0.0 for k in range(new + 1)]
                show(coeffs, clamp_left)
            elif cmd == "clamp":
                clamp_left = not clamp_left
                print(f"  clamp_left now {'ON' if clamp_left else 'OFF'}")
                show(coeffs, clamp_left)
            elif cmd == "coef":
                print_coeffs(coeffs)
            elif cmd == "table":
                print_table(coeffs, clamp_left)
            elif cmd == "plot":
                print_plot(coeffs, clamp_left)
            elif cmd == "r" and len(p) > 1:
                rv = float(p[1])
                t = settle_target(coeffs, rv, clamp_left)
                print(f"  r={rv:.1f} -> raw p={poly_eval(coeffs, rv):.1f}  "
                      f"target={t:.1f}  kick={t - CENTER:+.1f} deg")
            elif len(p) > 1:
                val = float(p[1])
                if cmd == "s" and deg >= 1:
                    coeffs[1] = val
                elif cmd == "i":
                    coeffs[0] = val
                elif cmd.startswith("c") and cmd[1:].isdigit():
                    k = int(cmd[1:])
                    if 0 <= k <= deg:
                        coeffs[k] = val
                    else:
                        print(f"  c{k} out of range for degree {deg}"); continue
                elif len(cmd) == 1 and cmd.isalpha():
                    idx = index_for_letter(cmd, deg)
                    if idx is None:
                        print(f"  '{cmd}' not a coeff for degree {deg}"); continue
                    coeffs[idx] = val
                else:
                    print("  ? unknown command"); continue
                show(coeffs, clamp_left)
            else:
                print("  ? deg <n> | <letter> <v> | s/i <v> | c<k> <v> | r <v> | "
                      "clamp | coef | table | plot | q")
        except ValueError as exc:
            print(f"  ({exc})")


# ---------------------------------------------------------------- regress
def parse_points(text):
    pts = []
    for chunk in text.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        rs, ps = chunk.split(":")
        pts.append((float(rs), float(ps)))
    return pts


def regress_flow(points):
    if not points:
        raw = input("no collected points. enter as r:p,r:p,... (blank to cancel): ").strip()
        if not raw:
            return None
        try:
            points = parse_points(raw)
        except Exception:
            print("  could not parse points"); return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    print("  points: " + ", ".join(f"({x:g},{y:g})" for x, y in points))
    try:
        deg = int(input("degree (1=lin 2=quad 3=cub 4=quart ...): ").strip())
    except ValueError:
        print("  not a number"); return None
    try:
        coeffs = polyfit(xs, ys, deg)
    except ValueError as exc:
        print(f"  fit failed: {exc}"); return None
    print(f"\n  fit: {formula_str(coeffs)}")
    print_coeffs(coeffs)
    print(f"  R^2 = {r_squared(xs, ys, coeffs):.5f}")
    if input("load this into the simulator? (y/n): ").strip().lower().startswith("y"):
        return coeffs
    return None


# ---------------------------------------------------------------- calibrate
def calibrate():
    """Hardware sweep on the Pi. Returns list of (r, pushback) points."""
    try:
        import pygame
    except Exception as exc:
        print(f"pygame unavailable (Pi only): {exc}")
        return []
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "controller" / "current"))
    try:
        from rc_car_app.config import (
            PCA9685_FREQUENCY_HZ, PCA9685_I2C_ADDRESS, PCA9685_SERVO_CHANNEL,
            STEERING_SERVO_ACTUATION_RANGE_DEG, STEERING_SERVO_MAX_PULSE_US,
            STEERING_SERVO_MIN_PULSE_US,
        )
        from rc_car_app.hardware import PCA9685SteeringServo
    except Exception as exc:
        print(f"steering hardware unavailable (Pi only): {exc}")
        return []

    center_offset = TRIM_DELTA_DEG / (float(STEERING_SERVO_ACTUATION_RANGE_DEG) / 2.0)
    try:
        servo = PCA9685SteeringServo(
            channel=PCA9685_SERVO_CHANNEL, address=PCA9685_I2C_ADDRESS,
            frequency_hz=PCA9685_FREQUENCY_HZ, min_pulse_us=STEERING_SERVO_MIN_PULSE_US,
            max_pulse_us=STEERING_SERVO_MAX_PULSE_US,
            actuation_range_deg=STEERING_SERVO_ACTUATION_RANGE_DEG,
            center_offset=center_offset, center_preload=0.0, center_preload_window=0.0,
        )
    except Exception as exc:
        print(f"could not init steering servo (is the car service stopped?): {exc}")
        return []

    pygame.display.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("No joystick detected. Plug in the Xbox controller.")
        servo.value = CENTER
        return []
    js = pygame.joystick.Joystick(0)
    js.init()
    print(f"Joystick: {js.get_name()}   (A=save & next, Share=quit)")

    def pressed(btn):
        return js.get_numbuttons() > btn and bool(js.get_button(btn))

    def wait(seconds):
        end = time.time() + seconds
        while time.time() < end:
            pygame.event.pump()
            if pressed(QUIT_BUTTON):
                return "quit"
            if pressed(A_BUTTON):
                while pressed(A_BUTTON):       # debounce release
                    pygame.event.pump(); time.sleep(0.02)
                return "save"
            time.sleep(0.02)
        return "timeout"

    points = []
    try:
        for r in RELEASE_ANGLES:
            if r >= CENTER:                    # released straight -> no pushback
                points.append((float(r), CENTER))
                print(f"r={r:.0f}  -> {CENTER:.0f} (straight, auto)")
                continue
            print(f"\n=== release r={r:.0f}  (A=lock current, Share=quit) ===")
            saved = None
            cand = CANDIDATE_START
            while cand >= CANDIDATE_FLOOR - 1e-9:
                print(f"  r={r:.0f}   L{cand:.0f}:{KICK_DURATION_SEC} +{TRIM_DELTA_DEG:.0f}D")
                servo.value = CENTER; time.sleep(0.15)
                servo.value = float(r); time.sleep(0.40)      # go to release position
                servo.value = cand; time.sleep(KICK_DURATION_SEC)  # the pushback kick
                servo.value = CENTER                          # return; observe if straight
                act = wait(OBSERVE_SEC)
                if act == "quit":
                    raise KeyboardInterrupt
                if act == "save":
                    saved = cand
                    break
                cand -= CANDIDATE_STEP
            if saved is None:
                saved = CENTER
            points.append((float(r), float(saved)))
            print(f"  -> locked (r={r:.0f}, pushback={saved:.0f})")
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        try:
            servo.value = CENTER
            servo.close()
        except Exception:
            pass
        try:
            pygame.quit()
        except Exception:
            pass

    if points:
        print("\ncollected points (r:pushback):")
        print("  " + ", ".join(f"{int(r)}:{int(p)}" for r, p in points))
    return points


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Steering pushback curve tool")
    ap.add_argument("--calibrate", action="store_true", help="run the Pi hardware sweep")
    ap.add_argument("--once", action="store_true", help="print sim table+plot and exit")
    ap.add_argument("-s", "--slope", type=float, default=-0.64, help="linear slope (sim --once)")
    ap.add_argument("-i", "--intercept", type=float, default=160.0, help="linear intercept (sim --once)")
    ap.add_argument("--no-clamp", action="store_true", help="allow left kicks (no center floor)")
    args = ap.parse_args()

    clamp_left = not args.no_clamp
    coeffs = list(DEFAULT_COEFFS)
    points = []

    if args.once:
        show([args.intercept, args.slope], clamp_left)
        return
    if args.calibrate:
        points = calibrate()
        if points and input("\nfit a regression now? (y/n): ").strip().lower().startswith("y"):
            new = regress_flow(points)
            if new:
                simulate_repl(new, clamp_left)
        return

    while True:
        try:
            choice = input("\n[c]alibrate (Pi)  [r]egress  [s]imulate  [q]uit > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice.startswith("c"):
            points = calibrate() or points
        elif choice.startswith("r"):
            new = regress_flow(points)
            if new:
                coeffs = new
        elif choice.startswith("s"):
            coeffs, clamp_left = simulate_repl(coeffs, clamp_left)
        elif choice.startswith("q"):
            return


if __name__ == "__main__":
    main()
