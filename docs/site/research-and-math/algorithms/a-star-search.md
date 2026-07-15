# A* Search

A* search is the graph pathfinder that turns a start and destination into an ordered list of sidewalk nodes for SidewalkPilot to follow. It runs on the Raspberry Pi 5 controller inside `code/controller/current/rc_car_app/navigation.py` (the `astar` function), over the Trossachs route graph stored in `code/controller/current/rc_car_app/trossachs_nav_graph.json`.

## How it works

A* is best-first search that expands the state minimizing `f = g + h`, where `g` is the accumulated route cost and `h` estimates remaining cost. Under the usual conditions used here (nonnegative costs, an admissible heuristic, and the implementation's state bookkeeping), A* returns a minimum-cost path for the defined graph/cost function. The heuristic can reduce explored states, but the amount depends on the graph.

In this project:

- **Nodes / edges.** Sidewalk, crosswalk, intersection, and house-access points are graph nodes with `lat`/`lon`. `build_graph` walks the edge list, keeps only edges that `edge_allowed` accepts (for example a `sidewalk` edge must join two sidewalk-type nodes), and stores each as a bidirectional neighbor with a scalar cost.
- **Edge cost `g`.** `edge_cost` starts from the edge's stored metric distance and adds fixed penalties for less-preferred edge kinds: `+220 m` for a `crosswalk_transfer`, `+48 m` for an `intersection` or `osm_gap`, `+36 m` for an `inferred_crosswalk`. This biases routes toward continuous sidewalks and away from unnecessary road crossings without ever making the search inadmissible for distance.
- **Heuristic `h`.** The straight-line great-circle distance to the goal, computed by `haversine(nodes[nxt], nodes[goal])` on a 6,371,000 m Earth radius. For graph edges whose stored distance is at least their endpoint straight-line distance, with only nonnegative added penalties, this heuristic does not overestimate the remaining defined cost.
- **State = (previous node, current node).** The search state is a `(prev_id, current)` tuple rather than just the current node. This is what lets the cost function charge a `turn_penalty` for the bend `prev -> current -> next` (see the Turn Penalty State page). The priority queue is Python's `heapq`; each pop takes the lowest-`f` state, and `came_from` plus `reconstruct_path` rebuild the node sequence once the goal is popped.
- **House filtering.** Intermediate `house`-type nodes are skipped (`if nodes[nxt].get("type") == "house" and nxt not in (start, goal): continue`) so the router never cuts a path through someone's driveway that is not the actual origin or destination.

| Concept field | Value in this project |
|---|---|
| Algorithm | A* (`f = g + h`) over a `heapq` priority queue, `astar()` in `navigation.py` |
| `g` (path cost) | `edge_cost` (metres + edge-kind penalties) plus accumulated `turn_penalty`, units metres |
| `h` (heuristic) | `haversine` great-circle distance to goal, units metres, admissible |
| State | `(prev_id, current_id)` to support turn penalties |
| Output | Ordered node-id list plus `path_distance` (sum of leg haversines, metres) |
| Runtime use | `navigation.py`; graph from `trossachs_nav_graph.json` |

## Why this choice

A* searches the explicit graph while using the heuristic to prioritize promising states. Edge-kind penalties encode a project preference for continuous sidewalk and fewer crossings in an inspectable cost function rather than a learned route policy. Given the same graph, costs, and implementation ordering, the result is repeatable and can be debugged from the selected edges.

## Worked example

Take a start node S and goal G that are 100 m apart in a straight line, with two candidate legs from the current node:

- Leg A: a 60 m `sidewalk` edge to node X, no turn. Cost `g = 60`. If X is 55 m straight-line from G, `f = 60 + 55 = 115`.
- Leg B: a 40 m `intersection` edge to node Y. Cost `g = 40 + 48 = 88`. If Y is 70 m from G, `f = 88 + 70 = 158`.

A* pops Leg A first (115 < 158), correctly preferring the longer-but-continuous sidewalk over the shorter path that forces a penalized intersection crossing. This is the intended behavior: the intersection penalty makes the router "pay" for crossings.

## What can go wrong

- **Inadmissible heuristic.** If `h` overestimated remaining defined cost, A* could return a non-minimum route. Straight-line distance is appropriate only while graph distance and added penalties satisfy the assumptions above.
- **Disconnected graph.** If `edge_allowed` filters out every path between the snapped start and goal, `astar` returns `([], inf)`. That surfaces as a no-route result, which is why sidewalk-snapping and connectivity fixes (tasks around GPS snap and unreachable snaps) live upstream of the search.
- **Bad graph coordinates.** The heuristic and costs trust the node `lat`/`lon`; corrupt coordinates degrade both `g` and `h` but do not break admissibility.

## Related pages

- `research-and-math/machine-learning/regression-framing.md`
- `ai-and-models/training-pipeline/overview.md`
- `autonomy-stack/navigation/overview.md`
