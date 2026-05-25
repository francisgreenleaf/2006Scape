#!/usr/bin/env python3
"""Profile-scoped intentional memories and goals for 2006Scape agents."""

import argparse
import datetime as dt
import json
import os
import re
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
NAV_ROOT = SCRIPT_DIR.parents[0]
DEFAULT_MEMORY_ROOT = NAV_ROOT / ".local" / "character-memory"
KNOWN_PROFILE_ALIASES = {
    "mrflame": "MrFlame",
    "mrgem": "MrGem",
}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_profile_name(profile):
    raw = str(profile or "").strip()
    key = re.sub(r"[^A-Za-z0-9]+", "", raw).lower()
    if key in KNOWN_PROFILE_ALIASES:
        return KNOWN_PROFILE_ALIASES[key]
    return raw or "MrFlame"


def profile_from_args(args):
    return normalize_profile_name(
        args.profile
        or os.environ.get("RS_PROFILE")
        or os.environ.get("RSBRIDGE_PROFILE")
        or os.environ.get("RS_TRACE_PROFILE")
        or "MrFlame"
    )


def profile_slug(profile):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(profile).strip()).strip(".-_").lower()
    return slug or "profile"


def memory_dir(args):
    root = Path(args.memory_root or DEFAULT_MEMORY_ROOT)
    return root / profile_slug(profile_from_args(args))


def memory_paths(args):
    base = memory_dir(args)
    return {
        "dir": base,
        "memories": base / "memories.jsonl",
        "goals": base / "goals.jsonl",
        "summary": base / "summary.md",
    }


def read_jsonl(path):
    records = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"event": "corrupt_line", "raw": line})
    return records


def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def split_tags(value):
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def compact_id(prefix):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "{}-{}-{}".format(prefix, stamp, uuid.uuid4().hex[:6])


def load_goals(path):
    goals = {}
    for record in read_jsonl(path):
        event = record.get("event")
        goal_id = record.get("id")
        if not goal_id:
            continue
        if event == "goal":
            goals[goal_id] = dict(record)
        elif event == "goal_update":
            goal = goals.setdefault(goal_id, {"id": goal_id, "event": "goal", "text": ""})
            goal.update({
                "status": record.get("status", goal.get("status", "active")),
                "updatedAt": record.get("updatedAt", record.get("timestamp")),
                "lastNote": record.get("note", ""),
            })
    return sorted(goals.values(), key=lambda item: item.get("createdAt", item.get("timestamp", "")))


def active_goals(goals):
    return [goal for goal in goals if goal.get("status", "active") == "active"]


def render_summary(profile, paths, limit=12):
    memories = read_jsonl(paths["memories"])
    goals = load_goals(paths["goals"])
    recent_memories = memories[-limit:]
    lines = [
        "# Character Memory: {}".format(profile),
        "",
        "Generated: {}".format(utc_now()),
        "",
        "These are intentional, profile-scoped notes for future agents. Keep them sparse and actionable.",
        "",
        "## Active Goals",
    ]
    current_goals = active_goals(goals)
    if current_goals:
        for goal in current_goals[-limit:]:
            tags = ", ".join(goal.get("tags") or [])
            suffix = " ({})".format(tags) if tags else ""
            lines.append("- [{}] {}{} - {}".format(
                goal.get("priority", "normal"),
                goal.get("id", ""),
                suffix,
                goal.get("text", ""),
            ))
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Recent Memories"])
    if recent_memories:
        for memory in recent_memories:
            tags = ", ".join(memory.get("tags") or [])
            suffix = " ({})".format(tags) if tags else ""
            lines.append("- [{}:{}] {}{} - {}".format(
                memory.get("priority", "normal"),
                memory.get("kind", "memory"),
                memory.get("id", ""),
                suffix,
                memory.get("text", ""),
            ))
    else:
        lines.append("- None recorded.")
    paths["summary"].parent.mkdir(parents=True, exist_ok=True)
    paths["summary"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def command_remember(args):
    profile = profile_from_args(args)
    paths = memory_paths(args)
    record = {
        "event": "memory",
        "id": compact_id("mem"),
        "profile": profile,
        "createdAt": utc_now(),
        "kind": args.kind,
        "priority": args.priority,
        "text": args.text.strip(),
        "tags": split_tags(args.tags),
        "source": args.source.strip(),
        "evidence": args.evidence.strip(),
    }
    if not record["text"]:
        raise SystemExit("--text is required")
    append_jsonl(paths["memories"], record)
    render_summary(profile, paths)
    print(json.dumps({"ok": True, "record": record, "summary": str(paths["summary"])}, sort_keys=True))


def command_goal(args):
    profile = profile_from_args(args)
    paths = memory_paths(args)
    record = {
        "event": "goal",
        "id": compact_id("goal"),
        "profile": profile,
        "createdAt": utc_now(),
        "status": "active",
        "priority": args.priority,
        "text": args.text.strip(),
        "reason": args.reason.strip(),
        "tags": split_tags(args.tags),
        "source": args.source.strip(),
    }
    if not record["text"]:
        raise SystemExit("--text is required")
    append_jsonl(paths["goals"], record)
    render_summary(profile, paths)
    print(json.dumps({"ok": True, "record": record, "summary": str(paths["summary"])}, sort_keys=True))


def command_complete_goal(args):
    profile = profile_from_args(args)
    paths = memory_paths(args)
    record = {
        "event": "goal_update",
        "id": args.id,
        "profile": profile,
        "updatedAt": utc_now(),
        "status": args.status,
        "note": args.note.strip(),
    }
    append_jsonl(paths["goals"], record)
    render_summary(profile, paths)
    print(json.dumps({"ok": True, "record": record, "summary": str(paths["summary"])}, sort_keys=True))


def command_show(args):
    profile = profile_from_args(args)
    paths = memory_paths(args)
    render_summary(profile, paths, limit=args.limit)
    memories = read_jsonl(paths["memories"])
    goals = load_goals(paths["goals"])
    payload = {
        "profile": profile,
        "profileSlug": profile_slug(profile),
        "dir": str(paths["dir"]),
        "summary": str(paths["summary"]),
        "activeGoals": active_goals(goals)[-args.limit:],
        "recentMemories": memories[-args.limit:],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(paths["summary"].read_text(encoding="utf-8").rstrip())


def command_list(args):
    profile = profile_from_args(args)
    paths = memory_paths(args)
    payload = {"profile": profile}
    if args.kind in ("all", "memories"):
        payload["memories"] = read_jsonl(paths["memories"])[-args.limit:]
    if args.kind in ("all", "goals"):
        payload["goals"] = load_goals(paths["goals"])[-args.limit:]
    print(json.dumps(payload, indent=2, sort_keys=True))


def add_common(parser):
    parser.add_argument("--profile", default="", help="Character/profile name. Defaults to RS_PROFILE or MrFlame.")
    parser.add_argument("--memory-root", default="", help="Override memory root, mainly for tests.")
    return parser


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read and write sparse, profile-scoped 2006Scape memories.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show = add_common(subparsers.add_parser("show", help="Show active goals and recent memories."))
    show.add_argument("--limit", type=int, default=12)
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=command_show)

    remember = add_common(subparsers.add_parser("remember", help="Append a noteworthy memory."))
    remember.add_argument("--text", required=True)
    remember.add_argument("--kind", choices=["memory", "lesson", "preference", "warning", "resource", "route", "tooling"],
                          default="memory")
    remember.add_argument("--priority", choices=["low", "normal", "high"], default="normal")
    remember.add_argument("--tags", default="")
    remember.add_argument("--source", default="")
    remember.add_argument("--evidence", default="")
    remember.set_defaults(func=command_remember)

    goal = add_common(subparsers.add_parser("goal", help="Append an active long-term goal."))
    goal.add_argument("--text", required=True)
    goal.add_argument("--priority", choices=["low", "normal", "high"], default="normal")
    goal.add_argument("--tags", default="")
    goal.add_argument("--reason", default="")
    goal.add_argument("--source", default="")
    goal.set_defaults(func=command_goal)

    complete = add_common(subparsers.add_parser("complete-goal", help="Mark a goal done, dropped, or blocked."))
    complete.add_argument("id")
    complete.add_argument("--status", choices=["done", "dropped", "blocked"], default="done")
    complete.add_argument("--note", default="")
    complete.set_defaults(func=command_complete_goal)

    list_cmd = add_common(subparsers.add_parser("list", help="List memories and/or goals as JSON."))
    list_cmd.add_argument("--kind", choices=["all", "memories", "goals"], default="all")
    list_cmd.add_argument("--limit", type=int, default=20)
    list_cmd.set_defaults(func=command_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
