#!/usr/bin/env python3
"""Thin wrapper for the current agility progression phase."""

import argparse
import subprocess
import sys

import bridge_script as bridge
from agility_course_runner_common import course_defined, current_agility_level
from profile_utils import resolve_profile


GNOME_RUNNER = bridge.SCRIPT_DIR / "agility_gnome_course_runner.py"
PYRAMID_RUNNER = bridge.SCRIPT_DIR / "agility_pyramid_runner.py"
BARBARIAN_RUNNER = bridge.SCRIPT_DIR / "agility_barbarian_outpost_runner.py"


def choose_phase(profile):
    level = current_agility_level(profile)
    if level >= 66 and course_defined("pyramid"):
        return PYRAMID_RUNNER, None
    if level >= 35 and course_defined("barbarian"):
        return BARBARIAN_RUNNER, 65
    return GNOME_RUNNER, 35


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the current agility progression phase.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--target-agility-level", type=int, default=99)
    parser.add_argument("--laps", type=int, default=20000)
    parser.add_argument("--min-run-energy", type=int, default=8)
    parser.add_argument("--route-max-batches", type=int, default=80)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    runner, phase_cap = choose_phase(args.profile)
    phase_target = args.target_agility_level
    if phase_cap is not None:
        phase_target = min(int(args.target_agility_level), int(phase_cap))
    command = [
        sys.executable,
        str(runner),
        "--profile", args.profile,
        "--laps", str(args.laps),
        "--target-agility-level", str(phase_target),
        "--min-run-energy", str(args.min_run_energy),
        "--route-max-batches", str(args.route_max_batches),
    ]
    if args.quiet:
        command.append("--quiet")

    return subprocess.call(command, cwd=str(bridge.REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
