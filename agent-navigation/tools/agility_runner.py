#!/usr/bin/env python3
"""Adaptive bridge-backed agility course runner.

This runner keeps agility-course execution out of the AI token loop. It uses
normal bridge gameplay tools to walk to each obstacle, click it, prove the
post-state, and write compact JSONL evidence that can later train course-
specific timing/failure models separately from global route heat maps.
"""

import argparse
import datetime as dt
import json
import math
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"
COURSES_PATH = ROOT / "data" / "agility_courses.json"
AGILITY_DIR = ROOT / "data" / "agility"
RUNS_DIR = AGILITY_DIR / "runs"
POLICY_DIR = AGILITY_DIR / "policies"
RUN_PROFILE = ""

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import navdb  # noqa: E402


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def log(message):
    print(message, flush=True)


def tile_key(tile):
    return navdb.tile_str(tile)


def tile_from_player(player):
    return {
        "x": int(player["x"]),
        "y": int(player["y"]),
        "height": int(player.get("height", player.get("h", 0)) or 0),
    }


def tile_distance(a, b):
    if int(a.get("height", 0)) != int(b.get("height", 0)):
        return 10_000
    return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))


def manhattan(a, b):
    if int(a.get("height", 0)) != int(b.get("height", 0)):
        return 10_000
    return abs(int(a["x"]) - int(b["x"])) + abs(int(a["y"]) - int(b["y"]))


def compact_player(player):
    skills = player.get("skills") or {}
    agility = skills.get("agility") or {}
    return {
        "tile": tile_from_player(player),
        "hitpoints": int(player.get("hitpoints", player.get("hp", 0)) or 0),
        "maxHitpoints": int(player.get("maxHitpoints", player.get("maxHp", 0)) or 0),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled", False)),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "agilityLevel": int(agility.get("level", 0) or 0),
        "agilityXp": int(float(agility.get("xp", 0) or 0)),
    }


def call_tool(tool, arguments=None):
    args_json = json.dumps(arguments or {}, separators=(",", ":"))
    env = os.environ.copy()
    if RUN_PROFILE:
        env["RS_PROFILE"] = RUN_PROFILE
    proc = subprocess.run(
        [str(RS_TOOL), tool, args_json],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(tool, proc.stderr.strip() or proc.stdout.strip()))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("{} returned invalid JSON: {}".format(tool, exc))


def player_from(result):
    player = result.get("player")
    if not isinstance(player, dict):
        raise RuntimeError("bridge response did not include player state")
    return player


def observe():
    return player_from(call_tool("observe_state", {}))


def observe_with_tick():
    result = call_tool("observe_state", {})
    return player_from(result), int(result.get("serverTick", 0) or 0)


def response_tick(result, fallback=0):
    return int(result.get("serverTick", fallback) or fallback)


def ensure_run(player, args, current_tick=0):
    if args.no_run:
        return player, current_tick
    if int(player.get("runEnergy", 0) or 0) < args.min_run_energy:
        return player, current_tick
    if bool(player.get("runEnabled", False)):
        return player, current_tick
    result = call_tool("set_run", {"enabled": True})
    return player_from(result), response_tick(result, current_tick)


def write_event(handle, event, data):
    record = {"event": event, "timestamp": utc_now()}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def load_courses():
    with COURSES_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {course["id"]: course for course in data.get("courses", [])}


def policy_path(course_id):
    return POLICY_DIR / "{}.policy.json".format(course_id)


def load_policy(course_id):
    path = policy_path(course_id)
    if not path.exists():
        return {"courseId": course_id, "updatedAt": None, "steps": {}}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_policy(course_id, policy):
    POLICY_DIR.mkdir(parents=True, exist_ok=True)
    policy["courseId"] = course_id
    policy["updatedAt"] = utc_now()
    path = policy_path(course_id)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def variant_key(step, variant):
    return "{}:{}".format(step["id"], variant.get("id", "main"))


def variant_stats(policy, step_id, variant):
    return policy.setdefault("steps", {}).setdefault(step_id, {}).setdefault(
        "variants", {}
    ).setdefault(variant.get("id", "main"), {
        "attempts": 0,
        "successes": 0,
        "failures": 0,
        "avgTicks": None,
        "bestTicks": None,
        "avgSeconds": None,
        "bestSeconds": None,
        "avgRunEnergySpent": None,
        "lastPostTile": None,
        "lastFailureReason": None,
    })


def update_moving_average(current, value, count):
    if current is None:
        return float(value)
    return float(current) + (float(value) - float(current)) / max(1, int(count))


def update_variant(policy, step, variant, success, result):
    stats = variant_stats(policy, step["id"], variant)
    stats["attempts"] += 1
    if success:
        stats["successes"] += 1
        success_count = stats["successes"]
        ticks = int(result.get("ticks") or 0)
        seconds = float(result.get("durationSeconds") or 0.0)
        run_spent = int(result.get("runEnergySpent") or 0)
        stats["avgTicks"] = update_moving_average(stats.get("avgTicks"), ticks, success_count)
        stats["avgSeconds"] = update_moving_average(stats.get("avgSeconds"), seconds, success_count)
        stats["avgRunEnergySpent"] = update_moving_average(
            stats.get("avgRunEnergySpent"), run_spent, success_count)
        stats["bestTicks"] = ticks if stats.get("bestTicks") is None else min(int(stats["bestTicks"]), ticks)
        stats["bestSeconds"] = seconds if stats.get("bestSeconds") is None else min(float(stats["bestSeconds"]), seconds)
        stats["lastPostTile"] = result.get("endTile")
        stats["lastFailureReason"] = None
    else:
        stats["failures"] += 1
        stats["lastFailureReason"] = result.get("reason", "failed")


def variant_score(policy, step, variant, args):
    stats = variant_stats(policy, step["id"], variant)
    attempts = int(stats.get("attempts") or 0)
    successes = int(stats.get("successes") or 0)
    failures = int(stats.get("failures") or 0)
    if attempts == 0:
        return -args.untried_bonus
    avg_ticks = float(stats.get("avgTicks") if stats.get("avgTicks") is not None else args.default_step_ticks)
    failure_rate = failures / max(1, attempts)
    confidence_penalty = args.low_sample_penalty / math.sqrt(max(1, successes))
    return avg_ticks + failure_rate * args.failure_penalty + confidence_penalty


def choose_variant(policy, step, args):
    variants = list(step.get("variants") or [])
    if not variants:
        raise RuntimeError("step {} has no variants".format(step["id"]))
    if len(variants) > 1 and random.random() < args.explore_rate:
        return random.choice(variants), "explore-random"
    scored = sorted(
        ((variant_score(policy, step, variant, args), variant) for variant in variants),
        key=lambda item: (item[0], item[1].get("id", "")),
    )
    return scored[0][1], "adaptive-score"


def nearby_object_override(player, variant):
    wanted_id = int(variant["objectId"])
    wanted_height = int((variant.get("objectTile") or {}).get("height", variant.get("approachTile", {}).get("height", 0)))
    objects = []
    for obj in player.get("nearbyObjects", []):
        obj_id = obj.get("objectId", obj.get("id", -1))
        if int(obj_id) != wanted_id:
            continue
        if int(obj.get("height", obj.get("h", wanted_height)) or 0) != wanted_height:
            continue
        objects.append(obj)
    if not objects:
        return variant
    approach = variant.get("approachTile") or {}
    obj = min(objects, key=lambda item: manhattan(
        {"x": int(item["x"]), "y": int(item["y"]), "height": wanted_height},
        approach,
    ))
    updated = dict(variant)
    updated["objectTile"] = {
        "x": int(obj["x"]),
        "y": int(obj["y"]),
        "height": int(obj.get("height", obj.get("h", wanted_height)) or 0),
    }
    walk_target = obj.get("interactionWalkTarget") or obj.get("nearestInteractionTile")
    if isinstance(walk_target, dict):
        updated["approachTile"] = {
            "x": int(walk_target["x"]),
            "y": int(walk_target["y"]),
            "height": int(walk_target.get("height", 0)),
        }
    return updated


def walk_to(tile, args):
    return call_tool("walk_to_tile_until_arrived", {
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0)),
        "stopDistance": 0,
        "maxTicks": args.walk_max_ticks,
        "maxWalkDistance": args.max_walk_distance,
        "stopOnCombat": True,
        "stopOnStall": True,
    })


def wait_idle(max_ticks):
    return call_tool("wait_until_idle", {
        "maxTicks": int(max_ticks),
        "movement": True,
        "skilling": True,
        "combat": False,
    })


def wait_for_post_state(step, max_ticks, poll_ticks):
    deadline = time.monotonic() + max(1, int(max_ticks)) * 0.75 + 1.0
    last_result = None
    last_player = None
    while time.monotonic() <= deadline:
        last_result = wait_idle(min(max(1, int(poll_ticks)), max(1, int(max_ticks))))
        last_player = player_from(last_result)
        if in_post_state(step, tile_from_player(last_player)):
            return last_result, last_player
        if last_player.get("isDead") or last_player.get("isInCombat"):
            return last_result, last_player
        time.sleep(0.25)
    if last_player is None:
        last_player = observe()
    return last_result, last_player


def in_post_state(step, tile):
    radius = int(step.get("postRadius", 0))
    return any(tile_distance(tile, post) <= radius for post in step.get("postTiles", []))


def step_index_from_state(course, player):
    tile = tile_from_player(player)
    steps = course["steps"]
    start_tile = course["startTile"]
    if tile_distance(tile, start_tile) <= int(course.get("startRadius", 4)):
        return 0
    for index, step in enumerate(steps):
        if int(tile.get("height", 0)) == int(step.get("expectedHeight", 0)):
            for variant in step.get("variants", []):
                if tile_distance(tile, variant["approachTile"]) <= 3:
                    return index
        if in_post_state(step, tile):
            if index == len(steps) - 1:
                return 0
            return min(index + 1, len(steps))
    matching_height = [
        (manhattan(tile, variant["approachTile"]), index)
        for index, step in enumerate(steps)
        if int(tile.get("height", 0)) == int(step.get("expectedHeight", 0))
        for variant in step.get("variants", [])
    ]
    if matching_height:
        return min(matching_height)[1]
    return 0


def recover_to_course(course, args, handle, run_id, lap, reason):
    player = observe()
    tile = tile_from_player(player)
    start = course["startTile"]
    if player.get("isDead") or player.get("isInCombat"):
        write_event(handle, "recovery_blocked", {
            "runId": run_id,
            "lap": lap,
            "reason": reason,
            "state": compact_player(player),
        })
        return False
    if tile_distance(tile, start) <= int(course.get("startRadius", 6)):
        return True
    if int(tile.get("height", 0)) == int(start.get("height", 0)) and manhattan(tile, start) <= args.local_recovery_distance:
        write_event(handle, "recovery_walk", {
            "runId": run_id,
            "lap": lap,
            "reason": reason,
            "from": tile,
            "to": start,
        })
        result = walk_to(start, args)
        return bool(result.get("success")) and not player_from(result).get("isDead")
    if not args.preposition:
        return False
    command = [
        sys.executable,
        str(ROUTE_RUNNER),
        "--to",
        course.get("placeId") or course["id"],
        "--allow-frontier",
        "--direct-if-preview",
        "--probe-toward-target",
        "--run-reserve",
        "auto",
    ]
    if RUN_PROFILE:
        command.extend(["--profile", RUN_PROFILE])
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    write_event(handle, "recovery_route_runner", {
        "runId": run_id,
        "lap": lap,
        "reason": reason,
        "command": command[1:],
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout.strip().splitlines()[-8:],
        "stderr": proc.stderr.strip()[:800],
    })
    return proc.returncode == 0


def run_step(course, step, policy, args, handle, run_id, lap, step_number, current_player=None, current_tick=0):
    if current_player is None:
        player, start_tick = observe_with_tick()
    else:
        player = current_player
        start_tick = current_tick
    player, start_tick = ensure_run(player, args, start_tick)
    variant, decision = choose_variant(policy, step, args)
    variant = nearby_object_override(player, variant)
    approach = variant["approachTile"]
    start_player = compact_player(player)
    start_tile = start_player["tile"]
    start_time = time.monotonic()
    reason = None
    last_tool_result = None

    if player.get("isDead") or player.get("isInCombat"):
        reason = "dead_or_combat"
    elif int(start_tile.get("height", 0)) != int(approach.get("height", 0)):
        reason = "wrong_height"
    elif tile_distance(start_tile, approach) > args.approach_radius:
        walk_result = walk_to(approach, args)
        last_tool_result = walk_result
        player = player_from(walk_result)
        if player.get("isDead") or player.get("isInCombat"):
            reason = "walk_interrupted"
        elif tile_distance(tile_from_player(player), approach) > args.approach_radius:
            reason = "approach_not_reached"
        else:
            variant = nearby_object_override(player, variant)

    interact_result = None
    if reason is None:
        obj_tile = variant["objectTile"]
        interact_result = call_tool("interact_object", {
            "objectId": int(variant["objectId"]),
            "x": int(obj_tile["x"]),
            "y": int(obj_tile["y"]),
            "height": int(obj_tile.get("height", 0)),
            "option": "first",
        })
        last_tool_result = interact_result
        if not interact_result.get("success"):
            refreshed = observe()
            refreshed_variant = nearby_object_override(refreshed, variant)
            if refreshed_variant.get("objectTile") != obj_tile:
                variant = refreshed_variant
                obj_tile = variant["objectTile"]
                interact_result = call_tool("interact_object", {
                    "objectId": int(variant["objectId"]),
                    "x": int(obj_tile["x"]),
                    "y": int(obj_tile["y"]),
                    "height": int(obj_tile.get("height", 0)),
                    "option": "first",
                })
                last_tool_result = interact_result
            if not interact_result.get("success"):
                reason = "interact_failed"

    idle_result = None
    if reason is None:
        idle_result, player = wait_for_post_state(
            step, step.get("maxTicks", args.step_max_ticks), args.post_poll_ticks)
        last_tool_result = idle_result

    end_player = compact_player(player)
    end_tile = end_player["tile"]
    success = reason is None and in_post_state(step, end_tile)
    if not success and reason is None:
        reason = "post_state_not_proven"
    duration = time.monotonic() - start_time
    end_tick = response_tick(last_tool_result or {}, start_tick)
    ticks = max(0, end_tick - start_tick)
    result = {
        "runId": run_id,
        "courseId": course["id"],
        "lap": lap,
        "step": step_number,
        "stepId": step["id"],
        "stepName": step["name"],
        "variantId": variant.get("id", "main"),
        "variantDecision": decision,
        "objectId": int(variant["objectId"]),
        "objectTile": variant["objectTile"],
        "approachTile": approach,
        "startState": start_player,
        "endState": end_player,
        "startTile": start_tile,
        "endTile": end_tile,
        "success": success,
        "reason": reason,
        "ticks": ticks,
        "durationSeconds": round(duration, 3),
        "runEnergySpent": max(0, start_player["runEnergy"] - end_player["runEnergy"]),
        "agilityXpGained": max(0, end_player["agilityXp"] - start_player["agilityXp"]),
        "isAgilityCourse": True,
    }
    update_variant(policy, step, variant, success, result)
    write_event(handle, "step_end", result)
    return success, result, player, end_tick


def run_lap(course, policy, args, handle, run_id, lap):
    start_time = time.monotonic()
    current_player, current_tick = observe_with_tick()
    start_state = compact_player(current_player)
    write_event(handle, "lap_start", {
        "runId": run_id,
        "courseId": course["id"],
        "lap": lap,
        "startState": start_state,
        "isAgilityCourse": True,
    })
    step_index = step_index_from_state(course, current_player)
    step_results = []
    failure_counts = {}
    success = True
    while step_index < len(course["steps"]):
        step = course["steps"][step_index]
        ok, result, current_player, current_tick = run_step(
            course, step, policy, args, handle, run_id, lap, step_index + 1,
            current_player=current_player, current_tick=current_tick)
        step_results.append(result)
        if ok:
            step_index += 1
            continue
        success = False
        if result["endState"]["isDead"] or result["endState"]["isInCombat"]:
            break
        step_failures = failure_counts.get(step["id"], 0) + 1
        failure_counts[step["id"]] = step_failures
        inferred = step_index_from_state(course, current_player)
        if inferred > step_index:
            step_index = inferred
            success = True
            continue
        if step_failures <= args.max_step_retries:
            recover_to_course(course, args, handle, run_id, lap, result.get("reason") or "step_failed")
            current_player, current_tick = observe_with_tick()
            step_index = step_index_from_state(course, current_player)
            continue
        break
    end_state = compact_player(current_player)
    duration = time.monotonic() - start_time
    lap_success = success and step_index >= len(course["steps"]) and not end_state["isDead"] and not end_state["isInCombat"]
    lap_result = {
        "runId": run_id,
        "courseId": course["id"],
        "lap": lap,
        "success": lap_success,
        "durationSeconds": round(duration, 3),
        "stepsCompleted": len([item for item in step_results if item.get("success")]),
        "stepCount": len(step_results),
        "ticks": sum(int(item.get("ticks") or 0) for item in step_results),
        "runEnergySpent": max(0, start_state["runEnergy"] - end_state["runEnergy"]),
        "agilityXpGained": max(0, end_state["agilityXp"] - start_state["agilityXp"]),
        "startState": start_state,
        "endState": end_state,
        "isAgilityCourse": True,
    }
    write_event(handle, "lap_end", lap_result)
    return lap_result


def target_reached(args, player_state):
    if args.target_agility_level is None:
        return False
    return int(player_state.get("agilityLevel", 0) or 0) >= int(args.target_agility_level)


def run_route_after_target(args, handle, run_id):
    if not args.route_after_target:
        return None
    command = [
        sys.executable,
        str(ROUTE_RUNNER),
        "--to",
        args.route_after_target,
        "--allow-frontier",
        "--direct-if-preview",
        "--probe-toward-target",
        "--max-batches",
        str(args.route_max_batches),
        "--run-reserve",
        args.route_run_reserve,
    ]
    if RUN_PROFILE:
        command.extend(["--profile", RUN_PROFILE])
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = {
        "runId": run_id,
        "target": args.route_after_target,
        "command": command[1:],
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout.strip().splitlines()[-20:],
        "stderr": proc.stderr.strip()[:1200],
    }
    write_event(handle, "route_after_target", result)
    return result


def write_summary(path, summary):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(args):
    courses = load_courses()
    if args.course not in courses:
        raise SystemExit("unknown agility course: {}".format(args.course))
    course = courses[args.course]
    policy = load_policy(course["id"])
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    log_path = RUNS_DIR / "{}.jsonl".format(run_id)
    summary_path = RUNS_DIR / "{}.summary.json".format(run_id)

    if args.dry_run:
        print(json.dumps({
            "course": course,
            "policyPath": str(policy_path(course["id"])),
            "runLogPath": str(log_path),
            "currentState": compact_player(observe()),
        }, sort_keys=True))
        return 0

    laps = []
    best_lap = None
    route_result = None
    with log_path.open("a", encoding="utf-8") as handle:
        write_event(handle, "run_start", {
            "runId": run_id,
            "courseId": course["id"],
            "courseName": course["name"],
            "settings": vars(args),
            "initialState": compact_player(observe()),
            "isAgilityCourse": True,
        })
        if args.preposition:
            current = observe()
            if int(tile_from_player(current).get("height", 0)) != int(course["startTile"].get("height", 0)):
                write_event(handle, "recovery_partial_course_start", {
                    "runId": run_id,
                    "courseId": course["id"],
                    "state": compact_player(current),
                    "isAgilityCourse": True,
                })
                run_lap(course, policy, args, handle, run_id, 0)
            recover_to_course(course, args, handle, run_id, 0, "preposition")
        for lap in range(1, args.laps + 1):
            current_state = compact_player(observe())
            if target_reached(args, current_state):
                break
            result = run_lap(course, policy, args, handle, run_id, lap)
            laps.append(result)
            if result["success"]:
                best_lap = result["durationSeconds"] if best_lap is None else min(best_lap, result["durationSeconds"])
            write_policy(course["id"], policy)
            write_summary(summary_path, {
                "runId": run_id,
                "courseId": course["id"],
                "lapsRequested": args.laps,
                "lapsCompleted": len([lap_result for lap_result in laps if lap_result["success"]]),
                "bestLapSeconds": best_lap,
                "targetAgilityLevel": args.target_agility_level,
                "targetReached": target_reached(args, result["endState"]),
                "logPath": str(log_path),
                "policyPath": str(policy_path(course["id"])),
                "laps": laps,
            })
            log("lap {} {} seconds={} ticks={} xp={} best={}".format(
                result["lap"],
                "ok" if result["success"] else "failed",
                result["durationSeconds"],
                result["ticks"],
                result["agilityXpGained"],
                best_lap,
            ))
            if not result["success"] and args.stop_on_failure:
                break
            if result["endState"]["isDead"] and args.stop_on_death:
                break
            if target_reached(args, result["endState"]):
                break
        final_state = compact_player(observe())
        target_success = target_reached(args, final_state)
        success = (
            (args.target_agility_level is not None and target_success)
            or (len(laps) == args.laps and all(item["success"] for item in laps))
        )
        if success and target_success and args.route_after_target:
            route_result = run_route_after_target(args, handle, run_id)
            write_summary(summary_path, {
                "runId": run_id,
                "courseId": course["id"],
                "lapsRequested": args.laps,
                "lapsCompleted": len([lap_result for lap_result in laps if lap_result["success"]]),
                "bestLapSeconds": best_lap,
                "targetAgilityLevel": args.target_agility_level,
                "targetReached": target_success,
                "routeAfterTarget": route_result,
                "logPath": str(log_path),
                "policyPath": str(policy_path(course["id"])),
                "laps": laps,
            })
        write_event(handle, "run_end", {
            "runId": run_id,
            "courseId": course["id"],
            "success": success,
            "lapsRequested": args.laps,
            "lapsCompleted": len([lap_result for lap_result in laps if lap_result["success"]]),
            "bestLapSeconds": best_lap,
            "targetAgilityLevel": args.target_agility_level,
            "targetReached": target_success,
            "routeAfterTarget": route_result,
            "finalState": final_state,
            "logPath": str(log_path),
            "summaryPath": str(summary_path),
            "policyPath": str(policy_path(course["id"])),
            "isAgilityCourse": True,
        })
    return 0 if success else 5


def main(argv=None):
    global RUN_PROFILE
    parser = argparse.ArgumentParser(description="Run adaptive 2006Scape agility-course laps.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "")
    parser.add_argument("--course", default="gnome_agility_course")
    parser.add_argument("--laps", type=int, default=10)
    parser.add_argument("--target-agility-level", type=int)
    parser.add_argument("--route-after-target")
    parser.add_argument("--route-run-reserve", default="auto")
    parser.add_argument("--route-max-batches", type=int, default=80)
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preposition", action="store_true", default=True)
    parser.add_argument("--no-preposition", dest="preposition", action="store_false")
    parser.add_argument("--stop-on-failure", action="store_true", default=True)
    parser.add_argument("--continue-on-failure", dest="stop_on_failure", action="store_false")
    parser.add_argument("--stop-on-death", action="store_true", default=True)
    parser.add_argument("--no-run", action="store_true")
    parser.add_argument("--min-run-energy", type=int, default=8)
    parser.add_argument("--approach-radius", type=int, default=0)
    parser.add_argument("--walk-max-ticks", type=int, default=60)
    parser.add_argument("--step-max-ticks", type=int, default=24)
    parser.add_argument("--post-poll-ticks", type=int, default=1)
    parser.add_argument("--max-walk-distance", type=int, default=48)
    parser.add_argument("--local-recovery-distance", type=int, default=96)
    parser.add_argument("--max-step-retries", type=int, default=1)
    parser.add_argument("--explore-rate", type=float, default=0.0)
    parser.add_argument("--untried-bonus", type=float, default=20.0)
    parser.add_argument("--default-step-ticks", type=float, default=24.0)
    parser.add_argument("--failure-penalty", type=float, default=18.0)
    parser.add_argument("--low-sample-penalty", type=float, default=4.0)
    args = parser.parse_args(argv)
    if args.laps < 1:
        raise SystemExit("--laps must be at least 1")
    if not 0.0 <= args.explore_rate <= 1.0:
        raise SystemExit("--explore-rate must be between 0 and 1")
    RUN_PROFILE = args.profile
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
