# Failure Clips

This page collects the driving videos where SidewalkPilot got it wrong: drift,
mis-classified scenes, a disengagement, or a place where the safety layer had to
step in. These clips are kept on purpose — the failures are what drove nearly every
model and data decision in the project.

## What each clip proves

A failure clip earns its place by pinning down *why* it failed, not just *that* it
failed. It should name the same fields a success clip does, plus a root-cause note
that ties the footage to a specific fix or a specific gap in the training data.

| Field | What to record |
|---|---|
| Clip | File name or link |
| Model version | e.g. Series 3 `v3.1b`, or a Series 1/2 checkpoint |
| Route / condition | Route, lighting, weather |
| Failure mode | Drift, wrong bucket, missed turn, false stop, disengagement |
| Suspected cause | Data gap, argmax flicker, lighting, hardware |
| Follow-up | Data batch, aug change, or code fix it motivated |
| Privacy status | Raw / reviewed / cleared |

## Known failure modes on record

These are the real, observed failures that shaped the project — not hypotheticals:

- **Turn-in-shadow observation.** Some tested checkpoints reacted to shadow edges
  like turns, while more center-biased behavior could miss a real turn. The clips
  motivate targeted turn-in-shadow collection; they do not prove a universal cause.
- **Center collapse.** A checkpoint can concentrate predictions near ST and retain
  weak turn recall while its aggregate MAE remains competitive. This is why the
  report includes class-balanced and turn metrics.
- **`v3.1b` orange lamppost.** First hybrid field test drove well at night but
  **failed on an orange lamppost light** — a lighting/color case the training data
  under-covered.
- **Blocky steering (argmax transitions).** An earlier hybrid test showed stepped
  steering as the selected class changed. Runtime EMA smoothing is now implemented;
  that code change does not by itself prove the physical issue is resolved.

## Why keep failures at all

Failure footage bounds claims and connects a code/data change to observed behavior.
Disengagements and LiDAR interventions should retain model, route, conditions, and
operator notes so they can be interpreted rather than presented as isolated clips.

## Status

- Most failure footage is from Series 3 field tests (`v3.1b` onward).
- `v3.3` and `v3.3b` were tested on July 13 and both regressed from their earlier references. The exact failure clips were not indexed in the run record.
- Series 4 has no field footage yet.
- All clips are internal until a privacy pass (faces, plates, house numbers).

## Related pages

- `exhibits/media/video-index.md`
- `exhibits/media/success-clips.md`
- `portfolio-evidence/reader-paths/evidence-map.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
