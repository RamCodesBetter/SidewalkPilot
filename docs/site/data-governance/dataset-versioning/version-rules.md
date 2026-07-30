# Version Rules

Version rules keep model, preprocessing, labels, and dataset identity together. A model name alone is not enough to reproduce a run.

## The Series and Their Contracts

| Series | Model | Input | Target | Label fields | Status |
|---|---|---|---|---|---|
| 1 / 2 | `SteeringAutonomyV2`, ~0.67M params | 200x66 | steering only (single tanh regression) | `image`, `steering`, `repeat`, `source` | Frozen (2,224 images) |
| 3 | `SidewalkPilotV3`, 5.53M params | 320x180 | v3.1+ hybrid steering + optional throttle loss | image key, `steering`, `throttle` | shared 81,237-frame training snapshot |
| 4.0 | PC / CF / PCF, 5.54-5.57M params | 320x180 plus optional previous targets | steering horizons only | same Series 3/4 base records | all six models field-tested; CF model v4.0f remained viable |
| 4.1 | PC / CF / PCF, 5.54-5.55M params | 320x180 plus optional previous targets | steering horizons only | same Series 3/4 base records | trained and evaluated offline; not integrated into the live selector or field-tested |

Series 1/2 use the earlier direct-regression architecture. Series 3/4 use Jetson Orin Nano and the larger 320x180 visual backbone. Existing Series 4 checkpoints share the 81,237-frame training snapshot but remove throttle prediction and add temporal-target experiments.

## The Rules

1. **Labels must match the image and loader.** Steering is stored as logical degrees (`0`=left, `90`=straight, `180`=right). Series 3/4 base rows also retain absolute physical throttle as `0.0..1.0`.
2. **Series 3 must include throttle on every entry.** The trainer skips any sample it cannot read a throttle for (`skipped_bad`). Throttle range is `0.00`-`1.00`; reverse is not a model output.
3. **Preserve capture provenance.** The parser cannot tell whether a command came from a human, autonomy, or simulation. Training inclusion must be based on recorded source/run evidence, not a guess made later.
4. **Public data must pass privacy review** before it goes to Hugging Face (faces, plates, identifiable private property).
5. **Do not infer CARLA use from support code.** A checkpoint is CARLA-assisted only when its saved roots, run configuration, or source-count log demonstrates that CARLA data was loaded.

## Snapshot Naming and Active Labels

Working run folders use date/run identities; published dataset repositories use stable series identities. The active label set is the exact base snapshot plus any explicitly named correction file used by a command. A local file's presence does not make it active.

Removed labels should be recorded as exclusions with a reason rather than erased from project history. Historical metrics remain attached to the dataset, trainer, split, and model that produced them. They are never silently recalculated and presented under the old name.

## Why This Choice

Offline metrics are only comparable when architecture adapters, dataset snapshot,
split, and command are known. These rules prevent later documentation from
inventing provenance that the saved files do not contain.

## Valid and Invalid Examples

Good — a Series 3 entry with matching schema:

```json
{ "photo_20260520_123456.jpg": { "steering": 92, "throttle": 0.37 } }
```

Bad — a row missing a field required by the Series 3 loader:

```json
{ "photo_20260510_201501.jpg": { "steering": 74 } }
```

## Validation

The Series 3 trainer prints `skipped bad labels`, `skipped missing images`, and per-source counts every time it loads a dataset; a fresh capture with a nonzero bad-label count means throttle is missing somewhere. Series 1/2 shape can be checked directly:

```bash
python3 - <<'PY'
import json
rows = json.load(open("code/ai_models_datasets/series_1_and_2/steering_corrections.json"))
print("rows", len(rows),
      "throttle-fields (should be 0 for S1/2)",
      sum("throttle" in r for r in rows))
PY
```

An empty list was valid when a new dataset was first initialized. It is not the current state: the active local Series 3/4 root contains 80,969 labeled frames after the July 29 audit. Existing models and the published dataset remain tied to the earlier 81,237-frame snapshot.

## Recovery When a Rule Is Broken

- Missing throttle in Series 3: re-derive it from that run's CSV log for the affected frames and re-write the label file; do not backfill a constant.
- Unknown provenance: quarantine the row from a claimed reproducible snapshot until the capture source is established.

Never delete images or label files to "fix" a rule violation without Ram's sign-off — count and report the bad rows first.

## Related Pages

- [Dataset Overview](../../data/dataset-overview.md)
- [Hugging Face Publishing](../../publishing/huggingface.md)
- [Data Quality](../data-quality/image-quality-checks.md)
