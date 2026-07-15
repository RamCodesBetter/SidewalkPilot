# AI Manual Segments

Once A* returns a path, SidewalkPilot does not drive the whole thing autonomously.
The route is split into alternating **AI segments** (sidewalks the camera model
drives) and **manual segments** (crosswalks the human drives). This split is built by
`build_segment_plan()` / `split_route_segments()` in
`code/controller/current/rc_car_app/navigation.py`.

## How it works

- `split_route_segments()` walks the path edge by edge, looks up each edge's `kind`,
  and maps it to a segment type via `segment_type_for_edge()`:
  - `SIDEWALK_SEGMENT_EDGE_KINDS` (`sidewalk`, `sidewalk_split`, `house_access`,
    `house_access_fallback`) → segment type `sidewalk`.
  - `CROSSWALK_SEGMENT_EDGE_KINDS` (`crosswalk`, `intersection`,
    `crosswalk_transfer`, `osm_gap`, `inferred_crosswalk`) → segment type
    `crosswalk`. Anything unknown also defaults to `crosswalk` (safe: hand to human).
- Consecutive edges of the same type are merged into one segment. Each segment records
  its node list, edge kinds, start/end path indices, distance, and its role.
- `build_segment_plan()` then tags each segment:
  - Sidewalk segments → `mode="ai"`, `operator="AUTO"`.
  - Crosswalk segments → `mode="manual"`, `operator="MNUL"`.
- At runtime, `operator_for_index()` decides who is driving right now based on the
  car's position along the path — returning `AUTO` on sidewalk stretches and `MNUL`
  on crosswalks, with the handoff/resume geometry (below) smoothing the transition.

## Why this choice

- The camera steering model is trained to follow **sidewalks**. Crossing a road is a
  fundamentally different, higher-risk maneuver with no sidewalk to follow, so the
  design hands crossings to the human every time rather than trusting the model
  outside its training distribution.
- Encoding "who drives" in the map itself (via edge kind) means the decision is
  explicit and inspectable, not an emergent guess from the network.
- Defaulting unknown edge kinds to manual is a conservative software default: an unclassified stretch is
  handed to the human, never silently auto-driven.

## Handoff and resume

- Approaching a crosswalk, a sidewalk segment sets a `handoff_node` ~3.0 m
  (`HANDOFF_ALERT_M`) before the crossing so control is handed to the driver before
  the car reaches the road. See `crosswalk-handoff.md`.
- After the crossing, control resumes to AI within a 2.5 m radius
  (`RESUME_RADIUS_M`) of the crosswalk's far end. See `resume-radius.md`.

## Related pages

- `autonomy-stack/navigation/crosswalk-handoff.md`
- `autonomy-stack/navigation/resume-radius.md`
- `runtime-code/runtime-loop.md`
