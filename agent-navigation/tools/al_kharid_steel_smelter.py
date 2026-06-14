#!/usr/bin/env python3
"""Smelt banked iron ore and coal into steel bars at Al Kharid."""

import argparse
import json
import sys
import time

import bridge_script as bridge
import smithing_goal_common as common
from profile_utils import resolve_profile


STATUS_NAME = "al-kharid-steel-smelter-status"
SMITHING_RUNNER = common.SCRIPT_DIR / "smithing_runner.py"
AL_KHARID_FURNACE_SMELT_TILE = {"x": 3274, "y": 3179, "height": 0}


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
    common.write_event(handle, "steel_timing", data)


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


def timed_withdraw_items(player, profile, withdrawals, handle=None, reason="withdraw_items"):
    items = [
        {"itemId": int(item_id), "amount": int(amount)}
        for item_id, amount in withdrawals
        if int(amount) > 0
    ]
    if not items:
        return player
    result = timed_call_tool(
        profile,
        handle,
        reason,
        "withdraw_bank_items_XS",
        {"items": items},
    )
    updated = bridge._player_from_or(result, player)
    common.write_event(handle, "withdraw_items", {
        "reason": reason,
        "items": result.get("items", items),
        "requested": len(items),
        "withdrawn": result.get("withdrawn"),
        "withdrawnAmount": result.get("withdrawnAmount"),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": common.compact(updated),
    })
    if not result.get("success"):
        raise RuntimeError("batch withdraw failed: {}".format(result.get("message")))
    return updated


def timed_ensure_run(player, profile, handle, args, reason):
    if bool(player.get("runEnabled", False)) or int(player.get("runEnergy", 0) or 0) < args.min_run_energy:
        return player
    result = timed_call_tool(profile, handle, reason, "set_run_XXS", {"enabled": True})
    next_player = dict(player)
    next_player.update(bridge.player_from(result))
    common.write_event(handle, "set_run", {
        "reason": reason,
        "before": common.compact(player),
        "after": common.compact(next_player),
    })
    return next_player


def fast_local_walk(profile, tile, handle, args, reason, stop_distance=0, max_ticks=45, player=None):
    if player is None:
        player = timed_observe_xs(profile, handle, "{}:pre_walk_observe".format(reason))
    if common.near_tile(player, tile, max(1, int(stop_distance))):
        return player
    player = timed_ensure_run(player, profile, handle, args, reason)
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
    if not result.get("success"):
        raise RuntimeError("local walk to {} failed: {}".format(reason, result.get("message")))
    return updated


def route_to_furnace(profile, handle, args, player=None):
    if player is None:
        player = timed_observe_xs(profile, handle, "steel_furnace:route_observe")
    if common.near_tile(player, AL_KHARID_FURNACE_SMELT_TILE, 0):
        return player
    if args.fast_local_shuttle and common.near_tile(player, common.AL_KHARID_BANK_TILE, 48):
        return fast_local_walk(profile, AL_KHARID_FURNACE_SMELT_TILE, handle, args, "steel_furnace", player=player)
    return common.ml2_route_to(profile, AL_KHARID_FURNACE_SMELT_TILE, handle, "steel_furnace", args, arrival_radius=0)


def ensure_al_kharid_bank(profile, handle, args, coin_float=0, player=None):
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
        coin_float=coin_float,
        radius=8,
    )


def run_steel_batch(profile, steel_count, handle, args, player=None):
    if not args.smelt_via_subprocess:
        return run_steel_batch_direct(profile, steel_count, handle, args, player=player)
    return run_steel_batch_subprocess(profile, steel_count, handle, args, player=player)


def run_steel_batch_direct(profile, steel_count, handle, args, player=None):
    player = route_to_furnace(profile, handle, args, player=player)
    before_iron = bridge.count_inventory_item(player, common.IRON_ORE)
    before_bars = bridge.count_inventory_item(player, common.STEEL_BAR)
    before_xp = bridge.skill_xp(player, "smithing")
    start = timed_call_tool(profile, handle, "smelt_steel:start", "smelt_bar", {
        "bar": "steel",
        "amount": int(steel_count),
        "maxDistance": 6,
        "legacyCompatibility": True,
    })
    if not start.get("success"):
        common.write_event(handle, "smelt_steel_batch", {
            "mode": "direct",
            "amount": int(steel_count),
            "startSuccess": False,
            "startMessage": start.get("message"),
            "player": common.compact(bridge._player_from_or(start, player)),
        })
        raise RuntimeError("steel smelt start failed: {}".format(start.get("message")))
    wait = timed_call_tool(profile, handle, "smelt_steel:wait", "wait_until_idle_XS", {
        "maxTicks": 260,
        "movement": True,
        "skilling": True,
        "combat": False,
    })
    player = bridge.player_from(wait)
    after_iron = bridge.count_inventory_item(player, common.IRON_ORE)
    after_bars = bridge.count_inventory_item(player, common.STEEL_BAR)
    after_xp = bridge.skill_xp(player, "smithing")
    made_progress = after_bars > before_bars or after_xp > before_xp or after_iron < before_iron
    common.write_event(handle, "smelt_steel_batch", {
        "mode": "direct",
        "amount": int(steel_count),
        "startSuccess": True,
        "startMessage": start.get("message"),
        "waitStatus": wait.get("batchStatus"),
        "beforeIron": before_iron,
        "afterIron": after_iron,
        "beforeBars": before_bars,
        "afterBars": after_bars,
        "beforeXp": before_xp,
        "afterXp": after_xp,
        "madeProgress": bool(made_progress),
        "player": common.compact(player),
    })
    if not made_progress:
        raise RuntimeError("direct steel smelting made no bar or XP progress")
    return player


def run_steel_batch_subprocess(profile, steel_count, handle, args, player=None):
    route_to_furnace(profile, handle, args, player=player)
    command = [
        sys.executable,
        str(SMITHING_RUNNER),
        "--profile", profile,
        "--mode", "smelt",
        "--bar", "steel",
        "--amount", str(steel_count),
        "--max-cycles", "1",
        "--min-run-energy", str(args.min_run_energy),
    ]
    if args.quiet:
        command.append("--quiet")
    try:
        common.run_subprocess(
            command,
            profile,
            handle,
            "smelt_steel_batch",
            args,
            timeout=args.batch_timeout_seconds,
        )
    except RuntimeError as exc:
        common.write_event(handle, "smelt_steel_batch_recovery", {
            "reason": "subprocess_failed_or_timed_out",
            "message": str(exc),
            "player": common.compact(bridge.observe_xs(profile=profile)),
        })
        raise


def possible_steel(counts):
    return min(int(counts[common.IRON_ORE]["bank"]), int(counts[common.COAL]["bank"]) // 2)


def apply_completed_batch_counts(counts, steel_count):
    steel_count = int(steel_count)
    counts[common.IRON_ORE]["bank"] = max(0, int(counts[common.IRON_ORE]["bank"]) - steel_count)
    counts[common.IRON_ORE]["total"] = max(0, int(counts[common.IRON_ORE]["total"]) - steel_count)
    counts[common.COAL]["bank"] = max(0, int(counts[common.COAL]["bank"]) - steel_count * 2)
    counts[common.COAL]["total"] = max(0, int(counts[common.COAL]["total"]) - steel_count * 2)
    counts[common.STEEL_BAR]["bank"] = int(counts[common.STEEL_BAR]["bank"]) + steel_count
    counts[common.STEEL_BAR]["total"] = int(counts[common.STEEL_BAR]["total"]) + steel_count


def refresh_counts_and_player(profile, handle, phase):
    counts, _count_player = timed_count_items(profile, [common.IRON_ORE, common.COAL, common.STEEL_BAR], handle, "{}:count".format(phase))
    player = timed_observe_xs(profile, handle, "{}:post_count_observe".format(phase))
    return counts, player


def maybe_refresh_counts_after_deposit(profile, player, counts, handle, args, batches, steel_count, phase):
    if int(args.count_refresh_batches) > 0 and int(batches) % int(args.count_refresh_batches) == 0:
        return refresh_counts_and_player(profile, handle, phase)
    apply_completed_batch_counts(counts, steel_count)
    common.write_event(handle, "steel_count_cache_update", {
        "phase": phase,
        "batches": int(batches),
        "steelCount": int(steel_count),
        "possibleSteelBars": int(possible_steel(counts)),
        "ironOre": counts[common.IRON_ORE],
        "coal": counts[common.COAL],
        "steelBars": counts[common.STEEL_BAR],
        "player": common.compact(player),
    })
    return counts, player


def payload(player, counts, args, phase, batches, run_path):
    return {
        "script": "al_kharid_steel_smelter",
        "phase": phase,
        "batches": int(batches),
        "possibleSteelBars": int(possible_steel(counts)),
        "ironOre": counts[common.IRON_ORE],
        "coal": counts[common.COAL],
        "steelBars": counts[common.STEEL_BAR],
        "player": common.compact(player),
        "logPath": str(run_path),
    }


def run(args):
    if args.status:
        print(json.dumps(common.read_status(args.profile, STATUS_NAME), indent=2, sort_keys=True))
        return 0
    run_path, handle = common.open_run_log("steel-smelt", args)
    profile = args.profile
    batches = 0
    bank_ready = False
    counts = None
    try:
        player = ensure_al_kharid_bank(profile, handle, args, coin_float=args.route_coin_float)
        common.write_event(handle, "run_start", {"args": vars(args), "player": common.compact(player)})
        while True:
            if not bank_ready:
                player = ensure_al_kharid_bank(profile, handle, args)
                player = timed_deposit_all_except(player, profile, keep_ids=(), handle=handle, reason="pre_steel_cleanup")
                counts, player = refresh_counts_and_player(profile, handle, "pre_steel_cleanup")
            bank_ready = False
            if bridge.skill_level(player, "smithing") < 20:
                data = payload(player, counts, args, "blocked_smithing_under_20", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                raise RuntimeError("steel smelting requires Smithing 20")
            remaining = possible_steel(counts)
            if remaining <= 0:
                counts, player = refresh_counts_and_player(profile, handle, "material_depleted_confirm")
                remaining = possible_steel(counts)
                if remaining > 0:
                    bank_ready = True
                    continue
                data = payload(player, counts, args, "complete_material_depleted", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                common.write_event(handle, "run_finish", data)
                common.log("steel smelting complete: iron or coal depleted", args)
                return 0
            if args.max_batches > 0 and batches >= args.max_batches:
                data = payload(player, counts, args, "batch_cap_reached", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                common.write_event(handle, "run_paused", data)
                common.log("steel smelting paused at batch cap; possible steel {}".format(remaining), args)
                return 0
            steel_count = min(int(args.steel_per_batch), int(remaining))
            player = timed_withdraw_items(
                player,
                profile,
                ((common.IRON_ORE, steel_count), (common.COAL, steel_count * 2)),
                handle=handle,
                reason="withdraw_steel_materials",
            )
            common.log("smelting {} steel bars; possible steel remaining before batch {}".format(steel_count, remaining), args)
            try:
                player = run_steel_batch(profile, steel_count, handle, args, player=player)
            except RuntimeError:
                common.close_interfaces(profile)
                player = ensure_al_kharid_bank(profile, handle, args)
                player = timed_deposit_all_except(player, profile, keep_ids=(), handle=handle, reason="recover_partial_steel_bank")
                counts, player = refresh_counts_and_player(profile, handle, "recover_partial_steel_bank")
                common.write_status(profile, STATUS_NAME, payload(player, counts, args, "recovered_partial_batch", batches, run_path))
                bank_ready = True
                continue
            player = ensure_al_kharid_bank(profile, handle, args, player=player)
            batches += 1
            player = timed_deposit_all_except(player, profile, keep_ids=(), handle=handle, reason="post_steel_bank")
            counts, player = maybe_refresh_counts_after_deposit(
                profile,
                player,
                counts,
                handle,
                args,
                batches,
                steel_count,
                "post_steel_bank",
            )
            common.write_status(profile, STATUS_NAME, payload(player, counts, args, "running", batches, run_path))
            bank_ready = True
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Smelt banked iron ore and coal into steel bars at Al Kharid.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--steel-per-batch", type=int, default=9)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--count-refresh-batches", type=int, default=25)
    parser.add_argument("--batch-timeout-seconds", type=int, default=210)
    parser.add_argument("--route-coin-float", type=int, default=20)
    parser.add_argument("--fast-local-shuttle", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--smelt-via-subprocess", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
