# House-Side Edge Drift

House-side edge drift means the vehicle approaches the lawn, dirt, hedge, or other boundary
opposite the road side. It is a useful field category, but the current record does not
support a normalized event rate or a claim that this is the most frequent drift direction.

## Evaluation

For each event, preserve:

- Model and artifact hash;
- Route position, surface, and lighting;
- Requested steering and physical outcome;
- CSV time range and linked clip;
- Whether LiDAR intervened; and
- The operator's takeover reason.

Review whether the neural command was wrong, late, unstable, or physically not executed as
expected. Grass or a hedge may produce LiDAR points, but the center-corridor policy is not a
sidewalk-edge detector and must not be credited with general lateral containment.

## Current Evidence Limit

Older notes associate some v3.2b interruptions with house-side drift and dappled shadows,
but the complete clips, route record, and normalized exposure are not indexed here. Exact
counts and causal attribution are therefore not carried forward as verified results.

The next fixed-route comparison should report house-side and road-side events separately.
That record can support a directional rate only when every candidate receives comparable
distance, speed, lighting, and intervention criteria.

## Related Pages

- [Road-Entry Risk](road-entry-risk.md)
- [Manual Takeover Count](manual-takeover-count.md)
- [Model Retest Plan](../../testing/field-testing/model-retest-plan.md)
