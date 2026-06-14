#!/usr/bin/env python3
"""Compact timing report for adaptive agility-runner JSONL logs."""

import argparse
import datetime as dt
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from profile_utils import resolve_profile


SCRIPT_DIR = Path(__file__).resolve().parent
NAV_ROOT = SCRIPT_DIR.parent
RUNS_DIR = NAV_ROOT / "data" / "agility" / "runs"


def parse_ts(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def event_seconds(event):
    if event.get("runElapsedMs") is not None:
        return float(event["runElapsedMs"]) / 1000.0
    return parse_ts(event.get("ts") or event.get("timestamp"))


def read_events(path):
    events = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def first_event(events, name):
    for event in events:
        if event.get("event") == name:
            return event
    return None


def last_event(events, name):
    for event in reversed(events):
        if event.get("event") == name:
            return event
    return None


def run_profile(events):
    start = first_event(events, "run_start") or {}
    settings = start.get("settings") or {}
    if settings.get("profile"):
        return settings.get("profile")
    state = start.get("initialState") or {}
    return state.get("name") or ""


def run_course(events):
    start = first_event(events, "run_start") or {}
    if start.get("courseId"):
        return start.get("courseId")
    for event in events:
        if event.get("courseId"):
            return event.get("courseId")
    return ""


def candidate_matches(path, course, profile):
    try:
        events = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(events) >= 12 or events[-1].get("event") == "run_start":
                    break
    except OSError:
        return False
    if not events:
        return False
    if course and run_course(events) != course:
        return False
    found_profile = run_profile(events)
    if profile and found_profile and found_profile.lower() != profile.lower():
        return False
    return True


def latest_log(course, profile):
    candidates = sorted(
        RUNS_DIR.glob("*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        if candidate_matches(path, course, profile):
            return path
    return None


def values(events, field):
    return [float(event[field]) for event in events if event.get(field) is not None]


def stat(vals):
    vals = [float(value) for value in vals if value is not None]
    if not vals:
        return None
    return {
        "n": len(vals),
        "min": round(min(vals), 3),
        "avg": round(statistics.fmean(vals), 3),
        "max": round(max(vals), 3),
    }


def percent(numer, denom):
    if denom <= 0:
        return None
    return round(float(numer) * 100.0 / float(denom), 2)


def rate_per_hour(amount, seconds):
    if seconds is None or seconds <= 0:
        return None
    return round(float(amount) * 3600.0 / float(seconds), 1)


def tile_string(tile):
    if not isinstance(tile, dict):
        return ""
    return "{},{},{}".format(tile.get("x"), tile.get("y"), tile.get("height", 0))


def compact_state(state):
    if not isinstance(state, dict):
        return {}
    tile = state.get("tile") or {}
    return {
        "tile": tile_string(tile),
        "hp": state.get("hitpoints", state.get("hp")),
        "maxHp": state.get("maxHitpoints", state.get("maxHp")),
        "runEnergy": state.get("runEnergy"),
        "agilityLevel": state.get("agilityLevel"),
        "agilityXp": state.get("agilityXp"),
        "isDead": state.get("isDead"),
        "isInCombat": state.get("isInCombat"),
    }


def summarize_steps(step_events):
    grouped = defaultdict(list)
    for event in step_events:
        grouped[event.get("stepId") or "unknown"].append(event)
    summaries = []
    for step_id, group in grouped.items():
        skipped = [event for event in group if event.get("skipped")]
        successes = [event for event in group if event.get("success") and not event.get("skipped")]
        failures = [event for event in group if not event.get("success")]
        reasons = Counter(str(event.get("reason") or "unknown") for event in failures)
        skip_reasons = Counter(str(event.get("reason") or "unknown") for event in skipped)
        names = [event.get("stepName") for event in group if event.get("stepName")]
        summaries.append({
            "stepId": step_id,
            "stepName": names[0] if names else "",
            "attempts": len(group),
            "successes": len(successes),
            "skipped": len(skipped),
            "failures": len(failures),
            "successPct": percent(len(successes), len(group)),
            "ticks": stat(values(successes, "ticks")),
            "durationSeconds": stat(values(successes, "durationSeconds")),
            "walkSeconds": stat(values(successes, "walkDurationSeconds")),
            "interactSeconds": stat(values(successes, "interactDurationSeconds")),
            "postPollCount": stat(values(successes, "postPollCount")),
            "xp": stat(values(successes, "agilityXpGained")),
            "failureReasons": dict(reasons),
            "skipReasons": dict(skip_reasons),
        })
    summaries.sort(key=lambda item: item["stepId"])
    return summaries


def report_for(path):
    events = read_events(path)
    if not events:
        return {"ok": False, "error": "empty_log", "logPath": str(path)}

    run_start = first_event(events, "run_start") or {}
    run_end = last_event(events, "run_end") or {}
    lap_events = [event for event in events if event.get("event") == "lap_end"]
    step_events = [event for event in events if event.get("event") == "step_end"]
    successful_laps = [event for event in lap_events if event.get("success")]
    failed_laps = [event for event in lap_events if not event.get("success")]
    completed_lap_numbers = set(event.get("lap") for event in lap_events)
    completed_lap_step_events = [
        event for event in step_events if event.get("lap") in completed_lap_numbers
    ]
    live_step_events = [
        event for event in step_events if event.get("lap") not in completed_lap_numbers
    ]
    expected_lap_xp_values = [
        int(event["expectedLapXp"]) for event in lap_events if event.get("expectedLapXp") is not None
    ]
    expected_lap_xp = expected_lap_xp_values[-1] if expected_lap_xp_values else None
    xp_mismatch_laps = [
        event for event in successful_laps
        if event.get("expectedLapXp") is not None
        and int(event.get("agilityXpGained") or 0) != int(event.get("expectedLapXp") or 0)
    ]
    skipped_steps = [event for event in completed_lap_step_events if event.get("skipped")]
    successful_steps = [
        event for event in completed_lap_step_events
        if event.get("success") and not event.get("skipped")
    ]
    failed_steps = [event for event in completed_lap_step_events if not event.get("success")]

    start_s = event_seconds(events[0])
    end_event = lap_events[-1] if lap_events else events[-1]
    end_s = event_seconds(end_event)
    wall_seconds = end_s - start_s if start_s is not None and end_s is not None else None
    active_lap_seconds = sum(float(event.get("durationSeconds") or 0.0) for event in successful_laps)
    total_xp = sum(int(event.get("agilityXpGained") or 0) for event in lap_events)
    successful_xp = sum(int(event.get("agilityXpGained") or 0) for event in successful_laps)
    failure_reasons = Counter(str(event.get("reason") or "unknown") for event in failed_steps)
    slowest_steps = sorted(
        successful_steps,
        key=lambda event: float(event.get("durationSeconds") or 0.0),
        reverse=True,
    )[:8]

    final_state = run_end.get("finalState")
    if not final_state:
        for event in reversed(events):
            final_state = event.get("endState") or event.get("player")
            if final_state:
                break

    return {
        "ok": True,
        "logPath": str(path),
        "runId": run_start.get("runId") or run_end.get("runId") or Path(path).stem,
        "courseId": run_course(events),
        "courseName": run_start.get("courseName"),
        "profile": run_profile(events),
        "success": run_end.get("success"),
        "targetReached": run_end.get("targetReached"),
        "targetAgilityLevel": run_end.get("targetAgilityLevel"),
        "lapsRequested": run_end.get("lapsRequested"),
        "lapsCompleted": len(successful_laps),
        "lapsFailed": len(failed_laps),
        "lapSuccessPct": percent(len(successful_laps), len(lap_events)),
        "expectedLapXp": expected_lap_xp,
        "xpMismatchLaps": len(xp_mismatch_laps),
        "stepsAttempted": len(completed_lap_step_events),
        "stepsSucceeded": len(successful_steps),
        "stepsSkipped": len(skipped_steps),
        "stepsFailed": len(failed_steps),
        "completedLapStepsAttempted": len(completed_lap_step_events),
        "liveStepsInProgress": len(live_step_events),
        "liveLapInProgress": max((int(event.get("lap") or 0) for event in live_step_events), default=None),
        "stepSuccessPct": percent(len(successful_steps) + len(skipped_steps), len(completed_lap_step_events)),
        "wallSeconds": round(wall_seconds, 3) if wall_seconds is not None else None,
        "activeLapSeconds": round(active_lap_seconds, 3),
        "xpGained": total_xp,
        "successfulLapXp": successful_xp,
        "xpPerHourWall": rate_per_hour(total_xp, wall_seconds),
        "xpPerHourActiveLaps": rate_per_hour(successful_xp, active_lap_seconds),
        "successfulLapsPerHourWall": rate_per_hour(len(successful_laps), wall_seconds),
        "lapDurationSeconds": stat(values(successful_laps, "durationSeconds")),
        "lapTicks": stat(values(successful_laps, "ticks")),
        "lapXp": stat(values(successful_laps, "agilityXpGained")),
        "stepSummary": summarize_steps(completed_lap_step_events),
        "failureReasons": dict(failure_reasons),
        "slowestSteps": [
            {
                "lap": event.get("lap"),
                "step": event.get("step"),
                "stepId": event.get("stepId"),
                "stepName": event.get("stepName"),
                "durationSeconds": event.get("durationSeconds"),
                "ticks": event.get("ticks"),
                "walkSeconds": event.get("walkDurationSeconds"),
                "interactSeconds": event.get("interactDurationSeconds"),
                "postPollCount": event.get("postPollCount"),
            }
            for event in slowest_steps
        ],
        "eventCounts": dict(Counter(str(event.get("event") or "unknown") for event in events)),
        "finalState": compact_state(final_state),
    }


def text_report(summary):
    if not summary.get("ok"):
        return "Agility report unavailable: {}".format(summary.get("error"))
    lines = []
    lines.append("Agility Runner Report")
    lines.append("log: {}".format(summary["logPath"]))
    lines.append("course: {} | profile: {} | run: {}".format(
        summary.get("courseId") or "-", summary.get("profile") or "-", summary.get("runId") or "-"))
    lines.append("laps: {} complete, {} failed | steps: {} ok / {} failed".format(
        summary.get("lapsCompleted"), summary.get("lapsFailed"),
        summary.get("stepsSucceeded"), summary.get("stepsFailed")))
    if summary.get("stepsSkipped"):
        lines.append("skipped steps: {}".format(summary.get("stepsSkipped")))
    if summary.get("liveStepsInProgress"):
        lines.append("live lap {} in progress: {} steps observed".format(
            summary.get("liveLapInProgress"), summary.get("liveStepsInProgress")))
    lines.append("xp: {} | wall xp/hr: {} | active-lap xp/hr: {}".format(
        summary.get("xpGained"), summary.get("xpPerHourWall"), summary.get("xpPerHourActiveLaps")))
    if summary.get("expectedLapXp") is not None:
        lines.append("expected lap xp: {} | xp mismatch laps: {}".format(
            summary.get("expectedLapXp"), summary.get("xpMismatchLaps")))
    lap = summary.get("lapDurationSeconds") or {}
    lines.append("lap seconds: avg={} min={} max={}".format(
        lap.get("avg", "-"), lap.get("min", "-"), lap.get("max", "-")))
    if summary.get("failureReasons"):
        lines.append("failures: {}".format(summary["failureReasons"]))
    lines.append("steps:")
    for step in summary.get("stepSummary") or []:
        duration = step.get("durationSeconds") or {}
        ticks = step.get("ticks") or {}
        lines.append("  {}: ok {}/{} skipped={} avg={}s ticks={} failures={} skipReasons={}".format(
            step.get("stepId"), step.get("successes"), step.get("attempts"),
            step.get("skipped", 0), duration.get("avg", "-"), ticks.get("avg", "-"),
            step.get("failureReasons") or {}, step.get("skipReasons") or {}))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize adaptive agility-runner timing logs.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--course", help="Filter latest-log lookup to a course id.")
    parser.add_argument("--log", help="Specific agility JSONL log to summarize.")
    parser.add_argument("--text", action="store_true", help="Print a compact text report instead of JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    path = Path(args.log).expanduser() if args.log else latest_log(args.course, args.profile)
    if not path:
        payload = {
            "ok": False,
            "error": "no_matching_agility_log",
            "courseId": args.course or "",
            "profile": args.profile or "",
            "runsDir": str(RUNS_DIR),
        }
        if args.text:
            print(text_report(payload))
        else:
            print(json.dumps(payload, sort_keys=True, indent=2 if args.pretty else None,
                             separators=None if args.pretty else (",", ":")))
        return 2

    payload = report_for(path)
    if args.text:
        print(text_report(payload))
    else:
        print(json.dumps(payload, sort_keys=True, indent=2 if args.pretty else None,
                         separators=None if args.pretty else (",", ":")))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
