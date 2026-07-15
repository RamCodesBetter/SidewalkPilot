# Battery Check

Battery Check is the power runbook run before every field test. SidewalkPilot has two power domains: a 3S LiPo drives the motors through the Yahboom AT8236 H-bridge, and a separate supply powers the Raspberry Pi 5, camera, and sensors. A sagging pack shows up as weak or asymmetric drive thrust and can be mistaken for a steering or model problem, so this check comes first. Follow it in order; each step ends with a measured value or a pass/fail.

## Preconditions

- A charged, undamaged 3S LiPo (no puffing, no nicked leads).
- A multimeter or LiPo cell checker on hand.
- The car powered off before any pack is connected or disconnected.

## Steps

1. Inspect the 3S LiPo physically: no swelling, no exposed strands, connectors intact. Fail here means do not use the pack.
2. Measure total pack voltage and per-cell balance. A healthy 3S rests near 12.6 V full and should not be run down near 3.0 V/cell. Evidence: recorded pack voltage and per-cell spread.
3. Confirm the electronics supply (Raspberry Pi 5 + camera + sensors) is separate from the motor pack and adequately charged. The Raspberry Pi 5 browns out under camera and inference load if the supply is weak.
4. Power the car on and confirm a clean boot with no undervoltage warnings. On the Raspberry Pi 5, CPU temperature is read from `vcgencmd measure_temp` and surfaced in the CSV log (`CPU Temp (C)`) and on the dashboard; a throttled Raspberry Pi 5 is often a power symptom.
5. Baseline the drive channel: with the car safely lifted (wheels off the ground) and in gear D, give a small throttle and confirm both drive channels respond. The runtime commands the AT8236 as right-forward on GPIO19 + left-backward on GPIO25 for forward motion (`update_gpio` in `rc_car_app/runtime.py`); both wheels should spin.
6. Watch for pull under centered steering. Record surface, payload, battery, physical wheel center, approach direction, and throttle before assigning a cause. Motor scales, servo mapping, and IMU correction are separate controls; both motor scales are `1.0` today.
7. Confirm the dashboard shows a live speed once the hall sensor turns (GPIO24, `PULSES_PER_REVOLUTION = 455`, `WHEEL_DIAMETER_CM = 7.0`). No pulses means no speed reading and cruise control will refuse to engage.

## Stop condition

Abort the run if the LiPo is puffed or below a safe field voltage, if per-cell balance is far off, if the Raspberry Pi 5 reports undervoltage/throttling, or if one drive channel does not respond. A weak pack invalidates any steering or model conclusions drawn from the run.

## Evidence

- Pack voltage and per-cell readings
- Boot log free of undervoltage warnings
- Note of any centered-steering pull and the measured PWM-scale values in use

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
