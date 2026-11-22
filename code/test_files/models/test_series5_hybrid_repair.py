"""Regression guards for localized proposal edits."""
from pathlib import Path
import sys
import unittest
import tempfile
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'ai_models_datasets/series_5/tools'))
from hybrid_repair_pilot import merge_local, rectangle
from package_hybrid_review import guarded_region, reconstruct, polygon_region
from label_grounded_sam2 import save_mask, sha256


class HybridRepairTests(unittest.TestCase):
    def test_rectangle_is_half_open(self):
        mask=rectangle([1,2,4,5],(6,7))
        self.assertEqual(mask.shape,(7,6))
        self.assertEqual(int(mask.sum()),9)
        self.assertTrue(mask[2,1]);self.assertFalse(mask[5,4])

    def test_invalid_rectangles(self):
        for box in ([0,0,8,7],[-1,0,4,3],[1,1,1,2],[0.,0,2,2],[0,0,2],None):
            with self.assertRaises(ValueError):rectangle(box,(6,7))

    def test_replace_preserves_every_pixel_outside_region(self):
        before=np.array([[0,1,255],[1,1,0],[255,0,1]],dtype=np.uint8)
        region=rectangle([1,0,3,2],(3,3))
        output=merge_local(before,np.zeros((3,3),bool),region,'replace')
        np.testing.assert_array_equal(output[~region],before[~region])
        self.assertTrue((output[region]==0).all())
        self.assertEqual(before[0,2],255)

    def test_add_never_removes_sidewalk(self):
        before=np.ones((4,4),dtype=np.uint8);before[1,1]=0
        predicted=np.zeros((4,4),bool);predicted[1,1]=True
        output=merge_local(before,predicted,np.ones((4,4),bool),'add')
        self.assertTrue((output==1).all())

    def test_subtract_does_not_fill_existing_holes(self):
        before=np.ones((4,4),dtype=np.uint8);before[0,0]=0
        predicted=np.zeros((4,4),bool);predicted[2,2]=True
        output=merge_local(before,predicted,np.ones((4,4),bool),'subtract')
        self.assertEqual(output[0,0],0);self.assertEqual(output[2,2],0)
        self.assertEqual(int((output==1).sum()),14)

    def test_empty_region_preserves_baseline(self):
        before=np.arange(9,dtype=np.uint8).reshape(3,3)%2
        for mode in ('add','subtract','replace'):
            np.testing.assert_array_equal(merge_local(before,np.ones((3,3),bool),np.zeros((3,3),bool),mode),before)

    def test_invalid_merge(self):
        mask=np.zeros((3,3),dtype=np.uint8);region=np.ones((3,3),bool)
        with self.assertRaises(ValueError):merge_local(mask,region,np.ones((2,2),bool),'add')
        with self.assertRaises(ValueError):merge_local(mask,region,region,'unknown')
        with self.assertRaises(ValueError):merge_local(np.full((3,3),2),region,region,'add')

    def test_guard_protects_interior(self):
        inside=np.zeros((12,12),bool);inside[2:10,2:10]=True
        region=guarded_region(np.ones((12,12),bool),inside,1)
        self.assertTrue(region[0,0]);self.assertTrue(region[2,2])
        self.assertFalse(region[5,5])
        np.testing.assert_array_equal(guarded_region(np.ones((12,12),bool),inside,0),~inside)
        with self.assertRaises(ValueError):guarded_region(region,inside,-1)

    def test_rejected_and_ineligible_candidates(self):
        baseline=np.ones((8,8),dtype=np.uint8)
        record={'operations':[{'eligible':False}]}
        decision={'operations':[{'accept':False,'reason':'failed points'}],'direct_edits':[]}
        output,report=reconstruct(baseline,record,decision,baseline.astype(bool),Path('/unused'))
        np.testing.assert_array_equal(output,baseline)
        self.assertEqual(report['changed_pixels'],0)
        decision['operations'][0]['accept']=True
        with self.assertRaises(ValueError):reconstruct(baseline,record,decision,baseline.astype(bool),Path('/unused'))

    def test_candidate_identity_and_locality(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'candidate.png'
            save_mask(path,np.ones((2,2),np.uint8))
            baseline=np.ones((8,8),np.uint8)
            record={'operations':[{'eligible':True,'candidate':'candidate.png','candidate_sha256':sha256(path),
                'operation':{'kind':'sam','mode':'subtract','region':[3,3,5,5],'crop':[3,3,5,5]}}]}
            decision={'operations':[{'accept':True,'reason':'inspected'}],'direct_edits':[]}
            output,report=reconstruct(baseline,record,decision,baseline.astype(bool),root)
            self.assertEqual(int((output==0).sum()),4)
            self.assertEqual(report['outside_effective_regions'],0)
            save_mask(path,np.zeros((2,2),np.uint8))
            with self.assertRaises(ValueError):reconstruct(baseline,record,decision,baseline.astype(bool),root)

    def test_explicit_uncertainty_edit(self):
        baseline=np.zeros((8,8),np.uint8)
        decision={'operations':[],'direct_edits':[{'value':255,'rectangle':[2,2,4,4],'reason':'blur'}]}
        output,report=reconstruct(baseline,{'operations':[]},decision,baseline.astype(bool),Path('/unused'))
        self.assertEqual(int((output==255).sum()),4)
        self.assertEqual(report['changed_pixels'],4)
        with self.assertRaises(ValueError):polygon_region([[0,0],[2,2],[8,7]],(8,8))

    def test_adoption_cannot_omit_operation(self):
        with self.assertRaises(ValueError):reconstruct(np.zeros((4,4),np.uint8),{'operations':[{}]},
            {'operations':[],'direct_edits':[]},np.zeros((4,4),bool),Path('/unused'))


if __name__=='__main__':unittest.main()
