#!/usr/bin/env python3
"""Verify that a configured Discord bot can see a mirrored marker in its channel."""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts" / "lib"))

from discord_bot_probe import DiscordProbeError, verify_channel_messages  # noqa: E402
from deployment_proof_manifest import write_manifest_updates  # noqa: E402


def fail(message):
    raise SystemExit("Discord channel message verification failed: {}".format(message))


def print_text_results(results):
    total = sum(int(result.get("matched", 0)) for result in results)
    print("ok: matched {} Discord channel message{}".format(
        total,
        "" if total == 1 else "s",
    ))
    for result in results:
        print("bot {}: latest message {} in channel {}{} authorBot={} at {}".format(
            result.get("agent"),
            result.get("latestMessageId") or "unknown-id",
            result.get("channelId") or "unknown-channel",
            " ({})".format(result.get("channelName")) if result.get("channelName") else "",
            "yes" if result.get("latestAuthorBot") else "no",
            result.get("latestTimestamp") or "unknown-time",
        ))


def manifest_agents(args, results):
    agents = list(args.agent or [])
    if agents:
        return agents
    seen = []
    for result in results:
        if int(result.get("matched", 0)) <= 0:
            continue
        agent = str(result.get("agent") or "").strip()
        if agent and agent not in seen:
            seen.append(agent)
    return seen


def update_proof_manifest(args, results):
    if not args.proof_manifest:
        return {}
    if args.allow_human_author:
        fail("refusing to record server-to-Discord proof with --allow-human-author")
    updates = {
        "discord_channel_message_text": args.text_contains,
    }
    agents = manifest_agents(args, results)
    if agents:
        updates["discord_channel_message_agent"] = agents
    if args.limit != 50:
        updates["discord_channel_message_limit"] = args.limit
    if args.after_id:
        updates["discord_channel_message_after_id"] = args.after_id
    if args.require_all:
        updates["discord_channel_message_require_all"] = True
    try:
        return write_manifest_updates(args.proof_manifest, updates)
    except ValueError as exc:
        fail(str(exc))


def main():
    parser = argparse.ArgumentParser(
        description="Verify a recent Discord channel message containing a marker.")
    parser.add_argument("--secrets", default=str(ROOT_DIR / "2006Scape Server" / "data" / "secrets.json"),
            help="Path to ignored data/secrets.json with agent-discord-bots.")
    parser.add_argument("--agent", action="append", default=[],
            help="Only check this agent/profile. May be passed more than once.")
    parser.add_argument("--text-contains", required=True,
            help="Marker text that must appear in the Discord message content.")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--limit", type=int, default=50,
            help="Recent channel messages to inspect per bot, 1-100.")
    parser.add_argument("--after-id", default="",
            help="Only inspect Discord messages newer than this message id.")
    parser.add_argument("--allow-human-author", action="store_true",
            help="Accept any author. Omit for server-to-Discord mirror proof, which requires the configured bot author.")
    parser.add_argument("--require-all", action="store_true",
            help="Require every selected bot channel to contain the marker.")
    parser.add_argument("--proof-manifest", default="",
            help=("Optional existing deployment-proof-manifest JSON to update after successful "
                  "server-to-Discord mirror verification."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        results = verify_channel_messages(
            args.secrets,
            args.text_contains,
            timeout=args.timeout,
            agents=args.agent,
            limit=args.limit,
            after_id=args.after_id,
            require_bot_author=not args.allow_human_author,
            require_all=args.require_all,
        )
    except DiscordProbeError as exc:
        fail(str(exc))

    manifest_updates = update_proof_manifest(args, results)
    if args.json:
        if not args.proof_manifest:
            print(json.dumps(results, sort_keys=True))
            return 0
        payload = {
            "results": results,
            "proofManifest": args.proof_manifest,
            "manifestUpdates": manifest_updates,
        }
        print(json.dumps(payload, sort_keys=True))
    else:
        print_text_results(results)
        if args.proof_manifest:
            print("proof manifest: {}".format(args.proof_manifest))
            print("manifest fields: {}".format(", ".join(sorted(manifest_updates))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
