#!/usr/bin/env python3
"""Orchestrate Mining and Smithing training through existing primitive runners."""

import argparse
import datetime as dt
import subprocess
import sys
import uuid

import bridge_script as bridge


RUNS_DIR = bridge.ROOT / "data" / "smithing" / "runs"

COINS = 995
HAMMER = 2347
IRON_ORE = 440
IRON_BAR = 2351
BRONZE_BAR = 2349

AL_KHARID_BANK = "al kharid bank"
AL_KHARID_FURNACE = "al kharid furnace"
VARROCK_EAST_BANK = "varrock east bank"
VARROCK_WEST_BANK = "varrock west bank"
VARROCK_WEST_ANVILS = "varrock west anvils"

MINING_RUNNER = bridge.SCRIPT_DIR / "mining_runner.py"
SMITHING_RUNNER = bridge.SCRIPT_DIR / "smithing_runner.py"
METALS_RUNNER = bridge.SCRIPT_DIR / "al_kharid_metals_runner.py"


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def write(handle, event, data):
    bridge.write_event(handle, event, data)


def carried(player, item_id):
    return bridge.count_inventory_item(player, item_id)


def banked(player, item_id):
    return bridge.count_bank_item(player, item_id)


def total(player, item_id):
    return carried(player, item_id) + banked(player, item_id)


def close_interfaces(profile):
    bridge.call_tool("close_interfaces", {}, profile=profile)


def ensure_bank(player, profile, handle, target, reason):
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
    write(handle, "deposit_all_except", {
        "reason": reason,
        "keepIds": sorted(keep),
        "itemIds": deposit_ids,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("mining", "smithing")),
    })
    return bridge.observe(profile)


def withdraw_item(player, item_id, amount, profile, handle, reason):
    if amount <= 0:
        return player
    result = bridge.call_tool("withdraw_bank_items", {
        "itemId": int(item_id),
        "amount": int(amount),
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    write(handle, "withdraw_item", {
        "reason": reason,
        "itemId": int(item_id),
        "amount": int(amount),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("mining", "smithing")),
    })
    return bridge.observe(profile)


def ensure_coin_float(player, amount, profile, handle, args):
    if amount <= 0 or carried(player, COINS) >= amount:
        return player
    if total(player, COINS) < amount:
        raise RuntimeError("not enough coins available for travel/shop recovery")
    return withdraw_item(player, COINS, amount - carried(player, COINS), profile, handle, "coin_float")


def run_child(command, handle, event_name, args):
    write(handle, event_name + "_start", {"command": command})
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
        "stdoutTail": stdout_lines[-12:],
        "stderrTail": stderr_lines[-12:],
    }
    write(handle, event_name + "_finish", payload)
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(command[0], "\n".join(stderr_lines[-5:] or stdout_lines[-5:])))
    if stdout_lines:
        log("{} ok: {}".format(event_name, stdout_lines[-1]), args)


def train_bronze_to_iron(profile, handle, args):
    command = [
        str(METALS_RUNNER),
        "--profile", profile,
        "--target-smithing-level", "15",
        "--iron-target-mining-level", "0",
        "--no-start-iron-after-smithing",
        "--min-run-energy", str(args.min_run_energy),
    ]
    if args.quiet:
        command.append("--quiet")
    run_child(command, handle, "bronze_to_iron_unlock", args)


def mine_iron(profile, handle, args, target_level=0, loads=0):
    command = [
        str(MINING_RUNNER),
        "--profile", profile,
        "--ores", "iron",
        "--bank", VARROCK_EAST_BANK,
        "--auto-buy-bronze-pickaxe",
        "--auto-upgrade-pickaxe",
        "--min-run-energy", str(args.min_run_energy),
    ]
    if int(target_level) > 0:
        command.extend(["--target-mining-level", str(target_level)])
    if int(loads) > 0:
        command.extend(["--max-loads", str(loads)])
    run_child(command, handle, "mine_iron", args)


def smelt_iron_batch(player, profile, handle, args):
    player = ensure_bank(player, profile, handle, AL_KHARID_BANK, "iron_smelt_bank")
    player = deposit_all_except(player, keep_ids=(COINS,), profile=profile, handle=handle, reason="iron_smelt_cleanup")
    player = ensure_coin_float(player, args.coin_float, profile, handle, args)
    ore = min(27, banked(player, IRON_ORE))
    if ore <= 0:
        return player, False
    player = withdraw_item(player, IRON_ORE, ore, profile, handle, "withdraw_iron_ore")
    command = [
        str(SMITHING_RUNNER),
        "--profile", profile,
        "--mode", "smelt",
        "--bar", "iron",
        "--furnace", AL_KHARID_FURNACE,
        "--max-cycles", "8",
        "--min-run-energy", str(args.min_run_energy),
    ]
    if args.quiet:
        command.append("--quiet")
    run_child(command, handle, "smelt_iron_batch", args)
    player = ensure_bank(bridge.observe(profile), profile, handle, AL_KHARID_BANK, "post_iron_smelt_bank")
    player = deposit_all_except(player, keep_ids=(COINS,), profile=profile, handle=handle, reason="post_iron_smelt_cleanup")
    return bridge.observe(profile), True


def smith_bar_batch(player, profile, handle, args, bar_id, bar_name):
    player = ensure_bank(player, profile, handle, VARROCK_WEST_BANK, "{}_smith_bank".format(bar_name))
    player = deposit_all_except(player, keep_ids=(HAMMER,), profile=profile, handle=handle, reason="smith_cleanup")
    if carried(player, HAMMER) < 1:
        if banked(player, HAMMER) < 1:
            raise RuntimeError("hammer is required for smithing")
        player = withdraw_item(player, HAMMER, 1, profile, handle, "withdraw_hammer")
    bars = min(27, banked(player, bar_id))
    if bars <= 0:
        return player, False
    player = withdraw_item(player, bar_id, bars, profile, handle, "withdraw_{}_bars".format(bar_name))
    command = [
        str(SMITHING_RUNNER),
        "--profile", profile,
        "--mode", "smith",
        "--anvil", VARROCK_WEST_ANVILS,
        "--target-smithing-level", str(args.target_smithing_level),
        "--max-cycles", "20",
        "--min-run-energy", str(args.min_run_energy),
    ]
    if args.quiet:
        command.append("--quiet")
    run_child(command, handle, "smith_{}_batch".format(bar_name), args)
    player = ensure_bank(bridge.observe(profile), profile, handle, VARROCK_WEST_BANK, "post_smith_bank")
    player = deposit_all_except(player, keep_ids=(HAMMER,), profile=profile, handle=handle, reason="post_smith_cleanup")
    return bridge.observe(profile), True


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-mining-smithing-goal-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = bridge.observe(profile)
        player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason="mining_smithing_goal")
        write(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("mining", "smithing")),
            "materials": {
                "bronzeBars": total(player, BRONZE_BAR),
                "ironOre": total(player, IRON_ORE),
                "ironBars": total(player, IRON_BAR),
            },
        })

        if bridge.skill_level(player, "smithing") < 15:
            train_bronze_to_iron(profile, handle, args)
            player = bridge.observe(profile)

        if bridge.skill_level(player, "mining") < args.target_mining_level:
            mine_iron(profile, handle, args, target_level=args.target_mining_level)
            player = bridge.observe(profile)

        loops = 0
        while (
            bridge.skill_level(player, "smithing") < args.target_smithing_level
            or bridge.skill_level(player, "mining") < args.target_mining_level
        ):
            loops += 1
            if args.max_loops > 0 and loops > args.max_loops:
                raise RuntimeError("reached loop cap before target levels")

            progressed = False
            if bridge.skill_level(player, "smithing") >= 15 and total(player, IRON_BAR) > 0:
                player, progressed = smith_bar_batch(player, profile, handle, args, IRON_BAR, "iron")
            elif total(player, IRON_ORE) > 0 and bridge.skill_level(player, "smithing") >= 15:
                player, progressed = smelt_iron_batch(player, profile, handle, args)
            else:
                mine_iron(profile, handle, args, loads=1)
                player = bridge.observe(profile)
                progressed = True

            player = bridge.observe(profile)
            log(
                "loop {} mining={} smithing={} ironOre={} ironBars={}".format(
                    loops,
                    bridge.skill_level(player, "mining"),
                    bridge.skill_level(player, "smithing"),
                    total(player, IRON_ORE),
                    total(player, IRON_BAR),
                ),
                args,
            )
            if not progressed:
                raise RuntimeError("no mining or smithing progress path was available")

        write(handle, "run_finish", {
            "player": bridge.compact_player(player, ("mining", "smithing")),
            "materials": {
                "ironOre": total(player, IRON_ORE),
                "ironBars": total(player, IRON_BAR),
            },
        })
        if handle is not None:
            log("mining/smithing goal log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train Mining and Smithing toward target levels using primitive runners.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--target-mining-level", type=int, default=30)
    parser.add_argument("--target-smithing-level", type=int, default=30)
    parser.add_argument("--coin-float", type=int, default=20)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--max-loops", type=int, default=0)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
