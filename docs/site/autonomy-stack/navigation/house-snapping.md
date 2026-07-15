# House Snapping

House snapping is how a destination that is a *building* (a house node) gets turned
into a *sidewalk* node the router can actually reach. The car can only drive on
sidewalks, so a house address is snapped to the sidewalk stop in front of it before
A* runs. This is `snap_endpoint_to_sidewalk()` (with `nearest_sidewalk_node()`) in
`code/controller/current/rc_car_app/navigation.py`.

## How it works

- Route endpoints (start and destination) are passed through
  `snap_endpoint_to_sidewalk()` before planning:
  1. **House node with a pre-computed stop:** if the node is `type == "house"` and it
     has a `stop_for_house` field pointing at a valid node, that stop is used as the
     routing endpoint, and the original house ID is remembered as the `final_destination`
     (so the display still names the house even though A* routes to its sidewalk stop).
  2. **Already a sidewalk node:** returned as-is.
  3. **Anything else:** falls back to `nearest_sidewalk_node()`, a linear scan that
     returns the closest node of a sidewalk type (`footway`, `pedestrian`, `steps`,
     `crosswalk`) by haversine distance.
- The `stop_for_house` link is not computed on the car — it is baked into the graph at
  build time by `code/test_files/navigation/geojson_to_graph.py`, which connects each
  house to a sidewalk with a `house_access` (or `house_access_fallback`) edge under a
  connector-distance budget (`MAX_HOUSE_CONNECTOR_M = 85.0` m in the builder). The
  runtime just trusts the pre-assigned stop.
- Inside A*, house nodes are also blocked as pass-through neighbors, so a house can
  only be a route's start or end, never a shortcut. This means the snapped sidewalk
  stop is genuinely where routing begins/ends near a home.

## Why this choice

- Addresses are what a human enters ("go to this house"), but the vehicle graph is
  sidewalks. Snapping bridges the two so the driver picks a building and the car plans
  to the correct curb in front of it.
- Precomputing `stop_for_house` in the offline builder keeps the runtime cheap and
  deterministic — the car never has to solve the harder "which sidewalk serves this
  address" problem live; it was solved once, on the correct street, at build time.
- Keeping the original house ID as `destination_id` means the on-screen destination
  still reads as the house, even though the routed goal is the sidewalk node.

## Known constraints / notes

- `nearest_sidewalk_node()` is a pure nearest-by-distance fallback and can pick a
  geometrically close but wrong-street sidewalk. The correct-street snapping logic
  lives in the offline builder; wrong-street snapping for sidewalk-less roads is a
  known open item on the builder side, not the runtime.

## Related pages

- `autonomy-stack/navigation/graph-format.md`
- `autonomy-stack/navigation/gps-reader.md`
- `autonomy-stack/navigation/a-star.md`
