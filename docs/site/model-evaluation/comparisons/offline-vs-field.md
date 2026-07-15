# Offline Versus Field Evaluation

Offline evaluation and physical testing answer different questions.

## Offline evidence

The common evaluator applies every compatible checkpoint to the same labeled
challenge subset. It can expose class collapse, directional bias, large errors,
and candidates worth driving. It cannot reproduce closed-loop error growth,
servo load, wheel behavior, route hazards, or a particular lighting geometry.

## Field evidence

A supervised field comparison reveals whether the car actually holds the tested
route. The result is strongest when the route, lighting, artifact hash, takeover
count, logs, and clips are preserved. A successful run remains bounded to those
conditions.

The July 13, 2026 comparison rejected v3.3 and v3.3b, found v3.4b slightly worse
than v3.4, and selected v3.4. Its route and clip record was incomplete, so the
verdict is qualitative rather than a repeatable benchmark. Series 4 remains
offline-only until the planned physical comparison.

## Promotion rule

Use offline metrics to order candidates, then require a supervised physical run
before changing the field baseline. Neither stage alone establishes general
safety or universal robustness.

## Related pages

- [Offline Evaluation](../offline-evaluation/overview.md)
- [Field Testing](../../testing/field-testing/overview.md)
- [Model Claim](../../portfolio-evidence/claims-and-proof/model-claim.md)
