# Mission

The mission of SidewalkPilot is to learn how a real autonomous system is designed, trained, tested, failed, repaired, and explained by building one end to end.

The project focuses on a difficult but bounded question: can a small physical vehicle follow a residential sidewalk from camera images while independent safety and human-control layers constrain what it is allowed to do?

## Why a Physical Car

A simulation can test algorithms quickly, but a physical car exposes problems that do not appear cleanly in software:

- Sun and tree shadows can look like sidewalk edges.
- A heavy chassis loads steering rods and reveals backlash or asymmetry.
- Bluetooth, USB, UART, and Wi-Fi links can stall or disconnect.
- A servo does not always return to the same physical angle from both directions.
- Camera, LiDAR, GPS, dashboard, and inference work compete for time.
- A metric that looks better on a dataset can perform worse on the route.

Those problems are not distractions from the project. Solving and documenting them is the project.

## What Success Means

SidewalkPilot is successful when it demonstrates a repeatable engineering loop:

1. Observe a specific field failure.
2. Preserve the evidence and labels.
3. Form a testable explanation.
4. Change one identifiable part of the system.
5. Evaluate it offline and on the car.
6. Keep, revise, or roll back the change based on evidence.

The July 2026 v3.4 result is one example. Earlier models were observed following harsh diagonal shadows. v3.3 and v3.3b regressed in the field comparison; v3.4 became the first model in that comparison to complete every shadow case presented. The available evidence establishes the result, not a single proven reason for it.

## Boundaries

The goal is not to claim general autonomous-driving capability. SidewalkPilot:

- Operates only in supervised, bounded test conditions.
- Keeps a human takeover and shutdown control available.
- Does not use LiDAR to choose a path around obstacles.
- Requires the operator to stop a run when conditions exceed the tested limits.
- Publishes limitations alongside positive results.
- Treats public-road operation as out of scope.

The system's present capability is summarized in [Current Status](current-status.md). Its evidence standards are described in the [Evidence Map](../portfolio-evidence/reader-paths/evidence-map.md).
