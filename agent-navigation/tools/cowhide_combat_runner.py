#!/usr/bin/env python3
"""Bounded cow combat and cowhide banking runner.

This keeps early cow combat, hide pickup, kebab restocking, and bank trips out
of the AI token loop. It uses normal bridge gameplay only: all game actions go
through rs-tool.sh, and travel goes through ML1 route definitions.
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
RUNS_DIR = ROOT / "data" / "combat" / "runs"
RUNNER_CONTROL_DIR = ROOT / ".local" / "runners"
RUNNER_CONTROL_NAME = "cowhide-combat"
RUN_PROFILE = ""

COWHIDE = 1739
COINS = 995
KEBAB = 1971
BRONZE_SCIMITAR = 1321
IRON_SCIMITAR = 1323
STEEL_SCIMITAR = 1325
MITHRIL_SCIMITAR = 1329
STEEL_WEAPON_ATTACK_LEVEL = 5
MITHRIL_SCIMITAR_ATTACK_LEVEL = 20
EARLY_STYLE_LEVEL = 5
EXTRA_COW_TRIP_BANK_ITEM_IDS = (IRON_SCIMITAR,)  # Iron scimitar; steel scimitar is equipped once attack is 5.
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
    (3250, 3266, 0),  # clear outside anchor for ML1 routing
)
AL_KHARID_GATE_WEST_TILE = (3267, 3227, 0)
AL_KHARID_GATE_EAST_TILE = (3268, 3227, 0)
AL_KHARID_GATE_DIALOGUE_IDS = {1019, 1020, 1024, 1026, 1027}
AL_KHARID_GATE_DIALOGUE_ACTIONS = {502, 508}
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


def same_tile(player, destination):
    x, y, h = destination
    return player_x(player) == int(x) and player_y(player) == int(y) and player_h(player) == int(h)


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


def is_al_kharid_bank_target(target):
    normalized = str(target or "").strip().lower().replace("_", " ")
    return normalized in {"al kharid bank", "al_kharid_bank", "3269,3167,0", "3270,3167,0"}


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


def equipment_has_item(player, item_id):
    target = int(item_id)
    for item in equipment(player):
        try:
            current = int(item.get("id", item.get("itemId", -1)) or -1)
        except (TypeError, ValueError):
            current = -1
        if current == target:
            return True
    return False


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
        "nextChat": int(player.get("nextChat", 0) or 0),
        "dialogueAction": int(player.get("dialogueAction", 0) or 0),
        "talkingNpc": int(player.get("talkingNpc", -1) or -1),
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


def runner_profile_label(args):
    profile = (getattr(args, "profile", "") or os.environ.get("RS_PROFILE", "")).strip()
    return profile or "default"


def runner_control_stem(args):
    profile = runner_profile_label(args)
    if profile == "default":
        return RUNNER_CONTROL_NAME
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in profile).strip("-")
    return "{}-{}".format(RUNNER_CONTROL_NAME, slug or "profile")


def runner_status_path(args):
    return RUNNER_CONTROL_DIR / "{}.status.json".format(runner_control_stem(args))


def runner_primary_stop_path(args):
    return RUNNER_CONTROL_DIR / "{}.stop".format(runner_control_stem(args))


def runner_stop_paths(args):
    paths = [runner_primary_stop_path(args)]
    if runner_profile_label(args) != "default":
        paths.append(RUNNER_CONTROL_DIR / "{}.stop".format(RUNNER_CONTROL_NAME))
    return paths


def runner_stop_requested(args):
    return any(path.exists() for path in runner_stop_paths(args))


def existing_runner_stop_paths(args):
    return [str(path) for path in runner_stop_paths(args) if path.exists()]


def clear_runner_stop_requests(args):
    cleared = []
    for path in runner_stop_paths(args):
        try:
            path.unlink()
            cleared.append(str(path))
        except FileNotFoundError:
            continue
    return cleared


def request_runner_stop(args):
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    paths = [runner_primary_stop_path(args)]
    if runner_profile_label(args) != "default":
        paths.append(RUNNER_CONTROL_DIR / "{}.stop".format(RUNNER_CONTROL_NAME))
    payload = {
        "runner": "cowhide_combat_runner",
        "profile": runner_profile_label(args),
        "requestedAt": utc_now(),
        "pid": os.getpid(),
    }
    for path in paths:
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "runner": "cowhide_combat_runner",
        "profile": runner_profile_label(args),
        "stopRequests": [str(path) for path in paths],
    }, sort_keys=True))
    return 0


def print_runner_status(args):
    path = runner_status_path(args)
    payload = {
        "ok": path.exists(),
        "runner": "cowhide_combat_runner",
        "profile": runner_profile_label(args),
        "statusPath": str(path),
        "stopRequested": runner_stop_requested(args),
        "stopFiles": existing_runner_stop_paths(args),
    }
    if path.exists():
        try:
            payload["status"] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            payload["ok"] = False
            payload["error"] = str(exc)
    elif runner_profile_label(args) == "default":
        payload["knownStatusPaths"] = [
            str(item) for item in sorted(RUNNER_CONTROL_DIR.glob("{}*.status.json".format(RUNNER_CONTROL_NAME)))
        ] if RUNNER_CONTROL_DIR.exists() else []
    print(json.dumps(payload, sort_keys=True))
    return 1 if payload.get("error") else 0


def runner_args_summary(args):
    keys = (
        "profile",
        "target_attack",
        "target_strength",
        "target_defence",
        "max_cycles",
        "bank_target",
        "cow_area_target",
        "bank_at_hides",
        "stop_when_inventory_full",
        "final_bank",
        "auto_buy_mithril_scimitar",
        "quiet",
    )
    return {key: jsonable(getattr(args, key, None)) for key in keys}


def write_runner_status(args, status, run_path=None, reason=None, cycle=None, fights_done=None, player=None, extra=None):
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "runner": "cowhide_combat_runner",
        "profile": runner_profile_label(args),
        "status": status,
        "reason": reason,
        "pid": os.getpid(),
        "updatedAt": utc_now(),
        "args": runner_args_summary(args),
        "stopRequested": runner_stop_requested(args),
        "stopFiles": existing_runner_stop_paths(args),
    }
    if run_path is not None:
        payload["runLog"] = str(run_path)
        payload["routeEvidencePath"] = route_evidence_path(args, run_path)
    if cycle is not None:
        payload["cycle"] = cycle
    if fights_done is not None:
        payload["fightsDone"] = fights_done
    if player is not None:
        payload["player"] = compact_player(player)
    if extra:
        payload.update(extra)
    path = runner_status_path(args)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def safe_stop_requested(args, handle, phase, cycle, player):
    if not runner_stop_requested(args):
        return False
    compact = compact_player(player)
    if compact["isInCombat"] or compact["isMoving"]:
        write_event(handle, "stop_request_deferred", {
            "phase": phase,
            "cycle": cycle,
            "stopFiles": existing_runner_stop_paths(args),
            "player": compact,
        })
        return False
    write_event(handle, "stop_requested", {
        "phase": phase,
        "cycle": cycle,
        "stopFiles": existing_runner_stop_paths(args),
        "player": compact,
    })
    return True


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
    write_event(handle, "route_start", {
        "reason": reason,
        "target": target,
        "method": "ml1_route_definition",
        "routeEvidencePath": evidence_path,
    })
    extra_args = {
        "runner_max_batches": int(args.route_max_batches),
        "max_batch_distance": int(args.route_max_batch_distance),
        "max_walk_distance": int(args.route_max_walk_distance),
        "max_ticks": int(args.route_max_ticks),
        "run_mode": "auto",
        "eat_at": int(args.eat_threshold),
        "stop_on_combat": True,
        "evidence_jsonl": evidence_path,
    }
    error = ""
    try:
        bridge.route_to(target, profile=RUN_PROFILE, handle=handle, reason=reason, extra_args=extra_args)
        success = True
    except Exception as exc:
        success = False
        error = str(exc)
    write_event(handle, "route_done", {
        "reason": reason,
        "target": target,
        "success": success,
        "error": error[:1200],
        "routeEvidencePath": evidence_path,
    })
    if not success:
        fallback = bridge_landmark_fallback(target) if bool(getattr(args, "allow_java_landmark_fallback", False)) else None
        if fallback:
            log("route failed target={} reason={}; trying bridge landmark {}".format(target, reason, fallback), args, force=True)
            return travel_to_bridge_landmark(fallback, args, handle, reason, target)
        if bridge_landmark_fallback(target):
            write_event(handle, "bridge_landmark_fallback_skipped", {
                "reason": reason,
                "target": target,
                "message": "Java landmark fallback disabled; ML1/script primitives must handle this leg.",
            })
        log("route failed target={} reason={}".format(target, reason), args, force=True)
        return False
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
        raise RunnerStop("no_route", "ML1 routing failed while routing to {} for {}.".format(target, reason), player)
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


def route_to_al_kharid_gate_tile(player, destination, args, handle, run_path, reason):
    if same_tile(player, destination):
        return player
    target = "{},{},{}".format(int(destination[0]), int(destination[1]), int(destination[2]))
    _state, player = route_or_stop(target, args, handle, reason + "_route", run_path, player)
    if same_tile(player, destination):
        return player
    _walk, player = walk_short(
        player,
        destination,
        args,
        handle,
        reason + "_exact_tile",
        max_ticks=max(24, int(args.cow_gate_approach_ticks)),
        max_distance=max(12, int(args.cow_gate_approach_distance)),
    )
    return player


def al_kharid_gate_object_for_player(player):
    found = call_tool("find_nearest_object", {"name": "gate", "maxDistance": 4})
    gate = found.get("object") if isinstance(found, dict) else None
    if isinstance(gate, dict):
        try:
            object_id = int(gate.get("objectId", gate.get("id", -1)))
            x = int(gate.get("x"))
            y = int(gate.get("y"))
            h = int(gate.get("height", gate.get("h", 0)) or 0)
        except (TypeError, ValueError):
            object_id = -1
            x = y = h = 0
        if object_id in (2882, 2883) and h == player_h(player) and 3267 <= x <= 3268 and y in (3227, 3228):
            return {
                "objectId": object_id,
                "x": x,
                "y": y,
                "height": h,
            }
    y = player_y(player)
    return {
        "objectId": 2883 if y == 3228 else 2882,
        "x": 3268,
        "y": y,
        "height": player_h(player),
    }


def al_kharid_gate_dialogue_active(player):
    try:
        next_chat = int(player.get("nextChat", 0) or 0)
        dialogue_action = int(player.get("dialogueAction", 0) or 0)
    except (TypeError, ValueError):
        return False
    return (
        next_chat in AL_KHARID_GATE_DIALOGUE_IDS
        or (dialogue_action == 502 and next_chat == 1020)
        or (dialogue_action == 508 and next_chat == 1024)
    )


def al_kharid_gate_crossed(player, to_bank_side):
    return on_al_kharid_side(player) if to_bank_side else not on_al_kharid_side(player)


def advance_al_kharid_gate_dialogue(player):
    next_chat = int(player.get("nextChat", 0) or 0)
    dialogue_action = int(player.get("dialogueAction", 0) or 0)
    if next_chat in (1026, 1027):
        return "continue_dialogue", call_tool("continue_dialogue", {})
    if (dialogue_action == 502 and next_chat == 1020) or (dialogue_action == 508 and next_chat == 1024):
        return "select_dialogue_option", call_tool("select_dialogue_option", {"option": 1})
    if next_chat in AL_KHARID_GATE_DIALOGUE_IDS:
        return "continue_dialogue", call_tool("continue_dialogue", {})
    return "none", {"success": False, "message": "No Al Kharid gate dialogue is active.", "player": player}


def cross_al_kharid_gate_with_primitives(player, args, handle, reason, run_path, to_bank_side):
    approach = AL_KHARID_GATE_WEST_TILE if to_bank_side else AL_KHARID_GATE_EAST_TILE
    direction = "east" if to_bank_side else "west"
    player = ensure_run(player, args, handle, "al_kharid_gate_" + direction + "_" + reason)
    player = route_to_al_kharid_gate_tile(player, approach, args, handle, run_path, "al_kharid_gate_" + direction + "_" + reason)
    try:
        player = bridge.cross_al_kharid_toll_gate(
            player,
            to_east=to_bank_side,
            profile=RUN_PROFILE,
            handle=handle,
            reason=reason,
            attempts=int(args.al_kharid_gate_attempts),
            dialogue_steps=int(args.al_kharid_gate_dialogue_steps),
            approach_max_ticks=max(24, int(args.cow_gate_approach_ticks)),
            approach_max_walk_distance=max(12, int(args.cow_gate_approach_distance)),
            min_run_energy=int(args.min_run_energy),
            compact_player_fn=compact_player,
        )
    except bridge.ObjectTransitionError as exc:
        raise RunnerStop(exc.reason, exc.message, exc.player)
    state, observed = observe_state()
    stop_if_unsafe(state, observed, args, handle, "al_kharid_gate_" + direction + "_after_cross")
    if not al_kharid_gate_crossed(observed, to_bank_side):
        raise RunnerStop("al_kharid_gate_cross_failed", "Could not prove crossing {} through the Al Kharid gate.".format(direction), observed)
    return close_interfaces_if_needed(observed, handle, "after_al_kharid_gate_" + direction)


def cross_al_kharid_gate_to_lumbridge_side(player, args, handle, reason, run_path):
    if not on_al_kharid_side(player):
        return player
    return cross_al_kharid_gate_with_primitives(player, args, handle, reason, run_path, to_bank_side=False)


def cross_al_kharid_gate_to_bank_side(player, args, handle, reason, run_path):
    if on_al_kharid_side(player):
        return player
    return cross_al_kharid_gate_with_primitives(player, args, handle, reason, run_path, to_bank_side=True)


def route_to_al_kharid_bank_for_cow_trip(player, args, handle, run_path, reason):
    if bool(player.get("inBankArea", False)):
        return player
    if in_lumbridge_cow_pen(player):
        player = exit_lumbridge_cow_pen_gate(player, args, handle, "bank_hides_" + reason)
    if not on_al_kharid_side(player):
        player = cross_al_kharid_gate_to_bank_side(player, args, handle, reason, run_path)
    if bool(player.get("inBankArea", False)):
        return player
    _state, player = route_or_stop(args.bank_target, args, handle, "al_kharid_bank_" + reason, run_path, player)
    return player


def cow_gate_transition_steps(player, destination_x, gate_x=3253, gate_y=3266):
    if player_h(player) != 0:
        return []
    current_x = player_x(player)
    current_y = player_y(player)
    destination_x = int(destination_x)
    gate_x = int(gate_x)
    gate_y = int(gate_y)
    if current_x == destination_x and current_y == gate_y:
        return []

    steps = []
    if current_y != gate_y:
        if current_x != gate_x or abs(current_y - gate_y) != 1:
            return []
        steps.append((gate_x, gate_y, 0))
        current_x = gate_x
        current_y = gate_y

    if current_x == destination_x:
        return steps
    direction = 1 if destination_x > current_x else -1
    steps.extend((x, gate_y, 0) for x in range(current_x + direction, destination_x + direction, direction))
    return steps


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

        destinations = cow_gate_transition_steps(player, 3254)
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

        destinations = cow_gate_transition_steps(player, 3250)
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
            player = cross_al_kharid_gate_to_lumbridge_side(player, args, handle, reason, run_path)
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
    if defence < min(defence_target, EARLY_STYLE_LEVEL):
        return "defence", "defence_target"
    if attack < balance_until or strength < balance_until:
        if attack >= balance_until:
            return "strength", "balance_attack_strength_to_checkpoint"
        if strength >= balance_until:
            return "attack", "balance_attack_strength_to_checkpoint"
        return ("attack" if attack <= strength else "strength"), "balance_attack_strength"
    attack_before_all = min(int(args.attack_before_balanced_all), int(args.target_attack))
    if attack < attack_before_all:
        return "attack", "post_balance_attack_target"
    if bool(args.balance_all_after_attack_checkpoint):
        candidates = []
        for style, level, target in (
            ("attack", attack, int(args.target_attack)),
            ("strength", strength, int(args.target_strength)),
            ("defence", defence, defence_target),
        ):
            if level < target:
                candidates.append((level, {"strength": 0, "attack": 1, "defence": 2}[style], style))
        if candidates:
            level, _priority, style = min(candidates)
            return style, "balance_all_lowest_level_{}".format(level)
    if attack < int(args.target_attack):
        return "attack", "post_balance_attack_target"
    if strength < int(args.target_strength):
        return "strength", "post_balance_strength_target"
    if defence < defence_target:
        return "defence", "post_balance_defence_target"
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
    attack = skill_level(player, "attack")
    candidates = (
        (MITHRIL_SCIMITAR, MITHRIL_SCIMITAR_ATTACK_LEVEL, "mithril_scimitar"),
        (STEEL_SCIMITAR, STEEL_WEAPON_ATTACK_LEVEL, "steel_scimitar"),
        (IRON_SCIMITAR, 1, "iron_scimitar"),
        (BRONZE_SCIMITAR, 1, "bronze_scimitar"),
    )
    for item_id, required_attack, label in candidates:
        if attack < required_attack or equipment_has_item(player, item_id) or count_inventory_item(player, item_id) <= 0:
            continue
        result = call_tool("equip_item", {"itemId": int(item_id)})
        updated = player_from_or(result, player)
        write_event(handle, "equip_known_upgrade", {
            "reason": reason,
            "itemId": int(item_id),
            "label": label,
            "requiredAttack": int(required_attack),
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact_player(updated),
        })
        return updated
    write_event(handle, "equip_known_upgrade_skipped", {
        "reason": reason,
        "attack": attack,
        "player": compact_player(player),
    })
    return player


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


def equip_inventory_item(player, item_id, args, handle, reason):
    result = call_tool("equip_item", {"itemId": int(item_id)})
    updated = player_from_or(result, player)
    write_event(handle, "equip_item", {
        "reason": reason,
        "itemId": int(item_id),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(updated),
    })
    if not result.get("success"):
        raise RunnerStop("equip_item_failed", "Could not equip item {} for {}.".format(item_id, reason), updated)
    return updated


def route_to_bank_for_upgrade(player, args, handle, run_path, reason):
    if bool(player.get("inBankArea", False)):
        return player
    if is_lumbridge_cow_pen_target(args.cow_area_target) and is_al_kharid_bank_target(args.bank_target):
        return route_to_al_kharid_bank_for_cow_trip(player, args, handle, run_path, reason)
    _state, player = route_or_stop(args.bank_target, args, handle, reason, run_path, player)
    return player


def ensure_mithril_scimitar_upgrade(player, args, handle, run_path, reason):
    if not bool(args.auto_buy_mithril_scimitar):
        return player
    if skill_level(player, "attack") < MITHRIL_SCIMITAR_ATTACK_LEVEL:
        return player
    if equipment_has_item(player, MITHRIL_SCIMITAR):
        return player

    if count_inventory_item(player, MITHRIL_SCIMITAR) > 0:
        return equip_inventory_item(player, MITHRIL_SCIMITAR, args, handle, "mithril_scimitar_inventory_" + reason)

    if count_bank_item(player, MITHRIL_SCIMITAR) > 0:
        player = route_to_bank_for_upgrade(player, args, handle, run_path, "mithril_scimitar_bank_" + reason)
        withdrawn = call_tool("withdraw_bank_items", {"itemId": MITHRIL_SCIMITAR, "amount": 1})
        player = player_from_or(withdrawn, player)
        write_event(handle, "withdraw_mithril_scimitar", {
            "reason": reason,
            "success": bool(withdrawn.get("success")),
            "message": withdrawn.get("message"),
            "withdrawnAmount": withdrawn.get("withdrawnAmount"),
            "player": compact_player(player),
        })
        if count_inventory_item(player, MITHRIL_SCIMITAR) <= 0:
            raise RunnerStop("mithril_scimitar_withdraw_failed", "Mithril scimitar was banked but could not be withdrawn.", player)
        return equip_inventory_item(player, MITHRIL_SCIMITAR, args, handle, "mithril_scimitar_bank_" + reason)

    if inventory_coins(player) < int(args.mithril_scimitar_coin_budget):
        player = route_to_bank_for_upgrade(player, args, handle, run_path, "mithril_scimitar_coins_" + reason)
        player = prepare_bank_loadout(player, args, handle, run_path, "mithril_scimitar_pre_buy_loadout")
        need = max(0, int(args.mithril_scimitar_coin_budget) - inventory_coins(player))
        if need > 0:
            withdrawn = call_tool("withdraw_bank_items", {"itemId": COINS, "amount": need})
            player = player_from_or(withdrawn, player)
            write_event(handle, "withdraw_mithril_scimitar_coins", {
                "reason": reason,
                "requestedAmount": need,
                "success": bool(withdrawn.get("success")),
                "message": withdrawn.get("message"),
                "withdrawnAmount": withdrawn.get("withdrawnAmount"),
                "player": compact_player(player),
            })
        if inventory_coins(player) < int(args.mithril_scimitar_coin_budget):
            raise RunnerStop("mithril_scimitar_coins_missing", "Could not withdraw enough coins for a Mithril scimitar.", player)

    if int(player.get("freeInventorySlots", 0) or 0) <= 0:
        player = route_to_bank_for_upgrade(player, args, handle, run_path, "mithril_scimitar_space_" + reason)
        player = prepare_bank_loadout(player, args, handle, run_path, "mithril_scimitar_inventory_space")
        if int(player.get("freeInventorySlots", 0) or 0) <= 0:
            raise RunnerStop("mithril_scimitar_inventory_full", "No inventory slot available to buy a Mithril scimitar.", player)

    _state, player = route_or_stop(args.mithril_scimitar_shop_target, args, handle, "mithril_scimitar_shop_" + reason, run_path, player)
    player = close_interfaces_if_needed(player, handle, "before_mithril_scimitar_shop")
    opened = call_tool("open_nearest_shop", {"name": args.mithril_scimitar_shop_name, "maxDistance": args.shop_max_distance})
    player = player_from_or(opened, player)
    shop = (opened.get("player") or {}).get("shop") or {}
    write_event(handle, "open_mithril_scimitar_shop", {
        "reason": reason,
        "success": bool(opened.get("success")),
        "message": opened.get("message"),
        "shop": shop,
        "player": compact_player(player),
    })
    if not opened.get("success"):
        raise RunnerStop("mithril_scimitar_shop_unavailable", "Could not open a nearby scimitar shop.", player)

    bought = call_tool("buy_shop_item", {"itemId": MITHRIL_SCIMITAR, "amount": 1})
    player = player_from_or(bought, player)
    write_event(handle, "buy_mithril_scimitar", {
        "reason": reason,
        "success": bool(bought.get("success")),
        "message": bought.get("message"),
        "bought": bought.get("bought", 0),
        "player": compact_player(player),
    })
    player = close_interfaces_if_needed(player, handle, "after_mithril_scimitar_shop")
    if count_inventory_item(player, MITHRIL_SCIMITAR) <= 0 and not equipment_has_item(player, MITHRIL_SCIMITAR):
        raise RunnerStop("mithril_scimitar_purchase_failed", "Could not buy a Mithril scimitar.", player)
    if not equipment_has_item(player, MITHRIL_SCIMITAR):
        player = equip_inventory_item(player, MITHRIL_SCIMITAR, args, handle, "mithril_scimitar_bought_" + reason)

    if is_al_kharid_bank_target(args.bank_target):
        _state, player = route_or_stop(args.bank_target, args, handle, "mithril_scimitar_post_buy_bank", run_path, player)
        player = prepare_bank_loadout(player, args, handle, run_path, "mithril_scimitar_post_buy_loadout")
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
        if is_lumbridge_cow_pen_target(args.cow_area_target) and is_al_kharid_bank_target(args.bank_target):
            player = route_to_al_kharid_bank_for_cow_trip(player, args, handle, run_path, "bank_hides_" + reason)
        else:
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
    cleared_stop_requests = clear_runner_stop_requests(args)
    try:
        write_event(handle, "run_start", {
            "args": jsonable(vars(args)),
            "runLog": str(run_path),
            "routeEvidencePath": route_evidence_path(args, run_path),
            "clearedStopRequests": cleared_stop_requests,
        })
        write_runner_status(args, "running", run_path=run_path, reason="started", extra={
            "startedAt": utc_now(),
            "clearedStopRequests": cleared_stop_requests,
        })
        state, player = observe_state()
        write_event(handle, "observe", {"player": compact_player(player)})
        write_runner_status(args, "running", run_path=run_path, reason="observed_start", player=player)
        stop_if_unsafe(state, player, args, handle, "run_start")

        for cycle in range(1, int(args.max_cycles) + 1):
            cycles_done = cycle
            state, player = observe_state()
            write_runner_status(
                args,
                "running",
                run_path=run_path,
                reason="cycle_start",
                cycle=cycle,
                fights_done=fights_done,
                player=player,
            )
            if safe_stop_requested(args, handle, "cycle_start", cycle, player):
                stopped_reason = "stop_requested"
                break
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
            player = ensure_mithril_scimitar_upgrade(player, args, handle, run_path, "cycle_start")
            player = buy_kebabs_if_needed(player, args, handle, run_path, "before_fight")
            if targets_reached(player, args):
                stopped_reason = "target_levels"
                write_event(handle, "target_reached", {"cycle": cycle, "player": compact_player(player)})
                break

            _state, player = ensure_cow_area(player, args, handle, run_path, "cow_area_pre_fight")
            state, player = observe_state()
            stop_if_unsafe(state, player, args, handle, "before_fight")
            player = eat_if_needed(state, player, args, handle, "before_fight")
            pre_fight_interval = int(args.pre_fight_loot_interval)
            if cycle == 1 or (pre_fight_interval > 0 and cycle % pre_fight_interval == 0):
                player = pickup_cowhides(player, args, handle, "before_fight")
            else:
                write_event(handle, "pickup_cowhide_sweep_skipped", {
                    "reason": "before_fight",
                    "cycle": cycle,
                    "preFightLootInterval": pre_fight_interval,
                    "player": compact_player(player),
                })
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
            if fight_status == "fought":
                write_event(handle, "pickup_cowhide_sweep_skipped", {
                    "reason": "after_fight_already_picked",
                    "cycle": cycle,
                    "fightStatus": fight_status,
                    "player": compact_player(player),
                })
            else:
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
            write_runner_status(
                args,
                "running",
                run_path=run_path,
                reason="cycle_done",
                cycle=cycle,
                fights_done=fights_done,
                player=player,
            )
            if safe_stop_requested(args, handle, "cycle_done", cycle, player):
                stopped_reason = "stop_requested"
                break

        else:
            stopped_reason = "max_cycles"

        state, player = observe_state()
        if cowhide_count(player) > 0 and args.final_bank and not args.stop_when_inventory_full and stopped_reason != "stop_requested":
            player = bank_hides(player, args, handle, run_path, "final")
        write_event(handle, "run_finish", {
            "reason": stopped_reason or "complete",
            "cyclesDone": cycles_done,
            "fightsDone": fights_done,
            "player": compact_player(player),
            "runLog": str(run_path),
            "routeEvidencePath": route_evidence_path(args, run_path),
        })
        write_runner_status(
            args,
            "finished",
            run_path=run_path,
            reason=stopped_reason or "complete",
            cycle=cycles_done,
            fights_done=fights_done,
            player=player,
        )
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
        write_runner_status(
            args,
            "blocked",
            run_path=run_path,
            reason=exc.reason,
            cycle=cycles_done,
            fights_done=fights_done,
            player=exc.player,
            extra={"message": exc.message},
        )
        log("blocked: {} ({})".format(exc.reason, exc.message), args, force=True)
        log("cowhide combat log: {}".format(run_path), args, force=True)
        return 2
    finally:
        handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run bounded cow combat, cowhide pickup, and banking.")
    parser.add_argument("--profile", default="", help="Bridge profile/session to use. Defaults to the active session.")
    parser.add_argument("--status", action="store_true",
                        help="Print this runner's cooperative status file and exit without touching the game.")
    parser.add_argument("--request-stop", action="store_true",
                        help="Ask a running cowhide runner to stop at the next safe non-combat boundary.")
    parser.add_argument("--clear-stop", action="store_true",
                        help="Clear this runner's pending cooperative stop request and exit.")
    parser.add_argument("--target-attack", type=int, default=20)
    parser.add_argument("--target-strength", type=int, default=20)
    parser.add_argument("--target-defence", type=int, default=5)
    parser.add_argument("--balance-attack-strength-until", type=int, default=15,
                        help="After early gear/defence goals, balance Attack and Strength up to this level, then finish Attack before Strength.")
    parser.add_argument("--attack-before-balanced-all", type=int, default=20,
                        help="After the Attack/Strength checkpoint, force Attack to this level before lowest-level all-melee balancing.")
    parser.add_argument("--balance-all-after-attack-checkpoint", action=argparse.BooleanOptionalAction, default=True,
                        help="After the Attack checkpoint, train the lowest of Attack/Strength/Defence with direct styles instead of controlled XP.")
    parser.add_argument("--bank-target", default="al_kharid_bank", help="ML1 route target for hide banking.")
    parser.add_argument("--cow-area-target", default="lumbridge_cow_pen", help="ML1 route target for cow combat.")
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
    parser.add_argument("--pre-fight-loot-interval", type=int, default=0,
                        help="Run a broad pre-fight cowhide sweep on the first cycle and then every N cycles. Default 0 skips recurring sweeps for faster next-cow attacks.")
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
    parser.add_argument("--auto-buy-mithril-scimitar", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--mithril-scimitar-shop-target", default="al_kharid_scimitar_shop")
    parser.add_argument("--mithril-scimitar-shop-name", default="scimitar")
    parser.add_argument("--mithril-scimitar-coin-budget", type=int, default=2000)
    parser.add_argument("--cow-scan-distance", type=int, default=24)
    parser.add_argument("--max-cow-hit", type=int, default=1)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--route-max-batches", type=int, default=60)
    parser.add_argument("--route-max-walk-distance", type=int, default=80)
    parser.add_argument("--route-max-batch-distance", type=int, default=48)
    parser.add_argument("--route-max-ticks", type=int, default=180)
    parser.add_argument("--evidence-jsonl", help="Optional route evidence JSONL path.")
    parser.add_argument("--allow-java-landmark-fallback", action=argparse.BooleanOptionalAction, default=False,
                        help="Emergency compatibility fallback to travel_to_landmark when ML1 routing fails. Disabled by default so the script uses ML1 plus primitives.")
    parser.add_argument("--al-kharid-gate-attempts", type=int, default=3)
    parser.add_argument("--al-kharid-gate-dialogue-steps", type=int, default=6)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args(argv)

    if args.status:
        return print_runner_status(args)
    if args.request_stop:
        return request_runner_stop(args)
    if args.clear_stop:
        print(json.dumps({
            "ok": True,
            "runner": "cowhide_combat_runner",
            "profile": runner_profile_label(args),
            "clearedStopRequests": clear_runner_stop_requests(args),
        }, sort_keys=True))
        return 0

    for name in ("target_attack", "target_strength", "target_defence"):
        if int(getattr(args, name)) < 1:
            parser.error("--{} must be at least 1".format(name.replace("_", "-")))
    if int(args.fight_poll_ticks) < 1 or int(args.fight_poll_ticks) > 25:
        parser.error("--fight-poll-ticks must be between 1 and 25")
    if int(args.fight_poll_attempts) < 1:
        parser.error("--fight-poll-attempts must be at least 1")
    if int(args.pre_fight_loot_interval) < 0:
        parser.error("--pre-fight-loot-interval must be at least 0")
    if int(args.al_kharid_gate_attempts) < 1:
        parser.error("--al-kharid-gate-attempts must be at least 1")
    if int(args.al_kharid_gate_dialogue_steps) < 1:
        parser.error("--al-kharid-gate-dialogue-steps must be at least 1")
    if args.retreat_threshold > args.eat_threshold:
        parser.error("--retreat-threshold must be less than or equal to --eat-threshold")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
