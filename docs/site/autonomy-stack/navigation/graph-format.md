# Graph Format

The navigation graph is the map SidewalkPilot plans over. It is a single JSON file,
`code/controller/current/rc_car_app/trossachs_nav_graph.json`, built offline from an
OpenStreetMap export of the Trossachs test neighborhood by
`code/test_files/navigation/geojson_to_graph.py`. The runtime never touches OSM
directly — it only loads this pre-built graph.

## How it works

The file has these top-level keys: `nodes`, `edges`, `home_candidates`,
`default_destination_candidates`, `source_geojson`, and `label_mode`.

**Nodes** are a dict keyed by 3-character uppercase IDs (`AAA`, `AAB`, ... over the
alphabet `ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`). The current graph has **6183 nodes**
of four types: `footway` (4369), `house` (1287), `crosswalk` (519), and `steps` (8).
Each node carries `lat`, `lon`, `region`, `road`, `way_id`, `type`, `way_role`,
`crosswalk_endpoint`, and — for house/house-stop nodes — `house`, `house_id`,
`street`, `stop_for_house`, and connector metadata (`connector_distance_m`,
`connector_status`, `connector_reason`).

**Edges** are a list of `[a, b, distance_m, kind]` arrays — **10072 edges** in the
current graph. Edges are undirected (the runtime adds both directions in
`build_graph()`). The `kind` field is what the router keys off of. Current kind
counts: `sidewalk` (2993), `sidewalk_split` (2412), `osm_gap` (1656),
`house_access` (1049), `crosswalk_transfer` (853), `intersection` (522),
`crosswalk` (346), `house_access_fallback` (238), and `inferred_crosswalk` (3).

Edge kinds are grouped by the runtime into named sets that drive routing and
segmenting:

- `SIDEWALK_SEGMENT_EDGE_KINDS` = `{sidewalk, sidewalk_split, house_access,
  house_access_fallback}` — driven as AI/`AUTO`.
- `CROSSWALK_SEGMENT_EDGE_KINDS` = `{crosswalk, intersection, crosswalk_transfer,
  osm_gap, inferred_crosswalk}` — driven manually/`MNUL`.

On load, `NavigationManager.load()` uppercases all node keys and edge endpoints so
lookups are case-consistent, builds an `edges_by_pair` lookup (sorted `(a, b)` tuple),
and constructs the adjacency graph via `edge_allowed()` / `edge_cost()`.

## Why this choice

- A flat, human-readable JSON graph is trivial to inspect, diff in git, and load with
  no dependencies — no live map API on the car, no network at drive time.
- Tagging every edge with a `kind` lets one graph serve two jobs at once: A* cost
  shaping (crosswalks/gaps cost more) and segment classification (sidewalk vs
  crosswalk decides AUTO vs MNUL).
- The runtime and HTML route planner consume the same JSON, so both use the same
  checked-in map data.

## Related pages

- `autonomy-stack/navigation/a-star.md`
- `autonomy-stack/navigation/house-snapping.md`
- `autonomy-stack/navigation/ai-manual-segments.md`
