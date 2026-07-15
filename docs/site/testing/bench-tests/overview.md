# Overview

The bench-tests section documents standalone utilities used on the bench, over SSH, or with the car restrained before a field drive. Hardware and navigation utilities are grouped under matching `camera/`, `controller/`, `display/`, `lidar/`, `navigation/`, `sensors/`, `setup/`, and `steering/` folders inside `code/test_files/`; cross-cutting experiments remain at its root. Experiments stay outside the live control loop so they can be run and reviewed independently.

A bench test exists to answer one question with proof: does this sensor stream real data, does this servo hit the angle I command, does this model turn the wheels the way the picture says it should. Every page here states what is being tested, the exact command, and what counts as pass, warn, or fail. Because these are hardware tests, most of them talk to real GPIO, I2C (PCA9685 at `0x40`), or a UART, so the page also notes which device the command runs on (Pi 5 controller vs. Zero 2 W dashboard) and whether it moves anything.

## What a good bench-test record captures

| Test record field | What I fill in |
|---|---|
| Setup | Device (Pi 5 / Zero 2 W), branch, model version, wiring |
| Procedure | The exact command with its flags, and which state the car must be in (motors off, wheels up, controller connected) |
| Pass / warn / fail | Defined before running, in terms of the values printed |
| Evidence | Command output, a short clip, a CSV row, or a note of the value found |

## Why bench tests matter here

- This is real hardware that moves motors and steering. A bench test isolates one subsystem so a failure has one obvious cause, instead of debugging it live mid-drive.
- Tests make progress measurable: a steering-trim number, a filtered yaw-rate, a LiDAR distance in millimeters, a route distance in meters.
- The debugging discipline for this repo is prove, don't assume. These utilities are how I instrument and observe a value end to end instead of asserting from the armchair.

## Pages in this section

- Steering/servo: `servo.md`, `servo-calibration.md`, `steering-trim-tuner.md`, `model-steering.md`
- Sensors: `gps-compass.md`, `lidar-viewer.md`, `imu-verifier.md`
- Display/telemetry: `dashboard.md`, `camera-preview.md`
- Navigation tooling: `geojson-graph.md`, `a-star-cli.md`

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
