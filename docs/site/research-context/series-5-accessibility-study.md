# Series 5 Accessibility Study Plan

Last revised: September 12, 2026.

This AI-assisted documentation summarizes the student's current planning decisions. It
is not the student's official research-plan submission, an approval to test, or a report
of completed Series 5 work. Existing Series 1-4 results remain separate.

## Scope

The proposed study compares clear sidewalk width, passing-space width and length,
passing-space intervals, and running and cross slopes against physical measurements
from a laser measuring tool and digital inclinometer. It also compares person-hours
and recurring cost per surveyed mile with a one-person manual field survey.

## Model Preparation

- Generate segmentation reference masks for the existing Series 3/4 images using
  Grounded SAM 2. Preserve the source images and mask provenance.
- Review 200 masks and correct identified errors. At least 80% correct (160 of 200)
  does not trigger a dataset-wide relabel. Otherwise check 200 additional masks.
  Fewer than 75% correct (fewer than 150 of the additional 200) triggers relabeling
  with Grounded SAM 2. The denominator for the second threshold is the additional
  sample, not all 400 images; review fractions describe labels before correction.
- Establish an 80/10/10 training/validation/test split before training. Keep adjacent
  or near-duplicate images in one partition, rather than exposing almost-identical
  frames during both training and testing. Different examples of the same class may
  still occur in all three partitions.
- Train an image-to-semantic-mask model and evaluate its predictions against reference
  masks using IoU, precision, recall, and F1. Record the references' review status.

The two sample thresholds are student-selected review criteria, not measured model
accuracy. The second threshold is less strict than the first. Sample selection, the
definition of a correctly labeled mask, and review after relabeling remain to be
specified before execution. Generated references are not automatically verified ground
truth, and a passing sample does not prove that every remaining label is correct.

## Planned Control and Measurements

The selected model will run on the Jetson Orin Nano. Downstream geometry and path-planning
code will feed steering and throttle control on the Raspberry Pi 5. The segmentation
model does not directly output those commands, and this plan adds no normal braking
output. Existing LiDAR AEB, manual takeover, and failure-stop behavior remain separate.

Accessibility data will be collected during each survey drive:

| Measurement | Planned inputs and calculation |
|---|---|
| Clear width and passing-space dimensions | Mask boundaries projected through calibrated camera geometry; along-path distance for passing-space length |
| Running and cross slope | Calibrated orientation estimated from timestamped IMU accelerometer and gyroscope readings received over USB |
| Passing-space intervals | Accumulated Hall-effect encoder pulse count multiplied by calibrated distance per pulse |

Raw IMU readings are not themselves slopes. Encoder pulses per second give a pulse
rate; accumulated pulse count gives distance after calibration. Measurements, timestamps,
route distance, and validity will be retained in per-run CSV logs. Manual measurements
use a recording sheet and spreadsheet, with stopwatch records retained separately.
See the [hardware overview](../hardware/build-overview.md) and
[project BOM](https://1drv.ms/x/c/9685d41907cf4e28/IQAZPTqPm5FDRLypIrzf-Jv5AapVDVfyFpqjfn2W666oeXk?e=3MadEB)
for materials; those references do not establish that planned measurement code is ready.

## Final Comparison Trials

| Method | Final surveys | Planned distance per survey |
|---|---|---|
| SidewalkPilot | Three complete runs | 1.06 sidewalk miles |
| Manual field survey | One complete run | Same 1.06-mile route and direction |

Offline evaluation, stationary control/safety checks, and low-speed supervised navigation
tests precede the final comparison. Development runs have no fixed count and are not
included as final trials. Keep the final model, hardware, and calibration fixed across
the three SidewalkPilot runs. Record actual surveyed sidewalk distance and route changes.

The manual survey records applicable features at approximately 10-foot stations and at
passing spaces. Match each SidewalkPilot run to the same manual reference locations.
Record temporary changes rather than treating a changed obstruction as measurement
error. Three repeated passes over one route are not three independent environments.

The operator remains with the controller in hand. Existing logging records takeover
triggers, not automatically the underlying reason; the reason is determined during
review. Approximately two seconds of preceding camera footage can be retained when
enough footage is available, subject to verification in the final runtime configuration.
Required safety and approval steps still apply before field testing.

## Analysis and Limits

- Calculate MAE and RMSE separately for each physical measurement and each SidewalkPilot
  run. Report per-run results and the mean and spread across the three runs, along with
  missing measurements and coverage. Segmentation IoU/F1 are separate metrics.
- Include preparation, surveying or active safety supervision, interruptions, road
  crossings, data entry, and final checking in person-hours. Normalize each run by its
  actual surveyed sidewalk miles. Compare the mean of the three SidewalkPilot per-mile
  rates with the single manual survey's rate, not three runs' combined effort with one.
- Report recurring cost per mile per run and the SidewalkPilot mean. Keep upfront
  equipment separate; reusing the vehicle does not triple its purchase cost. Disclose
  development, labeling, and training costs separately from recurring deployment costs.
- Compare observed results with the hypothesis and estimate break-even distance from
  the cost model. Existing per-mile theoretical predictions are unchanged by trial count
  and must not be described as experimental findings.

One manual survey cannot establish between-survey manual labor/cost variability.
Station-level repeatability checks are not repeated full manual surveys. Three
SidewalkPilot runs on one route give limited repeatability evidence, not broad evidence
of performance on other routes. Accessibility screening is not compliance certification.
