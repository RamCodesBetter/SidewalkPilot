# Overview

This section is the honest half of SidewalkPilot: the failure log. Every page under `testing/failures` records a place where the car did the wrong thing — misread a driveway as the sidewalk, chased a hard shadow, drifted toward the road, dropped the LiDAR link — and pairs the symptom with a suspected cause and the next dataset or code change. The clean demos live elsewhere; this is where the project's real learning is captured.

## Why a failure log exists

I keep these notes so each change can be tied to a specific failure. A lower MAE does not establish better driving on a straight-heavy set, so the failure pages record what happened on the sidewalk: corridor holding, turn completion, braking response, and operator takeover. Those observations complement the offline metrics rather than replacing them with another single score.

## How a failure page is structured

Each page tries to answer four questions in order:

- **What was being tested** — the route or bench setup, the model version, and the branch/hardware in play.
- **What went wrong** — the observed symptom, described concretely (which direction it drifted, how far, under what light).
- **Suspected cause** — a hypothesis tied to code or data, never an armchair assertion. The project rule is prove-don't-guess: grep the constant across every layer, read the whole code path, instrument the wire before concluding.
- **Next change** — the dataset bucket to collect, the constant to tune, or the code path to fix, marked clearly as done vs. planned.

## Test record fields

| Test record field | What it should contain |
|---|---|
| Setup | Hardware (Raspberry Pi 5 controller, Zero 2 W dashboard, LiDAR/GPS/IMU as relevant), branch, model version, dataset tag |
| Procedure | Exact command (run `car`, then select `<ver>` on the dashboard model page) or the field route walked |
| Pass / warn / fail | Defined *before* the run, not after |
| Evidence | Runtime CSV log, video clip, field photos, manual-takeover count |

## Current failure pages

- **Shadow failures** — the car chases hard-edged shadows across the sidewalk as if they were the path edge. The core turn-vs-shadow tradeoff.
- **Evening failures** — low-light and point-light-source (orange lamppost) failures, including the v3.1b field note.
- **Harsh sidewalk** — broken, textured, or high-contrast concrete that breaks the corridor-edge assumptions.
- **Driveway confusion** — driveway cuts read as the sidewalk continuing, pulling the car toward a drive.
- **Road entry risk** — the highest-consequence class: the car heading toward a road/crosswalk boundary instead of stopping for the manual handoff.
- **LiDAR disconnects** — the AEB sensor dropping its USB link mid-run and how the runtime is expected to tolerate it.

## Consolidated Failure Record

| Failure class | Observed lesson | Current response |
|---|---|---|
| Hard shadows | A diagonal dark boundary can resemble a sidewalk edge | Targeted collection/augmentation, class-aware evaluation, v3.4 field baseline |
| Evening/point lighting | Daylight success does not transfer automatically | Night remains outside ordinary claims; collect and test separately |
| Harsh concrete | Texture and contrast can overwhelm corridor cues | Add representative surfaces and preserve failure clips |
| Driveway confusion | A driveway can look like continuing pavement | Treat as a model/navigation failure; supervise near road access |
| Road approach | LiDAR cannot identify pavement ownership | Manual crosswalk/road handoff and conservative supervised routes |
| LiDAR disconnect | A USB serial device can disappear mid-run | Background reconnect; loss currently removes intervention rather than forcing a stop |

The most important field comparison found v3.3/v3.3b worse than earlier baselines under the tested conditions, while v3.4 handled all shadow cases presented and became the baseline. This remains a bounded qualitative record because complete route/clip/takeover evidence was not preserved.

## Related pages

- [Field Testing](../field-testing/overview.md)
- [Field Evaluation](../../model-evaluation/field-evaluation/overview.md)
- [Safety Overview](../../safety-case/safety-overview.md)
