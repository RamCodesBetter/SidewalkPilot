# Chassis

The rolling platform is a Yahboom Ackermann 520M chassis. It provides the frame,
the four drive wheels, and the Ackermann steering linkage that the steering servo
turns. Everything else on the car - the compute boards, sensors, batteries, and
dashboard - is mounted on this chassis.

## Parts (Amazon)

- [Yahboom Ackermann 520M Chassis](https://www.amazon.com/dp/B0BR9PGZWN?th=1&linkCode=sl1&tag=ramcodes-20&linkId=2d71e1269d116bb03b4dca16401e9028&language=en_US&ref_=as_li_ss_tl) — $99.99

## How it works

- The chassis uses **Ackermann steering**: the front wheels pivot on a linkage driven by a
  single steering servo, while the drive comes from the wheel motors through the AT8236
  H-bridge. This matches how a real car steers, not skid/tank steering.
- Logical steering commands (`0` = left, `90` = center, `180` = right) are turned into
  servo angles in `hardware.py`; the linkage geometry translates that into the actual
  wheel angle.
- The chassis is the physical reference frame for steering tests. Bench work observed
  direction-dependent steering return and field testing observed left drift. Those observations
  can have multiple contributors, including linkage geometry, load, surface, trim, and
  motor balance; the current motor scales remain neutral at `1.0` on both sides.

## Why this choice

- An Ackermann chassis produces car-like turning geometry, which keeps the steering-model
  labels meaningful and matches the target domain (sidewalks/roads) far better than a
  differential-drive robot base.
- The 520M is a well-supported, off-the-shelf platform, so effort could go into the
  autonomy stack instead of fabricating a frame - the same reuse-what-exists reasoning
  behind the rest of the build.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
