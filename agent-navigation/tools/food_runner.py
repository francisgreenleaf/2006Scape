#!/usr/bin/env python3
"""Primitive-backed fishing, cooking, and firemaking runner."""

import argparse
import datetime as dt
import sys
import uuid

import bridge_script as bridge
from usage_log import log_usage


RUNS_DIR = bridge.ROOT / "data" / "food" / "runs"

SMALL_FISHING_NET = 303
TINDERBOX = 590
NET_FISHING_SPOTS = [316, 319, 323, 325, 326, 327, 329, 330, 333, 404]
RAW_FOOD_IDS = [377, 335, 331, 321, 317, 2132, 2138]
COOKING_OBJECT_IDS = [
    114, 2728, 2729, 2730, 2731, 2732, 2859, 3039, 4172,
    5275, 8750, 9682, 12102, 13539, 13540, 13541, 13542, 13543, 13544, 14919,
]
FIRE_OBJECT_IDS = [2732, 11404, 11405, 11406]
LOG_IDS = [1511, 1521, 1519, 1517, 1515, 1513]


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def raw_food_item(player):
    return bridge.first_inventory_item(player, RAW_FOOD_IDS)


def inventory_item_count(player, item_id):
    return sum(
        int(item.get("amount", 0) or 0)
        for item in bridge.inventory(player)
        if int(item.get("id", item.get("itemId", -1)) or -1) == int(item_id)
    )


def log_item(player):
    return bridge.first_inventory_item(player, LOG_IDS)


def route_if_requested(target, profile, handle, reason):
    if target:
        bridge.route_to(target, profile=profile, handle=handle, reason=reason)


def walk_to_object_interaction_tile(player, obj, profile, handle, args, reason):
    if bool(obj.get("interactionInRange", False)):
        return player
    target = obj.get("nearestInteractionTile") or obj.get("interactionWalkTarget")
    if not isinstance(target, dict):
        return player
    result = bridge.call_tool("walk_to_tile_until_arrived", {
        "x": int(target["x"]),
        "y": int(target["y"]),
        "height": int(target.get("height", 0) or 0),
        "stopDistance": 0,
        "maxTicks": args.object_approach_ticks,
        "maxWalkDistance": args.object_approach_distance,
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=profile)
    player = bridge._player_from_or(result, player)
    bridge.write_event(handle, "object_approach", {
        "reason": reason,
        "object": obj,
        "target": target,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "batchStatus": result.get("batchStatus"),
        "batchTicks": result.get("batchTicks"),
        "player": bridge.compact_player(player),
    })
    return player


def fish_until_full(profile, args, handle):
    if not bridge.has_inventory_item(bridge.observe(profile), SMALL_FISHING_NET):
        raise RuntimeError("small fishing net is required for the default food runner")
    total_ticks = 0
    rounds = 0
    player = bridge.observe(profile)
    while total_ticks < args.max_ticks and int(player.get("freeInventorySlots", 0) or 0) > 0:
        find_result = bridge.call_tool("find_nearest_npc", {
            "npcIds": NET_FISHING_SPOTS,
            "maxDistance": args.npc_max_distance,
            "reachable": True,
        }, profile=profile)
        if not find_result.get("success"):
            route_if_requested(args.fishing_spot, profile, handle, "fishing_spot")
            player = bridge.observe(profile)
            find_result = bridge.call_tool("find_nearest_npc", {
                "npcIds": NET_FISHING_SPOTS,
                "maxDistance": args.npc_max_distance,
                "reachable": True,
            }, profile=profile)
            if not find_result.get("success"):
                raise RuntimeError(find_result.get("message", "no fishing spot found"))
        npc = find_result.get("npc") or {}
        interact = bridge.call_tool("interact_npc", {
            "npcIndex": npc.get("npcIndex"),
            "option": "first",
            "requireReachable": True,
        }, profile=profile)
        wait_ticks = min(80, max(1, args.max_ticks - total_ticks))
        wait = bridge.call_tool("wait_until_idle", {
            "maxTicks": wait_ticks,
            "movement": True,
            "skilling": True,
            "combat": False,
        }, profile=profile)
        player = bridge.player_from(wait)
        total_ticks += max(1, int(wait.get("batchTicks", wait_ticks) or wait_ticks))
        rounds += 1
        bridge.write_event(handle, "fish_round", {
            "round": rounds,
            "npc": npc,
            "interactSuccess": bool(interact.get("success")),
            "waitStatus": wait.get("batchStatus"),
            "player": bridge.compact_player(player, ("fishing",)),
        })
        if not interact.get("success", False) or not wait.get("success", False):
            break
    return player


def cook_inventory(profile, args, handle):
    player = bridge.observe(profile)
    total_ticks = 0
    rounds = 0
    no_progress_rounds = 0
    while total_ticks < args.max_ticks:
        food = raw_food_item(player)
        if food is None:
            break
        before_raw_count = inventory_item_count(player, int(food["id"]))
        before_cooking_xp = bridge.skill_xp(player, "cooking")
        object_ids = FIRE_OBJECT_IDS if args.fire_only else COOKING_OBJECT_IDS
        find_result = bridge.call_tool("find_nearest_object", {
            "objectIds": object_ids,
            "maxDistance": args.object_max_distance,
        }, profile=profile)
        if not find_result.get("success"):
            route_if_requested(args.cooking_place, profile, handle, "cooking_place")
            player = bridge.observe(profile)
            find_result = bridge.call_tool("find_nearest_object", {
                "objectIds": object_ids,
                "maxDistance": args.object_max_distance,
            }, profile=profile)
            if not find_result.get("success"):
                raise RuntimeError(find_result.get("message", "no cooking object found"))
        obj = find_result.get("object") or {}
        player = walk_to_object_interaction_tile(player, obj, profile, handle, args, "cooking_object")
        use_result = bridge.call_tool("use_item_on_object", {
            "itemId": int(food["id"]),
            "objectId": obj.get("objectId"),
            "x": obj.get("x"),
            "y": obj.get("y"),
        }, profile=profile)
        button = bridge.call_tool("click_interface_button", {"buttonId": args.cook_button_id}, profile=profile)
        wait_ticks = min(160, max(1, args.max_ticks - total_ticks))
        wait = bridge.call_tool("wait_until_idle", {
            "maxTicks": wait_ticks,
            "movement": True,
            "skilling": True,
            "combat": False,
        }, profile=profile)
        player = bridge.player_from(wait)
        after_raw_count = inventory_item_count(player, int(food["id"]))
        after_cooking_xp = bridge.skill_xp(player, "cooking")
        total_ticks += max(1, int(wait.get("batchTicks", wait_ticks) or wait_ticks))
        rounds += 1
        made_progress = after_raw_count < before_raw_count or after_cooking_xp != before_cooking_xp
        if made_progress:
            no_progress_rounds = 0
        else:
            no_progress_rounds += 1
        bridge.write_event(handle, "cook_round", {
            "round": rounds,
            "food": food,
            "object": obj,
            "useSuccess": bool(use_result.get("success")),
            "buttonSuccess": bool(button.get("success")),
            "waitStatus": wait.get("batchStatus"),
            "rawCountBefore": before_raw_count,
            "rawCountAfter": after_raw_count,
            "cookingXpBefore": before_cooking_xp,
            "cookingXpAfter": after_cooking_xp,
            "madeProgress": made_progress,
            "noProgressRounds": no_progress_rounds,
            "player": bridge.compact_player(player, ("cooking",)),
        })
        if not use_result.get("success", False) or not button.get("success", False) or not wait.get("success", False):
            break
        if no_progress_rounds >= args.max_no_progress_rounds:
            raise RuntimeError("cooking made no inventory or XP progress for {} rounds".format(no_progress_rounds))
    return player


def light_fires(profile, args, handle):
    player = bridge.observe(profile)
    rounds = 0
    while rounds < args.max_fires:
        logs = log_item(player)
        if logs is None:
            break
        use_result = bridge.call_tool("use_item_on_item", {
            "itemId": TINDERBOX,
            "targetItemId": int(logs["id"]),
        }, profile=profile)
        wait = bridge.call_tool("wait_until_idle", {
            "maxTicks": args.fire_ticks,
            "movement": True,
            "skilling": True,
            "combat": False,
        }, profile=profile)
        player = bridge.player_from(wait)
        rounds += 1
        bridge.write_event(handle, "firemaking_round", {
            "round": rounds,
            "log": logs,
            "useSuccess": bool(use_result.get("success")),
            "waitStatus": wait.get("batchStatus"),
            "player": bridge.compact_player(player, ("firemaking",)),
        })
        if not use_result.get("success", False) or not wait.get("success", False):
            break
    return player


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = bridge.observe(profile)
        player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason="food_runner")
        bridge.write_event(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("fishing", "cooking", "firemaking")),
        })
        if args.mode in ("fish", "fish-cook"):
            player = fish_until_full(profile, args, handle)
            log("fished: fishing={} free={}".format(bridge.skill_level(player, "fishing"), player.get("freeInventorySlots")), args)
        if args.mode in ("cook", "fish-cook"):
            player = cook_inventory(profile, args, handle)
            log("cooked: cooking={} free={}".format(bridge.skill_level(player, "cooking"), player.get("freeInventorySlots")), args)
        if args.mode == "firemake":
            player = light_fires(profile, args, handle)
            log("firemaking={} free={}".format(bridge.skill_level(player, "firemaking"), player.get("freeInventorySlots")), args)
        bridge.write_event(handle, "run_finish", {
            "player": bridge.compact_player(player, ("fishing", "cooking", "firemaking")),
        })
        if handle is not None:
            log("food log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    argv_list = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Run primitive-backed fishing, cooking, and firemaking.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--mode", choices=["fish", "cook", "fish-cook", "firemake"], default="fish-cook")
    parser.add_argument("--fishing-spot", default="lumbridge_fishing_spot")
    parser.add_argument("--cooking-place", default="lumbridge_kitchen_range")
    parser.add_argument("--npc-max-distance", type=int, default=20)
    parser.add_argument("--object-max-distance", type=int, default=20)
    parser.add_argument("--object-approach-distance", type=int, default=12)
    parser.add_argument("--object-approach-ticks", type=int, default=24)
    parser.add_argument("--max-no-progress-rounds", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=260)
    parser.add_argument("--cook-button-id", type=int, default=53149)
    parser.add_argument("--fire-only", action="store_true")
    parser.add_argument("--max-fires", type=int, default=28)
    parser.add_argument("--fire-ticks", type=int, default=20)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-log", action="store_true")
    log_usage("food_runner", surface="full", argv=argv_list)
    return run(parser.parse_args(argv_list))


if __name__ == "__main__":
    raise SystemExit(main())
