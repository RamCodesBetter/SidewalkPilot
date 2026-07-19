# Driveway Confusion

A driveway interrupts normal sidewalk-edge geometry: concrete widens or crosses a vehicle path, a curb may ramp down, and one visual boundary can weaken. A steering model can interpret that opening as a turn instead of continuing across the sidewalk alignment.

## Current implementation

`estimate_path_bias_from_frame()` in `vision.py` contains a classic image-processing fallback with a `driveway_cut_hint`. That heuristic remains in the source for diagnostics or fallback work, but the current Series 3/4 Jetson Orin Nano result sets `driveway_cut_hint = False` and supplies a neural steering result directly. The live Series 3/4 path therefore does **not** have a verified driveway classifier or an active driveway-specific stop gate.

The runtime recognizes `stop_reason == "driveway_cut"` for dashboard alert formatting, but the current neural path does not generate that reason. A dormant state field is not evidence of an active safety feature.

## Plausible contributors

- A missing or weakened sidewalk edge can change the visual center cue.
- Driveway scenes may be underrepresented or inconsistently labeled.
- Lighting, pavement texture, steering history, and vehicle position can be confounded with the driveway itself.

These are hypotheses to test, not established root causes for a recorded failure.

## Required test

1. Define a fixed set of driveway approaches, including straight crossings and nearby true turns.
2. Preserve model version, frame/video, CSV, lighting, starting position, and whether manual takeover occurred.
3. Compare v3.4, viable v4.0f, and any v4.1 candidate that passes bench replay without changing other runtime constants.
4. Treat entry into the vehicle path or a required takeover as a failure. Record an unnecessary stop separately from a correct straight crossing.

No completed, route-level driveway comparison is currently claimed.

## Related pages

- [Field Testing Overview](../field-testing/overview.md)
- [Field Evaluation Overview](../../model-evaluation/field-evaluation/overview.md)
- [Safety Overview](../../safety-case/safety-overview.md)
