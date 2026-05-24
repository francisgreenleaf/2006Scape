#!/usr/bin/env python3
"""Render movement topology from every recorded agent movement trace.

The renderer uses only Python standard-library code and the local navigation
helpers. It reads the accumulated movement JSONL logs, plots every tile the
player has stood on, and colors learned edges by trouble observed on that edge.
"""

import argparse
import json
import math
from pathlib import Path

from cache_world_map import draw_world_map, load_cache_world_map
from navdb import is_trace_failure, iter_movement_traces, tile_from_record
from render_navigation_png import Canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "topology"

PALETTE = {
    "paper": (244, 241, 231),
    "paper2": (227, 220, 200),
    "ink": (31, 41, 48),
    "muted": (91, 96, 91),
    "land": (230, 224, 205),
    "grid": (205, 194, 165),
    "grid_major": (178, 164, 131),
    "node": (34, 82, 153),
    "node_hot": (28, 110, 174),
    "edge": (39, 124, 83),
    "edge_combat": (207, 121, 29),
    "edge_failure": (190, 54, 50),
    "death": (14, 17, 20),
    "path_halo": (238, 242, 226),
    "white": (255, 255, 255),
}

FAILURE_BATCH_STATUSES = set([
    "oscillation",
    "stalled",
    "unexpected_combat",
    "player_dead",
    "max_ticks_reached",
])


def tile_key(tile):
    return "%d,%d,%d" % (tile["x"], tile["y"], tile.get("height", 0))


def include_tile(tile, surface_only):
    if tile is None:
        return False
    if surface_only and (int(tile.get("height", 0)) != 0 or int(tile["y"]) >= 6400):
        return False
    return True


def record_failed(record):
    return (
        is_trace_failure(record)
        or record.get("success") is False
        or str(record.get("batchStatus") or "") in FAILURE_BATCH_STATUSES
    )


def record_death(record):
    return record.get("isDead") is True or str(record.get("event") or "") == "player_dead"


def empty_node(tile):
    return {
        "tile": tile,
        "visits": 0,
        "combatTicks": 0,
        "failures": 0,
        "deaths": 0,
        "firstSeen": "",
        "lastSeen": "",
    }


def empty_edge(previous, current):
    return {
        "from": previous,
        "to": current,
        "ticks": 0,
        "successes": 0,
        "failures": 0,
        "combatTicks": 0,
        "hitpointsLost": 0,
        "energySpent": 0,
        "lastSeen": "",
    }


def load_topology(extra_paths, surface_only):
    nodes = {}
    edges = {}
    failure_tiles = []
    death_tiles = []
    trace_ids = set()
    source_paths = set()
    total_records = 0
    included_records = 0
    skipped_records = 0

    for record in iter_movement_traces(extra_paths):
        total_records += 1
        current = tile_from_record(record, "tile")
        if not include_tile(current, surface_only):
            skipped_records += 1
            continue
        included_records += 1

        source = record.get("_sourcePath")
        if source:
            source_paths.add(source)
        trace_id = str(record.get("traceId") or record.get("sessionId") or "")
        if trace_id:
            trace_ids.add(trace_id)

        current_key = tile_key(current)
        failed = record_failed(record)
        died = record_death(record)
        node = nodes.setdefault(current_key, empty_node(current))
        node["visits"] += 1
        if record.get("isInCombat") is True:
            node["combatTicks"] += 1
        if failed:
            node["failures"] += 1
            failure_tiles.append(current)
        if died:
            node["deaths"] += 1
            death_tiles.append(current)
        timestamp = str(record.get("timestamp") or "")
        if timestamp:
            if not node["firstSeen"]:
                node["firstSeen"] = timestamp
            node["lastSeen"] = timestamp

        previous = tile_from_record(record, "previousTile")
        if not include_tile(previous, surface_only):
            continue
        previous_key = tile_key(previous)
        nodes.setdefault(previous_key, empty_node(previous))
        if previous_key == current_key:
            continue

        edge_key = (previous_key, current_key)
        edge = edges.setdefault(edge_key, empty_edge(previous, current))
        edge["ticks"] += 1
        if failed:
            edge["failures"] += 1
        else:
            edge["successes"] += 1
        if record.get("isInCombat") is True:
            edge["combatTicks"] += 1
        edge["hitpointsLost"] += max(0, int(record.get("hitpointsLost") or 0))
        edge["energySpent"] += max(0, int(record.get("runEnergySpent") or 0))
        if timestamp:
            edge["lastSeen"] = timestamp

    return {
        "nodes": nodes,
        "edges": edges,
        "failureTiles": failure_tiles,
        "deathTiles": death_tiles,
        "traceIds": trace_ids,
        "sourcePaths": source_paths,
        "totalRecords": total_records,
        "includedRecords": included_records,
        "skippedRecords": skipped_records,
    }


def edge_color(edge):
    if edge["failures"] > 0:
        return PALETTE["edge_failure"]
    if edge["combatTicks"] > 0 or edge["hitpointsLost"] > 0:
        return PALETTE["edge_combat"]
    return PALETTE["edge"]


def blend_visit_color(visits, max_visits):
    if max_visits <= 1:
        return PALETTE["node"]
    t = min(1.0, math.log(max(1, visits), 8) / max(1.0, math.log(max_visits, 8)))
    return (
        int(PALETTE["node"][0] * (1.0 - t) + PALETTE["node_hot"][0] * t),
        int(PALETTE["node"][1] * (1.0 - t) + PALETTE["node_hot"][1] * t),
        int(PALETTE["node"][2] * (1.0 - t) + PALETTE["node_hot"][2] * t),
    )


def write_summary(path, topology, render_info, png_path, surface_only):
    nodes = topology["nodes"]
    edges = topology["edges"]
    summary = {
        "schemaVersion": 1,
        "source": "unified-movement-traces",
        "surfaceOnly": surface_only,
        "records": topology["includedRecords"],
        "totalRecords": topology["totalRecords"],
        "skippedRecords": topology["skippedRecords"],
        "traceSessions": len(topology["traceIds"]),
        "sourceTraceFiles": len(topology["sourcePaths"]),
        "nodes": len(nodes),
        "edges": len(edges),
        "failures": len(topology["failureTiles"]),
        "deaths": len(topology["deathTiles"]),
        "combatEdges": sum(1 for edge in edges.values() if edge["combatTicks"] > 0 or edge["hitpointsLost"] > 0),
        "failureEdges": sum(1 for edge in edges.values() if edge["failures"] > 0),
        "worldMapTiles": render_info["worldMapTiles"],
        "worldMapObjects": render_info["worldMapObjects"],
        "worldMapSource": render_info["worldMapSource"],
        "worldMapRegions": render_info["worldMapRegions"],
        "worldMapObjectDefs": render_info.get("worldMapObjectDefs", 0),
        "worldMapMapSceneSprites": render_info.get("worldMapMapSceneSprites", 0),
        "worldMapMapSceneObjects": render_info.get("worldMapMapSceneObjects", 0),
        "worldMapMapFunctionObjects": render_info.get("worldMapMapFunctionObjects", 0),
        "worldMapFootprintObjects": render_info.get("worldMapFootprintObjects", 0),
        "bounds": render_info["bounds"],
        "pixelsPerTile": render_info["pixelsPerTile"],
        "pixelWidth": render_info["pixelWidth"],
        "pixelHeight": render_info["pixelHeight"],
        "png": str(png_path),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def render(topology, args):
    nodes = topology["nodes"]
    edges = topology["edges"]
    if not nodes:
        raise SystemExit("no movement trace tiles to render")

    tiles = [node["tile"] for node in nodes.values()]
    pad = args.padding_tiles
    min_x = min(tile["x"] for tile in tiles) - pad
    max_x = max(tile["x"] for tile in tiles) + pad
    min_y = min(tile["y"] for tile in tiles) - pad
    max_y = max(tile["y"] for tile in tiles) + pad
    span_x = max(1, max_x - min_x + 1)
    span_y = max(1, max_y - min_y + 1)
    scale = float(args.pixels_per_tile)
    if args.max_map_pixels > 0:
        scale = min(scale, float(args.max_map_pixels) / float(max(span_x, span_y)))
    scale = max(0.2, scale)

    map_w = int(math.ceil(span_x * scale)) + 1
    map_h = int(math.ceil(span_y * scale)) + 1
    margin = 40
    title_h = 56
    legend_h = 82
    width = max(map_w + margin * 2, 820)
    height = map_h + title_h + legend_h + margin
    map_x0 = (width - map_w) // 2
    map_y0 = title_h

    def project(tile):
        x = int(map_x0 + (int(tile["x"]) - min_x) * scale)
        y = int(map_y0 + map_h - 1 - (int(tile["y"]) - min_y) * scale)
        return x, y

    bounds = {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y}
    world_map_source = "none"
    world_map_tiles = []
    world_map_objects = []
    world_map = None
    world_map_regions = 0
    world_map_stats = {}
    if args.no_world_map or args.world_map_source == "none":
        world_map_source = "none"
    else:
        world_map = load_cache_world_map(bounds, plane=args.plane)
        world_map_tiles = world_map["tiles"]
        world_map_objects = world_map["objects"]
        world_map_regions = world_map["regions"]
        world_map_stats = world_map.get("stats", {})
        world_map_source = "2006Scape Server/data/cache"

    canvas = Canvas(width, height, PALETTE["paper"])
    canvas.blend_rect(0, 0, width - 1, title_h - 1, PALETTE["paper2"], 0.7)
    canvas.text(18, 16, "MRFLAME MOVEMENT TOPOLOGY", PALETTE["ink"], 2)
    mode = "SURFACE ONLY" if args.surface_only else "ALL HEIGHTS"
    subtitle = "%.2G PX PER TILE  %s  %d RECORDS  %d NODES  %d EDGES  %d MAP TILES" % (
        scale,
        mode,
        topology["includedRecords"],
        len(nodes),
        len(edges),
        len(world_map_tiles),
    )
    canvas.text(20, 42, subtitle, PALETTE["muted"], 1)

    canvas.rect(map_x0 - 1, map_y0 - 1, map_x0 + map_w, map_y0 + map_h, PALETTE["grid_major"])
    canvas.rect(map_x0, map_y0, map_x0 + map_w - 1, map_y0 + map_h - 1, PALETTE["land"])

    if world_map_source.startswith("2006Scape Server"):
        draw_world_map(canvas, world_map, project, scale)

    for gx in range(int(min_x // 10 * 10), max_x + 1, 10):
        x = int(map_x0 + (gx - min_x) * scale)
        color = PALETTE["grid_major"] if gx % 50 == 0 else PALETTE["grid"]
        canvas.line(x, map_y0, x, map_y0 + map_h - 1, color)
    for gy in range(int(min_y // 10 * 10), max_y + 1, 10):
        y = int(map_y0 + map_h - 1 - (gy - min_y) * scale)
        color = PALETTE["grid_major"] if gy % 50 == 0 else PALETTE["grid"]
        canvas.line(map_x0, y, map_x0 + map_w - 1, y, color)

    edge_width = max(1, int(round(scale / 2.5)))
    halo_width = edge_width + 2
    for edge in edges.values():
        ax, ay = project(edge["from"])
        bx, by = project(edge["to"])
        canvas.line(ax, ay, bx, by, PALETTE["path_halo"], width=halo_width)
    for edge in edges.values():
        ax, ay = project(edge["from"])
        bx, by = project(edge["to"])
        canvas.line(ax, ay, bx, by, edge_color(edge), width=edge_width)

    max_visits = max(node["visits"] for node in nodes.values())
    block = max(1, int(math.ceil(scale)))
    for node in nodes.values():
        x, y = project(node["tile"])
        color = blend_visit_color(node["visits"], max_visits)
        canvas.rect(x - 1, y - block, x + block, y + 1, PALETTE["path_halo"])
        canvas.rect(x, y - block + 1, x + block - 1, y, color)

    marker_r = max(2, int(round(scale * 0.8)))
    for tile in topology["failureTiles"]:
        x, y = project(tile)
        canvas.circle(x, y, marker_r, PALETTE["edge_failure"], alpha=0.9)
    for tile in topology["deathTiles"]:
        x, y = project(tile)
        canvas.circle(x, y, marker_r + 2, PALETTE["death"], alpha=1.0)
        canvas.circle(x, y, marker_r + 3, PALETTE["white"], alpha=1.0, outline=True)

    legend_y = map_y0 + map_h + 20
    canvas.text(18, legend_y, "LEGEND", PALETTE["ink"], 2)
    legend = [
        ("WALKED TILE", PALETTE["node"]),
        ("LEARNED EDGE", PALETTE["edge"]),
        ("COMBAT EDGE", PALETTE["edge_combat"]),
        ("FAILED EDGE", PALETTE["edge_failure"]),
        ("DEATH", PALETTE["death"]),
        ("WORLD MAP", PALETTE["land"]),
    ]
    lx = 126
    ly = legend_y + 3
    for label, color in legend:
        if lx + 140 > width - 20:
            lx = 126
            ly += 18
        canvas.rect(lx, ly, lx + 15, ly + 9, color)
        canvas.text(lx + 22, ly, label, PALETTE["ink"], 1)
        lx += 142

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save_png(output)
    return {
        "bounds": bounds,
        "pixelsPerTile": scale,
        "pixelWidth": width,
        "pixelHeight": height,
        "worldMapTiles": len(world_map_tiles),
        "worldMapObjects": len(world_map_objects),
        "worldMapRegions": world_map_regions,
        "worldMapSource": world_map_source,
        "worldMapObjectDefs": world_map_stats.get("objectDefs", 0),
        "worldMapMapSceneSprites": world_map_stats.get("mapSceneSprites", 0),
        "worldMapMapSceneObjects": world_map_stats.get("mapSceneObjects", 0),
        "worldMapMapFunctionObjects": world_map_stats.get("mapFunctionObjects", 0),
        "worldMapFootprintObjects": world_map_stats.get("footprintObjects", 0),
    }


def main():
    parser = argparse.ArgumentParser(description="Render all learned movement trace tiles as a topology PNG.")
    parser.add_argument("--trace-file", action="append", help="Extra trace JSONL file or directory to include.")
    parser.add_argument("--pixels-per-tile", type=float, default=4.0)
    parser.add_argument("--max-map-pixels", type=int, default=3200)
    parser.add_argument("--padding-tiles", type=int, default=20)
    parser.add_argument("--surface-only", action="store_true", default=True)
    parser.add_argument("--include-underground", action="store_true")
    parser.add_argument("--plane", type=int, default=0)
    parser.add_argument("--world-map-source", choices=("cache", "none"), default="cache")
    parser.add_argument("--no-world-map", action="store_true", help="Do not paint a world map as the background.")
    parser.add_argument("--output", default=str(OUT / "movement-topology.png"))
    parser.add_argument("--summary", default=str(OUT / "movement-topology.json"))
    args = parser.parse_args()
    if args.include_underground:
        args.surface_only = False

    topology = load_topology(args.trace_file, args.surface_only)
    render_info = render(topology, args)
    summary = write_summary(Path(args.summary), topology, render_info, Path(args.output), args.surface_only)
    print(json.dumps({"success": True, "output": args.output, "summary": args.summary, **summary}, sort_keys=True))


if __name__ == "__main__":
    main()
