# Raw BGR vs. CLAHE

Comparing two input pipelines for the steering model: feeding raw BGR frames straight to the network, versus applying CLAHE contrast normalization first. Only two checkpoints (v2.0 / v2.0b) were ever trained and served on the CLAHE path.

## The Comparison

Raw BGR (default) vs CLAHE contrast enhancement (tested only on `2.0`/`2.0b` via
`steering_uses_clahe`). CLAHE boosts local contrast, which could help in shadow but changes the
image statistics.

## Result

CLAHE did not become the standard path; raw BGR stayed default, with shadow handled via
augmentation and real data instead. HSV/CLAHE remains off in the current pipeline.

## Related pages

- `ai-and-models/training-pipeline/metrics.md`
- `testing/field-testing/model-retest-plan.md`
- `portfolio-evidence/claims-and-proof/model-claim.md`
