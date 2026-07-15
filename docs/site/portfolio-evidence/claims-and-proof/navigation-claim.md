# Navigation Claim

This page states what SidewalkPilot's route navigation actually does, backed by the graph-search code in `navigation.py`.

## The Claim

SidewalkPilot can plan a route over a mapped sidewalk graph and represent it as automatic and manual segments. It uses A* over OpenStreetMap-derived nodes and edges, adds turn costs, marks sidewalk stretches as AI-driven, and marks road crossings as manual. The runtime contains the handoff logic needed to return control before a crosswalk. End-to-end GPS-driven execution has not yet been preserved as a quantitative field result. The routing target is the mapped Trossachs test route, not arbitrary worldwide navigation.

## What the Code Implements

The route logic lives in `code/controller/current/rc_car_app/navigation.py`, against the graph in `trossachs_nav_graph.json`:

- **A* path search** (`astar`) with a haversine straight-line heuristic and a `turn_penalty` term, so among equal-distance paths it prefers the one with gentler turns. House nodes are excluded from through-traffic (only allowed as start/goal).
- **Edge typing and cost** (`edge_allowed`, `edge_cost`): sidewalks, crosswalks, splits, intersections, and inferred/transfer crossings are distinguished, and crosswalk transfers carry extra cost so the planner does not treat a road crossing as free sidewalk.
- **Segment plan** (`build_segment_plan`, `split_route_segments`): the raw path is cut into typed segments. Sidewalk segments are tagged `mode: ai` / operator `AUTO`; crosswalk segments are tagged `mode: manual` / operator `MNUL`. Each segment carries its node list and distance.
- **Crosswalk handoff** (`handoff_index`): before an AI sidewalk segment reaches a following crosswalk, the code computes a handoff point so the operator is warned to take over ahead of the crossing rather than at it.

## Planner implementations

The runtime, Python CLI utility, and HTML planner each contain project-graph routing logic. Similar names do not prove byte-for-byte or route-for-route parity, so matching start/goal regression cases should be used when parity matters.

## What is planned / not-yet-real

- Some **snapping/connectivity refinements are still open** (e.g. connectivity-aware sidewalk fallback and road/entrance stops for sidewalk-less roads) — the graph does not yet perfectly handle every address that lacks a mapped sidewalk. Mark route-correctness on arbitrary new addresses as in-progress.
- **GPS-driven live segment switching in the field** is part of the autonomy stack but its end-to-end reliability is a planned field-test result, not a proven metric yet.

## Evidence to attach

- Code: `navigation.py` (`astar`, `build_segment_plan`, `handoff_index`) and `trossachs_nav_graph.json`.
- Nav tooling in `code/test_files/navigation/` (`geojson_to_graph.py`, `astar_nav.py`, `generate_printable_map.py`).
- A saved custom-planner route and a separately recorded car run using the same start, goal, graph revision, and AI/manual split.

## Related pages

- `portfolio-evidence/reader-paths/evidence-map.md`
- `start-here/project-overview.md`
- `publishing/mkdocs-site.md`
