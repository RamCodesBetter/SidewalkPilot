# GPS Loss

GPS drives navigation (which sidewalk segment the car is on, when to hand off at a
crosswalk), not steering. Losing GPS degrades routing, it does not by itself make the
car unsafe, because steering and braking do not depend on a fix. This page documents
that separation.

## Hazard

The BN880 GPS (`/dev/ttyAMA0`, 9600 baud) can lose its fix (indoors, tree cover, cold
start, antenna knock). If navigation kept advancing the route on a lost or drifting
fix, it could mis-time a crosswalk handoff or think it has arrived when it has not.

## Detection

`navigation.py` reads NMEA and tracks fix state; the runtime seeds navigation with
`{"fix": False, "sats": 0}` at startup and updates it each cycle. Navigation decisions
key off whether a valid fix is present and how many satellites are reported, so a lost
fix is visible to the route manager and on the dashboard rather than silently assumed.

## Response

- **Steering and braking are unaffected.** They come from the camera model, LiDAR/AEB,
  and the operator, none of which read GPS. A GPS loss never removes the obstacle or
  override safety layers.
- **Navigation pauses/does not advance.** Without a valid fix, segment progress and
  the crosswalk handoff alert should not advance on garbage coordinates; the route
  waits for the fix to return (resume within `RESUME_RADIUS_M = 2.5 m`).
- **Operator fallback.** The route can always be cancelled by manual input, and the
  car can be driven manually with no GPS at all.

## Stop condition and who triggers it

GPS loss is not a braking condition. It suspends navigation guidance. The car keeps
whatever drive mode it is in (manual or camera-model autonomous), with LiDAR/AEB and
manual override still active.

## Evidence

- Code: `navigation.py` — `GPS_PORT`/`GPS_BAUD`, fix/sats handling, `ARRIVED_RADIUS_M`,
  `HANDOFF_ALERT_M`, `RESUME_RADIUS_M`.
- Runtime: `runtime.py` — `navigation.update({"fix": False, "sats": 0}, 0.0, 0.0)`
  seed and per-cycle updates; navigation cancel-on-manual-input.
- Field evidence: GPS-loss route behavior is **planned / not-yet-logged** as a labeled
  test; note that `/dev/ttyAMA0` must be freed from the serial console for GPS to open.

## Series 3 note

Series 3 does not change GPS handling; navigation and GPS stay on the Raspberry Pi 5 and are
independent of the steering model host.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
