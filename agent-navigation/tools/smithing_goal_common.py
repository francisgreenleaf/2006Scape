#!/usr/bin/env python3
"""Shared helpers for the Smithing progression phase runners."""

import datetime as dt
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import bridge_script as bridge


ROOT = bridge.ROOT
REPO_ROOT = bridge.REPO_ROOT
SCRIPT_DIR = bridge.SCRIPT_DIR
ML2_DEFINE = ROOT / "ml2-routing" / "route_ml_XS.py"
LOCAL_DIR = ROOT / ".local"
RUNS_DIR = ROOT / "data" / "smithing" / "runs"

COINS = 995
COPPER = 436
TIN = 438
IRON_ORE = 440
COAL = 453
HAMMER = 2347
BRONZE_BAR = 2349
STEEL_BAR = 2353
RUNE_PICKAXE = 1275

AL_KHARID_BANK = "al_kharid_bank"
AL_KHARID_BANK_TILE = {"x": 3269, "y": 3167, "height": 0}
AL_KHARID_FURNACE = "al kharid furnace"
AL_KHARID_FURNACE_TILE = {"x": 3275, "y": 3186, "height": 0}
VARROCK_WEST_BANK = "varrock_west_bank"
VARROCK_WEST_BANK_TILE = {"x": 3185, "y": 3436, "height": 0}
VARROCK_WEST_ANVILS = "varrock west anvils"
VARROCK_WEST_ANVILS_TILE = {"x": 3188, "y": 3425, "height": 0}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def log(message, args):
    if not getattr(args, "quiet", False):
        print(message, flush=True)


def write_event(handle, event, data):
    bridge.write_event(handle, event, data)


def safe_profile(profile):
    value = str(profile or "default").strip().lower()
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-") or "default"


def status_path(profile, name):
    return LOCAL_DIR / "{}-{}.json".format(safe_profile(profile), name)


def write_status(profile, name, payload):
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data["profile"] = profile
    data["updatedAt"] = utc_now()
    path = status_path(profile, name)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_status(profile, name):
    path = status_path(profile, name)
    if not path.exists():
        return {"profile": profile, "status": "missing", "path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def xp_for_level(level):
    points = 0
    for current in range(1, int(level)):
        points += math.floor(current + 300 * (2 ** (current / 7.0)))
    return math.floor(points / 4)


def tile_string(tile):
    return "{},{},{}".format(int(tile["x"]), int(tile["y"]), int(tile.get("height", 0) or 0))


def tile_from_player(player):
    return bridge.tile_from_player(player)


def chebyshev(a, b):
    return bridge.chebyshev(a, b)


def near_tile(player, tile, radius):
    return chebyshev(tile_from_player(player), tile) <= int(radius)


def compact(player):
    return bridge.compact_player(player, ("mining", "smithing"))


def open_run_log(script_name, args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / "{}-{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        script_name,
        os.getpid(),
    )
    return path, (None if getattr(args, "no_log", False) else path.open("a", encoding="utf-8"))


def close_interfaces(profile):
    bridge.call_tool("close_interfaces", {}, profile=profile)


def count_items(profile, item_ids):
    result = bridge.call_tool("bank_item_count_XS", {"itemIds": [int(item_id) for item_id in item_ids]}, profile=profile)
    items = {}
    for item in result.get("items") or []:
        item_id = int(item.get("id", item.get("itemId", 0)) or 0)
        items[item_id] = {
            "bank": int(item.get("bankAmount", 0) or 0),
            "inventory": int(item.get("inventoryAmount", 0) or 0),
            "equipment": int(item.get("equipmentAmount", 0) or 0),
            "total": int(item.get("totalAmount", 0) or 0),
            "name": item.get("name", ""),
        }
    for item_id in item_ids:
        items.setdefault(int(item_id), {"bank": 0, "inventory": 0, "equipment": 0, "total": 0, "name": ""})
    return items, bridge.player_from(result)


def inventory_item_ids(player, keep_ids=()):
    keep = {int(item_id) for item_id in keep_ids}
    seen = set()
    result = []
    for item in bridge.inventory(player):
        item_id = int(item.get("id", item.get("itemId", -1)) or -1)
        if item_id < 0 or item_id in keep or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item_id)
    return result


def deposit_all_except(player, profile, keep_ids=(), handle=None, reason="deposit_all_except"):
    item_ids = inventory_item_ids(player, keep_ids=keep_ids)
    if not item_ids:
        return player
    result = bridge.call_tool("deposit_inventory_items_XS", {"itemIds": item_ids}, profile=profile)
    updated = bridge._player_from_or(result, player)
    write_event(handle, "deposit_all_except", {
        "reason": reason,
        "itemIds": item_ids,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact(updated),
    })
    return updated


def withdraw_item(player, profile, item_id, amount, handle=None, reason="withdraw"):
    if int(amount) <= 0:
        return player
    result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": int(item_id), "amount": int(amount)}, profile=profile)
    updated = bridge._player_from_or(result, player)
    write_event(handle, "withdraw_item", {
        "reason": reason,
        "itemId": int(item_id),
        "amount": int(amount),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact(updated),
    })
    if not result.get("success"):
        raise RuntimeError("withdraw {} x{} failed: {}".format(item_id, amount, result.get("message")))
    return updated


def ensure_coin_float_for_route(player, profile, amount, handle=None):
    if int(amount) <= 0 or not bool(player.get("inBankArea", False)):
        return player
    carried = bridge.count_inventory_item(player, COINS)
    if carried >= int(amount):
        return player
    counts, player = count_items(profile, [COINS])
    needed = min(int(amount) - carried, counts[COINS]["bank"])
    if needed > 0:
        player = withdraw_item(player, profile, COINS, needed, handle=handle, reason="route_coin_float")
    return player


def run_subprocess(command, profile, handle, event, args, expect_json=False, timeout=None):
    env = os.environ.copy()
    if profile:
        env["RS_PROFILE"] = profile
        env["RSBRIDGE_PROFILE"] = profile
    try:
        proc = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        write_event(handle, event, {
            "command": command,
            "timeoutSeconds": int(timeout or 0),
            "stdoutTail": [line for line in (exc.stdout or "").splitlines() if line.strip()][-10:],
            "stderrTail": [line for line in (exc.stderr or "").splitlines() if line.strip()][-10:],
        })
        raise RuntimeError("{} timed out after {} seconds".format(event, int(timeout or 0)))
    stdout_lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    stderr_lines = [line for line in (proc.stderr or "").splitlines() if line.strip()]
    write_event(handle, event, {
        "command": command,
        "returncode": int(proc.returncode),
        "stdoutTail": stdout_lines[-10:],
        "stderrTail": stderr_lines[-10:],
    })
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(event, "\n".join(stderr_lines[-4:] or stdout_lines[-4:])))
    if expect_json:
        return json.loads(proc.stdout)
    if stdout_lines and not getattr(args, "quiet", False):
        log("{}: {}".format(event, stdout_lines[-1]), args)
    return None


def ml2_route_to(profile, target, handle, reason, args, arrival_radius=4):
    player = bridge.observe_xs(profile=profile)
    target_tile = None
    if isinstance(target, dict):
        target_tile = target
        target_value = tile_string(target)
    else:
        target_value = str(target)
    if target_tile and near_tile(player, target_tile, arrival_radius):
        return player
    command = [
        sys.executable,
        str(ML2_DEFINE),
        "define",
        "--from",
        tile_string(tile_from_player(player)),
        "--to",
        target_value,
        "--combat-level",
        str(int(player.get("combatLevel", player.get("cb", 3)) or 3)),
        "--food",
        "0",
        "--run-energy",
        str(int(player.get("runEnergy", 0) or 0)),
    ]
    if player.get("runEnabled"):
        command.append("--run-enabled")
    definition = run_subprocess(command, profile, handle, "ml2_route_define", args, expect_json=True)
    if definition.get("status") != "ok" or not definition.get("path"):
        raise RuntimeError("ML2 route to {} failed with status {}".format(target_value, definition.get("status")))
    route_path = REPO_ROOT / definition["path"]
    route_definition = json.loads(route_path.read_text(encoding="utf-8"))
    exec_command = route_definition.get("execution", {}).get("command")
    if not exec_command:
        raise RuntimeError("ML2 route definition had no execution command: {}".format(route_path))
    run_subprocess(exec_command, profile, handle, "ml2_route_execute", args)
    write_event(handle, "route_complete", {"reason": reason, "target": target_value, "routePath": str(route_path)})
    return bridge.observe_xs(profile=profile)


def ensure_bank_at(profile, bank_place, bank_tile, handle, args, coin_float=0, radius=10):
    player = bridge.observe_xs(profile=profile)
    if bool(player.get("inBankArea", False)) and near_tile(player, bank_tile, radius):
        return player
    if bool(player.get("inBankArea", False)) and coin_float > 0:
        player = ensure_coin_float_for_route(player, profile, coin_float, handle=handle)
    close_interfaces(profile)
    player = ml2_route_to(profile, bank_place, handle, "bank:{}".format(bank_place), args, arrival_radius=radius)
    if not bool(player.get("inBankArea", False)):
        player = bridge.observe_xs(profile=profile)
    if not bool(player.get("inBankArea", False)):
        raise RuntimeError("arrived near {} but not in a bank area".format(bank_place))
    return player


def smelt_load_size(possible, needed, hard_cap=10):
    possible = int(possible)
    needed = max(1, int(needed))
    return max(1, min(possible, needed, int(hard_cap)))
