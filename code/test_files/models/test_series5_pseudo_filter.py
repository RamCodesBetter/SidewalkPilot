import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai_models_datasets/series_5"))
from pseudo_mask_filter import filter_masks, POLICY


class PseudoFilterTests(unittest.TestCase):
    def test_agreement_labels_negative_and_preserves_unknown_edge(self):
        mask = np.zeros((100,100), dtype=np.uint8);mask[:,20:80]=1
        labels, report = filter_masks(mask,mask,[.9,.8])
        self.assertTrue(report["accepted_for_pseudo_training"])
        self.assertTrue(np.all(labels[:,30:70]==1))
        self.assertTrue(np.all(labels[:,:10]==0))
        self.assertTrue(np.any(labels==255))
        self.assertEqual(labels[-1,50],1)

    def test_disagreement_not_forced_into_background(self):
        a=np.zeros((100,100),dtype=np.uint8);a[:,20:80]=1
        b=a.copy();b[:,75:80]=0
        labels, _=filter_masks(a,b,[.9,.9])
        self.assertTrue(np.all(labels[:,76:80]==255))

    def test_empty_flooded_and_low_score_defer(self):
        for mask in (np.zeros((100,100)),np.ones((100,100))):
            self.assertFalse(filter_masks(mask,mask,[.9,.9])[1]["accepted_for_pseudo_training"])
        mask=np.zeros((100,100));mask[:,20:80]=1
        self.assertIn('weak_detection',filter_masks(mask,mask,[.3,.9])[1]["reasons"])

    def test_substantial_disconnected_sidewalk_is_not_deleted(self):
        mask=np.zeros((100,100));mask[:,20:80]=1;mask[20:30,3:13]=1
        labels,report=filter_masks(mask,mask,[.9,.9])
        self.assertIn('multiple_substantial_components',report['reasons'])
        self.assertEqual(labels[25,8],1)

    def test_speck_removal_never_becomes_negative(self):
        mask=np.zeros((100,100));mask[:,20:80]=1;mask[5,5]=1
        labels,report=filter_masks(mask,mask,[.9,.9])
        self.assertEqual(report['removed_speck_pixels'],1)
        self.assertEqual(labels[5,5],255)

    def test_holes_not_filled(self):
        mask=np.zeros((100,100));mask[:,20:80]=1;mask[30:40,40:50]=0
        labels,_=filter_masks(mask,mask,[.9,.9])
        self.assertEqual(labels[35,45],0)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):filter_masks(np.zeros((2,2)),np.zeros((3,2)),[.9,.9])
        with self.assertRaises(ValueError):filter_masks(np.full((2,2),255),np.zeros((2,2)),[.9,.9])
        with self.assertRaises(ValueError):filter_masks(np.zeros((2,2)),np.zeros((2,2)),[float('nan'),.9])

if __name__=='__main__':unittest.main()
