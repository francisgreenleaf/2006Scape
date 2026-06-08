#!/usr/bin/env python3
"""Smelt banked iron ore and coal into steel bars at Al Kharid."""

import argparse
import json
import sys

import bridge_script as bridge
import smithing_goal_common as common
from profile_utils import resolve_profile


STATUS_NAME = "al-kharid-steel-smelter-status"
SMITHING_RUNNER = common.SCRIPT_DIR / "smithing_runner.py"


def run_steel_batch(profile, steel_count, handle, args):
    common.ml2_route_to(profile, common.AL_KHARID_FURNACE_TILE, handle, "steel_furnace", args, arrival_radius=3)
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
    common.run_subprocess(command, profile, handle, "smelt_steel_batch", args)


def possible_steel(counts):
    return min(int(counts[common.IRON_ORE]["bank"]), int(counts[common.COAL]["bank"]) // 2)


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
    try:
        player = common.ensure_bank_at(
            profile,
            common.AL_KHARID_BANK,
            common.AL_KHARID_BANK_TILE,
            handle,
            args,
            coin_float=args.route_coin_float,
            radius=8,
        )
        common.write_event(handle, "run_start", {"args": vars(args), "player": common.compact(player)})
        while True:
            player = common.ensure_bank_at(
                profile,
                common.AL_KHARID_BANK,
                common.AL_KHARID_BANK_TILE,
                handle,
                args,
                radius=8,
            )
            player = common.deposit_all_except(player, profile, keep_ids=(), handle=handle, reason="pre_steel_cleanup")
            counts, _count_player = common.count_items(profile, [common.IRON_ORE, common.COAL, common.STEEL_BAR])
            player = bridge.observe_xs(profile=profile)
            if bridge.skill_level(player, "smithing") < 20:
                data = payload(player, counts, args, "blocked_smithing_under_20", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                raise RuntimeError("steel smelting requires Smithing 20")
            remaining = possible_steel(counts)
            if remaining <= 0:
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
            player = common.withdraw_item(player, profile, common.IRON_ORE, steel_count, handle=handle, reason="withdraw_iron")
            player = common.withdraw_item(player, profile, common.COAL, steel_count * 2, handle=handle, reason="withdraw_coal")
            common.log("smelting {} steel bars; possible steel remaining before batch {}".format(steel_count, remaining), args)
            run_steel_batch(profile, steel_count, handle, args)
            player = common.ensure_bank_at(
                profile,
                common.AL_KHARID_BANK,
                common.AL_KHARID_BANK_TILE,
                handle,
                args,
                radius=8,
            )
            batches += 1
            player = common.deposit_all_except(player, profile, keep_ids=(), handle=handle, reason="post_steel_bank")
            counts, _count_player = common.count_items(profile, [common.IRON_ORE, common.COAL, common.STEEL_BAR])
            player = bridge.observe_xs(profile=profile)
            common.write_status(profile, STATUS_NAME, payload(player, counts, args, "running", batches, run_path))
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Smelt banked iron ore and coal into steel bars at Al Kharid.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--steel-per-batch", type=int, default=9)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--route-coin-float", type=int, default=20)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
