#!/usr/bin/env python3
"""Verify that the running server wrote an expected AgentChatService log entry."""

import argparse
import json
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG_ROOT = ROOT_DIR / "2006Scape Server" / "data" / "logs" / "agent-chat"
sys.path.insert(0, str(ROOT_DIR / "scripts" / "lib"))

from deployment_proof_manifest import write_manifest_updates  # noqa: E402


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


def manifest_field(value):
    if value is None:
        return ""
    return str(value).strip()


def manifest_bool_string(value):
    actual = bool_value(value)
    if actual is True:
        return "true"
    if actual is False:
        return "false"
    return ""


def add_if_present(updates, key, value):
    clean = manifest_field(value)
    if clean:
        updates[key] = clean


def add_since_fields(updates, prefix, args):
    if args.since_id:
        updates["{}_since_id".format(prefix)] = args.since_id
    if args.since_seconds:
        updates["{}_since_seconds".format(prefix)] = args.since_seconds
    default_root = str(DEFAULT_LOG_ROOT)
    if str(args.log_root) != default_root:
        add_if_present(updates, "{}_root".format(prefix), args.log_root)


def infer_proof_kind(args):
    if args.proof_kind != "auto":
        return args.proof_kind
    if args.expect_absent:
        return "blocked-routing"
    if args.event == "agent_chat_player_delivery":
        return "agent-player-delivery"
    return "discord-ingress"


def manifest_updates_for(args, latest):
    kind = infer_proof_kind(args)
    updates = {}
    if kind == "agent-player-delivery":
        if args.expect_absent:
            fail("agent-player-delivery proof cannot use --expect-absent")
        target = args.to_name or args.delivered_to or (latest or {}).get("toName")
        add_if_present(updates, "agent_chat_delivery_log_text", args.text_contains)
        add_if_present(updates, "agent_chat_delivery_log_to_name", target)
        add_if_present(updates, "agent_chat_delivery_log_channel", args.channel or (latest or {}).get("channel"))
        add_since_fields(updates, "agent_chat_delivery_log", args)
    elif kind == "blocked-routing":
        if not args.expect_absent:
            fail("blocked-routing proof requires --expect-absent")
        add_if_present(updates, "agent_chat_blocked_log_text", args.text_contains)
        add_if_present(updates, "agent_chat_blocked_log_channel", args.channel)
        add_since_fields(updates, "agent_chat_blocked_log", args)
    elif kind == "discord-ingress":
        if args.expect_absent:
            fail("discord-ingress proof cannot use --expect-absent")
        entry = latest or {}
        from_bot = args.from_bot or manifest_bool_string(entry.get("fromBot"))
        add_if_present(updates, "agent_chat_log_text", args.text_contains)
        add_if_present(updates, "agent_chat_log_from_type", args.from_type or entry.get("fromType"))
        add_if_present(updates, "agent_chat_log_from_name", args.from_name or entry.get("fromName"))
        add_if_present(updates, "agent_chat_log_from_profile", args.from_profile or entry.get("fromProfile"))
        add_if_present(updates, "agent_chat_log_from_bot", from_bot)
        add_if_present(updates, "agent_chat_log_discord_message_id",
                args.discord_message_id or entry.get("discordMessageId"))
        add_if_present(updates, "agent_chat_log_to_type", args.to_type or entry.get("toType"))
        add_if_present(updates, "agent_chat_log_to_name", args.to_name or entry.get("toName"))
        add_if_present(updates, "agent_chat_log_channel", args.channel or entry.get("channel"))
        add_since_fields(updates, "agent_chat_log", args)
    else:
        fail("unsupported proof kind: {}".format(kind))
    if not updates:
        fail("no proof manifest fields could be inferred for {}".format(kind))
    return kind, updates


def update_proof_manifest(args, latest):
    if not args.proof_manifest:
        return "", {}
    kind, updates = manifest_updates_for(args, latest)
    try:
        written = write_manifest_updates(args.proof_manifest, updates)
    except ValueError as exc:
        fail(str(exc))
    return kind, written


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
    parser.add_argument("--proof-manifest", default="",
            help=("Optional existing deployment-proof-manifest JSON to update after successful verification. "
                  "Auto maps delivery, Discord ingress, or blocked-routing absence proof fields."))
    parser.add_argument("--proof-kind", choices=("auto", "agent-player-delivery", "discord-ingress", "blocked-routing"),
            default="auto",
            help="Manifest field group to update when --proof-manifest is supplied. Defaults to auto.")
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
        manifest_kind, manifest_updates = update_proof_manifest(args, None)
        if args.json:
            print(json.dumps({
                "expectAbsent": True,
                "matched": 0,
                "manifestUpdates": manifest_updates,
                "proofKind": manifest_kind,
                "proofManifest": args.proof_manifest,
            }, sort_keys=True))
        else:
            print("ok: no matching agent chat log entries found")
            if args.proof_manifest:
                print("proof manifest: {}".format(args.proof_manifest))
                print("manifest proof kind: {}".format(manifest_kind))
                print("manifest fields: {}".format(", ".join(sorted(manifest_updates))))
        return 0
    if not matches_found:
        fail("no matching agent chat log entry found")
    latest = redact_entry(matches_found[-1])
    manifest_kind, manifest_updates = update_proof_manifest(args, latest)
    if args.json:
        print(json.dumps({
            "manifestUpdates": manifest_updates,
            "matched": len(matches_found),
            "latest": latest,
            "proofKind": manifest_kind,
            "proofManifest": args.proof_manifest,
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
        if args.proof_manifest:
            print("proof manifest: {}".format(args.proof_manifest))
            print("manifest proof kind: {}".format(manifest_kind))
            print("manifest fields: {}".format(", ".join(sorted(manifest_updates))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
