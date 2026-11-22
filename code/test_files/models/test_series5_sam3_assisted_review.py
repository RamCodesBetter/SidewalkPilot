import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ai_models_datasets/series_5'))
from label_grounded_sam2 import digest_json, sha256, write_json
from sam3_assisted_review import CHECKPOINT_SHA256, MODEL_REVISION, build, load_inputs, load_selection, revise


class Sam3AssistedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package, self.sam3 = self.root / 'parent', self.root / 'raw'
        (self.package / 'images').mkdir(parents=True)
        (self.sam3 / 'records').mkdir(parents=True)
        (self.sam3 / 'masks').mkdir()
        pairs, records = [], []
        for n in range(1, 4):
            path = self.package / f'images/{n:03d}.jpg'
            Image.new('RGB', (12, 8), (n*30, 100, 60)).save(path)
            frame = dict(id=f'pair-{n:03d}', source_pair_id=f'old-{n}', image=str(path.relative_to(self.package)),
                         source_name=f'source-{n}.jpg', source_sha256=sha256(path), size=[12, 8])
            pairs.append(frame)
            mask = np.full((8, 12), 255, dtype=np.uint8)
            if n != 2:
                mask[4:] = 1
            mp = self.sam3 / f'masks/{n:02d}.png'
            Image.fromarray(mask).save(mp)
            record = {k: frame[k] for k in ('image','size','source_sha256')}
            record['instance_union'] = dict(path=str(mp.relative_to(self.sam3)), sha256=sha256(mp))
            records.append(record)
            write_json(self.sam3 / f'records/{n:02d}.json', record)
        self.manifest = dict(kind='sidewalkpilot-paired-class1-v1', count=3, pairs=pairs)
        self.save_manifest()
        self.config = dict(model='facebook/sam3', native_sam3_control=True, prompt='concrete sidewalk',
                           revision=MODEL_REVISION, checkpoint_sha256=CHECKPOINT_SHA256,
                           score_threshold=.4, mask_threshold=.5, load_report={'strict': True},
                           selection_sha256=sha256(self.package / 'manifest.json'))
        write_json(self.sam3 / 'config.json', self.config)
        write_json(self.sam3 / 'summary.json', dict(count=3, images=records))
        self.plan = dict(schema='sidewalkpilot-sam3-ai-edits-v1', parent_package_id=self.manifest['package_id'],
                         sam3_config_sha256=sha256(self.sam3 / 'config.json'), frames=[
            dict(id='pair-001', raw_mask_sha256=records[0]['instance_union']['sha256'], action='correct',
                 observation='Known shadow on pavement', edits=[dict(rectangle=[3,2,7,5], value=1, reason='Shadow')]),
            dict(id='pair-002', raw_mask_sha256=records[1]['instance_union']['sha256'], action='defer',
                 observation='Empty prediction unresolved', edits=[]),
            dict(id='pair-003', raw_mask_sha256=records[2]['instance_union']['sha256'], action='keep',
                 observation='No local edit identified', edits=[])])
        self.edits = self.root / 'edits.json'
        write_json(self.edits, self.plan)

    def save_manifest(self):
        self.manifest.pop('package_id', None)
        self.manifest['package_id'] = digest_json(self.manifest)
        write_json(self.package / 'manifest.json', self.manifest)

    def test_selection_uses_originals_without_loading_parent_masks(self):
        selection = load_selection(self.package)
        self.assertEqual(selection['count'], 3)
        self.assertEqual(selection['frames'][0]['source_pair_id'], 'old-1')
        self.assertIn('not a fresh random audit', selection['sampling'])
        self.assertFalse((self.package / 'masks').exists())

    def test_invalid_selection_identity_and_paths(self):
        initial = copy.deepcopy(self.manifest)
        for kind in ('count','duplicate','path','dimensions','source','hash'):
            self.manifest = copy.deepcopy(initial)
            if kind == 'count': self.manifest['count'] = 4
            if kind == 'duplicate': self.manifest['pairs'][1]['source_sha256'] = self.manifest['pairs'][0]['source_sha256']
            if kind == 'path': self.manifest['pairs'][0]['image'] = '../outside.jpg'
            if kind == 'dimensions': self.manifest['pairs'][0]['size'] = [1,1]
            if kind == 'source': self.manifest['pairs'][0]['source_sha256'] = 'bad'
            self.save_manifest()
            if kind == 'hash':
                write_json(self.package / 'manifest.json', dict(self.manifest, package_id='bad'))
            with self.subTest(kind=kind), self.assertRaises((ValueError, FileNotFoundError)):
                load_selection(self.package)

    def test_reject_other_recipe_or_changed_raw_mask(self):
        for change in (dict(model='sam2'), dict(native_sam3_control=False), dict(prompt='sidewalk'),
                       dict(score_threshold=.5), dict(mask_threshold=.4), dict(load_report={'strict': False}),
                       dict(selection_sha256='bad'), dict(revision='other'), dict(checkpoint_sha256='bad')):
            write_json(self.sam3 / 'config.json', dict(self.config, **change))
            with self.subTest(change=change), self.assertRaises(ValueError):
                load_inputs(self.package, self.sam3)
        write_json(self.sam3 / 'config.json', self.config)
        Image.new('L', (12,8), 1).save(self.sam3 / 'masks/01.png')
        with self.assertRaises(ValueError):
            load_inputs(self.package, self.sam3)

    def test_revise_locality_keep_defer_and_input_immutability(self):
        _, rows = load_inputs(self.package, self.sam3)
        labels = rows[0][2]
        before = labels.copy()
        output, report = revise(labels, self.plan['frames'][0])
        self.assertTrue(np.array_equal(labels, before))
        self.assertEqual(report['sidewalk_pixels_added'], 8)
        self.assertEqual(report['sidewalk_pixels_removed'], 0)
        self.assertTrue(np.array_equal(output[:, :3], labels[:, :3]))
        for decision, (_, _, labels) in zip(self.plan['frames'][1:], rows[1:]):
            out, report = revise(labels, decision)
            self.assertTrue(np.array_equal(out, labels))
            self.assertEqual(report['changed_pixels'], 0)

    def test_invalid_decisions_fail_closed(self):
        labels = np.full((8,12),255,dtype=np.uint8)
        good = self.plan['frames'][0]
        for change in (dict(action='auto'), dict(observation=''), dict(edits=[]), dict(action='keep'),
                       dict(edits=[dict(rectangle=[0,0,13,8], value=1, reason='outside')]),
                       dict(edits=[dict(rectangle=[0,0,2,2], value=255, reason='no change')])):
            with self.subTest(change=change), self.assertRaises(ValueError):
                revise(labels, dict(good, **change))

    def test_package_preserves_raw_and_has_no_accepted_decisions(self):
        tracked = {p: sha256(p) for root in (self.package,self.sam3) for p in root.rglob('*') if p.is_file()}
        out, private = self.root / 'viewer', self.root / 'private.json'
        with contextlib.redirect_stdout(io.StringIO()):
            build(self.package,self.sam3,out,self.edits,private)
        manifest = json.loads((out / 'manifest.json').read_text())
        mapping = json.loads(private.read_text())
        content = {k:v for k,v in manifest.items() if k != 'package_id'}
        self.assertEqual(digest_json(content),manifest['package_id'])
        self.assertNotIn('decisions', manifest)
        self.assertEqual(manifest['package_id'],mapping['package_id'])
        for n, frame in enumerate(manifest['pairs'],1):
            for side, candidate in frame['candidates'].items():
                p = out / candidate['mask']
                self.assertEqual(sha256(p),candidate['mask_sha256'])
                values = np.array(Image.open(p))
                rle = candidate['rle']
                expected = sum(length for i,length in enumerate(rle['lengths']) if (rle['first']+i)%2)
                self.assertEqual(int((values==1).sum()),expected)
                if n != 1 or mapping['pairs'][frame['id']][side] == 'sam3_raw':
                    self.assertEqual(p.read_bytes(),(self.sam3/f'masks/{n:02d}.png').read_bytes())
        self.assertTrue(all(sha256(p)==h for p,h in tracked.items()))
        with self.assertRaises(ValueError):
            build(self.package,self.sam3,out,self.edits,private)

    def test_bad_edit_identity_writes_nothing(self):
        for change in ('config','order','raw'):
            plan = copy.deepcopy(self.plan)
            if change == 'config': plan['sam3_config_sha256'] = 'bad'
            if change == 'order': plan['frames'].reverse()
            if change == 'raw': plan['frames'][0]['raw_mask_sha256'] = 'bad'
            write_json(self.edits,plan)
            out = self.root / 'invalid'
            with self.subTest(change=change), self.assertRaises(ValueError):
                build(self.package,self.sam3,out,self.edits,self.root/'private.json')
            self.assertFalse(out.exists())

    def test_private_mapping_cannot_write_into_inputs(self):
        out = self.root / 'invalid'
        for root in (self.package,self.sam3,out):
            with self.subTest(root=root), self.assertRaises(ValueError):
                build(self.package,self.sam3,out,self.edits,root/'private.json')
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
