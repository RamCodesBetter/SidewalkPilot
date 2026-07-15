# Crosswalk Risk

A crosswalk is where a sidewalk route enters a road. The steering model predicts sidewalk steering only; it does not detect traffic or decide when a road is safe to cross. The route design therefore marks crossing-family segments for manual operation.

## Implemented software policy

`build_segment_plan()` in `navigation.py` divides a route into typed segments:

- Sidewalk segments request `operator = "AUTO"`;
- `crosswalk`, `intersection`, `crosswalk_transfer`, `osm_gap`, and `inferred_crosswalk` edges request `operator = "MNUL"`;
- Crossing-family edges also receive added A* cost so the planner prefers routes with fewer or lower-cost crossings;
- `HANDOFF_ALERT_M = 3.0` defines the configured pre-crossing alert distance; and
- `RESUME_RADIUS_M = 2.5` defines the configured far-side resume region.

When runtime route state changes to `MNUL`, it calls `cancel_autonomous_mode()`. A change back to `AUTO` can re-enable autonomy when the camera/model path is available.

## Limits

This is an implemented planning and state-transition contract, not a certified road-entry barrier:

- GPS error or a wrong graph edge kind can move or omit the handoff.
- The 3.0 m and 2.5 m values are policy constants, not measured guarantees.
- LiDAR does not recognize traffic or road boundaries. When AEB is enabled, it reacts only to qualifying center-corridor range points.
- Manual override depends on a connected controller and responsive Pi process.
- No preserved live-GPS crosswalk run currently establishes end-to-end handoff timing and resume behavior.

Therefore, crossing operation remains manual and supervised. The project does not claim unattended or autonomous road crossing.

## Hazard record

| Field | Current state |
|---|---|
| Hazard | Autonomous entry onto a road at a crossing/intersection |
| Detection input | Route edge kind and GPS distance to route nodes |
| Software response | Request `MNUL` near the configured handoff; permit later `AUTO` only when route state advances |
| Dependency | Correct graph labels, usable GPS, dashboard/operator attention, connected controller |
| Evidence available | Route-planning and runtime transition code |
| Evidence missing | Preserved physical crossing test with GPS trace, video, alert timing, and takeover result |

## Required field test

Use a non-road bench simulation or controlled private mock crossing first. Preserve the route/segment output, GPS trace, dashboard alert, runtime CSV, and video. Treat a late/missing handoff or autonomous motion into the crossing region as a failure.

## Related pages

- [Safety Overview](../safety-overview.md)
- [Manual Override](../fault-handling/manual-override.md)
- [Navigation Graph Diagram](../../exhibits/diagrams/navigation-graph-diagram.md)
