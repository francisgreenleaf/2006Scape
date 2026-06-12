#!/usr/bin/env python3
"""Make cannonballs from banked steel bars at Al Kharid."""

import argparse
import json
import time

import bridge_script as bridge
import smithing_goal_common as common
from profile_utils import resolve_profile


STATUS_NAME = "al-kharid-cannonball-smelter-status"
AMMO_MOULD = 4
CANNONBALL = 2
FURNACE_IDS = [14921, 9390, 2781, 2785, 2966, 3294, 3413, 4304, 4305, 6189, 6190, 11009, 11010, 11666, 12100, 12809]
AL_KHARID_FURNACE_SMELT_TILE = {"x": 3274, "y": 3179, "height": 0}
AL_KHARID_FURNACE_OBJECT = {
    "objectId": 2785,
    "tile": "3273,3184,0",
    "name": "Furnace",
}


def parse_tile(value):
    if isinstance(value, dict):
        return {
            "x": int(value.get("x", 0) or 0),
            "y": int(value.get("y", 0) or 0),
            "height": int(value.get("height", value.get("h", 0)) or 0),
        }
    parts = str(value or "").split(",")
    if len(parts) >= 2:
        return {
            "x": int(parts[0]),
            "y": int(parts[1]),
            "height": int(parts[2]) if len(parts) >= 3 else 0,
        }
    return None


def log_timing(handle, phase, call, start, success=True, player=None, **extra):
    data = {
        "phase": phase,
        "call": call,
        "durationMs": int(round((time.monotonic() - start) * 1000)),
        "success": bool(success),
    }
    if player is not None:
        data["player"] = common.compact(player)
    data.update(extra)
    common.write_event(handle, "cannonball_timing", data)


def timed_observe_xs(profile, handle, phase):
    start = time.monotonic()
    player = bridge.observe_xs(profile=profile)
    log_timing(handle, phase, "observe_xs", start, True, player=player)
    return player


def timed_call_tool(profile, handle, phase, tool, args):
    start = time.monotonic()
    result = bridge.call_tool(tool, args, profile=profile)
    log_timing(
        handle,
        phase,
        tool,
        start,
        bool(result.get("success")),
        player=bridge._player_from_or(result, None),
        message=result.get("message"),
        batchStatus=result.get("batchStatus"),
        batchTicks=result.get("batchTicks"),
        startedCannonballMaking=result.get("startedCannonballMaking"),
        itemCountBefore=result.get("itemCountBefore"),
        itemCountAfter=result.get("itemCountAfter"),
    )
    return result


def timed_count_items(profile, item_ids, handle, phase):
    start = time.monotonic()
    counts, player = common.count_items(profile, item_ids)
    log_timing(
        handle,
        phase,
        "bank_item_count_XS",
        start,
        True,
        player=player,
        itemIds=[int(item_id) for item_id in item_ids],
    )
    return counts, player


def timed_deposit_all_except(player, profile, keep_ids=(), handle=None, reason="deposit_all_except"):
    item_ids = common.inventory_item_ids(player, keep_ids=keep_ids)
    if not item_ids:
        return player
    result = timed_call_tool(
        profile,
        handle,
        reason,
        "deposit_inventory_items_XS",
        {"itemIds": item_ids},
    )
    updated = bridge._player_from_or(result, player)
    common.write_event(handle, "deposit_all_except", {
        "reason": reason,
        "itemIds": item_ids,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": common.compact(updated),
    })
    return updated


def timed_withdraw_item(player, profile, item_id, amount, handle=None, reason="withdraw"):
    if int(amount) <= 0:
        return player
    result = timed_call_tool(
        profile,
        handle,
        reason,
        "withdraw_bank_items_XS",
        {"itemId": int(item_id), "amount": int(amount)},
    )
    updated = bridge._player_from_or(result, player)
    common.write_event(handle, "withdraw_item", {
        "reason": reason,
        "itemId": int(item_id),
        "amount": int(amount),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": common.compact(updated),
    })
    if not result.get("success"):
        raise RuntimeError("withdraw {} x{} failed: {}".format(item_id, amount, result.get("message")))
    return updated


def leg_run_policy(args, reason):
    if reason == "cannonball_furnace":
        return bool(args.run_to_furnace), int(args.min_run_energy_to_furnace)
    if reason == "al_kharid_bank":
        return bool(args.run_to_bank), int(args.min_run_energy_to_bank)
    return True, int(args.min_run_energy)


def timed_set_run(player, profile, handle, enabled, reason):
    if bool(player.get("runEnabled", False)) == bool(enabled):
        return player
    result = timed_call_tool(profile, handle, reason, "set_run_XXS", {"enabled": bool(enabled)})
    next_player = dict(player)
    next_player.update(bridge.player_from(result))
    common.write_event(handle, "set_run", {
        "reason": reason,
        "enabled": bool(enabled),
        "before": common.compact(player),
        "after": common.compact(next_player),
    })
    return next_player


def timed_ensure_run(player, profile, handle, args, reason):
    should_run, min_energy = leg_run_policy(args, reason)
    energy = int(player.get("runEnergy", 0) or 0)
    if not should_run:
        return timed_set_run(player, profile, handle, False, reason)
    if energy < int(min_energy):
        return timed_set_run(player, profile, handle, False, reason)
    return timed_set_run(player, profile, handle, True, reason)


def fast_local_walk(profile, tile, handle, args, reason, stop_distance=0, max_ticks=45, player=None):
    if player is None:
        player = timed_observe_xs(profile, handle, "{}:pre_walk_observe".format(reason))
    if common.near_tile(player, tile, max(1, int(stop_distance))):
        return player
    before = common.compact(player)
    player = timed_ensure_run(player, profile, handle, args, reason)
    after_toggle = common.compact(player)
    result = timed_call_tool(profile, handle, reason, "walk_to_tile_until_arrived_XS", {
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0) or 0),
        "stopDistance": int(stop_distance),
        "maxTicks": int(max_ticks),
        "maxWalkDistance": 48,
        "stopOnCombat": True,
        "stopOnStall": True,
    })
    updated = bridge._player_from_or(result, player)
    common.write_event(handle, "fast_local_walk", {
        "reason": reason,
        "target": tile,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "batchStatus": result.get("batchStatus"),
        "player": common.compact(updated),
    })
    common.write_event(handle, "walk_leg", {
        "reason": reason,
        "target": tile,
        "success": bool(result.get("success")),
        "batchStatus": result.get("batchStatus"),
        "batchTicks": result.get("batchTicks"),
        "before": before,
        "afterToggle": after_toggle,
        "after": common.compact(updated),
    })
    if not result.get("success"):
        raise RuntimeError("local walk to {} failed: {}".format(reason, result.get("message")))
    return updated


def find_furnace(profile, handle, args):
    result = timed_call_tool(profile, handle, "furnace:find", "find_nearest_object_XS", {
        "objectIds": FURNACE_IDS,
        "maxDistance": int(args.object_max_distance),
    })
    if not result.get("success"):
        raise RuntimeError(result.get("message", "furnace not found"))
    obj = result.get("object") or {}
    common.write_event(handle, "furnace_cached", {"object": obj})
    return obj


def furnace_tile(furnace):
    return parse_tile(furnace.get("tile"))


def furnace_interaction_tile(furnace):
    return (
        parse_tile(furnace.get("walkTarget"))
        or parse_tile(furnace.get("nearestInteractionTile"))
        or parse_tile(furnace.get("interactionWalkTarget"))
        or furnace_tile(furnace)
    )


def ensure_furnace_interaction(profile, handle, args, player, furnace):
    if not args.require_interaction_tile:
        return player
    target = furnace_interaction_tile(furnace)
    if not target:
        return player
    if common.near_tile(player, target, 0):
        return player
    player = fast_local_walk(
        profile,
        target,
        handle,
        args,
        "cannonball_furnace_interaction",
        stop_distance=0,
        max_ticks=12,
        player=player,
    )
    refreshed = find_furnace(profile, handle, args)
    furnace.clear()
    furnace.update(refreshed)
    return player


def route_to_furnace(profile, handle, args, player=None):
    if player is None:
        player = timed_observe_xs(profile, handle, "cannonball_furnace:route_observe")
    if common.near_tile(player, AL_KHARID_FURNACE_SMELT_TILE, 0):
        return player
    if args.fast_local_shuttle and common.near_tile(player, common.AL_KHARID_BANK_TILE, 48):
        return fast_local_walk(profile, AL_KHARID_FURNACE_SMELT_TILE, handle, args, "cannonball_furnace", player=player)
    return common.ml2_route_to(profile, AL_KHARID_FURNACE_SMELT_TILE, handle, "cannonball_furnace", args, arrival_radius=0)


def ensure_al_kharid_bank(profile, handle, args, player=None):
    if player is None:
        player = timed_observe_xs(profile, handle, "al_kharid_bank:ensure_observe")
    if bool(player.get("inBankArea", False)) and common.near_tile(player, common.AL_KHARID_BANK_TILE, 8):
        return player
    if args.fast_local_shuttle and common.near_tile(player, common.AL_KHARID_FURNACE_TILE, 48):
        common.close_interfaces(profile)
        player = fast_local_walk(profile, common.AL_KHARID_BANK_TILE, handle, args, "al_kharid_bank", stop_distance=1, player=player)
        if bool(player.get("inBankArea", False)):
            return player
        player = timed_observe_xs(profile, handle, "al_kharid_bank:post_walk_observe")
        if bool(player.get("inBankArea", False)):
            return player
    return common.ensure_bank_at(
        profile,
        common.AL_KHARID_BANK,
        common.AL_KHARID_BANK_TILE,
        handle,
        args,
        radius=8,
    )


def possible_batches(counts, bars_per_batch):
    return int(counts[common.STEEL_BAR]["bank"]) // max(1, int(bars_per_batch))


def apply_completed_batch_counts(counts, steel_count):
    steel_count = int(steel_count)
    counts[common.STEEL_BAR]["inventory"] = max(0, int(counts[common.STEEL_BAR]["inventory"]) - steel_count)
    counts[common.STEEL_BAR]["total"] = max(0, int(counts[common.STEEL_BAR]["total"]) - steel_count)
    counts[CANNONBALL]["inventory"] = int(counts[CANNONBALL]["inventory"]) + steel_count * 4
    counts[CANNONBALL]["total"] = int(counts[CANNONBALL]["total"]) + steel_count * 4


def apply_withdrawn_steel_counts(counts, amount):
    amount = max(0, int(amount))
    if amount <= 0:
        return
    counts[common.STEEL_BAR]["bank"] = max(0, int(counts[common.STEEL_BAR]["bank"]) - amount)
    counts[common.STEEL_BAR]["inventory"] = int(counts[common.STEEL_BAR]["inventory"]) + amount


def actual_steel_carried(player):
    return bridge.count_inventory_item(player, common.STEEL_BAR)


def apply_deposited_cannonballs(counts, deposited):
    deposited = max(0, int(deposited))
    if deposited <= 0:
        return
    counts[CANNONBALL]["inventory"] = max(0, int(counts[CANNONBALL]["inventory"]) - deposited)
    counts[CANNONBALL]["bank"] = int(counts[CANNONBALL]["bank"]) + deposited


def refresh_counts_and_player(profile, handle, phase, player=None):
    counts, _count_player = timed_count_items(profile, [common.STEEL_BAR, CANNONBALL, AMMO_MOULD], handle, "{}:count".format(phase))
    if player is None:
        player = timed_observe_xs(profile, handle, "{}:post_count_observe".format(phase))
    else:
        common.write_event(handle, "count_player_reused", {
            "phase": phase,
            "player": common.compact(player),
        })
    return counts, player


def maybe_refresh_counts(profile, player, counts, handle, args, batches, steel_count, phase):
    if int(args.count_refresh_batches) > 0 and int(batches) % int(args.count_refresh_batches) == 0:
        return refresh_counts_and_player(profile, handle, phase, player=player)
    apply_completed_batch_counts(counts, steel_count)
    counts[common.STEEL_BAR]["inventory"] = actual_steel_carried(player)
    common.write_event(handle, "cannonball_count_cache_update", {
        "phase": phase,
        "batches": int(batches),
        "steelCount": int(steel_count),
        "steelBars": counts[common.STEEL_BAR],
        "cannonballs": counts[CANNONBALL],
        "ammoMould": counts[AMMO_MOULD],
        "player": common.compact(player),
    })
    return counts, player


def run_cannonball_batch(profile, steel_count, furnace, handle, args, player=None):
    player = route_to_furnace(profile, handle, args, player=player)
    if not furnace:
        furnace = None if args.discover_furnace else dict(AL_KHARID_FURNACE_OBJECT)
    if not furnace:
        furnace = find_furnace(profile, handle, args)
    player = ensure_furnace_interaction(profile, handle, args, player, furnace)
    furnace_loc = furnace_tile(furnace) or {"x": 0, "y": 0, "height": 0}
    before_steel = bridge.count_inventory_item(player, common.STEEL_BAR)
    before_cballs = bridge.count_inventory_item(player, CANNONBALL)
    before_xp = bridge.skill_xp(player, "smithing")
    if before_steel <= 0:
        raise RuntimeError("cannonball batch has no steel bars in inventory")
    start = timed_call_tool(profile, handle, "cannonball:start", "use_item_on_object", {
        "itemId": common.STEEL_BAR,
        "objectId": int(furnace.get("objectId", furnace.get("id", 0)) or 0),
        "x": int(furnace.get("x", furnace_loc["x"]) or 0),
        "y": int(furnace.get("y", furnace_loc["y"]) or 0),
    })
    player = bridge._player_from_or(start, player)
    started_cannonballs = bool(start.get("startedCannonballMaking"))
    if not start.get("success") or not started_cannonballs:
        common.write_event(handle, "cannonball_batch", {
            "amount": int(steel_count),
            "startSuccess": bool(start.get("success")),
            "startedCannonballMaking": started_cannonballs,
            "startMessage": start.get("message"),
            "itemCountBefore": start.get("itemCountBefore"),
            "itemCountAfter": start.get("itemCountAfter"),
            "player": common.compact(player),
        })
        raise RuntimeError("cannonball start failed: {} startedCannonballMaking={}".format(
            start.get("message"),
            started_cannonballs,
        ))
    wait_ticks = max(20, int(before_steel) * int(args.ticks_per_bar) + int(args.wait_tick_padding))
    wait = timed_call_tool(profile, handle, "cannonball:wait", "wait_until_idle_XS", {
        "maxTicks": wait_ticks,
        "movement": True,
        "skilling": True,
        "combat": False,
    })
    player = bridge.player_from(wait)
    after_steel = bridge.count_inventory_item(player, common.STEEL_BAR)
    after_cballs = bridge.count_inventory_item(player, CANNONBALL)
    after_xp = bridge.skill_xp(player, "smithing")
    consumed = max(0, before_steel - after_steel)
    produced = max(0, after_cballs - before_cballs)
    made_progress = consumed > 0 or produced > 0 or after_xp > before_xp
    common.write_event(handle, "cannonball_batch", {
        "amount": int(steel_count),
        "inventorySteelAtStart": before_steel,
        "startSuccess": True,
        "startedCannonballMaking": started_cannonballs,
        "startMessage": start.get("message"),
        "startItemCountBefore": start.get("itemCountBefore"),
        "startItemCountAfter": start.get("itemCountAfter"),
        "waitStatus": wait.get("batchStatus"),
        "waitTicks": wait.get("batchTicks"),
        "waitMaxTicks": wait_ticks,
        "beforeSteel": before_steel,
        "afterSteel": after_steel,
        "steelConsumed": consumed,
        "beforeCannonballs": before_cballs,
        "afterCannonballs": after_cballs,
        "cannonballsProduced": produced,
        "beforeXp": before_xp,
        "afterXp": after_xp,
        "xpGained": after_xp - before_xp,
        "madeProgress": bool(made_progress),
        "player": common.compact(player),
    })
    if not made_progress:
        raise RuntimeError("cannonball batch made no cannonballs or XP progress")
    return player, furnace, consumed


def payload(player, counts, args, phase, batches, run_path):
    return {
        "script": "al_kharid_cannonball_smelter",
        "phase": phase,
        "batches": int(batches),
        "barsPerBatch": int(args.bars_per_batch),
        "fullBatchesRemaining": possible_batches(counts, args.bars_per_batch),
        "steelBars": counts[common.STEEL_BAR],
        "cannonballs": counts[CANNONBALL],
        "ammoMould": counts[AMMO_MOULD],
        "player": common.compact(player),
        "logPath": str(run_path),
    }


def run(args):
    if args.status:
        print(json.dumps(common.read_status(args.profile, STATUS_NAME), indent=2, sort_keys=True))
        return 0
    run_path, handle = common.open_run_log("cannonball-smelt", args)
    profile = args.profile
    batches = 0
    bank_ready = False
    counts = None
    furnace = None
    try:
        player = ensure_al_kharid_bank(profile, handle, args)
        common.write_event(handle, "run_start", {"args": vars(args), "player": common.compact(player)})
        while True:
            if not bank_ready:
                player = ensure_al_kharid_bank(profile, handle, args, player=player)
                player = timed_deposit_all_except(
                    player,
                    profile,
                    keep_ids=(AMMO_MOULD, CANNONBALL),
                    handle=handle,
                    reason="pre_cannonball_cleanup",
                )
                counts, player = refresh_counts_and_player(profile, handle, "pre_cannonball_cleanup", player=player)
            bank_ready = False
            if bridge.skill_level(player, "smithing") < 35:
                data = payload(player, counts, args, "blocked_smithing_under_35", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                raise RuntimeError("cannonballs require Smithing 35")
            if counts[AMMO_MOULD]["total"] <= 0 and bridge.count_inventory_item(player, AMMO_MOULD) <= 0:
                data = payload(player, counts, args, "blocked_missing_ammo_mould", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                raise RuntimeError("ammo mould is required for cannonballs")
            if bridge.count_inventory_item(player, AMMO_MOULD) <= 0:
                player = timed_withdraw_item(player, profile, AMMO_MOULD, 1, handle=handle, reason="withdraw_ammo_mould")
            remaining = int(counts[common.STEEL_BAR]["bank"])
            if remaining <= 0:
                counts, player = refresh_counts_and_player(profile, handle, "steel_depleted_confirm", player=player)
                remaining = int(counts[common.STEEL_BAR]["bank"])
                if remaining > 0:
                    bank_ready = True
                    continue
                player = timed_deposit_all_except(
                    player,
                    profile,
                    keep_ids=(),
                    handle=handle,
                    reason="final_deposit_cannonballs",
                )
                counts, player = refresh_counts_and_player(profile, handle, "complete_steel_depleted", player=player)
                data = payload(player, counts, args, "complete_steel_depleted", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                common.write_event(handle, "run_finish", data)
                common.log("cannonball smelting complete: steel bars depleted", args)
                return 0
            if args.max_batches > 0 and batches >= args.max_batches:
                data = payload(player, counts, args, "batch_cap_reached", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                common.write_event(handle, "run_paused", data)
                common.log("cannonball smelting paused at batch cap; steel bars remaining {}".format(remaining), args)
                return 0
            carried_steel = actual_steel_carried(player)
            free_slots = int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0)
            if carried_steel > int(args.bars_per_batch):
                common.write_event(handle, "carried_steel_over_batch_size", {
                    "carriedSteel": int(carried_steel),
                    "barsPerBatch": int(args.bars_per_batch),
                    "player": common.compact(player),
                })
            withdraw_amount = max(0, min(
                int(args.bars_per_batch) - int(carried_steel),
                remaining,
                free_slots,
            ))
            if carried_steel <= 0 and withdraw_amount <= 0:
                player = timed_deposit_all_except(
                    player,
                    profile,
                    keep_ids=(AMMO_MOULD, CANNONBALL),
                    handle=handle,
                    reason="recover_no_free_slots",
                )
                counts, player = refresh_counts_and_player(profile, handle, "recover_no_free_slots", player=player)
                bank_ready = True
                continue
            if withdraw_amount > 0:
                player = timed_withdraw_item(
                    player,
                    profile,
                    common.STEEL_BAR,
                    withdraw_amount,
                    handle=handle,
                    reason="withdraw_steel_bars",
                )
                apply_withdrawn_steel_counts(counts, withdraw_amount)
            steel_count = actual_steel_carried(player)
            common.write_event(handle, "cannonball_loadout_ready", {
                "carriedSteelBeforeWithdraw": int(carried_steel),
                "withdrawAmount": int(withdraw_amount),
                "steelCount": int(steel_count),
                "freeSlotsBeforeWithdraw": int(free_slots),
                "player": common.compact(player),
            })
            common.log("making cannonballs from {} steel bars; bank steel before batch {}".format(steel_count, remaining), args)
            try:
                player, furnace, consumed = run_cannonball_batch(profile, steel_count, furnace, handle, args, player=player)
            except RuntimeError:
                common.close_interfaces(profile)
                player = ensure_al_kharid_bank(profile, handle, args)
                player = timed_deposit_all_except(
                    player,
                    profile,
                    keep_ids=(AMMO_MOULD, CANNONBALL),
                    handle=handle,
                    reason="recover_partial_cannonball_bank",
                )
                counts, player = refresh_counts_and_player(profile, handle, "recover_partial_cannonball_bank", player=player)
                common.write_status(profile, STATUS_NAME, payload(player, counts, args, "recovered_partial_batch", batches, run_path))
                bank_ready = True
                continue
            player = ensure_al_kharid_bank(profile, handle, args, player=player)
            batches += 1
            deposited_cannonballs = 0
            if args.deposit_cannonballs_each_lap:
                deposited_cannonballs = bridge.count_inventory_item(player, CANNONBALL)
                player = timed_deposit_all_except(
                    player,
                    profile,
                    keep_ids=(AMMO_MOULD,),
                    handle=handle,
                    reason="post_cannonball_deposit_each_lap",
                )
            counts, player = maybe_refresh_counts(
                profile,
                player,
                counts,
                handle,
                args,
                batches,
                consumed or steel_count,
                "post_cannonball_bank",
            )
            if args.deposit_cannonballs_each_lap:
                apply_deposited_cannonballs(counts, deposited_cannonballs)
                common.write_event(handle, "cannonball_deposit_cache_update", {
                    "phase": "post_cannonball_bank",
                    "depositedCannonballs": int(deposited_cannonballs),
                    "cannonballs": counts[CANNONBALL],
                    "player": common.compact(player),
                })
            common.write_status(profile, STATUS_NAME, payload(player, counts, args, "running", batches, run_path))
            bank_ready = True
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make cannonballs from banked steel bars at Al Kharid.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--bars-per-batch", type=int, default=26)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--min-run-energy", type=int, default=1)
    parser.add_argument("--min-run-energy-to-furnace", type=int, default=45)
    parser.add_argument("--min-run-energy-to-bank", type=int, default=1)
    parser.add_argument("--run-to-furnace", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-to-bank", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--count-refresh-batches", type=int, default=25)
    parser.add_argument("--object-max-distance", type=int, default=8)
    parser.add_argument("--ticks-per-bar", type=int, default=3)
    parser.add_argument("--wait-tick-padding", type=int, default=12)
    parser.add_argument("--fast-local-shuttle", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-interaction-tile", action="store_true")
    parser.add_argument("--discover-furnace", action="store_true")
    parser.add_argument("--deposit-cannonballs-each-lap", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
