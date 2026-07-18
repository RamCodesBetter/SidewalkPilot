#!/usr/bin/env python3
"""Regression checks for brake-triggered autonomous disengagement."""

import sys
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


if __name__ == "__main__":
    unittest.main()
