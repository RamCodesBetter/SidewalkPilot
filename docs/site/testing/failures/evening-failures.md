# Evening Failures

Evening scenes differ from the better-tested daytime domain through lower light,
motion blur, glare, and concentrated light sources.

## Recorded observation

An earlier v3.1b field run was reported to drive acceptably in ordinary low light
but fail near an orange lamp or its light cast. The model also appeared blocky.
The route, clip, exact artifact hash, and takeover count are not attached here, so
this is a bounded historical field note rather than a quantitative result.

The hybrid head selects one of nine classes and decodes an offset inside that
class. Adjacent-class changes may contribute to visible command steps, but the
field note alone does not prove that architecture was the cause. Runtime output
smoothing is now implemented separately and does not establish night robustness.

## Current safety limitation

The neural path does not produce calibrated image-quality confidence. A fresh
accepted result is assigned confidence `1.0`, so the `LOW_CAMERA_CONFIDENCE` gate
mainly catches unavailable or stale inference. It should not be described as an
automatic detector for darkness, glare, or unfamiliar lighting.

Night operation remains outside the current test envelope. A future test must
use direct supervision and preserve the model hash, route, light source, CSV,
video, and takeover record.

## Related pages

- [Lighting Limits](../../safety-case/operating-limits/lighting-limits.md)
- [Field Testing](../field-testing/overview.md)
- [Failure Clips](../../exhibits/media/failure-clips.md)
