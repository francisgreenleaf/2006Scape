#!/usr/bin/env python3
"""Bridge-backed woodcutting and fletching runner.

This keeps the repetitive chop -> fletch -> sell loop out of the AI token loop.
It uses normal bridge gameplay only and leaves movement evidence to the passive
server traces plus route_runner evidence when route travel is needed.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"
RUNS_DIR = ROOT / "data" / "fletching" / "runs"
RUN_PROFILE = ""

AXE_IDS = [1351, 1349, 1353, 1361, 1355, 1357, 1359, 6739]
KNIFE_ID = 946
LOG_IDS = {1511: "Tree", 1521: "Oak", 1519: "Willow", 1517: "Maple", 1515: "Yew", 1513: "Magic"}
FLETCHING_PRODUCT_IDS = {52, 50, 48, 54, 56, 60, 58, 64, 62, 68, 66, 72, 70}
BIRD_NEST_IDS = {5070, 5071, 5072, 5073, 5074, 5075, 7413}


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
    }


def inventory(player):
    return player.get("inventory") or []


def equipment(player):
    return player.get("equipment") or []


def count_inventory_item(player, item_id):
    total = 0
    for item in inventory(player):
        if int(item.get("id", -1)) == int(item_id):
            total += int(item.get("amount", 1) or 1)
    return total


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
    result = call_tool("equip_item", {"itemId": axe_id})
    write_event(handle, "equip_axe", {"itemId": axe_id, "after": compact_player(result["player"])})
    return result["player"]


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
        if bird_nest_count(player) > 0:
            break
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
        result = call_tool("pickup_ground_item", {
            "itemIds": sorted(BIRD_NEST_IDS),
            "maxDistance": args.nest_pickup_distance,
        })
        player = result.get("player") or player
        moved = int(result.get("pickedUp", 0) or 0)
        write_event(handle, "bird_nest_pickup_attempt", {
            "reason": reason,
            "attempt": attempt + 1,
            "message": result.get("message"),
            "pickedUp": moved,
            "player": compact_player(player),
        })
        picked += moved
        if moved > 0 or bird_nest_count(player) > 0:
            break
        call_tool("wait_until_idle", {"maxTicks": 20, "movement": True, "skilling": False})
    if picked > 0:
        log("picked up bird nest x{}".format(picked), args, force=True)
    return player


def route_to(target, args, handle, reason):
    command = [
        sys.executable,
        str(ROUTE_RUNNER),
        "--to",
        target,
        "--max-batches",
        str(args.route_max_batches),
        "--max-walk-distance",
        str(args.route_max_walk_distance),
        "--max-batch-distance",
        str(args.route_max_batch_distance),
        "--allow-frontier",
        "--direct-if-preview",
        "--direct-preview-distance",
        str(args.route_direct_preview_distance),
        "--probe-toward-target",
        "--probe-distance",
        str(args.route_probe_distance),
        "--run-reserve",
        args.run_reserve,
    ]
    if args.route_evidence_jsonl:
        command.extend(["--evidence-jsonl", str(args.route_evidence_jsonl)])
    env = os.environ.copy()
    if RUN_PROFILE:
        env["RS_PROFILE"] = RUN_PROFILE
    write_event(handle, "route_start", {"reason": reason, "target": target, "command": command})
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    write_event(handle, "route_done", {
        "reason": reason,
        "target": target,
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout.strip().splitlines()[-8:],
        "stderrTail": proc.stderr.strip().splitlines()[-8:],
    })
    if proc.returncode != 0:
        raise RuntimeError("route_runner failed while routing to {}: {}".format(
            target, proc.stderr.strip() or proc.stdout.strip()))


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
    opened = call_tool("open_nearest_shop", {"name": "general", "maxDistance": args.shop_max_distance})
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
        if args.bank:
            route_to(args.bank, args, handle, "bank_sale_coins")
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


def bank_bird_nests_if_needed(player, args, handle, reason):
    if bird_nest_count(player) < 1:
        return player
    if args.bank:
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


def should_stop(player, args):
    compact = compact_player(player)
    return (
        (args.target_woodcutting_level > 0 and compact["woodcuttingLevel"] >= args.target_woodcutting_level)
        and (args.target_fletching_level > 0 and compact["fletchingLevel"] >= args.target_fletching_level)
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run normal-gameplay woodcutting and fletching loops.")
    parser.add_argument("--target-woodcutting-level", type=int, default=50)
    parser.add_argument("--target-fletching-level", type=int, default=50)
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--tree", default="auto", help="Tree, Oak, Willow, or auto.")
    parser.add_argument("--tree-max-distance", type=int, default=30)
    parser.add_argument("--chop-ticks", type=int, default=250)
    parser.add_argument("--fletch-ticks", type=int, default=250)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--run-reserve", default="auto")
    parser.add_argument("--route-max-batches", type=int, default=60)
    parser.add_argument("--route-max-walk-distance", type=int, default=80)
    parser.add_argument("--route-max-batch-distance", type=int, default=48)
    parser.add_argument("--route-direct-preview-distance", type=int, default=96)
    parser.add_argument("--route-probe-distance", type=int, default=48)
    parser.add_argument("--shop", default="varrock_general_store")
    parser.add_argument("--bank", default="varrock_west_bank")
    parser.add_argument("--bank-coins", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--shop-max-distance", type=int, default=14)
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
            })
            log("cycle {} wc={} fletch={} free={} logs={} products={} run={}".format(
                cycle,
                compact["woodcuttingLevel"],
                compact["fletchingLevel"],
                compact["freeSlots"],
                fletchable_log_count(player),
                product_count(player),
                compact["runEnergy"],
            ), args)

            if compact["isDead"] or compact["isInCombat"]:
                write_event(handle, "blocked", {"reason": "dead_or_combat", "player": compact})
                return 2
            if should_stop(player, args):
                write_event(handle, "target_reached", {"player": compact})
                break

            ensure_knife(player)
            player = ensure_axe_equipped(player, handle)
            player = ensure_run(player, args.min_run_energy, handle)

            if fletchable_log_count(player) > 0:
                player = close_interfaces_if_needed(player, handle, "before_fletch")
                fletch_args = {
                    "maxTicks": args.fletch_ticks,
                }
                if compact_player(player)["fletchingLevel"] < args.target_fletching_level:
                    fletch_args["targetFletchingLevel"] = args.target_fletching_level
                result = call_tool("fletch_logs_until_inventory_empty", fletch_args)
                player = result["player"]
                player = pickup_nearby_bird_nests(args, handle, "after_fletch")
                player = bank_bird_nests_if_needed(player, args, handle, "after_fletch")
                write_event(handle, "fletch", {
                    "cycle": cycle,
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
                player = sell_products(args, handle, "inventory_pressure")
                continue

            tree = choose_tree(player, args.tree)
            player = close_interfaces_if_needed(player, handle, "before_chop")
            result = call_tool("chop_tree_until_inventory_full", {
                "tree": tree,
                "maxDistance": args.tree_max_distance,
                "maxTicks": args.chop_ticks,
            })
            player = result["player"]
            player = pickup_nearby_bird_nests(args, handle, "after_chop")
            player = bank_bird_nests_if_needed(player, args, handle, "after_chop")
            write_event(handle, "chop", {
                "cycle": cycle,
                "tree": tree,
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
        player = pickup_nearby_bird_nests(args, handle, "final_start")
        player = bank_bird_nests_if_needed(player, args, handle, "final_start")
        if fletchable_log_count(player) > 0:
            player = close_interfaces_if_needed(player, handle, "final_before_fletch")
            result = call_tool("fletch_logs_until_inventory_empty", {
                "maxTicks": args.fletch_ticks,
                "targetFletchingLevel": args.target_fletching_level,
            })
            player = result["player"]
            player = pickup_nearby_bird_nests(args, handle, "final_after_fletch")
            player = bank_bird_nests_if_needed(player, args, handle, "final_after_fletch")
            write_event(handle, "final_fletch", {
                "batchStatus": result.get("batchStatus"),
                "batchTicks": result.get("batchTicks"),
                "player": compact_player(player),
                "products": product_count(player),
            })
        if not args.no_final_sell and product_count(player) > 0:
            try:
                player = sell_products(args, handle, "final")
            except Exception as exc:
                write_event(handle, "final_sell_failed", {"error": str(exc), "player": compact_player(observe())})
        write_event(handle, "done", {"player": compact_player(observe()), "runLog": str(run_path)})
        log("run log: {}".format(run_path), args, force=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
