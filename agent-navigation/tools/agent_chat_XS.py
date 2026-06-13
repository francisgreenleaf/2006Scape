#!/usr/bin/env python3
"""Compact helper for structured agent chat bridge tools."""

import argparse
import json

import bridge_script as bridge
from profile_utils import resolve_profile


def dump(payload):
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description="Send/read compact structured agent chat.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    sub = parser.add_subparsers(dest="command", required=True)

    send = sub.add_parser("send", help="Send a structured chat message.")
    send.add_argument("message")
    send.add_argument("--to", default="")
    send.add_argument("--to-type", default="")
    send.add_argument("--agent", default="", help="Shortcut for --to-type agent --to NAME.")
    send.add_argument("--player", default="", help="Shortcut for --to-type player --to NAME.")
    send.add_argument("--broadcast", action="store_true", help="Broadcast to the shared agent channel and online players.")
    send.add_argument("--channel", default="agent")
    send.add_argument("--also-public", action="store_true")
    send.add_argument("--deliver-to-players", action="store_true")

    read = sub.add_parser("read", help="Read recent structured chat messages.")
    read.add_argument("--since-id", type=int, default=0)
    read.add_argument("--channel", default="agent")
    read.add_argument("--limit", type=int, default=10)

    status = sub.add_parser("status", help="Read compact structured chat status.")
    status.add_argument("--since-id", type=int, default=0)
    status.add_argument("--channel", default="agent")

    args = parser.parse_args()
    if args.command == "send":
        shortcut_targets = [bool(args.agent), bool(args.player), bool(args.broadcast)]
        if sum(shortcut_targets) > 1:
            parser.error("send accepts only one of --agent, --player, or --broadcast")
        if (args.agent or args.player or args.broadcast) and (args.to or args.to_type):
            parser.error("send shortcut targets cannot be combined with --to or --to-type")
        payload = {"message": args.message, "channel": args.channel}
        if args.agent:
            payload["agent"] = args.agent
        elif args.player:
            payload["player"] = args.player
        elif args.broadcast:
            payload["toType"] = "broadcast"
        else:
            if args.to:
                payload["to"] = args.to
            if args.to_type:
                payload["toType"] = args.to_type
        if args.also_public:
            payload["alsoPublic"] = True
        if args.deliver_to_players:
            payload["deliverToPlayers"] = True
        dump(bridge.call_tool("agent_chat_send_XS", payload, profile=args.profile))
        return 0
    if args.command == "read":
        dump(bridge.call_tool("agent_chat_read_XS", {
            "sinceId": args.since_id,
            "channel": args.channel,
            "limit": args.limit,
        }, profile=args.profile))
        return 0
    dump(bridge.call_tool("agent_chat_status_XS", {
        "sinceId": args.since_id,
        "channel": args.channel,
    }, profile=args.profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
