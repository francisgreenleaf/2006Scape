#!/usr/bin/env python3
"""Get Crafting to 10 with local glassmaking, then make Seers bowstrings."""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
RUNS_DIR = ROOT / "data" / "crafting" / "runs"
CONTROL_DIR = ROOT / ".local" / "runners"
CUSTOM_FEATURE_FLAGS_FILE = REPO_ROOT / "2006Scape Server" / "src" / "main" / "java" / "com" / "rs2" / "game" / "content" / "custom" / "CustomFeatureFlags.java"
FEATURE_FLAG_NAME = "CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
import seers_flax_bowstring_runner as flax_runner  # noqa: E402
from profile_utils import resolve_profile, safe_profile  # noqa: E402


COINS = 995
GLASSBLOWING_PIPE = 1785
BUCKET_OF_SAND = 1783
SODA_ASH = 1781
MOLTEN_GLASS = 1775
BEER_GLASS = 1919

CATHERBY_BANK = "catherby_bank"
CATHERBY_BANK_TILE = {"x": 2814, "y": 3440, "height": 0}
CATHERBY_CHARTER_SHOP_TILE = {"x": 2804, "y": 3422, "height": 0}
ARDOUGNE_NORTH_BANK = "ardougne_north_bank"
ARDOUGNE_FURNACE_TILE = {"x": 2601, "y": 3310, "height": 0}
ARDOUGNE_FURNACE_OBJECT = 2781
BEER_GLASS_MAKE_ALL_BUTTON = 48115


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def run_stem(profile):
    return "seers-crafting-plan-{}".format(safe_profile(profile))


def status_path(profile):
    return CONTROL_DIR / "{}.status.json".format(run_stem(profile))


def stop_path(profile):
    return CONTROL_DIR / "{}.stop".format(run_stem(profile))


def compact(player):
    data = bridge.compact_player(player, ("crafting",))
    data.update({
        "coins": bridge.count_inventory_item(player, COINS),
        "sand": bridge.count_inventory_item(player, BUCKET_OF_SAND),
        "sodaAsh": bridge.count_inventory_item(player, SODA_ASH),
        "moltenGlass": bridge.count_inventory_item(player, MOLTEN_GLASS),
        "beerGlass": bridge.count_inventory_item(player, BEER_GLASS),
        "pipe": bridge.count_inventory_item(player, GLASSBLOWING_PIPE),
        "flax": bridge.count_inventory_item(player, flax_runner.FLAX),
        "bowstrings": bridge.count_inventory_item(player, flax_runner.BOW_STRING),
        "bankedBowstrings": bridge.count_bank_item(player, flax_runner.BOW_STRING),
    })
    return data


def write(handle, event, data):
    bridge.write_event(handle, event, data)


def write_status(args, phase, player, run_path=None, extra=None):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "runner": "seers_crafting_plan_runner",
        "updatedAt": utc_now(),
        "phase": phase,
        "profile": args.profile,
        "pid": os.getpid(),
        "stopRequested": stop_path(args.profile).exists(),
        "runLog": str(run_path) if run_path else None,
        "player": compact(player) if player else None,
        "targetCraftingLevel": args.target_crafting_level,
        "targetBowstrings": args.target_bowstrings,
        "args": vars(args),
    }
    if extra:
        payload.update(extra)
    status_path(args.profile).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                                         encoding="utf-8")


def print_status(args):
    path = status_path(args.profile)
    payload = {
        "statusPath": str(path),
        "stopPath": str(stop_path(args.profile)),
        "stopRequested": stop_path(args.profile).exists(),
    }
    if path.exists():
        payload["status"] = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload["error"] = "no_status"
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def request_stop(args):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    path = stop_path(args.profile)
    path.write_text(utc_now() + "\n", encoding="utf-8")
    child_path = flax_runner.stop_path(args.profile)
    child_path.write_text(utc_now() + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "stopRequested": True,
        "stopPath": str(path),
        "childStopPath": str(child_path),
    }, indent=2, sort_keys=True))
    return 0


def clear_stop(args):
    path = stop_path(args.profile)
    if path.exists():
        path.unlink()
    child_path = flax_runner.stop_path(args.profile)
    if child_path.exists():
        child_path.unlink()
    print(json.dumps({
        "ok": True,
        "stopRequested": False,
        "stopPath": str(path),
        "childStopPath": str(child_path),
    }, indent=2, sort_keys=True))
    return 0


def catherby_charter_feature_enabled():
    if not CUSTOM_FEATURE_FLAGS_FILE.exists():
        return False
    text = CUSTOM_FEATURE_FLAGS_FILE.read_text(encoding="utf-8")
    pattern = r"\b{}\b\s*=\s*true\s*;".format(re.escape(FEATURE_FLAG_NAME))
    return re.search(pattern, text) is not None


def require_catherby_charter_feature_enabled():
    if not catherby_charter_feature_enabled():
        raise RuntimeError("{} is disabled in {}; Catherby glass bootstrap is unavailable.".format(
            FEATURE_FLAG_NAME, CUSTOM_FEATURE_FLAGS_FILE))


def stop_requested(args):
    return stop_path(args.profile).exists()


def observe(profile):
    return bridge.observe_xs(profile=profile)


def safety_check(player):
    if player.get("isDead"):
        raise RuntimeError("player is dead")
    if player.get("isInCombat"):
        raise RuntimeError("player is in combat")


def player_from_or(result, profile, fallback):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return fallback or observe(profile)


def ensure_bank(player, args, handle, reason):
    if not bool(player.get("inBankArea", False)):
        player = flax_runner.ml2_route_to(CATHERBY_BANK, args, handle, reason + "_route", arrival_radius=2)
    result = bridge.call_tool("deposit_inventory_items_XS", {"name": "__codex_open_bank_only__"}, profile=args.profile)
    player = player_from_or(result, args.profile, player)
    write(handle, "open_bank", {"reason": reason, "success": bool(result.get("success")), "player": compact(player)})
    return player


def deposit_glass_products(player, args, handle, reason):
    player = ensure_bank(player, args, handle, reason)
    result = bridge.call_tool("deposit_inventory_items_XS", {
        "itemIds": [BEER_GLASS, MOLTEN_GLASS, BUCKET_OF_SAND, SODA_ASH],
    }, profile=args.profile)
    player = player_from_or(result, args.profile, player)
    write(handle, "deposit_glass_products", {
        "reason": reason,
        "success": bool(result.get("success")),
        "depositedAmount": result.get("depositedAmount"),
        "player": compact(player),
    })
    return player


def withdraw_coins(player, args, handle):
    player = ensure_bank(player, args, handle, "withdraw_coins")
    if bridge.count_inventory_item(player, COINS) >= args.coin_float:
        return player
    result = bridge.call_tool("withdraw_bank_items_XS", {
        "itemId": COINS,
        "amount": int(args.coin_float - bridge.count_inventory_item(player, COINS)),
    }, profile=args.profile)
    player = player_from_or(result, args.profile, player)
    write(handle, "withdraw_coins", {
        "coinFloat": args.coin_float,
        "success": bool(result.get("success")),
        "withdrawnAmount": result.get("withdrawnAmount"),
        "player": compact(player),
    })
    return player


def route_to_catherby_shop(player, args, handle):
    player = flax_runner.ml2_route_to(CATHERBY_BANK, args, handle, "catherby_bank_for_charter", arrival_radius=2)
    player = flax_runner.walk_tile(CATHERBY_CHARTER_SHOP_TILE, args, handle, "catherby_bank_to_charter_shop",
                                   max_ticks=70, stop_distance=3)
    return player


def buy_item(item_id, amount, args, handle, reason):
    result = bridge.call_tool("buy_shop_item", {"itemId": int(item_id), "amount": int(amount)}, profile=args.profile)
    player = player_from_or(result, args.profile, None)
    write(handle, "buy_shop_item", {
        "reason": reason,
        "itemId": int(item_id),
        "amount": int(amount),
        "success": bool(result.get("success")),
        "bought": result.get("bought"),
        "player": compact(player),
    })
    return player, int(result.get("bought", 0) or 0)


def buy_glass_supplies(player, args, handle):
    player = withdraw_coins(player, args, handle)
    player = route_to_catherby_shop(player, args, handle)
    result = bridge.call_tool("interact_npc", {
        "npcId": 4651,
        "option": "second",
        "maxDistance": 10,
        "requireReachable": True,
    }, profile=args.profile)
    player = player_from_or(result, args.profile, player)
    write(handle, "open_charter_shop", {"success": bool(result.get("success")), "player": compact(player)})
    if not result.get("success"):
        result = bridge.call_tool("open_nearest_shop", {"name": "trader", "maxDistance": 10}, profile=args.profile)
        player = player_from_or(result, args.profile, player)
        write(handle, "open_charter_shop_fallback", {"success": bool(result.get("success")), "player": compact(player)})
    if bridge.count_inventory_item(player, GLASSBLOWING_PIPE) <= 0:
        player, _ = buy_item(GLASSBLOWING_PIPE, 1, args, handle, "pipe")
    free = int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0)
    pairs = max(1, min(args.supply_batch, free // 2))
    player, sand = buy_item(BUCKET_OF_SAND, pairs, args, handle, "sand")
    player, soda = buy_item(SODA_ASH, pairs, args, handle, "soda_ash")
    bought_pairs = min(sand, soda)
    if bought_pairs <= 0:
        raise RuntimeError("unable to buy glassmaking supply pair from Catherby charter shop")
    return player


def route_to_ardougne_furnace(player, args, handle):
    player = flax_runner.walk_tile(CATHERBY_BANK_TILE, args, handle, "charter_shop_to_catherby_bank",
                                   max_ticks=70, stop_distance=2)
    player = flax_runner.ml2_route_to(ARDOUGNE_NORTH_BANK, args, handle, "ardougne_north_bank_for_furnace",
                                      arrival_radius=2)
    return flax_runner.walk_tile(ARDOUGNE_FURNACE_TILE, args, handle, "ardougne_bank_to_furnace",
                                 max_ticks=90, stop_distance=2)


def make_molten_glass(player, args, handle):
    player = route_to_ardougne_furnace(player, args, handle)
    made = 0
    while bridge.count_inventory_item(player, BUCKET_OF_SAND) > 0 and bridge.count_inventory_item(player, SODA_ASH) > 0:
        before_xp = bridge.skill_xp(player, "crafting")
        before_molten = bridge.count_inventory_item(player, MOLTEN_GLASS)
        result = bridge.call_tool("use_item_on_object", {
            "itemId": BUCKET_OF_SAND,
            "objectId": ARDOUGNE_FURNACE_OBJECT,
            "x": ARDOUGNE_FURNACE_TILE["x"],
            "y": ARDOUGNE_FURNACE_TILE["y"],
            "height": ARDOUGNE_FURNACE_TILE["height"],
        }, profile=args.profile)
        player = player_from_or(result, args.profile, player)
        wait = bridge.call_tool("wait_ticks_XS", {"ticks": 2}, profile=args.profile)
        player = player_from_or(wait, args.profile, player)
        if bridge.count_inventory_item(player, MOLTEN_GLASS) > before_molten:
            made += 1
        write(handle, "make_molten_glass", {
            "success": bool(result.get("success")),
            "handledCustomContent": result.get("handledCustomContent"),
            "beforeCraftingXp": before_xp,
            "afterCraftingXp": bridge.skill_xp(player, "crafting"),
            "madeThisTrip": made,
            "player": compact(player),
        })
    return player


def blow_beer_glasses(player, args, handle):
    if bridge.count_inventory_item(player, MOLTEN_GLASS) <= 0:
        return player
    if bridge.count_inventory_item(player, GLASSBLOWING_PIPE) <= 0:
        raise RuntimeError("glassblowing pipe is required to blow beer glasses")
    before_molten = bridge.count_inventory_item(player, MOLTEN_GLASS)
    before_beer = bridge.count_inventory_item(player, BEER_GLASS)
    before_xp = bridge.skill_xp(player, "crafting")
    use_result = bridge.call_tool("use_item_on_item", {
        "itemId": GLASSBLOWING_PIPE,
        "targetItemId": MOLTEN_GLASS,
    }, profile=args.profile)
    player = player_from_or(use_result, args.profile, player)
    button = bridge.call_tool("click_interface_button_XXS", {"buttonId": BEER_GLASS_MAKE_ALL_BUTTON}, profile=args.profile)
    player = player_from_or(button, args.profile, player)
    wait = bridge.call_tool("wait_until_idle_XS", {
        "maxTicks": max(40, before_molten * 4 + 12),
        "movement": False,
        "skilling": True,
        "combat": False,
    }, profile=args.profile)
    player = player_from_or(wait, args.profile, player)
    write(handle, "blow_beer_glasses", {
        "beforeMoltenGlass": before_molten,
        "afterMoltenGlass": bridge.count_inventory_item(player, MOLTEN_GLASS),
        "beforeBeerGlass": before_beer,
        "afterBeerGlass": bridge.count_inventory_item(player, BEER_GLASS),
        "beforeCraftingXp": before_xp,
        "afterCraftingXp": bridge.skill_xp(player, "crafting"),
        "player": compact(player),
    })
    return player


def bootstrap_crafting(player, args, handle):
    require_catherby_charter_feature_enabled()
    batches = 0
    while bridge.skill_level(player, "crafting") < args.target_crafting_level:
        if stop_requested(args):
            write_status(args, "stopped", player, extra={"reason": "stop_requested"})
            return player
        if batches >= args.max_glass_batches:
            raise RuntimeError("reached max glass batches before Crafting level {}".format(args.target_crafting_level))
        player = buy_glass_supplies(player, args, handle)
        player = make_molten_glass(player, args, handle)
        player = blow_beer_glasses(player, args, handle)
        player = deposit_glass_products(player, args, handle, "glass_batch_done")
        batches += 1
        write_status(args, "glass_bootstrap", player, extra={"glassBatches": batches})
        log("glass batch {} crafting={}".format(batches, bridge.skill_level(player, "crafting")), args)
        if bridge.skill_level(player, "crafting") < args.target_crafting_level:
            time.sleep(max(0.0, args.shop_restock_wait_seconds))
    return player


def run_plan(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-seers-crafting-plan-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    if stop_path(args.profile).exists():
        stop_path(args.profile).unlink()
    with run_path.open("a", encoding="utf-8") as handle:
        player = observe(args.profile)
        safety_check(player)
        write(handle, "run_start", {"profile": args.profile, "player": compact(player), "args": vars(args)})
        write_status(args, "running", player, run_path=run_path)
        if bridge.skill_level(player, "crafting") < args.target_crafting_level:
            player = bootstrap_crafting(player, args, handle)
        if stop_requested(args):
            write_status(args, "stopped", player, run_path=run_path, extra={"reason": "stop_requested"})
            return 0
        write_status(args, "bowstring_phase", player, run_path=run_path)
        flax_args = argparse.Namespace(
            profile=args.profile,
            target_bowstrings=args.target_bowstrings,
            max_cycles=args.max_flax_cycles,
            combat_level=args.combat_level,
            food=args.food,
            allow_ml2_route=True,
            allow_below_level=False,
            pick_only=False,
            quiet=args.quiet,
            status=False,
            request_stop=False,
            clear_stop=False,
        )
        return flax_runner.run_loop(flax_args)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="", help="Bridge profile. Defaults to RS_PROFILE, then MrFlame.")
    parser.add_argument("--target-crafting-level", type=int, default=10)
    parser.add_argument("--target-bowstrings", type=int, default=5000)
    parser.add_argument("--max-flax-cycles", type=int, default=0)
    parser.add_argument("--max-glass-batches", type=int, default=12)
    parser.add_argument("--supply-batch", type=int, default=10)
    parser.add_argument("--coin-float", type=int, default=500)
    parser.add_argument("--shop-restock-wait-seconds", type=float, default=15.0)
    parser.add_argument("--combat-level", type=int, default=0)
    parser.add_argument("--food", type=int, default=0)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--status", action="store_true", help="Print cooperative runner status and exit.")
    parser.add_argument("--request-stop", action="store_true", help="Ask the runner to stop at the next safe boundary.")
    parser.add_argument("--clear-stop", action="store_true", help="Clear a pending stop request.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.profile = resolve_profile(args.profile)
    if args.status:
        return print_status(args)
    if args.request_stop:
        return request_stop(args)
    if args.clear_stop:
        return clear_stop(args)
    return run_plan(args)


if __name__ == "__main__":
    raise SystemExit(main())
