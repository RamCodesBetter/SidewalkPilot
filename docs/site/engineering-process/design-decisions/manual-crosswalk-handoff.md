# Manual Crosswalk Handoff

This page records the decision that the model drives **sidewalk** segments
autonomously but **hands control back to the human operator at crosswalks**,
with an advance warning before the handoff.

## Decision

The navigation planner (`code/controller/current/rc_car_app/navigation.py`)
splits an A* route into typed segments and assigns an operator to each:

```python
"operator": "AUTO" if segment["type"] == "sidewalk" else "MNUL"
```

- **Sidewalk segments → `AUTO`** — the camera steering model drives (runtime sets
  `autonomous_mode = True`, gear `D`).
- **Crosswalk segments → `MNUL`** — the human takes over; the model is disabled
  for that segment.

Before a sidewalk segment ends at a crosswalk, the planner arms an early warning
`HANDOFF_ALERT_M = 3.0` m out (`handoff_index(...)`), and `operator_for_index`
flips the segment's effective operator to `MNUL` once the car is within that
distance — so the driver is told to take the wheel *before* stepping into the
road, not at the curb. When the crosswalk segment ends, the operator flips back
to `AUTO` for the next sidewalk. The runtime reads the live `operator` field each
loop and toggles autonomy accordingly (see the `nav_operator` handling in
`runtime.py`).

## Alternatives considered

| Option | Pros | Cons |
|---|---|---|
| Drive crosswalks autonomously too | fully hands-off | crosswalks mean cars, traffic timing, and pedestrians — far out of the sidewalk-only training distribution and unsafe for a solo test platform |
| Just stop and wait at every curb | simple | doesn't actually cross; no route completion |
| **Auto on sidewalk, manual at crosswalk with a 3 m warning (chosen)** | keeps autonomy where the model is competent; puts a human in the loop for the genuinely dangerous, out-of-distribution part; the advance alert avoids an abrupt curb-edge handoff | requires an operator present; segment typing must be correct in the route graph |

## Reason

The steering model is trained on sidewalk imagery and knows nothing about road
traffic, signal timing, or right-of-way. A crosswalk is precisely where a wrong
autonomous decision is most dangerous and where the training data gives the least
support. Handing off to a human at those segments keeps the safety story honest —
autonomy is claimed only where it is actually earned — and the `HANDOFF_ALERT_M`
warning gives the operator time to react instead of being surprised at the curb.
Manual input is processed regardless of segment type while the controller and Pi loop are responsive. A physical stop remains necessary for failures that prevent software override.

## How to know it worked (test gate)

- On a route that crosses a road, the dashboard/nav status should raise a handoff
  alert ~3 m before the crosswalk and the car should drop out of autonomous mode
  (`operator = MNUL`) for the crossing, then resume `AUTO` on the far sidewalk.
- `latest_nav["operator"]` and the runtime's `navigation_operator_last`
  transitions confirm the flip in both directions.

## Related pages

- `engineering-process/design-decisions/lidar-priority.md`
- `testing/failures/overview.md`
- `roadmap/next-steps.md`
