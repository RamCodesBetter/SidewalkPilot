from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools"))
import workspace
workspace.activate()
from run_single_corridor_campaign import instance


class SingleCorridorTests(unittest.TestCase):
    def setUp(self):
        self.mask = np.zeros((72,128), bool)
        self.mask[20:,25:100] = True

    def test_duplicate_masks_are_one_proposal(self):
        best, reason = instance([self.mask,self.mask],[.69,.88],.65)
        self.assertIsNone(reason)
        self.assertEqual(best[0],.88)
        np.testing.assert_array_equal(best[1],self.mask)

    def test_competing_anchored_corridors_defer(self):
        other = self.mask.copy()
        other[:,25:50] = False
        self.assertEqual(instance([self.mask,other],[.9,.8],.65)[1],"competing_sidewalk_instances")

    def test_low_score_fragment_and_empty_defer(self):
        fragmented = self.mask.copy()
        fragmented[:8,:8] = True
        for masks,scores in (([self.mask],[.4]),([fragmented],[.95]),([],[])):
            self.assertIsNone(instance(masks,scores,.65)[0])
