# Haversine Distance

The haversine formula gives the great-circle distance between two points on a sphere from their latitude and longitude. SidewalkPilot uses it as the single source of truth for "how far apart are two places" throughout navigation: edge lengths, remaining route distance, A* heuristic, nearest-node snapping, and crosswalk handoff/resume radii are all measured with it.

## How it works

In `navigation.py` (`haversine(a, b)`), with Earth radius `R = 6,371,000 m`:

```python
x = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
d = 2 * R * asin(sqrt(x))
```

- **Input:** two node dicts with `lat` / `lon` in decimal degrees. Both latitudes, and the deltas `dlat` and `dlon`, are converted to radians first.
- **Output:** distance in **meters** along the Earth's surface.

The intermediate `x` is the squared half-chord (the "haversine" of the central angle); `2R·asin(√x)` turns that back into arc length. Using `asin(sqrt(...))` instead of the naive spherical law of cosines keeps the result numerically stable for the very short distances between adjacent sidewalk nodes, where a cosine-based formula loses precision.

### Runtime use

`haversine` lives in `code/controller/current/rc_car_app/navigation.py` and is called all over that file:

- `path_distance` / `segment_distance` sum it over consecutive nodes to get total and per-segment route length in meters.
- `astar` uses `haversine(node, goal)` as its admissible heuristic (straight-line distance never overestimates the real path), which is what makes the A* search both correct and fast.
- `nearest_node`, `nearest_sidewalk_node`, and `closest_path_index` use it to snap the live GPS fix to the closest graph node/route point.
- Handoff and resume logic compares it against fixed radii (`HANDOFF_ALERT_M = 3.0`, `RESUME_RADIUS_M = 2.5`, `ARRIVED_RADIUS_M = 3.0`) to decide when to hand control to manual at a crosswalk and when to resume AI driving.

## Why this choice

- Straight-line meters is exactly what A* needs for an admissible heuristic and what the dashboard needs for "distance remaining." One formula covers all of it, so distance is defined once and consistently.
- Haversine is accurate and cheap over the short hops in the route graph, and it degrades gracefully — no trig blow-ups — at the meter scale where the car actually operates.

## Worked example

Two points 0.0010° apart in latitude at ~55° N, same longitude:

- `dlat = radians(0.0010) ≈ 1.745e-5`, `dlon = 0`
- `x = sin(dlat/2)**2 ≈ (8.727e-6)**2 ≈ 7.62e-11`
- `d = 2 * 6,371,000 * asin(sqrt(7.62e-11)) ≈ 2 * 6,371,000 * 8.727e-6 ≈ 111.2 m`

So 0.001° of latitude is about 111 m, which matches the textbook value of ~111 m per 0.001° of latitude anywhere on Earth.

## What could go wrong

- **Bad coordinates:** `_safe_float` defaults missing/invalid `lat`/`lon` to `0.0`, so a node with no fix would compute a huge (thousands-of-km) distance to the equator/prime-meridian. Graph nodes must carry real coordinates; the live loop only feeds GPS when `fix` is true.
- **Spherical Earth assumption:** haversine treats Earth as a perfect sphere with a fixed radius, so it carries a sub-percent error versus the true ellipsoid. At sidewalk scale (meters) that error is far below GPS noise and irrelevant to routing decisions.
- **Units:** the constant is in meters, so every downstream threshold (`*_M` radii, `ARRIVED_RADIUS_M`) is also in meters. Mixing in a value that was actually degrees would silently break the handoff logic.

## Related pages

- `research-and-math/geometry/bearing.md`
- `research-and-math/geometry/turn-angle.md`
- `autonomy-stack/navigation/overview.md`
