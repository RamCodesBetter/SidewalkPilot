# Pedestrian Risk

SidewalkPilot shares the type of space used by pedestrians, so tests are supervised and the operator keeps the connected controller in hand. The test is stopped or not started when pedestrians enter the intended test area.

## Detection Boundary

The LD19 is not a pedestrian classifier. It reports range points. A sufficiently confident return inside the center corridor can make the current policy slow or stop, regardless of whether the return came from a person, wall, post, or another object.

With AEB enabled in forward drive:

- 1.65 m to 1.25 m: throttle cap falls from 100% to 60% reference;
- 1.25 m to 1.05 m: cap remains at 60% reference; and
- At or inside 1.05 m: zero throttle and full brake are requested.

The policy does not steer around a person, does not predict motion, and does not prove that every body shape or approach angle will produce enough valid center-corridor returns.

## Operating Control

- Do not use people as first test obstacles.
- Begin with stationary, broad, visible objects and low speed.
- Keep the operator beside the vehicle with immediate takeover.
- Do not operate autonomously in uncontrolled pedestrian traffic.
- Preserve repeated stopping-distance and false-negative evidence before making a performance claim.

No formal pedestrian-approach validation is currently claimed.
