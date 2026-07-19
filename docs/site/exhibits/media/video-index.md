# Media Index

This page is the master index for all SidewalkPilot driving video, grouping the
available field footage and stating what each set of recordings is meant to show.

## What Lives Here

Video is the primary field evidence for an autonomy project: a confusion matrix
proves what a model does on held-out frames, but only recorded driving proves
what the whole loop (Raspberry Pi 5 controller -> Jetson Orin Nano inference at
`10.42.0.2:8770` -> camera, LiDAR, and GPS state -> PCA9685 Servo Controller,
AT8236 Motor Controller, and JGB37-520 DC motors) does on a real sidewalk. Each
clip should be tied to a model version, route, date, weather, and lighting
condition so a viewer can assess the evidence in context.

The media record groups:

| Media | Purpose | Claim it supports |
|---|---|---|
| Success clips | Runs where the car followed the sidewalk and handled the presented scene as intended | End-to-end behavior in bounded field conditions |
| Failure clips | Disengagements, drift, shadows, road approach, and sensor/link failures | Honest failure analysis and iteration source |
| Photos | Hardware build, wiring, sensors, route, and field setup | Physical implementation and development journey |
| Dashboard screenshots | Zero 2 W pages, camera/LiDAR previews, and link states | Telemetry and observability implementation |

## Why Keep an Index (and Keep Failures)

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
- Series 4.0 field clips were recorded and remain private pending indexing and privacy review. Series 4.1 has not been driven.
- Privacy review (faces, license plates, house numbers) is required before any clip
  is published externally; treat all raw footage as internal until reviewed.

## Required Metadata

Every published clip or image should carry date, model/version where relevant, route/condition description, what is visible, whether the result is success/failure/illustration, and a privacy-review state. A cropped highlight without its run context is not standalone evidence.

## Related Pages

- [Evidence Map](../../portfolio-evidence/reader-paths/evidence-map.md)
- [Reports and PDF](../../publishing/reports.md)
- [Evidence Tables](../tables/model-metrics-table.md)
