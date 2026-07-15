# Overview

Navigation is the route-level layer of the SidewalkPilot autonomy stack. It answers
"which way do I need to go to reach the destination" while the camera steering model
answers "how do I follow the sidewalk that is directly in front of me." The two are
deliberately kept separate: route planning runs over an explicit map graph so it can
be inspected and explained, and local sidewalk-following stays inside the neural
network where it belongs. Manual override and the LiDAR/AEB safety layer can interrupt
either one at any time.

The whole navigation subsystem lives in one file,
`code/controller/current/rc_car_app/navigation.py`. It loads a pre-built map graph
(`trossachs_nav_graph.json`), reads the BN880 GPS over `/dev/ttyAMA0` at 9600 baud,
snaps the car's start and the chosen destination onto sidewalk nodes, plans a path
with A*, and splits that path into alternating AI (sidewalk) and manual (crosswalk)
segments. On every control-loop tick, `NavigationManager.update()` re-localizes the
car to the nearest path node, computes remaining distance and ETA, and decides whether
the current segment should be driven by the model (`AUTO`) or handed to the human
(`MNUL`).

## How it works

- `NavigationManager` loads the graph on startup: `6183` nodes and `10072` edges of
  the Trossachs test neighborhood, keyed by uppercase 3-character IDs like `AAA`.
- `GpsReader` runs a background thread parsing `$GPGGA`/`$GNGGA` NMEA sentences into
  lat/lon/fix/sats.
- Each loop, the runtime calls `navigation.update(gps_state, odometer_m, speed_mps)`
  and then `navigation.set_start_from_gps(...)` so the route start always tracks the
  car's current position.
- A* plans over the sidewalk/crosswalk graph with turn penalties, then the path is
  cut into segments. Sidewalk segments are `mode="ai"` / operator `AUTO`; crosswalk
  segments are `mode="manual"` / operator `MNUL`.
- Handoff and resume geometry (a 3.0 m handoff alert before a crosswalk, a 2.5 m
  resume radius after it) drive the AI-to-manual transition at road crossings.

## Why this choice

- Route planning is far easier to inspect, debug, and defend to reviewers when it is
  an explicit graph search rather than something buried inside the CNN.
- Separating map-level decisions from local steering keeps each piece small and
  testable: the model only ever has to follow the sidewalk in front of it.
- The graph is a real OpenStreetMap-derived map of the actual test route, so planned
  paths correspond to real sidewalks the car has driven and photographed.

## Layers

| Layer | Role | Where |
|---|---|---|
| Navigation graph | OSM-derived sidewalk/crosswalk/house map | `trossachs_nav_graph.json` |
| A* + turn penalties | Compute the route over the graph | `astar()` in `navigation.py` |
| Segment planner | Split path into AI vs manual stretches | `build_segment_plan()` |
| GPS reader | Localize the car on the graph | `GpsReader` in `navigation.py` |
| Camera model | Follow the local sidewalk on AI segments | `vision.py` (Series 3 on Jon) |

## Related pages

- `autonomy-stack/architecture/layered-autonomy.md`
- `runtime-code/runtime-loop.md`
- `safety-case/safety-overview.md`
