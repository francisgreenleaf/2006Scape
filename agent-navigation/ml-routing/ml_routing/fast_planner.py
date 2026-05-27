"""Fast model-backed route planning for agent-facing calls."""

from __future__ import annotations

import heapq
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from .collision import build_cache_collision, bounds_for_tiles, expand_route_path
from .common import coordinate_layer_transition_block, distance, iter_jsonl, parse_tile, tile_key
from .model import segment_prediction
from .paths import ensure_tool_imports


TRACE_SOURCE = "model_trace"
ROUTE_HINT_SOURCE = "route_hint"
SNAP_SOURCE = "snap"
CACHE_DIRECT_SOURCE = "cache_direct"


def _load_nav_modules():
    ensure_tool_imports()
    import navdb  # type: ignore
    import route_eval  # type: ignore

    return navdb, route_eval


def _hazard_severity(hazard: Dict[str, Any]) -> float:
    risk = str(hazard.get("risk", "")).lower()
    if any(word in risk for word in ("death", "lethal", "deadly")):
        return 10000.0
    if any(word in risk for word in ("high", "combat contact")):
        return 650.0
    if "medium" in risk:
        return 120.0
    if "low" in risk:
        return 15.0
    return 60.0


def _hazard_penalty(db: Dict[str, Any], navdb: Any, tile: Dict[str, int], args: SimpleNamespace) -> Tuple[float, List[Dict[str, Any]]]:
    penalty = 0.0
    warnings = []
    for dist, hazard in navdb.hazards_near(db, tile, args.hazard_buffer):
        risk_warnings = navdb.risk_warnings(
            hazard,
            args.combat_level,
            args.food,
            coins=args.coins,
            run_energy=args.run_energy,
            run_enabled=args.run_enabled,
        )
        if not risk_warnings:
            continue
        severity = _hazard_severity(hazard)
        penalty += severity
        warnings.append({
            "id": hazard.get("id"),
            "risk": hazard.get("risk", "unknown"),
            "distance": dist,
            "warnings": risk_warnings,
        })
    return penalty, warnings


def _direct_hazard_base_cost(hazard: Dict[str, Any], warnings: List[str], args: SimpleNamespace) -> float:
    risk = str(hazard.get("risk", "")).lower()
    if "operational" in risk:
        base = 3.0
    elif "blocker" in risk:
        base = 55.0 if warnings else 18.0
    elif any(word in risk for word in ("death", "lethal", "deadly", "dangerous")):
        base = 130.0 if warnings else 45.0
    elif "high" in risk:
        base = 90.0 if warnings else 32.0
    elif "medium" in risk:
        base = 26.0 if warnings else 8.0
    elif "low" in risk:
        base = 6.0 if warnings else 2.0
    else:
        base = 12.0 if warnings else 4.0
    return base * _runnable_hazard_factor(hazard, args)


def _runnable_hazard_factor(hazard: Dict[str, Any], args: SimpleNamespace) -> float:
    requirements = hazard.get("requirements", {}) or {}
    min_combat = requirements.get("minCombatLevel")
    min_food = requirements.get("minFood")
    min_run = requirements.get("minRunEnergy")
    margin = int(getattr(args, "direct_combat_margin", 5))
    combat_level = int(getattr(args, "combat_level", 0) or 0)
    food = int(getattr(args, "food", 0) or 0)
    run_energy = int(getattr(args, "run_energy", 0) or 0)
    run_enabled = bool(getattr(args, "run_enabled", False))
    combat_close = min_combat is None or combat_level >= int(min_combat) - margin
    food_ready = min_food is None or food >= int(min_food)
    run_ready = (
        run_enabled
        and (min_run is None or run_energy >= int(min_run))
    )
    if combat_close and food_ready and run_ready:
        return float(getattr(args, "runnable_hazard_cost_factor", 0.15))
    if food_ready and run_ready:
        return 0.7
    return 1.0


def _max_xy_distance(left: Dict[str, int], right: Dict[str, int]) -> int:
    return max(abs(int(left["x"]) - int(right["x"])), abs(int(left["y"]) - int(right["y"])))


def _target_hazard_discount(record: Dict[str, Any], x: int, y: int) -> float:
    if not record.get("targetInInfluence"):
        return 1.0
    target = record.get("targetTile") or {}
    if "x" not in target or "y" not in target:
        return 1.0
    radius = max(1, int(record.get("targetDiscountRadius") or 1))
    dist = max(abs(int(target["x"]) - x), abs(int(target["y"]) - y))
    if dist > radius:
        return 1.0
    floor = float(record.get("terminalHazardCostFactor") or 0.25)
    return floor + ((1.0 - floor) * (float(dist) / float(radius)))


def _hazard_influence_records(db: Dict[str, Any], navdb: Any, args: SimpleNamespace,
                              plane: int, target_tile: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    records = []
    buffer_radius = max(0, int(getattr(args, "direct_hazard_buffer", getattr(args, "hazard_buffer", 10))))
    for hazard in db.get("hazards", []):
        center = hazard.get("center") or {}
        if int(center.get("height", 0)) != plane:
            continue
        warnings = navdb.risk_warnings(
            hazard,
            args.combat_level,
            args.food,
            coins=args.coins,
            run_energy=args.run_energy,
            run_enabled=args.run_enabled,
        )
        radius = max(0, int(hazard.get("radius") or 0))
        influence_radius = radius + buffer_radius
        target_in_influence = bool(
            target_tile
            and target_tile.get("height", 0) == plane
            and _max_xy_distance(center, target_tile) <= influence_radius
        )
        base_cost = _direct_hazard_base_cost(hazard, warnings, args)
        if target_in_influence:
            base_cost *= float(getattr(args, "terminal_hazard_cost_factor", 0.25))
        records.append({
            "hazard": hazard,
            "center": center,
            "radius": radius,
            "influenceRadius": influence_radius,
            "targetTile": target_tile,
            "targetInInfluence": target_in_influence,
            "targetDiscountRadius": max(8, min(52, influence_radius)),
            "terminalHazardCostFactor": float(getattr(args, "terminal_hazard_cost_factor", 0.25)),
            "warnings": warnings,
            "baseCost": base_cost,
        })
    return records


def _direct_tile_penalty(records: List[Dict[str, Any]]):
    def penalty(x: int, y: int) -> float:
        total = 0.0
        for record in records:
            radius = int(record["influenceRadius"])
            if radius <= 0:
                continue
            center = record["center"]
            dist = max(abs(int(center["x"]) - x), abs(int(center["y"]) - y))
            if dist > radius:
                continue
            closeness = float(radius - dist + 1) / float(radius + 1)
            total += (
                float(record["baseCost"])
                * closeness
                * closeness
                * _target_hazard_discount(record, x, y)
            )
        return total

    return penalty


def _path_hazard_warnings(db: Dict[str, Any], navdb: Any, tiles: List[Dict[str, int]],
                          args: SimpleNamespace) -> List[Dict[str, Any]]:
    if not tiles:
        return []
    found: Dict[str, Dict[str, Any]] = {}
    stride = max(1, int(len(tiles) / 80))
    sample = list(tiles[::stride])
    if tile_key(sample[-1]) != tile_key(tiles[-1]):
        sample.append(tiles[-1])
    for tile in sample:
        for dist, hazard in navdb.hazards_near(db, tile, int(getattr(args, "hazard_buffer", 10))):
            warnings = navdb.risk_warnings(
                hazard,
                args.combat_level,
                args.food,
                coins=args.coins,
                run_energy=args.run_energy,
                run_enabled=args.run_enabled,
            )
            if not warnings:
                continue
            hazard_id = hazard.get("id")
            existing = found.get(hazard_id)
            if existing is None or dist < existing["distance"]:
                found[hazard_id] = {
                    "id": hazard_id,
                    "risk": hazard.get("risk", "unknown"),
                    "distance": dist,
                    "warnings": warnings,
                }
    return sorted(found.values(), key=lambda item: (item["distance"], item["id"]))


def _hazard_run_requirement(hazard: Dict[str, Any]) -> int:
    requirements = hazard.get("requirements", {}) or {}
    min_energy = int(requirements.get("minRunEnergy") or 0)
    if requirements.get("requiresRun") and min_energy <= 0:
        min_energy = 20
    return min_energy


def _is_run_worthy_hazard(hazard: Dict[str, Any]) -> bool:
    risk = str(hazard.get("risk", "")).lower()
    if _hazard_run_requirement(hazard) > 0:
        return True
    return any(word in risk for word in ("death", "dangerous", "lethal", "deadly"))


def _run_hazards_at_tile(db: Dict[str, Any], navdb: Any, tile: Dict[str, int],
                         args: SimpleNamespace) -> List[Dict[str, Any]]:
    hazards = []
    for dist, hazard in navdb.hazards_near(db, tile, int(getattr(args, "hazard_buffer", 10))):
        if not _is_run_worthy_hazard(hazard):
            continue
        hazards.append({
            "id": hazard.get("id"),
            "risk": hazard.get("risk", "unknown"),
            "distance": dist,
            "minRunEnergy": _hazard_run_requirement(hazard),
            "requiresRun": bool((hazard.get("requirements") or {}).get("requiresRun")),
        })
    return hazards


def _run_segments_for_path(db: Dict[str, Any], navdb: Any, tiles: List[Dict[str, int]],
                           args: SimpleNamespace) -> List[Dict[str, Any]]:
    segments = []
    active = None
    for index, (left, right) in enumerate(zip(tiles, tiles[1:])):
        hazards = _run_hazards_at_tile(db, navdb, right, args)
        if hazards:
            ids = sorted(set(item["id"] for item in hazards if item.get("id")))
            min_energy = max([int(item.get("minRunEnergy") or 0) for item in hazards] or [0])
            if active is None:
                active = {
                    "startIndex": index,
                    "endIndex": index + 1,
                    "from": left,
                    "to": right,
                    "hazardIds": ids,
                    "minRunEnergy": min_energy,
                    "distance": distance(left, right),
                }
            else:
                active["endIndex"] = index + 1
                active["to"] = right
                active["hazardIds"] = sorted(set(active["hazardIds"]) | set(ids))
                active["minRunEnergy"] = max(int(active["minRunEnergy"]), min_energy)
                active["distance"] += distance(left, right)
        elif active is not None:
            active["distance"] = int(active["distance"])
            segments.append(active)
            active = None
    if active is not None:
        active["distance"] = int(active["distance"])
        segments.append(active)
    return segments


def attach_run_plan(route: Dict[str, Any], db: Dict[str, Any], navdb: Any, args: SimpleNamespace) -> None:
    tiles = [tile for tile in (route.get("collisionPath") or route.get("waypoints") or []) if isinstance(tile, dict)]
    if len(tiles) < 2:
        return
    run_segments = _run_segments_for_path(db, navdb, tiles, args)
    run_tiles = sum(int(segment.get("distance") or 0) for segment in run_segments)
    total = _path_distance(tiles)
    route["runSegments"] = run_segments
    route["runPlan"] = {
        "policy": "conserve_run_until_hazard_segments",
        "runTileDistance": run_tiles,
        "walkTileDistance": max(0, total - run_tiles),
        "segmentCount": len(run_segments),
        "routeDistance": total,
    }


def _add_edge(adjacency: Dict[str, List[Dict[str, Any]]], left: str, right: str, cost: float, source: str, meta: Dict[str, Any]) -> None:
    if left == right:
        return
    adjacency.setdefault(left, []).append({
        "to": right,
        "cost": float(cost),
        "source": source,
        "meta": meta,
    })


def _route_hint_records(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        from .dataset import route_hint_edges

        current_records = route_hint_edges()
        if current_records:
            return current_records
    except Exception:
        pass

    dataset_dir = model.get("datasetDir")
    if not dataset_dir:
        return []
    path = Path(dataset_dir) / "route_hint_edges.jsonl"
    return list(iter_jsonl(path))


def _allowed_route_status(status: str, args: SimpleNamespace) -> bool:
    if status in ("verified", "learned-graph"):
        return True
    if status == "learned-partial":
        return bool(getattr(args, "include_partial", False))
    if status == "derived-from-existing-landmark":
        return bool(getattr(args, "include_derived", False))
    if status == "needs-verification":
        return bool(getattr(args, "include_unverified", False))
    return False


def _edge_cost_from_stats(model: Dict[str, Any], stats: Dict[str, Any], left: Dict[str, int], right: Dict[str, int]) -> Tuple[float, Dict[str, Any]]:
    prediction = segment_prediction(model, left, right)
    weights = model.get("weights", {})
    cost = prediction["predictedTicks"]
    cost += prediction["riskScore"] * float(weights.get("riskPenalty", 950.0))
    cost += (1.0 - min(1.0, prediction["confidence"])) * float(weights.get("lowConfidencePenalty", 140.0))
    cost += float(stats.get("objectInteractionRate") or 0.0) * float(weights.get("objectInteractionPenalty", 25.0))
    return cost, prediction


def _build_graph(model: Dict[str, Any], db: Dict[str, Any], navdb: Any, args: SimpleNamespace) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, int]] = {}
    adjacency: Dict[str, List[Dict[str, Any]]] = {}
    hazard_warnings: Dict[str, List[Dict[str, Any]]] = {}
    for key, stats in model.get("edgeStats", {}).items():
        if ">" not in key or int(stats.get("successes") or 0) <= 0:
            continue
        left_key, right_key = key.split(">", 1)
        left = parse_tile(left_key)
        right = parse_tile(right_key)
        if not left or not right:
            continue
        nodes[left_key] = left
        nodes[right_key] = right
        cost, prediction = _edge_cost_from_stats(model, stats, left, right)
        hazard_cost, warnings = _hazard_penalty(db, navdb, right, args)
        if hazard_cost >= 8000.0 and not args.allow_lethal:
            continue
        if warnings:
            hazard_warnings.setdefault(right_key, []).extend(warnings)
        _add_edge(adjacency, left_key, right_key, cost + hazard_cost, TRACE_SOURCE, {
            "prediction": prediction,
            "successes": stats.get("successes"),
            "failures": stats.get("failures"),
            "confidence": stats.get("confidence"),
            "riskScore": stats.get("riskScore"),
            "objectInteractionRate": stats.get("objectInteractionRate"),
        })

    for record in _route_hint_records(model):
        status = str(record.get("routeStatus") or "")
        if not _allowed_route_status(status, args):
            continue
        left = parse_tile(record.get("fromTile") or record.get("from"))
        right = parse_tile(record.get("toTile") or record.get("to"))
        if not left or not right:
            continue
        left_key = tile_key(left)
        right_key = tile_key(right)
        nodes[left_key] = left
        nodes[right_key] = right
        dist = float(record.get("distance") or distance(left, right) or 1.0)
        hazard_cost, warnings = _hazard_penalty(db, navdb, right, args)
        if hazard_cost >= 8000.0 and not args.allow_lethal:
            continue
        if warnings:
            hazard_warnings.setdefault(right_key, []).extend(warnings)
        cost = max(1.0, dist) + float(record.get("statusPenalty") or 0.0) + hazard_cost
        _add_edge(adjacency, left_key, right_key, cost, ROUTE_HINT_SOURCE, {
            "route": record.get("routeId"),
            "status": status,
            "distance": dist,
            "objectStepCount": int(record.get("objectStepCount") or 0),
        })
        if record.get("bidirectional") is True:
            _add_edge(adjacency, right_key, left_key, cost, ROUTE_HINT_SOURCE, {
                "route": record.get("routeId"),
                "status": status,
                "distance": dist,
                "objectStepCount": int(record.get("objectStepCount") or 0),
            })
    return {"nodes": nodes, "adjacency": adjacency, "hazardWarningsByKey": hazard_warnings}


def _parse_tile_or_place(db: Dict[str, Any], navdb: Any, value: str) -> Tuple[Dict[str, int], str]:
    tile = parse_tile(value)
    if tile:
        return tile, tile_key(tile)
    place = navdb.find_place(db, value)
    if not place:
        raise RuntimeError("unknown place or tile: {}".format(value))
    return place["tile"], place["id"]


def _target_place(db: Dict[str, Any], navdb: Any, value: str) -> Dict[str, Any]:
    target = navdb.place_or_tile_target(db, value)
    if not target:
        raise RuntimeError("unknown target place or tile: {}".format(value))
    return target


def _connect_start(graph: Dict[str, Any], start_tile: Dict[str, int], snap_distance: int) -> str:
    start_key = tile_key(start_tile)
    graph["nodes"][start_key] = start_tile
    if graph["adjacency"].get(start_key):
        return start_key
    for key, tile in list(graph["nodes"].items()):
        if key == start_key:
            continue
        dist = distance(start_tile, tile)
        if dist <= snap_distance:
            _add_edge(graph["adjacency"], start_key, key, max(1.0, dist), SNAP_SOURCE, {"distance": dist})
    return start_key


def _target_keys(graph: Dict[str, Any], target: Dict[str, Any]) -> set:
    radius = int(target.get("arrivalRadius", 1))
    target_tile = target["tile"]
    return {key for key, tile in graph["nodes"].items() if distance(tile, target_tile) <= radius}


def _dijkstra(graph: Dict[str, Any], start_key: str, targets: set) -> Tuple[Optional[str], Dict[str, float], Dict[str, Tuple[str, Dict[str, Any]]], set]:
    queue = [(0.0, start_key)]
    best = {start_key: 0.0}
    previous: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    settled = set()
    while queue:
        cost, key = heapq.heappop(queue)
        if key in settled:
            continue
        settled.add(key)
        if key in targets:
            return key, best, previous, settled
        for edge in graph["adjacency"].get(key, []):
            next_key = edge["to"]
            next_cost = cost + edge["cost"]
            if next_cost >= best.get(next_key, math.inf):
                continue
            best[next_key] = next_cost
            previous[next_key] = (key, edge)
            heapq.heappush(queue, (next_cost, next_key))
    return None, best, previous, settled


def _reconstruct(previous: Dict[str, Tuple[str, Dict[str, Any]]], end_key: str) -> Tuple[List[str], List[Tuple[str, str, Dict[str, Any]]]]:
    edges = []
    key = end_key
    while key in previous:
        prev_key, edge = previous[key]
        edges.append((prev_key, key, edge))
        key = prev_key
    edges.reverse()
    if not edges:
        return [end_key], []
    keys = [edges[0][0]]
    for _prev, to_key, _edge in edges:
        keys.append(to_key)
    return keys, edges


def _path_distance(tiles: List[Dict[str, int]]) -> int:
    return int(sum(distance(left, right) for left, right in zip(tiles, tiles[1:]) if math.isfinite(distance(left, right))))


def _source_summary(edges: List[Tuple[str, str, Dict[str, Any]]]) -> Tuple[Dict[str, int], Dict[str, int]]:
    sources: Dict[str, int] = {}
    routes: Dict[str, int] = {}
    for _left, _right, edge in edges:
        source = edge.get("source", "unknown")
        sources[source] = sources.get(source, 0) + 1
        route_id = edge.get("meta", {}).get("route")
        if route_id:
            routes[route_id] = routes.get(route_id, 0) + 1
    return sources, routes


def _tick_estimate(edges: List[Tuple[str, str, Dict[str, Any]]]) -> float:
    total = 0.0
    for _left, _right, edge in edges:
        meta = edge.get("meta", {})
        prediction = meta.get("prediction") if isinstance(meta.get("prediction"), dict) else {}
        if prediction.get("predictedTicks") is not None:
            total += float(prediction.get("predictedTicks") or 0.0)
        else:
            total += float(meta.get("distance") or edge.get("cost") or 1.0)
    return total


def _compress_waypoints(route_eval: Any, graph: Dict[str, Any], keys: List[str], max_gap: int) -> List[Dict[str, int]]:
    # Reuse the existing route_eval helpers indirectly by keeping this simple:
    if not keys:
        return []
    tiles = [graph["nodes"][key] for key in keys]
    kept = [tiles[0]]
    last = tiles[0]
    for tile in tiles[1:-1]:
        if distance(last, tile) >= max_gap:
            kept.append(tile)
            last = tile
    if kept[-1] != tiles[-1]:
        kept.append(tiles[-1])
    return kept


def _first_batch_target(graph: Dict[str, Any], keys: List[str], max_distance: int) -> Dict[str, int]:
    tiles = [graph["nodes"][key] for key in keys]
    if len(tiles) <= 1:
        return tiles[0]
    start = tiles[0]
    best = tiles[1]
    for tile in tiles[1:]:
        if distance(start, tile) > max_distance:
            break
        best = tile
    return best


def _first_path_batch_target(tiles: List[Dict[str, int]], max_distance: int) -> Dict[str, int]:
    if len(tiles) <= 1:
        return tiles[0]
    travelled = 0.0
    best = tiles[1]
    for left, right in zip(tiles, tiles[1:]):
        step = distance(left, right)
        if travelled + step > max_distance:
            break
        travelled += step
        best = right
    return best


def _cache_collision_enabled(args: SimpleNamespace) -> bool:
    return not bool(getattr(args, "no_cache_collision", False))


def _target_distance_increases(tiles: List[Dict[str, int]], target_tile: Dict[str, int]) -> int:
    if not tiles:
        return 0
    increases = 0
    previous_distance = distance(tiles[0], target_tile)
    for tile in tiles[1:]:
        current_distance = distance(tile, target_tile)
        if current_distance > previous_distance:
            increases += 1
        previous_distance = current_distance
    return increases


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _turn_waypoints(tiles: List[Dict[str, int]]) -> List[Dict[str, int]]:
    if len(tiles) <= 2:
        return tiles
    kept = [tiles[0]]
    previous_direction = None
    for left, right in zip(tiles, tiles[1:]):
        direction = (
            _sign(int(right["x"]) - int(left["x"])),
            _sign(int(right["y"]) - int(left["y"])),
        )
        if previous_direction is not None and direction != previous_direction:
            kept.append(left)
        previous_direction = direction
    if kept[-1] != tiles[-1]:
        kept.append(tiles[-1])
    return kept


def _route_steps(tiles: List[Dict[str, int]], max_gap: int) -> List[Dict[str, int]]:
    if len(tiles) <= 2:
        return tiles
    max_gap = max(1, int(max_gap))
    kept = [tiles[0]]
    previous_direction = None
    since_last = 0.0
    for left, right in zip(tiles, tiles[1:]):
        direction = (
            _sign(int(right["x"]) - int(left["x"])),
            _sign(int(right["y"]) - int(left["y"])),
        )
        since_last += distance(left, right)
        turn_after_enough_distance = (
            previous_direction is not None
            and direction != previous_direction
            and since_last >= max(4, max_gap // 2)
        )
        if turn_after_enough_distance or since_last >= max_gap:
            if kept[-1] != left:
                kept.append(left)
            since_last = 0.0
        previous_direction = direction
    if kept[-1] != tiles[-1]:
        kept.append(tiles[-1])
    return kept


def _apply_cache_collision(base: Dict[str, Any], route_eval: Any, tiles: List[Dict[str, int]],
                           edges: List[Tuple[str, str, Dict[str, Any]]], target_tile: Dict[str, int],
                           args: SimpleNamespace, arrival_radius: int = 0) -> None:
    if not _cache_collision_enabled(args) or len(tiles) < 2:
        return
    if tile_key(tiles[-1]) != tile_key(target_tile):
        arrival_radius = 0
    expanded = expand_route_path(
        tiles,
        edges=edges,
        padding=int(getattr(args, "collision_padding_tiles", 64)),
        max_expansions_per_segment=int(getattr(args, "collision_max_expansions", 250000)),
        final_arrival_radius=arrival_radius,
        waypoint_arrival_radius=int(getattr(args, "waypoint_arrival_radius", 1)),
        optimize_shortcuts=not bool(getattr(args, "no_shortcut_optimize", False)),
        shortcut_max_span=int(getattr(args, "shortcut_max_span", 128)),
        shortcut_min_savings=int(getattr(args, "shortcut_min_savings", 4)),
        shortcut_corridor_radius=int(getattr(args, "shortcut_corridor_radius", 18)),
    )
    path = expanded.get("tiles") or []
    summary = {
        "enabled": True,
        "success": bool(expanded.get("success")),
        "pathTiles": len(path),
        "distance": expanded.get("distance"),
        "preShortcutDistance": expanded.get("preShortcutDistance"),
        "shortcutSavings": expanded.get("shortcutSavings"),
        "shortcutCount": expanded.get("shortcutCount"),
        "segmentsExpanded": expanded.get("segmentsExpanded"),
        "skippedObjectTransitions": expanded.get("skippedObjectTransitions"),
        "arrivedWithinRadius": expanded.get("arrivedWithinRadius"),
        "arrivedNearWaypoints": expanded.get("arrivedNearWaypoints"),
        "failures": len(expanded.get("failures") or []),
        "gridStats": (expanded.get("grid") or {}).get("stats", {}),
        "bounds": (expanded.get("grid") or {}).get("bounds"),
    }
    base["collision"] = summary
    base["collisionExpanded"] = bool(expanded.get("success"))
    base["collisionPathDistance"] = expanded.get("distance")
    base["collisionWarnings"] = (expanded.get("warnings") or [])[:int(getattr(args, "max_warnings", 8))]
    if expanded.get("failures"):
        base["collisionFailures"] = expanded["failures"][:int(getattr(args, "max_warnings", 8))]
    if not path:
        return
    base["collisionPath"] = path
    route_steps = _route_steps(path, int(getattr(args, "route_step_gap", 10)))
    base["routeSteps"] = route_steps
    base["routeStepCount"] = len(route_steps)
    if not expanded.get("success"):
        if base.get("quality") not in ("bad",):
            base["quality"] = "suspicious"
        return
    direct_distance = distance(tiles[0], target_tile)
    route_distance = int(expanded.get("distance") or 0)
    analysis_path = _turn_waypoints(path)
    target_distance_increases = _target_distance_increases(analysis_path, target_tile)
    wrong_way = route_eval.wrong_way_flags(analysis_path, target_tile)
    detours = route_eval.detour_segments(
        analysis_path,
        target_tile,
        max_segments=int(getattr(args, "max_suspects", 5)),
    )
    base["macroRouteDistance"] = base.get("routeDistance")
    base["routeDistance"] = route_distance
    base["next"] = _first_path_batch_target(path, int(getattr(args, "max_batch_distance", 24)))
    base["directDistance"] = direct_distance
    base["detourRatio"] = round(float(route_distance) / max(1.0, float(direct_distance)), 3)
    base["targetDistanceIncreases"] = target_distance_increases
    base["collision"]["analysisWaypoints"] = len(analysis_path)
    base["wrongWayFlags"] = wrong_way
    base["detourSegments"] = detours
    base["quality"] = route_eval.quality_level(base["detourRatio"], target_distance_increases, len(wrong_way))


def _cache_direct_candidate(db: Dict[str, Any], navdb: Any, route_eval: Any,
                            start_tile: Dict[str, int], start_label: str, target: Dict[str, Any],
                            args: SimpleNamespace) -> Optional[Dict[str, Any]]:
    if bool(getattr(args, "no_cache_collision", False)) or bool(getattr(args, "no_cache_direct", False)):
        return None
    target_tile = target["tile"]
    if start_tile.get("height", 0) != target_tile.get("height", 0):
        return None
    padding = max(
        int(getattr(args, "collision_padding_tiles", 64)),
        int(getattr(args, "hazard_buffer", 10)) + 32,
    )
    bounds = bounds_for_tiles([start_tile, target_tile], padding=padding)
    grid = build_cache_collision(bounds, plane=int(start_tile.get("height", 0)))
    hazard_records = _hazard_influence_records(db, navdb, args, int(start_tile.get("height", 0)), target_tile=target_tile)
    target_radius = int(target.get("arrivalRadius", 1))
    path = grid.find_path(
        start_tile,
        target_tile,
        max_expansions=int(getattr(args, "direct_max_expansions", getattr(args, "collision_max_expansions", 250000))),
        arrival_radius=target_radius,
        tile_penalty=_direct_tile_penalty(hazard_records),
    )
    if not path:
        return {
            "mode": "cache_direct",
            "status": "error",
            "quality": "bad",
            "error": "no cache-clipped direct path",
            "collision": {
                "enabled": True,
                "success": False,
                "gridStats": grid.stats,
                "bounds": grid.bounds,
            },
        }
    route_distance = _path_distance(path)
    direct_distance = distance(start_tile, target_tile)
    analysis_path = _turn_waypoints(path)
    target_distance_increases = _target_distance_increases(analysis_path, target_tile)
    wrong_way = route_eval.wrong_way_flags(analysis_path, target_tile)
    detours = route_eval.detour_segments(
        analysis_path,
        target_tile,
        max_segments=int(getattr(args, "max_suspects", 5)),
    )
    hazard_warnings = _path_hazard_warnings(db, navdb, path, args)
    route_steps = _route_steps(path, int(getattr(args, "route_step_gap", 10)))
    arrived = distance(path[-1], target_tile) <= target_radius
    candidate = {
        "planner": "fast",
        "mode": "cache_direct",
        "status": "ok" if arrived else "no-learned-route",
        "quality": route_eval.quality_level(
            float(route_distance) / max(1.0, float(direct_distance)),
            target_distance_increases,
            len(wrong_way),
        ),
        "from": start_label,
        "to": target["id"],
        "targetTile": target_tile,
        "arrivalRadius": target_radius,
        "endTile": path[-1],
        "next": _first_path_batch_target(path, int(getattr(args, "max_batch_distance", 24))),
        "waypoints": route_steps,
        "routeSteps": route_steps,
        "routeStepCount": len(route_steps),
        "directDistance": direct_distance,
        "routeDistance": route_distance,
        "collisionPathDistance": route_distance,
        "collisionPath": path,
        "collisionExpanded": True,
        "collision": {
            "enabled": True,
            "success": True,
            "pathTiles": len(path),
            "distance": route_distance,
            "directCandidate": True,
            "hazardInfluences": len(hazard_records),
            "gridStats": grid.stats,
            "bounds": grid.bounds,
        },
        "estimatedTicks": round(float(route_distance), 1),
        "detourRatio": round(float(route_distance) / max(1.0, float(direct_distance)), 3),
        "targetDistanceIncreases": target_distance_increases,
        "wrongWayFlags": wrong_way,
        "detourSegments": detours,
        "edgeSources": {CACHE_DIRECT_SOURCE: max(0, len(path) - 1)},
        "hazardWarnings": hazard_warnings[:int(getattr(args, "max_warnings", 8))],
    }
    attach_run_plan(candidate, db, navdb, args)
    return candidate


def _quality_rank(quality: Optional[str]) -> int:
    return {
        "ok": 0,
        "watch": 1,
        "suspicious": 2,
        "bad": 3,
    }.get(quality or "", 2)


def _compact_direct_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    keep = [
        "mode", "status", "quality", "routeDistance", "directDistance", "detourRatio",
        "targetDistanceIncreases", "edgeSources", "hazardWarnings", "error",
        "routeStepCount", "endTile", "next", "runPlan",
    ]
    return {key: candidate[key] for key in keep if key in candidate and candidate[key] not in (None, [], {})}


def _should_try_cache_direct(base: Dict[str, Any], args: SimpleNamespace) -> bool:
    if bool(getattr(args, "no_cache_direct", False)):
        return False
    if base.get("status") != "ok":
        return True
    detour_ratio = float(base.get("detourRatio") or 1.0)
    if detour_ratio >= float(getattr(args, "direct_candidate_min_detour", 1.22)):
        return True
    if base.get("quality") == "bad":
        return True
    if int(base.get("targetDistanceIncreases") or 0) >= 4:
        return True
    return False


def _maybe_select_cache_direct(base: Dict[str, Any], direct: Optional[Dict[str, Any]],
                               args: SimpleNamespace) -> Dict[str, Any]:
    if not direct:
        return base
    base["directCandidate"] = _compact_direct_candidate(direct)
    if direct.get("status") != "ok":
        return base
    base_distance = float(base.get("routeDistance") or math.inf)
    direct_distance = float(direct.get("routeDistance") or math.inf)
    savings = base_distance - direct_distance
    min_savings = float(getattr(args, "direct_candidate_min_savings", 24))
    direct_rank = _quality_rank(direct.get("quality"))
    base_rank = _quality_rank(base.get("quality"))
    base_incomplete = base.get("status") != "ok"
    large_detour = float(base.get("detourRatio") or 1.0) >= float(getattr(args, "direct_candidate_min_detour", 1.22))
    safe_enough = direct_rank <= base_rank + 1
    if base_incomplete or (safe_enough and savings >= min_savings) or (large_detour and safe_enough and savings > 0):
        selected = dict(direct)
        selection = {
            "previousStatus": base.get("status"),
            "previousQuality": base.get("quality"),
            "previousRouteDistance": base.get("routeDistance"),
        }
        if base_incomplete:
            selection.update({
                "completionAddedTiles": int(-savings) if math.isfinite(savings) and savings < 0 else 0,
                "reason": "learned graph only reached a frontier; cache-direct path is selected because it reaches the requested target",
            })
        else:
            selection.update({
                "savedTiles": int(savings) if math.isfinite(savings) else None,
                "reason": "cache-direct path reached the requested target with a shorter hazard-costed clipped route",
            })
        selected["selectedOverLearned"] = selection
        selected["learnedCandidate"] = _compact_direct_candidate(base)
        return selected
    return base


def _frontier(graph: Dict[str, Any], target_tile: Dict[str, int], best: Dict[str, float],
              previous: Dict[str, Tuple[str, Dict[str, Any]]], start_tile: Dict[str, int],
              max_batch_distance: int) -> Optional[Tuple[str, Dict[str, Any]]]:
    choice = None
    start_remaining = distance(start_tile, target_tile)
    for key, cost in best.items():
        tile = graph["nodes"].get(key)
        if not tile or tile.get("height", 0) != target_tile.get("height", 0):
            continue
        remaining = distance(tile, target_tile)
        progress = start_remaining - remaining
        score = remaining + (cost * 0.05)
        if progress <= 0:
            score += 5000.0
        if choice is None or score < choice[0]:
            choice = (score, key, tile, remaining, progress)
    if not choice:
        return None
    _score, key, tile, remaining, progress = choice
    keys, edges = _reconstruct(previous, key)
    tiles = [graph["nodes"][item] for item in keys]
    return key, {
        "frontierTile": tile,
        "frontierDistanceToTarget": remaining,
        "routeDistance": _path_distance(tiles),
        "estimatedTicks": round(_tick_estimate(edges), 1),
        "cost": round(best.get(key, 0.0), 3),
        "frontierScore": {
            "remainingDistance": remaining,
            "distanceProgress": progress,
            "score": round(_score, 2),
        },
        "next": _first_batch_target(graph, keys, max_batch_distance) if len(keys) > 1 else tile,
        "waypoints": _compress_waypoints(None, graph, keys, max_batch_distance),
        "edgeSources": _source_summary(edges)[0],
        "_macroTiles": tiles,
        "_macroEdges": edges,
    }


def fast_route(args: SimpleNamespace, model: Dict[str, Any]) -> Dict[str, Any]:
    if not model:
        raise RuntimeError("no trained ML routing model found; run route_ml.py export && route_ml.py train first")
    navdb, route_eval = _load_nav_modules()
    db = navdb.load_db()
    start_tile, start_label = _parse_tile_or_place(db, navdb, args.from_tile)
    target = _target_place(db, navdb, args.to)
    base = {
        "planner": "fast",
        "from": start_label,
        "to": target["id"],
        "targetTile": target["tile"],
        "arrivalRadius": int(target.get("arrivalRadius", 1)),
        "connectedNodes": 0,
        "modelId": model.get("modelId"),
        "modelTrainedAt": model.get("trainedAt"),
    }
    transition_block = coordinate_layer_transition_block(start_tile, target["tile"])
    if transition_block:
        message = transition_block["message"]
        base.update({
            "mode": transition_block["mode"],
            "status": transition_block["status"],
            "quality": "bad",
            "error": message,
            "message": message,
            "transition": transition_block,
            "coordinateLayers": {
                "from": transition_block["fromLayer"],
                "to": transition_block["toLayer"],
            },
        })
        return base

    graph = _build_graph(model, db, navdb, args)
    start_key = _connect_start(graph, start_tile, args.graph_snap_distance)
    targets = _target_keys(graph, target)
    end_key, best, previous, settled = _dijkstra(graph, start_key, targets)
    base["connectedNodes"] = len(settled)
    if end_key is None:
        frontier = _frontier(graph, target["tile"], best, previous, start_tile, args.max_batch_distance)
        base["status"] = "no-learned-route"
        if frontier:
            _frontier_key, details = frontier
            base.update(details)
            macro_tiles = base.pop("_macroTiles", [])
            macro_edges = base.pop("_macroEdges", [])
            _apply_cache_collision(
                base, route_eval, macro_tiles, macro_edges, target["tile"], args,
                arrival_radius=int(target.get("arrivalRadius", 1)),
            )
        if _should_try_cache_direct(base, args):
            direct = _cache_direct_candidate(db, navdb, route_eval, start_tile, start_label, target, args)
            base = _maybe_select_cache_direct(base, direct, args)
        attach_run_plan(base, db, navdb, args)
        return base

    keys, edges = _reconstruct(previous, end_key)
    tiles = [graph["nodes"][key] for key in keys]
    source_counts, route_counts = _source_summary(edges)
    tick_estimate = _tick_estimate(edges)
    direct_distance = navdb.distance(start_tile, target["tile"])
    route_distance = _path_distance(tiles)
    target_distance_increases = 0
    previous_distance = navdb.distance(tiles[0], target["tile"]) if tiles else 0
    for tile in tiles[1:]:
        current_distance = navdb.distance(tile, target["tile"])
        if current_distance > previous_distance:
            target_distance_increases += 1
        previous_distance = current_distance
    detour_ratio = float(route_distance) / max(1.0, float(direct_distance))
    wrong_way = route_eval.wrong_way_flags(tiles, target["tile"])
    detours = route_eval.detour_segments(tiles, target["tile"], max_segments=args.max_suspects)
    warnings = []
    for _left, right, _edge in edges:
        warnings.extend(graph["hazardWarningsByKey"].get(right, []))
    base.update({
        "status": "ok",
        "cost": round(best[end_key], 3),
        "estimatedTicks": round(tick_estimate, 1),
        "endTile": graph["nodes"][end_key],
        "next": _first_batch_target(graph, keys, args.max_batch_distance),
        "waypoints": _compress_waypoints(route_eval, graph, keys, args.compress_gap),
        "directDistance": direct_distance,
        "routeDistance": route_distance,
        "detourRatio": round(detour_ratio, 3),
        "quality": route_eval.quality_level(detour_ratio, target_distance_increases, len(wrong_way)),
        "targetDistanceIncreases": target_distance_increases,
        "wrongWayFlags": wrong_way,
        "detourSegments": detours,
        "edgeSources": source_counts,
        "routesUsed": route_counts,
        "hazardWarnings": warnings[:args.max_warnings],
    })
    _apply_cache_collision(
        base, route_eval, tiles, edges, target["tile"], args,
        arrival_radius=int(target.get("arrivalRadius", 1)),
    )
    if _should_try_cache_direct(base, args):
        direct = _cache_direct_candidate(db, navdb, route_eval, start_tile, start_label, target, args)
        base = _maybe_select_cache_direct(base, direct, args)
    attach_run_plan(base, db, navdb, args)
    return base
