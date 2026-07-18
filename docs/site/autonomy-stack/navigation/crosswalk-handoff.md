# Crosswalk Handoff

The crosswalk handoff is the moment SidewalkPilot takes the car out of AI mode and
tells the human to drive, just before a road crossing. It is computed by
`handoff_index()` and applied in `operator_for_index()` /
`NavigationManager.update()` in
`code/controller/current/rc_car_app/navigation.py`.

## How it works

- During `build_segment_plan()`, whenever a `sidewalk` segment is immediately followed
  by a `crosswalk` segment, the planner marks a **handoff node** partway back from the
  end of the sidewalk segment. `handoff_index()` walks backward from the segment end,
  accumulating haversine distance, and picks the first node that is at least
  `HANDOFF_ALERT_M = 3.0` meters before the crossing. The segment stores
  `handoff_alert_m = 3.0`, `handoff_node`, and `handoff_path_index`.
- At drive time, `operator_for_index()` measures the live GPS distance to the
  `handoff_node`. While the car is still more than 3.0 m away it returns `AUTO`; once
  within 3.0 m it returns `MNUL`, handing steering to the driver **before** the car
  reaches the road.
- `NavigationManager.update()` also emits a `handoff_alert` flag (true when the car is
  active and within `HANDOFF_ALERT_M` of the handoff node) plus `handoff_node` and
  `handoff_distance_m`, so the dashboard can warn the driver that a manual crossing is
  coming up.

## Returning to Automatic Control

The crosswalk segment remains `MNUL` while the operator crosses. Its far-side node carries
`RESUME_RADIUS_M = 2.5 m`. Once GPS places the car within that radius and another segment
exists, `operator_for_index()` returns the next segment's operator, normally `AUTO` for the
far sidewalk. The runtime also publishes the resume node, distance, and readiness state to
the dashboard. This keeps the human in control through the crossing while tolerating normal
GPS error near the far curb.

## Why this choice

- A crossing is the highest-risk part of any route and the camera model was never
  trained to cross roads, so control must leave the model before the car is in the
  crossing, not at the last second.
- Handing off ~3 m early gives the human real reaction time to take the controller and
  check for traffic, instead of being surprised at the curb.
- Basing the trigger on distance-to-node (not just "reached the last sidewalk node")
  means the alert fires at a consistent physical distance regardless of how the
  sidewalk nodes happen to be spaced.

Driving crossings autonomously was rejected because the model is trained for sidewalks,
not traffic, right-of-way, or pedestrian negotiation. Stopping permanently at every curb
would avoid that unsupported behavior but would not complete a route. The selected design
keeps a human present for the crossing and makes unknown segment types manual by default.

A valid test must show the dashboard warning before the crossing, the operator changing to
`MNUL`, human control through the road segment, and `AUTO` returning only near the far-side
resume node. Code presence alone does not prove that GPS triggers each transition at the
correct physical point.

## Key constants

- `HANDOFF_ALERT_M = 3.0` (meters before the crosswalk to hand off).
- `RESUME_RADIUS_M = 2.5` (meters from the far-side node before the next segment resumes).

## Related pages

- [Navigation Overview](overview.md)
- [Safety Overview](../../safety-case/safety-overview.md)
