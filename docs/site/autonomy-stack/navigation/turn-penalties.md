# Turn Penalties

Turn penalties bias the A* router toward routes a car can actually drive comfortably —
they add extra cost to sharp changes of direction so the planner prefers straighter
paths and avoids needless zig-zags. They are computed by `turn_amount()` and
`turn_penalty()` in `code/controller/current/rc_car_app/navigation.py`.

## How it works

- Because the A* search state is `(prev_node, current_node)` (see `a-star.md`), the
  search always knows the heading it arrived on. `turn_amount()` computes the incoming
  bearing (`prev → current`) and the outgoing bearing (`current → next`) using the
  graph `bearing()` helper, then returns the absolute turn angle in degrees, folded to
  the `0..180` range.
- `turn_penalty()` converts that angle into an extra cost (in "meters" added to the
  edge cost), stepped by severity:

  | Turn angle | Added cost |
  |---|---:|
  | < 25° | 0.0 |
  | 25°–45° | 3.0 |
  | 45°–90° | 10.0 |
  | 90°–135° | 24.0 |
  | ≥ 135° | 44.0 |

- The penalty is added inside the A* neighbor expansion:
  `new_cost = cost_so_far + step_cost + turn_penalty(...)`. The first move of a route
  (`prev_id is None`) gets no penalty.

## Why this choice

- Shortest-by-distance is not the same as best-to-drive. Without a turn penalty, A*
  will happily route through a tangle of short connector edges that add up to fewer
  meters but require the car to keep turning. The stepped penalty makes the planner
  prefer a slightly longer, straighter path.
- The penalty affects only the **optimization cost**, not the reported route distance
  — `path_distance()` still reports true meters, so ETA and remaining-distance stay
  honest even though the router internally "paid extra" to avoid sharp corners.
- A near-arbitrary large jump at ≥135° (essentially a U-turn) strongly discourages
  doubling back, which is almost never what you want on a sidewalk route.

## Key constants

- Thresholds and costs live entirely in `turn_penalty()`; the angle math is in
  `turn_amount()` on top of `bearing()`.

## Related pages

- `autonomy-stack/navigation/a-star.md`
- `research-and-math/geometry/bearing.md`
- `autonomy-stack/navigation/overview.md`
