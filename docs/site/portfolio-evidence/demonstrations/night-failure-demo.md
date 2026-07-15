# Night Failure Field Note

An earlier operator note records a v3.1b steering failure near orange artificial light and
visibly blocky steering. The exact clip, CSV, route, artifact hash, and AEB state are not
indexed together, so this page treats the event as a historical observation rather than a
reproducible demonstration.

## Bounded Observation

- The reported model was v3.1b under an evening or night condition.
- Steering appeared biased near a warm-colored light source.
- Steering also appeared blocky.
- The available record does not establish a night-driving success rate or a single cause.

The hybrid head can jump between adjacent steering classes, but architecture, image content,
runtime smoothing, mechanics, and timing were not isolated in this event. Insufficient
matching data is also a hypothesis, not a proven explanation.

## Current Limit

The runtime now applies EMA smoothing once per completed Jetson Orin Nano inference. That implementation
does not establish night robustness or guarantee smooth physical steering. The neural path
reports confidence `1.0` for a fresh accepted result, so low-camera-confidence logic must not
be described as a darkness or glare detector.

Night operation remains outside the current validated autonomy envelope. A future retest
needs a linked clip, CSV range, model hash, route, light condition, AEB state, and takeover
record before the result can be reported quantitatively.

## Related Pages

- [Evening Robustness](../../model-evaluation/field-evaluation/evening-robustness.md)
- [Lighting Limits](../../safety-case/operating-limits/lighting-limits.md)
- [Evidence Map](../reader-paths/evidence-map.md)
