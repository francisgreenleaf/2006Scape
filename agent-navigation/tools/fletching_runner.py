#!/usr/bin/env python3
"""Bridge-backed woodcutting and fletching runner.

This keeps the repetitive chop -> fletch -> sell loop out of the AI token loop.
It uses normal bridge gameplay only and leaves movement evidence to the passive
server traces plus ML route executor evidence when route travel is needed.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import uuid
from pathlib import Path

import bridge_script as bridge


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
RUNS_DIR = ROOT / "data" / "fletching" / "runs"
RUN_PROFILE = ""

AXE_IDS = [1351, 1349, 1353, 1361, 1355, 1357, 1359, 6739]
KNIFE_ID = 946
LOG_IDS = {1511: "Tree", 1521: "Oak", 1519: "Willow", 1517: "Maple", 1515: "Yew", 1513: "Magic"}
FLETCHING_PRODUCT_IDS = {52, 50, 48, 54, 56, 60, 58, 64, 62, 68, 66, 72, 70}
BIRD_NEST_IDS = {5070, 5071, 5072, 5073, 5074, 5075, 7413}
FLETCHING_CHOICES = [
    {"logId": 1511, "productId": 52, "level": 1, "xp": 5.0, "makeAllButtonId": 34182},
    {"logId": 1511, "productId": 50, "level": 5, "xp": 5.0, "makeAllButtonId": 34186},
    {"logId": 1511, "productId": 48, "level": 10, "xp": 10.0, "makeAllButtonId": 34190},
    {"logId": 1521, "productId": 54, "level": 20, "xp": 16.5, "makeAllButtonId": 34167},
    {"logId": 1521, "productId": 56, "level": 25, "xp": 25.0, "makeAllButtonId": 34171},
    {"logId": 1519, "productId": 60, "level": 35, "xp": 33.3, "makeAllButtonId": 34167},
    {"logId": 1519, "productId": 58, "level": 40, "xp": 41.5, "makeAllButtonId": 34171},
    {"logId": 1517, "productId": 64, "level": 50, "xp": 50.0, "makeAllButtonId": 34167},
    {"logId": 1517, "productId": 62, "level": 55, "xp": 58.3, "makeAllButtonId": 34171},
    {"logId": 1515, "productId": 68, "level": 65, "xp": 67.5, "makeAllButtonId": 34167},
    {"logId": 1515, "productId": 66, "level": 70, "xp": 70.0, "makeAllButtonId": 34171},
    {"logId": 1513, "productId": 72, "level": 80, "xp": 83.25, "makeAllButtonId": 34167},
    {"logId": 1513, "productId": 70, "level": 85, "xp": 91.5, "makeAllButtonId": 34171},
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def log(message, args=None, force=False):
    if force or args is None or not getattr(args, "quiet", False):
        print(message, flush=True)


def write_event(handle, event_type, data):
    event = {"ts": utc_now(), "event": event_type}
    event.update(data)
    handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    return value


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


def observe_state():
    return call_tool("observe_state", {})


def observe():
    result = observe_state()
    player = result.get("player")
    if not isinstance(player, dict):
        raise RuntimeError("observe_state did not include player state")
    return player


def compact_player(player):
    skills = player.get("skills") or {}
    woodcutting = skills.get("woodcutting") or {}
    fletching = skills.get("fletching") or {}
    coins = coin_summary(player)
    return {
        "tile": {
            "x": int(player.get("x", 0) or 0),
            "y": int(player.get("y", 0) or 0),
            "height": int(player.get("height", player.get("h", 0)) or 0),
        },
        "hitpoints": int(player.get("hitpoints", player.get("hp", 0)) or 0),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled", False)),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "freeSlots": int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0),
        "woodcuttingLevel": int(woodcutting.get("level", 0) or 0),
        "woodcuttingXp": int(float(woodcutting.get("xp", 0) or 0)),
        "fletchingLevel": int(fletching.get("level", 0) or 0),
        "fletchingXp": int(float(fletching.get("xp", 0) or 0)),
        "coins": coins,
    }


def inventory(player):
    return player.get("inventory") or []


def bank(player):
    return player.get("bank") or []


def equipment(player):
    return player.get("equipment") or []


def count_inventory_item(player, item_id):
    total = 0
    for item in inventory(player):
        if int(item.get("id", -1)) == int(item_id):
            total += int(item.get("amount", 1) or 1)
    return total


def count_bank_item(player, item_id):
    total = 0
    for item in bank(player):
        if int(item.get("id", item.get("itemId", -1)) or -1) == int(item_id):
            total += int(item.get("amount", 1) or 1)
    return total


def total_item_count(player, item_id):
    return count_inventory_item(player, item_id) + count_bank_item(player, item_id)


def coin_summary(player):
    inventory_coins = count_inventory_item(player, 995)
    bank_coins = count_bank_item(player, 995)
    return {
        "inventory": inventory_coins,
        "bank": bank_coins,
        "total": inventory_coins + bank_coins,
    }


def count_inventory_ids(player, item_ids):
    return sum(count_inventory_item(player, item_id) for item_id in item_ids)


def has_equipped_axe(player):
    for item in equipment(player):
        if int(item.get("id", -1)) in AXE_IDS:
            return True
    return False


def inventory_axe_id(player):
    for item in inventory(player):
        item_id = int(item.get("id", -1))
        if item_id in AXE_IDS:
            return item_id
    return None


def fletchable_log_count(player):
    return count_inventory_ids(player, LOG_IDS.keys())


def product_count(player):
    return count_inventory_ids(player, FLETCHING_PRODUCT_IDS)


def bird_nest_count(player):
    return count_inventory_ids(player, BIRD_NEST_IDS)


def ground_bird_nests(state):
    matches = []
    for item in state.get("nearbyGroundItems") or []:
        try:
            item_id = int(item.get("id", item.get("itemId", -1)))
        except (TypeError, ValueError):
            item_id = -1
        name = str(item.get("name", "")).lower()
        if item_id in BIRD_NEST_IDS or "bird nest" in name or "bird's nest" in name:
            matches.append(item)
    matches.sort(key=lambda item: int(item.get("distance", 9999) or 9999))
    return matches


def choose_tree(player, requested):
    if requested and requested.lower() != "auto":
        return requested
    wc_level = compact_player(player)["woodcuttingLevel"]
    fletching_level = compact_player(player)["fletchingLevel"]
    if wc_level >= 30 and fletching_level >= 35:
        return "Willow"
    if wc_level >= 15 and fletching_level >= 20:
        return "Oak"
    return "Tree"


def best_fletching_choice(player):
    level = compact_player(player)["fletchingLevel"]
    available = []
    for choice in FLETCHING_CHOICES:
        if choice["level"] > level:
            continue
        if count_inventory_item(player, choice["logId"]) < 1:
            continue
        available.append(choice)
    if not available:
        return None
    available.sort(key=lambda choice: (-choice["xp"], -choice["level"], choice["productId"]))
    return available[0]


def fletching_target_reached(player, args):
    return args.target_fletching_level > 0 and compact_player(player)["fletchingLevel"] >= args.target_fletching_level


def legacy_fletch_until_empty(args, target_level=True):
    payload = {"maxTicks": args.fletch_ticks}
    if target_level:
        payload["targetFletchingLevel"] = args.target_fletching_level
    result = call_tool("fletch_logs_until_inventory_empty", payload)
    result["fletchingMode"] = "legacy_tool"
    return result


def primitive_fletch_until_empty(player, args, handle, reason):
    total_ticks = 0
    rounds = 0
    last_result = {"success": True, "player": player, "batchStatus": "not_started", "batchTicks": 0}
    while rounds < 8 and total_ticks < args.fletch_ticks:
        rounds += 1
        player = observe()
        if fletching_target_reached(player, args):
            last_result = {"success": True, "player": player, "batchStatus": "target_level_reached"}
            break
        if fletchable_log_count(player) < 1:
            last_result = {"success": True, "player": player, "batchStatus": "inventory_empty"}
            break
        choice = best_fletching_choice(player)
        if choice is None:
            last_result = {
                "success": False,
                "message": "No fletchable logs are available for the current level.",
                "player": player,
                "batchStatus": "blocked",
            }
            break
        use_result = call_tool("use_item_on_item", {
            "itemId": KNIFE_ID,
            "targetItemId": choice["logId"],
        })
        button_result = call_tool("click_interface_button", {
            "buttonId": choice["makeAllButtonId"],
        })
        wait_ticks = max(1, min(250, args.fletch_ticks - total_ticks))
        wait_result = call_tool("wait_until_idle", {
            "maxTicks": wait_ticks,
            "movement": True,
            "skilling": True,
            "combat": False,
        })
        player = wait_result.get("player") or button_result.get("player") or use_result.get("player") or player
        total_ticks += int(wait_result.get("batchTicks", wait_ticks) or wait_ticks)
        last_result = wait_result
        last_result["player"] = player
        last_result["fletchingMode"] = "primitive_script"
        last_result["fletchingChoice"] = dict(choice)
        write_event(handle, "primitive_fletch_round", {
            "reason": reason,
            "round": rounds,
            "choice": choice,
            "useSuccess": bool(use_result.get("success")),
            "buttonSuccess": bool(button_result.get("success")),
            "waitStatus": wait_result.get("batchStatus"),
            "player": compact_player(player),
            "logs": fletchable_log_count(player),
            "products": product_count(player),
        })
        if not wait_result.get("success", False):
            last_result["batchStatus"] = wait_result.get("batchStatus", "blocked")
            break
        if fletching_target_reached(player, args):
            last_result["batchStatus"] = "target_level_reached"
            break
        if fletchable_log_count(player) < 1:
            last_result["batchStatus"] = "inventory_empty"
            break
    last_result["batchTicks"] = total_ticks
    if "batchStatus" not in last_result:
        last_result["batchStatus"] = "max_ticks_reached" if total_ticks >= args.fletch_ticks else "complete"
    return last_result


def fletch_until_empty(player, args, handle, reason):
    if args.legacy_fletch_tool:
        return legacy_fletch_until_empty(args)
    try:
        return primitive_fletch_until_empty(player, args, handle, reason)
    except RuntimeError as exc:
        if not args.legacy_fletch_fallback:
            raise
        text = str(exc)
        primitive_missing = (
            "Unknown RuneScape agent tool" in text
            or "use_item_on_item" in text
            or "click_interface_button" in text
        )
        if not primitive_missing:
            raise
        write_event(handle, "primitive_fletch_fallback", {"reason": reason, "error": text})
        return legacy_fletch_until_empty(args)


def legacy_chop_until_inventory_full(tree, args):
    result = call_tool("chop_tree_until_inventory_full", {
        "tree": tree,
        "maxDistance": args.tree_max_distance,
        "maxTicks": args.chop_ticks,
    })
    result["woodcuttingMode"] = "legacy_tool"
    return result


def primitive_chop_until_inventory_full(tree, args, handle, reason):
    total_ticks = 0
    rounds = 0
    player = observe()
    last_result = {"success": True, "player": player, "batchStatus": "not_started", "batchTicks": 0}
    while total_ticks < args.chop_ticks:
        player = observe()
        if int(player.get("freeInventorySlots", 0) or 0) < 1:
            last_result = {"success": True, "player": player, "batchStatus": "inventory_full"}
            break
        find_result = call_tool("find_nearest_tree", {
            "tree": tree,
            "maxDistance": args.tree_max_distance,
            "reachable": True,
        })
        if not find_result.get("success"):
            last_result = find_result
            last_result["player"] = player
            last_result["batchStatus"] = "blocked"
            break
        obj = find_result.get("object") or {}
        interact_result = call_tool("interact_object", {
            "objectId": obj.get("objectId"),
            "x": obj.get("x"),
            "y": obj.get("y"),
            "option": "first",
        })
        wait_ticks = min(40, max(1, args.chop_ticks - total_ticks))
        wait_result = call_tool("wait_until_idle", {
            "maxTicks": wait_ticks,
            "movement": True,
            "skilling": True,
            "combat": False,
        })
        player = wait_result.get("player") or interact_result.get("player") or player
        total_ticks += max(1, int(wait_result.get("batchTicks", wait_ticks) or wait_ticks))
        rounds += 1
        last_result = wait_result
        last_result["player"] = player
        last_result["batchStatus"] = wait_result.get("batchStatus", "round_complete")
        write_event(handle, "primitive_chop_round", {
            "reason": reason,
            "round": rounds,
            "tree": tree,
            "object": obj,
            "interactSuccess": bool(interact_result.get("success")),
            "waitStatus": wait_result.get("batchStatus"),
            "player": compact_player(player),
            "logs": fletchable_log_count(player),
        })
        if not interact_result.get("success", False) or not wait_result.get("success", False):
            last_result["batchStatus"] = "blocked"
            break
        if int(player.get("freeInventorySlots", 0) or 0) < 1:
            last_result["batchStatus"] = "inventory_full"
            break
    else:
        last_result["batchStatus"] = "max_ticks_reached"
    last_result["batchTicks"] = total_ticks
    last_result["woodcuttingMode"] = "primitive_script"
    return last_result


def chop_until_inventory_full(tree, args, handle, reason):
    if args.legacy_chop_tool:
        return legacy_chop_until_inventory_full(tree, args)
    try:
        return primitive_chop_until_inventory_full(tree, args, handle, reason)
    except RuntimeError as exc:
        if not args.legacy_chop_fallback:
            raise
        text = str(exc)
        primitive_missing = (
            "Unknown RuneScape agent tool" in text
            or "find_nearest_tree" in text
            or "interact_object" in text
            or "wait_until_idle" in text
        )
        if not primitive_missing:
            raise
        write_event(handle, "primitive_chop_fallback", {"reason": reason, "tree": tree, "error": text})
        return legacy_chop_until_inventory_full(tree, args)


def ensure_run(player, min_energy, handle):
    before = compact_player(player)
    if before["runEnabled"] or before["runEnergy"] < min_energy:
        return player
    result = call_tool("set_run", {"enabled": True})
    write_event(handle, "set_run", {"before": before, "after": compact_player(result["player"])})
    return result["player"]


def ensure_axe_equipped(player, handle):
    if has_equipped_axe(player):
        return player
    axe_id = inventory_axe_id(player)
    if axe_id is None:
        raise RuntimeError("No axe found in inventory or equipment.")
    write_event(handle, "axe_available", {
        "itemId": axe_id,
        "location": "inventory",
        "player": compact_player(player),
    })
    return player


def ensure_knife(player):
    if count_inventory_item(player, KNIFE_ID) < 1:
        raise RuntimeError("No knife found in inventory.")


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
    write_event(handle, "close_interfaces", {
        "reason": reason,
        "before": compact_player(player),
        "after": compact_player(result["player"]),
    })
    return result["player"]


def pickup_nearby_bird_nests(args, handle, reason):
    if not args.pickup_bird_nests:
        return observe()
    picked = 0
    player = observe()
    for attempt in range(max(1, args.nest_pickup_attempts)):
        state = observe_state()
        player = state.get("player") or player
        nests = ground_bird_nests(state)
        if not nests:
            break
        if int(player.get("freeInventorySlots", 0) or 0) <= 0:
            write_event(handle, "bird_nest_blocked", {
                "reason": reason,
                "blocker": "inventory_full",
                "nearest": nests[0],
                "player": compact_player(player),
            })
            break
        before_count = bird_nest_count(player)
        result = call_tool("pickup_ground_item", {
            "itemIds": sorted(BIRD_NEST_IDS),
            "maxDistance": args.nest_pickup_distance,
        })
        player = result.get("player") or player
        moved = int(result.get("pickedUp", 0) or 0)
        after_count = bird_nest_count(player)
        write_event(handle, "bird_nest_pickup_attempt", {
            "reason": reason,
            "attempt": attempt + 1,
            "message": result.get("message"),
            "pickedUp": moved,
            "beforeCount": before_count,
            "afterCount": after_count,
            "player": compact_player(player),
        })
        picked += moved
        if int(player.get("freeInventorySlots", 0) or 0) <= 0:
            break
        if moved <= 0 and after_count <= before_count:
            call_tool("wait_until_idle", {"maxTicks": 20, "movement": True, "skilling": False})
    if picked > 0:
        log("picked up bird nest x{}".format(picked), args, force=True)
    return player


def route_to(target, args, handle, reason):
    extra_args = {
        "runner_max_batches": args.route_max_batches,
        "max_batch_distance": args.route_max_batch_distance,
        "run_mode": args.route_run_mode,
        "eat_at": args.route_eat_at,
        "evidence_jsonl": args.route_evidence_jsonl,
    }
    bridge.route_to(target, profile=RUN_PROFILE, handle=handle, reason=reason, extra_args=extra_args)


def sell_products(args, handle, reason):
    player = observe()
    if product_count(player) < 1:
        return player
    if args.shop:
        try:
            route_to(args.shop, args, handle, reason)
        except RuntimeError as exc:
            write_event(handle, "route_soft_fail", {
                "reason": reason,
                "target": args.shop,
                "error": str(exc),
            "fallback": "try_open_nearest_shop",
            })
        player = observe()
    opened = call_tool("open_nearest_shop", {"name": args.shop_name, "maxDistance": args.shop_max_distance})
    write_event(handle, "open_shop", {"reason": reason, "result": opened.get("message"), "player": compact_player(opened["player"])})
    sold = call_tool("sell_inventory_items", {"category": "fletching_products", "amount": args.sell_amount})
    write_event(handle, "sell_products", {
        "reason": reason,
        "sold": sold.get("sold", 0),
        "coinsReceived": sold.get("coinsReceived", 0),
        "player": compact_player(sold["player"]),
    })
    player = close_interfaces_if_needed(sold["player"], handle, "after_sell")
    if args.bank_coins and count_inventory_item(player, 995) > 0:
        coin_bank = args.coin_bank or args.bank
        if not coin_bank:
            write_event(handle, "bank_coins_deferred", {
                "reason": reason,
                "coins": count_inventory_item(player, 995),
                "player": compact_player(player),
            })
            return player
        route_to(coin_bank, args, handle, "bank_sale_coins")
        player = observe()
        deposited = call_tool("deposit_inventory_items", {
            "itemIds": [995],
            "amount": count_inventory_item(player, 995),
        })
        write_event(handle, "bank_coins", {
            "reason": reason,
            "depositedAmount": deposited.get("depositedAmount", 0),
            "player": compact_player(deposited["player"]),
        })
        player = deposited["player"]
    return player


def bank_products_if_needed(player, args, handle, reason):
    if product_count(player) < 1:
        return player
    if not args.bank:
        write_event(handle, "bank_products_deferred", {
            "reason": reason,
            "products": product_count(player),
            "player": compact_player(player),
        })
        return player
    route_to(args.bank, args, handle, "bank_products")
    player = observe()
    deposited = call_tool("deposit_inventory_items", {
        "itemIds": sorted(FLETCHING_PRODUCT_IDS),
        "amount": product_count(player),
    })
    write_event(handle, "bank_products", {
        "reason": reason,
        "depositedAmount": deposited.get("depositedAmount", 0),
        "player": compact_player(deposited["player"]),
    })
    return deposited["player"]


def bank_bird_nests_if_needed(player, args, handle, reason):
    if bird_nest_count(player) < 1:
        return player
    if not args.bank:
        write_event(handle, "bank_bird_nests_deferred", {
            "reason": reason,
            "count": bird_nest_count(player),
            "player": compact_player(player),
        })
        log("carrying bird nest until next bank trip", args, force=True)
        return player
    route_to(args.bank, args, handle, "bank_bird_nests")
    player = observe()
    deposited = call_tool("deposit_inventory_items", {
        "itemIds": sorted(BIRD_NEST_IDS),
        "amount": bird_nest_count(player),
    })
    write_event(handle, "bank_bird_nests", {
        "reason": reason,
        "depositedAmount": deposited.get("depositedAmount", 0),
        "player": compact_player(deposited["player"]),
    })
    log("banked bird nests x{}".format(deposited.get("depositedAmount", 0)), args, force=True)
    return deposited["player"]


def stop_reason(player, args):
    compact = compact_player(player)
    if args.target_coins > 0 and compact["coins"]["total"] >= args.target_coins:
        return "target_coins"
    if args.stop_at_bird_nests > 0 and bird_nest_count(player) >= args.stop_at_bird_nests:
        return "bird_nests"
    if args.stop_at_fletching_level > 0 and compact["fletchingLevel"] >= args.stop_at_fletching_level:
        return "fletching_level"
    if args.stop_at_woodcutting_level > 0 and compact["woodcuttingLevel"] >= args.stop_at_woodcutting_level:
        return "woodcutting_level"
    has_level_target = args.target_woodcutting_level > 0 or args.target_fletching_level > 0
    woodcutting_reached = args.target_woodcutting_level <= 0 or compact["woodcuttingLevel"] >= args.target_woodcutting_level
    fletching_reached = args.target_fletching_level <= 0 or compact["fletchingLevel"] >= args.target_fletching_level
    if has_level_target and woodcutting_reached and fletching_reached:
        return "target_levels"
    return None


def should_stop(player, args):
    return stop_reason(player, args) is not None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run normal-gameplay woodcutting and fletching loops.")
    parser.add_argument("--target-woodcutting-level", type=int, default=50)
    parser.add_argument("--target-fletching-level", type=int, default=50)
    parser.add_argument("--target-coins", type=int, default=0,
                        help="Stop once inventory plus visible bank coins reaches this amount.")
    parser.add_argument("--stop-at-woodcutting-level", type=int, default=0)
    parser.add_argument("--stop-at-fletching-level", type=int, default=0)
    parser.add_argument("--stop-at-bird-nests", type=int, default=0)
    parser.add_argument("--stop-immediate", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--tree", default="auto", help="Tree, Oak, Willow, or auto.")
    parser.add_argument("--chop-anchor", default="", help="Route target to stand at before chopping, e.g. lumbridge_tree_stand.")
    parser.add_argument("--tree-max-distance", type=int, default=30)
    parser.add_argument("--chop-ticks", type=int, default=250)
    parser.add_argument("--fletch-ticks", type=int, default=250)
    parser.add_argument("--legacy-fletch-tool", action="store_true",
                        help="Use the legacy server-side fletch_logs_until_inventory_empty tool instead of primitives.")
    parser.add_argument("--legacy-fletch-fallback", action=argparse.BooleanOptionalAction, default=True,
                        help="Fall back to the legacy fletching tool if the live runtime has not been restarted with primitives.")
    parser.add_argument("--legacy-chop-tool", action="store_true",
                        help="Use the legacy server-side chop_tree_until_inventory_full tool instead of primitive object interaction.")
    parser.add_argument("--legacy-chop-fallback", action=argparse.BooleanOptionalAction, default=True,
                        help="Fall back to the legacy chop tool if the live runtime has not been restarted with primitives.")
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--run-reserve", default="auto")
    parser.add_argument("--route-run-mode", choices=["auto", "always", "never", "preserve"], default="auto")
    parser.add_argument("--route-eat-at", type=int, default=10)
    parser.add_argument("--route-max-batches", type=int, default=60)
    parser.add_argument("--route-max-walk-distance", type=int, default=80)
    parser.add_argument("--route-max-batch-distance", type=int, default=48)
    parser.add_argument("--route-direct-preview-distance", type=int, default=96)
    parser.add_argument("--route-probe-distance", type=int, default=48)
    parser.add_argument("--shop", default="varrock_general_store")
    parser.add_argument("--bank", default="varrock_west_bank")
    parser.add_argument("--coin-bank", default="",
                        help="Optional route target used only for banking sale coins. Defaults to --bank.")
    parser.add_argument("--bank-coins", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--shop-name", default="general")
    parser.add_argument("--shop-max-distance", type=int, default=14)
    parser.add_argument("--bank-products", action=argparse.BooleanOptionalAction, default=False,
                        help="Bank fletching products on inventory pressure instead of selling them.")
    parser.add_argument("--sell-amount", type=int, default=28000)
    parser.add_argument("--sell-at-free-slots", type=int, default=6)
    parser.add_argument("--pickup-bird-nests", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--nest-pickup-distance", type=int, default=20)
    parser.add_argument("--nest-pickup-attempts", type=int, default=5)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-final-sell", action="store_true")
    parser.add_argument("--route-evidence-jsonl")
    parser.add_argument("--profile", default="")
    args = parser.parse_args(argv)

    global RUN_PROFILE
    RUN_PROFILE = args.profile

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    if args.route_evidence_jsonl is None:
        evidence_dir = ROOT / ".local" / "run-evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        args.route_evidence_jsonl = evidence_dir / "fletching-runner.routes.jsonl"
    else:
        args.route_evidence_jsonl = Path(args.route_evidence_jsonl)

    with run_path.open("a", encoding="utf-8") as handle:
        write_event(handle, "start", {"args": jsonable(vars(args))})
        player = observe()
        write_event(handle, "observe", {"player": compact_player(player)})
        last_wc_level = compact_player(player)["woodcuttingLevel"]
        last_fletching_level = compact_player(player)["fletchingLevel"]
        stopped_reason = None

        for cycle in range(1, args.max_cycles + 1):
            player = observe()
            player = pickup_nearby_bird_nests(args, handle, "cycle_start")
            player = bank_bird_nests_if_needed(player, args, handle, "cycle_start")
            compact = compact_player(player)
            write_event(handle, "cycle_start", {
                "cycle": cycle,
                "player": compact,
                "logs": fletchable_log_count(player),
                "products": product_count(player),
                "coins": compact["coins"],
            })
            log("cycle {} wc={} fletch={} free={} logs={} products={} coins={} run={}".format(
                cycle,
                compact["woodcuttingLevel"],
                compact["fletchingLevel"],
                compact["freeSlots"],
                fletchable_log_count(player),
                product_count(player),
                compact["coins"]["total"],
                compact["runEnergy"],
            ), args)

            if compact["isDead"] or compact["isInCombat"]:
                write_event(handle, "blocked", {"reason": "dead_or_combat", "player": compact})
                return 2
            stopped_reason = stop_reason(player, args)
            if stopped_reason:
                write_event(handle, "target_reached", {"reason": stopped_reason, "player": compact})
                break

            ensure_knife(player)
            player = ensure_axe_equipped(player, handle)
            player = ensure_run(player, args.min_run_energy, handle)

            if fletchable_log_count(player) > 0:
                player = close_interfaces_if_needed(player, handle, "before_fletch")
                result = fletch_until_empty(player, args, handle, "cycle")
                player = result["player"]
                player = pickup_nearby_bird_nests(args, handle, "after_fletch")
                player = bank_bird_nests_if_needed(player, args, handle, "after_fletch")
                write_event(handle, "fletch", {
                    "cycle": cycle,
                    "mode": result.get("fletchingMode"),
                    "choice": result.get("fletchingChoice"),
                    "batchStatus": result.get("batchStatus"),
                    "batchTicks": result.get("batchTicks"),
                    "player": compact_player(player),
                    "products": product_count(player),
                })
                current_fletching = compact_player(player)["fletchingLevel"]
                if current_fletching > last_fletching_level:
                    log("fletching level {}".format(current_fletching), args, force=True)
                    last_fletching_level = current_fletching
                continue

            if product_count(player) > 0 and compact_player(player)["freeSlots"] <= args.sell_at_free_slots:
                if args.bank_products:
                    player = bank_products_if_needed(player, args, handle, "inventory_pressure")
                else:
                    player = sell_products(args, handle, "inventory_pressure")
                continue

            tree = choose_tree(player, args.tree)
            player = close_interfaces_if_needed(player, handle, "before_chop")
            if args.chop_anchor:
                route_to(args.chop_anchor, args, handle, "chop_anchor")
                player = observe()
            result = chop_until_inventory_full(tree, args, handle, "cycle")
            player = result["player"]
            player = pickup_nearby_bird_nests(args, handle, "after_chop")
            player = bank_bird_nests_if_needed(player, args, handle, "after_chop")
            write_event(handle, "chop", {
                "cycle": cycle,
                "tree": tree,
                "mode": result.get("woodcuttingMode"),
                "chopAnchor": args.chop_anchor or None,
                "batchStatus": result.get("batchStatus"),
                "batchTicks": result.get("batchTicks"),
                "player": compact_player(player),
                "logs": fletchable_log_count(player),
            })
            current_wc = compact_player(player)["woodcuttingLevel"]
            if current_wc > last_wc_level:
                log("woodcutting level {}".format(current_wc), args, force=True)
                last_wc_level = current_wc

        player = observe()
        if stopped_reason and args.stop_immediate:
            write_event(handle, "done", {
                "reason": stopped_reason,
                "player": compact_player(player),
                "runLog": str(run_path),
            })
            log("run log: {}".format(run_path), args, force=True)
            return 0
        player = pickup_nearby_bird_nests(args, handle, "final_start")
        player = bank_bird_nests_if_needed(player, args, handle, "final_start")
        if fletchable_log_count(player) > 0:
            player = close_interfaces_if_needed(player, handle, "final_before_fletch")
            result = fletch_until_empty(player, args, handle, "final")
            player = result["player"]
            player = pickup_nearby_bird_nests(args, handle, "final_after_fletch")
            player = bank_bird_nests_if_needed(player, args, handle, "final_after_fletch")
            write_event(handle, "final_fletch", {
                "mode": result.get("fletchingMode"),
                "choice": result.get("fletchingChoice"),
                "batchStatus": result.get("batchStatus"),
                "batchTicks": result.get("batchTicks"),
                "player": compact_player(player),
                "products": product_count(player),
            })
        if not args.no_final_sell and product_count(player) > 0:
            if args.bank_products:
                try:
                    player = bank_products_if_needed(player, args, handle, "final")
                except Exception as exc:
                    write_event(handle, "final_bank_products_failed", {"error": str(exc), "player": compact_player(observe())})
            else:
                try:
                    player = sell_products(args, handle, "final")
                except Exception as exc:
                    write_event(handle, "final_sell_failed", {"error": str(exc), "player": compact_player(observe())})
        write_event(handle, "done", {"player": compact_player(observe()), "runLog": str(run_path)})
        log("run log: {}".format(run_path), args, force=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
