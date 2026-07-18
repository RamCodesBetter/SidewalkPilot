#!/usr/bin/python3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


CURRENT_DIR = Path(__file__).resolve().parents[2] / "controller" / "current"
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from rc_car_app.interruption_recorder import InterruptionClipRecorder


class InterruptionRecorderShippingTests(unittest.TestCase):
    def test_existing_clips_ship_when_current_run_recording_is_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clip = Path(temp_dir) / "clip_20260718_120000.mp4"
            clip.write_bytes(b"existing clip")
            recorder = InterruptionClipRecorder(out_dir=temp_dir, enabled=False)

            self.assertFalse(recorder.enabled)
            with mock.patch("rc_car_app.interruption_recorder.subprocess.run") as run:
                recorder.ship_to_jon("10.42.0.2")

            run.assert_called_once()
            command = run.call_args.args[0]
            self.assertIn(str(clip), command)
            self.assertEqual(command[-1], "ram@10.42.0.2:/nvme/interruption_clips/")
            self.assertIn("--remove-source-files", command)

    def test_missing_host_keeps_existing_clips_local(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            clip = Path(temp_dir) / "clip_20260718_120000.mp4"
            clip.write_bytes(b"existing clip")
            recorder = InterruptionClipRecorder(out_dir=temp_dir, enabled=False)

            with mock.patch("rc_car_app.interruption_recorder.subprocess.run") as run:
                recorder.ship_to_jon("")

            run.assert_not_called()
            self.assertTrue(clip.exists())


if __name__ == "__main__":
    unittest.main()
