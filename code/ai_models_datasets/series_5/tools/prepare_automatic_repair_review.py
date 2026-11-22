#!/usr/bin/env python3
"""Freeze 200 new, duplicate-reduced review frames using local history only."""
import argparse
from bisect import insort
from collections import Counter, defaultdict
import json
from pathlib import Path
import random

from PIL import Image

from automatic_repair import recipe
from label_grounded_sam2 import DEFAULT_SOURCE, digest_json, sha256, utc_now, write_json
from prepare_paired_review import (GUARD_SECONDS, HASH_DISTANCE, dhash, image_names,
                                  near_time, quotas, timestamp)

HERE = Path(__file__).resolve().parent


def collect_history(history, source_names):
    paths = set()
    for pattern in ('**/*manifest.json', '**/selection.json', '**/exclusions.json'):
        paths.update(history.glob(pattern))
    excluded, evidence = set(), {}
    for path in sorted(paths):
        data = json.loads(path.read_text())
        found = set(image_names(data)) & source_names
        if found:
            excluded.update(found)
            evidence[str(path)] = dict(sha256=sha256(path), source_images=len(found))
    return excluded, evidence


def choose_frames(source, names, excluded, count, seed):
    groups, old_times = defaultdict(list), defaultdict(list)
    for name in names:
        groups[name.split('__', 1)[0]].append(name)
    for name in excluded:
        insort(old_times[name.split('__', 1)[0]], timestamp(name))
    hashes = []
    for name in sorted(excluded):
        with Image.open(source / name) as image:
            hashes.append(dhash(image))
    limits = quotas(groups, count)
    rng = random.Random(seed)
    selected, chosen_names, chosen_times = [], set(), defaultdict(list)
    available, shortages, rejected = {}, {}, Counter()

    def attempt(name, run):
        value = timestamp(name)
        if name in chosen_names or near_time(value, chosen_times[run]):
            rejected['new_sample_time_guard'] += 1
            return False
        with Image.open(source / name) as image:
            descriptor, size = dhash(image), list(image.size)
        if any((descriptor ^ previous).bit_count() <= HASH_DISTANCE for previous in hashes):
            rejected['perceptual_near_duplicate'] += 1
            return False
        selected.append(dict(image=name, size=size, source_sha256=sha256(source / name), dhash64=f'{descriptor:016x}'))
        hashes.append(descriptor)
        chosen_names.add(name)
        insort(chosen_times[run], value)
        return True

    for run, group in sorted(groups.items()):
        candidates = [n for n in group if n not in excluded and not near_time(timestamp(n), old_times[run])]
        rng.shuffle(candidates)
        available[run] = candidates
        before = len(selected)
        for name in candidates:
            if len(selected) - before == limits[run]:
                break
            attempt(name, run)
        if len(selected) - before < limits[run]:
            shortages[run] = limits[run] - (len(selected) - before)
        print(json.dumps(dict(run=run, eligible=len(candidates), quota=limits[run], selected=len(selected) - before)), flush=True)
    for run in sorted(groups, key=lambda r: (-len(groups[r]), r)):
        for name in available[run]:
            if len(selected) == count:
                break
            attempt(name, run)
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError('Cannot fill sample without relaxing duplicate guards')
    rng.shuffle(selected)
    return selected, limits, shortages, dict(rejected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--history', type=Path, default=Path.home() / 'sidewalkpilot-labels')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261109)
    parser.add_argument('--config', type=Path, default=HERE / 'automatic_repair_config.json')
    parser.add_argument('--grounding-config', type=Path, default=HERE / 'label_config_sidewalk_first.json')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    source = args.source.resolve()
    names = sorted(p.name for p in source.glob('*.jpg'))
    if set(names) != set(json.loads((source / 'labels.json').read_text())):
        raise ValueError('Source pool and steering labels differ')
    frozen = recipe(args.config, args.grounding_config)
    excluded, provenance = collect_history(args.history, set(names))
    if len(excluded) < 200:
        raise ValueError('Historical exclusion inventory unexpectedly small')
    print(f'Excluding {len(excluded)} previously selected or inspected images before temporal/perceptual guards.', flush=True)
    chosen, limits, shortages, rejected = choose_frames(source, names, excluded, 200, args.seed)
    args.output.mkdir(parents=True)
    write_json(args.output / 'exclusions.json', dict(images=sorted(excluded), prior_records=provenance,
               method='Local metadata snapshots, including prior Mac test inventory and context manifests. No laptop access.'))
    write_json(args.output / 'recipe.json', frozen)
    selection = dict(kind='automatic-repair-fresh-selection-v1', created_utc=utc_now(),
        source=str(source), source_count=len(names), source_names_sha256=digest_json(names),
        steering_labels_sha256=sha256(source / 'labels.json'), seed=args.seed,
        recipe_sha256=digest_json(frozen), images=[f['image'] for f in chosen], frames=chosen,
        original_quotas=limits, exhausted_run_shortages=shortages, rejections=rejected,
        excluded_count=len(excluded), exclusions_sha256=sha256(args.output / 'exclusions.json'),
        guard_seconds=GUARD_SECONDS, dhash64_max_excluded_distance=HASH_DISTANCE,
        sample_runs=dict(Counter(f['image'].split('__', 1)[0] for f in chosen)),
        runner_sha256=sha256(Path(__file__)),
        purpose='Fresh duplicate-reduced class-1 labeling workflow review. Not the eventual held-out model test, an IID accuracy estimate, or a twelve-class evaluation.',
        sampling='Proportional source-run quotas, seeded permutation, 5-second and dHash<=4 exclusions against historical frames and the new sample. Exhausted run quotas redistributed without weakening guards.',
        limits='Temporal and perceptual guards reduce near duplication; they cannot prove all semantically similar scenes are excluded. No fresh-reference masks or image-specific edits enter inference.')
    write_json(args.output / 'selection.json', selection)
    print(json.dumps(dict(output=str(args.output), count=200, excluded=len(excluded), sample_runs=selection['sample_runs']), indent=2))


if __name__ == '__main__':
    main()
