#!/usr/bin/env python3
"""Deterministic checks for the production center-corridor LiDAR AEB policy."""

import math
import sys
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


CONTROLLER_DIR = Path(__file__).resolve().parents[1] / "controller" / "current"
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

from rc_car_app import config as C  # noqa: E402
from rc_car_app import lidar_avoidance  # noqa: E402

try:  # Runtime imports the real GPIO classes on the Pi; CI/desktop tests use inert stubs.
    import gpiozero  # noqa: F401
except ImportError:
    gpiozero = types.ModuleType("gpiozero")
    for class_name in ("PWMOutputDevice", "DigitalInputDevice", "DigitalOutputDevice", "Servo"):
        setattr(gpiozero, class_name, type(class_name, (), {}))
    sys.modules["gpiozero"] = gpiozero

from rc_car_app import runtime  # noqa: E402


def point(lateral_m, forward_m, confidence=200):
    distance_m = math.hypot(lateral_m, forward_m)
    return SimpleNamespace(
        is_valid=True,
        confidence=confidence,
        distance_mm=int(round(distance_m * 1000.0)),
        angle_deg=math.degrees(math.atan2(lateral_m, forward_m)),
    )


class LidarCenterAebTest(unittest.TestCase):
    def test_empty_scan_leaves_throttle_and_steering_untouched(self):
        result = lidar_avoidance.evaluate([])
        self.assertFalse(result["stop"])
        self.assertEqual(result["throttle"], C.AUTONOMOUS_CRUISE_PWM)
        self.assertIsNone(result["steer"])
        self.assertEqual(result["lane_action"], "normal")
        self.assertEqual(result["lane_occupancy"], "")

    def test_side_obstacles_are_telemetry_only(self):
        forward_m = C.LIDAR_OVERRIDE_EMERGENCY_STOP_M - 0.20
        for lateral_m in (
            -(C.LIDAR_CENTER_HALF_WIDTH_M + 0.05),
            C.LIDAR_CENTER_HALF_WIDTH_M + 0.05,
            -0.70,
            0.70,
        ):
            with self.subTest(lateral_m=lateral_m):
                result = lidar_avoidance.evaluate([point(lateral_m, forward_m)])
                self.assertFalse(result["stop"])
                self.assertEqual(result["throttle"], C.AUTONOMOUS_CRUISE_PWM)
                self.assertEqual(result["lane_occupancy"], "")
                self.assertIsNone(result["steer"])

    def test_center_obstacle_scales_from_full_to_60_percent_reference(self):
        at_full = lidar_avoidance.evaluate([point(0.0, C.LIDAR_GOV_FULL_M)])
        midpoint_m = (C.LIDAR_GOV_FULL_M + C.LIDAR_GOV_STOP_M) / 2.0
        midpoint = lidar_avoidance.evaluate([point(0.0, midpoint_m)])
        creep = lidar_avoidance.evaluate([
            point(0.0, C.LIDAR_OVERRIDE_EMERGENCY_STOP_M + 0.05)
        ])

        self.assertEqual(at_full["throttle"], C.AUTONOMOUS_CRUISE_PWM)
        self.assertEqual(at_full["lane_occupancy"], "C")
        self.assertGreater(midpoint["throttle"], C.LIDAR_GOV_MIN_PWM)
        self.assertLess(midpoint["throttle"], C.AUTONOMOUS_CRUISE_PWM)
        self.assertEqual(midpoint["lane_action"], "slow")
        self.assertEqual(creep["throttle"], C.LIDAR_GOV_MIN_PWM)
        self.assertAlmostEqual(
            C.absolute_throttle_to_reference(creep["throttle"]), 0.60
        )
        self.assertEqual(creep["lane_action"], "creep")

    def test_center_obstacle_at_emergency_boundary_hard_stops(self):
        result = lidar_avoidance.evaluate([
            point(0.0, C.LIDAR_OVERRIDE_EMERGENCY_STOP_M)
        ])
        self.assertTrue(result["stop"])
        self.assertEqual(result["code"], "EMR")
        self.assertEqual(result["throttle"], 0.0)
        self.assertEqual(result["lane_action"], "brake")
        self.assertEqual(result["emergency_lane_occupancy"], "C")
        self.assertIsNone(result["steer"])

    def test_aeb_disabled_disables_slowdown_and_stop(self):
        result = lidar_avoidance.evaluate(
            [point(0.0, C.LIDAR_OVERRIDE_EMERGENCY_STOP_M - 0.20)],
            enabled=False,
        )
        self.assertFalse(result["stop"])
        self.assertEqual(result["code"], "")
        self.assertEqual(result["throttle"], C.AUTONOMOUS_CRUISE_PWM)
        self.assertEqual(result["lane_action"], "disabled")
        self.assertEqual(result["lane_occupancy"], "C")
        self.assertIsNone(result["steer"])

    def test_autonomous_emergency_bypasses_vision_latency(self):
        class VisionMustNotRun:
            def get_analysis(self):
                raise AssertionError("vision ran before the emergency brake")

        scan = [point(0.0, C.LIDAR_OVERRIDE_EMERGENCY_STOP_M - 0.20)]
        policy = lidar_avoidance.evaluate(scan, enabled=True)
        state = C.create_state()
        state["autonomous_mode"] = True
        metrics = C.Metrics()
        metrics.aeb_enabled = True

        throttle, brake = runtime.apply_autonomous_controls(
            state,
            metrics,
            hardware=None,
            webcam_vision=VisionMustNotRun(),
            lidar_scan=scan,
            active_model_choice="3.4",
            lidar_policy=policy,
        )

        self.assertEqual(throttle, 0.0)
        self.assertTrue(brake)
        self.assertEqual(state["stop_reason"], "lidar_emergency")
        self.assertEqual(metrics.auto_last_cause_code, "EMR")

    def test_autonomous_aeb_off_preserves_model_steering_and_full_throttle(self):
        class FreshVision:
            def get_analysis(self):
                return ({
                    "heading_bias": 0.0,
                    "confidence": 1.0,
                    "left_edge_found": False,
                    "right_edge_found": False,
                    "corridor_width_px": 0.0,
                    "driveway_cut_hint": False,
                    "steering_angle_deg": 117.0,
                    "method": "test",
                }, time.time())

        scan = [point(0.0, C.LIDAR_OVERRIDE_EMERGENCY_STOP_M - 0.20)]
        policy = lidar_avoidance.evaluate(scan, enabled=False)
        state = C.create_state()
        state["autonomous_mode"] = True
        metrics = C.Metrics()
        metrics.aeb_enabled = False

        throttle, brake = runtime.apply_autonomous_controls(
            state,
            metrics,
            hardware=None,
            webcam_vision=FreshVision(),
            lidar_scan=scan,
            active_model_choice="3.4",
            lidar_policy=policy,
        )

        self.assertEqual(throttle, C.AUTONOMOUS_CRUISE_PWM)
        self.assertFalse(brake)
        self.assertEqual(state["steering_servo_deg"], 117.0)
        self.assertFalse(state["lidar_override_active"])

    def test_autonomous_control_consumes_cached_jetson_result(self):
        class FreshCamera:
            camera_fps = 30.0

            def get_analysis(self):
                return ({
                    "heading_bias": 0.0,
                    "confidence": 0.0,
                    "left_edge_found": False,
                    "right_edge_found": False,
                    "corridor_width_px": 0.0,
                    "driveway_cut_hint": False,
                    "method": "camera_only",
                }, time.time())

            def grab_latest_frame(self):
                return "latest-frame"

        class CachedJetson:
            jon_cpu_temp_c = 48.0
            jon_gpu_temp_c = 52.0
            infer_fps = 30.0
            infer_ms = 10.0

            def __init__(self):
                self.submissions = []

            def submit(self, frame, model_version=None):
                self.submissions.append((frame, model_version))
                return 8

            def get_latest_sample(self, model_version=None, max_age_sec=None):
                return {
                    "sequence": 7,
                    "model_version": model_version,
                    "result": (121.0, 0.0),
                    "age_sec": 0.01,
                }

        state = C.create_state()
        state["autonomous_mode"] = True
        state["_perf_next"] = time.time() + 60.0
        state["_autodbg_next"] = time.time() + 60.0
        metrics = C.Metrics()
        jetson = CachedJetson()
        policy = lidar_avoidance.evaluate([], enabled=True)

        started = time.perf_counter()
        throttle, brake = runtime.apply_autonomous_controls(
            state,
            metrics,
            hardware=None,
            webcam_vision=FreshCamera(),
            lidar_scan=[],
            jetson_client=jetson,
            active_model_choice="3.4",
            lidar_policy=policy,
        )

        self.assertLess(time.perf_counter() - started, 0.05)
        self.assertEqual(jetson.submissions, [("latest-frame", "3.4")])
        self.assertEqual(state["steering_servo_deg"], 121.0)
        self.assertEqual(throttle, C.AUTONOMOUS_CRUISE_PWM)
        self.assertFalse(brake)

    def test_policy_never_outputs_a_steering_command(self):
        distances = (
            C.LIDAR_OVERRIDE_EMERGENCY_STOP_M - 0.10,
            C.LIDAR_OVERRIDE_EMERGENCY_STOP_M + 0.10,
            C.LIDAR_GOV_STOP_M + 0.10,
            C.LIDAR_GOV_FULL_M + 0.10,
        )
        for enabled in (False, True):
            for distance_m in distances:
                with self.subTest(enabled=enabled, distance_m=distance_m):
                    result = lidar_avoidance.evaluate(
                        [point(0.0, distance_m)], enabled=enabled
                    )
                    self.assertIsNone(result["steer"])
                    self.assertNotIn(result["code"], ("SWR", "CRP"))

    def test_low_confidence_center_point_is_ignored(self):
        result = lidar_avoidance.evaluate([
            point(
                0.0,
                C.LIDAR_OVERRIDE_EMERGENCY_STOP_M - 0.20,
                confidence=C.LIDAR_MIN_CONFIDENCE - 1,
            )
        ])
        self.assertFalse(result["stop"])
        self.assertEqual(result["lane_occupancy"], "")

    def test_governor_holds_at_60_percent_reference_before_emr(self):
        self.assertEqual(
            lidar_avoidance.governor_target(C.LIDAR_OVERRIDE_EMERGENCY_STOP_M),
            0.0,
        )
        self.assertEqual(
            lidar_avoidance.governor_target(C.LIDAR_OVERRIDE_EMERGENCY_STOP_M + 0.01),
            C.LIDAR_GOV_MIN_PWM,
        )
        self.assertEqual(
            lidar_avoidance.governor_target(C.LIDAR_GOV_STOP_M),
            C.LIDAR_GOV_MIN_PWM,
        )
        self.assertAlmostEqual(
            C.absolute_throttle_to_reference(C.LIDAR_GOV_MIN_PWM), 0.60
        )
        self.assertAlmostEqual(C.LIDAR_GOV_MIN_PWM, 0.82)
        self.assertEqual(
            lidar_avoidance.governor_target(C.LIDAR_GOV_FULL_M),
            C.AUTONOMOUS_CRUISE_PWM,
        )

    def test_reference_throttle_does_not_change_absolute_training_labels(self):
        self.assertEqual(C.absolute_throttle_to_reference(0.30), 0.0)
        self.assertEqual(
            C.absolute_throttle_to_reference(C.LIDAR_MIN_MOVE_PWM), 0.0
        )
        midpoint = (C.LIDAR_MIN_MOVE_PWM + 1.0) / 2.0
        self.assertAlmostEqual(C.absolute_throttle_to_reference(midpoint), 0.5)
        self.assertEqual(C.absolute_throttle_to_reference(1.0), 1.0)
        self.assertAlmostEqual(C.reference_throttle_to_absolute(0.60), 0.82)
        self.assertEqual(
            runtime.current_forward_throttle_label({"current_motor_pwm": 0.55}),
            0.55,
        )
        self.assertEqual(
            runtime.current_forward_throttle_label({"current_motor_pwm": 0.82}),
            0.82,
        )
        self.assertEqual(
            runtime.current_forward_throttle_label({"current_motor_pwm": 1.0}),
            1.0,
        )
        self.assertEqual(
            runtime.current_forward_throttle_label({"current_motor_pwm": -0.82}),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
