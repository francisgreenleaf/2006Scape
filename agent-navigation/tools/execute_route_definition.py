#!/usr/bin/env python3
"""Execute an ML1 route definition through normal bridge walking primitives."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import bridge_script as bridge
from usage_log import log_usage


DEFAULT_EVIDENCE_JSONL = "agent-navigation/.local/run-evidence/ml-route-executor.routes.jsonl"
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


def compact_player(player: Dict[str, Any]) -> Dict[str, Any]:
    return {
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


def nearest_step_index(steps: List[Dict[str, int]], current: Dict[str, int]) -> int:
    best_index = 0
    best_distance = 100000
    for index, step in enumerate(steps):
        dist = distance(current, step)
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


def execution_steps(definition: Dict[str, Any], current: Dict[str, int]) -> List[Dict[str, int]]:
    steps = [normalize_tile(item) for item in definition.get("routeSteps") or []]
    steps = [step for step in steps if step is not None]
    if not steps:
        raise RuntimeError("route definition has no routeSteps")
    start_index = nearest_step_index(steps, current)
    if distance(current, steps[start_index]) <= 1:
        start_index += 1
    return steps[start_index:]


def outcome_status(player: Dict[str, Any], target_tile: Optional[Dict[str, int]], arrival_radius: int) -> str:
    if player_dead(player):
        return "death"
    if target_tile and distance(player_tile(player), target_tile) <= arrival_radius:
        return "success"
    return "partial"


def run(args: argparse.Namespace) -> int:
    definition_path = Path(args.route_definition)
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    if definition.get("api") != "2006scape.route-definition":
        raise RuntimeError("not a 2006scape route definition: {}".format(definition_path))

    profile = args.profile or os.environ.get("RS_PROFILE", "")
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
    }, sort_keys=True), flush=True)

    for batch, target in enumerate(steps, start=1):
        before = dict(player)
        player = maybe_eat(player, args.eat_at, profile)
        before_hp = player_hp(player)
        before_run = int(player.get("runEnergy", 0) or 0)
        result = bridge.call_tool("walk_to_tile_until_arrived", {
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
            "routeId": route_id,
            "routeMode": definition.get("mode"),
            "routeQuality": definition.get("quality"),
            "targetPlace": definition.get("to"),
            "targetPlaceTile": target_tile,
            "batch": batch,
            "mode": "route-definition-steps",
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
        if target_tile and distance(player_tile(player), target_tile) <= arrival_radius:
            break

    status = outcome_status(player, target_tile, arrival_radius)
    outcome = {
        "schemaVersion": 1,
        "event": "route_outcome",
        "timestamp": utcnow(),
        "source": "execute_route_definition",
        "profile": profile,
        "routeId": route_id,
        "status": status,
        "success": status == "success",
        "problemKind": "enemy_contact" if combat_seen and status == "success" else "",
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
        "notes": "Executed ML1 routeSteps through bridge primitives.",
    }
    append_jsonl(args.evidence_jsonl, {key: value for key, value in outcome.items() if value not in ("", [], {}, None)})
    print(json.dumps({"event": "route_end", **outcome}, sort_keys=True), flush=True)
    return 0 if status == "success" else 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a persisted ML1 route definition with bridge primitives.")
    parser.add_argument("--route-definition", required=True)
    parser.add_argument("--to", default="", help="Optional human-readable target label; the route definition remains authoritative.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE", ""))
    parser.add_argument("--run-mode", choices=["auto", "always", "never", "preserve"], default="auto",
                        help="auto currently preserves normal walking unless the caller explicitly chooses always/never.")
    parser.add_argument("--eat-at", type=int, default=10,
                        help="Eat best available food before the next step when HP is at or below this value. Use 0 to disable.")
    parser.add_argument("--arrival-radius", type=int)
    parser.add_argument("--max-ticks", type=int, default=95)
    parser.add_argument("--max-walk-distance", type=int, default=36)
    parser.add_argument("--stop-distance", type=int, default=0)
    parser.add_argument("--stop-on-combat", action="store_true")
    parser.add_argument("--observe-on-contact", action="store_true", default=True)
    parser.add_argument("--no-observe-on-contact", dest="observe_on_contact", action="store_false")
    parser.add_argument("--evidence-jsonl", default=DEFAULT_EVIDENCE_JSONL)
    parser.add_argument("--report-every", type=int, default=6)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    log_usage("execute_route_definition", surface="full", argv=argv_list)
    return run(build_parser().parse_args(argv_list))


if __name__ == "__main__":
    raise SystemExit(main())
