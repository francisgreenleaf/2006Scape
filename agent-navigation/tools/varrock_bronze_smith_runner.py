#!/usr/bin/env python3
"""Smith banked bronze bars at Varrock west anvils until Smithing 30."""

import argparse
import json
import sys

import bridge_script as bridge
import smithing_goal_common as common
from profile_utils import resolve_profile


STATUS_NAME = "varrock-bronze-smith-status"
SMITHING_RUNNER = common.SCRIPT_DIR / "smithing_runner.py"


def run_smith_batch(profile, bars, handle, args):
    common.ml2_route_to(profile, common.VARROCK_WEST_ANVILS, handle, "varrock_bronze_anvil", args, arrival_radius=3)
    command = [
        sys.executable,
        str(SMITHING_RUNNER),
        "--profile", profile,
        "--mode", "smith",
        "--item", "bronze",
        "--amount", str(bars),
        "--target-smithing-level", str(args.target_smithing_level),
        "--max-cycles", "1",
        "--min-run-energy", str(args.min_run_energy),
    ]
    if args.quiet:
        command.append("--quiet")
    common.run_subprocess(command, profile, handle, "smith_bronze_batch", args)


def payload(player, counts, args, phase, batches, run_path):
    return {
        "script": "varrock_bronze_smith_runner",
        "phase": phase,
        "batches": int(batches),
        "targetSmithingLevel": int(args.target_smithing_level),
        "bronzeBars": counts[common.BRONZE_BAR],
        "hammer": counts[common.HAMMER],
        "player": common.compact(player),
        "logPath": str(run_path),
    }


def run(args):
    if args.status:
        print(json.dumps(common.read_status(args.profile, STATUS_NAME), indent=2, sort_keys=True))
        return 0
    run_path, handle = common.open_run_log("bronze-smith", args)
    profile = args.profile
    batches = 0
    try:
        player = common.ensure_bank_at(
            profile,
            common.VARROCK_WEST_BANK,
            common.VARROCK_WEST_BANK_TILE,
            handle,
            args,
            coin_float=args.route_coin_float,
            radius=10,
        )
        common.write_event(handle, "run_start", {"args": vars(args), "player": common.compact(player)})
        while True:
            player = common.ensure_bank_at(
                profile,
                common.VARROCK_WEST_BANK,
                common.VARROCK_WEST_BANK_TILE,
                handle,
                args,
                radius=10,
            )
            if bridge.skill_level(player, "smithing") >= int(args.target_smithing_level):
                player = common.deposit_all_except(player, profile, keep_ids=(), handle=handle, reason="phase_complete_cleanup")
                counts, player = common.count_items(profile, [common.BRONZE_BAR, common.HAMMER])
                data = payload(player, counts, args, "complete", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                common.write_event(handle, "run_finish", data)
                common.log("bronze smithing complete: Smithing {}".format(bridge.skill_level(player, "smithing")), args)
                return 0
            if args.max_batches > 0 and batches >= args.max_batches:
                counts, player = common.count_items(profile, [common.BRONZE_BAR, common.HAMMER])
                data = payload(player, counts, args, "batch_cap_reached", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                common.write_event(handle, "run_paused", data)
                common.log("bronze smithing paused at batch cap; Smithing {}".format(bridge.skill_level(player, "smithing")), args)
                return 0
            player = common.deposit_all_except(player, profile, keep_ids=(common.HAMMER,), handle=handle, reason="pre_smith_cleanup")
            counts, player = common.count_items(profile, [common.BRONZE_BAR, common.HAMMER])
            if counts[common.HAMMER]["total"] <= 0:
                data = payload(player, counts, args, "blocked_missing_hammer", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                raise RuntimeError("hammer is required for bronze smithing")
            if bridge.count_inventory_item(player, common.HAMMER) <= 0:
                player = common.withdraw_item(player, profile, common.HAMMER, 1, handle=handle, reason="withdraw_hammer")
            counts, player = common.count_items(profile, [common.BRONZE_BAR, common.HAMMER])
            banked_bars = counts[common.BRONZE_BAR]["bank"]
            if banked_bars <= 0:
                data = payload(player, counts, args, "blocked_no_bronze_bars", batches, run_path)
                common.write_status(profile, STATUS_NAME, data)
                common.write_event(handle, "run_blocked", data)
                common.log("bronze smithing blocked: no banked bronze bars", args)
                return 2
            bars = min(int(args.bars_per_batch), int(banked_bars))
            player = common.withdraw_item(player, profile, common.BRONZE_BAR, bars, handle=handle, reason="withdraw_bronze_bars")
            common.log("smithing {} bronze bars at Varrock; Smithing {}".format(bars, bridge.skill_level(player, "smithing")), args)
            run_smith_batch(profile, bars, handle, args)
            player = common.ensure_bank_at(
                profile,
                common.VARROCK_WEST_BANK,
                common.VARROCK_WEST_BANK_TILE,
                handle,
                args,
                radius=10,
            )
            batches += 1
            player = common.deposit_all_except(player, profile, keep_ids=(common.HAMMER,), handle=handle, reason="post_smith_bank")
            counts, player = common.count_items(profile, [common.BRONZE_BAR, common.HAMMER])
            common.write_status(profile, STATUS_NAME, payload(player, counts, args, "running", batches, run_path))
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Smith bronze bars at Varrock west anvils until a target Smithing level.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--target-smithing-level", type=int, default=30)
    parser.add_argument("--bars-per-batch", type=int, default=27)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--route-coin-float", type=int, default=20)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
