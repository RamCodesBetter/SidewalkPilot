# A*

A* is the route planner for SidewalkPilot. Given a start sidewalk node and a goal
node, it finds the lowest-cost walkable path across the map graph. It is implemented
in `astar()` in `code/controller/current/rc_car_app/navigation.py` and is called once
per route by `NavigationManager.start_route()`.

## How it works

- The search state is a `(prev_node, current_node)` pair, not just the current node.
  Carrying the previous node lets the cost function apply a **turn penalty** based on
  the bearing change at each vertex (see `turn-penalties.md`), which a plain
  node-only A* cannot do.
- The priority queue is a `heapq` of `(priority, cost_so_far, state)`. `priority =
  cost_so_far + haversine(next, goal)`, so the great-circle straight-line distance to
  the goal is the admissible heuristic.
- Neighbors come from a pre-built adjacency map (`build_graph()`), which only includes
  edges that pass `edge_allowed()` — sidewalk-to-sidewalk, valid crosswalk/helper
  edges, and house-access links. Edge costs come from `edge_cost()`, which adds a
  distance surcharge to expensive edge kinds (e.g. `crosswalk_transfer` +220 m,
  `intersection`/`osm_gap` +48 m, `inferred_crosswalk` +36 m).
- **House nodes are blocked mid-route:** any neighbor whose `type == "house"` is
  skipped unless it is the start or goal. This forces the path to travel on sidewalks
  and only touch a house at its two endpoints, never as a shortcut through someone's
  yard.
- On reaching the goal, `reconstruct_path()` walks the `came_from` map back to the
  start state and returns the node-ID list; `path_distance()` reports the true
  summed haversine length (distinct from the search cost, which includes penalties).
- If either endpoint is missing or no path exists, it returns `([], inf)` and the
  route entry shows an error rather than starting a bad route.

## Why this choice

- A* with a haversine heuristic is the standard, explainable shortest-path method for
  a geographic graph — it is fast on this `6183`-node map and easy to reason about.
- Keeping the `(prev, current)` state is the key design decision: the router's job is
  not just "shortest," it is "shortest that a car can actually drive," and that means
  penalizing sharp turns at intersections. That only works if the search knows where
  it came from.
- Reported distance is kept separate from optimized cost on purpose, so the ETA and
  the on-screen remaining-distance reflect real meters, not penalty-inflated cost.

## Key constants

- Heuristic: `haversine(node, goal)` (meters, admissible).
- Cost surcharges live in `edge_cost()`; turn surcharges in `turn_penalty()`.
- House-node passthrough block lives inside the neighbor loop of `astar()`.

## Related pages

- `autonomy-stack/navigation/turn-penalties.md`
- `autonomy-stack/navigation/graph-format.md`
- `autonomy-stack/navigation/overview.md`
