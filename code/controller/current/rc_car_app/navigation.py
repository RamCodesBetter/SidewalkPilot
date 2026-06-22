#!/usr/bin/python3
from __future__ import annotations

import heapq
import json
import math
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import serial
except ImportError:
    serial = None

GRAPH_PATH = Path(__file__).resolve().parent / "trossachs_nav_graph.json"
GPS_PORT = "/dev/ttyAMA0"
GPS_BAUD = 9600
NODE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
ARRIVED_RADIUS_M = 3.0
ARRIVED_MESSAGE_SEC = 5.0
NAV_ENTRY_ERROR_SEC = 2.0
NAV_TIME_UPDATE_SEC = 0.5
NAV_TIME_SPEED_ALPHA = 0.12
HANDOFF_ALERT_M = 3.0
RESUME_RADIUS_M = 2.5
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
# House<->sidewalk connectors are NOT drivable sidewalk. They only mark where to
# stop on the sidewalk in front of a house's driveway; the car never drives the
# connector/driveway. Labeled "driveway" and handled manually, never AUTO.
DRIVEWAY_SEGMENT_EDGE_KINDS = {"house_access", "house_access_fallback"}
CROSSWALK_SEGMENT_EDGE_KINDS = {
    "crosswalk",
    "intersection",
    "crosswalk_transfer",
    "osm_gap",
    "inferred_crosswalk",
}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def haversine(a: Dict[str, object], b: Dict[str, object]) -> float:
    radius_m = 6371000.0
    lat1 = math.radians(_safe_float(a.get("lat")))
    lon1 = math.radians(_safe_float(a.get("lon")))
    lat2 = math.radians(_safe_float(b.get("lat")))
    lon2 = math.radians(_safe_float(b.get("lon")))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    x = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    return 2.0 * radius_m * math.asin(math.sqrt(x))


def is_sidewalk_node(node: Dict[str, object]) -> bool:
    return node.get("type") in SIDEWALK_TYPES


def is_crosswalk_node(node: Dict[str, object]) -> bool:
    return node.get("type") == "crosswalk" or node.get("way_role") == "crosswalk"


def is_crosswalk_endpoint(node: Dict[str, object]) -> bool:
    return not is_crosswalk_node(node) or bool(node.get("crosswalk_endpoint"))


def display_road(node: Dict[str, object]) -> str:
    if node.get("type") == "house":
        return str(node.get("street") or node.get("road") or "")
    return str(node.get("road") or "")


def helper_edge_allowed(kind: str, a_node: Dict[str, object], b_node: Dict[str, object]) -> bool:
    if not is_crosswalk_endpoint(a_node) or not is_crosswalk_endpoint(b_node):
        return False
    if kind not in {"intersection", "osm_gap"}:
        return True
    same_road = display_road(a_node) == display_road(b_node)
    touches_crosswalk = is_crosswalk_node(a_node) or is_crosswalk_node(b_node)
    return same_road or touches_crosswalk


def edge_allowed(edge: List[object], nodes: Dict[str, Dict[str, object]]) -> bool:
    if len(edge) < 3:
        return False
    a, b = str(edge[0]).upper(), str(edge[1]).upper()
    if a not in nodes or b not in nodes:
        return False
    kind = str(edge[3]) if len(edge) > 3 else "way"
    if kind in {"sidewalk", "crosswalk", "sidewalk_split", "inferred_crosswalk"}:
        return is_sidewalk_node(nodes[a]) and is_sidewalk_node(nodes[b])
    if kind in {"intersection", "crosswalk_transfer", "osm_gap"}:
        return (
            is_sidewalk_node(nodes[a])
            and is_sidewalk_node(nodes[b])
            and helper_edge_allowed(kind, nodes[a], nodes[b])
        )
    if kind in {"house_access", "house_access_fallback"}:
        return (
            nodes[a].get("type") == "house"
            and is_sidewalk_node(nodes[b])
            or nodes[b].get("type") == "house"
            and is_sidewalk_node(nodes[a])
        )
    return False


def edge_cost(edge: List[object], nodes: Dict[str, Dict[str, object]]) -> float:
    dist = _safe_float(edge[2], 1.0)
    kind = str(edge[3]) if len(edge) > 3 else "way"
    if kind == "crosswalk_transfer":
        return dist + 220.0
    if kind == "inferred_crosswalk":
        return dist + 36.0
    if kind in {"intersection", "osm_gap"}:
        return dist + 48.0
    return dist


def build_graph(nodes: Dict[str, Dict[str, object]], edges: List[List[object]]) -> Dict[str, List[Tuple[str, float]]]:
    graph: Dict[str, List[Tuple[str, float]]] = {}
    for edge in edges:
        if not edge_allowed(edge, nodes):
            continue
        a, b = str(edge[0]).upper(), str(edge[1]).upper()
        cost = edge_cost(edge, nodes)
        graph.setdefault(a, []).append((b, cost))
        graph.setdefault(b, []).append((a, cost))
    return graph


def bearing(a: Dict[str, object], b: Dict[str, object]) -> float:
    lat1 = math.radians(_safe_float(a.get("lat")))
    lat2 = math.radians(_safe_float(b.get("lat")))
    dlon = math.radians(_safe_float(b.get("lon")) - _safe_float(a.get("lon")))
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def turn_amount(prev_node: Dict[str, object], current_node: Dict[str, object], next_node: Dict[str, object]) -> float:
    before = bearing(prev_node, current_node)
    after = bearing(current_node, next_node)
    return abs((after - before + 540.0) % 360.0 - 180.0)


def turn_penalty(nodes: Dict[str, Dict[str, object]], prev_id: Optional[str], current_id: str, next_id: str) -> float:
    if prev_id is None:
        return 0.0
    amount = turn_amount(nodes[prev_id], nodes[current_id], nodes[next_id])
    if amount < 25.0:
        return 0.0
    if amount < 45.0:
        return 3.0
    if amount < 90.0:
        return 10.0
    if amount < 135.0:
        return 24.0
    return 44.0


def reconstruct_path(
    came_from: Dict[Tuple[Optional[str], str], Tuple[Optional[str], str]],
    start_state: Tuple[Optional[str], str],
    goal_state: Tuple[Optional[str], str],
) -> List[str]:
    states = [goal_state]
    current = goal_state
    while current != start_state:
        current = came_from[current]
        states.append(current)
    states.reverse()
    return [state[1] for state in states]


def astar(
    graph: Dict[str, List[Tuple[str, float]]],
    nodes: Dict[str, Dict[str, object]],
    start: str,
    goal: str,
) -> Tuple[List[str], float]:
    if start not in nodes or goal not in nodes:
        return [], float("inf")
    start_state = (None, start)
    counter = 0
    pq = [(0.0, 0.0, counter, start_state)]
    came_from: Dict[Tuple[Optional[str], str], Tuple[Optional[str], str]] = {}
    cost_so_far = {start_state: 0.0}
    while pq:
        _, current_cost, _, state = heapq.heappop(pq)
        prev_id, current = state
        if current == goal:
            path = reconstruct_path(came_from, start_state, state)
            return path, path_distance(path, nodes)
        if current_cost > cost_so_far.get(state, float("inf")):
            continue
        for nxt, step_cost in graph.get(current, []):
            if nodes[nxt].get("type") == "house" and nxt not in (start, goal):
                continue
            new_state = (current, nxt)
            new_cost = cost_so_far[state] + step_cost + turn_penalty(nodes, prev_id, current, nxt)
            if new_cost < cost_so_far.get(new_state, float("inf")):
                cost_so_far[new_state] = new_cost
                priority = new_cost + haversine(nodes[nxt], nodes[goal])
                counter += 1
                heapq.heappush(pq, (priority, new_cost, counter, new_state))
                came_from[new_state] = state
    return [], float("inf")


def path_distance(path: List[str], nodes: Dict[str, Dict[str, object]]) -> float:
    return sum(haversine(nodes[a], nodes[b]) for a, b in zip(path, path[1:]))


def edge_lookup(edges: List[List[object]]) -> Dict[Tuple[str, str], List[object]]:
    lookup: Dict[Tuple[str, str], List[object]] = {}
    for edge in edges:
        if len(edge) >= 2:
            a, b = str(edge[0]).upper(), str(edge[1]).upper()
            lookup[tuple(sorted((a, b)))] = edge
    return lookup


def edge_kind(a: str, b: str, edges_by_pair: Dict[Tuple[str, str], List[object]]) -> str:
    edge = edges_by_pair.get(tuple(sorted((a, b))))
    if not edge:
        return "missing"
    return str(edge[3]) if len(edge) > 3 else "way"


def segment_type_for_edge(kind: str) -> str:
    if kind in SIDEWALK_SEGMENT_EDGE_KINDS:
        return "sidewalk"
    if kind in DRIVEWAY_SEGMENT_EDGE_KINDS:
        return "driveway"
    if kind in CROSSWALK_SEGMENT_EDGE_KINDS:
        return "crosswalk"
    return "crosswalk"


def split_route_segments(path: List[str], edges_by_pair: Dict[Tuple[str, str], List[object]]) -> List[Dict[str, object]]:
    if len(path) < 2:
        return []
    raw_segments: List[Dict[str, object]] = []
    current_type: Optional[str] = None
    current_nodes: List[str] = []
    current_edge_kinds: List[str] = []
    start_path_index = 0
    current_start_index = 0
    for path_index, (a, b) in enumerate(zip(path, path[1:])):
        kind = edge_kind(a, b, edges_by_pair)
        seg_type = segment_type_for_edge(kind)
        if current_type != seg_type:
            if current_nodes:
                raw_segments.append(
                    {
                        "type": current_type,
                        "nodes": current_nodes,
                        "edge_kinds": current_edge_kinds,
                        "start_path_index": current_start_index,
                        "end_path_index": path_index,
                    }
                )
            current_type = seg_type
            current_nodes = [a, b]
            current_edge_kinds = [kind]
            current_start_index = start_path_index
        else:
            current_nodes.append(b)
            current_edge_kinds.append(kind)
        start_path_index = path_index + 1
    if current_nodes:
        raw_segments.append(
            {
                "type": current_type,
                "nodes": current_nodes,
                "edge_kinds": current_edge_kinds,
                "start_path_index": current_start_index,
                "end_path_index": len(path) - 1,
            }
        )
    return raw_segments


def segment_distance(node_ids: List[str], nodes: Dict[str, Dict[str, object]]) -> float:
    return sum(haversine(nodes[a], nodes[b]) for a, b in zip(node_ids, node_ids[1:]))


def handoff_index(node_ids: List[str], nodes: Dict[str, Dict[str, object]], alert_m: float) -> int:
    if len(node_ids) <= 1:
        return 0
    dist = 0.0
    for index in range(len(node_ids) - 1, 0, -1):
        dist += haversine(nodes[node_ids[index]], nodes[node_ids[index - 1]])
        if dist >= alert_m:
            return index - 1
    return 0


def build_segment_plan(
    path: List[str],
    nodes: Dict[str, Dict[str, object]],
    edges_by_pair: Dict[Tuple[str, str], List[object]],
) -> List[Dict[str, object]]:
    raw_segments = split_route_segments(path, edges_by_pair)
    segments: List[Dict[str, object]] = []
    for index, segment in enumerate(raw_segments):
        node_ids = list(segment["nodes"])
        next_segment = raw_segments[index + 1] if index + 1 < len(raw_segments) else None
        base = {
            "index": index,
            "display_index": index + 1,
            "type": segment["type"],
            "mode": "ai" if segment["type"] == "sidewalk" else "manual",
            "operator": "AUTO" if segment["type"] == "sidewalk" else "MNUL",
            "road": display_road(nodes[node_ids[0]]),
            "start_node": node_ids[0],
            "end_node": node_ids[-1],
            "nodes": node_ids,
            "start_path_index": int(segment["start_path_index"]),
            "end_path_index": int(segment["end_path_index"]),
            "distance_m": round(segment_distance(node_ids, nodes), 1),
            "edge_kinds": list(segment["edge_kinds"]),
            "handoff_alert_m": None,
            "handoff_node": "",
            "resume_radius_m": None,
        }
        if segment["type"] == "sidewalk" and next_segment and next_segment["type"] == "crosswalk":
            alert_idx = handoff_index(node_ids, nodes, HANDOFF_ALERT_M)
            base["handoff_alert_m"] = HANDOFF_ALERT_M
            base["handoff_node"] = node_ids[alert_idx]
            base["handoff_path_index"] = int(segment["start_path_index"]) + alert_idx
        elif segment["type"] == "crosswalk":
            base["resume_radius_m"] = RESUME_RADIUS_M
        segments.append(base)
    return segments


def parse_nmea_gga(line: str) -> Optional[Dict[str, object]]:
    parts = line.strip().split(",")
    if len(parts) < 10 or parts[6] in ("", "0"):
        return {"fix": False}

    def dm_to_dd(dm: str, hemi: str) -> Optional[float]:
        if not dm or "." not in dm:
            return None
        dot = dm.index(".")
        deg = float(dm[: dot - 2])
        mins = float(dm[dot - 2 :])
        dd = deg + mins / 60.0
        return -dd if hemi in ("S", "W") else dd

    return {
        "lat": dm_to_dd(parts[2], parts[3]),
        "lon": dm_to_dd(parts[4], parts[5]),
        "fix": True,
        "sats": int(parts[7]) if parts[7] else 0,
        "alt": float(parts[9]) if parts[9] else None,
        "updated_at": time.time(),
    }


class GpsReader:
    def __init__(self, port: str = GPS_PORT, baud: int = GPS_BAUD):
        self.port = port
        self.baud = baud
        self.state: Dict[str, object] = {"lat": None, "lon": None, "fix": False, "sats": 0, "alt": None}
        self.lock = threading.Lock()
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        if serial is None:
            print("GPS disabled: pyserial is unavailable.")
            return False
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def get_state(self) -> Dict[str, object]:
        with self.lock:
            return dict(self.state)

    def _run(self) -> None:
        try:
            gps_serial = serial.Serial(self.port, self.baud, timeout=1)
            print(f"GPS connected on {self.port} @ {self.baud}.")
        except Exception as exc:
            print(f"GPS disabled: failed to open {self.port}: {exc}")
            self.running = False
            return
        while self.running:
            try:
                line = gps_serial.readline().decode("ascii", errors="ignore")
                if line.startswith(("$GPGGA", "$GNGGA")):
                    parsed = parse_nmea_gga(line)
                    if parsed:
                        with self.lock:
                            self.state.update(parsed)
            except Exception:
                time.sleep(0.1)


class NavigationManager:
    def __init__(self, graph_path: Path = GRAPH_PATH):
        self.graph_path = graph_path
        self.nodes: Dict[str, Dict[str, object]] = {}
        self.edges: List[List[object]] = []
        self.edge_kinds: Dict[Tuple[str, str], str] = {}
        self.edges_by_pair: Dict[Tuple[str, str], List[object]] = {}
        self.graph: Dict[str, List[Tuple[str, float]]] = {}
        self.available = False
        self.start_chars = ["A", "A", "A"]
        self.end_chars = ["A", "A", "A"]
        self.cursor = 0
        self.phase = "end"  # start is auto-filled from GPS; user only edits destination.
        self.confirm_yes = True
        self.active = False
        self.path: List[str] = []
        self.segments: List[Dict[str, object]] = []
        self.route_start_id = ""
        self.route_goal_id = ""
        self.destination_id = ""
        self.total_distance_m = 0.0
        self.arrived_until = 0.0
        self.arrived_node = ""
        self.entry_error_until = 0.0
        self.time_speed_mps = 0.0
        self.display_remaining_time_s = 0.0
        self.display_next_time_s = 0.0
        self.last_time_update = 0.0
        self.entry_error_until = 0.0
        self.load()

    def load(self) -> None:
        if not self.graph_path.exists():
            print(f"Navigation disabled: graph not found: {self.graph_path}")
            return
        data = json.loads(self.graph_path.read_text(encoding="utf-8"))
        self.nodes = {str(k).upper(): v for k, v in data.get("nodes", {}).items()}
        self.edges = data.get("edges", [])
        self.edges_by_pair = edge_lookup(self.edges)
        self.edge_kinds = {}
        for edge in self.edges:
            if len(edge) >= 4:
                self.edge_kinds[tuple(sorted((str(edge[0]).upper(), str(edge[1]).upper())))] = str(edge[3])
        self.graph = build_graph(self.nodes, self.edges)
        self.available = bool(self.nodes and self.graph)
        print(f"Navigation graph loaded: nodes={len(self.nodes)} edges={len(self.edges)}")

    def nearest_sidewalk_node(self, node_id: str) -> Tuple[str, float]:
        source = self.nodes[node_id]
        best_id = ""
        best_dist = float("inf")
        for candidate_id, candidate in self.nodes.items():
            if not is_sidewalk_node(candidate):
                continue
            dist = haversine(source, candidate)
            if dist < best_dist:
                best_id = candidate_id
                best_dist = dist
        return best_id, best_dist

    def snap_endpoint_to_sidewalk(self, node_id: str) -> Tuple[str, str]:
        """Use geojson_to_graph house links: route to a house's sidewalk stop."""
        node_id = node_id.upper()
        node = self.nodes[node_id]
        if node.get("type") == "house":
            stop_id = str(node.get("stop_for_house") or "").upper()
            if stop_id and stop_id in self.nodes:
                return stop_id, node_id
        if is_sidewalk_node(node):
            return node_id, ""
        sidewalk_id, _ = self.nearest_sidewalk_node(node_id)
        return sidewalk_id, node_id

    @property
    def start_id(self) -> str:
        return "".join(self.start_chars)

    @property
    def end_id(self) -> str:
        return "".join(self.end_chars)

    def reset_entry(self) -> None:
        self.cursor = 0
        self.phase = "end"   # skip start entry — start is always current GPS node
        self.confirm_yes = True
        self.active = False
        self.path = []
        self.segments = []
        self.route_start_id = ""
        self.route_goal_id = ""
        self.destination_id = ""
        self.total_distance_m = 0.0
        self.time_speed_mps = 0.0
        self.display_remaining_time_s = 0.0
        self.display_next_time_s = 0.0
        self.last_time_update = 0.0

    def set_start_from_gps(self, nearest_node_id: str) -> None:
        """Call this whenever GPS nearest node updates so start is always current position."""
        if nearest_node_id and nearest_node_id in self.nodes:
            self.start_chars = list((nearest_node_id.upper() + "AAA")[:3])

    def adjust_current(self, direction: int) -> None:
        if time.monotonic() < self.entry_error_until:
            return
        chars = self.end_chars  # only end is user-editable now
        idx = NODE_CHARS.index(chars[self.cursor]) if chars[self.cursor] in NODE_CHARS else 0
        chars[self.cursor] = NODE_CHARS[(idx + direction) % len(NODE_CHARS)]

    def move_cursor(self, direction: int) -> None:
        if time.monotonic() < self.entry_error_until or self.active:
            return
        self.cursor = (self.cursor + int(direction)) % len(self.end_chars)

    def advance(self) -> Optional[str]:
        if time.monotonic() < self.entry_error_until:
            return None
        return self.start_route()

    def start_route(self) -> Optional[str]:
        start_raw = self.start_id.upper()
        end_raw = self.end_id.upper()
        if not self.available or start_raw not in self.nodes or end_raw not in self.nodes:
            self.phase = "end"
            self.confirm_yes = True
            self.entry_error_until = time.monotonic() + NAV_ENTRY_ERROR_SEC
            return None
        start, _ = self.snap_endpoint_to_sidewalk(start_raw)
        end, final_destination = self.snap_endpoint_to_sidewalk(end_raw)
        if not start or not end:
            self.phase = "end"
            self.confirm_yes = True
            self.entry_error_until = time.monotonic() + NAV_ENTRY_ERROR_SEC
            return None
        path, distance_m = astar(self.graph, self.nodes, start, end)
        if not path:
            self.phase = "end"
            self.confirm_yes = True
            self.entry_error_until = time.monotonic() + NAV_ENTRY_ERROR_SEC
            return None
        self.path = path
        self.segments = build_segment_plan(path, self.nodes, self.edges_by_pair)
        self.route_start_id = start
        self.route_goal_id = end
        self.destination_id = final_destination or end_raw
        self.total_distance_m = distance_m
        self.active = True
        self.phase = "running"
        self.cursor = 0
        self.time_speed_mps = 0.0
        self.display_remaining_time_s = 0.0
        self.display_next_time_s = 0.0
        self.last_time_update = 0.0
        return self.operator_for_index(0, None, None)

    def nearest_node(self, lat: Optional[float], lon: Optional[float]) -> Tuple[str, float]:
        if lat is None or lon is None or not self.nodes:
            return "", 0.0
        point = {"lat": lat, "lon": lon}
        best_id = ""
        best_dist = float("inf")
        for node_id, node in self.nodes.items():
            if not is_sidewalk_node(node) and node.get("type") != "house":
                continue
            dist = haversine(point, node)
            if dist < best_dist:
                best_id = node_id
                best_dist = dist
        return best_id, best_dist

    def closest_path_index(self, lat: Optional[float], lon: Optional[float]) -> int:
        if not self.path or lat is None or lon is None:
            return 0
        point = {"lat": lat, "lon": lon}
        distances = [(haversine(point, self.nodes[node_id]), index) for index, node_id in enumerate(self.path)]
        return min(distances)[1]

    def edge_kind_for(self, a: str, b: str) -> str:
        return self.edge_kinds.get(tuple(sorted((a, b))), "")

    def segment_for_path_index(self, path_index: int) -> Optional[Dict[str, object]]:
        for segment in self.segments:
            if int(segment["start_path_index"]) <= path_index <= int(segment["end_path_index"]):
                return segment
        return self.segments[-1] if self.segments else None

    def next_segment_after(self, segment: Dict[str, object]) -> Optional[Dict[str, object]]:
        next_index = int(segment.get("index", -1)) + 1
        if 0 <= next_index < len(self.segments):
            return self.segments[next_index]
        return None

    def operator_for_index(self, index: int, lat: Optional[float], lon: Optional[float]) -> str:
        if not self.path:
            return "MNUL"
        segment = self.segment_for_path_index(index)
        if not segment:
            if index >= len(self.path) - 1:
                return "MNUL"
            kind = self.edge_kind_for(self.path[index], self.path[index + 1])
            return "AUTO" if kind in SIDEWALK_SEGMENT_EDGE_KINDS else "MNUL"
        if segment.get("type") == "sidewalk":
            handoff_node = str(segment.get("handoff_node") or "")
            if handoff_node and lat is not None and lon is not None:
                dist_to_handoff = haversine({"lat": lat, "lon": lon}, self.nodes[handoff_node])
                if dist_to_handoff <= HANDOFF_ALERT_M:
                    return "MNUL"
            return "AUTO"
        if segment.get("type") == "crosswalk":
            end_node = str(segment.get("end_node") or "")
            if end_node and lat is not None and lon is not None:
                dist_to_end = haversine({"lat": lat, "lon": lon}, self.nodes[end_node])
                next_segment = self.next_segment_after(segment)
                if dist_to_end <= RESUME_RADIUS_M and next_segment:
                    return str(next_segment.get("operator", "MNUL"))
            return "MNUL"
        return str(segment.get("operator", "MNUL"))

    def compact_segments(self) -> List[Dict[str, object]]:
        return [
            {
                "index": int(segment["display_index"]),
                "mode": segment["mode"],
                "operator": segment["operator"],
                "type": segment["type"],
                "start_node": segment["start_node"],
                "end_node": segment["end_node"],
                "distance_m": segment["distance_m"],
                "handoff_node": segment.get("handoff_node", ""),
                "resume_radius_m": segment.get("resume_radius_m"),
            }
            for segment in self.segments
        ]

    def update(self, gps_state: Dict[str, object], odometer_m: float, speed_mps: float) -> Dict[str, object]:
        lat = gps_state.get("lat")
        lon = gps_state.get("lon")
        fix = bool(gps_state.get("fix")) and lat is not None and lon is not None
        sats = int(gps_state.get("sats") or 0)
        closest, closest_dist = self.nearest_node(lat if fix else None, lon if fix else None)
        path_index = self.closest_path_index(lat if fix else None, lon if fix else None)
        fix_lat = float(lat) if fix and lat is not None else None
        fix_lon = float(lon) if fix and lon is not None else None

        prev_node = self.path[path_index - 1] if self.path and path_index > 0 else ""
        current_node = self.path[path_index] if self.path else closest
        next_node = self.path[path_index + 1] if self.path and path_index + 1 < len(self.path) else ""
        remaining_m = path_distance(self.path[path_index:], self.nodes) if self.path else 0.0
        next_dist_m = haversine(self.nodes[current_node], self.nodes[next_node]) if current_node and next_node else 0.0
        start_dist_m = self.total_distance_m - remaining_m if self.path else 0.0
        segment = self.segment_for_path_index(path_index)
        operator = self.operator_for_index(path_index, fix_lat, fix_lon) if self.path else "MNUL"
        handoff_node = str(segment.get("handoff_node") or "") if segment else ""
        handoff_distance_m = (
            haversine({"lat": fix_lat, "lon": fix_lon}, self.nodes[handoff_node])
            if handoff_node and fix_lat is not None and fix_lon is not None
            else 0.0
        )
        handoff_alert = bool(handoff_node and self.active and handoff_distance_m <= HANDOFF_ALERT_M)
        resume_node = str(segment.get("end_node") or "") if segment and segment.get("type") == "crosswalk" else ""
        resume_distance_m = (
            haversine({"lat": fix_lat, "lon": fix_lon}, self.nodes[resume_node])
            if resume_node and fix_lat is not None and fix_lon is not None
            else 0.0
        )
        resume_ready = bool(resume_node and resume_distance_m <= RESUME_RADIUS_M)

        now = time.monotonic()
        if self.active and speed_mps > 0.2:
            if self.time_speed_mps <= 0.0:
                self.time_speed_mps = speed_mps
            else:
                self.time_speed_mps = (NAV_TIME_SPEED_ALPHA * speed_mps) + ((1.0 - NAV_TIME_SPEED_ALPHA) * self.time_speed_mps)
        if self.active and self.time_speed_mps > 0.2 and now - self.last_time_update >= NAV_TIME_UPDATE_SEC:
            self.display_remaining_time_s = remaining_m / self.time_speed_mps
            self.display_next_time_s = next_dist_m / self.time_speed_mps
            self.last_time_update = now
        if not self.active:
            self.display_remaining_time_s = 0.0
            self.display_next_time_s = 0.0
        entry_error_visible = time.monotonic() < self.entry_error_until

        if self.active and remaining_m <= ARRIVED_RADIUS_M and self.path:
            self.active = False
            self.arrived_node = self.path[-1]
            self.arrived_until = time.monotonic() + ARRIVED_MESSAGE_SEC

        return {
            "available": self.available,
            "fix": fix,
            "sats": sats,
            "lat": float(lat) if lat is not None else 0.0,
            "lon": float(lon) if lon is not None else 0.0,
            "start_id": self.start_id,
            "end_id": self.end_id,
            "route_start_id": self.route_start_id,
            "route_goal_id": self.route_goal_id,
            "destination_id": self.destination_id,
            "entry_phase": self.phase,
            "entry_cursor": self.cursor,
            "entry_error": entry_error_visible,
            "confirm_yes": self.confirm_yes,
            "active": self.active,
            "operator": operator,
            "segment_index": int(segment["display_index"]) if segment else 0,
            "segment_mode": str(segment.get("mode", "")) if segment else "",
            "segment_type": str(segment.get("type", "")) if segment else "",
            "segments": self.compact_segments(),
            "handoff_alert": handoff_alert,
            "handoff_node": handoff_node,
            "handoff_distance_m": handoff_distance_m,
            "resume_node": resume_node,
            "resume_radius_m": RESUME_RADIUS_M if resume_node else 0.0,
            "resume_distance_m": resume_distance_m,
            "resume_ready": resume_ready,
            "previous_node": prev_node,
            "closest_node": current_node or closest,
            "next_node": next_node,
            "nearest_node": closest,
            "closest_distance_m": closest_dist,
            "remaining_distance_m": remaining_m,
            "next_node_distance_m": next_dist_m,
            "next_distance_m": next_dist_m,
            "start_distance_m": start_dist_m,
            "total_distance_m": self.total_distance_m,
            "remaining_time_s": self.display_remaining_time_s,
            "next_time_s": self.display_next_time_s,
            "odometer_m": odometer_m,
            "arrived_visible": time.monotonic() < self.arrived_until,
            "arrived_node": self.arrived_node,
        }
