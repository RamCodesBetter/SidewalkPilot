# Public Roads

This page states where SidewalkPilot is and is not operated, and why the platform stays off public roads and vehicle traffic. It is a scope-and-safety boundary, not a demo page.

## The Boundary

SidewalkPilot is a small RC-scale car built to drive on **sidewalks and private test routes** under direct human supervision. It is explicitly not a road vehicle and is not operated in vehicle traffic lanes. The name and the whole design target the pedestrian environment: slow speed, narrow paths, walking-pace decisions.

- **Controlled sidewalk test routes only.** The operator stays present with line of sight and stops the run when pedestrians, traffic, or conditions make the test unsuitable.
- **No public-road driving.** The car does not enter roadways with cars. Where a route must cross a road, that crossing is handled as a manual/human-operated segment, not an autonomous one (see below).
- **Direct supervision is required.** The operating procedure requires an operator holding the controller and ready to cut power. With the controller connected and the loop responsive, steering, gas, or brake input cancels autonomy through `cancel_autonomous_mode`.

## Why the platform stays off roads

- **Speed and scale.** The vehicle is RC-scale and tested conservatively. Although `MAX_AUTONOMOUS_SPEED_MPH = 3.2` is declared, it is not an enforced closed-loop cap and must not be presented as one.
- **Sensing envelope.** The autonomy stack is tuned for sidewalk-scale hazards: center-corridor LiDAR slowdown and emergency braking, a forward camera for steering, and GPS for route-level navigation. It is not designed to perceive or negotiate road traffic.
- **Conservative model-fault response.** When the model is unavailable or its result is stale, the autonomous path requests a hard stop instead of continuing. This is one implemented response, not a complete functional-safety guarantee.

## Crosswalks and road crossings

The navigation layer (`navigation.py`, A* over a route graph) supports splitting a route into AI-driven and human/manual segments. A crossing is modeled as a handoff: the route can hand control back to the human operator for the crossing rather than driving itself across a road. When a navigation route requests a segment the camera model can't serve, the runtime cancels autonomy and reverts to manual (`cancel_autonomous_mode`, e.g. "human/manual segment"). This keeps the road-adjacent part of any route under human control.

## Series 3 note

New steering models do not change this boundary. Expanding beyond directly supervised sidewalk testing would require a separate safety, legal, and engineering review.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
