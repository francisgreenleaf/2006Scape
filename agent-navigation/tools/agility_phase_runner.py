#!/usr/bin/env python3
"""Thin wrapper for the current agility progression phase."""

import argparse
import subprocess
import sys

import bridge_script as bridge
from agility_course_runner_common import course_defined, current_agility_level


GNOME_RUNNER = bridge.SCRIPT_DIR / "agility_gnome_course_runner.py"
PYRAMID_RUNNER = bridge.SCRIPT_DIR / "agility_pyramid_runner.py"
BARBARIAN_RUNNER = bridge.SCRIPT_DIR / "agility_barbarian_course_runner.py"


def choose_runner(profile, target_level):
    level = current_agility_level(profile)
    if level >= 35 and course_defined("barbarian"):
        return BARBARIAN_RUNNER
    if level >= 30 and course_defined("pyramid"):
        return PYRAMID_RUNNER
    return GNOME_RUNNER


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the current agility progression phase.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--target-agility-level", type=int, default=50)
    parser.add_argument("--laps", type=int, default=500)
    parser.add_argument("--min-run-energy", type=int, default=8)
    parser.add_argument("--route-max-batches", type=int, default=80)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    runner = choose_runner(args.profile, args.target_agility_level)
    command = [
        sys.executable,
        str(runner),
        "--profile", args.profile,
        "--laps", str(args.laps),
        "--target-agility-level", str(args.target_agility_level),
        "--min-run-energy", str(args.min_run_energy),
        "--route-max-batches", str(args.route_max_batches),
    ]
    if args.quiet:
        command.append("--quiet")

    return subprocess.call(command, cwd=str(bridge.REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
