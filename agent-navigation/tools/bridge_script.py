#!/usr/bin/env python3
"""Shared helpers for primitive-backed 2006Scape gameplay scripts."""

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"
ROUTE_ML = ROOT / "ml-routing" / "route_ml.py"
ROUTE_EXECUTOR = SCRIPT_DIR / "execute_route_definition.py"
COINS = 995
DEFAULT_BRIDGE_TOOL_URL = "http://127.0.0.1:43610/agent/tool"
DEFAULT_PROFILE = "MrFlame"


def safe_profile(value):
    text = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum() or ch in ("-", "_"))
    return text or "default"


def normalized_player_name(value):
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def session_file_for_profile(profile=""):
    override = os.environ.get("RSBRIDGE_SESSION_FILE")
    if override:
        return Path(override).expanduser()
    selected = profile or os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or ""
    if not selected or safe_profile(selected) == safe_profile(DEFAULT_PROFILE):
        return ROOT / ".local" / "rsbridge-session.json"
    return ROOT / ".local" / "rsbridge-session-{}.json".format(safe_profile(selected))


def expected_player_for_profile(profile=""):
    return os.environ.get("RSBRIDGE_EXPECT_PLAYER", profile or os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "")


def read_session(profile=""):
    path = session_file_for_profile(profile)
    if not path.exists():
        raise RuntimeError("bridge session file not found: {}".format(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = normalized_player_name(expected_player_for_profile(profile))
    actual = normalized_player_name(data.get("playerName"))
    if expected and actual and expected != actual:
        raise RuntimeError("session player mismatch: expected {} but session is {}".format(expected, actual))
    session_key = data.get("token")
    if not session_key:
        raise RuntimeError("bridge session credential missing: {}".format(path))
    return session_key


def log_tool_usage(tool_name, arguments):
    try:
        import usage_log
        usage_log.log_usage(
            "rs-tool",
            surface="direct",
            argv=[tool_name, json.dumps(arguments or {}, separators=(",", ":"))],
            cwd=REPO_ROOT,
        )
    except Exception:
        pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def call_tool_shell(tool_name, arguments=None, profile=""):
    """Call an rs bridge tool through the shell wrapper and return raw JSON."""
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


def call_tool_direct(tool_name, arguments=None, profile=""):
    """Call an rs bridge tool in-process and return the raw JSON response."""
    args = arguments or {}
    session_key = read_session(profile)
    payload = json.dumps({"tool": tool_name, "arguments": args}, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        os.environ.get("RSBRIDGE_TOOL_URL", DEFAULT_BRIDGE_TOOL_URL),
        data=payload,
        headers={
            "X-Agent-Token": session_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(os.environ.get("RSBRIDGE_TIMEOUT_SECONDS", "600"))
    log_tool_usage(tool_name, args)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError("{} failed: HTTP {} {}".format(tool_name, exc.code, detail[:500]))
    except urllib.error.URLError as exc:
        raise RuntimeError("{} failed: {}".format(tool_name, exc.reason))
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("{} returned invalid JSON: {}".format(tool_name, exc))


def call_tool(tool_name, arguments=None, profile=""):
    """Call an rs bridge tool and return the raw JSON response."""
    if os.environ.get("RSBRIDGE_USE_SHELL", "").lower() in ("1", "true", "yes", "on"):
        return call_tool_shell(tool_name, arguments, profile=profile)
    return call_tool_direct(tool_name, arguments, profile=profile)


def player_from(result):
    """Extract the player dict from a raw bridge or compact tool response."""
    player = result.get("player")
    if isinstance(player, dict):
        return player
    state = result.get("state")
    if isinstance(state, dict) and isinstance(state.get("player"), dict):
        return state["player"]
    raise RuntimeError("bridge response did not include player state")


def observe(profile=""):
    """Return the already-unwrapped player state from full observe_state."""
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
    tile = player.get("tile")
    if isinstance(tile, str):
        parts = tile.split(",")
        if len(parts) >= 3:
            try:
                return {
                    "x": int(parts[0]),
                    "y": int(parts[1]),
                    "height": int(parts[2]),
                }
            except (TypeError, ValueError):
                pass
    if isinstance(tile, dict):
        try:
            return {
                "x": int(tile.get("x", 0) or 0),
                "y": int(tile.get("y", 0) or 0),
                "height": int(tile.get("height", tile.get("h", 0)) or 0),
            }
        except (TypeError, ValueError):
            pass
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


def ensure_auto_retaliate_off(player, profile="", handle=None, reason="", compact_player_fn=None):
    result = call_tool("click_interface_button", {"buttonId": 151}, profile=profile)
    updated = _player_from_or(result, player)
    write_event(handle, "auto_retaliate_off", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": _transition_compact(updated, compact_player_fn),
    })
    return updated


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

EDGEVILLE_DUNGEON_SURFACE_APPROACH = {"x": 3096, "y": 3468, "height": 0}
EDGEVILLE_DUNGEON_CLOSED_OBJECT = {"objectId": 1568, "x": 3097, "y": 3468, "height": 0}
EDGEVILLE_DUNGEON_OPEN_TRAPDOOR = {"objectId": 10698, "x": 3097, "y": 3468, "height": 0}
EDGEVILLE_DUNGEON_UNDERGROUND_APPROACH = {"x": 3096, "y": 9868, "height": 0}
EDGEVILLE_DUNGEON_LADDER = {"objectId": 1755, "x": 3097, "y": 9867, "height": 0}
EDGEVILLE_DRUID_FIRST_GATE_APPROACH_WEST = {"x": 3103, "y": 9911, "height": 0}
EDGEVILLE_DRUID_FIRST_GATE_APPROACH_EAST = {"x": 3105, "y": 9909, "height": 0}
EDGEVILLE_DRUID_FIRST_GATE_NORTH = {"objectId": 1557, "x": 3103, "y": 9910, "height": 0}
EDGEVILLE_DRUID_FIRST_GATE_SOUTH = {"objectId": 1558, "x": 3103, "y": 9909, "height": 0}
EDGEVILLE_DRUID_SECOND_GATE_APPROACH_SOUTH = {"x": 3132, "y": 9916, "height": 0}
EDGEVILLE_DRUID_SECOND_GATE_APPROACH_NORTH = {"x": 3132, "y": 9919, "height": 0}
EDGEVILLE_DRUID_SECOND_GATE_WEST = {"objectId": 1596, "x": 3131, "y": 9917, "height": 0}
EDGEVILLE_DRUID_SECOND_GATE_EAST = {"objectId": 1597, "x": 3132, "y": 9917, "height": 0}

VARROCK_SEWER_SURFACE_APPROACH = {"x": 3238, "y": 3458, "height": 0}
VARROCK_SEWER_MANHOLE_TILE = {"x": 3237, "y": 3458, "height": 0}
VARROCK_SEWER_UNDERGROUND_APPROACH = {"x": 3237, "y": 9859, "height": 0}
VARROCK_SEWER_LADDER = {"objectId": 1755, "x": 3237, "y": 9858, "height": 0}
VARROCK_SEWER_MANHOLE_IDS = (882, 881, 883, 10321)


def _player_x(player):
    return int(tile_from_player(player)["x"])


def _player_y(player):
    return int(tile_from_player(player)["y"])


def _player_h(player):
    return int(tile_from_player(player)["height"])


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


def edgeville_dungeon_surface_side(player):
    return _player_h(player) == 0 and 3088 <= _player_x(player) <= 3104 and 3460 <= _player_y(player) <= 3476


def edgeville_dungeon_underground_side(player):
    return _player_h(player) == 0 and 3088 <= _player_x(player) <= 3104 and 9860 <= _player_y(player) <= 9878


def edgeville_druid_first_gate_east_side(player):
    return _player_h(player) == 0 and _player_x(player) >= 3104 and 9907 <= _player_y(player) <= 9912


def edgeville_druid_first_gate_west_side(player):
    return _player_h(player) == 0 and _player_x(player) <= 3103 and 9908 <= _player_y(player) <= 9915


def edgeville_druid_second_gate_north_side(player):
    return _player_h(player) == 0 and _player_y(player) >= 9919 and 3128 <= _player_x(player) <= 3135


def edgeville_druid_second_gate_south_side(player):
    return _player_h(player) == 0 and _player_y(player) <= 9916 and 3128 <= _player_x(player) <= 3135


def edgeville_druid_second_gate_midline(player):
    return _player_h(player) == 0 and _player_x(player) == 3132 and _player_y(player) in (9917, 9918)


def varrock_sewer_surface_side(player):
    return _player_h(player) == 0 and 3228 <= _player_x(player) <= 3248 and 3448 <= _player_y(player) <= 3468


def varrock_sewer_underground_side(player):
    return _player_h(player) == 0 and 3140 <= _player_x(player) <= 3248 and 9840 <= _player_y(player) <= 9920


def varrock_sewer_entry_underground_side(player):
    return _player_h(player) == 0 and 3228 <= _player_x(player) <= 3248 and 9848 <= _player_y(player) <= 9868


def _resolve_object_ref(object_ref, player, profile=""):
    if callable(object_ref):
        try:
            return object_ref(player, profile=profile)
        except TypeError:
            return object_ref(player)
    return object_ref


def find_varrock_sewer_manhole_object(player, profile=""):
    found = call_tool("find_nearest_object", {"name": "manhole", "maxDistance": 6}, profile=profile)
    obj = found.get("object") if isinstance(found, dict) else None
    if isinstance(obj, dict):
        try:
            object_id = int(obj.get("objectId", obj.get("id", -1)))
            x = int(obj.get("x"))
            y = int(obj.get("y"))
            h = int(obj.get("height", obj.get("h", 0)) or 0)
        except (TypeError, ValueError):
            object_id = -1
            x = y = h = 0
        if h == 0 and 3235 <= x <= 3239 and 3456 <= y <= 3460 and (
            object_id in VARROCK_SEWER_MANHOLE_IDS or "manhole" in str(obj.get("name", "")).lower()
        ):
            return {
                "objectId": object_id,
                "x": x,
                "y": y,
                "height": h,
                "source": "find_nearest_object",
            }

    return {
        "objectId": 882,
        "x": VARROCK_SEWER_MANHOLE_TILE["x"],
        "y": VARROCK_SEWER_MANHOLE_TILE["y"],
        "height": 0,
        "source": "fallback",
    }


def _interact_transition_object(player, object_ref, profile="", handle=None, reason="", option="open",
                                compact_player_fn=None):
    object_ref = _resolve_object_ref(object_ref, player, profile=profile)
    before = _transition_compact(player, compact_player_fn)
    result = call_tool("interact_object", {
        "objectId": int(object_ref["objectId"]),
        "x": int(object_ref["x"]),
        "y": int(object_ref["y"]),
        "height": int(object_ref.get("height", 0) or 0),
        "option": option,
    }, profile=profile)
    updated = _player_from_or(result, player)
    write_event(handle, "object_transition_interact", {
        "reason": reason,
        "object": object_ref,
        "option": option,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "before": before,
        "player": _transition_compact(updated, compact_player_fn),
    })
    return updated, result


def _walk_gate_transition_steps(player, steps, profile="", handle=None, reason="", max_ticks=12,
                                compact_player_fn=None):
    if not steps:
        return player
    player = observe(profile=profile)
    filtered_steps = []
    previous = tile_from_player(player)
    for step in steps:
        current_step = {
            "x": int(step["x"]),
            "y": int(step["y"]),
            "height": int(step.get("height", previous.get("height", 0)) or 0),
        }
        if tile_string(current_step) == tile_string(previous):
            continue
        dx = abs(int(current_step["x"]) - int(previous["x"]))
        dy = abs(int(current_step["y"]) - int(previous["y"]))
        if dx + dy == 1:
            filtered_steps.append(current_step)
            previous = current_step
            continue
        if filtered_steps:
            break
    if not filtered_steps:
        write_event(handle, "object_transition_walk_steps", {
            "reason": reason,
            "success": True,
            "message": "No remaining adjacent crossing steps after observing current tile.",
            "steps": steps,
            "player": _transition_compact(player, compact_player_fn),
        })
        return player
    result = call_tool("walk_path_steps", {
        "steps": filtered_steps,
        "run": bool(player.get("runEnabled", True)),
        "allowObjectTransition": True,
    }, profile=profile)
    queued = _player_from_or(result, player)
    write_event(handle, "object_transition_walk_steps", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "queuedSteps": result.get("queuedSteps"),
        "steps": filtered_steps,
        "requestedSteps": steps,
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


def walk_object_transition_steps(player, steps, profile="", handle=None, reason="", cross_wait_ticks=12,
                                 compact_player_fn=None):
    """Queue already-proven adjacent crossing steps without requiring an object click."""
    return _walk_gate_transition_steps(
        player,
        steps,
        profile=profile,
        handle=handle,
        reason=reason,
        max_ticks=cross_wait_ticks,
        compact_player_fn=compact_player_fn,
    )


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


def cross_directional_open_gate(player, transition, direction, approach, gate, steps, crossed_fn,
                                midline_fn=None, profile="", handle=None, reason="", attempts=3,
                                approach_max_ticks=40, approach_max_walk_distance=48,
                                cross_wait_ticks=12, min_run_energy=1, compact_player_fn=None):
    """Reusable primitive for simple timed gates: approach, open, step through, prove side.

    This covers the common non-dialogue gate family where the reliable behavior
    is not "click gate and trust pathfinding"; it is exact-side positioning plus
    immediate adjacent steps through the opened footprint. Location wrappers
    still own object ids, approach tiles, and proof predicates.
    """
    player = observe(profile=profile)
    for attempt in range(1, int(attempts) + 1):
        if crossed_fn(player):
            return player
        player = ensure_run(player, min_run_energy, profile=profile, handle=handle,
                            reason=transition + "_" + direction)
        player = ensure_auto_retaliate_off(
            player,
            profile=profile,
            handle=handle,
            reason=transition + "_" + direction,
            compact_player_fn=compact_player_fn,
        )
        player = observe(profile=profile)
        if crossed_fn(player):
            return player

        if midline_fn is not None and midline_fn(player):
            write_event(handle, "object_transition_approach", {
                "reason": transition + "_" + direction + "_midline_resume",
                "attempt": attempt,
                "destination": approach,
                "success": True,
                "message": "Resuming gate crossing from the gate line.",
                "player": _transition_compact(player, compact_player_fn),
            })
        else:
            player = _walk_exact_tile(
                player,
                approach,
                profile=profile,
                handle=handle,
                reason=transition + "_" + direction + "_approach",
                max_ticks=approach_max_ticks,
                max_walk_distance=approach_max_walk_distance,
                compact_player_fn=compact_player_fn,
                stop_on_combat=False,
            )
            if crossed_fn(player):
                return player
            resolved_gate = _resolve_object_ref(gate, player, profile=profile)
            player, _opened = _interact_transition_object(
                player,
                resolved_gate,
                profile=profile,
                handle=handle,
                reason=reason or transition + "_" + direction + "_open",
                option="open",
                compact_player_fn=compact_player_fn,
            )

        player = _walk_gate_transition_steps(
            player,
            steps,
            profile=profile,
            handle=handle,
            reason=transition + "_" + direction + "_cross",
            max_ticks=cross_wait_ticks,
            compact_player_fn=compact_player_fn,
        )
        player = observe(profile=profile)
        crossed = bool(crossed_fn(player))
        write_event(handle, "object_transition_proof", {
            "reason": reason or transition + "_" + direction,
            "transition": transition,
            "direction": direction,
            "attempt": attempt,
            "success": crossed,
            "player": _transition_compact(player, compact_player_fn),
        })
        if crossed:
            return player

    raise ObjectTransitionError(
        transition + "_cross_failed",
        "Could not prove crossing {} through {}.".format(direction, transition),
        player,
    )


def gate_transition_catalog():
    """Return known gate transition metadata grouped by primitive family.

    Keep this catalog small and proven. The route/combat scripts can identify a
    nearby gate by key, then execute the matching primitive instead of trying a
    raw object click and hoping the server pathfinder walks through in time.
    """
    return {
        "al_kharid_toll_gate": {
            "primitive": "toll_dialogue_gate",
            "directions": ("east", "west"),
            "notes": "Exact approach, click Gate, advance toll dialogue, prove side change.",
        },
        "taverley_white_wolf_gate": {
            "primitive": "simple_timed_open_gate",
            "directions": ("west", "east"),
            "notes": "Open the live Gate object and immediately queue adjacent steps through the opening.",
        },
        "edgeville_druid_first_gate": {
            "primitive": "chained_timed_open_gate",
            "directions": ("east", "west"),
            "notes": "Two-panel gate row; open the correct panel sequence, queue adjacent steps, prove side.",
        },
        "edgeville_druid_second_gate": {
            "primitive": "simple_timed_open_gate",
            "directions": ("north", "south"),
            "notes": "Combat-area gate; disable auto-retaliate, open, queue through-footprint steps, support midline resume.",
        },
    }


def _simple_gate_transition_specs():
    return {
        "taverley_white_wolf_gate": {
            "west": {
                "approach": TAVERLEY_WHITE_WOLF_GATE_EAST_APPROACH,
                "gate": find_taverley_white_wolf_gate_object,
                "steps": [
                    {"x": 2935, "y": 3451, "height": 0},
                    {"x": 2934, "y": 3451, "height": 0},
                ],
                "crossedFn": lambda player: taverley_white_wolf_gate_crossed(player, True),
                "approachMaxTicks": 18,
                "approachMaxWalkDistance": 12,
            },
            "east": {
                "approach": TAVERLEY_WHITE_WOLF_GATE_WEST_APPROACH,
                "gate": find_taverley_white_wolf_gate_object,
                "steps": [
                    {"x": 2935, "y": 3451, "height": 0},
                    {"x": 2936, "y": 3451, "height": 0},
                ],
                "crossedFn": lambda player: taverley_white_wolf_gate_crossed(player, False),
                "approachMaxTicks": 18,
                "approachMaxWalkDistance": 12,
            },
        },
        "edgeville_druid_second_gate": {
            "north": {
                "approach": EDGEVILLE_DRUID_SECOND_GATE_APPROACH_SOUTH,
                "gate": EDGEVILLE_DRUID_SECOND_GATE_WEST,
                "steps": [
                    {"x": 3132, "y": 9917, "height": 0},
                    {"x": 3132, "y": 9918, "height": 0},
                    {"x": 3132, "y": 9919, "height": 0},
                ],
                "crossedFn": edgeville_druid_second_gate_north_side,
                "midlineFn": edgeville_druid_second_gate_midline,
                "approachMaxTicks": 40,
                "approachMaxWalkDistance": 48,
            },
            "south": {
                "approach": EDGEVILLE_DRUID_SECOND_GATE_APPROACH_NORTH,
                "gate": EDGEVILLE_DRUID_SECOND_GATE_EAST,
                "steps": [
                    {"x": 3132, "y": 9917, "height": 0},
                    {"x": 3132, "y": 9916, "height": 0},
                ],
                "crossedFn": edgeville_druid_second_gate_south_side,
                "midlineFn": edgeville_druid_second_gate_midline,
                "approachMaxTicks": 40,
                "approachMaxWalkDistance": 48,
            },
        },
    }


def cross_known_simple_gate(player, transition, direction, profile="", handle=None, reason="",
                            attempts=3, cross_wait_ticks=12, min_run_energy=1,
                            approach_max_ticks=None, approach_max_walk_distance=None,
                            compact_player_fn=None):
    specs = _simple_gate_transition_specs()
    if transition not in specs or direction not in specs[transition]:
        raise ObjectTransitionError(
            "unknown_simple_gate_transition",
            "No simple timed gate primitive is registered for {} {}.".format(transition, direction),
            player,
        )
    spec = specs[transition][direction]
    return cross_directional_open_gate(
        player,
        transition,
        direction,
        spec["approach"],
        spec["gate"],
        spec["steps"],
        spec["crossedFn"],
        midline_fn=spec.get("midlineFn"),
        profile=profile,
        handle=handle,
        reason=reason,
        attempts=attempts,
        approach_max_ticks=approach_max_ticks or spec.get("approachMaxTicks", 40),
        approach_max_walk_distance=approach_max_walk_distance or spec.get("approachMaxWalkDistance", 48),
        cross_wait_ticks=cross_wait_ticks,
        min_run_energy=min_run_energy,
        compact_player_fn=compact_player_fn,
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


def enter_edgeville_dungeon_trapdoor(player, profile="", handle=None, reason="", compact_player_fn=None):
    """Use the proven Edgeville trapdoor transition south of the bank.

    The cache walk target for the visible trapdoor can be wrong in this runtime;
    stand at 3096,3468,0, open object 1568 at 3097,3468,0 if needed, then use
    open trapdoor 10698 at 3097,3468,0. Proof is the underground entrance tile
    band around 3096,9868,0.
    """
    player = observe(profile=profile)
    if edgeville_dungeon_underground_side(player):
        return player
    player = ensure_run(player, 1, profile=profile, handle=handle, reason="edgeville_dungeon_trapdoor_enter")
    player = _walk_exact_tile(
        player,
        EDGEVILLE_DUNGEON_SURFACE_APPROACH,
        profile=profile,
        handle=handle,
        reason="edgeville_dungeon_trapdoor_surface_approach",
        max_ticks=40,
        max_walk_distance=48,
        compact_player_fn=compact_player_fn,
    )

    # Try the already-open trapdoor first. If the closed cover is present, open
    # it and immediately use the proven open-trapdoor object.
    player, result = _interact_transition_object(
        player,
        EDGEVILLE_DUNGEON_OPEN_TRAPDOOR,
        profile=profile,
        handle=handle,
        reason=reason or "edgeville_dungeon_trapdoor_enter_open",
        option="first",
        compact_player_fn=compact_player_fn,
    )
    waited = call_tool("wait_until_idle", {"maxTicks": 8, "movement": True, "skilling": False, "combat": False}, profile=profile)
    player = _player_from_or(waited, player)
    if not edgeville_dungeon_underground_side(player):
        player = observe(profile=profile)
    if edgeville_dungeon_underground_side(player):
        write_event(handle, "object_transition_proof", {
            "reason": reason or "edgeville_dungeon_trapdoor_enter",
            "transition": "edgeville_dungeon_trapdoor",
            "direction": "down",
            "success": True,
            "player": _transition_compact(player, compact_player_fn),
        })
        return player

    player, _opened = _interact_transition_object(
        player,
        EDGEVILLE_DUNGEON_CLOSED_OBJECT,
        profile=profile,
        handle=handle,
        reason=reason or "edgeville_dungeon_trapdoor_open_cover",
        option="open",
        compact_player_fn=compact_player_fn,
    )
    waited = call_tool("wait_until_idle", {"maxTicks": 4, "movement": True, "skilling": False, "combat": False}, profile=profile)
    player = _player_from_or(waited, player)
    if not _same_player_tile_ref(player, EDGEVILLE_DUNGEON_SURFACE_APPROACH):
        player = _walk_exact_tile(
            player,
            EDGEVILLE_DUNGEON_SURFACE_APPROACH,
            profile=profile,
            handle=handle,
            reason="edgeville_dungeon_trapdoor_surface_reapproach",
            max_ticks=12,
            max_walk_distance=12,
            compact_player_fn=compact_player_fn,
        )
    player, _used = _interact_transition_object(
        player,
        EDGEVILLE_DUNGEON_OPEN_TRAPDOOR,
        profile=profile,
        handle=handle,
        reason=reason or "edgeville_dungeon_trapdoor_enter_after_open",
        option="first",
        compact_player_fn=compact_player_fn,
    )
    waited = call_tool("wait_until_idle", {"maxTicks": 10, "movement": True, "skilling": False, "combat": False}, profile=profile)
    player = _player_from_or(waited, player)
    if not edgeville_dungeon_underground_side(player):
        player = observe(profile=profile)
    if edgeville_dungeon_underground_side(player):
        write_event(handle, "object_transition_proof", {
            "reason": reason or "edgeville_dungeon_trapdoor_enter",
            "transition": "edgeville_dungeon_trapdoor",
            "direction": "down",
            "success": True,
            "player": _transition_compact(player, compact_player_fn),
        })
        return player
    raise ObjectTransitionError(
        "edgeville_dungeon_trapdoor_enter_failed",
        "Could not prove descent through the Edgeville dungeon trapdoor.",
        player,
    )


def exit_edgeville_dungeon_trapdoor(player, profile="", handle=None, reason="", compact_player_fn=None):
    """Use the proven Edgeville dungeon ladder back to the surface trapdoor tile."""
    player = observe(profile=profile)
    if edgeville_dungeon_surface_side(player):
        return player
    player = ensure_run(player, 1, profile=profile, handle=handle, reason="edgeville_dungeon_trapdoor_exit")
    player = _walk_exact_tile(
        player,
        EDGEVILLE_DUNGEON_UNDERGROUND_APPROACH,
        profile=profile,
        handle=handle,
        reason="edgeville_dungeon_ladder_approach",
        max_ticks=40,
        max_walk_distance=48,
        compact_player_fn=compact_player_fn,
        stop_on_combat=False,
    )
    player, _used = _interact_transition_object(
        player,
        EDGEVILLE_DUNGEON_LADDER,
        profile=profile,
        handle=handle,
        reason=reason or "edgeville_dungeon_ladder_exit",
        option="first",
        compact_player_fn=compact_player_fn,
    )
    waited = call_tool("wait_until_idle", {"maxTicks": 10, "movement": True, "skilling": False, "combat": False}, profile=profile)
    player = _player_from_or(waited, player)
    if not edgeville_dungeon_surface_side(player):
        player = observe(profile=profile)
    if edgeville_dungeon_surface_side(player):
        write_event(handle, "object_transition_proof", {
            "reason": reason or "edgeville_dungeon_ladder_exit",
            "transition": "edgeville_dungeon_trapdoor",
            "direction": "up",
            "success": True,
            "player": _transition_compact(player, compact_player_fn),
        })
        return player
    raise ObjectTransitionError(
        "edgeville_dungeon_ladder_exit_failed",
        "Could not prove exit through the Edgeville dungeon ladder.",
        player,
    )


def enter_varrock_sewer_manhole(player, profile="", handle=None, reason="", compact_player_fn=None):
    """Enter Varrock sewer through the manhole east of Varrock palace.

    The matching exit proof is Ladder 1755 at 3237,9858,0, which climbs back
    to 3238,3458,0. On the surface, stand east of the manhole and try the live
    Manhole object first so object id variants can be discovered by the cache.
    """
    player = observe(profile=profile)
    if varrock_sewer_underground_side(player):
        return player
    player = ensure_run(player, 1, profile=profile, handle=handle, reason="varrock_sewer_manhole_enter")
    player = _walk_exact_tile(
        player,
        VARROCK_SEWER_SURFACE_APPROACH,
        profile=profile,
        handle=handle,
        reason="varrock_sewer_manhole_surface_approach",
        max_ticks=80,
        max_walk_distance=80,
        compact_player_fn=compact_player_fn,
        stop_on_combat=False,
    )

    tried = []
    for attempt in range(1, 7):
        live = find_varrock_sewer_manhole_object(player, profile=profile)
        candidates = [live]
        for object_id in VARROCK_SEWER_MANHOLE_IDS:
            candidates.append({
                "objectId": object_id,
                "x": VARROCK_SEWER_MANHOLE_TILE["x"],
                "y": VARROCK_SEWER_MANHOLE_TILE["y"],
                "height": 0,
                "source": "fallback_variant",
            })
        for object_ref in candidates:
            key = (int(object_ref["objectId"]), int(object_ref["x"]), int(object_ref["y"]), "open" if attempt == 1 else "first")
            if key in tried:
                continue
            tried.append(key)
            option = "open" if attempt == 1 else "first"
            player, _used = _interact_transition_object(
                player,
                object_ref,
                profile=profile,
                handle=handle,
                reason=reason or "varrock_sewer_manhole_enter",
                option=option,
                compact_player_fn=compact_player_fn,
            )
            waited = call_tool("wait_until_idle", {
                "maxTicks": 10,
                "movement": True,
                "skilling": False,
                "combat": False,
            }, profile=profile)
            player = _player_from_or(waited, player)
            player = observe(profile=profile)
            if varrock_sewer_underground_side(player):
                write_event(handle, "object_transition_proof", {
                    "reason": reason or "varrock_sewer_manhole_enter",
                    "transition": "varrock_sewer_manhole",
                    "direction": "down",
                    "success": True,
                    "object": object_ref,
                    "player": _transition_compact(player, compact_player_fn),
                })
                return player
            if not _same_player_tile_ref(player, VARROCK_SEWER_SURFACE_APPROACH):
                player = _walk_exact_tile(
                    player,
                    VARROCK_SEWER_SURFACE_APPROACH,
                    profile=profile,
                    handle=handle,
                    reason="varrock_sewer_manhole_surface_reapproach",
                    max_ticks=20,
                    max_walk_distance=20,
                    compact_player_fn=compact_player_fn,
                    stop_on_combat=False,
                )

    raise ObjectTransitionError(
        "varrock_sewer_manhole_enter_failed",
        "Could not prove descent through the Varrock sewer manhole.",
        player,
    )


def exit_varrock_sewer_ladder(player, profile="", handle=None, reason="", compact_player_fn=None):
    """Exit Varrock sewer through Ladder 1755 at 3237,9858,0."""
    player = observe(profile=profile)
    if varrock_sewer_surface_side(player):
        return player
    player = ensure_run(player, 1, profile=profile, handle=handle, reason="varrock_sewer_ladder_exit")
    player = _walk_exact_tile(
        player,
        VARROCK_SEWER_UNDERGROUND_APPROACH,
        profile=profile,
        handle=handle,
        reason="varrock_sewer_ladder_approach",
        max_ticks=160,
        max_walk_distance=160,
        compact_player_fn=compact_player_fn,
        stop_on_combat=False,
    )
    player, _used = _interact_transition_object(
        player,
        VARROCK_SEWER_LADDER,
        profile=profile,
        handle=handle,
        reason=reason or "varrock_sewer_ladder_exit",
        option="first",
        compact_player_fn=compact_player_fn,
    )
    waited = call_tool("wait_until_idle", {
        "maxTicks": 10,
        "movement": True,
        "skilling": False,
        "combat": False,
    }, profile=profile)
    player = _player_from_or(waited, player)
    player = observe(profile=profile)
    if varrock_sewer_surface_side(player):
        write_event(handle, "object_transition_proof", {
            "reason": reason or "varrock_sewer_ladder_exit",
            "transition": "varrock_sewer_manhole",
            "direction": "up",
            "success": True,
            "player": _transition_compact(player, compact_player_fn),
        })
        return player
    raise ObjectTransitionError(
        "varrock_sewer_ladder_exit_failed",
        "Could not prove exit through the Varrock sewer ladder.",
        player,
    )


def cross_edgeville_druid_first_gate(player, to_east=True, profile="", handle=None, reason="",
                                     compact_player_fn=None):
    """Cross the first Edgeville dungeon druid gate near 3103,9910."""
    player = observe(profile=profile)
    direction = "east" if to_east else "west"
    if to_east and edgeville_druid_first_gate_east_side(player):
        return player
    if not to_east and edgeville_druid_first_gate_west_side(player):
        return player
    player = ensure_run(player, 1, profile=profile, handle=handle,
                        reason="edgeville_druid_first_gate_" + direction)
    player = ensure_auto_retaliate_off(
        player,
        profile=profile,
        handle=handle,
        reason="edgeville_druid_first_gate_" + direction,
        compact_player_fn=compact_player_fn,
    )

    if to_east:
        player = _walk_exact_tile(
            player,
            EDGEVILLE_DRUID_FIRST_GATE_APPROACH_WEST,
            profile=profile,
            handle=handle,
            reason="edgeville_druid_first_gate_east_approach",
            max_ticks=40,
            max_walk_distance=48,
            compact_player_fn=compact_player_fn,
            stop_on_combat=False,
        )
        player, _opened = _interact_transition_object(
            player,
            EDGEVILLE_DRUID_FIRST_GATE_NORTH,
            profile=profile,
            handle=handle,
            reason=reason or "edgeville_druid_first_gate_east_open_north",
            option="open",
            compact_player_fn=compact_player_fn,
        )
        player = _walk_gate_transition_steps(
            player,
            [{"x": 3103, "y": 9910, "height": 0}, {"x": 3103, "y": 9909, "height": 0}],
            profile=profile,
            handle=handle,
            reason="edgeville_druid_first_gate_east_old_row",
            max_ticks=10,
            compact_player_fn=compact_player_fn,
        )
        player, _opened = _interact_transition_object(
            player,
            EDGEVILLE_DRUID_FIRST_GATE_SOUTH,
            profile=profile,
            handle=handle,
            reason=reason or "edgeville_druid_first_gate_east_open_south",
            option="open",
            compact_player_fn=compact_player_fn,
        )
        player = _walk_gate_transition_steps(
            player,
            [{"x": 3104, "y": 9909, "height": 0}, {"x": 3105, "y": 9909, "height": 0}],
            profile=profile,
            handle=handle,
            reason="edgeville_druid_first_gate_east_cross",
            max_ticks=10,
            compact_player_fn=compact_player_fn,
        )
    else:
        player = _walk_exact_tile(
            player,
            {"x": 3104, "y": 9909, "height": 0},
            profile=profile,
            handle=handle,
            reason="edgeville_druid_first_gate_west_approach",
            max_ticks=40,
            max_walk_distance=48,
            compact_player_fn=compact_player_fn,
            stop_on_combat=False,
        )
        player, _opened = _interact_transition_object(
            player,
            EDGEVILLE_DRUID_FIRST_GATE_SOUTH,
            profile=profile,
            handle=handle,
            reason=reason or "edgeville_druid_first_gate_west_open_south",
            option="open",
            compact_player_fn=compact_player_fn,
        )
        player = _walk_gate_transition_steps(
            player,
            [
                {"x": 3103, "y": 9909, "height": 0},
                {"x": 3103, "y": 9910, "height": 0},
                {"x": 3103, "y": 9911, "height": 0},
            ],
            profile=profile,
            handle=handle,
            reason="edgeville_druid_first_gate_west_cross",
            max_ticks=12,
            compact_player_fn=compact_player_fn,
        )

    player = observe(profile=profile)
    crossed = edgeville_druid_first_gate_east_side(player) if to_east else edgeville_druid_first_gate_west_side(player)
    write_event(handle, "object_transition_proof", {
        "reason": reason or "edgeville_druid_first_gate_" + direction,
        "transition": "edgeville_druid_first_gate",
        "direction": direction,
        "success": bool(crossed),
        "player": _transition_compact(player, compact_player_fn),
    })
    if crossed:
        return player
    raise ObjectTransitionError(
        "edgeville_druid_first_gate_cross_failed",
        "Could not prove crossing {} through the first Edgeville druid gate.".format(direction),
        player,
    )


def cross_edgeville_druid_second_gate(player, to_north=True, profile="", handle=None, reason="",
                                      compact_player_fn=None):
    """Cross the second Edgeville dungeon druid gate near 3131,9917.

    This gate is an east-west barrier. The proven inbound sequence is
    south-to-north: stand 3132,9916, open 1596 at 3131,9917, then run through
    3132,9917 -> 3132,9919.
    """
    player = observe(profile=profile)
    direction = "north" if to_north else "south"
    if to_north and edgeville_druid_second_gate_north_side(player):
        return player
    if not to_north and edgeville_druid_second_gate_south_side(player):
        return player

    return cross_known_simple_gate(
        player,
        "edgeville_druid_second_gate",
        direction,
        profile=profile,
        handle=handle,
        reason=reason,
        attempts=3,
        cross_wait_ticks=12,
        compact_player_fn=compact_player_fn,
    )


def enter_edgeville_druid_room_gates(player, profile="", handle=None, reason="", compact_player_fn=None):
    player = cross_edgeville_druid_first_gate(
        player,
        to_east=True,
        profile=profile,
        handle=handle,
        reason=reason or "edgeville_druid_first_gate_enter",
        compact_player_fn=compact_player_fn,
    )
    player = _walk_exact_tile(
        player,
        EDGEVILLE_DRUID_SECOND_GATE_APPROACH_SOUTH,
        profile=profile,
        handle=handle,
        reason="edgeville_druid_second_gate_enter_approach",
        max_ticks=80,
        max_walk_distance=64,
        compact_player_fn=compact_player_fn,
        stop_on_combat=False,
    )
    return cross_edgeville_druid_second_gate(
        player,
        to_north=True,
        profile=profile,
        handle=handle,
        reason=reason or "edgeville_druid_second_gate_enter",
        compact_player_fn=compact_player_fn,
    )


def leave_edgeville_druid_room_gates(player, profile="", handle=None, reason="", compact_player_fn=None):
    player = cross_edgeville_druid_second_gate(
        player,
        to_north=False,
        profile=profile,
        handle=handle,
        reason=reason or "edgeville_druid_second_gate_exit",
        compact_player_fn=compact_player_fn,
    )
    player = _walk_exact_tile(
        player,
        {"x": 3104, "y": 9909, "height": 0},
        profile=profile,
        handle=handle,
        reason="edgeville_druid_first_gate_exit_approach",
        max_ticks=90,
        max_walk_distance=64,
        compact_player_fn=compact_player_fn,
        stop_on_combat=False,
    )
    return cross_edgeville_druid_first_gate(
        player,
        to_east=False,
        profile=profile,
        handle=handle,
        reason=reason or "edgeville_druid_first_gate_exit",
        compact_player_fn=compact_player_fn,
    )


def _walk_exact_tile(player, destination, profile="", handle=None, reason="", max_ticks=24,
                     max_walk_distance=12, compact_player_fn=None, stop_on_combat=True):
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
        "stopOnCombat": bool(stop_on_combat),
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
        waited = call_tool("wait_until_idle", {
            "maxTicks": 6,
            "movement": True,
            "skilling": False,
            "combat": False,
        }, profile=profile)
        updated = _player_from_or(waited, updated)
    if not _same_player_tile(updated, x, y, h) and chebyshev(tile_from_player(updated), destination) <= 8:
        retry = call_tool("walk_to_tile_until_arrived", {
            "x": x,
            "y": y,
            "height": h,
            "stopDistance": 0,
            "maxTicks": max(12, min(int(max_ticks), 24)),
            "maxWalkDistance": int(max_walk_distance),
            "stopOnCombat": bool(stop_on_combat),
            "stopOnStall": True,
        }, profile=profile)
        updated = _player_from_or(retry, updated)
        write_event(handle, "object_transition_approach", {
            "reason": reason + "_retry",
            "destination": destination,
            "success": bool(retry.get("success")),
            "message": retry.get("message"),
            "batchStatus": retry.get("batchStatus"),
            "batchTicks": retry.get("batchTicks"),
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
    return cross_known_simple_gate(
        player,
        "taverley_white_wolf_gate",
        direction,
        profile=profile,
        handle=handle,
        reason=reason,
        attempts=attempts,
        cross_wait_ticks=cross_wait_ticks,
        min_run_energy=min_run_energy,
        approach_max_ticks=approach_max_ticks,
        approach_max_walk_distance=approach_max_walk_distance,
        compact_player_fn=compact_player_fn,
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
