"""Fast model-backed route planning for agent-facing calls."""

from __future__ import annotations

import heapq
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple

from .collision import (
    build_cache_collision,
    bounds_for_tiles,
    cache_area_for_tile,
    cache_area_transition_block,
    expand_route_path,
)
from .common import coordinate_layer, coordinate_layer_transition_block, distance, iter_jsonl, parse_tile, tile_key
from .model import segment_prediction
from .paths import ensure_tool_imports
from .transition_catalog import reverse_transition, transition_pair
from .validation import walk_edge_warning


TRACE_SOURCE = "model_trace"
ROUTE_HINT_SOURCE = "route_hint"
SNAP_SOURCE = "snap"
CACHE_DIRECT_SOURCE = "cache_direct"
CACHE_MESH_SOURCE = "cache_mesh"
OBJECT_TRANSITION_SOURCE = "object_transition"


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


def _route_hint_requirement_warnings(navdb: Any, record: Dict[str, Any],
                                     args: SimpleNamespace) -> List[str]:
    route_like = {
        "requirements": record.get("requirements") or {},
        "runPolicy": record.get("runPolicy") or {},
    }
    return navdb.route_requirement_warnings(
        route_like,
        args.combat_level,
        args.food,
        coins=args.coins,
        run_energy=args.run_energy,
        run_enabled=args.run_enabled,
    )


def _route_hint_requirement_penalty(warnings: List[str]) -> float:
    penalty = 0.0
    for warning in warnings:
        lowered = str(warning).lower()
        if "combat" in lowered:
            penalty += 900.0
        elif "food" in lowered:
            penalty += 700.0
        elif "run energy" in lowered or "run disabled" in lowered:
            penalty += 800.0
        else:
            penalty += 500.0
    return penalty


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


def _learned_exposure_tile_penalty(model: Dict[str, Any], plane: int):
    weights = model.get("weights", {}) if isinstance(model, dict) else {}
    region_stats = model.get("regionStats", {}) if isinstance(model, dict) else {}
    combat_weight = float(weights.get("combatExposureTilePenalty", 18.0))
    hp_weight = float(weights.get("hpLossTilePenalty", 1.5))
    failure_weight = float(weights.get("failureTilePenalty", 8.0))

    def penalty(x: int, y: int) -> float:
        stats = region_stats.get("{},{},{}".format(x // 8, y // 8, plane)) or {}
        combat_exposure = float(stats.get("combatExposure") or stats.get("combatRate") or 0.0)
        hp_loss = float(stats.get("hpLossPerAttempt") or 0.0)
        if combat_exposure <= 0.0 and hp_loss <= 0.0:
            return 0.0
        failure_rate = float(stats.get("failureRate") or 0.0)
        confidence = max(0.15, min(1.0, float(stats.get("confidence") or 0.0)))
        return confidence * (
            combat_exposure * combat_weight
            + hp_loss * hp_weight
            + failure_rate * failure_weight
        )

    return penalty


def _path_learned_exposure(model: Dict[str, Any], tiles: List[Dict[str, int]]) -> Dict[str, Any]:
    if not isinstance(model, dict) or not tiles:
        return {}
    region_stats = model.get("regionStats", {}) or {}
    if not region_stats:
        return {}
    stride = max(1, int(len(tiles) / 120))
    samples = []
    for tile in tiles[::stride]:
        key = "{},{},{}".format(int(tile["x"]) // 8, int(tile["y"]) // 8, int(tile.get("height", 0)))
        stats = region_stats.get(key)
        if not stats:
            continue
        exposure = float(stats.get("combatExposure") or stats.get("combatRate") or 0.0)
        hp_loss = float(stats.get("hpLossPerAttempt") or 0.0)
        if exposure <= 0.0 and hp_loss <= 0.0:
            continue
        samples.append((exposure, hp_loss, float(stats.get("confidence") or 0.0)))
    if not samples:
        return {}
    return {
        "source": "model_region",
        "sampledRegions": len(samples),
        "maxCombatExposure": round(max(item[0] for item in samples), 6),
        "avgCombatExposure": round(sum(item[0] for item in samples) / len(samples), 6),
        "maxHpLossPerAttempt": round(max(item[1] for item in samples), 4),
        "avgConfidence": round(sum(item[2] for item in samples) / len(samples), 6),
    }


def _direct_tile_penalty(records: List[Dict[str, Any]], learned_penalty=None):
    def penalty(x: int, y: int) -> float:
        total = learned_penalty(x, y) if learned_penalty is not None else 0.0
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
    cost += prediction.get("combatExposure", 0.0) * float(weights.get("combatExposurePenalty", 420.0))
    cost += prediction.get("hpLossPerAttempt", 0.0) * float(weights.get("hpLossPenalty", 35.0))
    cost += (1.0 - min(1.0, prediction["confidence"])) * float(weights.get("lowConfidencePenalty", 140.0))
    cost += float(stats.get("objectInteractionRate") or 0.0) * float(weights.get("objectInteractionPenalty", 25.0))
    return cost, prediction


def _route_area_filter(start_tile: Dict[str, int], target_tile: Dict[str, int]) -> Optional[Callable[[Dict[str, int]], bool]]:
    start_layer = coordinate_layer(start_tile)
    target_layer = coordinate_layer(target_tile)
    if start_layer != target_layer:
        return None
    if start_layer == "surface":
        return lambda tile: coordinate_layer(tile) == "surface"
    if start_layer == "underground":
        start_component = cache_area_for_tile(start_tile).get("componentId")
        if not start_component:
            return lambda _tile: False
        return lambda tile: cache_area_for_tile(tile).get("componentId") == start_component
    return None


def _build_graph(model: Dict[str, Any], db: Dict[str, Any], navdb: Any, args: SimpleNamespace,
                 area_filter: Optional[Callable[[Dict[str, int]], bool]] = None) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, int]] = {}
    adjacency: Dict[str, List[Dict[str, Any]]] = {}
    hazard_warnings: Dict[str, List[Dict[str, Any]]] = {}
    rejected_model_edges: List[Dict[str, Any]] = []
    for key, stats in model.get("edgeStats", {}).items():
        if ">" not in key or int(stats.get("successes") or 0) <= 0:
            continue
        left_key, right_key = key.split(">", 1)
        left = parse_tile(left_key)
        right = parse_tile(right_key)
        if not left or not right:
            continue
        geometry_warning = walk_edge_warning(left, right)
        if geometry_warning:
            geometry_warning["edge"] = key
            rejected_model_edges.append(geometry_warning)
            continue
        if area_filter is not None and (not area_filter(left) or not area_filter(right)):
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
        if area_filter is not None and (not area_filter(left) or not area_filter(right)):
            continue
        left_key = tile_key(left)
        right_key = tile_key(right)
        nodes[left_key] = left
        nodes[right_key] = right
        dist = float(record.get("distance") or distance(left, right) or 1.0)
        hazard_cost, warnings = _hazard_penalty(db, navdb, right, args)
        route_warnings = _route_hint_requirement_warnings(navdb, record, args)
        if hazard_cost >= 8000.0 and not args.allow_lethal:
            continue
        if warnings:
            hazard_warnings.setdefault(right_key, []).extend(warnings)
        if route_warnings:
            hazard_warnings.setdefault(right_key, []).append({
                "id": "route:{}".format(record.get("routeId")),
                "risk": "route-requirement",
                "distance": 0,
                "warnings": route_warnings,
            })
        requirement_cost = _route_hint_requirement_penalty(route_warnings)
        cost = max(1.0, dist) + float(record.get("statusPenalty") or 0.0) + hazard_cost + requirement_cost
        transition = record.get("transition") if isinstance(record.get("transition"), dict) else None
        object_transition = bool(record.get("objectTransition") or transition)
        meta = {
            "route": record.get("routeId"),
            "status": status,
            "distance": dist,
            "objectStepCount": int(record.get("objectStepCount") or 0),
            "objectTransition": object_transition,
            "transition": transition,
            "routeRequirementWarnings": route_warnings,
            "preserveShape": bool(record.get("preserveShape")),
        }
        _add_edge(adjacency, left_key, right_key, cost, ROUTE_HINT_SOURCE, meta)
        if record.get("bidirectional") is True:
            reverse_meta = dict(meta)
            reverse_meta["transition"] = reverse_transition(transition)
            _add_edge(adjacency, right_key, left_key, cost, ROUTE_HINT_SOURCE, reverse_meta)
    return {
        "nodes": nodes,
        "adjacency": adjacency,
        "hazardWarningsByKey": hazard_warnings,
        "rejectedModelEdges": rejected_model_edges,
    }


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


def _edge_meta(edge: Dict[str, Any]) -> Dict[str, Any]:
    meta = edge.get("meta") if isinstance(edge.get("meta"), dict) else {}
    return meta


def _is_short_object_transition(left: Dict[str, int], right: Dict[str, int], edge: Dict[str, Any]) -> bool:
    meta = _edge_meta(edge)
    if bool(meta.get("objectTransition")):
        return True
    try:
        object_steps = int(meta.get("objectStepCount") or 0)
    except (TypeError, ValueError):
        object_steps = 0
    if object_steps <= 0:
        return False
    dist = distance(left, right)
    if dist <= 2:
        return True
    route_id = str(meta.get("route") or "").lower()
    return "transition" in route_id and dist <= 4


def _transition_edges_from_learned_path(edges: List[Tuple[str, str, Dict[str, Any]]]) -> List[Tuple[Dict[str, int], Dict[str, int], Dict[str, Any]]]:
    transitions: List[Tuple[Dict[str, int], Dict[str, int], Dict[str, Any]]] = []
    seen = set()
    for left_key, right_key, edge in edges:
        left = parse_tile(left_key)
        right = parse_tile(right_key)
        if not left or not right:
            continue
        if left.get("height", 0) != right.get("height", 0):
            continue
        if not _is_short_object_transition(left, right, edge):
            continue
        signature = (tile_key(left), tile_key(right), _edge_meta(edge).get("route"))
        if signature in seen:
            continue
        seen.add(signature)
        transitions.append((left, right, edge))
    return transitions


def _object_transition_payload(edge: Dict[str, Any]) -> Dict[str, Any]:
    meta = dict(_edge_meta(edge))
    meta["objectTransition"] = True
    return {
        "source": OBJECT_TRANSITION_SOURCE,
        "cost": float(edge.get("cost") or 1.0),
        "meta": meta,
    }


def _cache_mesh_payload() -> Dict[str, Any]:
    return {
        "source": CACHE_MESH_SOURCE,
        "cost": 1.0,
        "meta": {},
    }


def _cache_mesh_waypoints(start_tile: Dict[str, int], target_tile: Dict[str, int],
                          transitions: List[Tuple[Dict[str, int], Dict[str, int], Dict[str, Any]]]) -> Tuple[List[Dict[str, int]], List[Dict[str, Any]]]:
    waypoints = [dict(start_tile)]
    edges: List[Dict[str, Any]] = []
    for left, right, edge in transitions:
        if tile_key(waypoints[-1]) != tile_key(left):
            waypoints.append(dict(left))
            edges.append(_cache_mesh_payload())
        if tile_key(waypoints[-1]) != tile_key(right):
            waypoints.append(dict(right))
            edges.append(_object_transition_payload(edge))
    if tile_key(waypoints[-1]) != tile_key(target_tile):
        waypoints.append(dict(target_tile))
        edges.append(_cache_mesh_payload())
    return waypoints, edges


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


def _step_completion_tile(step: Dict[str, Any]) -> Optional[Dict[str, int]]:
    if step.get("type") == "object_transition":
        return parse_tile(step.get("postTile")) or parse_tile(step.get("to")) or parse_tile(step)
    return parse_tile(step.get("to")) or parse_tile(step)


def _walk_route_step(tile: Dict[str, int]) -> Dict[str, Any]:
    normalized = {
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0) or 0),
    }
    return {
        "type": "walk",
        **normalized,
        "to": dict(normalized),
    }


def _transition_route_step(transition: Dict[str, Any], left: Dict[str, int], right: Dict[str, int]) -> Dict[str, Any]:
    payload = dict(transition or {})
    payload["type"] = "object_transition"
    payload.setdefault("preTile", dict(left))
    payload.setdefault("approachTile", dict(left))
    payload.setdefault("postTile", dict(right))
    payload.setdefault("to", dict(right))
    payload["x"] = int(right["x"])
    payload["y"] = int(right["y"])
    payload["height"] = int(right.get("height", 0) or 0)
    proof = dict(payload.get("transitionProof") or {})
    proof.setdefault("preTile", dict(left))
    proof.setdefault("objectTile", payload.get("objectTile"))
    proof.setdefault("postTile", dict(right))
    payload["transitionProof"] = {key: value for key, value in proof.items() if value not in (None, "", [], {})}
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}


def _edge_transition(edge: Dict[str, Any], left: Dict[str, int], right: Dict[str, int]) -> Optional[Dict[str, Any]]:
    meta = _edge_meta(edge)
    transition = meta.get("transition") if isinstance(meta.get("transition"), dict) else None
    if transition:
        pair = transition_pair(transition)
        direct = (tile_key(left), tile_key(right))
        if pair == direct:
            return transition
        reversed_payload = reverse_transition(transition)
        if transition_pair(reversed_payload or {}) == direct:
            return reversed_payload
        adjusted = dict(transition)
        adjusted["preTile"] = dict(left)
        adjusted["approachTile"] = dict(left)
        adjusted["postTile"] = dict(right)
        adjusted["to"] = dict(right)
        return adjusted
    if _is_short_object_transition(left, right, edge):
        return {
            "type": "object_transition",
            "routeId": meta.get("route"),
            "preTile": dict(left),
            "approachTile": dict(left),
            "postTile": dict(right),
            "to": dict(right),
            "option": "first",
            "transitionProof": {
                "preTile": dict(left),
                "postTile": dict(right),
            },
        }
    return None


def _transition_map_from_edges(edges: List[Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    transitions: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in edges or []:
        if isinstance(item, tuple) and len(item) == 3:
            left = parse_tile(item[0])
            right = parse_tile(item[1])
            edge = item[2]
        else:
            edge = item
            meta = _edge_meta(edge) if isinstance(edge, dict) else {}
            transition = meta.get("transition") if isinstance(meta.get("transition"), dict) else None
            left = parse_tile((transition or {}).get("preTile"))
            right = parse_tile((transition or {}).get("postTile"))
        if not isinstance(edge, dict) or not left or not right:
            continue
        transition = _edge_transition(edge, left, right)
        if transition:
            transitions[(tile_key(left), tile_key(right))] = transition
    return transitions


def _append_walk_route_steps(output: List[Dict[str, Any]], tiles: List[Dict[str, int]], max_gap: int) -> None:
    if not tiles:
        return
    for tile in _route_steps(tiles, max_gap):
        if output and tile_key(_step_completion_tile(output[-1])) == tile_key(tile):
            continue
        output.append(_walk_route_step(tile))


def _typed_route_steps_from_path(path: List[Dict[str, int]], edges: List[Any], max_gap: int) -> List[Dict[str, Any]]:
    transitions = _transition_map_from_edges(edges)
    if not transitions:
        return _route_steps(path, max_gap)
    typed_steps: List[Dict[str, Any]] = []
    segment: List[Dict[str, int]] = [path[0]] if path else []
    used_transition = False
    index = 0
    while index < len(path) - 1:
        left = path[index]
        right = path[index + 1]
        transition = transitions.get((tile_key(left), tile_key(right)))
        if transition:
            if not segment or tile_key(segment[-1]) != tile_key(left):
                segment.append(left)
            _append_walk_route_steps(typed_steps, segment, max_gap)
            typed_steps.append(_transition_route_step(transition, left, right))
            segment = [right]
            used_transition = True
        else:
            segment.append(right)
        index += 1
    _append_walk_route_steps(typed_steps, segment, max_gap)
    return typed_steps if used_transition else _route_steps(path, max_gap)


def _edges_preserve_route_shape(edges: List[Tuple[str, str, Dict[str, Any]]]) -> bool:
    for _left, _right, edge in edges:
        meta = edge.get("meta", {}) if isinstance(edge, dict) else {}
        if bool(meta.get("preserveShape")):
            return True
    return False


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
        optimize_shortcuts=(
            not bool(getattr(args, "no_shortcut_optimize", False))
            and not _edges_preserve_route_shape(edges)
        ),
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
    route_steps = _typed_route_steps_from_path(path, edges, int(getattr(args, "route_step_gap", 10)))
    base["routeSteps"] = route_steps
    base["routeStepCount"] = len(route_steps)
    if not expanded.get("success"):
        message = "Route was rejected because cache collision could not expand every walk segment safely."
        base["status"] = "invalid-route-geometry"
        base["error"] = message
        base["message"] = message
        base["quality"] = "bad"
        base["next"] = None
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


def _cache_direct_candidate(model: Dict[str, Any], db: Dict[str, Any], navdb: Any, route_eval: Any,
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
        tile_penalty=_direct_tile_penalty(
            hazard_records,
            learned_penalty=_learned_exposure_tile_penalty(model, int(start_tile.get("height", 0))),
        ),
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
    learned_exposure = _path_learned_exposure(model, path)
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
    if learned_exposure:
        candidate["learnedExposure"] = learned_exposure
    attach_run_plan(candidate, db, navdb, args)
    return candidate


def _cache_mesh_candidate(model: Dict[str, Any], db: Dict[str, Any], navdb: Any, route_eval: Any,
                          start_tile: Dict[str, int], start_label: str, target: Dict[str, Any],
                          learned_edges: List[Tuple[str, str, Dict[str, Any]]],
                          args: SimpleNamespace) -> Optional[Dict[str, Any]]:
    if bool(getattr(args, "no_cache_collision", False)) or bool(getattr(args, "no_cache_mesh", False)):
        return None
    target_tile = target["tile"]
    if start_tile.get("height", 0) != target_tile.get("height", 0):
        return None
    transitions = _transition_edges_from_learned_path(learned_edges)
    if not transitions:
        return None
    waypoints, waypoint_edges = _cache_mesh_waypoints(start_tile, target_tile, transitions)
    expanded = expand_route_path(
        waypoints,
        edges=waypoint_edges,
        padding=int(getattr(args, "collision_padding_tiles", 64)),
        max_expansions_per_segment=int(getattr(args, "collision_max_expansions", 250000)),
        final_arrival_radius=int(target.get("arrivalRadius", 1)),
        waypoint_arrival_radius=0,
        optimize_shortcuts=not bool(getattr(args, "no_shortcut_optimize", False)),
        shortcut_max_span=int(getattr(args, "shortcut_max_span", 128)),
        shortcut_min_savings=int(getattr(args, "shortcut_min_savings", 4)),
        shortcut_corridor_radius=int(getattr(args, "shortcut_corridor_radius", 18)),
    )
    path = expanded.get("tiles") or []
    transition_count = int(expanded.get("skippedObjectTransitions") or 0)
    if not path:
        return {
            "planner": "fast",
            "mode": "cache_mesh",
            "status": "error",
            "quality": "bad",
            "error": "cache mesh did not produce a path",
            "transitionCount": len(transitions),
        }
    if not expanded.get("success"):
        return {
            "planner": "fast",
            "mode": "cache_mesh",
            "status": "error",
            "quality": "bad",
            "error": "cache mesh could not expand every walkable segment",
            "collisionFailures": expanded.get("failures") or [],
            "transitionCount": len(transitions),
        }
    target_radius = int(target.get("arrivalRadius", 1))
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
    learned_exposure = _path_learned_exposure(model, path)
    route_steps = _typed_route_steps_from_path(path, waypoint_edges, int(getattr(args, "route_step_gap", 10)))
    transition_routes: Dict[str, int] = {}
    for _left, _right, edge in transitions:
        route_id = _edge_meta(edge).get("route")
        if route_id:
            transition_routes[str(route_id)] = transition_routes.get(str(route_id), 0) + 1
    candidate = {
        "planner": "fast",
        "mode": "cache_mesh",
        "status": "ok" if distance(path[-1], target_tile) <= target_radius else "no-learned-route",
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
            "preShortcutDistance": expanded.get("preShortcutDistance"),
            "shortcutSavings": expanded.get("shortcutSavings"),
            "shortcutCount": expanded.get("shortcutCount"),
            "segmentsExpanded": expanded.get("segmentsExpanded"),
            "skippedObjectTransitions": transition_count,
            "gridStats": (expanded.get("grid") or {}).get("stats", {}),
            "bounds": (expanded.get("grid") or {}).get("bounds"),
        },
        "estimatedTicks": round(float(route_distance), 1),
        "detourRatio": round(float(route_distance) / max(1.0, float(direct_distance)), 3),
        "targetDistanceIncreases": target_distance_increases,
        "wrongWayFlags": wrong_way,
        "detourSegments": detours,
        "edgeSources": {
            CACHE_MESH_SOURCE: max(0, len(path) - 1 - transition_count),
            OBJECT_TRANSITION_SOURCE: transition_count,
        },
        "routesUsed": transition_routes,
        "hazardWarnings": hazard_warnings[:int(getattr(args, "max_warnings", 8))],
        "transitionCount": transition_count,
    }
    if learned_exposure:
        candidate["learnedExposure"] = learned_exposure
    if expanded.get("warnings"):
        candidate["collisionWarnings"] = expanded["warnings"][:int(getattr(args, "max_warnings", 8))]
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
        "routeStepCount", "endTile", "next", "runPlan", "transitionCount", "routesUsed",
        "learnedExposure",
    ]
    return {key: candidate[key] for key in keep if key in candidate and candidate[key] not in (None, [], {})}


def _maybe_select_cache_mesh(base: Dict[str, Any], mesh: Optional[Dict[str, Any]],
                             args: SimpleNamespace) -> Dict[str, Any]:
    if not mesh:
        return base
    base["cacheMeshCandidate"] = _compact_direct_candidate(mesh)
    if mesh.get("status") != "ok":
        return base
    if mesh.get("hazardWarnings") and not base.get("hazardWarnings") and not bool(getattr(args, "allow_lethal", False)):
        return base
    base_distance = float(base.get("routeDistance") or math.inf)
    mesh_distance = float(mesh.get("routeDistance") or math.inf)
    savings = base_distance - mesh_distance
    min_savings = float(getattr(args, "direct_candidate_min_savings", 24))
    mesh_rank = _quality_rank(mesh.get("quality"))
    base_rank = _quality_rank(base.get("quality"))
    base_incomplete = base.get("status") != "ok"
    large_detour = float(base.get("detourRatio") or 1.0) >= float(getattr(args, "direct_candidate_min_detour", 1.22))
    safe_enough = mesh_rank <= base_rank + 1
    if base_incomplete or (safe_enough and (savings >= min_savings or (large_detour and savings > 0))):
        selected = dict(mesh)
        selected["selectedOverLearned"] = {
            "previousStatus": base.get("status"),
            "previousQuality": base.get("quality"),
            "previousRouteDistance": base.get("routeDistance"),
            "savedTiles": int(savings) if math.isfinite(savings) else None,
            "reason": (
                "learned route geometry was incomplete; cache mesh rebuilt every walkable leg and kept only required object transitions"
                if base_incomplete else
                "cache mesh rebuilt walkable legs from cache collision and kept only required object transitions from the learned path"
            ),
        }
        selected["learnedCandidate"] = _compact_direct_candidate(base)
        return selected
    return base


def _should_try_cache_direct(base: Dict[str, Any], args: SimpleNamespace) -> bool:
    if bool(getattr(args, "no_cache_direct", False)):
        return False
    if base.get("preserveShape") and base.get("status") == "ok":
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
    if base.get("preserveShape") and base.get("status") == "ok":
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
    transition_block = (
        coordinate_layer_transition_block(start_tile, target["tile"])
        or cache_area_transition_block(start_tile, target["tile"])
    )
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

    graph = _build_graph(model, db, navdb, args, area_filter=_route_area_filter(start_tile, target["tile"]))
    rejected_model_edges = graph.get("rejectedModelEdges") or []
    if rejected_model_edges:
        base["modelIntegrity"] = {
            "valid": False,
            "rejectedEdgeCount": len(rejected_model_edges),
            "firstRejectedEdge": rejected_model_edges[0],
        }
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
            direct = _cache_direct_candidate(model, db, navdb, route_eval, start_tile, start_label, target, args)
            base = _maybe_select_cache_direct(base, direct, args)
        attach_run_plan(base, db, navdb, args)
        return base

    keys, edges = _reconstruct(previous, end_key)
    tiles = [graph["nodes"][key] for key in keys]
    source_counts, route_counts = _source_summary(edges)
    preserve_shape = _edges_preserve_route_shape(edges)
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
        "preserveShape": preserve_shape,
        "hazardWarnings": warnings[:args.max_warnings],
    })
    _apply_cache_collision(
        base, route_eval, tiles, edges, target["tile"], args,
        arrival_radius=int(target.get("arrivalRadius", 1)),
    )
    mesh = _cache_mesh_candidate(model, db, navdb, route_eval, start_tile, start_label, target, edges, args)
    base = _maybe_select_cache_mesh(base, mesh, args)
    if _should_try_cache_direct(base, args):
        direct = _cache_direct_candidate(model, db, navdb, route_eval, start_tile, start_label, target, args)
        base = _maybe_select_cache_direct(base, direct, args)
    attach_run_plan(base, db, navdb, args)
    return base
