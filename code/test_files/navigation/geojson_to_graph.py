import json
import math
import argparse
from collections import defaultdict

ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
REGION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
REGION_SIZE = 50
LABEL_MODE = "3"

MIN_LON = -122.05
MAX_LON = -121.90
MIN_LAT = 47.55
MAX_LAT = 47.65
REGION_MIN_LON = -122.16
REGION_MAX_LON = -121.90
REGION_MIN_LAT = 47.48
REGION_MAX_LAT = 47.68

SIDEWALK_TYPES = {"footway", "pedestrian", "steps"}
ROAD_TYPES = {
    "residential",
    "service",
    "tertiary",
    "unclassified",
    "living_street",
    "secondary",
    "primary",
}
ENDPOINT_JOIN_M = 12.0
CROSSING_JOIN_M = 24.0
OSM_GAP_JOIN_M = 8.0
INFERRED_CROSSWALK_JOIN_M = 28.0
ROAD_SIDEWALK_SEARCH_M = 45.0
SAME_SIDE_PENALTY_M = 30.0
MAX_HOUSE_CONNECTOR_M = 85.0
HELPER_EDGE_PENALTY_M = 18.0
ADDRESS_ROAD_MAX_DIST_M = 75.0
ADDRESS_ROAD_MAX_EXTRA_M = 35.0
LOCAL_SIDEWALK_OVERRIDE_M = 12.0
MISALIGNED_SIDEWALK_PENALTY_M = 55.0
SOFT_MISALIGNED_SIDEWALK_PENALTY_M = 18.0
ENDPOINT_PROJECTION_PENALTY_M = 22.0
ADDRESS_SIDEWALK_MAX_M = 110.0
LOCAL_HOUSE_SIDEWALK_MAX_M = 45.0
ACCESS_SIDEWALK_TIE_M = 6.0
ADDRESS_ACCESS_MAX_CONNECTOR_M = 140.0
ADDRESS_ACCESS_ROAD_MAX_LENGTH_M = 70.0
UNRELATED_FALLBACK_MIN_CONNECTOR_M = 20.0
UNRELATED_FALLBACK_MAX_CONNECTOR_M = LOCAL_HOUSE_SIDEWALK_MAX_M
UNRELATED_FALLBACK_ROAD_MARGIN_M = 10.0

INPUT_GEOJSON = "trossachs.geojson"
OUTPUT_GRAPH = "trossachs_nav_graph.json"
OVERRIDE_FILE = "house_stop_overrides.json"


def label(i):
    base = len(ALNUM)
    if LABEL_MODE == "3":
        if i >= base ** 3:
            raise ValueError("Too many nodes for 3-character alphanumeric IDs")
        region = i // REGION_SIZE
        suffix = i % (base * base)
        return f"{ALNUM[region % base]}{ALNUM[(suffix // base) % base]}{ALNUM[suffix % base]}"

    unique_base = len(ALNUM)
    region_base = len(REGION_LETTERS)
    region_size = unique_base ** 2
    region = i // region_size
    unique = i % region_size
    if region >= region_base ** 2:
        raise ValueError("Too many nodes for 4-character region/unique IDs")
    return (
        f"{REGION_LETTERS[region // region_base]}"
        f"{REGION_LETTERS[region % region_base]}"
        f"{ALNUM[unique // unique_base]}"
        f"{ALNUM[unique % unique_base]}"
    )


def haversine(a, b):
    radius_m = 6371000
    lat1, lon1 = math.radians(a[1]), math.radians(a[0])
    lat2, lon2 = math.radians(b[1]), math.radians(b[0])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    x = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(x))


def normalize_name(name):
    if not name:
        return ""
    replacements = {
        ".": " ",
        ",": " ",
        " se ": " southeast ",
        " st ": " street ",
        " pl ": " place ",
        " ave ": " avenue ",
        " ct ": " court ",
        " dr ": " drive ",
        " ln ": " lane ",
        " wy ": " way ",
    }
    text = f" {name.lower()} "
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def load():
    with open(INPUT_GEOJSON) as f:
        return json.load(f)


def load_house_stop_overrides(path=OVERRIDE_FILE):
    try:
        with open(path) as f:
            raw = json.load(f)
    except FileNotFoundError:
        return {}

    overrides = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        normalized_key = normalize_address_key(key)
        if normalized_key:
            overrides[normalized_key] = value
    return overrides


def normalize_address_key(raw):
    text = " ".join(str(raw or "").split())
    if not text:
        return ""
    parts = text.split(" ", 1)
    if len(parts) != 2:
        return normalize_name(text)
    return f"{parts[0]} {normalize_name(parts[1])}"


def house_address_key(house):
    return normalize_address_key(f"{house.get('num', '')} {house.get('street', '')}")


def coordinate_values(data):
    lons = []
    lats = []

    def walk(value):
        if not isinstance(value, list):
            return
        if (
            len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
            and -180 <= value[0] <= 180
            and -90 <= value[1] <= 90
        ):
            lons.append(value[0])
            lats.append(value[1])
            return
        for item in value:
            walk(item)

    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        walk(geometry.get("coordinates"))

    return lons, lats


def percentile(values, pct):
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * pct)
    return ordered[index]


def configure_bounds(data):
    """Use robust bounds so one bad OSM outlier cannot stretch the whole map."""
    global MIN_LON, MAX_LON, MIN_LAT, MAX_LAT
    lons, lats = coordinate_values(data)
    if not lons or not lats:
        return

    lon_pad = 0.01
    lat_pad = 0.01
    MIN_LON = max(percentile(lons, 0.01) - lon_pad, REGION_MIN_LON)
    MAX_LON = min(percentile(lons, 0.99) + lon_pad, REGION_MAX_LON)
    MIN_LAT = max(percentile(lats, 0.01) - lat_pad, REGION_MIN_LAT)
    MAX_LAT = min(percentile(lats, 0.99) + lat_pad, REGION_MAX_LAT)


def centroid(coords):
    lon = sum(c[0] for c in coords) / len(coords)
    lat = sum(c[1] for c in coords) / len(coords)
    return lon, lat


def geometry_point(geometry):
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Point":
        return tuple(coords)
    if gtype == "LineString":
        return centroid(coords)
    if gtype == "Polygon":
        return centroid(coords[0])
    if gtype == "MultiLineString":
        return centroid([p for line in coords for p in line])
    if gtype == "MultiPolygon":
        return centroid([p for polygon in coords for ring in polygon for p in ring])
    return None


def in_bounds(point):
    lon, lat = point
    return MIN_LON <= lon <= MAX_LON and MIN_LAT <= lat <= MAX_LAT


def line_in_bounds(points):
    return any(in_bounds(point) for point in points)


def is_sidewalk_way(way):
    return way["type"] in SIDEWALK_TYPES


def is_road_way(way):
    return way["type"] in ROAD_TYPES


def is_crossing_way(way):
    return way.get("footway") == "crossing"


def extract(data):
    ways = {}
    houses = []
    named_roads = []
    house_index = 0

    for feature in data.get("features", []):
        geometry = feature.get("geometry") or {}
        props = feature.get("properties", {})
        gtype = geometry.get("type")
        coords = geometry.get("coordinates")

        if gtype == "LineString" and "highway" in props:
            line_points = [tuple(p) for p in coords]
            if not line_in_bounds(line_points):
                continue

            wid = props.get("@id", f"way/{len(ways)}")
            way = {
                "id": wid,
                "name": props.get("name"),
                "nodes": line_points,
                "type": props.get("highway", "unknown"),
                "footway": props.get("footway"),
            }
            ways[wid] = way
            if way["name"]:
                named_roads.append((way["name"], way["nodes"]))

        house_num = props.get("addr:housenumber")
        if house_num:
            point = geometry_point(geometry)
            if point and in_bounds(point):
                houses.append(
                    {
                        "id": props.get("@id") or f"addr/{house_index}",
                        "num": house_num,
                        "street": props.get("addr:street"),
                        "point": point,
                    }
                )
                house_index += 1

    fill_missing_way_names(ways, named_roads, houses)
    return ways, houses


def nearest_point_name(point, named_roads):
    best_name = None
    best_dist = float("inf")
    for name, coords in named_roads:
        for p in coords:
            dist = haversine(point, p)
            if dist < best_dist:
                best_dist = dist
                best_name = name
    return best_name, best_dist


def nearest_house_street(point, houses):
    best_street = None
    best_dist = float("inf")
    for house in houses:
        if not house.get("street"):
            continue
        dist = haversine(point, house["point"])
        if dist < best_dist:
            best_dist = dist
            best_street = house["street"]
    return best_street, best_dist


def fill_missing_way_names(ways, named_roads, houses):
    for way in ways.values():
        if way["name"]:
            continue
        mid = way["nodes"][len(way["nodes"]) // 2]
        road_name, road_dist = nearest_point_name(mid, named_roads)
        house_street, house_dist = nearest_house_street(mid, houses)
        if road_name and road_dist <= 80:
            way["name"] = road_name
        elif house_street and house_dist <= 120:
            way["name"] = house_street
        else:
            way["name"] = "unnamed"


def local_xy(point, origin):
    lon0, lat0 = origin
    lon, lat = point
    lat_scale = 110540
    lon_scale = 111320 * math.cos(math.radians(lat0))
    return (lon - lon0) * lon_scale, (lat - lat0) * lat_scale


def side_of_segment(point, a, b):
    px, py = local_xy(point, a)
    bx, by = local_xy(b, a)
    cross = bx * py - by * px
    if abs(cross) < 0.01:
        return 0
    return 1 if cross > 0 else -1


def segment_angle_delta(a, b, c, d):
    abx, aby = local_xy(b, a)
    cdx, cdy = local_xy(d, c)
    mag1 = math.hypot(abx, aby)
    mag2 = math.hypot(cdx, cdy)
    if mag1 < 1e-9 or mag2 < 1e-9:
        return 0
    dot = (abx * cdx + aby * cdy) / (mag1 * mag2)
    dot = max(-1, min(1, dot))
    angle = math.degrees(math.acos(dot))
    return min(angle, 180 - angle)


def endpoint_projection_penalty(t):
    return ENDPOINT_PROJECTION_PENALTY_M if t <= 0.04 or t >= 0.96 else 0.0


def alignment_penalty(road_segment, way, idx):
    if not road_segment or len(way["nodes"]) < 2:
        return 0.0
    way_a = way["nodes"][idx]
    way_b = way["nodes"][min(idx + 1, len(way["nodes"]) - 1)]
    angle = segment_angle_delta(road_segment[0], road_segment[1], way_a, way_b)
    if angle >= 65:
        return MISALIGNED_SIDEWALK_PENALTY_M
    if angle >= 35:
        return SOFT_MISALIGNED_SIDEWALK_PENALTY_M
    return 0.0


def closest_point_on_segment(point, a, b):
    lon0, lat0 = point
    lat_scale = 110540
    lon_scale = 111320 * math.cos(math.radians(lat0))
    ax = (a[0] - lon0) * lon_scale
    ay = (a[1] - lat0) * lat_scale
    bx = (b[0] - lon0) * lon_scale
    by = (b[1] - lat0) * lat_scale
    abx = bx - ax
    aby = by - ay
    denom = abx * abx + aby * aby
    if denom == 0:
        return a, 0
    t = ((0 - ax) * abx + (0 - ay) * aby) / denom
    t = max(0, min(1, t))
    lon = a[0] + (b[0] - a[0]) * t
    lat = a[1] + (b[1] - a[1]) * t
    return (lon, lat), t


def nearest_way_point(point, way_points):
    best_index = 0
    best_point = way_points[0]
    best_dist = float("inf")
    best_t = 0
    if len(way_points) == 1:
        return best_index, best_point, haversine(point, best_point), best_t
    for idx in range(len(way_points) - 1):
        projected, t = closest_point_on_segment(point, way_points[idx], way_points[idx + 1])
        dist = haversine(point, projected)
        if dist < best_dist:
            best_index = idx
            best_point = projected
            best_dist = dist
            best_t = t
    return best_index, best_point, best_dist, best_t


def nearest_road(point, ways, street=None):
    normalized_street = normalize_name(street)
    road_ways = [(wid, way) for wid, way in ways.items() if is_road_way(way)]
    named_candidates = [(wid, way) for wid, way in road_ways if normalize_name(way["name"]) == normalized_street]

    best_any = (None, None, None, float("inf"), 0)
    for wid, way in road_ways:
        idx, projected, dist, t = nearest_way_point(point, way["nodes"])
        if dist < best_any[3]:
            best_any = (wid, idx, projected, dist, t)

    if not named_candidates:
        return best_any

    best_named = (None, None, None, float("inf"), 0)
    for wid, way in named_candidates:
        idx, projected, dist, t = nearest_way_point(point, way["nodes"])
        if dist < best_named[3]:
            best_named = (wid, idx, projected, dist, t)

    # Address tags are not always the closest physical access road. Apartment
    # clusters and private developments can carry a boulevard address while the
    # usable pedestrian access is on a small local road/path next to the house.
    # Use the address road when it is plausibly local; otherwise use the nearest
    # physical road so connectors do not fan across the map to an entrance.
    if (
        best_named[0] is not None
        and (
            best_named[3] <= ADDRESS_ROAD_MAX_DIST_M
            or best_named[3] <= best_any[3] + ADDRESS_ROAD_MAX_EXTRA_M
        )
    ):
        return best_named

    return best_any


def nearest_address_road(point, ways, street=None):
    normalized_street = normalize_name(street)
    if not normalized_street:
        return nearest_road(point, ways, street)

    best = (None, None, None, float("inf"), 0)
    for wid, way in ways.items():
        if not is_road_way(way) or normalize_name(way["name"]) != normalized_street:
            continue
        idx, projected, dist, t = nearest_way_point(point, way["nodes"])
        if dist < best[3]:
            best = (wid, idx, projected, dist, t)

    if best[0] is not None:
        return best
    return nearest_road(point, ways, street)


def nearest_sidewalk_to_point(point, ways, preferred_point=None):
    best = None
    best_dist = float("inf")
    best_preferred_dist = float("inf")
    for wid, way in ways.items():
        if not is_sidewalk_way(way) or is_crossing_way(way):
            continue
        idx, projected, dist, t = nearest_way_point(point, way["nodes"])
        preferred_dist = haversine(preferred_point, projected) if preferred_point else 0.0
        close_enough_to_best = dist <= best_dist + ACCESS_SIDEWALK_TIE_M
        better_tie = close_enough_to_best and preferred_dist < best_preferred_dist
        if dist < best_dist - ACCESS_SIDEWALK_TIE_M or better_tie:
            best = (wid, idx, projected, dist, t)
            best_dist = dist
            best_preferred_dist = preferred_dist
    return best


def nearest_sidewalk_vertex_to_point(point, ways, preferred_point=None, road_segment=None, preferred_side=0):
    best = None
    best_score = float("inf")
    for wid, way in ways.items():
        if not is_sidewalk_way(way) or is_crossing_way(way):
            continue
        for node_index, candidate in enumerate(way["nodes"]):
            endpoint_dist = haversine(point, candidate)
            preferred_dist = haversine(preferred_point, candidate) if preferred_point else 0.0
            side_penalty = 0.0
            if road_segment and preferred_side:
                candidate_side = side_of_segment(candidate, road_segment[0], road_segment[1])
                if candidate_side and candidate_side != preferred_side:
                    side_penalty = SAME_SIDE_PENALTY_M * 3
            score = endpoint_dist + preferred_dist * 0.08 + side_penalty
            if score < best_score:
                segment_index = min(node_index, max(0, len(way["nodes"]) - 2))
                t = 1.0 if node_index == len(way["nodes"]) - 1 else 0.0
                best = (wid, segment_index, candidate, endpoint_dist, t)
                best_score = score
    return best


def address_road_access_sidewalk(road_id, ways, preferred_point=None, road_segment=None, preferred_side=0):
    """Find the sidewalk nearest the address road's access endpoint.

    Some short residential courts do not have mapped sidewalks. For those,
    the correct stop is not the closest sidewalk to each house; it is the
    sidewalk reachable at the court's street connection.
    """
    if not road_id or road_id not in ways:
        return None

    road = ways[road_id]
    if len(road["nodes"]) < 2:
        return None

    best = None
    best_dist = float("inf")
    best_preferred_dist = float("inf")
    for endpoint in (road["nodes"][0], road["nodes"][-1]):
        candidate = nearest_sidewalk_vertex_to_point(endpoint, ways, preferred_point, road_segment, preferred_side)
        if not candidate:
            continue
        preferred_dist = haversine(preferred_point, candidate[2]) if preferred_point else 0.0
        close_enough_to_best = candidate[3] <= best_dist + ACCESS_SIDEWALK_TIE_M
        better_tie = close_enough_to_best and preferred_dist < best_preferred_dist
        if candidate[3] < best_dist - ACCESS_SIDEWALK_TIE_M or better_tie:
            best = candidate
            best_dist = candidate[3]
            best_preferred_dist = preferred_dist

    return best


def override_point(value):
    if not isinstance(value, dict):
        return None
    if "lat" in value and "lon" in value:
        return (float(value["lon"]), float(value["lat"]))
    if "point" in value and isinstance(value["point"], list) and len(value["point"]) == 2:
        return (float(value["point"][0]), float(value["point"][1]))
    return None


def override_sidewalk_stop(house, ways, override):
    """Force a house to the nearest existing mapped sidewalk near a coordinate."""
    point = override_point(override)
    if not point:
        return None

    max_m = float(override.get("max_m", 10.0))
    best = None
    best_dist = float("inf")
    for wid, way in ways.items():
        if way.get("synthetic") or not is_sidewalk_way(way) or is_crossing_way(way):
            continue
        idx, projected, dist, t = nearest_way_point(point, way["nodes"])
        if dist < best_dist:
            best = (wid, idx, projected, haversine(house["point"], projected), t)
            best_dist = dist

    if best and best_dist <= max_m:
        return (*best, "override")
    return None


def way_length(way):
    return sum(haversine(a, b) for a, b in zip(way["nodes"], way["nodes"][1:]))


def unrelated_fallback_limit(road_dist):
    if not math.isfinite(road_dist):
        return UNRELATED_FALLBACK_MIN_CONNECTOR_M
    return min(
        UNRELATED_FALLBACK_MAX_CONNECTOR_M,
        max(UNRELATED_FALLBACK_MIN_CONNECTOR_M, road_dist + UNRELATED_FALLBACK_ROAD_MARGIN_M),
    )


def choose_sidewalk_stop(house, ways, overrides=None):
    override = (overrides or {}).get(house_address_key(house))
    if override:
        choice = override_sidewalk_stop(house, ways, override)
        if choice:
            return choice

    road_id, _, road_point, road_dist, _ = nearest_address_road(house["point"], ways, house.get("street"))
    road_name = normalize_name(ways[road_id]["name"]) if road_id else normalize_name(house.get("street"))
    house_street = normalize_name(house.get("street"))
    road_segment = None
    house_side = 0
    if road_id and road_id in ways and road_point is not None:
        road = ways[road_id]
        access_road_mode = way_length(road) <= ADDRESS_ACCESS_ROAD_MAX_LENGTH_M
        road_idx, _, _, _ = nearest_way_point(house["point"], road["nodes"])
        if len(road["nodes"]) >= 2:
            road_segment = (
                road["nodes"][road_idx],
                road["nodes"][min(road_idx + 1, len(road["nodes"]) - 1)],
            )
            house_side = side_of_segment(house["point"], road_segment[0], road_segment[1])
    else:
        access_road_mode = False
    access_sidewalk = (
        address_road_access_sidewalk(road_id, ways, house["point"], road_segment, house_side)
        if access_road_mode
        else None
    )
    best_related = None
    best_related_dist = float("inf")
    best_any = None
    best_any_dist = float("inf")

    for wid, way in ways.items():
        if not is_sidewalk_way(way) or is_crossing_way(way):
            continue
        idx, projected, dist, t = nearest_way_point(house["point"], way["nodes"])
        if dist < best_any_dist:
            best_any = (wid, idx, projected, dist, t)
            best_any_dist = dist

        sidewalk_name = normalize_name(way["name"])
        same_address = house_street and sidewalk_name == house_street
        same_road = road_name and sidewalk_name == road_name
        near_address_road = False
        if road_point is not None:
            _, _, road_sidewalk_dist, _ = nearest_way_point(road_point, way["nodes"])
            near_address_road = road_sidewalk_dist <= ROAD_SIDEWALK_SEARCH_M

        # A same-named sidewalk only belongs to this house if it is local to
        # the address-road projection or physically close to the house. Without
        # this guard, far-away fragments with the same road name pull groups of
        # houses into one bad connector point.
        local_named_sidewalk = (same_address or same_road) and (
            near_address_road or dist <= MAX_HOUSE_CONNECTOR_M
        )

        if local_named_sidewalk or (near_address_road and not access_road_mode):
            if dist < best_related_dist:
                best_related = (wid, idx, projected, dist, t)
                best_related_dist = dist

    if access_sidewalk:
        access_wid, access_idx, access_projected, access_dist, access_t = access_sidewalk
        access_way = ways[access_wid]
        address_has_local_sidewalk = (
            best_related
            and (
                normalize_name(access_way["name"]) == house_street
                or best_related_dist <= LOCAL_HOUSE_SIDEWALK_MAX_M
            )
        )
        if not address_has_local_sidewalk and access_dist <= ADDRESS_SIDEWALK_MAX_M:
            connector_dist = haversine(house["point"], access_projected)
            if connector_dist <= ADDRESS_ACCESS_MAX_CONNECTOR_M:
                return (access_wid, access_idx, access_projected, connector_dist, access_t, "address_road_access")

    if best_related and best_related_dist <= MAX_HOUSE_CONNECTOR_M:
        return (*best_related, "direct")
    # Prefer the house's own-road sidewalk (even a bit farther, or on the
    # opposite side of the road) over snapping to a DIFFERENT road's nearer
    # sidewalk. A house can legitimately be across from its only sidewalk.
    if best_related and best_related_dist <= ADDRESS_SIDEWALK_MAX_M:
        return (*best_related, "same_road_extended")
    if best_any:
        mode = "nearest_sidewalk_fallback"
        if best_any_dist > unrelated_fallback_limit(road_dist):
            mode = "forced_sidewalk_fallback"
        return (*best_any, mode)
    return None


def add_node(nodes, node_lookup, next_id, point, info):
    node_type = info.get("type")
    if node_type in {"house", "house_stop"} or info.get("way_role") in {"house", "house_stop"}:
        identity = info.get("house_id") or info.get("stop_for_house") or info.get("house")
    else:
        identity = info.get("way_id")

    key = (
        round(point[0], 7),
        round(point[1], 7),
        node_type,
        identity,
    )
    if key in node_lookup:
        return node_lookup[key], next_id

    nid = label(next_id)
    next_id += 1
    nodes[nid] = {
        "lat": point[1],
        "lon": point[0],
        "region": (next_id - 1) // REGION_SIZE,
        "road": info.get("road") or "unnamed",
        "way_id": info.get("way_id"),
        "type": info.get("type"),
        "house": info.get("house"),
        "house_id": info.get("house_id"),
        "street": info.get("street"),
        "stop_for_house": info.get("stop_for_house"),
        "connector_distance_m": info.get("connector_distance_m"),
        "connector_status": info.get("connector_status"),
        "connector_reason": info.get("connector_reason"),
        "way_role": info.get("way_role"),
        "crosswalk_endpoint": bool(info.get("crosswalk_endpoint")),
    }
    node_lookup[key] = nid
    return nid, next_id


def add_edge(edges, existing, a, b, dist, kind):
    if a == b:
        return
    key = tuple(sorted((a, b)))
    old = existing.get(key)
    if old is not None and old <= dist:
        return
    existing[key] = dist
    edges.append((a, b, dist, kind))


def build(ways, houses, overrides=None):
    nodes = {}
    node_lookup = {}
    edges = []
    existing_edges = {}
    next_id = 0
    way_node_ids = {}
    way_endpoint_ids = []

    for wid, way in ways.items():
        if not is_sidewalk_way(way):
            continue
        ids = []
        role = "crosswalk" if is_crossing_way(way) else "sidewalk"
        last_raw_index = len(way["nodes"]) - 1
        for raw_index, point in enumerate(way["nodes"]):
            nid, next_id = add_node(
                nodes,
                node_lookup,
                next_id,
                point,
                {
                    "road": way["name"],
                    "way_id": wid,
                    "type": "crosswalk" if role == "crosswalk" else way["type"],
                    "way_role": role,
                    "crosswalk_endpoint": role == "crosswalk" and raw_index in {0, last_raw_index},
                },
            )
            ids.append((raw_index, nid))
        way_node_ids[wid] = ids
        if ids:
            way_endpoint_ids.append((ids[0][1], wid, role))
            way_endpoint_ids.append((ids[-1][1], wid, role))
        for (_, a_id), (_, b_id) in zip(ids, ids[1:]):
            a = (nodes[a_id]["lon"], nodes[a_id]["lat"])
            b = (nodes[b_id]["lon"], nodes[b_id]["lat"])
            add_edge(edges, existing_edges, a_id, b_id, haversine(a, b), role)

    for i, (a_id, a_wid, a_role) in enumerate(way_endpoint_ids):
        a = (nodes[a_id]["lon"], nodes[a_id]["lat"])
        for b_id, b_wid, b_role in way_endpoint_ids[i + 1 :]:
            if a_wid == b_wid:
                continue
            b = (nodes[b_id]["lon"], nodes[b_id]["lat"])
            dist = haversine(a, b)
            if dist <= ENDPOINT_JOIN_M:
                add_edge(edges, existing_edges, a_id, b_id, dist, "intersection")
            elif (a_role == "crosswalk" or b_role == "crosswalk") and dist <= CROSSING_JOIN_M:
                add_edge(edges, existing_edges, a_id, b_id, dist, "crosswalk_transfer")

    for house in houses:
        choice = choose_sidewalk_stop(house, ways, overrides)
        if not choice:
            _, next_id = add_node(
                nodes,
                node_lookup,
                next_id,
                house["point"],
                {
                    "road": house.get("street") or "unmapped",
                    "type": "house",
                    "house": house["num"],
                    "house_id": house["id"],
                    "street": house.get("street"),
                    "connector_status": "unmapped",
                    "connector_reason": "no sidewalk candidate found",
                    "way_role": "house",
                },
            )
            continue
        wid, raw_index, stop_point, stop_dist, _, connector_mode = choice
        way = ways[wid]
        role = "crosswalk" if is_crossing_way(way) else "sidewalk"

        stop_id, next_id = add_node(
            nodes,
            node_lookup,
            next_id,
            stop_point,
            {
                "road": house.get("street") or way["name"],
                "way_id": wid,
                "type": "crosswalk" if role == "crosswalk" else way["type"],
                "house": house["num"],
                "house_id": house["id"],
                "street": house.get("street"),
                "stop_for_house": None,
                "connector_distance_m": stop_dist,
                "connector_status": "connected" if connector_mode == "direct" else connector_mode,
                "connector_reason": (
                    None
                    if connector_mode == "direct"
                    else "forced by house_stop_overrides.json to an existing mapped sidewalk"
                    if connector_mode == "override"
                    else "attached to sidewalk nearest the house's nearest road point"
                ),
                "way_role": "house_stop",
            },
        )
        house_id, next_id = add_node(
            nodes,
            node_lookup,
            next_id,
            house["point"],
            {
                "road": house.get("street") or way["name"],
                "way_id": wid,
                "type": "house",
                "house": house["num"],
                "house_id": house["id"],
                "street": house.get("street"),
                "stop_for_house": stop_id,
                "connector_distance_m": stop_dist,
                "connector_status": "connected" if connector_mode == "direct" else connector_mode,
                "connector_reason": (
                    None
                    if connector_mode == "direct"
                    else "forced by house_stop_overrides.json to an existing mapped sidewalk"
                    if connector_mode == "override"
                    else "attached to sidewalk nearest the house's nearest road point"
                ),
                "way_role": "house",
            },
        )
        edge_kind = "house_access" if connector_mode == "direct" else "house_access_fallback"
        add_edge(edges, existing_edges, house_id, stop_id, stop_dist, edge_kind)

        endpoint_ids = []
        if connector_mode != "address_road_access":
            for segment_index in (raw_index, raw_index + 1):
                if segment_index >= len(way["nodes"]):
                    continue
                endpoint_point = way["nodes"][segment_index]
                endpoint_id, next_id = add_node(
                    nodes,
                    node_lookup,
                    next_id,
                    endpoint_point,
                    {
                        "road": way["name"],
                        "way_id": wid,
                        "type": "crosswalk" if role == "crosswalk" else way["type"],
                        "street": house.get("street"),
                        "way_role": role,
                        "crosswalk_endpoint": role == "crosswalk" and segment_index in {0, len(way["nodes"]) - 1},
                    },
                )
                endpoint_ids.append(endpoint_id)
            for endpoint_id in endpoint_ids:
                endpoint = (nodes[endpoint_id]["lon"], nodes[endpoint_id]["lat"])
                add_edge(edges, existing_edges, stop_id, endpoint_id, haversine(stop_point, endpoint), "sidewalk_split")

    add_osm_gap_transfers(nodes, edges, existing_edges)
    add_inferred_crosswalk_transfers(nodes, edges, existing_edges)
    return nodes, edges


def add_osm_gap_transfers(nodes, edges, existing_edges, threshold_m=OSM_GAP_JOIN_M):
    sidewalk_ids = [
        nid
        for nid, node in nodes.items()
        if node["type"] in SIDEWALK_TYPES or node["type"] == "crosswalk"
    ]
    cell = threshold_m / 111000
    buckets = defaultdict(list)

    for nid in sidewalk_ids:
        node = nodes[nid]
        key = (int(node["lon"] / cell), int(node["lat"] / cell))
        buckets[key].append(nid)

    for a_id in sidewalk_ids:
        a = nodes[a_id]
        if a["type"] == "crosswalk" and not a.get("crosswalk_endpoint"):
            continue
        bx = int(a["lon"] / cell)
        by = int(a["lat"] / cell)

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for b_id in buckets.get((bx + dx, by + dy), []):
                    if b_id <= a_id:
                        continue

                    b = nodes[b_id]
                    if b["type"] == "crosswalk" and not b.get("crosswalk_endpoint"):
                        continue
                    a_crosswalk = a["type"] == "crosswalk"
                    b_crosswalk = b["type"] == "crosswalk"
                    if (a.get("way_role") == "house_stop" or b.get("way_role") == "house_stop") and not (
                        a_crosswalk or b_crosswalk
                    ):
                        continue
                    if a.get("way_id") == b.get("way_id"):
                        continue

                    dist = haversine((a["lon"], a["lat"]), (b["lon"], b["lat"]))
                    if dist <= threshold_m:
                        add_edge(edges, existing_edges, a_id, b_id, dist, "osm_gap")


def route_network_node(node):
    if node.get("way_role") == "house_stop":
        return False
    return node["type"] in SIDEWALK_TYPES or node["type"] == "crosswalk"


def component_edges_for_repair(edge):
    kind = edge[3] if len(edge) > 3 else "way"
    return kind in {
        "sidewalk",
        "crosswalk",
        "sidewalk_split",
        "intersection",
        "crosswalk_transfer",
        "osm_gap",
        "inferred_crosswalk",
    }


def sidewalk_components(nodes, edges):
    graph = defaultdict(list)
    for edge in edges:
        if not component_edges_for_repair(edge):
            continue
        a, b = edge[:2]
        if route_network_node(nodes[a]) and route_network_node(nodes[b]):
            graph[a].append(b)
            graph[b].append(a)

    seen = set()
    components = []
    for nid, node in nodes.items():
        if not route_network_node(node) or nid in seen:
            continue
        stack = [nid]
        seen.add(nid)
        component = []
        while stack:
            current = stack.pop()
            component.append(current)
            for nxt in graph.get(current, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(component)

    components.sort(key=len, reverse=True)
    return components


def add_inferred_crosswalk_transfers(
    nodes,
    edges,
    existing_edges,
    threshold_m=INFERRED_CROSSWALK_JOIN_M,
):
    components = sidewalk_components(nodes, edges)
    if len(components) <= 1:
        return

    connected_ids = set(components[0])
    for component in components[1:]:
        best = None
        best_dist = float("inf")

        for a_id in component:
            a = nodes[a_id]
            if not route_network_node(a):
                continue
            for b_id in connected_ids:
                b = nodes[b_id]
                if not route_network_node(b):
                    continue
                if a.get("way_id") == b.get("way_id"):
                    continue
                dist = haversine((a["lon"], a["lat"]), (b["lon"], b["lat"]))
                if dist < best_dist:
                    best = (a_id, b_id)
                    best_dist = dist

        if best and best_dist <= threshold_m:
            add_edge(edges, existing_edges, best[0], best[1], best_dist, "inferred_crosswalk")
            connected_ids.update(component)




def parse_args():
    parser = argparse.ArgumentParser(description="Build a sidewalk navigation graph from exported OSM GeoJSON.")
    parser.add_argument("--input", default=INPUT_GEOJSON, help="Input GeoJSON file")
    parser.add_argument("--output", default=OUTPUT_GRAPH, help="Output graph JSON file")
    parser.add_argument(
        "--label-mode",
        choices=("3", "4"),
        default="3",
        help="Node label length: 3 for Trossachs, 4 for larger Sammamish/Issaquah maps",
    )
    return parser.parse_args()


def main():
    global INPUT_GEOJSON, OUTPUT_GRAPH, LABEL_MODE
    args = parse_args()
    INPUT_GEOJSON = args.input
    OUTPUT_GRAPH = args.output
    LABEL_MODE = args.label_mode

    geo = load()
    configure_bounds(geo)
    ways, houses = extract(geo)
    overrides = load_house_stop_overrides()
    nodes, edges = build(ways, houses, overrides)
    home_key = normalize_address_key("2019 264th Place Southeast")
    dest_key = normalize_address_key("2028 263rd Place Southeast")
    home = [nid for nid, node in nodes.items() if node.get("type") == "house" and normalize_address_key(f"{node.get('house', '')} {node.get('street', '')}") == home_key]
    dest = [nid for nid, node in nodes.items() if node.get("type") == "house" and normalize_address_key(f"{node.get('house', '')} {node.get('street', '')}") == dest_key]
    with open(OUTPUT_GRAPH, "w") as f:
        json.dump(
            {
                "nodes": nodes,
                "edges": edges,
                "home_candidates": home,
                "default_destination_candidates": dest,
                "source_geojson": INPUT_GEOJSON,
                "label_mode": LABEL_MODE,
            },
            f,
            indent=2,
        )
    print(f"SOURCE: {INPUT_GEOJSON}")
    print(f"LABEL MODE: {LABEL_MODE}")
    print(f"BOUNDS: lat {MIN_LAT:.6f}..{MAX_LAT:.6f}, lon {MIN_LON:.6f}..{MAX_LON:.6f}")
    print("TOTAL WAYS:", len(ways))
    print("SIDEWALK/CROSSWALK WAYS:", sum(1 for w in ways.values() if is_sidewalk_way(w)))
    print("CROSSWALK WAYS:", sum(1 for w in ways.values() if is_crossing_way(w)))
    print("TOTAL HOUSES:", len(houses))
    print("HOUSE STOP OVERRIDES:", len(overrides))
    print("NODES:", len(nodes))
    print("EDGES:", len(edges))
    print("HOME CANDIDATES:", home)
    print("DEST CANDIDATES:", dest)
    print(f"DONE -> {OUTPUT_GRAPH}")


if __name__ == "__main__":
    main()
