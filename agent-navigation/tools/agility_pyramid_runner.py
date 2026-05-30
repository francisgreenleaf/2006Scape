#!/usr/bin/env python3
"""Run the Agility Pyramid phase when its course definition is available."""

import argparse

from agility_course_runner_common import launch_course


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the Agility Pyramid phase.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--target-agility-level", type=int, default=40)
    parser.add_argument("--laps", type=int, default=500)
    parser.add_argument("--min-run-energy", type=int, default=8)
    parser.add_argument("--route-max-batches", type=int, default=80)
    parser.add_argument("--quiet", action="store_true")
    return launch_course("pyramid", parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
