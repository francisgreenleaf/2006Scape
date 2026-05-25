#!/usr/bin/env python3
"""Render navigation topology PNGs from agent-navigation data.

Default output is an ignored, overwritten surface map. The renderer uses only
the Python standard library so agents can run it in the gameplay harness.
"""

import argparse
import json
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / ".local" / "map-summaries"

PALETTE = {
    "paper": (245, 239, 219),
    "paper2": (232, 223, 196),
    "ink": (38, 47, 55),
    "muted": (99, 103, 96),
    "grid": (211, 199, 168),
    "grid_major": (190, 176, 142),
    "verified": (36, 116, 88),
    "partial": (207, 126, 33),
    "blocked": (188, 56, 54),
    "derived": (55, 91, 153),
    "place": (24, 42, 58),
    "obs": (114, 77, 180),
    "hazard": (202, 45, 38),
    "white": (255, 255, 255),
    "water": (173, 204, 214),
    "land": (226, 218, 189),
}

FONT = {
    " ": ["000", "000", "000", "000", "000", "000", "000"],
    "-": ["000", "000", "000", "111", "000", "000", "000"],
    ":": ["0", "1", "0", "0", "0", "1", "0"],
    ".": ["0", "0", "0", "0", "0", "1", "0"],
    ",": ["0", "0", "0", "0", "0", "1", "1"],
    "/": ["001", "001", "010", "010", "100", "100", "000"],
    "0": ["111", "101", "101", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "010", "010", "111"],
    "2": ["111", "001", "001", "111", "100", "100", "111"],
    "3": ["111", "001", "001", "111", "001", "001", "111"],
    "4": ["101", "101", "101", "111", "001", "001", "001"],
    "5": ["111", "100", "100", "111", "001", "001", "111"],
    "6": ["111", "100", "100", "111", "101", "101", "111"],
    "7": ["111", "001", "001", "010", "010", "100", "100"],
    "8": ["111", "101", "101", "111", "101", "101", "111"],
    "9": ["111", "101", "101", "111", "001", "001", "111"],
}

LETTERS = {
    "A": ["010", "101", "101", "111", "101", "101", "101"],
    "B": ["110", "101", "101", "110", "101", "101", "110"],
    "C": ["011", "100", "100", "100", "100", "100", "011"],
    "D": ["110", "101", "101", "101", "101", "101", "110"],
    "E": ["111", "100", "100", "110", "100", "100", "111"],
    "F": ["111", "100", "100", "110", "100", "100", "100"],
    "G": ["011", "100", "100", "101", "101", "101", "011"],
    "H": ["101", "101", "101", "111", "101", "101", "101"],
    "I": ["111", "010", "010", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "001", "101", "101", "010"],
    "K": ["101", "101", "110", "100", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101", "101", "101"],
    "N": ["101", "111", "111", "111", "101", "101", "101"],
    "O": ["010", "101", "101", "101", "101", "101", "010"],
    "P": ["110", "101", "101", "110", "100", "100", "100"],
    "Q": ["010", "101", "101", "101", "101", "011", "001"],
    "R": ["110", "101", "101", "110", "110", "101", "101"],
    "S": ["011", "100", "100", "010", "001", "001", "110"],
    "T": ["111", "010", "010", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "101", "101", "010"],
    "W": ["101", "101", "101", "101", "111", "111", "101"],
    "X": ["101", "101", "101", "010", "101", "101", "101"],
    "Y": ["101", "101", "101", "010", "010", "010", "010"],
    "Z": ["111", "001", "001", "010", "100", "100", "111"],
}
FONT.update(LETTERS)


def load_json(name):
    with (DATA / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_observations(limit):
    path = DATA / "observations.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows[-limit:] if limit else rows


def tile_of_place(place):
    tile = place.get("tile") or {}
    if "x" in tile and "y" in tile:
        return int(tile["x"]), int(tile["y"]), int(tile.get("height", 0))
    return None


def tile_of_step(step):
    tile = step.get("to") or step.get("near") or step.get("postTile") or step.get("objectTile")
    if isinstance(tile, dict) and "x" in tile and "y" in tile:
        return int(tile["x"]), int(tile["y"]), int(tile.get("height", 0))
    return None


def status_color(status):
    if status == "verified":
        return PALETTE["verified"]
    if status in ("learned-partial", "partial"):
        return PALETTE["partial"]
    if status in ("blocked", "failed"):
        return PALETTE["blocked"]
    return PALETTE["derived"]


class Canvas:
    def __init__(self, width, height, bg):
        self.width = width
        self.height = height
        self.pixels = bytearray(bg * (width * height))

    def get(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 3
            return tuple(self.pixels[i:i + 3])
        return (0, 0, 0)

    def set(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 3
            self.pixels[i:i + 3] = bytes(color)

    def blend(self, x, y, color, alpha):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        i = (y * self.width + x) * 3
        if alpha >= 1.0:
            self.pixels[i] = color[0]
            self.pixels[i + 1] = color[1]
            self.pixels[i + 2] = color[2]
            return
        inv = 1.0 - alpha
        self.pixels[i] = int(self.pixels[i] * inv + color[0] * alpha)
        self.pixels[i + 1] = int(self.pixels[i + 1] * inv + color[1] * alpha)
        self.pixels[i + 2] = int(self.pixels[i + 2] * inv + color[2] * alpha)

    def rect(self, x0, y0, x1, y1, color):
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        x_start = max(0, int(x0))
        x_end = min(self.width, int(x1) + 1)
        y_start = max(0, int(y0))
        y_end = min(self.height, int(y1) + 1)
        if x_start >= x_end or y_start >= y_end:
            return
        row = bytes(color) * (x_end - x_start)
        stride = self.width * 3
        offset = x_start * 3
        for y in range(y_start, y_end):
            start = y * stride + offset
            self.pixels[start:start + len(row)] = row

    def blend_rect(self, x0, y0, x1, y1, color, alpha):
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        x_start = max(0, int(x0))
        x_end = min(self.width, int(x1) + 1)
        y_start = max(0, int(y0))
        y_end = min(self.height, int(y1) + 1)
        if x_start >= x_end or y_start >= y_end or alpha <= 0:
            return
        if alpha >= 1.0:
            self.rect(x_start, y_start, x_end - 1, y_end - 1, color)
            return
        pixels = self.pixels
        stride = self.width * 3
        cr, cg, cb = color
        inv = 1.0 - alpha
        for y in range(y_start, y_end):
            index = y * stride + x_start * 3
            for _x in range(x_start, x_end):
                pixels[index] = int(pixels[index] * inv + cr * alpha)
                pixels[index + 1] = int(pixels[index + 1] * inv + cg * alpha)
                pixels[index + 2] = int(pixels[index + 2] * inv + cb * alpha)
                index += 3

    def circle(self, cx, cy, r, color, alpha=1.0, outline=False):
        rr = r * r
        inner = max(0, r - 2) ** 2 if outline else 0
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                d = (x - cx) * (x - cx) + (y - cy) * (y - cy)
                if d <= rr and d >= inner:
                    if alpha >= 1.0:
                        self.set(x, y, color)
                    else:
                        self.blend(x, y, color, alpha)

    def line(self, x0, y0, x1, y1, color, width=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            radius = max(0, width // 2)
            for yy in range(y0 - radius, y0 + radius + 1):
                for xx in range(x0 - radius, x0 + radius + 1):
                    self.set(xx, yy, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def text(self, x, y, text, color, scale=1):
        cursor = x
        for ch in text.upper():
            glyph = FONT.get(ch, FONT.get(" "))
            for gy, row in enumerate(glyph):
                for gx, value in enumerate(row):
                    if value == "1":
                        self.rect(cursor + gx * scale, y + gy * scale,
                                  cursor + (gx + 1) * scale - 1, y + (gy + 1) * scale - 1, color)
            cursor += (len(glyph[0]) + 1) * scale

    def save_png(self, path):
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            start = y * stride
            raw.extend(self.pixels[start:start + stride])

        def chunk(kind, data):
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)

        png = b"".join([
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
            chunk(b"IEND", b""),
        ])
        path.write_bytes(png)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="all")
    parser.add_argument("--pixels-per-tile", type=float, default=6.0)
    parser.add_argument("--surface-only", action="store_true", default=True)
    parser.add_argument("--include-underground", action="store_true")
    parser.add_argument("--observations", type=int, default=200)
    parser.add_argument("--output", default=str(OUT / "surface-routes.png"))
    args = parser.parse_args()
    if args.include_underground:
        args.surface_only = False

    all_regions = args.region in ("all", "*", "")
    places = [p for p in load_json("places.json").get("places", []) if all_regions or p.get("region") == args.region]
    routes = [r for r in load_json("routes.json").get("routes", []) if all_regions or args.region in r.get("tags", []) or r.get("from", "").startswith(args.region) or r.get("to", "").startswith(args.region)]
    hazards = [h for h in load_json("hazards.json").get("hazards", []) if all_regions or h.get("region") == args.region]
    observations = load_observations(args.observations)

    def include_tile(tile):
        if not tile:
            return False
        if args.surface_only and (tile[2] != 0 or tile[1] >= 6400):
            return False
        return True

    place_tiles = {p["id"]: tile_of_place(p) for p in places}
    points = [t for t in place_tiles.values() if include_tile(t)]
    for route in routes:
        if include_tile(place_tiles.get(route.get("from"))):
            points.append(place_tiles[route["from"]])
        for step in route.get("steps", []):
            tile = tile_of_step(step)
            if include_tile(tile):
                points.append(tile)
    for hazard in hazards:
        center = hazard.get("center") or {}
        if "x" in center and "y" in center:
            tile = (int(center["x"]), int(center["y"]), int(center.get("height", 0)))
            if include_tile(tile):
                points.append(tile)
    for obs in observations:
        if obs.get("x") is not None and obs.get("y") is not None:
            tile = (int(obs["x"]), int(obs["y"]), int(obs.get("height", 0)))
            if include_tile(tile):
                points.append(tile)
    if not points:
        raise SystemExit("no points to render")

    min_x = min(p[0] for p in points) - 12
    max_x = max(p[0] for p in points) + 12
    min_y = min(p[1] for p in points) - 12
    max_y = max(p[1] for p in points) + 12
    map_w = int(math.ceil((max_x - min_x) * args.pixels_per_tile)) + 1
    map_h = int(math.ceil((max_y - min_y) * args.pixels_per_tile)) + 1
    margin = 40
    title_h = 56
    legend_h = 78
    width = max(map_w + margin * 2, 760)
    height = map_h + title_h + legend_h + margin
    scale = args.pixels_per_tile
    map_x0 = (width - map_w) // 2
    map_y0 = title_h

    def project(tile):
        x, y, _h = tile
        px = int(map_x0 + (x - min_x) * scale)
        py = int(map_y0 + map_h - 1 - (y - min_y) * scale)
        return px, py

    canvas = Canvas(width, height, PALETTE["paper"])
    canvas.blend_rect(0, 0, width - 1, title_h - 1, PALETTE["paper2"], 0.65)
    canvas.text(18, 16, "MRFLAME SURFACE ROUTE MAP", PALETTE["ink"], 2)
    subtitle = "%G PX = 1 STEP TILE  SURFACE ONLY  %d ROUTES  %d PLACES" % (args.pixels_per_tile, len(routes), len(places))
    canvas.text(20, 42, subtitle, PALETTE["muted"], 1)

    canvas.rect(map_x0 - 1, map_y0 - 1, map_x0 + map_w, map_y0 + map_h, PALETTE["grid_major"])
    canvas.rect(map_x0, map_y0, map_x0 + map_w - 1, map_y0 + map_h - 1, PALETTE["land"])
    for gx in range(int(min_x // 10 * 10), max_x + 1, 10):
        x = int(map_x0 + (gx - min_x) * scale)
        color = PALETTE["grid_major"] if gx % 50 == 0 else PALETTE["grid"]
        canvas.line(x, map_y0, x, map_y0 + map_h - 1, color)
    for gy in range(int(min_y // 10 * 10), max_y + 1, 10):
        y = int(map_y0 + map_h - 1 - (gy - min_y) * scale)
        color = PALETTE["grid_major"] if gy % 50 == 0 else PALETTE["grid"]
        canvas.line(map_x0, y, map_x0 + map_w - 1, y, color)

    for hazard in hazards:
        center = hazard.get("center") or {}
        if "x" not in center or "y" not in center:
            continue
        tile = (int(center["x"]), int(center["y"]), int(center.get("height", 0)))
        if not include_tile(tile):
            continue
        cx, cy = project(tile)
        radius = max(6, int(int(hazard.get("radius", 4)) * scale))
        canvas.circle(cx, cy, radius, PALETTE["hazard"], alpha=0.28)
        canvas.circle(cx, cy, radius, PALETTE["hazard"], alpha=0.95, outline=True)

    for route in routes:
        color = status_color(route.get("status"))
        route_points = []
        if include_tile(place_tiles.get(route.get("from"))):
            route_points.append(place_tiles[route["from"]])
        for step in route.get("steps", []):
            tile = tile_of_step(step)
            if include_tile(tile):
                route_points.append(tile)
        for a, b in zip(route_points, route_points[1:]):
            ax, ay = project(a)
            bx, by = project(b)
            route_width = max(2, int(round(scale / 2))) if route.get("status") == "verified" else max(1, int(round(scale / 3)))
            canvas.line(ax, ay, bx, by, color, width=route_width)

    for obs in observations:
        if obs.get("x") is None or obs.get("y") is None:
            continue
        tile = (int(obs["x"]), int(obs["y"]), int(obs.get("height", 0)))
        if include_tile(tile):
            x, y = project(tile)
            canvas.circle(x, y, max(2, int(round(scale / 2))), PALETTE["obs"])

    for place in places:
        tile = place_tiles.get(place.get("id"))
        if include_tile(tile):
            x, y = project(tile)
            marker = max(3, int(round(scale * 0.9)))
            canvas.rect(x - marker, y - marker, x + marker, y + marker, PALETTE["white"])
            canvas.rect(x - marker + 1, y - marker + 1, x + marker - 1, y + marker - 1, PALETTE["place"])

    legend_y = map_y0 + map_h + 20
    canvas.text(18, legend_y, "LEGEND", PALETTE["ink"], 2)
    legend = [
        ("VERIFIED", PALETTE["verified"]),
        ("DERIVED", PALETTE["derived"]),
        ("PARTIAL", PALETTE["partial"]),
        ("BLOCKED", PALETTE["blocked"]),
        ("HAZARD", PALETTE["hazard"]),
        ("PLACE", PALETTE["place"]),
        ("OBS", PALETTE["obs"]),
    ]
    lx = 122
    ly = legend_y + 3
    for label, color in legend:
        if lx + 88 > width - 20:
            lx = 122
            ly += 18
        canvas.rect(lx, ly, lx + 15, ly + 9, color)
        canvas.text(lx + 22, ly, label, PALETTE["ink"], 1)
        lx += 92

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save_png(out)
    print(json.dumps({
        "success": True,
        "output": str(out),
        "region": args.region,
        "surfaceOnly": args.surface_only,
        "pixelsPerTile": args.pixels_per_tile,
        "pixelWidth": width,
        "pixelHeight": height,
        "bounds": {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
