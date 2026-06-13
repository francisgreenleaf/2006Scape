#!/usr/bin/env python3
"""Probe configured 2006Scape per-agent Discord bots without starting the game server."""

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts" / "lib"))

from discord_bot_probe import DiscordProbeError, load_bot_configs, probe_discord_bots  # noqa: E402


def fail(message):
    raise SystemExit("Discord agent bot probe failed: {}".format(message))


def dry_run(secrets_path, agents, allow_placeholders):
    configs = load_bot_configs(secrets_path, allow_placeholders=allow_placeholders, agents=agents)
    return [
        {
            "agent": config["agent"],
            "channelId": config.get("channelId", ""),
            "channelName": config.get("channelName", ""),
            "tokenPresent": bool(config.get("token")),
        }
        for config in configs
    ]


def print_text_results(results, dry_run_mode=False):
    action = "validated" if dry_run_mode else "probed"
    print("ok: {} {} Discord agent bot config{}".format(
        action,
        len(results),
        "" if len(results) == 1 else "s",
    ))
    for result in results:
        if dry_run_mode:
            target = result.get("channelId") or result.get("channelName") or "unknown-channel"
            print("bot {}: config ok, target {}".format(result.get("agent"), target))
            continue
        text = "bot {}: authenticated as {} ({})".format(
            result.get("agent"),
            result.get("botUsername") or "unknown",
            result.get("botUserId") or "unknown-id",
        )
        if result.get("channelChecked"):
            text += ", channel {} ok".format(result.get("channelId"))
            if result.get("channelName"):
                text += " ({})".format(result.get("channelName"))
        elif result.get("warning"):
            text += ", warning: {}".format(result.get("warning"))
        text += ", testMessage={}".format("sent" if result.get("messageSent") else "skipped")
        print(text)


def main():
    parser = argparse.ArgumentParser(description="Probe configured 2006Scape per-agent Discord bots.")
    parser.add_argument("--secrets", default=str(ROOT_DIR / "2006Scape Server" / "data" / "secrets.json"),
            help="Path to ignored data/secrets.json with agent-discord-bots.")
    parser.add_argument("--agent", action="append", default=[],
            help="Only probe this agent/profile. May be passed more than once.")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--send-test-message", action="store_true",
            help="Send one sanitized test message to each configured channelId. Omitted by default.")
    parser.add_argument("--message", default="",
            help="Optional message for --send-test-message. Mentions are escaped before sending.")
    parser.add_argument("--dry-run", action="store_true",
            help="Validate local secrets shape and selected agents without contacting Discord.")
    parser.add_argument("--allow-placeholder-discord-secrets", action="store_true",
            help="Allow tracked placeholder token/channel values. Only useful with --dry-run for source validation.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.allow_placeholder_discord_secrets and not args.dry_run:
        fail("--allow-placeholder-discord-secrets is only valid with --dry-run")
    try:
        if args.dry_run:
            results = dry_run(args.secrets, args.agent, args.allow_placeholder_discord_secrets)
        else:
            results = probe_discord_bots(
                args.secrets,
                timeout=args.timeout,
                agents=args.agent,
                send_test_message=args.send_test_message,
                message=args.message,
            )
    except DiscordProbeError as exc:
        fail(str(exc))

    if args.json:
        print(json.dumps(results, sort_keys=True))
    else:
        print_text_results(results, dry_run_mode=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
