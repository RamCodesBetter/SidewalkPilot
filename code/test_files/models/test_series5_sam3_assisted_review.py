import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ai_models_datasets/series_5/tools'))
from workspace import activate
activate()
from label_grounded_sam2 import digest_json, sha256, write_json
from sam3_assisted_review import load_selection


class Sam3AssistedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / 'parent'
        (self.package / 'images').mkdir(parents=True)
        pairs = []
        for n in range(1, 4):
            path = self.package / f'images/{n:03d}.jpg'
            Image.new('RGB', (12, 8), (n*30, 100, 60)).save(path)
            frame = dict(id=f'pair-{n:03d}', source_pair_id=f'old-{n}', image=str(path.relative_to(self.package)),
                         source_name=f'source-{n}.jpg', source_sha256=sha256(path), size=[12, 8])
            pairs.append(frame)
        self.manifest = dict(kind='sidewalkpilot-paired-class1-v1', count=3, pairs=pairs)
        self.save_manifest()

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


if __name__ == "__main__":
    unittest.main()
