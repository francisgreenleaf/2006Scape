#!/usr/bin/env python3
# Main-agent trial note: this runner is intentionally mine-specific and can be
# launched for a long mining attempt, but it is not yet a detached daemon with
# status/stop controls and it is not tick-perfect. It delegates to
# mining_runner.py for ML1 routing, banking, and pickaxe loadout behavior.
"""Mine and bank iron at the Ardougne south cluster.

This is a mine-specific wrapper around mining_runner.py. It keeps the general
runner's ML1 route execution, primitive rock interaction loop, ore banking, and
pickaxe loadout behavior, while fixing the site to the dense Ardougne south
iron cluster near the south bank.
"""

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import mining_runner  # noqa: E402
import bridge_script as bridge  # noqa: E402
from profile_utils import resolve_profile  # noqa: E402


ARDY_SOUTH_IRON_SITE = "2606,3238,0"
ARDY_SOUTH_BANK = "ardougne_south_bank"
ARDY_SOUTH_BANK_TILE = "2654,3283,0"


def _ardy_tile(value):
    return mining_runner.parse_tile(value)


def _ardy_direct_walk(target, args, handle, reason, stop_distance=0, require_bank=False):
    max_distance = max(int(args.max_walk_distance), 96)
    result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
        "x": int(target["x"]),
        "y": int(target["y"]),
        "height": int(target.get("height", 0) or 0),
        "stopDistance": int(stop_distance),
        "maxTicks": int(args.route_max_ticks),
        "maxWalkDistance": max_distance,
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=args.profile)
    player = bridge.player_from(result)
    ok = bool(player.get("inBankArea")) if require_bank else (
        mining_runner.chebyshev(mining_runner.tile_from_player(player), target) <= int(stop_distance)
    )
    mining_runner.write_event(handle, "ardy_direct_walk", {
        "reason": reason,
        "target": mining_runner.tile_string(target),
        "stopDistance": int(stop_distance),
        "requireBank": bool(require_bank),
        "success": ok,
        "batchStatus": result.get("batchStatus"),
        "message": result.get("message"),
        "player": mining_runner.compact_player(player),
    })
    return ok


def install_ardy_route_hooks():
    original_route_to_tile = mining_runner.route_to_tile
    original_route_to_bank = mining_runner.route_to_bank
    site_tile = _ardy_tile(ARDY_SOUTH_IRON_SITE)
    bank_tile = _ardy_tile(ARDY_SOUTH_BANK_TILE)

    def route_to_tile(target_tile, args, handle, reason):
        if mining_runner.tile_string(target_tile) == ARDY_SOUTH_IRON_SITE:
            return _ardy_direct_walk(
                site_tile,
                args,
                handle,
                reason or "ardy_mine_site",
                stop_distance=int(args.arrival_radius),
            )
        return original_route_to_tile(target_tile, args, handle, reason)

    def route_to_bank(site, args, handle):
        if site.get("bankPlace") == ARDY_SOUTH_BANK or mining_runner.tile_string(site.get("bankTile", {})) == ARDY_SOUTH_BANK_TILE:
            return _ardy_direct_walk(
                bank_tile,
                args,
                handle,
                "ardy_south_bank",
                stop_distance=4,
                require_bank=True,
            )
        return original_route_to_bank(site, args, handle)

    mining_runner.route_to_tile = route_to_tile
    mining_runner.route_to_bank = route_to_bank


def build_mining_args(args):
    forwarded = [
        "--profile", args.profile,
        "--ores", "iron",
        "--site", ARDY_SOUTH_IRON_SITE,
        "--bank", ARDY_SOUTH_BANK,
        "--bank-tile", ARDY_SOUTH_BANK_TILE,
        "--arrival-radius", str(args.arrival_radius),
        "--rock-scan-distance", str(args.rock_scan_distance),
        "--mine-max-ticks", str(args.mine_max_ticks),
        "--max-batches-per-leg", str(args.max_batches_per_leg),
        "--max-walk-distance", str(args.max_walk_distance),
        "--route-max-ticks", str(args.route_max_ticks),
        "--min-run-energy", str(args.min_run_energy),
        "--loop-delay", str(args.loop_delay),
        "--prefer-known-rocks",
    ]
    if args.target_mining_level:
        forwarded.extend(["--target-mining-level", str(args.target_mining_level)])
    if args.max_loads is not None:
        forwarded.extend(["--max-loads", str(args.max_loads)])
    if args.max_mining_batches is not None:
        forwarded.extend(["--max-mining-batches", str(args.max_mining_batches)])
    if args.no_enable_run:
        forwarded.append("--no-enable-run")
    if args.auto_buy_bronze_pickaxe:
        forwarded.append("--auto-buy-bronze-pickaxe")
    if args.auto_upgrade_pickaxe:
        forwarded.append("--auto-upgrade-pickaxe")
    if args.no_wait_for_local_respawn:
        forwarded.append("--no-wait-for-local-respawn")
    if args.stop_on_blocked:
        forwarded.append("--stop-on-blocked")
    if args.no_log:
        forwarded.append("--no-log")
    return forwarded


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Mine iron at the Ardougne south cluster and bank at Ardougne south bank."
    )
    parser.add_argument("--profile", default=resolve_profile(default=""), help="Bridge profile/session to use.")
    parser.add_argument("--target-mining-level", type=int, default=0)
    parser.add_argument("--max-loads", type=int)
    parser.add_argument("--max-mining-batches", type=int)
    parser.add_argument("--arrival-radius", type=int, default=5)
    parser.add_argument("--rock-scan-distance", type=int, default=8)
    parser.add_argument("--mine-max-ticks", type=int, default=250)
    parser.add_argument("--max-batches-per-leg", type=int, default=8)
    parser.add_argument("--max-walk-distance", type=int, default=96)
    parser.add_argument("--route-max-ticks", type=int, default=180)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--loop-delay", type=float, default=0.05)
    parser.add_argument("--no-enable-run", action="store_true")
    parser.add_argument("--auto-buy-bronze-pickaxe", action="store_true")
    parser.add_argument("--auto-upgrade-pickaxe", action="store_true")
    parser.add_argument("--no-wait-for-local-respawn", action="store_true")
    parser.add_argument("--stop-on-blocked", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--print-command", action="store_true",
                        help="Print the delegated mining_runner.py arguments without running.")
    args = parser.parse_args(argv)

    delegated = build_mining_args(args)
    if args.print_command:
        print("python3 agent-navigation/tools/mining_runner.py " + " ".join(delegated))
        return 0
    install_ardy_route_hooks()
    return mining_runner.main(delegated)


if __name__ == "__main__":
    raise SystemExit(main())
