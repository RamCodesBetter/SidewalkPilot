# Navigation Graph Diagram

This page diagrams the GPS route graph that SidewalkPilot plans over: the node/edge structure, how A* searches it, and how the resulting route is split into AI and manual segments with a crosswalk handoff. It is the map-side companion to the runtime and safety diagrams.

## The Graph

The runtime graph is `code/controller/current/rc_car_app/trossachs_nav_graph.json`, built from OSM data by the `code/test_files/navigation/geojson_to_graph.py` tooling. As currently checked in it holds **6,183 nodes** and **10,072 edges**. Node types are footway/steps (the walkable sidewalk network), crosswalk, and house (address endpoints). Edges carry a *kind* that both gates connectivity and sets cost: `sidewalk` and `sidewalk_split` (the sidewalk network), `crosswalk`, `intersection`, `crosswalk_transfer`, `osm_gap`, `inferred_crosswalk` (ways to cross or bridge gaps), and `house_access` / `house_access_fallback` (links from a house to its sidewalk stop).

## Planning with A*

`NavigationManager.start_route()` snaps the start and destination to sidewalk nodes (`snap_endpoint_to_sidewalk` — a house routes to its `stop_for_house` node) and runs `astar()` over the built graph:

- **Cost:** base edge distance plus kind penalties — `crosswalk_transfer` +220, `intersection`/`osm_gap` +48, `inferred_crosswalk` +36 — so the planner prefers real sidewalk and treats crossings as costly.
- **Turn penalty:** the search state carries the previous node, and `turn_penalty()` adds 3–44 extra cost as the turn angle grows, which biases routes toward straighter, easier-to-drive paths.
- **Heuristic:** straight-line haversine distance to the goal (admissible), so A* stays optimal.
- **Houses** are only allowed as the start or goal, never as pass-through nodes.

## Route into segments

`build_segment_plan()` walks the returned path and splits it into **sidewalk** and **crosswalk** segments. Sidewalk segments are represented as AI/`AUTO`; crosswalk segments are manual/`MNUL`. At the end of a sidewalk segment that feeds a crosswalk, a **handoff node** is selected using `HANDOFF_ALERT_M` (3 m). After a crossing, the configured resume region uses `RESUME_RADIUS_M` (2.5 m). The runtime can fill the start from the nearest GPS graph node while the operator enters the three-character destination on dashboard page 5. These are implemented transitions, not a measured guarantee that GPS accuracy will trigger each one at the intended physical point.

## What this exhibit documents

The implemented weighted A* graph search and AUTO/MNUL segment-plan contract. End-to-end field reliability of GPS-driven switching remains a separate test question.

## Graph-flow view

```text
GPS/start + selected house
          |
          v
snap endpoints to graph
          |
          v
A* with distance + edge-kind + turn costs
          |
          v
route nodes -> sidewalk AUTO segments / crossing MNUL segments
          |
          v
handoff alert before crossing -> operator -> resume region
```

`code/test_files/navigation/generate_printable_map.py` and `trossachs_printable_map.svg` can render the graph. Source anchors are `navigation.py` (`astar`, `edge_cost`, `turn_penalty`, `build_segment_plan`) and `trossachs_nav_graph.json`.

## Related pages

- `portfolio-evidence/reader-paths/evidence-map.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
