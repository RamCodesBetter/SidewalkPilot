#!/usr/bin/env python3
"""Regression tests for the non-blocking Pi-to-Jetson control boundary."""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


CONTROLLER_DIR = Path(__file__).resolve().parents[2] / "controller" / "current"
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

from rc_car_app.jetson_client import (  # noqa: E402
    AsyncJetsonSteeringClient,
    JetsonSteeringClient,
)


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
        self.jpeg_encode_ms = 2.0
        self.socket_round_trip_ms = 14.0
        self.inference_request_ms = 16.0
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
        self.jpeg_encode_ms = 2.0
        self.socket_round_trip_ms = 14.0
        self.inference_request_ms = 16.0
        self.infer_ms = 11.0

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
    def test_failed_connection_closes_the_new_socket(self):
        failed_socket = mock.Mock()
        failed_socket.connect.side_effect = OSError("Jetson offline")
        client = JetsonSteeringClient("10.42.0.2")

        with mock.patch("rc_car_app.jetson_client.socket.socket", return_value=failed_socket):
            self.assertFalse(client.connect())

        failed_socket.close.assert_called_once()
        self.assertIsNone(client.sock)

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

    def test_slow_result_is_stale_from_submission_not_completion(self):
        class SlowClient(RecordingFakeClient):
            def infer(self, frame, model_version=None, target_history=None):
                time.sleep(0.06)
                return super().infer(frame, model_version, target_history)

        fake = SlowClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            history_result_max_age_sec=0.03,
            client=fake,
        )
        try:
            client.begin_autonomous_sequence(90.0)
            client.submit("delayed-frame", model_version="4.0p")
            self.assertTrue(fake.wait_for_inferences(1))
            deadline = time.monotonic() + 0.2
            while client._latest_result is None and time.monotonic() < deadline:
                time.sleep(0.002)
            self.assertIsNotNone(client._latest_result)
            self.assertIsNone(
                client.get_latest_sample(model_version="4.0p", max_age_sec=0.03)
            )
            self.assertEqual(client._target_history, [90.0, 90.0, 90.0])
        finally:
            client.close()

    def test_manual_targets_seed_auto_then_predictions_advance_history(self):
        fake = RecordingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            history_sample_interval_sec=0.0,
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

    def test_submit_binds_frame_to_history_snapshot(self):
        fake = BlockingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=0.05,
            history_sample_interval_sec=0.0,
            client=fake,
        )
        try:
            self.assertTrue(fake.status_started.wait(timeout=0.2))
            for steering in (62.0, 71.0, 83.0):
                client.observe_manual_steering(steering)

            client.submit("captured-frame", model_version="4.1a")
            client.observe_manual_steering(120.0)
            fake.release_status.set()
            self.assertTrue(fake.inference_finished.wait(timeout=0.5))

            self.assertEqual(fake.infer_histories, [(62.0, 71.0, 83.0)])
        finally:
            fake.release_status.set()
            client.close()

    def test_submit_uses_history_from_camera_capture_time(self):
        fake = RecordingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            history_sample_interval_sec=0.0,
            client=fake,
        )
        try:
            now = time.monotonic()
            client.observe_manual_steering(62.0, sampled_at=now - 0.30)
            client.observe_manual_steering(71.0, sampled_at=now - 0.20)
            client.observe_manual_steering(83.0, sampled_at=now - 0.10)
            captured_at = now - 0.05

            # This command happened after the image was captured and must not be
            # paired with that older image.
            client.observe_manual_steering(120.0, sampled_at=now)
            client.submit(
                "captured-frame",
                model_version="4.1a",
                captured_at=captured_at,
            )
            self.assertTrue(fake.wait_for_inferences(1))

            self.assertEqual(fake.infer_histories, [(62.0, 71.0, 83.0)])
        finally:
            client.close()

    def test_result_age_and_metadata_start_at_camera_capture(self):
        fake = RecordingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            client=fake,
        )
        try:
            captured_at = time.monotonic() - 0.06
            client.submit(
                "captured-frame",
                model_version="3.4",
                source_frame_sequence=42,
                captured_at=captured_at,
            )
            self.assertTrue(fake.wait_for_inferences(1))

            self.assertIsNone(
                client.get_latest_sample(model_version="3.4", max_age_sec=0.03)
            )
            sample = client.get_latest_sample(model_version="3.4", max_age_sec=1.0)
            self.assertIsNotNone(sample)
            self.assertEqual(sample["source_frame_sequence"], 42)
            self.assertGreaterEqual(sample["capture_to_result_ms"], 60.0)
        finally:
            client.close()

    def test_latency_summary_reports_rolling_successful_requests(self):
        fake = RecordingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            latency_window_size=2,
            client=fake,
        )
        try:
            for index, request_ms in enumerate((10.0, 20.0, 30.0)):
                fake.inference_request_ms = request_ms
                fake.socket_round_trip_ms = request_ms - 2.0
                sequence = client.submit(f"frame-{index}", model_version="3.4")
                self.assertTrue(fake.wait_for_inferences(index + 1))
                deadline = time.monotonic() + 0.2
                sample = None
                while sample is None or sample["sequence"] != sequence:
                    if time.monotonic() >= deadline:
                        self.fail("latency sample was not recorded")
                    sample = client.get_latest_sample("3.4", max_age_sec=1.0)
                    time.sleep(0.002)

            summary = client.get_latency_summary()
            self.assertEqual(summary["sample_count"], 2)
            self.assertEqual(summary["window_size"], 2)
            self.assertAlmostEqual(summary["inference_request_ms"]["mean"], 25.0)
            self.assertAlmostEqual(summary["inference_request_ms"]["p50"], 25.0)
            self.assertAlmostEqual(summary["inference_request_ms"]["p95"], 29.5)
        finally:
            client.close()

    def test_history_matches_ten_hz_training_cadence_and_latest_manual_target(self):
        fake = RecordingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            history_sample_interval_sec=0.1,
            client=fake,
        )
        try:
            client.observe_manual_steering(62.0, sampled_at=1.00)
            client.observe_manual_steering(70.0, sampled_at=1.04)  # too soon: ignored
            client.observe_manual_steering(71.0, sampled_at=1.10)
            client.observe_manual_steering(83.0, sampled_at=1.20)
            client.begin_autonomous_sequence(88.0, sampled_at=1.25)

            client.submit("first-auto-frame", model_version="4.0a")
            self.assertTrue(fake.wait_for_inferences(1))
            self.assertEqual(fake.infer_histories[0], (71.0, 83.0, 88.0))
        finally:
            client.close()

    def test_new_autonomy_sequence_discards_an_older_inflight_result(self):
        class SequencedBlockingClient(RecordingFakeClient):
            def __init__(self):
                super().__init__()
                self.first_started = threading.Event()
                self.release_first = threading.Event()

            def infer(self, frame, model_version=None, target_history=None):
                if frame == "old-frame":
                    self.first_started.set()
                    self.release_first.wait(timeout=0.5)
                    return 140.0, 0.0
                return super().infer(frame, model_version, target_history)

        fake = SequencedBlockingClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            history_sample_interval_sec=0.0,
            client=fake,
        )
        try:
            client.submit("old-frame", model_version="3.4")
            self.assertTrue(fake.first_started.wait(timeout=0.2))
            client.begin_autonomous_sequence(77.0)
            fake.release_first.set()
            client.submit("new-frame", model_version="4.0p")
            self.assertTrue(fake.wait_for_inferences(1))

            deadline = time.monotonic() + 0.5
            sample = None
            while sample is None and time.monotonic() < deadline:
                sample = client.get_latest_sample("4.0p", max_age_sec=1.0)
                time.sleep(0.005)
            self.assertIsNotNone(sample)
            self.assertEqual(sample["result"], (90.0, 0.0))
            self.assertIsNone(client.get_latest_sample("3.4", max_age_sec=1.0))
        finally:
            fake.release_first.set()
            client.close()

    def test_manual_takeover_discards_an_inflight_autonomous_result(self):
        class BlockingInferenceClient(RecordingFakeClient):
            def __init__(self):
                super().__init__()
                self.started = threading.Event()
                self.release = threading.Event()

            def infer(self, frame, model_version=None, target_history=None):
                self.started.set()
                self.release.wait(timeout=0.5)
                return 140.0, 0.0

        fake = BlockingInferenceClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            history_sample_interval_sec=0.0,
            client=fake,
        )
        try:
            client.begin_autonomous_sequence(83.0)
            client.submit("auto-frame", model_version="4.0p")
            self.assertTrue(fake.started.wait(timeout=0.2))

            client.observe_manual_steering(62.0)
            fake.release.set()
            time.sleep(0.03)

            self.assertIsNone(client.get_latest_sample("4.0p", max_age_sec=1.0))
            self.assertEqual(client._target_history[-1], 62.0)
        finally:
            fake.release.set()
            client.close()

    def test_nonfinite_manual_history_is_ignored(self):
        fake = RecordingFakeClient()
        client = AsyncJetsonSteeringClient(
            "10.42.0.2",
            status_interval_sec=10.0,
            history_sample_interval_sec=0.0,
            client=fake,
        )
        try:
            before = tuple(client._target_history)
            client.observe_manual_steering(float("nan"))
            self.assertEqual(tuple(client._target_history), before)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
