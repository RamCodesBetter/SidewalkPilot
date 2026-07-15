# Lighting Limits

Autonomous steering is camera-driven, so lighting outside the tested distribution
is an operating limit.

## Current Runtime Behavior

The Pi stops autonomy when the camera/model result is unavailable or stale. A
fresh Pi-local or Jon model prediction currently carries confidence `1.0`; the
`LOW_CAMERA_CONFIDENCE` gate therefore does **not** estimate uncertainty for a
fresh neural prediction. It is mainly an availability/freshness gate on the
active model path.

This means a well-formed but wrong prediction under glare or unusual light may
not trigger an automatic camera-confidence stop. Manual override and LiDAR AEB
remain separate layers, but LiDAR does not validate sidewalk boundaries or model
steering.

## Bounded Field Evidence

- The 81,237-frame Series 3/4 dataset contains real outdoor captures and shadow
  cases, plus training-time lighting/shadow augmentation.
- In the July 13 field comparison, v3.4 handled every shadow case presented and
  became the field-selected baseline.
- An earlier v3.1b operator note records a failure near orange artificial light.
- Direct lens glare, wet reflections, headlights, weather extremes, and broad
  autonomous night operation do not have a controlled validation record here.

These observations are condition-specific, not universal robustness claims.

## Operating Rule

Use supervised daylight testing on a known, controlled route. Stop for saturated,
dark, obscured, or unfamiliar camera conditions. Do not interpret fresh-result
confidence `1.0` as calibrated perception confidence.

## Related Pages

- [Night Driving Risk](../hazard-analysis/night-driving-risk.md)
- [Shadow Failures](../../testing/failures/shadow-failures.md)
- [Field Evaluation](../../model-evaluation/field-evaluation/overview.md)
