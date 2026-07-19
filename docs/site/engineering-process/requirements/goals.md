# Goals

This page states what SidewalkPilot is actually trying to achieve, in priority order, so every design decision can be traced back to a goal instead of being justified after the fact.

## What I am building toward

SidewalkPilot is a real RC car that drives itself on sidewalks and private test routes. It is not a screen demo. Every goal below has to survive contact with real hardware, real weather, and a real Xbox controller that I can grab at any moment. I built the platform on a Raspberry Pi 5 for real-time I/O (Xbox controller via pygame, Raspberry Pi Camera Module 3 Wide via Picamera2, LiDAR, GPS, hall sensor, PCA9685 steering servo, AT8236 drive motors, CSV logging, and USB dashboard telemetry), and I offload the heavy Series 3 steering model to a Jetson Orin Nano because the Raspberry Pi 5 owns the timing-critical loop and the Jetson Orin Nano supplies the GPU.

My goals, in the order I actually care about them:

1. **Maintain clean, traceable training data.** The 81,237-image Series 3/4 dataset must retain stable absolute steering/throttle labels, source provenance, split integrity, and targeted coverage of failures. Diversity and label quality matter more than increasing the raw count.
2. **Drive the sidewalk from camera.** Steering comes from the vision model. Series 1/2 use `SteeringAutonomyV2` (672,877 parameters, 200x66, single tanh regression). Series 3 uses 320x180 input: v3.0/v3.0b output steering and throttle directly, while v3.1-v3.4b use nine class logits, nine local offsets, and one throttle output. Series 4 keeps the 320x180 visual backbone, removes throttle prediction, and compares causal-history and future-supervision designs. Series 3/4 ONNX inference runs on Jetson Orin Nano.
3. **Stay safe.** The design target is for enabled LiDAR AEB to constrain forward motion and for qualifying controller input to cancel autonomy on a responsive loop. These software priorities do not cover every sensor, controller, process, power, or mechanical fault.
4. **Navigate a route.** GPS + A* over a route graph (`navigation.py`, `trossachs_nav_graph.json`) with AI and manual segments and a crosswalk handoff.
5. **Stay observable.** The Zero 2 W USB dashboard shows live car state, every controller launch writes a local CSV, training telemetry goes to Weights & Biases, and local InfluxDB telemetry is available when explicitly configured.

## Why these are the goals

The whole point of the project is a working autonomy and data loop, not a one-off drive. Good data feeds a better model; a better model needs a reliable and safe platform to be tested on; and none of it is trustworthy unless I can see the car's state and prove what happened. Data quality sits at the top because a biased dataset (for example the 2026-06-15 left-drift batch) silently poisons every model trained on it, and no amount of clever architecture fixes bad labels.

## Acceptance targets

These are target gates, not a declaration that every item has already passed. In particular,
the current record still lacks a measured physical AEB stopping-distance study and a timed
manual-override latency study.

| Goal | Done gate |
|---|---|
| Clean data | A photo run has stable labels, no corrupt files, source metadata, and a steering/lighting quality review before entering a dataset snapshot. |
| Camera driving | The model holds the sidewalk corridor on a real route without needing constant manual takeover. |
| Safety | Repeated physical obstacle tests characterize AEB stopping behavior, and timed controller tests characterize override behavior. |
| Navigation | A* produces a followable route and the car respects AI/manual segment boundaries and crosswalk handoff. |
| Observability | Dashboard stays linked over USB and the CSV captures the run; optional InfluxDB is verified separately when used. |

The current field-selected steering baseline is v3.4: it handled the tested normal and shadow cases better than v3.3, v3.3b, and v3.4b. Series 4.0 later produced a bounded field verdict: `4.0f` was viable, while the history models failed through prediction echo. Series 4.1 has no field result. None of these comparisons proves route-independent reliability.

## Related pages

- `engineering-process/design-decisions/b-checkpoints.md`
- `testing/failures/overview.md`
- `roadmap/next-steps.md`
