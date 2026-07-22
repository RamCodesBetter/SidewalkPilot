"""Center-corridor LiDAR throttle governor and emergency brake.

The camera model owns every steering command. LiDAR points outside the center safety
corridor are telemetry only and never cause a swerve. A valid point directly ahead can
reduce the reference throttle target from 100% to 60% and can request a hard stop at
the emergency boundary. The 60% reference target is 82% physical PWM because the
physical 0..55% motor dead zone maps to reference 0%.

The caller passes the operator's AEB toggle into :func:`evaluate`. When disabled, this
module reports occupancy for the dashboard but returns full throttle and no stop.
"""

import math

from . import config as C


_MAX_RANGE_M = 12.0


def _valid(point) -> bool:
    return (
        getattr(point, "is_valid", False)
        and getattr(point, "distance_mm", 0) > 0
        and getattr(point, "confidence", 0) >= C.LIDAR_MIN_CONFIDENCE
    )


def _normalized_angle_deg(point) -> float:
    angle = float(getattr(point, "angle_deg", 0.0))
    return angle - 360.0 if angle > 180.0 else angle


def center_forward_distance(scan) -> float:
    """Return the nearest forward distance inside the car-relative center corridor."""
    nearest = _MAX_RANGE_M
    for point in scan or []:
        if not _valid(point):
            continue
        angle_rad = math.radians(_normalized_angle_deg(point))
        distance_m = float(point.distance_mm) / 1000.0
        lateral_m = distance_m * math.sin(angle_rad)
        forward_m = distance_m * math.cos(angle_rad)
        if forward_m <= 0.0 or abs(lateral_m) > C.LIDAR_CENTER_HALF_WIDTH_M:
            continue
        nearest = min(nearest, forward_m)
    return nearest


def center_occupancy(scan, max_forward_m: float) -> str:
    """Return ``C`` when the center corridor is occupied within the requested rung."""
    return "C" if center_forward_distance(scan) <= float(max_forward_m) else ""


def lane_occupancy(scan, max_forward_m: float) -> str:
    """Compatibility name for dashboard telemetry; only the C lane now exists."""
    return center_occupancy(scan, max_forward_m)


def governor_target(front_m: float) -> float:
    """Map center clearance to physical PWM, flooring the governor at 60% reference."""
    if front_m <= C.LIDAR_OVERRIDE_EMERGENCY_STOP_M:
        return 0.0
    if front_m <= C.LIDAR_GOV_STOP_M:
        return C.LIDAR_GOV_MIN_PWM
    if front_m >= C.LIDAR_GOV_FULL_M:
        return C.AUTONOMOUS_CRUISE_PWM
    fraction = (front_m - C.LIDAR_GOV_STOP_M) / (
        C.LIDAR_GOV_FULL_M - C.LIDAR_GOV_STOP_M
    )
    return C.LIDAR_GOV_MIN_PWM + fraction * (
        C.AUTONOMOUS_CRUISE_PWM - C.LIDAR_GOV_MIN_PWM
    )


def evaluate(scan, enabled: bool = True, scan_fresh: bool = True) -> dict:
    """Return the center-corridor throttle/stop decision for manual or autonomous use."""
    front_m = center_forward_distance(scan)
    occupancy = "C" if front_m <= C.LIDAR_GOV_FULL_M else ""
    emergency_occupancy = (
        "C" if front_m <= C.LIDAR_OVERRIDE_EMERGENCY_STOP_M else ""
    )

    if not enabled:
        return {
            "code": "",
            "stop": False,
            "steer": None,
            "throttle": C.AUTONOMOUS_CRUISE_PWM,
            "front_m": front_m,
            "reason": "",
            "lane_occupancy": occupancy,
            "emergency_lane_occupancy": emergency_occupancy,
            "lane_action": "disabled",
        }

    if not scan_fresh:
        return {
            "code": "EMR",
            "stop": True,
            "steer": None,
            "throttle": 0.0,
            "front_m": front_m,
            "reason": "lidar_unavailable",
            "lane_occupancy": occupancy,
            "emergency_lane_occupancy": emergency_occupancy,
            "lane_action": "brake",
        }

    if emergency_occupancy:
        return {
            "code": "EMR",
            "stop": True,
            "steer": None,
            "throttle": 0.0,
            "front_m": front_m,
            "reason": "lidar_emergency",
            "lane_occupancy": occupancy,
            "emergency_lane_occupancy": emergency_occupancy,
            "lane_action": "brake",
        }

    throttle = governor_target(front_m)
    if throttle <= C.LIDAR_GOV_MIN_PWM and occupancy:
        action = "creep"
    elif throttle < C.AUTONOMOUS_CRUISE_PWM:
        action = "slow"
    else:
        action = "normal"
    return {
        "code": "",
        "stop": False,
        "steer": None,
        "throttle": throttle,
        "front_m": front_m,
        "reason": "",
        "lane_occupancy": occupancy,
        "emergency_lane_occupancy": "",
        "lane_action": action,
    }
