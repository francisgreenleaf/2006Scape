"""Verified object-transition catalog for ML2 route planning."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from .common import parse_tile, tile_key


TRANSITION_STEP_TYPES = {
    "interact_object",
    "object_transition",
    "door_transition",
    "gate_transition",
    "stair_transition",
    "floor_transition",
    "trapdoor_transition",
    "ladder_transition",
    "rope_transition",
}

TRANSITION_NAME_WORDS = (
    "door",
    "gate",
    "trapdoor",
    "ladder",
    "stair",
    "rope",
)


def normalize_tile(value: Any) -> Optional[Dict[str, int]]:
    return parse_tile(value)


def _compact_tile(tile: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]:
    if not tile:
        return None
    return {
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0) or 0),
    }


def is_transition_step(step: Dict[str, Any]) -> bool:
    step_type = str(step.get("type") or "")
    if step_type in TRANSITION_STEP_TYPES:
        return True
    name = str(step.get("objectName") or "").strip().lower()
    return any(word in name for word in TRANSITION_NAME_WORDS)


def _default_option(step: Dict[str, Any]) -> str:
    option = str(step.get("option") or step.get("objectOption") or "").strip().lower()
    if option:
        return option
    name = str(step.get("objectName") or "").strip().lower()
    step_type = str(step.get("type") or "").strip().lower()
    if any(word in name or word in step_type for word in ("door", "gate", "trapdoor")):
        return "open"
    return "first"


def transition_from_step(route: Dict[str, Any], step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(step, dict) or not is_transition_step(step):
        return None
    proof = step.get("transitionProof") if isinstance(step.get("transitionProof"), dict) else {}
    pre_tile = (
        normalize_tile(step.get("preTile"))
        or normalize_tile(step.get("approachTile"))
        or normalize_tile(proof.get("preTile"))
        or normalize_tile(proof.get("approachTile"))
    )
    object_tile = (
        normalize_tile(step.get("objectTile"))
        or normalize_tile(proof.get("objectTile"))
        or normalize_tile(step.get("to"))
        or normalize_tile(step)
    )
    post_tile = (
        normalize_tile(step.get("postTile"))
        or normalize_tile(proof.get("postTile"))
        or normalize_tile(step.get("destinationTile"))
    )
    post_condition = step.get("postCondition") or proof.get("postCondition")
    if not pre_tile or not object_tile:
        return None
    if not post_tile and not post_condition:
        return None

    object_id = step.get("objectId", step.get("id"))
    try:
        object_id = int(object_id)
    except (TypeError, ValueError):
        object_id = None

    walk_steps = []
    for value in (step.get("walkSteps") or step.get("crossingSteps") or []):
        tile = normalize_tile(value)
        if tile:
            walk_steps.append(tile)

    payload = {
        "type": "object_transition",
        "routeId": route.get("id"),
        "routeName": route.get("name"),
        "sourceRouteStatus": route.get("status"),
        "objectId": object_id,
        "objectName": step.get("objectName") or step.get("name") or "",
        "objectTile": _compact_tile(object_tile),
        "preTile": _compact_tile(pre_tile),
        "approachTile": _compact_tile(normalize_tile(step.get("approachTile")) or pre_tile),
        "postTile": _compact_tile(post_tile),
        "postCondition": post_condition,
        "option": _default_option(step),
        "walkSteps": walk_steps,
        "transitionProof": {
            "preTile": _compact_tile(pre_tile),
            "objectTile": _compact_tile(object_tile),
        },
        "bidirectional": bool(route.get("bidirectional")),
    }
    if post_tile:
        payload["transitionProof"]["postTile"] = _compact_tile(post_tile)
        payload["x"] = int(post_tile["x"])
        payload["y"] = int(post_tile["y"])
        payload["height"] = int(post_tile.get("height", 0) or 0)
        payload["to"] = _compact_tile(post_tile)
    if post_condition:
        payload["transitionProof"]["postCondition"] = post_condition
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}


def reverse_transition(transition: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(transition, dict):
        return None
    pre_tile = normalize_tile(transition.get("preTile"))
    post_tile = normalize_tile(transition.get("postTile"))
    if not pre_tile or not post_tile:
        return dict(transition)
    reversed_payload = dict(transition)
    reversed_payload["preTile"] = _compact_tile(post_tile)
    reversed_payload["approachTile"] = _compact_tile(post_tile)
    reversed_payload["postTile"] = _compact_tile(pre_tile)
    reversed_payload["to"] = _compact_tile(pre_tile)
    reversed_payload["x"] = int(pre_tile["x"])
    reversed_payload["y"] = int(pre_tile["y"])
    reversed_payload["height"] = int(pre_tile.get("height", 0) or 0)
    proof = dict(reversed_payload.get("transitionProof") or {})
    proof["preTile"] = _compact_tile(post_tile)
    proof["objectTile"] = _compact_tile(normalize_tile(transition.get("objectTile")))
    proof["postTile"] = _compact_tile(pre_tile)
    reversed_payload["transitionProof"] = {key: value for key, value in proof.items() if value not in (None, "", [], {})}
    if transition.get("option"):
        reversed_payload["option"] = transition["option"]
    return reversed_payload


def transition_catalog(db: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for route in db.get("routes", []):
        for step in route.get("steps", []):
            transition = transition_from_step(route, step)
            if transition:
                records.append(transition)
    return records


def transition_pair(transition: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    pre = normalize_tile(transition.get("preTile"))
    post = normalize_tile(transition.get("postTile"))
    if not pre or not post:
        return None
    return tile_key(pre), tile_key(post)


def transition_step_target(step: Dict[str, Any]) -> Optional[Dict[str, int]]:
    if not isinstance(step, dict):
        return None
    if is_transition_step(step):
        return normalize_tile(step.get("postTile")) or normalize_tile((step.get("transitionProof") or {}).get("postTile"))
    return normalize_tile(step.get("to")) or normalize_tile(step.get("near")) or normalize_tile(step)


def route_known_transition_pairs(catalog: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    pairs: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for transition in catalog:
        pair = transition_pair(transition)
        if not pair:
            continue
        pairs[pair] = transition
        if transition.get("bidirectional"):
            reversed_payload = reverse_transition(transition)
            reversed_pair = transition_pair(reversed_payload or {})
            if reversed_pair:
                pairs[reversed_pair] = reversed_payload or transition
    return pairs
