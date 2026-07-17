# Evening Robustness

Evening scenes introduce low exposure, motion blur, glare, and concentrated artificial
light. These conditions differ from the better-tested daytime route and remain outside the
current validated autonomy envelope.

## Historical Observation

An earlier v3.1b field note reports acceptable behavior in ordinary low light followed by
steering failure near an orange lamp or its cast light. The steering also appeared blocky.
The exact clip, route, artifact hash, CSV, and takeover count are not attached, so this is a
bounded operator observation rather than a night-performance result.

Adjacent hybrid-head classes can produce visibly different decoded commands, but the note
does not isolate class switching as the cause. It also cannot support a confidence claim:
the current neural path assigns confidence `1.0` to any fresh accepted result and does not
produce calibrated darkness, glare, or out-of-distribution confidence.

## Required Test

A future evening comparison should preserve model hashes, route, light sources, exposure,
speed, AEB state, CSV, continuous video, and every takeover. It should compare ordinary
low-light segments separately from colored artificial-light and glare cases.

Until that record exists, SidewalkPilot should not claim reliable night operation.

## Related Pages

- [Lighting Limits](../../safety-case/operating-limits/lighting-limits.md)
- [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md)
- [Field Evaluation Overview](overview.md)
