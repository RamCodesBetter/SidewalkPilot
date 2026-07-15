# Compass Heading

How the BN880's onboard magnetometer heading could be used alongside GPS bearing to
know which way the car is actually pointing during navigation.

> **Status: planned / not-yet-wired.** The BN880 board carries a magnetometer
> (a QMC5883L on I2C `0x1E`), and there is a bench test for it at
> `code/test_files/sensors/bn880_test.py`, but the runtime navigation code
> (`navigation.py`) does **not** read the compass today. Route localization and
> orientation currently come from GPS position and the graph, not from a live
> compass heading. This page documents the intended use, marked as future work.

## How it would work

- The magnetometer would give an absolute heading (which way the car's nose points)
  even when the car is stationary — something GPS cannot do, because GPS can only
  infer a bearing from movement between two fixes.
- Runtime already has a graph `bearing()` helper (`navigation.py`) that computes the
  compass bearing from one node to the next along the planned path. A live compass
  heading would be compared against that path bearing to tell whether the car is
  oriented the right way before an AI segment or crosswalk crossing begins.
- A future closed loop could fuse compass heading with the XIAO MG24 IMU's yaw rate
  (the separate yaw-rate steering work) for a more stable orientation estimate than
  either sensor alone.

## Why it matters

- At low speed and at a standstill, GPS-derived bearing is noisy or undefined, so the
  car cannot reliably tell its facing direction from GPS alone. An absolute compass
  heading fills that gap — useful right at a crosswalk handoff, where knowing the car
  is aimed across the road (not along it) matters for a safe manual crossing.

## Current reality

- The compass is characterized only on the bench (`bn880_test.py` reads the QMC5883L
  and prints a heading). It is not fused into `NavigationManager` and does not affect
  any routing, segmenting, or handoff decision. Do not describe compass fusion as a
  proven navigation feature.

## Related pages

- `autonomy-stack/navigation/gps-reader.md`
- `research-and-math/geometry/bearing.md`
- `hardware/gps-compass.md`
