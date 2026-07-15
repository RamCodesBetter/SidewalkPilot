# Bearing

Bearing is the compass direction, in degrees clockwise from true north, that points from one geographic coordinate toward another. SidewalkPilot's A* route planner uses it to reason about how sharply the route changes direction at each graph node, so the planner can prefer straighter walking routes over ones that zig-zag.

## How it works

The bearing (also called forward azimuth) from point `a` to point `b` is computed with the standard great-circle initial-bearing formula. In `navigation.py` (`bearing(a, b)`):

```python
x = sin(dlon) * cos(lat2)
y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
theta = (degrees(atan2(x, y)) + 360.0) % 360.0
```

- **Input:** two node dicts, each with `lat` / `lon` in decimal degrees. Latitudes and the longitude difference `dlon` are converted to radians before the trig.
- **Output:** a bearing in `[0, 360)` degrees. `0` = north, `90` = east, `180` = south, `270` = west. The `+ 360 % 360` step folds the raw `atan2` range of `(-180, 180]` into a clean `0..360` compass value.

Why `atan2(x, y)` and not simple slope: over the curved Earth a fixed longitude step covers less east-west ground as you move away from the equator, so the east component is weighted by `cos(lat2)`. Using `atan2` also keeps the result correct and continuous through all four quadrants without divide-by-zero.

### Runtime use

`bearing` is a helper inside `code/controller/current/rc_car_app/navigation.py`. Its consumer is `turn_amount(prev, current, next)`, which takes the bearing of the incoming edge and the bearing of the outgoing edge and measures how many degrees the route turns at the middle node (see the Turn Angle page). That turn amount then drives `turn_penalty`, an extra cost added inside `astar` so the planner favors gently-curving sidewalk routes. Bearing is a pure geometric helper here; it is not currently wired to the BN880 compass or the live driving heading.

## Why this choice

- The great-circle initial-bearing formula is the standard, well-understood way to get direction between two lat/lon points, and it stays accurate over the short (tens-to-hundreds-of-meters) sidewalk hops in the Trossachs route graph.
- Computing bearing from the graph coordinates keeps the deterministic navigation math fully inspectable and independent of any sensor: the same route graph always yields the same turn costs.

## Worked example

From node `a = (55.0000, -4.0000)` to `b = (55.0000, -3.9990)` (due east, same latitude):

- `dlon = radians(0.0010) = 1.745e-5`
- `x = sin(dlon) * cos(lat2) ≈ 1.745e-5 * 0.5736 ≈ 1.001e-5`
- `y = cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon) ≈ 0` (the two terms nearly cancel for a tiny east step at fixed latitude)
- `theta = atan2(x, y) ≈ 90°`

So a small step due east returns a bearing of about `90°`, as expected.

## What could go wrong

- **Missing or malformed coordinates:** `_safe_float` defaults a bad `lat`/`lon` to `0.0`, so a node with no coordinates would silently compute a bearing toward the equator/prime-meridian. Route graphs should always carry real coordinates.
- **Antimeridian / poles:** the formula is correct across the ±180° longitude seam because it works on the `dlon` difference, but bearing is undefined exactly at the poles. The Trossachs test area is far from both, so this is not a practical risk.
- **Initial vs. constant bearing:** this returns the *initial* bearing of the great-circle path, which drifts slightly over a long arc. Over sidewalk-length edges the drift is negligible.

## Related pages

- `research-and-math/geometry/turn-angle.md`
- `research-and-math/geometry/haversine-distance.md`
- `autonomy-stack/navigation/overview.md`
