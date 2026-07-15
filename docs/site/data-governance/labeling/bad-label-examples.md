# Bad Label Examples

This page is the concrete catalogue of what the SidewalkPilot pipeline treats as a bad label, so a labeler can recognize and fix them before training instead of shipping poisoned data into a model. Every case here maps to a specific reason the trainer will skip or misread a row.

## What counts as a bad label

The Series 3 dataset loader in `series_3_sidewalkpilot_trainer.py` classifies each row as `used`, `missing`, or `bad` while reading. A row is bad when it cannot be turned into a valid `(image, steering, throttle)` sample. The Series 4 temporal loader consumes image and steering from the same base records but does not train a throttle output.

| Case | Why it is bad | What the trainer does |
|---|---|---|
| No image key | `resolve_image_path` returns `None` | counted `missing` |
| Image path not found | Not in `images/`, root, `rgb/`, `camera/`, or script dir | counted `missing` |
| Non-numeric `steering` | `float()` raises `TypeError`/`ValueError` | counted `bad`, skipped |
| Series 3 row with no `throttle` | joint steer+throttle target incomplete | counted `bad`, skipped |
| Steering stored in `[-1, 1]` when degrees were meant | loader infers "normalized" mode and rescales it | wrong label, trains silently |
| Non-object entry in a correction file | `load_correction_items` raises | whole file rejected |
| Same image, two conflicting labels in one root file | no in-file dedup | both train, model gets pulled apart |
| Unknown capture provenance | inclusion cannot be defended | parser accepts it, but release audit must flag it |

The last row is a governance check, not a parser rule. The loader cannot infer who or what produced a command.

## Why this matters

Bad labels are worse than missing data because they train the model toward the wrong behavior while looking like progress. Some semantic errors pass syntax checks, so numeric validation must be paired with provenance and spot review.

## Good vs bad

Good (Series 3, complete, degrees + throttle):

```json
{ "image": "photo_20260520_123456.jpg", "steering": 92, "throttle": 0.37 }
```

Bad (Series 3, throttle missing — skipped):

```json
{ "image": "photo_20260520_123456.jpg", "steering": 92 }
```

Bad (steering as a normalized value instead of degrees — misread, not skipped):

```json
{ "image": "photo_20260520_123456.jpg", "steering": 0.02, "throttle": 0.37 }
```

## Validation

The load logs already surface bad-label totals: `root done=<name> labels=<n> used=<n> missing=<n> bad=<n>` per root, and `corrections used/missing/bad`. A fast pre-flight audit:

```bash
python3 -c "import json; d=json.load(open('steering_corrections.json')); bad=[r for r in d if 'image' not in r or not isinstance(r.get('steering',None),(int,float))]; print('rows',len(d),'suspect',len(bad)); print(bad[:3])"
```

## Recovery

Fix the row, not the loader: add the missing `throttle`, convert a normalized value back to degrees, or correct the image path. If a batch is systematically bad (for example a known drift-biased run), count and report it first, then exclude it from the training goal — do not delete captures without explicit sign-off.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
