# Road Entry Risk

This is the highest-consequence failure class in the current project. Road-entry risk includes leaving the sidewalk toward a road or continuing autonomous motion near a crossing. The current mitigations reduce risk but do not guarantee containment or operator takeover under every software, controller, GPS, or mechanical fault.

## What the design does

Road crossings are deliberately **not** assigned to the vision model. Navigation splits a planned route into segments in `code/controller/current/rc_car_app/navigation.py`: sidewalk segments request `AUTO`, while crossing-family segments request `MNUL`. Near the end of an AI segment, the nav manager raises a handoff alert using `HANDOFF_ALERT_M = 3.0 m`. This is an implemented software contract; its GPS timing and end-to-end behavior have not yet been preserved as a completed crossing field test.

## What can go wrong

The risk is any path where the car keeps steering itself toward the road instead of stopping for the manual handoff:

- **Perception mistakes a curb-cut/road edge for the corridor.** This is the driveway-confusion failure aimed at a real road: the sideways opening at a crossing reads as the path continuing, and vision-mode steering pulls toward it. (See `driveway-confusion.md`.)
- **Handoff timing.** If GPS is degraded or a segment is mislabeled, the 3 m alert could arrive late or the wrong segment could run in `ai` mode near a road.
- **The operator misses the alert.** The handoff is only safe if the alert is clearly surfaced on the dashboard and the operator is watching.

## Layers that keep it safe

- **Segment mode** — the planner marks crossing-family segments `MNUL` instead of `AUTO`.
- **LiDAR / AEB** — when enabled and receiving qualifying center-corridor points, LiDAR can reduce forward throttle or request a stop. It does not recognize roads or guarantee detection of a curb, vehicle, or person.
- **Manual override** — processed by the Raspberry Pi 5 loop while the Xbox controller is connected and responsive.
- **Supervision** — the project is operated on controlled private test routes with an operator ready to stop motion; it is not approved for unattended road-adjacent operation.

## Next change

- **Planned:** verify handoff timing on real crossings with GPS in the loop, and confirm the dashboard surfaces the `handoff_alert` prominently enough (LED rows are tiny, so wording must be unambiguous). Treat any AI-mode steering that continues past a handoff node as a fail, not a warn.

## Test setup

- **Setup:** Raspberry Pi 5 controller with GPS (BN880 on `/dev/ttyAMA0`), LiDAR/AEB armed, Raspberry Pi Camera Module 3 Wide; a planned route that ends an AI segment at a crosswalk/road.
- **Procedure:** run `car`, then select `<version>` on the dashboard model page, drive the route toward the crossing; watch for the handoff alert and the mode switch to manual.
- **Pass/warn/fail:** pass = handoff alert fires by ~3 m and control drops to manual before the road edge; warn = alert late but operator takes over cleanly; fail = car keeps AI-steering toward/into the road boundary.
- **Evidence to attach (planned):** route + segment-mode log, handoff-alert timing from the runtime CSV, dashboard capture, manual-takeover count, model version.

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
