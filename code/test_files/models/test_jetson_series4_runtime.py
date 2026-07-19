#!/usr/bin/env python3
"""Regression tests for Series 4 contracts in the live Jon inference service."""

import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


CONTROLLER_DIR = Path(__file__).resolve().parents[2] / "controller" / "current"
if str(CONTROLLER_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_DIR))

from rc_car_app import jetson_inference_server as jis  # noqa: E402
from rc_car_app.jetson_client import JetsonSteeringClient  # noqa: E402
from rc_car_app.vision import STEERING_MODEL_VERSIONS  # noqa: E402


def hybrid18(bucket, offset_raw=0.0):
    output = np.full(18, -20.0, dtype=np.float32)
    output[int(bucket)] = 20.0
    output[9 + int(bucket)] = float(offset_raw)
    return output


class FakeSession:
    def __init__(self, output):
        self.output = np.asarray(output, dtype=np.float32)
        self.feeds = []

    def run(self, _output_names, feeds):
        self.feeds.append({key: value.copy() for key, value in feeds.items()})
        return [self.output]


class JetsonSeries4RuntimeTests(unittest.TestCase):
    def test_all_series4_versions_are_selectable(self):
        expected = {
            "4.0p", "4.0r", "4.0f", "4.0g", "4.0a", "4.0c",
            "4.1p", "4.1r", "4.1f", "4.1g", "4.1a", "4.1c",
        }
        self.assertTrue(expected.issubset(set(STEERING_MODEL_VERSIONS)))

    def test_series4_decodes_current_horizon_only(self):
        output = np.stack(
            (
                hybrid18(1),
                hybrid18(8),
                hybrid18(7),
                hybrid18(6),
            ),
            axis=0,
        )[None, ...]

        steering, throttle = jis.decode_output(output)
        probabilities = jis.decode_probs9(output)

        self.assertAlmostEqual(steering, 52.5, places=4)
        self.assertEqual(throttle, 0.0)
        self.assertEqual(int(np.argmax(probabilities)), 1)
        self.assertAlmostEqual(float(np.sum(probabilities)), 1.0, places=5)

    def test_all_versions_require_their_exact_onnx_contract(self):
        expected = {
            "4.0p": (3, ["batch", 1, 18]),
            "4.0r": (3, ["batch", 1, 18]),
            "4.0f": (0, ["batch", 4, 18]),
            "4.0g": (0, ["batch", 4, 18]),
            "4.0a": (3, ["batch", 4, 18]),
            "4.0c": (3, ["batch", 4, 18]),
            "4.1p": (3, ["batch", 1, 18]),
            "4.1r": (3, ["batch", 1, 18]),
            "4.1f": (0, ["batch", 4, 18]),
            "4.1g": (0, ["batch", 4, 18]),
            "4.1a": (3, ["batch", 4, 18]),
            "4.1c": (3, ["batch", 4, 18]),
        }
        for version, (history_steps, output_shape) in expected.items():
            with self.subTest(version=version):
                jis._validate_series4_contract(version, history_steps, output_shape)

    def test_mislabeled_series4_contract_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "contract mismatch"):
            jis._validate_series4_contract("4.1f", 3, ["batch", 1, 18])

    def test_pc_history_is_fed_then_updated_with_decoded_target(self):
        session = FakeSession(hybrid18(6)[None, None, :])
        model = jis.SteeringModel.__new__(jis.SteeringModel)
        model.backend = "onnx"
        model.session = session
        model.input_name = "image"
        model.history_input_name = "target_history"
        model.history_steps = 3
        model.target_history = [90.0, 90.0, 90.0]
        model.width = 320
        model.height = 180
        model.use_clahe = False

        with mock.patch.object(
            jis,
            "preprocess",
            return_value=np.zeros((1, 3, 180, 320), dtype=np.float32),
        ):
            steering, throttle, _probabilities = model.infer(np.zeros((2, 2, 3)))

        np.testing.assert_allclose(
            session.feeds[0]["target_history"],
            np.asarray([[90.0, 90.0, 90.0]], dtype=np.float32),
        )
        self.assertAlmostEqual(steering, 112.5, places=4)
        self.assertEqual(throttle, 0.0)
        np.testing.assert_allclose(model.target_history, [90.0, 90.0, 112.5])

        model.reset_temporal_state()
        self.assertEqual(model.target_history, [90.0, 90.0, 90.0])

        model.set_target_history([62.0, 71.0, 83.0])
        self.assertEqual(model.target_history, [62.0, 71.0, 83.0])

    def test_history_seed_requires_exact_contract_length(self):
        model = jis.SteeringModel.__new__(jis.SteeringModel)
        model.history_steps = 3
        model.target_history = [90.0, 90.0, 90.0]
        with self.assertRaisesRegex(ValueError, "expected 3"):
            model.set_target_history([80.0, 90.0])
        with self.assertRaisesRegex(ValueError, "finite values"):
            model.set_target_history([80.0, float("nan"), 90.0])

    def test_failed_hot_swap_restores_the_previous_model_state(self):
        model = jis.SteeringModel.__new__(jis.SteeringModel)
        model.current_version = "3.4"
        model.use_clahe = False
        model.session = "working-session"

        def failed_load(_spec):
            model.use_clahe = True
            model.session = "partial-session"
            raise RuntimeError("bad model")

        model.load = failed_load
        self.assertFalse(model.ensure_version("4.0p"))
        self.assertEqual(model.current_version, "3.4")
        self.assertFalse(model.use_clahe)
        self.assertEqual(model.session, "working-session")

    def test_failed_or_pinned_model_switch_is_rejected(self):
        failed = mock.Mock(current_version="3.4", pinned=False)
        failed.ensure_version.return_value = False
        self.assertFalse(jis._activate_requested_model(failed, "4.0p"))

        pinned = mock.Mock(current_version="3.4", pinned=True)
        self.assertTrue(jis._activate_requested_model(pinned, "3.4"))
        self.assertFalse(jis._activate_requested_model(pinned, "4.0p"))
        pinned.ensure_version.assert_not_called()

    def test_nonfinite_model_output_is_rejected(self):
        output = hybrid18(4)[None, None, :]
        output[0, 0, 4] = np.nan
        session = FakeSession(output)
        model = jis.SteeringModel.__new__(jis.SteeringModel)
        model.backend = "onnx"
        model.session = session
        model.input_name = "image"
        model.history_input_name = None
        model.history_steps = 0
        model.target_history = []
        model.width = 320
        model.height = 180
        model.use_clahe = False
        with mock.patch.object(
            jis,
            "preprocess",
            return_value=np.zeros((1, 3, 180, 320), dtype=np.float32),
        ):
            with self.assertRaisesRegex(RuntimeError, "non-finite"):
                model.infer(np.zeros((2, 2, 3)))

    def test_v2_socket_round_trip_delivers_manual_history(self):
        class CaptureSocket:
            def __init__(self):
                self.sent = bytearray()
                self.reply = bytearray(jis.struct.pack(">15f", *([0.0] * 15)))

            def sendall(self, payload):
                self.sent.extend(payload)

            def recv(self, size):
                chunk = bytes(self.reply[:size])
                del self.reply[:size]
                return chunk

            def close(self):
                pass

        class MemoryConnection:
            def __init__(self, payload):
                self.payload = bytearray(payload)

            def recv(self, size):
                chunk = bytes(self.payload[:size])
                del self.payload[:size]
                return chunk

        wire = CaptureSocket()
        client = JetsonSteeringClient("unused")
        client.sock = wire
        client.infer(
            np.zeros((32, 32, 3), dtype=np.uint8),
            model_version="4.1p",
            target_history=(62.0, 71.0, 83.0),
        )

        version, history, jpeg = jis._recv_request(MemoryConnection(wire.sent))
        self.assertEqual(version, "4.1p")
        np.testing.assert_allclose(history, (62.0, 71.0, 83.0))
        self.assertGreater(len(jpeg), 0)

    def test_client_rejects_nonfinite_history_without_sending(self):
        class NoSendSocket:
            def __init__(self):
                self.sent = False

            def sendall(self, _payload):
                self.sent = True

            def close(self):
                pass

        wire = NoSendSocket()
        client = JetsonSteeringClient("unused")
        client.sock = wire
        result = client.infer(
            np.zeros((32, 32, 3), dtype=np.uint8),
            model_version="4.0p",
            target_history=(62.0, float("nan"), 83.0),
        )
        self.assertIsNone(result)
        self.assertFalse(wire.sent)

    def test_existing_series_decoders_are_unchanged(self):
        steering, throttle = jis.decode_output(np.asarray([[0.5, -0.5]], dtype=np.float32))
        self.assertAlmostEqual(steering, 135.0)
        self.assertAlmostEqual(throttle, 0.25)

        hybrid19 = np.concatenate((hybrid18(4), np.asarray([0.0], dtype=np.float32)))
        steering, throttle = jis.decode_output(hybrid19[None, :])
        self.assertAlmostEqual(steering, 90.0)
        self.assertAlmostEqual(throttle, 0.5)


if __name__ == "__main__":
    unittest.main()
