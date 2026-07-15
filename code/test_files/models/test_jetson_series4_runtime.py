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
    def test_all_six_series4_versions_are_selectable(self):
        expected = {"4.0p", "4.0r", "4.0f", "4.0g", "4.0a", "4.0c"}
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
