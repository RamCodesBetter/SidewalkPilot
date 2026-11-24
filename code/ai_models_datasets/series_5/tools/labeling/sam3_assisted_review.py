"""Read a historical paired selection for the pinned SAM diagnostic."""
import copy
import json

from PIL import Image

from evaluate_class1_corrections import safe_file
from label_grounded_sam2 import digest_json, sha256


def load_selection(package):
    package = package.resolve()
    manifest = json.loads((package / 'manifest.json').read_text())
    content = {k:v for k,v in manifest.items() if k != 'package_id'}
    pairs = manifest.get('pairs', [])
    if (manifest.get('kind') != 'sidewalkpilot-paired-class1-v1'
            or not 0 < len(pairs) <= 30 or manifest.get('count') != len(pairs)
            or digest_json(content) != manifest.get('package_id')
            or len({p['id'] for p in pairs}) != len(pairs)
            or len({p['source_sha256'] for p in pairs}) != len(pairs)):
        raise ValueError('Expected an intact, distinct paired development pilot of at most 30 images')
    frames = []
    for pair in pairs:
        path = safe_file(package, pair['image'])
        with Image.open(path) as image:
            if sha256(path) != pair['source_sha256'] or list(image.size) != pair['size']:
                raise ValueError('Source image identity changed')
        frames.append({k:copy.deepcopy(pair[k]) for k in ('id','image','size','source_sha256','source_name')})
        frames[-1]['source_pair_id'] = pair.get('source_pair_id', pair['id'])
    return dict(source=str(package), parent_package_id=manifest['package_id'], frames=frames,
                images=[f['image'] for f in frames], count=len(frames),
                selection_sha256=sha256(package / 'manifest.json'),
                sampling='Repeated targeted development images; not a fresh random audit')
