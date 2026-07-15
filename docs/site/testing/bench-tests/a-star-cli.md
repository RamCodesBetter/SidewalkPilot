# A* CLI

The A* CLI is the offline route-planning test: given a start and a goal, it plans a sidewalk route over the navigation graph and prints both human directions and the machine-readable segment plan the runtime follows. It is how I verify routing logic — snapping, crosswalk handoffs, turn penalties, distances — without moving the car. It runs `code/test_files/navigation/astar_nav.py` against the `*_nav_graph.json` produced by the GeoJSON builder.

## How it works

- It loads the graph (default `trossachs_nav_graph.json`), resolves each of `start` and `goal` from a node ID, a bare house number, `HOME`, or a quoted street address (with abbreviation normalization like `se -> southeast`, `st -> street`), then snaps houses to their sidewalk stop and any non-sidewalk endpoint to the nearest sidewalk node.
- It runs A* over the walkable edge kinds with a haversine heuristic, a per-edge cost that penalizes helper edges (e.g. `crosswalk_transfer` `+220`, `intersection`/`osm_gap` `+48`, `inferred_crosswalk` `+36`), and a turn-smoothness penalty that grows with turn angle so routes prefer straighter paths.
- It then splits the path into segments and labels each as an AI sidewalk segment or a manual crosswalk/transfer segment, with a handoff alert `3.0 m` before a crosswalk and an AI-resume radius of `2.5 m` past it. It emits turn-by-turn directions, a route-health check (non-sidewalk intermediates, number of transfers, long house connectors), a `SEGMENT PLAN` summary, and a `SEGMENT_PLAN_JSON` payload (including a nominal `car_average_speed_mph` of `4.0`).

## Command

Run from the navigation folder (the script reads `trossachs_nav_graph.json` by relative name):

```bash
cd code/test_files/navigation

# full output: directions + segment plan + JSON
python3 astar_nav.py "2059 264th Pl SE" "2028 263rd Pl SE"

# just the human segment plan / just the robot JSON
python3 astar_nav.py HOME 1234 --human
python3 astar_nav.py HOME 1234 --robot
```

## Pass / warn / fail

- Pass: the route stays on sidewalks, hands off to manual only at real crosswalks, and the total distance and segment breakdown match the map.
- Warn: route-health flags long house connectors or non-sidewalk intermediates, or a plan snaps to the wrong street — a graph/snapping issue to fix in the builder, not here.
- Fail: `NO PATH FOUND` between two nodes that should connect — a disconnected graph; rebuild it before trusting any route.

## Why it matters

- The `SEGMENT_PLAN_JSON` uses the same project-graph concepts as the runtime and is useful for checking AI/manual/crosswalk segmentation before a drive. The HTML and runtime implementations still need matching start/goal regression cases to establish parity.
- It is the fast feedback loop for graph fixes: change a snapping rule or threshold, rebuild with `geojson_to_graph.py`, and re-plan here to see the effect.

## Evidence to attach

- The printed directions and segment plan for a known route
- The `SEGMENT_PLAN_JSON` payload
- Any route-health warnings

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
