#!/usr/bin/env python3
"""Regression tests for the non-blocking Pi-to-Jetson control boundary."""

import sys
import threading
import time
import unittest
from pathlib import Path


CONTROLLER_DIR = Path(__file__).resolve().parents[2] / "controller" / "current"
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

from rc_car_app.jetson_client import AsyncJetsonSteeringClient  # noqa: E402


class BlockingFakeClient:
    """Behaves like an unavailable Jon until the test releases its socket wait."""

    timeout = 0.4

    def __init__(self):
        self.status_started = threading.Event()
        self.release_status = threading.Event()
        self.inference_finished = threading.Event()
        self.infer_calls = []
        self.infer_histories = []
        self.jon_cpu_temp_c = 47.0
        self.jon_gpu_temp_c = 51.0
        self.infer_fps = 29.5
        self.infer_ms = 11.0
        self.last_jpeg = None
        self.bucket_probs = [0.1] * 9

    def poll_status(self):
        self.status_started.set()
        self.release_status.wait(timeout=self.timeout)
        return False

    def infer(self, frame, model_version=None, target_history=None):
        self.infer_calls.append((frame, model_version))
        self.infer_histories.append(tuple(target_history or ()))
        self.last_jpeg = b"test-jpeg"
        self.inference_finished.set()
        return 123.0, 0.75

    def close(self):
        self.release_status.set()


class RecordingFakeClient:
    timeout = 0.1

    def __init__(self):
        self.infer_calls = []
        self.status_calls = 0
        self.infer_histories = []
        self._condition = threading.Condition()

    def infer(self, frame, model_version=None, target_history=None):
        with self._condition:
            self.infer_calls.append((frame, model_version))
            self.infer_histories.append(tuple(target_history or ()))
            self._condition.notify_all()
        return 90.0, 0.0

    def poll_status(self):
        with self._condition:
            self.status_calls += 1
            self._condition.notify_all()
        return True

    def wait_for_inferences(self, count, timeout=0.5):
        deadline = time.monotonic() + timeout
        with self._condition:
            while len(self.infer_calls) < count and time.monotonic() < deadline:
                self._condition.wait(timeout=max(0.0, deadline - time.monotonic()))
            return len(self.infer_calls) >= count

    def wait_for_status(self, timeout=0.5):
        deadline = time.monotonic() + timeout
        with self._condition:
            while self.status_calls == 0 and time.monotonic() < deadline:
                self._condition.wait(timeout=max(0.0, deadline - time.monotonic()))
            return self.status_calls > 0

    def close(self):
        pass


class AsyncJetsonClientTest(unittest.TestCase):
    def test_powered_off_status_timeout_never_blocks_control_calls(self):
        fake = BlockingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=0.05,
            client=fake,
        )
        try:
            self.assertTrue(fake.status_started.wait(timeout=0.2))

            started = time.perf_counter()
            first_sequence = client.submit("old-frame", model_version="3.3")
            second_sequence = client.submit("latest-frame", model_version="3.4")
            self.assertIsNone(
                client.get_latest_sample(model_version="3.4", max_age_sec=1.0)
            )
            elapsed = time.perf_counter() - started

            self.assertLess(elapsed, 0.02)
            self.assertGreater(second_sequence, first_sequence)

            fake.release_status.set()
            self.assertTrue(fake.inference_finished.wait(timeout=0.5))

            deadline = time.monotonic() + 0.5
            sample = None
            while sample is None and time.monotonic() < deadline:
                sample = client.get_latest_sample(
                    model_version="3.4",
                    max_age_sec=1.0,
                )
                time.sleep(0.005)

            self.assertIsNotNone(sample)
            self.assertEqual(sample["sequence"], second_sequence)
            self.assertEqual(sample["result"], (123.0, 0.75))
            self.assertEqual(fake.infer_calls, [("latest-frame", "3.4")])
            self.assertIsNone(
                client.get_latest_sample(model_version="3.3", max_age_sec=1.0)
            )
            self.assertEqual(client.last_jpeg, b"test-jpeg")
            self.assertEqual(client.infer_fps, 29.5)
        finally:
            fake.release_status.set()
            client.close()

    def test_active_inference_postpones_history_resetting_status_poll(self):
        fake = RecordingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=0.10,
            client=fake,
        )
        try:
            for index in range(4):
                client.submit(f"frame-{index}", model_version="4.0p")
                self.assertTrue(fake.wait_for_inferences(index + 1))
                time.sleep(0.04)

            self.assertEqual(fake.status_calls, 0)
            self.assertTrue(fake.wait_for_status(timeout=0.3))
        finally:
            client.close()

    def test_manual_targets_seed_auto_then_predictions_advance_history(self):
        fake = RecordingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            client=fake,
        )
        try:
            for steering in (62.0, 71.0, 83.0):
                client.observe_manual_steering(steering)

            client.submit("first-auto-frame", model_version="4.0p")
            self.assertTrue(fake.wait_for_inferences(1))
            self.assertEqual(fake.infer_histories[0], (62.0, 71.0, 83.0))

            client.submit("second-auto-frame", model_version="4.0p")
            self.assertTrue(fake.wait_for_inferences(2))
            self.assertEqual(fake.infer_histories[1], (71.0, 83.0, 90.0))
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
