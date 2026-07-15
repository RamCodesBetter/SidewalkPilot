# Dmmdd Naming

The historical Series 1/2 labels carry a `source` tag that identifies their field-test batch. Their convention is `Dmmdd_description`: a capital `D`, the two-digit month and day, then a short description. This convention should not be generalized to every SidewalkPilot dataset row; the current Series 3/4 `labels.json` is image-keyed and does not store the same per-row `source` field.

## How it works

- The tag starts with `D` (for "date").
- `mmdd` is the capture month and day, zero-padded, e.g. `0425` for April 25.
- After an underscore comes a short description in lowercase words joined by underscores that says what the batch targeted.
- The same tag is reused for every Series 1/2 image in that batch.

These are the exact `source` values from the frozen Series 1/2 dataset (`code/ai_models_datasets/series_1_and_2/steering_corrections.json`):

| Source tag | Images | What the batch was for |
|---|---:|---|
| `D0328_first_dataset_relabel` | 315 | First dataset relabel |
| `D0329_first_dataset_relabel` | 413 | First dataset relabel (day 2) |
| `D0425_street_test` | 65 | Street test images |
| `D0426_curves_shadows` | 53 | Curves and shadow cases |
| `D0427_curved_curb` | 72 | Curved curb behavior |
| `D0429_driveway_shadow_fix` | 53 | Driveway and shadow cases |
| `D0502_shadow_fix` | 154 | Shadow robustness |
| `D0502_19_hard_turn_curb_smoothness_fix` | 156 | Hard turns, curb hugging, smoothness |
| `D0503_harsh_sidewalk` | 159 | Harsh sidewalk surface cases |
| `D0506_8pm_sidewalk` | 24 | Evening / low-light sidewalk |
| `D0510_v2_3_run_1` | 167 | v2.3 field-run capture, run 1 |
| `D0510_v2_3_run_2` | 8 | v2.3 field-run capture, run 2 |
| `D0510_v2_3_run_3` | 585 | v2.3 field-run capture, run 3 |

Note two real-world patterns in that list: multiple batches can share a date and are disambiguated by description (`D0510_v2_3_run_1/2/3`), and a description may include an hour or a model version when that context matters (`D0502_19_...`, `D0510_v2_3_...`).

## Why this choice

For Series 1/2, the tag supports provenance and per-source analysis. The Series 3/4 trainer derives a broad source category such as `real` or `carla` from each dataset root and can apply source weights, but that is different from a `Dmmdd_description` row tag. A specific historical run's source mix must be established from its root list or scan log.

## Good vs bad example

Good — dated, described, matches the image date:

```json
{ "image": "sidewalkpilot_dataset/photo_20260425_145756.jpg",
  "steering": 110.0, "repeat": 50, "source": "D0425_street_test" }
```

Bad — no date prefix, no batch meaning, cannot be grouped or excluded:

```json
{ "image": "sidewalkpilot_dataset/photo_20260425_145756.jpg",
  "steering": 110.0, "repeat": 50, "source": "test" }
```

Also note the underlying image filenames use the full timestamp form `photo_YYYYMMDD_HHMMSS.jpg`; the `Dmmdd` tag is the batch grouping laid on top of those per-frame filenames.

## Validation

List the sources actually present and confirm each begins with `D` + four digits:

```bash
grep -oE '"source": "[^"]*"' \
  code/ai_models_datasets/series_1_and_2/steering_corrections.json | sort -u
```

Within the Series 1/2 label list, a tag that does not start with `D` followed by `mmdd` is off-convention and should be reviewed before publishing.

## Recovery when the rule is broken

If a batch was tagged wrong, rename its `source` in place across every affected row (the tag is a plain string field, so a scripted find-and-replace on that one batch's value is safe) and re-run the source count. Do not merge two real batches under one tag just to "clean up" — that destroys the per-source subset metrics.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
