#!/usr/bin/env python3
"""Steering settle "pushback" curve simulator (offline, no hardware).

Models the proposed proportional settle:

    p(r) = s * r + i

where
    r = released steering value (logical servo angle you let go from;
        0 = full left, 90 = center, 180 = full right)
    p = pushback = the servo target the settle kicks to, held briefly,
        then released back to 90 (center)
    s = slope      -> how pushback changes per degree of released value
                      (negative => more-left releases get MORE right pushback)
    i = intercept  -> pushback when r = 0 (released from full left)

Use it to tune s and i in the shell BEFORE touching the live runtime:

    # one-shot (print table + plot for given values, then exit):
    python3 pushback_curve_sim.py -s -0.64 -i 160

    # interactive REPL (edit values live):
    python3 pushback_curve_sim.py
        s -0.5        set slope
        i 150         set intercept
        r 30          pushback for a single released value
        clamp         toggle "never kick left" (target floored at 90)
        table         reprint the table
        plot          reprint the ASCII plot
        q             quit

Nothing here writes to hardware, the dashboard, or steering_tune.json. When the
curve looks right, tell the values to wire into the runtime settle.
"""

import argparse

CENTER = 90.0          # logical center
SERVO_MIN = 0.0
SERVO_MAX = 180.0


def pushback(r: float, s: float, i: float) -> float:
    """Raw curve value p(r) = s*r + i (unclamped)."""
    return s * r + i


def target(r: float, s: float, i: float, clamp_left: bool) -> float:
    """Servo target after clamping to the valid range.

    clamp_left=True floors the target at CENTER so right-side releases never
    produce a leftward kick (hysteresis is a left-return problem)."""
    p = pushback(r, s, i)
    lo = CENTER if clamp_left else SERVO_MIN
    return max(lo, min(SERVO_MAX, p))


def zero_kick_r(s: float, i: float):
    """Released value where the target equals center (no kick). None if flat."""
    if s == 0:
        return None
    return (CENTER - i) / s


def print_table(s: float, i: float, clamp_left: bool, step: float = 15.0):
    print(f"\n  p(r) = {s:g}*r + {i:g}   clamp_left={'ON' if clamp_left else 'OFF'}")
    print("  released_r   raw p(r)   target    kick(deg)   dir")
    print("  " + "-" * 52)
    r = 0.0
    while r <= SERVO_MAX + 1e-9:
        p = pushback(r, s, i)
        t = target(r, s, i, clamp_left)
        kick = t - CENTER
        direction = "R" if kick > 0.5 else ("L" if kick < -0.5 else "-")
        tag = ""
        if abs(r - CENTER) < 1e-9:
            tag = "  <- center"
        elif r == 0.0:
            tag = "  <- full left"
        elif r == SERVO_MAX:
            tag = "  <- full right"
        print(f"   {r:6.1f}     {p:7.1f}   {t:6.1f}    {kick:+7.1f}     {direction}{tag}")
        r += step
    zk = zero_kick_r(s, i)
    if zk is not None:
        print(f"\n  zero-kick release value: r = {zk:.1f}  "
              f"(releases left of this get a right kick)")
    print(f"  full-left target: {target(0, s, i, clamp_left):.1f}    "
          f"center-release target: {target(CENTER, s, i, clamp_left):.1f}")


def print_plot(s: float, i: float, clamp_left: bool, width: int = 56, height: int = 17):
    """ASCII plot of target (y) vs released value r (x, 0..180)."""
    xs = [SERVO_MAX * c / (width - 1) for c in range(width)]
    ys = [target(r, s, i, clamp_left) for r in xs]
    ymin, ymax = min(ys + [CENTER]), max(ys + [CENTER])
    if ymax - ymin < 1e-6:
        ymax = ymin + 1.0

    def row_for(val):
        return int(round((val - ymin) / (ymax - ymin) * (height - 1)))

    grid = [[" "] * width for _ in range(height)]
    center_row = row_for(CENTER)
    if 0 <= center_row < height:
        grid[height - 1 - center_row] = ["."] * width  # center reference line
    for col, yv in enumerate(ys):
        row = row_for(yv)
        row = max(0, min(height - 1, row))
        grid[height - 1 - row][col] = "*"

    print("\n  target servo vs released r   (* = target, . = center 90)")
    print(f"  {ymax:6.1f} |" + "".join(grid[0]))
    for rrow in grid[1:-1]:
        print("         |" + "".join(rrow))
    print(f"  {ymin:6.1f} |" + "".join(grid[-1]))
    print("          +" + "-" * width)
    print(f"           r=0 (full left){' ' * (width - 28)}r=180 (full right)")


def show(s, i, clamp_left):
    print_table(s, i, clamp_left)
    print_plot(s, i, clamp_left)


def repl(s, i, clamp_left):
    print("Interactive pushback sim. Commands: s <v> | i <v> | r <v> | "
          "clamp | table | plot | q")
    show(s, i, clamp_left)
    while True:
        try:
            line = input("\npush> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()
        try:
            if cmd in ("q", "quit", "exit"):
                return
            elif cmd == "s" and len(parts) > 1:
                s = float(parts[1]); show(s, i, clamp_left)
            elif cmd == "i" and len(parts) > 1:
                i = float(parts[1]); show(s, i, clamp_left)
            elif cmd == "r" and len(parts) > 1:
                rv = float(parts[1])
                t = target(rv, s, i, clamp_left)
                print(f"  r={rv:.1f} -> raw p={pushback(rv, s, i):.1f}  "
                      f"target={t:.1f}  kick={t - CENTER:+.1f} deg")
            elif cmd == "clamp":
                clamp_left = not clamp_left
                print(f"  clamp_left now {'ON' if clamp_left else 'OFF'}")
                show(s, i, clamp_left)
            elif cmd == "table":
                print_table(s, i, clamp_left)
            elif cmd == "plot":
                print_plot(s, i, clamp_left)
            else:
                print("  ? commands: s <v> | i <v> | r <v> | clamp | table | plot | q")
        except ValueError:
            print("  (need a number, e.g. 's -0.5')")


def main():
    ap = argparse.ArgumentParser(description="Steering settle pushback curve simulator")
    ap.add_argument("-s", "--slope", type=float, default=-0.64,
                    help="slope s in p(r)=s*r+i (default -0.64)")
    ap.add_argument("-i", "--intercept", type=float, default=160.0,
                    help="intercept i = pushback at r=0 (default 160)")
    ap.add_argument("--no-clamp", action="store_true",
                    help="allow targets below center (let right releases kick left)")
    ap.add_argument("--once", action="store_true",
                    help="print table+plot for the given values and exit (no REPL)")
    args = ap.parse_args()
    clamp_left = not args.no_clamp
    if args.once:
        show(args.slope, args.intercept, clamp_left)
    else:
        repl(args.slope, args.intercept, clamp_left)


if __name__ == "__main__":
    main()
