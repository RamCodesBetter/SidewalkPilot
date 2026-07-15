# Active Label Set

The active label set is the exact list of label fields that a SidewalkPilot dataset entry is allowed to carry for the current model series. It is the schema contract every label file has to satisfy before an image can be counted, trained on, or published. Because the project spans two frozen series and one open series, "active" always means the schema of the series you are currently collecting for.

## Series 1/2 label set (frozen)

Series 1 and 2 are the camera-to-steering series. Every label entry in `code/ai_models_datasets/series_1_and_2/steering_corrections.json` is a JSON object with four fields:

| Field | Type | Meaning |
|---|---|---|
| `image` | string | Relative image path, e.g. `sidewalkpilot_dataset/photo_20260425_145756.jpg` |
| `steering` | number | Servo angle in degrees, `0`=hard left, `90`=straight, `180`=hard right |
| `repeat` | integer | Training repeat/weight for that sample |
| `source` | string | Field-test group tag in `Dmmdd_description` form (see `dmmdd-naming.md`) |

There is no throttle field in Series 1/2. This set is closed: the finalized dataset holds 2,224 images and 2,224 labels across 13 sources, and new data does not go here.

## Series 3/4 label set (active)

The shared Series 3/4 dataset carries:

| Field | Type | Meaning |
|---|---|---|
| image filename key | string | Captured frame filename |
| `steering` | number | Final steering servo angle in degrees (`0`/`90`/`180`) |
| `throttle` | number | Final forward motor command, `0.00`=stop, `1.00`=full forward |

Throttle is **required** by the Series 3 loader. It is an absolute physical PWM fraction, not reference throttle. Series 4 keeps the source record intact but trains steering horizons only. Reverse is not a model output; braking, stopping, and reverse stay runtime responsibilities.

The nine steering classes used by the v3.1+ hybrid head and common evaluator are HL, L, L+, SL, ST, SR, R, R+, and HR. The trainer also retains a coarser seven-bucket summary for sampler diagnostics. Neither scheme changes the stored degree label.

## Good vs bad example

Good (Series 3, complete):

```json
{ "photo_20260520_123456.jpg": { "steering": 92, "throttle": 0.37 } }
```

Bad (Series 3, no throttle — skipped as a bad label):

```json
{ "photo_20260520_123456.jpg": { "steering": 92 } }
```

## Validation

Before training or publishing, confirm the label set matches the series. A Series 1/2 check counts entries and confirms every row has `image`/`steering`/`repeat`/`source`:

```bash
python3 - <<'PY'
import json
rows = json.load(open("code/ai_models_datasets/series_1_and_2/steering_corrections.json"))
need = {"image","steering","repeat","source"}
bad = [r for r in rows if not need.issubset(r)]
print("entries", len(rows), "missing-field rows", len(bad))
PY
```

The Series 3 trainer prints `skipped bad labels` and source counts on load. A nonzero bad count means steering or throttle could not be parsed; inspect the reported root rather than assuming one cause.

## Recovery when the set is wrong

If a Series 3/4 base row is missing throttle, recover it only from the matching capture record. Do not invent a constant or delete the image to make a count pass.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
