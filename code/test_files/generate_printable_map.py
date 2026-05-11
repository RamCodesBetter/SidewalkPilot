import html
import json
import math
from collections import Counter, defaultdict

GRAPH_FILE = "trossachs_nav_graph.json"
OUTPUT_FILE = "trossachs_printable_map.svg"

WIDTH = 7200
HEIGHT = 5400
PADDING = 380


def load_graph():
    with open(GRAPH_FILE) as f:
        return json.load(f)


def graph_bounds(nodes):
    lats = [node["lat"] for node in nodes.values()]
    lons = [node["lon"] for node in nodes.values()]
    return min(lons), min(lats), max(lons), max(lats)


def haversine(a, b):
    radius_m = 6371000
    lat1, lon1 = math.radians(a[1]), math.radians(a[0])
    lat2, lon2 = math.radians(b[1]), math.radians(b[0])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    x = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius_m * math.asin(math.sqrt(x))


def project(lon, lat, bounds):
    min_lon, min_lat, max_lon, max_lat = bounds
    graph_w = max_lon - min_lon
    graph_h = max_lat - min_lat
    usable_w = WIDTH - PADDING * 2
    usable_h = HEIGHT - PADDING * 2
    scale = min(usable_w / graph_w, usable_h / graph_h)
    map_w = graph_w * scale
    map_h = graph_h * scale
    x_offset = (WIDTH - map_w) / 2
    y_offset = (HEIGHT - map_h) / 2
    return x_offset + (lon - min_lon) * scale, y_offset + (max_lat - lat) * scale


def node_color(node_type):
    if node_type == "house":
        return "#c77700"
    if node_type == "footway":
        return "#2374d1"
    if node_type in {"path", "track", "cycleway", "steps"}:
        return "#168a46"
    if node_type in {"residential", "service", "tertiary", "unclassified", "primary"}:
        return "#475569"
    return "#64748b"


def edge_style(a, b):
    types = {a["type"], b["type"]}
    if "house" in types:
        return "#f59e0b", 2.0, "2 7", 0.72
    if "footway" in types:
        return "#2b7bd8", 3.0, "", 0.86
    if types & {"path", "track", "cycleway", "steps"}:
        return "#1c9b50", 3.0, "10 7", 0.84
    return "#475569", 5.0, "", 0.9


def road_label_points(nodes):
    groups = defaultdict(list)
    for nid, node in nodes.items():
        road = node["road"]
        if road and road != "unnamed":
            groups[road].append((nid, node))

    labels = []
    for road, values in groups.items():
        if len(values) < 5:
            continue
        lon = sum(node["lon"] for _, node in values) / len(values)
        lat = sum(node["lat"] for _, node in values) / len(values)
        labels.append((road, lon, lat, len(values)))

    labels.sort(key=lambda item: item[3], reverse=True)
    return labels[:90]


def house_labels(nodes):
    interesting = {"2019", "2028"}
    labels = []
    for nid, node in nodes.items():
        if node["type"] == "house" and node.get("house") in interesting:
            labels.append((nid, node))
    return labels


def scale_bar(bounds):
    min_lon, min_lat, max_lon, max_lat = bounds
    mid_lat = (min_lat + max_lat) / 2
    graph_width_m = haversine((min_lon, mid_lat), (max_lon, mid_lat))
    map_left, _ = project(min_lon, mid_lat, bounds)
    map_right, _ = project(max_lon, mid_lat, bounds)
    px_per_m = (map_right - map_left) / graph_width_m
    meters = 250
    width_px = meters * px_per_m
    return meters, width_px


def make_svg(data):
    nodes = data["nodes"]
    bounds = graph_bounds(nodes)
    road_counts = Counter(node["road"] for node in nodes.values())

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="High resolution Trossachs navigation graph">',
        "<defs>",
        '<filter id="labelShadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="1" stdDeviation="1.2" flood-color="#ffffff" flood-opacity="0.95"/></filter>',
        '<marker id="arrow" markerWidth="8" markerHeight="8" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#ef4444"/></marker>',
        "</defs>",
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#172033;letter-spacing:0}",
        ".title{font-size:72px;font-weight:800}.subtitle{font-size:32px;fill:#475569}",
        ".road-label{font-size:31px;font-weight:760;paint-order:stroke;stroke:#fff;stroke-width:8;stroke-linejoin:round}",
        ".house-label{font-size:28px;font-weight:850;paint-order:stroke;stroke:#fff;stroke-width:8;stroke-linejoin:round}",
        ".grid-label{font-size:22px;fill:#94a3b8}.legend{font-size:31px}.small{font-size:26px;fill:#475569}",
        "</style>",
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
    ]

    # Grid.
    for i in range(9):
        x = PADDING + i * (WIDTH - PADDING * 2) / 8
        parts.append(f'<line x1="{x:.1f}" y1="{PADDING}" x2="{x:.1f}" y2="{HEIGHT - PADDING}" stroke="#e2e8f0" stroke-width="1"/>')
        parts.append(f'<text class="grid-label" x="{x + 6:.1f}" y="{PADDING - 16}">{chr(65 + i)}</text>')
    for i in range(7):
        y = PADDING + i * (HEIGHT - PADDING * 2) / 6
        parts.append(f'<line x1="{PADDING}" y1="{y:.1f}" x2="{WIDTH - PADDING}" y2="{y:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        parts.append(f'<text class="grid-label" x="{PADDING - 34}" y="{y - 6:.1f}">{i + 1}</text>')

    # Roads/paths with casing.
    for a_id, b_id, _ in data["edges"]:
        if a_id not in nodes or b_id not in nodes:
            continue
        a = nodes[a_id]
        b = nodes[b_id]
        x1, y1 = project(a["lon"], a["lat"], bounds)
        x2, y2 = project(b["lon"], b["lat"], bounds)
        color, width, dash, opacity = edge_style(a, b)
        casing = width + 3.0
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#ffffff" stroke-width="{casing:.1f}" stroke-linecap="round" opacity="0.92"/>')
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width:.1f}" stroke-linecap="round" opacity="{opacity}"{dash_attr}/>')

    # Nodes by type.
    for nid, node in nodes.items():
        x, y = project(node["lon"], node["lat"], bounds)
        radius = 6.2 if node["type"] == "house" else 3.5
        stroke = "#ffffff" if node["type"] == "house" else "none"
        stroke_width = 2.2 if node["type"] == "house" else 0
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{node_color(node["type"])}" stroke="{stroke}" stroke-width="{stroke_width}" opacity="0.94"><title>{html.escape(nid)} | {html.escape(node["road"])} | {html.escape(str(node.get("house") or ""))}</title></circle>')

    # Road labels.
    for road, lon, lat, count in road_label_points(nodes):
        x, y = project(lon, lat, bounds)
        if road_counts[road] >= 20:
            parts.append(f'<text class="road-label" x="{x:.1f}" y="{y:.1f}" text-anchor="middle" filter="url(#labelShadow)">{html.escape(road)}</text>')

    # Special house/node labels.
    for nid, node in house_labels(nodes):
        x, y = project(node["lon"], node["lat"], bounds)
        text = f'{nid}  {node["house"]} {node.get("street") or node["road"]}'
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="16" fill="#ef4444" stroke="#fff" stroke-width="5"/>')
        parts.append(f'<text class="house-label" x="{x + 22:.1f}" y="{y - 20:.1f}">{html.escape(text)}</text>')

    # Title and scale.
    parts.append('<text class="title" x="150" y="120">Trossachs Navigation Graph</text>')
    parts.append(f'<text class="subtitle" x="150" y="172">{len(nodes):,} nodes, {len(data["edges"]):,} graph edges, address and sidewalk routing layer</text>')

    meters, bar_width = scale_bar(bounds)
    sx = WIDTH - 780
    sy = HEIGHT - 205
    parts.append(f'<rect x="{sx - 44}" y="{sy - 86}" width="600" height="190" fill="#ffffff" stroke="#cbd5e1" rx="12" opacity="0.96"/>')
    parts.append(f'<line x1="{sx}" y1="{sy}" x2="{sx + bar_width:.1f}" y2="{sy}" stroke="#0f172a" stroke-width="13" stroke-linecap="butt"/>')
    parts.append(f'<line x1="{sx}" y1="{sy - 20}" x2="{sx}" y2="{sy + 20}" stroke="#0f172a" stroke-width="6"/>')
    parts.append(f'<line x1="{sx + bar_width:.1f}" y1="{sy - 20}" x2="{sx + bar_width:.1f}" y2="{sy + 20}" stroke="#0f172a" stroke-width="6"/>')
    parts.append(f'<text class="legend" x="{sx}" y="{sy + 66}">{meters} m</text>')
    parts.append(f'<text class="small" x="{sx}" y="{sy - 38}">Print scale guide</text>')

    # Legend.
    lx = 150
    ly = HEIGHT - 240
    legend = [
        ("#c77700", "House"),
        ("#2374d1", "Footway / sidewalk"),
        ("#168a46", "Path / trail"),
        ("#475569", "Road / service"),
        ("#ef4444", "Highlighted home/destination addresses"),
    ]
    parts.append(f'<rect x="{lx - 48}" y="{ly - 70}" width="900" height="230" fill="#ffffff" stroke="#cbd5e1" rx="12" opacity="0.96"/>')
    for idx, (color, text) in enumerate(legend):
        x = lx + (idx % 2) * 430
        y = ly + (idx // 2) * 64
        parts.append(f'<circle cx="{x}" cy="{y}" r="13" fill="{color}"/>')
        parts.append(f'<text class="legend" x="{x + 32}" y="{y + 11}">{html.escape(text)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    data = load_graph()
    svg = make_svg(data)
    with open(OUTPUT_FILE, "w") as f:
        f.write(svg)
    print(f"Wrote {OUTPUT_FILE}")
    print(f"Nodes: {len(data['nodes'])}")
    print(f"Edges: {len(data['edges'])}")


if __name__ == "__main__":
    main()
