# Navigation Demo Plan

This page describes the implemented route-planning and segment-handoff code and the evidence needed for a complete navigation demonstration. An indexed end-to-end GPS field result is not preserved yet.

## What the Code Implements

- Routing and segment planning live in `code/controller/current/rc_car_app/navigation.py` (`astar()`, `build_segment_plan()`, `NavigationManager`) over `trossachs_nav_graph.json`.
- GPS fixes come from a BN880 on `/dev/ttyAMA0` at 9600 baud through `GpsReader`.
- Sidewalk edges become AI (`AUTO`) segments; crosswalks, transfers, and gaps become manual (`MNUL`) segments.
- `runtime.py` contains the state transitions that consume this plan. Code presence does not prove that GPS will trigger every physical handoff at the intended location.

## How a route runs

1. On dashboard page 5 (nav entry), I pick a destination and confirm. `NavigationManager` runs A* to build a node path.
2. `build_segment_plan()` splits the path into segments. Each sidewalk segment gets `operator = "AUTO"`; each crosswalk / transfer / gap segment gets `operator = "MNUL"`.
3. As the car moves, `navigation.update()` tracks progress from GPS plus wheel odometry (hall sensor distance) and speed.
4. When a segment's operator is `AUTO` and the camera model is available, the runtime enables autonomous mode and shifts to `D`. When it flips to `MNUL`, autonomy is cancelled and the human takes the crosswalk.
5. On arrival the runtime cancels autonomy (`"Navigation arrived at destination."`).

The A* cost model penalizes turns (`turn_penalty()`) and weights crosswalk transfers so the planner prefers staying on continuous sidewalk where it can.

## Design Rationale and Limit

Navigation treats crosswalks as human-operated segments by construction rather than claiming autonomous road crossing. GPS snapping still depends on fix quality, graph coverage, and connectivity. Connectivity-aware fallback remains an open refinement, so the documentation does not claim that every address produces a reachable route. The HTML route planner in `test_files` is a separate offline tool and is not bridged into the live route.

## Evidence to attach

- Navigation clip with route and crosswalk handoff; no exact published clip is indexed on this page yet.
- Code: `code/controller/current/rc_car_app/navigation.py`
- Graph: `code/controller/current/rc_car_app/trossachs_nav_graph.json`
- Matching `~/logs/log_*.csv` (or the configured `RC_CAR_LOG_DIR`) from the same navigated run.
- GitHub: https://github.com/RamCodesBetter/SidewalkPilot

## Related pages

- `portfolio-evidence/reader-paths/evidence-map.md`
- `start-here/project-overview.md`
- `publishing/mkdocs-site.md`
