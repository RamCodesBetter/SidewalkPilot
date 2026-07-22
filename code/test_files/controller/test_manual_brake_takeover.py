#!/usr/bin/env python3
"""Regression checks for brake-triggered autonomous disengagement."""

import sys
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


CONTROLLER_DIR = Path(__file__).resolve().parents[2] / "controller" / "current"
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

try:
    import gpiozero  # noqa: F401
except ImportError:
    gpiozero = types.ModuleType("gpiozero")
    for class_name in ("PWMOutputDevice", "DigitalInputDevice", "DigitalOutputDevice", "Servo"):
        setattr(gpiozero, class_name, type(class_name, (), {}))
    sys.modules["gpiozero"] = gpiozero

from rc_car_app import config as C  # noqa: E402
from rc_car_app import runtime  # noqa: E402


class Output:
    def __init__(self, value=0.0):
        self.value = value


class FailingOutput:
    def __init__(self):
        self.attempts = []

    @property
    def value(self):
        return 0.0

    @value.setter
    def value(self, value):
        self.attempts.append(value)
        raise OSError("output unavailable")


def hardware_stub():
    return SimpleNamespace(
        steering_servo=Output(C.STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0),
        motor_left_fwd=Output(),
        motor_left_bwd=Output(),
        motor_right_fwd=Output(),
        motor_right_bwd=Output(),
    )


class NavigationStub:
    def __init__(self):
        self.active = True
        self.reset_called = False

    def reset_entry(self):
        self.reset_called = True


class ManualBrakeTakeoverTest(unittest.TestCase):
    def test_nonfinite_controller_inputs_default_to_safe_values(self):
        self.assertEqual(runtime.normalize_trigger_axis(float("nan")), 0.0)
        self.assertEqual(runtime.manual_throttle_pwm(float("nan")), 0.0)
        self.assertEqual(runtime.apply_steering_deadzone(float("nan")), 0.0)
        self.assertEqual(runtime.clamp_servo_degrees(float("nan")), 90.0)
        self.assertEqual(C.reference_throttle_to_absolute(-0.5), 0.0)
        self.assertEqual(C.reference_throttle_to_absolute(float("nan")), 0.0)

    def test_stale_imu_bypasses_yaw_correction(self):
        class StaleImu:
            def is_fresh(self):
                return False

            def get_yaw(self):
                return 20.0

            def note_stationary(self):
                pass

        class RecordingYawController:
            mode = "straight"
            engaged = False
            last_target_yaw = 0.0
            last_correction = 0.0

            def __init__(self):
                self.allow_values = []

            def reset(self):
                self.engaged = False

            def compute(self, commanded, _yaw, _speed, _dt, allow=True):
                self.allow_values.append(allow)
                self.engaged = bool(allow)
                return commanded + 30.0 if allow else commanded

        state = C.create_state()
        state.update({"gear_mode": "D", "steering_servo_deg": 90.0})
        metrics = C.Metrics()
        metrics.aeb_enabled = False
        controller = RecordingYawController()
        hardware = hardware_stub()

        runtime.update_gpio(
            state,
            metrics,
            hardware,
            webcam_vision=None,
            lidar_scan=[],
            dt=1.0 / 60.0,
            yaw_controller=controller,
            imu_reader=StaleImu(),
        )

        self.assertEqual(controller.allow_values, [False])
        self.assertEqual(state["steering_effective_servo_deg"], 90.0)

    def test_metrics_timestamps_are_created_for_each_run(self):
        first = C.Metrics()
        time.sleep(0.002)
        second = C.Metrics()
        self.assertGreater(second.start_time, first.start_time)
        self.assertGreater(second.last_pulse_time, first.last_pulse_time)

    def test_immediate_shutdown_commands_at8236_hard_brake(self):
        hardware = hardware_stub()
        hardware.motor_left_fwd.value = 0.8
        hardware.motor_right_fwd.value = 0.8

        runtime.write_hardware_hard_stop(hardware)

        self.assertEqual(hardware.motor_left_fwd.value, 1.0)
        self.assertEqual(hardware.motor_left_bwd.value, 1.0)
        self.assertEqual(hardware.motor_right_fwd.value, 1.0)
        self.assertEqual(hardware.motor_right_bwd.value, 1.0)

    def test_hard_stop_attempts_every_output_when_one_output_fails(self):
        hardware = hardware_stub()
        failed = FailingOutput()
        hardware.motor_left_fwd = failed

        runtime.write_hardware_hard_stop(hardware)

        self.assertEqual(failed.attempts, [0.0, 1.0])
        self.assertEqual(hardware.motor_left_bwd.value, 1.0)
        self.assertEqual(hardware.motor_right_fwd.value, 1.0)
        self.assertEqual(hardware.motor_right_bwd.value, 1.0)

    def test_model_switch_cancels_autonomy_and_resets_model_state(self):
        class VisionStub:
            def set_model_choice(self, _choice):
                return True

        state = C.create_state()
        state.update({
            "dashboard_page": 3,
            "autonomous_mode": True,
            "steering_servo_deg": 121.0,
            "steer_smoothed_deg": 45.0,
            "throttle": 1.0,
        })
        navigation = NavigationStub()
        navigation.active = False

        selected = runtime.handle_dpad_y_action(
            1,
            state,
            C.Metrics(),
            navigation,
            VisionStub(),
            "3.4",
            dashboard_sender=None,
        )

        self.assertEqual(selected, "3.4b")
        self.assertFalse(state["autonomous_mode"])
        self.assertEqual(state["throttle"], 0.0)
        self.assertEqual(state["steer_smoothed_deg"], 90.0)

    def test_gear_shift_cancels_autonomy_and_preserves_held_brake(self):
        state = C.create_state()
        state.update({
            "autonomous_mode": True,
            "gear_mode": "D",
            "brake": True,
            "brake_force": 0.8,
            "manual_brake_force": 0.8,
        })

        runtime.shift_gear(state, C.Metrics(), -1)

        self.assertFalse(state["autonomous_mode"])
        self.assertEqual(state["gear_mode"], "N")
        self.assertTrue(state["brake"])
        self.assertEqual(state["manual_brake_force"], 0.8)

    def test_autonomy_start_uses_current_manual_steering_and_resets_filter(self):
        class JetsonStub:
            def __init__(self):
                self.seeds = []

            def begin_autonomous_sequence(self, steering):
                self.seeds.append(steering)

        state = C.create_state()
        state.update({
            "steering_servo_deg": 73.0,
            "steer_smoothed_deg": 140.0,
            "_jon_result_sequence": 99,
            "gear_mode": "P",
        })
        jetson = JetsonStub()

        self.assertTrue(runtime.engage_autonomous_mode(state, C.Metrics(), jetson_client=jetson))
        self.assertTrue(state["autonomous_mode"])
        self.assertEqual(state["gear_mode"], "D")
        self.assertEqual(state["steer_smoothed_deg"], 73.0)
        self.assertEqual(state["_jon_result_sequence"], 0)
        self.assertEqual(jetson.seeds, [73.0])

    def test_autonomy_cannot_start_while_manual_brake_is_held(self):
        state = C.create_state()
        state["manual_brake_force"] = 1.0
        state["brake"] = True

        self.assertFalse(runtime.engage_autonomous_mode(state, C.Metrics()))
        self.assertFalse(state["autonomous_mode"])
        self.assertTrue(state["brake"])

    def test_ordinary_autonomy_cancel_still_clears_brake_state(self):
        state = C.create_state()
        state.update({
            "autonomous_mode": True,
            "brake": True,
            "brake_force": 1.0,
            "manual_brake_force": 1.0,
        })

        runtime.cancel_autonomous_mode(state, C.Metrics(), "button")

        self.assertFalse(state["autonomous_mode"])
        self.assertFalse(state["brake"])
        self.assertEqual(state["brake_force"], 0.0)
        self.assertEqual(state["manual_brake_force"], 0.0)

    def test_throttle_takeover_preserves_current_operator_command(self):
        state = C.create_state()
        state.update({
            "autonomous_mode": True,
            "throttle": 0.82,
            "current_motor_pwm": 1.0,
        })

        runtime.cancel_autonomous_mode(
            state,
            C.Metrics(),
            "Autonomous driving cancelled by gas pedal.",
            preserve_manual_throttle=True,
        )

        self.assertFalse(state["autonomous_mode"])
        self.assertEqual(state["throttle"], 0.82)
        self.assertEqual(state["current_motor_pwm"], 1.0)

    def test_navigation_throttle_takeover_preserves_current_operator_command(self):
        state = C.create_state()
        state.update({
            "autonomous_mode": True,
            "throttle": 0.73,
            "current_motor_pwm": 0.91,
        })
        navigation = NavigationStub()

        runtime.cancel_navigation_route(
            state,
            C.Metrics(),
            navigation,
            "Navigation cancelled by gas pedal.",
            preserve_manual_throttle=True,
        )

        self.assertFalse(navigation.active)
        self.assertFalse(state["autonomous_mode"])
        self.assertEqual(state["throttle"], 0.73)
        self.assertEqual(state["current_motor_pwm"], 0.91)

    def test_brake_takeover_retains_full_analog_brake(self):
        state = C.create_state()
        state.update({
            "autonomous_mode": True,
            "brake": True,
            "brake_force": 1.0,
            "manual_brake_force": 1.0,
            "current_motor_pwm": 1.0,
        })

        runtime.cancel_autonomous_mode(
            state,
            C.Metrics(),
            "Autonomous driving cancelled by brake.",
            preserve_manual_brake=True,
        )

        self.assertFalse(state["autonomous_mode"])
        self.assertTrue(state["brake"])
        self.assertEqual(state["brake_force"], 1.0)
        self.assertEqual(state["manual_brake_force"], 1.0)

    def test_navigation_brake_takeover_retains_full_analog_brake(self):
        state = C.create_state()
        state.update({
            "autonomous_mode": True,
            "brake": True,
            "brake_force": 1.0,
            "manual_brake_force": 1.0,
        })
        navigation = NavigationStub()

        runtime.cancel_navigation_route(
            state,
            C.Metrics(),
            navigation,
            "Navigation cancelled by brake.",
            preserve_manual_brake=True,
        )

        self.assertFalse(navigation.active)
        self.assertTrue(navigation.reset_called)
        self.assertFalse(state["autonomous_mode"])
        self.assertTrue(state["brake"])
        self.assertEqual(state["manual_brake_force"], 1.0)

    def test_retained_full_brake_commands_at8236_hard_brake(self):
        state = C.create_state()
        state.update({
            "autonomous_mode": False,
            "gear_mode": "D",
            "brake": True,
            "brake_force": 1.0,
            "manual_brake_force": 1.0,
            "current_motor_pwm": 1.0,
        })
        hardware = hardware_stub()

        runtime.update_gpio(
            state,
            C.Metrics(),
            hardware,
            webcam_vision=None,
            lidar_scan=[],
            dt=1.0 / 60.0,
        )

        self.assertEqual(state["current_motor_pwm"], 0.0)
        self.assertEqual(state["dashboard_brake_percent"], 100)
        self.assertEqual(hardware.motor_left_fwd.value, 1.0)
        self.assertEqual(hardware.motor_left_bwd.value, 1.0)
        self.assertEqual(hardware.motor_right_fwd.value, 1.0)
        self.assertEqual(hardware.motor_right_bwd.value, 1.0)

    def test_aeb_brake_does_not_latch_after_the_hazard_clears(self):
        def point(distance_m):
            return SimpleNamespace(
                angle_deg=0.0,
                distance_mm=distance_m * 1000.0,
                confidence=255,
                is_valid=True,
            )

        state = C.create_state()
        state.update({
            "gear_mode": "D",
            "throttle": 1.0,
            "manual_brake_force": 0.0,
            "lidar_scan_fresh": True,
        })
        metrics = C.Metrics()
        hardware = hardware_stub()

        runtime.update_gpio(
            state,
            metrics,
            hardware,
            webcam_vision=None,
            lidar_scan=[point(0.5)],
            dt=1.0 / 60.0,
        )
        self.assertTrue(state["brake"])
        self.assertTrue(metrics.aeb_triggered)

        runtime.update_gpio(
            state,
            metrics,
            hardware,
            webcam_vision=None,
            lidar_scan=[],
            dt=1.0 / 60.0,
        )
        self.assertFalse(state["brake"])
        self.assertFalse(metrics.aeb_triggered)
        self.assertEqual(hardware.motor_left_fwd.value, 0.0)
        self.assertEqual(hardware.motor_left_bwd.value, 0.0)


if __name__ == "__main__":
    unittest.main()
