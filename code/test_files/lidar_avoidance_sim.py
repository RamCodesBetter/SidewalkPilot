#!/usr/bin/env python3
"""lidar_avoidance_sim.py -- OFFLINE prototype for smarter LiDAR obstacle handling.

This is a bench prototype ONLY. It touches no hardware and no runtime code. It exists
so we can tune the new autonomous-avoidance behaviour on synthetic LiDAR scans BEFORE
any of it goes near the live control loop (motors + a real sidewalk + real people).

Two behaviours are prototyped here, matching the two field problems:

  A) PROPORTIONAL THROTTLE GOVERNOR ("controlled throttle from LiDAR")
     Today autonomous throttle is binary: full speed (1.0) until an obstacle enters the
     warn ring, then a cliff to 0.5 (swerve) or 0.0 (stop). That approaches people too
     fast and resumes with a full-throttle jump. The governor instead scales throttle
     smoothly with forward clearance, and RATE-LIMITS the resume so it eases back up
     instead of snapping to 1.0. Braking is immediate (safety); only speeding up is
     rate-limited.

  B) PERSON / WIDE-OBSTACLE DETECTION (brake instead of swerving off the sidewalk)
     The live swerve only checks "is a side >= 0.75 m clear?" -- it is sidewalk-blind, so
     a person filling the sidewalk (with grass/road beside them) makes the car swerve OFF
     the sidewalk. A person shows on LiDAR as TWO leg clusters (two dots / two short arcs),
     not one solid wall. This classifier clusters the near returns and calls it:
       - CLEAR        : no near returns            -> follow the model, governed throttle
       - MAILBOX      : one narrow cluster         -> swerve (today's behaviour, kept)
       - PERSON/WIDE  : two close leg clusters, OR
                        one wide solid arc         -> BRAKE + hold, do NOT swerve off
     When it brakes, the governor ramps throttle back up once the path clears.

Thresholds mirror rc_car_app/config.py so the numbers transfer to the runtime later.

Usage:
  python3 lidar_avoidance_sim.py                 # run all synthetic scenarios
  python3 lidar_avoidance_sim.py --csv run.csv --col "LiDAR Front Distance (m)"   # governor on a real front-distance trace
"""
import argparse
import csv as _csv

# --- thresholds mirrored from rc_car_app/config.py --------------------------
WARN_M = 1.2                 # lidar_warn_threshold_m: below this we react
SIDE_CLEAR_M = 0.75          # LIDAR_OVERRIDE_SIDE_CLEARANCE_M: side must be this clear to swerve
EMERGENCY_STOP_M = 0.35      # LIDAR_OVERRIDE_EMERGENCY_STOP_M: untouchable hard-stop line
CRUISE_PWM = 1.0             # AUTONOMOUS_CRUISE_PWM

# --- governor tuning (A) ----------------------------------------------------
GOV_FULL_M = 2.5             # at/above this forward clearance -> full cruise throttle
GOV_STOP_M = 0.60            # at/below this -> throttle 0 (soft stop, above the 0.35 emergency)
RESUME_RAMP_PER_FRAME = 0.05 # max throttle INCREASE per frame (ease back up); braking is instant

# --- classifier tuning (B) --------------------------------------------------
NEAR_ANGLE_DEG = 75.0        # only points within +/- this arc count as "ahead"
CLUSTER_GAP_DEG = 8.0        # angular gap that splits one cluster from the next (splits legs apart)
NARROW_MAX_DEG = 15.0        # a cluster narrower than this is a post/mailbox (swervable)
WIDE_MIN_DEG = 18.0          # a single cluster wider than this is a wall/person (brake)
LEG_GAP_MAX_DEG = 45.0       # two clusters whose centres are within this = a person's legs
LEG_RANGE_TOL_M = 0.40       # ...and whose ranges match within this = same person
MIN_CONFIDENCE = 150         # matches the runtime confidence gate


class Pt:
    """Mirrors rc_car_app.lidar.LidarPoint's fields used by the runtime filters."""
    def __init__(self, angle_deg, distance_m, confidence=200):
        self.angle_deg = angle_deg
        self.distance_mm = distance_m * 1000.0
        self.confidence = confidence
        self.is_valid = distance_m > 0


# ---------------------------------------------------------------------------
# A) throttle governor
# ---------------------------------------------------------------------------
def governor_target(front_clear_m):
    """Steady-state throttle for a given forward clearance (before rate-limiting)."""
    if front_clear_m <= GOV_STOP_M:
        return 0.0
    if front_clear_m >= GOV_FULL_M:
        return CRUISE_PWM
    frac = (front_clear_m - GOV_STOP_M) / (GOV_FULL_M - GOV_STOP_M)
    return round(CRUISE_PWM * frac, 3)


def governed_throttle(front_clear_m, prev_throttle):
    """Apply the governor with an asymmetric rate limit: brake instantly, resume slowly."""
    target = governor_target(front_clear_m)
    if target >= prev_throttle:                       # speeding up -> ease in
        return round(min(target, prev_throttle + RESUME_RAMP_PER_FRAME), 3)
    return target                                     # slowing down -> immediate


# ---------------------------------------------------------------------------
# B) obstacle classifier
# ---------------------------------------------------------------------------
def _near_points(scan):
    pts = []
    for p in scan or []:
        if not getattr(p, "is_valid", False) or p.distance_mm <= 0 or p.confidence < MIN_CONFIDENCE:
            continue
        a = p.angle_deg
        if a > 180.0:
            a -= 360.0
        if abs(a) > NEAR_ANGLE_DEG:
            continue
        d = p.distance_mm / 1000.0
        if d <= WARN_M:
            pts.append((a, d))
    return sorted(pts)


def _cluster(pts):
    """Split angle-sorted near points into clusters wherever the angular gap is large."""
    clusters, cur = [], []
    for a, d in pts:
        if cur and a - cur[-1][0] > CLUSTER_GAP_DEG:
            clusters.append(cur)
            cur = []
        cur.append((a, d))
    if cur:
        clusters.append(cur)
    out = []
    for c in clusters:
        angles = [a for a, _ in c]
        dists = [d for _, d in c]
        out.append({
            "width_deg": max(angles) - min(angles),
            "centre_deg": sum(angles) / len(angles),
            "min_dist_m": min(dists),
            "n": len(c),
        })
    return out


def classify(scan):
    """Return (label, detail) where label in {CLEAR, MAILBOX, PERSON, WALL, EMERGENCY}."""
    pts = _near_points(scan)
    if not pts:
        return "CLEAR", {"front_m": GOV_FULL_M}   # nothing in the warn ring -> open path
    front_m = min(d for _, d in pts)
    if front_m < EMERGENCY_STOP_M:
        return "EMERGENCY", {"front_m": front_m}

    clusters = _cluster(pts)

    # two close, similar-range clusters straddling ahead = a person's legs
    if len(clusters) == 2:
        a, b = clusters
        gap = abs(a["centre_deg"] - b["centre_deg"])
        range_match = abs(a["min_dist_m"] - b["min_dist_m"]) <= LEG_RANGE_TOL_M
        both_narrow = a["width_deg"] < NARROW_MAX_DEG and b["width_deg"] < NARROW_MAX_DEG
        if gap <= LEG_GAP_MAX_DEG and range_match and both_narrow:
            return "PERSON", {"front_m": front_m, "leg_gap_deg": round(gap, 1),
                              "legs": [round(a["centre_deg"], 1), round(b["centre_deg"], 1)]}

    # one wide solid arc = wall / hedge / broadside person
    widest = max(clusters, key=lambda c: c["width_deg"])
    if widest["width_deg"] >= WIDE_MIN_DEG:
        return "WALL", {"front_m": front_m, "width_deg": round(widest["width_deg"], 1)}

    # otherwise a narrow object (post/mailbox) -> swervable
    return "MAILBOX", {"front_m": front_m, "centre_deg": round(widest["centre_deg"], 1),
                       "width_deg": round(widest["width_deg"], 1)}


def decide(scan, left_dist_m, right_dist_m, prev_throttle):
    """Combine classifier + governor into an action, and contrast with today's logic."""
    label, detail = classify(scan)
    front_m = detail["front_m"]
    left_clear = left_dist_m >= SIDE_CLEAR_M
    right_clear = right_dist_m >= SIDE_CLEAR_M

    # today's runtime: any side clear -> swerve, else stop (sidewalk-blind)
    if label == "EMERGENCY":
        old = "HARD STOP"
    elif front_m < WARN_M:
        old = "SWERVE" if (left_clear or right_clear) else "HARD STOP"
    else:
        old = "FOLLOW MODEL"

    # new logic
    if label == "EMERGENCY":
        new, thr = "HARD STOP", 0.0
    elif label == "CLEAR":
        new, thr = "FOLLOW MODEL", governed_throttle(front_m, prev_throttle)
    elif label == "MAILBOX":
        side = "right" if right_clear else ("left" if left_clear else None)
        if side:
            new, thr = f"SWERVE {side}", governed_throttle(front_m, prev_throttle)
        else:
            new, thr = "BRAKE + HOLD", governed_throttle(front_m, prev_throttle)
    else:  # PERSON or WALL -> never swerve off the sidewalk
        new, thr = "BRAKE + HOLD", governed_throttle(front_m, prev_throttle)
    return label, detail, old, new, thr


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------
def arc(centre_deg, half_width_deg, dist_m, step=3.0):
    """A short arc of returns (a solid object spanning an angular width)."""
    pts, a = [], centre_deg - half_width_deg
    while a <= centre_deg + half_width_deg + 1e-9:
        pts.append(Pt(a, dist_m))
        a += step
    return pts


def scenarios():
    return [
        ("clear path", [], 3.0, 3.0),
        ("mailbox on right, left clear", arc(30, 4, 0.9), 2.0, 0.9),
        ("person (two legs) ahead, grass on both sides",
         arc(-9, 3, 1.0) + arc(9, 3, 1.0), 0.85, 0.85),
        ("hedge/wall broadside, sides open", arc(0, 22, 0.9), 0.8, 0.8),
        ("person very close (emergency)", arc(-6, 3, 0.30) + arc(7, 3, 0.31), 0.9, 0.9),
        ("narrow post dead ahead, both sides clear", arc(0, 5, 1.0), 1.5, 1.5),
    ]


def run_scenarios():
    print("Prototype LiDAR avoidance -- synthetic scenarios\n")
    print(f"{'scenario':<44} {'class':<9} {'front':>6}  {'OLD':<12} -> {'NEW':<14} {'thr':>5}")
    print("-" * 100)
    prev = 1.0
    for name, scan, left, right in scenarios():
        label, detail, old, new, thr = decide(scan, left, right, prev)
        print(f"{name:<44} {label:<9} {detail['front_m']:>5.2f}m  {old:<12} -> {new:<14} {thr:>5.2f}")
    print("-" * 100)
    print("OLD swerves off the sidewalk for the person (a side is 'clear' = grass); "
          "NEW brakes and holds, then the governor ramps throttle back when they move.\n")


def run_csv(path, col):
    """Replay the throttle governor over a real forward-distance trace from a run CSV."""
    vals = []
    with open(path) as f:
        for row in _csv.DictReader(f):
            try:
                vals.append(float(row[col]))
            except (KeyError, ValueError, TypeError):
                pass
    if not vals:
        raise SystemExit(f"no numeric values in column '{col}' of {path}")
    print(f"governor replay over {len(vals)} frames of '{col}' from {path}\n")
    print(f"{'frame':>6} {'front_m':>8} {'target':>8} {'governed':>9}")
    prev = 0.0
    for i, d in enumerate(vals):
        g = governed_throttle(d, prev)
        if i < 20 or i % max(1, len(vals) // 20) == 0:
            print(f"{i:>6} {d:>8.2f} {governor_target(d):>8.2f} {g:>9.2f}")
        prev = g
    print("\n(target = instantaneous governor; governed = after resume rate-limit)")


def main():
    ap = argparse.ArgumentParser(description="Offline prototype for LiDAR throttle governor + person detection.")
    ap.add_argument("--csv", help="run CSV to replay the throttle governor over a forward-distance column")
    ap.add_argument("--col", default="LiDAR Front Distance (m)", help="forward-distance column name in --csv")
    a = ap.parse_args()
    if a.csv:
        run_csv(a.csv, a.col)
    else:
        run_scenarios()


if __name__ == "__main__":
    main()
