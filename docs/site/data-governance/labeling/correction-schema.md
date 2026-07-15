# Correction Schema

The correction schema defines how a hand-fixed steering (and, for Series 3, throttle) label overrides the raw captured label for an image. Corrections are the mechanism by which a human relabels a frame the car got wrong, and they are treated as the highest-authority label in training.

## What a correction is

A correction lives in a `steering_corrections.json` file and follows the same field layout as a normal label, plus an optional `repeat`:

| Field | Type | Meaning |
|---|---|---|
| `image` | string | Image path/filename the correction applies to |
| `steering` | number | Corrected servo angle in degrees (`0`=left, `90`=straight, `180`=right) |
| `throttle` | number | Absolute forward command (`0.00`..`1.00`); required by the Series 3 correction path |
| `repeat` | integer | How many times to duplicate this sample into training (default 6, min 1) |
| `source` | string | Field-test group tag (Series 1/2 rows carry one) |

The correction loader (`load_correction_items` in `series_3_sidewalkpilot_trainer.py`) accepts three physical layouts and normalizes them all to a list of objects: a plain JSON list, a `{"samples": [...]}` wrapper, and an image-to-label dict (`{"photo_x.jpg": {...}}` or `{"photo_x.jpg": 90}`). Each loaded item is tagged with its `_correction_file` so images can be resolved relative to that file.

## How it works

1. Before any root labels are read, the trainer resolves every correction image to an absolute path and builds a `correction_image_paths` set.
2. While reading each dataset root, any image whose resolved path is in that set is **skipped and counted as overridden** — the root's original label never enters training.
3. Corrections are then loaded separately with `source="correction"`, duplicated `repeat` times, and (in the weighted sampler) given the highest source weight (`correction_weight=3.0`, versus `2.0` real and `0.6` CARLA).

This makes a correction win over the raw label deterministically and lets a single fixed frame carry extra training influence via `repeat`.

This describes the Series 3 correction path. The current Series 4 temporal engine does
not expose `--corrections`; its PC, CF, and PCF runs used the shared base `labels.json`
records unchanged. Adding temporal correction support would require defining how a
corrected anchor affects neighboring history and future targets.

## Why this choice

Corrections can fix a reviewed label without editing or deleting the original capture: the raw photo run stays auditable while the correction file holds the override. The default sampler gives corrections more influence than ordinary real or CARLA-tagged roots. That is an implemented capability, not evidence that a particular checkpoint used corrections; verify the launched command and scan log.

## Good example

```json
{
  "image": "sidewalkpilot_dataset/photo_20260425_145826.jpg",
  "steering": 140.0,
  "repeat": 50,
  "source": "D0425_street_test"
}
```

## Bad example

```json
{ "steering": 140.0, "repeat": 50 }
```

No image key means `resolve_image_path` returns `None`, the correction cannot be matched to any frame, and it is counted as `missing`. A Series 3 correction with no `throttle` is counted as `bad`.

## Validation

The trainer prints correction health on load: `corrections used=<n> missing=<n> bad=<n>`, and the per-root logs show `skipped_overridden` counts so you can confirm the intended raw labels were actually replaced. A pre-flight check:

```bash
cd code/ai_models_datasets/series_1_and_2
python3 -c "import json; d=json.load(open('steering_corrections.json')); print('corrections',len(d)); print('no_image',sum('image' not in r for r in d))"
```

## Recovery

If `missing` is nonzero, the correction points at an image that is not present in any root under `images/`, the root itself, `rgb/`, `camera/`, or next to the trainer — fix the path or move the image, do not silently drop the correction. If a correction produced a wrong override, edit the correction row; never hand-edit the raw capture to match.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
