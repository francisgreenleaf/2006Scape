"""Validation helpers for ML2 mixed route definitions."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .common import parse_tile, tile_key
from .transition_catalog import (
    route_known_transition_pairs,
    transition_catalog,
    transition_step_target,
)


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
    return transition_step_warnings(steps) + known_transition_plain_walk_warnings(steps, catalog)


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
