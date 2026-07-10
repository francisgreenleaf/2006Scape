"""Validation helpers for ML2 mixed route definitions."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List

from .common import distance, parse_tile, tile_key
from .transition_catalog import (
    route_known_transition_pairs,
    transition_catalog,
    transition_step_target,
)


MAX_UNTYPED_WALK_DISTANCE = 64


def _is_object_transition_step(step: Dict[str, Any]) -> bool:
    return str(step.get("type") or "").lower() == "object_transition"


def _step_tile(step: Dict[str, Any]) -> Dict[str, int] | None:
    if _is_object_transition_step(step):
        return parse_tile(step.get("postTile")) or parse_tile(step.get("to")) or parse_tile(step)
    return transition_step_target(step)


def transition_step_warnings(route_steps: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    warnings = []
    for index, step in enumerate(route_steps):
        if not isinstance(step, dict) or not _is_object_transition_step(step):
            continue
        missing = []
        if step.get("objectId") is None:
            missing.append("objectId")
        if not parse_tile(step.get("objectTile")):
            missing.append("objectTile")
        if not (parse_tile(step.get("preTile")) or parse_tile(step.get("approachTile"))):
            missing.append("preTile")
        if not (
            parse_tile(step.get("postTile"))
            or step.get("postCondition")
            or (step.get("transitionProof") or {}).get("postCondition")
        ):
            missing.append("postTile_or_postCondition")
        if missing:
            warnings.append({
                "type": "object_transition_missing_fields",
                "index": index,
                "missing": missing,
                "step": step,
            })
    return warnings


def known_transition_plain_walk_warnings(route_steps: Iterable[Dict[str, Any]], catalog: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pairs = route_known_transition_pairs(catalog)
    warnings = []
    previous_tile = None
    previous_was_transition = False
    for index, step in enumerate(route_steps):
        if not isinstance(step, dict):
            continue
        current_tile = _step_tile(step)
        if not current_tile:
            continue
        current_is_transition = _is_object_transition_step(step)
        if previous_tile and not previous_was_transition and not current_is_transition:
            transition = pairs.get((tile_key(previous_tile), tile_key(current_tile)))
            if transition:
                warnings.append({
                    "type": "known_transition_as_plain_walk",
                    "index": index,
                    "from": previous_tile,
                    "to": current_tile,
                    "objectId": transition.get("objectId"),
                    "objectName": transition.get("objectName"),
                    "objectTile": transition.get("objectTile"),
                    "routeId": transition.get("routeId"),
                })
        previous_tile = current_tile
        previous_was_transition = current_is_transition
    return warnings


def validate_route_steps(route_steps: Iterable[Dict[str, Any]], catalog: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    steps = list(route_steps)
    return (
        transition_step_warnings(steps)
        + route_geometry_warnings(steps)
        + known_transition_plain_walk_warnings(steps, catalog)
    )


def walk_edge_warning(left: Dict[str, int], right: Dict[str, int], index: int | None = None,
                      max_distance: int = MAX_UNTYPED_WALK_DISTANCE) -> Dict[str, Any] | None:
    gap = distance(left, right)
    if math.isfinite(gap) and gap <= max_distance:
        return None
    warning = {
        "type": "untyped_route_discontinuity",
        "from": left,
        "to": right,
        "distance": int(gap) if math.isfinite(gap) else None,
        "planeChange": left.get("height", 0) != right.get("height", 0),
        "maxWalkDistance": int(max_distance),
    }
    if index is not None:
        warning["index"] = index
    return warning


def route_geometry_warnings(route_steps: Iterable[Dict[str, Any]],
                            max_distance: int = MAX_UNTYPED_WALK_DISTANCE) -> List[Dict[str, Any]]:
    warnings = []
    previous = None
    for index, step in enumerate(route_steps):
        if not isinstance(step, dict):
            continue
        if _is_object_transition_step(step):
            approach = parse_tile(step.get("preTile")) or parse_tile(step.get("approachTile"))
            if previous and approach:
                warning = walk_edge_warning(previous, approach, index=index, max_distance=max_distance)
                if warning:
                    warning["segment"] = "transition_approach"
                    warnings.append(warning)
            previous = _step_tile(step)
            continue
        current = _step_tile(step)
        if previous and current:
            warning = walk_edge_warning(previous, current, index=index, max_distance=max_distance)
            if warning:
                warning["segment"] = "walk"
                warnings.append(warning)
        if current:
            previous = current
    return warnings


def route_geometry_summary(route_steps: Iterable[Dict[str, Any]],
                           max_distance: int = MAX_UNTYPED_WALK_DISTANCE) -> Dict[str, Any]:
    steps = list(route_steps)
    warnings = transition_step_warnings(steps) + route_geometry_warnings(steps, max_distance=max_distance)
    discontinuities = [item for item in warnings if item.get("type") == "untyped_route_discontinuity"]
    largest = None
    if discontinuities:
        largest = max(discontinuities, key=lambda item: int(item.get("distance") or 1000000000))
    return {
        "valid": bool(steps) and not warnings,
        "checkedStepCount": len(steps),
        "maxUntypedWalkDistance": int(max_distance),
        "warningCount": len(warnings),
        "largestDiscontinuity": largest,
        "warnings": warnings[:8],
    }


def model_edge_warnings(model: Dict[str, Any],
                        max_distance: int = MAX_UNTYPED_WALK_DISTANCE) -> List[Dict[str, Any]]:
    warnings = []
    for key in (model.get("edgeStats") or {}):
        if ">" not in key:
            warnings.append({"type": "invalid_model_edge_key", "edge": key})
            continue
        left_key, right_key = key.split(">", 1)
        left = parse_tile(left_key)
        right = parse_tile(right_key)
        if not left or not right:
            warnings.append({"type": "invalid_model_edge_key", "edge": key})
            continue
        warning = walk_edge_warning(left, right, max_distance=max_distance)
        if warning:
            warning["edge"] = key
            warnings.append(warning)
    return warnings


def validate_db(db: Dict[str, Any]) -> Dict[str, Any]:
    catalog = transition_catalog(db)
    route_warnings = []
    for route in db.get("routes", []):
        steps = route.get("steps") or []
        warnings = transition_step_warnings(steps)
        if warnings:
            route_warnings.append({
                "routeId": route.get("id"),
                "warnings": warnings,
            })
    return {
        "schemaVersion": 1,
        "transitionCatalogCount": len(catalog),
        "routeWarningCount": sum(len(item["warnings"]) for item in route_warnings),
        "routeWarnings": route_warnings,
    }
