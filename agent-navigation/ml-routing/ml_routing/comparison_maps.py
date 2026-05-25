"""Before/after route comparison maps for ML routing benchmarks."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .benchmark import DEFAULT_CASES
from .collision import expand_route_path
from .common import distance, tile_key, utcnow, write_json
from .fast_planner import attach_run_plan, fast_route
from .model import load_model
from .paths import ARTIFACT_ROOT, ensure_artifact_dirs, ensure_tool_imports, timestamp_id


OLD_COLOR = (225, 67, 57)
NEW_COLOR = (45, 203, 227)
RUN_COLOR = (255, 222, 64)
RUN_EDGE_COLOR = (25, 29, 34)
START_COLOR = (74, 221, 132)
END_COLOR = (255, 222, 92)
FRONTIER_COLOR = (159, 111, 240)
INK = (22, 27, 33)
PAPER = (245, 239, 219)
WHITE = (255, 255, 255)
BASE_MAP_SOURCE = "cache_world_map+render_context_map"


def _load_render_modules():
    ensure_tool_imports()
    import cache_world_map  # type: ignore
    import navdb  # type: ignore
    import route_eval  # type: ignore
    import render_context_map  # type: ignore
    from render_navigation_png import Canvas  # type: ignore

    return cache_world_map, navdb, route_eval, render_context_map, Canvas


def _route_args(base: SimpleNamespace, case: Dict[str, Any], planner: str) -> SimpleNamespace:
    values = vars(base).copy()
    values["from_tile"] = case["from"]
    values["to"] = case["to"]
    values["planner"] = planner
    values.setdefault("allow_lethal", False)
    values.setdefault("allow_failed_traces", False)
    values.setdefault("allow_failed_candidate", False)
    values.setdefault("include_partial", False)
    values.setdefault("include_derived", False)
    values.setdefault("include_unverified", False)
    values.setdefault("include_unscoped_traces", False)
    return SimpleNamespace(**values)


def _old_route(args: SimpleNamespace) -> Tuple[Dict[str, Any], float]:
    _cache_world_map, _navdb, route_eval, _render_context_map, _Canvas = _load_render_modules()
    start = time.perf_counter()
    result = route_eval.evaluate(args)
    elapsed = time.perf_counter() - start
    result["planner"] = "old_full"
    result["plannerSeconds"] = round(elapsed, 4)
    return result, elapsed


def _new_route(args: SimpleNamespace, model: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
    start = time.perf_counter()
    result = fast_route(args, model)
    elapsed = time.perf_counter() - start
    result["planner"] = "new_fast_ml"
    result["plannerSeconds"] = round(elapsed, 4)
    return result, elapsed


def _tiles_from_result(result: Dict[str, Any]) -> List[Dict[str, int]]:
    for key in ("collisionPath", "waypoints"):
        tiles = [tile for tile in result.get(key) or [] if isinstance(tile, dict)]
        if tiles:
            return tiles
    return []


def _expand_result_for_map(result: Dict[str, Any], args: SimpleNamespace) -> None:
    if result.get("collisionPath"):
        return
    waypoints = [tile for tile in result.get("waypoints") or [] if isinstance(tile, dict)]
    if len(waypoints) < 2:
        return
    target_tile = result.get("targetTile") if isinstance(result.get("targetTile"), dict) else {}
    arrival_radius = int(result.get("arrivalRadius") or 0)
    if target_tile and tile_key(waypoints[-1]) != tile_key(target_tile):
        arrival_radius = 0
    expanded = expand_route_path(
        waypoints,
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
    result["collision"] = {
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
    result["collisionPathDistance"] = expanded.get("distance")
    result["collisionExpanded"] = bool(expanded.get("success"))
    result["collisionWarnings"] = (expanded.get("warnings") or [])[:int(getattr(args, "max_warnings", 8))]
    if expanded.get("failures"):
        result["collisionFailures"] = expanded["failures"][:int(getattr(args, "max_warnings", 8))]
    if path:
        result["collisionPath"] = path
    if expanded.get("success"):
        result["macroRouteDistance"] = result.get("routeDistance")
        result["routeDistance"] = expanded.get("distance")


def _all_tiles(*paths: Iterable[Dict[str, int]]) -> List[Dict[str, int]]:
    tiles = []
    for path in paths:
        for tile in path:
            if isinstance(tile, dict) and "x" in tile and "y" in tile:
                tiles.append(tile)
    return tiles


def _bounds_for_tiles(tiles: List[Dict[str, int]], padding: int) -> Dict[str, int]:
    if not tiles:
        raise RuntimeError("no tiles to render")
    return {
        "minX": min(int(tile["x"]) for tile in tiles) - padding,
        "minY": min(int(tile["y"]) for tile in tiles) - padding,
        "maxX": max(int(tile["x"]) for tile in tiles) + padding,
        "maxY": max(int(tile["y"]) for tile in tiles) + padding,
        "height": int(tiles[0].get("height", 0)),
    }


def _projector(bounds: Dict[str, int], width: int, height: int, scale: int, header: int):
    def project(tile: Dict[str, int]) -> Tuple[int, int]:
        px = int((int(tile["x"]) - bounds["minX"]) * scale)
        py = header + int((bounds["maxY"] - int(tile["y"])) * scale)
        return px, py

    return project


def _draw_path(canvas: Any, project: Any, tiles: List[Dict[str, int]], color: Tuple[int, int, int],
               scale: int, width_factor: float = 0.9) -> int:
    if len(tiles) < 2:
        return 0
    drawn = 0
    width = max(2, int(round(scale * width_factor)))
    for left, right in zip(tiles, tiles[1:]):
        if left.get("height", 0) != right.get("height", 0):
            continue
        x0, y0 = project(left)
        x1, y1 = project(right)
        canvas.line(x0, y0, x1, y1, color, width=width)
        drawn += 1
    return drawn


def _draw_run_segments(canvas: Any, project: Any, tiles: List[Dict[str, int]],
                       run_segments: List[Dict[str, Any]], scale: int,
                       width_factor: float = 0.45) -> int:
    if len(tiles) < 2 or not run_segments:
        return 0
    drawn = 0
    edge_width = max(3, int(round(scale * (width_factor + 0.5))))
    fill_width = max(2, int(round(scale * width_factor)))
    for segment in run_segments:
        start = max(0, int(segment.get("startIndex") or 0))
        end = min(len(tiles) - 1, int(segment.get("endIndex") or start))
        if end <= start:
            continue
        for index in range(start, end):
            left = tiles[index]
            right = tiles[index + 1]
            if left.get("height", 0) != right.get("height", 0):
                continue
            x0, y0 = project(left)
            x1, y1 = project(right)
            canvas.line(x0, y0, x1, y1, RUN_EDGE_COLOR, width=edge_width)
            canvas.line(x0, y0, x1, y1, RUN_COLOR, width=fill_width)
            drawn += 1
    return drawn


def _draw_marker(canvas: Any, project: Any, tile: Optional[Dict[str, int]], color: Tuple[int, int, int], scale: int) -> None:
    if not tile:
        return
    x, y = project(tile)
    radius = max(4, int(round(scale * 1.2)))
    canvas.circle(x, y, radius + 2, INK)
    canvas.circle(x, y, radius, color)


def _draw_text(canvas: Any, x: int, y: int, text: str, color: Tuple[int, int, int] = INK, scale: int = 1) -> None:
    safe = "".join(ch if ch.isalnum() or ch in " .,:/-+%<>=_" else " " for ch in str(text))
    canvas.text(x, y, safe, color, scale=scale)


def _pct(old: Optional[float], new: Optional[float]) -> Optional[float]:
    if old is None or new is None or old <= 0:
        return None
    return round(((old - new) / old) * 100.0, 1)


def _metric_delta(old: Dict[str, Any], new: Dict[str, Any], old_seconds: float, new_seconds: float) -> Dict[str, Any]:
    old_tiles = old.get("routeDistance")
    new_tiles = new.get("routeDistance")
    old_ticks = old.get("estimatedTicks")
    new_ticks = new.get("estimatedTicks")
    return {
        "oldStatus": old.get("status"),
        "newStatus": new.get("status"),
        "oldQuality": old.get("quality"),
        "newQuality": new.get("quality"),
        "oldRouteDistance": old_tiles,
        "newRouteDistance": new_tiles,
        "tileDelta": (old_tiles - new_tiles) if isinstance(old_tiles, (int, float)) and isinstance(new_tiles, (int, float)) else None,
        "tileImprovementPct": _pct(old_tiles, new_tiles) if isinstance(old_tiles, (int, float)) and isinstance(new_tiles, (int, float)) else None,
        "oldEstimatedTicks": old_ticks,
        "newEstimatedTicks": new_ticks,
        "tickDelta": round(old_ticks - new_ticks, 1) if isinstance(old_ticks, (int, float)) and isinstance(new_ticks, (int, float)) else None,
        "tickImprovementPct": _pct(old_ticks, new_ticks) if isinstance(old_ticks, (int, float)) and isinstance(new_ticks, (int, float)) else None,
        "oldPlannerSeconds": round(old_seconds, 4),
        "newPlannerSeconds": round(new_seconds, 4),
        "plannerSpeedup": round(old_seconds / new_seconds, 1) if new_seconds > 0 else None,
        "frontierDistanceToTarget": new.get("frontierDistanceToTarget"),
    }


def _base_map_summary(world_map: Dict[str, Any], context_layers: Dict[str, Any], include_markers: bool = False) -> Dict[str, Any]:
    summary = {
        "source": BASE_MAP_SOURCE,
        "tiles": len(world_map.get("tiles", [])),
        "objects": len(world_map.get("objects", [])),
        "regions": world_map.get("regions", []),
        "mapFunctionMarkerCount": context_layers["mapFunctionMarkerCount"],
        "mapFunctionIconsDrawn": context_layers["mapFunctionIconsDrawn"],
        "placeMarkerCount": len(context_layers["placeMarkers"]),
        "placeLabelsDrawn": context_layers["placeLabelsDrawn"],
    }
    if include_markers:
        summary["mapFunctionMarkers"] = context_layers["mapFunctionMarkers"]
        summary["placeMarkers"] = context_layers["placeMarkers"]
    return summary


def render_case(case: Dict[str, Any], base_args: SimpleNamespace, model: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    cache_world_map, navdb, _route_eval, render_context_map, Canvas = _load_render_modules()
    old_args = _route_args(base_args, case, "full")
    new_args = _route_args(base_args, case, "fast")
    old, old_seconds = _old_route(old_args)
    new, new_seconds = _new_route(new_args, model)
    db = navdb.load_db()
    start_tile, _label = _resolve_start(db, navdb, case["from"])
    target = navdb.place_or_tile_target(db, case["to"])
    target_tile = target["tile"] if target else None
    if target:
        old["arrivalRadius"] = int(target.get("arrivalRadius", 1))
        new["arrivalRadius"] = int(target.get("arrivalRadius", 1))
    _expand_result_for_map(old, base_args)
    _expand_result_for_map(new, base_args)
    attach_run_plan(old, db, navdb, base_args)
    attach_run_plan(new, db, navdb, base_args)
    old_tiles = _tiles_from_result(old)
    new_tiles = _tiles_from_result(new)
    frontier = new.get("frontierTile") if isinstance(new.get("frontierTile"), dict) else None
    tiles = _all_tiles(old_tiles, new_tiles, [start_tile], [target_tile] if target_tile else [], [frontier] if frontier else [])
    bounds = _bounds_for_tiles(tiles, int(base_args.padding_tiles))
    scale = int(base_args.pixels_per_tile)
    header = int(base_args.header_pixels)
    world_map = cache_world_map.load_cache_world_map(bounds, plane=int(bounds.get("height", 0)))
    bounds = dict(world_map["bounds"])
    bounds["height"] = int(start_tile.get("height", 0))
    span_x = bounds["maxX"] - bounds["minX"] + 1
    span_y = bounds["maxY"] - bounds["minY"] + 1
    width = span_x * scale + 1
    height = span_y * scale + 1 + header
    canvas = Canvas(width, height, PAPER)
    canvas.rect(0, 0, width - 1, header - 1, (238, 233, 218))
    project = _projector(bounds, width, height, scale, header)
    cache_world_map.draw_world_map(canvas, world_map, project, scale)
    context_layers = render_context_map.draw_static_context_layers(
        canvas,
        project,
        world_map,
        db,
        bounds,
        scale,
        mapfunction_icons=getattr(base_args, "mapfunction_icons", True),
        mapfunction_labels=getattr(base_args, "mapfunction_labels", False),
        place_markers=getattr(base_args, "place_markers", True),
        place_labels=getattr(base_args, "place_labels", True),
        max_place_markers=int(getattr(base_args, "max_place_markers", 80)),
    )
    old_edges = _draw_path(canvas, project, old_tiles, OLD_COLOR, scale, width_factor=1.0)
    new_edges = _draw_path(canvas, project, new_tiles, NEW_COLOR, scale, width_factor=0.55)
    old_run_edges = _draw_run_segments(canvas, project, old_tiles, old.get("runSegments") or [], scale, width_factor=0.55)
    new_run_edges = _draw_run_segments(canvas, project, new_tiles, new.get("runSegments") or [], scale, width_factor=0.35)
    _draw_marker(canvas, project, start_tile, START_COLOR, scale)
    _draw_marker(canvas, project, target_tile, END_COLOR, scale)
    _draw_marker(canvas, project, frontier, FRONTIER_COLOR, scale)
    metrics = _metric_delta(old, new, old_seconds, new_seconds)
    title = "{}  OLD RED  NEW CYAN  RUN YELLOW".format(case["name"].replace("_", " ").upper())
    _draw_text(canvas, 10, 10, title, INK, scale=2 if width > 780 else 1)
    metric_line = "TILES {} -> {}  DELTA {}  PLAN {:.3F}s -> {:.3F}s".format(
        metrics.get("oldRouteDistance"),
        metrics.get("newRouteDistance"),
        metrics.get("tileDelta"),
        metrics["oldPlannerSeconds"],
        metrics["newPlannerSeconds"],
    )
    _draw_text(canvas, 10, 34 if width > 780 else 24, metric_line, INK, scale=1)
    if new.get("status") == "no-learned-route":
        _draw_text(canvas, 10, 48 if width > 780 else 38, "NEW IS SAFE FRONTIER/PROBE, NOT COMPLETE DESTINATION", (101, 65, 184), scale=1)
    output = output_dir / "{}.png".format(case["name"])
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save_png(output)
    summary = {
        "case": case,
        "output": str(output),
        "detail": str(output.with_suffix(".json")),
        "bounds": {key: bounds[key] for key in ("minX", "minY", "maxX", "maxY")},
        "pixelsPerTile": scale,
        "baseMap": _base_map_summary(world_map, context_layers, include_markers=True),
        "old": _compact_route(old, old_edges, include_steps=True),
        "new": _compact_route(new, new_edges, include_steps=True),
        "metrics": metrics,
    }
    summary["old"]["runEdgesDrawn"] = old_run_edges
    summary["new"]["runEdgesDrawn"] = new_run_edges
    write_json(output.with_suffix(".json"), summary)
    compact_summary = dict(summary)
    compact_summary["baseMap"] = _base_map_summary(world_map, context_layers, include_markers=False)
    compact_summary["old"] = _compact_route(old, old_edges, include_steps=False)
    compact_summary["new"] = _compact_route(new, new_edges, include_steps=False)
    compact_summary["old"]["runEdgesDrawn"] = old_run_edges
    compact_summary["new"]["runEdgesDrawn"] = new_run_edges
    return compact_summary


def _resolve_start(db: Dict[str, Any], navdb: Any, value: str) -> Tuple[Dict[str, int], str]:
    if "," in value:
        tile = navdb.tile_from_arg(value)
        return tile, tile_key(tile)
    place = navdb.find_place(db, value)
    if not place:
        raise RuntimeError("unknown start: {}".format(value))
    return place["tile"], place["id"]


def _compact_route(route: Dict[str, Any], edges_drawn: int, include_steps: bool = False) -> Dict[str, Any]:
    compact = {
        "planner": route.get("planner"),
        "mode": route.get("mode"),
        "status": route.get("status"),
        "quality": route.get("quality"),
        "routeDistance": route.get("routeDistance"),
        "macroRouteDistance": route.get("macroRouteDistance"),
        "collisionPathDistance": route.get("collisionPathDistance"),
        "collisionExpanded": route.get("collisionExpanded"),
        "collisionFailures": len(route.get("collisionFailures") or []),
        "estimatedTicks": route.get("estimatedTicks"),
        "plannerSeconds": route.get("plannerSeconds"),
        "edgeSources": route.get("edgeSources"),
        "targetDistanceIncreases": route.get("targetDistanceIncreases"),
        "frontierTile": route.get("frontierTile"),
        "frontierDistanceToTarget": route.get("frontierDistanceToTarget"),
        "selectedOverLearned": route.get("selectedOverLearned"),
        "directCandidate": route.get("directCandidate"),
        "runPlan": route.get("runPlan"),
        "runSegments": (route.get("runSegments") or []) if include_steps else (route.get("runSegments") or [])[:8],
        "waypointCount": len(route.get("waypoints") or []),
        "edgesDrawn": edges_drawn,
    }
    route_steps = route.get("routeSteps") or []
    if route_steps:
        compact["routeStepCount"] = len(route_steps)
        compact["routeStepsPreview"] = route_steps[:5]
        if len(route_steps) > 5:
            compact["routeStepsPreview"].append(route_steps[-1])
        if include_steps:
            compact["routeSteps"] = route_steps
    return compact


def run_comparison_maps(args: SimpleNamespace) -> Dict[str, Any]:
    ensure_artifact_dirs()
    model = load_model(args.model)
    if not model:
        raise SystemExit("no trained model found; run route_ml.py export && route_ml.py train first")
    now = utcnow()
    run_id = args.run_id or timestamp_id(now)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else ARTIFACT_ROOT / "comparisons" / run_id
    cases = DEFAULT_CASES
    if args.case:
        wanted = set(args.case)
        cases = [case for case in cases if case["name"] in wanted or case["to"] in wanted or case["from"] in wanted]
    if args.limit:
        cases = cases[:args.limit]
    summaries = [render_case(case, args, model, output_dir) for case in cases]
    report = {
        "schemaVersion": 1,
        "runId": run_id,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "outputDir": str(output_dir),
        "modelId": model.get("modelId"),
        "caseCount": len(summaries),
        "cases": summaries,
    }
    write_json(output_dir / "comparison-report.json", report)
    write_json(ARTIFACT_ROOT / "comparisons" / "latest.json", report)
    return report
