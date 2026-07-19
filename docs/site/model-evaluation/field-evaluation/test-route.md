# Test Route

A fixed route is the intended protocol for comparing field models, but the existing field record is not complete enough to claim that every historical run used one identical route, start pose, speed, weather condition, and scoring procedure.

## Known route context

Testing occurs on controlled private sidewalk routes in the Trossachs area, which also supplies the checked-in navigation graph. The training dataset includes frames from the project's real driving routes. This creates useful in-distribution tests, but it does not establish performance on unseen neighborhoods or all conditions within the known route.

The July 13 comparison supports the bounded conclusion that v3.4 handled the normal and harsh-shadow cases presented better than v3.3, v3.3b, and v3.4b. Exact route, clip, weather, start-pose, and takeover metadata were not preserved well enough for a quantitative route-level claim.

## Required comparison protocol

For every new model comparison, preserve:

1. Route identifier and direction;
2. Fixed start pose and speed policy;
3. Model version and code/config revision;
4. Lighting/weather and approximate time;
5. CSV path and continuous video or takeover clips;
6. Autonomous distance, interventions, causes, and completion status; and
7. The same ordered cases for every candidate.

The first v4.0 comparison is complete. It found v4.0f viable but mixed against v3.4, v4.0g worse, and all four PC/PCF models affected by steering echo. The next comparison should begin only after v4.1 live integration and bench replay. Use v3.4 and v4.0f as controls, test each v4.1 candidate that passes replay, and repeat v3.4 at the end to expose route or lighting drift. Offline ranking selects candidates; it does not replace physical comparison.

## Interpretation limits

- A fixed route controls some geometry, but lighting, pedestrians, parked vehicles, GPS, battery state, and starting alignment can still vary.
- Testing on a trained route is an in-distribution check, not proof of generalization.
- A lower takeover count is meaningful only when route distance, operator policy, and failure definitions are held constant.
- If video or CSV is missing, report the run as qualitative rather than reconstructing precise metrics from memory.

## Related pages

- [Field Evaluation Overview](overview.md)
- [Model Retest Plan](../../testing/field-testing/model-retest-plan.md)
- [Manual Takeover Count](manual-takeover-count.md)
