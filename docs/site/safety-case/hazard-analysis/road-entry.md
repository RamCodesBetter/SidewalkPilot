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
