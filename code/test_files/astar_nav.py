import heapq
import json
import math
import sys
import argparse

GRAPH_FILE = "trossachs_nav_graph.json"
HOME = "PNX"  # fallback; refreshed from graph home_candidates at runtime
SIDEWALK_TYPES = {"footway", "pedestrian", "steps", "crosswalk"}
WALK_EDGE_KINDS = {
    "sidewalk",
    "crosswalk",
    "intersection",
    "crosswalk_transfer",
    "sidewalk_split",
    "osm_gap",
    "inferred_crosswalk",
}
SIDEWALK_SEGMENT_EDGE_KINDS = {"sidewalk", "sidewalk_split"}
DRIVEWAY_SEGMENT_EDGE_KINDS = {"house_access", "house_access_fallback"}
CROSSWALK_SEGMENT_EDGE_KINDS = {
    "crosswalk",
    "intersection",
    "crosswalk_transfer",
    "osm_gap",
    "inferred_crosswalk",
}
HANDOFF_ALERT_M = 3.0
RESUME_RADIUS_M = 2.5


def is_sidewalk_node(node):
    return node.get("type") in SIDEWALK_TYPES


def is_crosswalk_node(node):
    return node.get("type") == "crosswalk" or node.get("way_role") == "crosswalk"


def is_crosswalk_endpoint(node):
    return not is_crosswalk_node(node) or node.get("crosswalk_endpoint")


def helper_edge_allowed(kind, a_node, b_node):
    if not is_crosswalk_endpoint(a_node) or not is_crosswalk_endpoint(b_node):
        return False
    if kind not in {"intersection", "osm_gap"}:
        return True
    same_road = display_road(a_node) == display_road(b_node)
    touches_crosswalk = is_crosswalk_node(a_node) or is_crosswalk_node(b_node)
    return same_road or touches_crosswalk


def effective_edge_cost(edge, nodes):
    a, b, dist = edge[:3]
    kind = edge[3] if len(edge) > 3 else "way"
    a_node = nodes[a]
    b_node = nodes[b]
    if kind == "crosswalk_transfer":
        return dist + 220
    if kind == "inferred_crosswalk":
        return dist + 36
    if kind in {"intersection", "osm_gap"}:
        return dist + 48
    return dist


def haversine(a, b):
    radius_m = 6371000
    lat1, lon1 = math.radians(a["lat"]), math.radians(a["lon"])
    lat2, lon2 = math.radians(b["lat"]), math.radians(b["lon"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    x = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * radius_m * math.asin(math.sqrt(x))


def edge_allowed(edge, nodes):
    a, b = edge[:2]
    kind = edge[3] if len(edge) > 3 else "way"

    if kind in {"sidewalk", "crosswalk", "sidewalk_split"}:
        return is_sidewalk_node(nodes[a]) and is_sidewalk_node(nodes[b])

    if kind == "inferred_crosswalk":
        return is_sidewalk_node(nodes[a]) and is_sidewalk_node(nodes[b])

    if kind in {"intersection", "crosswalk_transfer", "osm_gap"}:
        return is_sidewalk_node(nodes[a]) and is_sidewalk_node(nodes[b]) and helper_edge_allowed(kind, nodes[a], nodes[b])

    if kind in {"house_access", "house_access_fallback"}:
        return (
            nodes[a].get("type") == "house" and is_sidewalk_node(nodes[b])
            or nodes[b].get("type") == "house" and is_sidewalk_node(nodes[a])
        )

    return False


def build_graph(edges, nodes):
    graph = {}
    for edge in edges:
        a, b, dist = edge[:3]
        if not edge_allowed(edge, nodes):
            continue
        cost = effective_edge_cost(edge, nodes)
        graph.setdefault(a, []).append((b, cost))
        graph.setdefault(b, []).append((a, cost))
    return graph


def turn_amount(prev_node, current_node, next_node):
    before = bearing(prev_node, current_node)
    after = bearing(current_node, next_node)
    return abs((after - before + 540) % 360 - 180)


def turn_penalty(nodes, prev_id, current_id, next_id):
    if prev_id is None:
        return 0

    amount = turn_amount(nodes[prev_id], nodes[current_id], nodes[next_id])

    if amount < 25:
        return 0
    if amount < 45:
        return 3
    if amount < 90:
        return 10
    if amount < 135:
        return 24
    return 44


def astar(graph, nodes, start, goal):
    start_state = (None, start)
    pq = [(0, 0, start_state)]
    came_from = {}
    cost_so_far = {start_state: 0}

    while pq:
        _, _, state = heapq.heappop(pq)
        prev_id, current = state

        if current == goal:
            path = reconstruct_path(came_from, start_state, state)
            return path, path_distance(path, nodes)

        for nxt, edge_cost in graph.get(current, []):
            # House nodes are destinations/starts, not through-roads.
            if nodes[nxt].get("type") == "house" and nxt not in (start, goal):
                continue

            new_state = (current, nxt)
            smooth_cost = turn_penalty(nodes, prev_id, current, nxt)
            new_cost = cost_so_far[state] + edge_cost + smooth_cost

            if new_state not in cost_so_far or new_cost < cost_so_far[new_state]:
                cost_so_far[new_state] = new_cost
                priority = new_cost + haversine(nodes[nxt], nodes[goal])
                heapq.heappush(pq, (priority, new_cost, new_state))
                came_from[new_state] = state

    return [], float("inf")


def reconstruct_path(came_from, start_state, goal_state):
    states = [goal_state]
    current = goal_state

    while current != start_state:
        current = came_from[current]
        states.append(current)

    states.reverse()
    return [state[1] for state in states]


def path_distance(path, nodes):
    total = 0
    for a, b in zip(path, path[1:]):
        total += haversine(nodes[a], nodes[b])
    return total


def smooth_path(path, nodes):
    if len(path) <= 2:
        return path

    smoothed = [path[0]]

    for i in range(1, len(path) - 1):
        prev_id = smoothed[-1]
        cur_id = path[i]
        next_id = path[i + 1]
        prev_node = nodes[prev_id]
        cur_node = nodes[cur_id]
        next_node = nodes[next_id]

        road_changes = (
            display_road(cur_node) != display_road(prev_node)
            or display_road(cur_node) != display_road(next_node)
        )
        important_node = cur_node.get("type") == "house"
        sharp_turn = turn_amount(prev_node, cur_node, next_node) >= 28
        long_skip = haversine(prev_node, next_node) > 85

        if road_changes or important_node or sharp_turn or long_skip:
            smoothed.append(cur_id)

    smoothed.append(path[-1])
    return smoothed


def bearing(a, b):
    lat1 = math.radians(a["lat"])
    lat2 = math.radians(b["lat"])
    dlon = math.radians(b["lon"] - a["lon"])

    x = math.sin(dlon) * math.cos(lat2)
    y = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    )
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def turn_text(prev_bearing, next_bearing):
    diff = (next_bearing - prev_bearing + 540) % 360 - 180
    amount = abs(diff)

    if amount < 20:
        return "continue straight"
    if amount < 45:
        return "slight right" if diff > 0 else "slight left"
    if amount < 120:
        return "turn right" if diff > 0 else "turn left"
    return "sharp right" if diff > 0 else "sharp left"


def node_label(nid, node):
    house = node.get("house")
    if node.get("type") == "house" and house:
        return f"{nid} house {house}"
    if node.get("way_role") == "house_stop" and house:
        return f"{nid} sidewalk stop for house {house}"
    return nid


def display_road(node):
    if node.get("type") == "house":
        return node.get("street") or node.get("road")
    return node.get("road")


def normalize_address_query(raw):
    text = " ".join(str(raw).strip().split())
    if not text:
        return None

    parts = text.split(" ", 1)
    if not parts[0].isdigit() or len(parts) != 2:
        return None

    return parts[0], normalize_street_query(parts[1])


def normalize_street_query(street):
    abbreviations = {
        "se": "southeast",
        "st": "street",
        "pl": "place",
        "ave": "avenue",
        "ct": "court",
        "dr": "drive",
        "ln": "lane",
        "wy": "way",
        "blvd": "boulevard",
    }
    cleaned = str(street).lower().replace(".", " ").replace(",", " ")
    return " ".join(abbreviations.get(part, part) for part in cleaned.split())


def edge_lookup(edges):
    lookup = {}
    for edge in edges:
        a, b = edge[:2]
        lookup[tuple(sorted((a, b)))] = edge
    return lookup


def route_health(path, nodes, edges_by_pair):
    warnings = []
    if not path:
        return warnings

    for nid in path[1:-1]:
        if not is_sidewalk_node(nodes[nid]):
            warnings.append(f"Non-sidewalk intermediate node {nid} ({nodes[nid].get('type')})")

    helper_count = 0
    long_house_connectors = []
    for a, b in zip(path, path[1:]):
        edge = edges_by_pair.get(tuple(sorted((a, b))))
        if not edge:
            warnings.append(f"Missing edge metadata for {a}->{b}")
            continue
        kind = edge[3] if len(edge) > 3 else "way"
        dist = edge[2]
        if kind in {"intersection", "crosswalk_transfer", "osm_gap", "inferred_crosswalk"}:
            helper_count += 1
        if kind == "house_access" and dist > 30:
            long_house_connectors.append((a, b, dist))

    if helper_count:
        warnings.append(f"Uses {helper_count} sidewalk transfer(s)")
    for a, b, dist in long_house_connectors:
        warnings.append(f"Long house connector {a}->{b}: {dist:.1f} m")

    return warnings


def edge_kind(a, b, edges_by_pair):
    edge = edges_by_pair.get(tuple(sorted((a, b))))
    if not edge:
        return "missing"
    return edge[3] if len(edge) > 3 else "way"


def segment_type_for_edge(kind):
    if kind in SIDEWALK_SEGMENT_EDGE_KINDS:
        return "sidewalk"
    if kind in DRIVEWAY_SEGMENT_EDGE_KINDS:
        return "driveway"
    if kind in CROSSWALK_SEGMENT_EDGE_KINDS:
        return "crosswalk"
    return "crosswalk"


def split_route_segments(path, edges_by_pair):
    if len(path) < 2:
        return []

    raw_segments = []
    current_type = None
    current_nodes = []
    current_edge_kinds = []

    for a, b in zip(path, path[1:]):
        kind = edge_kind(a, b, edges_by_pair)
        seg_type = segment_type_for_edge(kind)

        if current_type != seg_type:
            if current_nodes:
                raw_segments.append(
                    {
                        "type": current_type,
                        "nodes": current_nodes,
                        "edge_kinds": current_edge_kinds,
                    }
                )
            current_type = seg_type
            current_nodes = [a, b]
            current_edge_kinds = [kind]
        else:
            current_nodes.append(b)
            current_edge_kinds.append(kind)

    if current_nodes:
        raw_segments.append(
            {
                "type": current_type,
                "nodes": current_nodes,
                "edge_kinds": current_edge_kinds,
            }
        )

    return raw_segments


def segment_distance(node_ids, nodes):
    return sum(haversine(nodes[a], nodes[b]) for a, b in zip(node_ids, node_ids[1:]))


def coords_for_nodes(node_ids, nodes):
    return [[nodes[nid]["lat"], nodes[nid]["lon"]] for nid in node_ids]


def handoff_index(node_ids, nodes, alert_m):
    if len(node_ids) <= 1:
        return 0

    dist = 0
    for index in range(len(node_ids) - 1, 0, -1):
        dist += haversine(nodes[node_ids[index]], nodes[node_ids[index - 1]])
        if dist >= alert_m:
            return index - 1
    return 0


def build_segment_plan(path, nodes, edges_by_pair):
    raw_segments = split_route_segments(path, edges_by_pair)
    segments = []

    for index, segment in enumerate(raw_segments):
        node_ids = segment["nodes"]
        first = nodes[node_ids[0]]
        last = nodes[node_ids[-1]]
        next_segment = raw_segments[index + 1] if index + 1 < len(raw_segments) else None

        base = {
            "index": index + 1,
            "type": segment["type"],
            "road": display_road(first),
            "start_node": node_ids[0],
            "end_node": node_ids[-1],
            "nodes": node_ids,
            "coords": coords_for_nodes(node_ids, nodes),
            "distance_m": round(segment_distance(node_ids, nodes), 1),
            "edge_kinds": segment["edge_kinds"],
        }

        if segment["type"] == "sidewalk":
            alert_idx = None
            if next_segment and next_segment["type"] == "crosswalk":
                alert_idx = handoff_index(node_ids, nodes, HANDOFF_ALERT_M)
            base.update(
                {
                    "mode": "ai",
                    "instruction": "AI drives this sidewalk segment until the end node or handoff point.",
                    "handoff_alert_m": HANDOFF_ALERT_M if alert_idx is not None else None,
                    "handoff_alert_index": alert_idx,
                    "handoff_coord": (
                        [nodes[node_ids[alert_idx]]["lat"], nodes[node_ids[alert_idx]]["lon"]]
                        if alert_idx is not None
                        else None
                    ),
                }
            )
        else:
            base.update(
                {
                    "mode": "manual",
                    "instruction": "User manually drives this crosswalk/transfer segment; AI resumes near end_node.",
                    "start_coord": [first["lat"], first["lon"]],
                    "end_coord": [last["lat"], last["lon"]],
                    "resume_radius_m": RESUME_RADIUS_M,
                }
            )

        segments.append(base)

    return segments


def segment_plan_summary(segments):
    if not segments:
        return ["SEGMENT PLAN: no route"]

    lines = ["SEGMENT PLAN:"]
    for segment in segments:
        if segment["type"] == "sidewalk":
            mode = "AI SIDEWALK"
            extra = ""
            if segment.get("handoff_coord"):
                extra = f", handoff alert at {segment['nodes'][segment['handoff_alert_index']]}"
        else:
            mode = "MANUAL CROSSWALK"
            extra = f", resume within {segment['resume_radius_m']:.1f} m of {segment['end_node']}"

        lines.append(
            f"{segment['index']}. {mode}: {segment['start_node']} -> {segment['end_node']} "
            f"on {segment['road']} ({segment['distance_m']:.1f} m{extra})"
        )

    return lines


def directions(path, nodes, total_dist, edges_by_pair=None):
    if not path:
        return ["NO PATH FOUND"]
    edges_by_pair = edges_by_pair or {}

    route_path = smooth_path(path, nodes)
    steps = []
    start = nodes[route_path[0]]
    goal = nodes[route_path[-1]]
    steps.append(f"START at {node_label(route_path[0], start)} on {display_road(start)}")

    prev_bearing = None
    prev_road = display_road(start)
    last_house = start.get("house")

    for i in range(1, len(route_path)):
        prev_id = route_path[i - 1]
        cur_id = route_path[i]
        prev = nodes[prev_id]
        cur = nodes[cur_id]

        segment_dist = haversine(prev, cur)
        cur_bearing = bearing(prev, cur)
        road = display_road(cur)

        if road != prev_road:
            if prev_bearing is None:
                steps.append(f"Enter {road} at {cur_id} and continue {segment_dist:.1f} m")
            else:
                steps.append(
                    f"{turn_text(prev_bearing, cur_bearing).capitalize()} onto {road} "
                    f"at {cur_id}, then continue {segment_dist:.1f} m"
                )
            prev_road = road
        else:
            if prev_bearing is not None:
                turn = turn_text(prev_bearing, cur_bearing)
                if turn != "continue straight":
                    steps.append(f"{turn.capitalize()} at {cur_id}, continue on {road}")

        house = cur.get("house")
        if house and house != last_house:
            steps.append(f"Pass house {house} at node {cur_id}")
            last_house = house

        prev_bearing = cur_bearing

    steps.append(f"ARRIVE at {node_label(route_path[-1], goal)} on {display_road(goal)}")
    steps.append(f"TOTAL DISTANCE: {total_dist:.1f} m")
    warnings = route_health(path, nodes, edges_by_pair)
    if warnings:
        steps.append("ROUTE HEALTH:")
        steps.extend(f"- {warning}" for warning in warnings)
    steps.append("CHECKPOINT PATH: " + " -> ".join(route_path))
    if route_path != path:
        steps.append("RAW PATH: " + " -> ".join(path))
    return steps


def resolve_target(raw, nodes):
    if raw.upper() == "HOME":
        return HOME

    if raw in nodes:
        return raw

    address_query = normalize_address_query(raw)
    if address_query:
        house_number, street = address_query
        matches = [
            nid
            for nid, node in nodes.items()
            if (
                node.get("type") == "house"
                and str(node.get("house")) == house_number
                and normalize_street_query(node.get("street") or node.get("road") or "") == street
            )
        ]

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:
            print(f"Address {raw} matched multiple nodes:")
            for nid in matches[:20]:
                node = nodes[nid]
                print(f"  {nid}: {node.get('house')} on {node.get('street') or node.get('road')}")
            print("Use one of those node IDs to choose the exact house.")
            sys.exit(1)

        print(f"Could not find address: {raw}")
        sys.exit(1)

    matches = [
        nid
        for nid, node in nodes.items()
        if node.get("type") == "house" and str(node.get("house")) == raw
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        print(f"House number {raw} matched multiple nodes:")
        for nid in matches[:20]:
            node = nodes[nid]
            print(f"  {nid}: {node.get('house')} on {node.get('road')}")
        print("Use one of those node IDs to choose the exact house.")
        sys.exit(1)

    print(f"Could not find node ID or house number: {raw}")
    sys.exit(1)


def nearest_sidewalk_node(nid, nodes):
    source = nodes[nid]
    best_id = None
    best_dist = float("inf")

    for candidate_id, candidate in nodes.items():
        if not is_sidewalk_node(candidate):
            continue

        dist = haversine(source, candidate)
        if dist < best_dist:
            best_id = candidate_id
            best_dist = dist

    return best_id, best_dist


def snap_endpoint_to_sidewalk(nid, nodes, verbose=True):
    node = nodes[nid]
    if node.get("type") == "house":
        stop_id = node.get("stop_for_house")
        if stop_id and stop_id in nodes:
            if verbose:
                print(f"STOP {nid} house -> {stop_id} sidewalk stop")
            return stop_id, nid
    if is_sidewalk_node(node):
        return nid, None

    sidewalk_id, dist = nearest_sidewalk_node(nid, nodes)
    if sidewalk_id is None:
        print(f"No sidewalk node exists near {nid}.")
        sys.exit(1)

    if verbose:
        print(f"SNAP {nid} ({node.get('type')}) -> {sidewalk_id} sidewalk ({dist:.1f} m)")
    return sidewalk_id, nid


def parse_args():
    parser = argparse.ArgumentParser(
        description="Plan a Trossachs sidewalk route with A*."
    )
    parser.add_argument("start", help='Start node ID, house number, HOME, or quoted address like "2059 264th Pl SE"')
    parser.add_argument("goal", help='Goal node ID, house number, or quoted address like "2028 263rd Pl SE"')
    parser.add_argument(
        "--human",
        action="store_true",
        help="Print only the human-readable SEGMENT PLAN.",
    )
    parser.add_argument(
        "--robot",
        action="store_true",
        help="Print only the machine-readable SEGMENT_PLAN_JSON.",
    )
    return parser.parse_args()


def robot_payload(start_input, goal_input, start, goal, total_dist, segments):
    return {
        "start_input": start_input,
        "goal_input": goal_input,
        "start_node": start,
        "goal_node": goal,
        "total_distance_m": round(total_dist, 1) if math.isfinite(total_dist) else None,
        "car_average_speed_mph": 4.0,
        "segments": segments,
    }


def main():
    args = parse_args()
    selected_output = args.human or args.robot
    verbose_snap = not selected_output

    with open(GRAPH_FILE) as f:
        data = json.load(f)

    global HOME
    if data.get("home_candidates"):
        HOME = data["home_candidates"][0]

    nodes = data["nodes"]
    edges = data["edges"]
    graph = build_graph(edges, nodes)
    edges_by_pair = edge_lookup(edges)

    start_raw = resolve_target(args.start, nodes)
    goal_raw = resolve_target(args.goal, nodes)
    start, _ = snap_endpoint_to_sidewalk(start_raw, nodes, verbose=verbose_snap)
    goal, _ = snap_endpoint_to_sidewalk(goal_raw, nodes, verbose=verbose_snap)

    if not selected_output:
        print(f"START INPUT {args.start} -> {start}")
        print(f"GOAL INPUT {args.goal} -> {goal}")

    path, total_dist = astar(graph, nodes, start, goal)

    segments = build_segment_plan(path, nodes, edges_by_pair)
    payload = robot_payload(args.start, args.goal, start, goal, total_dist, segments)

    if args.human:
        print("\n".join(segment_plan_summary(segments)))

    if args.robot:
        print(json.dumps(payload, indent=2))

    if selected_output:
        return

    print("\n".join(directions(path, nodes, total_dist, edges_by_pair)))
    print()
    print("\n".join(segment_plan_summary(segments)))
    print()
    print("SEGMENT_PLAN_JSON:")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
