# GeoJSON Graph

The GeoJSON-to-graph test is the offline build step that turns exported OpenStreetMap data into the sidewalk navigation graph the car actually routes over. It is a bench/tooling test rather than a hardware one: it runs `code/test_files/navigation/geojson_to_graph.py`, which reads a neighborhood GeoJSON and emits the `*_nav_graph.json` that both the runtime A* and the route planner consume. A good build here is the prerequisite for every navigation test downstream.

## How it works

- It reads an exported OSM GeoJSON (default `trossachs.geojson`), pulls out sidewalk-type ways (`footway`, `pedestrian`, `steps`) and road types, plus house/address points and manual `house_stop_overrides.json` overrides, and stitches them into a connected graph of nodes and edges.
- It assigns short alphanumeric node IDs and classifies edges by kind (`sidewalk`, `crosswalk`, `intersection`, `crosswalk_transfer`, `osm_gap`, `inferred_crosswalk`, `sidewalk_split`, `house_access`, `house_access_fallback`). A set of distance thresholds controls how gaps are bridged and how houses connect to the nearest sidewalk — for example `ENDPOINT_JOIN_M = 12.0`, `CROSSING_JOIN_M = 24.0`, `INFERRED_CROSSWALK_JOIN_M = 28.0`, `MAX_HOUSE_CONNECTOR_M = 85.0`, and address-matching limits like `ADDRESS_SIDEWALK_MAX_M = 110.0`.
- It computes home and destination candidates from normalized address matches, writes the output graph JSON, and prints a summary: source file, label mode, bounds, total ways, sidewalk/crosswalk way counts, house count, override count, node and edge counts, and the home/dest candidate lists.

## Command

Run on the workstation or Raspberry Pi 5 from the navigation folder (it reads/writes files by relative name):

```bash
cd code/test_files/navigation
python3 geojson_to_graph.py                 # trossachs.geojson -> trossachs_nav_graph.json
python3 geojson_to_graph.py --input sammamish.geojson --output sammamish_nav_graph.json
```

## Pass / warn / fail

- Pass: the printed node/edge counts and home/dest candidates look right for the neighborhood, and the output graph loads cleanly in the A* CLI.
- Warn: the summary reports long house connectors or unexpected candidate lists — a snapping/threshold issue to inspect before routing on it.
- Fail: it can't find the input GeoJSON or produces a disconnected graph — fix the input or thresholds; a broken graph makes every route test meaningless.

## Why it matters

- The route graph is the source of truth for the runtime and offline navigation tools. The runtime follows its AI/manual segment plan with crosswalk handoffs. If the build is wrong, wrong-street snapping and unreachable snaps show up downstream, so this is where I catch them.
- Keeping the builder a checked-in, rerunnable tool (not a one-off) is what lets me regenerate the graph after fixing a snapping rule and diff the result.

## Evidence to attach

- The build summary output (counts + candidates)
- A note of the input GeoJSON and thresholds used
- The A* CLI result on the fresh graph

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
