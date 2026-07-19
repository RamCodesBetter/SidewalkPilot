# Road Entry

Unintended departure from a sidewalk toward a road is a high-consequence steering hazard.

## Why LiDAR Is Not the Boundary Guard

A flat road edge may produce no obstacle in the center LiDAR corridor. The current LiDAR layer can slow or brake for a physical return ahead, but it cannot identify pavement ownership or steer the car back onto the sidewalk. Road-edge control therefore depends on the camera model, route choice, conservative speed, and human supervision.

## Controls

- Field tests use selected, controlled sidewalk routes with direct line of sight.
- Road crossings remain human-operated segments.
- The operator keeps the connected controller in hand; qualifying input has software priority on the next processed control iteration.
- Stale/unavailable model output is rejected rather than reused indefinitely.
- Road-side intervention clips and CSV logs are reviewed as model failures.

The July v3.4 shadow result reduced failures in the tested conditions, but no model is claimed to make autonomous road entry impossible.

## Other Primary Hazards

| Hazard | Why it matters | Current control and limitation |
|---|---|---|
| Pedestrian or animal | Camera steering is not an object classifier | Human supervision and LiDAR stop for a center return when enabled/fresh; no general negotiation claim |
| Crosswalk | Route continuation can enter a roadway | Manual handoff; resume only after operator traversal and route proximity |
| Night/low light | Exposure and point lights differ from daylight training | Not approved by daylight testing; preserve separate night evidence |
| Sensor disconnect | Missing data can resemble a clear state | Freshness checks for camera/model; LiDAR reconnects but stale/empty LiDAR currently removes intervention |
| Mechanical steering fault | Commanded angle is not measured wheel angle | Preflight linkage check, conservative speed, operator takeover |

Risk controls reduce likelihood or consequence; they do not prove a certified residual-risk level.
