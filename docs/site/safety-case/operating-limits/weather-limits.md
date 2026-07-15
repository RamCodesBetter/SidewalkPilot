# Weather Limits

SidewalkPilot is a dry-weather research platform. Its electronics are not
weather-sealed, and its camera and LiDAR behavior has not been validated in
precipitation, fog, snow, or ice.

## Hardware exposure

The open chassis carries exposed compute boards, motor electronics, sensors,
connectors, and batteries. Rain, standing water, and spray create risks of
shorting, corrosion, loss of control, and battery damage. This hardware limit is
enough to exclude wet-weather operation regardless of model performance.

## Sensing limits

- **Camera steering:** rain on the lens, reflections, and low contrast can move
  the image outside the training distribution. The current neural response does
  not provide a calibrated measure of scene quality: an accepted fresh result is
  assigned confidence `1.0`. The low-confidence stop therefore catches missing
  or stale inference, not every dark, wet, or unfamiliar image.
- **LiDAR AEB:** precipitation or fog may produce spurious or missing returns.
  This behavior has not been characterized on the FHL-LD19. The runtime retries
  a disconnected reader, but an empty or sparse scan is not proof that the path
  is clear.

## Operating envelope

| Condition | Status | Evidence or reason |
|---|---|---|
| Dry, clear | Tested with direct operator supervision | Current field-test domain |
| Dry, overcast | Limited field domain | Lower contrast may still expose model failures |
| Light drizzle or damp surface | Do not run | Exposed hardware and unvalidated sensing |
| Rain or standing water | Do not run | Water-ingress and battery risk |
| Snow or ice | Do not run | Traction and sensing are unvalidated |
| Fog or heavy haze | Do not run | Camera and LiDAR behavior are unvalidated |
| High wind | Do not run autonomously | Crosswind effects have not been measured |

## Controls

There is no weather sensor or automatic weather abort. The operator must check
conditions before power-up, supervise the entire run, and stop the car if the
environment changes. LiDAR AEB remains a distance-based backstop when enabled;
it is not a weather-safety guarantee.

No claim is made that SidewalkPilot is safe in weather beyond the dry conditions
actually tested. Weatherproofing and adverse-weather validation are not current
capabilities.

## Related pages

- [Lighting Limits](lighting-limits.md)
- [Preflight Checklist](../../testing/field-testing/preflight-checklist.md)
- [Where It Cannot Run](where-it-cannot-run.md)
