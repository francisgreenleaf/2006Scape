#!/usr/bin/env python3
"""Render a small cache-backed context map around a tile, place, or trace.

This is intentionally cheaper than the full topology render: it draws a bounded
cache map at an integer tile scale and overlays only tactical context such as the
current player tile or recent trace path.
"""

import argparse
import datetime as dt
import json
import math
import os
import uuid
from pathlib import Path

import cache_world_map
import navdb
from render_navigation_png import Canvas


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_MAP_ARCHIVE = ROOT / ".local" / "context-maps"

PALETTE = {
    "paper": (232, 224, 199),
    "current": (255, 221, 78),
    "current_shadow": (35, 34, 28),
    "recent": (58, 170, 224),
    "recent_run": (75, 235, 146),
    "recent_risk": (221, 70, 57),
    "segment": (139, 95, 218),
    "place": (255, 255, 255),
    "place_outline": (35, 47, 58),
    "place_label": (255, 255, 255),
    "label_shadow": (0, 0, 0),
    "map_function_icon": (255, 232, 86),
    "map_function_outline": (32, 26, 16),
    "start": (60, 185, 113),
    "end": (235, 87, 87),
    "grid": (66, 68, 58),
}


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("value must be an integer")
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def nonnegative_int(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("value must be an integer")
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be nonnegative")
    return parsed


def trace_timestamp(record):
    value = record.get("timestampMs")
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def player_matches(record, player):
    if not player:
        return True
    name = str(record.get("playerName") or record.get("player") or "").strip().lower()
    return not name or name == player.strip().lower()


def sorted_trace_records(extra_paths, player):
    records = [record for record in navdb.iter_movement_traces(extra_paths) if player_matches(record, player)]
    return sorted(
        records,
        key=lambda record: (
            trace_timestamp(record),
            str(record.get("_sourcePath") or ""),
            int(record.get("_sourceLine") or 0),
        ),
    )


def limit_records(records, max_records):
    if max_records <= 0 or len(records) <= max_records:
        return records
    return records[-max_records:]


def latest_trace_tile(records):
    for record in reversed(records):
        tile = navdb.tile_from_record(record, "tile")
        if tile is not None:
            return tile, record
    return None, None


def tile_in_bounds(tile, bounds):
    return (
        tile is not None
        and int(tile.get("height", 0)) == int(bounds.get("height", tile.get("height", 0)))
        and bounds["minX"] <= int(tile["x"]) <= bounds["maxX"]
        and bounds["minY"] <= int(tile["y"]) <= bounds["maxY"]
    )


def tile_near_place(tile, place):
    if tile is None or place is None:
        return False
    place_tile = place.get("tile") or {}
    if int(tile.get("height", 0)) != int(place_tile.get("height", 0)):
        return False
    radius = int(place.get("arrivalRadius") or 3)
    return navdb.distance(tile, place_tile) <= radius


def latest_segment(records, start_place, end_place):
    best = None
    open_start = None
    for index, record in enumerate(records):
        tile = navdb.tile_from_record(record, "tile")
        if tile_near_place(tile, start_place):
            open_start = index
        if open_start is not None and tile_near_place(tile, end_place):
            if index > open_start:
                best = (open_start, index)
            open_start = None
    if best is None:
        return []
    return records[best[0]:best[1] + 1]


def recent_records(records, seconds):
    if seconds <= 0 or not records:
        return []
    latest = max(trace_timestamp(record) for record in records)
    if latest <= 0:
        return records[-max(1, seconds):]
    cutoff = latest - seconds * 1000
    return [record for record in records if trace_timestamp(record) >= cutoff]


def center_from_arg(db, records, value):
    if value in ("latest", "current", "player"):
        tile, record = latest_trace_tile(records)
        if tile is None:
            raise SystemExit("no movement trace tile available for --center {}".format(value))
        return tile, {
            "mode": value,
            "timestamp": record.get("timestamp"),
            "timestampMs": record.get("timestampMs"),
            "source": record.get("_sourcePath"),
        }
    if "," in value:
        return navdb.tile_from_arg(value), {"mode": "tile"}
    place = navdb.find_place(db, value)
    if place is None:
        raise SystemExit("unknown center place: {}".format(value))
    return place["tile"], {"mode": "place", "placeId": place["id"], "placeName": place["name"]}


def bounds_around(center, radius):
    return {
        "minX": int(center["x"]) - radius,
        "minY": int(center["y"]) - radius,
        "maxX": int(center["x"]) + radius,
        "maxY": int(center["y"]) + radius,
    }


def bounds_for_records(records, padding):
    tiles = []
    for record in records:
        tile = navdb.tile_from_record(record, "tile")
        if tile is not None:
            tiles.append(tile)
        previous = navdb.tile_from_record(record, "previousTile")
        if previous is not None:
            tiles.append(previous)
    if not tiles:
        return None
    return {
        "minX": min(tile["x"] for tile in tiles) - padding,
        "minY": min(tile["y"] for tile in tiles) - padding,
        "maxX": max(tile["x"] for tile in tiles) + padding,
        "maxY": max(tile["y"] for tile in tiles) + padding,
    }


def distance_to_bounds(tile, bounds):
    dx = 0
    dy = 0
    x = int(tile["x"])
    y = int(tile["y"])
    if x < bounds["minX"]:
        dx = bounds["minX"] - x
    elif x > bounds["maxX"]:
        dx = x - bounds["maxX"]
    if y < bounds["minY"]:
        dy = bounds["minY"] - y
    elif y > bounds["maxY"]:
        dy = y - bounds["maxY"]
    return max(dx, dy)


def context_anchor_priority(place):
    text = " ".join([
        str(place.get("id") or ""),
        str(place.get("name") or ""),
        " ".join(str(alias) for alias in place.get("aliases", [])),
    ]).lower()
    kind = str(place.get("kind") or "")
    if any(word in text for word in ("dock", "port", "sarim", "ship", "boat", "ferry")):
        return 0
    if kind in ("bank", "shop"):
        return 1
    if kind in ("hub", "town", "utility"):
        return 2
    return 3


def expand_bounds_for_context_places(db, bounds, radius, max_anchors):
    if radius <= 0 or max_anchors <= 0:
        return bounds, []
    candidates = []
    plane = int(bounds.get("height", 0))
    for place in db.get("places", []):
        tile = place.get("tile")
        if tile is None or int(tile.get("height", 0)) != plane:
            continue
        if tile_in_bounds(tile, bounds):
            continue
        distance = distance_to_bounds(tile, bounds)
        if distance > radius:
            continue
        candidates.append((context_anchor_priority(place), distance, str(place.get("id") or ""), place))
    candidates.sort()
    anchors = [place for _priority, _distance, _id, place in candidates[:max_anchors]]
    if not anchors:
        return bounds, []
    expanded = dict(bounds)
    for place in anchors:
        tile = place["tile"]
        expanded["minX"] = min(expanded["minX"], int(tile["x"]))
        expanded["minY"] = min(expanded["minY"], int(tile["y"]))
        expanded["maxX"] = max(expanded["maxX"], int(tile["x"]))
        expanded["maxY"] = max(expanded["maxY"], int(tile["y"]))
    return expanded, [{
        "id": place["id"],
        "name": place["name"],
        "kind": place.get("kind"),
        "tile": place["tile"],
        "distanceToOriginalBounds": distance_to_bounds(place["tile"], bounds),
    } for place in anchors]


def clamp_bounds(bounds, max_span):
    span_x = bounds["maxX"] - bounds["minX"] + 1
    span_y = bounds["maxY"] - bounds["minY"] + 1
    if span_x <= max_span and span_y <= max_span:
        return bounds
    cx = (bounds["minX"] + bounds["maxX"]) // 2
    cy = (bounds["minY"] + bounds["maxY"]) // 2
    half = max_span // 2
    return {
        "minX": cx - half,
        "minY": cy - half,
        "maxX": cx + half,
        "maxY": cy + half,
    }


def draw_marker(canvas, project, tile, color, scale, shadow=True):
    cx, cy = project(tile)
    radius = max(3, int(round(scale * 0.95)))
    if shadow:
        canvas.circle(cx, cy, radius + max(2, scale // 2), PALETTE["current_shadow"])
    canvas.circle(cx, cy, radius, color)
    arm = max(radius + 2, int(round(scale * 1.35)))
    width = max(1, scale // 3)
    canvas.line(cx - arm, cy, cx + arm, cy, color, width=width)
    canvas.line(cx, cy - arm, cx, cy + arm, color, width=width)


def record_color(record, default):
    if record.get("isDead") is True or record.get("isInCombat") is True or int(record.get("hitpointsLost") or 0) > 0:
        return PALETTE["recent_risk"]
    activity = record.get("activity") if isinstance(record.get("activity"), dict) else {}
    if record.get("runEnabled") is True or activity.get("runningStep") is True or int(record.get("runEnergySpent") or 0) > 0:
        return PALETTE["recent_run"]
    return default


def draw_trace(canvas, project, records, bounds, scale, color):
    drawn = 0
    width = max(1, int(round(scale * 0.42)))
    for record in records:
        tile = navdb.tile_from_record(record, "tile")
        previous = navdb.tile_from_record(record, "previousTile")
        if tile is None or previous is None:
            continue
        if int(tile.get("height", 0)) != int(previous.get("height", 0)):
            continue
        if navdb.distance(tile, previous) > 12:
            continue
        if not tile_in_bounds(tile, bounds) or not tile_in_bounds(previous, bounds):
            continue
        x0, y0 = project(previous)
        x1, y1 = project(tile)
        canvas.line(x0, y0, x1, y1, record_color(record, color), width=width)
        drawn += 1
    return drawn


def draw_place_markers(canvas, project, db, bounds, scale, max_places, draw_labels=False):
    places = []
    for place in db["places"]:
        tile = place.get("tile")
        if tile_in_bounds(tile, bounds):
            places.append(place)
    places = sorted(places, key=lambda place: (context_anchor_priority(place), str(place["id"])))[:max_places]
    marker = max(2, scale // 2)
    label_boxes = []
    results = []
    for place in places:
        x, y = project(place["tile"])
        canvas.rect(x - marker - 1, y - marker - 1, x + marker + 1, y + marker + 1, PALETTE["place_outline"])
        canvas.rect(x - marker, y - marker, x + marker, y + marker, PALETTE["place"])
        label_drawn = False
        if draw_labels:
            label = sanitize_label(place.get("name") or place.get("id"))
            label_x = x + marker + 3
            label_y = y - marker - 8
            box = label_bounds(label_x, label_y, label)
            if label and not any(boxes_overlap(box, existing) for existing in label_boxes):
                label_drawn = draw_label(canvas, label_x, label_y, label)
                if label_drawn:
                    label_boxes.append(box)
        results.append({
            "id": place["id"],
            "name": place["name"],
            "kind": place.get("kind"),
            "tile": place["tile"],
            "labelDrawn": label_drawn,
        })
    return results


def label_bounds(x, y, text, scale=1):
    return (int(x), int(y), int(x) + len(str(text)) * 4 * int(scale), int(y) + 7 * int(scale))


def boxes_overlap(left, right, padding=2):
    return not (
        left[2] + padding < right[0]
        or right[2] + padding < left[0]
        or left[3] + padding < right[1]
        or right[3] + padding < left[1]
    )


def draw_grid(canvas, bounds, project, scale, interval):
    if interval <= 0:
        return 0
    lines = 0
    width = max(1, scale // 6)
    for x in range(bounds["minX"], bounds["maxX"] + 1):
        if x % interval != 0:
            continue
        x0, y0 = project({"x": x, "y": bounds["minY"], "height": 0})
        x1, y1 = project({"x": x, "y": bounds["maxY"], "height": 0})
        canvas.line(x0, y0, x1, y1, PALETTE["grid"], width=width)
        lines += 1
    for y in range(bounds["minY"], bounds["maxY"] + 1):
        if y % interval != 0:
            continue
        x0, y0 = project({"x": bounds["minX"], "y": y, "height": 0})
        x1, y1 = project({"x": bounds["maxX"], "y": y, "height": 0})
        canvas.line(x0, y0, x1, y1, PALETTE["grid"], width=width)
        lines += 1
    return lines


def sanitize_label(value, max_length=28):
    text = str(value or "").replace("_", " ").strip()
    if len(text) > max_length:
        text = text[:max_length - 1].rstrip() + "."
    return "".join(ch if ch.isalnum() or ch in " -." else " " for ch in text)


def slug(value, max_length=48):
    text = str(value or "").strip().lower().replace("_", "-")
    chars = []
    previous_dash = False
    for ch in text:
        if ch.isalnum():
            chars.append(ch)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    cleaned = "".join(chars).strip("-")
    if not cleaned:
        cleaned = "map"
    return cleaned[:max_length].strip("-") or "map"


def tile_filename_part(tile):
    return "x{}-y{}-h{}".format(
        int(tile["x"]),
        int(tile["y"]),
        int(tile.get("height", 0)),
    )


def resolve_output_paths(args, center, segment_info):
    requested_output = getattr(args, "output", None)
    requested_summary = getattr(args, "summary", None)
    if requested_output and requested_summary:
        return Path(requested_output), Path(requested_summary), None
    if requested_output:
        output = Path(requested_output)
        return output, output.with_suffix(".json"), None
    if requested_summary:
        summary = Path(requested_summary)
        return summary.with_suffix(".png"), summary, None

    now = dt.datetime.now(dt.timezone.utc)
    date_dir = now.strftime("%Y-%m-%d")
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    kind = "segment" if segment_info else "center"
    if segment_info:
        label = "{}-to-{}".format(segment_info.get("from"), segment_info.get("to"))
    else:
        center_info = getattr(args, "_center_info", {}) or {}
        label = center_info.get("placeId") or center_info.get("mode") or "center"
    artifact_id = "{}-{}-{}-{}-r{}-ppt{}-{}".format(
        stamp,
        kind,
        slug(label),
        tile_filename_part(center),
        int(args.radius_tiles),
        int(args.pixels_per_tile),
        uuid.uuid4().hex[:8],
    )
    archive_root = Path(getattr(args, "artifact_dir", None) or CONTEXT_MAP_ARCHIVE)
    archive_dir = archive_root / date_dir
    return archive_dir / "{}.png".format(artifact_id), archive_dir / "{}.json".format(artifact_id), {
        "id": artifact_id,
        "kind": kind,
        "archiveRoot": str(archive_root),
        "archiveDate": date_dir,
        "autoNamed": True,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
    }


def draw_label(canvas, x, y, text, color=PALETTE["place_label"], scale=1):
    text = sanitize_label(text)
    if not text:
        return False
    canvas.text(x + 1, y + 1, text, PALETTE["label_shadow"], scale=scale)
    canvas.text(x, y, text, color, scale=scale)
    return True


def nearest_place(tile, db, max_distance=8):
    best = None
    best_key = None
    priority = {
        "bank": 0,
        "shop": 1,
        "town": 2,
        "hub": 2,
        "surface_checkpoint": 3,
    }
    for place in db.get("places", []):
        place_tile = place.get("tile")
        if place_tile is None or int(place_tile.get("height", 0)) != int(tile.get("height", 0)):
            continue
        distance = navdb.distance(tile, place_tile)
        if distance > max_distance:
            continue
        kind = str(place.get("kind") or "")
        key = (distance, priority.get(kind, 4), str(place.get("id") or ""))
        if best_key is None or key < best_key:
            best = place
            best_key = key
    if best is None:
        return None
    return {
        "id": best.get("id"),
        "name": best.get("name"),
        "kind": best.get("kind"),
        "distance": int(best_key[0]),
    }


def mapfunction_markers(world_map, bounds, db):
    markers = []
    seen = set()
    for obj in world_map.get("objects", []):
        map_function = int(obj.get("mapFunction", -1))
        if map_function < 0:
            continue
        tile = {
            "x": int(obj["x"]),
            "y": int(obj["y"]),
            "height": int(obj.get("height", 0)),
        }
        if not tile_in_bounds(tile, bounds):
            continue
        key = (tile["x"], tile["y"], tile["height"], map_function, int(obj.get("id", -1)))
        if key in seen:
            continue
        seen.add(key)
        place = nearest_place(tile, db)
        name = obj.get("name") or (place or {}).get("name") or "mapfunction-%d" % map_function
        markers.append({
            "kind": "mapfunction",
            "label": sanitize_label(name),
            "objectId": int(obj.get("id", -1)),
            "objectName": obj.get("name"),
            "mapFunction": map_function,
            "nearestPlace": place,
            "tile": tile,
        })
    return markers


def draw_indexed_sprite(canvas, sprite, cx, cy, scale, alpha=1.0):
    palette = sprite.get("palette") or []
    pixels = sprite.get("pixels") or []
    width = int(sprite.get("width", 0))
    height = int(sprite.get("height", 0))
    if width <= 0 or height <= 0 or not palette:
        return False
    draw_w = width * scale
    draw_h = height * scale
    left = cx - draw_w / 2.0
    top = cy - draw_h / 2.0
    for sy in range(height):
        for sx in range(width):
            palette_index = pixels[sx + sy * width]
            if palette_index <= 0 or palette_index >= len(palette):
                continue
            color = palette[palette_index]
            x0 = int(math.floor(left + sx * scale))
            x1 = int(math.ceil(left + (sx + 1) * scale)) - 1
            y0 = int(math.floor(top + sy * scale))
            y1 = int(math.ceil(top + (sy + 1) * scale)) - 1
            canvas.blend_rect(x0, y0, x1, y1, color, alpha)
    return True


def draw_mapfunction_fallback(canvas, cx, cy, radius):
    canvas.circle(cx, cy, radius + 1, PALETTE["map_function_outline"], alpha=0.86)
    canvas.rect(cx - radius, cy, cx + radius, cy, PALETTE["map_function_icon"])
    canvas.rect(cx, cy - radius, cx, cy + radius, PALETTE["map_function_icon"])


def draw_mapfunction_icons(canvas, project, markers, scale, draw_labels=False):
    if not markers:
        return 0
    sprites = cache_world_map.load_background_sprites(name="mapfunction", limit=100)
    icon_scale = max(1.0, float(scale) / 4.0)
    fallback_radius = max(2, int(round(scale * 0.8)))
    drawn = 0
    for marker in markers:
        px, py = project(marker["tile"])
        cx = px + max(0, int(round(scale / 2.0)))
        cy = py - max(0, int(round(scale / 2.0)))
        sprite = sprites.get(int(marker.get("mapFunction", -1)))
        if sprite is not None:
            if not draw_indexed_sprite(canvas, sprite, cx, cy, icon_scale, 1.0):
                draw_mapfunction_fallback(canvas, cx, cy, fallback_radius)
        else:
            draw_mapfunction_fallback(canvas, cx, cy, fallback_radius)
        drawn += 1
        if draw_labels:
            draw_label(canvas, cx + fallback_radius + 3, cy - fallback_radius - 8, marker.get("label"))
    return drawn


def draw_static_context_layers(canvas, project, world_map, db, bounds, scale,
                               mapfunction_icons=True, mapfunction_labels=False,
                               place_markers=True, place_labels=True,
                               max_place_markers=40):
    """Draw reusable POI layers on top of a cache world map.

    This is shared by tactical context maps and ML comparison maps so agents get
    the same banks, shops, docks, and named places without custom renderer work.
    """
    mapfunction_markers_in_bounds = mapfunction_markers(world_map, bounds, db) if mapfunction_icons else []
    mapfunction_icons_drawn = draw_mapfunction_icons(
        canvas,
        project,
        mapfunction_markers_in_bounds,
        scale,
        draw_labels=mapfunction_labels,
    ) if mapfunction_icons else 0
    places = draw_place_markers(
        canvas,
        project,
        db,
        bounds,
        scale,
        max_place_markers,
        draw_labels=place_labels,
    ) if place_markers else []
    return {
        "mapFunctionMarkerCount": len(mapfunction_markers_in_bounds),
        "mapFunctionIconsDrawn": mapfunction_icons_drawn,
        "mapFunctionMarkers": mapfunction_markers_in_bounds,
        "placeMarkers": places,
        "placeLabelsDrawn": sum(1 for place in places if place.get("labelDrawn")),
    }


def render(args):
    db = navdb.load_db()
    all_records = sorted_trace_records(args.trace_file, args.player)
    max_trace_records = getattr(args, "max_trace_records", 0)
    records = limit_records(all_records, max_trace_records)
    segment_records = []
    segment_info = None
    if args.segment_from or args.segment_to:
        if not args.segment_from or not args.segment_to:
            raise SystemExit("--segment-from and --segment-to must be used together")
        start_place = navdb.find_place(db, args.segment_from)
        end_place = navdb.find_place(db, args.segment_to)
        if start_place is None:
            raise SystemExit("unknown segment start place: {}".format(args.segment_from))
        if end_place is None:
            raise SystemExit("unknown segment end place: {}".format(args.segment_to))
        segment_records = latest_segment(records, start_place, end_place)
        segment_info = {
            "from": start_place["id"],
            "to": end_place["id"],
            "records": len(segment_records),
        }
        if not segment_records:
            raise SystemExit("no completed trace segment found from {} to {}".format(start_place["id"], end_place["id"]))

    recent = recent_records(records, args.recent_seconds)
    center, center_info = center_from_arg(db, records, args.center)
    args._center_info = center_info
    bounds = None
    context_anchors = []
    if args.bounds:
        bounds = cache_world_map.parse_bounds(args.bounds)
    elif segment_records and args.fit_segment:
        bounds = bounds_for_records(segment_records, args.padding_tiles)
    if bounds is None:
        bounds = bounds_around(center, args.radius_tiles)
    bounds["height"] = int(center.get("height", args.plane))
    if segment_records and args.fit_segment:
        bounds, context_anchors = expand_bounds_for_context_places(
            db,
            bounds,
            getattr(args, "context_place_radius", 0),
            getattr(args, "max_context_anchors", 0),
        )
    bounds = clamp_bounds(bounds, args.max_span_tiles)
    bounds["height"] = int(center.get("height", args.plane))

    world_map = cache_world_map.load_cache_world_map(bounds, plane=args.plane)
    bounds = dict(world_map["bounds"])
    bounds["height"] = int(center.get("height", args.plane))
    span_x = bounds["maxX"] - bounds["minX"] + 1
    span_y = bounds["maxY"] - bounds["minY"] + 1
    width = span_x * args.pixels_per_tile + 1
    height = span_y * args.pixels_per_tile + 1
    canvas = Canvas(width, height, PALETTE["paper"])

    def project(tile):
        px = int((int(tile["x"]) - bounds["minX"]) * args.pixels_per_tile)
        py = int(height - 1 - (int(tile["y"]) - bounds["minY"]) * args.pixels_per_tile)
        return px, py

    cache_world_map.draw_world_map(canvas, world_map, project, args.pixels_per_tile)
    grid_lines = draw_grid(canvas, bounds, project, args.pixels_per_tile, args.grid_interval)
    segment_edges = draw_trace(canvas, project, segment_records, bounds, args.pixels_per_tile, PALETTE["segment"])
    recent_edges = draw_trace(canvas, project, recent, bounds, args.pixels_per_tile, PALETTE["recent"])
    context_layers = draw_static_context_layers(
        canvas,
        project,
        world_map,
        db,
        bounds,
        args.pixels_per_tile,
        mapfunction_icons=getattr(args, "mapfunction_icons", True),
        mapfunction_labels=getattr(args, "mapfunction_labels", False),
        place_markers=args.place_markers,
        place_labels=getattr(args, "place_labels", False),
        max_place_markers=args.max_place_markers,
    )

    if segment_records:
        start_tile = navdb.tile_from_record(segment_records[0], "tile")
        end_tile = navdb.tile_from_record(segment_records[-1], "tile")
        if tile_in_bounds(start_tile, bounds):
            draw_marker(canvas, project, start_tile, PALETTE["start"], args.pixels_per_tile, shadow=False)
        if tile_in_bounds(end_tile, bounds):
            draw_marker(canvas, project, end_tile, PALETTE["end"], args.pixels_per_tile, shadow=False)
    if args.current_marker and tile_in_bounds(center, bounds):
        draw_marker(canvas, project, center, PALETTE["current"], args.pixels_per_tile)

    output, summary_path, artifact = resolve_output_paths(args, center, segment_info)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save_png(output)

    summary = {
        "success": True,
        "output": str(output),
        "summary": str(summary_path),
        "artifact": artifact,
        "source": "2006Scape Server/data/cache",
        "totalTraceRecords": len(all_records),
        "traceRecordsConsidered": len(records),
        "maxTraceRecords": max_trace_records,
        "bounds": {key: bounds[key] for key in ("minX", "minY", "maxX", "maxY")},
        "center": center,
        "centerInfo": center_info,
        "plane": args.plane,
        "pixelsPerTile": args.pixels_per_tile,
        "pixelWidth": width,
        "pixelHeight": height,
        "spanTiles": {"x": span_x, "y": span_y},
        "tiles": len(world_map.get("tiles", [])),
        "objects": len(world_map.get("objects", [])),
        "regions": world_map.get("regions", []),
        "recentSeconds": args.recent_seconds,
        "recentRecords": len(recent),
        "recentEdgesDrawn": recent_edges,
        "segment": segment_info,
        "contextAnchors": context_anchors,
        "segmentEdgesDrawn": segment_edges,
        "mapFunctionMarkerCount": context_layers["mapFunctionMarkerCount"],
        "mapFunctionIconsDrawn": context_layers["mapFunctionIconsDrawn"],
        "mapFunctionMarkers": context_layers["mapFunctionMarkers"],
        "placeMarkers": context_layers["placeMarkers"],
        "placeLabelsDrawn": context_layers["placeLabelsDrawn"],
        "gridLines": grid_lines,
        "lossless": True,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Render a small lossless cache-map window with tactical route context.")
    parser.add_argument("--center", default="latest", help="latest/current, x,y,h, or place id/name.")
    parser.add_argument("--bounds", help="Explicit minX,minY,maxX,maxY bounds.")
    parser.add_argument("--radius-tiles", type=positive_int, default=64)
    parser.add_argument("--padding-tiles", type=positive_int, default=24)
    parser.add_argument("--max-span-tiles", type=positive_int, default=224)
    parser.add_argument("--context-place-radius", type=nonnegative_int, default=0,
                        help="For fitted segment maps, expand bounds to include nearby useful place anchors.")
    parser.add_argument("--max-context-anchors", type=nonnegative_int, default=0,
                        help="Maximum nearby place anchors to pull into fitted segment bounds.")
    parser.add_argument("--plane", type=int, default=0)
    parser.add_argument("--pixels-per-tile", type=positive_int, default=4,
                        help="Integer tile scale; output is not resampled.")
    parser.add_argument("--recent-seconds", type=nonnegative_int, default=60,
                        help="Overlay passive movement records from the latest trace timestamp window.")
    parser.add_argument("--segment-from")
    parser.add_argument("--segment-to")
    parser.add_argument("--fit-segment", action="store_true", default=True)
    parser.add_argument("--no-fit-segment", dest="fit_segment", action="store_false")
    parser.add_argument("--player", default=os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or "mrflame")
    parser.add_argument("--trace-file", action="append")
    parser.add_argument("--max-trace-records", type=nonnegative_int, default=0,
                        help="Use only the newest N trace records after sorting. 0 considers all records.")
    parser.add_argument("--current-marker", action="store_true", default=True)
    parser.add_argument("--no-current-marker", dest="current_marker", action="store_false")
    parser.add_argument("--mapfunction-icons", action="store_true", default=True,
                        help="Draw every cache-backed mapfunction icon in bounds.")
    parser.add_argument("--no-mapfunction-icons", dest="mapfunction_icons", action="store_false")
    parser.add_argument("--mapfunction-labels", action="store_true", default=False,
                        help="Also label every mapfunction icon with its object/mapfunction name.")
    parser.add_argument("--place-markers", action="store_true", default=True)
    parser.add_argument("--no-place-markers", dest="place_markers", action="store_false")
    parser.add_argument("--place-labels", action="store_true", default=True,
                        help="Draw simple labels for place markers.")
    parser.add_argument("--no-place-labels", dest="place_labels", action="store_false")
    parser.add_argument("--max-place-markers", type=positive_int, default=40)
    parser.add_argument("--grid-interval", type=int, default=0,
                        help="Draw coordinate grid every N tiles. 0 disables.")
    parser.add_argument("--artifact-dir", default=str(CONTEXT_MAP_ARCHIVE),
                        help="Default archive root for unique context-map artifacts.")
    parser.add_argument("--output",
                        help="Exact PNG output path. If omitted, a unique ignored artifact path is used.")
    parser.add_argument("--summary",
                        help="Exact JSON summary path. If omitted with --output, uses the PNG path with .json.")
    args = parser.parse_args()
    if args.grid_interval < 0:
        raise SystemExit("--grid-interval must be >= 0")
    summary = render(args)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
