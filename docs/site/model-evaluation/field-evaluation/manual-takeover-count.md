# Manual Takeover Count

Manual takeover count records how often the operator cancels autonomy during a defined
route. It becomes comparable only when route length, conditions, model, intervention rules,
and exposure time are preserved.

## How it works

When the controller is connected and the Raspberry Pi 5 loop is responsive, qualifying steering input,
gas above the runtime threshold, or brake input calls `cancel_autonomous_mode(...)` on a
processed control iteration. The CSV records autonomous state and intervention fields. A
mid-route `On` to `Off` transition can therefore be reviewed with nearby telemetry and the
runtime's cancellation reason.

The interruption-clip recorder is configured to retain two seconds of pre-takeover JPEGs
while autonomy is active. Clip creation and transfer must be verified for the individual run;
configuration alone is not evidence that every intervention has a usable file.

## Reporting contract

For each comparison, preserve:

- Route identifier and distance;
- Model version and artifact hash;
- Lighting, surface, payload, battery, and sensor state;
- Total autonomous time and distance;
- Takeover count and trigger;
- Reason category and linked clip when available.

Report both interventions per run and interventions per kilometer when distance is known.
A zero-takeover run is evidence for that exposure only, not proof of general reliability.

## Current evidence limit

An earlier draft described seven v3.2b takeovers and attributed all of them to dappled tree
shadow. The current repository does not link a complete route record, normalized distance,
and seven preserved clips sufficient to audit that exact claim, so it is not carried forward
as a verified study result. The July 13 v3.4 verdict is also qualitative and bounded.

The next ordered Series 4 field test should produce the complete record above before a new
checkpoint is promoted over v3.4.

## Related pages

- `ai-and-models/training-pipeline/metrics.md`
- `testing/field-testing/model-retest-plan.md`
- `portfolio-evidence/reader-paths/evidence-map.md`
