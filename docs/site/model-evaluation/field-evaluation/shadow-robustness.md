# Shadow Robustness

Shadow robustness asks whether a steering model follows the sidewalk rather than a
high-contrast lighting boundary. Dappled tree shade and hard diagonal shadows have been
repeated field failure conditions for this project.

## Evaluation Protocol

Run each candidate over the same supervised route sections containing ordinary turns and
known shadow cases. Preserve the model hash, route, time, weather, starting pose, CSV,
continuous video or interruption clips, and every manual takeover. Score a case as pass,
warning, or failure using a rule chosen before comparing the next model.

The interruption recorder and `code/test_files/models/clip_bucket_analyzer.py` can help inspect the commands before
a takeover. A clip does not contain steering ground truth or a measured wheel angle, so it
supports diagnosis but cannot prove a single root cause.

## Evidence Record

Earlier working notes describe a seven-clip v3.2b review associated with dappled shadows.
The clips and complete analysis record are not indexed in this repository, so the exact
counts, directions, and confidence statistics from that draft are not reported as verified
results. The current remote neural path also assigns confidence `1.0` to every fresh accepted
result; that field is not a calibrated shadow or image-quality score.

The strongest preserved field statement is the bounded July 13 comparison: v3.4 handled
every shadow case presented in that run and performed better than v3.4b, v3.3, and v3.3b.
The exact route, clip identifiers, and takeover count were not retained, so this is a
qualitative field selection rather than a shadow success rate.

## Interpretation

Shadow-following is consistent with a visual model treating a lighting boundary as path
geometry, but the project has not isolated one causal training feature. Dataset membership,
labels, augmentation, preprocessing, and closed-loop behavior can all contribute. Future
experiments should change one factor at a time and repeat the same preserved field cases.

## Related Pages

- [Interruption Clips](interruption-clips.md)
- [Model Retest Plan](../../testing/field-testing/model-retest-plan.md)
- [Model Claim](../../portfolio-evidence/claims-and-proof/model-claim.md)
