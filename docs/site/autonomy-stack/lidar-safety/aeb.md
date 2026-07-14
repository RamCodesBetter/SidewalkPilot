# Automatic Emergency Braking

The RSB controller button toggles LiDAR AEB. The toggle has the same meaning in manual and autonomous driving:

| AEB state | Center slowdown | Center emergency stop | LiDAR steering |
|---|---|---|---|
| ON | Enabled | Enabled | Never |
| OFF | Disabled | Disabled | Never |

This fixes the previous split behavior where the final brake respected the toggle but an earlier autonomous `SWR/CRP` path could still alter control.

## Runtime Path

`update_gpio()` calls:

```python
lidar_avoidance.evaluate(lidar_scan, enabled=metrics.aeb_enabled)
```

once per control loop. The resulting throttle cap and stop flag are shared by manual and autonomous paths. The same result populates dashboard occupancy/action fields, preventing control and display logic from using different interpretations of the scan.

In Drive gear:

- manual throttle or cruise control is capped by the policy throttle;
- autonomous throttle is capped before motor output;
- an emergency result activates the existing AT8236 hard-brake output; and
- Reverse is not subject to forward AEB.

## Bench Test

Keep the wheels lifted or mechanically unable to move during the first test.

1. Start the controller and open the LiDAR dashboard page.
2. Confirm only two blue center guides and one `C` glyph are shown.
3. Switch AEB OFF. Move an object through every rung in the center. Confirm no control intervention.
4. Switch AEB ON. Put the object outside either center guide. Confirm no intervention.
5. Move it between the center guides from beyond 1.65 m toward 1.25 m. Confirm throttle decreases smoothly.
6. Hold it between 1.25 m and 1.05 m. Confirm the dashboard target is 60% reference (82% physical PWM).
7. Move it to 1.05 m or closer. Confirm hard brake and `C`/brake indication.
8. Repeat with autonomous mode enabled and verify model steering remains unchanged by LiDAR.

Abort on any side-object brake, any LiDAR steering change, failure to stop at the emergency boundary, stale scan, or unexpected motor direction.

## Automated Regression

`code/test_files/test_lidar_center_aeb.py` proves the threshold behavior, side-point exclusion, AEB-disabled behavior, and the invariant that every result has `steer=None`.
