#!/usr/bin/env python3
"""Cache-backed surface world-map rendering helpers.

This reads the local 2006Scape cache directly and produces minimap-style tile
colors without sampling the visible client UI. It follows the same broad layers
as the client minimap: floor underlays/overlays, mapscene-backed objects, simple
wall/object line marks, and mapfunction hints.
"""

import argparse
import bz2
import json
import math
import struct
import zlib
from pathlib import Path

from render_navigation_png import Canvas


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT.parent / "2006Scape Server" / "data" / "cache"
OUT = ROOT / "topology"

REGION_SIZE = 64
PLANES = 4
SHAPE_MASKS = [
    [0 for _i in range(16)],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 1, 1, 1],
    [1, 1, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1],
    [0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0],
    [1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1],
    [1, 1, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1],
]
ROTATION_MASKS = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    [12, 8, 4, 0, 13, 9, 5, 1, 14, 10, 6, 2, 15, 11, 7, 3],
    [15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    [3, 7, 11, 15, 2, 6, 10, 14, 1, 5, 9, 13, 0, 4, 8, 12],
]

PALETTE = {
    "paper": (232, 224, 199),
    "grid": (184, 172, 139),
    "wall": (72, 66, 57),
    "wall_light": (214, 210, 195),
    "footprint": (104, 92, 73),
    "ground_decoration": (99, 116, 77),
    "map_function": (145, 96, 28),
}


class CacheReader:
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.data_path = self.cache_dir / "main_file_cache.dat"

    def get_file(self, index, file_id):
        idx_path = self.cache_dir / ("main_file_cache.idx%d" % index)
        with idx_path.open("rb") as handle:
            handle.seek(file_id * 6)
            entry = handle.read(6)
        if len(entry) != 6:
            return None
        size = int.from_bytes(entry[0:3], "big")
        block = int.from_bytes(entry[3:6], "big")
        if size <= 0 or block <= 0:
            return None
        data = bytearray()
        read = 0
        chunk = 0
        with self.data_path.open("rb") as handle:
            while read < size:
                handle.seek(block * 520)
                header = handle.read(8)
                if len(header) != 8:
                    raise IOError("truncated cache header for index %d file %d" % (index, file_id))
                current_chunk = int.from_bytes(header[2:4], "big")
                next_block = int.from_bytes(header[4:7], "big")
                if current_chunk != chunk:
                    raise IOError("cache chunk mismatch for index %d file %d" % (index, file_id))
                length = min(512, size - read)
                payload = handle.read(length)
                if len(payload) != length:
                    raise IOError("truncated cache payload for index %d file %d" % (index, file_id))
                data.extend(payload)
                read += length
                block = next_block
                chunk += 1
        return bytes(data)

    def get_archive_entry(self, index, file_id, name):
        archive = decode_archive(self.get_file(index, file_id))
        key = archive_hash(name)
        if key not in archive:
            raise KeyError("archive entry not found: %s" % name)
        return archive[key]


def degzip(data):
    return zlib.decompress(data, 16 + zlib.MAX_WBITS)


def archive_hash(name):
    value = 0
    for char in name.upper():
        value = (value * 61 + ord(char) - 32) & 0xffffffff
    return value


def read_medium(data, offset):
    return int.from_bytes(data[offset:offset + 3], "big")


def decode_archive(data):
    extracted_size = read_medium(data, 0)
    compressed_size = read_medium(data, 3)
    payload = data[6:6 + compressed_size]
    extracted = False
    if compressed_size != extracted_size:
        payload = bz2.decompress(b"BZh1" + payload)
        extracted = True
    offset = 0
    count = int.from_bytes(payload[offset:offset + 2], "big")
    offset += 2
    entries = []
    for _index in range(count):
        identifier = int.from_bytes(payload[offset:offset + 4], "big")
        offset += 4
        entry_extracted_size = read_medium(payload, offset)
        offset += 3
        entry_size = read_medium(payload, offset)
        offset += 3
        entries.append((identifier, entry_extracted_size, entry_size))
    decoded = {}
    for identifier, entry_extracted_size, entry_size in entries:
        entry = payload[offset:offset + entry_size]
        offset += entry_size
        if not extracted:
            entry = bz2.decompress(b"BZh1" + entry)
        decoded[identifier] = entry[:entry_extracted_size]
    return decoded


class Buffer:
    def __init__(self, data):
        self.data = data
        self.offset = 0

    def u8(self):
        value = self.data[self.offset]
        self.offset += 1
        return value

    def s8(self):
        value = self.u8()
        return value - 256 if value > 127 else value

    def u16(self):
        value = int.from_bytes(self.data[self.offset:self.offset + 2], "big")
        self.offset += 2
        return value

    def s16(self):
        value = self.u16()
        return value - 65536 if value > 32767 else value

    def u24(self):
        value = int.from_bytes(self.data[self.offset:self.offset + 3], "big")
        self.offset += 3
        return value

    def smart(self):
        value = self.data[self.offset]
        if value < 128:
            self.offset += 1
            return value
        return self.u16() - 32768

    def skip_string(self):
        while self.offset < len(self.data):
            if self.u8() == 10:
                return

    def string(self):
        start = self.offset
        self.skip_string()
        return self.data[start:self.offset - 1].decode("latin1", errors="replace")

    def skip(self, length):
        self.offset += length


def load_map_index(cache=None):
    cache = cache or CacheReader()
    data = cache.get_archive_entry(0, 5, "map_index")
    records = []
    for offset in range(0, len(data), 7):
        if offset + 7 > len(data):
            break
        region_id = int.from_bytes(data[offset:offset + 2], "big")
        terrain = int.from_bytes(data[offset + 2:offset + 4], "big")
        objects = int.from_bytes(data[offset + 4:offset + 6], "big")
        members = data[offset + 6] == 1
        records.append({
            "regionId": region_id,
            "regionX": (region_id >> 8) * REGION_SIZE,
            "regionY": (region_id & 0xff) * REGION_SIZE,
            "terrainFile": terrain,
            "objectFile": objects,
            "members": members,
        })
    return records


def map_index_bounds(records):
    return {
        "minX": min(record["regionX"] for record in records),
        "maxX": max(record["regionX"] + REGION_SIZE - 1 for record in records),
        "minY": min(record["regionY"] for record in records),
        "maxY": max(record["regionY"] + REGION_SIZE - 1 for record in records),
    }


def load_flo_defs(cache=None):
    cache = cache or CacheReader()
    data = cache.get_archive_entry(0, 2, "flo.dat")
    buf = Buffer(data)
    count = buf.u16()
    floors = []
    for _index in range(count):
        rgb = None
        texture = -1
        while True:
            opcode = buf.u8()
            if opcode == 0:
                break
            if opcode == 1:
                rgb = buf.u24()
            elif opcode == 2:
                texture = buf.u8()
            elif opcode == 3:
                pass
            elif opcode == 5:
                pass
            elif opcode == 6:
                buf.skip_string()
            elif opcode == 7:
                buf.u24()
            else:
                raise ValueError("unknown flo opcode %d" % opcode)
        floors.append({
            "rgb": rgb_to_tuple(rgb) if rgb is not None else None,
            "texture": texture,
        })
    return floors


def load_flo_colors(cache=None):
    return [floor["rgb"] for floor in load_flo_defs(cache)]


def load_loc_defs(cache=None):
    cache = cache or CacheReader()
    dat = cache.get_archive_entry(0, 2, "loc.dat")
    idx = cache.get_archive_entry(0, 2, "loc.idx")
    index = Buffer(idx)
    count = index.u16()
    offsets = []
    offset = 2
    for _object_id in range(count):
        offsets.append(offset)
        offset += index.u16()
    objects = []
    for object_id, offset in enumerate(offsets):
        buf = Buffer(dat)
        buf.offset = offset
        definition = {
            "id": object_id,
            "name": None,
            "width": 1,
            "length": 1,
            "mapFunction": -1,
            "mapScene": -1,
            "hasActions": False,
            "blocks": True,
        }
        action_flag = -1
        models_present = False
        actions_present = False
        while True:
            opcode = buf.u8()
            if opcode == 0:
                break
            if opcode == 1:
                count_models = buf.u8()
                buf.skip(count_models * 3)
                models_present = models_present or count_models > 0
            elif opcode == 2:
                definition["name"] = buf.string()
            elif opcode == 3:
                buf.skip_string()
            elif opcode == 5:
                count_models = buf.u8()
                buf.skip(count_models * 2)
                models_present = models_present or count_models > 0
            elif opcode == 14:
                definition["width"] = buf.u8()
            elif opcode == 15:
                definition["length"] = buf.u8()
            elif opcode == 17:
                definition["blocks"] = False
            elif opcode == 18:
                pass
            elif opcode == 19:
                action_flag = buf.u8()
            elif opcode in (21, 22, 23):
                pass
            elif opcode == 24:
                animation = buf.u16()
                if animation == 65535:
                    animation = -1
            elif opcode == 28:
                buf.u8()
            elif opcode in (29, 39):
                buf.s8()
            elif 30 <= opcode < 39:
                action = buf.string()
                if action.lower() != "hidden":
                    actions_present = True
            elif opcode == 40:
                recolors = buf.u8()
                buf.skip(recolors * 4)
            elif opcode == 60:
                definition["mapFunction"] = buf.u16()
            elif opcode in (62, 64, 73, 74):
                pass
            elif opcode in (65, 66, 67):
                buf.u16()
            elif opcode == 68:
                definition["mapScene"] = buf.u16()
            elif opcode == 69:
                buf.u8()
            elif opcode in (70, 71, 72):
                buf.s16()
            elif opcode == 75:
                buf.u8()
            elif opcode == 77:
                varbit = buf.u16()
                varp = buf.u16()
                if varbit == 65535:
                    varbit = -1
                if varp == 65535:
                    varp = -1
                children = buf.u8()
                for _child in range(children + 1):
                    child_id = buf.u16()
                    if child_id == 65535:
                        child_id = -1
            else:
                raise ValueError("unknown loc opcode %d for object %d" % (opcode, object_id))
        if action_flag == -1:
            definition["hasActions"] = (models_present and True) or actions_present
        else:
            definition["hasActions"] = action_flag == 1 or actions_present
        objects.append(definition)
    return objects


def rgb_to_tuple(rgb):
    return (rgb >> 16 & 0xff, rgb >> 8 & 0xff, rgb & 0xff)


def adjust_brightness(rgb, power):
    red = int(((rgb >> 16) / 256.0) ** power * 256.0)
    green = int(((rgb >> 8 & 0xff) / 256.0) ** power * 256.0)
    blue = int(((rgb & 0xff) / 256.0) ** power * 256.0)
    return (red << 16) + (green << 8) + blue


def texture_average_color(data, index_data, brightness=0.8):
    stream = Buffer(data)
    index = Buffer(index_data)
    index.offset = stream.u16()
    index.u16()
    index.u16()
    palette_count = index.u8()
    if palette_count <= 0:
        return None
    palette = [0 for _entry in range(palette_count)]
    for entry in range(1, palette_count):
        color = adjust_brightness(index.u24(), brightness)
        if (color & 0xf8f8ff) == 0:
            color = 1
        palette[entry] = color
    red = sum(color >> 16 & 0xff for color in palette) // len(palette)
    green = sum(color >> 8 & 0xff for color in palette) // len(palette)
    blue = sum(color & 0xff for color in palette) // len(palette)
    average = adjust_brightness((red << 16) + (green << 8) + blue, 1.4)
    if average == 0:
        average = 1
    return rgb_to_tuple(average)


def load_texture_average_colors(cache=None):
    cache = cache or CacheReader()
    archive_data = cache.get_file(0, 6)
    if archive_data is None:
        return {}
    archive = decode_archive(archive_data)
    index_data = archive.get(archive_hash("index.dat"))
    if index_data is None:
        return {}
    colors = {}
    for texture_id in range(50):
        data = archive.get(archive_hash("%d.dat" % texture_id))
        if data is None:
            continue
        try:
            color = texture_average_color(data, index_data)
        except Exception:
            continue
        if color is not None:
            colors[texture_id] = color
    return colors


def load_background_sprites(cache=None, name="mapscene", limit=100):
    cache = cache or CacheReader()
    archive_data = cache.get_file(0, 4)
    if archive_data is None:
        return {}
    archive = decode_archive(archive_data)
    data = archive.get(archive_hash("%s.dat" % name))
    index_data = archive.get(archive_hash("index.dat"))
    if data is None or index_data is None:
        return {}
    sprites = {}
    for sprite_id in range(limit):
        try:
            sprite = decode_background_sprite(data, index_data, sprite_id)
        except Exception:
            continue
        if sprite is not None:
            sprites[sprite_id] = sprite
    return sprites


def decode_background_sprite(data, index_data, sprite_id):
    stream = Buffer(data)
    index = Buffer(index_data)
    index.offset = stream.u16()
    if index.offset + 5 > len(index.data):
        return None
    max_width = index.u16()
    max_height = index.u16()
    palette_count = index.u8()
    if palette_count <= 0:
        return None
    if index.offset + (palette_count - 1) * 3 > len(index.data):
        return None
    palette = [(0, 0, 0)]
    for _entry in range(palette_count - 1):
        color = index.u24()
        palette.append(rgb_to_tuple(color))
    for _skipped in range(sprite_id):
        if index.offset + 5 > len(index.data):
            return None
        index.skip(2)
        width = index.u16()
        height = index.u16()
        if width <= 0 or height <= 0 or stream.offset + width * height > len(stream.data):
            return None
        stream.skip(width * height)
        index.skip(1)
    if index.offset + 7 > len(index.data):
        return None
    x_offset = index.u8()
    y_offset = index.u8()
    width = index.u16()
    height = index.u16()
    layout = index.u8()
    if width <= 0 or height <= 0 or width * height > 4096:
        return None
    if stream.offset + width * height > len(stream.data):
        return None
    pixels = [0 for _pixel in range(width * height)]
    if layout == 0:
        for pixel in range(width * height):
            pixels[pixel] = stream.u8()
    elif layout == 1:
        for x in range(width):
            for y in range(height):
                pixels[x + y * width] = stream.u8()
    else:
        return None
    return {
        "id": sprite_id,
        "palette": palette,
        "pixels": pixels,
        "width": width,
        "height": height,
        "xOffset": x_offset,
        "yOffset": y_offset,
        "maxWidth": max_width,
        "maxHeight": max_height,
    }


def decode_terrain(data):
    buf = Buffer(data)
    underlays = [[[0 for _y in range(REGION_SIZE)] for _x in range(REGION_SIZE)] for _p in range(PLANES)]
    overlays = [[[0 for _y in range(REGION_SIZE)] for _x in range(REGION_SIZE)] for _p in range(PLANES)]
    overlay_shapes = [[[0 for _y in range(REGION_SIZE)] for _x in range(REGION_SIZE)] for _p in range(PLANES)]
    overlay_rotations = [[[0 for _y in range(REGION_SIZE)] for _x in range(REGION_SIZE)] for _p in range(PLANES)]
    settings = [[[0 for _y in range(REGION_SIZE)] for _x in range(REGION_SIZE)] for _p in range(PLANES)]
    for plane in range(PLANES):
        for x in range(REGION_SIZE):
            for y in range(REGION_SIZE):
                while True:
                    tile_type = buf.u8()
                    if tile_type == 0:
                        break
                    if tile_type == 1:
                        buf.u8()
                        break
                    if tile_type <= 49:
                        overlays[plane][x][y] = buf.s8() & 0xff
                        overlay_shapes[plane][x][y] = (tile_type - 2) // 4
                        overlay_rotations[plane][x][y] = (tile_type - 2) & 3
                    elif tile_type <= 81:
                        settings[plane][x][y] = tile_type - 49
                    else:
                        underlays[plane][x][y] = tile_type - 81
    return {
        "underlays": underlays,
        "overlays": overlays,
        "overlayShapes": overlay_shapes,
        "overlayRotations": overlay_rotations,
        "settings": settings,
    }


def decode_objects(data):
    buf = Buffer(data)
    objects = []
    object_id = -1
    id_offset = buf.smart()
    while id_offset != 0:
        object_id += id_offset
        packed = 0
        position_offset = buf.smart()
        while position_offset != 0:
            packed += position_offset - 1
            attributes = buf.u8()
            objects.append({
                "id": object_id,
                "x": packed >> 6 & 0x3f,
                "y": packed & 0x3f,
                "height": packed >> 12 & 0x3,
                "type": attributes >> 2,
                "orientation": attributes & 0x3,
            })
            position_offset = buf.smart()
        id_offset = buf.smart()
    return objects


def floor_color(floor, texture_colors):
    texture = floor.get("texture", -1)
    if texture >= 0:
        color = texture_colors.get(texture)
        if color and color != (255, 0, 255):
            return color
    color = floor.get("rgb")
    if color and color != (255, 0, 255):
        return color
    return None


def color_for_tile(flo_defs, texture_colors, underlay, overlay):
    if overlay > 0 and overlay - 1 < len(flo_defs):
        color = floor_color(flo_defs[overlay - 1], texture_colors)
        if color:
            return color
    if underlay > 0 and underlay - 1 < len(flo_defs):
        color = floor_color(flo_defs[underlay - 1], texture_colors)
        if color:
            return color
    return None


def tile_colors(flo_defs, texture_colors, underlay, overlay):
    underlay_color = None
    overlay_color = None
    if underlay > 0 and underlay - 1 < len(flo_defs):
        underlay_color = floor_color(flo_defs[underlay - 1], texture_colors)
    if overlay > 0 and overlay - 1 < len(flo_defs):
        overlay_color = floor_color(flo_defs[overlay - 1], texture_colors)
    return underlay_color, overlay_color


def region_intersects(record, bounds):
    return not (
        record["regionX"] + REGION_SIZE - 1 < bounds["minX"]
        or record["regionX"] > bounds["maxX"]
        or record["regionY"] + REGION_SIZE - 1 < bounds["minY"]
        or record["regionY"] > bounds["maxY"]
    )


def load_cache_world_map(bounds, plane=0, cache_dir=CACHE_DIR):
    cache = CacheReader(cache_dir)
    records = load_map_index(cache)
    if bounds is None:
        bounds = map_index_bounds(records)
    flo_defs = load_flo_defs(cache)
    loc_defs = load_loc_defs(cache)
    map_scenes = load_background_sprites(cache, "mapscene", 100)
    texture_colors = load_texture_average_colors(cache)
    tiles = []
    objects = []
    regions = 0
    stats = {
        "objectDefs": len(loc_defs),
        "mapSceneSprites": len(map_scenes),
        "mapSceneObjects": 0,
        "mapFunctionObjects": 0,
        "footprintObjects": 0,
    }
    for record in records:
        if not region_intersects(record, bounds):
            continue
        terrain_file = cache.get_file(4, record["terrainFile"])
        object_file = cache.get_file(4, record["objectFile"])
        if terrain_file is None:
            continue
        try:
            terrain = decode_terrain(degzip(terrain_file))
        except Exception:
            continue
        regions += 1
        min_lx = max(0, bounds["minX"] - record["regionX"])
        max_lx = min(REGION_SIZE - 1, bounds["maxX"] - record["regionX"])
        min_ly = max(0, bounds["minY"] - record["regionY"])
        max_ly = min(REGION_SIZE - 1, bounds["maxY"] - record["regionY"])
        for local_x in range(min_lx, max_lx + 1):
            for local_y in range(min_ly, max_ly + 1):
                underlay_color, overlay_color = tile_colors(
                    flo_defs,
                    texture_colors,
                    terrain["underlays"][plane][local_x][local_y],
                    terrain["overlays"][plane][local_x][local_y],
                )
                if underlay_color is not None or overlay_color is not None:
                    underlay_color = underlay_color or overlay_color
                    overlay_color = overlay_color or underlay_color
                    tiles.append((
                        record["regionX"] + local_x,
                        record["regionY"] + local_y,
                        plane,
                        underlay_color[0],
                        underlay_color[1],
                        underlay_color[2],
                        overlay_color[0],
                        overlay_color[1],
                        overlay_color[2],
                        terrain["overlayShapes"][plane][local_x][local_y],
                        terrain["overlayRotations"][plane][local_x][local_y],
                    ))
        if object_file is None:
            continue
        try:
            decoded_objects = decode_objects(degzip(object_file))
        except Exception:
            continue
        for obj in decoded_objects:
            if obj["height"] != plane:
                continue
            x = record["regionX"] + obj["x"]
            y = record["regionY"] + obj["y"]
            if bounds["minX"] <= x <= bounds["maxX"] and bounds["minY"] <= y <= bounds["maxY"]:
                loc = loc_defs[obj["id"]] if obj["id"] < len(loc_defs) else {}
                width = int(loc.get("width", 1))
                length = int(loc.get("length", 1))
                map_scene = int(loc.get("mapScene", -1))
                map_function = int(loc.get("mapFunction", -1))
                if map_scene >= 0:
                    stats["mapSceneObjects"] += 1
                if map_function >= 0:
                    stats["mapFunctionObjects"] += 1
                if width > 1 or length > 1:
                    stats["footprintObjects"] += 1
                objects.append({
                    "id": obj["id"],
                    "name": loc.get("name"),
                    "x": x,
                    "y": y,
                    "height": plane,
                    "type": obj["type"],
                    "orientation": obj["orientation"],
                    "width": width,
                    "length": length,
                    "mapScene": map_scene,
                    "mapFunction": map_function,
                })
    return {"tiles": tiles, "objects": objects, "regions": regions, "bounds": bounds,
            "textures": len(texture_colors), "mapScenes": map_scenes, "stats": stats}


def draw_tile(canvas, tile, project, scale):
    block = max(1, int(round(scale)))
    if isinstance(tile, dict):
        x = tile["x"]
        y = tile["y"]
        h = tile.get("height", 0)
        underlay = tuple(tile["underlay"])
        overlay = tuple(tile.get("overlay") or tile["underlay"])
        shape = int(tile.get("shape", 0))
        rotation = int(tile.get("rotation", 0))
    elif len(tile) >= 11:
        x, y, h, ur, ug, ub, or_, og, ob, shape, rotation = tile[:11]
        underlay = (ur, ug, ub)
        overlay = (or_, og, ob)
    else:
        x, y, h, r, g, b, _count = tile
        underlay = (r, g, b)
        overlay = underlay
        shape = 0
        rotation = 0
    px, py = project({"x": x, "y": y, "height": h})
    x0 = px
    y0 = py - block + 1
    x1 = px + block - 1
    y1 = py
    if shape <= 1 or shape >= len(SHAPE_MASKS) or underlay == overlay:
        canvas.rect(x0, y0, x1, y1, overlay)
        return
    canvas.rect(x0, y0, x1, y1, underlay)
    mask = SHAPE_MASKS[shape]
    rotation_mask = ROTATION_MASKS[rotation % 4]
    for sub_y in range(4):
        for sub_x in range(4):
            mask_index = rotation_mask[sub_y * 4 + sub_x]
            if not mask[mask_index]:
                continue
            sx0 = x0 + int(math.floor(sub_x * block / 4.0))
            sx1 = x0 + int(math.ceil((sub_x + 1) * block / 4.0)) - 1
            sy0 = y0 + int(math.floor(sub_y * block / 4.0))
            sy1 = y0 + int(math.ceil((sub_y + 1) * block / 4.0)) - 1
            canvas.rect(sx0, sy0, sx1, sy1, overlay)


def object_dimensions(obj, rotate_large=True):
    width = max(1, int(obj.get("width", 1)))
    length = max(1, int(obj.get("length", 1)))
    if rotate_large and int(obj.get("type", 0)) in (10, 11) and int(obj.get("orientation", 0)) in (1, 3):
        return length, width
    return width, length


def draw_object_footprint(canvas, obj, project, scale):
    obj_type = int(obj.get("type", 0))
    map_scene = int(obj.get("mapScene", -1))
    width_tiles, length_tiles = object_dimensions(obj)
    if map_scene < 0 and obj_type not in (10, 11):
        return
    if map_scene < 0 and width_tiles <= 1 and length_tiles <= 1:
        return
    px, py = project(obj)
    block = max(1, int(round(scale)))
    x0 = px
    x1 = px + max(1, int(round(width_tiles * scale))) - 1
    y1 = py
    y0 = py - max(1, int(round(length_tiles * scale))) + 1
    color = PALETTE["footprint"]
    alpha = 0.32
    if map_scene >= 0:
        alpha = 0.46
    canvas.blend_rect(x0, y0, x1, y1, color, alpha)
    if width_tiles > 1 or length_tiles > 1:
        canvas.line(x0, y0, x1, y0, color, width=max(1, block // 3))
        canvas.line(x0, y1, x1, y1, color, width=max(1, block // 3))
        canvas.line(x0, y0, x0, y1, color, width=max(1, block // 3))
        canvas.line(x1, y0, x1, y1, color, width=max(1, block // 3))


def draw_background_sprite(canvas, sprite, x, y, scale):
    pixel_scale = max(0.18, float(scale) / 4.0)
    palette = sprite["palette"]
    pixels = sprite["pixels"]
    width = sprite["width"]
    height = sprite["height"]
    for sy in range(height):
        for sx in range(width):
            palette_index = pixels[sx + sy * width]
            if palette_index <= 0 or palette_index >= len(palette):
                continue
            color = palette[palette_index]
            dx0 = int(math.floor(x + sx * pixel_scale))
            dx1 = int(math.ceil(x + (sx + 1) * pixel_scale)) - 1
            dy0 = int(math.floor(y + sy * pixel_scale))
            dy1 = int(math.ceil(y + (sy + 1) * pixel_scale)) - 1
            canvas.rect(dx0, dy0, dx1, dy1, color)


def draw_mapscene(canvas, obj, map_scenes, project, scale):
    map_scene = int(obj.get("mapScene", -1))
    if map_scene < 0:
        return False
    sprite = map_scenes.get(map_scene)
    if sprite is None:
        return False
    px, py = project(obj)
    width_tiles, length_tiles = object_dimensions(obj, rotate_large=False)
    footprint_width = width_tiles * 4
    footprint_height = length_tiles * 4
    sprite_x = (footprint_width - sprite["width"]) / 2.0 + sprite["xOffset"]
    sprite_y = (footprint_height - sprite["height"]) / 2.0 + sprite["yOffset"]
    x = px + sprite_x * scale / 4.0
    y = py - length_tiles * scale + 1 + sprite_y * scale / 4.0
    draw_background_sprite(canvas, sprite, x, y, scale)
    return True


def draw_mapfunction_marker(canvas, obj, project, scale):
    if int(obj.get("mapFunction", -1)) < 0:
        return
    px, py = project(obj)
    radius = max(1, int(round(scale * 0.55)))
    cx = px + max(0, int(round(scale / 2.0)))
    cy = py - max(0, int(round(scale / 2.0)))
    canvas.rect(cx - radius, cy, cx + radius, cy, PALETTE["map_function"])
    canvas.rect(cx, cy - radius, cx, cy + radius, PALETTE["map_function"])


def draw_world_map(canvas, world_map, project, scale):
    block = max(1, int(round(scale)))
    for tile in world_map.get("tiles", []):
        draw_tile(canvas, tile, project, scale)
    objects = world_map.get("objects", [])
    for obj in objects:
        draw_object_footprint(canvas, obj, project, scale)
    map_scenes = world_map.get("mapScenes", {})
    mapscene_drawn = set()
    for index, obj in enumerate(objects):
        if draw_mapscene(canvas, obj, map_scenes, project, scale):
            mapscene_drawn.add(index)
    for obj in objects:
        draw_mapfunction_marker(canvas, obj, project, scale)
    width = max(1, int(round(scale / 3.0)))
    for index, obj in enumerate(objects):
        obj_type = obj.get("type")
        if index in mapscene_drawn:
            continue
        if obj_type not in (0, 2, 3, 9):
            continue
        x, y = project(obj)
        x0 = x
        y0 = y - block + 1
        x1 = x + block - 1
        y1 = y
        color = PALETTE["wall_light"] if obj_type == 9 else PALETTE["wall"]
        orientation = int(obj.get("orientation", 0))
        if obj_type == 9:
            if orientation in (0, 2):
                canvas.line(x0, y1, x1, y0, color, width=width)
            else:
                canvas.line(x0, y0, x1, y1, color, width=width)
        elif obj_type == 3:
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            cx, cy = corners[orientation % 4]
            canvas.rect(cx, cy, cx, cy, color)
        elif orientation == 0:
            canvas.line(x0, y0, x0, y1, color, width=width)
        elif orientation == 1:
            canvas.line(x0, y0, x1, y0, color, width=width)
        elif orientation == 2:
            canvas.line(x1, y0, x1, y1, color, width=width)
        else:
            canvas.line(x0, y1, x1, y1, color, width=width)


def parse_bounds(text):
    if str(text).strip().lower() in ("all", "*", "world", "full"):
        return None
    parts = [int(part.strip()) for part in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bounds must be minX,minY,maxX,maxY")
    return {"minX": parts[0], "minY": parts[1], "maxX": parts[2], "maxY": parts[3]}


def render_png(bounds, output, plane=0, pixels_per_tile=4.0):
    world_map = load_cache_world_map(bounds, plane=plane)
    bounds = world_map["bounds"]
    span_x = max(1, bounds["maxX"] - bounds["minX"] + 1)
    span_y = max(1, bounds["maxY"] - bounds["minY"] + 1)
    width = int(span_x * pixels_per_tile) + 1
    height = int(span_y * pixels_per_tile) + 1
    canvas = Canvas(width, height, PALETTE["paper"])

    def project(tile):
        px = int((tile["x"] - bounds["minX"]) * pixels_per_tile)
        py = int(height - 1 - (tile["y"] - bounds["minY"]) * pixels_per_tile)
        return px, py

    draw_world_map(canvas, world_map, project, pixels_per_tile)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save_png(output)
    return {"output": str(output), "bounds": bounds, "plane": plane, "tiles": len(world_map["tiles"]),
            "objects": len(world_map["objects"]), "regions": world_map["regions"],
            "textures": world_map.get("textures", 0), **world_map.get("stats", {}),
            "pixelWidth": width, "pixelHeight": height, "pixelsPerTile": pixels_per_tile,
            "source": "2006Scape Server/data/cache"}


def main():
    parser = argparse.ArgumentParser(description="Render a cache-backed minimap-style world map.")
    parser.add_argument("--bounds", default="all", type=parse_bounds, help="minX,minY,maxX,maxY or all")
    parser.add_argument("--plane", type=int, default=0)
    parser.add_argument("--pixels-per-tile", type=float, default=2.0)
    parser.add_argument("--output", default=str(OUT / "cache-world-map.png"))
    parser.add_argument("--summary", default=str(OUT / "cache-world-map.json"))
    args = parser.parse_args()
    summary = render_png(args.bounds, args.output, args.plane, args.pixels_per_tile)
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "summary": str(summary_path), **summary}, sort_keys=True))


if __name__ == "__main__":
    main()
