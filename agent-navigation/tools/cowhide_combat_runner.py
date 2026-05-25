#!/usr/bin/env python3
"""Bounded cow combat and cowhide banking runner.

This keeps early cow combat, hide pickup, kebab restocking, and bank trips out
of the AI token loop. It uses normal bridge gameplay only: all game actions go
through rs-tool.sh, and all travel goes through route_runner.py.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bridge_script as bridge


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"
RUNS_DIR = ROOT / "data" / "combat" / "runs"
RUN_PROFILE = ""

COWHIDE = 1739
COINS = 995
KEBAB = 1971
STEEL_WEAPON_ATTACK_LEVEL = 5
EARLY_STYLE_LEVEL = 5
EXTRA_COW_TRIP_BANK_ITEM_IDS = (1323,)  # Iron scimitar; steel scimitar is equipped once attack is 5.
LUMBRIDGE_COW_PEN_GATE_IDS = {1551, 1553}
LUMBRIDGE_COW_PEN_GATE_X_RANGE = (3251, 3253)
LUMBRIDGE_COW_PEN_GATE_Y_RANGE = (3266, 3267)
LUMBRIDGE_COW_PEN_ENTRY_TILES = (
    (3253, 3266, 0),  # old gate tile after opening
    (3254, 3266, 0),  # clear first cow-side tile east of the gate
)
LUMBRIDGE_COW_PEN_EXIT_TILES = (
    (3252, 3266, 0),  # immediate west step through the opened gate
    (3251, 3266, 0),
    (3250, 3266, 0),  # clear outside anchor for route_runner
)
KNOWN_FOOD_IDS = {
    KEBAB,
    1891,  # Cake
    1893,  # 2/3 cake
    1895,  # Slice of cake
    1901,  # Chocolate slice
    1905,  # Asgarnian ale
    1963,  # Banana
    1973,  # Chocolate bar
    1985,  # Cheese
    2142,  # Cooked meat
    2140,  # Cooked chicken
    315,   # Shrimps
    319,   # Anchovies
    325,   # Sardine
    329,   # Salmon
    333,   # Trout
    339,   # Cod
    347,   # Herring
    351,   # Pike
    355,   # Mackerel
    361,   # Tuna
    365,   # Bass
    379,   # Lobster
    385,   # Shark
}


class RunnerStop(Exception):
    def __init__(self, reason, message, player=None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.player = player or {}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def log(message, args=None, force=False):
    if force or args is None or not getattr(args, "quiet", False):
        print(message, flush=True)


def jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    return value


def write_event(handle, event, data):
    if handle is None:
        return
    record = {"event": event, "timestamp": utc_now()}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def call_tool(tool_name, arguments=None):
    env = os.environ.copy()
    if RUN_PROFILE:
        env["RS_PROFILE"] = RUN_PROFILE
    proc = subprocess.run(
        [str(RS_TOOL), tool_name, json.dumps(arguments or {}, separators=(",", ":"))],
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(tool_name, proc.stderr.strip() or proc.stdout.strip()))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("{} returned invalid JSON: {}".format(tool_name, exc))


def player_from(result):
    player = result.get("player")
    if isinstance(player, dict):
        return player
    state = result.get("state")
    if isinstance(state, dict) and isinstance(state.get("player"), dict):
        return state["player"]
    raise RuntimeError("bridge response did not include player state")


def player_from_or(result, fallback):
    try:
        return player_from(result)
    except RuntimeError:
        return fallback


def observe_state():
    result = call_tool("observe_state", {})
    player = player_from(result)
    return result, player


def tile(x, y, height=0):
    return {"x": int(x), "y": int(y), "height": int(height)}


def tile_from_player(player):
    return tile(player.get("x", 0), player.get("y", 0), player.get("height", player.get("h", 0)))


def tile_string(value):
    return "{},{},{}".format(int(value["x"]), int(value["y"]), int(value.get("height", 0)))


def player_x(player):
    return int(player.get("x", 0) or 0)


def player_y(player):
    return int(player.get("y", 0) or 0)


def player_h(player):
    return int(player.get("height", player.get("h", 0)) or 0)


def is_lumbridge_cow_pen_target(target):
    normalized = str(target or "").strip().lower().replace("_", " ")
    return normalized in {
        "lumbridge cow pen",
        "lumbridge cows",
        "lumbridge cow area",
        "3255,3266,0",
        "3257,3267,0",
    }


def in_lumbridge_cow_pen(player):
    x = player_x(player)
    y = player_y(player)
    return player_h(player) == 0 and 3253 <= x <= 3268 and 3260 <= y <= 3293


def in_lumbridge_cow_training_pocket(player):
    x = player_x(player)
    y = player_y(player)
    return player_h(player) == 0 and 3250 <= x <= 3268 and 3260 <= y <= 3293


def near_lumbridge_cow_pen_gate(player):
    x = player_x(player)
    y = player_y(player)
    return player_h(player) == 0 and 3248 <= x <= 3258 and 3260 <= y <= 3272


def on_al_kharid_side(player):
    x = player_x(player)
    y = player_y(player)
    return player_h(player) == 0 and x >= 3268 and 3150 <= y <= 3232


def gate_object_is_lumbridge_cow_pen(gate):
    if not isinstance(gate, dict):
        return False
    try:
        object_id = int(gate.get("objectId", gate.get("id", -1)))
        x = int(gate.get("x", 0))
        y = int(gate.get("y", 0))
        h = int(gate.get("height", gate.get("h", 0)) or 0)
    except (TypeError, ValueError):
        return False
    return (
        object_id in LUMBRIDGE_COW_PEN_GATE_IDS
        and h == 0
        and LUMBRIDGE_COW_PEN_GATE_X_RANGE[0] <= x <= LUMBRIDGE_COW_PEN_GATE_X_RANGE[1]
        and LUMBRIDGE_COW_PEN_GATE_Y_RANGE[0] <= y <= LUMBRIDGE_COW_PEN_GATE_Y_RANGE[1]
    )


def skill_level(player, name):
    skills = player.get("skills") or {}
    skill = skills.get(name) or {}
    return int(skill.get("baseLevel", skill.get("level", 0)) or 0)


def skill_xp(player, name):
    skills = player.get("skills") or {}
    skill = skills.get(name) or {}
    return int(skill.get("xp", 0) or 0)


def inventory(player):
    return player.get("inventory") or []


def equipment(player):
    return player.get("equipment") or []


def bank(player):
    return player.get("bank") or []


def count_items(items, item_id):
    total = 0
    for item in items:
        if int(item.get("id", -1)) == int(item_id):
            total += int(item.get("amount", 1) or 1)
    return total


def count_inventory_item(player, item_id):
    return count_items(inventory(player), item_id)


def count_bank_item(player, item_id):
    return count_items(bank(player), item_id)


def count_known_food(player):
    return sum(count_inventory_item(player, item_id) for item_id in KNOWN_FOOD_IDS)


def inventory_food_count(player):
    readiness = player.get("combatReadiness") or {}
    if "inventoryFoodCount" in readiness:
        return int(readiness.get("inventoryFoodCount", 0) or 0)
    return count_known_food(player)


def bank_food_count(player):
    readiness = player.get("combatReadiness") or {}
    if "bankFoodCount" in readiness:
        return int(readiness.get("bankFoodCount", 0) or 0)
    return 0


def inventory_coins(player):
    readiness = player.get("combatReadiness") or {}
    if "inventoryCoins" in readiness:
        return int(readiness.get("inventoryCoins", 0) or 0)
    return count_inventory_item(player, COINS)


def bank_coins(player):
    readiness = player.get("combatReadiness") or {}
    if "bankCoins" in readiness:
        return int(readiness.get("bankCoins", 0) or 0)
    return count_bank_item(player, COINS)


def cowhide_count(player):
    return count_inventory_item(player, COWHIDE)


def compact_item(item):
    if not isinstance(item, dict):
        return item
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "amount": item.get("amount"),
        "slot": item.get("slot"),
        "slotName": item.get("slotName"),
    }


def compact_player(player):
    target = player.get("targetNpc") if isinstance(player.get("targetNpc"), dict) else None
    return {
        "tile": tile_from_player(player),
        "hitpoints": int(player.get("hitpoints", player.get("hp", 0)) or 0),
        "maxHitpoints": int(player.get("maxHitpoints", player.get("maxHp", 0)) or 0),
        "attackLevel": skill_level(player, "attack"),
        "strengthLevel": skill_level(player, "strength"),
        "defenceLevel": skill_level(player, "defence"),
        "combatLevel": int(player.get("combatLevel", 0) or 0),
        "combatStyle": player.get("combatStyle"),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled", False)),
        "isDead": bool(player.get("isDead", False)),
        "isMoving": bool(player.get("isMoving", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "targetNpc": target,
        "inBankArea": bool(player.get("inBankArea", False)),
        "isShopping": bool(player.get("isShopping", False)),
        "freeSlots": int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0),
        "cowhides": cowhide_count(player),
        "inventoryFood": inventory_food_count(player),
        "bankFood": bank_food_count(player),
        "inventoryCoins": inventory_coins(player),
        "bankCoins": bank_coins(player),
        "equipment": [compact_item(item) for item in equipment(player)],
    }


def active_combat_npc(state, player):
    target = player.get("targetNpc")
    if isinstance(target, dict):
        return target
    active_ids = set()
    for key in ("npcIndex", "killingNpcIndex", "underAttackBy", "underAttackBy2"):
        try:
            npc_id = int(player.get(key, 0) or 0)
        except (TypeError, ValueError):
            npc_id = 0
        if npc_id > 0:
            active_ids.add(npc_id)
    for npc in state.get("nearbyNpcs") or []:
        try:
            npc_index = int(npc.get("npcIndex", -1))
        except (TypeError, ValueError):
            npc_index = -1
        if npc_index in active_ids:
            return npc
    return None


def is_cow_npc(npc):
    if not isinstance(npc, dict):
        return False
    return "cow" in str(npc.get("name", "")).strip().lower()


def stop_if_unsafe(state, player, args, handle, reason):
    compact = compact_player(player)
    if compact["isDead"]:
        raise RunnerStop("death", "Player is dead.", player)
    if compact["isInCombat"]:
        npc = active_combat_npc(state, player)
        if not is_cow_npc(npc):
            write_event(handle, "unexpected_combat_target", {
                "reason": reason,
                "npc": npc,
                "player": compact,
            })
            raise RunnerStop("unexpected_combat_target", "Player is in combat with a non-cow or unknown target.", player)
    if compact["hitpoints"] <= int(args.retreat_threshold) and compact["inventoryFood"] <= 0:
        raise RunnerStop("low_hp_no_food", "Hitpoints are at or below retreat threshold and no food is carried.", player)


def stop_if_fight_poll_unsafe(state, player, args, handle, reason, last_known_cow=None, gained_xp=False):
    compact = compact_player(player)
    if compact["isDead"]:
        raise RunnerStop("death", "Player is dead.", player)
    if compact["hitpoints"] <= int(args.retreat_threshold) and compact["inventoryFood"] <= 0:
        raise RunnerStop("low_hp_no_food", "Hitpoints are at or below retreat threshold and no food is carried.", player)
    if compact["isInCombat"]:
        npc = active_combat_npc(state, player)
        if is_cow_npc(npc):
            return npc
        # At the kill/drop boundary this server can briefly report inCombat
        # with no targetNpc even though the fight was a cow and XP has landed.
        # Let the drop-pickup poll prove completion instead of stopping early.
        if npc is None and gained_xp and is_cow_npc(last_known_cow):
            write_event(handle, "stale_cow_combat_flag", {
                "reason": reason,
                "lastKnownCow": last_known_cow,
                "player": compact,
            })
            return None
        write_event(handle, "unexpected_combat_target", {
            "reason": reason,
            "npc": npc,
            "player": compact,
        })
        raise RunnerStop("unexpected_combat_target", "Player is in combat with a non-cow or unknown target.", player)
    return None


def interface_open(player):
    return (
        bool(player.get("isShopping", False))
        or bool(player.get("inTrade", False))
        or int(player.get("dialogueAction", 0) or 0) != 0
        or int(player.get("nextChat", 0) or 0) != 0
    )


def close_interfaces_if_needed(player, handle, reason):
    if not interface_open(player):
        return player
    result = call_tool("close_interfaces", {})
    updated = player_from(result)
    write_event(handle, "close_interfaces", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(updated),
    })
    return updated


def ensure_run(player, args, handle, reason):
    before = compact_player(player)
    if bool(player.get("runEnabled", False)) or int(player.get("runEnergy", 0) or 0) < int(args.min_run_energy):
        write_event(handle, "run_policy", {
            "reason": reason,
            "decision": "already_enabled_or_low_energy",
            "player": before,
        })
        return player
    result = call_tool("set_run", {"enabled": True})
    updated = player_from(result)
    write_event(handle, "run_policy", {
        "reason": reason,
        "decision": "set_run",
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "before": before,
        "after": compact_player(updated),
    })
    return updated


def route_evidence_path(args, run_path):
    if args.evidence_jsonl:
        return str(Path(args.evidence_jsonl))
    return str(run_path.with_name(run_path.stem + ".routes.jsonl"))


def route_to(target, args, handle, reason, run_path):
    evidence_path = route_evidence_path(args, run_path)
    Path(evidence_path).parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROUTE_RUNNER),
        "--to",
        target,
        "--allow-frontier",
        "--direct-if-preview",
        "--probe-toward-target",
        "--run-reserve",
        "auto",
        "--max-batches",
        str(args.route_max_batches),
        "--max-walk-distance",
        str(args.route_max_walk_distance),
        "--max-batch-distance",
        str(args.route_max_batch_distance),
        "--max-ticks",
        str(args.route_max_ticks),
        "--evidence-jsonl",
        evidence_path,
    ]
    if RUN_PROFILE:
        command.extend(["--profile", RUN_PROFILE])
    env = os.environ.copy()
    if RUN_PROFILE:
        env["RS_PROFILE"] = RUN_PROFILE
    write_event(handle, "route_start", {
        "reason": reason,
        "target": target,
        "command": command[1:],
        "routeEvidencePath": evidence_path,
    })
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    stdout_lines = proc.stdout.strip().splitlines()
    stderr_lines = proc.stderr.strip().splitlines()
    run_warnings = [line for line in stdout_lines if "runWarn=" in line and "runWarn=none" not in line]
    write_event(handle, "route_done", {
        "reason": reason,
        "target": target,
        "returncode": proc.returncode,
        "stdoutTail": stdout_lines[-10:],
        "stderrTail": stderr_lines[-10:],
        "runWarningLines": run_warnings[-5:],
        "routeEvidencePath": evidence_path,
    })
    if proc.returncode != 0:
        fallback = bridge_landmark_fallback(target)
        if fallback:
            log("route failed target={} reason={}; trying bridge landmark {}".format(target, reason, fallback), args, force=True)
            return travel_to_bridge_landmark(fallback, args, handle, reason, target)
        log("route failed target={} reason={}".format(target, reason), args, force=True)
        return False
    if not args.quiet:
        for line in stdout_lines[-4:]:
            log(line, args)
    return True


def bridge_landmark_fallback(target):
    normalized = str(target or "").strip().lower().replace("_", " ")
    if normalized in {"al kharid bank", "al kharid bank"}:
        return "al kharid bank"
    if normalized in {"al kharid kebab shop", "kebab shop"}:
        return "al kharid kebab shop"
    if normalized in {"lumbridge cow pen", "lumbridge cows", "3252,3266,0"}:
        # The bridge landmark path handles the Al Kharid toll gate; the cow
        # runner handles the actual pen gate after reaching the Lumbridge side.
        return "lumbridge goblins"
    return None


def travel_to_bridge_landmark(landmark, args, handle, reason, original_target):
    result = call_tool("travel_to_landmark_until_arrived", {
        "name": landmark,
        "maxTicks": int(args.route_max_ticks),
        "stopOnCombat": True,
        "stopOnStall": True,
    })
    updated = player_from_or(result, {})
    write_event(handle, "bridge_landmark_route_done", {
        "reason": reason,
        "target": original_target,
        "landmark": landmark,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "complete": bool(result.get("complete")),
        "batchStatus": result.get("batchStatus"),
        "batchTicks": result.get("batchTicks"),
        "player": compact_player(updated) if updated else {},
    })
    return bool(result.get("success")) and bool(result.get("complete"))


def route_or_stop(target, args, handle, reason, run_path, player=None):
    if not route_to(target, args, handle, reason, run_path):
        raise RunnerStop("no_route", "route_runner failed while routing to {} for {}.".format(target, reason), player)
    state, updated = observe_state()
    stop_if_unsafe(state, updated, args, handle, "after_route_" + reason)
    return state, updated


def walk_short(player, destination, args, handle, reason, max_ticks=None, max_distance=None):
    x, y, h = destination
    result = call_tool("walk_to_tile_until_arrived", {
        "x": int(x),
        "y": int(y),
        "height": int(h),
        "stopDistance": 0,
        "maxTicks": int(max_ticks or args.cow_gate_cross_ticks),
        "maxWalkDistance": int(max_distance or args.cow_gate_cross_distance),
        "stopOnCombat": True,
        "stopOnStall": True,
    })
    updated = player_from_or(result, player)
    write_event(handle, "walk_short", {
        "reason": reason,
        "destination": tile(x, y, h),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "batchStatus": result.get("batchStatus"),
        "batchTicks": result.get("batchTicks"),
        "player": compact_player(updated),
    })
    return result, updated


def cross_al_kharid_gate_to_lumbridge_side(player, args, handle, reason):
    if not on_al_kharid_side(player):
        return player
    player = ensure_run(player, args, handle, "al_kharid_gate_" + reason)
    if player_x(player) != 3268 or player_y(player) not in (3227, 3228):
        _walk, player = walk_short(
            player,
            (3268, 3227, 0),
            args,
            handle,
            "al_kharid_gate_approach_" + reason,
            max_ticks=max(80, int(args.route_max_ticks)),
            max_distance=max(80, int(args.route_max_walk_distance)),
        )
    if not on_al_kharid_side(player):
        return player

    for attempt in range(1, 4):
        before = compact_player(player)
        result = call_tool("travel_to_landmark", {"name": "lumbridge goblins"})
        player = player_from_or(result, player)
        write_event(handle, "al_kharid_gate_cross", {
            "reason": reason,
            "attempt": attempt,
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "coinsSpent": result.get("coinsSpent"),
            "before": before,
            "player": compact_player(player),
        })
        waited = call_tool("wait_until_idle", {
            "maxTicks": int(args.cow_gate_cross_ticks),
            "movement": True,
            "skilling": False,
            "combat": False,
        })
        player = player_from_or(waited, player)
        write_event(handle, "al_kharid_gate_cross_wait", {
            "reason": reason,
            "attempt": attempt,
            "success": bool(waited.get("success")),
            "message": waited.get("message"),
            "player": compact_player(player),
        })
        if not on_al_kharid_side(player):
            return player
        if inventory_coins(player) < 10:
            raise RunnerStop("al_kharid_gate_toll_missing", "Could not pay the Al Kharid gate toll from the east side.", player)

    raise RunnerStop("al_kharid_gate_cross_failed", "Could not prove crossing west through the Al Kharid gate.", player)


def horizontal_gate_steps(player, destination_x, y=3266):
    if player_h(player) != 0 or player_y(player) != int(y):
        return []
    current_x = player_x(player)
    destination_x = int(destination_x)
    if current_x == destination_x:
        return []
    direction = 1 if destination_x > current_x else -1
    return [(x, int(y), 0) for x in range(current_x + direction, destination_x + direction, direction)]


def walk_gate_transition_steps(player, destinations, args, handle, reason):
    if not destinations:
        return player
    result = call_tool("walk_path_steps", {
        "steps": [tile(*destination) for destination in destinations],
        "run": bool(player.get("runEnabled", True)),
        "allowObjectTransition": True,
    })
    queued = player_from_or(result, player)
    write_event(handle, "walk_gate_transition_steps", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "queuedSteps": result.get("queuedSteps"),
        "steps": [tile(*destination) for destination in destinations],
        "player": compact_player(queued),
    })
    if not result.get("success"):
        return queued
    waited = call_tool("wait_until_idle", {
        "maxTicks": int(args.cow_gate_cross_ticks),
        "movement": True,
        "skilling": False,
        "combat": False,
    })
    updated = player_from_or(waited, queued)
    write_event(handle, "walk_gate_transition_wait", {
        "reason": reason,
        "success": bool(waited.get("success")),
        "message": waited.get("message"),
        "batchStatus": waited.get("batchStatus"),
        "batchTicks": waited.get("batchTicks"),
        "player": compact_player(updated),
    })
    return updated


def find_lumbridge_cow_pen_gate(handle, player):
    result = call_tool("find_nearest_object", {
        "name": "gate",
        "maxDistance": 8,
    })
    gate = result.get("object") if isinstance(result, dict) else None
    write_event(handle, "find_cow_pen_gate", {
        "success": bool(result.get("success")) if isinstance(result, dict) else False,
        "message": result.get("message") if isinstance(result, dict) else None,
        "object": gate,
        "player": compact_player(player),
    })
    if gate_object_is_lumbridge_cow_pen(gate):
        return gate
    return None


def approach_gate_interaction_tile(gate, player, args, handle, reason):
    if not isinstance(gate, dict) or bool(gate.get("interactionInRange", False)):
        return player
    target = gate.get("interactionWalkTarget") or gate.get("nearestInteractionTile")
    if not isinstance(target, dict):
        return player
    destination = (
        int(target.get("x")),
        int(target.get("y")),
        int(target.get("height", target.get("h", 0)) or 0),
    )
    _walk, updated = walk_short(
        player,
        destination,
        args,
        handle,
        "cow_pen_gate_interaction_approach_" + reason,
        max_ticks=args.cow_gate_approach_ticks,
        max_distance=args.cow_gate_approach_distance,
    )
    return updated


def cross_lumbridge_cow_pen_gate(player, args, handle, reason):
    """Open the Lumbridge cow pen gate and immediately click through.

    The wooden gate opens as a temporary object transition. Observing or waiting
    after the click is too slow and lets the runner stand on the wrong side, so
    this method chains the open click directly into short inside-tile clicks and
    only then verifies the post-state.
    """
    player = ensure_run(player, args, handle, "cow_pen_gate_" + reason)
    if not near_lumbridge_cow_pen_gate(player):
        _walk, player = walk_short(
            player,
            (3252, 3266, 0),
            args,
            handle,
            "cow_pen_gate_approach_" + reason,
            max_ticks=args.cow_gate_approach_ticks,
            max_distance=args.cow_gate_approach_distance,
        )
    if in_lumbridge_cow_pen(player):
        return player

    for attempt in range(1, int(args.cow_gate_entry_attempts) + 1):
        gate = find_lumbridge_cow_pen_gate(handle, player)
        if gate is None:
            state, observed = observe_state()
            write_event(handle, "cow_pen_gate_missing", {
                "attempt": attempt,
                "reason": reason,
                "player": compact_player(observed),
            })
            if in_lumbridge_cow_pen(observed):
                return observed
            player = observed
            continue

        player = approach_gate_interaction_tile(gate, player, args, handle, reason)
        opened = call_tool("interact_object", {
            "objectId": int(gate.get("objectId", gate.get("id"))),
            "x": int(gate.get("x")),
            "y": int(gate.get("y")),
            "height": int(gate.get("height", gate.get("h", 0)) or 0),
            "option": "open",
        })
        player = player_from_or(opened, player)
        write_event(handle, "open_cow_pen_gate", {
            "attempt": attempt,
            "reason": reason,
            "success": bool(opened.get("success")),
            "message": opened.get("message"),
            "object": opened.get("object", gate),
            "player": compact_player(player),
        })
        if not opened.get("success"):
            continue
        if int(args.cow_gate_open_wait_ticks) > 0:
            waited = call_tool("wait_ticks", {"ticks": int(args.cow_gate_open_wait_ticks)})
            player = player_from_or(waited, player)

        destinations = horizontal_gate_steps(player, 3254)
        if not destinations:
            destinations = LUMBRIDGE_COW_PEN_ENTRY_TILES
        player = walk_gate_transition_steps(
            player,
            destinations,
            args,
            handle,
            "cow_pen_gate_cross_{}".format(attempt),
        )
        if in_lumbridge_cow_pen(player):
            write_event(handle, "cow_pen_gate_crossed", {
                "attempt": attempt,
                "destination": tile_from_player(player),
                "player": compact_player(player),
            })
            return player

        state, observed = observe_state()
        stop_if_unsafe(state, observed, args, handle, "cow_pen_gate_failed_attempt")
        if in_lumbridge_cow_pen(observed):
            write_event(handle, "cow_pen_gate_crossed_after_observe", {
                "attempt": attempt,
                "player": compact_player(observed),
            })
            return observed
        player = observed

    raise RunnerStop(
        "cow_pen_gate_failed",
        "Could not prove crossing into the Lumbridge cow pen after opening the gate.",
        player,
    )


def exit_lumbridge_cow_pen_gate(player, args, handle, reason):
    """Open the Lumbridge cow pen gate from inside and immediately click out."""
    if not in_lumbridge_cow_pen(player):
        return player
    player = ensure_run(player, args, handle, "cow_pen_gate_exit_" + reason)
    if not near_lumbridge_cow_pen_gate(player):
        _walk, player = walk_short(
            player,
            (3254, 3266, 0),
            args,
            handle,
            "cow_pen_gate_exit_approach_" + reason,
            max_ticks=args.cow_gate_approach_ticks,
            max_distance=args.cow_gate_approach_distance,
        )
    if not in_lumbridge_cow_pen(player):
        return player

    for attempt in range(1, int(args.cow_gate_entry_attempts) + 1):
        gate = find_lumbridge_cow_pen_gate(handle, player)
        if gate is None:
            state, observed = observe_state()
            stop_if_unsafe(state, observed, args, handle, "cow_pen_gate_exit_missing")
            if not in_lumbridge_cow_pen(observed):
                return observed
            player = observed
            continue

        player = approach_gate_interaction_tile(gate, player, args, handle, reason)
        opened = call_tool("interact_object", {
            "objectId": int(gate.get("objectId", gate.get("id"))),
            "x": int(gate.get("x")),
            "y": int(gate.get("y")),
            "height": int(gate.get("height", gate.get("h", 0)) or 0),
            "option": "open",
        })
        player = player_from_or(opened, player)
        write_event(handle, "open_cow_pen_gate_for_exit", {
            "attempt": attempt,
            "reason": reason,
            "success": bool(opened.get("success")),
            "message": opened.get("message"),
            "object": opened.get("object", gate),
            "player": compact_player(player),
        })
        if not opened.get("success"):
            continue
        if int(args.cow_gate_open_wait_ticks) > 0:
            waited = call_tool("wait_ticks", {"ticks": int(args.cow_gate_open_wait_ticks)})
            player = player_from_or(waited, player)

        destinations = horizontal_gate_steps(player, 3250)
        if not destinations:
            destinations = LUMBRIDGE_COW_PEN_EXIT_TILES
        player = walk_gate_transition_steps(
            player,
            destinations,
            args,
            handle,
            "cow_pen_gate_exit_{}".format(attempt),
        )
        if not in_lumbridge_cow_pen(player):
            write_event(handle, "cow_pen_gate_exited", {
                "attempt": attempt,
                "destination": tile_from_player(player),
                "player": compact_player(player),
            })
            return player

        state, observed = observe_state()
        stop_if_unsafe(state, observed, args, handle, "cow_pen_gate_exit_failed_attempt")
        if not in_lumbridge_cow_pen(observed):
            write_event(handle, "cow_pen_gate_exited_after_observe", {
                "attempt": attempt,
                "player": compact_player(observed),
            })
            return observed
        player = observed

    raise RunnerStop(
        "cow_pen_gate_exit_failed",
        "Could not prove crossing out of the Lumbridge cow pen after opening the gate.",
        player,
    )


def ensure_cow_area(player, args, handle, run_path, reason):
    if in_lumbridge_cow_training_pocket(player):
        npc = find_local_cow(player, args, handle, reason + "_local_precheck")
        if npc is not None:
            write_event(handle, "cow_area_local_ready", {
                "reason": reason,
                "npc": npc,
                "player": compact_player(player),
            })
            return {"success": True, "nearbyNpcs": [npc]}, player

    if not is_lumbridge_cow_pen_target(args.cow_area_target):
        return route_or_stop(args.cow_area_target, args, handle, reason, run_path, player)

    state, observed = observe_state()
    stop_if_unsafe(state, observed, args, handle, reason + "_observe")
    if in_lumbridge_cow_pen(observed):
        return state, observed
    player = observed

    if not near_lumbridge_cow_pen_gate(player):
        if on_al_kharid_side(player):
            player = cross_al_kharid_gate_to_lumbridge_side(player, args, handle, reason)
            state, player = observe_state()
            stop_if_unsafe(state, player, args, handle, reason + "_after_al_kharid_gate")
        state, player = route_or_stop(
            args.cow_gate_approach_target,
            args,
            handle,
            reason + "_gate_approach",
            run_path,
            player,
        )
        if in_lumbridge_cow_pen(player):
            return state, player

    player = cross_lumbridge_cow_pen_gate(player, args, handle, reason)
    state, player = observe_state()
    stop_if_unsafe(state, player, args, handle, reason + "_after_gate")
    if not in_lumbridge_cow_pen(player):
        raise RunnerStop("cow_pen_gate_failed", "Post-gate observation is still outside the cow pen.", player)
    return state, player


def choose_combat_style(player, args):
    attack = skill_level(player, "attack")
    strength = skill_level(player, "strength")
    defence = skill_level(player, "defence")

    attack_gate = min(STEEL_WEAPON_ATTACK_LEVEL, int(args.target_attack))
    defence_target = int(args.target_defence)
    balance_until = min(
        int(args.balance_attack_strength_until),
        int(args.target_attack),
        int(args.target_strength),
    )
    if attack < attack_gate:
        return "attack", "steel_weapon_attack_gate"
    if strength < min(EARLY_STYLE_LEVEL, int(args.target_strength)):
        return "strength", "early_strength"
    if defence < defence_target:
        return "defence", "defence_target"
    if attack < balance_until or strength < balance_until:
        if attack >= balance_until:
            return "strength", "balance_attack_strength_to_checkpoint"
        if strength >= balance_until:
            return "attack", "balance_attack_strength_to_checkpoint"
        return ("attack" if attack <= strength else "strength"), "balance_attack_strength"
    if attack < int(args.target_attack):
        return "attack", "post_balance_attack_target"
    if strength < int(args.target_strength):
        return "strength", "post_balance_strength_target"
    return None, "targets_reached"


def targets_reached(player, args):
    return (
        skill_level(player, "attack") >= int(args.target_attack)
        and skill_level(player, "strength") >= int(args.target_strength)
        and skill_level(player, "defence") >= int(args.target_defence)
    )


def ensure_combat_style(player, style, handle, reason):
    if not style:
        return player
    if str(player.get("combatStyle", "")).lower() == style:
        return player
    result = call_tool("set_combat_style", {"style": style})
    updated = player_from(result)
    write_event(handle, "set_combat_style", {
        "reason": reason,
        "style": style,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(updated),
    })
    return updated


def maybe_equip_best(player, handle, reason):
    if skill_level(player, "attack") < STEEL_WEAPON_ATTACK_LEVEL:
        return player
    result = call_tool("equip_best_items", {})
    updated = player_from(result)
    write_event(handle, "equip_best_items", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "equipped": result.get("equipped"),
        "equippedItems": result.get("equippedItems", []),
        "player": compact_player(updated),
    })
    return updated


def eat_if_needed(state, player, args, handle, reason, safety_checked=False):
    if not safety_checked:
        stop_if_unsafe(state, player, args, handle, reason)
    if int(player.get("hitpoints", 0) or 0) > int(args.eat_threshold):
        return player
    if inventory_food_count(player) <= 0:
        return player
    result = call_tool("eat_best_food", {
        "emergency": int(player.get("hitpoints", 0) or 0) <= int(args.retreat_threshold),
    })
    updated = player_from_or(result, player)
    write_event(handle, "eat_food", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "itemId": result.get("itemId"),
        "healed": result.get("healed"),
        "player": compact_player(updated),
    })
    return updated


def withdraw_coin_float(player, args, handle, run_path, reason):
    wanted = int(args.coin_float)
    if wanted <= 0 or inventory_coins(player) >= wanted or bank_coins(player) <= 0:
        return player
    if not bool(player.get("inBankArea", False)):
        _state, player = route_or_stop(args.bank_target, args, handle, "coin_float_bank_" + reason, run_path, player)
    amount = min(bank_coins(player), max(1, wanted - inventory_coins(player)))
    result = call_tool("withdraw_bank_items", {"itemId": COINS, "amount": amount})
    updated = player_from_or(result, player)
    write_event(handle, "withdraw_coin_float", {
        "reason": reason,
        "requestedAmount": amount,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(updated),
    })
    return updated


def prepare_bank_loadout(player, args, handle, run_path, reason, deposit_hides=False):
    if not bool(player.get("inBankArea", False)):
        return player

    deposit_ids = list(EXTRA_COW_TRIP_BANK_ITEM_IDS)
    if deposit_hides:
        deposit_ids.insert(0, COWHIDE)
    updated, summary = bridge.execute_bank_policy(
        player,
        profile=RUN_PROFILE,
        handle=handle,
        reason=reason,
        deposit_all_ids=deposit_ids,
        food_item_ids=[KEBAB],
        keep_food_count=int(args.food_target),
        coin_float=int(args.coin_float),
    )
    write_event(handle, "cow_trip_bank_policy", {
        "reason": reason,
        "depositHides": bool(deposit_hides),
        "actions": len(summary.get("actions", [])),
        "player": compact_player(updated),
    })
    return updated


def buy_kebabs_if_needed(player, args, handle, run_path, reason):
    if not args.buy_kebabs:
        return player
    food = inventory_food_count(player)
    if food >= int(args.min_food_before_fight):
        return player
    if int(player.get("freeInventorySlots", 0) or 0) <= 0:
        if cowhide_count(player) > 0:
            player = bank_hides(player, args, handle, run_path, "food_restock_inventory_full")
        else:
            raise RunnerStop("full_inventory", "Inventory is full before kebab restock and no hides can be banked.", player)
    player = withdraw_coin_float(player, args, handle, run_path, reason)
    deficit = max(0, int(args.food_target) - inventory_food_count(player))
    amount = min(deficit, int(player.get("freeInventorySlots", 0) or 0))
    if amount <= 0:
        return player
    affordable = inventory_coins(player) // max(1, int(args.kebab_price))
    amount = min(amount, affordable)
    if amount <= 0:
        raise RunnerStop("no_food_money", "No carried coins are available for kebabs.", player)
    _state, player = route_or_stop(args.kebab_shop_target, args, handle, "kebab_shop_" + reason, run_path, player)
    player = close_interfaces_if_needed(player, handle, "before_kebab_shop")
    opened = call_tool("open_nearest_shop", {"name": args.kebab_shop_name, "maxDistance": args.shop_max_distance})
    player = player_from_or(opened, player)
    write_event(handle, "open_kebab_shop", {
        "reason": reason,
        "success": bool(opened.get("success")),
        "message": opened.get("message"),
        "player": compact_player(player),
    })
    if not opened.get("success"):
        raise RunnerStop("kebab_shop_unavailable", "Could not open a nearby kebab shop.", player)
    bought = call_tool("buy_shop_item", {"itemId": KEBAB, "amount": amount})
    player = player_from_or(bought, player)
    write_event(handle, "buy_kebabs", {
        "reason": reason,
        "requestedAmount": amount,
        "bought": bought.get("bought", 0),
        "success": bool(bought.get("success")),
        "message": bought.get("message"),
        "player": compact_player(player),
    })
    if inventory_food_count(player) < int(args.min_food_before_fight) and int(bought.get("bought", 0) or 0) <= 0:
        player = close_interfaces_if_needed(player, handle, "after_failed_kebab_purchase")
        raise RunnerStop("kebab_purchase_failed", "Could not buy enough kebabs for the configured food minimum.", player)
    player = close_interfaces_if_needed(player, handle, "after_kebab_shop")
    return player


def should_bank(player, args):
    if cowhide_count(player) <= 0:
        return False
    if int(player.get("freeInventorySlots", 0) or 0) <= 0:
        return True
    if cowhide_count(player) >= int(args.bank_at_hides):
        return True
    return int(player.get("freeInventorySlots", 0) or 0) <= int(args.bank_when_free_slots_at_or_below)


def bank_hides(player, args, handle, run_path, reason):
    if cowhide_count(player) <= 0:
        return prepare_bank_loadout(player, args, handle, run_path, "bank_loadout_no_hides_" + reason)
    if not bool(player.get("inBankArea", False)):
        if is_lumbridge_cow_pen_target(args.cow_area_target) and in_lumbridge_cow_pen(player):
            player = exit_lumbridge_cow_pen_gate(player, args, handle, "bank_hides_" + reason)
        _state, player = route_or_stop(args.bank_target, args, handle, "bank_hides_" + reason, run_path, player)
    carried_hides = cowhide_count(player)
    updated = prepare_bank_loadout(player, args, handle, run_path, "bank_hides_" + reason, deposit_hides=True)
    deposited = max(0, carried_hides - cowhide_count(updated))
    write_event(handle, "bank_hides", {
        "reason": reason,
        "success": cowhide_count(updated) == 0,
        "depositedAmount": deposited,
        "player": compact_player(updated),
    })
    if carried_hides > 0 and cowhide_count(updated) > 0:
        raise RunnerStop("bank_failed", "Banking failed to deposit carried cowhides.", updated)
    log("banked cowhides x{}".format(deposited), args, force=True)
    return updated


def pickup_cowhides(player, args, handle, reason):
    picked_total = 0
    current = player
    for attempt in range(1, int(args.loot_attempts) + 1):
        if int(current.get("freeInventorySlots", 0) or 0) <= 0:
            break
        result = call_tool("pickup_ground_item", {
            "itemId": COWHIDE,
            "maxDistance": int(args.max_loot_distance),
        })
        current = player_from_or(result, current)
        picked = int(result.get("pickedUp", 0) or 0)
        picked_total += picked
        write_event(handle, "pickup_cowhide", {
            "reason": reason,
            "attempt": attempt,
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "pickedUp": picked,
            "groundItem": result.get("groundItem"),
            "player": compact_player(current),
        })
        if picked > 0:
            continue
        if not result.get("success"):
            break
        waited = call_tool("wait_ticks", {"ticks": int(args.loot_retry_ticks)})
        current = player_from_or(waited, current)
    if picked_total > 0:
        log("picked up cowhides x{}".format(picked_total), args)
    return current


def pickup_cowhide_once(player, args, handle, reason):
    if int(player.get("freeInventorySlots", 0) or 0) <= 0:
        return player, 0
    result = call_tool("pickup_ground_item", {
        "itemId": COWHIDE,
        "maxDistance": int(args.max_loot_distance),
    })
    updated = player_from_or(result, player)
    picked = int(result.get("pickedUp", 0) or 0)
    write_event(handle, "pickup_cowhide_once", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "pickedUp": picked,
        "groundItem": result.get("groundItem"),
        "player": compact_player(updated),
    })
    if picked > 0:
        log("picked up cowhides x{}".format(picked), args)
    return updated, picked


def find_local_cow(player, args, handle, reason):
    result = call_tool("find_training_npc", {
        "name": "Cow",
        "maxDistance": int(args.cow_scan_distance),
        "minHitpoints": 1,
        "maxNpcMaxHit": int(args.max_cow_hit),
        "reachable": True,
        "allowUnderAttack": False,
    })
    write_event(handle, "find_cow", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "candidateCount": len(result.get("candidates") or []),
        "player": compact_player(player),
    })
    if result.get("success") and isinstance(result.get("npc"), dict):
        return result["npc"]
    return None


def find_cow(player, args, handle, run_path):
    npc = find_local_cow(player, args, handle, "local")
    if npc is not None:
        return npc
    _state, player = ensure_cow_area(player, args, handle, run_path, "cow_area")
    result = call_tool("find_training_npc", {
        "name": "Cow",
        "maxDistance": int(args.cow_scan_distance),
        "minHitpoints": 1,
        "maxNpcMaxHit": int(args.max_cow_hit),
        "reachable": True,
        "allowUnderAttack": False,
    })
    write_event(handle, "find_cow_after_route", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "candidateCount": len(result.get("candidates") or []),
        "player": compact_player(player),
    })
    if result.get("success") and isinstance(result.get("npc"), dict):
        return result["npc"]
    raise RunnerStop("no_cow_target", "No reachable cow target was found near the cow area.", player)


def fight_one_cow(player, args, handle, run_path, cycle):
    style, style_reason = choose_combat_style(player, args)
    if style is None:
        write_event(handle, "target_reached", {"cycle": cycle, "player": compact_player(player)})
        return player, "target_reached"
    player = ensure_combat_style(player, style, handle, style_reason)
    player = maybe_equip_best(player, handle, "before_fight")
    before_style_xp = skill_xp(player, style)
    before_hitpoints_xp = skill_xp(player, "hitpoints")
    npc = find_cow(player, args, handle, run_path)
    attack = call_tool("attack_npc", {"npcIndex": int(npc["npcIndex"])})
    player = player_from_or(attack, player)
    write_event(handle, "attack_cow", {
        "cycle": cycle,
        "style": style,
        "styleReason": style_reason,
        "success": bool(attack.get("success")),
        "message": attack.get("message"),
        "npc": attack.get("npc", npc),
        "player": compact_player(player),
    })
    if not attack.get("success"):
        raise RunnerStop("attack_failed", "Could not attack the selected cow.", player)
    empty_idle_polls = 0
    last_known_cow = attack.get("npc", npc)
    for poll in range(1, int(args.fight_poll_attempts) + 1):
        started = time.monotonic()
        wait = call_tool("wait_ticks", {"ticks": int(args.fight_poll_ticks)})
        elapsed = round(time.monotonic() - started, 3)
        player = player_from(wait)
        gained_style_xp = skill_xp(player, style) - before_style_xp
        gained_hitpoints_xp = skill_xp(player, "hitpoints") - before_hitpoints_xp
        npc = active_combat_npc(wait, player)
        if is_cow_npc(npc):
            last_known_cow = npc
        safety_npc = stop_if_fight_poll_unsafe(
            wait,
            player,
            args,
            handle,
            "fight_poll",
            last_known_cow=last_known_cow,
            gained_xp=(gained_style_xp > 0 or gained_hitpoints_xp > 0),
        )
        if is_cow_npc(safety_npc):
            npc = safety_npc
            last_known_cow = safety_npc
        player = eat_if_needed(wait, player, args, handle, "fight_poll", safety_checked=True)

        before_hides = cowhide_count(player)
        player, picked = pickup_cowhide_once(player, args, handle, "fight_poll")
        if picked > 0:
            write_event(handle, "fight_resolved_by_hide", {
                "cycle": cycle,
                "style": style,
                "poll": poll,
                "elapsedSeconds": elapsed,
                "beforeHides": before_hides,
                "player": compact_player(player),
            })
            return player, "fought"

        in_combat = bool(player.get("isInCombat", False))
        write_event(handle, "fight_poll", {
            "cycle": cycle,
            "style": style,
            "poll": poll,
            "waitedTicks": wait.get("waitedTicks"),
            "elapsedSeconds": elapsed,
            "gainedStyleXp": gained_style_xp,
            "gainedHitpointsXp": gained_hitpoints_xp,
            "npc": npc,
            "player": compact_player(player),
        })

        if in_combat:
            if npc is None and (gained_style_xp > 0 or gained_hitpoints_xp > 0) and is_cow_npc(last_known_cow):
                empty_idle_polls += 1
                if empty_idle_polls >= int(args.post_xp_empty_polls):
                    cancelled = call_tool("cancel_current_action", {})
                    player = player_from_or(cancelled, player)
                    player, picked = pickup_cowhide_once(player, args, handle, "stale_combat_after_xp_cancel")
                    write_event(handle, "cancel_stale_cow_combat_after_xp", {
                        "cycle": cycle,
                        "style": style,
                        "poll": poll,
                        "gainedStyleXp": gained_style_xp,
                        "gainedHitpointsXp": gained_hitpoints_xp,
                        "pickedAfterCancel": picked,
                        "success": bool(cancelled.get("success")),
                        "message": cancelled.get("message"),
                        "player": compact_player(player),
                    })
                    return player, "fought_stale_cancelled_after_xp"
                continue
            if not is_cow_npc(npc):
                raise RunnerStop("unexpected_combat_target", "Player is in combat with a non-cow or unknown target.", player)
            empty_idle_polls = 0
            continue

        if gained_style_xp > 0 or gained_hitpoints_xp > 0:
            # Give ground-item visibility a short grace window before moving on.
            empty_idle_polls += 1
            if empty_idle_polls >= int(args.post_xp_empty_polls):
                return player, "fought_no_hide_seen"
            continue

        empty_idle_polls += 1
        if empty_idle_polls >= int(args.no_xp_idle_polls):
            raise RunnerStop("attack_stalled", "Cow attack produced no combat and no XP/drop evidence.", player)

    gained_style_xp = skill_xp(player, style) - before_style_xp
    gained_hitpoints_xp = skill_xp(player, "hitpoints") - before_hitpoints_xp
    if gained_style_xp > 0 or gained_hitpoints_xp > 0:
        cancelled = call_tool("cancel_current_action", {})
        player = player_from_or(cancelled, player)
        player, picked = pickup_cowhide_once(player, args, handle, "fight_poll_timeout_after_cancel")
        write_event(handle, "cancel_cow_combat_after_xp", {
            "cycle": cycle,
            "style": style,
            "gainedStyleXp": gained_style_xp,
            "gainedHitpointsXp": gained_hitpoints_xp,
            "pickedAfterCancel": picked,
            "success": bool(cancelled.get("success")),
            "message": cancelled.get("message"),
            "player": compact_player(player),
        })
        return player, "fought_cancelled_after_xp"
    raise RunnerStop("fight_timeout", "Cow fight produced no drop or XP before the configured poll limit.", player)


def run(args):
    global RUN_PROFILE
    RUN_PROFILE = args.profile or ""

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = run_path.open("a", encoding="utf-8")
    fights_done = 0
    cycles_done = 0
    stopped_reason = None
    try:
        write_event(handle, "run_start", {
            "args": jsonable(vars(args)),
            "runLog": str(run_path),
            "routeEvidencePath": route_evidence_path(args, run_path),
        })
        state, player = observe_state()
        write_event(handle, "observe", {"player": compact_player(player)})
        stop_if_unsafe(state, player, args, handle, "run_start")

        for cycle in range(1, int(args.max_cycles) + 1):
            cycles_done = cycle
            state, player = observe_state()
            stop_if_unsafe(state, player, args, handle, "cycle_start")
            player = eat_if_needed(state, player, args, handle, "cycle_start")
            if targets_reached(player, args):
                stopped_reason = "target_levels"
                write_event(handle, "target_reached", {"cycle": cycle, "player": compact_player(player)})
                break

            if int(player.get("freeInventorySlots", 0) or 0) <= 0:
                if args.stop_when_inventory_full:
                    stopped_reason = "inventory_full"
                    write_event(handle, "inventory_full_handoff", {"cycle": cycle, "player": compact_player(player)})
                    break
                if cowhide_count(player) > 0:
                    player = bank_hides(player, args, handle, run_path, "inventory_full")
                else:
                    raise RunnerStop("full_inventory", "Inventory is full and there are no cowhides to bank.", player)
            elif not args.stop_when_inventory_full and should_bank(player, args):
                player = bank_hides(player, args, handle, run_path, "bank_threshold")

            if bool(player.get("inBankArea", False)):
                player = prepare_bank_loadout(player, args, handle, run_path, "cycle_start")
            player = buy_kebabs_if_needed(player, args, handle, run_path, "before_fight")
            if targets_reached(player, args):
                stopped_reason = "target_levels"
                write_event(handle, "target_reached", {"cycle": cycle, "player": compact_player(player)})
                break

            _state, player = ensure_cow_area(player, args, handle, run_path, "cow_area_pre_fight")
            state, player = observe_state()
            stop_if_unsafe(state, player, args, handle, "before_fight")
            player = eat_if_needed(state, player, args, handle, "before_fight")
            player = pickup_cowhides(player, args, handle, "before_fight")
            if int(player.get("freeInventorySlots", 0) or 0) <= 0:
                if args.stop_when_inventory_full:
                    stopped_reason = "inventory_full"
                    write_event(handle, "inventory_full_handoff", {"cycle": cycle, "player": compact_player(player)})
                    break
                player = bank_hides(player, args, handle, run_path, "inventory_full_after_pre_fight_loot")

            before = compact_player(player)
            player, fight_status = fight_one_cow(player, args, handle, run_path, cycle)
            if fight_status == "target_reached":
                stopped_reason = "target_levels"
                break
            fights_done += 1
            player = pickup_cowhides(player, args, handle, "after_fight")
            after = compact_player(player)
            write_event(handle, "cycle_done", {
                "cycle": cycle,
                "fightStatus": fight_status,
                "before": before,
                "after": after,
            })
            log("cycle {} atk={} str={} def={} hp={}/{} hides={} food={} free={}".format(
                cycle,
                after["attackLevel"],
                after["strengthLevel"],
                after["defenceLevel"],
                after["hitpoints"],
                after["maxHitpoints"],
                after["cowhides"],
                after["inventoryFood"],
                after["freeSlots"],
            ), args)

        else:
            stopped_reason = "max_cycles"

        state, player = observe_state()
        if cowhide_count(player) > 0 and args.final_bank and not args.stop_when_inventory_full:
            player = bank_hides(player, args, handle, run_path, "final")
        write_event(handle, "run_finish", {
            "reason": stopped_reason or "complete",
            "cyclesDone": cycles_done,
            "fightsDone": fights_done,
            "player": compact_player(player),
            "runLog": str(run_path),
            "routeEvidencePath": route_evidence_path(args, run_path),
        })
        log("cowhide combat log: {}".format(run_path), args, force=True)
        return 0
    except RunnerStop as exc:
        stopped_reason = exc.reason
        write_event(handle, "blocked", {
            "reason": exc.reason,
            "message": exc.message,
            "cyclesDone": cycles_done,
            "fightsDone": fights_done,
            "player": compact_player(exc.player) if exc.player else {},
            "runLog": str(run_path),
            "routeEvidencePath": route_evidence_path(args, run_path),
        })
        log("blocked: {} ({})".format(exc.reason, exc.message), args, force=True)
        log("cowhide combat log: {}".format(run_path), args, force=True)
        return 2
    finally:
        handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run bounded cow combat, cowhide pickup, and banking.")
    parser.add_argument("--profile", default="", help="Bridge profile/session to use. Defaults to the active session.")
    parser.add_argument("--target-attack", type=int, default=20)
    parser.add_argument("--target-strength", type=int, default=20)
    parser.add_argument("--target-defence", type=int, default=5)
    parser.add_argument("--balance-attack-strength-until", type=int, default=15,
                        help="After early gear/defence goals, balance Attack and Strength up to this level, then finish Attack before Strength.")
    parser.add_argument("--bank-target", default="al_kharid_bank", help="route_runner target for hide banking.")
    parser.add_argument("--cow-area-target", default="lumbridge_cow_pen", help="route_runner target for cow combat.")
    parser.add_argument("--cow-gate-approach-target", default="3252,3266,0",
                        help="West-side approach tile for the Lumbridge cow pen gate.")
    parser.add_argument("--cow-gate-entry-attempts", type=int, default=2)
    parser.add_argument("--cow-gate-approach-ticks", type=int, default=30)
    parser.add_argument("--cow-gate-approach-distance", type=int, default=24)
    parser.add_argument("--cow-gate-cross-ticks", type=int, default=8)
    parser.add_argument("--cow-gate-cross-distance", type=int, default=8)
    parser.add_argument("--cow-gate-open-wait-ticks", type=int, default=0,
                        help="Optional wait after a gate open click. Default 0 keeps timed gates fast.")
    parser.add_argument("--kebab-shop-target", default="al_kharid_kebab_shop")
    parser.add_argument("--eat-threshold", type=int, default=8)
    parser.add_argument("--retreat-threshold", type=int, default=5)
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--max-fight-ticks", type=int, default=80,
                        help="Legacy timeout hint; the runner now uses short fight poll ticks for fast looting.")
    parser.add_argument("--fight-poll-ticks", type=int, default=1,
                        help="Ticks between combat/drop checks while fighting a cow.")
    parser.add_argument("--fight-poll-attempts", type=int, default=120,
                        help="Maximum short poll attempts before treating a cow fight as stalled.")
    parser.add_argument("--post-xp-empty-polls", type=int, default=3,
                        help="Short no-hide grace polls after combat XP before moving on.")
    parser.add_argument("--no-xp-idle-polls", type=int, default=3,
                        help="Short idle polls allowed after attack if no combat XP or drop appears.")
    parser.add_argument("--max-loot-distance", type=int, default=12)
    parser.add_argument("--loot-attempts", type=int, default=6)
    parser.add_argument("--loot-retry-ticks", type=int, default=1,
                        help="Ticks to wait between repeated cowhide pickup attempts after a queued pickup.")
    parser.add_argument("--bank-at-hides", type=int, default=20)
    parser.add_argument("--bank-when-free-slots-at-or-below", type=int, default=2)
    parser.add_argument("--stop-when-inventory-full", action=argparse.BooleanOptionalAction, default=False,
                        help="Stop and hand control back when inventory fills instead of banking hides.")
    parser.add_argument("--final-bank", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--buy-kebabs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--food-target", type=int, default=3)
    parser.add_argument("--min-food-before-fight", type=int, default=1)
    parser.add_argument("--kebab-price", type=int, default=3)
    parser.add_argument("--coin-float", type=int, default=100)
    parser.add_argument("--kebab-shop-name", default="kebab")
    parser.add_argument("--shop-max-distance", type=int, default=8)
    parser.add_argument("--cow-scan-distance", type=int, default=24)
    parser.add_argument("--max-cow-hit", type=int, default=1)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--route-max-batches", type=int, default=60)
    parser.add_argument("--route-max-walk-distance", type=int, default=80)
    parser.add_argument("--route-max-batch-distance", type=int, default=48)
    parser.add_argument("--route-max-ticks", type=int, default=180)
    parser.add_argument("--evidence-jsonl", help="Optional route_runner evidence JSONL path.")
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args(argv)

    for name in ("target_attack", "target_strength", "target_defence"):
        if int(getattr(args, name)) < 1:
            parser.error("--{} must be at least 1".format(name.replace("_", "-")))
    if int(args.fight_poll_ticks) < 1 or int(args.fight_poll_ticks) > 25:
        parser.error("--fight-poll-ticks must be between 1 and 25")
    if int(args.fight_poll_attempts) < 1:
        parser.error("--fight-poll-attempts must be at least 1")
    if args.retreat_threshold > args.eat_threshold:
        parser.error("--retreat-threshold must be less than or equal to --eat-threshold")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
