#!/usr/bin/env python3
"""Shared helpers for primitive-backed 2006Scape gameplay scripts."""

import datetime as dt
import json
import os
import subprocess
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"
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


def route_to(target, profile="", handle=None, reason="route", extra_args=None):
    command = [str(ROUTE_RUNNER), "--to", str(target), "--run-reserve", "auto"]
    for key, value in (extra_args or {}).items():
        if value is None or value is False:
            continue
        command.append("--{}".format(key.replace("_", "-")))
        if value is not True:
            command.append(str(value))
    env = os.environ.copy()
    if profile:
        env["RS_PROFILE"] = profile
    write_event(handle, "route_start", {"reason": reason, "target": str(target), "command": command[1:]})
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    write_event(handle, "route_finish", {
        "reason": reason,
        "target": str(target),
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout.strip().splitlines()[-8:],
        "stderr": proc.stderr.strip()[:1000],
    })
    if proc.returncode != 0:
        raise RuntimeError("route to {} failed: {}".format(target, proc.stderr.strip() or proc.stdout.strip()))
    return True
