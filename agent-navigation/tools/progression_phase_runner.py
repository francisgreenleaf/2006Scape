#!/usr/bin/env python3
"""Sequential MrFlame progression wrapper.

This keeps phase selection out of the heartbeat prompt. It reuses the
individual primitive-backed phase runners and only runs the phases that still
have work remaining.
"""

import argparse
import subprocess
import sys

import bridge_script as bridge


SCRIPT_DIR = bridge.SCRIPT_DIR
LEATHER_RUNNER = SCRIPT_DIR / "al_kharid_crafting_runner.py"
METALS_RUNNER = SCRIPT_DIR / "al_kharid_metals_runner.py"
THIEVING_RUNNER = SCRIPT_DIR / "thieving_runner.py"
AGILITY_RUNNER = SCRIPT_DIR / "agility_phase_runner.py"

COWHIDE = 1739
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

PHASES = ("leather", "metals", "thieving", "agility")


def item_total(player, item_id):
    total = bridge.count_inventory_item(player, item_id) + bridge.count_bank_item(player, item_id)
    for item in bridge.equipment(player):
        current = int(item.get("id", item.get("itemId", -1)) or -1)
        if current == int(item_id):
            total += int(item.get("amount", 0) or 0)
    return total


def leather_pending(player, preserve_boots):
    material_ids = (COWHIDE, SOFT_LEATHER, HARD_LEATHER)
    if any(item_total(player, item_id) > 0 for item_id in material_ids):
        return True
    for item_id in SELLABLE_PRODUCTS:
        keep = int(preserve_boots) if int(item_id) == LEATHER_BOOTS else 0
        if item_total(player, item_id) > keep:
            return True
    return False


def skill_level(player, name):
    return bridge.skill_level(player, name)


def run_child(script_path, child_args):
    command = [sys.executable, str(script_path)] + list(child_args)
    return subprocess.call(command, cwd=str(bridge.REPO_ROOT))


def phase_enabled(name, start_at, stop_after):
    start_index = PHASES.index(start_at)
    stop_index = PHASES.index(stop_after)
    current_index = PHASES.index(name)
    return start_index <= current_index <= stop_index


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the prepared MrFlame progression phases in order.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--preserve-boots", type=int, default=1)
    parser.add_argument("--target-smithing-level", type=int, default=15)
    parser.add_argument("--target-mining-level", type=int, default=20)
    parser.add_argument("--target-thieving-level", type=int, default=20)
    parser.add_argument("--target-agility-level", type=int, default=50)
    parser.add_argument("--start-at", choices=PHASES, default="leather")
    parser.add_argument("--stop-after", choices=PHASES, default="agility")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    profile = args.profile
    player = bridge.observe(profile)

    if phase_enabled("leather", args.start_at, args.stop_after) and leather_pending(player, args.preserve_boots):
        rc = run_child(LEATHER_RUNNER, [
            "--profile", profile,
            "--preserve-boots", str(args.preserve_boots),
            "--quiet",
        ] if args.quiet else [
            "--profile", profile,
            "--preserve-boots", str(args.preserve_boots),
        ])
        if rc != 0:
            return rc
        player = bridge.observe(profile)

    if phase_enabled("metals", args.start_at, args.stop_after) and (
        skill_level(player, "smithing") < int(args.target_smithing_level)
        or skill_level(player, "mining") < int(args.target_mining_level)
    ):
        child_args = [
            "--profile", profile,
            "--target-smithing-level", str(args.target_smithing_level),
            "--iron-target-mining-level", str(args.target_mining_level),
        ]
        if args.quiet:
            child_args.append("--quiet")
        rc = run_child(METALS_RUNNER, child_args)
        if rc != 0:
            return rc
        player = bridge.observe(profile)

    if phase_enabled("thieving", args.start_at, args.stop_after) and skill_level(player, "thieving") < int(args.target_thieving_level):
        child_args = [
            "--profile", profile,
            "--target-thieving-level", str(args.target_thieving_level),
        ]
        if args.quiet:
            child_args.append("--quiet")
        rc = run_child(THIEVING_RUNNER, child_args)
        if rc != 0:
            return rc
        player = bridge.observe(profile)

    if phase_enabled("agility", args.start_at, args.stop_after) and skill_level(player, "agility") < int(args.target_agility_level):
        child_args = [
            "--profile", profile,
            "--target-agility-level", str(args.target_agility_level),
        ]
        if args.quiet:
            child_args.append("--quiet")
        rc = run_child(AGILITY_RUNNER, child_args)
        if rc != 0:
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
