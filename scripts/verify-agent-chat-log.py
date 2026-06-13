#!/usr/bin/env python3
"""Verify that the running server wrote an expected AgentChatService log entry."""

import argparse
import json
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG_ROOT = ROOT_DIR / "2006Scape Server" / "data" / "logs" / "agent-chat"


def fail(message):
    raise SystemExit("agent chat log verification failed: {}".format(message))


def load_entries(log_root):
    root = Path(log_root)
    if not root.exists():
        fail("log root does not exist: {}".format(root))
    if not root.is_dir():
        fail("log root is not a directory: {}".format(root))
    paths = sorted(root.glob("*/agent-chat.jsonl"))
    if not paths:
        fail("no agent-chat.jsonl files found under {}".format(root))
    entries = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            fail("could not read {}: {}".format(path, exc))
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                fail("invalid JSON in {} line {}: {}".format(path, line_number, exc))
            if isinstance(entry, dict):
                entry["_path"] = str(path)
                entry["_line"] = line_number
                entries.append(entry)
    return entries


def canonical(value):
    return "" if value is None else str(value).strip().lower()


def numeric(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def bool_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean in ("true", "1", "yes", "on"):
            return True
        if clean in ("false", "0", "no", "off"):
            return False
    return None


def canonical_list(value):
    if not isinstance(value, list):
        return []
    return [canonical(item) for item in value if canonical(item)]


def matches(entry, args, cutoff_ms):
    if args.event and str(entry.get("event", "")) != args.event:
        return False
    if cutoff_ms and numeric(entry.get("timestampMs", entry.get("createdAt", 0))) < cutoff_ms:
        return False
    if args.since_id and numeric(entry.get("id", 0)) <= args.since_id:
        return False
    for field, expected in (
        ("fromType", args.from_type),
        ("fromName", args.from_name),
        ("fromProfile", args.from_profile),
        ("toType", args.to_type),
        ("toName", args.to_name),
        ("channel", args.channel),
        ("discordMessageId", args.discord_message_id),
    ):
        if expected and canonical(entry.get(field, "")) != canonical(expected):
            return False
    if args.from_bot:
        expected_from_bot = args.from_bot == "true"
        actual_from_bot = bool_value(entry.get("fromBot"))
        if actual_from_bot is None or actual_from_bot != expected_from_bot:
            return False
    if args.delivered_to and canonical(args.delivered_to) not in canonical_list(entry.get("deliveredTo")):
        return False
    if args.undelivered_to and canonical(args.undelivered_to) not in canonical_list(entry.get("undeliveredTo")):
        return False
    if args.no_undelivered and canonical_list(entry.get("undeliveredTo")):
        return False
    if args.text_contains and args.text_contains not in str(entry.get("text", "")):
        return False
    return True


def redact_entry(entry):
    clean = dict(entry)
    return clean


def main():
    parser = argparse.ArgumentParser(description="Verify expected AgentChatService JSONL log entries.")
    parser.add_argument("--log-root", default=str(DEFAULT_LOG_ROOT),
            help="Directory containing dated agent-chat/ log folders.")
    parser.add_argument("--text-contains", required=True,
            help="Marker text that must appear in the sanitized logged message text.")
    parser.add_argument("--event", default="agent_chat_message",
            help="Expected log event. Defaults to agent_chat_message; use agent_chat_player_delivery for direct player delivery proof.")
    parser.add_argument("--from-type", default="",
            help="Expected fromType, for example discord, agent, or player.")
    parser.add_argument("--from-name", default="")
    parser.add_argument("--from-profile", default="")
    parser.add_argument("--from-bot", choices=("true", "false"), default="",
            help="Require logged fromBot metadata. Useful for proving real human Discord ingress.")
    parser.add_argument("--discord-message-id", default="",
            help="Require a specific Discord message id captured on ingress.")
    parser.add_argument("--to-type", default="")
    parser.add_argument("--to-name", default="")
    parser.add_argument("--channel", default="")
    parser.add_argument("--delivered-to", default="",
            help="Require a name in the deliveredTo array. Useful with --event agent_chat_player_delivery.")
    parser.add_argument("--undelivered-to", default="",
            help="Require a name in the undeliveredTo array.")
    parser.add_argument("--no-undelivered", action="store_true",
            help="Reject entries that have any undeliveredTo values.")
    parser.add_argument("--since-id", type=int, default=0)
    parser.add_argument("--since-seconds", type=float, default=0.0,
            help="Only accept entries whose timestampMs/createdAt is within this many seconds.")
    parser.add_argument("--expect-absent", action="store_true",
            help="Succeed only when no matching entry exists. Useful for blocked-routing proof markers.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cutoff_ms = 0
    if args.since_seconds:
        if args.since_seconds < 0:
            fail("--since-seconds must be non-negative")
        cutoff_ms = int((time.time() - args.since_seconds) * 1000)
    entries = load_entries(args.log_root)
    matches_found = [entry for entry in entries if matches(entry, args, cutoff_ms)]
    if args.expect_absent:
        if matches_found:
            fail("found {} matching agent chat log entr{} but expected none".format(
                len(matches_found),
                "y" if len(matches_found) == 1 else "ies",
            ))
        if args.json:
            print(json.dumps({
                "expectAbsent": True,
                "matched": 0,
            }, sort_keys=True))
        else:
            print("ok: no matching agent chat log entries found")
        return 0
    if not matches_found:
        fail("no matching agent chat log entry found")
    latest = redact_entry(matches_found[-1])
    if args.json:
        print(json.dumps({
            "matched": len(matches_found),
            "latest": latest,
        }, sort_keys=True))
    else:
        print("ok: matched {} agent chat log entr{}".format(
            len(matches_found),
            "y" if len(matches_found) == 1 else "ies",
        ))
        print("latest: id={} event={} fromType={} fromName={} fromBot={} discordMessageId={} toType={} channel={} file={}:{}".format(
            latest.get("id"),
            latest.get("event", ""),
            latest.get("fromType"),
            latest.get("fromName"),
            latest.get("fromBot", ""),
            latest.get("discordMessageId", ""),
            latest.get("toType"),
            latest.get("channel"),
            latest.get("_path"),
            latest.get("_line"),
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
