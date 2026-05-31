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
from profile_utils import resolve_profile  # noqa: E402


ARDY_SOUTH_IRON_SITE = "2606,3238,0"
ARDY_SOUTH_BANK = "ardougne_south_bank"
ARDY_SOUTH_BANK_TILE = "2654,3283,0"


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
    parser.add_argument("--max-walk-distance", type=int, default=48)
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
    return mining_runner.main(delegated)


if __name__ == "__main__":
    raise SystemExit(main())
