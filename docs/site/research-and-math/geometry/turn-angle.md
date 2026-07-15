# Turn Angle

The turn angle is how many degrees the walking route changes direction at a graph node — the difference between the bearing of the edge arriving at the node and the bearing of the edge leaving it. SidewalkPilot's A* planner turns this angle into an extra cost so it prefers straighter, more natural sidewalk routes over ones that make sharp or unnecessary turns.

## How it works

In `navigation.py`, `turn_amount(prev_node, current_node, next_node)`:

```python
before = bearing(prev_node, current_node)   # incoming edge direction
after  = bearing(current_node, next_node)   # outgoing edge direction
return abs((after - before + 540.0) % 360.0 - 180.0)
```

- **Input:** three consecutive route nodes (previous, current, next), each with `lat` / `lon`.
- **Output:** the unsigned turn magnitude in degrees, in `[0, 180]`. `0` = keep going perfectly straight; `180` = a full U-turn back the way you came.

The `(diff + 540) % 360 - 180` trick is the key. Simply subtracting two compass bearings can give a value anywhere in `(-360, 360)` and wraps badly across north (e.g. 350° vs 10° should be a 20° turn, not 340°). Adding 540, taking mod 360, then subtracting 180 folds any raw difference into the range `[-180, 180]`; `abs(...)` then collapses left and right turns of equal sharpness to the same magnitude, since the planner only cares *how sharp*, not which way.

### Turn penalty (runtime use)

`turn_amount` feeds `turn_penalty(nodes, prev_id, current_id, next_id)`, a stepwise cost added to the edge cost inside `astar`:

| Turn magnitude | Added cost |
|---|---|
| `< 25°` | `0.0` (treated as going straight) |
| `25°–45°` | `3.0` |
| `45°–90°` | `10.0` |
| `90°–135°` | `24.0` |
| `≥ 135°` | `44.0` |

If there is no previous node (the route's first step) the penalty is `0.0`, since there is no incoming direction to turn from. These penalties are in the same abstract cost units as `edge_cost` (roughly meters plus per-kind surcharges), so a sharp turn is worth avoiding as long as the detour it saves is not too long. All of this lives in `code/controller/current/rc_car_app/navigation.py`; the cost is applied in `astar` via `cost_so_far[state] + step_cost + turn_penalty(...)`.

## Why this choice

- Penalizing turns is what makes A* pick the route a person would actually walk instead of a jagged path that happens to be a few meters shorter. The near-zero deadband under 25° keeps small graph-geometry wobble from being charged as a "turn."
- The stepwise ramp is cheap, easy to read, and easy to tune. It sharply discourages 90°+ turns and U-turns while barely touching gentle course corrections.

## Worked example

Route heading due east, then turning to head due north:

- Incoming bearing `before ≈ 90°`, outgoing bearing `after ≈ 0°` (north)
- `diff = 0 - 90 = -90`
- `(-90 + 540) % 360 - 180 = 450 % 360 - 180 = 90 - 180 = -90`
- `abs(-90) = 90°` turn

A 90° turn lands right at the `90` boundary, so `turn_penalty` charges `24.0` (the `< 135` bucket). A gentle 20° course correction returns `0.0`.

## What could go wrong

- **Wrap-around bugs if the fold is removed:** without the `+540 % 360 -180` normalization, a turn across north (e.g. 350° to 10°) would be mis-measured as ~340°, wrongly flagging a straight path as a U-turn and distorting the route.
- **Degenerate/duplicate nodes:** if `prev`, `current`, and `next` are the same or nearly coincident points, the bearings are ill-defined and the turn angle becomes noisy. The route graph should not contain zero-length edges.
- **Sign is discarded:** because the result is `abs`, left and right turns cost the same. That is intended for planning, but this function alone cannot tell you turn *direction* — that would need the signed value before `abs`.

## Related pages

- `research-and-math/geometry/bearing.md`
- `research-and-math/geometry/haversine-distance.md`
- `autonomy-stack/navigation/overview.md`
