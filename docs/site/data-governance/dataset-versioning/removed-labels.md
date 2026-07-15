# Removed and Family-Specific Labels

The project has two active dataset schemas. A field absent from one family is not
automatically obsolete everywhere, so this page separates fields that are not
used by a model from fields that the current loaders still support.

## Current Contracts

| Family | Primary labels | Fields used for training |
|---|---|---|
| Series 1/2 | list entries in `series_1_and_2/steering_corrections.json` | `image`, `steering`, `repeat`, `source` |
| Series 3 | image-keyed `series_3_and_4/sidewalkpilot_dataset/labels.json` | `steering`, absolute physical `throttle` |
| Series 4 | the same Series 3/4 `labels.json` | steering plus derived temporal target order; throttle is present but not predicted |

The Series 3/4 base file stores throttle as a physical PWM fraction from `0.0`
to `1.0`. A value of `0.55` means 55% physical PWM. Reference throttle, center
trim, and other runtime mappings are not written back into labels.

## Not Used by a Given Family

- **Throttle is not a Series 1/2 target.** Those models predict steering only.
- **Throttle is not a Series 4 output.** The shared dataset keeps the field so
  Series 3 data remains intact, but Series 4 trains steering horizons only.
- **Reverse is not a learned target.** The stored throttle value is a forward
  physical command. Reverse and emergency stopping remain runtime controls.
- **`repeat` is not part of the Series 3/4 base `labels.json` schema.** It is
  still supported in an optional correction file and is the normal weighting
  field in the frozen Series 1/2 correction list.

These are architecture boundaries, not instructions to delete fields from a
published dataset.

## What the Loader Actually Rejects

For Series 3, the current loader drops a row when the image cannot be resolved or
when steering or throttle cannot be converted to a number. It reports missing,
bad, converted/clipped, and overridden counts during the scan. Series 4 uses the
same base records but constructs steering-only temporal examples in its common
trainer.

The code does not determine whether a command came from a human or a model. That
is a provenance decision that must be recorded at collection time; it must not be
invented later from a filename or from trainer defaults.

## Validation

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path("code/ai_models_datasets/series_3_and_4/sidewalkpilot_dataset/labels.json")
rows = json.loads(p.read_text())
bad = [name for name, value in rows.items()
       if not isinstance(value, dict)
       or not isinstance(value.get("steering"), (int, float))
       or not isinstance(value.get("throttle"), (int, float))]
print("entries", len(rows), "invalid", len(bad))
PY
```

Do not delete a row merely because a field is unused by one model family. Audit
the dataset contract, preserve the original capture, and make exclusions explicit.

## Related Pages

- [Active Label Set](active-label-set.md)
- [Dataset Overview](../../data/dataset-overview.md)
- [Input Labels](../../ai-and-models/training-pipeline/input-labels.md)
