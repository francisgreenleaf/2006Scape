#!/usr/bin/env python3
"""Catherby fish/cook/bank runner backed by ML1 route definitions."""

import argparse
import datetime as dt
import json
import math
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bridge_script as bridge
from usage_log import log_usage


RUNS_DIR = bridge.ROOT / "data" / "food" / "catherby-runs"
EVIDENCE_DIR = bridge.REPO_ROOT / "agent-navigation" / ".local" / "run-evidence"
RUNNER_CONTROL_DIR = bridge.ROOT / ".local" / "runners"
RUNNER_CONTROL_NAME = "catherby-food"
PASSIVE_TRACE_DIR = bridge.REPO_ROOT / "2006Scape Server" / "data" / "logs" / "player-movement-traces"

SMALL_NET = 303
FISHING_ROD = 307
LOBSTER_POT = 301
HARPOON = 311
FISHING_BAIT = 313

CATHERBY_BANK_TILE = {"x": 2814, "y": 3440, "height": 0}
CATHERBY_SHORE_TILE = {"x": 2853, "y": 3424, "height": 0}
CATHERBY_CAGE_HARPOON_TILE = {"x": 2859, "y": 3427, "height": 0}
CATHERBY_RANGE_TILE = {"x": 2817, "y": 3443, "height": 0}
CATHERBY_RANGE_INTERACTION_TILE = {"x": 2819, "y": 3443, "height": 0}
CATHERBY_FISHING_SHOP_TILE = {"x": 2834, "y": 3440, "height": 0}
CATHERBY_RANGE_OBJECT = {"objectId": 2728, "x": 2817, "y": 3444, "height": 0}
CATHERBY_BANK_TARGET = "catherby_bank"
CATHERBY_SHORE_TARGET = "catherby_fishing_shore"
CATHERBY_RANGE_TARGET = "catherby_range"
CATHERBY_FISHING_SHOP_TARGET = "catherby_fishing_shop"
WAIT_UNTIL_IDLE_SERVER_MAX_TICKS = 250
SERVER_TICK_SECONDS = 0.6

NET_FISHING_SPOTS = [316, 319, 323, 325, 326, 327, 329, 330, 333, 404]
BAIT_FISHING_SPOTS = [316, 326, 327, 330, 332, 404]
CAGE_HARPOON_SPOTS = [312, 321, 324, 405]
LOBSTER_SPOTS = CAGE_HARPOON_SPOTS
HARPOON_SPOTS = CAGE_HARPOON_SPOTS
BUYABLE_SUPPLIES = {SMALL_NET, FISHING_ROD, LOBSTER_POT, HARPOON, FISHING_BAIT}
FISHING_SUPPLY_IDS = {SMALL_NET, FISHING_ROD, LOBSTER_POT, HARPOON, FISHING_BAIT}
SHOP_PRICE_ESTIMATES = {
    SMALL_NET: 5,
    FISHING_ROD: 5,
    HARPOON: 5,
    LOBSTER_POT: 20,
    FISHING_BAIT: 3,
}

RAW_FISH_IDS = [317, 321, 327, 335, 331, 345, 349, 353, 359, 363, 371, 377, 383]
COOKED_FISH_IDS = [315, 319, 325, 333, 329, 347, 351, 355, 361, 365, 373, 379, 385]
BURNT_FISH_IDS = [323, 343, 357, 367, 369, 375, 381, 387, 7954]
RAW_FISH_COOKING_LEVELS = {
    317: 1,   # Raw shrimps
    327: 1,   # Raw sardine
    321: 5,   # Raw anchovies
    345: 5,   # Raw herring
    353: 10,  # Raw mackerel
    335: 15,  # Raw trout
    349: 20,  # Raw pike
    331: 25,  # Raw salmon
    359: 30,  # Raw tuna
    377: 40,  # Raw lobster
    363: 43,  # Raw bass
    371: 50,  # Raw swordfish
    383: 76,  # Raw shark
}
# Current live evidence shows primitive use_item_on_object opens the lobster
# cooking flow reliably. Tuna/swordfish can still opt into the quarantined
# cook_food compatibility path with --compat-cook when testing stale runtimes.
COMPAT_FIRST_COOK_IDS = {359, 371}
FISHING_METHOD_ORDER = [
    {"name": "small_net_shrimp", "fishing": 1, "cooking": 1},
    {"name": "rod_bait_sardine_herring", "fishing": 5, "cooking": 5},
    {"name": "small_net_shrimp_anchovies", "fishing": 15, "cooking": 1},
    {"name": "harpoon_tuna", "fishing": 35, "cooking": 30},
    {"name": "lobster", "fishing": 40, "cooking": 40},
    {"name": "harpoon_tuna_swordfish", "fishing": 50, "cooking": 50},
]
BANK_WITHDRAW_ITEM_BUTTON = 21011


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_event(handle, event, data):
    if handle is None:
        return
    record = {"timestamp": utc_now(), "event": event}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def log(args, message):
    if not args.quiet:
        print(message, flush=True)


def runner_profile_label(args):
    profile = (getattr(args, "profile", "") or os.environ.get("RS_PROFILE", "")).strip()
    return profile or "default"


def runner_control_stem(args):
    profile = runner_profile_label(args)
    if profile == "default":
        return RUNNER_CONTROL_NAME
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in profile).strip("-")
    return "{}-{}".format(RUNNER_CONTROL_NAME, slug or "profile")


def runner_status_path(args):
    return RUNNER_CONTROL_DIR / "{}.status.json".format(runner_control_stem(args))


def runner_primary_stop_path(args):
    return RUNNER_CONTROL_DIR / "{}.stop".format(runner_control_stem(args))


def runner_stop_paths(args):
    paths = [runner_primary_stop_path(args)]
    if runner_profile_label(args) != "default":
        paths.append(RUNNER_CONTROL_DIR / "{}.stop".format(RUNNER_CONTROL_NAME))
    return paths


def runner_stop_requested(args):
    return any(path.exists() for path in runner_stop_paths(args))


def existing_runner_stop_paths(args):
    return [str(path) for path in runner_stop_paths(args) if path.exists()]


def clear_runner_stop_requests(args):
    cleared = []
    for path in runner_stop_paths(args):
        try:
            path.unlink()
            cleared.append(str(path))
        except FileNotFoundError:
            continue
    return cleared


def runner_args_summary(args):
    keys = (
        "profile",
        "cycles",
        "target_fishing_level",
        "target_cooking_level",
        "run_mode",
        "compat_cook",
        "max_fish_ticks",
        "fish_round_max_ticks",
        "max_cook_ticks",
        "cook_interface_ticks",
        "quiet",
    )
    return {key: getattr(args, key, None) for key in keys}


def xp_for_level(level):
    level = max(1, int(level or 1))
    if level <= 1:
        return 0
    points = 0
    for current in range(1, level):
        points += int(current + 300 * (2 ** (current / 7.0)))
    return points // 4


def skill_level_any(player, name):
    try:
        value = bridge.skill_level(player, name)
        if value:
            return value
    except Exception:
        pass
    return int(player.get("{}Level".format(name), 0) or 0)


def skill_xp_any(player, name):
    try:
        value = bridge.skill_xp(player, name)
        if value:
            return value
    except Exception:
        pass
    return int(float(player.get("{}Xp".format(name), 0) or 0))


def skill_progress(player, name, target_level=None):
    level = skill_level_any(player, name)
    xp = skill_xp_any(player, name)
    if level <= 0 and xp <= 0:
        return None
    next_level = max(level + 1, 2)
    next_xp = xp_for_level(next_level)
    payload = {
        "level": level,
        "xp": xp,
        "nextLevel": next_level,
        "nextLevelXp": next_xp,
        "xpToNextLevel": max(0, next_xp - xp),
    }
    if target_level:
        target = max(level, int(target_level))
        target_xp = xp_for_level(target)
        payload.update({
            "targetLevel": target,
            "targetLevelXp": target_xp,
            "xpToTargetLevel": max(0, target_xp - xp),
        })
    return payload


def method_name_for_levels(fishing, cooking):
    fake_player = {
        "skills": {
            "fishing": {"level": int(fishing or 0), "xp": 0},
            "cooking": {"level": int(cooking or 0), "xp": 0},
        }
    }
    return fishing_method(fake_player)["name"]


def next_method_requirement(fishing, cooking):
    current = method_name_for_levels(fishing, cooking)
    current_index = next(
        (idx for idx, item in enumerate(FISHING_METHOD_ORDER) if item["name"] == current),
        0,
    )
    for item in FISHING_METHOD_ORDER[current_index + 1:]:
        if fishing < item["fishing"] or cooking < item["cooking"]:
            return {
                "name": item["name"],
                "fishingLevelRequired": item["fishing"],
                "cookingLevelRequired": item["cooking"],
                "fishingLevelsRemaining": max(0, item["fishing"] - int(fishing or 0)),
                "cookingLevelsRemaining": max(0, item["cooking"] - int(cooking or 0)),
            }
    return None


def parse_utc_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def recent_cycle_rates(run_log_path):
    if not run_log_path:
        return None
    path = Path(run_log_path)
    if not path.exists():
        return None
    bank_events = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-2000:]
    except OSError:
        return None
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "bank_cooked" and isinstance(event.get("player"), dict):
            bank_events.append(event)
    if not bank_events:
        return None

    recent = bank_events[-6:]
    cooked_counts = [
        int(event.get("cookedBefore", 0) or 0)
        for event in bank_events[-5:]
        if int(event.get("cookedBefore", 0) or 0) > 0
    ]
    fishing_deltas = []
    cooking_deltas = []
    cycle_seconds = []
    for previous, current in zip(recent, recent[1:]):
        previous_player = previous.get("player") or {}
        current_player = current.get("player") or {}
        fishing_delta = skill_xp_any(current_player, "fishing") - skill_xp_any(previous_player, "fishing")
        cooking_delta = skill_xp_any(current_player, "cooking") - skill_xp_any(previous_player, "cooking")
        if fishing_delta > 0:
            fishing_deltas.append(fishing_delta)
        if cooking_delta > 0:
            cooking_deltas.append(cooking_delta)
        previous_time = parse_utc_timestamp(previous.get("timestamp"))
        current_time = parse_utc_timestamp(current.get("timestamp"))
        if previous_time and current_time and current_time > previous_time:
            cycle_seconds.append((current_time - previous_time).total_seconds())

    def average(values, ndigits=1):
        if not values:
            return None
        return round(sum(values) / float(len(values)), ndigits)

    return {
        "recentCompletedCycles": len(bank_events),
        "lastBankedCooked": int(bank_events[-1].get("cookedBefore", 0) or 0),
        "recentAvgCookedBanked": average(cooked_counts),
        "recentAvgFishingXpPerCycle": average(fishing_deltas),
        "recentAvgCookingXpPerCycle": average(cooking_deltas),
        "recentAvgSecondsPerCycle": average(cycle_seconds),
    }


def enrich_progress_estimates(progress, rates):
    if not isinstance(progress, dict) or not isinstance(rates, dict):
        return progress
    seconds = rates.get("recentAvgSecondsPerCycle")
    skill_rates = {
        "fishing": rates.get("recentAvgFishingXpPerCycle"),
        "cooking": rates.get("recentAvgCookingXpPerCycle"),
    }
    for skill, rate in skill_rates.items():
        skill_payload = (progress.get("skills") or {}).get(skill)
        if not isinstance(skill_payload, dict) or not rate or rate <= 0:
            continue
        for key, output_key in (
            ("xpToNextLevel", "estimatedCyclesToNextLevel"),
            ("xpToTargetLevel", "estimatedCyclesToTargetLevel"),
        ):
            remaining = skill_payload.get(key)
            if remaining is None:
                continue
            cycles = int(math.ceil(max(0, remaining) / float(rate))) if remaining else 0
            skill_payload[output_key] = cycles
            if seconds:
                skill_payload[output_key.replace("Cycles", "Seconds")] = round(cycles * float(seconds), 1)
    return progress


def runner_progress(player, args_summary=None, run_log_path=None):
    args_summary = args_summary or {}
    fishing = skill_level_any(player, "fishing")
    cooking = skill_level_any(player, "cooking")
    progress = {
        "currentMethodByLevel": method_name_for_levels(fishing, cooking),
        "nextMethodRequirement": next_method_requirement(fishing, cooking),
        "skills": {},
    }
    fishing_progress = skill_progress(player, "fishing", args_summary.get("target_fishing_level"))
    cooking_progress = skill_progress(player, "cooking", args_summary.get("target_cooking_level"))
    if fishing_progress:
        progress["skills"]["fishing"] = fishing_progress
    if cooking_progress:
        progress["skills"]["cooking"] = cooking_progress
    rates = recent_cycle_rates(run_log_path)
    if rates:
        progress["recentCycleRates"] = rates
        enrich_progress_estimates(progress, rates)
    return progress


def write_runner_status(args, status, run_path=None, reason=None, cycle=None, player=None, extra=None):
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "runner": "catherby_food_runner",
        "profile": runner_profile_label(args),
        "status": status,
        "reason": reason,
        "pid": os.getpid(),
        "updatedAt": utc_now(),
        "args": runner_args_summary(args),
        "stopRequested": runner_stop_requested(args),
        "stopFiles": existing_runner_stop_paths(args),
    }
    if run_path is not None:
        payload["runLog"] = str(run_path)
        payload["routeEvidencePath"] = str(EVIDENCE_DIR / "catherby-food.routes.jsonl")
    if cycle is not None:
        payload["cycle"] = cycle
    if player is not None:
        payload["player"] = bridge.compact_player(player, ("fishing", "cooking"))
        payload["progress"] = runner_progress(player, runner_args_summary(args), run_path)
    if extra:
        payload.update(extra)
    path = runner_status_path(args)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def request_runner_stop(args):
    RUNNER_CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    paths = runner_stop_paths(args)
    payload = {
        "runner": "catherby_food_runner",
        "profile": runner_profile_label(args),
        "requestedAt": utc_now(),
        "pid": os.getpid(),
    }
    for path in paths:
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "runner": "catherby_food_runner",
        "profile": runner_profile_label(args),
        "stopRequests": [str(path) for path in paths],
    }, sort_keys=True))
    return 0


def print_runner_status(args):
    path = runner_status_path(args)
    payload = {
        "ok": path.exists(),
        "runner": "catherby_food_runner",
        "profile": runner_profile_label(args),
        "statusPath": str(path),
        "stopRequested": runner_stop_requested(args),
        "stopFiles": existing_runner_stop_paths(args),
    }
    if path.exists():
        try:
            payload["status"] = json.loads(path.read_text(encoding="utf-8"))
            status_player = payload["status"].get("player")
            if isinstance(status_player, dict):
                payload["status"]["progress"] = runner_progress(
                    status_player,
                    payload["status"].get("args") or runner_args_summary(args),
                    payload["status"].get("runLog"),
                )
            updated = payload["status"].get("updatedAt")
            if isinstance(updated, str):
                try:
                    updated_dt = dt.datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    payload["statusAgeSeconds"] = round((dt.datetime.now(dt.timezone.utc) - updated_dt).total_seconds(), 1)
                except ValueError:
                    pass
        except (OSError, json.JSONDecodeError) as exc:
            payload["ok"] = False
            payload["error"] = str(exc)
    elif runner_profile_label(args) == "default":
        payload["knownStatusPaths"] = [
            str(item) for item in sorted(RUNNER_CONTROL_DIR.glob("{}*.status.json".format(RUNNER_CONTROL_NAME)))
        ] if RUNNER_CONTROL_DIR.exists() else []
    print(json.dumps(payload, sort_keys=True))
    return 1 if payload.get("error") else 0


def trace_player_name(args):
    profile = runner_profile_label(args)
    if profile != "default":
        return profile.lower()
    return "mrflame"


def is_active_trace(record):
    activity = record.get("activity") or {}
    return bool(
        record.get("isMoving")
        or record.get("isInCombat")
        or activity.get("moving")
        or activity.get("skilling")
        or activity.get("fishing")
        or activity.get("cooking")
        or activity.get("banking")
        or activity.get("shopping")
        or activity.get("dialogue")
        or activity.get("combat")
    )


def print_efficiency_report(args):
    player_name = trace_player_name(args)
    cutoff_ms = int(time.time() * 1000) - int(args.efficiency_window_minutes * 60 * 1000)
    records = []
    if PASSIVE_TRACE_DIR.exists():
        for path in sorted(PASSIVE_TRACE_DIR.glob("*/{}.jsonl".format(player_name))):
            try:
                with path.open(encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        timestamp_ms = int(record.get("timestampMs") or 0)
                        if timestamp_ms >= cutoff_ms:
                            records.append(record)
            except OSError:
                continue
    records.sort(key=lambda item: int(item.get("timestampMs") or 0))

    active_ms = 0
    idle_ms = 0
    activity_ms = {}
    idle_spans = []
    previous = None
    for record in records:
        if previous is None:
            previous = record
            continue
        delta_ms = max(0, int(record.get("timestampMs") or 0) - int(previous.get("timestampMs") or 0))
        if is_active_trace(previous):
            active_ms += delta_ms
            for key, value in (previous.get("activity") or {}).items():
                if value:
                    activity_ms[key] = activity_ms.get(key, 0) + delta_ms
        else:
            idle_ms += delta_ms
            if delta_ms >= int(args.idle_span_threshold_seconds * 1000):
                idle_spans.append({
                    "seconds": round(delta_ms / 1000.0, 1),
                    "timestamp": previous.get("timestamp"),
                    "tile": previous.get("tile"),
                    "event": previous.get("event"),
                    "serverTick": previous.get("serverTick"),
                })
        previous = record

    total_ms = active_ms + idle_ms
    last = records[-1] if records else None
    payload = {
        "ok": bool(records),
        "runner": "catherby_food_runner",
        "profile": runner_profile_label(args),
        "tracePlayer": player_name,
        "windowMinutes": args.efficiency_window_minutes,
        "records": len(records),
        "activeSeconds": round(active_ms / 1000.0, 1),
        "idleSeconds": round(idle_ms / 1000.0, 1),
        "idlePct": round((idle_ms / total_ms) * 100.0, 1) if total_ms else None,
        "activitySeconds": {key: round(value / 1000.0, 1) for key, value in sorted(activity_ms.items())},
        "idleSpansOverThreshold": idle_spans[-10:],
        "last": {
            "timestamp": last.get("timestamp"),
            "tile": last.get("tile"),
            "freeInventorySlots": last.get("freeInventorySlots"),
            "activity": last.get("activity"),
        } if last else None,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if records else 1


def safe_stop_requested(args, handle, phase, cycle, player, run_path):
    if not runner_stop_requested(args):
        return False
    write_event(handle, "stop_requested", {
        "phase": phase,
        "cycle": cycle,
        "stopFiles": existing_runner_stop_paths(args),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    write_runner_status(args, "stopped", run_path=run_path, reason="stop_requested",
                        cycle=cycle, player=player, extra={"phase": phase})
    return True


def count_any(player, item_ids):
    return sum(bridge.count_inventory_item(player, item_id) for item_id in item_ids)


def cookable_raw_ids(player):
    cooking = bridge.skill_level(player, "cooking")
    return [
        item_id for item_id in RAW_FISH_IDS
        if cooking >= RAW_FISH_COOKING_LEVELS.get(item_id, 1)
    ]


def count_cookable_raw(player):
    return count_any(player, cookable_raw_ids(player))


def first_cookable_raw_item(player):
    cookable = set(cookable_raw_ids(player))
    for item in bridge.inventory(player):
        try:
            item_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if item_id in cookable:
            return item
    return None


def player_tile_text(player):
    return bridge.tile_string(bridge.tile_from_player(player))


def route_define(target, player, args):
    command = [
        sys.executable,
        str(bridge.ROUTE_ML),
        "define",
        "--from",
        player_tile_text(player),
        "--to",
        str(target),
        "--combat-level",
        str(int(player.get("combatLevel", 0) or 0)),
        "--food",
        str(sum(int(item.get("amount", 1) or 1) for item in bridge.inventory(player) if item.get("foodHeal"))),
        "--coins",
        str(bridge.count_inventory_item(player, bridge.COINS)),
        "--run-energy",
        str(int(player.get("runEnergy", 0) or 0)),
        "--planner",
        "fast",
        "--runner-max-batches",
        "3",
        "--max-batch-distance",
        str(args.max_batch_distance),
    ]
    if bool(player.get("runEnabled", False)):
        command.append("--run-enabled")
    proc = subprocess.run(
        command,
        cwd=str(bridge.REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        raise RuntimeError("ML route define failed for {}: {}".format(target, proc.stderr.strip() or proc.stdout.strip()))
    return json.loads(proc.stdout)


def execute_route_definition(definition, target, args, handle):
    route_path = (definition.get("execution") or {}).get("routeDefinitionPath")
    if not route_path:
        raise RuntimeError("ML route definition did not include routeDefinitionPath for {}".format(target))
    command = [
        sys.executable,
        str(bridge.ROUTE_EXECUTOR),
        "--to",
        str(target),
        "--run-mode",
        args.run_mode,
        "--eat-at",
        str(args.eat_at),
        "--evidence-jsonl",
        str(EVIDENCE_DIR / "catherby-food.routes.jsonl"),
        "--route-definition",
        str(route_path),
    ]
    proc = subprocess.run(
        command,
        cwd=str(bridge.REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )
    write_event(handle, "ml_route_execute", {
        "target": str(target),
        "routeId": definition.get("routeId"),
        "status": definition.get("status"),
        "quality": definition.get("quality"),
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout.strip().splitlines()[-6:],
        "stderr": proc.stderr.strip()[:1000],
    })
    return proc.returncode == 0, bridge.observe(args.profile)


def ml_route_to(target, args, handle, accept_bank_area=False):
    player = bridge.observe(args.profile)
    definition = route_define(target, player, args)
    write_event(handle, "ml_route_define", {
        "target": str(target),
        "routeId": definition.get("routeId"),
        "status": definition.get("status"),
        "quality": definition.get("quality"),
        "safety": definition.get("safety"),
        "routeSteps": definition.get("routeSteps"),
    })
    ok, player = execute_route_definition(definition, target, args, handle)
    if ok or (accept_bank_area and bool(player.get("inBankArea", False))):
        return player
    raise RuntimeError("ML route to {} failed; current tile {}".format(target, player_tile_text(player)))


def wait_seconds(max_ticks):
    effective_ticks = min(max(0, int(max_ticks or 0)), WAIT_UNTIL_IDLE_SERVER_MAX_TICKS)
    return round(effective_ticks * SERVER_TICK_SECONDS, 1)


def walk_tile(tile, args, max_ticks=24, max_distance=24, stop_distance=0, handle=None, reason="local_walk"):
    fallback_player = None
    if getattr(args, "run_mode", "auto") != "off":
        try:
            fallback_player = bridge.observe(args.profile)
            fallback_player = bridge.ensure_run(
                fallback_player,
                1,
                profile=args.profile,
                handle=handle,
                reason=reason,
            )
        except Exception as exc:
            if handle is not None:
                write_event(handle, "local_walk_run_enable_error", {
                    "reason": reason,
                    "message": str(exc),
                })
    result = bridge.call_tool("walk_to_tile_until_arrived", {
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0) or 0),
        "stopDistance": int(stop_distance),
        "maxTicks": int(max_ticks),
        "maxWalkDistance": int(max_distance),
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=args.profile)
    try:
        player = bridge.player_from(result)
    except RuntimeError:
        player = fallback_player if fallback_player is not None else bridge.observe(args.profile)
    return player, result


def open_catherby_range_door(args, handle):
    player = bridge.observe(args.profile)
    try:
        player = bridge.open_catherby_south_range_door(player, profile=args.profile, handle=handle,
                                                       reason="catherby_food_runner")
    except bridge.ObjectTransitionError as exc:
        write_event(handle, "range_door_error", {
            "reason": exc.reason,
            "message": exc.message,
            "player": bridge.compact_player(exc.player),
        })
        raise
    return player


def exit_range_building_toward_shore(args, handle):
    player, approach = walk_tile({"x": 2817, "y": 3439, "height": 0}, args, max_ticks=18, max_distance=10,
                                 handle=handle, reason="range_building_exit_approach")
    opened = bridge.call_tool("interact_object", {
        "objectId": 1530,
        "x": 2816,
        "y": 3438,
        "height": 0,
        "option": "open",
    }, profile=args.profile)
    player = bridge._player_from_or(opened, player)
    steps = [
        {"x": 2817, "y": 3438, "height": 0},
        {"x": 2818, "y": 3438, "height": 0},
    ]
    queued = bridge.call_tool("walk_path_steps", {
        "steps": steps,
        "run": bool(player.get("runEnabled", True)),
        "allowObjectTransition": True,
    }, profile=args.profile)
    player = bridge._player_from_or(queued, player)
    waited = bridge.call_tool("wait_until_idle", {
        "maxTicks": 12,
        "movement": True,
        "skilling": False,
        "combat": False,
    }, profile=args.profile)
    player = bridge._player_from_or(waited, player)
    write_event(handle, "range_building_exit", {
        "approachSuccess": bool(approach.get("success")),
        "approachStatus": approach.get("batchStatus"),
        "openSuccess": bool(opened.get("success")),
        "openMessage": opened.get("message"),
        "queueSuccess": bool(queued.get("success")),
        "waitStatus": waited.get("batchStatus"),
        "steps": steps,
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player


def ensure_bank(args, handle):
    player = bridge.observe(args.profile)
    if bool(player.get("inBankArea", False)):
        return player
    if bridge.chebyshev(bridge.tile_from_player(player), CATHERBY_BANK_TILE) <= 12:
        player, result = walk_tile(CATHERBY_BANK_TILE, args, max_ticks=20, max_distance=16,
                                   handle=handle, reason="bank_local_walk")
        write_event(handle, "bank_local_walk", {
            "success": bool(result.get("success")),
            "status": result.get("batchStatus"),
            "message": result.get("message"),
            "player": bridge.compact_player(player),
        })
        if bool(player.get("inBankArea", False)):
            return player
    definition = route_define(CATHERBY_BANK_TARGET, player, args)
    write_event(handle, "bank_route_define", {
        "routeId": definition.get("routeId"),
        "status": definition.get("status"),
        "quality": definition.get("quality"),
        "routeSteps": definition.get("routeSteps"),
    })
    ok, player = execute_route_definition(definition, CATHERBY_BANK_TARGET, args, handle)
    if bool(player.get("inBankArea", False)):
        return player
    player, result = walk_tile(CATHERBY_BANK_TILE, args, max_ticks=30, max_distance=18,
                               handle=handle, reason="bank_direct_recovery")
    write_event(handle, "bank_direct_recovery", {
        "routeExecutorSuccess": bool(ok),
        "success": bool(result.get("success")),
        "status": result.get("batchStatus"),
        "message": result.get("message"),
        "player": bridge.compact_player(player),
    })
    if bool(player.get("inBankArea", False)):
        return player
    open_catherby_range_door(args, handle)
    player, result = walk_tile(CATHERBY_BANK_TILE, args, max_ticks=28, max_distance=18,
                               handle=handle, reason="bank_door_recovery")
    write_event(handle, "bank_door_recovery", {
        "routeExecutorSuccess": bool(ok),
        "success": bool(result.get("success")),
        "status": result.get("batchStatus"),
        "message": result.get("message"),
        "player": bridge.compact_player(player),
    })
    if not bool(player.get("inBankArea", False)):
        raise RuntimeError("could not reach Catherby bank area from {}".format(player_tile_text(player)))
    return player


def ensure_tool(args, handle, item_id):
    player = bridge.observe(args.profile)
    if bridge.count_inventory_item(player, item_id) > 0:
        return player
    player = ensure_bank(args, handle)
    if bridge.count_bank_item(player, item_id) <= 0:
        raise RuntimeError("missing required fishing tool item {}".format(item_id))
    player = ensure_bank_item_withdraw_mode(args, handle, player, "withdraw_tool")
    result = bridge.call_tool("withdraw_bank_items", {"itemId": item_id, "amount": 1}, profile=args.profile)
    player = bridge._player_from_or(result, player)
    write_event(handle, "withdraw_tool", {
        "itemId": item_id,
        "success": bool(result.get("success")),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player


def ensure_bank_item_withdraw_mode(args, handle, player, reason):
    """Force unnoted bank withdrawals before taking fishing tools/supplies."""
    if not bool(player.get("inBankArea", False)):
        player = ensure_bank(args, handle)
    opened = bridge.call_tool("deposit_inventory_items", {"name": "__codex_open_bank_only__"}, profile=args.profile)
    player = bridge._player_from_or(opened, player)
    mode = bridge.call_tool("click_interface_button", {"buttonId": BANK_WITHDRAW_ITEM_BUTTON}, profile=args.profile)
    player = bridge._player_from_or(mode, player)
    write_event(handle, "set_withdraw_item_mode", {
        "reason": reason,
        "buttonId": BANK_WITHDRAW_ITEM_BUTTON,
        "openSuccess": bool(opened.get("success")),
        "modeSuccess": bool(mode.get("success")),
        "message": mode.get("message"),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player


def fishing_method(player):
    fishing = bridge.skill_level(player, "fishing")
    cooking = bridge.skill_level(player, "cooking")
    if fishing >= 50 and cooking >= 50:
        return {
            "name": "harpoon_tuna_swordfish",
            "tool": HARPOON,
            "npcIds": HARPOON_SPOTS,
            "option": "second",
            "bait": None,
        }
    if fishing >= 40 and cooking >= 40:
        return {
            "name": "lobster",
            "tool": LOBSTER_POT,
            "npcIds": LOBSTER_SPOTS,
            "option": "first",
            "bait": None,
        }
    if fishing >= 35 and cooking >= 30:
        return {
            "name": "harpoon_tuna",
            "tool": HARPOON,
            "npcIds": HARPOON_SPOTS,
            "option": "second",
            "bait": None,
        }
    if fishing >= 15:
        return {
            "name": "small_net_shrimp_anchovies",
            "tool": SMALL_NET,
            "npcIds": NET_FISHING_SPOTS,
            "option": "first",
            "bait": None,
        }
    if fishing >= 5 and cooking >= 5:
        return {
            "name": "rod_bait_sardine_herring",
            "tool": FISHING_ROD,
            "npcIds": BAIT_FISHING_SPOTS,
            "option": "second",
            "bait": FISHING_BAIT,
        }
    return {
        "name": "small_net_shrimp",
        "tool": SMALL_NET,
        "npcIds": NET_FISHING_SPOTS,
        "option": "first",
        "bait": None,
    }


def close_interfaces(args, handle, reason):
    result = bridge.call_tool("close_interfaces", {}, profile=args.profile)
    player = bridge._player_from_or(result, bridge.observe(args.profile))
    write_event(handle, "close_interfaces", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player


def buy_supplies(args, handle, requests):
    if not args.auto_buy_supplies:
        raise RuntimeError("missing required fishing supplies and auto-buy is disabled")
    player = bridge.observe(args.profile)
    estimated_cost = sum(SHOP_PRICE_ESTIMATES.get(int(item_id), 100) * int(amount) for item_id, amount in requests)
    if bridge.count_inventory_item(player, bridge.COINS) < estimated_cost:
        player = ensure_bank(args, handle)
        if bridge.count_inventory_item(player, bridge.COINS) < estimated_cost:
            result = bridge.call_tool("withdraw_bank_items", {
                "itemId": bridge.COINS,
                "amount": max(
                    estimated_cost - bridge.count_inventory_item(player, bridge.COINS),
                    args.supply_coin_float - bridge.count_inventory_item(player, bridge.COINS),
                ),
            }, profile=args.profile)
            player = bridge._player_from_or(result, player)
            write_event(handle, "withdraw_supply_coins", {
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "player": bridge.compact_player(player, ("fishing", "cooking")),
            })

    try:
        player = ml_route_to(CATHERBY_FISHING_SHOP_TARGET, args, handle)
    except RuntimeError:
        player, result = walk_tile(CATHERBY_FISHING_SHOP_TILE, args, max_ticks=80, max_distance=48, stop_distance=3,
                                   handle=handle, reason="fishing_shop_local_walk")
        write_event(handle, "supply_shop_direct_recovery", {
            "success": bool(result.get("success")),
            "status": result.get("batchStatus"),
            "message": result.get("message"),
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })

    opened = bridge.call_tool("open_nearest_shop", {
        "name": args.supply_shop_name,
        "maxDistance": args.shop_max_distance,
    }, profile=args.profile)
    player = bridge._player_from_or(opened, player)
    write_event(handle, "open_supply_shop", {
        "success": bool(opened.get("success")),
        "message": opened.get("message"),
        "shop": (opened.get("player") or {}).get("shop"),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    if not opened.get("success"):
        raise RuntimeError("could not open Catherby fishing shop: {}".format(opened.get("message", "")))

    for item_id, amount in requests:
        bought = bridge.call_tool("buy_shop_item", {"itemId": int(item_id), "amount": int(amount)}, profile=args.profile)
        player = bridge._player_from_or(bought, player)
        write_event(handle, "buy_supply", {
            "itemId": int(item_id),
            "amount": int(amount),
            "success": bool(bought.get("success")),
            "message": bought.get("message"),
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
        if not bought.get("success"):
            raise RuntimeError("could not buy supply item {}: {}".format(item_id, bought.get("message", "")))

    return close_interfaces(args, handle, "after_supply_shop")


def ensure_inventory_quantity(args, handle, item_id, desired_amount):
    player = bridge.observe(args.profile)
    carried = bridge.count_inventory_item(player, item_id)
    if carried >= desired_amount:
        return player

    if bridge.count_bank_item(player, item_id) > 0 or bool(player.get("inBankArea", False)):
        player = ensure_bank(args, handle)
        carried = bridge.count_inventory_item(player, item_id)
        missing = max(0, int(desired_amount) - carried)
        banked = bridge.count_bank_item(player, item_id)
        if missing > 0 and banked > 0:
            player = ensure_bank_item_withdraw_mode(args, handle, player, "withdraw_supply_item")
            result = bridge.call_tool("withdraw_bank_items", {
                "itemId": int(item_id),
                "amount": min(missing, banked),
            }, profile=args.profile)
            player = bridge._player_from_or(result, player)
            write_event(handle, "withdraw_supply_item", {
                "itemId": int(item_id),
                "desiredAmount": int(desired_amount),
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "player": bridge.compact_player(player, ("fishing", "cooking")),
            })
            carried = bridge.count_inventory_item(player, item_id)
            if carried >= desired_amount:
                return player

    if int(item_id) not in BUYABLE_SUPPLIES:
        raise RuntimeError("missing required fishing supply item {}".format(item_id))

    buy_amount = max(1, int(desired_amount) - bridge.count_inventory_item(player, item_id))
    if int(item_id) == FISHING_BAIT:
        buy_amount = max(buy_amount, int(args.bait_buy_amount))
    player = buy_supplies(args, handle, [(item_id, buy_amount)])
    if bridge.count_inventory_item(player, item_id) < desired_amount:
        raise RuntimeError("could not acquire required fishing supply item {}".format(item_id))
    return player


def ensure_method_supplies(args, handle, method):
    desired = [(int(method["tool"]), 1)]
    if method.get("bait"):
        desired.append((int(method["bait"]), max(1, int(args.bait_inventory_target))))

    player = bridge.observe(args.profile)
    if any(bridge.count_inventory_item(player, item_id) < amount and bridge.count_bank_item(player, item_id) > 0
           for item_id, amount in desired):
        player = ensure_bank(args, handle)
        player = ensure_bank_item_withdraw_mode(args, handle, player, "withdraw_method_supplies")
        for item_id, amount in desired:
            missing = max(0, amount - bridge.count_inventory_item(player, item_id))
            banked = bridge.count_bank_item(player, item_id)
            if missing <= 0 or banked <= 0:
                continue
            result = bridge.call_tool("withdraw_bank_items", {
                "itemId": item_id,
                "amount": min(missing, banked),
            }, profile=args.profile)
            player = bridge._player_from_or(result, player)
            write_event(handle, "withdraw_supply_item", {
                "itemId": item_id,
                "desiredAmount": amount,
                "success": bool(result.get("success")),
                "message": result.get("message"),
                "player": bridge.compact_player(player, ("fishing", "cooking")),
            })

    requests = []
    for item_id, amount in desired:
        missing = max(0, amount - bridge.count_inventory_item(player, item_id))
        if missing <= 0:
            continue
        if item_id not in BUYABLE_SUPPLIES:
            raise RuntimeError("missing required fishing supply item {}".format(item_id))
        if item_id == FISHING_BAIT:
            missing = max(missing, int(args.bait_buy_amount))
        requests.append((item_id, missing))

    if requests:
        player = buy_supplies(args, handle, requests)

    for item_id, amount in desired:
        if bridge.count_inventory_item(player, item_id) < amount:
            raise RuntimeError("could not acquire required fishing supply item {}".format(item_id))

    if requests:
        cleanup_needed = bridge.count_inventory_item(player, bridge.COINS) > 0
        required = {item_id for item_id, _ in desired}
        cleanup_needed = cleanup_needed or any(
            bridge.count_inventory_item(player, item_id) > 0
            for item_id in FISHING_SUPPLY_IDS - required
        )
        if cleanup_needed:
            player = ensure_bank(args, handle)
            write_event(handle, "post_purchase_supply_cleanup_bank", {
                "method": method["name"],
                "requests": requests,
                "player": bridge.compact_player(player, ("fishing", "cooking")),
            })

    return cleanup_unused_supplies(args, handle, player, method)


def cleanup_unused_supplies(args, handle, player, method):
    if not bool(player.get("inBankArea", False)):
        return player
    required = {int(method["tool"])}
    if method.get("bait"):
        required.add(int(method["bait"]))
    deposit_ids = [
        item_id for item_id in sorted(FISHING_SUPPLY_IDS - required)
        if bridge.count_inventory_item(player, item_id) > 0
    ]
    if deposit_ids:
        result = bridge.call_tool("deposit_inventory_items", {"itemIds": deposit_ids}, profile=args.profile)
        player = bridge._player_from_or(result, player)
        write_event(handle, "deposit_unused_fishing_supplies", {
            "itemIds": deposit_ids,
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "method": method["name"],
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
    if bridge.count_inventory_item(player, bridge.COINS) > 0:
        result = bridge.call_tool("deposit_excess_coins", {"keepAmount": 0}, profile=args.profile)
        player = bridge._player_from_or(result, player)
        write_event(handle, "deposit_supply_coins", {
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "method": method["name"],
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
    return player


def fishing_shore_tile(method):
    if isinstance(method, dict) and method.get("name") in ("harpoon_tuna", "lobster", "harpoon_tuna_swordfish"):
        return CATHERBY_CAGE_HARPOON_TILE
    return CATHERBY_SHORE_TILE


def ensure_shore(args, handle, method=None):
    target_tile = fishing_shore_tile(method)
    player = bridge.observe(args.profile)
    if bridge.chebyshev(bridge.tile_from_player(player), target_tile) <= 1:
        return player
    if bridge.chebyshev(bridge.tile_from_player(player), target_tile) <= 60:
        player, result = walk_tile(target_tile, args, max_ticks=80, max_distance=48,
                                   handle=handle, reason="shore_local_walk")
        write_event(handle, "shore_local_walk", {
            "method": method.get("name") if isinstance(method, dict) else None,
            "targetTile": target_tile,
            "success": bool(result.get("success")),
            "status": result.get("batchStatus"),
            "message": result.get("message"),
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
        if bridge.chebyshev(bridge.tile_from_player(player), target_tile) <= 1:
            return player
    try:
        player = ml_route_to(CATHERBY_SHORE_TARGET, args, handle)
    except RuntimeError:
        player = exit_range_building_toward_shore(args, handle)
        player, result = walk_tile(target_tile, args, max_ticks=80, max_distance=48, stop_distance=2,
                                   handle=handle, reason="shore_door_recovery")
        write_event(handle, "shore_door_recovery", {
            "method": method.get("name") if isinstance(method, dict) else None,
            "targetTile": target_tile,
            "success": bool(result.get("success")),
            "status": result.get("batchStatus"),
            "message": result.get("message"),
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
        if bridge.chebyshev(bridge.tile_from_player(player), target_tile) > 4:
            raise
        return player
    if bridge.chebyshev(bridge.tile_from_player(player), target_tile) <= 1:
        return player
    player, result = walk_tile(target_tile, args, max_ticks=24, max_distance=12,
                               handle=handle, reason="shore_exact_recovery")
    write_event(handle, "shore_exact_recovery", {
        "method": method.get("name") if isinstance(method, dict) else None,
        "targetTile": target_tile,
        "success": bool(result.get("success")),
        "status": result.get("batchStatus"),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    if bridge.chebyshev(bridge.tile_from_player(player), target_tile) > 1:
        raise RuntimeError("could not reach exact Catherby fishing tile from {}".format(player_tile_text(player)))
    return player


def find_usable_range(args, handle, player, reason):
    found = bridge.call_tool("find_nearest_object", {
        "objectIds": [CATHERBY_RANGE_OBJECT["objectId"]],
        "maxDistance": max(int(args.object_max_distance), 8),
    }, profile=args.profile)
    range_object = found.get("object") if isinstance(found, dict) else None
    ready = False
    if isinstance(range_object, dict):
        ready = bool(range_object.get("interactionInRange", False))
    write_event(handle, "range_readiness", {
        "reason": reason,
        "success": bool(found.get("success")),
        "ready": ready,
        "object": range_object,
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return ready, range_object


def walk_to_range_interaction_tile(args, handle, player, range_object, reason):
    if not isinstance(range_object, dict) or not bool(range_object.get("reachable", False)):
        return player, False
    target = range_object.get("interactionWalkTarget") or range_object.get("nearestInteractionTile")
    if not isinstance(target, dict):
        return player, False
    player, result = walk_tile(target, args, max_ticks=30, max_distance=16,
                               handle=handle, reason="range_interaction_tile_recovery")
    write_event(handle, "range_interaction_tile_recovery", {
        "reason": reason,
        "object": range_object,
        "target": target,
        "success": bool(result.get("success")),
        "status": result.get("batchStatus"),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player, True


def fish_until_full(args, handle, run_path=None, cycle=None):
    player = bridge.observe(args.profile)
    method = fishing_method(player)
    player = ensure_method_supplies(args, handle, method)
    player = ensure_shore(args, handle, method)
    write_runner_status(args, "running", run_path=run_path, reason="fishing_at_shore",
                        cycle=cycle, player=player, extra={"phase": "fishing"})
    method = fishing_method(player)
    total_ticks = 0
    rounds = 0
    no_progress = 0
    while total_ticks < args.max_fish_ticks and int(player.get("freeInventorySlots", 0) or 0) > 0:
        next_method = fishing_method(player)
        if next_method["name"] != method["name"]:
            carried_raw = count_any(player, RAW_FISH_IDS)
            if carried_raw > 0:
                write_event(handle, "fishing_method_switch_deferred", {
                    "fromMethod": method["name"],
                    "toMethod": next_method["name"],
                    "rawCarried": carried_raw,
                    "player": bridge.compact_player(player, ("fishing", "cooking")),
                })
            else:
                write_event(handle, "fishing_method_switch", {
                    "fromMethod": method["name"],
                    "toMethod": next_method["name"],
                    "player": bridge.compact_player(player, ("fishing", "cooking")),
                })
                method = next_method
                player = ensure_method_supplies(args, handle, method)
                player = ensure_shore(args, handle, method)
        before_free = int(player.get("freeInventorySlots", 0) or 0)
        before_raw = count_any(player, RAW_FISH_IDS)
        found = bridge.call_tool("find_nearest_npc", {
            "npcIds": method["npcIds"],
            "maxDistance": args.npc_max_distance,
            "reachable": True,
        }, profile=args.profile)
        if not found.get("success"):
            player = ensure_shore(args, handle, method)
            found = bridge.call_tool("find_nearest_npc", {
                "npcIds": method["npcIds"],
                "maxDistance": args.npc_max_distance,
                "reachable": True,
            }, profile=args.profile)
        if not found.get("success"):
            raise RuntimeError(found.get("message", "no Catherby fishing spot found"))
        npc = found.get("npc") or {}
        interacted = bridge.call_tool("interact_npc", {
            "npcIndex": npc.get("npcIndex"),
            "option": method["option"],
            "requireReachable": True,
        }, profile=args.profile)
        fish_round_ticks = min(
            max(1, int(args.fish_round_max_ticks)),
            max(1, args.max_fish_ticks - total_ticks),
        )
        write_runner_status(args, "running", run_path=run_path, reason="fishing_wait",
                            cycle=cycle, player=player, extra={
                                "phase": "fishing",
                                "fishRound": rounds + 1,
                                "method": method["name"],
                                "rawBefore": before_raw,
                                "freeBefore": before_free,
                                "expectedWaitTicks": fish_round_ticks,
                                "expectedWaitSeconds": wait_seconds(fish_round_ticks),
                            })
        wait = bridge.call_tool("wait_until_idle", {
            "maxTicks": fish_round_ticks,
            "movement": True,
            "skilling": True,
            "combat": False,
        }, profile=args.profile)
        player = bridge._player_from_or(wait, player)
        total_ticks += max(1, int(wait.get("batchTicks", 1) or 1))
        rounds += 1
        after_free = int(player.get("freeInventorySlots", 0) or 0)
        after_raw = count_any(player, RAW_FISH_IDS)
        made_progress = after_free < before_free or after_raw > before_raw
        no_progress = 0 if made_progress else no_progress + 1
        write_event(handle, "fish_round", {
            "round": rounds,
            "method": method["name"],
            "npc": npc,
            "interactSuccess": bool(interacted.get("success")),
            "waitStatus": wait.get("batchStatus"),
            "rawBefore": before_raw,
            "rawAfter": after_raw,
            "freeBefore": before_free,
            "freeAfter": after_free,
            "maxWaitTicks": fish_round_ticks,
            "madeProgress": made_progress,
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
        write_runner_status(args, "running", run_path=run_path, reason="fishing_round",
                            cycle=cycle, player=player, extra={
                                "phase": "fishing",
                                "fishRound": rounds,
                                "method": method["name"],
                                "madeProgress": made_progress,
                                "rawAfter": after_raw,
                                "freeAfter": after_free,
                            })
        if no_progress >= args.max_no_progress_rounds:
            raise RuntimeError("fishing made no inventory progress for {} rounds".format(no_progress))
    return player


def ensure_range(args, handle):
    player = bridge.observe(args.profile)
    ready, range_object = find_usable_range(args, handle, player, "initial")
    if ready:
        return player
    player, walked = walk_to_range_interaction_tile(args, handle, player, range_object, "initial")
    if walked:
        ready, range_object = find_usable_range(args, handle, player, "after_initial_interaction_walk")
        if ready:
            return player
    if bridge.chebyshev(bridge.tile_from_player(player), CATHERBY_RANGE_INTERACTION_TILE) <= 60:
        player, result = walk_tile(CATHERBY_RANGE_INTERACTION_TILE, args, max_ticks=80, max_distance=48,
                                   handle=handle, reason="range_local_walk")
        write_event(handle, "range_local_walk", {
            "success": bool(result.get("success")),
            "status": result.get("batchStatus"),
            "message": result.get("message"),
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
        ready, range_object = find_usable_range(args, handle, player, "after_local_walk")
        if ready:
            return player
    try:
        player = ml_route_to(CATHERBY_RANGE_TARGET, args, handle)
    except RuntimeError:
        player = bridge.observe(args.profile)
        write_event(handle, "range_ml_route_failed", {
            "target": CATHERBY_RANGE_TARGET,
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })

    ready, range_object = find_usable_range(args, handle, player, "after_ml")
    if ready:
        return player
    player, walked = walk_to_range_interaction_tile(args, handle, player, range_object, "after_ml")
    if walked:
        ready, range_object = find_usable_range(args, handle, player, "after_ml_interaction_walk")
        if ready:
            return player

    player, result = walk_tile(CATHERBY_RANGE_TILE, args, max_ticks=80, max_distance=48, stop_distance=2,
                               handle=handle, reason="range_direct_recovery")
    write_event(handle, "range_direct_recovery", {
        "success": bool(result.get("success")),
        "status": result.get("batchStatus"),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    ready, range_object = find_usable_range(args, handle, player, "after_direct")
    if ready:
        return player
    player, walked = walk_to_range_interaction_tile(args, handle, player, range_object, "after_direct")
    if walked:
        ready, range_object = find_usable_range(args, handle, player, "after_direct_interaction_walk")
        if ready:
            return player

    open_catherby_range_door(args, handle)
    player, result = walk_tile(CATHERBY_RANGE_TILE, args, max_ticks=30, max_distance=24, stop_distance=2,
                               handle=handle, reason="range_door_recovery")
    write_event(handle, "range_door_recovery", {
        "success": bool(result.get("success")),
        "status": result.get("batchStatus"),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    ready, range_object = find_usable_range(args, handle, player, "after_door")
    if not ready:
        player, walked = walk_to_range_interaction_tile(args, handle, player, range_object, "after_door")
        if walked:
            ready, range_object = find_usable_range(args, handle, player, "after_door_interaction_walk")
    if not ready:
        raise RuntimeError("could not reach usable Catherby range from {}".format(player_tile_text(player)))
    return player


def primitive_cook_once(args, handle, player, run_path=None, cycle=None, cook_round=None):
    food = first_cookable_raw_item(player)
    if food is None:
        return player, True
    before_raw = count_any(player, RAW_FISH_IDS)
    before_xp = bridge.skill_xp(player, "cooking")
    used = bridge.call_tool("use_item_on_object", {
        "itemId": int(food["id"]),
        "objectId": CATHERBY_RANGE_OBJECT["objectId"],
        "x": CATHERBY_RANGE_OBJECT["x"],
        "y": CATHERBY_RANGE_OBJECT["y"],
        "height": CATHERBY_RANGE_OBJECT["height"],
    }, profile=args.profile)
    interface_wait = None
    if int(args.cook_interface_ticks) > 0:
        interface_wait = bridge.call_tool("wait_ticks", {"ticks": int(args.cook_interface_ticks)}, profile=args.profile)
    button = bridge.call_tool("click_interface_button", {"buttonId": 53149}, profile=args.profile)
    write_runner_status(args, "running", run_path=run_path, reason="cooking_wait",
                        cycle=cycle, player=player, extra={
                            "phase": "cooking",
                            "cookRound": cook_round,
                            "rawBefore": before_raw,
                            "expectedWaitTicks": int(args.max_cook_ticks),
                            "expectedWaitSeconds": wait_seconds(args.max_cook_ticks),
                        })
    wait = bridge.call_tool("wait_until_idle", {
        "maxTicks": args.max_cook_ticks,
        "movement": True,
        "skilling": True,
        "combat": False,
    }, profile=args.profile)
    player = bridge._player_from_or(wait, player)
    after_raw = count_any(player, RAW_FISH_IDS)
    after_xp = bridge.skill_xp(player, "cooking")
    made_progress = after_raw < before_raw or after_xp != before_xp
    write_event(handle, "cook_primitive_round", {
        "food": food,
        "useSuccess": bool(used.get("success")),
        "interfaceWait": {
            "success": bool(interface_wait.get("success")),
            "ticks": int(
                interface_wait.get("ticks")
                or interface_wait.get("waitedTicks")
                or interface_wait.get("batchTicks")
                or 0
            ),
            "message": interface_wait.get("message"),
        } if isinstance(interface_wait, dict) else None,
        "buttonSuccess": bool(button.get("success")),
        "waitStatus": wait.get("batchStatus"),
        "rawBefore": before_raw,
        "rawAfter": after_raw,
        "cookingXpBefore": before_xp,
        "cookingXpAfter": after_xp,
        "madeProgress": made_progress,
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player, made_progress


def compatibility_cook_batch(args, handle, player):
    food = first_cookable_raw_item(player)
    if food is None:
        return player, True
    raw = bridge.count_inventory_item(player, int(food["id"]))
    before_raw = raw
    before_xp = bridge.skill_xp(player, "cooking")
    started = bridge.call_tool("cook_food", {
        "itemId": int(food["id"]),
        "amount": raw,
        "maxDistance": args.object_max_distance,
        "legacyCompatibility": True,
    }, profile=args.profile)
    wait = bridge.call_tool("wait_until_idle", {
        "maxTicks": args.max_cook_ticks,
        "movement": True,
        "skilling": True,
        "combat": False,
    }, profile=args.profile)
    player = bridge._player_from_or(wait, player)
    made_progress = count_any(player, RAW_FISH_IDS) < before_raw or bridge.skill_xp(player, "cooking") != before_xp
    write_event(handle, "cook_compat_round", {
        "startSuccess": bool(started.get("success")),
        "waitStatus": wait.get("batchStatus"),
        "rawBefore": before_raw,
        "rawAfter": count_any(player, RAW_FISH_IDS),
        "cookingXpBefore": before_xp,
        "cookingXpAfter": bridge.skill_xp(player, "cooking"),
        "madeProgress": made_progress,
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player, made_progress


def should_use_compat_cook_first(args, player):
    if args.compat_cook == "always":
        return True
    if args.compat_cook != "auto":
        return False
    food = first_cookable_raw_item(player)
    if food is None:
        return False
    try:
        return int(food.get("id")) in COMPAT_FIRST_COOK_IDS
    except (TypeError, ValueError):
        return False


def cook_inventory(args, handle, run_path=None, cycle=None):
    player = ensure_range(args, handle)
    no_progress = 0
    rounds = 0
    while count_cookable_raw(player) > 0:
        if should_use_compat_cook_first(args, player):
            player, made_progress = compatibility_cook_batch(args, handle, player)
            rounds += 1
            write_runner_status(args, "running", run_path=run_path, reason="cook_round",
                                cycle=cycle, player=player, extra={
                                    "phase": "cooking",
                                    "cookRound": rounds,
                                    "madeProgress": made_progress,
                                    "rawRemaining": count_any(player, RAW_FISH_IDS),
                                })
            no_progress = 0 if made_progress else no_progress + 1
            if no_progress >= args.max_no_progress_rounds:
                raise RuntimeError("compatibility cooking made no progress for {} rounds".format(no_progress))
            continue
        player, made_progress = primitive_cook_once(
            args,
            handle,
            player,
            run_path=run_path,
            cycle=cycle,
            cook_round=rounds + 1,
        )
        rounds += 1
        write_runner_status(args, "running", run_path=run_path, reason="cook_round",
                            cycle=cycle, player=player, extra={
                                "phase": "cooking",
                                "cookRound": rounds,
                                "madeProgress": made_progress,
                                "rawRemaining": count_any(player, RAW_FISH_IDS),
                            })
        if made_progress:
            no_progress = 0
            continue
        no_progress += 1
        if args.compat_cook == "auto":
            player, made_progress = compatibility_cook_batch(args, handle, player)
            rounds += 1
            write_runner_status(args, "running", run_path=run_path, reason="cook_round_fallback",
                                cycle=cycle, player=player, extra={
                                    "phase": "cooking",
                                    "cookRound": rounds,
                                    "madeProgress": made_progress,
                                    "rawRemaining": count_any(player, RAW_FISH_IDS),
                                })
            if made_progress:
                no_progress = 0
                continue
            no_progress += 1
        if no_progress >= args.max_no_progress_rounds:
            raise RuntimeError("cooking made no progress for {} rounds".format(no_progress))
    remaining_raw = count_any(player, RAW_FISH_IDS)
    if remaining_raw > 0:
        write_event(handle, "cook_uncookable_raw_deferred", {
            "rawRemaining": remaining_raw,
            "cookableRawRemaining": count_cookable_raw(player),
            "cookingLevel": bridge.skill_level(player, "cooking"),
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
    return player


def drop_burnt(args, handle):
    player = bridge.observe(args.profile)
    burnt = count_any(player, BURNT_FISH_IDS)
    if burnt <= 0:
        return player
    result = bridge.call_tool("drop_inventory_items", {"itemIds": BURNT_FISH_IDS}, profile=args.profile)
    player = bridge._player_from_or(result, player)
    write_event(handle, "drop_burnt", {
        "burntBefore": burnt,
        "success": bool(result.get("success")),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player


def bank_cooked(args, handle):
    player = ensure_bank(args, handle)
    cooked = count_any(player, COOKED_FISH_IDS)
    if cooked <= 0:
        return player
    player, summary = bridge.execute_bank_policy(
        player,
        profile=args.profile,
        handle=handle,
        reason="catherby_food_runner_bank_cooked",
        deposit_all_ids=COOKED_FISH_IDS,
    )
    write_event(handle, "bank_cooked", {
        "cookedBefore": cooked,
        "plannedActions": len(summary.get("actions", [])),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player


def bank_raw_fish(args, handle, reason):
    player = bridge.observe(args.profile)
    raw = count_any(player, RAW_FISH_IDS)
    if raw <= 0:
        return player
    player = ensure_bank(args, handle)
    result = bridge.call_tool("deposit_inventory_items", {"itemIds": RAW_FISH_IDS}, profile=args.profile)
    player = bridge._player_from_or(result, player)
    write_event(handle, "bank_raw_fish", {
        "reason": reason,
        "rawBefore": raw,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("fishing", "cooking")),
    })
    return player


def targets_met(player, args):
    if args.target_fishing_level and bridge.skill_level(player, "fishing") < args.target_fishing_level:
        return False
    if args.target_cooking_level and bridge.skill_level(player, "cooking") < args.target_cooking_level:
        return False
    return bool(args.target_fishing_level or args.target_cooking_level)


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    try:
        player = bridge.observe(args.profile)
        cleared_stop_requests = clear_runner_stop_requests(args)
        write_event(handle, "run_start", {
            "args": vars(args),
            "clearedStopRequests": cleared_stop_requests,
            "player": bridge.compact_player(player, ("fishing", "cooking")),
        })
        write_runner_status(args, "running", run_path=run_path, reason="started",
                            cycle=0, player=player, extra={"phase": "started"})
        cycles = 0
        stopped_reason = None
        while cycles < args.cycles:
            player = bridge.observe(args.profile)
            write_runner_status(args, "running", run_path=run_path, reason="cycle_start",
                                cycle=cycles, player=player, extra={"phase": "cycle_start"})
            if safe_stop_requested(args, handle, "cycle_start", cycles, player, run_path):
                stopped_reason = "stop_requested"
                break
            if targets_met(player, args):
                stopped_reason = "target_levels"
                break
            raw = count_any(player, RAW_FISH_IDS)
            cooked = count_any(player, COOKED_FISH_IDS)
            burnt = count_any(player, BURNT_FISH_IDS)
            if raw > 0:
                log(args, "recovering partial inventory: raw={} cooked={} burnt={}".format(raw, cooked, burnt))
                write_runner_status(args, "running", run_path=run_path, reason="recover_raw",
                                    cycle=cycles, player=player, extra={"phase": "cooking"})
                player = cook_inventory(args, handle, run_path=run_path, cycle=cycles)
                player = drop_burnt(args, handle)
                player = bank_cooked(args, handle)
                player = bank_raw_fish(args, handle, "recover_raw_leftovers")
                write_runner_status(args, "running", run_path=run_path, reason="recover_raw_banked",
                                    cycle=cycles, player=player, extra={"phase": "banked"})
                if safe_stop_requested(args, handle, "after_recover_raw_bank", cycles, player, run_path):
                    stopped_reason = "stop_requested"
                    break
                continue
            if cooked > 0 or burnt > 0:
                log(args, "banking partial inventory: cooked={} burnt={}".format(cooked, burnt))
                write_runner_status(args, "running", run_path=run_path, reason="recover_cooked",
                                    cycle=cycles, player=player, extra={"phase": "banking"})
                player = drop_burnt(args, handle)
                player = bank_cooked(args, handle)
                write_runner_status(args, "running", run_path=run_path, reason="recover_cooked_banked",
                                    cycle=cycles, player=player, extra={"phase": "banked"})
                if safe_stop_requested(args, handle, "after_recover_cooked_bank", cycles, player, run_path):
                    stopped_reason = "stop_requested"
                    break
                continue
            cycles += 1
            log(args, "cycle {}: fishing={} cooking={}".format(
                cycles, bridge.skill_level(player, "fishing"), bridge.skill_level(player, "cooking")))
            write_runner_status(args, "running", run_path=run_path, reason="fishing",
                                cycle=cycles, player=player, extra={"phase": "fishing"})
            player = fish_until_full(args, handle, run_path=run_path, cycle=cycles)
            write_runner_status(args, "running", run_path=run_path, reason="cooking",
                                cycle=cycles, player=player, extra={"phase": "cooking"})
            player = cook_inventory(args, handle, run_path=run_path, cycle=cycles)
            player = drop_burnt(args, handle)
            write_runner_status(args, "running", run_path=run_path, reason="banking",
                                cycle=cycles, player=player, extra={"phase": "banking"})
            player = bank_cooked(args, handle)
            player = bank_raw_fish(args, handle, "cycle_raw_leftovers")
            write_runner_status(args, "running", run_path=run_path, reason="banked",
                                cycle=cycles, player=player, extra={"phase": "banked"})
            if safe_stop_requested(args, handle, "after_cycle_bank", cycles, player, run_path):
                stopped_reason = "stop_requested"
                break
        if stopped_reason is None:
            stopped_reason = "max_cycles" if cycles >= args.cycles else "target_levels"
        write_event(handle, "run_finish", {
            "cycles": cycles,
            "reason": stopped_reason,
            "player": bridge.compact_player(player, ("fishing", "cooking")),
            "inventoryRaw": count_any(player, RAW_FISH_IDS),
            "inventoryCooked": count_any(player, COOKED_FISH_IDS),
            "inventoryBurnt": count_any(player, BURNT_FISH_IDS),
        })
        write_runner_status(args, "stopped" if stopped_reason == "stop_requested" else "complete",
                            run_path=run_path, reason=stopped_reason, cycle=cycles,
                            player=player, extra={"phase": "finished"})
        if handle is not None:
            log(args, "catherby food log: {}".format(run_path))
        return 0
    except Exception as exc:
        try:
            player = bridge.observe(args.profile)
        except Exception:
            player = None
        write_runner_status(args, "error", run_path=run_path, reason=exc.__class__.__name__,
                            player=player, extra={"error": str(exc)})
        raise
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    argv_list = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Run Catherby fish/cook/drop/bank cycles.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE", ""))
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--target-fishing-level", type=int)
    parser.add_argument("--target-cooking-level", type=int)
    parser.add_argument("--run-mode", choices=["auto", "always", "never", "preserve"], default="auto")
    parser.add_argument("--eat-at", type=int, default=10)
    parser.add_argument("--max-batch-distance", type=int, default=24)
    parser.add_argument("--npc-max-distance", type=int, default=25)
    parser.add_argument("--object-max-distance", type=int, default=5)
    parser.add_argument("--supply-shop-name", default="fishing")
    parser.add_argument("--shop-max-distance", type=int, default=10)
    parser.add_argument("--supply-coin-float", type=int, default=1000)
    parser.add_argument("--bait-inventory-target", type=int, default=100)
    parser.add_argument("--bait-buy-amount", type=int, default=200)
    parser.add_argument("--auto-buy-supplies", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-fish-ticks", type=int, default=900)
    parser.add_argument("--fish-round-max-ticks", type=int, default=900,
                        help="Maximum ticks to wait after one fishing spot click before rechecking progress. Idle/spot movement still returns early.")
    parser.add_argument("--max-cook-ticks", type=int, default=120)
    parser.add_argument("--cook-interface-ticks", type=int, default=1)
    parser.add_argument("--max-no-progress-rounds", type=int, default=2)
    parser.add_argument("--compat-cook", choices=["auto", "always", "never"], default="never",
                        help="Opt in to the legacy Java cook_food compatibility path only when deliberately testing a stale runtime.")
    parser.add_argument("--status", action="store_true",
                        help="Print this runner's cooperative status file and exit without touching the game.")
    parser.add_argument("--efficiency-report", action="store_true",
                        help="Print recent passive-trace activity vs idle time and exit without touching the game.")
    parser.add_argument("--efficiency-window-minutes", type=int, default=15)
    parser.add_argument("--idle-span-threshold-seconds", type=int, default=5)
    parser.add_argument("--request-stop", action="store_true",
                        help="Ask a running Catherby food runner to stop at the next safe banked boundary.")
    parser.add_argument("--clear-stop", action="store_true",
                        help="Clear this runner's pending cooperative stop request and exit.")
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv_list)
    if args.status:
        return print_runner_status(args)
    if args.efficiency_report:
        return print_efficiency_report(args)
    if args.request_stop:
        return request_runner_stop(args)
    if args.clear_stop:
        print(json.dumps({
            "ok": True,
            "runner": "catherby_food_runner",
            "profile": runner_profile_label(args),
            "clearedStopRequests": clear_runner_stop_requests(args),
        }, sort_keys=True))
        return 0
    log_usage("catherby_food_runner", surface="full", argv=argv_list)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
