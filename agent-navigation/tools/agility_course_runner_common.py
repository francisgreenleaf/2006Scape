#!/usr/bin/env python3
"""Shared wrappers for course-specific agility runners."""

import json
import os
import subprocess
import sys

import bridge_script as bridge


AGILITY_RUNNER = bridge.SCRIPT_DIR / "agility_runner.py"
COURSES_PATH = bridge.ROOT / "data" / "agility_courses.json"

COURSE_SPECS = {
    "gnome": {
        "courseId": "gnome_agility_course",
        "name": "Gnome Agility Course",
        "minLevel": 1,
        "defaultTargetLevel": 35,
        "preferredUntilLevel": 34,
        "safety": "best current low-risk course with live route and course data",
    },
    "pyramid": {
        "courseId": "agility_pyramid_course",
        "name": "Agility Pyramid",
        "minLevel": 30,
        "defaultTargetLevel": 40,
        "preferredUntilLevel": 39,
        "safety": "higher-value mid-level course once the local route and full obstacle sequence are defined",
    },
    "barbarian": {
        "courseId": "barbarian_outpost_agility_course",
        "name": "Barbarian Outpost Agility Course",
        "minLevel": 35,
        "defaultTargetLevel": 50,
        "preferredUntilLevel": 50,
        "safety": "preferred sub-50 course once the player can route to the outpost safely",
    },
}


def load_defined_courses():
    with COURSES_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {course["id"] for course in data.get("courses", [])}


def course_spec(key):
    try:
        return COURSE_SPECS[key]
    except KeyError as exc:
        raise SystemExit("unknown course key: {}".format(key)) from exc


def course_defined(key):
    spec = course_spec(key)
    return spec["courseId"] in load_defined_courses()


def current_agility_level(profile=""):
    return bridge.skill_level(bridge.observe(profile), "agility")


def launch_course(key, args):
    spec = course_spec(key)
    if not course_defined(key):
        raise SystemExit(
            "{} is planned but not yet defined in agent-navigation/data/agility_courses.json (expected course id {}).".format(
                spec["name"], spec["courseId"]
            )
        )
    if current_agility_level(args.profile) < int(spec["minLevel"]):
        raise SystemExit(
            "{} requires Agility {}.".format(spec["name"], spec["minLevel"])
        )

    command = [
        sys.executable,
        str(AGILITY_RUNNER),
        "--profile", args.profile,
        "--course", spec["courseId"],
        "--laps", str(args.laps),
        "--target-agility-level", str(args.target_agility_level or spec["defaultTargetLevel"]),
        "--min-run-energy", str(args.min_run_energy),
        "--route-max-batches", str(args.route_max_batches),
    ]
    if args.quiet:
        command.append("--quiet")
    return subprocess.call(command, cwd=str(bridge.REPO_ROOT), env=os.environ.copy())
