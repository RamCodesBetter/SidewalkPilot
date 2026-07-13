"""lidar_avoidance.py -- autonomous LiDAR obstacle avoidance.

Validated offline in test_files/lidar_avoidance_sim.py; this is the production port.

Two ideas:
  * FORWARD CONE (+/-LIDAR_FORWARD_CONE_DEG) decides brake/stop + feeds the throttle governor.
    The side wedges (cone..NEAR_ANGLE) only decide whether there's room to swerve, so hedges/
    fences running ALONGSIDE the path never trigger a brake.
  * Classify the near forward object:
      EMERGENCY  (anything < emergency stop)         -> L/R lane policy or hard stop
      PERSON     (two narrow leg clusters)           -> full stop outside emergency lane handling
      WALL       (one wide arc)                      -> full stop, hold
      MAILBOX    (narrow, off-center) + a clear side -> swerve AWAY, proportional 20..80 deg
      (boxed in: narrow but no clear side)           -> full stop, hold
      CLEAR      (nothing near)                      -> follow the model
  Throttle is governed by forward clearance: full at/above GOV_FULL, ramps down to MIN_MOVE,
  then 0 at/below GOV_STOP. The runtime's existing ACCEL_RATE motor ramp handles the smooth
  resume, so we just return the target here.

evaluate(scan) -> dict the caller applies:
  code   : "" (clear) | "SWR" (swerve) | "CRP" (center creep) | "HLD" (hold) | "EMR" (emergency)
  stop   : True -> hard stop (throttle 0, brake)
  steer  : logical servo degrees to command for SWR/CRP; else None
  throttle: governor target (0..CRUISE)
  front_m: forward clearance used
  reason : stop_reason string for the log/dashboard
  lane_occupancy / emergency_lane_occupancy / lane_action: dashboard + debug metadata
"""
import math

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
    """(forward_corridor_min_m, left_wedge_min_m, right_wedge_min_m). Empty scan -> all clear.

    FORWARD blocking uses a LATERAL SIDEWALK CORRIDOR (the two dashboard blue lines), not an
    angular cone: a point blocks only if it's AHEAD and within +/-CORRIDOR_HALF_WIDTH_M laterally,
    scored by its FORWARD distance. Points past the sidewalk edge (alongside hedges/fences) are
    ignored no matter how close in angle -> no more braking for edge hedges at distance."""
    fwd = left = right = _MAX_RANGE_M
    hw = C.LIDAR_CORRIDOR_HALF_WIDTH_M
    for p in scan or []:
        if not _valid(p):
            continue
        a = _norm_angle(p)
        d = p.distance_mm / 1000.0
        ar = math.radians(a)
        x = d * math.sin(ar)                      # lateral offset (right +, left -)
        f = d * math.cos(ar)                      # forward distance
        if f > 0.0 and abs(x) <= hw:
            fwd = min(fwd, f)                     # inside the sidewalk corridor ahead -> can block
        elif abs(a) <= C.LIDAR_NEAR_ANGLE_DEG:    # outside corridor but within the fan -> swerve room
            if a < 0.0:
                left = min(left, d)
            else:
                right = min(right, d)
    return fwd, left, right


def _forward_clusters(scan):
    """Cluster the near (<= WARN) points that lie inside the forward SIDEWALK CORRIDOR."""
    pts = []
    hw = C.LIDAR_CORRIDOR_HALF_WIDTH_M
    for p in scan or []:
        if not _valid(p):
            continue
        a = _norm_angle(p)
        d = p.distance_mm / 1000.0
        ar = math.radians(a)
        if not (d * math.cos(ar) > 0.0 and abs(d * math.sin(ar)) <= hw):
            continue                              # only points inside the sidewalk corridor ahead
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


def _person_or_wall(clusters):
    """True if the near clusters look like a PERSON (two matched narrow leg clusters) or a WALL
    (one physically wide arc). These NEVER swerve -- always a full stop, in the emergency zone too."""
    if not clusters:
        return False
    person = False
    if len(clusters) == 2:
        a, b = clusters
        person = (abs(a["centre"] - b["centre"]) <= C.LIDAR_LEG_GAP_MAX_DEG
                  and abs(a["min_d"] - b["min_d"]) <= C.LIDAR_LEG_RANGE_TOL_M
                  and a["width"] < C.LIDAR_NARROW_MAX_DEG and b["width"] < C.LIDAR_NARROW_MAX_DEG)
    widest = max(clusters, key=lambda c: c["width_m"])
    return person or widest["width_m"] >= C.LIDAR_WALL_MIN_WIDTH_M


def lane_occupancy(scan, max_forward_m):
    """Return the occupied equal-width corridor lanes in canonical L/C/R order."""
    hw = C.LIDAR_CORRIDOR_HALF_WIDTH_M
    lane_half = hw / C.LIDAR_LANE_COUNT
    occupied = set()
    for p in scan or []:
        if not _valid(p):
            continue
        a = _norm_angle(p)
        d = p.distance_mm / 1000.0
        ar = math.radians(a)
        x = d * math.sin(ar)                          # lateral offset (right +, left -)
        f = d * math.cos(ar)                          # forward distance
        if f <= 0.0 or f > max_forward_m or abs(x) > hw:
            continue
        if x < -lane_half:
            occupied.add("L")
        elif x > lane_half:
            occupied.add("R")
        else:
            occupied.add("C")
    return "".join(lane for lane in "LCR" if lane in occupied)


def _result(code, stop, steer, throttle, front_m, reason, occupancy, action,
            emergency_occupancy=""):
    return {
        "code": code,
        "stop": stop,
        "steer": steer,
        "throttle": throttle,
        "front_m": front_m,
        "reason": reason,
        "lane_occupancy": occupancy,
        "emergency_lane_occupancy": emergency_occupancy,
        "lane_action": action,
    }


def _emergency_lane_decision(fwd, occupancy, display_occupancy):
    """Apply the fail-closed emergency L/C/R truth table."""
    if not C.LIDAR_EMERGENCY_LANE_POLICY_ENABLED:
        occupancy = ""
    if occupancy == "L":
        return _result(
            "SWR", False, _CENTER_DEG + C.LIDAR_SWERVE_MAX_DEG,
            C.LIDAR_MIN_MOVE_PWM, fwd, "lidar_lane_left", display_occupancy,
            "swerve_right", occupancy,
        )
    if occupancy == "R":
        return _result(
            "SWR", False, _CENTER_DEG - C.LIDAR_SWERVE_MAX_DEG,
            C.LIDAR_MIN_MOVE_PWM, fwd, "lidar_lane_right", display_occupancy,
            "swerve_left", occupancy,
        )
    if occupancy == "LR":
        return _result(
            "CRP", False, _CENTER_DEG, C.LIDAR_MIN_MOVE_PWM, fwd, "lidar_lane_center_creep",
            display_occupancy, "creep", occupancy,
        )
    return _result(
        "EMR", True, None, 0.0, fwd, "lidar_emergency", display_occupancy,
        "brake", occupancy,
    )


def evaluate(scan):
    fwd, left_m, right_m = _forward_and_wedges(scan)
    occupancy = lane_occupancy(scan, C.LIDAR_WARN_M)
    emergency_occupancy = lane_occupancy(scan, C.LIDAR_OVERRIDE_EMERGENCY_STOP_M)

    if fwd < C.LIDAR_OVERRIDE_EMERGENCY_STOP_M:
        return _emergency_lane_decision(fwd, emergency_occupancy, occupancy)

    clusters = _forward_clusters(scan)
    if not clusters:
        return _result("", False, None, governor_target(fwd), fwd, "", occupancy, "normal")

    front_m = min(c["min_d"] for c in clusters)

    if _person_or_wall(clusters):                                   # PHYSICAL width, not angular
        return _result("HLD", True, None, 0.0, front_m, "lidar_hold",
                       occupancy, "brake")                           # person/wall -> full stop

    # MAILBOX: swerve AWAY from the object, toward a clear side
    widest = max(clusters, key=lambda c: c["width_m"])
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
        return _result("HLD", True, None, 0.0, front_m, "lidar_boxed",
                       occupancy, "brake")                           # no room -> full stop
    # A mailbox/post is narrow -> clear it with the swerve. Gentle (far) swerve = full throttle
    # (matches the old basic-swerve behavior); sharper (closer) swerves shed a little throttle.
    off_frac = (off - C.LIDAR_SWERVE_MIN_DEG) / max(1e-6, C.LIDAR_SWERVE_MAX_DEG - C.LIDAR_SWERVE_MIN_DEG)
    swerve_throttle = max(C.LIDAR_MIN_MOVE_PWM,
                          C.AUTONOMOUS_CRUISE_PWM - off_frac * C.LIDAR_SWERVE_THROTTLE_DROP)
    action = "swerve_right" if steer > _CENTER_DEG else "swerve_left"
    return _result("SWR", False, steer, swerve_throttle, front_m, "lidar_override",
                   occupancy, action)
