#!/usr/bin/env python3
"""Bronze-smelting then iron-mining progression wrapper.

Bronze and iron ore are mined from the proven Varrock east bank mine clusters.
Bronze bars are still smelted at the Al Kharid furnace.
"""

import argparse
import datetime as dt
import subprocess
import sys
import uuid

import bridge_script as bridge


RUNS_DIR = bridge.ROOT / "data" / "smithing" / "runs"

COINS = 995
COPPER = 436
TIN = 438
BRONZE_BAR = 2349

AL_KHARID_BANK = "al kharid bank"
AL_KHARID_FURNACE = "al kharid furnace"
VARROCK_EAST_BANK = "varrock east bank"

MINING_RUNNER = bridge.SCRIPT_DIR / "mining_runner.py"
SMITHING_RUNNER = bridge.SCRIPT_DIR / "smithing_runner.py"


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def carried_count(player, item_id):
    return bridge.count_inventory_item(player, item_id)


def bank_count(player, item_id):
    return bridge.count_bank_item(player, item_id)


def total_count(player, item_id):
    return carried_count(player, item_id) + bank_count(player, item_id)


def bronze_pairs(player):
    return min(total_count(player, COPPER), total_count(player, TIN))


def close_interfaces(profile):
    bridge.call_tool("close_interfaces", {}, profile=profile)


def ensure_bank_area(player, profile, handle, target, reason):
    if bool(player.get("inBankArea", False)):
        return bridge.observe(profile)
    close_interfaces(profile)
    bridge.route_to(target, profile=profile, handle=handle, reason=reason)
    return bridge.observe(profile)


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
        "player": bridge.compact_player(updated, ("mining", "smithing")),
    })
    return bridge.observe(profile)


def withdraw_if_needed(player, item_id, amount, profile, handle, reason):
    needed = max(0, int(amount) - carried_count(player, item_id))
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
        "requested": int(amount),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("mining", "smithing")),
    })
    return bridge.observe(profile)


def ensure_coin_float(player, profile, handle, args):
    player = ensure_bank_area(player, profile, handle, AL_KHARID_BANK, "coin_float_bank")
    if carried_count(player, COINS) >= int(args.coin_float):
        return player
    if total_count(player, COINS) < int(args.coin_float):
        raise RuntimeError("not enough coins available for the Al Kharid toll and shop recovery")
    return withdraw_if_needed(player, COINS, args.coin_float, profile, handle, "coin_float")


def withdraw_bronze_ore_batch(player, profile, handle, args):
    player = ensure_bank_area(player, profile, handle, AL_KHARID_BANK, "bronze_ore_bank")
    player = deposit_all_except(player, keep_ids=(), profile=profile, handle=handle, reason="bronze_ore_cleanup")
    pairs = min(int(args.bronze_pairs_per_batch), bank_count(player, COPPER), bank_count(player, TIN))
    if pairs <= 0:
        raise RuntimeError("no bronze ore pairs are banked")
    player = withdraw_if_needed(player, COPPER, pairs, profile, handle, "withdraw_copper")
    player = withdraw_if_needed(player, TIN, pairs, profile, handle, "withdraw_tin")
    return player


def run_child(command, handle, event_name, args):
    bridge.write_event(handle, event_name + "_start", {"command": command})
    proc = subprocess.run(
        [sys.executable] + command,
        cwd=str(bridge.REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    stderr_lines = [line for line in (proc.stderr or "").splitlines() if line.strip()]
    payload = {
        "command": command,
        "returncode": int(proc.returncode),
        "stdoutTail": stdout_lines[-10:],
        "stderrTail": stderr_lines[-10:],
    }
    bridge.write_event(handle, event_name + "_finish", payload)
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(command[0], "\n".join(stderr_lines[-4:] or stdout_lines[-4:])))
    if stdout_lines and not args.quiet:
        log("{} ok: {}".format(event_name, stdout_lines[-1]), args)


def mine_bronze_load(profile, handle, args):
    command = [
        str(MINING_RUNNER),
        "--profile", profile,
        "--ores", "copper,tin",
        "--bank", VARROCK_EAST_BANK,
        "--strategy", "bronze-balanced",
        "--max-loads", "1",
        "--min-run-energy", str(args.min_run_energy),
        "--auto-buy-bronze-pickaxe",
        "--auto-upgrade-pickaxe",
    ]
    run_child(command, handle, "mine_bronze_load", args)


def smelt_bronze_batch(profile, handle, args):
    command = [
        str(SMITHING_RUNNER),
        "--profile", profile,
        "--mode", "smelt",
        "--bar", "bronze",
        "--furnace", AL_KHARID_FURNACE,
        "--max-cycles", "1",
        "--min-run-energy", str(args.min_run_energy),
    ]
    if args.quiet:
        command.append("--quiet")
    run_child(command, handle, "smelt_bronze_batch", args)


def start_iron_phase(profile, handle, args):
    command = [
        str(MINING_RUNNER),
        "--profile", profile,
        "--ores", "iron",
        "--bank", VARROCK_EAST_BANK,
        "--min-run-energy", str(args.min_run_energy),
        "--auto-buy-bronze-pickaxe",
        "--auto-upgrade-pickaxe",
    ]
    if int(args.iron_max_loads) > 0:
        command.extend(["--max-loads", str(args.iron_max_loads)])
    if int(args.iron_target_mining_level) > 0:
        command.extend(["--target-mining-level", str(args.iron_target_mining_level)])
    run_child(command, handle, "iron_phase", args)


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = bridge.observe(profile)
        player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason="al_kharid_metals_runner")
        bridge.write_event(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("mining", "smithing")),
        })

        bronze_cycles = 0
        while bridge.skill_level(player, "smithing") < int(args.target_smithing_level):
            if int(args.max_bronze_cycles) > 0 and bronze_cycles >= int(args.max_bronze_cycles):
                raise RuntimeError("reached bronze cycle cap before Smithing {}".format(args.target_smithing_level))

            player = ensure_bank_area(player, profile, handle, AL_KHARID_BANK, "bronze_loop_bank")
            if bronze_pairs(player) <= 0:
                player = ensure_coin_float(player, profile, handle, args)
                mine_bronze_load(profile, handle, args)
                player = bridge.observe(profile)

            if bridge.skill_level(player, "smithing") < int(args.target_smithing_level):
                player = withdraw_bronze_ore_batch(player, profile, handle, args)
                smelt_bronze_batch(profile, handle, args)
                player = bridge.observe(profile)

            player = ensure_bank_area(player, profile, handle, AL_KHARID_BANK, "post_smelt_bank")
            player = deposit_all_except(player, keep_ids=(COINS,), profile=profile, handle=handle, reason="post_smelt_cleanup")
            bronze_cycles += 1
            player = bridge.observe(profile)
            log(
                "bronze cycle {} smithing={} mining={} bronzePairs={} bankBronzeBars={}".format(
                    bronze_cycles,
                    bridge.skill_level(player, "smithing"),
                    bridge.skill_level(player, "mining"),
                    bronze_pairs(player),
                    bank_count(player, BRONZE_BAR),
                ),
                args,
            )

        if args.start_iron_after_smithing:
            player = ensure_bank_area(player, profile, handle, AL_KHARID_BANK, "iron_phase_bank")
            player = deposit_all_except(player, keep_ids=(COINS,), profile=profile, handle=handle, reason="iron_phase_cleanup")
            player = ensure_coin_float(player, profile, handle, args)
            start_iron_phase(profile, handle, args)
            player = bridge.observe(profile)

        bridge.write_event(handle, "run_finish", {
            "player": bridge.compact_player(player, ("mining", "smithing")),
        })
        if handle is not None:
            log("metals log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the Al Kharid bronze-smelting then iron-mining phase.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--target-smithing-level", type=int, default=15)
    parser.add_argument("--bronze-pairs-per-batch", type=int, default=14)
    parser.add_argument("--coin-float", type=int, default=20)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--max-bronze-cycles", type=int, default=40)
    parser.add_argument("--start-iron-after-smithing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--iron-max-loads", type=int, default=0)
    parser.add_argument("--iron-target-mining-level", type=int, default=20)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
