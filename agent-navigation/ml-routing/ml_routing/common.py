"""Small utilities shared by the ML routing commands."""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


Tile = Dict[str, int]

LEVEL0_SURFACE_BOUNDS = {"minX": 1728, "minY": 2560, "maxX": 3839, "maxY": 4031}
UNDERGROUND_MIN_Y = 6400


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError:
                continue
            record["_sourcePath"] = str(path)
            record["_sourceLine"] = line_no
            yield record


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
            count += 1
    return count


def parse_tile(value: Any) -> Optional[Tile]:
    if isinstance(value, dict) and "x" in value and "y" in value:
        try:
            return {
                "x": int(value["x"]),
                "y": int(value["y"]),
                "height": int(value.get("height", 0)),
            }
        except (TypeError, ValueError):
            return None
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        if len(parts) == 3:
            try:
                return {"x": int(parts[0]), "y": int(parts[1]), "height": int(parts[2])}
            except ValueError:
                return None
    return None


def tile_key(tile: Optional[Tile]) -> str:
    if tile is None:
        return ""
    return "{},{},{}".format(tile["x"], tile["y"], tile.get("height", 0))


def coordinate_layer(tile: Optional[Tile]) -> str:
    if not tile:
        return "unknown"
    x = int(tile["x"])
    y = int(tile["y"])
    if (
        LEVEL0_SURFACE_BOUNDS["minX"] <= x <= LEVEL0_SURFACE_BOUNDS["maxX"]
        and LEVEL0_SURFACE_BOUNDS["minY"] <= y <= LEVEL0_SURFACE_BOUNDS["maxY"]
    ):
        return "surface"
    if y >= UNDERGROUND_MIN_Y:
        return "underground"
    return "off_surface"


def coordinate_layer_transition_block(start: Optional[Tile], target: Optional[Tile]) -> Optional[Dict[str, Any]]:
    from_layer = coordinate_layer(start)
    to_layer = coordinate_layer(target)
    if from_layer == "surface" and to_layer == "surface":
        return None
    if from_layer == "unknown" or to_layer == "unknown":
        return None
    if from_layer != to_layer:
        status = "requires-object-transition"
        mode = "requires_object_transition"
        reason = "{}_to_{}_requires_object_transition".format(from_layer, to_layer)
        message = (
            "ML routing cannot route underground yet or cross coordinate layers. "
            "Route to the surface-side object transition first, use the transition, "
            "then continue with local previews or a dedicated area runner."
        )
    else:
        status = "unsupported-coordinate-layer"
        mode = "surface_only"
        reason = "{}_routing_not_supported".format(from_layer)
        message = (
            "ML routing cannot route underground yet. It is surface-only for now. "
            "Use local path previews, object transitions, or a dedicated area runner "
            "inside non-surface areas until entrance-aware underground routing exists."
        )
    return {
        "status": status,
        "mode": mode,
        "fromLayer": from_layer,
        "toLayer": to_layer,
        "fromTile": dict(start) if start else None,
        "targetTile": dict(target) if target else None,
        "reason": reason,
        "message": message,
        "surfaceBounds": dict(LEVEL0_SURFACE_BOUNDS),
        "undergroundMinY": UNDERGROUND_MIN_Y,
    }


def distance(a: Optional[Tile], b: Optional[Tile]) -> float:
    if not a or not b:
        return math.inf
    if a.get("height", 0) != b.get("height", 0):
        return math.inf
    return max(abs(a["x"] - b["x"]), abs(a["y"] - b["y"]))


def chunked(items: List[Any], chunks: int) -> List[List[Any]]:
    chunks = max(1, min(chunks, len(items) or 1))
    size = int(math.ceil(float(len(items)) / float(chunks))) if items else 1
    return [items[index:index + size] for index in range(0, len(items), size)] or [[]]


def compact_counter(counter: Dict[str, int], limit: int = 12) -> List[Dict[str, Any]]:
    return [
        {"key": key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on", "y")
