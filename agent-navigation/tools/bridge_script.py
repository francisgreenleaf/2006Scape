#!/usr/bin/env python3
"""Shared helpers for primitive-backed 2006Scape gameplay scripts."""

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"
ROUTE_ML = ROOT / "ml-routing" / "route_ml.py"
ROUTE_EXECUTOR = SCRIPT_DIR / "execute_route_definition.py"
COINS = 995


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def call_tool(tool_name, arguments=None, profile=""):
    env = os.environ.copy()
    if profile:
        env["RS_PROFILE"] = profile
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


def observe(profile=""):
    return player_from(call_tool("observe_state", {}, profile=profile))


def inventory(player):
    return player.get("inventory") or []


def equipment(player):
    return player.get("equipment") or []


def count_inventory_item(player, item_id):
    total = 0
    for item in inventory(player):
        if int(item.get("id", item.get("itemId", -1)) or -1) == int(item_id):
            total += int(item.get("amount", 0) or 0)
    return total


def count_bank_item(player, item_id):
    total = 0
    for item in player.get("bank") or []:
        if int(item.get("id", item.get("itemId", -1)) or -1) == int(item_id):
            total += int(item.get("amount", 0) or 0)
    return total


def _item_id(item):
    return int(item.get("id", item.get("itemId", -1)) or -1)


def _item_amount(item):
    return int(item.get("amount", 0) or 0)


def _unique_ints(values):
    seen = set()
    result = []
    for value in values or []:
        item_id = int(value)
        if item_id in seen:
            continue
        seen.add(item_id)
        result.append(item_id)
    return result


def inventory_counts(player):
    counts = {}
    for item in inventory(player):
        item_id = _item_id(item)
        if item_id < 0:
            continue
        counts[item_id] = counts.get(item_id, 0) + _item_amount(item)
    return counts


def bank_counts(player):
    counts = {}
    for item in player.get("bank") or []:
        item_id = _item_id(item)
        if item_id < 0:
            continue
        counts[item_id] = counts.get(item_id, 0) + _item_amount(item)
    return counts


def bank_policy_plan(player, deposit_all_ids=(), food_item_ids=(), keep_food_count=None, coin_float=None):
    inv = inventory_counts(player)
    bank = bank_counts(player)
    relevant_ids = set(_unique_ints(deposit_all_ids))
    food_ids = _unique_ints(food_item_ids)
    relevant_ids.update(food_ids)
    keep_food = None if keep_food_count is None else max(0, int(keep_food_count))
    food_id_set = set(food_ids) if keep_food is not None else set()
    actions = []

    deposit_ids = [
        item_id for item_id in _unique_ints(deposit_all_ids)
        if item_id not in food_id_set
        and not (coin_float is not None and item_id == COINS)
        and inv.get(item_id, 0) > 0
    ]
    if deposit_ids:
        actions.append({
            "reason": "deposit_matching_items",
            "tool": "deposit_inventory_items",
            "arguments": {"itemIds": deposit_ids},
            "itemIds": deposit_ids,
            "beforeAmounts": {str(item_id): inv.get(item_id, 0) for item_id in deposit_ids},
        })

    if keep_food is not None and food_ids:
        food_present = [item_id for item_id in food_ids if inv.get(item_id, 0) > 0]
        food_count = sum(inv.get(item_id, 0) for item_id in food_ids)
        if food_present and food_count > keep_food:
            actions.append({
                "reason": "trim_food",
                "tool": "deposit_inventory_items",
                "arguments": {"itemIds": food_present, "keepFoodCount": keep_food},
                "itemIds": food_present,
                "beforeFoodCount": food_count,
                "keepFoodCount": keep_food,
            })

    if coin_float is not None:
        relevant_ids.add(COINS)
        target = max(0, int(coin_float))
        carried = inv.get(COINS, 0)
        banked = bank.get(COINS, 0)
        if carried > target:
            actions.append({
                "reason": "deposit_coin_float",
                "tool": "deposit_excess_coins",
                "arguments": {"keepAmount": target},
                "inventoryCoins": carried,
                "targetCoins": target,
            })
        elif carried < target and banked > 0:
            amount = min(target - carried, banked)
            if amount > 0:
                actions.append({
                    "reason": "withdraw_coin_float",
                    "tool": "withdraw_bank_items",
                    "arguments": {"itemId": COINS, "amount": amount},
                    "inventoryCoins": carried,
                    "bankCoins": banked,
                    "targetCoins": target,
                    "withdrawAmount": amount,
                })

    return {
        "inBankArea": bool(player.get("inBankArea", False)),
        "inventoryCounts": {str(key): inv.get(key, 0) for key in sorted(relevant_ids) if inv.get(key, 0) > 0},
        "bankCounts": {str(key): bank.get(key, 0) for key in sorted(relevant_ids) if bank.get(key, 0) > 0},
        "actions": actions,
    }


def _player_from_or(result, fallback):
    try:
        return player_from(result)
    except RuntimeError:
        return fallback


def execute_bank_policy(player, profile="", handle=None, reason="", deposit_all_ids=(), food_item_ids=(),
                        keep_food_count=None, coin_float=None):
    if not bool(player.get("inBankArea", False)):
        raise RuntimeError("bank policy requires the player to already be in a bank area")

    plan = bank_policy_plan(
        player,
        deposit_all_ids=deposit_all_ids,
        food_item_ids=food_item_ids,
        keep_food_count=keep_food_count,
        coin_float=coin_float,
    )
    summary = {
        "reason": reason,
        "plannedActions": len(plan["actions"]),
        "actions": [],
        "initial": compact_player(player),
    }
    write_event(handle, "bank_policy_start", {
        "reason": reason,
        "plannedActions": len(plan["actions"]),
        "player": compact_player(player),
    })

    for action in plan["actions"]:
        before = compact_player(player)
        result = call_tool(action["tool"], action["arguments"], profile=profile)
        player = _player_from_or(result, player)
        step = {
            "reason": reason,
            "policyReason": action["reason"],
            "tool": action["tool"],
            "arguments": action["arguments"],
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "depositedAmount": result.get("depositedAmount"),
            "depositedCoins": result.get("depositedCoins"),
            "withdrawnAmount": result.get("withdrawnAmount"),
            "before": before,
            "player": compact_player(player),
        }
        summary["actions"].append(step)
        write_event(handle, "bank_policy_step", step)

    summary["final"] = compact_player(player)
    write_event(handle, "bank_policy_finish", {
        "reason": reason,
        "actions": len(summary["actions"]),
        "player": compact_player(player),
    })
    return player, summary


def has_inventory_item(player, item_id):
    return count_inventory_item(player, item_id) > 0


def first_inventory_item(player, item_ids):
    wanted = {int(item_id) for item_id in item_ids}
    for item in inventory(player):
        item_id = int(item.get("id", item.get("itemId", -1)) or -1)
        if item_id in wanted:
            return item
    return None


def skill_level(player, name):
    skill = (player.get("skills") or {}).get(name) or {}
    return int(skill.get("level", 0) or 0)


def skill_xp(player, name):
    skill = (player.get("skills") or {}).get(name) or {}
    return int(float(skill.get("xp", 0) or 0))


def tile_from_player(player):
    return {
        "x": int(player.get("x", 0) or 0),
        "y": int(player.get("y", 0) or 0),
        "height": int(player.get("height", player.get("h", 0)) or 0),
    }


def tile_string(tile):
    return "{},{},{}".format(int(tile["x"]), int(tile["y"]), int(tile.get("height", 0)))


def chebyshev(a, b):
    if int(a.get("height", 0)) != int(b.get("height", 0)):
        return 100000
    return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))


def compact_player(player, skills=()):
    data = {
        "tile": tile_from_player(player),
        "hitpoints": int(player.get("hitpoints", player.get("hp", 0)) or 0),
        "maxHitpoints": int(player.get("maxHitpoints", player.get("maxHp", 0)) or 0),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled", False)),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "inBankArea": bool(player.get("inBankArea", False)),
        "freeSlots": int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0),
    }
    for skill in skills:
        data[skill + "Level"] = skill_level(player, skill)
        data[skill + "Xp"] = skill_xp(player, skill)
    return data


def write_event(handle, event, data):
    if handle is None:
        return
    record = {"event": event, "timestamp": utc_now()}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def ensure_run(player, min_energy, profile="", handle=None, reason=""):
    if bool(player.get("runEnabled", False)) or int(player.get("runEnergy", 0) or 0) < min_energy:
        return player
    result = call_tool("set_run", {"enabled": True}, profile=profile)
    next_player = player_from(result)
    write_event(handle, "set_run", {
        "reason": reason,
        "before": compact_player(player),
        "after": compact_player(next_player),
    })
    return next_player


class ObjectTransitionError(RuntimeError):
    def __init__(self, reason, message, player=None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.player = player or {}


AL_KHARID_TOLL_GATE_OBJECT_IDS = {2882, 2883}
AL_KHARID_TOLL_GATE_DIALOGUE_IDS = {1019, 1020, 1024, 1026, 1027}
AL_KHARID_TOLL_GATE_DIALOGUE_OPTIONS = {
    (502, 1020): 1,
    (508, 1024): 1,
}

TAVERLEY_WHITE_WOLF_GATE_OBJECT_IDS = {1596, 1597}
TAVERLEY_WHITE_WOLF_GATE_X = 2935
TAVERLEY_WHITE_WOLF_GATE_Y = 3451
TAVERLEY_WHITE_WOLF_GATE_EAST_APPROACH = {"x": 2936, "y": 3451, "height": 0}
TAVERLEY_WHITE_WOLF_GATE_WEST_APPROACH = {"x": 2934, "y": 3451, "height": 0}


def _player_x(player):
    return int(player.get("x", 0) or 0)


def _player_y(player):
    return int(player.get("y", 0) or 0)


def _player_h(player):
    return int(player.get("height", player.get("h", 0)) or 0)


def _same_player_tile(player, x, y, h=0):
    return _player_x(player) == int(x) and _player_y(player) == int(y) and _player_h(player) == int(h)


def _transition_compact(player, compact_player_fn):
    return (compact_player_fn or compact_player)(player)


def _dialogue_state(player):
    return (
        int(player.get("dialogueAction", 0) or 0),
        int(player.get("nextChat", 0) or 0),
        int(player.get("talkingNpc", 0) or 0),
    )


def _al_kharid_toll_gate_dialogue_active(player):
    action, next_chat, _talking_npc = _dialogue_state(player)
    return next_chat in AL_KHARID_TOLL_GATE_DIALOGUE_IDS or (action, next_chat) in AL_KHARID_TOLL_GATE_DIALOGUE_OPTIONS


def al_kharid_toll_gate_on_east_side(player):
    return _player_h(player) == 0 and _player_x(player) >= 3268 and 3150 <= _player_y(player) <= 3232


def al_kharid_toll_gate_approach_tile(to_east):
    return {"x": 3267 if to_east else 3268, "y": 3227, "height": 0}


def al_kharid_toll_gate_crossed(player, to_east):
    return al_kharid_toll_gate_on_east_side(player) if to_east else not al_kharid_toll_gate_on_east_side(player)


def find_al_kharid_toll_gate_object(player, profile=""):
    found = call_tool("find_nearest_object", {"name": "gate", "maxDistance": 4}, profile=profile)
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
        if object_id in AL_KHARID_TOLL_GATE_OBJECT_IDS and h == _player_h(player) and 3267 <= x <= 3268 and y in (3227, 3228):
            return {
                "objectId": object_id,
                "x": x,
                "y": y,
                "height": h,
                "source": "find_nearest_object",
            }

    y = 3228 if _player_y(player) == 3228 else 3227
    return {
        "objectId": 2883 if y == 3228 else 2882,
        "x": 3268,
        "y": y,
        "height": _player_h(player),
        "source": "fallback",
    }


def taverley_white_wolf_gate_on_west_side(player):
    return _player_h(player) == 0 and _player_x(player) <= TAVERLEY_WHITE_WOLF_GATE_X and 3445 <= _player_y(player) <= 3458


def taverley_white_wolf_gate_approach_tile(to_west):
    return TAVERLEY_WHITE_WOLF_GATE_EAST_APPROACH if to_west else TAVERLEY_WHITE_WOLF_GATE_WEST_APPROACH


def taverley_white_wolf_gate_crossed(player, to_west):
    return taverley_white_wolf_gate_on_west_side(player) if to_west else not taverley_white_wolf_gate_on_west_side(player)


def find_taverley_white_wolf_gate_object(player, profile=""):
    found = call_tool("find_nearest_object", {"name": "gate", "maxDistance": 8}, profile=profile)
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
        if object_id in TAVERLEY_WHITE_WOLF_GATE_OBJECT_IDS and h == _player_h(player) and 2934 <= x <= 2936 and 3450 <= y <= 3452:
            return {
                "objectId": object_id,
                "x": x,
                "y": y,
                "height": h,
                "source": "find_nearest_object",
            }

    return {
        "objectId": 1596,
        "x": TAVERLEY_WHITE_WOLF_GATE_X,
        "y": TAVERLEY_WHITE_WOLF_GATE_Y,
        "height": _player_h(player),
        "source": "fallback",
    }


def _walk_gate_transition_steps(player, steps, profile="", handle=None, reason="", max_ticks=12,
                                compact_player_fn=None):
    if not steps:
        return player
    result = call_tool("walk_path_steps", {
        "steps": steps,
        "run": bool(player.get("runEnabled", True)),
        "allowObjectTransition": True,
    }, profile=profile)
    queued = _player_from_or(result, player)
    write_event(handle, "object_transition_walk_steps", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "queuedSteps": result.get("queuedSteps"),
        "steps": steps,
        "player": _transition_compact(queued, compact_player_fn),
    })
    if not result.get("success"):
        return queued
    waited = call_tool("wait_until_idle", {
        "maxTicks": int(max_ticks),
        "movement": True,
        "skilling": False,
        "combat": False,
    }, profile=profile)
    updated = _player_from_or(waited, queued)
    write_event(handle, "object_transition_walk_wait", {
        "reason": reason,
        "success": bool(waited.get("success")),
        "message": waited.get("message"),
        "batchStatus": waited.get("batchStatus"),
        "batchTicks": waited.get("batchTicks"),
        "player": _transition_compact(updated, compact_player_fn),
    })
    return updated


def open_object_then_walk_steps(player, object_ref, steps=(), profile="", handle=None, reason="",
                                option="open", attempts=2, cross_wait_ticks=12,
                                compact_player_fn=None):
    """Open a simple door/gate object and optionally queue immediate crossing steps.

    Use this for local object transitions whose mechanics are "stand close,
    open once, then quickly walk through/around the opened footprint". It is a
    small primitive building block; location-specific helpers should still
    provide exact approach/proof rules when a door or gate is known to be
    timing-sensitive.
    """
    player = observe(profile=profile)
    last_result = None
    for attempt in range(1, int(attempts) + 1):
        before = _transition_compact(player, compact_player_fn)
        opened = call_tool("interact_object", {
            "objectId": int(object_ref["objectId"]),
            "x": int(object_ref["x"]),
            "y": int(object_ref["y"]),
            "height": int(object_ref.get("height", 0) or 0),
            "option": option,
        }, profile=profile)
        last_result = opened
        player = _player_from_or(opened, player)
        write_event(handle, "object_transition_interact", {
            "reason": reason,
            "attempt": attempt,
            "object": object_ref,
            "option": option,
            "success": bool(opened.get("success")),
            "message": opened.get("message"),
            "before": before,
            "player": _transition_compact(player, compact_player_fn),
        })
        if opened.get("success") and steps:
            player = _walk_gate_transition_steps(
                player,
                steps,
                profile=profile,
                handle=handle,
                reason=reason + "_walk",
                max_ticks=cross_wait_ticks,
                compact_player_fn=compact_player_fn,
            )
            return player
        if opened.get("success"):
            waited = call_tool("wait_until_idle", {
                "maxTicks": int(cross_wait_ticks),
                "movement": True,
                "skilling": False,
                "combat": False,
            }, profile=profile)
            player = _player_from_or(waited, player)
            return player
        player = observe(profile=profile)

    raise ObjectTransitionError(
        "object_transition_open_failed",
        "Could not open object {} at {},{},{}: {}".format(
            object_ref.get("objectId"),
            object_ref.get("x"),
            object_ref.get("y"),
            object_ref.get("height", 0),
            (last_result or {}).get("message", "no result"),
        ),
        player,
    )


CATHERBY_SOUTH_RANGE_DOOR = {"objectId": 1530, "x": 2816, "y": 3438, "height": 0}
CATHERBY_SOUTH_RANGE_DOOR_APPROACH = {"x": 2817, "y": 3439, "height": 0}
CATHERBY_SOUTH_RANGE_DOOR_APPROACH_ALTERNATE = {"x": 2817, "y": 3438, "height": 0}
CATHERBY_SOUTH_RANGE_DOOR_APPROACHES = [
    CATHERBY_SOUTH_RANGE_DOOR_APPROACH,
    CATHERBY_SOUTH_RANGE_DOOR_APPROACH_ALTERNATE,
]
CATHERBY_SOUTH_RANGE_TILE = {"x": 2817, "y": 3443, "height": 0}


def _same_player_tile_ref(player, tile):
    return _same_player_tile(player, tile["x"], tile["y"], tile.get("height", 0))


def _same_player_any_tile(player, tiles):
    return any(_same_player_tile_ref(player, tile) for tile in tiles)


def open_catherby_south_range_door(player, profile="", handle=None, reason="",
                                   compact_player_fn=None):
    """Open the Catherby southern range-house door from a proven adjacent tile."""
    if not _same_player_any_tile(player, CATHERBY_SOUTH_RANGE_DOOR_APPROACHES):
        try:
            player = _walk_exact_tile(
                player,
                CATHERBY_SOUTH_RANGE_DOOR_APPROACH,
                profile=profile,
                handle=handle,
                reason="catherby_south_range_door_approach",
                max_ticks=20,
                max_walk_distance=12,
                compact_player_fn=compact_player_fn,
            )
        except ObjectTransitionError as exc:
            if not _same_player_any_tile(exc.player, CATHERBY_SOUTH_RANGE_DOOR_APPROACHES):
                player = _walk_exact_tile(
                    exc.player,
                    CATHERBY_SOUTH_RANGE_DOOR_APPROACH_ALTERNATE,
                    profile=profile,
                    handle=handle,
                    reason="catherby_south_range_door_alt_approach",
                    max_ticks=12,
                    max_walk_distance=8,
                    compact_player_fn=compact_player_fn,
                )
            else:
                player = exc.player
                write_event(handle, "object_transition_approach", {
                    "reason": "catherby_south_range_door_alt_approach",
                    "destination": CATHERBY_SOUTH_RANGE_DOOR_APPROACH_ALTERNATE,
                    "success": True,
                    "message": "Accepted alternate proven Catherby south range door approach tile.",
                    "player": _transition_compact(player, compact_player_fn),
                })
    return open_object_then_walk_steps(
        player,
        CATHERBY_SOUTH_RANGE_DOOR,
        profile=profile,
        handle=handle,
        reason=reason or "catherby_south_range_door",
        compact_player_fn=compact_player_fn,
    )


def _walk_exact_tile(player, destination, profile="", handle=None, reason="", max_ticks=24,
                     max_walk_distance=12, compact_player_fn=None):
    x = int(destination["x"])
    y = int(destination["y"])
    h = int(destination.get("height", 0))
    if _same_player_tile(player, x, y, h):
        return player
    result = call_tool("walk_to_tile_until_arrived", {
        "x": x,
        "y": y,
        "height": h,
        "stopDistance": 0,
        "maxTicks": int(max_ticks),
        "maxWalkDistance": int(max_walk_distance),
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=profile)
    updated = _player_from_or(result, player)
    write_event(handle, "object_transition_approach", {
        "reason": reason,
        "destination": destination,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "batchStatus": result.get("batchStatus"),
        "batchTicks": result.get("batchTicks"),
        "player": _transition_compact(updated, compact_player_fn),
    })
    if not _same_player_tile(updated, x, y, h):
        raise ObjectTransitionError(
            "object_transition_approach_failed",
            "Could not stand on required transition approach tile {}.".format(tile_string(destination)),
            updated,
        )
    return updated


def _advance_al_kharid_toll_gate_dialogue(player, profile=""):
    action, next_chat, _talking_npc = _dialogue_state(player)
    option = AL_KHARID_TOLL_GATE_DIALOGUE_OPTIONS.get((action, next_chat))
    if option is not None:
        return "select_dialogue_option", call_tool("select_dialogue_option", {"option": option}, profile=profile)
    if next_chat in AL_KHARID_TOLL_GATE_DIALOGUE_IDS:
        return "continue_dialogue", call_tool("continue_dialogue", {}, profile=profile)
    return "none", {"success": False, "message": "No Al Kharid toll gate dialogue is active.", "player": player}


def cross_al_kharid_toll_gate(player, to_east, profile="", handle=None, reason="", attempts=3,
                              dialogue_steps=6, approach_max_ticks=24, approach_max_walk_distance=12,
                              min_run_energy=1, compact_player_fn=None):
    """Cross the Al Kharid toll gate with exact approach, dialogue, and proof.

    This is a reusable object-transition primitive for scripts that already
    routed close to the gate. It intentionally discovers the live gate object
    after standing on the correct side because object 2882 is exposed at
    3268,3227 even when crossing west from the east-side tile.
    """
    direction = "east" if to_east else "west"
    player = ensure_run(player, min_run_energy, profile=profile, handle=handle, reason="al_kharid_toll_gate_" + direction)
    approach = al_kharid_toll_gate_approach_tile(to_east)
    player = _walk_exact_tile(
        player,
        approach,
        profile=profile,
        handle=handle,
        reason="al_kharid_toll_gate_" + direction + "_approach",
        max_ticks=approach_max_ticks,
        max_walk_distance=approach_max_walk_distance,
        compact_player_fn=compact_player_fn,
    )
    if al_kharid_toll_gate_crossed(player, to_east):
        return player
    if count_inventory_item(player, COINS) < 10:
        raise ObjectTransitionError("al_kharid_gate_toll_missing", "Al Kharid toll gate crossing needs 10 carried coins.", player)

    for attempt in range(1, int(attempts) + 1):
        if not _al_kharid_toll_gate_dialogue_active(player):
            gate = find_al_kharid_toll_gate_object(player, profile=profile)
            before = _transition_compact(player, compact_player_fn)
            opened = call_tool("interact_object", {
                "objectId": int(gate["objectId"]),
                "x": int(gate["x"]),
                "y": int(gate["y"]),
                "height": int(gate["height"]),
                "option": "open",
            }, profile=profile)
            player = _player_from_or(opened, player)
            write_event(handle, "al_kharid_toll_gate_interact", {
                "reason": reason,
                "direction": direction,
                "attempt": attempt,
                "object": gate,
                "success": bool(opened.get("success")),
                "message": opened.get("message"),
                "before": before,
                "player": _transition_compact(player, compact_player_fn),
            })
            if al_kharid_toll_gate_crossed(player, to_east):
                return player
            if not opened.get("success"):
                continue

        for dialogue_step in range(1, int(dialogue_steps) + 1):
            if al_kharid_toll_gate_crossed(player, to_east):
                return player
            if not _al_kharid_toll_gate_dialogue_active(player):
                break
            before = _transition_compact(player, compact_player_fn)
            action, result = _advance_al_kharid_toll_gate_dialogue(player, profile=profile)
            player = _player_from_or(result, player)
            write_event(handle, "al_kharid_toll_gate_dialogue", {
                "reason": reason,
                "direction": direction,
                "attempt": attempt,
                "dialogueStep": dialogue_step,
                "action": action,
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "before": before,
                "player": _transition_compact(player, compact_player_fn),
            })

        observed = observe(profile=profile)
        player = observed
        write_event(handle, "al_kharid_toll_gate_proof", {
            "reason": reason,
            "direction": direction,
            "attempt": attempt,
            "crossed": bool(al_kharid_toll_gate_crossed(player, to_east)),
            "player": _transition_compact(player, compact_player_fn),
        })
        if al_kharid_toll_gate_crossed(player, to_east):
            return player
        if count_inventory_item(player, COINS) < 10:
            raise ObjectTransitionError("al_kharid_gate_toll_missing", "Could not pay the Al Kharid toll gate from the {} side.".format("west" if to_east else "east"), player)

    raise ObjectTransitionError("al_kharid_gate_cross_failed", "Could not prove crossing {} through the Al Kharid toll gate.".format(direction), player)


def cross_taverley_white_wolf_gate(player, to_west=True, profile="", handle=None, reason="", attempts=3,
                                   approach_max_ticks=18, approach_max_walk_distance=12,
                                   cross_wait_ticks=12, min_run_energy=1, compact_player_fn=None):
    """Open and cross the Falador/Taverley gate at White Wolf Mountain.

    This is an MVP object-transition primitive for the gate around
    2935,3451,0. It stands on the known side tile, opens the live Gate object,
    immediately queues adjacent steps through the gate with object-transition
    clipping enabled, and proves the side change before returning.
    """
    direction = "west" if to_west else "east"
    player = ensure_run(player, min_run_energy, profile=profile, handle=handle, reason="taverley_white_wolf_gate_" + direction)
    approach = taverley_white_wolf_gate_approach_tile(to_west)
    player = _walk_exact_tile(
        player,
        approach,
        profile=profile,
        handle=handle,
        reason="taverley_white_wolf_gate_" + direction + "_approach",
        max_ticks=approach_max_ticks,
        max_walk_distance=approach_max_walk_distance,
        compact_player_fn=compact_player_fn,
    )
    if taverley_white_wolf_gate_crossed(player, to_west):
        return player

    for attempt in range(1, int(attempts) + 1):
        gate = find_taverley_white_wolf_gate_object(player, profile=profile)
        before = _transition_compact(player, compact_player_fn)
        opened = call_tool("interact_object", {
            "objectId": int(gate["objectId"]),
            "x": int(gate["x"]),
            "y": int(gate["y"]),
            "height": int(gate["height"]),
            "option": "open",
        }, profile=profile)
        player = _player_from_or(opened, player)
        write_event(handle, "taverley_white_wolf_gate_interact", {
            "reason": reason,
            "direction": direction,
            "attempt": attempt,
            "object": gate,
            "success": bool(opened.get("success")),
            "message": opened.get("message"),
            "before": before,
            "player": _transition_compact(player, compact_player_fn),
        })
        if taverley_white_wolf_gate_crossed(player, to_west):
            return player
        if opened.get("success"):
            if to_west:
                steps = [
                    {"x": 2935, "y": 3451, "height": 0},
                    {"x": 2934, "y": 3451, "height": 0},
                ]
            else:
                steps = [
                    {"x": 2935, "y": 3451, "height": 0},
                    {"x": 2936, "y": 3451, "height": 0},
                ]
            player = _walk_gate_transition_steps(
                player,
                steps,
                profile=profile,
                handle=handle,
                reason="taverley_white_wolf_gate_" + direction + "_{}".format(attempt),
                max_ticks=cross_wait_ticks,
                compact_player_fn=compact_player_fn,
            )
            if taverley_white_wolf_gate_crossed(player, to_west):
                return player

        observed = observe(profile=profile)
        player = observed
        write_event(handle, "taverley_white_wolf_gate_proof", {
            "reason": reason,
            "direction": direction,
            "attempt": attempt,
            "crossed": bool(taverley_white_wolf_gate_crossed(player, to_west)),
            "player": _transition_compact(player, compact_player_fn),
        })
        if taverley_white_wolf_gate_crossed(player, to_west):
            return player

    raise ObjectTransitionError(
        "taverley_white_wolf_gate_cross_failed",
        "Could not prove crossing {} through the Taverley White Wolf gate.".format(direction),
        player,
    )


def route_to(target, profile="", handle=None, reason="route", extra_args=None):
    player = observe(profile=profile)
    current = tile_string(tile_from_player(player))
    readiness = player.get("combatReadiness") or {}
    food = int(readiness.get("inventoryFoodCount", 0) or sum(
        int(item.get("amount", 1) or 1) for item in inventory(player) if item.get("foodHeal")
    ))
    coins = int(readiness.get("inventoryCoins", 0) or count_inventory_item(player, COINS))
    command = [
        sys.executable,
        str(ROUTE_ML),
        "define",
        "--from",
        current,
        "--to",
        str(target),
        "--combat-level",
        str(int(player.get("combatLevel", 0) or 0)),
        "--food",
        str(food),
        "--coins",
        str(coins),
        "--run-energy",
        str(int(player.get("runEnergy", 0) or 0)),
        "--planner",
        "fast",
        "--runner-max-batches",
        str((extra_args or {}).get("runner_max_batches", 8)),
        "--max-batch-distance",
        str((extra_args or {}).get("max_batch_distance", 24)),
    ]
    if bool(player.get("runEnabled", False)):
        command.append("--run-enabled")
    env = os.environ.copy()
    if profile:
        env["RS_PROFILE"] = profile
    write_event(handle, "route_define_start", {"reason": reason, "target": str(target), "command": command[1:]})
    defined = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    write_event(handle, "route_define_finish", {
        "reason": reason,
        "target": str(target),
        "returncode": defined.returncode,
        "stdoutTail": defined.stdout.strip().splitlines()[-8:],
        "stderr": defined.stderr.strip()[:1000],
    })
    if defined.returncode != 0:
        raise RuntimeError("route definition to {} failed: {}".format(target, defined.stderr.strip() or defined.stdout.strip()))
    definition = json.loads(defined.stdout)
    route_path = (definition.get("execution") or {}).get("routeDefinitionPath")
    if not route_path:
        raise RuntimeError("route definition to {} did not include a routeDefinitionPath".format(target))
    executor = [
        sys.executable,
        str(ROUTE_EXECUTOR),
        "--to",
        str(target),
        "--run-mode",
        str((extra_args or {}).get("run_mode", "auto")),
        "--eat-at",
        str((extra_args or {}).get("eat_at", 10)),
        "--route-definition",
        str(route_path),
    ]
    evidence = (extra_args or {}).get("evidence_jsonl")
    if evidence:
        executor.extend(["--evidence-jsonl", str(evidence)])
    write_event(handle, "route_execute_start", {
        "reason": reason,
        "target": str(target),
        "routeId": definition.get("routeId"),
        "status": definition.get("status"),
        "quality": definition.get("quality"),
        "safety": definition.get("safety"),
        "command": executor[1:],
    })
    proc = subprocess.run(
        executor,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    write_event(handle, "route_finish", {
        "reason": reason,
        "target": str(target),
        "routeId": definition.get("routeId"),
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout.strip().splitlines()[-8:],
        "stderr": proc.stderr.strip()[:1000],
    })
    if proc.returncode != 0:
        raise RuntimeError("route to {} failed: {}".format(target, proc.stderr.strip() or proc.stdout.strip()))
    return True
