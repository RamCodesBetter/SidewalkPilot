# Media Index

This page is the master index for all SidewalkPilot driving video, grouping the
individual clip pages and stating what each set of footage is meant to prove.

## What lives here

Video is the primary field evidence for an autonomy project: a confusion matrix
proves what a model does on held-out frames, but only recorded driving proves
what the whole loop (Raspberry Pi 5 controller -> Jetson Orin Nano inference at 10.42.0.2:8770
-> camera/LiDAR/GPS fusion -> PCA9685 steering and AT8236-controlled JGB37-520 DC motors) does on a real
sidewalk. Each clip is tied to a model version, a route, a date, and a weather /
lighting condition so a viewer can trust the artifact instead of taking a claim on
faith.

The media record groups:

| Media | Purpose | Claim it supports |
|---|---|---|
| Success clips | Runs where the car followed the sidewalk and handled the presented scene as intended | End-to-end behavior in bounded field conditions |
| Failure clips | Disengagements, drift, shadows, road approach, and sensor/link failures | Honest failure analysis and iteration source |
| Photos | Hardware build, wiring, sensors, route, and field setup | Physical implementation and development journey |
| Dashboard screenshots | Zero 2 W pages, camera/LiDAR previews, and link states | Telemetry and observability implementation |

## Why keep an index (and keep failures)

Two reasons. First, a single indexed list with model version and condition columns
is far easier to scan than prose scattered across a long report. Second, and more
important for the technical record: **failure clips are evidence too.** The core
finding of the model work — that MAE is a misleading metric and that the real gap
is turns, especially mid-right turns and turns in shadow — only becomes credible
when the failure footage that exposed it is shown alongside the successes. Hiding
the failures would weaken the argument, not strengthen it.

## Status

- Clip capture is ongoing; most Series 3 field footage (v3.1b onward) is recent.
- v3.3/v3.3b were tested and rejected on July 13; v3.4 was selected. The run lacks a complete clip index.
- Series 4 field clips are planned, not yet recorded.
- Privacy review (faces, license plates, house numbers) is required before any clip
  is published externally; treat all raw footage as internal until reviewed.

## Required Metadata

Every published clip or image should carry date, model/version where relevant, route/condition description, what is visible, whether the result is success/failure/illustration, and a privacy-review state. A cropped highlight without its run context is not standalone evidence.

## Related pages

- [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md)
- [Reports and PDF](../../publishing/reports.md)
- [Evidence Tables](../tables/model-metrics-table.md)
