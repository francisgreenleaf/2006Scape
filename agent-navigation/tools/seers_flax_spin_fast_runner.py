#!/usr/bin/env python3
"""Fast Seers flax picker and bowstring spinner.

Standalone runner: pick flax near Seers, climb to the spinning wheel, spin a
full inventory into bowstrings, bank, and repeat using compact bridge tools.
"""

import argparse
import datetime as dt
import json
import math
import os
import sys
import time
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
RUNS_DIR = ROOT / "data" / "crafting" / "seers-flax-fast-runs"
CONTROL_DIR = ROOT / ".local" / "runners"
TERMINAL_PHASES = {
    "blocked",
    "complete",
    "stopped",
}

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
import cache_world_map  # noqa: E402
from profile_utils import resolve_profile, safe_profile  # noqa: E402
from tick_analysis import TickEventWriter  # noqa: E402


EVENT_WRITER = TickEventWriter()


FLAX = 1779
BOW_STRING = 1777
KNIFE = 946
RUNE_AXE = 1359
FLAX_OBJECT = 2646
FLAX_OBJECTS = [FLAX_OBJECT]
SPINNING_WHEEL = 2644
GROUND_LADDER = 1747
UPSTAIRS_LADDER = 1746
SPIN_BUTTON = 34186
SERVER_TICK_SECONDS = 0.6
PICKABLE_GLOBAL_COOLDOWN_TICKS = 1
PICKABLE_RESPAWN_TICKS = 5
PICK_COOLDOWN_BUFFER_SECONDS = 0.05

SEERS_BANK = {"x": 2727, "y": 3493, "height": 0}
FLAX_FIELD = {"x": 2741, "y": 3451, "height": 0}
FLAX_PICK_TILE = {"x": 2735, "y": 3444, "height": 0}
GROUND_LADDER_TILE = {"x": 2715, "y": 3470, "height": 0}
UPSTAIRS_LADDER_TILE = {"x": 2715, "y": 3470, "height": 1}
SPINNING_WHEEL_TILE = {"x": 2710, "y": 3471, "height": 1}
FLAX_CACHE_RADIUS = 18
FLAX_CACHE_PICK_RADIUS = 5

BANK_TO_FLAX = [
    {"x": 2733, "y": 3482, "height": 0},
    {"x": 2738, "y": 3467, "height": 0},
    FLAX_FIELD,
]
FLAX_TO_LADDER = [
    {"x": 2738, "y": 3460, "height": 0},
    {"x": 2724, "y": 3464, "height": 0},
    GROUND_LADDER_TILE,
]
LADDER_TO_BANK = [
    {"x": 2717, "y": 3478, "height": 0},
    {"x": 2724, "y": 3488, "height": 0},
    SEERS_BANK,
]


def flax_respawn_seconds():
    return PICKABLE_RESPAWN_TICKS * SERVER_TICK_SECONDS + PICK_COOLDOWN_BUFFER_SECONDS


def pick_global_cooldown_seconds(args):
    return max(0.0, float(args.pick_global_cooldown_ticks) * SERVER_TICK_SECONDS + float(args.pick_cooldown_buffer_seconds))


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def monotonic_ms(started):
    return int((time.monotonic() - started) * 1000)


def run_stem(profile):
    return "seers-flax-spin-fast-{}".format(safe_profile(profile))


def status_path(profile):
    return CONTROL_DIR / "{}.status.json".format(run_stem(profile))


def stop_path(profile):
    return CONTROL_DIR / "{}.stop".format(run_stem(profile))


def write_event(handle, event, data):
    EVENT_WRITER.write(handle, event, data)


def emit_item_arrivals(handle, phase, item_id, item_name, count_delta, total_after, data):
    for index in range(int(max(0, count_delta))):
        payload = {
            "phase": phase,
            "itemId": int(item_id),
            "itemName": item_name,
            "deltaIndex": index + 1,
            "deltaCount": int(count_delta),
        }
        if total_after is not None:
            payload["totalAfter"] = int(total_after)
        payload.update(data)
        write_event(handle, "item_arrived", payload)


def tile(player):
    return bridge.tile_from_player(player)


def compact_tile(value):
    if isinstance(value, dict):
        if value.get("x") is not None and value.get("y") is not None:
            return {
                "x": int(value["x"]),
                "y": int(value["y"]),
                "height": int(value.get("height", value.get("h", 0)) or 0),
            }
        value = value.get("tile")
    parts = str(value or "").split(",")
    if len(parts) >= 2:
        return {
            "x": int(parts[0]),
            "y": int(parts[1]),
            "height": int(parts[2]) if len(parts) > 2 else 0,
        }
    raise RuntimeError("could not parse compact tile: {}".format(value))


def tile_string(value):
    return "{},{},{}".format(int(value["x"]), int(value["y"]), int(value.get("height", 0) or 0))


def distance(a, b):
    return bridge.chebyshev(a, b)


def count(player, item_id):
    return bridge.count_inventory_item(player, item_id)


def skill_level(player, skill):
    return bridge.skill_level(player, skill)


def compact(player):
    data = bridge.compact_player(player, ("crafting",))
    data.update({
        "flax": count(player, FLAX),
        "bowstrings": count(player, BOW_STRING),
        "tile": tile(player),
    })
    return data


def bounds_around(center, radius):
    return {
        "minX": int(center["x"]) - int(radius),
        "maxX": int(center["x"]) + int(radius),
        "minY": int(center["y"]) - int(radius),
        "maxY": int(center["y"]) + int(radius),
    }


def cached_flax_objects():
    world_map = cache_world_map.load_cache_world_map(bounds_around(FLAX_FIELD, FLAX_CACHE_RADIUS))
    objects = []
    for obj in world_map.get("objects", []):
        if int(obj.get("id", -1)) != FLAX_OBJECT:
            continue
        if int(obj.get("height", 0) or 0) != 0:
            continue
        objects.append({
            "objectId": FLAX_OBJECT,
            "name": "Flax",
            "source": "cache",
            "tile": tile_string({"x": obj["x"], "y": obj["y"], "height": obj.get("height", 0)}),
        })
    return sorted(objects, key=lambda item: item["tile"])


def player_from_or(result, args, fallback):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return fallback or observe(args)


def observe(args):
    return bridge.observe_xs(profile=args.profile)


def safety_check(player):
    if player.get("isDead"):
        raise RuntimeError("Mrwood is dead")
    if player.get("isInCombat"):
        raise RuntimeError("Mrwood is in combat")


def write_status(args, phase, player, run_path=None, extra=None):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "runner": "seers_flax_spin_fast_runner",
        "updatedAt": utc_now(),
        "phase": phase,
        "profile": args.profile,
        "pid": os.getpid(),
        "stopRequested": stop_path(args.profile).exists(),
        "runLog": str(run_path) if run_path else None,
        "player": compact(player) if player else None,
        "args": vars(args),
    }
    if extra:
        payload.update(extra)
    path = status_path(args.profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def print_status(args):
    path = status_path(args.profile)
    if path.exists():
        print(path.read_text(encoding="utf-8").strip())
        return 0
    print(json.dumps({"ok": False, "runner": "seers_flax_spin_fast_runner", "error": "no_status",
                      "statusPath": str(path)}, sort_keys=True, separators=(",", ":")))
    return 1


def print_shutdown_status(args):
    path = status_path(args.profile)
    stop = stop_path(args.profile)
    if not path.exists():
        print(json.dumps({"ok": False, "runner": "seers_flax_spin_fast_runner", "error": "no_status",
                          "profile": args.profile, "stopRequested": stop.exists(),
                          "shutdownComplete": False}, sort_keys=True, separators=(",", ":")))
        return 1
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(json.dumps({"ok": False, "runner": "seers_flax_spin_fast_runner", "error": "invalid_status",
                          "profile": args.profile, "stopRequested": stop.exists(),
                          "shutdownComplete": False}, sort_keys=True, separators=(",", ":")))
        return 1
    phase = str(status.get("phase") or "")
    stop_requested = bool(status.get("stopRequested")) or stop.exists()
    print(json.dumps({
        "ok": True,
        "runner": status.get("runner") or "seers_flax_spin_fast_runner",
        "profile": status.get("profile") or args.profile,
        "phase": phase,
        "stopRequested": stop_requested,
        "shutdownComplete": phase in TERMINAL_PHASES,
        "pid": status.get("pid"),
        "updatedAt": status.get("updatedAt"),
    }, sort_keys=True, separators=(",", ":")))
    return 0


def request_stop(args):
    path = stop_path(args.profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(utc_now() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "runner": "seers_flax_spin_fast_runner", "stopRequested": True,
                      "stopPath": str(path)}, sort_keys=True, separators=(",", ":")))
    return 0


def close_interfaces(args, handle, reason, player=None):
    started = time.monotonic()
    result = bridge.call_tool("close_interfaces", {}, profile=args.profile)
    updated = player_from_or(result, args, player)
    write_event(handle, "close_interfaces", {
        "reason": reason,
        "success": bool(result.get("success", True)),
        "durationMs": monotonic_ms(started),
        "player": compact(updated),
    })
    return updated


def maybe_run(args, handle, reason, player):
    compact_player = compact(player)
    if compact_player["runEnabled"] or compact_player["runEnergy"] < args.min_run_energy:
        return player
    started = time.monotonic()
    result = bridge.call_tool("set_run_XXS", {"enabled": True}, profile=args.profile)
    updated = player_from_or(result, args, player)
    write_event(handle, "set_run", {
        "reason": reason,
        "success": bool(result.get("success", True)),
        "durationMs": monotonic_ms(started),
        "player": compact(updated),
    })
    return updated


def walk_tile(args, handle, reason, destination, player=None, stop_distance=0, max_ticks=80):
    player = player or observe(args)
    safety_check(player)
    if distance(tile(player), destination) <= stop_distance:
        write_event(handle, "walk_tile_skip", {
            "reason": reason,
            "destination": destination,
            "stopDistance": int(stop_distance),
            "player": compact(player),
        })
        return player
    player = maybe_run(args, handle, reason + "_run", player)
    close_interfaces(args, handle, reason + "_close", player)
    started = time.monotonic()
    try:
        result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
            "x": int(destination["x"]),
            "y": int(destination["y"]),
            "height": int(destination.get("height", 0) or 0),
            "stopDistance": int(stop_distance),
            "maxTicks": int(max_ticks),
            "maxWalkDistance": 96,
            "stopOnCombat": True,
            "stopOnStall": True,
        }, profile=args.profile)
    except RuntimeError as exc:
        player = observe(args)
        if "oscillat" in str(exc).lower() and distance(tile(player), destination) <= max(1, stop_distance):
            result = {
                "success": True,
                "batchStatus": "accepted_oscillation_near_waypoint",
                "batchTicks": None,
            }
        else:
            raise
    player = player_from_or(result, args, player)
    write_event(handle, "walk_tile", {
        "reason": reason,
        "destination": destination,
        "success": bool(result.get("success")),
        "batchStatus": result.get("batchStatus"),
        "batchTicks": result.get("batchTicks"),
        "durationMs": monotonic_ms(started),
        "player": compact(player),
    })
    safety_check(player)
    if not result.get("success", False):
        raise RuntimeError("{} route stalled at {}".format(reason, compact(player)["tile"]))
    return player


def walk_path(args, handle, reason, path, player=None, stop_distance_last=0):
    player = player or observe(args)
    for index, destination in enumerate(path, start=1):
        stop_distance = stop_distance_last if index == len(path) else 1
        player = walk_tile(args, handle, "{}_{}".format(reason, index), destination, player=player,
                           stop_distance=stop_distance)
    return player


def ladder_transition(args, handle, reason, object_id, object_tile, expected_height, player=None):
    player = player or observe(args)
    if int(tile(player)["height"]) == int(expected_height):
        write_event(handle, "ladder_transition_skip", {
            "reason": reason,
            "objectId": object_id,
            "expectedHeight": expected_height,
            "player": compact(player),
        })
        return player
    player = walk_tile(args, handle, reason + "_approach", object_tile, player=player, stop_distance=1, max_ticks=30)
    write_event(handle, "action_start", {
        "action": "object_transition",
        "reason": reason,
        "objectId": object_id,
        "objectTile": object_tile,
        "expectedHeight": expected_height,
        "player": compact(player),
    })
    started = time.monotonic()
    result = bridge.call_tool("object_transition_step_XS", {
        "objectId": int(object_id),
        "x": int(object_tile["x"]),
        "y": int(object_tile["y"]),
        "height": int(object_tile.get("height", tile(player).get("height", 0)) or 0),
        "option": "first",
        "maxTicks": 20,
        "stopOnCombat": True,
    }, profile=args.profile)
    player = player_from_or(result, args, player)
    write_event(handle, "ladder_transition", {
        "reason": reason,
        "objectId": object_id,
        "expectedHeight": expected_height,
        "success": bool(result.get("success")),
        "batchStatus": result.get("batchStatus"),
        "durationMs": monotonic_ms(started),
        "player": compact(player),
    })
    if int(tile(player)["height"]) != int(expected_height):
        for _attempt in range(4):
            time.sleep(0.65)
            player = observe(args)
            if int(tile(player)["height"]) == int(expected_height):
                break
    if int(tile(player)["height"]) != int(expected_height):
        raise RuntimeError("{} failed height transition to {}".format(reason, expected_height))
    return player


def ensure_ground(args, handle, reason, player=None):
    player = player or observe(args)
    if int(tile(player)["height"]) == 0:
        return player
    return ladder_transition(args, handle, reason + "_down", UPSTAIRS_LADDER, UPSTAIRS_LADDER_TILE, 0, player)


def ensure_upstairs(args, handle, reason, player=None):
    player = player or observe(args)
    if int(tile(player)["height"]) == 1:
        return player
    return ladder_transition(args, handle, reason + "_up", GROUND_LADDER, GROUND_LADDER_TILE, 1, player)


def in_bank_area(player):
    return bool(player.get("inBankArea", False)) or distance(tile(player), SEERS_BANK) <= 2


def route_to_bank(args, handle, reason, player=None):
    player = ensure_ground(args, handle, reason + "_ground", player)
    if not in_bank_area(player):
        player = walk_path(args, handle, reason + "_to_bank", LADDER_TO_BANK, player=player, stop_distance_last=1)
    return walk_tile(args, handle, reason + "_bank_tile", SEERS_BANK, player=player, stop_distance=1, max_ticks=40)


def deposit_all(args, handle, reason, player=None):
    player = route_to_bank(args, handle, reason, player)
    started = time.monotonic()
    result = bridge.call_tool("deposit_inventory_items_XS", {"itemIds": [FLAX, BOW_STRING, KNIFE, RUNE_AXE]},
                              profile=args.profile)
    player = player_from_or(result, args, player)
    write_event(handle, "bank_deposit", {
        "reason": reason,
        "success": bool(result.get("success")),
        "depositedAmount": result.get("depositedAmount"),
        "durationMs": monotonic_ms(started),
        "player": compact(player),
    })
    close_interfaces(args, handle, reason + "_after_bank", player)
    return player


def bank_count(args, item_id):
    result = bridge.call_tool("bank_item_count_XS", {"itemIds": [int(item_id)]}, profile=args.profile)
    for item in result.get("items") or []:
        if int(item.get("itemId", item.get("id", -1)) or -1) == int(item_id):
            return int(item.get("bankAmount", item.get("amount", 0)) or 0)
    return 0


def withdraw_flax(args, handle, player):
    amount = min(28, int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0))
    if amount <= 0:
        return player
    started = time.monotonic()
    result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": FLAX, "amount": amount}, profile=args.profile)
    player = player_from_or(result, args, player)
    write_event(handle, "withdraw_flax", {
        "amount": amount,
        "success": bool(result.get("success")),
        "withdrawnAmount": result.get("withdrawnAmount"),
        "durationMs": monotonic_ms(started),
        "player": compact(player),
    })
    close_interfaces(args, handle, "withdraw_flax_after_bank", player)
    return player


def route_to_flax(args, handle, player=None):
    player = ensure_ground(args, handle, "to_flax_ground", player)
    found = nearest_flax(args, handle, player, "to_flax_initial")
    if found.get("success"):
        return move_to_flax_interaction(args, handle, player, found, "to_flax_initial_target")
    for index, destination in enumerate(BANK_TO_FLAX, start=1):
        try:
            player = walk_tile(args, handle, "to_flax_{}".format(index), destination, player=player,
                               stop_distance=1 if index < len(BANK_TO_FLAX) else 2)
        except RuntimeError:
            player = observe(args)
            found = nearest_flax(args, handle, player, "to_flax_after_oscillation_{}".format(index))
            if found.get("success"):
                return move_to_flax_interaction(args, handle, player, found,
                                                "to_flax_after_oscillation_{}_target".format(index))
            raise
        found = nearest_flax(args, handle, player, "to_flax_after_{}".format(index))
        if found.get("success"):
            return move_to_flax_interaction(args, handle, player, found, "to_flax_after_{}_target".format(index))
    return player


def move_to_flax_interaction(args, handle, player, found, reason):
    obj = found.get("object") or {}
    if obj.get("interactionInRange"):
        return player
    if distance(tile(player), FLAX_PICK_TILE) > 1:
        return walk_tile(args, handle, reason + "_central", FLAX_PICK_TILE, player=player,
                         stop_distance=1, max_ticks=18)
    target = obj.get("walkTarget")
    if target:
        return walk_tile(args, handle, reason, compact_tile(target), player=player, stop_distance=0, max_ticks=24)
    obj_tile = compact_tile(obj)
    if distance(tile(player), obj_tile) > FLAX_CACHE_PICK_RADIUS:
        return walk_tile(args, handle, reason, obj_tile, player=player, stop_distance=1, max_ticks=24)
    return player


def nearest_flax(args, handle, player, reason):
    started = time.monotonic()
    try:
        result = bridge.call_tool("find_nearest_object_XS", {
            "objectIds": FLAX_OBJECTS,
            "maxDistance": 14,
            "reachable": True,
        }, profile=args.profile)
    except RuntimeError as exc:
        result = {
            "success": False,
            "message": str(exc),
            "player": player,
        }
    write_event(handle, "find_flax", {
        "reason": reason,
        "success": bool(result.get("success")),
        "durationMs": monotonic_ms(started),
        "object": result.get("object"),
        "player": compact(player_from_or(result, args, player)),
    })
    return result


def choose_cached_flax(player, objects, cooldowns, pick_radius):
    now = time.monotonic()
    player_tile = tile(player)
    candidates = []
    for obj in objects:
        obj_tile = compact_tile(obj)
        if int(obj_tile.get("height", 0)) != int(player_tile.get("height", 0)):
            continue
        key = tile_string(obj_tile)
        if cooldowns.get(key, 0.0) > now:
            continue
        d = distance(player_tile, obj_tile)
        if d > int(pick_radius):
            continue
        candidate = dict(obj)
        candidate["key"] = key
        candidate["distance"] = int(d)
        candidates.append((d, key, candidate))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def cooldown_flax(args, cooldowns, obj, seconds=None):
    key = obj.get("key")
    if not key:
        try:
            key = tile_string(compact_tile(obj))
        except RuntimeError:
            key = ""
    if key:
        duration = flax_respawn_seconds() if seconds is None else float(seconds)
        cooldowns[key] = time.monotonic() + duration
        return duration
    return 0.0


def wait_for_pick_global_cooldown(args, handle, player, last_pick_at):
    if last_pick_at <= 0:
        return player, 0
    ready_at = last_pick_at + pick_global_cooldown_seconds(args)
    remaining = ready_at - time.monotonic()
    if remaining <= 0.25:
        return player, 0
    ticks = max(1, int(math.ceil(remaining / SERVER_TICK_SECONDS)))
    started = time.monotonic()
    waited = bridge.call_tool("wait_ticks_XS", {"ticks": ticks}, profile=args.profile)
    player = player_from_or(waited, args, player)
    write_event(handle, "pick_global_cooldown_wait", {
        "ticks": ticks,
        "cooldownSeconds": round(pick_global_cooldown_seconds(args), 3),
        "durationMs": monotonic_ms(started),
        "player": compact(player),
    })
    return player, ticks


def pick_inventory(args, handle, player=None):
    started_inventory = time.monotonic()
    player = route_to_flax(args, handle, player)
    picked = 0
    attempts = 0
    no_progress = 0
    known_flax = cached_flax_objects()
    known_cooldowns = {}
    last_productive_pick_at = 0.0
    while int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0) > 0:
        safety_check(player)
        if should_stop(args):
            break
        attempts += 1
        before = count(player, FLAX)
        player, timer_wait_ticks = wait_for_pick_global_cooldown(args, handle, player, last_productive_pick_at)
        find_started = time.monotonic()
        obj = choose_cached_flax(player, known_flax, known_cooldowns, args.flax_cache_pick_radius)
        source = "cached_flax"
        found = {"success": True, "message": "Selected cached flax object.", "object": obj}
        if not obj:
            found = nearest_flax(args, handle, player, "pick")
            obj = found.get("object") or {}
            source = "find_nearest_object_XS"
        find_ms = monotonic_ms(find_started)
        if not found.get("success") or not obj:
            raise RuntimeError("no reachable flax object near {}".format(compact(player)["tile"]))
        obj_tile = compact_tile(obj)
        click_started = time.monotonic()
        write_event(handle, "action_start", {
            "action": "pick_flax",
            "attempt": attempts,
            "object": obj,
            "source": source,
            "findMs": find_ms,
            "timerWaitTicks": timer_wait_ticks,
            "beforeFlax": before,
            "player": compact(player),
        })
        clicked = bridge.call_tool("interact_object_XS", {
            "objectId": int(obj.get("objectId", obj.get("id", FLAX_OBJECTS[0]))),
            "x": obj_tile["x"],
            "y": obj_tile["y"],
            "height": obj_tile["height"],
            "option": "second",
        }, profile=args.profile)
        player = player_from_or(clicked, args, player)
        wait_started = time.monotonic()
        waited = bridge.call_tool("wait_until_idle_XS", {
            "maxTicks": args.pick_wait_ticks,
            "movement": True,
            "skilling": False,
            "combat": False,
        }, profile=args.profile)
        player = player_from_or(waited, args, player)
        after = count(player, FLAX)
        gained = max(0, after - before)
        picked += gained
        no_progress = 0 if gained > 0 else no_progress + 1
        plant_cooldown_seconds = 0.0
        if source == "cached_flax" and gained > 0:
            last_productive_pick_at = click_started
            plant_cooldown_seconds = cooldown_flax(args, known_cooldowns, obj)
        elif source == "cached_flax" and gained <= 0:
            plant_cooldown_seconds = cooldown_flax(args, known_cooldowns, obj)
        write_event(handle, "pick_flax_click", {
            "attempt": attempts,
            "object": obj,
            "source": source,
            "findMs": find_ms,
            "clickMs": monotonic_ms(click_started),
            "waitMs": monotonic_ms(wait_started),
            "timerWaitTicks": timer_wait_ticks,
            "plantCooldownSeconds": round(plant_cooldown_seconds, 3),
            "beforeFlax": before,
            "afterFlax": after,
            "gained": gained,
            "success": bool(clicked.get("success")),
            "waitStatus": waited.get("batchStatus"),
            "player": compact(player),
        })
        emit_item_arrivals(handle, "pick", FLAX, "Flax", gained, after, {
            "attempt": attempts,
            "sourceAction": "pick_flax",
            "source": source,
            "object": obj,
            "clickToObservedMs": monotonic_ms(click_started),
            "waitMs": monotonic_ms(wait_started),
            "timerWaitTicks": timer_wait_ticks,
            "plantCooldownSeconds": round(plant_cooldown_seconds, 3),
            "inventoryBefore": before,
            "inventoryAfter": after,
            "player": compact(player),
        })
        if gained <= 0:
            player = observe(args)
        if no_progress >= args.max_pick_no_progress:
            raise RuntimeError("flax picking made no progress after {} attempts".format(no_progress))
    write_event(handle, "pick_inventory", {
        "picked": picked,
        "attempts": attempts,
        "durationMs": monotonic_ms(started_inventory),
        "player": compact(player),
    })
    return player


def route_to_wheel(args, handle, player=None):
    player = player or observe(args)
    if int(tile(player)["height"]) == 0:
        if distance(tile(player), GROUND_LADDER_TILE) > 3:
            if distance(tile(player), FLAX_FIELD) <= 14:
                player = walk_path(args, handle, "flax_to_ladder", FLAX_TO_LADDER, player=player, stop_distance_last=1)
            else:
                player = walk_path(args, handle, "bank_to_ladder", BANK_TO_FLAX[:1] + [GROUND_LADDER_TILE],
                                   player=player, stop_distance_last=1)
        player = ensure_upstairs(args, handle, "wheel_upstairs", player)
    return walk_tile(args, handle, "to_wheel", SPINNING_WHEEL_TILE, player=player, stop_distance=1, max_ticks=30)


def spin_inventory(args, handle, player=None):
    player = player or observe(args)
    if skill_level(player, "crafting") < 10:
        raise RuntimeError("Crafting level 10 is required to spin flax")
    if count(player, FLAX) < 1:
        return player
    started = time.monotonic()
    player = route_to_wheel(args, handle, player)
    before_flax = count(player, FLAX)
    before_strings = count(player, BOW_STRING)
    total_wait_ticks = 0
    attempts = 0
    used = {"success": True}
    button = {"success": True}
    waited = {"success": True, "message": "No wait needed."}
    use_ms = 0
    button_ms = 0
    wait_ms = 0
    while count(player, FLAX) > 0 and attempts < args.spin_max_reclicks:
        attempts += 1
        attempt_flax = count(player, FLAX)
        use_started = time.monotonic()
        write_event(handle, "action_start", {
            "action": "use_flax_on_spinning_wheel",
            "attempt": attempts,
            "beforeFlax": attempt_flax,
            "beforeBowstrings": count(player, BOW_STRING),
            "player": compact(player),
        })
        used = bridge.call_tool("use_item_on_object", {
            "itemId": FLAX,
            "objectId": SPINNING_WHEEL,
            "x": SPINNING_WHEEL_TILE["x"],
            "y": SPINNING_WHEEL_TILE["y"],
            "height": SPINNING_WHEEL_TILE["height"],
        }, profile=args.profile)
        use_duration = monotonic_ms(use_started)
        use_ms += use_duration
        player = player_from_or(used, args, player)
        write_event(handle, "spin_use_item_on_object", {
            "attempt": attempts,
            "success": bool(used.get("success", True)),
            "durationMs": use_duration,
            "beforeFlax": attempt_flax,
            "player": compact(player),
        })
        button_started = time.monotonic()
        button = bridge.call_tool("click_interface_button_XXS", {"buttonId": SPIN_BUTTON}, profile=args.profile)
        button_duration = monotonic_ms(button_started)
        button_ms += button_duration
        player = player_from_or(button, args, player)
        write_event(handle, "spin_button_click", {
            "attempt": attempts,
            "buttonId": SPIN_BUTTON,
            "success": bool(button.get("success", True)),
            "durationMs": button_duration,
            "player": compact(player),
        })
        wait_started = time.monotonic()
        no_progress = 0
        max_wait_ticks = max(int(args.spin_min_wait_ticks),
                             attempt_flax * int(args.spin_ticks_per_item) + int(args.spin_startup_ticks))
        attempt_wait_ticks = 0
        chunk_index = 0
        last_flax = attempt_flax
        last_strings = count(player, BOW_STRING)
        while last_flax > 0 and attempt_wait_ticks < max_wait_ticks:
            before_wait_flax = last_flax
            before_wait_strings = last_strings
            chunk = min(args.spin_wait_chunk_ticks, max_wait_ticks - attempt_wait_ticks)
            chunk_started = time.monotonic()
            waited = bridge.call_tool("wait_ticks_XS", {"ticks": chunk}, profile=args.profile)
            player = player_from_or(waited, args, player)
            attempt_wait_ticks += chunk
            total_wait_ticks += chunk
            after_wait_flax = count(player, FLAX)
            after_wait_strings = count(player, BOW_STRING)
            made_strings = max(0, after_wait_strings - before_wait_strings)
            chunk_index += 1
            if after_wait_flax < before_wait_flax:
                no_progress = 0
            else:
                no_progress += 1
            last_flax = after_wait_flax
            last_strings = after_wait_strings
            chunk_duration = monotonic_ms(chunk_started)
            write_event(handle, "spin_progress_chunk", {
                "attempt": attempts,
                "chunk": chunk_index,
                "ticks": chunk,
                "waitPlan": "exact_ticks",
                "durationMs": chunk_duration,
                "beforeFlax": before_wait_flax,
                "afterFlax": after_wait_flax,
                "beforeBowstrings": before_wait_strings,
                "afterBowstrings": after_wait_strings,
                "madeBowstrings": made_strings,
                "attemptWaitTicks": attempt_wait_ticks,
                "noProgressChunks": no_progress,
                "waitStatus": waited.get("batchStatus", waited.get("message")),
                "player": compact(player),
            })
            emit_item_arrivals(handle, "spin", BOW_STRING, "Bow string", made_strings, after_wait_strings, {
                "attempt": attempts,
                "chunk": chunk_index,
                "sourceAction": "spin_flax",
                "chunkTicks": chunk,
                "chunkDurationMs": chunk_duration,
                "sinceSpinStartMs": monotonic_ms(started),
                "sinceAttemptUseMs": monotonic_ms(use_started),
                "flaxBeforeChunk": before_wait_flax,
                "flaxAfterChunk": after_wait_flax,
                "bowstringsBeforeChunk": before_wait_strings,
                "bowstringsAfterChunk": after_wait_strings,
                "player": compact(player),
            })
            if no_progress >= args.spin_max_no_progress_chunks:
                break
        wait_ms += monotonic_ms(wait_started)
        fallback_wait = None
        if count(player, FLAX) > 0:
            fallback_wait = bridge.call_tool("wait_until_idle_XS", {
                "maxTicks": max(6, count(player, FLAX) * int(args.spin_max_ticks_per_item) + 6),
                "movement": False,
                "skilling": True,
                "combat": False,
            }, profile=args.profile)
            player = player_from_or(fallback_wait, args, player)
            write_event(handle, "spin_fallback_wait", {
                "attempt": attempts,
                "remainingFlax": count(player, FLAX),
                "status": fallback_wait.get("batchStatus", fallback_wait.get("message")),
                "player": compact(player),
            })
        write_event(handle, "spin_attempt", {
            "attempt": attempts,
            "beforeFlax": attempt_flax,
            "afterFlax": count(player, FLAX),
            "bowstrings": count(player, BOW_STRING),
            "waitTicks": attempt_wait_ticks,
            "maxWaitTicks": max_wait_ticks,
            "noProgressChunks": no_progress,
            "fallbackStatus": fallback_wait.get("batchStatus", fallback_wait.get("message")) if fallback_wait else None,
            "player": compact(player),
        })
    if count(player, FLAX) > 0:
        raise RuntimeError("spinning stalled with {} flax remaining after {} attempts and {} ticks".format(
            count(player, FLAX), attempts, total_wait_ticks))
    write_event(handle, "spin_inventory", {
        "beforeFlax": before_flax,
        "afterFlax": count(player, FLAX),
        "beforeBowstrings": before_strings,
        "afterBowstrings": count(player, BOW_STRING),
        "attempts": attempts,
        "useMs": use_ms,
        "buttonMs": button_ms,
        "waitMs": wait_ms,
        "waitTicks": total_wait_ticks,
        "durationMs": monotonic_ms(started),
        "useSuccess": bool(used.get("success")),
        "buttonSuccess": bool(button.get("success", True)),
        "waitStatus": waited.get("batchStatus", waited.get("message")),
        "player": compact(player),
    })
    return player


def should_stop(args):
    return stop_path(args.profile).exists()


def run_loop(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if stop_path(args.profile).exists():
        stop_path(args.profile).unlink()
    run_path = RUNS_DIR / "{}-seers-flax-spin-fast-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    cycles = 0
    with run_path.open("a", encoding="utf-8") as handle:
        player = None
        try:
            player = observe(args)
            write_event(handle, "run_start", {"profile": args.profile, "args": vars(args), "player": compact(player)})
            write_status(args, "started", player, run_path=run_path, extra={"cycles": cycles})
            while args.max_cycles <= 0 or cycles < args.max_cycles:
                cycle_started = time.monotonic()
                player = observe(args)
                safety_check(player)
                if should_stop(args):
                    player = deposit_all(args, handle, "stop_requested", player)
                    write_status(args, "stopped", player, run_path=run_path, extra={"cycles": cycles})
                    return 0
                if count(player, BOW_STRING) > 0 or count(player, FLAX) > 0:
                    if count(player, FLAX) > 0:
                        player = spin_inventory(args, handle, player)
                    player = deposit_all(args, handle, "carried_items", player)
                else:
                    if count(player, KNIFE) > 0 or count(player, RUNE_AXE) > 0:
                        player = deposit_all(args, handle, "cycle_start_cleanup", player)
                    if in_bank_area(player) and bank_count(args, FLAX) > 0:
                        player = withdraw_flax(args, handle, player)
                    else:
                        player = pick_inventory(args, handle, player)
                    player = spin_inventory(args, handle, player)
                    player = deposit_all(args, handle, "cycle_bank", player)
                cycles += 1
                write_event(handle, "cycle_complete", {
                    "cycle": cycles,
                    "durationMs": monotonic_ms(cycle_started),
                    "player": compact(player),
                })
                write_status(args, "running", player, run_path=run_path, extra={"cycles": cycles})
            write_status(args, "complete", player, run_path=run_path, extra={"cycles": cycles, "reason": "max_cycles"})
        except Exception as exc:
            try:
                player = observe(args)
            except Exception:
                pass
            write_event(handle, "runner_blocked", {
                "error": str(exc),
                "cycles": cycles,
                "player": compact(player) if player else None,
            })
            write_status(args, "blocked", player, run_path=run_path, extra={"cycles": cycles, "error": str(exc)})
            raise
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means run until cooperative stop.")
    parser.add_argument("--min-run-energy", type=int, default=20)
    parser.add_argument("--pick-wait-ticks", type=int, default=3)
    parser.add_argument("--pick-global-cooldown-ticks", type=int, default=PICKABLE_GLOBAL_COOLDOWN_TICKS)
    parser.add_argument("--pick-cooldown-buffer-seconds", type=float, default=PICK_COOLDOWN_BUFFER_SECONDS)
    parser.add_argument("--flax-cache-pick-radius", type=int, default=FLAX_CACHE_PICK_RADIUS)
    parser.add_argument("--max-pick-no-progress", type=int, default=5)
    parser.add_argument("--spin-ticks-per-item", type=int, default=3)
    parser.add_argument("--spin-startup-ticks", type=int, default=0)
    parser.add_argument("--spin-min-wait-ticks", type=int, default=3)
    parser.add_argument("--spin-max-ticks-per-item", type=int, default=16)
    parser.add_argument("--spin-wait-chunk-ticks", type=int, default=25)
    parser.add_argument("--spin-max-no-progress-chunks", type=int, default=2)
    parser.add_argument("--spin-max-reclicks", type=int, default=8)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--shutdown-status", action="store_true")
    parser.add_argument("--request-stop", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.profile = resolve_profile(args.profile)
    if args.status:
        return print_status(args)
    if args.shutdown_status:
        return print_shutdown_status(args)
    if args.request_stop:
        return request_stop(args)
    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
