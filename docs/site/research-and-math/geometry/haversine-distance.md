# Navigation Geometry and Routing

SidewalkPilot converts a start and destination into an ordered path through a geographic sidewalk graph. The navigation implementation lives in `code/controller/current/rc_car_app/navigation.py`; the graph is `trossachs_nav_graph.json`.

## Distance and Bearing

`haversine(a, b)` computes great-circle distance using an Earth radius of `6,371,000 m`:

```text
x = sin(dlat/2)^2 + cos(lat1) cos(lat2) sin(dlon/2)^2
distance = 2 R asin(sqrt(x))
```

The same meter-valued function supplies graph edge lengths, remaining route distance, nearest-node snapping, the A* heuristic, and navigation radii. The initial bearing from point `a` to `b` is:

```text
x = sin(dlon) cos(lat2)
y = cos(lat1) sin(lat2) - sin(lat1) cos(lat2) cos(dlon)
bearing = (degrees(atan2(x, y)) + 360) % 360
```

This graph-derived bearing is used for route planning. It is not the live BN880 compass heading.

## Turn Angle and Penalty

For three consecutive nodes, the unsigned route bend is:

```text
turn = abs((bearing_out - bearing_in + 540) % 360 - 180)
```

The wrap converts a difference across north, such as `350` to `10` degrees, into a 20-degree turn rather than 340 degrees. A stepwise penalty discourages paths that are difficult for an Ackermann-steering car:

| Turn | Added path cost |
|---|---:|
| Below 25 degrees | 0 |
| 25-45 degrees | 3 |
| 45-90 degrees | 10 |
| 90-135 degrees | 24 |
| 135 degrees or more | 44 |

Left and right bends receive equal cost because the planner uses turn magnitude, not direction.

## A* Search

A* expands the state with the lowest `f = g + h`:

- `g` is accumulated edge distance, edge-kind penalties, and turn penalties;
- `h` is the haversine distance to the goal;
- The state is `(previous_node, current_node)`, allowing the next expansion to price the turn;
- The result is an ordered list of graph node IDs.

Less-preferred edge kinds receive fixed costs: `+220 m` for `crosswalk_transfer`, `+48 m` for `intersection` or `osm_gap`, and `+36 m` for `inferred_crosswalk`. Intermediate house nodes are excluded so a route does not cut through an unrelated driveway.

## Runtime Boundaries

Handoff, resume, and arrival checks use meter-valued radii. Current constants include a `3.0 m` handoff alert, `2.5 m` resume radius, and `3.0 m` arrival radius. GPS noise, malformed graph coordinates, disconnected graph components, and duplicate zero-length edges can still produce bad snapping or no-route results. Navigation therefore remains supervised and crosswalk traversal remains manual.

See [Navigation Overview](../../autonomy-stack/navigation/overview.md) and [Crosswalk Handoff](../../autonomy-stack/navigation/crosswalk-handoff.md).
