#!/usr/bin/env python3
"""Compact reader for recent 2006Scape agent session logs."""

import argparse
import collections
import json
import os
from pathlib import Path

from usage_log import log_usage
from xs_common import ROOT, dump, tile


LOG_ROOT = ROOT / "2006Scape Server" / "data" / "logs" / "agent-sessions"


def norm(value):
    return str(value or "").strip().lower().replace(" ", "")


def message_from_result(result):
    if isinstance(result, dict):
        return result.get("message") or result.get("error") or ""
    return str(result or "")


def player_summary(player):
    if not isinstance(player, dict):
        return {}
    inv = player.get("inventory") if isinstance(player.get("inventory"), list) else []
    food = 0
    heal = 0
    for entry in inv:
        if isinstance(entry, dict) and entry.get("foodHeal"):
            amount = int(entry.get("amount") or 1)
            food += amount
            heal += amount * int(entry.get("foodHeal") or 0)
    return {
        "tile": tile(player),
        "hp": player.get("hitpoints"),
        "max": player.get("maxHitpoints"),
        "run": player.get("runEnergy"),
        "runOn": player.get("runEnabled"),
        "free": player.get("freeInventorySlots"),
        "food": food,
        "heal": heal,
        "bank": player.get("inBankArea"),
        "combat": player.get("isInCombat"),
        "dead": player.get("isDead"),
    }


def event_player(event):
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    result = data.get("result")
    if isinstance(result, dict) and isinstance(result.get("player"), dict):
        return result["player"]
    if isinstance(event.get("player"), dict):
        return event["player"]
    return {}


def session_matches(path, profile):
    if not profile:
        return True
    wanted = norm(profile)
    try:
        with path.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index > 80:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if norm(event.get("playerName")) == wanted:
                    return True
                player = event_player(event)
                if norm(player.get("name")) == wanted:
                    return True
    except OSError:
        return False
    return False


def latest_session_path(profile="", date=""):
    roots = [LOG_ROOT / date] if date else sorted(
        [path for path in LOG_ROOT.iterdir() if path.is_dir() and path.name[:4].isdigit()],
        reverse=True,
    )
    candidates = []
    for root in roots:
        if not root.exists():
            continue
        candidates.extend(root.glob("*.jsonl"))
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        if session_matches(path, profile):
            return path
    return None


def summarize(path, recent_limit=10, failure_limit=10):
    counts = collections.Counter()
    failures = []
    recent = collections.deque(maxlen=recent_limit)
    first_ts = ""
    last_ts = ""
    player_name = ""
    current = {}
    events = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events += 1
            ts = event.get("timestamp", "")
            first_ts = first_ts or ts
            last_ts = ts or last_ts
            if event.get("playerName"):
                player_name = event.get("playerName")
            kind = event.get("event")
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            tool = data.get("tool")
            if kind in ("tool_completed", "tool_failed") and tool:
                counts[tool] += 1
                result = data.get("result")
                player = event_player(event)
                if player:
                    current = player_summary(player)
                compact_event = {
                    "at": ts,
                    "tool": tool,
                    "ok": kind == "tool_completed",
                    "msg": message_from_result(result)[:160],
                    "status": result.get("batchStatus") if isinstance(result, dict) else None,
                    "p": current,
                }
                recent.append({k: v for k, v in compact_event.items() if v not in (None, "", {}, [])})
                if kind == "tool_failed":
                    failures.append(compact_event)
    md_path = path.with_suffix(".md")
    return {
        "ok": True,
        "sessionId": path.stem,
        "player": player_name,
        "started": first_ts,
        "updated": last_ts,
        "events": events,
        "jsonl": str(path),
        "jsonlBytes": path.stat().st_size,
        "md": str(md_path) if md_path.exists() else "",
        "mdBytes": md_path.stat().st_size if md_path.exists() else 0,
        "topTools": [{"tool": tool, "count": count} for tool, count in counts.most_common(12)],
        "failures": [
            {k: v for k, v in failure.items() if v not in (None, "", {}, [])}
            for failure in failures[-failure_limit:]
        ],
        "recent": list(recent),
        "current": current,
    }


def main():
    parser = argparse.ArgumentParser(description="Summarize latest/current agent session logs in compact form.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE", "MrFlame"))
    parser.add_argument("--date", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--latest", action="store_true", default=True)
    parser.add_argument("--recent", type=int, default=10)
    parser.add_argument("--failures", type=int, default=10)
    args = parser.parse_args()
    log_usage("agent_session_XS", surface="xs", argv=vars(args))
    if args.session_id:
        date_roots = [LOG_ROOT / args.date] if args.date else sorted(LOG_ROOT.glob("20??-??-??"), reverse=True)
        path = next((root / (args.session_id + ".jsonl") for root in date_roots
                     if (root / (args.session_id + ".jsonl")).exists()), None)
    else:
        path = latest_session_path(args.profile, args.date)
    if path is None:
        dump({"ok": False, "error": "no matching agent session log", "profile": args.profile, "date": args.date})
        return 1
    dump(summarize(path, recent_limit=max(1, args.recent), failure_limit=max(1, args.failures)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
