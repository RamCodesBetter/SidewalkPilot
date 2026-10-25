#!/usr/bin/env python3
"""Regression tests for SidewalkPilot's production runtime rate contract."""

import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock


CONTROLLER_DIR = Path(__file__).resolve().parents[2] / "controller" / "current"
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

from rc_car_app import config  # noqa: E402
from rc_car_app import hub75_dashboard  # noqa: E402
from rc_car_app import vision  # noqa: E402

try:
    import gpiozero  # noqa: F401,E402
except ImportError:
    gpiozero = types.ModuleType("gpiozero")
    for class_name in (
        "PWMOutputDevice",
        "DigitalInputDevice",
        "DigitalOutputDevice",
        "Servo",
    ):
        setattr(gpiozero, class_name, type(class_name, (), {}))
    sys.modules["gpiozero"] = gpiozero

from rc_car_app import runtime  # noqa: E402


class RuntimeRateContractTest(unittest.TestCase):
    def test_control_camera_and_servo_contract_is_fifty_hz(self):
        self.assertEqual(config.CONTROL_LOOP_HZ, 50)
        self.assertEqual(config.PCA9685_FREQUENCY_HZ, 50)
        self.assertEqual(vision.CAMERA_FPS, 50)
        self.assertAlmostEqual(1.0 / config.CONTROL_LOOP_HZ, 0.02)

    def test_dashboard_contract_remains_ten_hz(self):
        self.assertEqual(config.DASHBOARD_TELEMETRY_HZ, 10)
        self.assertAlmostEqual(config.HUB75_DASHBOARD_SEND_INTERVAL_SEC, 0.1)
        self.assertLess(config.DASHBOARD_TELEMETRY_HZ, config.CONTROL_LOOP_HZ)

    def test_training_capture_remains_ten_hz(self):
        self.assertEqual(config.PHOTO_RUN_CAPTURE_FPS, 10.0)

    def test_dashboard_sender_enforces_its_ten_hz_limit(self):
        sender = hub75_dashboard.Hub75DashboardSender(
            transport="udp",
            baud_rate=115200,
            send_interval_sec=config.HUB75_DASHBOARD_SEND_INTERVAL_SEC,
            udp_host="192.0.2.1",
            udp_port=8765,
        )
        sent_at = []

        def record_send(_payload, now):
            sender.last_send_time = now
            sent_at.append(now)
            return True

        sender._ensure_connected = lambda: True
        sender._write_payload = record_send
        required = (0.0, "P", False, False, "", 80)
        with mock.patch.object(
            hub75_dashboard.time,
            "monotonic",
            side_effect=(10.0, 10.05, 10.101),
        ):
            self.assertTrue(sender.send(*required))
            self.assertFalse(sender.send(*required))
            self.assertTrue(sender.send(*required))

        self.assertEqual(sent_at, [10.0, 10.101])

    def test_async_dashboard_retries_transition_once_without_stale_resends(self):
        class RetryingSender:
            def __init__(self):
                self.calls = []
                self.last_payload_json = ""
                self.sent = threading.Event()

            def send(self, *args, **kwargs):
                self.calls.append(dict(kwargs))
                if len(self.calls) == 1:
                    return False
                self.last_payload_json = "sent"
                self.sent.set()
                return True

            def close(self):
                pass

        sender = RetryingSender()
        async_sender = runtime.AsyncDashboardSender(sender)
        required = (0.0, "P", False, False, "", 80)
        try:
            self.assertTrue(
                async_sender.send(
                    *required,
                    dashboard_page_transition="left",
                )
            )
            self.assertTrue(async_sender.send(*required))
            self.assertTrue(sender.sent.wait(timeout=0.5))
            calls_after_send = len(sender.calls)
            time.sleep(config.HUB75_DASHBOARD_SEND_INTERVAL_SEC * 1.5)

            self.assertEqual(len(sender.calls), calls_after_send)
            self.assertGreaterEqual(calls_after_send, 2)
            self.assertTrue(
                all(
                    call.get("dashboard_page_transition") == "left"
                    for call in sender.calls
                )
            )
        finally:
            async_sender.close()


if __name__ == "__main__":
    unittest.main()
