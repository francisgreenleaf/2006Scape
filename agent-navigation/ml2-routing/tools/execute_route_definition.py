#!/usr/bin/env python3
"""Execute an ML2 mixed route definition through bridge walking/object primitives."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

NAV_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = NAV_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import bridge_script as bridge
from profile_utils import resolve_profile, run_evidence_path
from usage_log import log_usage


DEFAULT_EVIDENCE_JSONL = ""
SUCCESS_STATUSES = {"arrived", "ok", "success", "complete"}


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def tile_key(tile: Optional[Dict[str, int]]) -> str:
    if not isinstance(tile, dict):
        return ""
    return "{},{},{}".format(int(tile["x"]), int(tile["y"]), int(tile.get("height", 0)))


def normalize_tile(value: Any) -> Optional[Dict[str, int]]:
    if isinstance(value, dict) and "x" in value and "y" in value:
        return {
            "x": int(value["x"]),
            "y": int(value["y"]),
            "height": int(value.get("height", value.get("h", 0)) or 0),
        }
    if isinstance(value, str):
        parts = value.split(",")
        if len(parts) in (2, 3):
            return {
                "x": int(parts[0]),
                "y": int(parts[1]),
                "height": int(parts[2]) if len(parts) == 3 else 0,
            }
    return None


def player_tile(player: Dict[str, Any]) -> Dict[str, int]:
    return bridge.tile_from_player(player)


def player_hp(player: Dict[str, Any]) -> int:
    return int(player.get("hitpoints", player.get("hp", 0)) or 0)


def player_dead(player: Dict[str, Any]) -> bool:
    return bool(player.get("isDead", player.get("dead", False)))


def player_in_combat(player: Dict[str, Any]) -> bool:
    return bool(player.get("isInCombat", player.get("inCombat", False)))


def distance(left: Dict[str, int], right: Dict[str, int]) -> int:
    if int(left.get("height", 0)) != int(right.get("height", 0)):
        return 100000
    return max(abs(int(left["x"]) - int(right["x"])), abs(int(left["y"]) - int(right["y"])))


def append_jsonl(path_text: str, record: Dict[str, Any]) -> None:
    if not path_text:
        return
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def resolve_evidence_jsonl(path_text: str, profile: str) -> str:
    if path_text:
        return path_text
    return str(run_evidence_path(profile))


def compact_player(player: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "playerId": player.get("playerId", player.get("id")),
        "name": player.get("name", player.get("playerName")),
        "tile": player_tile(player),
        "hitpoints": player_hp(player),
        "maxHitpoints": int(player.get("maxHitpoints", player.get("maxHp", 0)) or 0),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled", False)),
        "isDead": player_dead(player),
        "isInCombat": player_in_combat(player),
        "foodCount": bridge.count_inventory_item(player, 1971),
        "combatLevel": int(player.get("combatLevel", 0) or 0),
        "coins": bridge.count_inventory_item(player, bridge.COINS),
    }


def is_object_transition_step(step: Dict[str, Any]) -> bool:
    return str(step.get("type") or "").lower() == "object_transition"


def step_completion_tile(step: Dict[str, Any]) -> Optional[Dict[str, int]]:
    if is_object_transition_step(step):
        return normalize_tile(step.get("postTile")) or normalize_tile(step.get("to")) or normalize_tile(step)
    return normalize_tile(step.get("to")) or normalize_tile(step.get("tile")) or normalize_tile(step)


def step_walk_target(step: Dict[str, Any]) -> Optional[Dict[str, int]]:
    if is_object_transition_step(step):
        return normalize_tile(step.get("preTile")) or normalize_tile(step.get("approachTile"))
    return step_completion_tile(step)


def step_object_tile(step: Dict[str, Any]) -> Optional[Dict[str, int]]:
    return normalize_tile(step.get("objectTile")) or normalize_tile((step.get("transitionProof") or {}).get("objectTile")) or normalize_tile(step.get("to"))


def step_post_tile(step: Dict[str, Any]) -> Optional[Dict[str, int]]:
    return normalize_tile(step.get("postTile")) or normalize_tile((step.get("transitionProof") or {}).get("postTile")) or normalize_tile(step.get("to"))


def route_step_from_value(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        step = dict(value)
        tile = step_completion_tile(step)
        if tile and "x" not in step:
            step.update(tile)
        return step
    tile = normalize_tile(value)
    if tile:
        return dict(tile)
    return None


def nearest_step_index(steps: List[Dict[str, Any]], current: Dict[str, int]) -> int:
    best_index = 0
    best_distance = 100000
    for index, step in enumerate(steps):
        tile = step_completion_tile(step)
        if not tile:
            continue
        dist = distance(current, tile)
        if dist < best_distance:
            best_index = index
            best_distance = dist
    return best_index


def compact_npc(npc: Dict[str, Any]) -> Dict[str, Any]:
    tile = normalize_tile(npc) or normalize_tile(npc.get("tile"))
    result = {
        "index": npc.get("idx", npc.get("index")),
        "name": npc.get("name", ""),
        "combatLevel": npc.get("level", npc.get("combatLevel")),
        "tile": tile,
        "aggressive": bool(npc.get("aggressive", False)),
        "underAttack": bool(npc.get("underAttack", False)),
    }
    return {key: value for key, value in result.items() if value not in (None, "", {}, [])}


def active_enemy_snapshot(player: Dict[str, Any], profile: str) -> Dict[str, Any]:
    ids = {
        int(value or 0)
        for value in (
            player.get("npcIndex"),
            player.get("killingNpcIndex"),
            player.get("underAttackBy"),
            player.get("underAttackBy2"),
            player.get("underAttackByNpcId"),
        )
        if int(value or 0) > 0
    }
    try:
        observed = bridge.call_tool("observe_state", {}, profile=profile)
    except Exception:
        return {}
    npcs = observed.get("nearbyNpcs") or []
    if not isinstance(npcs, list):
        return {}
    current = player_tile(player)
    best = None
    best_score = 100000
    for npc in npcs:
        if not isinstance(npc, dict):
            continue
        npc_index = int(npc.get("idx", npc.get("index", 0)) or 0)
        tile = normalize_tile(npc) or normalize_tile(npc.get("tile"))
        score = 0 if npc_index in ids else 1000
        if tile:
            score += distance(current, tile)
        if best is None or score < best_score:
            best = npc
            best_score = score
    return compact_npc(best or {})


def set_run_for_mode(player: Dict[str, Any], mode: str, profile: str) -> Dict[str, Any]:
    if mode in ("auto", "preserve"):
        return player
    desired = mode == "always"
    if mode == "never":
        desired = False
    if bool(player.get("runEnabled", False)) == desired:
        return player
    result = bridge.call_tool("set_run", {"enabled": desired}, profile=profile)
    return bridge._player_from_or(result, player)


def maybe_eat(player: Dict[str, Any], eat_at: int, profile: str) -> Dict[str, Any]:
    if eat_at <= 0 or player_hp(player) > eat_at:
        return player
    if bridge.count_inventory_item(player, 1971) <= 0:
        return player
    result = bridge.call_tool("eat_best_food", {}, profile=profile)
    return bridge._player_from_or(result, player)


def execution_steps(definition: Dict[str, Any], current: Dict[str, int]) -> List[Dict[str, Any]]:
    steps = [route_step_from_value(item) for item in definition.get("routeSteps") or []]
    steps = [step for step in steps if step is not None]
    if not steps:
        raise RuntimeError("route definition has no routeSteps")
    start_index = nearest_step_index(steps, current)
    completion = step_completion_tile(steps[start_index])
    if completion and distance(current, completion) <= 1:
        start_index += 1
    return steps[start_index:]


def choose_lookahead_target(
    steps: List[Dict[str, Any]],
    start_index: int,
    current: Dict[str, int],
    lookahead_distance: int,
    step_limit: int,
) -> tuple[int, Dict[str, int], int]:
    """Pick the farthest upcoming route step that remains a bounded route batch."""
    if start_index >= len(steps):
        target = step_completion_tile(steps[-1])
        if not target:
            raise RuntimeError("route step has no target tile")
        return len(steps) - 1, target, 0
    first_target = step_completion_tile(steps[start_index])
    if not first_target:
        raise RuntimeError("route step has no target tile")
    if lookahead_distance <= 0 or step_limit <= 1:
        return start_index, first_target, distance(current, first_target)

    max_index = min(len(steps) - 1, start_index + max(1, step_limit) - 1)
    target_index = start_index
    travelled = distance(current, first_target)
    if travelled > lookahead_distance:
        return target_index, first_target, travelled
    for index in range(start_index + 1, max_index + 1):
        if is_object_transition_step(steps[index]):
            break
        previous = step_completion_tile(steps[index - 1])
        current_step = step_completion_tile(steps[index])
        if not previous or not current_step:
            break
        travelled += distance(previous, current_step)
        if travelled > lookahead_distance:
            break
        target_index = index
    target = step_completion_tile(steps[target_index])
    if not target:
        raise RuntimeError("route step has no target tile")
    return target_index, target, travelled


def distance_to_route_steps(steps: List[Dict[str, Any]], current: Dict[str, int]) -> int:
    if not steps:
        return 100000
    tiles = [step_completion_tile(step) for step in steps]
    tiles = [tile for tile in tiles if tile]
    return min((distance(current, tile) for tile in tiles), default=100000)


def outcome_status(player: Dict[str, Any], target_tile: Optional[Dict[str, int]], arrival_radius: int) -> str:
    if player_dead(player):
        return "death"
    if target_tile and distance(player_tile(player), target_tile) <= arrival_radius:
        return "success"
    return "partial"


def transition_walk_steps(step: Dict[str, Any]) -> List[Dict[str, int]]:
    steps = []
    for value in step.get("walkSteps") or step.get("crossingSteps") or []:
        tile = normalize_tile(value)
        if tile:
            steps.append(tile)
    return steps


def transition_args(step: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    object_tile = step_object_tile(step)
    if not object_tile:
        raise RuntimeError("object_transition step is missing objectTile")
    object_id = step.get("objectId")
    payload = {
        "x": object_tile["x"],
        "y": object_tile["y"],
        "height": object_tile.get("height", 0),
        "maxTicks": int(args.transition_max_ticks),
    }
    if object_id is not None:
        payload["objectId"] = int(object_id)
    option = str(step.get("option") or "").strip()
    if option:
        payload["option"] = option
    return payload


def run(args: argparse.Namespace) -> int:
    definition_path = Path(args.route_definition)
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    if definition.get("api") != "2006scape.route-definition":
        raise RuntimeError("not a 2006scape route definition: {}".format(definition_path))

    profile = resolve_profile(args.profile, default="")
    args.evidence_jsonl = resolve_evidence_jsonl(args.evidence_jsonl, profile)
    player = bridge.observe(profile)
    player = set_run_for_mode(player, args.run_mode, profile)
    start_player = dict(player)
    target_tile = normalize_tile(definition.get("targetTile"))
    arrival_radius = int(args.arrival_radius if args.arrival_radius is not None else definition.get("arrivalRadius") or 1)
    route_id = definition.get("routeId", "")
    steps = execution_steps(definition, player_tile(player))
    total_hp_lost = 0
    total_run_spent = 0
    combat_seen = False
    active_enemy: Dict[str, Any] = {}

    print(json.dumps({
        "event": "route_start",
        "routeId": route_id,
        "from": tile_key(player_tile(player)),
        "to": definition.get("to"),
        "remainingSteps": len(steps),
        "runMode": args.run_mode,
        "eatAt": args.eat_at,
        "lookaheadDistance": 0 if args.no_lookahead else args.lookahead_distance,
        "lookaheadStepLimit": args.lookahead_step_limit,
    }, sort_keys=True), flush=True)

    step_index = 0
    batch = 0
    problem_kind = ""
    lookahead_distance = 0 if args.no_lookahead else int(args.lookahead_distance)
    while step_index < len(steps):
        batch += 1
        step = steps[step_index]
        if is_object_transition_step(step):
            before = dict(player)
            player = maybe_eat(player, args.eat_at, profile)
            before_hp = player_hp(player)
            before_run = int(player.get("runEnergy", 0) or 0)
            approach = step_walk_target(step)
            transition_result: Dict[str, Any] = {}
            approach_result: Dict[str, Any] = {"success": True, "status": "already_at_approach"}
            if approach and distance(player_tile(player), approach) > int(args.transition_approach_distance):
                approach_result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
                    "x": approach["x"],
                    "y": approach["y"],
                    "height": approach.get("height", 0),
                    "stopDistance": args.transition_approach_distance,
                    "maxTicks": args.max_ticks,
                    "maxWalkDistance": args.max_walk_distance,
                    "stopOnStall": True,
                    "stopOnCombat": bool(args.stop_on_combat),
                }, profile=profile)
                player = bridge._player_from_or(approach_result, player)
            if approach_result.get("success") and not player_dead(player):
                transition_result = bridge.call_tool("object_transition_step_XS", transition_args(step, args), profile=profile)
                player = bridge._player_from_or(transition_result, player)
                walk_steps = transition_walk_steps(step)
                if transition_result.get("success") and walk_steps:
                    walk_result = bridge.call_tool("walk_path_steps_XS", {
                        "steps": walk_steps,
                        "run": bool(player.get("runEnabled", True)),
                        "allowObjectTransition": True,
                    }, profile=profile)
                    player = bridge._player_from_or(walk_result, player)
                    waited = bridge.call_tool("wait_until_idle_XS", {
                        "maxTicks": int(args.transition_max_ticks),
                        "movement": True,
                        "skilling": False,
                        "combat": False,
                    }, profile=profile)
                    player = bridge._player_from_or(waited, player)
                    transition_result = {
                        "success": bool(walk_result.get("success")) and bool(waited.get("success", True)),
                        "status": waited.get("batchStatus") or waited.get("status") or walk_result.get("status"),
                        "walkResult": walk_result,
                        "waitResult": waited,
                    }
            post_tile = step_post_tile(step)
            post_distance = distance(player_tile(player), post_tile) if post_tile else 0
            proof_ok = post_tile is None or post_distance <= int(args.transition_post_distance)
            after_hp = player_hp(player)
            after_run = int(player.get("runEnergy", 0) or 0)
            hp_lost = max(0, before_hp - after_hp)
            run_spent = max(0, before_run - after_run)
            total_hp_lost += hp_lost
            total_run_spent += run_spent
            combat_seen = combat_seen or player_in_combat(player) or hp_lost > 0
            success = bool(approach_result.get("success")) and bool(transition_result.get("success")) and proof_ok and not player_dead(player)
            if not success:
                problem_kind = "object_transition_failed"
            record = {
                "schemaVersion": 1,
                "event": "route_transition",
                "timestamp": utcnow(),
                "tool": "execute_route_definition",
                "profile": profile,
                "playerName": player.get("name", player.get("playerName", profile)),
                "playerId": player.get("playerId", player.get("id")),
                "routeId": route_id,
                "routeMode": definition.get("mode"),
                "routeQuality": definition.get("quality"),
                "targetPlace": definition.get("to"),
                "targetPlaceTile": target_tile,
                "batch": batch,
                "mode": "object_transition",
                "routeStepIndex": step_index,
                "objectId": step.get("objectId"),
                "objectName": step.get("objectName"),
                "objectTile": step_object_tile(step),
                "preTile": step_walk_target(step),
                "postTile": post_tile,
                "postDistance": post_distance,
                "proofOk": proof_ok,
                "approachStatus": approach_result.get("batchStatus") or approach_result.get("status"),
                "transitionStatus": transition_result.get("batchStatus") or transition_result.get("status"),
                "success": success,
                "currentTile": player_tile(before),
                "finalTile": player_tile(player),
                "tile": player_tile(player),
                "hitpointsLost": hp_lost,
                "isDead": player_dead(player),
                "isInCombat": player_in_combat(player),
                "runEnabled": bool(before.get("runEnabled", False)),
                "runEnergySpent": run_spent,
                "playerBefore": compact_player(before),
                "playerAfter": compact_player(player),
            }
            append_jsonl(args.evidence_jsonl, {key: value for key, value in record.items() if value not in ("", [], {}, None)})
            append_jsonl(args.evidence_jsonl, {
                "schemaVersion": 1,
                "event": "route_batch",
                "timestamp": utcnow(),
                "tool": "execute_route_definition",
                "profile": profile,
                "routeId": route_id,
                "batch": batch,
                "mode": "object_transition",
                "routeStepIndex": step_index,
                "batchStatus": "arrived" if success else "object_transition_failed",
                "success": success,
                "currentTile": player_tile(before),
                "targetTile": post_tile,
                "finalTile": player_tile(player),
                "playerAfter": compact_player(player),
            })
            print(json.dumps({
                "event": "route_transition",
                "routeId": route_id,
                "batch": batch,
                "routeStepIndex": step_index,
                "objectId": step.get("objectId"),
                "objectTile": step_object_tile(step),
                "postTile": post_tile,
                "tile": player_tile(player),
                "status": "arrived" if success else "object_transition_failed",
                "proofOk": proof_ok,
                "hp": after_hp,
                "hitpointsLost": hp_lost,
                "inCombat": player_in_combat(player),
                "dead": player_dead(player),
            }, sort_keys=True), flush=True)
            if not success:
                break
            if target_tile and distance(player_tile(player), target_tile) <= arrival_radius:
                break
            step_index += 1
            continue
        target_index, target, planned_batch_distance = choose_lookahead_target(
            steps,
            step_index,
            player_tile(player),
            lookahead_distance,
            int(args.lookahead_step_limit),
        )
        before = dict(player)
        player = maybe_eat(player, args.eat_at, profile)
        before_hp = player_hp(player)
        before_run = int(player.get("runEnergy", 0) or 0)
        result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
            "x": target["x"],
            "y": target["y"],
            "height": target.get("height", 0),
            "stopDistance": args.stop_distance,
            "maxTicks": args.max_ticks,
            "maxWalkDistance": args.max_walk_distance,
            "stopOnStall": True,
            "stopOnCombat": bool(args.stop_on_combat),
        }, profile=profile)
        player = bridge._player_from_or(result, player)
        after_hp = player_hp(player)
        after_run = int(player.get("runEnergy", 0) or 0)
        hp_lost = max(0, before_hp - after_hp)
        run_spent = max(0, before_run - after_run)
        total_hp_lost += hp_lost
        total_run_spent += run_spent
        combat_seen = combat_seen or player_in_combat(player) or hp_lost > 0
        enemy = {}
        if args.observe_on_contact and (player_in_combat(player) or hp_lost > 0):
            enemy = active_enemy_snapshot(player, profile)
            if enemy:
                active_enemy = enemy
        record = {
            "schemaVersion": 1,
            "event": "route_batch",
            "timestamp": utcnow(),
            "tool": "execute_route_definition",
            "profile": profile,
            "playerName": player.get("name", player.get("playerName", profile)),
            "playerId": player.get("playerId", player.get("id")),
            "routeId": route_id,
            "routeMode": definition.get("mode"),
            "routeQuality": definition.get("quality"),
            "targetPlace": definition.get("to"),
            "targetPlaceTile": target_tile,
            "batch": batch,
            "mode": "route-definition-steps",
            "routeStepIndex": step_index,
            "targetRouteStepIndex": target_index,
            "lookaheadRouteSteps": target_index - step_index + 1,
            "plannedBatchDistance": planned_batch_distance,
            "currentTile": player_tile(before),
            "targetTile": target,
            "finalTile": player_tile(player),
            "tile": player_tile(player),
            "batchStatus": result.get("batchStatus") or result.get("status"),
            "success": bool(result.get("success")),
            "batchTicks": int(result.get("batchTicks") or result.get("ticks") or 0),
            "hitpointsLost": hp_lost,
            "isDead": player_dead(player),
            "isInCombat": player_in_combat(player),
            "runEnabled": bool(before.get("runEnabled", False)),
            "runEnergySpent": run_spent,
            "enemy": enemy,
            "playerBefore": compact_player(before),
            "playerAfter": compact_player(player),
        }
        append_jsonl(args.evidence_jsonl, record)
        if hp_lost or player_in_combat(player) or player_dead(player) or not result.get("success") or batch % max(1, args.report_every) == 0:
            print(json.dumps({
                "event": "route_step",
                "routeId": route_id,
                "batch": batch,
                "routeStepIndex": step_index,
                "targetRouteStepIndex": target_index,
                "lookaheadRouteSteps": target_index - step_index + 1,
                "target": target,
                "tile": player_tile(player),
                "status": record["batchStatus"],
                "hp": after_hp,
                "hitpointsLost": hp_lost,
                "inCombat": player_in_combat(player),
                "dead": player_dead(player),
                "enemy": enemy,
            }, sort_keys=True), flush=True)
        if not result.get("success") or player_dead(player):
            break
        off_route_distance = distance_to_route_steps(steps[target_index:], player_tile(player))
        if args.off_route_distance >= 0 and off_route_distance > args.off_route_distance:
            record = {
                "schemaVersion": 1,
                "event": "route_batch",
                "timestamp": utcnow(),
                "tool": "execute_route_definition",
                "profile": profile,
                "routeId": route_id,
                "batch": batch,
                "mode": "route-definition-steps",
                "batchStatus": "off_route",
                "success": False,
                "currentTile": player_tile(before),
                "targetTile": target,
                "finalTile": player_tile(player),
                "offRouteDistance": off_route_distance,
                "playerAfter": compact_player(player),
            }
            append_jsonl(args.evidence_jsonl, record)
            print(json.dumps({
                "event": "route_step",
                "routeId": route_id,
                "batch": batch,
                "target": target,
                "tile": player_tile(player),
                "status": "off_route",
                "offRouteDistance": off_route_distance,
            }, sort_keys=True), flush=True)
            break
        if target_tile and distance(player_tile(player), target_tile) <= arrival_radius:
            break
        step_index = target_index + 1

    status = outcome_status(player, target_tile, arrival_radius)
    outcome = {
        "schemaVersion": 1,
        "event": "route_outcome",
        "timestamp": utcnow(),
        "source": "execute_route_definition",
        "profile": profile,
        "playerName": start_player.get("name", start_player.get("playerName", profile)),
        "playerId": start_player.get("playerId", start_player.get("id")),
        "routeId": route_id,
        "status": status,
        "success": status == "success",
        "problemKind": problem_kind or ("enemy_contact" if combat_seen and status == "success" else ""),
        "targetPlace": definition.get("to"),
        "from": tile_key(player_tile(start_player)),
        "to": tile_key(target_tile),
        "final": tile_key(player_tile(player)),
        "fromTile": player_tile(start_player),
        "targetTile": target_tile,
        "finalTile": player_tile(player),
        "hitpointsLost": total_hp_lost,
        "isDead": player_dead(player),
        "isInCombat": player_in_combat(player),
        "runEnabled": bool(player.get("runEnabled", False)),
        "runEnergySpent": total_run_spent,
        "routeQuality": definition.get("quality"),
        "routeMode": definition.get("mode"),
        "routeDistance": definition.get("distanceTiles"),
        "routeStepCount": definition.get("routeStepCount"),
        "hazardIds": sorted({
            hazard_id
            for segment in definition.get("runSegments") or []
            for hazard_id in segment.get("hazardIds", [])
        }),
        "enemy": active_enemy,
        "notes": "Executed ML2 mixed routeSteps through bridge walking/object primitives.",
    }
    append_jsonl(args.evidence_jsonl, {key: value for key, value in outcome.items() if value not in ("", [], {}, None)})
    print(json.dumps({"event": "route_end", **outcome}, sort_keys=True), flush=True)
    return 0 if status == "success" else 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a persisted ML2 mixed route definition with bridge primitives.")
    parser.add_argument("--route-definition", required=True)
    parser.add_argument("--to", default="", help="Optional human-readable target label; the route definition remains authoritative.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--run-mode", choices=["auto", "always", "never", "preserve"], default="auto",
                        help="auto currently preserves normal walking unless the caller explicitly chooses always/never.")
    parser.add_argument("--eat-at", type=int, default=10,
                        help="Eat best available food before the next step when HP is at or below this value. Use 0 to disable.")
    parser.add_argument("--arrival-radius", type=int)
    parser.add_argument("--max-ticks", type=int, default=95)
    parser.add_argument("--max-walk-distance", type=int, default=36)
    parser.add_argument("--stop-distance", type=int, default=0)
    parser.add_argument("--transition-approach-distance", type=int, default=0,
                        help="Required distance to the preTile/approachTile before clicking an object transition.")
    parser.add_argument("--transition-post-distance", type=int, default=1,
                        help="Maximum distance from postTile accepted as object-transition proof.")
    parser.add_argument("--transition-max-ticks", type=int, default=20,
                        help="Tick budget for object transition and immediate crossing proof.")
    parser.add_argument("--lookahead-distance", type=int, default=30,
                        help="Route-step distance budget per walk batch. Use 0 to execute one routeStep at a time.")
    parser.add_argument("--lookahead-step-limit", type=int, default=4,
                        help="Maximum routeSteps to fold into one optimistic walk batch.")
    parser.add_argument("--no-lookahead", action="store_true",
                        help="Preserve the old executor behavior: one walk batch per routeStep.")
    parser.add_argument("--off-route-distance", type=int, default=12,
                        help="Stop after a successful batch if the player is this far from the remaining routeSteps; use -1 to disable.")
    parser.add_argument("--stop-on-combat", action="store_true")
    parser.add_argument("--observe-on-contact", action="store_true", default=True)
    parser.add_argument("--no-observe-on-contact", dest="observe_on_contact", action="store_false")
    parser.add_argument("--evidence-jsonl", default=DEFAULT_EVIDENCE_JSONL,
                        help="Route evidence JSONL. Defaults to a profile-scoped path under .local/run-evidence.")
    parser.add_argument("--report-every", type=int, default=6)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    log_usage("execute_route_definition", surface="full", argv=argv_list)
    return run(build_parser().parse_args(argv_list))


if __name__ == "__main__":
    raise SystemExit(main())
