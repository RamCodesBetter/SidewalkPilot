# B Versions

What the `b` suffix on a checkpoint actually means (e.g. `v3.0` vs `v3.0b`), and why the `b` — the "best" checkpoint — is the one to be suspicious of, not the one to trust.

## What b compares

Each `b` is an alternate checkpoint (often earlier epoch) of the same numeric version. Comparing
`X` vs `Xb` shows the epoch trade: `b` frequently has lower MAE but is more straight-collapsed.

## Verdict pattern

For v3.3, deploy the FINAL balanced `3.3`, not `3.3b`. HF cards list versions only up to
themselves (a v3.1 card must not show v3.1b).

## Related pages

- `ai-and-models/training-pipeline/metrics.md`
- `testing/field-testing/model-retest-plan.md`
- `portfolio-evidence/reader-paths/evidence-map.md`
