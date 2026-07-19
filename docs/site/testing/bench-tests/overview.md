# Bench Tests Overview

The bench-tests section documents standalone utilities used on the bench, over SSH, or with the car restrained before a field drive. Hardware and navigation utilities are grouped under matching `camera/`, `controller/`, `display/`, `lidar/`, `navigation/`, `sensors/`, `setup/`, and `steering/` folders inside `code/test_files/`; cross-cutting experiments remain at its root. Experiments stay outside the live control loop so they can be run and reviewed independently.

A bench test exists to answer one question with evidence: Does this sensor stream real data? Does this servo reach the commanded angle? Does this model steer in the direction expected from the image? Every page here states what is being tested, the exact command, and what counts as pass, warning, or failure. Because these are hardware tests, many communicate through GPIO, I2C (including the PCA9685 at `0x40`), or a serial port. Each page therefore identifies the computer that runs the command and whether the test can move the steering or motors.

## What a Good Bench-Test Record Captures

| Test record field | What I fill in |
|---|---|
| Setup | Device (Raspberry Pi 5 / Zero 2 W), branch, model version, wiring |
| Procedure | The exact command with its flags, and which state the car must be in (motors off, wheels up, controller connected) |
| Pass / warning / failure | Defined before running in terms of the values printed |
| Evidence | Command output, a short clip, a CSV row, or a note of the value found |

## Why Bench Tests Matter Here

- This is real hardware that moves motors and steering. A bench test isolates one subsystem so a failure has one obvious cause, instead of debugging it live mid-drive.
- Tests make progress measurable: a steering-trim number, a filtered yaw-rate, a LiDAR distance in millimeters, a route distance in meters.
- The debugging rule for this repository is to measure rather than assume. These utilities expose values from input through output so a conclusion can be tied to recorded evidence.

## Utilities in This Section

The checked-in tools are grouped under `code/test_files/steering`, `sensors`, `lidar`, `display`, `camera`, `navigation`, `controller`, `models`, `data`, and `setup`. Use the inventory below rather than relying on an old documentation filename.

## Bench-Test Matrix

| Area | Utility or check | Pass evidence |
|---|---|---|
| Camera | camera preview utility | Correct orientation, color, frame updates, no repeated stalls |
| Model steering | model steering tester / live dashboard | Matching model, finite outputs, expected directional response |
| Servo | servo step/controller utilities | Known commands move predictably with wheels unloaded |
| Steering calibration | trim tuner and stepped-angle test | Recorded center/endpoints and repeatability from both directions |
| LiDAR | viewer and center-AEB tests | Stable packet stream, correct corridor/rungs, expected policy actions |
| GPS/compass | BN880 bench utilities | Valid NMEA fix; compass result labeled bench-only |
| IMU | IMU verifier | Fresh finite yaw-rate stream and safe stale fallback |
| Dashboard | receiver/layout/link tests | Correct pages, colors, `NO LINK`/`STALE`, linked shutdown |
| Navigation | GeoJSON graph and A* CLI | Graph loads, route exists, endpoints/penalties are plausible |

Run hardware-moving tools with motors disabled or wheels clear. Record the exact command and output because filenames and flags can change. The authoritative inventory is [Test Files](../../code-reference/test-files.md).

## Related Pages

- [Field Testing](../field-testing/overview.md)
- [Field Evaluation](../../model-evaluation/field-evaluation/overview.md)
- [Safety Overview](../../safety-case/safety-overview.md)
