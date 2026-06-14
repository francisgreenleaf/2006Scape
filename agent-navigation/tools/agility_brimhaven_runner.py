#!/usr/bin/env python3
"""Run or supervise Brimhaven Agility Arena ticket training."""

import argparse
from collections import deque
from collections import Counter
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
NAV_ROOT = SCRIPT_DIR.parent
REPO_ROOT = NAV_ROOT.parent
RUNNER_NAME = "agility-brimhaven"
RUNS_DIR = NAV_ROOT / "data" / "agility" / "runs"
ML2_DEFINE = NAV_ROOT / "ml2-routing" / "route_ml_XS.py"
SERVER_TARGET_JAR = REPO_ROOT / "2006Scape Server" / "target" / "server-1.0-jar-with-dependencies.jar"
TICKET = 2996
COINS = 995
CAPN_IZZY = 437
PIRATE_JACKIE = 1055
CAPTAIN_BARNABY = 381
BRIMHAVEN_ENTRANCE = "brimhaven_agility_entrance"
DEFAULT_RESTOCK_BANK = "catherby_bank"
EXIT_LADDER = {"x": 2805, "y": 9590, "height": 3}
BRIMHAVEN_DOCK = {"x": 2772, "y": 3234, "height": 0}
ARDOUGNE_DOCK = {"x": 2683, "y": 3271, "height": 0}
BRIMHAVEN_DOCK_TARGET = "2772,3234,0"
ARDOUGNE_DOCK_TARGET = "2683,3271,0"
FOOD_ITEM_IDS = [
    385,  # Shark
    379,  # Lobster
    373,  # Swordfish
    365, 361, 333, 329, 325, 319, 315,
]
ARENA_BOUNDS = {"minX": 2758, "maxX": 2812, "minY": 9541, "maxY": 9595, "height": 3}
EXIT_LADDER_ID = 3618
TICKET_DISPENSER_ID = 3581
INACTIVE_TICKET_DISPENSER_ID = 3608
TICKET_DISPENSER_IDS = {TICKET_DISPENSER_ID, INACTIVE_TICKET_DISPENSER_ID}
OBSTACLE_MIN_ID = 3551
OBSTACLE_MAX_ID = 3585
ZERO_XP_OBSTACLE_IDS = {3567, 3568, 3569}
BLADE_OBSTACLE_IDS = ZERO_XP_OBSTACLE_IDS | {3580}
CROSS_X = "x"
CROSS_Y = "y"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
from profile_utils import resolve_profile, safe_profile  # noqa: E402


RUN_STARTED_AT = time.monotonic()
LAST_EVENT_AT = None
LAST_SERVER_TICK = None
LAST_EVENT_INDEX = 0
TICK_SECONDS = 0.6
ZERO_XP_OBSTACLE_PENALTY = 7000
REVERSE_EDGE_PENALTY = 1800
EDGE_REPEAT_PENALTY = 1200
BLADE_REPEAT_PENALTY = 2600
BLADE_BACKTRACK_PENALTY = 1800
BLADE_DAMAGE_RISK_PENALTY = 3600
BLADE_AWAY_PENALTY = 9000
BLADE_WEAK_PROGRESS_PENALTY = 4200
EDGE_REPEAT_COUNT_PENALTY = 650
REPEATED_AWAY_EDGE_PENALTY = 1600
NO_PROGRESS_REPEAT_PENALTY = 1800
NO_PROGRESS_REVERSE_PENALTY = 3600
WEAK_REPEAT_LOOP_PENALTY = 2800
WEAK_REVERSE_LOOP_PENALTY = 1800
RECENT_EDGE_MEMORY = 24
LOOP_ESCAPE_MIN_PROGRESS = -3

DISPENSERS = [
    {"id": 3608, "x": 2761, "y": 9546, "height": 3},
    {"id": 3608, "x": 2772, "y": 9546, "height": 3},
    {"id": 3608, "x": 2783, "y": 9546, "height": 3},
    {"id": 3608, "x": 2794, "y": 9546, "height": 3},
    {"id": 3608, "x": 2805, "y": 9546, "height": 3},
    {"id": 3608, "x": 2761, "y": 9557, "height": 3},
    {"id": 3608, "x": 2772, "y": 9557, "height": 3},
    {"id": 3581, "x": 2783, "y": 9557, "height": 3},
    {"id": 3581, "x": 2794, "y": 9557, "height": 3},
    {"id": 3608, "x": 2805, "y": 9557, "height": 3},
    {"id": 3608, "x": 2761, "y": 9568, "height": 3},
    {"id": 3581, "x": 2772, "y": 9568, "height": 3},
    {"id": 3581, "x": 2783, "y": 9568, "height": 3},
    {"id": 3581, "x": 2794, "y": 9568, "height": 3},
    {"id": 3608, "x": 2805, "y": 9568, "height": 3},
    {"id": 3608, "x": 2761, "y": 9579, "height": 3},
    {"id": 3608, "x": 2772, "y": 9579, "height": 3},
    {"id": 3608, "x": 2783, "y": 9579, "height": 3},
    {"id": 3581, "x": 2794, "y": 9579, "height": 3},
    {"id": 3608, "x": 2805, "y": 9579, "height": 3},
    {"id": 3608, "x": 2761, "y": 9590, "height": 3},
    {"id": 3608, "x": 2772, "y": 9590, "height": 3},
    {"id": 3608, "x": 2783, "y": 9590, "height": 3},
    {"id": 3608, "x": 2794, "y": 9590, "height": 3},
]

FALLBACK_OBSTACLES = [
    {"id": 3565, "name": "Low wall", "x": 2805, "y": 9562, "height": 3},
    {"id": 3582, "name": "Floor spikes", "x": 2800, "y": 9568, "height": 3},
    {"id": 3585, "name": "Pressure pad", "x": 2800, "y": 9579, "height": 3},
    {"id": 3572, "name": "Plank", "x": 2802, "y": 9590, "height": 3},
    {"id": 3566, "name": "Rope swing", "x": 2804, "y": 9584, "height": 3},
    {"id": 3553, "name": "Log balance", "x": 2794, "y": 9587, "height": 3},
    {"id": 3551, "name": "Balancing rope", "x": 2783, "y": 9588, "height": 3},
    {"id": 3585, "name": "Pressure pad", "x": 2772, "y": 9584, "height": 3},
    {"id": 3582, "name": "Floor spikes", "x": 2761, "y": 9574, "height": 3},
    {"id": 3566, "name": "Rope swing", "x": 2766, "y": 9569, "height": 3},
    {"id": 3551, "name": "Balancing rope", "x": 2772, "y": 9566, "height": 3},
    {"id": 3565, "name": "Low wall", "x": 2783, "y": 9562, "height": 3},
    {"id": 3563, "name": "Monkey bars", "x": 2794, "y": 9562, "height": 3},
    {"id": 3585, "name": "Pressure pad", "x": 2800, "y": 9557, "height": 3},
    {"id": 3553, "name": "Log balance", "x": 2805, "y": 9554, "height": 3},
    {"id": 3551, "name": "Balancing rope", "x": 2794, "y": 9555, "height": 3},
    {"id": 3568, "name": "Blade", "x": 2783, "y": 9551, "height": 3},
    {"id": 3582, "name": "Floor spikes", "x": 2772, "y": 9551, "height": 3},
    {"id": 3570, "name": "Plank", "x": 2769, "y": 9557, "height": 3},
    {"id": 3559, "name": "Balancing ledge", "x": 2769, "y": 9546, "height": 3},
    {"id": 3564, "name": "Monkey bars", "x": 2781, "y": 9545, "height": 3},
    {"id": 3583, "name": "Hand holds", "x": 2792, "y": 9544, "height": 3},
    {"id": 3559, "name": "Balancing ledge", "x": 2802, "y": 9546, "height": 3},
]

OBSTACLE_SPANS = [
    (3565, 3565, 2783, 2783, 9558, 9567, CROSS_Y),
    (3565, 3565, 2805, 2805, 9558, 9567, CROSS_Y),
    (3565, 3565, 2773, 2782, 9590, 9590, CROSS_X),
    (3551, 3552, 2772, 2772, 9559, 9566, CROSS_Y),
    (3551, 3552, 2783, 2783, 9581, 9588, CROSS_Y),
    (3551, 3552, 2794, 2794, 9548, 9555, CROSS_Y),
    (3553, 3558, 2764, 2769, 9579, 9579, CROSS_X),
    (3553, 3558, 2794, 2794, 9582, 9587, CROSS_Y),
    (3553, 3558, 2805, 2805, 9549, 9554, CROSS_Y),
    (3559, 3562, 2764, 2769, 9546, 9546, CROSS_X),
    (3559, 3562, 2764, 2769, 9590, 9590, CROSS_X),
    (3559, 3562, 2797, 2802, 9546, 9546, CROSS_X),
    (3563, 3564, 2772, 2772, 9571, 9576, CROSS_Y),
    (3563, 3564, 2775, 2780, 9546, 9546, CROSS_X),
    (3563, 3564, 2794, 2794, 9560, 9565, CROSS_Y),
    (3567, 3569, 2761, 2761, 9584, 9585, CROSS_Y),
    (3567, 3569, 2783, 2783, 9551, 9552, CROSS_Y),
    (3567, 3569, 2788, 2789, 9579, 9579, CROSS_X),
    (3580, 3580, 2777, 2779, 9556, 9556, CROSS_X),
    (3580, 3580, 2777, 2779, 9580, 9580, CROSS_X),
    (3580, 3580, 2782, 2782, 9573, 9575, CROSS_Y),
    (3570, 3577, 2764, 2769, 9556, 9558, CROSS_X),
    (3570, 3577, 2797, 2802, 9589, 9591, CROSS_X),
    (3578, 3579, 2761, 2761, 9549, 9554, CROSS_Y),
    (3578, 3579, 2786, 2791, 9568, 9568, CROSS_X),
    (3578, 3579, 2805, 2805, 9571, 9576, CROSS_Y),
    (3582, 3582, 2761, 2761, 9573, 9574, CROSS_Y),
    (3582, 3582, 2772, 2772, 9551, 9552, CROSS_Y),
    (3582, 3582, 2799, 2800, 9568, 9568, CROSS_X),
    (3583, 3584, 2759, 2759, 9559, 9566, CROSS_Y),
    (3583, 3584, 2785, 2792, 9544, 9544, CROSS_X),
    (3583, 3584, 2785, 2792, 9592, 9592, CROSS_X),
    (3585, 3585, 2772, 2772, 9584, 9585, CROSS_Y),
    (3585, 3585, 2799, 2800, 9557, 9557, CROSS_X),
    (3585, 3585, 2799, 2800, 9579, 9579, CROSS_X),
]


def utc_stamp():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def runner_dir(profile):
    return NAV_ROOT / ".local" / "runners" / safe_profile(profile)


def runner_paths(profile):
    directory = runner_dir(profile)
    return {
        "dir": directory,
        "pid": directory / "{}.pid".format(RUNNER_NAME),
        "logpath": directory / "{}.logpath".format(RUNNER_NAME),
        "stop": directory / "{}.stop".format(RUNNER_NAME),
    }


def read_text(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_pid(path):
    value = read_text(path)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def process_exists(pid):
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def server_runtime_status():
    pid_path = NAV_ROOT / ".local" / "server.pid"
    pid = read_pid(pid_path)
    payload = {
        "pid": pid,
        "pidFile": str(pid_path),
        "alive": process_exists(pid),
        "targetJar": str(SERVER_TARGET_JAR),
    }
    if not payload["alive"]:
        payload["staleForBrimhavenCourse"] = True
        payload["reason"] = "server_not_alive"
        return payload
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
        )
        command = proc.stdout.strip()
    except Exception as exc:
        payload["staleForBrimhavenCourse"] = None
        payload["reason"] = "ps_failed:{}".format(exc)
        return payload
    payload["command"] = command[:240]
    parts = command.split()
    runtime_jar = ""
    for idx, part in enumerate(parts):
        if part == "-jar" and idx + 1 < len(parts):
            runtime_jar = parts[idx + 1]
            break
    payload["runtimeJar"] = runtime_jar
    try:
        target_mtime = SERVER_TARGET_JAR.stat().st_mtime
        runtime_mtime = Path(runtime_jar).stat().st_mtime if runtime_jar else 0
    except OSError as exc:
        payload["staleForBrimhavenCourse"] = None
        payload["reason"] = "stat_failed:{}".format(exc)
        return payload
    payload["targetJarMtime"] = int(target_mtime)
    payload["runtimeJarMtime"] = int(runtime_mtime)
    payload["staleForBrimhavenCourse"] = target_mtime > runtime_mtime + 1
    if payload["staleForBrimhavenCourse"]:
        payload["reason"] = "running_server_jar_older_than_built_target"
    else:
        payload["reason"] = "runtime_matches_or_newer_than_target"
    return payload


def tail_lines(path, limit=8):
    if not path or not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-int(limit):]


def latest_evidence_path():
    try:
        paths = list(RUNS_DIR.glob("*-brimhaven.jsonl"))
    except OSError:
        return None
    if not paths:
        return None
    return max(paths, key=lambda item: item.stat().st_mtime)


def compact_evidence_event(event):
    payload = {
        "event": event.get("event"),
        "timestamp": event.get("timestamp"),
    }
    for key in ("success", "message", "reason", "dispenser", "activeWindow",
                "elapsedSeconds", "deltaSeconds", "deltaTicks", "ticketsGained",
                "ticketsSpent", "agilityXpGained", "tag", "sleepSeconds",
                "sleepTicks", "secondsToNextWindow", "nextActiveDispenser",
                "objectId", "name", "distance", "score",
                "currentTargetDistance", "predictedTargetDistance", "targetDistanceDelta",
                "scorePenalties", "selectionReason", "moved", "hpLost", "fromTile", "toTile",
                "objectTile", "predictedTile", "approachTile", "activeDispenser",
                "activeTarget", "navigationTargetReason", "navigationTarget",
                "serverTick", "deltaServerTicks", "reverseEdge", "edgeRepeat",
                "recentEdgeCount", "loopRiskPenalty", "isBladeCandidate", "escapeClick",
                "directedEdge", "undirectedEdge"):
        if key in event:
            payload[key] = event.get(key)
    for key in ("topCandidates", "nearbyTopCandidates", "preferredTopCandidates"):
        if key in event:
            payload[key] = event.get(key)
    player = event.get("player")
    if isinstance(player, dict):
        payload["player"] = {
            "tile": player.get("tile"),
            "hp": player.get("hp"),
            "maxHp": player.get("maxHp"),
            "runEnergy": player.get("runEnergy"),
            "runEnabled": player.get("runEnabled"),
            "isDead": player.get("isDead"),
            "isInCombat": player.get("isInCombat"),
            "isPoisoned": player.get("isPoisoned"),
            "agilityLevel": player.get("agilityLevel"),
            "agilityXp": player.get("agilityXp"),
            "tickets": player.get("tickets"),
            "coins": player.get("coins"),
            "serverTick": player.get("serverTick"),
        }
    return payload


def evidence_summary(tail=8):
    path = latest_evidence_path()
    if not path:
        return {"available": False}
    last_events = deque(maxlen=max(0, int(tail)))
    summary = {
        "available": True,
        "path": str(path),
        "events": 0,
        "tagEvents": 0,
        "successfulTags": 0,
        "ticketsGained": 0,
        "exchanges": 0,
        "ticketsSpent": 0,
        "agilityXpGained": 0,
        "obstacleSteps": 0,
        "successfulObstacleSteps": 0,
        "lastObstacle": None,
        "lastEvent": None,
        "lastTimestamp": None,
        "lastPlayer": None,
        "approachFailures": 0,
        "approachOscillations": 0,
        "approachSuppressions": 0,
        "fallbackClicks": 0,
        "fallbackSuppressions": 0,
        "zeroXpObstacleSteps": 0,
        "sameObstacleStreakMax": 0,
        "reverseStepEvents": 0,
        "nonProgressSteps": 0,
        "awayFromTargetSteps": 0,
        "recentChoiceSequence": [],
        "recentObstacleCounts": {},
        "recentDelayStats": {},
        "recentReverseSteps": [],
        "recentZeroXpSteps": [],
        "recentRepeatedEdges": [],
        "recentBladeSteps": [],
        "recentBladeAwaySteps": [],
        "recentLongDelays": [],
        "recentLoopRisks": [],
        "topRepeatedEdges": [],
        "edgeLoopSummary": {},
        "bladeLoopSummary": {},
    }
    recent_choices = deque(maxlen=12)
    recent_obstacle_names = deque(maxlen=40)
    recent_reverse_steps = deque(maxlen=8)
    recent_zero_xp_steps = deque(maxlen=8)
    recent_repeated_edges = deque(maxlen=8)
    recent_blade_steps = deque(maxlen=8)
    recent_blade_away_steps = deque(maxlen=8)
    recent_long_delays = deque(maxlen=8)
    recent_loop_risks = deque(maxlen=8)
    recent_delta_ticks = deque(maxlen=40)
    edge_stats = {}
    direct_reverse_pairs = 0
    blade_direct_reverse_pairs = 0
    blade_steps_total = 0
    blade_edge_repeats = 0
    blade_zero_xp_steps = 0
    blade_away_steps = 0
    previous_step = None
    same_obstacle_name = None
    same_obstacle_streak = 0
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            summary["events"] += 1
            name = event.get("event")
            if name == "tag_dispenser":
                summary["tagEvents"] += 1
                if event.get("success"):
                    summary["successfulTags"] += 1
                summary["ticketsGained"] += int(event.get("ticketsGained", 0) or 0)
            elif name == "exchange_tickets":
                summary["exchanges"] += 1
                summary["ticketsSpent"] += int(event.get("ticketsSpent", 0) or 0)
                summary["agilityXpGained"] += int(event.get("agilityXpGained", 0) or 0)
            elif name == "obstacle_step":
                summary["obstacleSteps"] += 1
                delta_server_ticks = event.get("deltaServerTicks")
                try:
                    delta_server_ticks_int = int(delta_server_ticks)
                except (TypeError, ValueError):
                    delta_server_ticks_int = None
                if delta_server_ticks_int is not None and delta_server_ticks_int > 8:
                    recent_long_delays.append({
                        "timestamp": event.get("timestamp"),
                        "serverTick": event.get("serverTick"),
                        "deltaServerTicks": delta_server_ticks_int,
                        "name": event.get("name"),
                        "objectId": event.get("objectId"),
                        "fromTile": event.get("fromTile"),
                        "toTile": event.get("toTile"),
                        "targetDistanceDelta": event.get("targetDistanceDelta"),
                    })
                if event.get("deltaTicks") is not None:
                    try:
                        recent_delta_ticks.append(int(event.get("deltaTicks")))
                    except (TypeError, ValueError):
                        pass
                if event.get("moved") or int(event.get("agilityXpGained", 0) or 0) > 0:
                    summary["successfulObstacleSteps"] += 1
                summary["agilityXpGained"] += int(event.get("agilityXpGained", 0) or 0)
                if int((event.get("scorePenalties") or {}).get("zeroXp", 0) or 0) > 0:
                    summary["zeroXpObstacleSteps"] += 1
                    recent_zero_xp_steps.append({
                        "timestamp": event.get("timestamp"),
                        "deltaTicks": event.get("deltaTicks"),
                        "name": event.get("name"),
                        "objectId": event.get("objectId"),
                        "fromTile": event.get("fromTile"),
                        "toTile": event.get("toTile"),
                        "targetDistanceDelta": event.get("targetDistanceDelta"),
                    })
                is_blade_step = "blade" in str(event.get("name", "")).lower() or int(event.get("objectId", 0) or 0) in ZERO_XP_OBSTACLE_IDS
                if int((event.get("scorePenalties") or {}).get("zeroXp", 0) or 0) > 0 and is_blade_step:
                    blade_zero_xp_steps += 1
                if is_blade_step:
                    blade_steps_total += 1
                    recent_blade_steps.append({
                        "timestamp": event.get("timestamp"),
                        "serverTick": event.get("serverTick"),
                        "deltaTicks": event.get("deltaTicks"),
                        "deltaServerTicks": event.get("deltaServerTicks"),
                        "name": event.get("name"),
                        "objectId": event.get("objectId"),
                        "fromTile": event.get("fromTile"),
                        "toTile": event.get("toTile"),
                        "agilityXpGained": event.get("agilityXpGained"),
                        "reverseEdge": bool(event.get("reverseEdge")),
                        "edgeRepeat": bool(event.get("edgeRepeat")),
                        "recentEdgeCount": event.get("recentEdgeCount"),
                        "targetDistanceDelta": event.get("targetDistanceDelta"),
                    })
                    if event.get("edgeRepeat"):
                        blade_edge_repeats += 1
                    target_delta = event.get("targetDistanceDelta")
                    if isinstance(target_delta, int) and target_delta > 0:
                        blade_away_steps += 1
                        recent_blade_away_steps.append({
                            "timestamp": event.get("timestamp"),
                            "serverTick": event.get("serverTick"),
                            "deltaTicks": event.get("deltaTicks"),
                            "deltaServerTicks": event.get("deltaServerTicks"),
                            "name": event.get("name"),
                            "objectId": event.get("objectId"),
                            "fromTile": event.get("fromTile"),
                            "toTile": event.get("toTile"),
                            "agilityXpGained": event.get("agilityXpGained"),
                            "targetDistanceDelta": target_delta,
                            "score": event.get("score"),
                            "scorePenalties": event.get("scorePenalties"),
                        })
                from_tile = event.get("fromTile")
                to_tile = event.get("toTile")
                if isinstance(from_tile, dict) and isinstance(to_tile, dict):
                    undirected_key = "{}:{}".format(event.get("name"), undirected_edge_key(from_tile, to_tile))
                    stats = edge_stats.setdefault(undirected_key, {
                        "name": event.get("name"),
                        "fromTo": directed_edge_key(from_tile, to_tile),
                        "edge": undirected_edge_key(from_tile, to_tile),
                        "count": 0,
                        "firstTimestamp": event.get("timestamp"),
                        "firstTick": event.get("serverTick"),
                        "lastTimestamp": None,
                        "lastTick": None,
                        "lastDirection": None,
                        "xpGained": 0,
                        "awaySteps": 0,
                        "zeroXpSteps": 0,
                        "repeatFlags": 0,
                        "reverseFlags": 0,
                    })
                    stats["count"] += 1
                    stats["lastTimestamp"] = event.get("timestamp")
                    stats["lastTick"] = event.get("serverTick")
                    stats["lastDirection"] = directed_edge_key(from_tile, to_tile)
                    stats["xpGained"] += int(event.get("agilityXpGained", 0) or 0)
                    if isinstance(event.get("targetDistanceDelta"), int) and event.get("targetDistanceDelta") > 0:
                        stats["awaySteps"] += 1
                    if int(event.get("agilityXpGained", 0) or 0) <= 0:
                        stats["zeroXpSteps"] += 1
                    if event.get("edgeRepeat"):
                        stats["repeatFlags"] += 1
                    if event.get("reverseEdge"):
                        stats["reverseFlags"] += 1
                target_delta = event.get("targetDistanceDelta")
                if isinstance(target_delta, int):
                    if target_delta >= 0:
                        summary["nonProgressSteps"] += 1
                    if target_delta > 0:
                        summary["awayFromTargetSteps"] += 1
                if event.get("name") == same_obstacle_name:
                    same_obstacle_streak += 1
                else:
                    same_obstacle_name = event.get("name")
                    same_obstacle_streak = 1
                if event.get("name"):
                    recent_obstacle_names.append(str(event.get("name")))
                summary["sameObstacleStreakMax"] = max(summary["sameObstacleStreakMax"], same_obstacle_streak)
                if previous_step and previous_step.get("fromTile") == event.get("toTile") and previous_step.get("toTile") == event.get("fromTile"):
                    direct_reverse_pairs += 1
                    if is_blade_step or previous_step.get("isBladeStep"):
                        blade_direct_reverse_pairs += 1
                    summary["reverseStepEvents"] += 1
                    recent_reverse_steps.append({
                        "timestamp": event.get("timestamp"),
                        "serverTick": event.get("serverTick"),
                        "deltaTicks": event.get("deltaTicks"),
                        "deltaServerTicks": event.get("deltaServerTicks"),
                        "name": event.get("name"),
                        "objectId": event.get("objectId"),
                        "fromTile": event.get("fromTile"),
                        "toTile": event.get("toTile"),
                        "targetDistanceDelta": event.get("targetDistanceDelta"),
                    })
                if event.get("reverseEdge") or event.get("edgeRepeat"):
                    recent_repeated_edges.append({
                        "timestamp": event.get("timestamp"),
                        "serverTick": event.get("serverTick"),
                        "deltaTicks": event.get("deltaTicks"),
                        "deltaServerTicks": event.get("deltaServerTicks"),
                        "name": event.get("name"),
                        "objectId": event.get("objectId"),
                        "fromTile": event.get("fromTile"),
                        "toTile": event.get("toTile"),
                        "targetDistanceDelta": event.get("targetDistanceDelta"),
                        "reverseEdge": bool(event.get("reverseEdge")),
                        "edgeRepeat": bool(event.get("edgeRepeat")),
                        "recentEdgeCount": event.get("recentEdgeCount"),
                    })
                previous_step = {
                    "fromTile": event.get("fromTile"),
                    "toTile": event.get("toTile"),
                    "isBladeStep": is_blade_step,
                }
                summary["lastObstacle"] = {
                    "id": event.get("objectId"),
                    "name": event.get("name"),
                    "from": event.get("fromTile"),
                    "to": event.get("toTile"),
                    "moved": event.get("moved"),
                }
                recent_choices.append({
                    "timestamp": event.get("timestamp"),
                    "deltaTicks": event.get("deltaTicks"),
                    "name": event.get("name"),
                    "objectId": event.get("objectId"),
                    "fromTile": event.get("fromTile"),
                    "toTile": event.get("toTile"),
                    "agilityXpGained": event.get("agilityXpGained"),
                    "targetDistanceDelta": event.get("targetDistanceDelta"),
                    "navigationTargetReason": event.get("navigationTargetReason"),
                })
            elif name == "obstacle_approach":
                if not event.get("success"):
                    summary["approachFailures"] += 1
                    if "oscillat" in str(event.get("message", "")).lower():
                        summary["approachOscillations"] += 1
            elif name == "obstacle_approach_suppressed":
                summary["approachSuppressions"] += 1
            elif name == "obstacle_approach_fallback_click":
                summary["fallbackClicks"] += 1
            elif name == "obstacle_approach_fallback_suppressed":
                summary["fallbackSuppressions"] += 1
            elif name == "obstacle_loop_risk":
                recent_loop_risks.append(compact_evidence_event(event))
            summary["lastEvent"] = name
            summary["lastTimestamp"] = event.get("timestamp")
            if isinstance(event.get("player"), dict):
                summary["lastPlayer"] = compact_evidence_event(event).get("player")
            if last_events.maxlen:
                last_events.append(compact_evidence_event(event))
    except OSError as exc:
        summary["readError"] = str(exc)
    if recent_obstacle_names:
        summary["recentObstacleCounts"] = dict(Counter(recent_obstacle_names).most_common(8))
    if recent_delta_ticks:
        ticks = list(recent_delta_ticks)
        summary["recentDelayStats"] = {
            "sampleSize": len(ticks),
            "minDeltaTicks": min(ticks),
            "maxDeltaTicks": max(ticks),
            "avgDeltaTicks": round(sum(ticks) / float(len(ticks)), 2),
        }
    summary["recentReverseSteps"] = list(recent_reverse_steps)
    summary["recentZeroXpSteps"] = list(recent_zero_xp_steps)
    summary["recentRepeatedEdges"] = list(recent_repeated_edges)
    summary["recentBladeSteps"] = list(recent_blade_steps)
    summary["recentBladeAwaySteps"] = list(recent_blade_away_steps)
    summary["recentLongDelays"] = list(recent_long_delays)
    summary["recentLoopRisks"] = list(recent_loop_risks)
    repeated_edges = [value for value in edge_stats.values() if int(value.get("count", 0)) > 1]
    repeated_edges.sort(key=lambda value: (-int(value.get("count", 0)), str(value.get("name", "")), str(value.get("edge", ""))))
    summary["topRepeatedEdges"] = repeated_edges[:8]
    summary["edgeLoopSummary"] = {
        "uniqueEdges": len(edge_stats),
        "repeatedEdges": len(repeated_edges),
        "directReversePairs": direct_reverse_pairs,
    }
    summary["bladeLoopSummary"] = {
        "bladeSteps": blade_steps_total,
        "bladeAwaySteps": blade_away_steps,
        "bladeEdgeRepeats": blade_edge_repeats,
        "bladeDirectReversePairs": blade_direct_reverse_pairs,
        "bladeZeroXpSteps": blade_zero_xp_steps,
    }
    summary["recentChoiceSequence"] = list(recent_choices)
    summary["tail"] = list(last_events)
    return summary


def tile_label(value):
    if not isinstance(value, dict):
        return "?"
    return "{},{},{}".format(value.get("x", "?"), value.get("y", "?"), value.get("height", "?"))


def loop_report(tail=40):
    path = latest_evidence_path()
    if not path:
        return {"ok": False, "available": False, "message": "No Brimhaven evidence log found."}
    steps = []
    redirects = []
    blade_allows = []
    suppressions = []
    loop_risks = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = event.get("event")
            if name == "obstacle_step":
                penalties = event.get("scorePenalties") or {}
                is_blade = "blade" in str(event.get("name", "")).lower() or int(event.get("objectId", 0) or 0) in BLADE_OBSTACLE_IDS
                steps.append({
                    "timestamp": event.get("timestamp"),
                    "serverTick": event.get("serverTick"),
                    "deltaServerTicks": event.get("deltaServerTicks"),
                    "deltaTicks": event.get("deltaTicks"),
                    "name": event.get("name"),
                    "objectId": event.get("objectId"),
                    "from": event.get("fromTile"),
                    "to": event.get("toTile"),
                    "xp": event.get("agilityXpGained"),
                    "targetDistanceDelta": event.get("targetDistanceDelta"),
                    "edgeRepeat": bool(event.get("edgeRepeat")),
                    "reverseEdge": bool(event.get("reverseEdge")),
                    "recentEdgeCount": event.get("recentEdgeCount"),
                    "score": event.get("score"),
                    "zeroXpPenalty": int(penalties.get("zeroXp", 0) or 0),
                    "bladeRiskPenalty": int(penalties.get("bladeDamageRisk", 0) or 0)
                        + int(penalties.get("bladeRepeat", 0) or 0)
                        + int(penalties.get("bladeBacktrack", 0) or 0)
                        + int(penalties.get("bladeAway", 0) or 0)
                        + int(penalties.get("bladeWeakProgress", 0) or 0),
                    "selectionReason": event.get("selectionReason"),
                    "isBlade": is_blade,
                })
            elif name == "obstacle_approach_redirected":
                redirects.append(compact_evidence_event(event))
            elif name == "obstacle_approach_blade_allowed":
                blade_allows.append(compact_evidence_event(event))
            elif name == "obstacle_approach_suppressed":
                suppressions.append(compact_evidence_event(event))
            elif name == "obstacle_loop_risk":
                loop_risks.append(compact_evidence_event(event))
    except OSError as exc:
        return {"ok": False, "available": False, "path": str(path), "message": str(exc)}
    recent_steps = steps[-max(0, int(tail)):]
    repeated = Counter()
    direct_reverses = 0
    for previous, current in zip(recent_steps, recent_steps[1:]):
        if previous.get("from") == current.get("to") and previous.get("to") == current.get("from"):
            direct_reverses += 1
    for step in recent_steps:
        repeated[(step.get("name"), undirected_edge_key(step.get("from"), step.get("to")))] += 1
    top_repeated = [
        {"name": name, "edge": edge, "count": count}
        for (name, edge), count in repeated.most_common(8)
        if count > 1
    ]
    span_ticks = 0
    span_seconds = 0.0
    if len(recent_steps) >= 2:
        first_tick = recent_steps[0].get("serverTick")
        last_tick = recent_steps[-1].get("serverTick")
        if isinstance(first_tick, int) and isinstance(last_tick, int):
            span_ticks = max(0, last_tick - first_tick)
            span_seconds = round(span_ticks * TICK_SECONDS, 1)
    return {
        "ok": True,
        "available": True,
        "path": str(path),
        "tail": len(recent_steps),
        "totalObstacleSteps": len(steps),
        "spanTicks": span_ticks,
        "spanSeconds": span_seconds,
        "recentDirectReverses": direct_reverses,
        "recentBladeSteps": sum(1 for step in recent_steps if step.get("isBlade")),
        "recentBladeRepeats": sum(1 for step in recent_steps if step.get("isBlade") and step.get("edgeRepeat")),
        "recentBladeAwaySteps": sum(1 for step in recent_steps if step.get("isBlade") and int(step.get("targetDistanceDelta") or 0) > 0),
        "recentAwaySteps": sum(1 for step in recent_steps if int(step.get("targetDistanceDelta") or 0) > 0),
        "recentRepeatSteps": sum(1 for step in recent_steps if step.get("edgeRepeat") or step.get("reverseEdge")),
        "topRepeatedEdges": top_repeated,
        "recentRedirects": redirects[-8:],
        "recentBladeAllows": blade_allows[-8:],
        "recentSuppressions": suppressions[-8:],
        "recentLoopRisks": loop_risks[-8:],
        "steps": recent_steps,
    }


def loop_report_text(report):
    if not report.get("ok"):
        return report.get("message", "No report available.")
    lines = [
        "Brimhaven loop report",
        "path: {}".format(report.get("path")),
        "tail: {} of {} obstacle steps, repeats={}, directReverses={}, bladeSteps={}, bladeRepeats={}, bladeAway={}".format(
            report.get("tail"), report.get("totalObstacleSteps"), report.get("recentRepeatSteps"),
            report.get("recentDirectReverses"), report.get("recentBladeSteps"),
            report.get("recentBladeRepeats"), report.get("recentBladeAwaySteps")),
        "span: {} ticks / {}s".format(report.get("spanTicks"), report.get("spanSeconds")),
    ]
    if report.get("topRepeatedEdges"):
        lines.append("top repeated edges:")
        for edge in report.get("topRepeatedEdges", []):
            lines.append("  {} x{} {}".format(edge.get("name"), edge.get("count"), edge.get("edge")))
    if report.get("recentRedirects"):
        lines.append("recent approach redirects:")
        for event in report.get("recentRedirects", [])[-4:]:
            lines.append("  {} tick={} {} -> {}".format(
                event.get("timestamp"), (event.get("player") or {}).get("serverTick"),
                event.get("reason"), event.get("message")))
    if report.get("recentBladeAllows"):
        lines.append("recent spinning-blade approach allows:")
        for event in report.get("recentBladeAllows", [])[-4:]:
            lines.append("  {} tick={} {} d={}".format(
                event.get("timestamp"), (event.get("player") or {}).get("serverTick"),
                event.get("reason"), event.get("preferredTargetDistanceDelta")))
    if report.get("recentLoopRisks"):
        lines.append("recent loop-risk selections:")
        for event in report.get("recentLoopRisks", [])[-6:]:
            lines.append("  {} tick={} {}#{} {} d={} risk={} rep={} rev={} blade={}".format(
                event.get("timestamp"), event.get("serverTick"), event.get("name"), event.get("objectId"),
                event.get("directedEdge"), event.get("targetDistanceDelta"), event.get("loopRiskPenalty"),
                event.get("edgeRepeat"), event.get("reverseEdge"), event.get("isBladeCandidate")))
    lines.append("recent steps:")
    for step in report.get("steps", []):
        lines.append(
            "  {ts} tick={tick} dt={dt}/{edt} {name}#{oid} {src}->{dst} xp={xp} d={delta} rep={rep} rev={rev} score={score} blade={blade} bladeRisk={risk} reason={reason}".format(
                ts=step.get("timestamp"),
                tick=step.get("serverTick"),
                dt=step.get("deltaServerTicks"),
                edt=step.get("deltaTicks"),
                name=step.get("name"),
                oid=step.get("objectId"),
                src=tile_label(step.get("from")),
                dst=tile_label(step.get("to")),
                xp=step.get("xp"),
                delta=step.get("targetDistanceDelta"),
                rep=step.get("edgeRepeat"),
                rev=step.get("reverseEdge"),
                score=step.get("score"),
                blade=step.get("isBlade"),
                risk=step.get("bladeRiskPenalty"),
                reason=step.get("selectionReason"),
            )
        )
    return "\n".join(lines)


def print_json(payload):
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def status_payload(profile, tail=8):
    paths = runner_paths(profile)
    pid = read_pid(paths["pid"])
    log_path_text = read_text(paths["logpath"])
    log_path = Path(log_path_text).expanduser() if log_path_text else None
    return {
        "ok": True,
        "runner": RUNNER_NAME,
        "profile": profile,
        "pid": pid,
        "pidFile": str(paths["pid"]),
        "alive": process_exists(pid),
        "stopRequested": paths["stop"].exists(),
        "stopPath": str(paths["stop"]),
        "logPath": str(log_path) if log_path else "",
        "logPathFile": str(paths["logpath"]),
        "logTail": tail_lines(log_path, tail) if log_path else [],
        "runtime": server_runtime_status(),
        "evidence": evidence_summary(tail=tail),
    }


def tile(player):
    return bridge.tile_from_player(player)


def tile_dist(a, b):
    if int(a.get("height", 0)) != int(b.get("height", 0)):
        return 10000
    return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))


def tile_key(value):
    return "{},{},{}".format(int(value["x"]), int(value["y"]), int(value.get("height", 0)))


def directed_edge_key(from_tile, to_tile):
    return "{}->{}".format(tile_key(from_tile), tile_key(to_tile))


def undirected_edge_key(from_tile, to_tile):
    a = tile_key(from_tile)
    b = tile_key(to_tile)
    left, right = sorted([a, b])
    return "{}<->{}".format(left, right)


def parse_tile_string(value):
    parts = str(value or "").split(",")
    if len(parts) < 3:
        return None
    try:
        return {"x": int(parts[0]), "y": int(parts[1]), "height": int(parts[2])}
    except ValueError:
        return None


def active_target():
    return DISPENSERS[active_dispenser()]


def next_dispenser(index):
    return int((int(index) + 1) % len(DISPENSERS))


def candidate_target(target_override=None):
    return target_override or active_target()


def predicted_destination(player_tile, obj):
    for min_id, max_id, min_x, max_x, min_y, max_y, axis in OBSTACLE_SPANS:
        object_id = int(obj["id"])
        object_x = int(obj["x"])
        object_y = int(obj["y"])
        if not (min_id <= object_id <= max_id):
            continue
        if not (min_x <= object_x <= max_x and min_y <= object_y <= max_y):
            continue
        dest_x = max(min_x, min(max_x, int(player_tile["x"])))
        dest_y = max(min_y, min(max_y, int(player_tile["y"])))
        if axis == CROSS_X:
            player_x = int(player_tile["x"])
            if player_x <= min_x:
                dest_x = max_x + 1
            elif player_x > max_x:
                dest_x = min_x - 1
            else:
                dest_x = max_x + 1 if player_x <= object_x else min_x - 1
        else:
            player_y = int(player_tile["y"])
            if player_y <= min_y:
                dest_y = max_y + 1
            elif player_y > max_y:
                dest_y = min_y - 1
            else:
                dest_y = max_y + 1 if player_y <= object_y else min_y - 1
        return {
            "x": max(2761, min(2806, dest_x)),
            "y": max(9544, min(9592, dest_y)),
            "height": 3,
        }
    dx = int(obj["x"]) - int(player_tile["x"])
    dy = int(obj["y"]) - int(player_tile["y"])
    dest_x = int(obj["x"])
    dest_y = int(obj["y"])
    if abs(dx) >= abs(dy) and dx != 0:
        dest_x = int(obj["x"]) + (1 if dx > 0 else -1)
    elif dy != 0:
        dest_y = int(obj["y"]) + (1 if dy > 0 else -1)
    else:
        dest_y = int(obj["y"]) + 1
    dest_x = max(2761, min(2806, dest_x))
    dest_y = max(9544, min(9592, dest_y))
    return {"x": dest_x, "y": dest_y, "height": 3}


def arena_tile(x, y):
    return {
        "x": max(2761, min(2806, int(x))),
        "y": max(9544, min(9592, int(y))),
        "height": 3,
    }


def obstacle_approach_tile(player_tile, obj, radius):
    dx = int(player_tile["x"]) - int(obj["x"])
    dy = int(player_tile["y"]) - int(obj["y"])
    distance = max(abs(dx), abs(dy))
    if distance <= max(1, int(radius)):
        return dict(player_tile)
    if distance == 0:
        return arena_tile(int(obj["x"]), int(obj["y"]) + 1)
    step = max(1, int(radius) - 1)
    scale = float(step) / float(distance)
    return arena_tile(
        int(round(int(obj["x"]) + dx * scale)),
        int(round(int(obj["y"]) + dy * scale)),
    )


def load_course_objects():
    try:
        import cache_world_map as cwm
        world = cwm.load_cache_world_map(
            {
                "minX": ARENA_BOUNDS["minX"],
                "maxX": ARENA_BOUNDS["maxX"],
                "minY": ARENA_BOUNDS["minY"],
                "maxY": ARENA_BOUNDS["maxY"],
            },
            plane=ARENA_BOUNDS["height"],
        )
        objects = []
        seen = set()
        for raw in world.get("objects", []):
            object_id = int(raw.get("id", -1))
            if object_id < OBSTACLE_MIN_ID or object_id > OBSTACLE_MAX_ID:
                continue
            if object_id in TICKET_DISPENSER_IDS:
                continue
            name = raw.get("name") or "Obstacle"
            key = (object_id, int(raw["x"]), int(raw["y"]), int(raw.get("height", 3)))
            if key in seen:
                continue
            seen.add(key)
            objects.append({
                "id": object_id,
                "name": name,
                "x": int(raw["x"]),
                "y": int(raw["y"]),
                "height": int(raw.get("height", 3)),
            })
        if objects:
            objects.sort(key=lambda obj: (obj["y"], obj["x"], obj["id"]))
            return objects
    except Exception:
        pass
    return list(FALLBACK_OBSTACLES)


def compact_player(player):
    skills = player.get("skills") or {}
    agility = skills.get("agility") or {}
    payload = {
        "tile": tile(player),
        "hp": int(player.get("hp", player.get("hitpoints", 0)) or 0),
        "maxHp": int(player.get("maxHp", player.get("maxHitpoints", 0)) or 0),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled")),
        "isDead": bool(player.get("isDead")),
        "isInCombat": bool(player.get("isInCombat")),
        "isPoisoned": bool(player.get("isPoisoned")),
        "freeInventorySlots": int(player.get("freeInventorySlots", player.get("freeSlots", -1)) or -1),
        "agilityLevel": int(agility.get("level", 0) or 0),
        "agilityXp": int(float(agility.get("xp", 0) or 0)),
        "tickets": bridge.count_inventory_item(player, TICKET),
        "coins": bridge.count_inventory_item(player, COINS),
    }
    if player.get("_serverTick") is not None:
        payload["serverTick"] = int(player.get("_serverTick"))
    return payload


def write_event(handle, event, **data):
    global LAST_EVENT_AT, LAST_SERVER_TICK, LAST_EVENT_INDEX
    preserve_timing = bool(data.pop("_preserveTiming", False))
    now = time.monotonic()
    elapsed = now - RUN_STARTED_AT
    delta = 0.0 if LAST_EVENT_AT is None else now - LAST_EVENT_AT
    LAST_EVENT_INDEX += 1
    payload = {"event": event, "eventIndex": LAST_EVENT_INDEX, "timestamp": utc_now(), "isAgilityCourse": True}
    payload["elapsedSeconds"] = round(elapsed, 3)
    payload["deltaSeconds"] = round(delta, 3)
    payload["deltaTicks"] = int(round(delta / TICK_SECONDS))
    payload.update(data)
    player = payload.get("player")
    if isinstance(player, dict) and player.get("serverTick") is not None:
        server_tick = int(player.get("serverTick"))
        payload["serverTick"] = server_tick
        if LAST_SERVER_TICK is not None:
            payload["deltaServerTicks"] = server_tick - int(LAST_SERVER_TICK)
        if not preserve_timing:
            LAST_SERVER_TICK = server_tick
    if not preserve_timing:
        LAST_EVENT_AT = now
    handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def attach_server_tick(result, player):
    tick_value = None
    if isinstance(result, dict):
        if result.get("serverTick") is not None:
            tick_value = result.get("serverTick")
        elif isinstance(result.get("state"), dict) and result["state"].get("serverTick") is not None:
            tick_value = result["state"].get("serverTick")
    if tick_value is not None:
        try:
            player = dict(player)
            player["_serverTick"] = int(tick_value)
        except (TypeError, ValueError):
            pass
    return player


def player_from_result(result):
    return attach_server_tick(result, bridge.player_from(result))


def observe_xs_with_tick(profile):
    return player_from_result(bridge.call_tool("observe_state_XS", {}, profile=profile))


def stop_requested(profile):
    return runner_paths(profile)["stop"].exists()


def clear_stop(profile):
    try:
        runner_paths(profile)["stop"].unlink()
    except FileNotFoundError:
        pass


def active_dispenser(now=None):
    now = time.time() if now is None else float(now)
    return int(abs(int(now // 60)) % len(DISPENSERS))


def dispenser_window(now=None):
    now = time.time() if now is None else float(now)
    return int(now // 60)


def seconds_until_next_window(now=None):
    now = time.time() if now is None else float(now)
    return max(0.0, 60.0 - (now % 60.0))


def target_reached(player, target_level):
    return int(compact_player(player)["agilityLevel"]) >= int(target_level)


def ensure_run(player, args):
    if int(player.get("runEnergy", 0) or 0) < int(args.min_run_energy):
        return player
    if bool(player.get("runEnabled")):
        return player
    return player_from_result(bridge.call_tool("set_run_XS", {"enabled": True}, profile=args.profile))


def heal_if_needed(player, args):
    hp = int(player.get("hp", player.get("hitpoints", 0)) or 0)
    if hp <= int(args.eat_at):
        result = bridge.call_tool("eat_best_food_XXS", {}, profile=args.profile)
        healed = player_from_result(result)
        if not (healed.get("skills") or {}).get("agility"):
            return observe_xs_with_tick(args.profile)
        return healed
    return player


def out_of_food_at_risk(player, args):
    hp = int(player.get("hp", player.get("hitpoints", 0)) or 0)
    return count_any_inventory(player, FOOD_ITEM_IDS) <= 0 and hp <= int(args.eat_at)


def in_arena(player):
    t = tile(player)
    return int(t.get("height", 0)) == 3 and 2760 <= int(t["x"]) <= 2810 and 9543 <= int(t["y"]) <= 9593


def enter_arena(args, handle):
    player = observe_xs_with_tick(args.profile)
    player = ensure_run(player, args)
    if in_arena(player):
        return player
    last_result = {}
    for attempt in range(1, 5):
        result = interact_npc_with_walk(CAPN_IZZY, args, max_distance=8)
        last_result = result
        player = player_from_result(result)
        write_event(handle, "enter_arena", attempt=attempt, success=bool(result.get("success")),
                    message=result.get("message"), player=compact_player(player))
        for _ in range(3):
            if in_arena(player):
                return player
            bridge.call_tool("wait_ticks_XS", {"ticks": 3}, profile=args.profile)
            player = observe_xs_with_tick(args.profile)
            if in_arena(player):
                write_event(handle, "enter_arena_arrived", attempt=attempt,
                            player=compact_player(player))
                return player
        player = ensure_run(player, args)
    write_event(handle, "enter_arena_failed", success=bool(last_result.get("success")),
                message=last_result.get("message"), player=compact_player(player))
    return player


def interact_npc_with_walk(npc_id, args, max_distance=8):
    arguments = {
        "npcId": CAPN_IZZY,
        "option": "first",
        "requireReachable": True,
        "maxDistance": int(max_distance),
    }
    arguments["npcId"] = int(npc_id)
    result = {}
    for _ in range(3):
        result = bridge.call_tool("interact_npc", arguments, profile=args.profile)
        if "walking toward" not in str(result.get("message", "")).lower():
            return result
        bridge.call_tool("wait_until_idle_XS", {"maxTicks": 24}, profile=args.profile)
    return result


def walk_to(tile_target, args):
    result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
        "x": int(tile_target["x"]),
        "y": int(tile_target["y"]),
        "height": int(tile_target.get("height", 0)),
        "maxTicks": 80,
    }, profile=args.profile)
    return player_from_result(result), result


def tag_dispenser(index, args, handle):
    target = DISPENSERS[index]
    player = observe_xs_with_tick(args.profile)
    player = ensure_run(player, args)
    player = heal_if_needed(player, args)
    if args.walk_to_dispenser and tile_dist(tile(player), target) > int(args.tag_radius):
        player, walk_result = walk_to(target, args)
        write_event(handle, "walk_to_dispenser", target=target,
                    success=bool(walk_result.get("success")), player=compact_player(player))
    if tile_dist(tile(player), target) > int(args.tag_radius):
        write_event(handle, "tag_skip", dispenser=index, target=target,
                    reason="not_on_target_platform", player=compact_player(player))
        return player, False
    if player.get("isDead") or player.get("isInCombat"):
        return player, False
    before_tickets = bridge.count_inventory_item(player, TICKET)
    window = dispenser_window()
    result = bridge.call_tool("interact_object_XS", {
        "objectId": int(target.get("id", TICKET_DISPENSER_ID)),
        "x": target["x"],
        "y": target["y"],
        "height": target["height"],
        "option": "first",
        "requireReachable": False,
        "directIfUnreachable": True,
    }, profile=args.profile)
    player = player_from_result(result)
    after_tickets = bridge.count_inventory_item(player, TICKET)
    write_event(handle, "tag_dispenser", dispenser=index, target=target,
                activeWindow=window,
                success=bool(result.get("success")), message=result.get("message"),
                ticketsGained=max(0, after_tickets - before_tickets), player=compact_player(player))
    return player, bool(result.get("success"))


def candidate_brief(item):
    score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance = item
    target_delta = int(predicted_target_distance) - int(current_target_distance)
    return {
        "objectId": int(obj["id"]),
        "name": obj.get("name"),
        "isBladeCandidate": int(obj["id"]) in BLADE_OBSTACLE_IDS,
        "objectTile": {"x": int(obj["x"]), "y": int(obj["y"]), "height": int(obj.get("height", 3))},
        "distance": int(distance),
        "score": int(score),
        "predictedTile": predicted,
        "currentTargetDistance": int(current_target_distance),
        "predictedTargetDistance": int(predicted_target_distance),
        "targetDistanceDelta": target_delta,
        "scorePenalties": penalties,
        "selectionReason": selection_reason(obj, target_delta, penalties),
    }


def candidate_briefs(candidates, limit=3):
    return [candidate_brief(item) for item in candidates[:max(0, int(limit))]]


def blade_risk_penalty(penalties):
    return (
        int(penalties.get("bladeRepeat", 0) or 0)
        + int(penalties.get("bladeBacktrack", 0) or 0)
        + int(penalties.get("bladeDamageRisk", 0) or 0)
        + int(penalties.get("bladeAway", 0) or 0)
        + int(penalties.get("bladeWeakProgress", 0) or 0)
    )


def loop_risk_penalty(penalties):
    return (
        int((penalties or {}).get("weakRepeatLoop", 0) or 0)
        + int((penalties or {}).get("weakReverseLoop", 0) or 0)
        + int((penalties or {}).get("repeatAway", 0) or 0)
        + int((penalties or {}).get("noProgressRepeat", 0) or 0)
        + int((penalties or {}).get("noProgressReverse", 0) or 0)
        + int((penalties or {}).get("edgeRepeat", 0) or 0)
        + int((penalties or {}).get("reverse", 0) or 0)
    )


def candidate_target_delta(item):
    return int(item[5]) - int(item[7])


def is_blade_candidate_item(item):
    return int(item[2]["id"]) in BLADE_OBSTACLE_IDS


def selection_reason(obj, target_delta, penalties):
    reasons = []
    object_id = int(obj["id"])
    if target_delta < 0:
        reasons.append("toward_target")
    elif target_delta == 0:
        reasons.append("neutral_target")
    else:
        reasons.append("away_from_target")
    if object_id in ZERO_XP_OBSTACLE_IDS:
        reasons.append("zero_xp_blade")
    elif object_id in BLADE_OBSTACLE_IDS:
        if target_delta <= -7:
            reasons.append("blade_strong_progress")
        elif target_delta < 0:
            reasons.append("blade_weak_progress")
        else:
            reasons.append("blade_away")
    if int(penalties.get("edgeRepeat", 0) or 0) or int(penalties.get("edgeRepeatCount", 0) or 0):
        reasons.append("repeat_edge")
    if int(penalties.get("reverse", 0) or 0):
        reasons.append("reverse_edge")
    if int(penalties.get("weakRepeatLoop", 0) or 0) or int(penalties.get("weakReverseLoop", 0) or 0):
        reasons.append("loop_risk")
    if int(penalties.get("progressAvailable", 0) or 0):
        reasons.append("better_progress_available")
    if int(penalties.get("recentDestination", 0) or 0) or int(penalties.get("recentObject", 0) or 0):
        reasons.append("recent_repeat")
    return ",".join(reasons[:6])


def safe_progress_approach_candidate(candidates, nearby_score, nearby_target_delta, args, force_progress=False):
    for item in candidates:
        score, distance, obj, _predicted, _key, _predicted_target_distance, penalties, _current_target_distance = item
        if int(distance) <= int(args.obstacle_radius):
            continue
        if int(obj["id"]) in BLADE_OBSTACLE_IDS:
            continue
        if int(penalties.get("zeroXp", 0) or 0) > 0:
            continue
        target_delta = candidate_target_delta(item)
        if target_delta >= 0:
            continue
        if force_progress or score + int(args.approach_preference_margin) < nearby_score or nearby_target_delta > 0:
            return item
    return None


def should_escape_failed_approach(fallback_item, preferred_item, args):
    if fallback_item is None or preferred_item is None:
        return False
    preferred_distance = int(preferred_item[1])
    max_escape_distance = min(int(args.loop_escape_click_radius), int(args.obstacle_radius))
    if preferred_distance > max_escape_distance:
        return False
    preferred_delta = candidate_target_delta(preferred_item)
    if preferred_delta > LOOP_ESCAPE_MIN_PROGRESS:
        return False
    fallback_penalties = fallback_item[6] or {}
    if loop_risk_penalty(fallback_penalties) <= 0:
        return False
    fallback_delta = candidate_target_delta(fallback_item)
    if fallback_delta < 0 and not (
            int(fallback_penalties.get("edgeRepeat", 0) or 0)
            or int(fallback_penalties.get("reverse", 0) or 0)):
        return False
    return True


def safe_nearby_fallback_candidate(candidates):
    for item in candidates:
        penalties = item[6] or {}
        if is_blade_candidate_item(item):
            continue
        if int(penalties.get("zeroXp", 0) or 0) > 0:
            continue
        if loop_risk_penalty(penalties) > 0:
            continue
        if candidate_target_delta(item) >= 0:
            continue
        return item
    return None


def should_suppress_failed_approach_fallback(item):
    if item is None:
        return False
    penalties = item[6] or {}
    target_delta = candidate_target_delta(item)
    if target_delta > 0 and loop_risk_penalty(penalties) > 0:
        return True
    if target_delta >= 0 and (
            int(penalties.get("edgeRepeat", 0) or 0)
            or int(penalties.get("reverse", 0) or 0)
            or int(penalties.get("weakRepeatLoop", 0) or 0)):
        return True
    return False


def choose_failed_approach_fallback(candidates, preferred_item, args):
    if not candidates:
        return None, False, "no_nearby_fallback"
    fallback_item = candidates[0]
    if should_escape_failed_approach(fallback_item, preferred_item, args):
        return preferred_item, True, None
    safe_item = safe_nearby_fallback_candidate(candidates)
    if safe_item is not None:
        return safe_item, False, None
    if should_suppress_failed_approach_fallback(fallback_item):
        return fallback_item, False, "loop_risk_away_fallback"
    return fallback_item, False, None


def obstacle_candidates(player, objects, args, seen_counts, no_move_counts, recent_tiles, recent_edges,
                        recent_object_keys, max_distance, target_override=None):
    player_tile = tile(player)
    player_tile_key = tile_key(player_tile)
    target = candidate_target(target_override)
    current_target_distance = tile_dist(player_tile, target)
    candidates = []
    for obj in objects:
        distance = tile_dist(player_tile, obj)
        if distance > int(max_distance):
            continue
        predicted = predicted_destination(player_tile, obj)
        predicted_key = tile_key(predicted)
        key = "{}:{}:{}".format(obj["id"], obj["x"], obj["y"])
        predicted_target_distance = tile_dist(predicted, target)
        backtrack_penalty = 220 if predicted_target_distance > current_target_distance else 0
        target_delta = predicted_target_distance - current_target_distance
        if target_delta > 0:
            progress_penalty = min(900, 260 + target_delta * 45)
        elif target_delta == 0:
            progress_penalty = 120
        else:
            progress_penalty = 0
        reverse_penalty = REVERSE_EDGE_PENALTY if (predicted_key, player_tile_key) in recent_edges else 0
        edge_repeat_penalty = EDGE_REPEAT_PENALTY if (player_tile_key, predicted_key) in recent_edges else 0
        recent_edge_count = sum(
            1 for edge in recent_edges
            if edge == (player_tile_key, predicted_key) or edge == (predicted_key, player_tile_key)
        )
        edge_repeat_count_penalty = 0
        if recent_edge_count > 0:
            edge_repeat_count_penalty = min(3200, recent_edge_count * EDGE_REPEAT_COUNT_PENALTY)
        repeated_away_penalty = 0
        if recent_edge_count > 0 and target_delta > 0:
            repeated_away_penalty = REPEATED_AWAY_EDGE_PENALTY
        no_progress_repeat_penalty = 0
        if recent_edge_count > 0 and target_delta == 0:
            no_progress_repeat_penalty = NO_PROGRESS_REPEAT_PENALTY
        no_progress_reverse_penalty = 0
        if reverse_penalty and target_delta >= 0:
            no_progress_reverse_penalty = NO_PROGRESS_REVERSE_PENALTY
        weak_repeat_loop_penalty = 0
        if recent_edge_count > 0 and target_delta > -5:
            weak_repeat_loop_penalty = min(5200, WEAK_REPEAT_LOOP_PENALTY + recent_edge_count * 900)
        weak_reverse_loop_penalty = 0
        if reverse_penalty and target_delta > -7:
            weak_reverse_loop_penalty = WEAK_REVERSE_LOOP_PENALTY
        is_blade_obstacle = int(obj["id"]) in BLADE_OBSTACLE_IDS
        blade_repeat_penalty = 0
        if is_blade_obstacle and (reverse_penalty or edge_repeat_penalty):
            blade_repeat_penalty = BLADE_REPEAT_PENALTY
        blade_backtrack_penalty = 0
        if is_blade_obstacle and target_delta > 0:
            blade_backtrack_penalty = BLADE_BACKTRACK_PENALTY
        blade_damage_risk_penalty = 0
        if is_blade_obstacle and target_delta > -8:
            blade_damage_risk_penalty = BLADE_DAMAGE_RISK_PENALTY
        blade_away_penalty = 0
        if is_blade_obstacle and target_delta >= 0:
            blade_away_penalty = BLADE_AWAY_PENALTY
        blade_weak_progress_penalty = 0
        if is_blade_obstacle and -7 < target_delta < 0:
            blade_weak_progress_penalty = BLADE_WEAK_PROGRESS_PENALTY
        recent_destination_penalty = 0
        for recency, recent_tile in enumerate(reversed(recent_tiles)):
            if predicted_key == recent_tile:
                recent_destination_penalty = max(recent_destination_penalty, max(80, 420 - recency * 60))
        recent_object_penalty = 0
        for recency, recent_key in enumerate(reversed(recent_object_keys)):
            if key == recent_key:
                recent_object_penalty = max(recent_object_penalty, max(120, 600 - recency * 80))
        zero_xp_penalty = ZERO_XP_OBSTACLE_PENALTY if int(obj["id"]) in ZERO_XP_OBSTACLE_IDS else 0
        if predicted_target_distance + 18 < current_target_distance:
            zero_xp_penalty = max(1800, zero_xp_penalty - 700)
        score = (
            predicted_target_distance * 10
            + int(seen_counts.get(key, 0)) * 12
            + int(no_move_counts.get(key, 0)) * 80
            + backtrack_penalty
            + progress_penalty
            + reverse_penalty
            + edge_repeat_penalty
            + edge_repeat_count_penalty
            + repeated_away_penalty
            + no_progress_repeat_penalty
            + no_progress_reverse_penalty
            + weak_repeat_loop_penalty
            + weak_reverse_loop_penalty
            + blade_repeat_penalty
            + blade_backtrack_penalty
            + blade_damage_risk_penalty
            + blade_away_penalty
            + blade_weak_progress_penalty
            + recent_destination_penalty
            + recent_object_penalty
            + zero_xp_penalty
            + distance
        )
        penalties = {
            "backtrack": backtrack_penalty,
            "progress": progress_penalty,
            "reverse": reverse_penalty,
            "edgeRepeat": edge_repeat_penalty,
            "edgeRepeatCount": edge_repeat_count_penalty,
            "repeatAway": repeated_away_penalty,
            "noProgressRepeat": no_progress_repeat_penalty,
            "noProgressReverse": no_progress_reverse_penalty,
            "weakRepeatLoop": weak_repeat_loop_penalty,
            "weakReverseLoop": weak_reverse_loop_penalty,
            "bladeRepeat": blade_repeat_penalty,
            "bladeBacktrack": blade_backtrack_penalty,
            "bladeDamageRisk": blade_damage_risk_penalty,
            "bladeAway": blade_away_penalty,
            "bladeWeakProgress": blade_weak_progress_penalty,
            "recentDestination": recent_destination_penalty,
            "recentObject": recent_object_penalty,
            "zeroXp": zero_xp_penalty,
        }
        candidates.append((score, distance, obj, predicted, key, predicted_target_distance, penalties,
                           current_target_distance))
    if candidates:
        best_delta = min(int(item[5]) - int(item[7]) for item in candidates)
        if best_delta < 0:
            adjusted = []
            for score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance in candidates:
                target_delta = int(predicted_target_distance) - int(current_target_distance)
                progress_available_penalty = 0
                if target_delta > 0:
                    progress_available_penalty = min(1800, 1000 + target_delta * 80)
                elif target_delta == 0:
                    progress_available_penalty = 650
                if progress_available_penalty:
                    penalties = dict(penalties)
                    penalties["progressAvailable"] = progress_available_penalty
                    score += progress_available_penalty
                adjusted.append((score, distance, obj, predicted, key, predicted_target_distance, penalties,
                                 current_target_distance))
            candidates = adjusted
    candidates.sort(key=lambda item: (item[0], item[1], item[2]["id"], item[2]["x"], item[2]["y"]))
    return candidates


def should_prefer_approach(nearby_score, nearby_penalties, nearby_target_delta,
                           wide_score, wide_distance, wide_target_delta, args):
    if wide_distance <= int(args.obstacle_radius):
        return False
    nearby_blade_risk = blade_risk_penalty(nearby_penalties) > 0
    if not nearby_blade_risk and int(nearby_penalties.get("zeroXp", 0)) <= 0 and wide_target_delta > -5:
        return False
    if not nearby_blade_risk and nearby_target_delta < 0 and int(nearby_penalties.get("zeroXp", 0)) <= 0:
        return False
    if wide_score + int(args.approach_preference_margin) >= nearby_score:
        return False
    if nearby_blade_risk and nearby_target_delta > 0:
        return True
    if int(nearby_penalties.get("zeroXp", 0)) > 0:
        return True
    if int(nearby_penalties.get("recentDestination", 0)) >= 120:
        return True
    if int(nearby_penalties.get("recentObject", 0)) >= 120:
        return True
    if int(nearby_penalties.get("reverse", 0)) > 0:
        return True
    return False


def nearby_obstacle_candidates(player, objects, args, seen_counts, no_move_counts, recent_tiles, recent_edges,
                               recent_object_keys, target_override=None):
    return obstacle_candidates(player, objects, args, seen_counts, no_move_counts,
                               recent_tiles, recent_edges, recent_object_keys,
                               int(args.obstacle_radius), target_override=target_override)


def approach_obstacle(player, objects, args, handle, seen_counts, no_move_counts, recent_tiles, recent_edges,
                      recent_object_keys, target_override=None, target_reason=None, preferred_key=None):
    candidates = obstacle_candidates(player, objects, args, seen_counts, no_move_counts,
                                     recent_tiles, recent_edges, recent_object_keys,
                                     int(args.approach_radius), target_override=target_override)
    if not candidates:
        write_event(handle, "obstacle_approach_stall", reason="no_candidate_in_approach_radius",
                    activeDispenser=active_dispenser(), activeTarget=active_target(),
                    navigationTarget=candidate_target(target_override), navigationTargetReason=target_reason,
                    player=compact_player(player))
        return player, False
    selected = candidates[0]
    if preferred_key is not None:
        for candidate in candidates:
            if candidate[4] == preferred_key:
                selected = candidate
                break
    score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance = selected
    approach = obstacle_approach_tile(tile(player), obj, int(args.obstacle_radius))
    try:
        result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
            "x": int(approach["x"]),
            "y": int(approach["y"]),
            "height": int(approach.get("height", 3)),
            "maxTicks": int(args.approach_max_ticks),
        }, profile=args.profile)
    except RuntimeError as exc:
        after_player = observe_xs_with_tick(args.profile)
        after_tile = tile(after_player)
        close_after_error = tile_dist(after_tile, obj) <= int(args.obstacle_radius)
        if not close_after_error:
            no_move_counts[key] = int(no_move_counts.get(key, 0)) + 3
        write_event(handle, "obstacle_approach",
                    objectId=int(obj["id"]), name=obj.get("name"),
                    objectTile={"x": int(obj["x"]), "y": int(obj["y"]), "height": int(obj.get("height", 3))},
                    distance=distance, score=score, predictedTile=predicted,
                    currentTargetDistance=current_target_distance,
                    predictedTargetDistance=predicted_target_distance, scorePenalties=penalties,
                    targetDistanceDelta=predicted_target_distance - current_target_distance,
                    topCandidates=candidate_briefs(candidates),
                    approachTile=approach,
                    activeDispenser=active_dispenser(), activeTarget=active_target(),
                    navigationTarget=candidate_target(target_override), navigationTargetReason=target_reason,
                    success=close_after_error,
                    partialSuccess=close_after_error,
                    message=str(exc), player=compact_player(after_player))
        return after_player, close_after_error
    after_player = player_from_result(result)
    write_event(handle, "obstacle_approach",
                objectId=int(obj["id"]), name=obj.get("name"),
                objectTile={"x": int(obj["x"]), "y": int(obj["y"]), "height": int(obj.get("height", 3))},
                distance=distance, score=score, predictedTile=predicted,
                currentTargetDistance=current_target_distance,
                predictedTargetDistance=predicted_target_distance, scorePenalties=penalties,
                targetDistanceDelta=predicted_target_distance - current_target_distance,
                topCandidates=candidate_briefs(candidates),
                approachTile=approach,
                activeDispenser=active_dispenser(), activeTarget=active_target(),
                navigationTarget=candidate_target(target_override), navigationTargetReason=target_reason,
                success=bool(result.get("success")), message=result.get("message"),
                player=compact_player(after_player))
    return after_player, bool(result.get("success"))


def obstacle_step(player, objects, args, handle, seen_counts, no_move_counts, recent_tiles, recent_edges,
                  recent_object_keys, target_override=None, target_reason=None):
    player = ensure_run(player, args)
    player = heal_if_needed(player, args)
    if args.no_restock and out_of_food_at_risk(player, args):
        write_event(handle, "obstacle_skip",
                    reason="no_food_low_hp", player=compact_player(player))
        return player, False
    if player.get("isDead") or player.get("isInCombat"):
        return player, False
    before = compact_player(player)
    candidates = nearby_obstacle_candidates(player, objects, args, seen_counts, no_move_counts,
                                            recent_tiles, recent_edges, recent_object_keys,
                                            target_override=target_override)
    if not candidates:
        return approach_obstacle(player, objects, args, handle, seen_counts, no_move_counts,
                                 recent_tiles, recent_edges, recent_object_keys,
                                 target_override=target_override, target_reason=target_reason)
    score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance = candidates[0]
    selected_target_delta = int(predicted_target_distance) - int(current_target_distance)
    selected_reason = selection_reason(obj, selected_target_delta, penalties)
    escape_click = False
    wide_candidates = obstacle_candidates(player, objects, args, seen_counts, no_move_counts,
                                          recent_tiles, recent_edges, recent_object_keys,
                                          int(args.approach_radius), target_override=target_override)
    if wide_candidates:
        wide_score, wide_distance, wide_obj, wide_predicted, wide_key, wide_predicted_target_distance, wide_penalties, wide_current_target_distance = wide_candidates[0]
        nearby_target_delta = int(predicted_target_distance) - int(current_target_distance)
        wide_target_delta = int(wide_predicted_target_distance) - int(wide_current_target_distance)
        prefer_approach = should_prefer_approach(score, penalties, nearby_target_delta,
                                                 wide_score, wide_distance, wide_target_delta, args)
        if prefer_approach and int(wide_obj["id"]) in BLADE_OBSTACLE_IDS:
            nearby_force_progress = int((penalties or {}).get("zeroXp", 0) or 0) > 0 or is_blade_candidate_item(
                (score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance))
            safe_candidate = safe_progress_approach_candidate(
                wide_candidates, score, nearby_target_delta, args, force_progress=nearby_force_progress)
            if safe_candidate is not None:
                safe_score, safe_distance, safe_obj, safe_predicted, safe_key, safe_predicted_target_distance, safe_penalties, safe_current_target_distance = safe_candidate
                write_event(handle, "obstacle_approach_redirected",
                            reason="avoid_walk_approach_to_blade",
                            message="using_non_blade_progress_candidate",
                            nearbyObjectId=int(obj["id"]), nearbyName=obj.get("name"),
                            nearbyScore=score, nearbyDistance=distance,
                            nearbyBladeRiskPenalty=blade_risk_penalty(penalties),
                            nearbyPredictedTile=predicted,
                            nearbyCurrentTargetDistance=current_target_distance,
                            nearbyPredictedTargetDistance=predicted_target_distance,
                            nearbyTargetDistanceDelta=predicted_target_distance - current_target_distance,
                            nearbyScorePenalties=penalties,
                            preferredObjectId=int(wide_obj["id"]), preferredName=wide_obj.get("name"),
                            preferredScore=wide_score, preferredDistance=wide_distance,
                            preferredBladeRiskPenalty=blade_risk_penalty(wide_penalties),
                            preferredPredictedTile=wide_predicted,
                            preferredCurrentTargetDistance=wide_current_target_distance,
                            preferredPredictedTargetDistance=wide_predicted_target_distance,
                            preferredTargetDistanceDelta=wide_predicted_target_distance - wide_current_target_distance,
                            preferredScorePenalties=wide_penalties,
                            selectedObjectId=int(safe_obj["id"]), selectedName=safe_obj.get("name"),
                            selectedScore=safe_score, selectedDistance=safe_distance,
                            selectedPredictedTile=safe_predicted,
                            selectedCurrentTargetDistance=safe_current_target_distance,
                            selectedPredictedTargetDistance=safe_predicted_target_distance,
                            selectedTargetDistanceDelta=safe_predicted_target_distance - safe_current_target_distance,
                            selectedScorePenalties=safe_penalties,
                            nearbyTopCandidates=candidate_briefs(candidates),
                            preferredTopCandidates=candidate_briefs(wide_candidates),
                            activeDispenser=active_dispenser(), activeTarget=active_target(),
                            navigationTarget=candidate_target(target_override), navigationTargetReason=target_reason,
                            player=before)
                approached_player, approached = approach_obstacle(
                    player, objects, args, handle, seen_counts, no_move_counts,
                    recent_tiles, recent_edges, recent_object_keys,
                    target_override=target_override, target_reason=target_reason,
                    preferred_key=safe_key)
                if approached:
                    return approached_player, True
                player = approached_player
                before = compact_player(player)
                candidates = nearby_obstacle_candidates(
                    player, objects, args, seen_counts, no_move_counts,
                    recent_tiles, recent_edges, recent_object_keys,
                    target_override=target_override)
                if not candidates:
                    return player, False
                selected_item, escape_click, suppress_reason = choose_failed_approach_fallback(
                    candidates, safe_candidate, args)
                if suppress_reason is not None:
                    write_event(handle, "obstacle_approach_fallback_suppressed",
                                reason=suppress_reason,
                                preferredObjectId=int(safe_obj["id"]), preferredName=safe_obj.get("name"),
                                preferredScore=safe_score, preferredDistance=safe_distance,
                                preferredPredictedTile=safe_predicted,
                                preferredCurrentTargetDistance=safe_current_target_distance,
                                preferredPredictedTargetDistance=safe_predicted_target_distance,
                                preferredTargetDistanceDelta=safe_predicted_target_distance - safe_current_target_distance,
                                preferredScorePenalties=safe_penalties,
                                nearbyTopCandidates=candidate_briefs(candidates),
                                activeDispenser=active_dispenser(), activeTarget=active_target(),
                                navigationTarget=candidate_target(target_override),
                                navigationTargetReason=target_reason, player=before)
                    return player, False
                score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance = selected_item
                selected_target_delta = int(predicted_target_distance) - int(current_target_distance)
                selected_reason = selection_reason(obj, selected_target_delta, penalties)
                write_event(handle, "obstacle_approach_fallback_click",
                            reason="redirected_approach_failed_using_nearby_candidate",
                            objectId=int(obj["id"]), name=obj.get("name"),
                            distance=distance, score=score, predictedTile=predicted,
                            currentTargetDistance=current_target_distance,
                            predictedTargetDistance=predicted_target_distance,
                            targetDistanceDelta=predicted_target_distance - current_target_distance,
                            selectionReason=selected_reason,
                            escapeClick=escape_click,
                            scorePenalties=penalties, topCandidates=candidate_briefs(candidates),
                            activeDispenser=active_dispenser(), activeTarget=active_target(),
                            navigationTarget=candidate_target(target_override),
                            navigationTargetReason=target_reason, player=before)
            elif int(wide_obj["id"]) not in ZERO_XP_OBSTACLE_IDS and wide_target_delta <= -7 and not (
                    wide_penalties.get("bladeRepeat") or wide_penalties.get("bladeBacktrack")):
                write_event(handle, "obstacle_approach_blade_allowed",
                            reason="meaningful_spinning_blade_progress",
                            nearbyObjectId=int(obj["id"]), nearbyName=obj.get("name"),
                            nearbyScore=score, nearbyDistance=distance,
                            nearbyBladeRiskPenalty=blade_risk_penalty(penalties),
                            nearbyPredictedTile=predicted,
                            nearbyCurrentTargetDistance=current_target_distance,
                            nearbyPredictedTargetDistance=predicted_target_distance,
                            nearbyTargetDistanceDelta=predicted_target_distance - current_target_distance,
                            nearbyScorePenalties=penalties,
                            preferredObjectId=int(wide_obj["id"]), preferredName=wide_obj.get("name"),
                            preferredScore=wide_score, preferredDistance=wide_distance,
                            preferredBladeRiskPenalty=blade_risk_penalty(wide_penalties),
                            preferredPredictedTile=wide_predicted,
                            preferredCurrentTargetDistance=wide_current_target_distance,
                            preferredPredictedTargetDistance=wide_predicted_target_distance,
                            preferredTargetDistanceDelta=wide_predicted_target_distance - wide_current_target_distance,
                            preferredScorePenalties=wide_penalties,
                            nearbyTopCandidates=candidate_briefs(candidates),
                            preferredTopCandidates=candidate_briefs(wide_candidates),
                            activeDispenser=active_dispenser(), activeTarget=active_target(),
                            navigationTarget=candidate_target(target_override), navigationTargetReason=target_reason,
                            player=before)
                approached_player, approached = approach_obstacle(
                    player, objects, args, handle, seen_counts, no_move_counts,
                    recent_tiles, recent_edges, recent_object_keys,
                    target_override=target_override, target_reason=target_reason,
                    preferred_key=wide_key)
                if approached:
                    return approached_player, True
                player = approached_player
                before = compact_player(player)
                candidates = nearby_obstacle_candidates(
                    player, objects, args, seen_counts, no_move_counts,
                    recent_tiles, recent_edges, recent_object_keys,
                    target_override=target_override)
                if not candidates:
                    return player, False
                preferred_item = (wide_score, wide_distance, wide_obj, wide_predicted, wide_key,
                                  wide_predicted_target_distance, wide_penalties, wide_current_target_distance)
                selected_item, escape_click, suppress_reason = choose_failed_approach_fallback(
                    candidates, preferred_item, args)
                if suppress_reason is not None:
                    write_event(handle, "obstacle_approach_fallback_suppressed",
                                reason=suppress_reason,
                                preferredObjectId=int(wide_obj["id"]), preferredName=wide_obj.get("name"),
                                preferredScore=wide_score, preferredDistance=wide_distance,
                                preferredPredictedTile=wide_predicted,
                                preferredCurrentTargetDistance=wide_current_target_distance,
                                preferredPredictedTargetDistance=wide_predicted_target_distance,
                                preferredTargetDistanceDelta=wide_predicted_target_distance - wide_current_target_distance,
                                preferredScorePenalties=wide_penalties,
                                nearbyTopCandidates=candidate_briefs(candidates),
                                activeDispenser=active_dispenser(), activeTarget=active_target(),
                                navigationTarget=candidate_target(target_override),
                                navigationTargetReason=target_reason, player=before)
                    return player, False
                score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance = selected_item
                selected_target_delta = int(predicted_target_distance) - int(current_target_distance)
                selected_reason = selection_reason(obj, selected_target_delta, penalties)
                write_event(handle, "obstacle_approach_fallback_click",
                            reason="blade_approach_failed_using_nearby_candidate",
                            objectId=int(obj["id"]), name=obj.get("name"),
                            distance=distance, score=score, predictedTile=predicted,
                            currentTargetDistance=current_target_distance,
                            predictedTargetDistance=predicted_target_distance,
                            targetDistanceDelta=predicted_target_distance - current_target_distance,
                            selectionReason=selected_reason,
                            escapeClick=escape_click,
                            scorePenalties=penalties, topCandidates=candidate_briefs(candidates),
                            activeDispenser=active_dispenser(), activeTarget=active_target(),
                            navigationTarget=candidate_target(target_override),
                            navigationTargetReason=target_reason, player=before)
            else:
                write_event(handle, "obstacle_approach_suppressed",
                            reason="avoid_walk_approach_to_blade",
                            nearbyObjectId=int(obj["id"]), nearbyName=obj.get("name"),
                            nearbyScore=score, nearbyDistance=distance,
                            nearbyBladeRiskPenalty=blade_risk_penalty(penalties),
                            nearbyPredictedTile=predicted,
                            nearbyCurrentTargetDistance=current_target_distance,
                            nearbyPredictedTargetDistance=predicted_target_distance,
                            nearbyTargetDistanceDelta=predicted_target_distance - current_target_distance,
                            nearbyScorePenalties=penalties,
                            preferredObjectId=int(wide_obj["id"]), preferredName=wide_obj.get("name"),
                            preferredScore=wide_score, preferredDistance=wide_distance,
                            preferredBladeRiskPenalty=blade_risk_penalty(wide_penalties),
                            preferredPredictedTile=wide_predicted,
                            preferredCurrentTargetDistance=wide_current_target_distance,
                            preferredPredictedTargetDistance=wide_predicted_target_distance,
                            preferredTargetDistanceDelta=wide_predicted_target_distance - wide_current_target_distance,
                            preferredScorePenalties=wide_penalties,
                            nearbyTopCandidates=candidate_briefs(candidates),
                            preferredTopCandidates=candidate_briefs(wide_candidates),
                            activeDispenser=active_dispenser(), activeTarget=active_target(),
                            navigationTarget=candidate_target(target_override), navigationTargetReason=target_reason,
                            player=before)
        elif prefer_approach:
            write_event(handle, "obstacle_prefer_approach",
                        reason="better_candidate_outside_click_radius",
                        nearbyObjectId=int(obj["id"]), nearbyName=obj.get("name"),
                        nearbyScore=score, nearbyDistance=distance,
                        nearbyBladeRiskPenalty=blade_risk_penalty(penalties),
                        nearbyPredictedTile=predicted,
                        nearbyCurrentTargetDistance=current_target_distance,
                        nearbyPredictedTargetDistance=predicted_target_distance,
                        nearbyTargetDistanceDelta=predicted_target_distance - current_target_distance,
                        nearbyScorePenalties=penalties,
                        preferredObjectId=int(wide_obj["id"]), preferredName=wide_obj.get("name"),
                        preferredScore=wide_score, preferredDistance=wide_distance,
                        preferredBladeRiskPenalty=blade_risk_penalty(wide_penalties),
                        preferredPredictedTile=wide_predicted,
                        preferredCurrentTargetDistance=wide_current_target_distance,
                        preferredPredictedTargetDistance=wide_predicted_target_distance,
                        preferredTargetDistanceDelta=wide_predicted_target_distance - wide_current_target_distance,
                        preferredScorePenalties=wide_penalties,
                        nearbyTopCandidates=candidate_briefs(candidates),
                        preferredTopCandidates=candidate_briefs(wide_candidates),
                        activeDispenser=active_dispenser(), activeTarget=active_target(),
                        navigationTarget=candidate_target(target_override), navigationTargetReason=target_reason,
                        player=before)
            approached_player, approached = approach_obstacle(
                player, objects, args, handle, seen_counts, no_move_counts,
                recent_tiles, recent_edges, recent_object_keys,
                target_override=target_override, target_reason=target_reason)
            if approached:
                return approached_player, True
            player = approached_player
            before = compact_player(player)
            candidates = nearby_obstacle_candidates(
                player, objects, args, seen_counts, no_move_counts,
                recent_tiles, recent_edges, recent_object_keys,
                target_override=target_override)
            if not candidates:
                return player, False
            preferred_item = (wide_score, wide_distance, wide_obj, wide_predicted, wide_key,
                              wide_predicted_target_distance, wide_penalties, wide_current_target_distance)
            selected_item, escape_click, suppress_reason = choose_failed_approach_fallback(
                candidates, preferred_item, args)
            if suppress_reason is not None:
                write_event(handle, "obstacle_approach_fallback_suppressed",
                            reason=suppress_reason,
                            preferredObjectId=int(wide_obj["id"]), preferredName=wide_obj.get("name"),
                            preferredScore=wide_score, preferredDistance=wide_distance,
                            preferredPredictedTile=wide_predicted,
                            preferredCurrentTargetDistance=wide_current_target_distance,
                            preferredPredictedTargetDistance=wide_predicted_target_distance,
                            preferredTargetDistanceDelta=wide_predicted_target_distance - wide_current_target_distance,
                            preferredScorePenalties=wide_penalties,
                            nearbyTopCandidates=candidate_briefs(candidates),
                            activeDispenser=active_dispenser(), activeTarget=active_target(),
                            navigationTarget=candidate_target(target_override),
                            navigationTargetReason=target_reason, player=before)
                return player, False
            score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance = selected_item
            selected_target_delta = int(predicted_target_distance) - int(current_target_distance)
            selected_reason = selection_reason(obj, selected_target_delta, penalties)
            write_event(handle, "obstacle_approach_fallback_click",
                        reason="approach_failed_using_nearby_candidate",
                        objectId=int(obj["id"]), name=obj.get("name"),
                        distance=distance, score=score, predictedTile=predicted,
                        currentTargetDistance=current_target_distance,
                        predictedTargetDistance=predicted_target_distance,
                        targetDistanceDelta=predicted_target_distance - current_target_distance,
                        selectionReason=selected_reason,
                        escapeClick=escape_click,
                        scorePenalties=penalties, topCandidates=candidate_briefs(candidates),
                        activeDispenser=active_dispenser(), activeTarget=active_target(),
                        navigationTarget=candidate_target(target_override),
                        navigationTargetReason=target_reason, player=before)
    if escape_click:
        write_event(handle, "obstacle_escape_click",
                    reason="avoid_failed_approach_loop_fallback",
                    objectId=int(obj["id"]), name=obj.get("name"),
                    distance=distance, score=score, predictedTile=predicted,
                    currentTargetDistance=current_target_distance,
                    predictedTargetDistance=predicted_target_distance,
                    targetDistanceDelta=predicted_target_distance - current_target_distance,
                    selectionReason=selected_reason,
                    scorePenalties=penalties,
                    activeDispenser=active_dispenser(), activeTarget=active_target(),
                    navigationTarget=candidate_target(target_override),
                    navigationTargetReason=target_reason, player=before)
    result = bridge.call_tool("interact_object_XS", {
        "objectId": int(obj["id"]),
        "x": int(obj["x"]),
        "y": int(obj["y"]),
        "height": int(obj.get("height", 3)),
        "option": "first",
        "requireReachable": False,
        "directIfUnreachable": True,
    }, profile=args.profile)
    if escape_click:
        try:
            bridge.call_tool("wait_until_idle_XS", {"maxTicks": int(args.approach_max_ticks)}, profile=args.profile)
        except RuntimeError:
            time.sleep(max(0.6, float(args.obstacle_wait_seconds)))
    else:
        time.sleep(max(0.6, float(args.obstacle_wait_seconds)))
    after_player = observe_xs_with_tick(args.profile)
    after = compact_player(after_player)
    moved = tile_key(before["tile"]) != tile_key(after["tile"])
    xp_gained = max(0, int(after["agilityXp"]) - int(before["agilityXp"]))
    hp_lost = max(0, int(before["hp"]) - int(after["hp"]))
    seen_counts[key] = int(seen_counts.get(key, 0)) + 1
    if xp_gained > 0 or (moved and hp_lost == 0):
        no_move_counts[key] = 0
    else:
        no_move_counts[key] = int(no_move_counts.get(key, 0)) + (4 if hp_lost > 0 else 1)
    before_key = tile_key(before["tile"])
    after_key = tile_key(after["tile"])
    predicted_key = tile_key(predicted)
    reverse_edge = (predicted_key, before_key) in recent_edges
    edge_repeat = (before_key, predicted_key) in recent_edges
    recent_edge_count = sum(1 for edge in recent_edges if edge == (before_key, predicted_key) or edge == (predicted_key, before_key))
    loop_risk_penalty = (
        int((penalties or {}).get("weakRepeatLoop", 0) or 0)
        + int((penalties or {}).get("weakReverseLoop", 0) or 0)
        + int((penalties or {}).get("repeatAway", 0) or 0)
        + blade_risk_penalty(penalties or {})
    )
    if loop_risk_penalty > 0 or edge_repeat or reverse_edge:
        write_event(handle, "obstacle_loop_risk",
                    objectId=int(obj["id"]), name=obj.get("name"),
                    objectTile={"x": int(obj["x"]), "y": int(obj["y"]), "height": int(obj.get("height", 3))},
                    distance=distance, score=score, scorePenalties=penalties,
                    predictedTile=predicted,
                    currentTargetDistance=current_target_distance,
                    predictedTargetDistance=predicted_target_distance,
                    targetDistanceDelta=predicted_target_distance - current_target_distance,
                    selectionReason=selected_reason,
                    loopRiskPenalty=loop_risk_penalty,
                    isBladeCandidate=is_blade_candidate_item(
                        (score, distance, obj, predicted, key, predicted_target_distance, penalties, current_target_distance)),
                    reverseEdge=reverse_edge, edgeRepeat=edge_repeat,
                    recentEdgeCount=recent_edge_count,
                    directedEdge=directed_edge_key(before["tile"], predicted),
                    undirectedEdge=undirected_edge_key(before["tile"], predicted),
                    activeDispenser=active_dispenser(), activeTarget=active_target(),
                    navigationTarget=candidate_target(target_override),
                    navigationTargetReason=target_reason,
                    topCandidates=candidate_briefs(candidates), player=before,
                    _preserveTiming=True)
    if moved:
        recent_edges.append((before_key, after_key))
        recent_tiles.append(after_key)
    if moved or xp_gained > 0:
        recent_object_keys.append(key)
    write_event(handle, "obstacle_step",
                objectId=int(obj["id"]), name=obj.get("name"), objectTile={
                    "x": int(obj["x"]), "y": int(obj["y"]), "height": int(obj.get("height", 3))
                }, distance=distance, score=score, scorePenalties=penalties,
                predictedTile=predicted,
                currentTargetDistance=current_target_distance,
                predictedTargetDistance=predicted_target_distance,
                targetDistanceDelta=predicted_target_distance - current_target_distance,
                selectionReason=selected_reason,
                topCandidates=candidate_briefs(candidates),
                success=bool(result.get("success")), message=result.get("message"),
                moved=moved, agilityXpGained=xp_gained, hpLost=hp_lost,
                escapeClick=escape_click,
                reverseEdge=reverse_edge, edgeRepeat=edge_repeat, recentEdgeCount=recent_edge_count,
                directedEdge=directed_edge_key(before["tile"], after["tile"]),
                undirectedEdge=undirected_edge_key(before["tile"], after["tile"]),
                activeDispenser=active_dispenser(), activeTarget=active_target(),
                navigationTarget=candidate_target(target_override), navigationTargetReason=target_reason,
                fromTile=before["tile"], toTile=after["tile"], player=after)
    return after_player, moved or xp_gained > 0


def run_course(args, handle, player):
    objects = load_course_objects()
    write_event(handle, "course_objects_loaded", count=len(objects), player=compact_player(player))
    if not in_arena(player):
        food_floor = max(3, int(args.food_target) // 3)
        if not args.no_restock and (count_any_inventory(player, FOOD_ITEM_IDS) <= food_floor or bridge.count_inventory_item(player, COINS) < int(args.restock_min_coins)):
            write_event(handle, "restock_before_arena",
                        food=count_any_inventory(player, FOOD_ITEM_IDS),
                        foodFloor=food_floor,
                        coins=bridge.count_inventory_item(player, COINS),
                        restockMinCoins=int(args.restock_min_coins),
                        player=compact_player(player))
            player = restock_if_needed(player, args, handle)
        player = enter_arena(args, handle)
        if not in_arena(player):
            write_event(handle, "run_stop", reason="not_in_arena", player=compact_player(player))
            return 2
    seen_counts = {}
    no_move_counts = {}
    recent_tiles = deque([tile_key(tile(player))], maxlen=8)
    recent_edges = deque(maxlen=RECENT_EDGE_MEMORY)
    recent_object_keys = deque(maxlen=12)
    stale_steps = 0
    last_tagged_window = None
    last_tagged_index = None
    for step in range(1, int(args.steps) + 1):
        if stop_requested(args.profile):
            write_event(handle, "run_stop", reason="stop_requested", player=compact_player(player))
            return 0
        if target_reached(player, args.target_agility_level):
            write_event(handle, "run_stop", reason="target_reached", player=compact_player(player))
            return 0
        if player.get("isDead") or player.get("isInCombat"):
            write_event(handle, "run_stop", reason="dead_or_combat", player=compact_player(player))
            return 4
        player = heal_if_needed(player, args)
        if args.no_restock and out_of_food_at_risk(player, args):
            write_event(handle, "run_stop", reason="no_food_low_hp",
                        food=count_any_inventory(player, FOOD_ITEM_IDS),
                        eatAt=int(args.eat_at), player=compact_player(player))
            return 10
        food_floor = max(3, int(args.food_target) // 3)
        if not args.no_restock and count_any_inventory(player, FOOD_ITEM_IDS) <= food_floor:
            write_event(handle, "restock_food_floor",
                        food=count_any_inventory(player, FOOD_ITEM_IDS),
                        foodFloor=food_floor,
                        foodTarget=int(args.food_target),
                        player=compact_player(player))
            if in_arena(player):
                player = exit_arena(args, handle)
                if in_arena(player):
                    write_event(handle, "run_stop", reason="exit_failed_for_food_restock",
                                player=compact_player(player))
                    return 6
            player = restock_if_needed(player, args, handle)
            player = enter_arena(args, handle)
            if not in_arena(player):
                write_event(handle, "run_stop", reason="reenter_failed_after_food_restock",
                            player=compact_player(player))
                return 7
            continue
        index = active_dispenser()
        window = dispenser_window()
        if tile_dist(tile(player), DISPENSERS[index]) <= int(args.tag_radius):
            if window == last_tagged_window and index == last_tagged_index:
                write_event(handle, "tag_skip", dispenser=index, target=DISPENSERS[index],
                            activeWindow=window, reason="already_tagged_active_window",
                            player=compact_player(player))
            else:
                before_tickets = bridge.count_inventory_item(player, TICKET)
                player, tagged = tag_dispenser(index, args, handle)
                after_tickets = bridge.count_inventory_item(player, TICKET)
                if tagged:
                    last_tagged_window = window
                    last_tagged_index = index
                if tagged or after_tickets > before_tickets:
                    stale_steps = 0
            if tile_dist(tile(player), DISPENSERS[index]) <= int(args.tag_radius):
                # A successful first tag only primes the streak. The next ticket can
                # come from a different active dispenser window, so keep training.
                pass
        navigation_target = None
        navigation_target_reason = None
        if window == last_tagged_window and index == last_tagged_index:
            next_index = next_dispenser(index)
            next_target = DISPENSERS[next_index]
            seconds_to_next = seconds_until_next_window()
            near_next_target = tile_dist(tile(player), next_target) <= int(args.tag_radius)
            soon_window_change = seconds_to_next <= max(float(args.tag_hold_wait_seconds),
                                                       float(args.obstacle_wait_seconds) + 1.5)
            if soon_window_change and not near_next_target:
                sleep_seconds = max(0.6, seconds_to_next + 0.4)
                write_event(handle, "hold_for_next_window",
                            reason="too_late_for_safe_obstacle_before_window",
                            activeDispenser=index, nextActiveDispenser=next_index,
                            sleepSeconds=round(sleep_seconds, 3),
                            sleepTicks=int(round(sleep_seconds / TICK_SECONDS)),
                            secondsToNextWindow=round(seconds_to_next, 3),
                            target=next_target, player=compact_player(player))
                deadline = time.monotonic() + sleep_seconds
                while time.monotonic() < deadline:
                    if stop_requested(args.profile):
                        write_event(handle, "run_stop", reason="stop_requested",
                                    player=compact_player(player))
                        return 0
                    time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
                player = observe_xs_with_tick(args.profile)
                continue
            if near_next_target:
                if seconds_to_next <= float(args.tag_return_window_seconds):
                    sleep_seconds = max(0.6, seconds_to_next + 0.4)
                    write_event(handle, "hold_for_next_dispenser",
                                reason="near_next_dispenser_before_window",
                                activeDispenser=index, nextActiveDispenser=next_index,
                                sleepSeconds=round(sleep_seconds, 3),
                                sleepTicks=int(round(sleep_seconds / TICK_SECONDS)),
                                secondsToNextWindow=round(seconds_to_next, 3),
                                target=next_target, player=compact_player(player))
                    deadline = time.monotonic() + sleep_seconds
                    while time.monotonic() < deadline:
                        if stop_requested(args.profile):
                            write_event(handle, "run_stop", reason="stop_requested",
                                        player=compact_player(player))
                            return 0
                        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
                    player = observe_xs_with_tick(args.profile)
                    continue
            if seconds_to_next > float(args.tag_return_window_seconds):
                navigation_target = DISPENSERS[next_dispenser(next_index)]
                navigation_target_reason = "course_loop_before_next_window"
            elif near_next_target:
                navigation_target = next_target
                navigation_target_reason = "return_for_next_dispenser"
            else:
                navigation_target = next_target
                navigation_target_reason = "next_dispenser_after_tag"
            write_event(handle, "course_navigation_decision",
                        activeDispenser=index, activeWindow=window,
                        nextActiveDispenser=next_index,
                        secondsToNextWindow=round(seconds_to_next, 3),
                        nearNextDispenser=near_next_target,
                        navigationTarget=navigation_target,
                        navigationTargetReason=navigation_target_reason,
                        player=compact_player(player))
        player, progressed = obstacle_step(player, objects, args, handle, seen_counts, no_move_counts,
                                           recent_tiles, recent_edges, recent_object_keys,
                                           target_override=navigation_target,
                                           target_reason=navigation_target_reason)
        if progressed:
            stale_steps = 0
        else:
            stale_steps += 1
            if stale_steps >= int(args.stall_limit):
                write_event(handle, "run_stop", reason="course_stalled",
                            activeDispenser=active_dispenser(), activeTarget=active_target(),
                            player=compact_player(player))
                return 8
        if int(args.cash_out_after) > 0 and bridge.count_inventory_item(player, TICKET) >= int(args.cash_out_after):
            player = exit_arena(args, handle)
            if in_arena(player):
                write_event(handle, "run_stop", reason="exit_failed", player=compact_player(player))
                return 6
            player = exchange_tickets(args, handle)
            if target_reached(player, args.target_agility_level):
                write_event(handle, "run_stop", reason="target_reached", player=compact_player(player))
                return 0
            player = restock_if_needed(player, args, handle)
            player = enter_arena(args, handle)
            if not in_arena(player):
                write_event(handle, "run_stop", reason="reenter_failed", player=compact_player(player))
                return 7
    write_event(handle, "run_stop", reason="steps_complete", player=compact_player(player))
    return 0


def exit_arena(args, handle):
    player = observe_xs_with_tick(args.profile)
    if not in_arena(player):
        return player
    result = bridge.call_tool("interact_object_XS", {
        "objectId": 3618,
        "x": EXIT_LADDER["x"],
        "y": EXIT_LADDER["y"],
        "height": EXIT_LADDER["height"],
        "option": "first",
        "requireReachable": False,
        "directIfUnreachable": True,
    }, profile=args.profile)
    player = player_from_result(result)
    write_event(handle, "exit_arena", success=bool(result.get("success")),
                message=result.get("message"), player=compact_player(player))
    time.sleep(1.5)
    return observe_xs_with_tick(args.profile)


def exchange_tickets(args, handle):
    player = observe_xs_with_tick(args.profile)
    before_xp = compact_player(player)["agilityXp"]
    before_tickets = bridge.count_inventory_item(player, TICKET)
    result = interact_npc_with_walk(PIRATE_JACKIE, args, max_distance=8)
    player = player_from_result(result)
    after = compact_player(player)
    write_event(handle, "exchange_tickets", success=bool(result.get("success")),
                message=result.get("message"), ticketsSpent=before_tickets - after["tickets"],
                agilityXpGained=after["agilityXp"] - before_xp, player=after)
    return player


def route_to_target(target, args, handle, reason):
    env = os.environ.copy()
    env["RS_PROFILE"] = args.profile
    env["PROFILE"] = args.profile
    env["RS_TRACE_PROFILE"] = args.profile
    last_error = None
    for route_attempt in range(1, 5):
        player = observe_xs_with_tick(args.profile)
        compact = compact_player(player)
        write_event(handle, "route_to_start", reason=reason, target=str(target),
                    attempt=route_attempt, player=compact)
        command = [
            sys.executable,
            str(ML2_DEFINE),
            "define",
            "--from",
            tile_key(compact["tile"]),
            "--to",
            str(target),
            "--combat-level",
            str(int(player.get("combatLevel", player.get("cb", 3)) or 3)),
            "--food",
            str(count_any_inventory(player, FOOD_ITEM_IDS)),
            "--coins",
            str(bridge.count_inventory_item(player, COINS)),
            "--run-energy",
            str(int(compact.get("runEnergy", 0) or 0)),
            "--planner",
            "fast",
            "--runner-max-batches",
            str(int(args.route_max_batches)),
            "--direct-max-expansions",
            "2000000",
            "--collision-max-expansions",
            "800000",
        ]
        if compact.get("runEnabled"):
            command.append("--run-enabled")
        write_event(handle, "ml2_route_define_start", reason=reason, target=str(target),
                    attempt=route_attempt, command=command)
        try:
            defined = subprocess.run(command, cwd=str(REPO_ROOT), text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env, timeout=45)
        except subprocess.TimeoutExpired as exc:
            stdout_tail = (exc.stdout or "")
            stderr_tail = (exc.stderr or "")
            if isinstance(stdout_tail, bytes):
                stdout_tail = stdout_tail.decode("utf-8", errors="replace")
            if isinstance(stderr_tail, bytes):
                stderr_tail = stderr_tail.decode("utf-8", errors="replace")
            last_error = "ML2 route definition to {} timed out".format(target)
            write_event(handle, "ml2_route_define_timeout", reason=reason, target=str(target),
                        attempt=route_attempt, timeoutSeconds=45,
                        stdoutTail=[line for line in stdout_tail.splitlines() if line.strip()][-8:],
                        stderrTail=[line for line in stderr_tail.splitlines() if line.strip()][-8:])
            continue
        stdout_lines = [line for line in (defined.stdout or "").splitlines() if line.strip()]
        stderr_lines = [line for line in (defined.stderr or "").splitlines() if line.strip()]
        write_event(handle, "ml2_route_define_finish", reason=reason, target=str(target),
                    attempt=route_attempt, returncode=int(defined.returncode),
                    stdoutTail=stdout_lines[-8:], stderrTail=stderr_lines[-8:])
        if defined.returncode != 0:
            last_error = "ML2 route definition to {} failed: {}".format(
                target, "\n".join(stderr_lines[-4:] or stdout_lines[-4:]))
            continue
        definition = json.loads(defined.stdout)
        if definition.get("status") != "ok" or not definition.get("path"):
            last_error = "ML2 route to {} was not executable: status={} decision={}".format(
                target, definition.get("status"), definition.get("decision"))
            write_event(handle, "ml2_route_retry", reason=reason, target=str(target),
                        attempt=route_attempt, error=last_error, player=compact_player(player))
            continue
        route_path = REPO_ROOT / str(definition["path"])
        route_definition = json.loads(route_path.read_text(encoding="utf-8"))
        exec_command = (route_definition.get("execution") or {}).get("command")
        if not exec_command:
            last_error = "ML2 route definition had no execution command: {}".format(route_path)
            continue
        write_event(handle, "ml2_route_execute_start", reason=reason, target=str(target),
                    attempt=route_attempt, routePath=str(route_path),
                    routeId=definition.get("id"), command=exec_command)
        executed = subprocess.run(exec_command, cwd=str(REPO_ROOT), text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env)
        stdout_lines = [line for line in (executed.stdout or "").splitlines() if line.strip()]
        stderr_lines = [line for line in (executed.stderr or "").splitlines() if line.strip()]
        player = observe_xs_with_tick(args.profile)
        write_event(handle, "ml2_route_execute_finish", reason=reason, target=str(target),
                    attempt=route_attempt, routePath=str(route_path),
                    routeId=definition.get("id"), returncode=int(executed.returncode),
                    stdoutTail=stdout_lines[-8:], stderrTail=stderr_lines[-8:],
                    player=compact_player(player))
        if executed.returncode == 0 or route_target_satisfied(target, player):
            write_event(handle, "route_to_finish", reason=reason, target=str(target),
                        attempt=route_attempt, acceptedNearTarget=executed.returncode != 0,
                        player=compact_player(player))
            return player
        last_error = "ML2 route execution to {} failed: {}".format(
            target, "\n".join(stderr_lines[-4:] or stdout_lines[-4:]))
        write_event(handle, "ml2_route_retry", reason=reason, target=str(target),
                    attempt=route_attempt, error=last_error, player=compact_player(player))
    raise RuntimeError(last_error or "ML2 route to {} failed".format(target))


def route_target_satisfied(target, player):
    target_text = str(target)
    player_tile = tile(player)
    if target_text == BRIMHAVEN_ENTRANCE:
        return tile_dist(player_tile, {"x": 2809, "y": 3193, "height": 0}) <= 8
    if target_text == DEFAULT_RESTOCK_BANK:
        return bool(player.get("inBankArea", False))
    try:
        parts = [int(part) for part in target_text.split(",")]
    except (TypeError, ValueError):
        return False
    if len(parts) == 3:
        return tile_dist(player_tile, {"x": parts[0], "y": parts[1], "height": parts[2]}) <= 2
    return False


def close_interfaces(args, handle, reason):
    try:
        result = bridge.call_tool("close_interfaces", {}, profile=args.profile)
    except RuntimeError as exc:
        write_event(handle, "close_interfaces", reason=reason, success=False, message=str(exc))
        return observe_xs_with_tick(args.profile)
    player = player_from_result(result)
    write_event(handle, "close_interfaces", reason=reason, success=bool(result.get("success")),
                message=result.get("message"), player=compact_player(player))
    return player


def sail_between_brimhaven_and_ardougne(args, handle, direction):
    if direction == "to_ardougne":
        expected = ARDOUGNE_DOCK
    elif direction == "to_brimhaven":
        expected = BRIMHAVEN_DOCK
    else:
        raise ValueError("unsupported sailing direction: {}".format(direction))
    player = observe_xs_with_tick(args.profile)
    before = compact_player(player)
    before_coins = bridge.count_inventory_item(player, COINS)
    if before_coins < 30:
        write_event(handle, "ship_transition_stop", direction=direction,
                    reason="not_enough_coins", coins=before_coins, player=before)
        raise RuntimeError("Need 30 coins for Captain Barnaby ship transition")
    result = interact_npc_with_walk(CAPTAIN_BARNABY, args, max_distance=8)
    after_click = player_from_result(result)
    write_event(handle, "ship_transition_click", direction=direction,
                success=bool(result.get("success")), message=result.get("message"),
                fromTile=before["tile"], expectedTile=expected,
                coinsBefore=before_coins, player=compact_player(after_click))
    bridge.call_tool("wait_ticks_XS", {"ticks": 5}, profile=args.profile)
    player = observe_xs_with_tick(args.profile)
    after = compact_player(player)
    arrived = tile_dist(after["tile"], expected) <= 5
    write_event(handle, "ship_transition_finish", direction=direction,
                success=arrived, expectedTile=expected,
                coinsBefore=before_coins, coinsAfter=bridge.count_inventory_item(player, COINS),
                fromTile=before["tile"], toTile=after["tile"], player=after)
    if not arrived:
        raise RuntimeError("Captain Barnaby ship transition {} did not arrive at expected dock".format(direction))
    return player


def route_to_catherby_bank_via_ship(player, args, handle):
    if str(args.restock_bank_target) != DEFAULT_RESTOCK_BANK:
        return route_to_target(args.restock_bank_target, args, handle, "brimhaven_restock_bank")
    write_event(handle, "restock_ship_route_start", direction="to_catherby_bank",
                bankTarget=str(args.restock_bank_target), player=compact_player(player))
    player = close_interfaces(args, handle, "before_brimhaven_ship_restock")
    if tile_dist(tile(player), ARDOUGNE_DOCK) <= 8:
        write_event(handle, "restock_ship_route_side_detected", direction="to_catherby_bank",
                    side="ardougne", player=compact_player(player))
    else:
        if tile_dist(tile(player), BRIMHAVEN_DOCK) > 8:
            player = route_to_target(BRIMHAVEN_DOCK_TARGET, args, handle, "brimhaven_restock_to_ship")
        player = sail_between_brimhaven_and_ardougne(args, handle, "to_ardougne")
    if tile_dist(tile(player), ARDOUGNE_DOCK) > 8:
        write_event(handle, "restock_ship_route_stop", direction="to_catherby_bank",
                    reason="not_at_ardougne_dock", player=compact_player(player))
        raise RuntimeError("Brimhaven restock route could not reach Ardougne dock")
    player = route_to_target(args.restock_bank_target, args, handle, "brimhaven_restock_ardougne_to_bank")
    write_event(handle, "restock_ship_route_finish", direction="to_catherby_bank",
                bankTarget=str(args.restock_bank_target), player=compact_player(player))
    return player


def route_from_catherby_bank_to_brimhaven_via_ship(player, args, handle):
    if str(args.return_target) != BRIMHAVEN_ENTRANCE:
        return route_to_target(args.return_target, args, handle, "brimhaven_restock_return")
    write_event(handle, "restock_ship_route_start", direction="to_brimhaven_entrance",
                returnTarget=str(args.return_target), player=compact_player(player))
    player = close_interfaces(args, handle, "before_brimhaven_ship_return")
    if tile_dist(tile(player), BRIMHAVEN_DOCK) <= 8:
        write_event(handle, "restock_ship_route_side_detected", direction="to_brimhaven_entrance",
                    side="brimhaven", player=compact_player(player))
    else:
        if tile_dist(tile(player), ARDOUGNE_DOCK) > 8:
            player = route_to_target(ARDOUGNE_DOCK_TARGET, args, handle, "brimhaven_restock_bank_to_ardougne_ship")
        player = sail_between_brimhaven_and_ardougne(args, handle, "to_brimhaven")
    if tile_dist(tile(player), BRIMHAVEN_DOCK) > 8:
        write_event(handle, "restock_ship_route_stop", direction="to_brimhaven_entrance",
                    reason="not_at_brimhaven_dock", player=compact_player(player))
        raise RuntimeError("Brimhaven restock route could not reach Brimhaven dock")
    player = route_to_target(args.return_target, args, handle, "brimhaven_restock_ship_to_entrance")
    write_event(handle, "restock_ship_route_finish", direction="to_brimhaven_entrance",
                returnTarget=str(args.return_target), player=compact_player(player))
    return player


def count_any_inventory(player, item_ids):
    return sum(bridge.count_inventory_item(player, item_id) for item_id in item_ids)


def open_bank(args, handle, reason):
    result = bridge.call_tool("deposit_inventory_items_XS", {"name": "__codex_open_bank_only__"},
                              profile=args.profile)
    player = player_from_result(result)
    write_event(handle, "open_bank", reason=reason, success=bool(result.get("success")),
                message=result.get("message"), player=compact_player(player))
    return player


def best_banked_food(player):
    for item_id in FOOD_ITEM_IDS:
        if bridge.count_bank_item(player, item_id) > 0:
            return item_id
    return None


def restock_if_needed(player, args, handle):
    if args.no_restock:
        return player
    coins = bridge.count_inventory_item(player, COINS)
    food = count_any_inventory(player, FOOD_ITEM_IDS)
    if coins >= int(args.restock_min_coins) and food >= int(args.food_target):
        return player
    if in_arena(player):
        player = exit_arena(args, handle)
    write_event(handle, "restock_needed", coins=coins, food=food,
                restockMinCoins=int(args.restock_min_coins),
                coinFloat=int(args.coin_float), foodTarget=int(args.food_target),
                bankTarget=str(args.restock_bank_target), player=compact_player(player))
    player = route_to_catherby_bank_via_ship(player, args, handle)
    if not bool(player.get("inBankArea", False)):
        write_event(handle, "restock_stop", reason="not_in_bank_area", player=compact_player(player))
        raise RuntimeError("Brimhaven restock route did not reach a bank area")
    player = open_bank(args, handle, "brimhaven_restock")
    if bridge.count_inventory_item(player, COINS) < int(args.coin_float):
        amount = int(args.coin_float) - bridge.count_inventory_item(player, COINS)
        result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": COINS, "amount": amount},
                                  profile=args.profile)
        player = player_from_result(result)
        write_event(handle, "restock_withdraw_coins", requested=amount,
                    success=bool(result.get("success")), message=result.get("message"),
                    player=compact_player(player))
    food = count_any_inventory(player, FOOD_ITEM_IDS)
    if food < int(args.food_target):
        food_id = best_banked_food(player)
        if food_id is None:
            write_event(handle, "restock_no_banked_food", player=compact_player(player))
        else:
            amount = int(args.food_target) - food
            result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": int(food_id), "amount": amount},
                                      profile=args.profile)
            player = player_from_result(result)
            write_event(handle, "restock_withdraw_food", itemId=int(food_id), requested=amount,
                        success=bool(result.get("success")), message=result.get("message"),
                        player=compact_player(player))
    player = route_from_catherby_bank_to_brimhaven_via_ship(player, args, handle)
    return player


def readiness(args):
    player = observe_xs_with_tick(args.profile)
    return {
        "ok": True,
        "runner": RUNNER_NAME,
        "profile": args.profile,
        "currentState": compact_player(player),
        "readyToEnter": tile_dist(tile(player), {"x": 2809, "y": 3193, "height": 0}) <= 12,
        "inArena": in_arena(player),
        "activeDispenser": active_dispenser(),
        "activeTarget": DISPENSERS[active_dispenser()],
        "runtime": server_runtime_status(),
    }


def run(args):
    clear_stop(args.profile)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = utc_stamp() + "-brimhaven"
    log_path = RUNS_DIR / "{}.jsonl".format(run_id)
    with log_path.open("a", encoding="utf-8") as handle:
        runtime = server_runtime_status()
        player = observe_xs_with_tick(args.profile)
        write_event(handle, "run_start", runId=run_id, player=compact_player(player),
                    settings=vars(args), runtime=runtime)
        if runtime.get("staleForBrimhavenCourse") and not args.allow_stale_runtime:
            write_event(handle, "run_stop", reason="stale_runtime",
                        message="Server runtime jar is older than the built Brimhaven course jar.",
                        runtime=runtime, player=compact_player(player))
            return 9
        if int(args.cash_out_after) > 0 and bridge.count_inventory_item(player, TICKET) >= int(args.cash_out_after):
            if in_arena(player):
                player = exit_arena(args, handle)
                if in_arena(player):
                    write_event(handle, "run_stop", reason="exit_failed", player=compact_player(player))
                    return 6
            player = exchange_tickets(args, handle)
            player = restock_if_needed(player, args, handle)
        if not args.ticket_only_mode:
            if int(args.steps) <= 0:
                write_event(handle, "run_stop", reason="steps_complete", player=compact_player(player))
                return 0
            return run_course(args, handle, player)
        if int(args.tags) <= 0:
            write_event(handle, "run_stop", reason="tags_complete", player=compact_player(player))
            return 0
        player = enter_arena(args, handle)
        if not in_arena(player):
            write_event(handle, "run_stop", reason="not_in_arena", player=compact_player(player))
            return 2
        for tag in range(1, int(args.tags) + 1):
            if stop_requested(args.profile):
                write_event(handle, "run_stop", reason="stop_requested", player=compact_player(player))
                return 0
            if target_reached(player, args.target_agility_level):
                write_event(handle, "run_stop", reason="target_reached", player=compact_player(player))
                return 0
            index = active_dispenser()
            player, ok = tag_dispenser(index, args, handle)
            if player.get("isDead") or player.get("isInCombat"):
                write_event(handle, "run_stop", reason="dead_or_combat", player=compact_player(player))
                return 4
            if not ok and args.stop_on_failed_tag:
                write_event(handle, "run_stop", reason="tag_failed", player=compact_player(player))
                return 5
            if int(args.cash_out_after) > 0 and bridge.count_inventory_item(player, TICKET) >= int(args.cash_out_after):
                player = exit_arena(args, handle)
                if in_arena(player):
                    write_event(handle, "run_stop", reason="exit_failed", player=compact_player(player))
                    return 6
                player = exchange_tickets(args, handle)
                if target_reached(player, args.target_agility_level):
                    write_event(handle, "run_stop", reason="target_reached", player=compact_player(player))
                    return 0
                player = restock_if_needed(player, args, handle)
                player = enter_arena(args, handle)
                if not in_arena(player):
                    write_event(handle, "run_stop", reason="reenter_failed", player=compact_player(player))
                    return 7
            sleep_seconds = max(1, int(args.poll_seconds))
            write_event(handle, "tag_wait", tag=tag, sleepSeconds=sleep_seconds,
                        nextActiveDispenser=active_dispenser(time.time() + sleep_seconds))
            time.sleep(sleep_seconds)
        write_event(handle, "run_stop", reason="tags_complete", player=compact_player(player))
    return 0


def launch_detached(args):
    paths = runner_paths(args.profile)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    try:
        paths["stop"].unlink()
    except FileNotFoundError:
        pass
    existing_pid = read_pid(paths["pid"])
    if process_exists(existing_pid):
        print_json({"ok": False, "runner": RUNNER_NAME, "error": "already_running", "pid": existing_pid})
        return 2
    runtime = server_runtime_status()
    if runtime.get("staleForBrimhavenCourse") and not args.allow_stale_runtime:
        print_json({
            "ok": False,
            "runner": RUNNER_NAME,
            "error": "stale_runtime",
            "message": "Server runtime jar is older than the built Brimhaven course jar.",
            "runtime": runtime,
        })
        return 9
    log_path = paths["dir"] / "{}-{}.log".format(RUNNER_NAME, utc_stamp())
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--profile", args.profile,
        "--target-agility-level", str(args.target_agility_level),
        "--tags", str(args.tags),
        "--steps", str(args.steps),
        "--min-run-energy", str(args.min_run_energy),
        "--eat-at", str(args.eat_at),
        "--obstacle-radius", str(args.obstacle_radius),
        "--approach-radius", str(args.approach_radius),
        "--approach-max-ticks", str(args.approach_max_ticks),
        "--approach-preference-margin", str(args.approach_preference_margin),
        "--loop-escape-click-radius", str(args.loop_escape_click_radius),
        "--obstacle-wait-seconds", str(args.obstacle_wait_seconds),
        "--tag-return-window-seconds", str(args.tag_return_window_seconds),
        "--tag-hold-wait-seconds", str(args.tag_hold_wait_seconds),
        "--stall-limit", str(args.stall_limit),
        "--cash-out-after", str(args.cash_out_after),
        "--restock-min-coins", str(args.restock_min_coins),
        "--coin-float", str(args.coin_float),
        "--food-target", str(args.food_target),
        "--restock-bank-target", str(args.restock_bank_target),
        "--return-target", str(args.return_target),
        "--route-max-batches", str(args.route_max_batches),
    ]
    if args.no_restock:
        command.append("--no-restock")
    if args.stop_on_failed_tag:
        command.append("--stop-on-failed-tag")
    if args.ticket_only_mode:
        command.append("--ticket-only-mode")
    if args.allow_stale_runtime:
        command.append("--allow-stale-runtime")
    env = os.environ.copy()
    env.update({"PROFILE": args.profile, "RS_PROFILE": args.profile, "RS_TRACE_PROFILE": args.profile})
    with log_path.open("wb", buffering=0) as handle:
        proc = subprocess.Popen(command, cwd=str(REPO_ROOT), stdin=subprocess.DEVNULL,
                                stdout=handle, stderr=subprocess.STDOUT,
                                start_new_session=True, env=env)
    paths["pid"].write_text(str(proc.pid), encoding="utf-8")
    paths["logpath"].write_text(str(log_path), encoding="utf-8")
    print_json({"ok": True, "runner": RUNNER_NAME, "pid": proc.pid,
                "pidFile": str(paths["pid"]), "logPath": str(log_path)})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run Brimhaven Agility Arena ticket training.",
        allow_abbrev=False)
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--target-agility-level", type=int, default=99)
    parser.add_argument("--tags", type=int, default=20000)
    parser.add_argument("--steps", type=int, default=20000,
                        help="Maximum physical obstacle attempts in normal course mode.")
    parser.add_argument("--min-run-energy", type=int, default=8)
    parser.add_argument("--eat-at", type=int, default=8)
    parser.add_argument("--tag-radius", type=int, default=4)
    parser.add_argument("--obstacle-radius", type=int, default=5)
    parser.add_argument("--approach-radius", type=int, default=10,
                        help="When no good nearby obstacle is available, walk within this range toward a better one.")
    parser.add_argument("--approach-max-ticks", type=int, default=24)
    parser.add_argument("--approach-preference-margin", type=int, default=120,
                        help="Prefer walking to a better obstacle when it beats the nearby click score by this much.")
    parser.add_argument("--loop-escape-click-radius", type=int, default=12,
                        help="After a failed approach, try a better progress obstacle within this radius instead of re-clicking a loop-risk fallback.")
    parser.add_argument("--obstacle-wait-seconds", type=float, default=2.4)
    parser.add_argument("--tag-return-window-seconds", type=float, default=35.0,
                        help="When already at the next dispenser within this many seconds of activation, hold there instead of continuing obstacle loops.")
    parser.add_argument("--tag-hold-wait-seconds", type=float, default=8.0,
                        help="When standing at the next dispenser this close to activation, wait and tag instead of clicking nearby obstacles.")
    parser.add_argument("--stall-limit", type=int, default=5)
    parser.add_argument("--poll-seconds", type=int, default=61)
    parser.add_argument("--cash-out-after", type=int, default=0,
                        help="Leave the arena and exchange tickets once this many are carried; 0 disables cash-out.")
    parser.add_argument("--restock-min-coins", type=int, default=1000,
                        help="After a ticket exchange, bank-restock when carried coins are below this amount.")
    parser.add_argument("--coin-float", type=int, default=25000,
                        help="Coin amount to carry after a bank restock.")
    parser.add_argument("--food-target", type=int, default=15,
                        help="Food count to carry after a bank restock.")
    parser.add_argument("--restock-bank-target", default=DEFAULT_RESTOCK_BANK,
                        help="ML2 bank target used for Brimhaven restocks.")
    parser.add_argument("--return-target", default=BRIMHAVEN_ENTRANCE,
                        help="ML2 target used to return after a Brimhaven restock.")
    parser.add_argument("--route-max-batches", type=int, default=80)
    parser.add_argument("--no-restock", action="store_true",
                        help="Disable bank restocking between cash-out cycles.")
    parser.add_argument("--walk-to-dispenser", action="store_true",
                        help="Try normal walking to the active dispenser before clicking it.")
    parser.add_argument("--ticket-only-mode", action="store_true",
                        help="Legacy mode that waits for active dispensers instead of physically traversing obstacles.")
    parser.add_argument("--allow-stale-runtime", action="store_true",
                        help="Run even when status says the live server jar predates the built Brimhaven course jar.")
    parser.add_argument("--stop-on-failed-tag", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--loop-report", "--report", dest="loop_report", action="store_true",
                        help="Summarize recent obstacle timing, repeated edges, and blade-loop evidence.")
    parser.add_argument("--report-text", action="store_true",
                        help="Print loop-report as concise human-readable text.")
    parser.add_argument("--tail-lines", type=int, default=8)
    parser.add_argument("--readiness", action="store_true")
    parser.add_argument("--launch-detached", action="store_true")
    parser.add_argument("--request-stop", action="store_true")
    parser.add_argument("--stop", dest="request_stop", action="store_true",
                        help="Alias for --request-stop.")
    parser.add_argument("--clear-stop", action="store_true")
    args = parser.parse_args(argv)
    if args.status:
        print_json(status_payload(args.profile, tail=args.tail_lines))
        return 0
    if args.loop_report:
        report = loop_report(tail=args.tail_lines)
        if args.report_text:
            print(loop_report_text(report))
        else:
            print_json(report)
        return 0
    if args.readiness:
        print_json(readiness(args))
        return 0
    if args.request_stop:
        runner_paths(args.profile)["dir"].mkdir(parents=True, exist_ok=True)
        runner_paths(args.profile)["stop"].write_text(utc_stamp() + "\n", encoding="utf-8")
        print_json({"ok": True, "runner": RUNNER_NAME, "stopRequested": True})
        return 0
    if args.clear_stop:
        clear_stop(args.profile)
        print_json({"ok": True, "runner": RUNNER_NAME, "stopRequested": False})
        return 0
    if args.launch_detached:
        return launch_detached(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
