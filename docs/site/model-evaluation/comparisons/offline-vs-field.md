# Offline Versus Field Evaluation

Offline evaluation and physical testing answer different questions.

## Offline Evidence

The common evaluator applies every compatible checkpoint to the same labeled
challenge subset. It can expose class collapse, directional bias, large errors,
and candidates worth driving. It cannot reproduce closed-loop error growth,
servo load, wheel behavior, route hazards, or a particular lighting geometry.

## Field Evidence

A supervised field comparison reveals whether the car actually holds the tested
route. The result is strongest when the route, lighting, model file hash, takeover
count, logs, and clips are preserved. A successful run remains bounded to those
conditions.

The July 13, 2026 comparison rejected v3.3 and v3.3b, found v3.4b slightly worse
than v3.4, and selected v3.4. Its route and clip record was incomplete, so the
verdict is qualitative rather than a repeatable benchmark. The later v4.0 test
also produced a qualitative verdict: v4.0f was viable but mixed against v3.4,
while the history-input models failed from steering echo. v4.1 remains offline-only.

## Promotion Rule

Use offline metrics to order candidates, then require a supervised physical run
before changing the field baseline. Neither stage alone establishes general
safety or universal robustness.

## Common Comparison Questions

**Final versus validation-selected checkpoints.** Regular models preserve the final epoch. Suffixes such as `b`, and Series 4 `r/g/c`, preserve the validation-selected checkpoint from the same run. The suffix does not guarantee better driving; both are candidates until evaluated.

**Raw BGR versus CLAHE.** v2.0/v2.0b use the historical CLAHE path. Other current models use raw BGR with matching training preprocessing. A comparison is valid only when each checkpoint receives its intended preprocessing.

**MAE versus turning capability.** On a straight-heavy set, lower MAE can accompany weaker turn recall. Bal9, turn exact, turn +/-1, confusion balance, and signed error are evaluated before using MAE to separate otherwise capable candidates.

**Per-dataset behavior.** Overall scores can be driven by one large or easy source. The evaluator therefore retains source-level results and a hold-last temporal baseline. Dataset names and counts must accompany claims.

## Related Pages

- [Offline Evaluation](../offline-evaluation/overview.md)
- [Field Testing](../../testing/field-testing/overview.md)
- [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md)
