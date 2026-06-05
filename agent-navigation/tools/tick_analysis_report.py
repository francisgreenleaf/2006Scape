#!/usr/bin/env python3
"""Summarize runner tick/timing JSONL logs without loading raw logs into context."""

import argparse
import datetime as dt
import glob
import json
import statistics
from pathlib import Path

from profile_utils import resolve_profile, safe_profile


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
FLAX_FAST_RUNS = ROOT / "data" / "crafting" / "seers-flax-fast-runs"
RUNNER_STATUS_DIR = ROOT / ".local" / "runners"


def parse_ts(value):
    if not value:
        return None
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000.0


def event_ms(event):
    if event.get("runElapsedMs") is not None:
        return float(event["runElapsedMs"])
    return parse_ts(event.get("ts"))


def ms(value):
    if value is None:
        return "-"
    value = float(value)
    if value >= 1000:
        return "{:.2f}s".format(value / 1000.0)
    return "{}ms".format(int(round(value)))


def stat(values):
    values = [float(v) for v in values if v is not None]
    if not values:
        return None
    return {
        "n": len(values),
        "min": min(values),
        "avg": statistics.fmean(values),
        "max": max(values),
    }


def fmt_stat(label, values):
    summary = stat(values)
    if not summary:
        return "  {}: no data".format(label)
    return "  {}: n={} avg={} min={} max={}".format(
        label,
        summary["n"],
        ms(summary["avg"]),
        ms(summary["min"]),
        ms(summary["max"]),
    )


def latest_log(profile, runner):
    if runner != "seers-flax-spin-fast":
        raise RuntimeError("unsupported runner: {}".format(runner))
    status = RUNNER_STATUS_DIR / "seers-flax-spin-fast-{}.status.json".format(safe_profile(profile))
    if status.exists():
        try:
            data = json.loads(status.read_text(encoding="utf-8"))
            path = data.get("runLog")
            if path and Path(path).exists():
                return Path(path)
        except (OSError, json.JSONDecodeError):
            pass
    logs = sorted(glob.glob(str(FLAX_FAST_RUNS / "*-seers-flax-spin-fast-*.jsonl")))
    if not logs:
        raise RuntimeError("no seers flax fast logs found")
    return Path(logs[-1])


def load_events(path):
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


def durations(events, name, field="durationMs", predicate=None):
    values = []
    for event in events:
        if event.get("event") != name:
            continue
        if predicate and not predicate(event):
            continue
        if event.get(field) is not None:
            values.append(event.get(field))
    return values


def intervals(events):
    values = []
    previous = None
    for event in events:
        current = event_ms(event)
        if current is None:
            continue
        if previous is not None:
            values.append(current - previous)
        previous = current
    return values


def first_after(events, index, name, predicate=None):
    for event in events[index + 1:]:
        if event.get("event") != name:
            continue
        if predicate and not predicate(event):
            continue
        return event
    return None


def leg_values(events, contains):
    return [
        event.get("durationMs")
        for event in events
        if event.get("event") == "walk_tile"
        and contains in str(event.get("reason", ""))
        and event.get("durationMs") is not None
    ]


def top_floor_to_first_bowstring(events):
    values = []
    for index, event in enumerate(events):
        if event.get("event") != "ladder_transition":
            continue
        if int(event.get("expectedHeight", -1)) != 1:
            continue
        source_ms = event_ms(event)
        if source_ms is None:
            continue
        arrived = first_after(events, index, "item_arrived", lambda item: item.get("phase") == "spin")
        if arrived:
            values.append(event_ms(arrived) - source_ms)
    return values


def route_leg_to_ladder_click(events):
    values = []
    for index, event in enumerate(events):
        if event.get("event") not in ("walk_tile", "walk_tile_skip"):
            continue
        if "ladder" not in str(event.get("reason", "")) or "approach" not in str(event.get("reason", "")):
            continue
        source_ms = event_ms(event)
        if source_ms is None:
            continue
        action = first_after(
            events,
            index,
            "action_start",
            lambda item: item.get("action") == "object_transition",
        )
        if action:
            values.append(event_ms(action) - source_ms)
    return values


def report(events, path):
    lines = []
    lines.append("Tick Analysis Report")
    lines.append("log: {}".format(path))
    if not events:
        lines.append("no events")
        return "\n".join(lines)

    start = event_ms(events[0])
    end = event_ms(events[-1])
    runtime_ms = end - start if start is not None and end is not None else None
    cycles = [event for event in events if event.get("event") == "cycle_complete"]
    bowstring_items = [
        event for event in events
        if event.get("event") == "item_arrived" and event.get("phase") == "spin"
    ]
    pick_items = [
        event for event in events
        if event.get("event") == "item_arrived" and event.get("phase") == "pick"
    ]
    old_spin_made = sum(
        max(0, int(event.get("afterBowstrings", 0) or 0) - int(event.get("beforeBowstrings", 0) or 0))
        for event in events
        if event.get("event") == "spin_inventory"
    )
    made_bowstrings = len(bowstring_items) or old_spin_made
    if runtime_ms and runtime_ms > 0:
        lines.append("runtime: {} | cycles: {} | bowstrings seen: {} | rate: {:.1f}/hr".format(
            ms(runtime_ms), len(cycles), made_bowstrings, made_bowstrings * 3600000.0 / runtime_ms))
    else:
        lines.append("cycles: {} | bowstrings seen: {}".format(len(cycles), made_bowstrings))

    lines.append("")
    lines.append("Cycle and phase durations")
    lines.append(fmt_stat("cycle_complete", durations(events, "cycle_complete")))
    lines.append(fmt_stat("pick_inventory", durations(events, "pick_inventory")))
    lines.append(fmt_stat("spin_inventory", durations(events, "spin_inventory")))
    lines.append(fmt_stat("bank_deposit", durations(events, "bank_deposit")))

    lines.append("")
    lines.append("Pick timing")
    lines.append(fmt_stat("pick click bridge call", durations(events, "pick_flax_click", "clickMs")))
    lines.append(fmt_stat("pick click->observed item", [event.get("clickToObservedMs") for event in pick_items]))
    lines.append(fmt_stat("successful pick item intervals", intervals(pick_items)))
    old_success_pick_intervals = intervals([
        event for event in events
        if event.get("event") == "pick_flax_click" and int(event.get("gained", 0) or 0) > 0
    ])
    if not pick_items:
        lines.append(fmt_stat("successful pick intervals fallback", old_success_pick_intervals))
    lines.append("  no-gain pick clicks: {}".format(sum(
        1 for event in events
        if event.get("event") == "pick_flax_click" and int(event.get("gained", 0) or 0) <= 0
    )))

    lines.append("")
    lines.append("Spin timing")
    lines.append(fmt_stat("use flax on wheel", durations(events, "spin_use_item_on_object")))
    lines.append(fmt_stat("spin button click", durations(events, "spin_button_click")))
    lines.append(fmt_stat("spin progress chunks", durations(events, "spin_progress_chunk")))
    coalesced_spin_items = [event for event in bowstring_items if int(event.get("deltaCount", 1) or 1) > 1]
    per_item_batches = [
        float(event.get("durationMs")) / max(1, int(event.get("madeBowstrings", 0) or 0))
        for event in events
        if event.get("event") == "spin_progress_chunk"
        and int(event.get("madeBowstrings", 0) or 0) > 0
        and event.get("durationMs") is not None
    ]
    if coalesced_spin_items:
        lines.append(fmt_stat("bowstring batch per-item estimate", per_item_batches))
        lines.append("  bowstring arrivals are coalesced: itemEvents={} chunks={} largestDelta={}".format(
            len(bowstring_items),
            len(per_item_batches),
            max(int(event.get("deltaCount", 1) or 1) for event in coalesced_spin_items),
        ))
    else:
        lines.append(fmt_stat("bowstring item intervals", intervals(bowstring_items)))
    lines.append(fmt_stat("attempt start->observed bowstring", [
        event.get("sinceAttemptUseMs") for event in bowstring_items
    ]))
    if not bowstring_items:
        estimated = []
        for event in events:
            if event.get("event") != "spin_inventory":
                continue
            made = max(0, int(event.get("afterBowstrings", 0) or 0) - int(event.get("beforeBowstrings", 0) or 0))
            if made > 0 and event.get("waitMs") is not None:
                estimated.append(float(event["waitMs"]) / made)
        lines.append(fmt_stat("estimated per bowstring fallback", estimated))

    lines.append("")
    lines.append("Route and transition timing")
    lines.append(fmt_stat("bank/flax route legs", leg_values(events, "to_flax")))
    lines.append(fmt_stat("flax->ladder route legs", leg_values(events, "flax_to_ladder")))
    lines.append(fmt_stat("arrived near ladder->transition action", route_leg_to_ladder_click(events)))
    lines.append(fmt_stat("ladder transition", durations(events, "ladder_transition")))
    lines.append(fmt_stat("upstairs ladder->first bowstring", top_floor_to_first_bowstring(events)))
    lines.append(fmt_stat("wheel approach", leg_values(events, "to_wheel")))
    lines.append(fmt_stat("ladder/bank route legs", leg_values(events, "to_bank")))

    slow = sorted(
        [
            event for event in events
            if event.get("durationMs") is not None and event.get("event") not in ("cycle_complete",)
        ],
        key=lambda item: float(item.get("durationMs") or 0),
        reverse=True,
    )[:8]
    lines.append("")
    lines.append("Slowest timed events")
    if slow:
        for event in slow:
            reason = event.get("reason") or event.get("action") or event.get("sourceAction") or ""
            lines.append("  {} {} duration={} seq={}".format(
                event.get("event"), reason, ms(event.get("durationMs")), event.get("seq", "-")))
    else:
        lines.append("  no timed events")

    if not pick_items or not bowstring_items:
        lines.append("")
        lines.append("Instrumentation note: item_arrived events are missing for at least one phase in this log, so fallback estimates are shown where possible.")
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--runner", default="seers-flax-spin-fast")
    parser.add_argument("--latest", action="store_true", help="Use the latest/status log for the selected runner.")
    parser.add_argument("--log", help="Path to a JSONL runner log.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.profile = resolve_profile(args.profile)
    path = Path(args.log) if args.log else latest_log(args.profile, args.runner)
    events = load_events(path)
    print(report(events, path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
