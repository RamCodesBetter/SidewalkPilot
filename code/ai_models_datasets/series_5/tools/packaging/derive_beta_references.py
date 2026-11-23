#!/usr/bin/env python3
"""Viewer-only binary comparison references; unknown complements remain provisional."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np
from PIL import Image

from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from package_beta_comparison import ASSETS
from package_model_review import mask_record
from prepare_reviewed_dataset import safe_file

HERE = _workspace.TOOLS
POLICY = {
    'version': 'viewer-binary-complement-v1',
    'foreground': 'Keep the accepted reference sidewalk outline exactly (class 1).',
    'background': 'For comparison only, treat unknown pixels outside that outline as background (class 0).',
    'provisional': 'Derived masks are not independently verified full-image annotations or final ground truth.',
    'preservation': 'Original references, predictions, training data, and checkpoints are unchanged.',
    'miou': 'Arithmetic mean of sidewalk and background IoU; a class with zero union is excluded.',
}


def derive(labels):
    if labels.dtype != np.uint8 or labels.ndim != 2 or not np.isin(labels, (0, 1, 255)).all():
        raise ValueError('Expected a 2D 0/1/255 reference')
    unknown = int((labels == 255).sum())
    return np.where(labels == 1, 1, 0).astype(np.uint8), unknown


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or source == output or source in output.parents or output in source.parents:
        raise ValueError('Use a new output directory separate from the source viewer')
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest.get('schema') != 'sidewalkpilot-beta-comparison-v1' or manifest.get('comparison_reference_id'):
        raise ValueError('Expected an original paired comparison package')
    checksums = json.loads((source/'integrity-check.json').read_text())['files_sha256']
    required = {'manifest.json'}
    for frame in manifest['frames']:
        required.update([frame['image'], frame['reference']['path'], *(r['path'] for r in frame['predictions'].values())])
    if not required <= checksums.keys():
        raise ValueError('Incomplete package integrity record')
    for name, expected in checksums.items():
        if sha256(safe_file(source, name)) != expected:
            raise ValueError(f'Source package changed: {name}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.binary-reference-', dir=output.parent) as tmp:
        root = Path(tmp)/'package'
        shutil.copytree(source, root)
        (root/'comparison-references').mkdir()
        shutil.copy2(source/'manifest.json', root/'provenance/original-comparison-manifest.json')
        updated = copy.deepcopy(manifest)
        counts = {'preserved_binary': 0, 'derived_binary': 0, 'assumed_background_pixels': 0}
        for i, frame in enumerate(updated['frames']):
            original = safe_file(source, frame['reference']['path'])
            if sha256(original) != frame['reference']['sha256']:
                raise ValueError('Reference identity mismatch')
            with Image.open(original) as image:
                labels = np.array(image)
            if labels.shape != tuple(reversed(frame['size'])):
                raise ValueError('Reference dimensions differ')
            converted, unknown = derive(labels)
            is_derived = unknown > 0 or frame['supervision'] != 'binary-reference'
            destination = root/'comparison-references'/f'{i+1:03d}.png'
            if is_derived:
                Image.fromarray(converted).save(destination)
            else:
                shutil.copy2(original, destination)
            frame['comparison_reference'] = {
                **mask_record(destination, root, converted),
                'kind': 'derived-binary-reference' if is_derived else 'binary-reference',
                'source_reference_sha256': frame['reference']['sha256'],
                'assumed_background_pixels': unknown,
                'background_independently_reviewed': not is_derived,
                'policy_version': POLICY['version'],
            }
            counts['derived_binary' if is_derived else 'preserved_binary'] += 1
            counts['assumed_background_pixels'] += unknown
        updated['comparison_reference_policy'] = POLICY
        updated['comparison_reference_summary'] = counts
        updated['comparison_reference_id'] = digest_json({'policy': POLICY, 'references': [
            {'id': f['id'], **f['comparison_reference']} for f in updated['frames']]})
        updated['reference_update_utc'] = utc_now()
        updated['reference_updater_sha256'] = sha256(Path(__file__))
        # Review compatibility is allowed only because every source and prediction stays identical.
        updated['compatible_review_package_ids'] = [manifest['package_id']]
        updated['metric_policy'] = 'Per-image P/R/F1/sidewalk IoU/mIoU against comparison references. '
        updated['metric_policy'] += 'Scores using assumed background are provisional, not independently verified accuracy.'
        del updated['package_id']
        updated['package_id'] = digest_json(updated)
        write_json(root/'manifest.json', updated)
        (root/'data.js').write_text('window.BETA_COMPARISON_DATA = '+json.dumps(updated, separators=(',', ':'))+';\n')
        for name in ASSETS:
            shutil.copy2(HERE/'review'/name, root/('index.html' if name == 'beta.html' else name))
        readme = (root/'READ-ME.txt').read_text()
        readme = readme.replace('Positive-only references have no valid P or F1; their recall covers known sidewalk only.\n',
            'All comparison references contain sidewalk/background. For the formerly partial references,\n'
            'the accepted sidewalk outline is unchanged and all unknown pixels are assumed background.\n'
            'Those per-image P/R/F1/IoU/mIoU scores are PROVISIONAL, not independently verified accuracy.\n'
            'Original reference PNGs remain in references/; derived copies are in comparison-references/.\n'
            'mIoU is the mean of sidewalk/background IoU; zero-union classes are excluded.\n')
        (root/'READ-ME.txt').write_text(readme)
        for name, expected in checksums.items():
            if sha256(safe_file(source, name)) != expected:
                raise ValueError('Source package changed during derivation')
            if name.startswith(('images/', 'predictions/', 'references/')) and sha256(root/name) != expected:
                raise ValueError('Original image, reference, or prediction changed')
        write_json(root/'integrity-check.json', {'files_sha256': {
            str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p != root/'integrity-check.json'}})
        root.rename(output)
    return {'package_id': updated['package_id'], 'comparison_reference_id': updated['comparison_reference_id'], **counts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--viewer', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.viewer, args.output), indent=2))
