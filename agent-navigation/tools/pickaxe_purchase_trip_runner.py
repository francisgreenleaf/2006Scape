#!/usr/bin/env python3
"""Separate Dwarven Mine pickaxe purchase trip for mining preparation."""

import argparse
import datetime as dt
import uuid

import bridge_script as bridge
from profile_utils import resolve_profile


RUNS_DIR = bridge.ROOT / "data" / "mining" / "runs"

COINS = 995
PICKAXES = [
    {"itemId": 1269, "name": "steel pickaxe", "level": 6},
    {"itemId": 1273, "name": "mithril pickaxe", "level": 21},
    {"itemId": 1271, "name": "adamant pickaxe", "level": 31},
    {"itemId": 1275, "name": "rune pickaxe", "level": 41},
]
PICKAXE_IDS = [1265, 1267, 1269, 1273, 1271, 1275]
MINING_PRODUCTS = [434, 436, 438, 440, 442, 444, 453, 1617, 1619, 1621, 1623]

VARROCK_EAST_BANK = "varrock east bank"
DWARVEN_MINE_LADDER = "dwarven mine ladder"
DWARVEN_MINE_SHOP = "nurmof pickaxe shop"
DWARVEN_MINE_UNDERGROUND_EXIT = "dwarven mine trapdoor underground"

SURFACE_LADDER_DOWN = {"objectId": 11867, "x": 3019, "y": 3450, "height": 0}
UNDERGROUND_LADDER_UP = {"objectId": 1755, "x": 3019, "y": 9850, "height": 0}


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def observe(profile):
    return bridge.observe(profile)


def is_underground(player):
    tile = bridge.tile_from_player(player)
    return 9800 <= int(tile["y"]) <= 9905


def total_count(player, item_id):
    return bridge.count_inventory_item(player, item_id) + bridge.count_bank_item(player, item_id)


def write(handle, event, data):
    bridge.write_event(handle, event, data)


def travel_landmark(profile, name, handle, args, attempts=4):
    last = None
    for attempt in range(1, attempts + 1):
        result = bridge.call_tool("travel_to_landmark_until_arrived", {
            "name": name,
            "maxTicks": int(args.travel_max_ticks),
            "stopOnCombat": True,
            "stopOnStall": True,
        }, profile=profile)
        last = result
        player = bridge._player_from_or(result, observe(profile))
        write(handle, "travel_landmark", {
            "name": name,
            "attempt": attempt,
            "success": bool(result.get("success")),
            "batchStatus": result.get("batchStatus"),
            "message": result.get("message"),
            "player": bridge.compact_player(player, ("mining",)),
        })
        if result.get("success") and (result.get("batchStatus") == "arrived" or result.get("complete")):
            return player
    raise RuntimeError("could not travel to {}: {}".format(name, (last or {}).get("message", "")))


def interact_object(profile, obj, handle, reason):
    result = bridge.call_tool("interact_object", obj, profile=profile)
    player = bridge._player_from_or(result, observe(profile))
    bridge.call_tool("wait_ticks", {"ticks": 4}, profile=profile)
    player = observe(profile)
    write(handle, "interact_object", {
        "reason": reason,
        "object": obj,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("mining",)),
    })
    return player


def walk_to_tile(profile, tile, handle, reason, max_ticks=40):
    result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0) or 0),
        "stopDistance": 0,
        "maxTicks": int(max_ticks),
        "maxWalkDistance": 64,
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=profile)
    player = bridge._player_from_or(result, observe(profile))
    write(handle, "walk_to_tile", {
        "reason": reason,
        "tile": tile,
        "success": bool(result.get("success")),
        "batchStatus": result.get("batchStatus"),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("mining",)),
    })
    return observe(profile)


def descend_to_dwarven_mine(profile, handle, args):
    player = observe(profile)
    if is_underground(player):
        return player
    player = travel_landmark(profile, DWARVEN_MINE_LADDER, handle, args)
    found = bridge.call_tool("find_nearest_object", {
        "objectIds": [SURFACE_LADDER_DOWN["objectId"]],
        "maxDistance": 12,
    }, profile=profile)
    obj = found.get("object") if isinstance(found, dict) else None
    target = {
        "objectId": int((obj or {}).get("objectId", SURFACE_LADDER_DOWN["objectId"])),
        "x": int((obj or {}).get("x", SURFACE_LADDER_DOWN["x"])),
        "y": int((obj or {}).get("y", SURFACE_LADDER_DOWN["y"])),
        "height": int((obj or {}).get("height", 0) or 0),
    }
    walk_target = (obj or {}).get("interactionWalkTarget") or (obj or {}).get("nearestInteractionTile")
    if isinstance(walk_target, dict):
        player = walk_to_tile(profile, walk_target, handle, "dwarven_mine_descend_approach")
    player = interact_object(profile, target, handle, "dwarven_mine_descend")
    if not is_underground(player):
        raise RuntimeError("failed to descend into Dwarven Mine")
    return player


def climb_out_of_dwarven_mine(profile, handle, args):
    player = observe(profile)
    if not is_underground(player):
        return player
    player = travel_landmark(profile, DWARVEN_MINE_UNDERGROUND_EXIT, handle, args)
    found = bridge.call_tool("find_nearest_object", {
        "objectIds": [UNDERGROUND_LADDER_UP["objectId"]],
        "maxDistance": 12,
    }, profile=profile)
    obj = found.get("object") if isinstance(found, dict) else None
    target = {
        "objectId": int((obj or {}).get("objectId", UNDERGROUND_LADDER_UP["objectId"])),
        "x": int((obj or {}).get("x", UNDERGROUND_LADDER_UP["x"])),
        "y": int((obj or {}).get("y", UNDERGROUND_LADDER_UP["y"])),
        "height": int((obj or {}).get("height", 0) or 0),
    }
    player = interact_object(profile, target, handle, "dwarven_mine_exit")
    if is_underground(player):
        raise RuntimeError("failed to leave Dwarven Mine")
    return player


def deposit_items(player, item_ids, profile, handle, reason):
    present = []
    seen = set()
    for item in bridge.inventory(player):
        item_id = int(item.get("id", item.get("itemId", -1)) or -1)
        if item_id in item_ids and item_id not in seen:
            seen.add(item_id)
            present.append(item_id)
    if not present:
        return player
    result = bridge.call_tool("deposit_inventory_items", {"itemIds": present}, profile=profile)
    player = bridge._player_from_or(result, player)
    write(handle, "deposit_items", {
        "reason": reason,
        "itemIds": present,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("mining",)),
    })
    return observe(profile)


def withdraw(profile, item_id, amount, handle, reason):
    result = bridge.call_tool("withdraw_bank_items", {"itemId": int(item_id), "amount": int(amount)}, profile=profile)
    player = bridge._player_from_or(result, observe(profile))
    write(handle, "withdraw", {
        "reason": reason,
        "itemId": int(item_id),
        "amount": int(amount),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("mining",)),
    })
    return observe(profile)


def prepare_cash(profile, handle, args):
    player = observe(profile)
    cleanup_ids = set(MINING_PRODUCTS + PICKAXE_IDS)
    needs_cleanup = any(
        int(item.get("id", item.get("itemId", -1)) or -1) in cleanup_ids
        for item in bridge.inventory(player)
    )
    if bridge.count_inventory_item(player, COINS) >= int(args.coin_float) and not needs_cleanup:
        return player
    if not player.get("inBankArea"):
        bridge.route_to(args.start_bank, profile=profile, handle=handle, reason="pickaxe_trip_bank")
        player = observe(profile)
    player = deposit_items(player, MINING_PRODUCTS + PICKAXE_IDS, profile, handle, "pre_trip_cleanup")
    if bridge.count_inventory_item(player, COINS) < int(args.coin_float):
        player = withdraw(profile, COINS, int(args.coin_float) - bridge.count_inventory_item(player, COINS), handle, "pickaxe_cash")
    return player


def buy_pickaxes(profile, handle, args):
    player = descend_to_dwarven_mine(profile, handle, args)
    player = travel_landmark(profile, DWARVEN_MINE_SHOP, handle, args)
    opened = bridge.call_tool("open_nearest_shop", {"name": "nurmof", "maxDistance": 10}, profile=profile)
    player = bridge._player_from_or(opened, player)
    write(handle, "open_pickaxe_shop", {
        "success": bool(opened.get("success")),
        "message": opened.get("message"),
        "player": bridge.compact_player(player, ("mining",)),
    })
    if not opened.get("success"):
        raise RuntimeError("could not open Nurmof's pickaxe shop")
    for pickaxe in PICKAXES:
        before = total_count(player, pickaxe["itemId"])
        if before > 0 and not args.buy_duplicates:
            write(handle, "buy_pickaxe_skip", {"pickaxe": pickaxe, "reason": "already_owned"})
            continue
        result = bridge.call_tool("buy_shop_item", {
            "itemId": int(pickaxe["itemId"]),
            "amount": 1,
        }, profile=profile)
        player = bridge._player_from_or(result, player)
        after = total_count(player, pickaxe["itemId"])
        write(handle, "buy_pickaxe", {
            "pickaxe": pickaxe,
            "success": bool(result.get("success")) and after > before,
            "message": result.get("message"),
            "before": before,
            "after": after,
            "player": bridge.compact_player(player, ("mining",)),
        })
        if after <= before:
            raise RuntimeError("failed to buy {}".format(pickaxe["name"]))
    bridge.call_tool("close_interfaces", {}, profile=profile)
    return observe(profile)


def return_to_varrock(profile, handle, args):
    player = climb_out_of_dwarven_mine(profile, handle, args)
    if not player.get("inBankArea"):
        bridge.route_to(VARROCK_EAST_BANK, profile=profile, handle=handle, reason="return_varrock_bank")
        player = observe(profile)
    player = deposit_items(player, [COINS] + PICKAXE_IDS + MINING_PRODUCTS, profile, handle, "post_trip_bank")
    return player


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-pickaxe-purchase-trip-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = observe(profile)
        write(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("mining",)),
        })
        prepare_cash(profile, handle, args)
        buy_pickaxes(profile, handle, args)
        player = return_to_varrock(profile, handle, args)
        final = observe(profile)
        write(handle, "run_finish", {
            "player": bridge.compact_player(final, ("mining",)),
            "pickaxeCounts": {str(item_id): total_count(final, item_id) for item_id in PICKAXE_IDS},
        })
        log("pickaxe trip log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Buy Dwarven Mine pickaxe upgrades, then return to Varrock bank.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--start-bank", default=VARROCK_EAST_BANK)
    parser.add_argument("--coin-float", type=int, default=70000)
    parser.add_argument("--travel-max-ticks", type=int, default=250)
    parser.add_argument("--buy-duplicates", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
