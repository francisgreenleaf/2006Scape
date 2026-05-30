"""Cache-derived clipping grid for fast route expansion.

The server builds movement clips in RegionFactory/Region from cache terrain
settings and loc.dat object definitions. This module mirrors that logic enough
for offline route planning: learned macro edges can be expanded into adjacent
walk tiles before they are scored or drawn.
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .common import Tile, UNDERGROUND_MIN_Y, coordinate_layer, distance, parse_tile, tile_key
from .paths import ensure_tool_imports


FULL_TILE_BLOCK = 0x200000
SOLID_OBJECT_BLOCK = 0x100
SOLID_OBJECT_EXTRA_BLOCK = 0x20000

MASK_SOUTH = 0x1280102
MASK_WEST = 0x1280108
MASK_NORTH = 0x1280120
MASK_EAST = 0x1280180
MASK_SOUTH_WEST = 0x128010E
MASK_NORTH_WEST = 0x1280138
MASK_SOUTH_EAST = 0x1280183
MASK_NORTH_EAST = 0x12801E0

DIRECTIONS = (
    (0, -1),
    (-1, 0),
    (0, 1),
    (1, 0),
    (-1, -1),
    (-1, 1),
    (1, -1),
    (1, 1),
)

CACHE_REGION_SIZE = 64
_CACHE_AREA_CACHE: Optional[Dict[str, Any]] = None


@dataclass
class CollisionGrid:
    bounds: Dict[str, int]
    plane: int
    clips: Dict[Tuple[int, int], int]
    stats: Dict[str, Any]
    valid_tiles: Optional[Set[Tuple[int, int]]] = None

    def in_bounds(self, x: int, y: int) -> bool:
        in_rect = (
            self.bounds["minX"] <= x <= self.bounds["maxX"]
            and self.bounds["minY"] <= y <= self.bounds["maxY"]
        )
        if not in_rect:
            return False
        if self.valid_tiles is not None and (x, y) not in self.valid_tiles:
            return False
        return True

    def clip(self, x: int, y: int) -> int:
        return self.clips.get((x, y), 0)

    def can_step_xy(self, x: int, y: int, dx: int, dy: int) -> bool:
        nx = x + dx
        ny = y + dy
        if not self.in_bounds(nx, ny):
            return False
        if dx == 0 and dy == -1:
            return (self.clip(x, y - 1) & MASK_SOUTH) == 0
        if dx == -1 and dy == 0:
            return (self.clip(x - 1, y) & MASK_WEST) == 0
        if dx == 0 and dy == 1:
            return (self.clip(x, y + 1) & MASK_NORTH) == 0
        if dx == 1 and dy == 0:
            return (self.clip(x + 1, y) & MASK_EAST) == 0
        if dx == -1 and dy == -1:
            return (
                (self.clip(x - 1, y - 1) & MASK_SOUTH_WEST) == 0
                and (self.clip(x - 1, y) & MASK_WEST) == 0
                and (self.clip(x, y - 1) & MASK_SOUTH) == 0
            )
        if dx == -1 and dy == 1:
            return (
                (self.clip(x - 1, y + 1) & MASK_NORTH_WEST) == 0
                and (self.clip(x - 1, y) & MASK_WEST) == 0
                and (self.clip(x, y + 1) & MASK_NORTH) == 0
            )
        if dx == 1 and dy == -1:
            return (
                (self.clip(x + 1, y - 1) & MASK_SOUTH_EAST) == 0
                and (self.clip(x + 1, y) & MASK_EAST) == 0
                and (self.clip(x, y - 1) & MASK_SOUTH) == 0
            )
        if dx == 1 and dy == 1:
            return (
                (self.clip(x + 1, y + 1) & MASK_NORTH_EAST) == 0
                and (self.clip(x + 1, y) & MASK_EAST) == 0
                and (self.clip(x, y + 1) & MASK_NORTH) == 0
            )
        return False

    def can_step(self, left: Tile, right: Tile) -> bool:
        if left.get("height", 0) != self.plane or right.get("height", 0) != self.plane:
            return False
        dx = int(right["x"]) - int(left["x"])
        dy = int(right["y"]) - int(left["y"])
        if max(abs(dx), abs(dy)) != 1:
            return False
        return self.can_step_xy(int(left["x"]), int(left["y"]), dx, dy)

    def find_path(self, start: Tile, end: Tile, max_expansions: int = 250000,
                  arrival_radius: int = 0,
                  tile_penalty: Optional[Callable[[int, int], float]] = None,
                  blocked: Optional[Callable[[int, int], bool]] = None) -> Optional[List[Tile]]:
        if start.get("height", 0) != self.plane or end.get("height", 0) != self.plane:
            return None
        start_xy = (int(start["x"]), int(start["y"]))
        end_xy = (int(end["x"]), int(end["y"]))
        arrival_radius = max(0, int(arrival_radius))
        if start_xy == end_xy or (arrival_radius and max(abs(start_xy[0] - end_xy[0]), abs(start_xy[1] - end_xy[1])) <= arrival_radius):
            return [dict(start)]
        if not self.in_bounds(*start_xy) or not self.in_bounds(*end_xy):
            return None

        def heuristic(x: int, y: int) -> int:
            return max(abs(end_xy[0] - x), abs(end_xy[1] - y))

        queue: List[Tuple[float, float, int, int, int]] = []
        serial = 0
        heapq.heappush(queue, (heuristic(*start_xy), 0, serial, start_xy[0], start_xy[1]))
        best = {start_xy: 0.0}
        previous: Dict[Tuple[int, int], Tuple[int, int]] = {}
        expansions = 0

        while queue:
            _priority, cost, _serial, x, y = heapq.heappop(queue)
            if cost != best.get((x, y)):
                continue
            if (x, y) == end_xy or (arrival_radius and heuristic(x, y) <= arrival_radius):
                return self._reconstruct(previous, start_xy, (x, y))
            expansions += 1
            if expansions > max_expansions:
                self.stats["lastPathLimitHit"] = True
                return None
            for dx, dy in DIRECTIONS:
                if not self.can_step_xy(x, y, dx, dy):
                    continue
                nx = x + dx
                ny = y + dy
                if blocked is not None and blocked(nx, ny):
                    continue
                penalty = float(tile_penalty(nx, ny) if tile_penalty is not None else 0.0)
                if not math.isfinite(penalty):
                    continue
                next_cost = cost + 1.0 + max(0.0, penalty)
                if next_cost >= best.get((nx, ny), math.inf):
                    continue
                best[(nx, ny)] = next_cost
                previous[(nx, ny)] = (x, y)
                serial += 1
                heapq.heappush(queue, (next_cost + heuristic(nx, ny), next_cost, serial, nx, ny))
        return None

    def _reconstruct(self, previous: Dict[Tuple[int, int], Tuple[int, int]],
                     start_xy: Tuple[int, int], end_xy: Tuple[int, int]) -> List[Tile]:
        keys = [end_xy]
        current = end_xy
        while current != start_xy:
            current = previous[current]
            keys.append(current)
        keys.reverse()
        return [{"x": x, "y": y, "height": self.plane} for x, y in keys]


def bounds_for_tiles(tiles: Iterable[Tile], padding: int = 64) -> Dict[str, int]:
    clean = [tile for tile in tiles if tile and "x" in tile and "y" in tile]
    if not clean:
        raise ValueError("cannot build collision bounds without tiles")
    plane = int(clean[0].get("height", 0))
    return {
        "minX": min(int(tile["x"]) for tile in clean) - int(padding),
        "minY": min(int(tile["y"]) for tile in clean) - int(padding),
        "maxX": max(int(tile["x"]) for tile in clean) + int(padding),
        "maxY": max(int(tile["y"]) for tile in clean) + int(padding),
        "height": plane,
    }


def _load_cache_world_map_module():
    ensure_tool_imports()
    import cache_world_map  # type: ignore

    return cache_world_map


def _region_intersects(record: Dict[str, int], bounds: Dict[str, int]) -> bool:
    return not (
        record["regionX"] + 63 < bounds["minX"]
        or record["regionX"] > bounds["maxX"]
        or record["regionY"] + 63 < bounds["minY"]
        or record["regionY"] > bounds["maxY"]
    )


def _region_origin(x: int, y: int) -> Tuple[int, int]:
    return (
        (int(x) // CACHE_REGION_SIZE) * CACHE_REGION_SIZE,
        (int(y) // CACHE_REGION_SIZE) * CACHE_REGION_SIZE,
    )


def _cache_areas() -> Dict[str, Any]:
    global _CACHE_AREA_CACHE
    if _CACHE_AREA_CACHE is not None:
        return _CACHE_AREA_CACHE
    cache_world_map = _load_cache_world_map_module()
    cache = cache_world_map.CacheReader()
    records = {
        (int(record["regionX"]), int(record["regionY"])): record
        for record in cache_world_map.load_map_index(cache)
    }
    underground_regions = {key for key in records if key[1] >= UNDERGROUND_MIN_Y}
    remaining = set(underground_regions)
    component_by_region: Dict[Tuple[int, int], str] = {}
    components: Dict[str, Dict[str, Any]] = {}
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = {start}
        while stack:
            x, y = stack.pop()
            for neighbor in (
                (x + CACHE_REGION_SIZE, y),
                (x - CACHE_REGION_SIZE, y),
                (x, y + CACHE_REGION_SIZE),
                (x, y - CACHE_REGION_SIZE),
            ):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        xs = [item[0] for item in component]
        ys = [item[1] for item in component]
        component_id = "underground-{}-{}".format(min(xs), min(ys))
        bounds = {
            "minX": min(xs),
            "minY": min(ys),
            "maxX": max(xs) + CACHE_REGION_SIZE - 1,
            "maxY": max(ys) + CACHE_REGION_SIZE - 1,
        }
        components[component_id] = {
            "id": component_id,
            "bounds": bounds,
            "regionCount": len(component),
        }
        for region in component:
            component_by_region[region] = component_id
    _CACHE_AREA_CACHE = {
        "records": records,
        "undergroundComponentByRegion": component_by_region,
        "components": components,
    }
    return _CACHE_AREA_CACHE


def cache_area_for_tile(tile: Optional[Tile]) -> Dict[str, Any]:
    layer = coordinate_layer(tile)
    if not tile:
        return {"layer": layer}
    x = int(tile["x"])
    y = int(tile["y"])
    region = _region_origin(x, y)
    areas = _cache_areas()
    record = areas["records"].get(region)
    result = {
        "layer": layer,
        "regionX": region[0],
        "regionY": region[1],
        "hasCacheRegion": bool(record),
    }
    if layer == "underground":
        component_id = areas["undergroundComponentByRegion"].get(region)
        result["componentId"] = component_id
        if component_id:
            result["component"] = areas["components"].get(component_id)
    return result


def cache_area_transition_block(start: Optional[Tile], target: Optional[Tile]) -> Optional[Dict[str, Any]]:
    if coordinate_layer(start) != "underground" or coordinate_layer(target) != "underground":
        return None
    from_area = cache_area_for_tile(start)
    to_area = cache_area_for_tile(target)
    if not from_area.get("componentId") or not to_area.get("componentId"):
        message = (
            "ML routing supports underground routes only inside known cache-backed "
            "underground areas. One of these tiles is outside loaded underground map data."
        )
        return {
            "status": "unsupported-coordinate-layer",
            "mode": "unknown_underground_area",
            "fromLayer": "underground",
            "toLayer": "underground",
            "fromTile": dict(start) if start else None,
            "targetTile": dict(target) if target else None,
            "fromArea": from_area,
            "toArea": to_area,
            "reason": "unknown_underground_cache_area",
            "message": message,
        }
    if from_area.get("componentId") != to_area.get("componentId"):
        message = (
            "ML routing cannot route between separate underground cache areas in one route. "
            "Use the appropriate entrance, exit, ladder, stairs, trapdoor, gate, or other "
            "object transition first, then request a new route in the destination area."
        )
        return {
            "status": "requires-object-transition",
            "mode": "requires_object_transition",
            "fromLayer": "underground",
            "toLayer": "underground",
            "fromTile": dict(start) if start else None,
            "targetTile": dict(target) if target else None,
            "fromArea": from_area,
            "toArea": to_area,
            "reason": "separate_underground_areas_require_object_transition",
            "message": message,
        }
    return None


def _add_clip(clips: Dict[Tuple[int, int], int], bounds: Dict[str, int], x: int, y: int, shift: int) -> bool:
    if not (
        bounds["minX"] <= x <= bounds["maxX"]
        and bounds["minY"] <= y <= bounds["maxY"]
    ):
        return False
    clips[(x, y)] = clips.get((x, y), 0) | int(shift)
    return True


def _object_definition(loc_defs: Sequence[Dict[str, Any]], object_id: int) -> Dict[str, Any]:
    if 0 <= object_id < len(loc_defs):
        return loc_defs[object_id]
    return {
        "id": object_id,
        "width": 1,
        "length": 1,
        "solid": True,
        "interactive": False,
        "clipped": True,
    }


def _object_dimensions(definition: Dict[str, Any], direction: int) -> Tuple[int, int]:
    width = max(1, int(definition.get("width", 1)))
    length = max(1, int(definition.get("length", 1)))
    if direction in (1, 3):
        return length, width
    return width, length


def _add_variable_object(clips: Dict[Tuple[int, int], int], bounds: Dict[str, int],
                         x: int, y: int, obj_type: int, direction: int, clipped: bool) -> int:
    added = 0

    def mark(px: int, py: int, shift: int) -> None:
        nonlocal added
        if _add_clip(clips, bounds, px, py, shift):
            added += 1

    if obj_type == 0:
        if direction == 0:
            mark(x, y, 128)
            mark(x - 1, y, 8)
        elif direction == 1:
            mark(x, y, 2)
            mark(x, y + 1, 32)
        elif direction == 2:
            mark(x, y, 8)
            mark(x + 1, y, 128)
        elif direction == 3:
            mark(x, y, 32)
            mark(x, y - 1, 2)
    elif obj_type in (1, 3):
        if direction == 0:
            mark(x, y, 1)
            mark(x - 1, y, 16)
        elif direction == 1:
            mark(x, y, 4)
            mark(x + 1, y + 1, 64)
        elif direction == 2:
            mark(x, y, 16)
            mark(x + 1, y - 1, 1)
        elif direction == 3:
            mark(x, y, 64)
            mark(x - 1, y - 1, 4)
    elif obj_type == 2:
        if direction == 0:
            mark(x, y, 130)
            mark(x - 1, y, 8)
            mark(x, y + 1, 32)
        elif direction == 1:
            mark(x, y, 10)
            mark(x, y + 1, 32)
            mark(x + 1, y, 128)
        elif direction == 2:
            mark(x, y, 40)
            mark(x + 1, y, 128)
            mark(x, y - 1, 2)
        elif direction == 3:
            mark(x, y, 160)
            mark(x, y - 1, 2)
            mark(x - 1, y, 8)

    if not clipped:
        return added
    if obj_type == 0:
        if direction == 0:
            mark(x, y, 65536)
            mark(x - 1, y, 4096)
        elif direction == 1:
            mark(x, y, 1024)
            mark(x, y + 1, 16384)
        elif direction == 2:
            mark(x, y, 4096)
            mark(x + 1, y, 65536)
        elif direction == 3:
            mark(x, y, 16384)
            mark(x, y - 1, 1024)
    elif obj_type in (1, 3):
        if direction == 0:
            mark(x, y, 512)
            mark(x - 1, y + 1, 8192)
        elif direction == 1:
            mark(x, y, 2048)
            mark(x + 1, y + 1, 32768)
        elif direction == 2:
            mark(x, y, 8192)
            mark(x + 1, y + 1, 512)
        elif direction == 3:
            mark(x, y, 32768)
            mark(x - 1, y - 1, 2048)
    elif obj_type == 2:
        if direction == 0:
            mark(x, y, 66560)
            mark(x - 1, y, 4096)
            mark(x, y + 1, 16384)
        elif direction == 1:
            mark(x, y, 5120)
            mark(x, y + 1, 16384)
            mark(x + 1, y, 65536)
        elif direction == 2:
            mark(x, y, 20480)
            mark(x + 1, y, 65536)
            mark(x, y - 1, 1024)
        elif direction == 3:
            mark(x, y, 81920)
            mark(x, y - 1, 1024)
            mark(x - 1, y, 4096)
    return added


def _add_solid_object(clips: Dict[Tuple[int, int], int], bounds: Dict[str, int],
                      x: int, y: int, width: int, length: int, clipped: bool) -> int:
    shift = SOLID_OBJECT_BLOCK + (SOLID_OBJECT_EXTRA_BLOCK if clipped else 0)
    added = 0
    for px in range(x, x + width):
        for py in range(y, y + length):
            if _add_clip(clips, bounds, px, py, shift):
                added += 1
    return added


def build_cache_collision(bounds: Dict[str, int], plane: Optional[int] = None) -> CollisionGrid:
    cache_world_map = _load_cache_world_map_module()
    plane = int(bounds.get("height", 0) if plane is None else plane)
    clean_bounds = {
        "minX": int(bounds["minX"]),
        "minY": int(bounds["minY"]),
        "maxX": int(bounds["maxX"]),
        "maxY": int(bounds["maxY"]),
        "height": plane,
    }
    cache = cache_world_map.CacheReader()
    records = cache_world_map.load_map_index(cache)
    loc_defs = cache_world_map.load_loc_defs(cache)
    clips: Dict[Tuple[int, int], int] = {}
    stats: Dict[str, Any] = {
        "regions": 0,
        "clips": 0,
        "validTiles": 0,
        "validTileBoundary": clean_bounds["maxY"] >= UNDERGROUND_MIN_Y,
        "terrainBlocks": 0,
        "wallObjects": 0,
        "solidObjects": 0,
        "groundDecorationBlocks": 0,
        "objectsSeen": 0,
        "lastPathLimitHit": False,
    }
    valid_tiles: Optional[Set[Tuple[int, int]]] = set() if stats["validTileBoundary"] else None

    for record in records:
        if not _region_intersects(record, clean_bounds):
            continue
        terrain_file = cache.get_file(4, record["terrainFile"])
        if terrain_file is None:
            continue
        try:
            terrain = cache_world_map.decode_terrain(cache_world_map.degzip(terrain_file))
        except Exception:
            continue
        stats["regions"] += 1
        if valid_tiles is not None:
            for local_x in range(64):
                x = record["regionX"] + local_x
                if x < clean_bounds["minX"] or x > clean_bounds["maxX"]:
                    continue
                for local_y in range(64):
                    y = record["regionY"] + local_y
                    if clean_bounds["minY"] <= y <= clean_bounds["maxY"]:
                        valid_tiles.add((x, y))
        settings = terrain["settings"]
        for local_z in range(4):
            for local_x in range(64):
                for local_y in range(64):
                    if (settings[local_z][local_x][local_y] & 1) != 1:
                        continue
                    height = local_z
                    if (settings[1][local_x][local_y] & 2) == 2:
                        height -= 1
                    if height != plane:
                        continue
                    if _add_clip(
                        clips,
                        clean_bounds,
                        record["regionX"] + local_x,
                        record["regionY"] + local_y,
                        FULL_TILE_BLOCK,
                    ):
                        stats["terrainBlocks"] += 1

        object_file = cache.get_file(4, record["objectFile"])
        if object_file is None:
            continue
        try:
            decoded_objects = cache_world_map.decode_objects(cache_world_map.degzip(object_file))
        except Exception:
            continue
        for obj in decoded_objects:
            height = int(obj["height"])
            local_x = int(obj["x"])
            local_y = int(obj["y"])
            if (settings[1][local_x][local_y] & 2) == 2:
                height -= 1
            if height != plane:
                continue
            x = record["regionX"] + local_x
            y = record["regionY"] + local_y
            if x < clean_bounds["minX"] - 3 or x > clean_bounds["maxX"] + 3:
                continue
            if y < clean_bounds["minY"] - 3 or y > clean_bounds["maxY"] + 3:
                continue
            stats["objectsSeen"] += 1
            definition = _object_definition(loc_defs, int(obj["id"]))
            if not bool(definition.get("solid", definition.get("blocks", True))):
                continue
            obj_type = int(obj["type"])
            direction = int(obj["orientation"])
            clipped = bool(definition.get("clipped", True))
            if obj_type == 22:
                if bool(definition.get("interactive", False)):
                    if _add_clip(clips, clean_bounds, x, y, FULL_TILE_BLOCK):
                        stats["groundDecorationBlocks"] += 1
                continue
            if obj_type >= 9:
                width, length = _object_dimensions(definition, direction)
                added = _add_solid_object(clips, clean_bounds, x, y, width, length, clipped)
                if added:
                    stats["solidObjects"] += 1
                continue
            if 0 <= obj_type <= 3:
                added = _add_variable_object(clips, clean_bounds, x, y, obj_type, direction, clipped)
                if added:
                    stats["wallObjects"] += 1

    stats["clips"] = len(clips)
    if valid_tiles is not None:
        stats["validTiles"] = len(valid_tiles)
    return CollisionGrid(clean_bounds, plane, clips, stats, valid_tiles=valid_tiles)


def _edge_payload(edge: Any) -> Dict[str, Any]:
    if isinstance(edge, tuple) and len(edge) >= 3 and isinstance(edge[2], dict):
        return edge[2]
    if isinstance(edge, dict):
        return edge
    return {}


def _is_object_transition(edge: Any) -> bool:
    payload = _edge_payload(edge)
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    try:
        if float(meta.get("objectInteractionRate") or 0.0) > 0.0:
            return True
    except (TypeError, ValueError):
        pass
    try:
        if int(meta.get("objectStepCount") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return bool(meta.get("objectTransition"))


def _compact_failure(left: Tile, right: Tile, edge: Any, reason: str) -> Dict[str, Any]:
    payload = _edge_payload(edge)
    return {
        "from": tile_key(left),
        "to": tile_key(right),
        "distance": distance(left, right),
        "source": payload.get("source", "unknown"),
        "reason": reason,
    }


def _path_distance(tiles: Sequence[Tile]) -> int:
    return int(sum(distance(left, right) for left, right in zip(tiles, tiles[1:])))


def _dedupe_adjacent(tiles: List[Tile]) -> List[Tile]:
    deduped = []
    previous = ""
    for tile in tiles:
        key = tile_key(tile)
        if key == previous:
            continue
        deduped.append(tile)
        previous = key
    return deduped


def _within_corridor(candidate: Sequence[Tile], reference: Sequence[Tile], radius: int) -> bool:
    if radius <= 0 or not reference:
        return True
    ref_xy = [(int(tile["x"]), int(tile["y"])) for tile in reference]
    for tile in candidate:
        x = int(tile["x"])
        y = int(tile["y"])
        if min(max(abs(x - rx), abs(y - ry)) for rx, ry in ref_xy) > radius:
            return False
    return True


def _shortcut_path(path: List[Tile], grid: CollisionGrid, max_span: int,
                   min_savings: int, corridor_radius: int,
                   max_expansions: int) -> Dict[str, Any]:
    if len(path) < 4 or max_span <= 2:
        return {"tiles": path, "shortcuts": 0, "savings": 0, "preDistance": _path_distance(path)}
    optimized = list(path)
    shortcuts = 0
    savings = 0
    i = 0
    while i < len(optimized) - 2:
        max_j = min(len(optimized) - 1, i + max_span)
        best = None
        for j in range(max_j, i + 2, -8):
            reference = optimized[i:j + 1]
            reference_distance = _path_distance(reference)
            if reference_distance < min_savings + 2:
                continue
            lower_bound = distance(optimized[i], optimized[j])
            if lower_bound + min_savings >= reference_distance:
                continue
            candidate = grid.find_path(optimized[i], optimized[j], max_expansions=max_expansions)
            if not candidate:
                continue
            candidate_distance = _path_distance(candidate)
            if candidate_distance + min_savings >= reference_distance:
                continue
            if not _within_corridor(candidate, reference, corridor_radius):
                continue
            best = (j, candidate, reference_distance, candidate_distance)
            break
        if not best:
            i += 4
            continue
        j, candidate, reference_distance, candidate_distance = best
        optimized = optimized[:i] + candidate + optimized[j + 1:]
        shortcuts += 1
        savings += int(reference_distance - candidate_distance)
        i = max(0, i - 8)
    return {
        "tiles": _dedupe_adjacent(optimized),
        "shortcuts": shortcuts,
        "savings": savings,
        "preDistance": _path_distance(path),
    }


def expand_route_path(tiles: Sequence[Tile], edges: Optional[Sequence[Any]] = None,
                      padding: int = 64, max_expansions_per_segment: int = 250000,
                      final_arrival_radius: int = 0,
                      waypoint_arrival_radius: int = 1,
                      optimize_shortcuts: bool = True,
                      shortcut_max_span: int = 128,
                      shortcut_min_savings: int = 4,
                      shortcut_corridor_radius: int = 18) -> Dict[str, Any]:
    clean = [parse_tile(tile) for tile in tiles]
    clean = [tile for tile in clean if tile is not None]
    if len(clean) < 2:
        return {
            "success": True,
            "tiles": clean,
            "distance": 0,
            "warnings": [],
            "failures": [],
            "skippedObjectTransitions": 0,
            "segmentsExpanded": 0,
            "grid": {},
        }

    plane = int(clean[0].get("height", 0))
    bounds = bounds_for_tiles(clean, padding=padding)
    grid = build_cache_collision(bounds, plane=plane)
    expanded: List[Tile] = [clean[0]]
    warnings: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    skipped_object_transitions = 0
    segments_expanded = 0
    edge_list = list(edges or [])

    final_arrival_radius = max(0, int(final_arrival_radius))
    waypoint_arrival_radius = max(0, int(waypoint_arrival_radius))
    arrived_within_radius = False
    arrived_near_waypoints = 0
    for index, (left, right) in enumerate(zip(clean, clean[1:])):
        edge = edge_list[index] if index < len(edge_list) else {}
        is_final = index == len(clean) - 2
        arrival_radius = final_arrival_radius if is_final else waypoint_arrival_radius
        if left.get("height", 0) != right.get("height", 0):
            skipped_object_transitions += 1
            warnings.append(_compact_failure(left, right, edge, "plane-change-transition"))
            expanded.append(right)
            continue
        if _is_object_transition(edge):
            skipped_object_transitions += 1
            warnings.append(_compact_failure(left, right, edge, "object-transition-not-expanded"))
            expanded.append(right)
            continue
        if distance(left, right) <= 1 and grid.can_step(left, right):
            expanded.append(right)
            segments_expanded += 1
            continue
        segment = grid.find_path(left, right, max_expansions=max_expansions_per_segment)
        if not segment and arrival_radius:
            segment = grid.find_path(
                left,
                right,
                max_expansions=max_expansions_per_segment,
                arrival_radius=arrival_radius,
            )
        if segment:
            if arrival_radius and tile_key(segment[-1]) != tile_key(right):
                if is_final:
                    arrived_within_radius = True
                    reason = "arrived-within-radius"
                else:
                    arrived_near_waypoints += 1
                    reason = "arrived-near-waypoint"
                warnings.append(_compact_failure(segment[-1], right, edge, reason))
            expanded.extend(segment[1:])
            segments_expanded += 1
            continue
        failure = _compact_failure(left, right, edge, "no-cache-clipped-path")
        failures.append(failure)
        warnings.append(failure)
        expanded.append(right)

    expanded = _dedupe_adjacent(expanded)
    shortcut_info = {
        "tiles": expanded,
        "shortcuts": 0,
        "savings": 0,
        "preDistance": _path_distance(expanded),
    }
    if optimize_shortcuts and not failures and skipped_object_transitions == 0:
        shortcut_info = _shortcut_path(
            expanded,
            grid,
            max_span=int(shortcut_max_span),
            min_savings=int(shortcut_min_savings),
            corridor_radius=int(shortcut_corridor_radius),
            max_expansions=max_expansions_per_segment,
        )
        expanded = shortcut_info["tiles"]
    return {
        "success": not failures,
        "tiles": expanded,
        "distance": _path_distance(expanded),
        "preShortcutDistance": shortcut_info["preDistance"],
        "shortcutSavings": shortcut_info["savings"],
        "shortcutCount": shortcut_info["shortcuts"],
        "warnings": warnings,
        "failures": failures,
        "skippedObjectTransitions": skipped_object_transitions,
        "arrivedWithinRadius": arrived_within_radius,
        "arrivedNearWaypoints": arrived_near_waypoints,
        "segmentsExpanded": segments_expanded,
        "grid": {
            "bounds": grid.bounds,
            "plane": grid.plane,
            "stats": grid.stats,
        },
    }
