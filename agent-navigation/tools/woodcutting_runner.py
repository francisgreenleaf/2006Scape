#!/usr/bin/env python3
"""Primitive-backed woodcutting runner."""

import argparse
import datetime as dt
import uuid
from pathlib import Path

import bridge_script as bridge


RUNS_DIR = bridge.ROOT / "data" / "woodcutting" / "runs"

AXE_IDS = {1351, 1349, 1353, 1361, 1355, 1357, 1359, 6739}
BIRD_NEST_IDS = {5070, 5071, 5072, 5073, 5074, 5075, 7413}


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def has_axe(player):
    for item in bridge.inventory(player) + bridge.equipment(player):
        if int(item.get("id", item.get("itemId", -1)) or -1) in AXE_IDS:
            return True
    return False


def pickup_bird_nests(profile, args, handle, reason):
    player = bridge.observe(profile)
    picked = 0
    for _attempt in range(max(0, args.nest_pickup_attempts)):
        nearby = player.get("nearbyGroundItems") or []
        nest = None
        for item in nearby:
            item_id = int(item.get("id", item.get("itemId", -1)) or -1)
            if item_id in BIRD_NEST_IDS and int(item.get("distance", 999) or 999) <= args.nest_pickup_distance:
                nest = item
                break
        if nest is None:
            break
        result = bridge.call_tool("pickup_ground_item", {
            "itemId": int(nest["id"]),
            "x": int(nest["x"]),
            "y": int(nest["y"]),
            "maxDistance": args.nest_pickup_distance,
        }, profile=profile)
        player = bridge.player_from(result)
        picked += 1
        bridge.write_event(handle, "pickup_bird_nest", {
            "reason": reason,
            "item": nest,
            "success": bool(result.get("success")),
            "player": bridge.compact_player(player, ("woodcutting",)),
        })
    return player, picked


def chop_round(tree, profile, args, handle):
    player = bridge.observe(profile)
    if int(player.get("freeInventorySlots", 0) or 0) < 1:
        return {"success": True, "player": player, "status": "inventory_full"}
    find_result = bridge.call_tool("find_nearest_tree", {
        "tree": tree,
        "maxDistance": args.tree_max_distance,
        "reachable": True,
    }, profile=profile)
    if not find_result.get("success"):
        find_result["player"] = player
        find_result["status"] = "blocked"
        return find_result
    obj = find_result.get("object") or {}
    interact_result = bridge.call_tool("interact_object", {
        "objectId": obj.get("objectId"),
        "x": obj.get("x"),
        "y": obj.get("y"),
        "option": "first",
    }, profile=profile)
    wait_result = bridge.call_tool("wait_until_idle", {
        "maxTicks": args.chop_ticks,
        "movement": True,
        "skilling": True,
        "combat": False,
    }, profile=profile)
    player = bridge.player_from(wait_result)
    status = wait_result.get("batchStatus", "round_complete")
    if int(player.get("freeInventorySlots", 0) or 0) < 1:
        status = "inventory_full"
    bridge.write_event(handle, "chop_round", {
        "tree": tree,
        "object": obj,
        "interactSuccess": bool(interact_result.get("success")),
        "waitStatus": wait_result.get("batchStatus"),
        "player": bridge.compact_player(player, ("woodcutting",)),
    })
    wait_result["player"] = player
    wait_result["status"] = status
    return wait_result


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = bridge.observe(profile)
        bridge.write_event(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("woodcutting",)),
        })
        if not has_axe(player):
            raise RuntimeError("no axe found in inventory or equipment")
        loads = 0
        for round_no in range(1, args.max_rounds + 1):
            player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason="woodcutting")
            if args.target_woodcutting_level and bridge.skill_level(player, "woodcutting") >= args.target_woodcutting_level:
                bridge.write_event(handle, "target_reached", {"player": bridge.compact_player(player, ("woodcutting",))})
                break
            if args.chop_anchor:
                bridge.route_to(args.chop_anchor, profile=profile, handle=handle, reason="chop_anchor")
                player = bridge.observe(profile)
            result = chop_round(args.tree, profile, args, handle)
            player = bridge.player_from(result)
            player, picked = pickup_bird_nests(profile, args, handle, "after_chop")
            log("round {} tree={} status={} wc={} xp={} free={} nests={}".format(
                round_no,
                args.tree,
                result.get("status"),
                bridge.skill_level(player, "woodcutting"),
                bridge.skill_xp(player, "woodcutting"),
                player.get("freeInventorySlots"),
                picked,
            ), args)
            if result.get("status") == "inventory_full":
                loads += 1
                if args.stop_when_inventory_full:
                    break
                if args.bank:
                    bridge.route_to(args.bank, profile=profile, handle=handle, reason="bank_logs")
                    player = bridge.call_tool("deposit_inventory_items", {"name": "logs"}, profile=profile)
                    player = bridge.player_from(player)
                    continue
                break
            if not result.get("success", False):
                raise RuntimeError(result.get("message", "woodcutting blocked"))
        bridge.write_event(handle, "run_finish", {
            "loads": loads,
            "player": bridge.compact_player(player, ("woodcutting",)),
        })
        if handle is not None:
            log("woodcutting log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run primitive-backed woodcutting loops.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--tree", default="tree", help="tree, oak, willow, maple, yew, or magic.")
    parser.add_argument("--target-woodcutting-level", type=int, default=0)
    parser.add_argument("--max-rounds", type=int, default=100)
    parser.add_argument("--tree-max-distance", type=int, default=30)
    parser.add_argument("--chop-ticks", type=int, default=250)
    parser.add_argument("--chop-anchor", default="")
    parser.add_argument("--bank", default="")
    parser.add_argument("--stop-when-inventory-full", action="store_true")
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--nest-pickup-distance", type=int, default=20)
    parser.add_argument("--nest-pickup-attempts", type=int, default=5)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
