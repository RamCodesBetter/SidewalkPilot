#!/usr/bin/env python3
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools"))
from prepare_targeted_corrections import FAILURES, select_rows


class TargetedSelectionTests(unittest.TestCase):
    def rows(self):
        rows = [{"pair": f"pair-{n:03d}", "image": f"run0__{n}.jpg", "gsam2_decision": "needs_correction",
                 "group": "both_need_correction", "gsam2_effort": "major", "sam3_effort": "major"} for n in FAILURES]
        rows += [{"pair": f"control-{i}", "image": f"run{i}__a.jpg", "gsam2_decision": "correct",
                  "group": "both_correct", "gsam2_effort": "none", "sam3_effort": "none"} for i in range(5)]
        return rows

    def test_fixed_failures_and_one_control_per_run(self):
        chosen = select_rows(self.rows())
        self.assertEqual(len(chosen), 17)
        self.assertEqual([r["pair"] for role, r in chosen if role == "failure"], [f"pair-{n:03d}" for n in FAILURES])
        self.assertEqual(len({r["image"].split("__")[0] for role, r in chosen if role == "control"}), 5)

    def test_selection_stable_under_input_reordering(self):
        self.assertEqual(select_rows(self.rows()), select_rows(list(reversed(self.rows()))))

    def test_reject_changed_failure_or_missing_control(self):
        rows = self.rows(); rows[0]["gsam2_decision"] = "correct"
        with self.assertRaises(ValueError):
            select_rows(rows)
        rows = self.rows(); rows[-1]["sam3_effort"] = "minor"
        with self.assertRaises(ValueError):
            select_rows(rows)

    def test_reject_duplicate_pair(self):
        rows = self.rows(); rows.append(rows[0])
        with self.assertRaises(ValueError):
            select_rows(rows)


if __name__ == "__main__":
    unittest.main()
