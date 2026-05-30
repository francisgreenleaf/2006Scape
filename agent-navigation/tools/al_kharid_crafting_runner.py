#!/usr/bin/env python3
"""Primitive-backed Al Kharid leather crafting runner."""

import argparse
import datetime as dt
import time
import uuid

import bridge_script as bridge


RUNS_DIR = bridge.ROOT / "data" / "crafting" / "runs"

COINS = 995
COWHIDE = 1739
NEEDLE = 1733
THREAD = 1734
SOFT_LEATHER = 1741
HARD_LEATHER = 1743
LEATHER_GLOVES = 1059
LEATHER_BOOTS = 1061
LEATHER_COWL = 1167
LEATHER_VAMBRACES = 1063
LEATHER_BODY = 1129
LEATHER_CHAPS = 1095
HARDLEATHER_BODY = 1131
COIF = 1169

TANNER_NPC_IDS = (804, 2824)
DOMMIK_NPC_ID = 545
AL_KHARID_BANK_TILE = {"x": 3269, "y": 3167, "height": 0}
TANNER_TILE = {"x": 3273, "y": 3191, "height": 0}
DOMMIK_TILE = {"x": 3319, "y": 3193, "height": 0}
DOMMIK_TARGET = "3319,3193,0"
GENERAL_STORE_TARGET = "al kharid general store"
WITHDRAW_NOTE_BUTTON = 21010
WITHDRAW_ITEM_BUTTON = 21011

SOFT_TAN_BUTTON = 57201
HARD_TAN_BUTTON = 57202

SELLABLE_PRODUCTS = (
    LEATHER_GLOVES,
    LEATHER_BOOTS,
    LEATHER_COWL,
    LEATHER_VAMBRACES,
    LEATHER_BODY,
    LEATHER_CHAPS,
    HARDLEATHER_BODY,
    COIF,
)

RECIPES = (
    {
        "name": "leather gloves",
        "level": 1,
        "leatherId": SOFT_LEATHER,
        "productId": 1059,
        "buttonId": 33188,
        "tanningButtonId": SOFT_TAN_BUTTON,
    },
    {
        "name": "leather boots",
        "level": 7,
        "leatherId": SOFT_LEATHER,
        "productId": 1061,
        "buttonId": 33191,
        "tanningButtonId": SOFT_TAN_BUTTON,
    },
    {
        "name": "leather cowl",
        "level": 9,
        "leatherId": SOFT_LEATHER,
        "productId": 1167,
        "buttonId": 33203,
        "tanningButtonId": SOFT_TAN_BUTTON,
    },
    {
        "name": "leather vambraces",
        "level": 11,
        "leatherId": SOFT_LEATHER,
        "productId": 1063,
        "buttonId": 33194,
        "tanningButtonId": SOFT_TAN_BUTTON,
    },
    {
        "name": "leather body",
        "level": 14,
        "leatherId": SOFT_LEATHER,
        "productId": 1129,
        "buttonId": 33185,
        "tanningButtonId": SOFT_TAN_BUTTON,
    },
    {
        "name": "leather chaps",
        "level": 18,
        "leatherId": SOFT_LEATHER,
        "productId": 1095,
        "buttonId": 33197,
        "tanningButtonId": SOFT_TAN_BUTTON,
    },
    {
        "name": "hardleather body",
        "level": 28,
        "leatherId": HARD_LEATHER,
        "productId": 1131,
        "buttonId": 6212,
        "tanningButtonId": HARD_TAN_BUTTON,
    },
    {
        "name": "coif",
        "level": 38,
        "leatherId": SOFT_LEATHER,
        "productId": 1169,
        "buttonId": 33200,
        "tanningButtonId": SOFT_TAN_BUTTON,
    },
)


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def is_tick_timeout_error(exc):
    return "Timed out waiting for the next game tick" in str(exc)


def observe_retry(profile, handle=None, reason="observe", attempts=3, sleep_seconds=1.2):
    last_error = None
    for attempt in range(1, int(attempts) + 1):
        try:
            return bridge.observe(profile)
        except RuntimeError as exc:
            last_error = exc
            if not is_tick_timeout_error(exc) or attempt >= int(attempts):
                raise
            bridge.write_event(handle, "observe_retry", {
                "reason": reason,
                "attempt": attempt,
                "error": str(exc)[:240],
            })
            time.sleep(float(sleep_seconds))
    raise last_error


def route_with_retry(target, profile, handle, reason, extra_args=None, attempts=2, sleep_seconds=1.2):
    last_error = None
    for attempt in range(1, int(attempts) + 1):
        try:
            bridge.route_to(
                str(target),
                profile=profile,
                handle=handle,
                reason=reason if attempt == 1 else "{}_retry".format(reason),
                extra_args=extra_args,
            )
            return True
        except RuntimeError as exc:
            last_error = exc
            if not is_tick_timeout_error(exc) or attempt >= int(attempts):
                raise
            bridge.write_event(handle, "route_retry", {
                "reason": reason,
                "target": str(target),
                "attempt": attempt,
                "error": str(exc)[:240],
            })
            time.sleep(float(sleep_seconds))
            observe_retry(profile, handle, "{}_retry_observe".format(reason))
    raise last_error


def choose_recipe(level):
    chosen = RECIPES[0]
    for recipe in RECIPES:
        if int(level) >= int(recipe["level"]):
            chosen = recipe
    return chosen


def choose_recipe_for_leather(level, leather_id):
    chosen = None
    for recipe in RECIPES:
        if int(recipe["leatherId"]) != int(leather_id):
            continue
        if int(level) >= int(recipe["level"]):
            chosen = recipe
    return chosen


def choose_carried_recipe(player):
    level = bridge.skill_level(player, "crafting")
    if carried_count(player, HARD_LEATHER) > 0:
        recipe = choose_recipe_for_leather(level, HARD_LEATHER)
        if recipe is None:
            raise RuntimeError("hard leather is carried but no hard-leather recipe is unlocked yet")
        return recipe
    if carried_count(player, SOFT_LEATHER) > 0:
        recipe = choose_recipe_for_leather(level, SOFT_LEATHER)
        if recipe is None:
            raise RuntimeError("soft leather is carried but no soft-leather recipe is unlocked yet")
        return recipe
    return choose_recipe(level)


def carried_count(player, item_id):
    return bridge.count_inventory_item(player, item_id)


def bank_count(player, item_id):
    return bridge.count_bank_item(player, item_id)


def equipment_count(player, item_id):
    total = 0
    for item in bridge.equipment(player):
        if int(item.get("id", item.get("itemId", -1)) or -1) == int(item_id):
            total += int(item.get("amount", 0) or 0)
    return total


def total_count(player, item_id):
    return carried_count(player, item_id) + bank_count(player, item_id) + equipment_count(player, item_id)


def noted_item_id(item_id):
    return int(item_id) + 1


def carried_sellable_count(player, item_id):
    return carried_count(player, item_id) + carried_count(player, noted_item_id(item_id))


def total_sellable_count(player, item_id):
    note_id = noted_item_id(item_id)
    return total_count(player, item_id) + total_count(player, note_id)


def close_interfaces(profile):
    bridge.call_tool("close_interfaces", {}, profile=profile)


def open_bank_interface(player, profile, handle, reason):
    if not bool(player.get("inBankArea", False)):
        raise RuntimeError("bank target is required to open a bank interface")
    result = bridge.call_tool("deposit_inventory_items", {
        "name": "__codex_open_bank_only__",
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "open_bank_interface", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return observe_retry(profile, handle, "{}_after_open_bank".format(reason))


def set_withdraw_mode(player, take_notes, profile, handle, reason):
    player = open_bank_interface(player, profile, handle, reason)
    button_id = WITHDRAW_NOTE_BUTTON if take_notes else WITHDRAW_ITEM_BUTTON
    result = bridge.call_tool("click_interface_button", {
        "buttonId": int(button_id),
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "set_withdraw_mode", {
        "reason": reason,
        "takeNotes": bool(take_notes),
        "buttonId": int(button_id),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return observe_retry(profile, handle, "{}_after_set_withdraw_mode".format(reason))


def walk_exact(player, destination, profile, handle, reason, max_ticks=40):
    result = bridge.call_tool("walk_to_tile_until_arrived", {
        "x": int(destination["x"]),
        "y": int(destination["y"]),
        "height": int(destination.get("height", 0) or 0),
        "stopDistance": 0,
        "maxTicks": int(max_ticks),
        "maxWalkDistance": 96,
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "walk_exact", {
        "reason": reason,
        "destination": destination,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "batchStatus": result.get("batchStatus"),
        "batchTicks": result.get("batchTicks"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return updated


def ensure_bank_area(player, profile, handle, args, reason):
    if bool(player.get("inBankArea", False)):
        return observe_retry(profile, handle, "{}_already_bank".format(reason))
    route_with_retry(args.bank_target, profile, handle, reason)
    return observe_retry(profile, handle, "{}_after_route".format(reason))


def near_tile(player, tile, radius):
    current = bridge.tile_from_player(player)
    return (
        int(current.get("height", 0)) == int(tile.get("height", 0))
        and max(abs(int(current.get("x", 0)) - int(tile["x"])), abs(int(current.get("y", 0)) - int(tile["y"]))) <= int(radius)
    )


def deposit_all_except(player, keep_ids, profile, handle, reason):
    keep = {int(item_id) for item_id in keep_ids}
    deposit_ids = []
    seen = set()
    for item in bridge.inventory(player):
        item_id = int(item.get("id", item.get("itemId", -1)) or -1)
        if item_id < 0 or item_id in keep or item_id in seen:
            continue
        seen.add(item_id)
        deposit_ids.append(item_id)
    if not deposit_ids:
        return player
    result = bridge.call_tool("deposit_inventory_items", {"itemIds": deposit_ids}, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "deposit_inventory_subset", {
        "reason": reason,
        "itemIds": deposit_ids,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return observe_retry(profile, handle, "{}_after_deposit".format(reason))


def route_to_target(target, player, profile, handle, reason, args):
    close_interfaces(profile)
    player = observe_retry(profile, handle, "{}_after_close".format(reason))
    player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason=reason)
    route_with_retry(
        str(target),
        profile,
        handle,
        reason,
        extra_args={"runner_max_batches": args.route_max_batches, "max_batch_distance": args.max_batch_distance},
    )
    return observe_retry(profile, handle, "{}_after_route".format(reason))


def withdraw_if_needed(player, item_id, amount, profile, handle, reason):
    carried = carried_count(player, item_id)
    needed = max(0, int(amount) - carried)
    if needed <= 0:
        return player
    result = bridge.call_tool("withdraw_bank_items", {
        "itemId": int(item_id),
        "amount": int(needed),
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "withdraw_if_needed", {
        "reason": reason,
        "itemId": int(item_id),
        "requested": int(needed),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return observe_retry(profile, handle, "{}_after_withdraw".format(reason))


def ensure_supplies(player, profile, handle, args):
    player = ensure_bank_area(player, profile, handle, args, "ensure_supplies_bank")
    player = deposit_all_except(player, keep_ids=(), profile=profile, handle=handle, reason="supply_cleanup")
    player = ensure_bank_area(player, profile, handle, args, "ensure_supplies_reconfirm_bank")
    player = withdraw_if_needed(player, COINS, args.coin_float, profile, handle, "coin_float")

    if carried_count(player, NEEDLE) > 0 or bank_count(player, NEEDLE) > 0:
        if carried_count(player, NEEDLE) == 0:
            player = withdraw_if_needed(player, NEEDLE, 1, profile, handle, "needle_from_bank")
    if carried_count(player, THREAD) >= args.thread_floor or bank_count(player, THREAD) >= args.thread_floor:
        if carried_count(player, THREAD) < args.thread_floor:
            player = withdraw_if_needed(player, THREAD, args.thread_floor, profile, handle, "thread_from_bank")
    if carried_count(player, NEEDLE) > 0 and carried_count(player, THREAD) >= args.thread_floor:
        return player

    if not near_tile(player, DOMMIK_TILE, 8):
        player = route_to_target(DOMMIK_TARGET, player, profile, handle, "route_dommik_supplies", args)
    if not near_tile(player, DOMMIK_TILE, 3):
        player = walk_exact(player, DOMMIK_TILE, profile, handle, "walk_dommik", max_ticks=25)
    open_result = bridge.call_tool("open_nearest_shop", {
        "name": "dommik",
        "maxDistance": 8,
    }, profile=profile)
    player = bridge._player_from_or(open_result, player)
    bridge.write_event(handle, "open_dommik_shop", {
        "success": bool(open_result.get("success")),
        "message": open_result.get("message"),
        "player": bridge.compact_player(player, ("crafting",)),
    })
    if not open_result.get("success"):
        raise RuntimeError(open_result.get("message", "could not open Dommik's crafting shop"))

    if carried_count(player, NEEDLE) <= 0 and bank_count(player, NEEDLE) <= 0:
        bought = bridge.call_tool("buy_shop_item", {"itemId": NEEDLE, "amount": 1}, profile=profile)
        player = bridge._player_from_or(bought, player)
        bridge.write_event(handle, "buy_needle", {
            "success": bool(bought.get("success")),
            "message": bought.get("message"),
            "player": bridge.compact_player(player, ("crafting",)),
        })
    total_thread = carried_count(player, THREAD) + bank_count(player, THREAD)
    if total_thread < args.thread_floor:
        buy_amount = max(args.thread_topup, args.thread_floor - total_thread)
        bought = bridge.call_tool("buy_shop_item", {"itemId": THREAD, "amount": int(buy_amount)}, profile=profile)
        player = bridge._player_from_or(bought, player)
        bridge.write_event(handle, "buy_thread", {
            "amount": int(buy_amount),
            "success": bool(bought.get("success")),
            "message": bought.get("message"),
            "player": bridge.compact_player(player, ("crafting",)),
        })
    close_interfaces(profile)
    player = ensure_bank_area(player, profile, handle, args, "return_bank_after_shop")
    player = observe_retry(profile, handle, "return_bank_after_shop")
    if carried_count(player, NEEDLE) == 0:
        player = withdraw_if_needed(player, NEEDLE, 1, profile, handle, "needle_after_shop")
    if carried_count(player, THREAD) < args.thread_floor:
        player = withdraw_if_needed(player, THREAD, args.thread_floor, profile, handle, "thread_after_shop")
    if carried_count(player, NEEDLE) <= 0 or carried_count(player, THREAD) <= 0:
        raise RuntimeError("could not secure leather crafting supplies from bank/shop")
    return player


def withdraw_trip_materials(player, profile, handle, args):
    player = ensure_bank_area(player, profile, handle, args, "withdraw_trip_materials_bank")
    recipe = choose_recipe(bridge.skill_level(player, "crafting"))
    keep_ids = (COINS, NEEDLE, THREAD)
    player = deposit_all_except(player, keep_ids=keep_ids, profile=profile, handle=handle, reason="trip_cleanup")
    player = ensure_bank_area(player, profile, handle, args, "withdraw_trip_materials_reconfirm_bank")
    player = withdraw_if_needed(player, COINS, args.coin_float, profile, handle, "trip_coin_float")
    player = withdraw_if_needed(player, NEEDLE, 1, profile, handle, "trip_needle")
    if bank_count(player, THREAD) + carried_count(player, THREAD) < int(args.thread_floor):
        player = ensure_supplies(player, profile, handle, args)
        player = ensure_bank_area(player, profile, handle, args, "withdraw_trip_materials_after_thread_shop")
    player = withdraw_if_needed(player, THREAD, args.thread_floor, profile, handle, "trip_thread")
    if bank_count(player, COWHIDE) <= 0 and carried_count(player, COWHIDE) <= 0:
        raise RuntimeError("no cowhides remain in bank for crafting")
    carried_now = carried_count(player, COWHIDE)
    needed_hides = max(0, int(args.trip_hides) - carried_now)
    if needed_hides > 0:
        result = bridge.call_tool("withdraw_bank_items", {
            "itemId": COWHIDE,
            "amount": int(needed_hides),
        }, profile=profile)
        player = bridge._player_from_or(result, player)
        bridge.write_event(handle, "withdraw_cowhides", {
            "requested": int(needed_hides),
            "recipe": recipe["name"],
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": bridge.compact_player(player, ("crafting",)),
        })
        player = observe_retry(profile, handle, "withdraw_cowhides")
    if carried_count(player, COWHIDE) <= 0:
        raise RuntimeError("failed to withdraw cowhides for trip")
    return player


def tan_hides(player, profile, handle, args):
    recipe = choose_recipe(bridge.skill_level(player, "crafting"))
    button_id = int(recipe["tanningButtonId"])
    before_hide_count = carried_count(player, COWHIDE)
    if before_hide_count <= 0:
        return player
    player = walk_exact(player, TANNER_TILE, profile, handle, "walk_tanner", max_ticks=50)
    found = bridge.call_tool("find_nearest_npc", {
        "npcIds": list(TANNER_NPC_IDS),
        "maxDistance": 8,
        "reachable": True,
    }, profile=profile)
    if not found.get("success"):
        raise RuntimeError(found.get("message", "could not find tanner"))
    npc = found.get("npc") or {}
    interact = bridge.call_tool("interact_npc", {
        "npcIndex": npc.get("npcIndex", npc.get("index")),
        "option": "first",
        "requireReachable": True,
    }, profile=profile)
    player = bridge._player_from_or(interact, player)
    button = bridge.call_tool("click_interface_button", {"buttonId": button_id}, profile=profile)
    player = bridge._player_from_or(button, player)
    bridge.call_tool("wait_ticks", {"ticks": 2}, profile=profile)
    updated = observe_retry(profile, handle, "tan_hides")
    bridge.write_event(handle, "tan_hides", {
        "recipe": recipe["name"],
        "npc": npc,
        "beforeCowhides": before_hide_count,
        "afterCowhides": carried_count(updated, COWHIDE),
        "afterLeather": carried_count(updated, recipe["leatherId"]),
        "interactSuccess": bool(interact.get("success")),
        "buttonSuccess": bool(button.get("success")),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    if carried_count(updated, recipe["leatherId"]) <= 0:
        raise RuntimeError("tanning made no leather progress for {}".format(recipe["name"]))
    return updated


def craft_batch(player, profile, handle, args):
    recipe = choose_carried_recipe(player)
    leather_id = int(recipe["leatherId"])
    if carried_count(player, leather_id) <= 0:
        return player, False
    if carried_count(player, NEEDLE) <= 0:
        raise RuntimeError("needle is required to craft leather goods")
    if carried_count(player, THREAD) <= 0:
        raise RuntimeError("thread is required to craft leather goods")

    before_leather = carried_count(player, leather_id)
    before_thread = carried_count(player, THREAD)
    before_xp = bridge.skill_xp(player, "crafting")
    try:
        use_result = bridge.call_tool("use_item_on_item", {
            "itemId": NEEDLE,
            "targetItemId": leather_id,
        }, profile=profile)
    except RuntimeError as exc:
        if "No matching target inventory item found." not in str(exc):
            raise
        refreshed = observe_retry(profile, handle, "craft_batch_missing_target_refresh")
        after_refresh_leather = carried_count(refreshed, leather_id)
        bridge.write_event(handle, "craft_batch_missing_target_refresh", {
            "recipe": recipe["name"],
            "beforeLeather": before_leather,
            "afterRefreshLeather": after_refresh_leather,
            "beforeThread": before_thread,
            "afterRefreshThread": carried_count(refreshed, THREAD),
            "beforeXp": before_xp,
            "afterRefreshXp": bridge.skill_xp(refreshed, "crafting"),
            "player": bridge.compact_player(refreshed, ("crafting",)),
        })
        if after_refresh_leather <= 0:
            return refreshed, True
        raise
    bridge.call_tool("wait_ticks", {"ticks": 1}, profile=profile)
    button = bridge.call_tool("click_interface_button", {"buttonId": int(recipe["buttonId"])}, profile=profile)
    wait = bridge.call_tool("wait_until_idle", {
        "maxTicks": int(args.craft_wait_ticks),
        "movement": True,
        "skilling": True,
        "combat": False,
    }, profile=profile)
    updated = bridge.player_from(wait)
    after_leather = carried_count(updated, leather_id)
    after_thread = carried_count(updated, THREAD)
    after_xp = bridge.skill_xp(updated, "crafting")
    made_progress = after_leather < before_leather or after_thread < before_thread or after_xp > before_xp
    bridge.write_event(handle, "craft_batch", {
        "recipe": recipe["name"],
        "buttonId": int(recipe["buttonId"]),
        "useSuccess": bool(use_result.get("success")),
        "buttonSuccess": bool(button.get("success")),
        "waitStatus": wait.get("batchStatus"),
        "beforeLeather": before_leather,
        "afterLeather": after_leather,
        "beforeThread": before_thread,
        "afterThread": after_thread,
        "beforeXp": before_xp,
        "afterXp": after_xp,
        "madeProgress": made_progress,
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return updated, made_progress


def craft_inventory(player, profile, handle, args):
    no_progress_rounds = 0
    while True:
        recipe = choose_carried_recipe(player)
        leather_id = int(recipe["leatherId"])
        if carried_count(player, leather_id) <= 0:
            return player
        player, made_progress = craft_batch(player, profile, handle, args)
        if made_progress:
            no_progress_rounds = 0
        else:
            no_progress_rounds += 1
            close_interfaces(profile)
            bridge.call_tool("wait_ticks", {"ticks": 1}, profile=profile)
            player = observe_retry(profile, handle, "craft_retry_refresh")
            bridge.write_event(handle, "craft_retry_refresh", {
                "recipe": recipe["name"],
                "noProgressRounds": no_progress_rounds,
                "player": bridge.compact_player(player, ("crafting",)),
            })
        if no_progress_rounds >= args.max_no_progress_rounds:
            raise RuntimeError("crafting made no inventory or XP progress for {} rounds".format(no_progress_rounds))


def travel_to_al_kharid(player, profile, handle, args):
    player = ensure_bank_area(player, profile, handle, args, "travel_start_bank")
    player = deposit_all_except(player, keep_ids=(), profile=profile, handle=handle, reason="travel_cleanup")
    player = withdraw_if_needed(player, COINS, args.coin_float, profile, handle, "travel_coin_float")
    route_with_retry(args.bank_target, profile, handle, "travel_to_al_kharid_bank")
    return observe_retry(profile, handle, "travel_to_al_kharid_bank")


def unequip_sellable_products(player, profile, handle):
    equipped = [item_id for item_id in SELLABLE_PRODUCTS if equipment_count(player, item_id) > 0]
    if not equipped:
        return player
    result = bridge.call_tool("unequip_items_XS", {"itemIds": equipped}, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "unequip_sellable_products", {
        "itemIds": equipped,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return observe_retry(profile, handle, "unequip_sellable_products")


def open_general_store(player, profile, handle, args):
    player = route_to_target(GENERAL_STORE_TARGET, player, profile, handle, "route_general_store", args)
    result = bridge.call_tool("open_nearest_shop", {
        "name": "general",
        "maxDistance": int(args.shop_max_distance),
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "open_general_store", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    if not result.get("success"):
        raise RuntimeError(result.get("message", "could not open Al Kharid general store"))
    return observe_retry(profile, handle, "open_general_store")


def open_dommik_shop(player, profile, handle, args):
    player = route_to_target(DOMMIK_TARGET, player, profile, handle, "route_dommik_sale_shop", args)
    result = bridge.call_tool("open_nearest_shop", {
        "name": "dommik",
        "maxDistance": int(args.shop_max_distance),
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "open_dommik_sale_shop", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    if not result.get("success"):
        raise RuntimeError(result.get("message", "could not open Dommik's crafting shop"))
    return observe_retry(profile, handle, "open_dommik_sale_shop")


def sell_loaded_item(player, item_id, amount, profile, handle):
    if amount <= 0:
        return player, 0
    before_coins = carried_count(player, COINS)
    try:
        result = bridge.call_tool("sell_inventory_items", {
            "itemIds": [int(item_id), noted_item_id(item_id)],
            "amount": int(amount),
        }, profile=profile)
    except RuntimeError as exc:
        if "No matching inventory items were sold." not in str(exc):
            raise
        refreshed = observe_retry(profile, handle, "sell_loaded_item_refresh")
        bridge.write_event(handle, "sell_loaded_item_refresh", {
            "itemId": int(item_id),
            "requested": int(amount),
            "message": str(exc),
            "player": bridge.compact_player(refreshed, ("crafting",)),
        })
        return refreshed, 0
    updated = bridge._player_from_or(result, player)
    sold = int(result.get("sold", 0) or 0)
    coins_received = int(result.get("coinsReceived", 0) or 0)
    if coins_received <= 0:
        coins_received = max(0, carried_count(updated, COINS) - before_coins)
    bridge.write_event(handle, "sell_loaded_item", {
        "itemId": int(item_id),
        "requested": int(amount),
        "sold": sold,
        "coinsReceived": coins_received,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return observe_retry(profile, handle, "sell_loaded_item"), sold


def try_sell_loaded_item(player, item_id, amount, profile, handle, opener, shop_label, args):
    player = opener(player, profile, handle, args)
    player, sold = sell_loaded_item(player, item_id, amount, profile, handle)
    bridge.write_event(handle, "sell_shop_attempt", {
        "shop": shop_label,
        "itemId": int(item_id),
        "requested": int(amount),
        "sold": int(sold),
        "player": bridge.compact_player(player, ("crafting",)),
    })
    close_interfaces(profile)
    player = observe_retry(profile, handle, "sell_shop_attempt_close")
    return player, sold


def withdraw_sell_batch(player, item_id, amount, profile, handle):
    if amount <= 0:
        return player, 0
    player = set_withdraw_mode(player, True, profile, handle, "withdraw_sell_batch_note_mode")
    note_id = noted_item_id(item_id)
    before_note = carried_count(player, note_id)
    before_normal = carried_count(player, item_id)
    result = None
    error_message = ""
    try:
        result = bridge.call_tool("withdraw_bank_items", {
            "itemId": int(item_id),
            "amount": int(amount),
        }, profile=profile)
        updated = bridge._player_from_or(result, player)
    except RuntimeError as exc:
        error_message = str(exc)
        updated = observe_retry(profile, handle, "withdraw_sell_batch_refresh")
    withdrawn_note = max(0, carried_count(updated, note_id) - before_note)
    withdrawn_normal = max(0, carried_count(updated, item_id) - before_normal)
    withdrawn = withdrawn_note + withdrawn_normal
    if result is None and withdrawn <= 0:
        raise RuntimeError(error_message or "failed to withdraw sell batch")
    bridge.write_event(handle, "withdraw_sell_batch", {
        "itemId": int(item_id),
        "noteId": int(note_id),
        "requested": int(amount),
        "withdrawn": withdrawn,
        "withdrawnNote": withdrawn_note,
        "withdrawnNormal": withdrawn_normal,
        "success": bool(result.get("success")) if isinstance(result, dict) else False,
        "message": result.get("message") if isinstance(result, dict) else error_message,
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return observe_retry(profile, handle, "withdraw_sell_batch"), withdrawn


def remaining_material_count(player):
    return (
        bank_count(player, COWHIDE)
        + carried_count(player, COWHIDE)
        + bank_count(player, SOFT_LEATHER)
        + carried_count(player, SOFT_LEATHER)
        + bank_count(player, HARD_LEATHER)
        + carried_count(player, HARD_LEATHER)
    )


def withdraw_leather_batch(player, leather_id, amount, profile, handle, recipe_name):
    result = bridge.call_tool("withdraw_bank_items", {
        "itemId": int(leather_id),
        "amount": int(amount),
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "withdraw_bank_leather", {
        "itemId": int(leather_id),
        "requested": int(amount),
        "recipe": recipe_name,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("crafting",)),
    })
    return observe_retry(profile, handle, "withdraw_bank_leather")


def consume_banked_leather(player, profile, handle, args):
    while True:
        player = ensure_bank_area(player, profile, handle, args, "banked_leather_bank")
        if bank_count(player, HARD_LEATHER) <= 0 and bank_count(player, SOFT_LEATHER) <= 0:
            return player
        player = deposit_all_except(player, keep_ids=(COINS, NEEDLE, THREAD), profile=profile, handle=handle, reason="banked_leather_cleanup")
        player = withdraw_if_needed(player, NEEDLE, 1, profile, handle, "banked_leather_needle")
        if bank_count(player, THREAD) + carried_count(player, THREAD) < int(args.thread_floor):
            player = ensure_supplies(player, profile, handle, args)
            player = ensure_bank_area(player, profile, handle, args, "banked_leather_after_thread_shop")
        player = withdraw_if_needed(player, THREAD, args.thread_floor, profile, handle, "banked_leather_thread")

        level = bridge.skill_level(player, "crafting")
        leather_id = 0
        recipe = None
        if bank_count(player, HARD_LEATHER) > 0:
            recipe = choose_recipe_for_leather(level, HARD_LEATHER)
            if recipe is not None:
                leather_id = HARD_LEATHER
        if leather_id == 0 and bank_count(player, SOFT_LEATHER) > 0:
            recipe = choose_recipe_for_leather(level, SOFT_LEATHER)
            if recipe is not None:
                leather_id = SOFT_LEATHER
        if leather_id == 0 or recipe is None:
            raise RuntimeError("leather remains banked but no unlocked recipe can consume it")

        free_slots = int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0)
        batch = min(int(args.trip_hides), int(bank_count(player, leather_id)), max(0, free_slots))
        if batch <= 0:
            raise RuntimeError("no free inventory slots available for banked leather crafting")
        player = withdraw_leather_batch(player, leather_id, batch, profile, handle, recipe["name"])
        player = craft_inventory(player, profile, handle, args)
        player = ensure_bank_area(player, profile, handle, args, "bank_after_banked_leather")
        player = deposit_all_except(player, keep_ids=(COINS, NEEDLE, THREAD), profile=profile, handle=handle, reason="bank_banked_leather_products")


def sell_crafted_products(player, profile, handle, args):
    player = ensure_bank_area(player, profile, handle, args, "bank_before_sell")
    player = unequip_sellable_products(player, profile, handle)
    player = ensure_bank_area(player, profile, handle, args, "bank_after_unequip")
    player = deposit_all_except(player, keep_ids=(), profile=profile, handle=handle, reason="pre_sell_cleanup")

    preserve_boots = max(0, int(args.preserve_boots))
    refused_shops_by_item = {}
    for item_id in SELLABLE_PRODUCTS:
        available_total = total_sellable_count(player, item_id)
        keep = preserve_boots if int(item_id) == LEATHER_BOOTS else 0
        remaining_to_sell = max(0, available_total - keep)
        if remaining_to_sell <= 0:
            continue
        refused_shops = refused_shops_by_item.setdefault(int(item_id), set())
        while remaining_to_sell > 0:
            player = ensure_bank_area(player, profile, handle, args, "bank_between_sell_trips")
            free_slots = int(player.get("freeInventorySlots", 0) or 0)
            if free_slots <= 0:
                player = deposit_all_except(player, keep_ids=(), profile=profile, handle=handle, reason="clear_for_sell_batch")
                free_slots = int(player.get("freeInventorySlots", 0) or 0)
            batch = remaining_to_sell
            if batch <= 0:
                raise RuntimeError("no free inventory slots available for selling crafted products")
            withdrawn = carried_sellable_count(player, item_id)
            if withdrawn <= 0:
                player, withdrawn = withdraw_sell_batch(player, item_id, batch, profile, handle)
            if withdrawn <= 0:
                raise RuntimeError("failed to withdraw item {} for sale".format(item_id))
            sold = 0
            if "dommik" not in refused_shops:
                player, sold = try_sell_loaded_item(player, item_id, withdrawn, profile, handle, open_dommik_shop, "dommik", args)
                if sold <= 0:
                    refused_shops.add("dommik")
            if sold <= 0 and "general" not in refused_shops:
                player, sold = try_sell_loaded_item(player, item_id, withdrawn, profile, handle, open_general_store, "general", args)
                if sold <= 0:
                    refused_shops.add("general")
            if sold <= 0:
                raise RuntimeError("failed to sell item {} at nearby leather/general shops".format(item_id))
            remaining_to_sell -= sold
    player = ensure_bank_area(player, profile, handle, args, "finish_sell_bank")
    player = deposit_all_except(player, keep_ids=(COINS,), profile=profile, handle=handle, reason="post_sell_cleanup")
    player = set_withdraw_mode(player, False, profile, handle, "post_sell_reset_withdraw_mode")
    return observe_retry(profile, handle, "sell_crafted_products_finish")


def resume_carried_trip(player, profile, handle, args):
    close_interfaces(profile)
    player = observe_retry(profile, handle, "resume_carried_trip_start")
    if carried_count(player, COWHIDE) > 0:
        player = tan_hides(player, profile, handle, args)
    if carried_count(player, SOFT_LEATHER) > 0 or carried_count(player, HARD_LEATHER) > 0:
        if carried_count(player, NEEDLE) <= 0 or carried_count(player, THREAD) <= 0:
            player = ensure_bank_area(player, profile, handle, args, "resume_leather_resupply_bank")
            player = deposit_all_except(
                player,
                keep_ids=(COINS, SOFT_LEATHER, HARD_LEATHER),
                profile=profile,
                handle=handle,
                reason="resume_leather_resupply_cleanup",
            )
            player = ensure_supplies(player, profile, handle, args)
        player = observe_retry(profile, handle, "resume_carried_leather_ready")
        player = craft_inventory(player, profile, handle, args)
    player = observe_retry(profile, handle, "resume_carried_trip_after_craft")
    if carried_count(player, COWHIDE) <= 0 and carried_count(player, SOFT_LEATHER) <= 0 and carried_count(player, HARD_LEATHER) <= 0:
        product_ids = list(SELLABLE_PRODUCTS)
        if any(carried_sellable_count(player, item_id) > 0 for item_id in product_ids):
            player = ensure_bank_area(player, profile, handle, args, "resume_bank_finished_goods")
            player = deposit_all_except(
                player,
                keep_ids=(COINS, NEEDLE, THREAD),
                profile=profile,
                handle=handle,
                reason="resume_bank_finished_goods",
            )
    return observe_retry(profile, handle, "resume_carried_trip_finish")


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = observe_retry(profile, handle, "run_start_observe")
        close_interfaces(profile)
        player = observe_retry(profile, handle, "run_start_after_close")
        player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason="al_kharid_crafting_runner")
        bridge.write_event(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("crafting",)),
        })

        if args.travel_only:
            player = travel_to_al_kharid(player, profile, handle, args)
            bridge.write_event(handle, "run_finish", {"player": bridge.compact_player(player, ("crafting",))})
            log("staged at Al Kharid bank tile={} crafting={}".format(bridge.tile_string(bridge.tile_from_player(player)), bridge.skill_level(player, "crafting")), args)
            if handle is not None:
                log("crafting log: {}".format(run_path), args)
            return 0

        player = resume_carried_trip(player, profile, handle, args)
        if not bool(player.get("inBankArea", False)):
            player = travel_to_al_kharid(player, profile, handle, args)
        player = ensure_supplies(player, profile, handle, args)

        for cycle in range(1, args.max_cycles + 1):
            if args.target_crafting_level and bridge.skill_level(player, "crafting") >= args.target_crafting_level:
                break
            if bank_count(player, COWHIDE) <= 0 and carried_count(player, COWHIDE) <= 0:
                break
            player = withdraw_trip_materials(player, profile, handle, args)
            player = tan_hides(player, profile, handle, args)
            player = craft_inventory(player, profile, handle, args)
            player = ensure_bank_area(player, profile, handle, args, "bank_after_craft")
            player = deposit_all_except(player, keep_ids=(COINS, NEEDLE, THREAD), profile=profile, handle=handle, reason="bank_finished_goods")
            player = observe_retry(profile, handle, "cycle_after_bank_finished_goods")
            recipe = choose_recipe(bridge.skill_level(player, "crafting"))
            log(
                "cycle {} crafting={} xp={} next_recipe={} bank_hides={}".format(
                    cycle,
                    bridge.skill_level(player, "crafting"),
                    bridge.skill_xp(player, "crafting"),
                    recipe["name"],
                    bank_count(player, COWHIDE),
                ),
                args,
            )
            if bank_count(player, COWHIDE) <= 0:
                break

        player = observe_retry(profile, handle, "run_finish_observe")
        if args.max_cycles > 0 and remaining_material_count(player) > 0:
            player = consume_banked_leather(player, profile, handle, args)
            player = observe_retry(profile, handle, "post_banked_leather_observe")
        if args.max_cycles > 0 and remaining_material_count(player) <= 0:
            player = sell_crafted_products(player, profile, handle, args)

        bridge.write_event(handle, "run_finish", {"player": bridge.compact_player(player, ("crafting",))})
        if handle is not None:
            log("crafting log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Al Kharid leather crafting with normal bridge primitives.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--bank-target", default="al kharid bank")
    parser.add_argument("--coin-float", type=int, default=120)
    parser.add_argument("--thread-floor", type=int, default=25)
    parser.add_argument("--thread-topup", type=int, default=100)
    parser.add_argument("--trip-hides", type=int, default=25)
    parser.add_argument("--target-crafting-level", type=int, default=0)
    parser.add_argument("--max-cycles", type=int, default=9999)
    parser.add_argument("--craft-wait-ticks", type=int, default=220)
    parser.add_argument("--max-no-progress-rounds", type=int, default=4)
    parser.add_argument("--min-run-energy", type=int, default=1)
    parser.add_argument("--route-max-batches", type=int, default=90)
    parser.add_argument("--max-batch-distance", type=int, default=48)
    parser.add_argument("--shop-max-distance", type=int, default=10)
    parser.add_argument("--preserve-boots", type=int, default=1)
    parser.add_argument("--travel-only", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
