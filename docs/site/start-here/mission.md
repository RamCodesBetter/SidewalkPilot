# Mission

The mission of SidewalkPilot is to learn how a real autonomous system is designed, trained, tested, failed, repaired, and explained by building one end to end.

The project focuses on a difficult but bounded question: can a small physical vehicle follow a residential sidewalk from camera images while independent safety and human-control layers constrain what it is allowed to do?

## Why A Physical Car

A simulation can test algorithms quickly, but a physical car exposes problems that do not appear cleanly in software:

- sun and tree shadows can look like sidewalk edges;
- a heavy chassis loads steering rods and reveals backlash or asymmetry;
- Bluetooth, USB, UART, and Wi-Fi links can stall or disconnect;
- a servo does not always return to the same physical angle from both directions;
- camera, LiDAR, GPS, dashboard, and inference work compete for time;
- a metric that looks better on a dataset can perform worse on the route.

Those problems are not distractions from the project. Solving and documenting them is the project.

## What Success Means

SidewalkPilot is successful when it demonstrates a repeatable engineering loop:

1. Observe a specific field failure.
2. Preserve the evidence and labels.
3. Form a testable explanation.
4. Change one identifiable part of the system.
5. evaluate it offline and on the car.
6. Keep, revise, or roll back the change based on evidence.

The July 2026 v3.4 result is one example. Earlier models followed harsh diagonal shadows. v3.3 increased shadow augmentation but regressed in the field. v3.4 rebalanced the training approach and became the first model in that comparison to complete every shadow case presented.

## Boundaries

The goal is not to claim general autonomous-driving capability. SidewalkPilot:

- operates only in supervised, bounded test conditions;
- keeps a human takeover and shutdown control available;
- does not use LiDAR to choose a path around obstacles;
- must stop when a situation exceeds its tested operating limits;
- publishes limitations alongside positive results;
- treats public-road operation as out of scope.

The system's present capability is summarized in [Current Status](current-status.md). Its evidence standards are described in the [Evidence Map](../portfolio-evidence/reader-paths/evidence-map.md).
