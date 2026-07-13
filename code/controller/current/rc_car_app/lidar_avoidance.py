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


def _emergency_swerve_through(scan, fwd):
    """An obstacle sits inside the emergency zone. If a car-width(+margin) lateral gap is clear on
    ONE side of the sidewalk corridor AND that escape lane is drivable ahead, return a swerve dict
    to squeeze THROUGH; otherwise None so the caller hard-stops. Fail-safe: any doubt -> None.
    The caller must have already ruled out person/wall."""
    hw = C.LIDAR_CORRIDOR_HALF_WIDTH_M
    need = C.LIDAR_CAR_WIDTH_M + C.LIDAR_SWERVE_THROUGH_MARGIN_M
    danger = C.LIDAR_OVERRIDE_EMERGENCY_STOP_M + C.LIDAR_SWERVE_THROUGH_BAND_M
    occ_x = []          # lateral positions of the emergency obstacle (points at/inside the danger band)
    ahead = []          # (x, forward) of every in-corridor point ahead -> used to test the escape lane
    for p in scan or []:
        if not _valid(p):
            continue
        a = _norm_angle(p)
        d = p.distance_mm / 1000.0
        ar = math.radians(a)
        x = d * math.sin(ar)                          # lateral offset (right +, left -)
        f = d * math.cos(ar)                          # forward distance
        if f <= 0.0 or abs(x) > hw:
            continue                                  # only points inside the sidewalk corridor, ahead
        ahead.append((x, f))
        if f <= danger:
            occ_x.append(x)
    if not occ_x:
        return None                                   # nothing concrete to squeeze past -> stop
    x_lo, x_hi = min(occ_x), max(occ_x)
    left_free = x_lo - (-hw)                           # clear lateral room LEFT of the obstacle
    right_free = hw - x_hi                             # clear lateral room RIGHT of the obstacle
    if left_free >= right_free:
        side, gap = "left", left_free
        lane_ahead = [f for x, f in ahead if x < x_lo]    # open strip LEFT of the obstacle (excl. its edge)
    else:
        side, gap = "right", right_free
        lane_ahead = [f for x, f in ahead if x > x_hi]    # open strip RIGHT of the obstacle (excl. its edge)
    if gap < need:
        return None                                   # obstacle spans the corridor (no car-width gap) -> stop
    if lane_ahead and min(lane_ahead) < C.LIDAR_SWERVE_THROUGH_AHEAD_M:
        return None                                   # a SEPARATE obstacle blocks the escape lane -> stop
    off = C.LIDAR_SWERVE_MAX_DEG                       # emergency = obstacle is close -> hardest swerve
    steer = _CENTER_DEG - off if side == "left" else _CENTER_DEG + off
    return {"code": "SWR", "stop": False, "steer": steer,        # reuse SWR: runtime already applies it
            "throttle": C.LIDAR_MIN_MOVE_PWM, "front_m": fwd, "reason": "lidar_swerve_through"}


def evaluate(scan):
    fwd, left_m, right_m = _forward_and_wedges(scan)

    if fwd < C.LIDAR_OVERRIDE_EMERGENCY_STOP_M:
        # Blue-corridor swerve-through: squeeze past a NARROW obstacle in the emergency zone only if
        # it is not a person/wall and a car-width(+margin) gap is clear with a drivable lane ahead.
        # Any doubt falls through to the hard stop.
        if C.LIDAR_SWERVE_THROUGH_ENABLED and not _person_or_wall(_forward_clusters(scan)):
            through = _emergency_swerve_through(scan, fwd)
            if through is not None:
                return through
        return {"code": "EMR", "stop": True, "steer": None, "throttle": 0.0,
                "front_m": fwd, "reason": "lidar_emergency"}

    clusters = _forward_clusters(scan)
    if not clusters:
        return {"code": "", "stop": False, "steer": None, "throttle": governor_target(fwd),
                "front_m": fwd, "reason": ""}                       # CLEAR -> follow model

    front_m = min(c["min_d"] for c in clusters)

    if _person_or_wall(clusters):                                   # PHYSICAL width, not angular
        return {"code": "HLD", "stop": True, "steer": None, "throttle": 0.0,
                "front_m": front_m, "reason": "lidar_hold"}         # person/wall -> full stop

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
        return {"code": "HLD", "stop": True, "steer": None, "throttle": 0.0,
                "front_m": front_m, "reason": "lidar_boxed"}        # no room -> full stop
    # A mailbox/post is narrow -> clear it with the swerve. Gentle (far) swerve = full throttle
    # (matches the old basic-swerve behavior); sharper (closer) swerves shed a little throttle.
    off_frac = (off - C.LIDAR_SWERVE_MIN_DEG) / max(1e-6, C.LIDAR_SWERVE_MAX_DEG - C.LIDAR_SWERVE_MIN_DEG)
    swerve_throttle = max(C.LIDAR_MIN_MOVE_PWM,
                          C.AUTONOMOUS_CRUISE_PWM - off_frac * C.LIDAR_SWERVE_THROTTLE_DROP)
    return {"code": "SWR", "stop": False, "steer": steer, "throttle": swerve_throttle,
            "front_m": front_m, "reason": "lidar_override"}
