#!/usr/bin/env python3
"""Deterministic tests for the production LiDAR emergency lane policy."""

import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


CONTROLLER_DIR = Path(__file__).resolve().parents[1] / "controller" / "current"
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

from rc_car_app import config as C  # noqa: E402
from rc_car_app import lidar_avoidance  # noqa: E402


def point(x_m, forward_m, confidence=200):
    distance_m = math.hypot(x_m, forward_m)
    return SimpleNamespace(
        is_valid=True,
        confidence=confidence,
        distance_mm=int(round(distance_m * 1000.0)),
        angle_deg=math.degrees(math.atan2(x_m, forward_m)),
    )


class LidarEmergencyLanePolicyTest(unittest.TestCase):
    def setUp(self):
        self.forward_m = C.LIDAR_OVERRIDE_EMERGENCY_STOP_M - 0.20
        self.lane_x = C.LIDAR_CORRIDOR_HALF_WIDTH_M * 2.0 / 3.0

    def scan(self, lanes):
        x_by_lane = {"L": -self.lane_x, "C": 0.0, "R": self.lane_x}
        return [point(x_by_lane[lane], self.forward_m) for lane in lanes]

    def assert_hard_brake(self, lanes):
        result = lidar_avoidance.evaluate(self.scan(lanes))
        self.assertEqual(result["code"], "EMR")
        self.assertTrue(result["stop"])
        self.assertEqual(result["throttle"], 0.0)
        self.assertEqual(result["lane_action"], "brake")
        self.assertEqual(result["emergency_lane_occupancy"], lanes)

    def test_empty_scan_is_normal_driving(self):
        result = lidar_avoidance.evaluate([])
        self.assertEqual(result["code"], "")
        self.assertFalse(result["stop"])
        self.assertEqual(result["lane_action"], "normal")
        self.assertEqual(result["lane_occupancy"], "")

    def test_left_only_swerves_right_at_minimum_moving_throttle(self):
        result = lidar_avoidance.evaluate(self.scan("L"))
        self.assertEqual(result["code"], "SWR")
        self.assertGreater(result["steer"], 90.0)
        self.assertEqual(result["throttle"], C.LIDAR_MIN_MOVE_PWM)
        self.assertEqual(result["lane_action"], "swerve_right")

    def test_right_only_swerves_left_at_minimum_moving_throttle(self):
        result = lidar_avoidance.evaluate(self.scan("R"))
        self.assertEqual(result["code"], "SWR")
        self.assertLess(result["steer"], 90.0)
        self.assertEqual(result["throttle"], C.LIDAR_MIN_MOVE_PWM)
        self.assertEqual(result["lane_action"], "swerve_left")

    def test_left_and_right_creep_straight_through_clear_center(self):
        result = lidar_avoidance.evaluate(self.scan("LR"))
        self.assertEqual(result["code"], "CRP")
        self.assertFalse(result["stop"])
        self.assertEqual(result["steer"], 90.0)
        self.assertEqual(result["throttle"], C.LIDAR_MIN_MOVE_PWM)
        self.assertEqual(result["lane_action"], "creep")

    def test_center_occupancy_always_hard_brakes(self):
        for lanes in ("C", "LC", "CR", "LCR"):
            with self.subTest(lanes=lanes):
                self.assert_hard_brake(lanes)

    def test_low_confidence_point_does_not_occupy_a_lane(self):
        result = lidar_avoidance.evaluate([
            point(0.0, self.forward_m, confidence=C.LIDAR_MIN_CONFIDENCE - 1)
        ])
        self.assertEqual(result["lane_occupancy"], "")
        self.assertEqual(result["lane_action"], "normal")

    def test_point_outside_corridor_does_not_occupy_a_lane(self):
        result = lidar_avoidance.evaluate([
            point(C.LIDAR_CORRIDOR_HALF_WIDTH_M + 0.10, self.forward_m)
        ])
        self.assertEqual(result["lane_occupancy"], "")
        self.assertEqual(result["lane_action"], "normal")


if __name__ == "__main__":
    unittest.main()
