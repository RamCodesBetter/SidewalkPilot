# Turn Coverage

The rule that the dataset must hold enough turning frames across the full steering range — not collapse into a pile of near-straight driving. Turn coverage is the single most important balance axis for Series 3, because the known dataset gap is turns (especially mid-right turns and turns-in-shadow), and because the model's steering head is scored on turn capability, not average error.

## How it works

Turn coverage is measured on the logical steering label (`0` left, `90` center, `180` right). The Series 3 trainer (`code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`) reports the distribution two ways.

`print_bucket_distribution()` prints the coverage histogram over seven servo-degree bands:

| Band | Servo degrees | Meaning |
|---|---|---|
| `0_to_45_hard_left` | `< 45` | hard left |
| `45_to_75_left` | `45–75` | left |
| `75_to_85_soft_left` | `75–85` | soft left |
| `85_to_95_straight` | `85–95` | straight |
| `95_to_105_soft_right` | `95–105` | soft right |
| `105_to_135_right` | `105–135` | right |
| `135_to_180_hard_right` | `135–180` | hard right |

The Series 3 training sampler (`make_weighted_sampler()` over the same `SERVO_BUCKETS`) applies `(median_bucket_count / its_bucket_count) ** sampler_balance_power`, multiplied by a source weight. Its default power `0.3` gently lifts thin turn buckets without fully flattening the distribution. The fixed Series 4 runs instead used sampler power `0.0`, deterministic left/right balance flipping, and class-loss power `0.5`. Neither configuration can invent scene diversity that was never captured.

The deployed model head is the hybrid 9-class scheme (HL, L, L+, SL, ST, SR, R, R+, HR) plus per-class offset; the seven trainer bands above are the diagnostic view of that same left-center-right axis.

## Why it matters

Two hard-won findings drive this rule:

1. Turn coverage must be measured per snapshot. The 81,237-image total does not guarantee balanced mid-right or turn-in-shadow examples.
2. MAE alone can favor center-biased predictions on a straight-heavy set. Models must also be judged by confusion-matrix balance, per-class recall, turn metrics, signed error, and field behavior.

## Good vs bad example

- Good: a batch with a full spread across all seven bands, both hard-left and hard-right represented, including turns taken under shadow.
- Bad: a batch dominated by `85_to_95_straight` with little representation in a required turn band. A raw count warning is not a model verdict, but it identifies coverage that sampling will repeatedly reuse rather than expand.

## Validation command

Run a scan/short pass and read the target-bucket histogram:

```bash
cd /home/rsabavat/rc_car_code/code/ai_models_datasets/series_3_and_4
python3 series_3_sidewalkpilot_trainer.py --help
```

Look for every band non-empty and the turn bands (not just straight) each holding a real share.

## Recovery step

If a turn band is thin, the fix is field collection of that specific turn (a mid-right-turn run, a turn-in-shadow run), not just leaning harder on the sampler weights — sampler oversampling of a tiny bucket amplifies whatever few frames exist, which can overfit. Turn-only horizontal flip augmentation can help balance left vs right, but it does not add turn-in-shadow diversity.

## Evidence to attach

- The seven-band `target buckets` histogram for the batch.
- Per-bucket counts for the exact dataset snapshot.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
