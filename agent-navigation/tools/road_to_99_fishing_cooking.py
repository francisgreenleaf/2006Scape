#!/usr/bin/env python3
"""Road to 99 Fishing/Cooking wrapper for the Catherby food runner."""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import uuid

import bridge_script as bridge
from profile_utils import resolve_profile
from usage_log import log_usage


RUNS_DIR = bridge.ROOT / "data" / "food" / "road-to-99-fishing-cooking-runs"
RUNNER_CONTROL_DIR = bridge.ROOT / ".local" / "runners"
RUNNER_CONTROL_NAME = "road-to-99-fishing-cooking"
CATHERBY_RUNNER = bridge.ROOT / "tools" / "catherby_food_runner.py"
CATHERBY_STATUS = bridge.ROOT / "tools" / "catherby_food_runner_XS.py"

COINS = 995
COOKING_GAUNTLETS = 775
COOKED_LOBSTER = 379
CALEB_NPC = 666

CATHERBY_BANK_TARGET = "catherby_bank"
CATHERBY_ARHEIN_TARGET = "2806,3433,0"

COOKED_FISH_IDS = [315, 319, 325, 333, 329, 347, 351, 355, 361, 365, 373, 379, 385]
SELL_UNTIL_GAUNTLETS_KEEP_LOBSTERS = 0
GAUNTLET_COST = 25000


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_event(handle, event, data):
    if handle is None:
        return
    record = {"timestamp": utc_now(), "event": event}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def log(args, message):
    if not args.quiet:
        print(message, flush=True)


def runner_profile_label(args):
    profile = resolve_profile(getattr(args, "profile", ""), default="").strip()
    return profile or "default"


def runner_control_stem(args):
    profile = runner_profile_label(args)
    if profile == "default":
        return RUNNER_CONTROL_NAME
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in profile).strip("-")
    return "{}-{}".format(RUNNER_CONTROL_NAME, slug or "profile")


def runner_status_path(args):
    return RUNNER_CONTROL_DIR / "{}.status.json".format(runner_control_stem(args))


def runner_primary_stop_path(args):
    return RUNNER_CONTROL_DIR / "{}.stop".format(runner_control_stem(args))


def runner_stop_paths(args):
    return [runner_primary_stop_path(args)]


def runner_stop_requested(args):
    return any(path.exists() for path in runner_stop_paths(args))


def existing_runner_stop_paths(args):
    return [str(path) for path in runner_stop_paths(args) if path.exists()]


def args_summary(args):
    return {
        "profile": args.profile,
        "cycles": args.cycles,
        "targetFishingLevel": args.target_fishing_level,
        "targetCookingLevel": args.target_cooking_level,
        "gauntletCoinTarget": args.gauntlet_coin_target,
        "keepCookedLobsters": args.keep_cooked_lobsters,
        "maxSaleBatches": args.max_sale_batches,
        "runMode": args.run_mode,
        "eatAt": args.eat_at,
    }


def clear_runner_stop_requests(args):
    cleared = []
    for path in runner_stop_paths(args):
        try:
            path.unlink()
            cleared.append(str(path))
        except FileNotFoundError:
            pass
    return cleared


def request_runner_stop(args):
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "runner": RUNNER_CONTROL_NAME,
        "profile": runner_profile_label(args),
        "requestedAt": utc_now(),
        "pid": os.getpid(),
    }
    paths = runner_stop_paths(args)
    for path in paths:
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    catherby = run_catherby_control(args, ["--request-stop", "--quiet"], check=False)
    print(json.dumps({
        "ok": True,
        "runner": RUNNER_CONTROL_NAME,
        "profile": runner_profile_label(args),
        "stopRequests": [str(path) for path in paths],
        "catherbyStopReturncode": catherby.returncode,
    }, sort_keys=True))
    return 0


def print_runner_status(args):
    payload = {
        "ok": runner_status_path(args).exists(),
        "runner": RUNNER_CONTROL_NAME,
        "profile": runner_profile_label(args),
        "statusPath": str(runner_status_path(args)),
        "stopRequested": runner_stop_requested(args),
        "stopFiles": existing_runner_stop_paths(args),
    }
    path = runner_status_path(args)
    if path.exists():
        try:
            payload["status"] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            payload["ok"] = False
            payload["error"] = str(exc)
    catherby = run_status_command(args, check=False)
    payload["catherbyStatusReturncode"] = catherby.returncode
    if catherby.stdout.strip():
        try:
            payload["catherby"] = json.loads(catherby.stdout)
        except json.JSONDecodeError:
            payload["catherbyOutput"] = catherby.stdout.strip()[:1000]
    print(json.dumps(payload, sort_keys=True))
    return 1 if payload.get("error") else 0


def compact_player(player):
    tile = player.get("tile")
    return {
        "tile": tile if tile else "{},{},{}".format(player.get("x"), player.get("y"), player.get("height")),
        "hitpoints": player.get("hitpoints"),
        "maxHitpoints": player.get("maxHitpoints"),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "inBankArea": bool(player.get("inBankArea", False)),
        "freeSlots": player.get("freeInventorySlots"),
        "runEnergy": player.get("runEnergy"),
        "runEnabled": bool(player.get("runEnabled", False)),
        "fishingLevel": bridge.skill_level(player, "fishing"),
        "fishingXp": bridge.skill_xp(player, "fishing"),
        "cookingLevel": bridge.skill_level(player, "cooking"),
        "cookingXp": bridge.skill_xp(player, "cooking"),
        "inventoryCoins": bridge.count_inventory_item(player, COINS),
        "bankCoins": bridge.count_bank_item(player, COINS),
        "cookedLobsters": total_item(player, COOKED_LOBSTER),
        "hasCookingGauntlets": owns_cooking_gauntlets(player),
    }


def write_runner_status(args, status, reason, player=None, run_path=None, cycle=None, extra=None):
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "runner": RUNNER_CONTROL_NAME,
        "profile": runner_profile_label(args),
        "status": status,
        "reason": reason,
        "pid": os.getpid(),
        "updatedAt": utc_now(),
        "stopRequested": runner_stop_requested(args),
        "stopFiles": existing_runner_stop_paths(args),
        "args": args_summary(args),
    }
    if run_path is not None:
        payload["runLog"] = str(run_path)
    if cycle is not None:
        payload["cycle"] = cycle
    if player is not None:
        payload["player"] = compact_player(player)
        payload["policy"] = policy_summary(player, args)
    if extra:
        payload.update(extra)
    path = runner_status_path(args)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def call_tool(tool, arguments=None, profile=""):
    return bridge.call_tool(tool, arguments or {}, profile=profile)


def player_from_or_observe(result, profile):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return bridge.observe_xs(profile)


def item_count(items, item_id):
    total = 0
    for item in items or []:
        try:
            current = int(item.get("id", item.get("itemId", -1)) or -1)
            amount = int(item.get("amount", item.get("a", 0)) or 0)
        except (TypeError, ValueError):
            continue
        if current == int(item_id):
            total += amount
    return total


def equipment_count(player, item_id):
    return item_count(player.get("equipment") or [], item_id)


def total_item(player, item_id):
    return (
        bridge.count_inventory_item(player, item_id)
        + bridge.count_bank_item(player, item_id)
        + equipment_count(player, item_id)
    )


def coin_total(player):
    return bridge.count_inventory_item(player, COINS) + bridge.count_bank_item(player, COINS)


def owns_cooking_gauntlets(player):
    return total_item(player, COOKING_GAUNTLETS) > 0


def refresh_if_gauntlets_missing(args, player):
    if owns_cooking_gauntlets(player):
        return player
    # Compact bank/deposit responses can omit equipment and make equipped
    # gauntlets look absent. Re-observe before any sale or purchase decision.
    return bridge.observe_xs(args.profile)


def targets_met(player, args):
    return (
        bridge.skill_level(player, "fishing") >= int(args.target_fishing_level)
        and bridge.skill_level(player, "cooking") >= int(args.target_cooking_level)
    )


def policy_summary(player, args):
    plan = sale_plan(player, args)
    return {
        "ownsCookingGauntlets": owns_cooking_gauntlets(player),
        "coinTotal": coin_total(player),
        "gauntletCoinTarget": int(args.gauntlet_coin_target),
        "cookedLobstersTotal": total_item(player, COOKED_LOBSTER),
        "keepCookedLobsters": int(args.keep_cooked_lobsters),
        "saleItemTotal": sum(plan.values()),
        "salePlan": {str(key): value for key, value in sorted(plan.items()) if value > 0},
    }


def sale_plan(player, args):
    if owns_cooking_gauntlets(player):
        return {}
    plan = {}
    for item_id in COOKED_FISH_IDS:
        total = total_item(player, item_id)
        keep = int(args.keep_cooked_lobsters) if item_id == COOKED_LOBSTER else 0
        sell = max(0, total - keep)
        if sell > 0:
            plan[item_id] = sell
    return plan


def sale_inventory_amount(player, plan):
    total = 0
    for item_id, requested in plan.items():
        total += min(int(requested), bridge.count_inventory_item(player, item_id))
    return total


def ensure_bank(args, handle, reason):
    player = bridge.observe_xs(args.profile)
    if not bool(player.get("inBankArea", False)):
        write_event(handle, "route_bank_start", {"reason": reason, "player": compact_player(player)})
        bridge.route_to(
            CATHERBY_BANK_TARGET,
            profile=args.profile,
            handle=handle,
            reason=reason,
            extra_args={"runner_max_batches": args.route_max_batches, "max_batch_distance": args.max_batch_distance},
        )
    opened = call_tool("deposit_inventory_items_XS", {"name": "__codex_open_bank_only__"}, profile=args.profile)
    player = player_from_or_observe(opened, args.profile)
    write_event(handle, "ensure_bank", {
        "reason": reason,
        "success": bool(opened.get("success")),
        "message": opened.get("message"),
        "player": compact_player(player),
    })
    return player


def close_interfaces(args, handle, reason):
    result = call_tool("close_interfaces", {}, profile=args.profile)
    player = player_from_or_observe(result, args.profile)
    write_event(handle, "close_interfaces", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return player


def deposit_sale_coins(args, handle, reason):
    player = ensure_bank(args, handle, reason + "_bank")
    if bridge.count_inventory_item(player, COINS) <= 0:
        return player
    result = call_tool("deposit_excess_coins_XXS", {"keepAmount": 0}, profile=args.profile)
    player = player_from_or_observe(result, args.profile)
    write_event(handle, "deposit_sale_coins", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return ensure_bank(args, handle, reason + "_refresh")


def withdraw_sale_batch(args, handle, player, plan):
    if sale_inventory_amount(player, plan) > 0:
        return player
    free_slots = int(player.get("freeInventorySlots", 0) or 0)
    if free_slots <= 0:
        raise RuntimeError("cannot withdraw sale fish: no free inventory slots at bank")
    for item_id, requested in sorted(plan.items()):
        banked = bridge.count_bank_item(player, item_id)
        if banked <= 0:
            continue
        amount = min(free_slots, int(requested), banked)
        if amount <= 0:
            continue
        result = call_tool("withdraw_bank_items_XS", {"itemId": int(item_id), "amount": int(amount)}, profile=args.profile)
        player = player_from_or_observe(result, args.profile)
        write_event(handle, "withdraw_sale_batch", {
            "itemId": int(item_id),
            "requested": int(requested),
            "withdrawAmount": int(amount),
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact_player(player),
        })
        return player
    return player


def route_to_arhein_shop(args, handle):
    player = close_interfaces(args, handle, "before_arhein_shop")
    write_event(handle, "route_arhein_start", {"player": compact_player(player)})
    bridge.route_to(
        CATHERBY_ARHEIN_TARGET,
        profile=args.profile,
        handle=handle,
        reason="road99_arhein_shop",
        extra_args={"runner_max_batches": args.route_max_batches, "max_batch_distance": args.max_batch_distance},
    )
    opened = call_tool("open_nearest_shop", {"name": "arhein", "maxDistance": int(args.shop_max_distance)}, profile=args.profile)
    player = player_from_or_observe(opened, args.profile)
    write_event(handle, "open_arhein_shop", {
        "success": bool(opened.get("success")),
        "message": opened.get("message"),
        "npc": opened.get("npc"),
        "player": compact_player(player),
    })
    if not opened.get("success"):
        raise RuntimeError("could not open Arhein Store: {}".format(opened.get("message", "")))
    return player


def sell_inventory_fish(args, handle, player, plan):
    sell_ids = [item_id for item_id in sorted(plan) if bridge.count_inventory_item(player, item_id) > 0]
    if not sell_ids:
        return player, 0, 0
    amount = sum(min(plan[item_id], bridge.count_inventory_item(player, item_id)) for item_id in sell_ids)
    before_coins = bridge.count_inventory_item(player, COINS)
    result = call_tool("sell_inventory_items", {"itemIds": sell_ids, "amount": int(amount)}, profile=args.profile)
    player = player_from_or_observe(result, args.profile)
    sold = int(result.get("sold", 0) or 0)
    coins = int(result.get("coinsReceived", 0) or 0)
    if coins <= 0:
        coins = max(0, bridge.count_inventory_item(player, COINS) - before_coins)
    write_event(handle, "sell_inventory_fish", {
        "itemIds": sell_ids,
        "requestedAmount": int(amount),
        "sold": sold,
        "coinsReceived": coins,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "soldItems": result.get("soldItems", []),
        "player": compact_player(player),
    })
    return player, sold, coins


def deposit_reserved_lobsters(args, handle, player, reason):
    if owns_cooking_gauntlets(player):
        return player
    inventory_lobsters = bridge.count_inventory_item(player, COOKED_LOBSTER)
    if inventory_lobsters <= 0:
        return player
    if total_item(player, COOKED_LOBSTER) > int(args.keep_cooked_lobsters):
        return player
    player = ensure_bank(args, handle, reason + "_bank")
    result = call_tool("deposit_inventory_items_XS", {"itemIds": [COOKED_LOBSTER]}, profile=args.profile)
    player = player_from_or_observe(result, args.profile)
    write_event(handle, "deposit_reserved_lobsters", {
        "reason": reason,
        "requestedItemId": COOKED_LOBSTER,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return player


def sell_inventory_before_bank(args, handle, player):
    plan = sale_plan(player, args)
    if sale_inventory_amount(player, plan) <= 0:
        return deposit_reserved_lobsters(args, handle, player, "reserve_after_no_inventory_sale"), 0, 0
    player = route_to_arhein_shop(args, handle)
    player, sold, coins = sell_inventory_fish(args, handle, player, plan)
    player = close_interfaces(args, handle, "after_inventory_sale")
    player = deposit_sale_coins(args, handle, "after_inventory_sale")
    player = deposit_reserved_lobsters(args, handle, player, "reserve_after_inventory_sale")
    return player, sold, coins


def sell_policy_batches(args, handle, player):
    total_sold = 0
    total_coins = 0
    batches = 0
    player = refresh_if_gauntlets_missing(args, player)
    if owns_cooking_gauntlets(player):
        write_event(handle, "sell_policy_skip", {
            "reason": "owns_cooking_gauntlets",
            "player": compact_player(player),
        })
        return player, total_sold, total_coins
    player, sold, coins = sell_inventory_before_bank(args, handle, player)
    total_sold += sold
    total_coins += coins
    player = ensure_bank(args, handle, "sell_policy_start")
    while batches < int(args.max_sale_batches):
        player = refresh_if_gauntlets_missing(args, player)
        if owns_cooking_gauntlets(player):
            write_event(handle, "sell_policy_skip", {
                "reason": "owns_cooking_gauntlets_after_bank_refresh",
                "player": compact_player(player),
            })
            break
        plan = sale_plan(player, args)
        if not plan:
            break
        player = withdraw_sale_batch(args, handle, player, plan)
        if sale_inventory_amount(player, plan) <= 0:
            break
        player = route_to_arhein_shop(args, handle)
        player, sold, coins = sell_inventory_fish(args, handle, player, plan)
        total_sold += sold
        total_coins += coins
        batches += 1
        player = close_interfaces(args, handle, "after_sale_batch")
        player = deposit_sale_coins(args, handle, "after_sale_batch")
        if sold <= 0:
            break
    if batches >= int(args.max_sale_batches):
        raise RuntimeError("sale policy hit max sale batches ({})".format(args.max_sale_batches))
    write_event(handle, "sell_policy_finish", {
        "sold": total_sold,
        "coinsReceived": total_coins,
        "batches": batches,
        "player": compact_player(player),
    })
    return player, total_sold, total_coins


def buy_cooking_gauntlets_if_ready(args, handle, player):
    player = ensure_bank(args, handle, "gauntlet_check")
    player = refresh_if_gauntlets_missing(args, player)
    if owns_cooking_gauntlets(player):
        return player, False
    if coin_total(player) < int(args.gauntlet_coin_target):
        write_event(handle, "gauntlet_deferred", {
            "reason": "not_enough_coins",
            "coinTotal": coin_total(player),
            "target": int(args.gauntlet_coin_target),
            "player": compact_player(player),
        })
        return player, False
    carried = bridge.count_inventory_item(player, COINS)
    needed = max(0, int(args.gauntlet_coin_target) - carried)
    if needed > 0:
        result = call_tool("withdraw_bank_items_XS", {"itemId": COINS, "amount": needed}, profile=args.profile)
        player = player_from_or_observe(result, args.profile)
        write_event(handle, "withdraw_gauntlet_coins", {
            "requested": needed,
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact_player(player),
        })
    player = close_interfaces(args, handle, "before_caleb")
    player = bridge.enter_catherby_caleb_house(
        player,
        profile=args.profile,
        handle=handle,
        reason="road99_caleb_house",
        compact_player_fn=compact_player,
    )
    found = call_tool("find_nearest_npc", {"npcIds": [CALEB_NPC], "maxDistance": int(args.npc_max_distance)}, profile=args.profile)
    npc = found.get("npc") or {}
    if not found.get("success") or npc.get("npcIndex") is None:
        raise RuntimeError("could not find Caleb for cooking gauntlets")
    talked = call_tool("interact_npc", {"npcIndex": npc.get("npcIndex"), "option": "first", "requireReachable": True}, profile=args.profile)
    if talked.get("approaching"):
        waited = call_tool("wait_until_idle_XS", {"maxTicks": 40}, profile=args.profile)
        write_event(handle, "approach_caleb", {
            "success": bool(waited.get("success")),
            "message": waited.get("message"),
            "player": compact_player(player_from_or_observe(waited, args.profile)),
        })
        found = call_tool("find_nearest_npc", {"npcIds": [CALEB_NPC], "maxDistance": int(args.npc_max_distance)}, profile=args.profile)
        npc = found.get("npc") or {}
        if not found.get("success") or npc.get("npcIndex") is None:
            raise RuntimeError("could not find Caleb after approach for cooking gauntlets")
        talked = call_tool("interact_npc", {"npcIndex": npc.get("npcIndex"), "option": "first", "requireReachable": True}, profile=args.profile)
    if not talked.get("success"):
        raise RuntimeError("could not start Caleb dialogue: {}".format(talked.get("message", "")))
    continued = call_tool("continue_dialogue", {}, profile=args.profile)
    selected = call_tool("click_interface_button_XS", {"buttonId": 9157}, profile=args.profile)
    player = player_from_or_observe(selected, args.profile)
    if total_item(player, COOKING_GAUNTLETS) > 0 and equipment_count(player, COOKING_GAUNTLETS) <= 0:
        equipped = call_tool("equip_item", {"itemId": COOKING_GAUNTLETS}, profile=args.profile)
        player = player_from_or_observe(equipped, args.profile)
        write_event(handle, "equip_cooking_gauntlets", {
            "success": bool(equipped.get("success")),
            "message": equipped.get("message"),
            "player": compact_player(player),
        })
    write_event(handle, "buy_cooking_gauntlets", {
        "talkSuccess": bool(talked.get("success")),
        "continueSuccess": bool(continued.get("success")),
        "selectSuccess": bool(selected.get("success")),
        "ownedAfter": owns_cooking_gauntlets(player),
        "player": compact_player(player),
    })
    player = deposit_sale_coins(args, handle, "after_gauntlets")
    if not owns_cooking_gauntlets(player):
        raise RuntimeError("gauntlet purchase did not result in cooking gauntlets")
    return player, True


def run_catherby_control(args, extra_args, check=True):
    command = [sys.executable, str(CATHERBY_RUNNER), "--profile", args.profile]
    command.extend(extra_args)
    env = os.environ.copy()
    env["PROFILE"] = args.profile
    env["RS_PROFILE"] = args.profile
    env["RS_TRACE_PROFILE"] = args.profile
    return subprocess.run(
        command,
        cwd=str(bridge.REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=check,
    )


def run_status_command(args, check=True):
    command = [sys.executable, str(CATHERBY_STATUS), "--profile", args.profile]
    env = os.environ.copy()
    env["PROFILE"] = args.profile
    env["RS_PROFILE"] = args.profile
    env["RS_TRACE_PROFILE"] = args.profile
    return subprocess.run(
        command,
        cwd=str(bridge.REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=check,
    )


def read_catherby_status(args):
    result = run_status_command(args, check=False)
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"parseError": result.stdout.strip()[:1000], "returncode": result.returncode}


def stop_existing_catherby_runner(args, handle):
    status = read_catherby_status(args)
    if status.get("state") != "running":
        return
    write_event(handle, "stop_existing_catherby_start", {"status": status})
    run_catherby_control(args, ["--request-stop", "--quiet"], check=False)
    deadline = time.time() + int(args.stop_existing_timeout)
    while time.time() < deadline:
        time.sleep(float(args.stop_poll_seconds))
        status = read_catherby_status(args)
        write_event(handle, "stop_existing_catherby_poll", {"status": status})
        if status.get("state") != "running":
            return
    raise RuntimeError("existing Catherby food runner did not stop within timeout")


def run_catherby_cycle(args, handle, cycle):
    player = bridge.observe_xs(args.profile)
    write_runner_status(args, "running", "catherby_cycle", run_path=args._run_path, cycle=cycle,
                        player=player)
    write_event(handle, "catherby_cycle_start", {"cycle": cycle})
    extra = [
        "--cycles", "1",
        "--run-mode", args.run_mode,
        "--eat-at", str(int(args.eat_at)),
        "--quiet",
    ]
    if not owns_cooking_gauntlets(player):
        extra.extend(["--post-cook-action", "keep-cooked-inventory"])
    result = run_catherby_control(args, extra, check=False)
    write_event(handle, "catherby_cycle_finish", {
        "cycle": cycle,
        "returncode": result.returncode,
        "stdoutTail": result.stdout.strip().splitlines()[-5:],
        "stderr": result.stderr.strip()[:1000],
    })
    if result.returncode != 0:
        raise RuntimeError("Catherby food runner cycle failed: {}".format(result.stderr.strip() or result.stdout.strip()))
    return bridge.observe_xs(args.profile)


def road_cycle(args, handle, cycle):
    player = run_catherby_cycle(args, handle, cycle)
    write_runner_status(args, "running", "post_cycle_policy", run_path=args._run_path, cycle=cycle, player=player)
    player, sold, coins = sell_policy_batches(args, handle, player)
    player, bought = buy_cooking_gauntlets_if_ready(args, handle, player)
    write_event(handle, "road_cycle_finish", {
        "cycle": cycle,
        "sold": sold,
        "coinsReceived": coins,
        "boughtCookingGauntlets": bought,
        "player": compact_player(player),
    })
    return player


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-road-to-99-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    args._run_path = run_path
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    cycles = 0
    try:
        clear_runner_stop_requests(args)
        run_catherby_control(args, ["--clear-stop", "--quiet"], check=False)
        stop_existing_catherby_runner(args, handle)
        player = bridge.observe_xs(args.profile)
        write_event(handle, "run_start", {"args": args_summary(args), "player": compact_player(player), "runLog": str(run_path)})
        write_runner_status(args, "running", "started", run_path=run_path, cycle=cycles, player=player)
        if not owns_cooking_gauntlets(player) and sale_plan(player, args):
            write_runner_status(args, "running", "pre_cycle_policy", run_path=run_path, cycle=cycles, player=player)
            player, sold, coins = sell_policy_batches(args, handle, player)
            player, bought = buy_cooking_gauntlets_if_ready(args, handle, player)
            write_event(handle, "pre_cycle_policy_finish", {
                "sold": sold,
                "coinsReceived": coins,
                "boughtCookingGauntlets": bought,
                "player": compact_player(player),
            })
        while args.cycles <= 0 or cycles < args.cycles:
            if runner_stop_requested(args):
                write_runner_status(args, "stopped", "stop_requested", run_path=run_path, cycle=cycles, player=player)
                break
            player = bridge.observe_xs(args.profile)
            if targets_met(player, args):
                write_runner_status(args, "complete", "target_levels", run_path=run_path, cycle=cycles, player=player)
                break
            cycles += 1
            player = road_cycle(args, handle, cycles)
            write_runner_status(args, "running", "cycle_complete", run_path=run_path, cycle=cycles, player=player)
        else:
            write_runner_status(args, "complete", "max_cycles", run_path=run_path, cycle=cycles, player=player)
        write_event(handle, "run_finish", {"cycles": cycles, "player": compact_player(player), "runLog": str(run_path)})
        if not args.quiet:
            print(json.dumps({"ok": True, "cycles": cycles, "runLog": str(run_path), "player": compact_player(player)}, sort_keys=True))
        return 0
    except Exception as exc:
        try:
            player = bridge.observe_xs(args.profile)
        except Exception:
            player = None
        write_event(handle, "run_error", {"error": str(exc), "player": compact_player(player) if player else None})
        write_runner_status(args, "error", exc.__class__.__name__, run_path=run_path, cycle=cycles,
                            player=player, extra={"error": str(exc)})
        raise
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    argv_list = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Road to 99 Fishing/Cooking wrapper around the Catherby food runner.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--cycles", type=int, default=0,
                        help="Number of wrapper cycles to run; 0 or negative runs forever.")
    parser.add_argument("--target-fishing-level", type=int, default=99)
    parser.add_argument("--target-cooking-level", type=int, default=99)
    parser.add_argument("--gauntlet-coin-target", type=int, default=GAUNTLET_COST)
    parser.add_argument("--keep-cooked-lobsters", type=int, default=SELL_UNTIL_GAUNTLETS_KEEP_LOBSTERS)
    parser.add_argument("--max-sale-batches", type=int, default=40)
    parser.add_argument("--shop-max-distance", type=int, default=14)
    parser.add_argument("--npc-max-distance", type=int, default=12)
    parser.add_argument("--route-max-batches", type=int, default=90)
    parser.add_argument("--max-batch-distance", type=int, default=48)
    parser.add_argument("--stop-existing-timeout", type=int, default=900)
    parser.add_argument("--stop-poll-seconds", type=float, default=10.0)
    parser.add_argument("--run-mode", choices=["auto", "always", "never", "preserve"], default="preserve")
    parser.add_argument("--eat-at", type=int, default=0)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--request-stop", action="store_true")
    parser.add_argument("--clear-stop", action="store_true")
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv_list)
    args.profile = resolve_profile(args.profile, default="")
    if not args.profile:
        parser.error("--profile or RS_PROFILE is required")
    if args.status:
        return print_runner_status(args)
    if args.request_stop:
        return request_runner_stop(args)
    if args.clear_stop:
        print(json.dumps({
            "ok": True,
            "runner": RUNNER_CONTROL_NAME,
            "profile": runner_profile_label(args),
            "clearedStopRequests": clear_runner_stop_requests(args),
        }, sort_keys=True))
        return 0
    log_usage("road_to_99_fishing_cooking", surface="full", argv=argv_list)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
