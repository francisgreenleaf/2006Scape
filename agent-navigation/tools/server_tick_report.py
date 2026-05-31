#!/usr/bin/env python3
"""Summarize 2006Scape server cycle-duration noise without touching the runtime."""

import argparse
import json
import re
from pathlib import Path


DEFAULT_LOG = Path("/tmp/2006scape-server.log")
CYCLE_RE = re.compile(
    r"Cycle #(?P<cycle>\d+) took (?P<duration>\d+) ms\. Players: (?P<players>\d+), NPCs: (?P<npcs>\d+).*Threads: (?P<threads>\d+)\."
)
CADENCE_RE = re.compile(
    r"Cadence: interval=(?P<interval>-?\d+)ms, avg=(?P<avg>-?\d+)ms, min=(?P<min>-?\d+)ms, "
    r"max=(?P<max>-?\d+)ms, samples=(?P<samples>\d+), short=(?P<short>\d+), long=(?P<long>\d+)\."
)
LEVEL_RE = re.compile(r"\[(?P<level>INFO|ERROR|WARN|WARNING)\].*?(?P<message>(NOTICE|WARNING|ERROR): .*duration exceeded .*?ms!?)(?: Duration: (?P<duration>\d+) ms\.)?")


def tail_lines(path, limit):
    if limit <= 0:
        return []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    return lines[-limit:]


def summarize(lines, include_lines=False):
    threshold_counts = {"notice": 0, "warning": 0, "error": 0}
    cycle_rows = []
    warnings = []
    errors = []
    for raw in lines:
        line = raw.rstrip("\n")
        level_match = LEVEL_RE.search(line)
        if level_match:
            message = level_match.group("message")
            upper = message.split(":", 1)[0].lower()
            if upper in threshold_counts:
                threshold_counts[upper] += 1
            if upper == "warning":
                warnings.append(line)
            elif upper == "error":
                errors.append(line)
        cycle_match = CYCLE_RE.search(line)
        if cycle_match:
            row = {
                "cycle": int(cycle_match.group("cycle")),
                "durationMs": int(cycle_match.group("duration")),
                "players": int(cycle_match.group("players")),
                "npcs": int(cycle_match.group("npcs")),
                "threads": int(cycle_match.group("threads")),
            }
            cadence_match = CADENCE_RE.search(line)
            if cadence_match:
                row["cadence"] = {
                    "intervalMs": int(cadence_match.group("interval")),
                    "avgMs": int(cadence_match.group("avg")),
                    "minMs": int(cadence_match.group("min")),
                    "maxMs": int(cadence_match.group("max")),
                    "samples": int(cadence_match.group("samples")),
                    "shortIntervals": int(cadence_match.group("short")),
                    "longIntervals": int(cadence_match.group("long")),
                }
            if include_lines:
                row["line"] = line
            cycle_rows.append(row)

    durations = [row["durationMs"] for row in cycle_rows]
    cadence_rows = [row["cadence"] for row in cycle_rows if "cadence" in row]
    report = {
        "thresholdCounts": threshold_counts,
        "cycleSamples": len(cycle_rows),
        "maxCycleDurationMs": max(durations) if durations else None,
        "recentCycle": cycle_rows[-1] if cycle_rows else None,
        "slowCycleSamples": [row for row in cycle_rows if row["durationMs"] > 100][-10:],
        "cadenceSamples": len(cadence_rows),
        "cadence": summarize_cadence(cadence_rows),
    }
    if include_lines:
        report["recentWarnings"] = warnings[-10:]
        report["recentErrors"] = errors[-10:]
    return report


def summarize_cadence(cadence_rows):
    if not cadence_rows:
        return None
    return {
        "recent": cadence_rows[-1],
        "maxIntervalMs": max(row["maxMs"] for row in cadence_rows),
        "minIntervalMs": min(row["minMs"] for row in cadence_rows),
        "shortIntervals": sum(row["shortIntervals"] for row in cadence_rows),
        "longIntervals": sum(row["longIntervals"] for row in cadence_rows),
    }


def print_text_report(path, tail_limit, report, include_lines=False):
    print("server log: {}".format(path))
    print("tail lines scanned: {}".format(tail_limit))
    print("cycle samples: {}".format(report["cycleSamples"]))
    print("threshold counts: notice={notice} warning={warning} error={error}".format(**report["thresholdCounts"]))
    print("max sampled cycle duration ms: {}".format(report["maxCycleDurationMs"]))
    if report["recentCycle"]:
        row = report["recentCycle"]
        print("recent cycle: #{cycle} {durationMs}ms players={players} npcs={npcs} threads={threads}".format(**row))
    if report.get("cadence"):
        cadence = report["cadence"]
        recent = cadence["recent"]
        print(
            "cadence samples: {} recent interval={}ms avg={}ms range={}..{}ms short={} long={}".format(
                report["cadenceSamples"],
                recent["intervalMs"],
                recent["avgMs"],
                recent["minMs"],
                recent["maxMs"],
                cadence["shortIntervals"],
                cadence["longIntervals"],
            )
        )
    if report["slowCycleSamples"]:
        print("slow sampled cycles:")
        for row in report["slowCycleSamples"]:
            print("  #{cycle} {durationMs}ms players={players} npcs={npcs} threads={threads}".format(**row))
    if include_lines and (report.get("recentWarnings") or report.get("recentErrors")):
        print("recent warning/error lines:")
        for line in (report.get("recentWarnings", []) + report.get("recentErrors", []))[-10:]:
            print("  {}".format(line))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize server cycle-duration log noise.")
    parser.add_argument("--log", default=str(DEFAULT_LOG), help="Server log path. Defaults to /tmp/2006scape-server.log.")
    parser.add_argument("--tail-lines", type=int, default=2000, help="Number of recent log lines to scan.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--include-lines", action="store_true", help="Include raw recent warning/error log lines.")
    args = parser.parse_args(argv)

    path = Path(args.log)
    if not path.exists():
        payload = {"ok": False, "error": "log file not found", "log": str(path)}
        print(json.dumps(payload, sort_keys=True) if args.json else payload["error"] + ": " + str(path))
        return 1
    lines = tail_lines(path, int(args.tail_lines))
    report = summarize(lines, include_lines=bool(args.include_lines))
    report.update({"ok": True, "log": str(path), "tailLines": int(args.tail_lines)})
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print_text_report(path, int(args.tail_lines), report, include_lines=bool(args.include_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
