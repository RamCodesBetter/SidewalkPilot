from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5/tools/datasets"))
from campaign10k import CampaignSampler, allocate


class CampaignTests(unittest.TestCase):
    def test_exact_sizes_and_pinned_group(self):
        groups={i:list(range(100)) for i in range(100)}
        parts=allocate(groups,{3,6},7)
        self.assertEqual([len(parts[k])*100 for k in ("train","validation","test")],[8000,1000,1000])
        self.assertTrue({3,6}<=parts["train"])
        self.assertEqual(len(set.union(*parts.values())),100)
        self.assertEqual(allocate(groups,{3,6},7),parts)

    def test_epoch_visits_each_image_once(self):
        sampler=CampaignSampler(list(range(17)),8,42)
        first=list(sampler)
        self.assertEqual(sorted(i for b in first for i,_ in b),list(range(17)))
        self.assertEqual(len(first),len(sampler))
        sampler.epoch+=1
        self.assertNotEqual(first,list(sampler))
