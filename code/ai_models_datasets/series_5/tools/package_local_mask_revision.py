#!/usr/bin/env python3
"""Apply traceable local edits only to flagged masks and package their re-review."""
import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from evaluate_class1_corrections import safe_file
from hybrid_repair_pilot import rectangle, render
from label_grounded_sam2 import digest_json, save_mask, sha256, utc_now, write_json
from package_hybrid_review import polygon_region
from package_visual_comparison import encode_labels

HERE = Path(__file__).resolve().parent
VALUES = (0, 1, 255)


def apply_edits(baseline, edits):
    if baseline.ndim != 2 or not np.isin(baseline, VALUES).all():
        raise ValueError('Invalid baseline mask')
    output = baseline.copy()
    allowed = np.zeros(baseline.shape, dtype=bool)
    steps = []
    size = [baseline.shape[1], baseline.shape[0]]
    for edit in edits:
        if not isinstance(edit.get('reason'), str) or not edit['reason'].strip():
            raise ValueError('Every edit needs a reason')
        if type(edit.get('value')) is not int or edit['value'] not in VALUES:
            raise ValueError('Invalid label value')
        if ('rectangle' in edit) == ('polygon' in edit):
            raise ValueError('Choose exactly one region shape')
        region = (rectangle(edit['rectangle'], size) if 'rectangle' in edit
                  else polygon_region(edit['polygon'], size))
        selected = edit.get('only_values', list(VALUES))
        if not isinstance(selected, list) or not selected or any(type(v) is not int or v not in VALUES for v in selected):
            raise ValueError('Invalid conditional labels')
        effective = region & np.isin(output, selected)
        steps.append({'reason': edit['reason'], 'changed_pixels': int((effective & (output != edit['value'])).sum())})
        output[effective] = edit['value']
        allowed |= effective
    if not np.array_equal(output[~allowed], baseline[~allowed]):
        raise ValueError('Edit escaped its effective region')
    return output, {'changed_pixels': int((output != baseline).sum()),
                    'outside_effective_regions': 0, 'steps': steps}


def flagged_ids(parent, review):
    if (review.get('schema') != 'sidewalkpilot-three-method-review-v1'
            or review.get('package_id') != parent['package_id']
            or review.get('review_methods') != ['codex']):
        raise ValueError('Review does not match the parent package')
    if set(review['reviews']) != {f['id'] for f in parent['frames']}:
        raise ValueError('Expected a completed review of the parent sample')
    flagged = []
    for frame in parent['frames']:
        row = review['reviews'][frame['id']]
        rating = row.get('methods', {}).get('codex', {})
        if (row.get('source_sha256') != frame['source_sha256']
                or rating.get('sha256') != frame['methods']['codex']['sha256']
                or rating.get('decision') not in ('correct', 'needs_correction', 'uncertain')):
            raise ValueError('Incomplete or mismatched review identity')
        if rating['decision'] != 'correct':
            flagged.append(frame['id'])
    return flagged


def revision_inventory(parent, review, review_sha256, inventory=None, inherited=None):
    """Resolve a subset review without dropping prior, unchanged acceptances."""
    flagged_ids(parent, review)
    frames = parent['frames'] if inventory is None else inventory['frames']
    current = {f['id']: f for f in parent['frames']}
    all_ids = [f['id'] for f in frames]
    if len(all_ids) != len(set(all_ids)) or not set(current).issubset(all_ids) or len(all_ids) > 30:
        raise ValueError('Invalid retained inventory')
    if inventory is not None and (inventory.get('revision_package_id') != parent['package_id']
                                  or inventory.get('count') != len(frames)):
        raise ValueError('Retained inventory belongs to another revision')
    inherited = inherited or {}
    if set(inherited) - set(all_ids):
        raise ValueError('Unknown inherited image')
    ratings, origins = {}, {}
    for frame in frames:
        key = frame['id']
        if key in current:
            if frame != current[key]:
                raise ValueError('Retained and visible frame records differ')
            row = review['reviews'][key]
            origin = {'review_package_id': parent['package_id'], 'review_sha256': review_sha256}
        else:
            evidence = inherited.get(key, {})
            row = evidence.get('rating', {})
            rating = row.get('methods', {}).get('codex', {})
            if (row.get('source_sha256') != frame['source_sha256']
                    or not isinstance(row.get('notes'), str)
                    or set(row.get('methods', {})) != {'codex'}
                    or rating.get('decision') != 'correct'
                    or rating.get('sha256') != frame['methods']['codex']['sha256']
                    or not evidence.get('review_package_id') or not evidence.get('review_sha256')):
                raise ValueError('Cannot carry forward an unaccepted or changed mask: ' + key)
            origin = {k: evidence[k] for k in ('review_package_id', 'review_sha256')}
        ratings[key], origins[key] = copy.deepcopy(row), origin
    return frames, ratings, origins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('package', 'review', 'edits', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    args = parser.parse_args()
    parent_file = args.package/'manifest.json'
    parent = json.loads(parent_file.read_text())
    review = json.loads(args.review.read_text())
    plan = json.loads(args.edits.read_text())
    ids = flagged_ids(parent, review)
    if (plan.get('schema') != 'sidewalkpilot-local-mask-edits-v1'
            or plan.get('parent_package_id') != parent['package_id']
            or plan.get('parent_manifest_sha256') != sha256(parent_file)
            or plan.get('review_sha256') != sha256(args.review)
            or [f['id'] for f in plan['frames']] != ids):
        raise ValueError('Edits must match exactly the flagged images and frozen inputs')
    if not ids or len(parent['frames']) > 30:
        raise ValueError('This tool is limited to a reviewed development pilot of at most 30 images')
    if args.output.exists():
        raise ValueError('Use a new output directory; never overwrite a review package')
    choices = {f['id']: f for f in plan['frames']}
    inputs = {}

    def track(path, expected=None):
        actual = sha256(path)
        if expected is not None and expected != actual:
            raise ValueError('Frozen input changed: ' + str(path))
        inputs[str(path.resolve())] = actual

    for p in (parent_file, args.review, args.edits, Path(__file__)):
        track(p)
    inventory_file = args.package/'all-frames.json'
    inventory, inherited = None, None
    carry_sources = []
    if inventory_file.exists():
        integrity = json.loads((args.package/'integrity-check.json').read_text())
        track(inventory_file, integrity['files_sha256']['all-frames.json'])
        inventory = json.loads(inventory_file.read_text())
        inherited = inventory.get('inherited_acceptances')
        carry_sources.append((inventory_file, 'parent-all-frames.json'))
        if inherited is None:
            # The first subset package predates explicit inherited-rating records.
            old_path = args.package/'provenance/prior-review.json'
            track(old_path, integrity['files_sha256']['provenance/prior-review.json'])
            old = json.loads(old_path.read_text())
            if old['package_id'] != parent['parent_package_id'] or old.get('review_methods') != ['codex']:
                raise ValueError('Wrong carry-forward review')
            visible = {f['id'] for f in parent['frames']}
            inherited = {key: {'rating': row, 'review_package_id': old['package_id'],
                              'review_sha256': sha256(old_path)}
                         for key, row in old['reviews'].items() if key not in visible}
            carry_sources.append((old_path, 'carry-forward-review.json'))
    frames, ratings, origins = revision_inventory(parent, review, sha256(args.review), inventory, inherited)
    prepared = []
    # Validate all inputs and compute the edits before creating output files.
    for frame in frames:
        source = safe_file(args.package, frame['image'])
        track(source, frame['source_sha256'])
        for method in ('gsam2', 'sam3', 'codex'):
            track(safe_file(args.package, frame['methods'][method]['mask']), frame['methods'][method]['sha256'])
        baseline = np.array(Image.open(args.package/frame['methods']['codex']['mask']))
        if baseline.shape != tuple(reversed(frame['size'])):
            raise ValueError('Mask dimensions do not match the source')
        if frame['id'] in choices:
            choice = choices[frame['id']]
            if not choice.get('notes') or not choice['edits']:
                raise ValueError('Flagged images need explicit edits and review notes')
            output, report = apply_edits(baseline, choice['edits'])
            if not report['changed_pixels']:
                raise ValueError('Flagged revision has no changes: ' + frame['id'])
        else:
            output, report = baseline, {'changed_pixels': 0, 'outside_effective_regions': 0, 'steps': []}
        prepared.append((frame, output, report))

    for directory in ('images', 'masks', 'preview', 'provenance'):
        (args.output/directory).mkdir(parents=True, exist_ok=True)
    all_frames, reports = [], []
    for frame, output, report in prepared:
        result = copy.deepcopy(frame)
        result['source_sample_id'] = frame['id']
        shutil.copy2(args.package/frame['image'], args.output/frame['image'])
        for method in ('gsam2', 'sam3', 'codex'):
            source = args.package/frame['methods'][method]['mask']
            destination = args.output/frame['methods'][method]['mask']
            if method == 'codex' and frame['id'] in choices:
                save_mask(destination, output)
                result['methods'][method].update(
                    sha256=sha256(destination), positive_pixels=int((output == 1).sum()),
                    uncertain_pixels=int((output == 255).sum()), rle=encode_labels(output))
            else:
                shutil.copy2(source, destination)
                if sha256(destination) != frame['methods'][method]['sha256']:
                    raise ValueError('Unedited mask changed')
        prior = ratings[frame['id']]['methods']['codex']
        report.update(id=frame['id'], previous_rating=prior['decision'],
                      previous_correction_level=prior.get('correction_level'),
                      rating_origin=origins[frame['id']],
                      previous_mask_sha256=frame['methods']['codex']['sha256'],
                      mask_sha256=result['methods']['codex']['sha256'],
                      uncertainty_pixels=int((output == 255).sum()))
        reports.append(report)
        if frame['id'] in choices:
            result['annotation_notes'] = frame['id'] + ': ' + choices[frame['id']]['notes']
            with Image.open(args.package/frame['image']) as im:
                render(im, output, args.output/'preview'/(frame['id'] + '.jpg'))
        all_frames.append(result)

    manifest = {k: copy.deepcopy(parent[k]) for k in ('schema', 'source_count', 'methods', 'annotation_policy')}
    manifest.update(count=len(ids), seed=parent['seed'], created_utc=utc_now(),
        parent_package_id=parent['package_id'], selection_sha256=digest_json(ids),
        parent_selection_sha256=parent['selection_sha256'], review_methods=['codex'],
        annotation_revision=parent['annotation_revision'] + 1,
        sample_description=f'{len(ids)} flagged images / original sample IDs retained',
        sampling='Targeted subset of the previously reviewed random 30-image development sample. Not a new random draw.',
        annotation_heading='Local revision notes', uncertain_label='Uncertain boundary',
        annotation_sha256=sha256(args.edits),
        annotation_method='Prior GSAM 2 + point-guided SAM 2 hybrid masks with explicit, AI-authored local label patches. No new model inference in this revision.',
        review_status='unreviewed',
        scope='Re-review only the flagged masks. Accepted masks are preserved byte-for-byte in all-frames.json. Repeated development sample, not held-out accuracy or independent ground truth. No training or full-dataset run.',
        frames=[f for f in all_frames if f['id'] in choices])
    manifest['package_id'] = digest_json(manifest)
    write_json(args.output/'manifest.json', manifest)
    write_json(args.output/'all-frames.json', {'parent_package_id': parent['package_id'],
        'revision_package_id': manifest['package_id'], 'count': len(all_frames), 'frames': all_frames,
        'inherited_acceptances': {f['id']: dict(origins[f['id']], rating=ratings[f['id']])
                                 for f in frames if f['id'] not in choices}})
    summary = {'parent_package_id': parent['package_id'], 'package_id': manifest['package_id'],
        'review_sha256': sha256(args.review), 'edited': len(ids), 'accepted_preserved': len(all_frames)-len(ids),
        'outside_effective_regions': sum(r['outside_effective_regions'] for r in reports), 'reports': reports}
    write_json(args.output/'revision-report.json', summary)
    (args.output/'data.js').write_text('window.COMPARISON_DATA = ' + json.dumps(manifest, separators=(',', ':')) + ';\n')
    for name in ('comparison.html', 'comparison.js', 'comparison.css', 'lucide.min.js', 'LUCIDE-LICENSE.txt'):
        track(HERE/'review'/name)
        shutil.copy2(HERE/'review'/name, args.output/('index.html' if name == 'comparison.html' else name))
    for source, name in ((parent_file, 'parent-manifest.json'), (args.review, 'prior-review.json'),
                         (args.edits, 'local-edits.json')):
        shutil.copy2(source, args.output/'provenance'/name)
    for source, name in carry_sources:
        shutil.copy2(source, args.output/'provenance'/name)
    for name in ('package_local_mask_revision.py', 'package_hybrid_review.py', 'package_visual_comparison.py',
                 'hybrid_repair_pilot.py', 'label_grounded_sam2.py', 'evaluate_class1_corrections.py',
                 'sam_point_diagnostic.py', 'label_assisted_pilot.py'):
        track(HERE/name)
        shutil.copy2(HERE/name, args.output/'provenance'/name)
    (args.output/'READ-ME.txt').write_text(f'''SidewalkPilot: targeted hybrid-mask revision

Open index.html. Review only the hybrid panel for the {len(ids)} flagged images.
Original sample IDs are retained; viewer positions run from 1 to {len(ids)}.
1 = correct; 2 = needs correction, then 1/2/3 = minor/moderate/major;
3 = uncertain; Enter = next. Export the review JSON after finishing.
New masks start unrated. Previous-package ratings cannot be imported here.

The other {len(all_frames)-len(ids)} accepted masks are unchanged, with hashes in revision-report.json
and their records in all-frames.json. Their past acceptance is not a new rating.
The original source images and GSAM 2 / SAM 3 references are unchanged.
This revision uses explicit local AI-authored edits on the prior hybrid masks,
not new inference. It is not independent ground truth or automatic full-dataset
labeling. No fresh-image test, training, or 81k-image run was performed.

Green is proposed sidewalk; amber is unresolved uncertainty (255), excluded
from confident labels. Raw GSAM/SAM 255 means unassigned, not human uncertainty.
Ordinary cracks, joints, stains and shadows remain sidewalk. Visible occluding
objects do not. Include the pedestrian corridor through a driveway, but not
adjoining driveway pavement. Blurred boundaries remain approximate.

The archived review contains the student's original ratings and notes. Local
edit shapes are the assistant's interpretations, not student-drawn pixel masks.
Blurred edges remain approximate; no revised mask is automatically accepted.
''')
    for filename, expected in inputs.items():
        if sha256(Path(filename)) != expected:
            raise ValueError('Input changed during packaging')
    write_json(args.output/'integrity-check.json', {'input_sha256': inputs,
        'files_sha256': {str(p.relative_to(args.output)): sha256(p) for p in sorted(args.output.rglob('*')) if p.is_file()}})
    print(json.dumps({k: v for k, v in summary.items() if k != 'reports'}, indent=2))


if __name__ == '__main__':
    main()
