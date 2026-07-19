# Success Clips

This page collects the driving videos where SidewalkPilot did what it was supposed
to: followed the sidewalk corridor, held a sensible steering line, and let the
LiDAR safety layer arbitrate without a human taking over.

## What each clip proves

A success clip is only useful if it names the exact conditions, because "it drove"
is not a claim you can reproduce. Every entry should carry the model version, the
route, the date, and the lighting/weather. That way a viewer can line the footage
up against the same model's confusion matrix and see that field behavior matches
the offline evaluation.

| Field | What to record |
|---|---|
| Clip | File name or link |
| Model version | e.g. Series 3 `v3.1b` (runs on Jetson Orin Nano), or a Series 1/2 checkpoint on the Raspberry Pi 5 |
| Route | Named sidewalk / test loop |
| Condition | Daylight, dusk, night, dry, wet, shadowed |
| Claim supported | What the run demonstrates |
| Privacy status | Raw / reviewed / cleared |

## What "success" means here

Success is judged against the same standard used to judge the models: not lowest
MAE, but whether the car took the correct **bucket** of action at the right moment.
The nine steering classes are HL, L, L+, SL, ST, SR, R, R+, HR, and a good run is
one where the car picks the right bucket into and out of turns instead of collapsing
to straight (ST). A clip that shows a clean mid-turn commit is stronger evidence
than a long straight-line cruise, because straight is the easy, over-represented
case in the data.

Representative things a success clip should show:

- Following a curving corridor and correctly leaving ST for L/L+/R/R+ into the turn.
- LiDAR AEB slowing or stopping for a real obstacle (the safety layer arbitrating
  over the model, exactly as designed), then resuming.
- A GPS/nav handoff — an A* route segment switching between AI and manual control —
  completing without the operator grabbing the Xbox override.

## Status and honesty note

- First hybrid Series 3 field footage is `v3.1b`: it **drove well at night** in
  testing, which is a genuine success worth showing.
- v3.4 is the current field selection after the July 13 shadow/turn comparison. That result should not receive a public clip claim until the exact footage is identified and privacy-reviewed.
- Series 4 has no success clip or field verdict yet.
- Every raw clip is internal until a privacy pass (faces, plates, house numbers) is
  done. Do not publish externally before that.

## Related pages

- `exhibits/media/video-index.md`
- `exhibits/media/failure-clips.md`
- `portfolio-evidence/claims-and-proof/reproducibility-claim.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
