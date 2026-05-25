#!/usr/bin/env python3
"""Shared engine for the active movement topology map renders.

The current user-facing maps use the plain-name wrappers. Running this module
directly is only useful for engine debugging or legacy comparison output.
"""

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from cache_world_map import CACHE_DIR, draw_world_map, load_background_sprites, load_cache_world_map
from navdb import default_trace_profile, iter_movement_traces, record_matches_profile, tile_from_record, trace_paths
from render_movement_topology import (
    empty_edge,
    empty_node,
    include_tile,
    record_death,
    record_failed,
)
from render_navigation_png import Canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "topology"
PLACES_PATH = ROOT / "data" / "places.json"
RUNESCAPE_FONT = ROOT / "assets" / "fonts" / "runescape_uf.ttf"
RUNESCAPE_FONT_SOURCE = "https://www.dafont.com/runescape-uf.font"
DEFAULT_COVERAGE_CACHE_DIR = ROOT / ".local" / "topology-render-cache"
FOG_REVEAL_CACHE_VERSION = 1
HEAT_MASK_CACHE_VERSION = 3
CANVAS_LAYER_CACHE_VERSION = 1
POI_CACHE_VERSION = 1
TOPOLOGY_CACHE_VERSION = 1
PLAYER_TRACE_PART = "player-movement-traces"
AGENT_TRACE_PART = "agent-movement-traces"
_RADIAL_HEAT_KERNELS = {}
_FOG_REVEAL_KERNELS = {}

FOOTER_HEIGHT = 280
FOOTER_RULE_Y = 12
FOOTER_SECTION_Y = 58
FOOTER_ITEM_MARKER_Y = 122
FOOTER_ITEM_TEXT_Y = 120
FOOTER_ROW_GAP = 48
FOOTER_STATS_ROW_Y = 100
FOOTER_STATS_ROW_GAP = 32
FOOTER_COVERAGE_X = 570
FOOTER_COVERAGE_TITLE_Y = 120
FOOTER_COVERAGE_BAR_Y = 154
FOOTER_COVERAGE_LABEL_Y = 218

PALETTE = {
    "paper": (14, 15, 16),
    "paper2": (24, 26, 28),
    "ink": (30, 38, 43),
    "muted": (170, 175, 168),
    "land": (220, 214, 195),
    "frame": (105, 109, 104),
    "grid": (238, 231, 209),
    "grid_major": (248, 244, 228),
    "trail_halo": (6, 25, 31),
    "trail": (18, 178, 213),
    "trail_hot": (112, 244, 255),
    "walk": (7, 92, 112),
    "walk_hot": (34, 141, 160),
    "run": (93, 255, 174),
    "combat": (255, 169, 42),
    "failure": (238, 45, 68),
    "death": (14, 17, 20),
    "current": (255, 221, 78),
    "bank": (72, 154, 255),
    "shop": (60, 218, 128),
    "poi_outline": (255, 245, 168),
    "fog": (5, 6, 8),
    "osrs_yellow": (255, 255, 0),
    "text_shadow": (0, 0, 0),
    "white": (255, 255, 255),
}

COVERAGE_HEAT_STOPS = [
    (0.00, (69, 84, 190)),
    (0.35, (24, 178, 205)),
    (0.66, (255, 232, 86)),
    (1.00, (255, 78, 45)),
]

STATIC_LABELS = [
    {
        "text": "Port Sarim",
        "tile": {"x": 3026, "y": 3218, "height": 0},
        "dx": -34,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Falador",
        "tile": {"x": 2965, "y": 3378, "height": 0},
        "dx": -30,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Rimmington",
        "tile": {"x": 2957, "y": 3215, "height": 0},
        "dx": -44,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Draynor",
        "tile": {"x": 3093, "y": 3245, "height": 0},
        "dx": -30,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Ice Mountain",
        "tile": {"x": 3008, "y": 3478, "height": 0},
        "dx": -64,
        "dy": -30,
        "color": "white",
        "outline": True,
    },
]

SUPPRESSED_PLACE_LABELS = {
    "Rimmington Center",
}


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def quantize_render_bounds(min_x, max_x, min_y, max_y, quantum):
    quantum = int(quantum or 0)
    if quantum <= 1:
        return int(min_x), int(max_x), int(min_y), int(max_y)
    q = quantum
    q_min_x = (int(min_x) // q) * q
    q_min_y = (int(min_y) // q) * q
    q_max_x = ((int(max_x) + q) // q) * q - 1
    q_max_y = ((int(max_y) + q) // q) * q - 1
    return q_min_x, q_max_x, q_min_y, q_max_y


def mix(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return tuple(int(a[i] * (1.0 - t) + b[i] * t) for i in range(3))


def color_hex(color):
    return "#%02x%02x%02x" % color


def color_rgba(color, alpha):
    return "rgba(%d,%d,%d,%.3f)" % (
        int(color[0]), int(color[1]), int(color[2]), clamp(float(alpha), 0.0, 1.0)
    )


def format_int(value):
    return "{:,}".format(int(value))


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def percentile_value(sorted_values, percentile):
    if not sorted_values:
        return 0
    percentile = clamp(float(percentile), 0.0, 1.0)
    index = int(round((len(sorted_values) - 1) * percentile))
    return sorted_values[index]


def edge_state(edge):
    if edge["failures"] > 0:
        return "failure"
    if edge["combatTicks"] > 0 or edge["hitpointsLost"] > 0:
        return "combat"
    return "trail"


def edge_color(edge, max_ticks):
    state = edge_state(edge)
    if state == "failure":
        return PALETTE["failure"]
    if state == "combat":
        return PALETTE["combat"]
    if max_ticks <= 1:
        return PALETTE["trail"]
    t = math.log(max(1, edge["ticks"]), 8) / max(1.0, math.log(max_ticks, 8))
    return mix(PALETTE["trail"], PALETTE["trail_hot"], t * 0.65)


def edge_run_ratio(edge):
    observed = max(1, int(edge.get("runObservedTicks") or edge.get("ticks") or 1))
    return clamp(float(edge.get("runEvidenceTicks", 0)) / float(observed), 0.0, 1.0)


def edge_display_color(edge, max_ticks, args):
    color = edge_color(edge, max_ticks)
    if getattr(args, "running_overlay", False) and edge_state(edge) == "trail":
        if int(edge.get("runEvidenceTicks", 0)) > 0:
            color = mix(color, PALETTE["run"], 0.28 + edge_run_ratio(edge) * 0.24)
        else:
            if max_ticks <= 1:
                color = PALETTE["walk"]
            else:
                t = math.log(max(1, edge["ticks"]), 8) / max(1.0, math.log(max_ticks, 8))
                color = mix(PALETTE["walk"], PALETTE["walk_hot"], t * 0.58)
    return color


def heat_color(value):
    value = clamp(value, 0.0, 1.0)
    previous_at, previous_color = COVERAGE_HEAT_STOPS[0]
    for stop_at, stop_color in COVERAGE_HEAT_STOPS[1:]:
        if value <= stop_at:
            span = max(0.0001, stop_at - previous_at)
            return mix(previous_color, stop_color, (value - previous_at) / span)
        previous_at, previous_color = stop_at, stop_color
    return COVERAGE_HEAT_STOPS[-1][1]


def blend_rect(canvas, x0, y0, x1, y1, color, alpha):
    canvas.blend_rect(int(x0), int(y0), int(x1), int(y1), color, alpha)


def blend_line(canvas, x0, y0, x1, y1, color, alpha=1.0, width=1):
    x0 = int(round(x0))
    y0 = int(round(y0))
    x1 = int(round(x1))
    y1 = int(round(y1))
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    radius = max(0, int(width) // 2)
    pixels = canvas.pixels
    canvas_width = canvas.width
    canvas_height = canvas.height
    stride = canvas_width * 3
    cr, cg, cb = color
    if alpha >= 1.0:
        while True:
            for yy in range(y0 - radius, y0 + radius + 1):
                if yy < 0 or yy >= canvas_height:
                    continue
                row = yy * stride
                for xx in range(x0 - radius, x0 + radius + 1):
                    if 0 <= xx < canvas_width:
                        index = row + xx * 3
                        pixels[index] = cr
                        pixels[index + 1] = cg
                        pixels[index + 2] = cb
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
    else:
        inv = 1.0 - alpha
        ar = cr * alpha
        ag = cg * alpha
        ab = cb * alpha
        while True:
            for yy in range(y0 - radius, y0 + radius + 1):
                if yy < 0 or yy >= canvas_height:
                    continue
                row = yy * stride
                for xx in range(x0 - radius, x0 + radius + 1):
                    if 0 <= xx < canvas_width:
                        index = row + xx * 3
                        pixels[index] = int(pixels[index] * inv + ar)
                        pixels[index + 1] = int(pixels[index + 1] * inv + ag)
                        pixels[index + 2] = int(pixels[index + 2] * inv + ab)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy


def blend_circle(canvas, cx, cy, r, color, alpha=1.0, outline=False, outline_width=2):
    cx = int(round(cx))
    cy = int(round(cy))
    r = int(round(r))
    rr = r * r
    inner = max(0, r - outline_width) ** 2 if outline else 0
    pixels = canvas.pixels
    stride = canvas.width * 3
    cr, cg, cb = color
    y0 = max(0, cy - r)
    y1 = min(canvas.height - 1, cy + r)
    x0 = max(0, cx - r)
    x1 = min(canvas.width - 1, cx + r)
    if alpha >= 1.0:
        for y in range(y0, y1 + 1):
            dy = y - cy
            index = y * stride + x0 * 3
            for x in range(x0, x1 + 1):
                d = (x - cx) * (x - cx) + dy * dy
                if d <= rr and d >= inner:
                    pixels[index] = cr
                    pixels[index + 1] = cg
                    pixels[index + 2] = cb
                index += 3
        return
    inv = 1.0 - alpha
    for y in range(y0, y1 + 1):
        dy = y - cy
        index = y * stride + x0 * 3
        for x in range(x0, x1 + 1):
            d = (x - cx) * (x - cx) + (y - cy) * (y - cy)
            if d <= rr and d >= inner:
                pixels[index] = int(pixels[index] * inv + cr * alpha)
                pixels[index + 1] = int(pixels[index + 1] * inv + cg * alpha)
                pixels[index + 2] = int(pixels[index + 2] * inv + cb * alpha)
            index += 3


def clipped_run(center, run_start, run_length, limit):
    absolute_start = center + run_start
    offset_start = max(0, -absolute_start)
    offset_end = min(run_length, limit - absolute_start)
    if offset_start >= offset_end:
        return None
    return absolute_start + offset_start, offset_start, offset_end


def radial_heat_kernel(radius):
    radius = int(radius)
    cached = _RADIAL_HEAT_KERNELS.get(radius)
    if cached is not None:
        return cached
    rr = radius * radius
    rows = []
    for dy in range(-radius, radius + 1):
        dy2 = dy * dy
        run_start = None
        weights = []
        for dx in range(-radius, radius + 1):
            d = dx * dx + dy2
            if d > rr:
                continue
            if run_start is None:
                run_start = dx
            falloff = 1.0 - (float(d) / float(rr))
            weights.append(falloff)
        if weights:
            rows.append((dy, run_start, tuple(weights)))
    _RADIAL_HEAT_KERNELS[radius] = rows
    return rows


def fog_reveal_kernel(radius, core_radius):
    key = (int(radius), int(core_radius))
    cached = _FOG_REVEAL_KERNELS.get(key)
    if cached is not None:
        return cached
    radius, core_radius = key
    rr = radius * radius
    core_rr = core_radius * core_radius
    falloff_denom = max(1, rr - core_rr)
    rows = []
    for dy in range(-radius, radius + 1):
        dy2 = dy * dy
        run_start = None
        values = []
        for dx in range(-radius, radius + 1):
            d = dx * dx + dy2
            if d > rr:
                continue
            if d <= core_rr:
                value = 255
            else:
                falloff = 1.0 - ((d - core_rr) / float(falloff_denom))
                value = int(255 * falloff * falloff)
            if value <= 0:
                continue
            if run_start is None:
                run_start = dx
            values.append(value)
        if values:
            rows.append((dy, run_start, bytes(values)))
    _FOG_REVEAL_KERNELS[key] = rows
    return rows


def stable_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def cache_key_matches(stored, current):
    return stable_json(stored) == stable_json(current)


def cache_dir(args):
    return Path(getattr(args, "coverage_cache_dir", DEFAULT_COVERAGE_CACHE_DIR))


def cache_digest(cache_key):
    return hashlib.sha256(stable_json(cache_key).encode("utf-8")).hexdigest()[:24]


def coverage_cache_paths(args, cache_key):
    if not getattr(args, "coverage_cache", True):
        return None
    digest = cache_digest(cache_key)
    return cache_dir(args) / ("fog-%s.json" % digest), cache_dir(args) / ("fog-%s.mask" % digest)


def heat_cache_paths(args, cache_key):
    if not getattr(args, "coverage_cache", True):
        return None
    digest = cache_digest(cache_key)
    return cache_dir(args) / ("heat-%s.json" % digest), cache_dir(args) / ("heat-%s.mask" % digest)


def generic_cache_paths(args, prefix, cache_key, body_suffix):
    if not getattr(args, "coverage_cache", True):
        return None
    digest = cache_digest(cache_key)
    return (
        cache_dir(args) / ("%s-%s.json" % (prefix, digest)),
        cache_dir(args) / ("%s-%s.%s" % (prefix, digest, body_suffix)),
    )


def read_canvas_cache(args, prefix, cache_key, width, height):
    paths = generic_cache_paths(args, prefix, cache_key, "rgb")
    if paths is None:
        return None, {}, "disabled"
    meta_path, body_path = paths
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("version") != CANVAS_LAYER_CACHE_VERSION or not cache_key_matches(meta.get("cacheKey"), cache_key):
            return None, {}, "miss"
        if int(meta.get("width", 0)) != int(width) or int(meta.get("height", 0)) != int(height):
            return None, {}, "stale"
        body = body_path.read_bytes()
        if len(body) != int(width) * int(height) * 3:
            return None, {}, "stale"
        canvas = Canvas(width, height, PALETTE["paper"])
        canvas.pixels[:] = body
        return canvas, meta, "hit"
    except (OSError, ValueError):
        return None, {}, "miss"


def write_canvas_cache(args, prefix, cache_key, canvas, extra_meta=None):
    paths = generic_cache_paths(args, prefix, cache_key, "rgb")
    if paths is None:
        return False
    meta_path, body_path = paths
    try:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        body_tmp = body_path.with_suffix(body_path.suffix + ".tmp")
        meta_tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
        body_tmp.write_bytes(bytes(canvas.pixels))
        meta = {
            "version": CANVAS_LAYER_CACHE_VERSION,
            "cacheKey": cache_key,
            "width": canvas.width,
            "height": canvas.height,
        }
        if extra_meta:
            meta.update(extra_meta)
        meta_tmp.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        body_tmp.replace(body_path)
        meta_tmp.replace(meta_path)
        return True
    except OSError:
        return False


def read_json_cache(args, prefix, cache_key, version):
    paths = generic_cache_paths(args, prefix, cache_key, "jsondata")
    if paths is None:
        return None, "disabled"
    meta_path, body_path = paths
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("version") != version or not cache_key_matches(meta.get("cacheKey"), cache_key):
            return None, "miss"
        return json.loads(body_path.read_text(encoding="utf-8")), "hit"
    except (OSError, ValueError):
        return None, "miss"


def write_json_cache(args, prefix, cache_key, version, data):
    paths = generic_cache_paths(args, prefix, cache_key, "jsondata")
    if paths is None:
        return False
    meta_path, body_path = paths
    try:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        body_tmp = body_path.with_suffix(body_path.suffix + ".tmp")
        meta_tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
        body_tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        meta_tmp.write_text(json.dumps({
            "version": version,
            "cacheKey": cache_key,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        body_tmp.replace(body_path)
        meta_tmp.replace(meta_path)
        return True
    except OSError:
        return False


def file_metadata(path):
    path = Path(path)
    try:
        stat = path.stat()
        return {
            "path": str(path),
            "size": int(stat.st_size),
            "mtimeNs": int(stat.st_mtime_ns),
        }
    except OSError:
        return {
            "path": str(path),
            "missing": True,
        }


def file_digest(path, byte_limit=None):
    digest = hashlib.sha256()
    remaining = None if byte_limit is None else int(byte_limit)
    with Path(path).open("rb") as handle:
        while remaining is None or remaining > 0:
            read_size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
            chunk = handle.read(read_size)
            if not chunk:
                break
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return digest.hexdigest()


def file_endswith_newline(path):
    path = Path(path)
    try:
        if path.stat().st_size <= 0:
            return True
        with path.open("rb") as handle:
            handle.seek(-1, 2)
            return handle.read(1) == b"\n"
    except OSError:
        return False


def cache_source_fingerprint():
    return [
        file_metadata(CACHE_DIR / "main_file_cache.dat"),
        file_metadata(CACHE_DIR / "main_file_cache.idx0"),
        file_metadata(CACHE_DIR / "main_file_cache.idx4"),
    ]


def places_fingerprint():
    return file_metadata(PLACES_PATH)


def load_fog_reveal_cache(args, cache_key, expected_length, current_node_keys):
    paths = coverage_cache_paths(args, cache_key)
    if paths is None:
        return None, set(), "disabled"
    meta_path, mask_path = paths
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not cache_key_matches(meta.get("cacheKey"), cache_key):
            return None, set(), "miss"
        cached_node_keys = set(meta.get("nodeKeys") or [])
        if not cached_node_keys.issubset(current_node_keys):
            return None, set(), "stale"
        mask = mask_path.read_bytes()
        if len(mask) != expected_length:
            return None, set(), "stale"
        return bytearray(mask), cached_node_keys, "hit"
    except (OSError, ValueError):
        return None, set(), "miss"


def write_fog_reveal_cache(args, cache_key, reveal, node_keys):
    paths = coverage_cache_paths(args, cache_key)
    if paths is None:
        return False
    meta_path, mask_path = paths
    try:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        mask_tmp = mask_path.with_suffix(mask_path.suffix + ".tmp")
        meta_tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
        mask_tmp.write_bytes(bytes(reveal))
        meta_tmp.write_text(json.dumps({
            "version": FOG_REVEAL_CACHE_VERSION,
            "cacheKey": cache_key,
            "nodeKeys": sorted(node_keys),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        mask_tmp.replace(mask_path)
        meta_tmp.replace(meta_path)
        return True
    except OSError:
        return False


def load_heat_mask_cache(args, cache_key, expected_length, current_node_values):
    paths = heat_cache_paths(args, cache_key)
    if paths is None:
        return None, {}, "disabled"
    meta_path, mask_path = paths
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("version") != HEAT_MASK_CACHE_VERSION or not cache_key_matches(meta.get("cacheKey"), cache_key):
            return None, {}, "miss"
        cached_node_values = {
            str(key): int(value)
            for key, value in (meta.get("nodeValues") or {}).items()
        }
        current_keys = set(current_node_values)
        cached_keys = set(cached_node_values)
        if not cached_keys.issubset(current_keys):
            return None, {}, "stale"
        for key, cached_value in cached_node_values.items():
            if int(current_node_values.get(key, -1)) < int(cached_value):
                return None, {}, "stale"
        mask = mask_path.read_bytes()
        if len(mask) != expected_length:
            return None, {}, "stale"
        return bytearray(mask), cached_node_values, "hit"
    except (OSError, ValueError):
        return None, {}, "miss"


def write_heat_mask_cache(args, cache_key, mask, node_values):
    paths = heat_cache_paths(args, cache_key)
    if paths is None:
        return False
    meta_path, mask_path = paths
    try:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        mask_tmp = mask_path.with_suffix(mask_path.suffix + ".tmp")
        meta_tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
        mask_tmp.write_bytes(bytes(mask))
        meta_tmp.write_text(json.dumps({
            "version": HEAT_MASK_CACHE_VERSION,
            "cacheKey": cache_key,
            "nodeValues": {key: int(node_values[key]) for key in sorted(node_values)},
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        mask_tmp.replace(mask_path)
        meta_tmp.replace(meta_path)
        return True
    except OSError:
        return False


def blend_radial_heat(canvas, cx, cy, r, color, alpha):
    cx = int(round(cx))
    cy = int(round(cy))
    r = int(round(r))
    if r <= 0 or alpha <= 0:
        return
    pixels = canvas.pixels
    width = canvas.width
    stride = width * 3
    cr, cg, cb = color
    for dy, run_start, weights in radial_heat_kernel(r):
        y = cy + dy
        if y < 0 or y >= canvas.height:
            continue
        clipped = clipped_run(cx, run_start, len(weights), width)
        if clipped is None:
            continue
        x0, offset_start, offset_end = clipped
        index = y * stride + x0 * 3
        for offset in range(offset_start, offset_end):
            falloff = weights[offset]
            local_alpha = alpha * falloff * falloff
            if local_alpha <= 0.003:
                index += 3
                continue
            inv = 1.0 - local_alpha
            pixels[index] = int(pixels[index] * inv + cr * local_alpha)
            pixels[index + 1] = int(pixels[index + 1] * inv + cg * local_alpha)
            pixels[index + 2] = int(pixels[index + 2] * inv + cb * local_alpha)
            index += 3


def draw_heat_gradient(canvas, x, y, width, height, alpha=1.0):
    x = int(round(x))
    y = int(round(y))
    width = int(round(width))
    height = int(round(height))
    if width <= 0 or height <= 0:
        return
    for offset in range(width):
        color = heat_color(offset / float(max(1, width - 1)))
        blend_rect(canvas, x + offset, y, x + offset, y + height - 1, color, alpha)
    canvas.rect(x - 1, y - 1, x + width, y - 1, PALETTE["frame"])
    canvas.rect(x - 1, y + height, x + width, y + height, PALETTE["frame"])
    canvas.rect(x - 1, y - 1, x - 1, y + height, PALETTE["frame"])
    canvas.rect(x + width, y - 1, x + width, y + height, PALETTE["frame"])


def draw_coverage_heatmap(canvas, nodes, project, map_x0, map_y0, map_w, map_h, work_scale, args, bounds=None):
    if not getattr(args, "coverage_heatmap", False):
        return {
            "coverageHeatNodes": 0,
            "coverageHeatMaxVisits": 0,
            "coverageHeatHighVisits": 0,
            "coverageHeatRadiusTiles": 0.0,
            "coverageHeatAlpha": 0.0,
            "coverageHeatCache": "disabled",
            "coverageHeatCachedNodes": 0,
            "coverageHeatRenderedNodes": 0,
        }
    visit_values = sorted(max(1, int(node["visits"])) for node in nodes.values())
    max_visits = visit_values[-1] if visit_values else 0
    if max_visits <= 0:
        return {
            "coverageHeatNodes": 0,
            "coverageHeatMaxVisits": 0,
            "coverageHeatHighVisits": 0,
            "coverageHeatRadiusTiles": args.coverage_heat_radius_tiles,
            "coverageHeatAlpha": args.coverage_heat_alpha,
            "coverageHeatCache": "disabled",
            "coverageHeatCachedNodes": 0,
            "coverageHeatRenderedNodes": 0,
        }

    radius = max(3, int(round(float(args.coverage_heat_radius_tiles) * work_scale)))
    high_visits = max(2, percentile_value(visit_values, args.coverage_heat_high_percentile))
    denom = max(1.0, math.log(high_visits, 8))
    gamma = max(0.2, float(args.coverage_heat_gamma))
    current_node_values = {}
    for node in nodes.values():
        visits = max(1, int(node["visits"]))
        intensity = clamp(math.log(visits, 8) / denom, 0.0, 1.0)
        intensity = math.pow(intensity, gamma)
        current_node_values[tile_key(node["tile"])] = max(1, int(round(255.0 * intensity)))

    cache_key = {
        "version": HEAT_MASK_CACHE_VERSION,
        "kind": "coverage-heat-mask",
        "bounds": bounds or {},
        "mapWidth": int(map_w),
        "mapHeight": int(map_h),
        "workScale": repr(float(work_scale)),
        "radius": int(radius),
        "highVisits": int(high_visits),
        "highPercentile": repr(float(args.coverage_heat_high_percentile)),
        "gamma": repr(float(args.coverage_heat_gamma)),
        "algorithm": "max-radial-square-falloff-mask-v3",
    }
    mask, cached_node_values, cache_status = load_heat_mask_cache(
        args, cache_key, max(1, map_w * map_h), current_node_values
    )
    if mask is None:
        mask = bytearray(max(1, map_w * map_h))
        cached_node_values = {}
    nodes_to_render = [
        (node, current_node_values.get(tile_key(node["tile"]), 0))
        for node in nodes.values()
        if current_node_values.get(tile_key(node["tile"]), 0) > cached_node_values.get(tile_key(node["tile"]), 0)
    ]
    if cache_status == "hit" and nodes_to_render:
        cache_status = "delta"

    kernel = radial_heat_kernel(radius)
    for node, node_value in nodes_to_render:
        if node_value <= 0:
            continue
        cx, cy = project(node["tile"])
        lx = int(cx - map_x0)
        ly = int(cy - map_y0)
        if lx < -radius or lx >= map_w + radius or ly < -radius or ly >= map_h + radius:
            continue
        for dy, run_start, weights in kernel:
            y = ly + dy
            if y < 0 or y >= map_h:
                continue
            clipped = clipped_run(lx, run_start, len(weights), map_w)
            if clipped is None:
                continue
            x0, offset_start, offset_end = clipped
            index = y * map_w + x0
            for offset in range(offset_start, offset_end):
                falloff = weights[offset]
                value = int(node_value * falloff * falloff)
                if value > mask[index]:
                    mask[index] = value
                index += 1

    cache_written = False
    if nodes_to_render or cache_status in ("miss", "stale"):
        cache_written = write_heat_mask_cache(args, cache_key, mask, current_node_values)

    heat_lut = []
    heat_alpha = float(args.coverage_heat_alpha)
    for value in range(256):
        if value <= 0:
            heat_lut.append(None)
            continue
        intensity = value / 255.0
        alpha = heat_alpha * (0.34 + 0.66 * intensity)
        if alpha <= 0.003:
            heat_lut.append(None)
            continue
        color = heat_color(intensity)
        heat_lut.append((1.0 - alpha, color[0] * alpha, color[1] * alpha, color[2] * alpha))

    pixels = canvas.pixels
    canvas_width = canvas.width
    heat_pixels = 0
    for y in range(map_h):
        mask_row = y * map_w
        pixel_row = (map_y0 + y) * canvas_width * 3 + map_x0 * 3
        for x in range(map_w):
            item = heat_lut[mask[mask_row + x]]
            if item is None:
                continue
            inv, ar, ag, ab = item
            index = pixel_row + x * 3
            pixels[index] = int(pixels[index] * inv + ar)
            pixels[index + 1] = int(pixels[index + 1] * inv + ag)
            pixels[index + 2] = int(pixels[index + 2] * inv + ab)
            heat_pixels += 1

    return {
        "coverageHeatNodes": len(nodes),
        "coverageHeatMaxVisits": max_visits,
        "coverageHeatHighVisits": high_visits,
        "coverageHeatHighPercentile": args.coverage_heat_high_percentile,
        "coverageHeatGamma": args.coverage_heat_gamma,
        "coverageHeatRadiusTiles": args.coverage_heat_radius_tiles,
        "coverageHeatAlpha": args.coverage_heat_alpha,
        "coverageHeatPixelRadius": radius,
        "coverageHeatPixels": heat_pixels,
        "coverageHeatCache": cache_status,
        "coverageHeatCacheWritten": cache_written,
        "coverageHeatCachedNodes": len(cached_node_values),
        "coverageHeatRenderedNodes": len(nodes_to_render),
    }


def draw_coverage_fog(canvas, nodes, project, map_x0, map_y0, map_w, map_h, work_scale, args, bounds=None):
    if not getattr(args, "coverage_fog", False):
        return {
            "coverageFogNodes": 0,
            "coverageFogRadiusTiles": 0.0,
            "coverageFogAlpha": 0.0,
            "coverageFogCoreFraction": 0.0,
        }
    if not nodes:
        return {
            "coverageFogNodes": 0,
            "coverageFogRadiusTiles": args.coverage_fog_radius_tiles,
            "coverageFogAlpha": args.coverage_fog_alpha,
            "coverageFogCoreFraction": args.coverage_fog_core_fraction,
        }

    radius = max(3, int(round(float(args.coverage_fog_radius_tiles) * work_scale)))
    core_fraction = clamp(float(args.coverage_fog_core_fraction), 0.0, 0.95)
    core_radius = int(round(radius * core_fraction))
    current_node_keys = set(tile_key(node["tile"]) for node in nodes.values())
    cache_key = {
        "version": FOG_REVEAL_CACHE_VERSION,
        "kind": "coverage-fog-reveal",
        "bounds": bounds or {},
        "mapWidth": int(map_w),
        "mapHeight": int(map_h),
        "workScale": repr(float(work_scale)),
        "radius": int(radius),
        "coreRadius": int(core_radius),
        "algorithm": "max-radial-square-falloff-v1",
    }
    reveal, cached_node_keys, cache_status = load_fog_reveal_cache(
        args, cache_key, max(1, map_w * map_h), current_node_keys
    )
    if reveal is None:
        reveal = bytearray(max(1, map_w * map_h))
        cached_node_keys = set()
    nodes_to_render = [
        node for node in nodes.values()
        if tile_key(node["tile"]) not in cached_node_keys
    ]
    if cache_status == "hit" and nodes_to_render:
        cache_status = "delta"
    kernel = fog_reveal_kernel(radius, core_radius)

    for node in nodes_to_render:
        cx, cy = project(node["tile"])
        lx = int(cx - map_x0)
        ly = int(cy - map_y0)
        if lx < -radius or lx >= map_w + radius or ly < -radius or ly >= map_h + radius:
            continue
        for dy, run_start, values in kernel:
            y = ly + dy
            if y < 0 or y >= map_h:
                continue
            clipped = clipped_run(lx, run_start, len(values), map_w)
            if clipped is None:
                continue
            x0, offset_start, offset_end = clipped
            row = y * map_w
            index = row + x0
            for offset in range(offset_start, offset_end):
                value = values[offset]
                if value > reveal[index]:
                    reveal[index] = value
                index += 1

    cache_written = False
    if nodes_to_render or cache_status in ("miss", "stale"):
        cache_written = write_fog_reveal_cache(args, cache_key, reveal, current_node_keys)

    pixels = canvas.pixels
    canvas_width = canvas.width
    fog_alpha = float(args.coverage_fog_alpha)
    fr, fg, fb = PALETTE["fog"]
    fog_lut = []
    for value in range(256):
        local_alpha = fog_alpha * (1.0 - (value / 255.0))
        if local_alpha <= 0.002:
            fog_lut.append(None)
        else:
            fog_lut.append((1.0 - local_alpha, fr * local_alpha, fg * local_alpha, fb * local_alpha))
    fogged_pixels = 0
    for y in range(map_h):
        mask_row = y * map_w
        pixel_row = (map_y0 + y) * canvas_width * 3 + map_x0 * 3
        for x in range(map_w):
            item = fog_lut[reveal[mask_row + x]]
            if item is None:
                continue
            inv, ar, ag, ab = item
            index = pixel_row + x * 3
            pixels[index] = int(pixels[index] * inv + ar)
            pixels[index + 1] = int(pixels[index + 1] * inv + ag)
            pixels[index + 2] = int(pixels[index + 2] * inv + ab)
            fogged_pixels += 1

    return {
        "coverageFogNodes": len(nodes),
        "coverageFogRadiusTiles": args.coverage_fog_radius_tiles,
        "coverageFogAlpha": args.coverage_fog_alpha,
        "coverageFogCoreFraction": args.coverage_fog_core_fraction,
        "coverageFogPixelRadius": radius,
        "coverageFogPixels": fogged_pixels,
        "coverageFogCache": cache_status,
        "coverageFogCacheWritten": cache_written,
        "coverageFogCachedNodes": len(cached_node_keys),
        "coverageFogRenderedNodes": len(nodes_to_render),
    }


def draw_cross(canvas, cx, cy, r, color, alpha, width):
    blend_line(canvas, cx - r, cy - r, cx + r, cy + r, color, alpha, width)
    blend_line(canvas, cx - r, cy + r, cx + r, cy - r, color, alpha, width)


def draw_death_marker(canvas, cx, cy, r, ss, alpha=1.0):
    blend_circle(canvas, cx, cy, r + 3 * ss, PALETTE["white"], 0.94 * alpha)
    blend_circle(canvas, cx, cy, r + ss, PALETTE["death"], 0.98 * alpha)
    draw_cross(canvas, cx, cy, r + 2 * ss, PALETTE["white"], 0.94 * alpha, max(2, ss + 1))


def draw_current_marker(canvas, cx, cy, r, ss, alpha=1.0):
    blend_circle(canvas, cx, cy, r + 9 * ss, PALETTE["death"], 0.58 * alpha)
    blend_circle(canvas, cx, cy, r + 6 * ss, PALETTE["white"], 0.92 * alpha,
                 outline=True, outline_width=max(3, 2 * ss))
    blend_circle(canvas, cx, cy, r + 3 * ss, PALETTE["current"], 0.98 * alpha,
                 outline=True, outline_width=max(3, 2 * ss))
    blend_circle(canvas, cx, cy, max(5 * ss, r // 3), PALETTE["current"], 0.98 * alpha)


def draw_bank_fallback(canvas, cx, cy, r, ss):
    blend_circle(canvas, cx, cy, r + 2 * ss, PALETTE["poi_outline"], 0.92)
    canvas.rect(cx - r, cy - r, cx + r, cy + r, PALETTE["bank"])
    canvas.rect(cx - r, cy - r, cx + r, cy - r + max(1, 2 * ss), PALETTE["white"])


def draw_shop_fallback(canvas, cx, cy, r, ss):
    blend_circle(canvas, cx, cy, r + 2 * ss, PALETTE["poi_outline"], 0.92)
    blend_circle(canvas, cx, cy, r, PALETTE["shop"], 0.98)
    canvas.rect(cx - r, cy - max(1, ss), cx + r, cy + max(1, ss), PALETTE["white"])


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


def downsample_canvas(canvas, factor):
    if factor <= 1:
        return canvas
    width = canvas.width // factor
    height = canvas.height // factor
    out = Canvas(width, height, PALETTE["paper"])
    source = canvas.pixels
    target = out.pixels
    source_stride = canvas.width * 3
    if factor == 2:
        out_index = 0
        for y in range(height):
            row0 = (y * 2) * source_stride
            row1 = row0 + source_stride
            for x in range(width):
                i0 = row0 + x * 6
                i1 = row1 + x * 6
                target[out_index] = (source[i0] + source[i0 + 3] + source[i1] + source[i1 + 3]) // 4
                target[out_index + 1] = (source[i0 + 1] + source[i0 + 4] + source[i1 + 1] + source[i1 + 4]) // 4
                target[out_index + 2] = (source[i0 + 2] + source[i0 + 5] + source[i1 + 2] + source[i1 + 5]) // 4
                out_index += 3
        return out
    factor_area = factor * factor
    out_index = 0
    for y in range(height):
        source_y = y * factor
        for x in range(width):
            total_r = 0
            total_g = 0
            total_b = 0
            source_x = x * factor * 3
            for yy in range(factor):
                index = (source_y + yy) * source_stride + source_x
                for _xx in range(factor):
                    total_r += source[index]
                    total_g += source[index + 1]
                    total_b += source[index + 2]
                    index += 3
            target[out_index] = total_r // factor_area
            target[out_index + 1] = total_g // factor_area
            target[out_index + 2] = total_b // factor_area
            out_index += 3
    return out


def latest_node(nodes):
    best = None
    for node in nodes.values():
        last_seen = node.get("lastSeen") or ""
        if last_seen and (best is None or last_seen > (best.get("lastSeen") or "")):
            best = node
    return best


def tile_key(tile):
    return "%d,%d,%d" % (int(tile["x"]), int(tile["y"]), int(tile.get("height", 0)))


def plausible_world_tile(tile, min_coord):
    if tile is None:
        return False
    return int(tile["x"]) >= min_coord and int(tile["y"]) >= min_coord


def filter_implausible_topology(topology, min_coord):
    if min_coord <= 0:
        return topology

    nodes = {}
    for key, node in topology["nodes"].items():
        if plausible_world_tile(node["tile"], min_coord):
            nodes[key] = node

    edges = {}
    for key, edge in topology["edges"].items():
        if plausible_world_tile(edge["from"], min_coord) and plausible_world_tile(edge["to"], min_coord):
            edges[key] = edge

    filtered = dict(topology)
    filtered["nodes"] = nodes
    filtered["edges"] = edges
    filtered["failureTiles"] = [tile for tile in topology["failureTiles"] if plausible_world_tile(tile, min_coord)]
    filtered["deathTiles"] = [tile for tile in topology["deathTiles"] if plausible_world_tile(tile, min_coord)]
    filtered["filteredImplausibleNodes"] = len(topology["nodes"]) - len(nodes)
    filtered["filteredImplausibleEdges"] = len(topology["edges"]) - len(edges)
    return filtered


def filter_nonlocal_edges(topology, max_distance):
    if max_distance <= 0:
        return topology

    edges = {}
    for key, edge in topology["edges"].items():
        if tile_distance(edge["from"], edge["to"]) <= max_distance:
            edges[key] = edge

    filtered = dict(topology)
    filtered["edges"] = edges
    filtered["filteredNonLocalEdges"] = len(topology["edges"]) - len(edges)
    return filtered


def unique_tiles(tiles):
    seen = set()
    result = []
    for tile in tiles:
        key = (int(tile["x"]), int(tile["y"]), int(tile.get("height", 0)))
        if key in seen:
            continue
        seen.add(key)
        result.append(tile)
    return result


def tile_distance(a, b):
    if a is None or b is None:
        return 999999
    if int(a.get("height", 0)) != int(b.get("height", 0)):
        return 999999
    return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))


def include_trace_tile(tile, surface_only):
    if tile is None:
        return False
    if surface_only and (int(tile.get("height", 0)) != 0 or int(tile["y"]) >= 6400):
        return False
    return True


def record_in_combat(record):
    if record.get("isInCombat") is not True:
        return False
    if safe_int(record.get("npcIndex"), 0) > 0:
        return True
    if safe_int(record.get("underAttackBy"), 0) > 0:
        return True
    if safe_int(record.get("underAttackBy2"), 0) > 0:
        return True
    return safe_int(record.get("hitpointsLost"), 0) > 0


def record_running_evidence(record, previous, current):
    activity = record.get("activity") if isinstance(record.get("activity"), dict) else {}
    explicit = activity.get("runningStep") is True
    energy_spent = safe_int(record.get("runEnergySpent"), 0) > 0
    run_enabled = record.get("runEnabled") is True
    distance = tile_distance(previous, current)
    inferred = run_enabled and 2 <= distance <= 3
    return {
        "running": explicit or energy_spent or inferred,
        "explicit": explicit,
        "energySpent": energy_spent,
        "inferred": inferred,
        "runEnabled": run_enabled,
    }


def annotate_running_edges(topology, extra_paths, surface_only, trace_profile=None, include_unscoped_traces=False):
    edges = topology["edges"]
    for edge in edges.values():
        edge.setdefault("runObservedTicks", 0)
        edge.setdefault("runEvidenceTicks", 0)
        edge.setdefault("runExplicitTicks", 0)
        edge.setdefault("runEnergySpentTicks", 0)
        edge.setdefault("runInferredTicks", 0)
        edge.setdefault("runEnabledTicks", 0)

    for record in iter_movement_traces(extra_paths, trace_profile, include_unscoped_traces):
        current = tile_from_record(record, "tile")
        previous = tile_from_record(record, "previousTile")
        if not include_trace_tile(current, surface_only) or not include_trace_tile(previous, surface_only):
            continue
        previous_key = tile_key(previous)
        current_key = tile_key(current)
        if previous_key == current_key:
            continue
        edge = edges.get((previous_key, current_key))
        if edge is None:
            continue

        evidence = record_running_evidence(record, previous, current)
        edge["runObservedTicks"] += 1
        if evidence["runEnabled"]:
            edge["runEnabledTicks"] += 1
        if evidence["running"]:
            edge["runEvidenceTicks"] += 1
        if evidence["explicit"]:
            edge["runExplicitTicks"] += 1
        if evidence["energySpent"]:
            edge["runEnergySpentTicks"] += 1
        if evidence["inferred"]:
            edge["runInferredTicks"] += 1

    return topology


def ensure_running_counters(edge):
    edge.setdefault("runObservedTicks", 0)
    edge.setdefault("runEvidenceTicks", 0)
    edge.setdefault("runExplicitTicks", 0)
    edge.setdefault("runEnergySpentTicks", 0)
    edge.setdefault("runInferredTicks", 0)
    edge.setdefault("runEnabledTicks", 0)


def empty_cached_topology():
    return {
        "nodes": {},
        "edges": {},
        "failureTiles": [],
        "deathTiles": [],
        "traceIds": set(),
        "sourcePaths": set(),
        "totalRecords": 0,
        "includedRecords": 0,
        "skippedRecords": 0,
    }


def process_topology_record(topology, record, surface_only):
    topology["totalRecords"] += 1
    current = tile_from_record(record, "tile")
    if not include_tile(current, surface_only):
        topology["skippedRecords"] += 1
        return False
    topology["includedRecords"] += 1

    source = record.get("_sourcePath")
    if source:
        topology["sourcePaths"].add(source)
    trace_id = str(record.get("traceId") or record.get("sessionId") or "")
    if trace_id:
        topology["traceIds"].add(trace_id)

    current_key = tile_key(current)
    failed = record_failed(record)
    died = record_death(record)
    in_combat = record_in_combat(record)
    node = topology["nodes"].setdefault(current_key, empty_node(current))
    node["visits"] += 1
    if in_combat:
        node["combatTicks"] += 1
    if failed:
        node["failures"] += 1
        topology["failureTiles"].append(current)
    if died:
        node["deaths"] += 1
        topology["deathTiles"].append(current)
    timestamp = str(record.get("timestamp") or "")
    if timestamp:
        if not node["firstSeen"]:
            node["firstSeen"] = timestamp
        node["lastSeen"] = timestamp

    previous = tile_from_record(record, "previousTile")
    if not include_tile(previous, surface_only):
        return True
    previous_key = tile_key(previous)
    topology["nodes"].setdefault(previous_key, empty_node(previous))
    if previous_key == current_key:
        return True

    edge_key = (previous_key, current_key)
    edge = topology["edges"].setdefault(edge_key, empty_edge(previous, current))
    edge["ticks"] += 1
    if failed:
        edge["failures"] += 1
    else:
        edge["successes"] += 1
    if in_combat:
        edge["combatTicks"] += 1
    edge["hitpointsLost"] += max(0, safe_int(record.get("hitpointsLost"), 0))
    edge["energySpent"] += max(0, safe_int(record.get("runEnergySpent"), 0))
    if timestamp:
        edge["lastSeen"] = timestamp

    ensure_running_counters(edge)
    evidence = record_running_evidence(record, previous, current)
    edge["runObservedTicks"] += 1
    if evidence["runEnabled"]:
        edge["runEnabledTicks"] += 1
    if evidence["running"]:
        edge["runEvidenceTicks"] += 1
    if evidence["explicit"]:
        edge["runExplicitTicks"] += 1
    if evidence["energySpent"]:
        edge["runEnergySpentTicks"] += 1
    if evidence["inferred"]:
        edge["runInferredTicks"] += 1
    return True


def serialize_topology(topology):
    return {
        "nodes": topology["nodes"],
        "edges": [
            {"fromKey": key[0], "toKey": key[1], "edge": edge}
            for key, edge in sorted(topology["edges"].items())
        ],
        "failureTiles": topology["failureTiles"],
        "deathTiles": topology["deathTiles"],
        "traceIds": sorted(topology["traceIds"]),
        "sourcePaths": sorted(topology["sourcePaths"]),
        "totalRecords": topology["totalRecords"],
        "includedRecords": topology["includedRecords"],
        "skippedRecords": topology["skippedRecords"],
    }


def deserialize_topology(data):
    topology = {
        "nodes": data.get("nodes", {}),
        "edges": {},
        "failureTiles": data.get("failureTiles", []),
        "deathTiles": data.get("deathTiles", []),
        "traceIds": set(data.get("traceIds", [])),
        "sourcePaths": set(data.get("sourcePaths", [])),
        "totalRecords": int(data.get("totalRecords", 0)),
        "includedRecords": int(data.get("includedRecords", 0)),
        "skippedRecords": int(data.get("skippedRecords", 0)),
    }
    for item in data.get("edges", []):
        key = (item["fromKey"], item["toKey"])
        edge = item["edge"]
        ensure_running_counters(edge)
        topology["edges"][key] = edge
    return topology


def iter_jsonl_from_offset(path, offset, start_line):
    line_no = int(start_line)
    with Path(path).open("rb") as handle:
        handle.seek(int(offset))
        for raw_line in handle:
            line_no += 1
            text = raw_line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                yield json.loads(text), str(path), line_no
            except json.JSONDecodeError:
                continue


def source_is_agent_batch(source):
    return AGENT_TRACE_PART in Path(source).parts


def source_is_player_trace(source):
    return PLAYER_TRACE_PART in Path(source).parts


def passive_trace_start(extra_paths, trace_profile=None, include_unscoped_traces=False):
    first = ""
    for path in trace_paths(extra_paths, include_agent_batch=False, include_legacy_recorder=False):
        for record, source, _line_no in iter_jsonl_from_offset(path, 0, 0):
            if not source_is_player_trace(source):
                continue
            if tile_from_record(record, "tile") is None:
                continue
            if not record_matches_profile(record, trace_profile, source, include_unscoped_traces):
                continue
            timestamp = str(record.get("timestamp") or "")
            if timestamp and (not first or timestamp < first):
                first = timestamp
    return first


def skip_trace_record(record, source, agent_batch_before=""):
    if agent_batch_before and source_is_agent_batch(source):
        timestamp = str(record.get("timestamp") or "")
        if not timestamp or timestamp >= agent_batch_before:
            return True
    return False


def process_trace_file(path, topology, surface_only, offset=0, start_line=0,
                       trace_profile=None, include_unscoped_traces=False,
                       agent_batch_before=""):
    processed = 0
    line_count = int(start_line)
    for record, source, line_no in iter_jsonl_from_offset(path, offset, start_line):
        line_count = line_no
        if tile_from_record(record, "tile") is None:
            continue
        if not record_matches_profile(record, trace_profile, source, include_unscoped_traces):
            continue
        if skip_trace_record(record, source, agent_batch_before):
            continue
        record["_sourcePath"] = source
        record["_sourceLine"] = line_no
        if process_topology_record(topology, record, surface_only):
            processed += 1
    return processed, line_count


def topology_cache_key(extra_paths, surface_only, trace_profile=None, include_unscoped_traces=False,
                       include_agent_batch=False, include_legacy_recorder=False, agent_batch_before=""):
    return {
        "version": TOPOLOGY_CACHE_VERSION,
        "kind": "movement-topology-prefix",
        "surfaceOnly": bool(surface_only),
        "traceProfile": trace_profile or "",
        "includeUnscopedTraces": bool(include_unscoped_traces),
        "includeAgentBatchTraces": bool(include_agent_batch),
        "includeLegacyRecorderTraces": bool(include_legacy_recorder),
        "agentBatchBefore": agent_batch_before or "",
        "extraPaths": [str(Path(path).expanduser()) for path in (extra_paths or [])],
    }


def topology_cache_paths(args, cache_key):
    if not getattr(args, "topology_cache", True):
        return None
    digest = cache_digest(cache_key)
    return cache_dir(args) / ("topology-%s.json" % digest)


def write_topology_cache(args, cache_key, topology, files):
    path = topology_cache_paths(args, cache_key)
    if path is None:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps({
            "version": TOPOLOGY_CACHE_VERSION,
            "cacheKey": cache_key,
            "files": files,
            "topology": serialize_topology(topology),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(path)
        return True
    except OSError:
        return False


def read_topology_cache(args, cache_key):
    path = topology_cache_paths(args, cache_key)
    if path is None:
        return None, "disabled"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != TOPOLOGY_CACHE_VERSION or not cache_key_matches(data.get("cacheKey"), cache_key):
            return None, "miss"
        return data, "hit"
    except (OSError, ValueError):
        return None, "miss"


def current_trace_entries(extra_paths, include_agent_batch=None, include_legacy_recorder=None):
    entries = []
    for path in trace_paths(extra_paths, include_agent_batch, include_legacy_recorder):
        meta = file_metadata(path)
        if not meta.get("missing"):
            entries.append(meta)
    return entries


def build_file_cache_entry(path, line_count):
    meta = file_metadata(path)
    meta["digest"] = file_digest(path)
    meta["lineCount"] = int(line_count)
    meta["endsWithNewline"] = file_endswith_newline(path)
    return meta


def load_topology_with_cache(extra_paths, surface_only, args):
    include_full_agent_batch = bool(getattr(args, "include_agent_batch_traces", False))
    include_historical_agent_batch = bool(getattr(args, "include_historical_agent_batch_traces", False))
    include_agent_batch = include_full_agent_batch or include_historical_agent_batch
    include_legacy_recorder = bool(getattr(args, "include_legacy_recorder_traces", False))
    agent_batch_before = ""
    if include_historical_agent_batch and not include_full_agent_batch:
        agent_batch_before = passive_trace_start(extra_paths, args.trace_profile, args.include_unscoped_traces)
    cache_key = topology_cache_key(
        extra_paths,
        surface_only,
        args.trace_profile,
        args.include_unscoped_traces,
        include_agent_batch,
        include_legacy_recorder,
        agent_batch_before,
    )
    current_entries = current_trace_entries(extra_paths, include_agent_batch, include_legacy_recorder)
    current_paths = [entry["path"] for entry in current_entries]
    cached, initial_status = read_topology_cache(args, cache_key)
    cold_reason = None
    processed_files = 0
    processed_records = 0
    cache_files = {}

    if cached is None:
        topology = empty_cached_topology()
        cache_status = initial_status
        cached_files = {}
        cold_reason = None
    else:
        topology = deserialize_topology(cached.get("topology", {}))
        cached_files = {entry["path"]: entry for entry in cached.get("files", [])}
        cache_status = "hit"
        missing_cached = set(cached_files) - set(current_paths)
        if missing_cached:
            cold_reason = "source-removed"

    if cold_reason is not None:
        topology = empty_cached_topology()
        cached_files = {}
        cache_status = "stale"

    if getattr(args, "topology_cache", True) is False:
        topology = empty_cached_topology()
        cached_files = {}
        cache_status = "disabled"

    for entry in current_entries:
        path = entry["path"]
        cached_entry = cached_files.get(path)
        offset = 0
        start_line = 0
        if cached_entry and cold_reason is None and cache_status != "disabled":
            cached_size = int(cached_entry.get("size", -1))
            current_size = int(entry.get("size", -1))
            if current_size < cached_size:
                cold_reason = "source-truncated"
            elif current_size == cached_size:
                if int(cached_entry.get("mtimeNs", -1)) != int(entry.get("mtimeNs", -2)):
                    if file_digest(path) != cached_entry.get("digest"):
                        cold_reason = "source-edited"
                    else:
                        cache_files[path] = build_file_cache_entry(path, cached_entry.get("lineCount", 0))
                        continue
                else:
                    cache_files[path] = cached_entry
                    continue
            else:
                if not cached_entry.get("endsWithNewline", False):
                    cold_reason = "partial-line"
                elif file_digest(path, cached_size) != cached_entry.get("digest"):
                    cold_reason = "prefix-edited"
                else:
                    offset = cached_size
                    start_line = int(cached_entry.get("lineCount", 0))
        if cold_reason is not None:
            break
        processed, line_count = process_trace_file(
            path, topology, surface_only, offset, start_line, args.trace_profile, args.include_unscoped_traces,
            agent_batch_before)
        processed_files += 1
        processed_records += processed
        cache_files[path] = build_file_cache_entry(path, line_count)

    if cold_reason is not None:
        topology = empty_cached_topology()
        cache_files = {}
        processed_files = 0
        processed_records = 0
        for entry in current_entries:
            path = entry["path"]
            processed, line_count = process_trace_file(
                path, topology, surface_only, 0, 0, args.trace_profile, args.include_unscoped_traces,
                agent_batch_before)
            processed_files += 1
            processed_records += processed
            cache_files[path] = build_file_cache_entry(path, line_count)
        cache_status = "stale"
    elif processed_records > 0 and cache_status == "hit":
        cache_status = "delta"

    cache_written = False
    if cache_status != "disabled" and (processed_files > 0 or cold_reason is not None or initial_status == "miss"):
        cache_written = write_topology_cache(
            args,
            cache_key,
            topology,
            [cache_files[path] for path in sorted(cache_files)],
        )

    latest = latest_node(topology["nodes"])
    topology["_cacheInfo"] = {
        "topologyCache": cache_status,
        "topologyCacheWritten": cache_written,
        "topologyCacheColdReason": cold_reason or "",
        "topologyCacheFiles": len(current_entries),
        "topologyCacheProcessedFiles": processed_files,
        "topologyCacheProcessedRecords": processed_records,
        "topologyCacheLatestSeen": latest.get("lastSeen") if latest else "",
        "topologyIncludeAgentBatchTraces": include_agent_batch,
        "topologyIncludeHistoricalAgentBatchTraces": include_historical_agent_batch and not include_full_agent_batch,
        "topologyIncludeLegacyRecorderTraces": include_legacy_recorder,
        "topologyAgentBatchBefore": agent_batch_before,
    }
    return topology


def dedup_death_sites(tiles):
    sites = []
    for tile in tiles:
        if not any(tile_distance(site, tile) <= 8 for site in sites):
            sites.append(tile)
    return unique_tiles(sites)


def load_places():
    if not PLACES_PATH.exists():
        return []
    data = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
    return data.get("places", [])


def in_bounds(tile, bounds):
    return (
        tile is not None
        and int(tile.get("height", 0)) == 0
        and bounds["minX"] <= int(tile["x"]) <= bounds["maxX"]
        and bounds["minY"] <= int(tile["y"]) <= bounds["maxY"]
    )


def poi_kind(place):
    kind = str(place.get("kind") or "").lower()
    tags = [str(tag).lower() for tag in place.get("tags", [])]
    if kind in ("hub", "town"):
        return "town"
    if kind == "bank":
        return "bank"
    if kind == "shop":
        return "shop"
    if kind != "surface_checkpoint" and ("city" in tags or "village" in tags):
        return "town"
    return None


def short_place_label(name):
    replacements = [
        ("Lumbridge Castle Courtyard", "Lumbridge"),
        ("Varrock Square", "Varrock"),
    ]
    for source, target in replacements:
        if name == source:
            return target
    return name


def static_labels_in_bounds(bounds):
    labels = []
    for label in STATIC_LABELS:
        if in_bounds(label.get("tile"), bounds):
            labels.append(label)
    return labels


def nearest_map_function(place_tile, objects, max_distance=8):
    best = None
    best_distance = max_distance + 1
    for obj in objects:
        if int(obj.get("mapFunction", -1)) < 0:
            continue
        distance = tile_distance(place_tile, obj)
        if distance < best_distance:
            best = obj
            best_distance = distance
    return best


def place_labels_in_bounds(bounds):
    labels = []
    seen = set()
    for place in load_places():
        tile = place.get("tile")
        if not in_bounds(tile, bounds):
            continue
        kind = poi_kind(place)
        if kind != "town":
            continue
        name = str(place.get("name") or place.get("id") or "").strip()
        if not name:
            continue
        if name in SUPPRESSED_PLACE_LABELS:
            continue
        text = short_place_label(name)
        if text in seen:
            continue
        seen.add(text)
        labels.append({
            "kind": kind,
            "text": text,
            "tile": {
                "x": int(tile["x"]),
                "y": int(tile["y"]),
                "height": int(tile.get("height", 0)),
            },
            "color": "yellow",
        })
    return labels


def merge_labels(labels):
    merged = []
    seen = set()
    for label in labels:
        key = str(label.get("text") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(label)
    return merged


def build_pois(world_map, bounds, args):
    if not args.show_pois or not world_map:
        labels = merge_labels(place_labels_in_bounds(bounds) + static_labels_in_bounds(bounds))
        return [], labels if args.poi_labels else []
    objects = world_map.get("objects", [])
    pois = []
    labels = []
    seen = set()
    if args.poi_mode == "all":
        for obj in objects:
            map_function = int(obj.get("mapFunction", -1))
            if map_function < 0:
                continue
            key = (int(obj["x"]), int(obj["y"]), int(obj.get("height", 0)), map_function)
            if key in seen:
                continue
            seen.add(key)
            pois.append({
                "kind": "mapfunction",
                "name": "mapfunction-%d" % map_function,
                "tile": {
                    "x": int(obj["x"]),
                    "y": int(obj["y"]),
                    "height": int(obj.get("height", 0)),
                },
                "mapFunction": map_function,
                "objectId": int(obj.get("id", -1)),
            })
        labels = merge_labels(place_labels_in_bounds(bounds) + static_labels_in_bounds(bounds))
        return pois, labels if args.poi_labels else []

    for place in load_places():
        tile = place.get("tile")
        if not in_bounds(tile, bounds):
            continue
        kind = poi_kind(place)
        if kind is None:
            continue
        name = str(place.get("name") or place.get("id") or "").strip()
        if not name:
            continue
        if kind in ("bank", "shop"):
            obj = nearest_map_function(tile, objects)
            poi_tile = obj if obj is not None else tile
            map_function = int(obj.get("mapFunction", -1)) if obj is not None else -1
            key = (kind, int(poi_tile["x"]), int(poi_tile["y"]), map_function)
            if key in seen:
                continue
            seen.add(key)
            pois.append({
                "kind": kind,
                "name": name,
                "tile": {
                    "x": int(poi_tile["x"]),
                    "y": int(poi_tile["y"]),
                    "height": int(poi_tile.get("height", 0)),
                },
                "mapFunction": map_function,
            })
        elif args.poi_labels:
            key = ("label", name)
            if key in seen:
                continue
            seen.add(key)
            labels.append({
                "kind": kind,
                "text": short_place_label(name),
                "tile": {
                    "x": int(tile["x"]),
                    "y": int(tile["y"]),
                    "height": int(tile.get("height", 0)),
                },
                "color": "yellow",
            })
    labels = merge_labels(labels + static_labels_in_bounds(bounds)) if args.poi_labels else labels
    return pois, labels


def world_map_info(source, tiles=None, objects=None, regions=0, stats=None):
    stats = stats or {}
    return {
        "worldMapTiles": len(tiles or []),
        "worldMapObjects": len(objects or []),
        "worldMapRegions": int(regions or 0),
        "worldMapSource": source,
        "worldMapObjectDefs": stats.get("objectDefs", 0),
        "worldMapMapSceneSprites": stats.get("mapSceneSprites", 0),
        "worldMapMapSceneObjects": stats.get("mapSceneObjects", 0),
        "worldMapMapFunctionObjects": stats.get("mapFunctionObjects", 0),
        "worldMapFootprintObjects": stats.get("footprintObjects", 0),
    }


def info_from_world_map(world_map, source):
    if not world_map:
        return world_map_info(source)
    return world_map_info(
        source,
        world_map.get("tiles", []),
        world_map.get("objects", []),
        world_map.get("regions", 0),
        world_map.get("stats", {}),
    )


def poi_cache_key(bounds, args, cache_source):
    return {
        "version": POI_CACHE_VERSION,
        "kind": "movement-topology-pois",
        "bounds": bounds,
        "plane": int(args.plane),
        "showPOIs": bool(args.show_pois),
        "poiMode": args.poi_mode,
        "poiLabels": bool(args.poi_labels),
        "worldMapSource": "none" if args.no_world_map or args.world_map_source == "none" else "cache",
        "cacheSource": cache_source,
        "places": places_fingerprint(),
    }


def load_or_build_pois(world_map, bounds, args, cache_source):
    cache_key = poi_cache_key(bounds, args, cache_source)
    cached, status = read_json_cache(args, "pois", cache_key, POI_CACHE_VERSION)
    if cached is not None:
        return cached.get("pois", []), cached.get("labels", []), status, world_map

    should_load_map = (
        world_map is None
        and args.show_pois
        and not args.no_world_map
        and args.world_map_source != "none"
    )
    if should_load_map:
        world_map = load_cache_world_map(bounds, plane=args.plane)
    pois, labels = build_pois(world_map, bounds, args)
    write_json_cache(args, "pois", cache_key, POI_CACHE_VERSION, {
        "pois": pois,
        "labels": labels,
    })
    return pois, labels, status, world_map


def tile_near_nodes(tile, nodes, radius_tiles):
    radius_sq = float(radius_tiles) * float(radius_tiles)
    tx = int(tile["x"])
    ty = int(tile["y"])
    th = int(tile.get("height", 0))
    for node in nodes.values():
        node_tile = node["tile"]
        if int(node_tile.get("height", 0)) != th:
            continue
        dx = tx - int(node_tile["x"])
        dy = ty - int(node_tile["y"])
        if dx * dx + dy * dy <= radius_sq:
            return True
    return False


def build_node_spatial_index(nodes, bucket_tiles):
    bucket_tiles = max(1, int(bucket_tiles))
    index = {}
    for node in nodes.values():
        node_tile = node["tile"]
        key = (
            int(node_tile.get("height", 0)),
            int(node_tile["x"]) // bucket_tiles,
            int(node_tile["y"]) // bucket_tiles,
        )
        index.setdefault(key, []).append(node_tile)
    return index


def tile_near_node_index(tile, node_index, bucket_tiles, radius_tiles):
    bucket_tiles = max(1, int(bucket_tiles))
    radius = float(radius_tiles)
    radius_sq = radius * radius
    tile_radius = int(math.ceil(radius))
    tx = int(tile["x"])
    ty = int(tile["y"])
    th = int(tile.get("height", 0))
    bx0 = (tx - tile_radius) // bucket_tiles
    bx1 = (tx + tile_radius) // bucket_tiles
    by0 = (ty - tile_radius) // bucket_tiles
    by1 = (ty + tile_radius) // bucket_tiles
    for bx in range(bx0, bx1 + 1):
        for by in range(by0, by1 + 1):
            for node_tile in node_index.get((th, bx, by), []):
                dx = tx - int(node_tile["x"])
                dy = ty - int(node_tile["y"])
                if dx * dx + dy * dy <= radius_sq:
                    return True
    return False


def filter_fogged_pois(pois, nodes, args):
    if not getattr(args, "hide_fogged_pois", False) or not getattr(args, "coverage_fog", False):
        return pois, 0, 0.0
    seen_radius = float(args.coverage_fog_radius_tiles) + float(args.coverage_fog_poi_extra_tiles)
    bucket_tiles = max(8, int(math.ceil(seen_radius)))
    node_index = build_node_spatial_index(nodes, bucket_tiles)
    visible = [
        poi for poi in pois
        if tile_near_node_index(poi["tile"], node_index, bucket_tiles, seen_radius)
    ]
    return visible, len(pois) - len(visible), seen_radius


def legend_items(args):
    if getattr(args, "running_overlay", False):
        return [
            ("ROUTE", PALETTE["walk"]),
            ("RUN", PALETTE["run"]),
            ("COMBAT", PALETTE["combat"]),
            ("PATH ENTROPY", PALETTE["failure"]),
            ("DEATH", PALETTE["death"]),
            ("LAST", PALETTE["current"]),
        ]
    return [
        ("ROUTE", PALETTE["trail"]),
        ("COMBAT", PALETTE["combat"]),
        ("PATH ENTROPY", PALETTE["failure"]),
        ("DEATH", PALETTE["death"]),
        ("LAST", PALETTE["current"]),
    ]


def legend_grid(args):
    return 3, 270 if getattr(args, "running_overlay", False) else 380


def running_summary(edges):
    return {
        "runningEdges": sum(1 for edge in edges.values() if int(edge.get("runEvidenceTicks", 0)) > 0),
        "runningTrailEdges": sum(
            1 for edge in edges.values()
            if edge_state(edge) == "trail" and int(edge.get("runEvidenceTicks", 0)) > 0
        ),
        "runningEvidenceTicks": sum(int(edge.get("runEvidenceTicks", 0)) for edge in edges.values()),
        "runningExplicitTicks": sum(int(edge.get("runExplicitTicks", 0)) for edge in edges.values()),
        "runningEnergySpentTicks": sum(int(edge.get("runEnergySpentTicks", 0)) for edge in edges.values()),
        "runningInferredTicks": sum(int(edge.get("runInferredTicks", 0)) for edge in edges.values()),
        "runEnabledTicks": sum(int(edge.get("runEnabledTicks", 0)) for edge in edges.values()),
    }


def short_timestamp(value):
    text = str(value or "")
    if not text:
        return "UNKNOWN"
    text = text[:16].replace("T", " ")
    if text.endswith("Z"):
        return text
    return text + "Z"


def draw_footer_decoration(canvas, x, y, stats, args):
    items = legend_items(args)
    ss = max(1, int(args.supersample))
    rows, col_gap = legend_grid(args)
    for index, (label, color) in enumerate(items):
        col = index // rows
        row = index % rows
        lx = x + col * col_gap * ss
        ly = y + (FOOTER_ITEM_MARKER_Y + row * FOOTER_ROW_GAP) * ss
        cx = lx + 21 * ss
        cy = ly + 11 * ss
        if label == "DEATH":
            draw_death_marker(canvas, cx, cy, 11 * ss, ss, 1.0)
            continue
        if label == "LAST":
            draw_current_marker(canvas, cx, cy, 16 * ss, ss, 1.0)
            continue
        canvas.rect(lx, ly, lx + 42 * ss, ly + 22 * ss, color)

    if getattr(args, "coverage_heatmap", False):
        bar_x = FOOTER_COVERAGE_X * ss
        bar_y = y + FOOTER_COVERAGE_BAR_Y * ss
        draw_heat_gradient(canvas, bar_x, bar_y, 250 * ss, 18 * ss, 0.90)


def add_annotation(command, x, y, pointsize, color, text):
    command.extend([
        "-fill", color_hex(color),
        "-pointsize", str(int(pointsize)),
        "-annotate", "+%d+%d" % (int(x), int(y)),
        str(text),
    ])


def add_shadow_text(command, x, y, pointsize, text, color=None):
    if color is None:
        color = PALETTE["osrs_yellow"]
    add_annotation(command, x + 2, y + 2, pointsize, PALETTE["text_shadow"], text)
    add_annotation(command, x, y, pointsize, color, text)


def add_right_annotation(command, right_margin, y, pointsize, color, text):
    command.extend([
        "-gravity", "NorthEast",
        "-fill", color_hex(color),
        "-pointsize", str(int(pointsize)),
        "-annotate", "+%d+%d" % (int(right_margin), int(y)),
        str(text),
        "-gravity", "NorthWest",
    ])


def add_right_shadow_text(command, right_margin, y, pointsize, text, color=None):
    if color is None:
        color = PALETTE["osrs_yellow"]
    shadow_margin = max(0, int(right_margin) - 2)
    add_right_annotation(command, shadow_margin, y + 2, pointsize, PALETTE["text_shadow"], text)
    add_right_annotation(command, right_margin, y, pointsize, color, text)


def wrapped_lines(text, max_chars, max_lines):
    if not text:
        return []
    lines = []
    for paragraph in str(text).splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines.extend(textwrap.wrap(paragraph, width=max_chars, break_long_words=False))
    if len(lines) <= max_lines:
        return lines
    clipped = lines[:max_lines]
    clipped[-1] = clipped[-1].rstrip(".,;: ") + "..."
    return clipped


def title_paragraph_layout(args, width, title):
    if args.title_paragraph_x >= 0:
        note_x = int(args.title_paragraph_x)
    else:
        note_x = max(540, min(width - 780, int(30 + len(title) * args.title_pointsize * 0.40)))
    right_margin = max(0, int(args.title_paragraph_right_margin))
    char_width = max(8, args.meta_pointsize * args.title_paragraph_char_factor)
    note_width = max(34, int((width - note_x - right_margin) / char_width))
    lines = wrapped_lines(args.title_paragraph, note_width, args.title_paragraph_lines)
    return note_x, right_margin, lines


def add_outline_text(command, x, y, pointsize, text, color, stroke_width=2):
    radius = max(1, int(stroke_width))
    for dx, dy in (
        (-radius, -radius), (0, -radius), (radius, -radius),
        (-radius, 0), (radius, 0),
        (-radius, radius), (0, radius), (radius, radius),
    ):
        add_annotation(command, x + dx, y + dy, pointsize, PALETTE["text_shadow"], text)
    add_annotation(command, x, y, pointsize, color, text)


def add_vector_circle(command, cx, cy, r, color, alpha=1.0, stroke_color=None, stroke_width=0):
    command.extend([
        "-fill", color_rgba(color, alpha),
        "-stroke", color_rgba(stroke_color, alpha) if stroke_color else "none",
        "-strokewidth", str(int(max(0, stroke_width))),
        "-draw", "circle %d,%d %d,%d" % (int(cx), int(cy), int(cx + r), int(cy)),
    ])


def add_vector_circle_outline(command, cx, cy, r, color, alpha=1.0, stroke_width=2):
    command.extend([
        "-fill", "none",
        "-stroke", color_rgba(color, alpha),
        "-strokewidth", str(int(max(1, stroke_width))),
        "-draw", "circle %d,%d %d,%d" % (int(cx), int(cy), int(cx + r), int(cy)),
    ])


def add_current_marker_overlay(command, marker):
    if not marker:
        return
    cx = int(marker["x"])
    cy = int(marker["y"])
    r = int(marker["r"])
    ss = max(1, int(marker.get("ss", 1)))
    add_vector_circle(command, cx, cy, r + 9 * ss, PALETTE["death"], 0.58)
    add_vector_circle_outline(command, cx, cy, r + 6 * ss, PALETTE["white"], 0.92, max(3, 2 * ss))
    add_vector_circle_outline(command, cx, cy, r + 3 * ss, PALETTE["current"], 0.98, max(3, 2 * ss))
    add_vector_circle(command, cx, cy, max(5 * ss, r // 3), PALETTE["current"], 0.98)


def apply_runescape_text(path, width, footer_top, stats, args):
    magick = shutil.which("magick")
    if not magick or not RUNESCAPE_FONT.exists():
        return False

    temp_path = path.with_name(path.stem + ".text.png")
    stat_columns = [
        [
        ("DATA POINTS", format_int(stats["records"])),
        ("VISITED TILES", format_int(stats["nodes"])),
        ("ROUTE EDGES", format_int(stats["edges"])),
        ("PATH ENTROPY", format_int(stats["failures"])),
        ("DEATHS", format_int(stats["deaths"])),
        ],
        [
            ("TRACE SESSIONS", format_int(stats["traceSessions"])),
            ("COMBAT LINKS", format_int(stats["combatEdges"])),
            ("ENTROPY SITES", format_int(stats["uniqueFailureSites"])),
            ("PEAK VISITS", format_int(stats["peakVisits"])),
            ("MAP SPAN", "%d X %d" % (stats["movementSpanX"], stats["movementSpanY"])),
        ],
    ]
    if getattr(args, "running_overlay", False):
        stat_columns[1] = [
            ("TRACE SESSIONS", format_int(stats["traceSessions"])),
            ("RUN LINKS", format_int(stats["runningTrailEdges"])),
            ("RUN SAMPLES", format_int(stats["runningEvidenceTicks"])),
            ("COMBAT LINKS", format_int(stats["combatEdges"])),
            ("MAP SPAN", "%d X %d" % (stats["movementSpanX"], stats["movementSpanY"])),
        ]
    command = [
        magick,
        str(path),
        "+antialias",
        "-font", str(RUNESCAPE_FONT),
    ]

    title = args.title_text or "MRFLAME MOVEMENT TOPOLOGY %s" % args.map_version
    add_shadow_text(command, 30, 90, args.title_pointsize, title)
    if args.title_paragraph:
        note_x, right_margin, paragraph_lines = title_paragraph_layout(args, width, title)
        for line_index, line in enumerate(paragraph_lines):
            y = args.title_paragraph_y + line_index * (args.meta_pointsize + 8)
            color = PALETTE["osrs_yellow"] if line_index == 0 else PALETTE["muted"]
            if args.title_paragraph_align == "right":
                add_right_shadow_text(command, right_margin, y, args.meta_pointsize, line, color)
            else:
                add_shadow_text(command, note_x, y, args.meta_pointsize, line, color)
    elif getattr(args, "coverage_heatmap", False):
        note_x = max(610, width - 390)
        add_shadow_text(command, note_x, 48, args.meta_pointsize + 4,
                        "route-learning telemetry", PALETTE["osrs_yellow"])
        add_shadow_text(command, note_x, 74, args.meta_pointsize,
                        "machine-learning route model in progress", PALETTE["muted"])
        add_shadow_text(command, note_x, 98, args.meta_pointsize,
                        "cool = sparse evidence   warm = dense traces", PALETTE["muted"])
    elif getattr(args, "coverage_fog", False):
        note_x = max(610, width - 420)
        add_shadow_text(command, note_x, 48, args.meta_pointsize + 4,
                        "fog-of-war coverage", PALETTE["osrs_yellow"])
        add_shadow_text(command, note_x, 74, args.meta_pointsize,
                        "clear = observed movement", PALETTE["muted"])
        add_shadow_text(command, note_x, 98, args.meta_pointsize,
                        "gray = unvisited map context", PALETTE["muted"])

    for label in stats.get("poiLabels", []):
        color = PALETTE["white"] if label.get("color") == "white" else PALETTE["osrs_yellow"]
        if label.get("outline"):
            add_outline_text(command, label["x"], label["y"], args.poi_label_pointsize, label["text"], color, 3)
        else:
            add_shadow_text(command, label["x"], label["y"], args.poi_label_pointsize, label["text"], color)

    legend_y = footer_top + FOOTER_SECTION_Y
    add_shadow_text(command, 30, legend_y, args.section_pointsize, "LEGEND")
    rows, col_gap = legend_grid(args)
    for index, (label, _color) in enumerate(legend_items(args)):
        col = index // rows
        row = index % rows
        x = 94 + col * col_gap
        y = footer_top + FOOTER_ITEM_TEXT_Y + row * FOOTER_ROW_GAP
        add_shadow_text(command, x, y, args.legend_pointsize, label)
    if getattr(args, "coverage_heatmap", False):
        add_shadow_text(command, FOOTER_COVERAGE_X, footer_top + FOOTER_COVERAGE_TITLE_Y,
                        args.legend_pointsize, "COVERAGE")
        add_shadow_text(command, FOOTER_COVERAGE_X, footer_top + FOOTER_COVERAGE_LABEL_Y,
                        args.meta_pointsize, "LOW", PALETTE["muted"])
        add_shadow_text(command, FOOTER_COVERAGE_X + 190, footer_top + FOOTER_COVERAGE_LABEL_Y,
                        args.meta_pointsize, "HIGH", PALETTE["muted"])

    stats_x = max(900, width - 760)
    add_shadow_text(command, stats_x, legend_y, args.section_pointsize, "STATS")
    for col, stat_lines in enumerate(stat_columns):
        left_x = stats_x + col * 360
        value_x = left_x + 236
        stat_y = footer_top + FOOTER_STATS_ROW_Y
        for label, value in stat_lines:
            add_shadow_text(command, left_x, stat_y, args.stats_pointsize, label)
            add_shadow_text(command, value_x, stat_y, args.stats_pointsize, value)
            stat_y += FOOTER_STATS_ROW_GAP

    add_current_marker_overlay(command, stats.get("currentMarker"))

    command.append(str(temp_path))
    subprocess.run(command, check=True)
    temp_path.replace(path)
    return True


def write_summary(path, topology, render_info, png_path, args):
    nodes = topology["nodes"]
    edges = topology["edges"]
    bounds = render_info["bounds"]
    movement_span = render_info.get("movementSpanTiles", {"x": 0, "y": 0})
    death_sites = dedup_death_sites(topology["deathTiles"])
    summary = {
        "schemaVersion": 2,
        "source": "unified-movement-traces",
        "mapVersion": args.map_version,
        "renderer": Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "render_movement_topology_v2.py",
        "surfaceOnly": args.surface_only,
        "records": topology["includedRecords"],
        "totalRecords": topology["totalRecords"],
        "skippedRecords": topology["skippedRecords"],
        "traceSessions": len(topology["traceIds"]),
        "sourceTraceFiles": len(topology["sourcePaths"]),
        "nodes": len(nodes),
        "edges": len(edges),
        "failures": len(topology["failureTiles"]),
        "uniqueFailureSites": len(unique_tiles(topology["failureTiles"])),
        "deathEvents": len(topology["deathTiles"]),
        "deaths": len(death_sites),
        "uniqueDeathSites": len(death_sites),
        "filteredImplausibleNodes": topology.get("filteredImplausibleNodes", 0),
        "filteredImplausibleEdges": topology.get("filteredImplausibleEdges", 0),
        "filteredNonLocalEdges": topology.get("filteredNonLocalEdges", 0),
        "combatEdges": sum(1 for edge in edges.values() if edge["combatTicks"] > 0 or edge["hitpointsLost"] > 0),
        "failureEdges": sum(1 for edge in edges.values() if edge["failures"] > 0),
        "peakVisits": max((node["visits"] for node in nodes.values()), default=0),
        "movementSpanTiles": movement_span,
        "renderSpanTiles": {
            "x": bounds["maxX"] - bounds["minX"] + 1,
            "y": bounds["maxY"] - bounds["minY"] + 1,
        },
        "worldMapTiles": render_info["worldMapTiles"],
        "worldMapObjects": render_info["worldMapObjects"],
        "worldMapSource": render_info["worldMapSource"],
        "worldMapRegions": render_info["worldMapRegions"],
        "worldMapObjectDefs": render_info.get("worldMapObjectDefs", 0),
        "worldMapMapSceneSprites": render_info.get("worldMapMapSceneSprites", 0),
        "worldMapMapSceneObjects": render_info.get("worldMapMapSceneObjects", 0),
        "worldMapMapFunctionObjects": render_info.get("worldMapMapFunctionObjects", 0),
        "worldMapFootprintObjects": render_info.get("worldMapFootprintObjects", 0),
        "poiCount": render_info.get("poiCount", 0),
        "poiLabelCount": render_info.get("poiLabelCount", 0),
        "pois": render_info.get("pois", []),
        "poiHiddenByFog": render_info.get("poiHiddenByFog", 0),
        "bounds": render_info["bounds"],
        "movementBounds": render_info.get("movementBounds", {}),
        "rawRenderBounds": render_info.get("rawRenderBounds", {}),
        "boundsQuantumTiles": render_info.get("boundsQuantumTiles", 0),
        "pixelsPerTile": render_info["pixelsPerTile"],
        "pixelWidth": render_info["pixelWidth"],
        "pixelHeight": render_info["pixelHeight"],
        "titleHeight": render_info.get("titleHeight", 0),
        "png": str(png_path),
        "fontApplied": render_info.get("fontApplied", False),
        "font": {
            "name": "RuneScape UF",
            "path": str(RUNESCAPE_FONT),
            "source": RUNESCAPE_FONT_SOURCE,
        },
        "cache": {
            **topology.get("_cacheInfo", {}),
            "baseLayerCache": render_info.get("baseLayerCache", "disabled"),
            "baseLayerCacheWritten": render_info.get("baseLayerCacheWritten", False),
            "poiCache": render_info.get("poiCache", "disabled"),
        },
        "style": {
            "backgroundMute": args.background_mute,
            "gridAlpha": args.grid_alpha,
            "majorGridAlpha": args.major_grid_alpha,
            "supersample": args.supersample,
            "routeWidth": args.route_width,
            "nodeAlpha": args.node_alpha,
            "maxEdgeDistance": args.max_edge_distance,
            "boundsQuantumTiles": args.bounds_quantum_tiles,
            "showPOIs": args.show_pois,
            "poiMode": args.poi_mode,
            "poiIconScale": args.poi_icon_scale,
            "hideFoggedPOIs": args.hide_fogged_pois,
            "titleText": args.title_text or "MRFLAME MOVEMENT TOPOLOGY %s" % args.map_version,
            "titleParagraph": args.title_paragraph,
            "titleParagraphAlign": args.title_paragraph_align,
            "titleParagraphRightMargin": args.title_paragraph_right_margin,
            "titleParagraphCharFactor": args.title_paragraph_char_factor,
            "titlePointsize": args.title_pointsize,
            "legendPointsize": args.legend_pointsize,
            "statsPointsize": args.stats_pointsize,
            "osrsYellow": "#FFFF00",
            "routingIssueLabel": "PATH ENTROPY",
        },
    }
    if getattr(args, "running_overlay", False):
        summary.update(running_summary(edges))
        summary["style"]["runningOverlay"] = True
        summary["style"]["runningLabel"] = "RUN"
        summary["style"]["runningColor"] = "#%02X%02X%02X" % PALETTE["run"]
    if getattr(args, "coverage_heatmap", False):
        summary.update({
            "coverageHeatmap": True,
            "coverageHeatNodes": render_info.get("coverageHeatNodes", 0),
            "coverageHeatMaxVisits": render_info.get("coverageHeatMaxVisits", 0),
            "coverageHeatHighVisits": render_info.get("coverageHeatHighVisits", 0),
            "coverageHeatHighPercentile": render_info.get("coverageHeatHighPercentile", 0.0),
            "coverageHeatGamma": render_info.get("coverageHeatGamma", 0.0),
            "coverageHeatRadiusTiles": render_info.get("coverageHeatRadiusTiles", 0.0),
            "coverageHeatAlpha": render_info.get("coverageHeatAlpha", 0.0),
            "coverageHeatPixelRadius": render_info.get("coverageHeatPixelRadius", 0),
            "coverageHeatPixels": render_info.get("coverageHeatPixels", 0),
            "coverageHeatCache": render_info.get("coverageHeatCache", "disabled"),
            "coverageHeatCacheWritten": render_info.get("coverageHeatCacheWritten", False),
            "coverageHeatCachedNodes": render_info.get("coverageHeatCachedNodes", 0),
            "coverageHeatRenderedNodes": render_info.get("coverageHeatRenderedNodes", 0),
            "coverageHeatGradient": [
                {"value": value, "color": "#%02X%02X%02X" % color}
                for value, color in COVERAGE_HEAT_STOPS
            ],
        })
        summary["style"]["coverageHeatmap"] = True
    if getattr(args, "coverage_fog", False):
        summary.update({
            "coverageFog": True,
            "coverageFogNodes": render_info.get("coverageFogNodes", 0),
            "coverageFogRadiusTiles": render_info.get("coverageFogRadiusTiles", 0.0),
            "coverageFogAlpha": render_info.get("coverageFogAlpha", 0.0),
            "coverageFogCoreFraction": render_info.get("coverageFogCoreFraction", 0.0),
            "coverageFogPixelRadius": render_info.get("coverageFogPixelRadius", 0),
            "coverageFogPixels": render_info.get("coverageFogPixels", 0),
            "coverageFogPoiExtraTiles": render_info.get("coverageFogPoiExtraTiles", 0.0),
            "coverageFogPoiSeenRadiusTiles": render_info.get("coverageFogPoiSeenRadiusTiles", 0.0),
            "coverageFogCache": render_info.get("coverageFogCache", "disabled"),
            "coverageFogCacheWritten": render_info.get("coverageFogCacheWritten", False),
            "coverageFogCachedNodes": render_info.get("coverageFogCachedNodes", 0),
            "coverageFogRenderedNodes": render_info.get("coverageFogRenderedNodes", 0),
        })
        summary["style"]["coverageFog"] = True
        summary["style"]["coverageFogColor"] = "#%02X%02X%02X" % PALETTE["fog"]
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
    tile_min_x = min(tile["x"] for tile in tiles)
    tile_max_x = max(tile["x"] for tile in tiles)
    tile_min_y = min(tile["y"] for tile in tiles)
    tile_max_y = max(tile["y"] for tile in tiles)
    movement_span_x = max(1, tile_max_x - tile_min_x + 1)
    movement_span_y = max(1, tile_max_y - tile_min_y + 1)
    raw_min_x = tile_min_x - pad
    raw_max_x = tile_max_x + pad
    raw_min_y = tile_min_y - pad
    raw_max_y = tile_max_y + pad
    min_x, max_x, min_y, max_y = quantize_render_bounds(
        raw_min_x, raw_max_x, raw_min_y, raw_max_y, args.bounds_quantum_tiles
    )
    span_x = max(1, max_x - min_x + 1)
    span_y = max(1, max_y - min_y + 1)
    ss = max(1, int(args.supersample))
    scale = float(args.pixels_per_tile)
    if args.max_map_pixels > 0:
        scale = min(scale, float(args.max_map_pixels) / float(max(span_x, span_y)))
    scale = max(0.2, scale)
    work_scale = scale * ss
    if work_scale >= 1.0:
        # The cache tile painter fills integer pixel blocks. Fractional
        # supersampled tile sizes leave seams that downsample into a grid.
        scale = max(1.0 / ss, math.floor(work_scale + 1e-9) / float(ss))

    map_w = int(math.ceil(span_x * scale)) + 1
    map_h = int(math.ceil(span_y * scale)) + 1
    margin = 28
    width = max(map_w + margin * 2, 980)
    title_h = 150
    if args.title_paragraph:
        title = args.title_text or "MRFLAME MOVEMENT TOPOLOGY %s" % args.map_version
        paragraph_lines = title_paragraph_layout(args, width, title)[2]
        title_h = max(150, int(args.title_paragraph_y + len(paragraph_lines) * (args.meta_pointsize + 8) + 24))
    footer_h = FOOTER_HEIGHT
    height = map_h + title_h + footer_h
    map_x0 = (width - map_w) // 2
    map_y0 = title_h

    work_w = width * ss
    work_h = height * ss
    work_scale = scale * ss
    work_map_w = map_w * ss
    work_map_h = map_h * ss
    work_map_x0 = map_x0 * ss
    work_map_y0 = map_y0 * ss

    def project(tile):
        x = int(work_map_x0 + (int(tile["x"]) - min_x) * work_scale)
        y = int(work_map_y0 + work_map_h - 1 - (int(tile["y"]) - min_y) * work_scale)
        return x, y

    movement_bounds = {"minX": tile_min_x, "maxX": tile_max_x, "minY": tile_min_y, "maxY": tile_max_y}
    raw_render_bounds = {"minX": raw_min_x, "maxX": raw_max_x, "minY": raw_min_y, "maxY": raw_max_y}
    bounds = {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y}
    cache_source = cache_source_fingerprint()
    expected_world_map_source = "none" if args.no_world_map or args.world_map_source == "none" else "2006Scape Server/data/cache"
    world_map = None
    world_info = world_map_info(expected_world_map_source)
    base_cache_key = {
        "version": CANVAS_LAYER_CACHE_VERSION,
        "kind": "movement-topology-base",
        "mapVersion": args.map_version,
        "bounds": bounds,
        "boundsQuantumTiles": int(args.bounds_quantum_tiles),
        "plane": int(args.plane),
        "worldMapSource": expected_world_map_source,
        "cacheSource": cache_source,
        "width": work_w,
        "height": work_h,
        "map": {
            "x": work_map_x0,
            "y": work_map_y0,
            "width": work_map_w,
            "height": work_map_h,
            "scale": repr(float(work_scale)),
        },
        "titleHeight": title_h * ss,
        "backgroundMute": args.background_mute,
        "palette": {
            "paper": PALETTE["paper"],
            "paper2": PALETTE["paper2"],
            "frame": PALETTE["frame"],
            "land": PALETTE["land"],
        },
    }
    canvas, base_meta, base_cache_status = read_canvas_cache(args, "base", base_cache_key, work_w, work_h)
    base_cache_written = False
    if canvas is not None:
        world_info = base_meta.get("worldMapInfo", world_info)
    else:
        canvas = Canvas(work_w, work_h, PALETTE["paper"])
        blend_rect(canvas, 0, 0, work_w - 1, title_h * ss - 1, PALETTE["paper2"], 1.0)

        canvas.rect(work_map_x0 - ss, work_map_y0 - ss,
                    work_map_x0 + work_map_w, work_map_y0 + work_map_h, PALETTE["frame"])
        canvas.rect(work_map_x0, work_map_y0,
                    work_map_x0 + work_map_w - 1, work_map_y0 + work_map_h - 1, PALETTE["land"])

    if canvas is not None and base_cache_status != "hit" and expected_world_map_source.startswith("2006Scape Server"):
        world_map = load_cache_world_map(bounds, plane=args.plane)
        world_info = info_from_world_map(world_map, expected_world_map_source)
        draw_world_map(canvas, world_map, project, work_scale)
        blend_rect(canvas, work_map_x0, work_map_y0,
                   work_map_x0 + work_map_w - 1, work_map_y0 + work_map_h - 1,
                   PALETTE["paper"], args.background_mute)
    if base_cache_status != "hit":
        base_cache_written = write_canvas_cache(args, "base", base_cache_key, canvas, {
            "worldMapInfo": world_info,
        })

    fog_info = draw_coverage_fog(canvas, nodes, project, work_map_x0, work_map_y0,
                                 work_map_w, work_map_h, work_scale, args, bounds=bounds)
    heat_info = draw_coverage_heatmap(canvas, nodes, project, work_map_x0, work_map_y0,
                                      work_map_w, work_map_h, work_scale, args, bounds=bounds)

    grid_start_x = int(min_x // 10 * 10)
    grid_start_y = int(min_y // 10 * 10)
    for gx in range(grid_start_x, max_x + 1, 10):
        x = work_map_x0 + (gx - min_x) * work_scale
        major = gx % 50 == 0
        color = PALETTE["grid_major"] if major else PALETTE["grid"]
        alpha = args.major_grid_alpha if major else args.grid_alpha
        width_px = max(1, ss if major else max(1, ss // 2))
        blend_line(canvas, x, work_map_y0, x, work_map_y0 + work_map_h - 1, color, alpha, width_px)
    for gy in range(grid_start_y, max_y + 1, 10):
        y = work_map_y0 + work_map_h - 1 - (gy - min_y) * work_scale
        major = gy % 50 == 0
        color = PALETTE["grid_major"] if major else PALETTE["grid"]
        alpha = args.major_grid_alpha if major else args.grid_alpha
        width_px = max(1, ss if major else max(1, ss // 2))
        blend_line(canvas, work_map_x0, y, work_map_x0 + work_map_w - 1, y, color, alpha, width_px)

    max_ticks = max([edge["ticks"] for edge in edges.values()] or [1])
    route_width = max(1, int(round(args.route_width * ss)))
    halo_width = max(route_width + ss * 2, int(round(route_width * 1.9)))
    sorted_edges = sorted(edges.values(), key=lambda edge: (edge_state(edge) != "trail", edge_state(edge) == "failure", edge["ticks"]))
    for edge in sorted_edges:
        ax, ay = project(edge["from"])
        bx, by = project(edge["to"])
        blend_line(canvas, ax, ay, bx, by, PALETTE["trail_halo"], 0.29, halo_width)
    for edge in sorted_edges:
        ax, ay = project(edge["from"])
        bx, by = project(edge["to"])
        state = edge_state(edge)
        alpha = 0.96 if state == "trail" else 0.98
        if getattr(args, "running_overlay", False) and state == "trail" and int(edge.get("runEvidenceTicks", 0)) <= 0:
            alpha = 0.82
        width_px = route_width + (ss if state != "trail" else 0)
        blend_line(canvas, ax, ay, bx, by, edge_display_color(edge, max_ticks, args), alpha, width_px)

    max_visits = max(node["visits"] for node in nodes.values())
    for node in nodes.values():
        x, y = project(node["tile"])
        if max_visits <= 1:
            intensity = 0.0
        else:
            intensity = math.log(max(1, node["visits"]), 8) / max(1.0, math.log(max_visits, 8))
        radius = max(1, int(round((0.18 + 0.20 * intensity) * work_scale)))
        color = mix(PALETTE["trail"], PALETTE["white"], 0.30 + intensity * 0.28)
        alpha = clamp(args.node_alpha + intensity * 0.22, 0.0, 0.88)
        blend_circle(canvas, x, y, radius, color, alpha)

    marker_r = max(4 * ss, int(round(work_scale * 0.82)))
    for tile in unique_tiles(topology["failureTiles"]):
        x, y = project(tile)
        blend_circle(canvas, x, y, marker_r, PALETTE["failure"], 0.96, outline=True, outline_width=max(2, ss + 1))
        draw_cross(canvas, x, y, marker_r - ss, PALETTE["failure"], 0.82, max(1, ss))
    death_sites = dedup_death_sites(topology["deathTiles"])
    death_r = marker_r + 5 * ss

    pois, poi_labels, poi_cache_status, world_map = load_or_build_pois(world_map, bounds, args, cache_source)
    pois, hidden_poi_count, poi_seen_radius = filter_fogged_pois(pois, nodes, args)
    map_functions = {}
    if pois:
        map_functions = load_background_sprites(name="mapfunction", limit=100)
    for poi in pois:
        x, y = project(poi["tile"])
        icon_scale = max(1.0, float(args.poi_icon_scale) * ss)
        radius = max(6 * ss, int(round(7 * icon_scale)))
        if args.poi_mode != "all":
            blend_circle(canvas, x, y, radius + 3 * ss, PALETTE["death"], 0.46)
            blend_circle(canvas, x, y, radius + ss, PALETTE["poi_outline"], 0.88, outline=True,
                         outline_width=max(2, ss + 1))
        sprite = map_functions.get(int(poi.get("mapFunction", -1)))
        if sprite is not None:
            draw_indexed_sprite(canvas, sprite, x, y, icon_scale, 1.0)
        elif poi["kind"] == "bank":
            draw_bank_fallback(canvas, x, y, radius, ss)
        elif poi["kind"] == "shop":
            draw_shop_fallback(canvas, x, y, radius, ss)
        else:
            blend_circle(canvas, x, y, max(2 * ss, radius // 2), PALETTE["poi_outline"], 0.92)

    rendered_poi_labels = []
    for label in poi_labels:
        x, y = project(label["tile"])
        rendered_poi_labels.append({
            "text": label["text"],
            "x": int(round(x / ss + int(label.get("dx", -24)))),
            "y": int(round(y / ss + int(label.get("dy", -18)))),
            "color": label.get("color", "yellow"),
            "outline": bool(label.get("outline", False)),
        })

    for tile in death_sites:
        x, y = project(tile)
        draw_death_marker(canvas, x, y, death_r, ss, 1.0)

    current = latest_node(nodes)
    if current is not None:
        x, y = project(current["tile"])
        current_r = max(marker_r + 18 * ss, int(round(work_scale * 2.6)))
        draw_current_marker(canvas, x, y, current_r, ss, 1.0)
        current_marker = {
            "x": int(round(x / ss)),
            "y": int(round(y / ss)),
            "r": int(round(current_r / ss)),
            "ss": 1,
        }
    else:
        current_marker = None

    footer_top = (map_y0 + map_h) * ss
    blend_rect(canvas, 0, footer_top, work_w - 1, work_h - 1, PALETTE["paper2"], 1.0)
    blend_line(canvas, margin * ss, footer_top + FOOTER_RULE_Y * ss,
               (width - margin) * ss, footer_top + FOOTER_RULE_Y * ss,
               PALETTE["frame"], 0.30, max(1, ss))
    legend_stats = {
        "records": topology["includedRecords"],
        "nodes": len(nodes),
        "edges": len(edges),
        "failures": len(topology["failureTiles"]),
        "deathEvents": len(topology["deathTiles"]),
        "deaths": len(death_sites),
        "uniqueFailureSites": len(unique_tiles(topology["failureTiles"])),
        "traceSessions": len(topology["traceIds"]),
        "combatEdges": sum(1 for edge in edges.values() if edge["combatTicks"] > 0 or edge["hitpointsLost"] > 0),
        "peakVisits": max((node["visits"] for node in nodes.values()), default=0),
        "movementSpanX": movement_span_x,
        "movementSpanY": movement_span_y,
        "pixelsPerTile": scale,
        "bounds": bounds,
        "latestSeen": current.get("lastSeen") if current is not None else "",
        "poiLabels": rendered_poi_labels,
        "currentMarker": current_marker,
    }
    if getattr(args, "running_overlay", False):
        legend_stats.update(running_summary(edges))
    draw_footer_decoration(canvas, 30 * ss, footer_top, legend_stats, args)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    final_canvas = downsample_canvas(canvas, ss)
    final_canvas.save_png(output)
    font_applied = apply_runescape_text(output, width, map_y0 + map_h, legend_stats, args)
    return {
        "bounds": bounds,
        "movementBounds": movement_bounds,
        "rawRenderBounds": raw_render_bounds,
        "boundsQuantumTiles": int(args.bounds_quantum_tiles),
        "movementSpanTiles": {
            "x": movement_span_x,
            "y": movement_span_y,
        },
        "pixelsPerTile": scale,
        "pixelWidth": width,
        "pixelHeight": height,
        "titleHeight": title_h,
        "worldMapTiles": world_info.get("worldMapTiles", 0),
        "worldMapObjects": world_info.get("worldMapObjects", 0),
        "worldMapRegions": world_info.get("worldMapRegions", 0),
        "worldMapSource": world_info.get("worldMapSource", expected_world_map_source),
        "worldMapObjectDefs": world_info.get("worldMapObjectDefs", 0),
        "worldMapMapSceneSprites": world_info.get("worldMapMapSceneSprites", 0),
        "worldMapMapSceneObjects": world_info.get("worldMapMapSceneObjects", 0),
        "worldMapMapFunctionObjects": world_info.get("worldMapMapFunctionObjects", 0),
        "worldMapFootprintObjects": world_info.get("worldMapFootprintObjects", 0),
        "baseLayerCache": base_cache_status,
        "baseLayerCacheWritten": base_cache_written,
        "poiCache": poi_cache_status,
        "poiCount": len(pois),
        "poiHiddenByFog": hidden_poi_count,
        "coverageFogPoiExtraTiles": args.coverage_fog_poi_extra_tiles if getattr(args, "hide_fogged_pois", False) else 0.0,
        "coverageFogPoiSeenRadiusTiles": poi_seen_radius,
        "poiLabelCount": len(rendered_poi_labels),
        "pois": pois,
        "fontApplied": font_applied,
        **fog_info,
        **heat_info,
    }


def main(default_output=None, default_summary=None, default_map_version="V2",
         default_show_pois=False, default_poi_mode="selected", default_poi_icon_scale=1.0,
         default_running_overlay=False, default_coverage_heatmap=False,
         default_coverage_fog=False, default_coverage_fog_alpha=0.40,
         default_coverage_fog_radius_tiles=18.0, default_coverage_fog_core_fraction=0.34,
         default_hide_fogged_pois=False, default_coverage_fog_poi_extra_tiles=30.0,
         default_coverage_heat_radius_tiles=18.0, default_coverage_heat_alpha=0.12,
         default_coverage_heat_high_percentile=0.98, default_coverage_heat_gamma=1.25,
         default_title_text=None, default_title_paragraph=None,
         default_title_paragraph_x=-1, default_title_paragraph_y=35,
         default_title_paragraph_lines=5, default_title_paragraph_align="left",
         default_title_paragraph_right_margin=34, default_title_paragraph_char_factor=0.56,
         default_meta_pointsize=18, default_include_historical_agent_batch_traces=False):
    parser = argparse.ArgumentParser(
        description="Render movement topology with the shared engine used by the active profile, heat, and fog maps."
    )
    parser.add_argument("--trace-file", action="append", help="Extra trace JSONL file or directory to include.")
    parser.add_argument("--trace-profile", default=default_trace_profile(),
                        help="Only use traces recorded by this player/profile. Defaults to RS_TRACE_PROFILE or RS_PROFILE.")
    parser.add_argument("--include-unscoped-traces", action="store_true",
                        help="When filtering by profile, also include legacy traces with no player name.")
    parser.add_argument("--include-agent-batch-traces", action="store_true",
                        help="Include all agent batch movement traces in addition to passive player traces.")
    parser.add_argument("--include-historical-agent-batch-traces", action="store_true",
                        default=default_include_historical_agent_batch_traces,
                        help="Backfill agent batch movement traces recorded before passive player tracing began.")
    parser.add_argument("--no-historical-agent-batch-traces", dest="include_historical_agent_batch_traces",
                        action="store_false")
    parser.add_argument("--include-legacy-recorder-traces", action="store_true",
                        help="Include legacy local movement_traces*.jsonl recorder files.")
    parser.add_argument("--pixels-per-tile", type=float, default=4.0)
    parser.add_argument("--max-map-pixels", type=int, default=3200)
    parser.add_argument("--padding-tiles", type=int, default=20)
    parser.add_argument("--bounds-quantum-tiles", type=int, default=64,
                        help="Quantize render bounds to this tile grid so small trace growth does not invalidate base caches.")
    parser.add_argument("--surface-only", action="store_true", default=True)
    parser.add_argument("--include-underground", action="store_true")
    parser.add_argument("--plane", type=int, default=0)
    parser.add_argument("--world-map-source", choices=("cache", "none"), default="cache")
    parser.add_argument("--no-world-map", action="store_true", help="Do not paint a world map as the background.")
    parser.add_argument("--supersample", type=int, default=2)
    parser.add_argument("--background-mute", type=float, default=0.18)
    parser.add_argument("--grid-alpha", type=float, default=0.0)
    parser.add_argument("--major-grid-alpha", type=float, default=0.0)
    parser.add_argument("--route-width", type=float, default=2.2)
    parser.add_argument("--node-alpha", type=float, default=0.28)
    parser.add_argument("--map-version", default=default_map_version)
    parser.add_argument("--title-text", default=default_title_text,
                        help="Display title to draw in the map title bar.")
    parser.add_argument("--title-paragraph", default=default_title_paragraph,
                        help="Short explanatory paragraph to draw in the map title bar.")
    parser.add_argument("--title-paragraph-x", type=int, default=default_title_paragraph_x)
    parser.add_argument("--title-paragraph-y", type=int, default=default_title_paragraph_y)
    parser.add_argument("--title-paragraph-lines", type=int, default=default_title_paragraph_lines)
    parser.add_argument("--title-paragraph-align", choices=("left", "right"),
                        default=default_title_paragraph_align)
    parser.add_argument("--title-paragraph-right-margin", type=int,
                        default=default_title_paragraph_right_margin)
    parser.add_argument("--title-paragraph-char-factor", type=float,
                        default=default_title_paragraph_char_factor)
    parser.add_argument("--show-pois", action="store_true", default=default_show_pois,
                        help="Draw cache-backed minimap icons.")
    parser.add_argument("--no-show-pois", dest="show_pois", action="store_false")
    parser.add_argument("--poi-mode", choices=("selected", "all"), default=default_poi_mode,
                        help="Use selected navigation POIs or every cache mapfunction object in the render bounds.")
    parser.add_argument("--poi-labels", action="store_true", default=default_show_pois,
                        help="Label town/hub POIs.")
    parser.add_argument("--no-poi-labels", dest="poi_labels", action="store_false")
    parser.add_argument("--poi-icon-scale", type=float, default=default_poi_icon_scale)
    parser.add_argument("--poi-label-pointsize", type=int, default=28)
    parser.add_argument("--hide-fogged-pois", action="store_true", default=default_hide_fogged_pois,
                        help="Hide POI icons outside the fog-of-war explored radius.")
    parser.add_argument("--no-hide-fogged-pois", dest="hide_fogged_pois", action="store_false")
    parser.add_argument("--running-overlay", action="store_true", default=default_running_overlay,
                        help="Tint route links with actual or inferred running evidence.")
    parser.add_argument("--no-running-overlay", dest="running_overlay", action="store_false")
    parser.add_argument("--coverage-heatmap", action="store_true", default=default_coverage_heatmap,
                        help="Draw a transparent visit-density heatmap under route overlays.")
    parser.add_argument("--no-coverage-heatmap", dest="coverage_heatmap", action="store_false")
    parser.add_argument("--coverage-heat-radius-tiles", type=float, default=default_coverage_heat_radius_tiles)
    parser.add_argument("--coverage-heat-alpha", type=float, default=default_coverage_heat_alpha)
    parser.add_argument("--coverage-heat-high-percentile", type=float, default=default_coverage_heat_high_percentile,
                        help="Visit-count percentile that should render as high coverage.")
    parser.add_argument("--coverage-heat-gamma", type=float, default=default_coverage_heat_gamma,
                        help="Gamma curve for coverage heat intensity; higher keeps low coverage cooler.")
    parser.add_argument("--coverage-fog", action="store_true", default=default_coverage_fog,
                        help="Dim unvisited map context while softly revealing observed movement corridors.")
    parser.add_argument("--no-coverage-fog", dest="coverage_fog", action="store_false")
    parser.add_argument("--coverage-fog-radius-tiles", type=float, default=default_coverage_fog_radius_tiles)
    parser.add_argument("--coverage-fog-alpha", type=float, default=default_coverage_fog_alpha)
    parser.add_argument("--coverage-fog-core-fraction", type=float, default=default_coverage_fog_core_fraction,
                        help="Fraction of the fog radius that stays fully clear around observed tiles.")
    parser.add_argument("--coverage-fog-poi-extra-tiles", type=float, default=default_coverage_fog_poi_extra_tiles,
                        help="Extra explored-radius tiles for POI icons beyond the visible fog reveal.")
    parser.add_argument("--coverage-cache-dir", default=str(DEFAULT_COVERAGE_CACHE_DIR),
                        help="Ignored local directory for exact topology and render-layer caches.")
    parser.add_argument("--no-coverage-cache", dest="coverage_cache", action="store_false",
                        help="Disable exact render-layer cache reads/writes.")
    parser.add_argument("--no-topology-cache", dest="topology_cache", action="store_false",
                        help="Disable append-validated movement topology cache reads/writes.")
    parser.set_defaults(coverage_cache=True)
    parser.set_defaults(topology_cache=True)
    parser.add_argument("--min-world-coordinate", type=int, default=1024)
    parser.add_argument("--max-edge-distance", type=int, default=8,
                        help="Drop movement edges longer than this many tiles; 0 disables the filter.")
    parser.add_argument("--title-pointsize", type=int, default=72)
    parser.add_argument("--section-pointsize", type=int, default=38)
    parser.add_argument("--legend-pointsize", type=int, default=28)
    parser.add_argument("--stats-pointsize", type=int, default=24)
    parser.add_argument("--meta-pointsize", type=int, default=default_meta_pointsize)
    parser.add_argument("--output", default=str(default_output or OUT / "movement-topology-v2.png"))
    parser.add_argument("--summary", default=str(default_summary or OUT / "movement-topology-v2.json"))
    args = parser.parse_args()
    if args.include_underground:
        args.surface_only = False
    args.background_mute = clamp(args.background_mute, 0.0, 0.85)
    args.grid_alpha = clamp(args.grid_alpha, 0.0, 1.0)
    args.major_grid_alpha = clamp(args.major_grid_alpha, 0.0, 1.0)
    args.node_alpha = clamp(args.node_alpha, 0.0, 1.0)
    args.coverage_heat_radius_tiles = clamp(args.coverage_heat_radius_tiles, 0.5, 20.0)
    args.coverage_heat_alpha = clamp(args.coverage_heat_alpha, 0.0, 0.5)
    args.coverage_heat_high_percentile = clamp(args.coverage_heat_high_percentile, 0.50, 1.0)
    args.coverage_heat_gamma = clamp(args.coverage_heat_gamma, 0.2, 4.0)
    args.coverage_fog_radius_tiles = clamp(args.coverage_fog_radius_tiles, 0.5, 28.0)
    args.coverage_fog_alpha = clamp(args.coverage_fog_alpha, 0.0, 0.75)
    args.coverage_fog_core_fraction = clamp(args.coverage_fog_core_fraction, 0.0, 0.95)
    args.coverage_fog_poi_extra_tiles = clamp(args.coverage_fog_poi_extra_tiles, 0.0, 80.0)
    args.title_paragraph_lines = max(1, min(8, int(args.title_paragraph_lines)))
    args.title_paragraph_right_margin = max(0, int(args.title_paragraph_right_margin))
    args.title_paragraph_char_factor = clamp(args.title_paragraph_char_factor, 0.25, 0.80)
    args.bounds_quantum_tiles = max(0, int(args.bounds_quantum_tiles))

    topology = load_topology_with_cache(args.trace_file, args.surface_only, args)
    topology = filter_implausible_topology(topology, args.min_world_coordinate)
    topology = filter_nonlocal_edges(topology, args.max_edge_distance)
    render_info = render(topology, args)
    summary = write_summary(Path(args.summary), topology, render_info, Path(args.output), args)
    print(json.dumps({"success": True, "output": args.output, "summary": args.summary, **summary}, sort_keys=True))


if __name__ == "__main__":
    main()
