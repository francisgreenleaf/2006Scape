#!/usr/bin/env python3
"""Mine and smelt enough Al Kharid bronze supplies for Smithing 30."""

import argparse
import json
import math
import sys

import bridge_script as bridge
import smithing_goal_common as common
from profile_utils import resolve_profile


STATUS_NAME = "al-kharid-bronze-prep-status"
SMITHING_RUNNER = common.SCRIPT_DIR / "smithing_runner.py"
BRONZE_SMELT_XP = 6
BRONZE_SMITH_XP_PER_BAR = 13
MINE_TILE = {"x": 3300, "y": 3300, "height": 0}
MINE_WAYPOINTS = [
    {"x": 3275, "y": 3183, "height": 0},
    {"x": 3280, "y": 3218, "height": 0},
    {"x": 3282, "y": 3260, "height": 0},
    MINE_TILE,
]
BANK_WAYPOINTS = [
    {"x": 3282, "y": 3260, "height": 0},
    {"x": 3280, "y": 3218, "height": 0},
    {"x": 3275, "y": 3183, "height": 0},
    common.AL_KHARID_BANK_TILE,
]
FURNACE_WAYPOINTS = [
    {"x": 3282, "y": 3260, "height": 0},
    {"x": 3280, "y": 3218, "height": 0},
    {"x": 3275, "y": 3183, "height": 0},
    common.AL_KHARID_FURNACE_TILE,
]


def bronze_need(player, counts, target_level):
    target_xp = common.xp_for_level(target_level)
    smithing_xp = bridge.skill_xp(player, "smithing")
    bronze_bars = counts[common.BRONZE_BAR]["total"]
    xp_after_banked_bars = smithing_xp + bronze_bars * BRONZE_SMITH_XP_PER_BAR
    remaining_xp = max(0, target_xp - xp_after_banked_bars)
    pair_xp = BRONZE_SMELT_XP + BRONZE_SMITH_XP_PER_BAR
    pairs_needed = int(math.ceil(float(remaining_xp) / float(pair_xp))) if remaining_xp > 0 else 0
    return {
        "targetXp": target_xp,
        "smithingXp": smithing_xp,
        "bronzeBars": bronze_bars,
        "xpAfterBankedBars": xp_after_banked_bars,
        "remainingXpAfterBankedBars": remaining_xp,
        "bronzePairsNeeded": pairs_needed,
    }


def ensure_rune_pickaxe(profile, player, handle):
    counts, player = common.count_items(profile, [common.RUNE_PICKAXE])
    if counts[common.RUNE_PICKAXE]["equipment"] > 0:
        return player
    if counts[common.RUNE_PICKAXE]["inventory"] <= 0:
        if counts[common.RUNE_PICKAXE]["bank"] <= 0:
            raise RuntimeError("rune pickaxe is required for bronze mining")
        player = common.withdraw_item(player, profile, common.RUNE_PICKAXE, 1, handle=handle, reason="withdraw_rune_pickaxe")
    result = bridge.call_tool("equip_item", {"itemId": common.RUNE_PICKAXE}, profile=profile)
    player = bridge._player_from_or(result, player)
    common.write_event(handle, "equip_rune_pickaxe", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": common.compact(player),
    })
    if not result.get("success"):
        raise RuntimeError("could not equip rune pickaxe: {}".format(result.get("message")))
    return player


def choose_ore(player):
    copper = bridge.count_inventory_item(player, common.COPPER)
    tin = bridge.count_inventory_item(player, common.TIN)
    return "copper" if copper <= tin else "tin"


def target_ore_for_carried_load(copper, tin, args):
    cap = int(args.max_smelt_pairs)
    if int(copper) >= cap and int(tin) < int(copper):
        return "tin"
    if int(tin) >= cap and int(copper) < int(tin):
        return "copper"
    return None


def find_rock(profile, ore, args, handle):
    try:
        return bridge.call_tool("find_nearest_rock_XS", {
            "resource": ore,
            "maxDistance": int(args.rock_scan_distance),
            "reachable": True,
        }, profile=profile)
    except RuntimeError as exc:
        common.write_event(handle, "find_rock_error", {
            "ore": ore,
            "error": str(exc)[:500],
        })
        return {"success": False, "message": str(exc)}


def mine_one_ore(profile, ore, player, handle, args, strict=False):
    find = find_rock(profile, ore, args, handle)
    if not find.get("success") and not strict:
        other = "tin" if ore == "copper" else "copper"
        find = find_rock(profile, other, args, handle)
        ore = other
    if not find.get("success"):
        wait = bridge.call_tool("wait_ticks_XS", {"ticks": 4}, profile=profile)
        common.write_event(handle, "mine_ore_unavailable_wait", {
            "ore": ore,
            "strict": bool(strict),
            "message": find.get("message"),
            "player": common.compact(bridge._player_from_or(wait, player)),
        })
        return bridge._player_from_or(wait, player), False
    obj = find.get("object") or {}
    rock_tile = rock_object_tile(obj)
    before_copper = bridge.count_inventory_item(player, common.COPPER)
    before_tin = bridge.count_inventory_item(player, common.TIN)
    try:
        click = bridge.call_tool("interact_object_XS", {
            "objectId": int(obj.get("objectId", obj.get("id", 0)) or 0),
            "x": int(rock_tile["x"]),
            "y": int(rock_tile["y"]),
            "height": int(rock_tile.get("height", 0) or 0),
            "option": "first",
            "requireReachable": True,
        }, profile=profile)
    except RuntimeError as exc:
        walk = bridge.call_tool("walk_to_tile_until_arrived_XS", {
            "x": int(rock_tile["x"]),
            "y": int(rock_tile["y"]),
            "height": int(rock_tile.get("height", 0) or 0),
            "stopDistance": 1,
            "maxTicks": 35,
            "maxWalkDistance": 24,
            "stopOnCombat": True,
            "stopOnStall": True,
        }, profile=profile)
        player = bridge._player_from_or(walk, player)
        common.write_event(handle, "mine_interaction_retry", {
            "ore": ore,
            "object": obj,
            "error": str(exc)[:500],
            "walkSuccess": bool(walk.get("success")),
            "walkStatus": walk.get("batchStatus"),
            "player": common.compact(player),
        })
        click = bridge.call_tool("interact_object_XS", {
            "objectId": int(obj.get("objectId", obj.get("id", 0)) or 0),
            "x": int(rock_tile["x"]),
            "y": int(rock_tile["y"]),
            "height": int(rock_tile.get("height", 0) or 0),
            "option": "first",
            "requireReachable": True,
        }, profile=profile)
    wait = bridge.call_tool("wait_until_idle_XS", {
        "maxTicks": int(args.mine_max_ticks),
        "movement": True,
        "skilling": True,
        "combat": False,
    }, profile=profile)
    player = bridge.player_from(wait)
    after_copper = bridge.count_inventory_item(player, common.COPPER)
    after_tin = bridge.count_inventory_item(player, common.TIN)
    progressed = after_copper > before_copper or after_tin > before_tin
    common.write_event(handle, "mine_one_ore", {
        "ore": ore,
        "object": obj,
        "findSuccess": bool(find.get("success")),
        "clickSuccess": bool(click.get("success")),
        "waitStatus": wait.get("batchStatus"),
        "progressed": bool(progressed),
        "beforeCopper": before_copper,
        "afterCopper": after_copper,
        "beforeTin": before_tin,
        "afterTin": after_tin,
        "player": common.compact(player),
    })
    return player, progressed


def rock_object_tile(obj):
    tile = obj.get("tile")
    if isinstance(tile, str):
        parts = tile.split(",")
        if len(parts) >= 3:
            return {"x": int(parts[0]), "y": int(parts[1]), "height": int(parts[2])}
    if isinstance(tile, dict):
        return {
            "x": int(tile.get("x", 0) or 0),
            "y": int(tile.get("y", 0) or 0),
            "height": int(tile.get("height", tile.get("h", 0)) or 0),
        }
    return {
        "x": int(obj.get("x")),
        "y": int(obj.get("y")),
        "height": int(obj.get("height", 0) or 0),
    }


def direct_walk(profile, tile, stop_distance, max_ticks, handle, reason, allow_partial=False):
    try:
        result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
            "x": int(tile["x"]),
            "y": int(tile["y"]),
            "height": int(tile.get("height", 0) or 0),
            "stopDistance": int(stop_distance),
            "maxTicks": int(max_ticks),
            "maxWalkDistance": 90,
            "stopOnCombat": True,
            "stopOnStall": True,
        }, profile=profile)
        player = bridge.player_from(result)
        common.write_event(handle, "direct_walk", {
            "reason": reason,
            "target": tile,
            "stopDistance": int(stop_distance),
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "batchStatus": result.get("batchStatus"),
            "player": common.compact(player),
        })
        return player
    except RuntimeError as exc:
        player = bridge.observe_xs(profile=profile)
        common.write_event(handle, "direct_walk_error", {
            "reason": reason,
            "target": tile,
            "stopDistance": int(stop_distance),
            "error": str(exc)[:500],
            "player": common.compact(player),
        })
        if allow_partial:
            return player
        raise


def walk_waypoints(profile, waypoints, final_stop_distance, handle, args, reason):
    player = bridge.observe_xs(profile=profile)
    current = common.tile_from_player(player)
    start_index = min(
        range(len(waypoints)),
        key=lambda idx: common.chebyshev(current, waypoints[idx]),
    )
    if start_index > 0:
        common.write_event(handle, "resume_waypoint_route", {
            "reason": reason,
            "startIndex": int(start_index),
            "current": common.tile_string(current),
            "waypoint": common.tile_string(waypoints[start_index]),
        })
    last_index = len(waypoints) - 1
    for index in range(start_index, len(waypoints)):
        tile = waypoints[index]
        stop = int(final_stop_distance) if index == last_index else 3
        if common.chebyshev(common.tile_from_player(player), tile) <= stop:
            continue
        before = common.tile_from_player(player)
        player = direct_walk(
            profile,
            tile,
            stop,
            args.mine_route_max_ticks,
            handle,
            "{}_{}".format(reason, index + 1),
            allow_partial=True,
        )
        after = common.tile_from_player(player)
        if common.chebyshev(after, tile) > stop and before == after:
            raise RuntimeError("no movement progress toward {} waypoint {}".format(reason, common.tile_string(tile)))
    if common.chebyshev(common.tile_from_player(player), waypoints[-1]) > int(final_stop_distance):
        raise RuntimeError("did not reach {} final waypoint {}".format(reason, common.tile_string(waypoints[-1])))
    return player


def mine_bronze_load(profile, handle, args, target_ore=None, target_count=None):
    player = bridge.observe_xs(profile=profile)
    if bool(player.get("inBankArea", False)) and target_ore:
        player = ensure_rune_pickaxe(profile, player, handle)
    elif bool(player.get("inBankArea", False)):
        player = common.deposit_all_except(player, profile, keep_ids=(common.RUNE_PICKAXE,), handle=handle, reason="pre_mine_cleanup")
        player = ensure_rune_pickaxe(profile, player, handle)
    elif bridge.count_inventory_item(player, common.RUNE_PICKAXE) > 0 or common.count_items(profile, [common.RUNE_PICKAXE])[0][common.RUNE_PICKAXE]["equipment"] > 0:
        common.write_event(handle, "continue_mine_from_current_location", {"player": common.compact(player)})
    else:
        player = walk_waypoints(profile, BANK_WAYPOINTS, 1, handle, args, "bank_for_pickaxe")
        player = common.deposit_all_except(player, profile, keep_ids=(common.RUNE_PICKAXE,), handle=handle, reason="pre_mine_cleanup")
        player = ensure_rune_pickaxe(profile, player, handle)
    player = walk_waypoints(profile, MINE_WAYPOINTS, 3, handle, args, "al_kharid_bronze_mine")
    rounds = 0
    no_progress = 0
    while int(player.get("freeInventorySlots", 0) or 0) > 0 and rounds < int(args.max_mine_rounds):
        if target_ore and target_count is not None:
            target_item = common.TIN if str(target_ore) == "tin" else common.COPPER
            if bridge.count_inventory_item(player, target_item) >= int(target_count):
                break
        rounds += 1
        ore = str(target_ore) if target_ore else choose_ore(player)
        player, progressed = mine_one_ore(profile, ore, player, handle, args, strict=bool(target_ore))
        no_progress = 0 if progressed else no_progress + 1
        if no_progress >= int(args.max_no_progress_rounds):
            break
    common.write_event(handle, "mine_bronze_load_finish", {
        "rounds": rounds,
        "targetOre": target_ore,
        "targetCount": target_count,
        "player": common.compact(player),
    })
    return player


def route_to_furnace_from_current(profile, player, handle, args, reason):
    if common.chebyshev(common.tile_from_player(player), common.AL_KHARID_FURNACE_TILE) <= 3:
        return player
    if common.chebyshev(common.tile_from_player(player), MINE_TILE) <= 32:
        return walk_waypoints(profile, FURNACE_WAYPOINTS, 3, handle, args, reason)
    common.ml2_route_to(profile, common.AL_KHARID_FURNACE_TILE, handle, reason, args, arrival_radius=3)
    return bridge.observe_xs(profile=profile)


def run_bronze_smelt(profile, pairs, handle, args):
    command = [
        sys.executable,
        str(SMITHING_RUNNER),
        "--profile", profile,
        "--mode", "smelt",
        "--bar", "bronze",
        "--amount", str(pairs),
        "--max-cycles", "1",
        "--min-run-energy", str(args.min_run_energy),
    ]
    if args.quiet:
        command.append("--quiet")
    common.run_subprocess(command, profile, handle, "smelt_bronze_batch", args)


def smelt_carried_bronze(profile, player, handle, args, reason):
    pairs = min(
        bridge.count_inventory_item(player, common.COPPER),
        bridge.count_inventory_item(player, common.TIN),
        int(args.max_smelt_pairs),
    )
    if pairs <= 0:
        return player
    player = route_to_furnace_from_current(profile, player, handle, args, reason)
    attempts = 0
    max_attempts = int(args.max_smelt_pairs) + 2
    while pairs > 0 and attempts < max_attempts:
        attempts += 1
        run_bronze_smelt(profile, pairs, handle, args)
        player = bridge.observe_xs(profile=profile)
        remaining_pairs = min(
            bridge.count_inventory_item(player, common.COPPER),
            bridge.count_inventory_item(player, common.TIN),
            int(args.max_smelt_pairs),
        )
        common.write_event(handle, "smelt_carried_bronze_progress", {
            "attempt": int(attempts),
            "beforePairs": int(pairs),
            "remainingPairs": int(remaining_pairs),
            "player": common.compact(player),
        })
        if remaining_pairs >= pairs:
            raise RuntimeError("bronze smelting did not reduce carried copper/tin pairs")
        pairs = remaining_pairs
    if pairs > 0:
        raise RuntimeError("bronze smelting still has {} carried pairs after {} attempts".format(pairs, attempts))
    player = common.ensure_bank_at(
        profile,
        common.AL_KHARID_BANK,
        common.AL_KHARID_BANK_TILE,
        handle,
        args,
        radius=8,
    )
    return common.deposit_all_except(player, profile, keep_ids=(), handle=handle, reason="post_bronze_smelt")


def smelt_banked_bronze(profile, pairs, handle, args):
    player = common.ensure_bank_at(
        profile,
        common.AL_KHARID_BANK,
        common.AL_KHARID_BANK_TILE,
        handle,
        args,
        radius=8,
    )
    player = common.deposit_all_except(player, profile, keep_ids=(), handle=handle, reason="pre_bronze_smelt")
    player = common.withdraw_item(player, profile, common.COPPER, pairs, handle=handle, reason="withdraw_copper")
    player = common.withdraw_item(player, profile, common.TIN, pairs, handle=handle, reason="withdraw_tin")
    return smelt_carried_bronze(profile, player, handle, args, "bronze_furnace")


def smelt_banked_copper_with_mined_tin(profile, pairs, handle, args):
    player = common.ensure_bank_at(
        profile,
        common.AL_KHARID_BANK,
        common.AL_KHARID_BANK_TILE,
        handle,
        args,
        radius=8,
    )
    player = common.deposit_all_except(player, profile, keep_ids=(common.RUNE_PICKAXE,), handle=handle, reason="pre_banked_copper_tin_mine")
    player = ensure_rune_pickaxe(profile, player, handle)
    player = common.withdraw_item(player, profile, common.COPPER, pairs, handle=handle, reason="withdraw_copper_for_tin_mine")
    player = mine_bronze_load(profile, handle, args, target_ore="tin", target_count=pairs)
    return smelt_carried_bronze(profile, player, handle, args, "al_kharid_furnace_after_tin_mine")


def status_payload(player, counts, args, phase, loops, run_path):
    need = bronze_need(player, counts, args.target_smithing_level)
    pairs_available = min(counts[common.COPPER]["total"], counts[common.TIN]["total"])
    return {
        "script": "al_kharid_bronze_prep_runner",
        "phase": phase,
        "loops": int(loops),
        "targetSmithingLevel": int(args.target_smithing_level),
        "bronzePairsAvailable": int(pairs_available),
        "copper": counts[common.COPPER],
        "tin": counts[common.TIN],
        "bronzeBars": counts[common.BRONZE_BAR],
        "runePickaxe": counts[common.RUNE_PICKAXE],
        "need": need,
        "player": common.compact(player),
        "logPath": str(run_path),
    }


def run(args):
    if args.status:
        print(json.dumps(common.read_status(args.profile, STATUS_NAME), indent=2, sort_keys=True))
        return 0
    run_path, handle = common.open_run_log("bronze-prep", args)
    profile = args.profile
    loops = 0
    try:
        player = bridge.observe_xs(profile=profile)
        common.write_event(handle, "run_start", {"args": vars(args), "player": common.compact(player)})
        while True:
            loops += 1
            counts, _count_player = common.count_items(profile, [common.COPPER, common.TIN, common.BRONZE_BAR, common.RUNE_PICKAXE])
            player = bridge.observe_xs(profile=profile)
            need = bronze_need(player, counts, args.target_smithing_level)
            carried_copper = bridge.count_inventory_item(player, common.COPPER)
            carried_tin = bridge.count_inventory_item(player, common.TIN)
            carried_pairs = min(carried_copper, carried_tin)
            banked_pairs = min(counts[common.COPPER]["bank"], counts[common.TIN]["bank"])
            banked_copper_surplus = max(0, counts[common.COPPER]["bank"] - counts[common.TIN]["bank"])
            free_slots = int(player.get("freeInventorySlots", 0) or 0)
            distance_to_mine = common.chebyshev(common.tile_from_player(player), MINE_TILE)
            distance_to_furnace = common.chebyshev(common.tile_from_player(player), common.AL_KHARID_FURNACE_TILE)
            should_extend_carried_load = (carried_copper > 0 or carried_tin > 0) and free_slots > 0 and distance_to_mine <= max(32, distance_to_furnace)
            if need["bronzePairsNeeded"] <= 0:
                payload = status_payload(player, counts, args, "complete", loops, run_path)
                common.write_status(profile, STATUS_NAME, payload)
                common.write_event(handle, "run_finish", payload)
                common.log("bronze prep complete: banked bronze bars can finish Smithing {}".format(args.target_smithing_level), args)
                return 0
            if args.max_loops > 0 and loops > args.max_loops:
                payload = status_payload(player, counts, args, "loop_cap_reached", loops - 1, run_path)
                common.write_status(profile, STATUS_NAME, payload)
                common.write_event(handle, "run_paused", payload)
                common.log("bronze prep paused at loop cap; pairs needed {}".format(need["bronzePairsNeeded"]), args)
                return 0
            if should_extend_carried_load:
                common.log("finishing carried Al Kharid copper/tin load; {} pairs still needed".format(need["bronzePairsNeeded"]), args)
                player = mine_bronze_load(
                    profile,
                    handle,
                    args,
                    target_ore=target_ore_for_carried_load(carried_copper, carried_tin, args),
                )
                player = smelt_carried_bronze(profile, player, handle, args, "al_kharid_furnace_after_mine")
            elif carried_pairs > 0:
                batch = min(carried_pairs, int(args.max_smelt_pairs), need["bronzePairsNeeded"])
                common.log("smelting {} carried bronze pairs; {} pairs still needed".format(batch, need["bronzePairsNeeded"]), args)
                player = smelt_carried_bronze(profile, player, handle, args, "bronze_furnace_carried")
            elif banked_pairs > 0:
                batch = common.smelt_load_size(banked_pairs, need["bronzePairsNeeded"], hard_cap=args.max_smelt_pairs)
                common.log("smelting {} bronze pairs; {} pairs still needed".format(batch, need["bronzePairsNeeded"]), args)
                player = smelt_banked_bronze(profile, batch, handle, args)
            elif banked_copper_surplus > 0:
                batch = common.smelt_load_size(banked_copper_surplus, need["bronzePairsNeeded"], hard_cap=args.max_smelt_pairs)
                common.log("mining tin for {} banked copper; {} pairs still needed".format(batch, need["bronzePairsNeeded"]), args)
                player = smelt_banked_copper_with_mined_tin(profile, batch, handle, args)
            else:
                common.log("mining one Al Kharid copper/tin load; {} pairs still needed".format(need["bronzePairsNeeded"]), args)
                player = mine_bronze_load(profile, handle, args)
                player = smelt_carried_bronze(profile, player, handle, args, "al_kharid_furnace_after_mine")
            counts, _count_player = common.count_items(profile, [common.COPPER, common.TIN, common.BRONZE_BAR, common.RUNE_PICKAXE])
            player = bridge.observe_xs(profile=profile)
            payload = status_payload(player, counts, args, "running", loops, run_path)
            common.write_status(profile, STATUS_NAME, payload)
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare enough copper/tin/bronze bars for Smithing 30 from Al Kharid.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--target-smithing-level", type=int, default=30)
    parser.add_argument("--max-loops", type=int, default=0)
    parser.add_argument("--max-smelt-pairs", type=int, default=14)
    parser.add_argument("--max-mine-rounds", type=int, default=32)
    parser.add_argument("--max-no-progress-rounds", type=int, default=4)
    parser.add_argument("--mine-max-ticks", type=int, default=90)
    parser.add_argument("--mine-route-max-ticks", type=int, default=260)
    parser.add_argument("--rock-scan-distance", type=int, default=28)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--route-coin-float", type=int, default=20)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
