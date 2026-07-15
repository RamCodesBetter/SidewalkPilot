# Where It Can Run

This page defines the environments where SidewalkPilot is designed and authorized
to drive autonomously. It is the positive half of the operating design domain
(ODD); the negative half — the exclusions — lives in `where-it-cannot-run.md`.
Everything here is scoped by what the hardware, the model, and the safety layer
were actually built and tested for, not by what the car might survive.

## The Intended Operating Domain

SidewalkPilot is a supervised sidewalk research platform. The domain it is
built for is:

- **Paved pedestrian sidewalks** with a recognizable corridor: a walkable strip
  bounded on both sides by an edge the vision stack can find (grass line, curb,
  fence, wall). The vision fallback in `vision.py` explicitly looks for a left and
  right corridor edge (`left_edge_found` / `right_edge_found`) and a corridor
  width; a scene with two findable edges is the intended case.
- **Selected controlled test sections** where the operator can walk alongside the
  car with the Xbox controller and stop when the route is no longer clear.
- **Roughly flat, single-level ground.** The chassis is a Yahboom Ackermann 520M
  with a fixed camera pitch; there is no ramp, stair, or slope handling in the
  code.
- **Operator-selected low speed.** `MAX_AUTONOMOUS_SPEED_MPH = 3.2` is declared but is
  not enforced as a closed-loop speed cap. The current LiDAR governor constrains a
  reference throttle command, not mph. See `speed-limits.md`.
- **Routes that exist in the nav graph.** GPS navigation (`navigation.py`) does A*
  over `trossachs_nav_graph.json`. The car can only self-navigate along segments
  that are actually in that graph; anywhere off-graph is manual-only driving.

## Preconditions before any autonomous run

Autonomy is never the default state. Before the car moves under the model, all of
the following must hold:

- A human operator is present with the Xbox controller. Manual override is the
  top software decision layer (`decision-priority.md`): qualifying steering,
  throttle, or brake input cancels autonomy when processed by the Raspberry Pi 5 loop.
- Autonomy is explicitly armed by the operator (`AUTONOMY_TOGGLE_BUTTON = 0`); it
  does not self-enable.
- The camera stream is live. `apply_autonomous_controls(...)` hard-stops with
  `model_unavailable` or `model_low_confidence` if `webcam_vision` is missing, local
  analysis is older than 0.75 seconds, a matching Jetson Orin Nano result is unavailable or older
  than 0.25 seconds, or confidence is below `LOW_CAMERA_CONFIDENCE` (0.25). This verifies result freshness/availability;
  accepted neural confidence is not calibrated proof that the scene is understood.
- The LiDAR safety layer is available for AEB. AEB is toggled by
  `AEB_TOGGLE_BUTTON = 14` and defaults on (`Metrics.aeb_enabled = True`). LiDAR
  dropouts are tolerated (the reader auto-reconnects) but a run should not start
  in a place where obstacle detection is expected to be unusable.

## Where it runs today vs. planned

- **Runs today (tested):** selected supervised sidewalk/driveway sections in
  daylight with the operator in the loop. This is where the real driving
  photos were captured and where the field verdicts (e.g. the v3.1b night test)
  were recorded.
- **Planned / not-yet-authorized:** unsupervised operation, public shared
  sidewalks with pedestrian traffic, or any route without a hand on the kill
  switch. None of that is claimed as tested and it is out of the current ODD.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
