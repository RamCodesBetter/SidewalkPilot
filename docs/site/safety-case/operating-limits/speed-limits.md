# Speed Limits

SidewalkPilot does not currently enforce a closed-loop autonomous top-speed limit in miles per hour.

## What the Code Enforces

- Motor commands are clamped to the `0..1` physical PWM range.
- Manual cruise control uses hall-sensor feedback and a PID target selected by the operator.
- With AEB enabled in forward drive, the center-corridor LiDAR policy caps throttle according to clearance.
- At 1.65 m or farther, the LiDAR governor allows the requested command up to full throttle.
- Between 1.65 m and 1.25 m, it reduces the cap from 100% to 60% reference throttle.
- From 1.25 m to 1.05 m, it holds that cap.
- At or inside 1.05 m, it requests zero throttle and full braking.

The reference range maps the useful moving range onto physical PWM. On this car, 0% reference is the measured 55% physical dead-zone boundary, and 60% reference maps to 82% physical PWM. Saved training labels remain on the absolute physical `0..100%` scale.

## Important Limit

`MAX_AUTONOMOUS_SPEED_MPH = 3.2` is declared in `config.py` but is not used as a final speed governor. It must not be presented as an enforced 3.2 mph limit. A future hard speed cap would need to use measured hall-sensor speed in the final throttle path and then be tested under the real payload and surface conditions.

Field operation therefore stays supervised and conservative. Stopping-distance tests, not a config constant or inference rate, define a defensible operating speed.
