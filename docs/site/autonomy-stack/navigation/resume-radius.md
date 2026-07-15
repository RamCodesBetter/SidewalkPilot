# Resume Radius

The resume radius is the counterpart to the crosswalk handoff: it is how SidewalkPilot
decides the human has finished crossing the road and control can return to the AI. It
is the `RESUME_RADIUS_M` constant applied in `operator_for_index()` and
`NavigationManager.update()` in
`code/controller/current/rc_car_app/navigation.py`.

## How it works

- Every `crosswalk` segment gets `resume_radius_m = RESUME_RADIUS_M = 2.5` set in
  `build_segment_plan()`. Its `end_node` is the far side of the crossing.
- While the car is on a crosswalk segment, `operator_for_index()` returns `MNUL`
  (human drives). It measures the live GPS distance to the crosswalk's `end_node`.
- Once the car is within `2.5` m of that far-side node **and** there is a next segment,
  `operator_for_index()` returns that next segment's operator — normally `AUTO`,
  resuming AI sidewalk-following on the other side of the road.
- `NavigationManager.update()` also emits `resume_node`, `resume_distance_m`, and a
  `resume_ready` flag (true when within 2.5 m of the far node) so the dashboard can
  show the driver that the AI is about to take back over.

## Why this choice

- Handing control back too early — while the car is still in the roadway — would put
  the model in charge during the most dangerous stretch. Waiting until the car has
  essentially reached the far curb keeps the human in control for the whole crossing.
- A 2.5 m radius is tight enough that AI resumes promptly once the sidewalk begins,
  but loose enough to tolerate GPS position noise so the resume actually triggers
  instead of the car overshooting the exact end node and never re-arming.
- Pairing a 3.0 m handoff (before) with a 2.5 m resume (after) gives a clean,
  symmetric manual "bubble" around each crossing.

## Key constants

- `RESUME_RADIUS_M = 2.5` (meters from the crosswalk far end to resume AI).
- Companion constant: `HANDOFF_ALERT_M = 3.0` for the entry-side handoff.

## Related pages

- `autonomy-stack/navigation/crosswalk-handoff.md`
- `autonomy-stack/navigation/ai-manual-segments.md`
- `runtime-code/runtime-loop.md`
