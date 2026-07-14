#!/usr/bin/env python3
import unittest
from pathlib import Path

import numpy as np
import torch

import series_4_common as s4


def frame(index, run, timestamp, steering):
    return s4.FrameRecord(
        index=index,
        path=Path(f"/{run}__photo_20260714_120000_{index:06d}.jpg"),
        steering=float(steering),
        source="real",
        run_key=run,
        timestamp=float(timestamp),
    )


class Series4TemporalTests(unittest.TestCase):
    def test_photo_identity_uses_run_and_microsecond_timestamp(self):
        root = Path("/dataset")
        path = root / "run_a__photo_20260714_120001_250000.jpg"
        run_key, timestamp = s4.parse_photo_identity(path, root)
        self.assertTrue(run_key.endswith("::run_a"))
        self.assertAlmostEqual(timestamp % 1.0, 0.25, places=4)

    def test_temporal_samples_stay_inside_run_and_split(self):
        frames = []
        for run_index, run_name in enumerate(("run_train", "run_val")):
            for offset in range(8):
                frames.append(frame(len(frames), run_name, run_index * 100 + offset * 0.1, 80 + offset))
        split = {
            item.index: ("train" if item.run_key == "run_train" else "val")
            for item in frames
        }
        samples, stats = s4.build_temporal_samples(frames, split, 2, 2, max_gap_sec=0.25)
        self.assertEqual(stats["train"], 4)
        self.assertEqual(stats["val"], 4)
        for sample in samples:
            self.assertEqual(len(sample.history), 2)
            self.assertEqual(len(sample.targets), 3)
            self.assertEqual(sample.anchor.run_key, "run_train" if sample.split == "train" else "run_val")

    def test_temporal_samples_reject_split_crossing_and_timestamp_gap(self):
        frames = [frame(i, "mixed_run", i * 0.1, 90 + i) for i in range(10)]
        frames += [frame(10 + i, "clean_val_run", 20 + i * 0.1, 80 + i) for i in range(6)]
        gap_times = (30.0, 30.1, 31.0, 31.1, 31.2, 31.3)
        frames += [frame(16 + i, "gap_train_run", stamp, 70 + i) for i, stamp in enumerate(gap_times)]
        split = {
            item.index: (
                "val"
                if item.run_key == "clean_val_run" or (item.run_key == "mixed_run" and item.index >= 5)
                else "train"
            )
            for item in frames
        }
        samples, stats = s4.build_temporal_samples(frames, split, 1, 1, max_gap_sec=0.25)
        self.assertGreater(stats["rejected_split"], 0)
        self.assertGreater(stats["rejected_gap"], 0)

    def test_mirror_applies_to_every_temporal_angle(self):
        values = np.asarray([10.0, 80.0, 90.0, 140.0, 180.0], dtype=np.float32)
        np.testing.assert_allclose(s4.mirror_angles(values), [170.0, 100.0, 90.0, 40.0, 0.0])

    def test_contract_output_shapes(self):
        image = torch.zeros(2, 3, 64, 64)
        pc = s4.SidewalkPilotV4(history_steps=3, future_steps=0).eval()
        cf = s4.SidewalkPilotV4(history_steps=0, future_steps=3).eval()
        pcf = s4.SidewalkPilotV4(history_steps=3, future_steps=3).eval()
        history = torch.full((2, 3), 90.0)
        with torch.no_grad():
            self.assertEqual(tuple(pc(image, history).shape), (2, 1, 18))
            self.assertEqual(tuple(cf(image).shape), (2, 4, 18))
            self.assertEqual(tuple(pcf(image, history).shape), (2, 4, 18))

    def test_temporal_loss_and_decode_cover_all_horizons(self):
        output = torch.randn(4, 4, 18, requires_grad=True)
        targets = torch.tensor(
            [[90.0, 100.0, 110.0, 120.0]] * 4,
            dtype=torch.float32,
        )
        loss, details = s4.temporal_hybrid_loss(output, targets, None, 1.0, 1.5, 0.7)
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertGreater(details["class_loss"], 0.0)
        self.assertEqual(tuple(s4.decode_hybrid(output.detach()).shape), (4, 4))


if __name__ == "__main__":
    unittest.main()
