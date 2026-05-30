#!/usr/bin/env python3
"""Shared primitive-backed combat trip loop for bespoke enemy runners."""

import argparse
import datetime as dt
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import bridge_script as bridge


ROOT = bridge.ROOT
RUNS_DIR = ROOT / "data" / "combat" / "runs"
RUNNER_CONTROL_DIR = ROOT / ".local" / "runners"

COINS = 995
BONES = 526
BIG_BONES = 532
STEEL_BAR = 2353
KEBAB = 1971
TUNA = 361
LOBSTER = 379
SWORDFISH = 373

MITHRIL_SCIMITAR = 1329
RUNE_SWORD = 1289
ADAMANT_LONGSWORD = 1301
MITHRIL_PLATEBODY = 1121
MITHRIL_CHAINBODY = 1109
STEEL_PLATEBODY = 1119
STEEL_CHAINBODY = 1105
IRON_PLATEBODY = 1115
ADAMANT_PLATEBODY = 1123
ADAMANT_CHAINBODY = 1111
BLACK_PLATEBODY = 1125
MITHRIL_PLATELEGS = 1071
MITHRIL_PLATESKIRT = 1085
ADAMANT_PLATELEGS = 1073
ADAMANT_PLATESKIRT = 1091
BLACK_PLATELEGS = 1077
BLACK_PLATESKIRT = 1089
STEEL_PLATELEGS = 1069
IRON_PLATELEGS = 1067
MITHRIL_FULL_HELM = 1159
MITHRIL_MED_HELM = 1143
ADAMANT_FULL_HELM = 1161
ADAMANT_MED_HELM = 1145
BLACK_FULL_HELM = 1165
BLACK_MED_HELM = 1151
STEEL_FULL_HELM = 1157
STEEL_MED_HELM = 1141
IRON_FULL_HELM = 1153
IRON_MED_HELM = 1137
MITHRIL_KITESHIELD = 1197
MITHRIL_SQ_SHIELD = 1181
ADAMANT_KITESHIELD = 1199
ADAMANT_SQ_SHIELD = 1183
BLACK_KITESHIELD = 1195
BLACK_SQ_SHIELD = 1179
STEEL_KITESHIELD = 1193
STEEL_SQ_SHIELD = 1177
IRON_KITESHIELD = 1191
IRON_SQ_SHIELD = 1175
WOODEN_SHIELD = 1171

FOOD_HEALS = {
    KEBAB: 5,
    TUNA: 10,
    LOBSTER: 12,
    SWORDFISH: 14,
}

DEFAULT_FOOD_ORDER = (KEBAB, TUNA, LOBSTER, SWORDFISH)
DEFAULT_GEAR_GROUPS = (
    {"slot": "weapon", "skill": "attack", "items": (
        {"id": RUNE_SWORD, "level": 40},
        {"id": ADAMANT_LONGSWORD, "level": 30},
        {"id": MITHRIL_SCIMITAR, "level": 20},
    )},
    {"slot": "body", "skill": "defence", "items": (
        {"id": ADAMANT_PLATEBODY, "level": 30},
        {"id": ADAMANT_CHAINBODY, "level": 30},
        {"id": MITHRIL_PLATEBODY, "level": 20},
        {"id": MITHRIL_CHAINBODY, "level": 20},
        {"id": BLACK_PLATEBODY, "level": 10},
        {"id": STEEL_PLATEBODY, "level": 5},
        {"id": STEEL_CHAINBODY, "level": 5},
        {"id": IRON_PLATEBODY, "level": 1},
    )},
    {"slot": "legs", "skill": "defence", "items": (
        {"id": ADAMANT_PLATELEGS, "level": 30},
        {"id": ADAMANT_PLATESKIRT, "level": 30},
        {"id": MITHRIL_PLATELEGS, "level": 20},
        {"id": MITHRIL_PLATESKIRT, "level": 20},
        {"id": BLACK_PLATELEGS, "level": 10},
        {"id": BLACK_PLATESKIRT, "level": 10},
        {"id": STEEL_PLATELEGS, "level": 5},
        {"id": IRON_PLATELEGS, "level": 1},
    )},
    {"slot": "helm", "skill": "defence", "items": (
        {"id": ADAMANT_FULL_HELM, "level": 30},
        {"id": ADAMANT_MED_HELM, "level": 30},
        {"id": MITHRIL_FULL_HELM, "level": 20},
        {"id": MITHRIL_MED_HELM, "level": 20},
        {"id": BLACK_FULL_HELM, "level": 10},
        {"id": BLACK_MED_HELM, "level": 10},
        {"id": STEEL_FULL_HELM, "level": 5},
        {"id": STEEL_MED_HELM, "level": 5},
        {"id": IRON_FULL_HELM, "level": 1},
        {"id": IRON_MED_HELM, "level": 1},
    )},
    {"slot": "shield", "skill": "defence", "items": (
        {"id": ADAMANT_KITESHIELD, "level": 30},
        {"id": ADAMANT_SQ_SHIELD, "level": 30},
        {"id": MITHRIL_KITESHIELD, "level": 20},
        {"id": MITHRIL_SQ_SHIELD, "level": 20},
        {"id": BLACK_KITESHIELD, "level": 10},
        {"id": BLACK_SQ_SHIELD, "level": 10},
        {"id": STEEL_KITESHIELD, "level": 5},
        {"id": STEEL_SQ_SHIELD, "level": 5},
        {"id": IRON_KITESHIELD, "level": 1},
        {"id": IRON_SQ_SHIELD, "level": 1},
        {"id": WOODEN_SHIELD, "level": 1},
    )},
)

HERB_IDS = (199, 201, 203, 205, 207, 209, 211, 213, 215, 217, 219, 231, 2485)
RUNE_IDS = (554, 555, 556, 557, 558, 559, 560, 561, 562, 563, 564, 565)
SEED_IDS = (5100, 5104, 5105, 5106, 5280, 5281, 5282, 5292, 5293, 5294, 5295, 5296, 5297, 5298, 5299, 5301, 5302, 5311, 5318, 5319, 5320, 5321, 5322, 5323, 5324)
USEFUL_STACKABLES = RUNE_IDS + SEED_IDS + (COINS, 440, 2351, STEEL_BAR, 2335, 227)
DEFAULT_SOLID_LOOT_SHOP_THRESHOLD = 100


class RunnerStop(Exception):
    def __init__(self, reason, message, player=None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.player = player or {}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def elapsed_seconds(started):
    return round(time.monotonic() - started, 3)


def log(args, message, force=False):
    if force or not getattr(args, "quiet", False):
        print(message, flush=True)


def write_event(handle, event, data):
    if handle is None:
        return
    record = {"event": event, "timestamp": utc_now()}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def skill_level(player, name):
    return bridge.skill_level(player, name)


def skill_xp(player, name):
    return bridge.skill_xp(player, name)


def inventory(player):
    return bridge.inventory(player)


def equipment(player):
    return bridge.equipment(player)


def count_inventory(player, item_id):
    return bridge.count_inventory_item(player, item_id)


def count_bank(player, item_id):
    return bridge.count_bank_item(player, item_id)


def item_id(item):
    return int(item.get("id", item.get("itemId", -1)) or -1)


def item_amount(item):
    return int(item.get("amount", 1) or 1)


def item_tile(item):
    if not isinstance(item, dict):
        raise ValueError("item must be an object")
    if "x" in item and "y" in item:
        return {
            "x": int(item.get("x", 0) or 0),
            "y": int(item.get("y", 0) or 0),
            "height": int(item.get("height", item.get("h", 0)) or 0),
        }
    if item.get("tile"):
        return parse_tile(item.get("tile"))
    raise ValueError("ground item did not include a tile: {}".format(item))


def hp(player):
    return int(player.get("hitpoints", player.get("hp", 0)) or 0)


def max_hp(player):
    return int(player.get("maxHitpoints", player.get("maxHp", hp(player))) or hp(player))


def free_slots(player):
    return int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0)


def player_tile(player):
    return bridge.tile_from_player(player)


def parse_tile(value):
    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    if len(parts) != 3:
        raise ValueError("tile must be x,y,h: {}".format(value))
    return {"x": int(parts[0]), "y": int(parts[1]), "height": int(parts[2])}


def compact_player(player):
    compact = bridge.compact_player(player, ("attack", "strength", "defence", "hitpoints", "prayer"))
    compact.update({
        "combatLevel": int(player.get("combatLevel", 0) or 0),
        "combatStyle": player.get("combatStyle"),
        "inventoryFood": inventory_food_count(player),
        "inventoryCoins": count_inventory(player, COINS),
        "bankCoins": count_bank(player, COINS),
        "equipment": [{"id": item_id(item), "name": item.get("name"), "slot": item.get("slot"), "slotName": item.get("slotName")} for item in equipment(player)],
    })
    return compact


def merge_player_state(base, update):
    merged = dict(base or {})
    for key, value in (update or {}).items():
        if value is not None:
            merged[key] = value
    if "hp" in merged and "hitpoints" not in merged:
        merged["hitpoints"] = merged.get("hp")
    if "maxHp" in merged and "maxHitpoints" not in merged:
        merged["maxHitpoints"] = merged.get("maxHp")
    return merged


def player_from_combat_state(state):
    player = bridge.player_from(state)
    flags = set(player.get("flags") or [])
    if "combat" in flags and "isInCombat" not in player:
        player["isInCombat"] = True
    if "moving" in flags and "isMoving" not in player:
        player["isMoving"] = True
    if "dead" in flags and "isDead" not in player:
        player["isDead"] = True
    if "hp" in player and "hitpoints" not in player:
        player["hitpoints"] = player.get("hp")
    if "maxHp" in player and "maxHitpoints" not in player:
        player["maxHitpoints"] = player.get("maxHp")
    combat = state.get("combat") if isinstance(state.get("combat"), dict) else {}
    if combat:
        if "hp" in combat:
            player["hitpoints"] = combat.get("hp")
        if "maxHp" in combat:
            player["maxHitpoints"] = combat.get("maxHp")
        if "style" in combat:
            player["combatStyle"] = combat.get("style")
        if "inCombat" in combat:
            player["isInCombat"] = combat.get("inCombat")
    inv = state.get("inventory") if isinstance(state.get("inventory"), dict) else {}
    if "food" in inv:
        player["inventoryFood"] = int(inv.get("food", 0) or 0)
    if isinstance(inv.get("counts"), list) and inv.get("counts"):
        normalized = []
        for item in inv.get("counts") or []:
            if "id" not in item:
                continue
            normalized.append({
                "id": item.get("id"),
                "amount": item.get("amount", item.get("a", 1)),
                "name": item.get("name"),
                "foodHeal": item.get("foodHeal", item.get("heal")),
            })
        player["inventory"] = normalized
    elif isinstance(inv.get("items"), list):
        normalized = []
        for item in inv.get("items") or []:
            if "id" not in item:
                continue
            normalized.append({
                "slot": item.get("slot"),
                "id": item.get("id"),
                "amount": item.get("amount", item.get("a", 1)),
                "name": item.get("name"),
                "foodHeal": item.get("foodHeal", item.get("heal")),
            })
        player["inventory"] = normalized
    return player


def unique(values):
    seen = set()
    out = []
    for value in values or ():
        value = int(value)
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def parse_ids(value):
    if not value:
        return []
    parts = []
    for chunk in str(value).split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(int(chunk))
    return parts


def equipment_ids(player):
    return {item_id(item) for item in equipment(player) if item_id(item) >= 0}


def equipment_has(player, ids):
    wanted = {gear_item_id(value) for value in ids}
    return bool(equipment_ids(player) & wanted)


def gear_item_id(candidate):
    if isinstance(candidate, dict):
        return int(candidate.get("id", candidate.get("itemId", -1)) or -1)
    return int(candidate)


def gear_level(candidate, group):
    if isinstance(candidate, dict) and "level" in candidate:
        return int(candidate.get("level", 1) or 1)
    return int(group.get("level", 1) or 1)


def available_gear_candidates(player, group):
    skill = group.get("skill")
    level = skill_level(player, skill) if skill else 99
    result = []
    for candidate in group.get("items", ()):
        candidate_id = gear_item_id(candidate)
        if candidate_id < 0 or level < gear_level(candidate, group):
            continue
        result.append(candidate_id)
    return result


def inventory_food_count(player):
    if "inventoryFood" in player:
        return int(player.get("inventoryFood", 0) or 0)
    if "food" in player:
        return int(player.get("food", 0) or 0)
    readiness = player.get("combatReadiness") or {}
    if "inventoryFoodCount" in readiness:
        return int(readiness.get("inventoryFoodCount", 0) or 0)
    return sum(item_amount(item) for item in inventory(player) if item_id(item) in FOOD_HEALS or item.get("foodHeal"))


def trip_food_count(player, args):
    food_ids = {int(food_id) for food_id in getattr(args, "food_order", ())}
    items = inventory(player)
    if not food_ids or not items:
        return inventory_food_count(player)
    return sum(item_amount(item) for item in items if item_id(item) in food_ids)


def carried_food_heals(player, food_ids=None):
    wanted = {int(food_id) for food_id in (food_ids or ())}
    heals = []
    fallback = []
    for item in inventory(player):
        iid = item_id(item)
        heal = int(item.get("foodHeal", FOOD_HEALS.get(iid, 0)) or 0)
        if heal > 0:
            values = [heal] * max(1, item_amount(item))
            fallback.extend(values)
            if not wanted or iid in wanted:
                heals.extend(values)
    if heals:
        return heals
    if wanted:
        return fallback
    return heals


def in_bounds(player, bounds):
    if not bounds:
        return False
    x1, y1, x2, y2, h = [int(value) for value in bounds]
    tile = player_tile(player)
    return int(tile["height"]) == h and x1 <= int(tile["x"]) <= x2 and y1 <= int(tile["y"]) <= y2


def npc_tile(npc):
    if not isinstance(npc, dict):
        return None
    if npc.get("tile"):
        try:
            return parse_tile(npc.get("tile"))
        except (TypeError, ValueError):
            return None
    try:
        return {
            "x": int(npc.get("x", npc.get("absX", 0)) or 0),
            "y": int(npc.get("y", npc.get("absY", 0)) or 0),
            "height": int(npc.get("height", npc.get("h", 0)) or 0),
        }
    except (TypeError, ValueError):
        return None


def npc_in_bounds(npc, bounds):
    if not bounds:
        return True
    tile = npc_tile(npc)
    if tile is None:
        return False
    x1, y1, x2, y2, h = [int(value) for value in bounds]
    return int(tile["height"]) == h and x1 <= int(tile["x"]) <= x2 and y1 <= int(tile["y"]) <= y2


def npc_in_target_bounds(npc, plan):
    return npc_in_bounds(npc, plan.get("targetBounds"))


def npc_distance_from_player(npc, player):
    try:
        return int(npc.get("distance", 999) or 999)
    except (AttributeError, TypeError, ValueError):
        pass
    tile = npc_tile(npc)
    if tile is None:
        return 999
    return bridge.chebyshev(player_tile(player), tile)


def npc_under_attack(npc):
    if not isinstance(npc, dict):
        return False
    return bool(npc.get("underAttack", npc.get("atk", False)))


def ordered_candidate_npcs(result):
    ordered = []
    seen = set()
    for npc in [result.get("npc")] + list(result.get("candidates") or []):
        if not isinstance(npc, dict):
            continue
        key = npc_suppression_key(npc)
        if key is None:
            key = json.dumps(npc, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(npc)
    return ordered


def select_reachable_target(result, plan, args):
    now = time.monotonic()
    eligible = []
    for npc in ordered_candidate_npcs(result):
        if not npc_in_target_bounds(npc, plan):
            continue
        if target_is_suppressed(npc, args, now=now):
            continue
        eligible.append(npc)
    if not eligible:
        return None
    if bool(plan.get("preferNearestTarget", False)):
        eligible.sort(key=lambda npc: (
            int(npc.get("distance", 9999) or 9999),
            -int(npc.get("maxHitpoints", npc.get("maxHp", 0)) or 0),
            -int(npc.get("hitpoints", npc.get("hp", 0)) or 0),
        ))
    return eligible[0]


def style_target_reached(player, style, args):
    targets = {
        "attack": int(args.target_attack),
        "strength": int(args.target_strength),
        "defence": int(args.target_defence),
    }
    target = targets.get(str(style).lower())
    if target is None:
        return False
    return skill_level(player, str(style).lower()) >= target


def in_stage_bounds(player, bounds):
    if bounds is None:
        return True
    return in_bounds(player, bounds)


def uses_edgeville_dungeon_transition(plan):
    return str(plan.get("dungeonTransition", "")).lower() == "edgeville_trapdoor"


def uses_varrock_sewer_transition(plan):
    return str(plan.get("dungeonTransition", "")).lower() == "varrock_sewer_manhole"


def uses_edgeville_druid_gate_transition(plan):
    return str(plan.get("areaTransition", "")).lower() == "edgeville_druid_gates"


def in_edgeville_dungeon(player):
    return int(player_tile(player)["height"]) == 0 and 9860 <= int(player_tile(player)["y"]) <= 9960 and 3080 <= int(player_tile(player)["x"]) <= 3135


def in_varrock_sewer(player):
    tile = player_tile(player)
    return int(tile["height"]) == 0 and 3140 <= int(tile["x"]) <= 3248 and 9840 <= int(tile["y"]) <= 9920


def in_varrock_sewer_entry(player):
    tile = player_tile(player)
    return int(tile["height"]) == 0 and 3228 <= int(tile["x"]) <= 3248 and 9848 <= int(tile["y"]) <= 9868


def runner_label(plan, args):
    profile = (args.profile or os.environ.get("RS_PROFILE", "")).strip() or "default"
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in profile).strip("-") or "default"
    return "{}-{}".format(plan["runnerId"], slug)


def status_path(plan, args):
    return RUNNER_CONTROL_DIR / "{}.status.json".format(runner_label(plan, args))


def stop_path(plan, args):
    return RUNNER_CONTROL_DIR / "{}.stop".format(runner_label(plan, args))


def write_status(plan, args, status, reason, run_path=None, player=None, extra=None):
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "runner": plan["runnerId"],
        "enemy": plan["npcName"],
        "profile": args.profile or os.environ.get("RS_PROFILE", "") or "default",
        "status": status,
        "reason": reason,
        "pid": os.getpid(),
        "updatedAt": utc_now(),
        "stopRequested": stop_path(plan, args).exists(),
        "args": {
            "targetAttack": args.target_attack,
            "targetStrength": args.target_strength,
            "targetDefence": args.target_defence,
            "maxCycles": args.max_cycles,
            "foodTarget": args.food_target,
            "minimumFoodForTrip": args.minimum_food_for_trip,
            "minFoodBeforeFight": args.min_food_before_fight,
            "exitFoodReserve": getattr(args, "exit_food_reserve", int(plan.get("exitFoodReserve", 0) or 0)),
            "bankTarget": args.bank_target,
            "areaTarget": args.area_target,
        },
    }
    if run_path is not None:
        payload["runLog"] = str(run_path)
    if player is not None:
        compact = compact_player(player)
        try:
            previous = json.loads(status_path(plan, args).read_text(encoding="utf-8"))
            previous_player = previous.get("player") if isinstance(previous, dict) else None
        except (OSError, json.JSONDecodeError):
            previous_player = None
        if isinstance(previous_player, dict):
            if "equipment" not in player and previous_player.get("equipment") and not compact.get("equipment"):
                compact["equipment"] = previous_player.get("equipment")
            if "bank" not in player and previous_player.get("bankCoins") and not compact.get("bankCoins"):
                compact["bankCoins"] = previous_player.get("bankCoins")
            if compact.get("combatStyle") is None and previous_player.get("combatStyle") is not None:
                compact["combatStyle"] = previous_player.get("combatStyle")
        payload["player"] = compact
    if extra:
        payload.update(extra)
    tmp = status_path(plan, args).with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(status_path(plan, args))


def print_status(plan, args):
    path = status_path(plan, args)
    payload = {
        "ok": path.exists(),
        "runner": plan["runnerId"],
        "enemy": plan["npcName"],
        "statusPath": str(path),
        "stopRequested": stop_path(plan, args).exists(),
    }
    if path.exists():
        try:
            payload["status"] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            payload["ok"] = False
            payload["error"] = str(exc)
    print(json.dumps(payload, sort_keys=True))
    return 1 if payload.get("error") else 0


def request_stop(plan, args):
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "runner": plan["runnerId"],
        "enemy": plan["npcName"],
        "profile": args.profile or os.environ.get("RS_PROFILE", "") or "default",
        "requestedAt": utc_now(),
        "pid": os.getpid(),
        "handoff": bool(getattr(args, "handoff_stop", False)),
        "finalBank": bool(getattr(args, "stop_final_bank", True)),
    }
    stop_path(plan, args).write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "runner": plan["runnerId"], "stopRequest": str(stop_path(plan, args))}, sort_keys=True))
    return 0


def clear_stop(plan, args):
    try:
        stop_path(plan, args).unlink()
        return True
    except FileNotFoundError:
        return False


def stop_requested(plan, args, player=None):
    if not stop_path(plan, args).exists():
        return False
    if player and (bool(player.get("isInCombat", False)) or bool(player.get("isMoving", False))):
        return False
    return True


def stop_file_exists(plan, args):
    return stop_path(plan, args).exists()


def stop_payload(plan, args):
    try:
        return json.loads(stop_path(plan, args).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def stop_wants_final_bank(plan, args):
    payload = stop_payload(plan, args)
    if bool(payload.get("handoff", False)):
        return False
    if "finalBank" in payload:
        return bool(payload.get("finalBank"))
    return True


def close_interfaces(profile, handle, reason, player):
    if not player.get("isShopping") and not player.get("inTrade") and not int(player.get("nextChat", 0) or 0) and not int(player.get("dialogueAction", 0) or 0):
        return player
    result = bridge.call_tool("close_interfaces", {}, profile=profile)
    updated = bridge.player_from(result)
    write_event(handle, "close_interfaces", {"reason": reason, "success": bool(result.get("success")), "player": compact_player(updated)})
    return updated


def open_bank_interface(profile, handle, reason, player):
    if not bool(player.get("inBankArea", False)):
        return player
    result = bridge.call_tool("deposit_inventory_items", {"name": "__codex_open_bank_only__"}, profile=profile)
    try:
        updated = bridge.player_from(result)
    except RuntimeError:
        updated = bridge.observe(profile)
    write_event(handle, "open_bank_interface", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(updated),
    })
    return updated


def ensure_bank_item_mode(profile, handle, reason, player):
    if not bool(player.get("inBankArea", False)):
        return player
    player = open_bank_interface(profile, handle, reason, player)
    result = bridge.call_tool("click_interface_button", {"buttonId": 21011}, profile=profile)
    try:
        updated = bridge.player_from(result)
    except RuntimeError:
        updated = bridge.observe(profile)
    write_event(handle, "bank_withdraw_item_mode", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(updated),
    })
    return updated


def keep_item_ids(plan, args):
    ids = [COINS]
    ids.extend(args.food_order)
    ids.extend(plan.get("extraKeepItemIds", ()))
    return set(unique(ids))


def needed_inventory_gear_ids(player, plan):
    ids = []
    for group in plan.get("gearGroups", DEFAULT_GEAR_GROUPS):
        candidates = available_gear_candidates(player, group)
        if candidates and not equipment_has(player, candidates):
            ids.extend(candidates)
    return set(unique(ids))


def bank_cleanup(player, plan, args, handle, reason):
    if not bool(player.get("inBankArea", False)):
        return player
    keep_ids = keep_item_ids(plan, args)
    keep_ids.update(needed_inventory_gear_ids(player, plan))
    carried_ids = unique(item_id(item) for item in inventory(player) if item_id(item) >= 0)
    deposit_ids = [iid for iid in carried_ids if iid not in keep_ids]
    if deposit_ids:
        result = bridge.call_tool("deposit_inventory_items", {"itemIds": deposit_ids}, profile=args.profile)
        player = bridge.player_from(result)
        write_event(handle, "deposit_non_loadout_items", {
            "reason": reason,
            "itemIds": deposit_ids,
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact_player(player),
        })
    if count_inventory(player, COINS) > int(args.coin_float):
        result = bridge.call_tool("deposit_excess_coins", {"keepAmount": int(args.coin_float)}, profile=args.profile)
        player = bridge.player_from(result)
        write_event(handle, "deposit_excess_coins", {
            "reason": reason,
            "keepAmount": int(args.coin_float),
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact_player(player),
        })
    if count_inventory(player, COINS) < int(args.coin_float) and count_bank(player, COINS) > 0:
        amount = min(int(args.coin_float) - count_inventory(player, COINS), count_bank(player, COINS))
        result = bridge.call_tool("withdraw_bank_items", {"itemId": COINS, "amount": amount}, profile=args.profile)
        player = bridge.player_from(result)
        write_event(handle, "withdraw_coin_float", {
            "reason": reason,
            "amount": amount,
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact_player(player),
        })
    return player


def unequip_non_loadout(player, plan, args, handle):
    allowed = set()
    for group in plan.get("gearGroups", DEFAULT_GEAR_GROUPS):
        allowed.update(gear_item_id(candidate) for candidate in group.get("items", ()))
    to_unequip = [item_id(item) for item in equipment(player) if item_id(item) >= 0 and item_id(item) not in allowed]
    if not to_unequip:
        return player
    result = bridge.call_tool("unequip_items", {"itemIds": unique(to_unequip)}, profile=args.profile)
    updated = bridge.player_from(result)
    write_event(handle, "unequip_non_loadout", {
        "itemIds": unique(to_unequip),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(updated),
    })
    return updated


def ensure_gear(player, plan, args, handle):
    player = unequip_non_loadout(player, plan, args, handle)
    player = ensure_bank_item_mode(args.profile, handle, "gear", player)
    for group in plan.get("gearGroups", DEFAULT_GEAR_GROUPS):
        candidates = available_gear_candidates(player, group)
        if not candidates or equipment_has(player, candidates):
            continue
        for candidate in candidates:
            if count_inventory(player, candidate) <= 0 and bool(player.get("inBankArea", False)) and count_bank(player, candidate) > 0:
                result = bridge.call_tool("withdraw_bank_items", {"itemId": candidate, "amount": 1}, profile=args.profile)
                player = bridge.player_from(result)
                write_event(handle, "withdraw_gear", {
                    "slot": group.get("slot"),
                    "itemId": candidate,
                    "success": bool(result.get("success")),
                    "message": result.get("message"),
                    "player": compact_player(player),
                })
            if count_inventory(player, candidate) <= 0:
                continue
            result = bridge.call_tool("equip_item", {"itemId": candidate}, profile=args.profile)
            player = bridge.player_from(result)
            write_event(handle, "equip_gear", {
                "slot": group.get("slot"),
                "itemId": candidate,
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "player": compact_player(player),
            })
            if result.get("success"):
                break
    return player


def ensure_food(player, plan, args, handle):
    if not bool(player.get("inBankArea", False)):
        return player
    player = ensure_bank_item_mode(args.profile, handle, "food", player)
    trim_attempt = 0
    while inventory_food_count(player) > int(args.food_target) and trim_attempt < 8:
        trim_attempt += 1
        before_food = inventory_food_count(player)
        food_ids = [int(food_id) for food_id in args.food_order]
        if food_ids:
            result = bridge.call_tool(
                "deposit_inventory_items",
                {"itemIds": food_ids, "keepFoodCount": int(args.food_target)},
                profile=args.profile,
            )
            player = bridge.player_from(result)
            write_event(handle, "trim_food", {
                "attempt": trim_attempt,
                "itemIds": food_ids,
                "keepFoodCount": int(args.food_target),
                "foodBefore": before_food,
                "foodAfter": inventory_food_count(player),
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "player": compact_player(player),
            })
            if inventory_food_count(player) >= before_food:
                break
        else:
            break
    if inventory_food_count(player) > int(args.food_target):
        raise RunnerStop(
            "food_trim_failed",
            "Could not trim carried food to {} before leaving the bank.".format(int(args.food_target)),
            player,
        )
    deficit = max(0, int(args.food_target) - inventory_food_count(player))
    for food_id in args.food_order:
        if deficit <= 0:
            break
        available = count_bank(player, food_id)
        if available <= 0:
            continue
        amount = min(deficit, available, free_slots(player))
        if amount <= 0:
            break
        result = bridge.call_tool("withdraw_bank_items", {"itemId": int(food_id), "amount": int(amount)}, profile=args.profile)
        player = bridge.player_from(result)
        write_event(handle, "withdraw_food", {
            "itemId": int(food_id),
            "amount": int(amount),
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact_player(player),
        })
        deficit = max(0, int(args.food_target) - inventory_food_count(player))
    return player


def ensure_trip_food_safety(player, plan, args, handle, reason):
    minimum = int(args.minimum_food_for_trip)
    food_count = trip_food_count(player, args)
    if minimum <= 0 or food_count >= minimum:
        return player
    write_event(handle, "insufficient_trip_food", {
        "reason": reason,
        "minimumFoodForTrip": minimum,
        "foodTarget": int(args.food_target),
        "inventoryFood": inventory_food_count(player),
        "tripFood": food_count,
        "bankFood": {str(food_id): count_bank(player, food_id) for food_id in args.food_order},
        "player": compact_player(player),
    })
    raise RunnerStop(
        "insufficient_food_for_trip",
        "Only {} food available after restock; {} needs at least {}.".format(
            food_count,
            plan["npcName"],
            minimum,
        ),
        player,
    )


def prepare_loadout(player, plan, args, handle, reason):
    if not bool(player.get("inBankArea", False)):
        return player
    player = bank_cleanup(player, plan, args, handle, reason)
    player = ensure_gear(player, plan, args, handle)
    player = ensure_food(player, plan, args, handle)
    player = ensure_trip_food_safety(player, plan, args, handle, reason)
    player = close_interfaces(args.profile, handle, "after_loadout_" + reason, player)
    if bool(player.get("inBankArea", False)):
        setattr(args, "_bank_loadout_prepared", True)
    return player


def wait_for_safe_trip_run_energy(player, plan, args, handle, reason):
    target = int(plan.get("minimumRunEnergyBeforeArea", 0) or 0)
    if target <= 0 or not bool(player.get("inBankArea", False)):
        return player
    max_ticks = int(plan.get("runEnergyWaitMaxTicks", 0) or 0)
    waited = 0
    while int(player.get("runEnergy", 0) or 0) < target and waited < max_ticks:
        step = min(5, max_ticks - waited)
        result = bridge.call_tool("wait_ticks", {"ticks": step}, profile=args.profile)
        try:
            player = bridge.player_from(result)
        except RuntimeError:
            player = bridge.observe(args.profile)
        waited += step
        success = int(player.get("runEnergy", 0) or 0) >= target
        write_event(handle, "wait_for_run_energy", {
            "reason": reason,
            "targetRunEnergy": target,
            "waitedTicks": waited,
            "success": success,
            "player": compact_player(player),
        })
        if waited == step or waited % 25 == 0 or success:
            write_status(plan, args, "running", "wait_for_run_energy", run_path=getattr(handle, "name", None), player=player, extra={
                "cycle": int(getattr(args, "_cycle", 0) or 0),
                "fightsDone": int(getattr(args, "_fights_done", 0) or 0),
                "targetRunEnergy": target,
                "waitedTicks": waited,
            })
        if not bool(player.get("inBankArea", False)):
            break
    return player


def route_to(target, plan, args, handle, reason):
    route_player = bridge.observe(args.profile)
    eat_at = no_waste_eat_at_hitpoints(route_player, args)
    write_event(handle, "route_request", {
        "reason": reason,
        "target": str(target),
        "mlRoute": "bridge_script.route_to",
        "eatAtHitpoints": eat_at,
        "player": compact_player(route_player),
    })
    try:
        bridge.route_to(
            str(target),
            profile=args.profile,
            handle=handle,
            reason=reason,
            extra_args={
                "runner_max_batches": int(args.route_max_batches),
                "max_batch_distance": int(args.route_max_batch_distance),
                "eat_at": eat_at,
            },
        )
    except Exception as exc:
        player = bridge.observe(args.profile)
        recovered = None
        if "_after_transition" not in reason:
            recovered = recover_known_route_transition(player, str(target), plan, args, handle, reason, str(exc))
        if recovered is not None:
            return route_to(target, plan, args, handle, reason + "_after_transition")
        write_event(handle, "route_failed", {
            "reason": reason,
            "target": str(target),
            "error": str(exc),
            "player": compact_player(player),
        })
        raise RunnerStop("route_failed", "ML route failed to {} for {}: {}".format(target, reason, exc), player)
    player = bridge.observe(args.profile)
    write_event(handle, "route_arrived", {"reason": reason, "target": str(target), "player": compact_player(player)})
    return player


def near_taverley_white_wolf_gate(player):
    tile = player_tile(player)
    return int(tile["height"]) == 0 and 2933 <= int(tile["x"]) <= 2937 and 3448 <= int(tile["y"]) <= 3454


def near_al_kharid_toll_gate(player):
    tile = player_tile(player)
    return int(tile["height"]) == 0 and 3266 <= int(tile["x"]) <= 3269 and 3226 <= int(tile["y"]) <= 3229


def target_wants_east_of_taverley_gate(target):
    text = str(target).lower()
    east_tokens = ("falador", "lumbridge", "al_kharid", "varrock", "barbarian", "edgeville")
    west_tokens = ("catherby", "taverley", "seers", "ardougne", "gnome")
    if any(token in text for token in east_tokens):
        return True
    if any(token in text for token in west_tokens):
        return False
    return None


def target_wants_east_of_al_kharid_gate(target):
    text = str(target).lower()
    if "al_kharid" in text:
        return True
    parts = text.split(",")
    if len(parts) >= 2:
        try:
            x = int(parts[0])
            y = int(parts[1])
        except ValueError:
            return None
        if 3150 <= y <= 3235:
            return x >= 3268
    west_tokens = ("lumbridge", "falador", "varrock", "draynor", "barbarian")
    if any(token in text for token in west_tokens):
        return False
    return None


def recover_known_route_transition(player, target, plan, args, handle, reason, error):
    if near_al_kharid_toll_gate(player):
        wants_east = target_wants_east_of_al_kharid_gate(target)
        if wants_east is not None:
            direction = "east" if wants_east else "west"
            write_event(handle, "route_transition_recovery_start", {
                "reason": reason,
                "target": target,
                "transition": "al_kharid_toll_gate",
                "direction": direction,
                "error": error[:1000],
                "player": compact_player(player),
            })
            try:
                recovered = bridge.cross_al_kharid_toll_gate(
                    player,
                    to_east=wants_east,
                    profile=args.profile,
                    handle=handle,
                    reason=reason + "_al_kharid_toll_gate_" + direction,
                    compact_player_fn=compact_player,
                )
            except bridge.ObjectTransitionError as exc:
                write_event(handle, "route_transition_recovery_failed", {
                    "reason": reason,
                    "target": target,
                    "transition": "al_kharid_toll_gate",
                    "error": exc.message,
                    "player": compact_player(exc.player),
                })
                return None
            write_event(handle, "route_transition_recovery_finish", {
                "reason": reason,
                "target": target,
                "transition": "al_kharid_toll_gate",
                "direction": direction,
                "player": compact_player(recovered),
            })
            return recovered

    if near_taverley_white_wolf_gate(player):
        wants_east = target_wants_east_of_taverley_gate(target)
        if wants_east is not None:
            direction = "east" if wants_east else "west"
            write_event(handle, "route_transition_recovery_start", {
                "reason": reason,
                "target": target,
                "transition": "taverley_white_wolf_gate",
                "direction": direction,
                "error": error[:1000],
                "player": compact_player(player),
            })
            try:
                recovered = bridge.cross_taverley_white_wolf_gate(
                    player,
                    to_west=not wants_east,
                    profile=args.profile,
                    handle=handle,
                    reason=reason + "_taverley_white_wolf_gate_" + direction,
                    compact_player_fn=compact_player,
                )
            except bridge.ObjectTransitionError as exc:
                write_event(handle, "route_transition_recovery_failed", {
                    "reason": reason,
                    "target": target,
                    "transition": "taverley_white_wolf_gate",
                    "error": exc.message,
                    "player": compact_player(exc.player),
                })
                return None
            write_event(handle, "route_transition_recovery_finish", {
                "reason": reason,
                "target": target,
                "transition": "taverley_white_wolf_gate",
                "direction": direction,
                "player": compact_player(recovered),
            })
            return recovered
    return None


def route_to_bank(player, plan, args, handle, reason):
    if in_bounds(player, args.bank_bounds):
        return player
    if uses_varrock_sewer_transition(plan) and in_varrock_sewer(player):
        ml_player = try_ml_dungeon_route(
            player,
            str(plan.get("sewerExitTarget", "3237,9858,0")),
            None,
            plan,
            args,
            handle,
            reason + "_varrock_sewer_exit",
        )
        if ml_player is not None:
            player = ml_player
        else:
            player = bridge.observe(args.profile)
        if not in_varrock_sewer_entry(player) and plan.get("bankRouteSteps"):
            player = execute_route_steps(
                player,
                plan.get("bankRouteSteps", ()),
                plan,
                args,
                handle,
                reason + "_varrock_sewer_manual",
                max_ticks=int(plan.get("bankWaypointMaxTicks", 160)),
                max_walk_distance=int(plan.get("bankWaypointMaxDistance", 160)),
            )
        for waypoint in plan.get("bankWaypoints", ()):
            if in_varrock_sewer_entry(player):
                break
            player = walk_direct_tile(
                player,
                waypoint,
                plan,
                args,
                handle,
                reason + "_varrock_sewer_waypoint_" + str(waypoint),
                max_ticks=int(plan.get("bankWaypointMaxTicks", 160)),
                max_walk_distance=int(plan.get("bankWaypointMaxDistance", 160)),
            )
        if not in_varrock_sewer_entry(player):
            player = walk_direct_tile(
                player,
                str(plan.get("sewerExitTarget", "3237,9858,0")),
                plan,
                args,
                handle,
                reason + "_varrock_sewer_exit_target",
                max_ticks=int(plan.get("bankWaypointMaxTicks", 160)),
                max_walk_distance=int(plan.get("bankWaypointMaxDistance", 160)),
            )
        try:
            player = bridge.exit_varrock_sewer_ladder(
                player,
                profile=args.profile,
                handle=handle,
                reason=reason + "_varrock_sewer_ladder_exit",
                compact_player_fn=compact_player,
            )
        except bridge.ObjectTransitionError as exc:
            write_event(handle, "route_transition_recovery_failed", {
                "reason": reason,
                "transition": "varrock_sewer_manhole",
                "direction": "up",
                "error": exc.message,
                "player": compact_player(exc.player),
            })
            raise RunnerStop("varrock_sewer_exit_failed", exc.message, exc.player)
        if in_bounds(player, args.bank_bounds):
            return player
    if uses_edgeville_dungeon_transition(plan) and in_edgeville_dungeon(player):
        if uses_edgeville_druid_gate_transition(plan) and not bridge.edgeville_dungeon_underground_side(player):
            try:
                player = bridge.leave_edgeville_druid_room_gates(
                    player,
                    profile=args.profile,
                    handle=handle,
                    reason=reason + "_edgeville_druid_gates_exit",
                    compact_player_fn=compact_player,
                )
            except bridge.ObjectTransitionError as exc:
                write_event(handle, "route_transition_recovery_failed", {
                    "reason": reason,
                    "transition": "edgeville_druid_gates",
                    "direction": "out",
                    "error": exc.message,
                    "player": compact_player(exc.player),
                })
                raise RunnerStop("edgeville_druid_gates_exit_failed", exc.message, exc.player)
        try:
            player = bridge.exit_edgeville_dungeon_trapdoor(
                player,
                profile=args.profile,
                handle=handle,
                reason=reason + "_edgeville_trapdoor_exit",
                compact_player_fn=compact_player,
            )
        except bridge.ObjectTransitionError as exc:
            write_event(handle, "route_transition_recovery_failed", {
                "reason": reason,
                "transition": "edgeville_dungeon_trapdoor",
                "direction": "up",
                "error": exc.message,
                "player": compact_player(exc.player),
            })
            raise RunnerStop("edgeville_dungeon_exit_failed", exc.message, exc.player)
        if in_bounds(player, args.bank_bounds):
            return player
    for stage in plan.get("bankStageTargets", ()):
        if in_bounds(player, args.bank_bounds):
            return player
        if not in_stage_bounds(player, stage.get("fromBounds")):
            continue
        target = stage.get("target")
        if not target:
            continue
        if stage.get("targetBounds") and in_bounds(player, stage.get("targetBounds")):
            continue
        player = route_to(target, plan, args, handle, reason + "_stage_" + str(target))
        if bool(player.get("inBankArea", False)):
            player = prepare_loadout(player, plan, args, handle, reason + "_stage_" + str(target))
    return route_to(args.bank_target, plan, args, handle, reason)


def walk_direct_tile(player, target, plan, args, handle, reason, max_ticks=80, max_walk_distance=48):
    destination = parse_tile(target)
    if bridge.chebyshev(player_tile(player), destination) == 0:
        return eat_if_needed(player, args, handle, reason + "_already_arrived")

    player = eat_if_needed(player, args, handle, reason + "_before_walk")
    safety_ticks = int(plan.get("routeSafetyPollTicks", max_ticks) or max_ticks)
    safety_ticks = max(1, min(int(max_ticks), safety_ticks))
    ticks_used = 0
    no_progress_batches = 0
    last_tile = player_tile(player)
    last_result = None
    updated = player

    while ticks_used < int(max_ticks):
        chunk_ticks = max(1, min(safety_ticks, int(max_ticks) - ticks_used))
        result = bridge.call_tool("walk_to_tile_until_arrived", {
            "x": int(destination["x"]),
            "y": int(destination["y"]),
            "height": int(destination["height"]),
            "stopDistance": 0,
            "maxTicks": int(chunk_ticks),
            "maxWalkDistance": int(max_walk_distance),
            "stopOnCombat": False,
            "stopOnStall": True,
        }, profile=args.profile)
        last_result = result
        updated = bridge.player_from(result)
        batch_ticks = int(result.get("batchTicks", chunk_ticks) or 0)
        ticks_used += max(1, batch_ticks)
        arrived = bridge.chebyshev(player_tile(updated), destination) == 0
        current_tile = player_tile(updated)
        if bridge.chebyshev(current_tile, last_tile) == 0 and not arrived:
            no_progress_batches += 1
        else:
            no_progress_batches = 0
        last_tile = current_tile
        write_event(handle, "direct_walk_tile", {
            "reason": reason,
            "target": target,
            "success": bool(result.get("success")) or arrived,
            "message": result.get("message"),
            "batchStatus": result.get("batchStatus"),
            "batchTicks": result.get("batchTicks"),
            "ticksUsed": ticks_used,
            "safetyPollTicks": safety_ticks,
            "player": compact_player(updated),
        })
        updated = eat_if_needed(updated, args, handle, reason + "_after_walk_batch")
        if bridge.chebyshev(player_tile(updated), destination) == 0:
            return updated
        if str(result.get("batchStatus", "")).lower() in ("stalled", "path_blocked", "blocked") or no_progress_batches >= 2:
            break
    write_event(handle, "direct_walk_failed", {
        "reason": reason,
        "target": target,
        "message": last_result.get("message") if isinstance(last_result, dict) else None,
        "batchStatus": last_result.get("batchStatus") if isinstance(last_result, dict) else None,
        "ticksUsed": ticks_used,
        "player": compact_player(updated),
    })
    raise RunnerStop("direct_walk_failed", "Could not walk to {} for {}.".format(target, reason), updated)


def normalize_step_tile(value):
    if isinstance(value, str):
        return parse_tile(value)
    return {
        "x": int(value["x"]),
        "y": int(value["y"]),
        "height": int(value.get("height", value.get("h", 0)) or 0),
    }


def route_step_completion_tiles(step):
    if isinstance(step, str):
        return [parse_tile(step)]
    if step.get("walk"):
        return [normalize_step_tile(step["walk"])]
    if step.get("steps"):
        return [normalize_step_tile(step["steps"][-1])]
    if step.get("approach"):
        return [normalize_step_tile(step["approach"])]
    return []


def route_step_approach_tiles(step):
    if isinstance(step, str):
        return [parse_tile(step)]
    tiles = []
    if step.get("approach"):
        tiles.append(normalize_step_tile(step["approach"]))
    if step.get("walk"):
        tiles.append(normalize_step_tile(step["walk"]))
    return tiles


def route_steps_start_index(player, steps, snap_distance):
    if not steps:
        return 0
    current = player_tile(player)
    best = (9999, 0)
    for index, step in enumerate(steps):
        for tile in route_step_completion_tiles(step):
            distance = bridge.chebyshev(current, tile)
            if distance == 0:
                return min(index + 1, len(steps))
            if distance < best[0]:
                best = (distance, index + 1)
        for tile in route_step_approach_tiles(step):
            distance = bridge.chebyshev(current, tile)
            if distance == 0:
                return index
            if distance < best[0]:
                best = (distance, index)
    if best[0] <= int(snap_distance):
        candidate = max(0, min(best[1], len(steps)))
        for index, step in enumerate(steps[:candidate]):
            if isinstance(step, str) or step.get("walk"):
                continue
            nearby_tiles = route_step_approach_tiles(step) + route_step_completion_tiles(step)
            if not nearby_tiles:
                continue
            if min(bridge.chebyshev(current, tile) for tile in nearby_tiles) <= int(snap_distance):
                return index
        return candidate
    return 0


def execute_route_steps(player, steps, plan, args, handle, reason, max_ticks=100, max_walk_distance=99):
    if not steps:
        return player
    start = route_steps_start_index(player, steps, int(plan.get("routeStepSnapDistance", 12)))
    write_event(handle, "manual_route_steps_start", {
        "reason": reason,
        "startIndex": start,
        "stepCount": len(steps),
        "player": compact_player(player),
    })
    for index, step in enumerate(steps[start:], start=start):
        if isinstance(step, str) or step.get("walk"):
            target = step if isinstance(step, str) else step.get("walk")
            player = walk_direct_tile(
                player,
                target,
                plan,
                args,
                handle,
                reason + "_step_{}_walk_{}".format(index, target),
                max_ticks=max_ticks,
                max_walk_distance=max_walk_distance,
            )
            continue

        approach = step.get("approach")
        if approach:
            player = walk_direct_tile(
                player,
                approach,
                plan,
                args,
                handle,
                reason + "_step_{}_approach_{}".format(index, approach),
                max_ticks=int(step.get("approachMaxTicks", max_ticks)),
                max_walk_distance=int(step.get("approachMaxDistance", max_walk_distance)),
            )
        object_ref = step.get("object") or {
            "objectId": int(step["objectId"]),
            "x": int(step["x"]),
            "y": int(step["y"]),
            "height": int(step.get("height", 0) or 0),
        }
        cross_steps = [normalize_step_tile(tile) for tile in step.get("steps", ())]
        proof_tiles = [normalize_step_tile(tile) for tile in step.get("proofTiles", ())]
        proved = not proof_tiles
        transition_attempts = int(step.get("transitionAttempts", 3))
        last_error = None
        for transition_attempt in range(1, transition_attempts + 1):
            player = eat_if_needed(
                player,
                args,
                handle,
                reason + "_step_{}_object_{}_attempt_{}_before_open".format(index, object_ref.get("objectId"), transition_attempt),
            )
            pre_cross_when_open = bool(step.get("preCrossWhenOpen", plan.get("routeObjectPreCrossWhenOpen", False)))
            if cross_steps and proof_tiles and pre_cross_when_open:
                try:
                    player = bridge.walk_object_transition_steps(
                        player,
                        cross_steps,
                        profile=args.profile,
                        handle=handle,
                        reason=reason + "_step_{}_object_{}_attempt_{}_pre_cross".format(
                            index,
                            object_ref.get("objectId"),
                            transition_attempt,
                        ),
                        cross_wait_ticks=int(step.get("preCrossWaitTicks", plan.get("routeObjectPreCrossWaitTicks", 3))),
                        compact_player_fn=compact_player,
                    )
                except RuntimeError as pre_cross_exc:
                    write_event(handle, "manual_route_object_pre_cross_failed", {
                        "reason": reason,
                        "stepIndex": index,
                        "attempt": transition_attempt,
                        "object": object_ref,
                        "error": str(pre_cross_exc),
                        "player": compact_player(player),
                    })
                else:
                    proved = any(bridge.chebyshev(player_tile(player), tile) == 0 for tile in proof_tiles)
                    write_event(handle, "manual_route_object_pre_cross", {
                        "reason": reason,
                        "stepIndex": index,
                        "attempt": transition_attempt,
                        "object": object_ref,
                        "proofTiles": proof_tiles,
                        "proved": bool(proved),
                        "player": compact_player(player),
                    })
                    if proved:
                        break
            try:
                player = bridge.open_object_then_walk_steps(
                    player,
                    object_ref,
                    steps=cross_steps,
                    profile=args.profile,
                    handle=handle,
                    reason=reason + "_step_{}_object_{}_attempt_{}".format(index, object_ref.get("objectId"), transition_attempt),
                    option=step.get("option", "first"),
                    attempts=int(step.get("openAttempts", step.get("attempts", 2))),
                    cross_wait_ticks=int(step.get("crossWaitTicks", 14)),
                    compact_player_fn=compact_player,
                )
                transition_reached_crossing = True
            except bridge.ObjectTransitionError as exc:
                transition_reached_crossing = False
                last_error = exc
                write_event(handle, "manual_route_object_failed", {
                    "reason": reason,
                    "stepIndex": index,
                    "attempt": transition_attempt,
                    "object": object_ref,
                    "error": exc.message,
                    "player": compact_player(exc.player),
                })
                player = exc.player
                if cross_steps:
                    try:
                        player = bridge.walk_object_transition_steps(
                            player,
                            cross_steps,
                            profile=args.profile,
                            handle=handle,
                            reason=reason + "_step_{}_object_{}_attempt_{}_fallback_cross".format(
                                index,
                                object_ref.get("objectId"),
                                transition_attempt,
                            ),
                            cross_wait_ticks=int(step.get("crossWaitTicks", 14)),
                            compact_player_fn=compact_player,
                        )
                        transition_reached_crossing = True
                    except RuntimeError as fallback_exc:
                        write_event(handle, "manual_route_object_fallback_cross_failed", {
                            "reason": reason,
                            "stepIndex": index,
                            "attempt": transition_attempt,
                            "object": object_ref,
                            "error": str(fallback_exc),
                            "player": compact_player(player),
                        })
            if transition_reached_crossing:
                player = eat_if_needed(
                    player,
                    args,
                    handle,
                    reason + "_step_{}_object_{}_attempt_{}_after_cross".format(index, object_ref.get("objectId"), transition_attempt),
                )
                proved = not proof_tiles or any(bridge.chebyshev(player_tile(player), tile) == 0 for tile in proof_tiles)
                if proved:
                    break
                write_event(handle, "manual_route_object_unproved", {
                    "reason": reason,
                    "stepIndex": index,
                    "attempt": transition_attempt,
                    "object": object_ref,
                    "proofTiles": proof_tiles,
                    "player": compact_player(player),
                })
            if transition_attempt < transition_attempts:
                player = bridge.observe(args.profile)
                player = eat_if_needed(
                    player,
                    args,
                    handle,
                    reason + "_step_{}_object_{}_attempt_{}_retry_observe".format(index, object_ref.get("objectId"), transition_attempt),
                )
                if approach and not any(bridge.chebyshev(player_tile(player), tile) == 0 for tile in proof_tiles):
                    player = walk_direct_tile(
                        player,
                        approach,
                        plan,
                        args,
                        handle,
                        reason + "_step_{}_retry_approach_{}".format(index, approach),
                        max_ticks=int(step.get("approachMaxTicks", max_ticks)),
                        max_walk_distance=int(step.get("approachMaxDistance", max_walk_distance)),
                    )
        if not proved:
            if last_error is not None:
                raise RunnerStop("object_transition_failed", last_error.message, last_error.player)
            raise RunnerStop("object_transition_unproved", "Object transition did not reach a proof tile.", player)
    return player


def try_ml_dungeon_route(player, target, target_bounds, plan, args, handle, reason):
    if not bool(plan.get("probeMlRoutingInDungeon", False)):
        return None
    now = time.monotonic()
    last = getattr(args, "_ml_dungeon_route_probe_at", 0.0)
    if now - last < int(plan.get("mlRouteProbeIntervalSeconds", 300)):
        return None
    setattr(args, "_ml_dungeon_route_probe_at", now)
    write_event(handle, "ml_dungeon_route_probe_start", {
        "reason": reason,
        "target": str(target),
        "player": compact_player(player),
    })
    if not bool(plan.get("executeMlDungeonRoute", False)):
        command = [
            "python3",
            str(bridge.ROOT / "ml-routing" / "route_ml_XS.py"),
            "define",
            "--from",
            bridge.tile_string(player_tile(player)),
            "--to",
            str(target),
            "--combat-level",
            str(int(player.get("combatLevel", 0) or 0)),
            "--food",
            str(trip_food_count(player, args)),
            "--run-energy",
            str(int(player.get("runEnergy", 0) or 0)),
        ]
        if bool(player.get("runEnabled", False)):
            command.append("--run-enabled")
        proc = subprocess.run(
            command,
            cwd=str(bridge.REPO_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        parsed = None
        try:
            parsed = json.loads(proc.stdout)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = None
        write_event(handle, "ml_dungeon_route_probe_define_only", {
            "reason": reason,
            "target": str(target),
            "returncode": proc.returncode,
            "status": parsed.get("status") if isinstance(parsed, dict) else None,
            "quality": parsed.get("quality") if isinstance(parsed, dict) else None,
            "routeId": parsed.get("id") if isinstance(parsed, dict) else None,
            "stepCount": parsed.get("stepCount") if isinstance(parsed, dict) else None,
            "stdoutTail": proc.stdout.splitlines()[-8:],
            "stderr": proc.stderr.strip()[:1000],
            "player": compact_player(bridge.observe(args.profile)),
        })
        return None
    route_player = bridge.observe(args.profile)
    try:
        bridge.route_to(
            str(target),
            profile=args.profile,
            handle=handle,
            reason=reason + "_ml_dungeon_probe",
            extra_args={
                "runner_max_batches": int(args.route_max_batches),
                "max_batch_distance": int(args.route_max_batch_distance),
                "eat_at": no_waste_eat_at_hitpoints(route_player, args),
            },
        )
    except Exception as exc:
        player = bridge.observe(args.profile)
        write_event(handle, "ml_dungeon_route_probe_failed", {
            "reason": reason,
            "target": str(target),
            "error": str(exc)[:1000],
            "player": compact_player(player),
        })
        return None
    player = bridge.observe(args.profile)
    arrived = in_bounds(player, target_bounds) if target_bounds else bridge.chebyshev(player_tile(player), parse_tile(target)) <= 1
    write_event(handle, "ml_dungeon_route_probe_finish", {
        "reason": reason,
        "target": str(target),
        "arrived": bool(arrived),
        "player": compact_player(player),
    })
    return player if arrived else None


def route_to_area(player, plan, args, handle, reason):
    if in_bounds(player, args.area_bounds):
        return player
    if uses_varrock_sewer_transition(plan):
        if not in_varrock_sewer(player):
            if bool(plan.get("stageBankBeforeArea", True)) and not in_bounds(player, args.bank_bounds):
                player = route_to_bank(player, plan, args, handle, reason + "_bank_stage")
                if bool(player.get("inBankArea", False)):
                    player = prepare_loadout(player, plan, args, handle, reason + "_bank_stage")
            if bool(player.get("inBankArea", False)):
                player = prepare_loadout(player, plan, args, handle, reason + "_bank_stage")
                player = wait_for_safe_trip_run_energy(player, plan, args, handle, reason + "_bank_stage")
            transition_target = str(plan.get("surfaceTransitionTarget", "3238,3458,0"))
            if transition_target:
                player = route_to(transition_target, plan, args, handle, reason + "_varrock_sewer_surface")
            try:
                player = bridge.enter_varrock_sewer_manhole(
                    player,
                    profile=args.profile,
                    handle=handle,
                    reason=reason + "_varrock_sewer_manhole_enter",
                    compact_player_fn=compact_player,
                )
            except bridge.ObjectTransitionError as exc:
                write_event(handle, "route_transition_recovery_failed", {
                    "reason": reason,
                    "transition": "varrock_sewer_manhole",
                    "direction": "down",
                    "error": exc.message,
                    "player": compact_player(exc.player),
                })
                raise RunnerStop("varrock_sewer_enter_failed", exc.message, exc.player)
        if in_bounds(player, args.area_bounds):
            return player
        ml_player = try_ml_dungeon_route(player, args.area_target, args.area_bounds, plan, args, handle, reason + "_varrock_sewer")
        if ml_player is not None and in_bounds(ml_player, args.area_bounds):
            return ml_player
        if ml_player is None:
            player = bridge.observe(args.profile)
        if plan.get("areaRouteSteps"):
            player = execute_route_steps(
                player,
                plan.get("areaRouteSteps", ()),
                plan,
                args,
                handle,
                reason + "_varrock_sewer_manual",
                max_ticks=int(plan.get("areaWaypointMaxTicks", 160)),
                max_walk_distance=int(plan.get("areaWaypointMaxDistance", 160)),
            )
            if in_bounds(player, args.area_bounds):
                return player
        for waypoint in plan.get("areaWaypoints", ()):
            if in_bounds(player, args.area_bounds):
                return player
            player = walk_direct_tile(
                player,
                waypoint,
                plan,
                args,
                handle,
                reason + "_varrock_sewer_waypoint_" + str(waypoint),
                max_ticks=int(plan.get("areaWaypointMaxTicks", 160)),
                max_walk_distance=int(plan.get("areaWaypointMaxDistance", 160)),
            )
        if in_bounds(player, args.area_bounds):
            return player
        return walk_direct_tile(
            player,
            args.area_target,
            plan,
            args,
            handle,
            reason + "_varrock_sewer_local_area",
            max_ticks=int(plan.get("areaWaypointMaxTicks", 160)),
            max_walk_distance=int(plan.get("areaWaypointMaxDistance", 160)),
        )
    if uses_edgeville_dungeon_transition(plan):
        if not in_edgeville_dungeon(player):
            if bool(plan.get("stageBankBeforeArea", True)) and not in_bounds(player, args.bank_bounds):
                player = route_to_bank(player, plan, args, handle, reason + "_bank_stage")
                if bool(player.get("inBankArea", False)):
                    player = prepare_loadout(player, plan, args, handle, reason + "_bank_stage")
            if bool(player.get("inBankArea", False)):
                player = prepare_loadout(player, plan, args, handle, reason + "_bank_stage")
            try:
                player = bridge.enter_edgeville_dungeon_trapdoor(
                    player,
                    profile=args.profile,
                    handle=handle,
                    reason=reason + "_edgeville_trapdoor_enter",
                    compact_player_fn=compact_player,
                )
            except bridge.ObjectTransitionError as exc:
                write_event(handle, "route_transition_recovery_failed", {
                    "reason": reason,
                    "transition": "edgeville_dungeon_trapdoor",
                    "direction": "down",
                    "error": exc.message,
                    "player": compact_player(exc.player),
                })
                raise RunnerStop("edgeville_dungeon_enter_failed", exc.message, exc.player)
        if in_bounds(player, args.area_bounds):
            return player
        use_entry_waypoints = True
        if uses_edgeville_druid_gate_transition(plan):
            tile = player_tile(player)
            use_entry_waypoints = int(tile["x"]) <= 3104 and int(tile["y"]) < 9918
        if use_entry_waypoints:
            for waypoint in plan.get("areaWaypoints", ()):
                if in_bounds(player, args.area_bounds):
                    return player
                player = walk_direct_tile(
                    player,
                    waypoint,
                    plan,
                    args,
                    handle,
                    reason + "_waypoint_" + str(waypoint),
                    max_ticks=int(plan.get("areaWaypointMaxTicks", 100)),
                    max_walk_distance=int(plan.get("areaWaypointMaxDistance", 48)),
                )
        if in_bounds(player, args.area_bounds):
            return player
        if uses_edgeville_druid_gate_transition(plan):
            if not bridge.edgeville_druid_second_gate_north_side(player):
                try:
                    player = bridge.enter_edgeville_druid_room_gates(
                        player,
                        profile=args.profile,
                        handle=handle,
                        reason=reason + "_edgeville_druid_gates_enter",
                        compact_player_fn=compact_player,
                    )
                except bridge.ObjectTransitionError as exc:
                    write_event(handle, "route_transition_recovery_failed", {
                        "reason": reason,
                        "transition": "edgeville_druid_gates",
                        "direction": "in",
                        "error": exc.message,
                        "player": compact_player(exc.player),
                    })
                    raise RunnerStop("edgeville_druid_gates_enter_failed", exc.message, exc.player)
            if in_bounds(player, args.area_bounds):
                return player
        return walk_direct_tile(
            player,
            args.area_target,
            plan,
            args,
            handle,
            reason + "_underground_local_area",
            max_ticks=int(plan.get("areaWaypointMaxTicks", 100)),
            max_walk_distance=int(plan.get("areaWaypointMaxDistance", 48)),
        )
    if bool(plan.get("stageBankBeforeArea", True)) and not in_bounds(player, args.bank_bounds):
        player = route_to_bank(player, plan, args, handle, reason + "_bank_stage")
        if bool(player.get("inBankArea", False)):
            player = prepare_loadout(player, plan, args, handle, reason + "_bank_stage")
        if in_bounds(player, args.area_bounds):
            return player
    return route_to(args.area_target, plan, args, handle, reason)


def should_eat(player, args):
    if hp(player) <= int(args.retreat_at_hitpoints):
        return True
    if hp(player) <= int(args.eat_at_hitpoints):
        return True
    heals = carried_food_heals(player, getattr(args, "food_order", ()))
    if not heals:
        return False
    return max_hp(player) - hp(player) >= min(heals)


def no_waste_eat_at_hitpoints(player, args):
    threshold = max(int(args.eat_at_hitpoints), int(args.retreat_at_hitpoints))
    heals = carried_food_heals(player, getattr(args, "food_order", ()))
    if heals:
        threshold = max(threshold, max_hp(player) - min(heals))
    return threshold


def eat_if_needed(player, args, handle, reason):
    if not should_eat(player, args):
        return player
    before = compact_player(player)
    result = bridge.call_tool("eat_best_food_XS", {"emergency": hp(player) <= no_waste_eat_at_hitpoints(player, args)}, profile=args.profile)
    player = player_from_combat_state(result)
    write_event(handle, "eat_food", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "itemId": result.get("itemId"),
        "healed": result.get("healed"),
        "before": before,
        "player": compact_player(player),
    })
    return player


def active_combat_npc(state, player):
    target = player.get("targetNpc")
    if isinstance(target, dict):
        return target
    combat = state.get("combat") if isinstance(state, dict) else None
    if isinstance(combat, dict) and isinstance(combat.get("targetNpc"), dict):
        return combat["targetNpc"]
    active_ids = set()
    for key in ("npcIndex", "killingNpcIndex", "underAttackBy", "underAttackBy2"):
        try:
            value = int(player.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            active_ids.add(value)
    for npc in state.get("nearbyNpcs") or []:
        try:
            if int(npc.get("npcIndex", -1)) in active_ids:
                return npc
        except (TypeError, ValueError):
            continue
    for npc in state.get("nearbyNpcs") or []:
        if bool(npc.get("underAttack", False)):
            return npc
    return None


def state_in_combat(state, player):
    combat = state.get("combat") if isinstance(state, dict) else None
    if isinstance(combat, dict) and "inCombat" in combat:
        return bool(combat.get("inCombat", False))
    return bool(player.get("isInCombat", False))


def npc_matches_plan(npc, plan):
    if not isinstance(npc, dict):
        return False
    ids = {int(value) for value in plan.get("npcIds", ())}
    try:
        npc_id = int(npc.get("id", npc.get("npcId", -1)) or -1)
    except (TypeError, ValueError):
        npc_id = -1
    if ids and npc_id in ids:
        return True
    wanted = str(plan["npcName"]).lower()
    return wanted in str(npc.get("name", "")).lower()


def npc_suppression_key(npc):
    if not isinstance(npc, dict):
        return None
    try:
        npc_index = int(npc.get("npcIndex", npc.get("index", -1)) or -1)
    except (TypeError, ValueError):
        npc_index = -1
    if npc_index >= 0:
        return "idx:{}".format(npc_index)
    if npc.get("tile"):
        return "tile:{}".format(npc.get("tile"))
    if "x" in npc and "y" in npc:
        return "tile:{},{},{}".format(
            int(npc.get("x", 0) or 0),
            int(npc.get("y", 0) or 0),
            int(npc.get("height", npc.get("h", 0)) or 0),
        )
    return None


def target_is_suppressed(npc, args, now=None):
    suppressed = getattr(args, "_suppressed_npc_targets", None)
    if not suppressed:
        return False
    key = npc_suppression_key(npc)
    if key is None:
        return False
    now = time.monotonic() if now is None else now
    expires_at = suppressed.get(key)
    if expires_at is None:
        return False
    if expires_at <= now:
        suppressed.pop(key, None)
        return False
    return True


def suppress_target(npc, args, handle, reason, cycle):
    key = npc_suppression_key(npc)
    if key is None:
        return
    suppressed = getattr(args, "_suppressed_npc_targets", None)
    if suppressed is None:
        suppressed = {}
        setattr(args, "_suppressed_npc_targets", suppressed)
    cooldown = int(getattr(args, "stale_target_cooldown_seconds", 180))
    suppressed[key] = time.monotonic() + max(1, cooldown)
    write_event(handle, "suppress_stale_target", {
        "cycle": cycle,
        "reason": reason,
        "key": key,
        "cooldownSeconds": cooldown,
        "npc": npc,
    })


def stop_if_unsafe(state, player, plan, args, handle, reason):
    if bool(player.get("isDead", False)):
        raise RunnerStop("death", "Player is dead.", player)
    if hp(player) <= int(args.retreat_at_hitpoints) and inventory_food_count(player) <= 0:
        raise RunnerStop("low_hp_no_food", "HP is unsafe and no food is carried.", player)
    if state_in_combat(state, player):
        npc = active_combat_npc(state, player)
        if npc is None:
            write_event(handle, "combat_flag_without_target", {
                "reason": reason,
                "player": compact_player(player),
            })
            return
        if not npc_matches_plan(npc, plan):
            write_event(handle, "unexpected_combat_target", {
                "reason": reason,
                "npc": npc,
                "player": compact_player(player),
            })
            raise RunnerStop("unexpected_combat_target", "In combat with an unexpected target.", player)


TRAINING_STYLE_ORDER = (
    ("attack", "attack", "target_attack"),
    ("strength", "strength", "target_strength"),
    ("defence", "defence", "target_defence"),
)


def choose_style(player, args):
    candidates = []
    for priority, (style, skill, target_attr) in enumerate(TRAINING_STYLE_ORDER):
        target = int(getattr(args, target_attr))
        level = skill_level(player, skill)
        if level < target:
            candidates.append((level, priority, style))
    if not candidates:
        return None
    return min(candidates)[2]


def targets_reached(player, args):
    return (
        skill_level(player, "attack") >= int(args.target_attack)
        and skill_level(player, "strength") >= int(args.target_strength)
        and skill_level(player, "defence") >= int(args.target_defence)
    )


def ensure_style(player, style, args, handle, reason):
    style = str(style or "").lower()
    allowed_styles = {entry[0] for entry in TRAINING_STYLE_ORDER}
    if style and style not in allowed_styles:
        raise RunnerStop("unsupported_combat_style", "Refusing unsupported combat style: {}".format(style), player)
    if not style or str(player.get("combatStyle", "")).lower() == style:
        return player
    result = bridge.call_tool("set_combat_style_XXS", {"style": style}, profile=args.profile)
    player = merge_player_state(player, bridge.player_from(result))
    if result.get("success"):
        player["combatStyle"] = style
    write_event(handle, "set_combat_style", {
        "reason": reason,
        "style": style,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return player


def normalize_fast_target(npc, distance):
    tile = parse_tile(npc.get("tile")) if npc.get("tile") else None
    normalized = {
        "npcIndex": int(npc.get("npcIndex", npc.get("index", 0)) or 0),
        "type": int(npc.get("type", npc.get("id", npc.get("npcId", 0))) or 0),
        "name": npc.get("name"),
        "combatLevel": int(npc.get("combatLevel", npc.get("level", 0)) or 0),
        "hitpoints": int(npc.get("hitpoints", npc.get("hp", 0)) or 0),
        "maxHitpoints": int(npc.get("maxHitpoints", npc.get("maxHp", 0)) or 0),
        "maxHit": int(npc.get("maxHit", 0) or 0),
        "distance": int(distance),
        "underAttack": npc_under_attack(npc),
        "aggressive": bool(npc.get("aggressive", False)),
    }
    if tile:
        normalized.update({"x": int(tile["x"]), "y": int(tile["y"]), "height": int(tile["height"])})
    return normalized


def fast_local_target_max_distance(plan, args):
    configured = plan.get("fastLocalTargetMaxDistance")
    if configured is not None:
        return max(0, int(configured))
    if bool(plan.get("forceReachableTargetScan", False)):
        return min(3, int(args.npc_max_distance))
    return int(args.npc_max_distance)


def record_eligible_idle(player, plan, args, handle, reason, cycle, style):
    if not bool(plan.get("logEligibleIdle", True)):
        return
    if bool(player.get("isInCombat", False)) or not in_bounds(player, args.area_bounds):
        return
    last = getattr(args, "_last_combat_activity_at", None)
    if last is None:
        return
    idle_seconds = time.monotonic() - float(last)
    threshold = float(plan.get("eligibleIdleLogSeconds", 8) or 0)
    if idle_seconds < threshold:
        return
    write_event(handle, "eligible_idle_before_target", {
        "cycle": cycle,
        "style": style,
        "reason": reason,
        "eligibleIdleSeconds": round(idle_seconds, 3),
        "player": compact_player(player),
    })


def candidate_target_from_state(state, player, plan, args, handle, reason):
    if not isinstance(state, dict):
        return None
    candidates = []
    suppressed_count = 0
    rejected_distance = 0
    rejected_bounds = 0
    now = time.monotonic()
    state_player = player_from_combat_state(state)
    for npc in state.get("nearbyNpcs") or []:
        if not npc_matches_plan(npc, plan):
            continue
        if npc_under_attack(npc):
            continue
        if not npc_in_target_bounds(npc, plan):
            rejected_bounds += 1
            continue
        distance = npc_distance_from_player(npc, state_player)
        if distance > int(args.npc_max_distance):
            rejected_distance += 1
            continue
        max_hp = int(npc.get("maxHitpoints", npc.get("maxHp", 0)) or 0)
        hp_now = int(npc.get("hitpoints", npc.get("hp", max_hp)) or max_hp)
        if max_hp < int(args.min_npc_hitpoints) or hp_now <= 0:
            continue
        if int(npc.get("maxHit", 999) or 999) > int(args.max_npc_max_hit):
            continue
        if target_is_suppressed(npc, args, now=now):
            suppressed_count += 1
            continue
        candidates.append((npc, distance))
    if bool(plan.get("preferNearestTarget", False)):
        candidates.sort(key=lambda entry: (
            int(entry[1]),
            -int(entry[0].get("maxHitpoints", entry[0].get("maxHp", 0)) or 0),
            -int(entry[0].get("hitpoints", entry[0].get("hp", 0)) or 0),
        ))
    else:
        candidates.sort(key=lambda entry: (
            -int(entry[0].get("maxHitpoints", entry[0].get("maxHp", 0)) or 0),
            int(entry[1]),
        ))
    if not candidates:
        write_event(handle, "cached_replacement_target_miss", {
            "reason": reason,
            "candidateCount": 0,
            "suppressedCount": suppressed_count,
            "rejectedDistance": rejected_distance,
            "rejectedBounds": rejected_bounds,
            "player": compact_player(state_player or player),
        })
        return None
    npc, distance = candidates[0]
    normalized = normalize_fast_target(npc, distance)
    write_event(handle, "cached_replacement_target", {
        "reason": reason,
        "candidateCount": len(candidates),
        "suppressedCount": suppressed_count,
        "rejectedDistance": rejected_distance,
        "rejectedBounds": rejected_bounds,
        "npc": normalized,
        "player": compact_player(state_player or player),
    })
    return normalized


def find_target(player, plan, args, handle):
    if (
        bool(plan.get("fastLocalLoop", False))
        and not bool(plan.get("disableFastLocalTargetScan", False))
        and in_bounds(player, args.area_bounds)
    ):
        started = time.monotonic()
        state = bridge.call_tool("combat_state_XS", {}, profile=args.profile)
        compact_player_state = player_from_combat_state(state)
        max_fast_distance = fast_local_target_max_distance(plan, args)
        candidates = []
        suppressed_count = 0
        rejected_distance = 0
        rejected_bounds = 0
        now = time.monotonic()
        for npc in state.get("nearbyNpcs") or []:
            if str(npc.get("name", "")).lower() != str(plan["npcName"]).lower():
                continue
            if npc_under_attack(npc):
                continue
            if not npc_in_target_bounds(npc, plan):
                rejected_bounds += 1
                continue
            distance = npc_distance_from_player(npc, compact_player_state)
            if distance > min(int(args.npc_max_distance), max_fast_distance):
                rejected_distance += 1
                continue
            max_hp = int(npc.get("maxHitpoints", npc.get("maxHp", 0)) or 0)
            hp_now = int(npc.get("hitpoints", npc.get("hp", max_hp)) or max_hp)
            if max_hp < int(args.min_npc_hitpoints) or hp_now <= 0:
                continue
            if int(npc.get("maxHit", 999) or 999) > int(args.max_npc_max_hit):
                continue
            if target_is_suppressed(npc, args, now=now):
                suppressed_count += 1
                continue
            candidates.append((npc, distance))
        if bool(plan.get("preferNearestTarget", False)):
            candidates.sort(key=lambda entry: (
                int(entry[1]),
                -int(entry[0].get("maxHitpoints", entry[0].get("maxHp", 0)) or 0),
                -int(entry[0].get("hitpoints", entry[0].get("hp", 0)) or 0),
            ))
        else:
            candidates.sort(key=lambda entry: (
                -int(entry[0].get("maxHitpoints", entry[0].get("maxHp", 0)) or 0),
                int(entry[1]),
            ))
        if candidates:
            npc, distance = candidates[0]
            normalized = normalize_fast_target(npc, distance)
            write_event(handle, "find_target_fast", {
                "success": True,
                "npc": normalized,
                "candidateCount": len(candidates),
                "suppressedCount": suppressed_count,
                "rejectedDistance": rejected_distance,
                "rejectedBounds": rejected_bounds,
                "maxDistance": max_fast_distance,
                "elapsedSeconds": elapsed_seconds(started),
                "player": compact_player(compact_player_state),
            })
            return normalized
        write_event(handle, "find_target_fast_miss", {
            "success": False,
            "candidateCount": 0,
            "suppressedCount": suppressed_count,
            "rejectedDistance": rejected_distance,
            "rejectedBounds": rejected_bounds,
            "maxDistance": max_fast_distance,
            "elapsedSeconds": elapsed_seconds(started),
            "player": compact_player(compact_player_state),
        })

    started = time.monotonic()
    result = bridge.call_tool("find_training_npc", {
        "name": plan["npcName"],
        "maxDistance": int(args.npc_max_distance),
        "minHitpoints": int(args.min_npc_hitpoints),
        "maxNpcMaxHit": int(args.max_npc_max_hit),
        "reachable": True,
        "allowUnderAttack": False,
    }, profile=args.profile)
    write_event(handle, "find_target", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "candidateCount": len(result.get("candidates") or []),
        "targetBounds": plan.get("targetBounds"),
        "elapsedSeconds": elapsed_seconds(started),
        "player": compact_player(player),
    })
    if result.get("success"):
        selected = select_reachable_target(result, plan, args)
        if selected is not None:
            if selected is not result.get("npc"):
                write_event(handle, "find_target_selected_candidate", {
                    "npc": selected,
                    "targetBounds": plan.get("targetBounds"),
                    "player": compact_player(player),
                })
            return selected
    raise RunnerStop("no_target", "No reachable {} target found.".format(plan["npcName"]), player)


def find_reachable_target(player, plan, args, handle, reason):
    result = bridge.call_tool("find_training_npc", {
        "name": plan["npcName"],
        "maxDistance": int(args.npc_max_distance),
        "minHitpoints": int(args.min_npc_hitpoints),
        "maxNpcMaxHit": int(args.max_npc_max_hit),
        "reachable": True,
        "allowUnderAttack": False,
    }, profile=args.profile)
    write_event(handle, "find_reachable_target", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "candidateCount": len(result.get("candidates") or []),
        "targetBounds": plan.get("targetBounds"),
        "player": compact_player(player),
    })
    if result.get("success"):
        return select_reachable_target(result, plan, args)
    return None


def attack_selected_target(player, npc, plan, args, handle, reason, cycle, style, event_name):
    if npc is None:
        return player, None, False
    npc_index = int(npc.get("npcIndex", npc.get("index", 0)) or 0)
    if npc_index <= 0:
        write_event(handle, event_name + "_missing_index", {
            "cycle": cycle,
            "style": style,
            "reason": reason,
            "npc": npc,
            "player": compact_player(player),
        })
        return player, npc, False
    started = time.monotonic()
    attack = bridge.call_tool("attack_npc_XXS", {"npcIndex": npc_index}, profile=args.profile)
    player = merge_player_state(player, bridge.player_from(attack))
    attacked_npc = attack.get("npc", npc)
    if attack.get("success"):
        setattr(args, "_last_combat_activity_at", time.monotonic())
    write_event(handle, event_name, {
        "cycle": cycle,
        "style": style,
        "reason": reason,
        "success": bool(attack.get("success")),
        "message": attack.get("message"),
        "npc": attacked_npc,
        "elapsedSeconds": elapsed_seconds(started),
        "player": compact_player(player),
    })
    return player, attacked_npc, bool(attack.get("success"))


def attack_replacement_target(player, plan, args, handle, reason, cycle, style, preferred_npc=None):
    if preferred_npc is not None:
        player, attacked_npc, attacked = attack_selected_target(
            player,
            preferred_npc,
            plan,
            args,
            handle,
            reason + "_cached",
            cycle,
            style,
            "retarget_cached_attack",
        )
        if attacked:
            return player, attacked_npc, True
    try:
        npc = find_target(player, plan, args, handle)
    except RunnerStop:
        npc = find_reachable_target(player, plan, args, handle, reason)
    if npc is None:
        write_event(handle, "retarget_replacement_missing", {
            "cycle": cycle,
            "style": style,
            "reason": reason,
            "player": compact_player(player),
        })
        return player, None, False
    return attack_selected_target(
        player,
        npc,
        plan,
        args,
        handle,
        reason,
        cycle,
        style,
        "retarget_replacement_attack",
    )


def wait_for_cancel_to_clear_combat(player, plan, args, handle, reason, cycle, style):
    if not bool(player.get("isInCombat", False)):
        return player
    ticks = int(plan.get("staleCancelClearWaitTicks", 3) or 0)
    if ticks <= 0:
        return player
    result = bridge.call_tool("wait_ticks", {"ticks": ticks}, profile=args.profile)
    try:
        player = bridge.player_from(result)
    except RuntimeError:
        player = bridge.observe(args.profile)
    write_event(handle, "stale_cancel_clear_wait", {
        "cycle": cycle,
        "style": style,
        "reason": reason,
        "ticks": ticks,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return player


def bury_inventory_bones(player, plan, args, handle, reason):
    bone_ids = unique(plan.get("boneItemIds", (BONES, BIG_BONES)))
    for bone_id in bone_ids:
        for attempt in range(1, int(args.bury_attempts) + 1):
            if count_inventory(player, bone_id) <= 0:
                break
            result = bridge.call_tool("bury_bones_XS", {"itemId": int(bone_id)}, profile=args.profile)
            player = bridge.player_from(result)
            write_event(handle, "bury_bones", {
                "reason": reason,
                "itemId": int(bone_id),
                "attempt": attempt,
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "buried": result.get("buried"),
                "player": compact_player(player),
            })
            if not result.get("success"):
                break
            if count_inventory(player, bone_id) > 0:
                bridge.call_tool("wait_ticks", {"ticks": 2}, profile=args.profile)
                player = bridge.observe(args.profile)
    return player


def solid_loot_shop_values(plan):
    values = {}
    for key, value in (plan.get("solidLootShopValues") or {}).items():
        try:
            values[int(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return values


def always_loot_ids(plan):
    ids = set((COINS,) + HERB_IDS + RUNE_IDS)
    ids.update(unique(plan.get("alwaysLootItemIds", ())))
    if not any(key in plan for key in ("alwaysLootItemIds", "valuableSolidItemIds", "solidLootShopValues")):
        ids.update(unique(plan.get("lootItemIds", ())))
    return ids


def valuable_solid_loot_ids(plan):
    threshold = int(plan.get("solidLootShopThreshold", DEFAULT_SOLID_LOOT_SHOP_THRESHOLD))
    values = solid_loot_shop_values(plan)
    ids = set(unique(plan.get("valuableSolidItemIds", ())))
    ids.update(item_id for item_id, value in values.items() if value >= threshold)
    return ids


def loot_priority(item, plan):
    iid = item_id(item)
    if iid == COINS:
        return 0
    if iid in RUNE_IDS:
        return 1
    if iid in HERB_IDS:
        return 2
    if iid in always_loot_ids(plan):
        return 3
    if iid in valuable_solid_loot_ids(plan):
        return 4
    if iid in set(unique(plan.get("boneItemIds", (BONES, BIG_BONES)))):
        return 9
    return None


def visible_loot_items(state, plan, args, include_bones=True):
    seen = set()
    visible = []
    items = []
    if isinstance(state.get("player"), dict):
        items.extend(state.get("player", {}).get("nearbyGroundItems", []) or [])
    items.extend(state.get("nearbyGroundItems", []) or [])
    bone_ids = set(unique(plan.get("boneItemIds", (BONES, BIG_BONES))))
    for item in items:
        try:
            tile = item_tile(item)
        except ValueError:
            continue
        iid = item_id(item)
        priority = loot_priority(item, plan)
        if priority is None:
            continue
        if not include_bones and iid in bone_ids:
            continue
        if int(item.get("distance", 999) or 999) > int(args.loot_distance):
            continue
        key = (iid, int(tile["x"]), int(tile["y"]), int(tile.get("height", 0)))
        if key in seen:
            continue
        seen.add(key)
        visible.append((priority, int(item.get("distance", 999) or 999), item, tile))
    visible.sort(key=lambda entry: (entry[0], entry[1]))
    return visible


def visible_pickable_non_bone_loot(state, player, plan, args):
    if not isinstance(state, dict):
        return []
    return [
        entry for entry in visible_loot_items(state, plan, args, include_bones=False)
        if can_pick_item(player, item_id(entry[2]))
    ]


def compact_visible_loot(entries, limit=6):
    compact = []
    for priority, distance, item, tile in list(entries or [])[:limit]:
        compact.append({
            "id": item_id(item),
            "name": item.get("name"),
            "amount": item_amount(item),
            "distance": distance,
            "priority": priority,
            "tile": "{},{},{}".format(int(tile["x"]), int(tile["y"]), int(tile.get("height", 0))),
        })
    return compact


def can_pick_item(player, iid):
    return free_slots(player) > 0 or (iid in set(USEFUL_STACKABLES) and count_inventory(player, iid) > 0)


def has_cleanup_inventory_items(player, plan):
    ids = set(always_loot_ids(plan))
    if bool(plan.get("buryBoneLoot", True)):
        ids.update(unique(plan.get("boneItemIds", (BONES, BIG_BONES))))
    return any(count_inventory(player, iid) > 0 for iid in ids)


def pickup_loot_item(item, tile, player, plan, args, handle, reason):
    iid = item_id(item)
    result = bridge.call_tool("pickup_ground_item", {
        "itemId": iid,
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0)),
        "maxDistance": int(args.loot_distance),
    }, profile=args.profile)
    player = bridge.player_from(result)
    amount = int(result.get("pickedUp", result.get("amount", 0)) or 0)
    write_event(handle, "pickup_loot", {
        "reason": reason,
        "priority": loot_priority(item, plan),
        "item": item,
        "tile": tile,
        "pickedUp": amount,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return player, amount


def collect_visible_loot(player, plan, args, handle, reason, include_non_bone=True):
    if free_slots(player) <= 0 and not has_cleanup_inventory_items(player, plan):
        return player
    bones = set(unique(plan.get("boneItemIds", (BONES, BIG_BONES))))

    for sweep in range(1, int(args.loot_sweep_rounds) + 1):
        state = bridge.call_tool("combat_state_XS", {}, profile=args.profile)
        player = player_from_combat_state(state)
        picked_any = 0

        if bool(plan.get("buryBoneLoot", True)):
            state = bridge.call_tool("combat_state_XS", {}, profile=args.profile)
            player = player_from_combat_state(state)
            picked_bones = 0
            for _priority, _distance, item, tile in visible_loot_items(state, plan, args, include_bones=True):
                iid = item_id(item)
                if iid not in bones:
                    continue
                if not can_pick_item(player, iid):
                    break
                player, amount = pickup_loot_item(item, tile, player, plan, args, handle, reason + "_bones")
                picked_bones += amount
            if picked_bones > 0:
                player = bury_inventory_bones(player, plan, args, handle, reason + "_after_bone_sweep")
                picked_any += picked_bones

        if include_non_bone:
            state = bridge.call_tool("combat_state_XS", {}, profile=args.profile)
            player = player_from_combat_state(state)
            for _priority, _distance, item, tile in visible_loot_items(state, plan, args, include_bones=False):
                iid = item_id(item)
                if not can_pick_item(player, iid):
                    break
                player, amount = pickup_loot_item(item, tile, player, plan, args, handle, reason)
                picked_any += amount

        if picked_any <= 0:
            break
    return player


def cleanup_item_ids(plan):
    ids = set(unique(plan.get("lootItemIds", ())))
    ids.update(unique(plan.get("boneItemIds", (BONES, BIG_BONES))))
    ids.update(always_loot_ids(plan))
    ids.update(valuable_solid_loot_ids(plan))
    return sorted(ids)


def should_defer_non_bone_cleanup(player, plan, args, reason, visible_non_bone=None):
    if not bool(plan.get("deferNonBoneLootAfterKills", False)):
        return False
    deferred_reasons = set(plan.get("deferNonBoneLootReasons", (
        "fight_poll_combat_loot",
        "fight_poll_loot",
        "after_no_target_no_xp",
        "after_fight",
        "after_fight_no_xp",
    )))
    if reason not in deferred_reasons:
        return False
    pressure_slots = int(plan.get("immediateLootFreeSlotsAtOrBelow", 2) or 0)
    if free_slots(player) <= pressure_slots:
        return False
    if bankable_loot_count(player, plan) >= int(args.bank_at_loot_items):
        return False
    if visible_non_bone:
        return False
    return True


def cleanup_after_combat(player, plan, args, handle, reason, state=None):
    if free_slots(player) <= 0 and not has_cleanup_inventory_items(player, plan):
        return player
    bone_ids = sorted(unique(plan.get("boneItemIds", (BONES, BIG_BONES))))
    if bool(plan.get("buryBoneLoot", True)) and bone_ids:
        player = bury_inventory_bones(player, plan, args, handle, reason + "_inventory_bones")
    if free_slots(player) <= 0 and not has_cleanup_inventory_items(player, plan):
        return player
    visible_non_bone = visible_pickable_non_bone_loot(state, player, plan, args)
    include_non_bone = not should_defer_non_bone_cleanup(player, plan, args, reason, visible_non_bone=visible_non_bone)
    if not include_non_bone:
        write_event(handle, "combat_cleanup_defer_non_bone", {
            "reason": reason,
            "freeSlots": free_slots(player),
            "bankableLoot": bankable_loot_count(player, plan),
            "visibleLoot": compact_visible_loot(visible_non_bone),
            "player": compact_player(player),
        })
    started = time.monotonic()
    player = collect_visible_loot(player, plan, args, handle, reason + "_primitive_cleanup", include_non_bone=include_non_bone)
    write_event(handle, "combat_cleanup_primitives", {
        "reason": reason,
        "includeNonBone": include_non_bone,
        "boneItemIds": bone_ids,
        "lootItemIds": cleanup_item_ids(plan),
        "elapsedSeconds": elapsed_seconds(started),
        "player": compact_player(player),
    })
    return player


def maybe_attack_next_after_cleanup(player, plan, args, handle, reason, cycle, style, preferred_npc=None):
    if not bool(plan.get("attackNextAfterCleanup", False)):
        return player
    if bool(player.get("isInCombat", False)) or not in_bounds(player, args.area_bounds):
        return player
    player = eat_if_needed(player, args, handle, reason + "_eat")
    if (
        targets_reached(player, args)
        or style_target_reached(player, style, args)
        or should_bank(player, plan, args)
        or stop_file_exists(plan, args)
    ):
        write_event(handle, "post_cleanup_reengage_skip", {
            "cycle": cycle,
            "style": style,
            "reason": reason,
            "targetsReached": targets_reached(player, args),
            "styleTargetReached": style_target_reached(player, style, args),
            "shouldBank": should_bank(player, plan, args),
            "stopRequested": stop_file_exists(plan, args),
            "player": compact_player(player),
        })
        return player
    player, _npc, attacked = attack_replacement_target(
        player,
        plan,
        args,
        handle,
        reason + "_next",
        cycle,
        style,
        preferred_npc=preferred_npc,
    )
    write_event(handle, "post_cleanup_reengage", {
        "cycle": cycle,
        "style": style,
        "reason": reason,
        "attacked": bool(attacked),
        "player": compact_player(player),
    })
    return player


def bankable_loot_count(player, plan):
    ids = set(unique(plan.get("lootItemIds", ()))) - set(unique(plan.get("boneItemIds", (BONES, BIG_BONES)))) - {COINS}
    return sum(1 for item in inventory(player) if item_id(item) in ids)


def exit_food_reserve(args):
    return max(0, int(getattr(args, "exit_food_reserve", 0) or 0))


def should_bank(player, plan, args):
    if free_slots(player) <= int(args.bank_when_free_slots_at_or_below):
        return True
    food_count = trip_food_count(player, args)
    if exit_food_reserve(args) > 0 and food_count <= exit_food_reserve(args):
        return True
    if food_count < int(args.min_food_before_fight):
        return True
    return bankable_loot_count(player, plan) >= int(args.bank_at_loot_items)


def wait_after_combat_end(player, args, handle, reason, event):
    if event not in ("combat_end", "combat_ended"):
        return player
    ticks = max(0, int(args.post_target_death_wait_ticks))
    if ticks <= 0:
        return player
    result = bridge.call_tool("wait_ticks", {"ticks": ticks}, profile=args.profile)
    try:
        updated = bridge.player_from(result)
    except RuntimeError:
        updated = bridge.observe(args.profile)
    write_event(handle, "post_combat_end_wait", {
        "reason": reason,
        "event": event,
        "ticks": ticks,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(updated),
    })
    return updated


def format_fallback_command(command, args):
    profile = args.profile or os.environ.get("RS_PROFILE", "")
    replacements = {
        "profile": profile,
        "target_attack": str(args.target_attack),
        "target_strength": str(args.target_strength),
        "target_defence": str(args.target_defence),
    }
    formatted = []
    for part in command:
        text = str(part)
        for key, value in replacements.items():
            text = text.replace("{" + key + "}", value)
        formatted.append(text)
    return formatted


def start_food_short_fallback(plan, args, handle, player):
    if not bool(args.fallback_on_food_short):
        return None
    command = plan.get("foodShortFallbackCommand")
    if not command:
        return None
    formatted = format_fallback_command(command, args)
    log_path = RUNNER_CONTROL_DIR / "{}-food-short-fallback.log".format(runner_label(plan, args))
    pid_path = RUNNER_CONTROL_DIR / "{}-food-short-fallback.pid".format(runner_label(plan, args))
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab", buffering=0)
    proc = subprocess.Popen(
        formatted,
        cwd=str(bridge.REPO_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log_handle.close()
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    fallback = {
        "pid": proc.pid,
        "command": formatted,
        "log": str(log_path),
        "pidFile": str(pid_path),
        "player": compact_player(player),
    }
    write_event(handle, "food_short_fallback_started", fallback)
    return fallback


def fight_once(player, plan, args, handle, cycle):
    style = choose_style(player, args)
    if not style:
        return player, "targets_reached"
    player = ensure_style(player, style, args, handle, "cycle_{}".format(cycle))
    before_style_xp = skill_xp(player, style)
    before_hp_xp = skill_xp(player, "hitpoints")
    fast_local_in_area = bool(plan.get("fastLocalLoop", False)) and in_bounds(player, args.area_bounds)
    if fast_local_in_area and not bool(player.get("isInCombat", False)):
        state = {"nearbyNpcs": []}
        npc = None
    elif fast_local_in_area:
        state = bridge.call_tool("combat_state_XS", {}, profile=args.profile)
        player = player_from_combat_state(state)
        npc = active_combat_npc(state, player) if bool(player.get("isInCombat", False)) else None
    else:
        state = bridge.call_tool("observe_state", {}, profile=args.profile)
        player = bridge.player_from(state)
        npc = active_combat_npc(state, player) if bool(player.get("isInCombat", False)) else None
    if npc_matches_plan(npc, plan) and target_is_suppressed(npc, args):
        cancel = bridge.call_tool("cancel_current_action", {}, profile=args.profile)
        try:
            player = bridge.player_from(cancel)
        except RuntimeError:
            player = player_from_combat_state(bridge.call_tool("combat_state_XS", {}, profile=args.profile))
        write_event(handle, "skip_suppressed_active_combat_target", {
            "cycle": cycle,
            "style": style,
            "npc": npc,
            "message": cancel.get("message"),
            "player": compact_player(player),
        })
        if bool(plan.get("bankOnStaleCombat", True)):
            return player, "safety_bank"
        player = eat_if_needed(player, args, handle, "skip_suppressed_active_combat_target")
        player = cleanup_after_combat(player, plan, args, handle, "skip_suppressed_active_combat_target")
        if should_bank(player, plan, args):
            return player, "safety_bank"
        player = wait_for_cancel_to_clear_combat(
            player,
            plan,
            args,
            handle,
            "skip_suppressed_active_combat_target",
            cycle,
            style,
        )
        if bool(player.get("isInCombat", False)):
            return player, "no_progress"
        player, replacement_npc, attacked = attack_replacement_target(
            player,
            plan,
            args,
            handle,
            "skip_suppressed_active_combat_target",
            cycle,
            style,
        )
        if not attacked:
            return player, "no_progress"
        npc = replacement_npc
    if npc_matches_plan(npc, plan):
        if npc_in_target_bounds(npc, plan):
            write_event(handle, "resume_combat_target", {
                "cycle": cycle,
                "style": style,
                "npc": npc,
                "underAttack": npc_under_attack(npc),
                "player": compact_player(player),
            })
            if not npc_under_attack(npc):
                npc_index = int(npc.get("npcIndex", npc.get("index", 0)) or 0)
                if npc_index > 0:
                    started = time.monotonic()
                    attack = bridge.call_tool("attack_npc_XXS", {"npcIndex": npc_index}, profile=args.profile)
                    player = merge_player_state(player, bridge.player_from(attack))
                    if attack.get("success"):
                        setattr(args, "_last_combat_activity_at", time.monotonic())
                    write_event(handle, "attack_active_combat_target", {
                        "cycle": cycle,
                        "style": style,
                        "success": bool(attack.get("success")),
                        "message": attack.get("message"),
                        "npc": attack.get("npc", npc),
                        "elapsedSeconds": elapsed_seconds(started),
                        "player": compact_player(player),
                    })
        else:
            cancel = bridge.call_tool("cancel_current_action", {}, profile=args.profile)
            try:
                player = bridge.player_from(cancel)
            except RuntimeError:
                player = player_from_combat_state(bridge.call_tool("combat_state_XS", {}, profile=args.profile))
            suppress_target(npc, args, handle, "reject_active_target", cycle)
            write_event(handle, "reject_active_combat_target", {
                "cycle": cycle,
                "style": style,
                "npc": npc,
                "underAttack": npc_under_attack(npc),
                "inTargetBounds": npc_in_target_bounds(npc, plan),
                "targetBounds": plan.get("targetBounds"),
                "message": cancel.get("message"),
                "player": compact_player(player),
            })
            return player, "safety_bank"
    if not npc_matches_plan(npc, plan):
        record_eligible_idle(player, plan, args, handle, "find_target", cycle, style)
        npc = find_target(player, plan, args, handle)
        attack = None
        for attack_attempt in range(1, int(args.attack_attempts) + 1):
            started = time.monotonic()
            attack = bridge.call_tool("attack_npc_XXS", {"npcIndex": int(npc["npcIndex"])}, profile=args.profile)
            player = merge_player_state(player, bridge.player_from(attack))
            if attack.get("success"):
                setattr(args, "_last_combat_activity_at", time.monotonic())
            write_event(handle, "attack_target", {
                "cycle": cycle,
                "attempt": attack_attempt,
                "style": style,
                "success": bool(attack.get("success")),
                "message": attack.get("message"),
                "npc": attack.get("npc", npc),
                "elapsedSeconds": elapsed_seconds(started),
                "player": compact_player(player),
            })
            if attack.get("success"):
                break
            retry_npc = find_reachable_target(player, plan, args, handle, "attack_failed_retry")
            if retry_npc is None:
                break
            npc = retry_npc
        if not attack or not attack.get("success"):
            write_event(handle, "attack_failed_retry_later", {
                "cycle": cycle,
                "style": style,
                "message": attack.get("message") if attack else "no attack attempted",
                "npc": npc,
                "player": compact_player(player),
            })
            return player, "no_progress"

    last_style_xp = before_style_xp
    last_hp_xp = before_hp_xp
    last_counted_style_xp = before_style_xp
    last_counted_hp_xp = before_hp_xp
    kills_seen = 0
    stale_combat_polls = 0
    max_polls = int(args.fight_poll_attempts)
    for poll in range(1, max_polls + 1):
        started = time.monotonic()
        food_ready_hp = no_waste_eat_at_hitpoints(player, args)
        state = bridge.call_tool("wait_until_combat_event_smart_XS", {
            "maxTicks": int(args.fight_poll_ticks),
            "hpAtOrBelow": food_ready_hp,
            "lootDistance": int(args.loot_distance),
            "maxGroundItemDistance": int(args.loot_distance),
            "autoExtendWhileSafe": bool(plan.get("autoExtendCombatWhileSafe", True)),
            "postTargetDeathWaitTicks": int(args.post_target_death_wait_ticks),
            "stopOnXpGain": bool(args.stop_on_xp_gain),
            "stopOnLoot": True,
            "stopOnGroundItem": True,
            "stopOnTargetDead": True,
            "stopOnTargetDeath": True,
            "stopOnCombatEnd": True,
            "stopOnFoodReady": True,
        }, profile=args.profile)
        elapsed = round(time.monotonic() - started, 3)
        player = player_from_combat_state(state)
        stop_if_unsafe(state, player, plan, args, handle, "fight_poll")
        pre_eat_food = trip_food_count(player, args)
        pre_eat_hp = hp(player)
        player = eat_if_needed(player, args, handle, "fight_poll")
        current_trip_food = trip_food_count(player, args)
        ate_during_poll = current_trip_food < pre_eat_food or hp(player) > pre_eat_hp
        reserve = exit_food_reserve(args)
        if ate_during_poll and reserve > 0 and current_trip_food <= reserve:
            cancel = bridge.call_tool("cancel_current_action", {}, profile=args.profile)
            try:
                player = bridge.player_from(cancel)
            except RuntimeError:
                player = player_from_combat_state(bridge.call_tool("combat_state_XS", {}, profile=args.profile))
            write_event(handle, "fight_exit_food_reserve", {
                "cycle": cycle,
                "poll": poll,
                "reserve": reserve,
                "foodBeforeEat": pre_eat_food,
                "tripFoodAfterEat": current_trip_food,
                "hpBeforeEat": pre_eat_hp,
                "message": cancel.get("message"),
                "player": compact_player(player),
            })
            return player, "safety_bank"
        current_style_xp = skill_xp(player, style)
        current_hp_xp = skill_xp(player, "hitpoints")
        gained_style = current_style_xp - before_style_xp
        gained_hp = current_hp_xp - before_hp_xp
        made_progress = current_style_xp > last_style_xp or current_hp_xp > last_hp_xp
        if made_progress:
            last_style_xp = current_style_xp
            last_hp_xp = current_hp_xp
            stale_combat_polls = 0
        npc = active_combat_npc(state, player)
        in_combat = state_in_combat(state, player)
        combat_event = state.get("batchStatus") or state.get("event") or state.get("status")
        loot_or_death_event = combat_event in ("target_dead", "combat_end", "combat_ended", "loot", "loot_appeared", "ground_item", "ground_item_nearby")
        visible_cleanup_loot = visible_loot_items(state, plan, args, include_bones=True)
        cleanup_trigger = loot_or_death_event or (visible_cleanup_loot and not in_combat)
        kill_evidence = cleanup_trigger and (
            current_style_xp > last_counted_style_xp or current_hp_xp > last_counted_hp_xp
        )
        if kill_evidence:
            kills_seen += 1
            last_counted_style_xp = current_style_xp
            last_counted_hp_xp = current_hp_xp
            setattr(args, "_last_combat_activity_at", time.monotonic())
            write_event(handle, "fight_kill_evidence", {
                "cycle": cycle,
                "poll": poll,
                "style": style,
                "killsSeen": kills_seen,
                "combatEvent": combat_event,
                "gainedStyleXp": gained_style,
                "gainedHitpointsXp": gained_hp,
                "inCombat": in_combat,
                "npc": npc,
                "player": compact_player(player),
            })
        write_event(handle, "fight_poll", {
            "cycle": cycle,
            "poll": poll,
            "style": style,
            "elapsedSeconds": elapsed,
            "combatEvent": combat_event,
            "foodReadyHitpoints": food_ready_hp,
            "gainedStyleXp": gained_style,
            "gainedHitpointsXp": gained_hp,
            "inCombat": in_combat,
            "npc": npc,
            "player": compact_player(player),
        })
        status_interval = max(1, int(plan.get("fightStatusPollInterval", 5) or 5))
        if poll == 1 or poll % status_interval == 0 or ate_during_poll or kill_evidence:
            active_npc = None
            if isinstance(npc, dict):
                active_npc = {
                    "index": npc.get("npcIndex", npc.get("index")),
                    "name": npc.get("name"),
                    "hp": npc.get("hitpoints", npc.get("hp")),
                    "maxHp": npc.get("maxHitpoints", npc.get("maxHp")),
                    "tile": npc.get("tile"),
                    "underAttack": npc.get("underAttack"),
                }
            write_status(plan, args, "running", "fight_poll", run_path=getattr(handle, "name", None), player=player, extra={
                "cycle": cycle,
                "fightsDone": int(getattr(args, "_fights_done", 0) or 0),
                "poll": poll,
                "combatEvent": combat_event,
                "activeNpc": active_npc,
            })
        if (
            in_combat
            and ate_during_poll
            and npc_matches_plan(npc, plan)
            and npc_in_target_bounds(npc, plan)
            and trip_food_count(player, args) >= int(args.min_food_before_fight)
        ):
            npc_index = int(npc.get("npcIndex", npc.get("index", 0)) or 0) if isinstance(npc, dict) else 0
            npc_hp = int(npc.get("hitpoints", npc.get("hp", 0)) or 0) if isinstance(npc, dict) else 0
            if npc_index > 0 and npc_hp > 0:
                started = time.monotonic()
                attack = bridge.call_tool("attack_npc_XXS", {"npcIndex": npc_index}, profile=args.profile)
                player = merge_player_state(player, bridge.player_from(attack))
                if attack.get("success"):
                    setattr(args, "_last_combat_activity_at", time.monotonic())
                write_event(handle, "reattack_after_eat", {
                    "cycle": cycle,
                    "poll": poll,
                    "style": style,
                    "success": bool(attack.get("success")),
                    "message": attack.get("message"),
                    "npc": attack.get("npc", npc),
                    "elapsedSeconds": elapsed_seconds(started),
                    "player": compact_player(player),
                })
                if attack.get("success"):
                    stale_combat_polls = 0
                    continue
        if in_combat:
            if loot_or_death_event:
                next_hint = candidate_target_from_state(
                    state, player, plan, args, handle, "fight_poll_combat_loot"
                )
                player = eat_if_needed(player, args, handle, "fight_poll_before_combat_loot")
                player = cleanup_after_combat(player, plan, args, handle, "fight_poll_combat_loot", state=state)
                player = eat_if_needed(player, args, handle, "fight_poll_combat_loot")
                if free_slots(player) <= 0 or trip_food_count(player, args) < int(args.min_food_before_fight):
                    write_event(handle, "fight_safe_boundary_after_kill", {
                        "cycle": cycle,
                        "poll": poll,
                        "style": style,
                        "killsSeen": kills_seen,
                        "reason": "inventory_or_food_boundary",
                        "player": compact_player(player),
                    })
                    return player, "fought"
                if kills_seen > 0 and stop_file_exists(plan, args):
                    write_event(handle, "fight_stop_requested_after_cleanup", {
                        "cycle": cycle,
                        "poll": poll,
                        "style": style,
                        "killsSeen": kills_seen,
                        "player": compact_player(player),
                    })
                    return player, "fought"
                if kills_seen > 0:
                    player = maybe_attack_next_after_cleanup(
                        player, plan, args, handle, "fight_poll_combat_loot", cycle, style,
                        preferred_npc=next_hint
                    )
                    if bool(player.get("isInCombat", False)):
                        stale_combat_polls = 0
                        continue
            npc_hp = int(npc.get("hitpoints", npc.get("hp", 0)) or 0) if isinstance(npc, dict) else 0
            npc_max_hp = int(npc.get("maxHitpoints", npc.get("maxHp", 0)) or 0) if isinstance(npc, dict) else 0
            active_npc_under_attack = bool(npc.get("underAttack", False)) if isinstance(npc, dict) else False
            if npc_matches_plan(npc, plan):
                if not npc_in_target_bounds(npc, plan):
                    cancel = bridge.call_tool("cancel_current_action", {}, profile=args.profile)
                    try:
                        player = bridge.player_from(cancel)
                    except RuntimeError:
                        player = player_from_combat_state(bridge.call_tool("combat_state_XS", {}, profile=args.profile))
                    suppress_target(npc, args, handle, "reject_active_poll_target", cycle)
                    write_event(handle, "reject_active_poll_combat_target", {
                        "cycle": cycle,
                        "poll": poll,
                        "style": style,
                        "killsSeen": kills_seen,
                        "npc": npc,
                        "message": cancel.get("message"),
                        "player": compact_player(player),
                    })
                    return player, "safety_bank"
                if not active_npc_under_attack and trip_food_count(player, args) >= int(args.min_food_before_fight):
                    if kills_seen > 0 and stop_file_exists(plan, args):
                        write_event(handle, "fight_stop_requested_before_reengage", {
                            "cycle": cycle,
                            "poll": poll,
                            "style": style,
                            "killsSeen": kills_seen,
                            "npc": npc,
                            "player": compact_player(player),
                        })
                        return player, "fought"
                    npc_index = int(npc.get("npcIndex", npc.get("index", 0)) or 0)
                    if npc_index > 0:
                        started = time.monotonic()
                        attack = bridge.call_tool("attack_npc_XXS", {"npcIndex": npc_index}, profile=args.profile)
                        player = merge_player_state(player, bridge.player_from(attack))
                        if attack.get("success"):
                            setattr(args, "_last_combat_activity_at", time.monotonic())
                        write_event(handle, "attack_active_poll_combat_target", {
                            "cycle": cycle,
                            "poll": poll,
                            "style": style,
                            "killsSeen": kills_seen,
                            "success": bool(attack.get("success")),
                            "message": attack.get("message"),
                            "npc": attack.get("npc", npc),
                            "elapsedSeconds": elapsed_seconds(started),
                            "player": compact_player(player),
                        })
                        if attack.get("success"):
                            stale_combat_polls = 0
                            continue
            if not made_progress:
                stale_combat_polls += 1
            else:
                stale_combat_polls = 0
            if stale_combat_polls >= int(args.stale_combat_no_xp_polls):
                if (
                    not active_npc_under_attack
                    and npc_matches_plan(npc, plan)
                    and npc_in_target_bounds(npc, plan)
                    and trip_food_count(player, args) >= int(args.min_food_before_fight)
                ):
                    npc_index = int(npc.get("npcIndex", npc.get("index", 0)) or 0) if isinstance(npc, dict) else 0
                    if npc_index > 0:
                        started = time.monotonic()
                        attack = bridge.call_tool("attack_npc_XXS", {"npcIndex": npc_index}, profile=args.profile)
                        player = merge_player_state(player, bridge.player_from(attack))
                        if attack.get("success"):
                            setattr(args, "_last_combat_activity_at", time.monotonic())
                        write_event(handle, "attack_stale_combat_target", {
                            "cycle": cycle,
                            "poll": poll,
                            "style": style,
                            "staleCombatPolls": stale_combat_polls,
                            "activeNpcUnderAttack": active_npc_under_attack,
                            "npcHitpoints": npc_hp,
                            "npcMaxHitpoints": npc_max_hp,
                            "success": bool(attack.get("success")),
                            "message": attack.get("message"),
                            "npc": attack.get("npc", npc),
                            "elapsedSeconds": elapsed_seconds(started),
                            "player": compact_player(player),
                        })
                        if attack.get("success"):
                            stale_combat_polls = 0
                            continue
                cancel = bridge.call_tool("cancel_current_action", {}, profile=args.profile)
                try:
                    player = bridge.player_from(cancel)
                except RuntimeError:
                    player = player_from_combat_state(bridge.call_tool("combat_state_XS", {}, profile=args.profile))
                write_event(handle, "stale_combat_cancel", {
                    "cycle": cycle,
                    "poll": poll,
                    "style": style,
                    "staleCombatPolls": stale_combat_polls,
                    "npc": npc,
                    "message": cancel.get("message"),
                    "player": compact_player(player),
                })
                suppress_target(npc, args, handle, "stale_combat_cancel", cycle)
                if not bool(plan.get("bankOnStaleCombat", True)):
                    player = eat_if_needed(player, args, handle, "stale_combat_cancel")
                    player = cleanup_after_combat(player, plan, args, handle, "stale_combat_cancel")
                    if should_bank(player, plan, args):
                        return player, "safety_bank"
                    if kills_seen > 0:
                        write_event(handle, "stale_combat_return_after_kill", {
                            "cycle": cycle,
                            "poll": poll,
                            "style": style,
                            "killsSeen": kills_seen,
                            "player": compact_player(player),
                        })
                        return player, "fought"
                    player = wait_for_cancel_to_clear_combat(
                        player,
                        plan,
                        args,
                        handle,
                        "stale_combat_cancel",
                        cycle,
                        style,
                    )
                    if bool(player.get("isInCombat", False)):
                        return player, "no_progress"
                    player, npc, attacked = attack_replacement_target(
                        player,
                        plan,
                        args,
                        handle,
                        "stale_combat_cancel",
                        cycle,
                        style,
                    )
                    if attacked:
                        stale_combat_polls = 0
                        continue
                    return player, "no_progress"
                return player, "safety_bank"
            continue
        if loot_or_death_event or visible_cleanup_loot:
            next_hint = candidate_target_from_state(
                state, player, plan, args, handle, "fight_poll_loot"
            )
            player = wait_after_combat_end(player, args, handle, "fight_poll_loot", combat_event)
            player = cleanup_after_combat(player, plan, args, handle, "fight_poll_loot", state=state)
            if free_slots(player) <= 0:
                return player, "fought"
            if kills_seen > 0 or (loot_or_death_event and (gained_style > 0 or gained_hp > 0)):
                player = maybe_attack_next_after_cleanup(
                    player, plan, args, handle, "fight_poll_loot", cycle, style,
                    preferred_npc=next_hint
                )
                if bool(player.get("isInCombat", False)):
                    stale_combat_polls = 0
                    continue
                return player, "fought"
        if npc is None and combat_event == "max_ticks_reached":
            has_progress = kills_seen > 0 or gained_style > 0 or gained_hp > 0
            next_hint = candidate_target_from_state(
                state, player, plan, args, handle, "after_no_target_progress"
            ) if has_progress else None
            if has_progress:
                player = wait_after_combat_end(player, args, handle, "after_no_target_progress", combat_event)
            player = cleanup_after_combat(player, plan, args, handle, "after_no_target_no_xp", state=state)
            write_event(handle, "fight_no_target_after_progress" if has_progress else "fight_no_target_no_xp_retarget", {
                "cycle": cycle,
                "poll": poll,
                "style": style,
                "killsSeen": kills_seen,
                "gainedStyleXp": gained_style,
                "gainedHitpointsXp": gained_hp,
                "player": compact_player(player),
            })
            if has_progress:
                player = maybe_attack_next_after_cleanup(
                    player, plan, args, handle, "after_no_target_progress", cycle, style,
                    preferred_npc=next_hint
                )
                if bool(player.get("isInCombat", False)):
                    stale_combat_polls = 0
                    continue
                return player, "fought"
            return player, "no_progress"
        if gained_style > 0 or gained_hp > 0:
            next_hint = candidate_target_from_state(
                state, player, plan, args, handle, "after_fight"
            )
            player = wait_after_combat_end(player, args, handle, "after_fight", combat_event)
            player = cleanup_after_combat(player, plan, args, handle, "after_fight", state=state)
            player = maybe_attack_next_after_cleanup(
                player, plan, args, handle, "after_fight", cycle, style,
                preferred_npc=next_hint
            )
            if bool(player.get("isInCombat", False)):
                stale_combat_polls = 0
                continue
            return player, "fought"
        if combat_event in ("target_dead", "combat_end", "combat_ended", "loot", "loot_appeared"):
            next_hint = candidate_target_from_state(
                state, player, plan, args, handle, "after_fight_no_xp"
            )
            player = wait_after_combat_end(player, args, handle, "after_fight_no_xp", combat_event)
            player = cleanup_after_combat(player, plan, args, handle, "after_fight_no_xp", state=state)
            player = maybe_attack_next_after_cleanup(
                player, plan, args, handle, "after_fight_no_xp", cycle, style,
                preferred_npc=next_hint
            )
            if bool(player.get("isInCombat", False)):
                stale_combat_polls = 0
                continue
            return player, "fought"
        if poll >= int(args.no_xp_idle_polls):
            raise RunnerStop("fight_stalled", "Attack produced no combat XP/drop evidence.", player)
    if kills_seen > 0:
        write_event(handle, "fight_timeout_after_kill", {
            "cycle": cycle,
            "style": style,
            "killsSeen": kills_seen,
            "player": compact_player(player),
        })
        return player, "fought"
    raise RunnerStop("fight_timeout", "{} fight timed out.".format(plan["npcName"]), player)


def run_enemy(args, plan):
    if args.status:
        return print_status(plan, args)
    if args.request_stop:
        return request_stop(plan, args)
    if args.clear_stop:
        print(json.dumps({"ok": True, "cleared": clear_stop(plan, args)}, sort_keys=True))
        return 0

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        plan["runnerId"],
        uuid.uuid4().hex[:8],
    )
    handle = run_path.open("a", encoding="utf-8")
    fights_done = 0
    cycle = 0
    try:
        clear_stop(plan, args)
        args._suppressed_npc_targets = {}
        write_event(handle, "run_start", {"plan": jsonable(plan), "args": jsonable(vars(args)), "runLog": str(run_path)})
        player = bridge.observe(args.profile)
        write_status(plan, args, "running", "started", run_path=run_path, player=player)
        player = bridge.ensure_run(player, int(args.min_run_energy), profile=args.profile, handle=handle, reason=plan["runnerId"])
        args._bank_loadout_prepared = False
        args._last_combat_activity_at = None
        if bool(plan.get("disableAutoRetaliate", False)):
            player = bridge.ensure_auto_retaliate_off(
                player,
                profile=args.profile,
                handle=handle,
                reason=plan["runnerId"],
                compact_player_fn=compact_player,
            )

        for cycle in range(1, int(args.max_cycles) + 1):
            args._cycle = cycle
            player = bridge.ensure_run(player, int(args.min_run_energy), profile=args.profile, handle=handle, reason=plan["runnerId"] + "_cycle")
            write_status(plan, args, "running", "cycle_start", run_path=run_path, player=player, extra={"cycle": cycle, "fightsDone": fights_done})
            if stop_requested(plan, args, player):
                write_event(handle, "stop_requested", {"cycle": cycle, "player": compact_player(player)})
                break
            stop_if_unsafe({"nearbyNpcs": []}, player, plan, args, handle, "cycle_start")
            player = eat_if_needed(player, args, handle, "cycle_start")
            if targets_reached(player, args):
                write_event(handle, "targets_reached", {"cycle": cycle, "player": compact_player(player)})
                break
            if bool(player.get("inBankArea", False)):
                if getattr(args, "_bank_loadout_prepared", False):
                    write_event(handle, "skip_redundant_bank_prepare", {
                        "cycle": cycle,
                        "reason": "cycle_start",
                        "player": compact_player(player),
                    })
                    args._bank_loadout_prepared = False
                else:
                    player = prepare_loadout(player, plan, args, handle, "cycle_start")
            else:
                args._bank_loadout_prepared = False
            if should_bank(player, plan, args):
                player = route_to_bank(player, plan, args, handle, "bank_restock")
                player = prepare_loadout(player, plan, args, handle, "bank_restock")
                if stop_file_exists(plan, args):
                    write_event(handle, "stop_requested", {
                        "cycle": cycle,
                        "player": compact_player(player),
                        "reason": "after_bank_restock",
                    })
                    break
            player = route_to_area(player, plan, args, handle, "combat_area")
            args._bank_loadout_prepared = False
            if not bool(plan.get("skipAreaReadyObserve", False)):
                player = bridge.observe(args.profile)
            write_status(plan, args, "running", "area_ready", run_path=run_path, player=player, extra={"cycle": cycle, "fightsDone": fights_done})
            if stop_file_exists(plan, args):
                write_event(handle, "stop_requested", {
                    "cycle": cycle,
                    "player": compact_player(player),
                    "reason": "after_route_to_area",
                })
                break
            fast_local_loop = bool(plan.get("fastLocalLoop", False)) and in_bounds(player, args.area_bounds)
            if fast_local_loop:
                stop_if_unsafe({"nearbyNpcs": []}, player, plan, args, handle, "before_fight_fast")
                player = eat_if_needed(player, args, handle, "before_fight_fast")
            else:
                state = bridge.call_tool("observe_state", {}, profile=args.profile)
                player = bridge.player_from(state)
                stop_if_unsafe(state, player, plan, args, handle, "before_fight")
                player = eat_if_needed(player, args, handle, "before_fight")
                player = cleanup_after_combat(player, plan, args, handle, "before_fight")
            if free_slots(player) <= 0:
                player = route_to_bank(player, plan, args, handle, "inventory_full_before_fight")
                player = prepare_loadout(player, plan, args, handle, "inventory_full_before_fight")
                continue
            if should_bank(player, plan, args):
                write_event(handle, "pre_fight_safety_bank", {
                    "cycle": cycle,
                    "inventoryFood": inventory_food_count(player),
                    "tripFood": trip_food_count(player, args),
                    "minFoodBeforeFight": int(args.min_food_before_fight),
                    "freeSlots": free_slots(player),
                    "player": compact_player(player),
                })
                player = route_to_bank(player, plan, args, handle, "pre_fight_safety_bank")
                player = prepare_loadout(player, plan, args, handle, "pre_fight_safety_bank")
                continue
            args._fights_done = fights_done
            player, status = fight_once(player, plan, args, handle, cycle)
            if status == "targets_reached":
                break
            if status == "safety_bank":
                write_event(handle, "fight_safety_bank", {
                    "cycle": cycle,
                    "reason": "stale_or_suppressed_active_target",
                    "player": compact_player(player),
                })
                player = route_to_bank(player, plan, args, handle, "fight_safety_bank")
                player = prepare_loadout(player, plan, args, handle, "fight_safety_bank")
                continue
            if status == "no_progress":
                write_event(handle, "fight_no_progress_retry", {"cycle": cycle, "player": compact_player(player)})
                continue
            fights_done += 1
            args._fights_done = fights_done
            # XS combat/cleanup waits intentionally omit bulky inventory, bank, and
            # equipment fields. Refresh before status/bank decisions so compact
            # snapshots do not report missing gear or collapsed supply counts.
            player = bridge.observe(args.profile)
            write_status(plan, args, "running", "after_fight", run_path=run_path, player=player, extra={"cycle": cycle, "fightsDone": fights_done})
            if stop_file_exists(plan, args):
                write_event(handle, "stop_requested", {"cycle": cycle, "player": compact_player(player), "reason": "after_fight"})
                break
            if should_bank(player, plan, args):
                player = route_to_bank(player, plan, args, handle, "bank_after_fight")
                player = prepare_loadout(player, plan, args, handle, "bank_after_fight")
            compact = compact_player(player)
            log(args, "cycle {} {} atk={} str={} def={} hp={}/{} food={} free={}".format(
                cycle,
                plan["npcName"],
                compact["attackLevel"],
                compact["strengthLevel"],
                compact["defenceLevel"],
                compact["hitpoints"],
                compact["maxHitpoints"],
                compact["inventoryFood"],
                compact["freeSlots"],
            ))

        player = bridge.observe(args.profile)
        if args.final_bank and stop_wants_final_bank(plan, args) and (
            not in_bounds(player, args.bank_bounds)
            or bankable_loot_count(player, plan) > 0
            or count_inventory(player, COINS) > int(args.coin_float)
        ):
            player = route_to_bank(player, plan, args, handle, "final_bank")
            player = prepare_loadout(player, plan, args, handle, "final_bank")
        write_event(handle, "run_finish", {"cycle": cycle, "fightsDone": fights_done, "player": compact_player(player), "runLog": str(run_path)})
        write_status(plan, args, "finished", "complete", run_path=run_path, player=player, extra={"cycle": cycle, "fightsDone": fights_done})
        log(args, "{} log: {}".format(plan["runnerId"], run_path), force=True)
        return 0
    except RunnerStop as exc:
        fallback = None
        if exc.reason == "insufficient_food_for_trip":
            fallback = start_food_short_fallback(plan, args, handle, exc.player)
            if fallback is not None:
                write_status(
                    plan,
                    args,
                    "fallback",
                    "insufficient_food_for_trip",
                    run_path=run_path,
                    player=exc.player,
                    extra={
                        "message": exc.message,
                        "cycle": cycle,
                        "fightsDone": fights_done,
                        "fallback": fallback,
                    },
                )
                log(args, "fallback: insufficient food for {} trips; started fallback runner pid={}".format(plan["npcName"], fallback["pid"]), force=True)
                log(args, "{} log: {}".format(plan["runnerId"], run_path), force=True)
                return 0
        write_event(handle, "blocked", {"reason": exc.reason, "message": exc.message, "player": compact_player(exc.player) if exc.player else {}, "runLog": str(run_path)})
        write_status(plan, args, "blocked", exc.reason, run_path=run_path, player=exc.player, extra={"message": exc.message, "cycle": cycle, "fightsDone": fights_done})
        log(args, "blocked: {} ({})".format(exc.reason, exc.message), force=True)
        log(args, "{} log: {}".format(plan["runnerId"], run_path), force=True)
        return 2
    finally:
        handle.close()


def bounds_arg(value):
    values = [int(part.strip()) for part in str(value).split(",") if part.strip()]
    if len(values) != 5:
        raise argparse.ArgumentTypeError("bounds must be x1,y1,x2,y2,h")
    return tuple(values)


def add_common_arguments(parser, plan):
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE", ""))
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--request-stop", action="store_true")
    parser.add_argument("--handoff-stop", action="store_true")
    parser.add_argument("--stop-final-bank", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--clear-stop", action="store_true")
    parser.add_argument("--target-attack", type=int, default=int(plan.get("targetAttack", 25)))
    parser.add_argument("--target-strength", type=int, default=int(plan.get("targetStrength", 25)))
    parser.add_argument("--target-defence", type=int, default=int(plan.get("targetDefence", 25)))
    parser.add_argument("--max-cycles", type=int, default=int(plan.get("maxCycles", 200)))
    parser.add_argument("--bank-target", default=plan.get("bankTarget", "al_kharid_bank"))
    parser.add_argument("--area-target", default=plan.get("areaTarget"))
    parser.add_argument("--bank-bounds", type=bounds_arg, default=tuple(plan.get("bankBounds", (0, 0, 0, 0, 0))))
    parser.add_argument("--area-bounds", type=bounds_arg, default=tuple(plan.get("areaBounds", (0, 0, 0, 0, 0))))
    parser.add_argument("--food-target", type=int, default=int(plan.get("foodTarget", 6)))
    parser.add_argument("--minimum-food-for-trip", type=int, default=int(plan.get("minimumFoodForTrip", plan.get("foodTarget", 6))))
    parser.add_argument("--fallback-on-food-short", action=argparse.BooleanOptionalAction, default=bool(plan.get("fallbackOnFoodShort", False)))
    parser.add_argument("--min-food-before-fight", type=int, default=int(plan.get("minFoodBeforeFight", 1)))
    parser.add_argument("--food-order", type=lambda value: parse_ids(value), default=list(plan.get("foodOrder", DEFAULT_FOOD_ORDER)))
    parser.add_argument("--coin-float", type=int, default=int(plan.get("coinFloat", 100)))
    parser.add_argument("--eat-at-hitpoints", type=int, default=int(plan.get("eatAtHitpoints", 10)))
    parser.add_argument("--retreat-at-hitpoints", type=int, default=int(plan.get("retreatAtHitpoints", 6)))
    parser.add_argument("--exit-food-reserve", type=int, default=int(plan.get("exitFoodReserve", 0)))
    parser.add_argument("--npc-max-distance", type=int, default=int(plan.get("npcMaxDistance", 24)))
    parser.add_argument("--min-npc-hitpoints", type=int, default=int(plan.get("minNpcHitpoints", 1)))
    parser.add_argument("--max-npc-max-hit", type=int, default=int(plan.get("maxNpcMaxHit", 999)))
    parser.add_argument("--loot-distance", type=int, default=int(plan.get("lootDistance", 12)))
    parser.add_argument("--loot-sweep-rounds", type=int, default=int(plan.get("lootSweepRounds", 3)))
    parser.add_argument("--cleanup-max-ticks", type=int, default=int(plan.get("cleanupMaxTicks", 30)))
    parser.add_argument("--bank-at-loot-items", type=int, default=int(plan.get("bankAtLootItems", 12)))
    parser.add_argument("--bank-when-free-slots-at-or-below", type=int, default=int(plan.get("bankWhenFreeSlotsAtOrBelow", 2)))
    parser.add_argument("--fight-poll-ticks", type=int, default=int(plan.get("fightPollTicks", 35)))
    parser.add_argument("--fight-poll-attempts", type=int, default=int(plan.get("fightPollAttempts", 20)))
    parser.add_argument("--attack-attempts", type=int, default=int(plan.get("attackAttempts", 2)))
    parser.add_argument("--post-target-death-wait-ticks", type=int, default=int(plan.get("postTargetDeathWaitTicks", 5)))
    parser.add_argument("--stop-on-xp-gain", action=argparse.BooleanOptionalAction, default=bool(plan.get("stopOnXpGain", False)))
    parser.add_argument("--stale-combat-no-xp-polls", type=int, default=int(plan.get("staleCombatNoXpPolls", 3)))
    parser.add_argument("--stale-target-cooldown-seconds", type=int, default=int(plan.get("staleTargetCooldownSeconds", 180)))
    parser.add_argument("--reattack-no-xp-polls", type=int, default=int(plan.get("reattackNoXpPolls", 12)))
    parser.add_argument("--post-xp-loot-polls", type=int, default=int(plan.get("postXpLootPolls", 2)))
    parser.add_argument("--no-xp-idle-polls", type=int, default=int(plan.get("noXpIdlePolls", 3)))
    parser.add_argument("--bury-attempts", type=int, default=int(plan.get("buryAttempts", 4)))
    parser.add_argument("--min-run-energy", type=int, default=int(plan.get("minRunEnergy", 1)))
    parser.add_argument("--route-max-batches", type=int, default=int(plan.get("routeMaxBatches", 80)))
    parser.add_argument("--route-max-batch-distance", type=int, default=int(plan.get("routeMaxBatchDistance", 48)))
    parser.add_argument("--final-bank", action=argparse.BooleanOptionalAction, default=bool(plan.get("finalBank", True)))
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    return parser
