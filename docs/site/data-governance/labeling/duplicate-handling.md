# Duplicate Handling

Duplicate handling defines what happens when the same image appears in more than one label source, and the difference between an accidental duplicate (a data bug) and an intentional repeat (a training weight). Getting this right keeps the effective sample count honest and stops one frame from silently dominating training.

## The Two Kinds of Duplication

There are two very different things that look like "the same image twice":

- **Intentional repeat.** A label carries `repeat` (default 6, minimum 1). The dataset loader appends the sample `repeat` times on purpose, so one hard/rare frame gets extra gradient weight. This is a feature, not a duplicate.
- **Cross-source collision.** The same image is labeled in both a dataset root and a correction file. This is resolved by override, not by counting both.

## How collisions are resolved

Before any root is read, the trainer builds a set of every correction image's resolved absolute path. While reading each root, any image already in that set is skipped and tallied as `skipped_overridden` — its root label is dropped, and only the correction label survives. This is a hard, path-based dedup: the correction always wins, and the raw label never enters training for that frame.

Image paths are resolved through `resolve_image_path`, which searches `images/`, the root itself, `rgb/`, `camera/`, and the script directory, then compared via `str(path.resolve())`. Because comparison is on the resolved absolute path, the same file referenced by different relative spellings still collides correctly.

## Why this choice

Counting a frame from both the root and a correction would double-label it and let a stale raw label leak back in even after it was fixed. Path-based override keeps exactly one authoritative label per physical image while still allowing deliberate up-weighting through `repeat`. It also means the fix for a bad frame is additive (write a correction) rather than destructive (delete the capture).

## Good example

One image, corrected once, up-weighted intentionally:

```json
{ "image": "sidewalkpilot_dataset/photo_20260425_145826.jpg", "steering": 140.0, "repeat": 50 }
```

The root copy of `photo_20260425_145826.jpg` is skipped as overridden; the corrected label appears 50 times. That is intended, not a duplicate bug.

## Bad example

The same image listed twice inside one root's `labels.json` with two different steering values, and no correction to arbitrate. Nothing dedups within a single root file, so both rows train and pull the model in opposite directions on identical pixels. Fix the label file so each image key appears once.

## Validation

The per-root log line reports `used`, `missing`, `bad`, and the run reports `skipped_overridden`; a rising `skipped_overridden` count with no matching corrections would signal an unexpected collision. A standalone duplicate check within one label file:

```bash
python3 -c "import json,collections; d=json.load(open('steering_corrections.json')); c=collections.Counter(r.get('image') for r in d); dupes={k:n for k,n in c.items() if n>1}; print('duplicate_images',len(dupes)); print(dict(list(dupes.items())[:5]))"
```

## Recovery

- If a single label file lists the same image twice, keep one row and delete the other; do not leave conflicting labels.
- If a frame is duplicated because a photo run was ingested twice, remove the duplicate ingest, not the original run's images.
- Never inflate `repeat` to paper over a distribution gap that real data should fill — repeats up-weight, they do not add new views.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
