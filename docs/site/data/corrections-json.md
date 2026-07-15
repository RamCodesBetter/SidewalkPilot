# Corrections JSON

`steering_corrections.json` is the frozen primary label list for Series 1/2. The
Series 3/4 dataset instead uses `sidewalkpilot_dataset/labels.json`; the Series 3
trainer can also accept optional correction files through `--corrections`. The
current Series 4 temporal engine does not. This page keeps those roles separate.

## Schema (Series 1/2)

The file is a flat JSON **list**. Each entry is one labeled image:

| Field | Type | Meaning |
|---|---|---|
| `image` | string | Relative image path used by the trainer, e.g. `sidewalkpilot_dataset/photo_20260425_145756.jpg` |
| `steering` | number | Servo angle label in degrees, 0 = hard left, 90 = center, 180 = hard right |
| `repeat` | integer | How many times this sample is duplicated during training (its weight) |
| `source` | string | The `Dmmdd`-tagged field-capture group the image came from |

Example entry:

```json
{
  "image": "sidewalkpilot_dataset/photo_20260425_145756.jpg",
  "steering": 110.0,
  "repeat": 50,
  "source": "D0425_street_test"
}
```

## How the trainer uses it

The trainer (`sidewalkpilot_trainer.py`) treats corrections as authoritative:

- **Override.** When a correction's image also appears in a dataset root's base
  `labels.json`, the base label is dropped and the correction is used instead. The
  trainer prints this as `skipped base labels overridden by corrections`. This is
  what lets a single wrong label be fixed without touching the raw capture.
- **Repeat weighting.** Each correction is added to the training set `repeat`
  times (`repeat = max(1, int(item.get("repeat", 6)))`, default 6). A high
  `repeat` — the Series 1/2 corrections use 50 — pushes the model harder toward
  that exact frame's label, which is how a hand-fixed hard case is made to "stick".
- **Source tagging.** Internally every correction sample is tagged with the source
  `"correction"` for the trainer's weighted sampler, while the human-readable
  `source` field preserves the `Dmmdd` field group for provenance.

## Series 1/2 sources

The finalized Series 1/2 file holds 2,224 entries across 13 `Dmmdd` sources.
Two of them are the original relabel of the very first dataset:

| Source | Count |
|---|---:|
| `D0328_first_dataset_relabel` | 315 |
| `D0329_first_dataset_relabel` | 413 |
| `D0425_street_test` | 65 |
| `D0426_curves_shadows` | 53 |
| `D0427_curved_curb` | 72 |
| `D0429_driveway_shadow_fix` | 53 |
| `D0502_shadow_fix` | 154 |
| `D0502_19_hard_turn_curb_smoothness_fix` | 156 |
| `D0503_harsh_sidewalk` | 159 |
| `D0506_8pm_sidewalk` | 24 |
| `D0510_v2_3_run_1` | 167 |
| `D0510_v2_3_run_2` | 8 |
| `D0510_v2_3_run_3` | 585 |

Source names were normalized once (git commit "Normalize Series 1 and 2 dataset
source names") so the `Dmmdd` history stays consistent and chronological.

## Series 3/4 base labels

The current shared dataset uses an image-keyed `labels.json`:

```json
{
  "photo_20260520_123456.jpg": {
    "steering": 92,
    "throttle": 0.37
  }
}
```

Throttle is an absolute physical `0.0..1.0` PWM fraction and is required by the
Series 3 loader. Series 4 derives steering-only temporal examples from the same
records. The repository does not currently contain a Series 3/4
`steering_corrections.json`; a correction file is optional and must be passed
explicitly when used.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/dmmdd-naming.md`
- `ai-and-models/training-pipeline/input-labels.md`
