#!/usr/bin/env python3
"""Regression checks for the temporary Raspberry Pi inference mode."""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock


ENTRYPOINT = (
    Path(__file__).resolve().parents[2] / "controller" / "current" / "rc_car.py"
)
SPEC = importlib.util.spec_from_file_location(
    "sidewalkpilot_rc_car_entrypoint", ENTRYPOINT
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not import controller entrypoint: {ENTRYPOINT}")
ENTRYPOINT_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENTRYPOINT_MODULE)


class LocalPiInferenceModeTests(unittest.TestCase):
    def test_local_mode_is_opt_in(self):
        self.assertFalse(ENTRYPOINT_MODULE._parser().parse_args([]).local_inference)
        self.assertTrue(
            ENTRYPOINT_MODULE._parser()
            .parse_args(["--local-inference"])
            .local_inference
        )

    @mock.patch.object(ENTRYPOINT_MODULE, "_wait_for_local_server")
    @mock.patch.object(ENTRYPOINT_MODULE, "_ensure_port_available")
    @mock.patch.object(ENTRYPOINT_MODULE.subprocess, "Popen")
    def test_local_server_uses_existing_inference_service(
        self, popen, ensure_port_available, wait_for_local_server
    ):
        process = popen.return_value

        result = ENTRYPOINT_MODULE._start_local_server(8770)

        self.assertIs(result, process)
        ensure_port_available.assert_called_once_with("127.0.0.1", 8770)
        command = popen.call_args.args[0]
        self.assertEqual(command[0], ENTRYPOINT_MODULE.sys.executable)
        self.assertTrue(command[1].endswith("rc_car_app/jetson_inference_server.py"))
        self.assertEqual(
            command[2:],
            ["--model", "highest", "--host", "127.0.0.1", "--port", "8770"],
        )
        wait_for_local_server.assert_called_once_with(
            process, "127.0.0.1", 8770
        )

    def test_stop_terminates_managed_server(self):
        process = mock.Mock()
        process.poll.return_value = None

        ENTRYPOINT_MODULE._stop_local_server(process)

        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5.0)
        process.kill.assert_not_called()

    def test_stop_kills_server_that_ignores_terminate(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="local-inference", timeout=5.0),
            0,
        ]

        ENTRYPOINT_MODULE._stop_local_server(process)

        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(
            process.wait.call_args_list,
            [mock.call(timeout=5.0), mock.call(timeout=2.0)],
        )


if __name__ == "__main__":
    unittest.main()
