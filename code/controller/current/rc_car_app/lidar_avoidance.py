"""lidar_avoidance.py -- autonomous LiDAR obstacle avoidance.

Validated offline in test_files/lidar_avoidance_sim.py; this is the production port.

Two ideas:
  * FORWARD CONE (+/-LIDAR_FORWARD_CONE_DEG) decides brake/stop + feeds the throttle governor.
    The side wedges (cone..NEAR_ANGLE) only decide whether there's room to swerve, so hedges/
    fences running ALONGSIDE the path never trigger a brake.
  * Classify the near forward object:
      EMERGENCY  (anything < emergency stop)         -> hard stop
      PERSON     (two narrow leg clusters)           -> full stop, hold  (never swerve off sidewalk)
      WALL       (one wide arc)                      -> full stop, hold
      MAILBOX    (narrow, off-center) + a clear side -> swerve AWAY, proportional 20..80 deg
      (boxed in: narrow but no clear side)           -> full stop, hold
      CLEAR      (nothing near)                      -> follow the model
  Throttle is governed by forward clearance: full at/above GOV_FULL, ramps down to MIN_MOVE,
  then 0 at/below GOV_STOP. The runtime's existing ACCEL_RATE motor ramp handles the smooth
  resume, so we just return the target here.

evaluate(scan) -> dict the caller applies:
  code   : "" (clear) | "SWR" (swerve) | "HLD" (person/wall/boxed stop) | "EMR" (emergency)
  stop   : True -> hard stop (throttle 0, brake)
  steer  : logical servo degrees to command (only for SWR); else None
  throttle: governor target (0..CRUISE)
  front_m: forward clearance used
  reason : stop_reason string for the log/dashboard
"""
from . import config as C

_MAX_RANGE_M = 12.0
_CENTER_DEG = C.STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0


def _valid(p):
    return (getattr(p, "is_valid", False)
            and getattr(p, "distance_mm", 0) > 0
            and getattr(p, "confidence", 0) >= C.LIDAR_MIN_CONFIDENCE)


def _norm_angle(p):
    a = float(getattr(p, "angle_deg", 0.0))
    return a - 360.0 if a > 180.0 else a


def _forward_and_wedges(scan):
    """(forward_cone_min_m, left_wedge_min_m, right_wedge_min_m). Empty scan -> all clear."""
    fwd = left = right = _MAX_RANGE_M
    for p in scan or []:
        if not _valid(p):
            continue
        a = _norm_angle(p)
        d = p.distance_mm / 1000.0
        if abs(a) <= C.LIDAR_FORWARD_CONE_DEG:
            fwd = min(fwd, d)
        elif -C.LIDAR_NEAR_ANGLE_DEG <= a < -C.LIDAR_FORWARD_CONE_DEG:
            left = min(left, d)
        elif C.LIDAR_FORWARD_CONE_DEG < a <= C.LIDAR_NEAR_ANGLE_DEG:
            right = min(right, d)
    return fwd, left, right


def _forward_clusters(scan):
    """Cluster the near (<= WARN) forward-cone points by angular gap."""
    pts = []
    for p in scan or []:
        if not _valid(p):
            continue
        a = _norm_angle(p)
        if abs(a) > C.LIDAR_FORWARD_CONE_DEG:
            continue
        d = p.distance_mm / 1000.0
        if d <= C.LIDAR_WARN_M:
            pts.append((a, d))
    pts.sort()
    clusters, cur = [], []
    for a, d in pts:
        if cur and a - cur[-1][0] > C.LIDAR_CLUSTER_GAP_DEG:
            clusters.append(cur)
            cur = []
        cur.append((a, d))
    if cur:
        clusters.append(cur)
    out = []
    for c in clusters:
        ang = [a for a, _ in c]
        dd = [d for _, d in c]
        span_deg = max(ang) - min(ang)
        min_d = min(dd)
        out.append({"width": span_deg, "centre": sum(ang) / len(ang), "min_d": min_d,
                    # physical width (chord) — distance-invariant so a close mailbox isn't a "wall"
                    "width_m": 2.0 * min_d * math.sin(math.radians(span_deg) / 2.0)})
    return out


def governor_target(front_m):
    """Steady-state throttle for a forward clearance; the runtime ramps toward it at ACCEL_RATE."""
    if front_m <= C.LIDAR_GOV_STOP_M:
        return 0.0
    if front_m >= C.LIDAR_GOV_FULL_M:
        return C.AUTONOMOUS_CRUISE_PWM
    frac = (front_m - C.LIDAR_GOV_STOP_M) / (C.LIDAR_GOV_FULL_M - C.LIDAR_GOV_STOP_M)
    return C.LIDAR_MIN_MOVE_PWM + frac * (C.AUTONOMOUS_CRUISE_PWM - C.LIDAR_MIN_MOVE_PWM)


def _swerve_offset(front_m):
    """Off-center swerve angle: gentle far (SWERVE_MIN), sharp close (SWERVE_MAX)."""
    span = max(1e-6, C.LIDAR_WARN_M - C.LIDAR_GOV_STOP_M)
    frac = max(0.0, min(1.0, (front_m - C.LIDAR_GOV_STOP_M) / span))   # 1 far, 0 close
    return C.LIDAR_SWERVE_MIN_DEG + (1.0 - frac) * (C.LIDAR_SWERVE_MAX_DEG - C.LIDAR_SWERVE_MIN_DEG)


def evaluate(scan):
    fwd, left_m, right_m = _forward_and_wedges(scan)

    if fwd < C.LIDAR_OVERRIDE_EMERGENCY_STOP_M:
        return {"code": "EMR", "stop": True, "steer": None, "throttle": 0.0,
                "front_m": fwd, "reason": "lidar_emergency"}

    clusters = _forward_clusters(scan)
    if not clusters:
        return {"code": "", "stop": False, "steer": None, "throttle": governor_target(fwd),
                "front_m": fwd, "reason": ""}                       # CLEAR -> follow model

    front_m = min(c["min_d"] for c in clusters)

    person = False
    if len(clusters) == 2:
        a, b = clusters
        person = (abs(a["centre"] - b["centre"]) <= C.LIDAR_LEG_GAP_MAX_DEG
                  and abs(a["min_d"] - b["min_d"]) <= C.LIDAR_LEG_RANGE_TOL_M
                  and a["width"] < C.LIDAR_NARROW_MAX_DEG and b["width"] < C.LIDAR_NARROW_MAX_DEG)
    widest = max(clusters, key=lambda c: c["width_m"])
    if person or widest["width_m"] >= C.LIDAR_WALL_MIN_WIDTH_M:      # PHYSICAL width, not angular
        return {"code": "HLD", "stop": True, "steer": None, "throttle": 0.0,
                "front_m": front_m, "reason": "lidar_hold"}         # person/wall -> full stop

    # MAILBOX: swerve AWAY from the object, toward a clear side
    left_clear = left_m >= C.LIDAR_AVOID_SIDE_CLEAR_M
    right_clear = right_m >= C.LIDAR_AVOID_SIDE_CLEAR_M
    away = "left" if widest["centre"] >= 0.0 else "right"
    off = _swerve_offset(front_m)
    if away == "left" and left_clear:
        steer = _CENTER_DEG - off
    elif away == "right" and right_clear:
        steer = _CENTER_DEG + off
    elif away == "left" and right_clear:
        steer = _CENTER_DEG + off
    elif away == "right" and left_clear:
        steer = _CENTER_DEG - off
    else:
        return {"code": "HLD", "stop": True, "steer": None, "throttle": 0.0,
                "front_m": front_m, "reason": "lidar_boxed"}        # no room -> full stop
    # A mailbox/post is narrow -> clear it with the swerve. Gentle (far) swerve = full throttle
    # (matches the old basic-swerve behavior); sharper (closer) swerves shed a little throttle.
    off_frac = (off - C.LIDAR_SWERVE_MIN_DEG) / max(1e-6, C.LIDAR_SWERVE_MAX_DEG - C.LIDAR_SWERVE_MIN_DEG)
    swerve_throttle = max(C.LIDAR_MIN_MOVE_PWM,
                          C.AUTONOMOUS_CRUISE_PWM - off_frac * C.LIDAR_SWERVE_THROTTLE_DROP)
    return {"code": "SWR", "stop": False, "steer": steer, "throttle": swerve_throttle,
            "front_m": front_m, "reason": "lidar_override"}
