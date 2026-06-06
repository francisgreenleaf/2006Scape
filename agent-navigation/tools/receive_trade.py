#!/usr/bin/env python3
"""Receive an expected player trade through compact bridge primitives."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
from profile_utils import normalize_player_name, resolve_profile  # noqa: E402


ITEM_ALIASES = {
    "coin": 995,
    "coins": 995,
    "gp": 995,
    "gold": 995,
}


def emit(payload: dict) -> None:
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def normalized(value: str | None) -> str:
    return normalize_player_name(value or "")


def resolve_expected_item(item: str, item_id: int) -> tuple[int, str]:
    if item_id >= 0:
        return item_id, item
    key = normalized(item)
    if key in ITEM_ALIASES:
        return ITEM_ALIASES[key], item
    return -1, item


def call_tool(profile: str, tool: str, arguments: dict | None = None) -> dict:
    result = bridge.call_tool(tool, arguments or {}, profile=profile)
    if not isinstance(result, dict):
        raise RuntimeError("{} returned non-object JSON".format(tool))
    return result


def trade_data(status: dict) -> dict:
    trade = status.get("trade")
    return trade if isinstance(trade, dict) else {}


def phase(status: dict) -> str:
    return str(status.get("phase") or trade_data(status).get("phase") or "")


def trade_open(status: dict) -> bool:
    trade = trade_data(status)
    return bool(status.get("tradeOpen") if "tradeOpen" in status else trade.get("tradeOpen"))


def partner_name(status: dict) -> str:
    partner = status.get("partner")
    if not isinstance(partner, dict):
        partner = trade_data(status).get("partner")
    if not isinstance(partner, dict):
        return ""
    return str(partner.get("name") or "")


def item_amount_from_entries(entries: object, item_id: int, item_name: str) -> int:
    if not isinstance(entries, list):
        return 0
    expected_name = normalized(item_name)
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id", entry.get("itemId"))
        entry_name = normalized(str(entry.get("name") or entry.get("n") or ""))
        matches_id = item_id >= 0 and int(entry_id or -1) == item_id
        matches_name = expected_name and expected_name in entry_name
        if matches_id or matches_name:
            total += int(entry.get("amount", entry.get("a")) or 0)
    return total


def partner_offered_amount(status: dict, item_id: int, item_name: str) -> int:
    trade = trade_data(status)
    offered = trade.get("partnerOfferedItems")
    amount = item_amount_from_entries(offered, item_id, item_name)
    if amount:
        return amount
    if item_id < 0 and not item_name:
        return int(status.get("partnerOfferedAmount") or trade.get("partnerOfferedAmount") or 0)
    return 0


def inventory_count(status: dict, item_id: int, item_name: str) -> int:
    inventory = status.get("inventory")
    if isinstance(inventory, dict):
        amount = item_amount_from_entries(inventory.get("counts"), item_id, item_name)
        if amount:
            return amount
        return item_amount_from_entries(inventory.get("items"), item_id, item_name)
    player = status.get("player")
    if isinstance(player, dict):
        return item_amount_from_entries(player.get("inventory"), item_id, item_name)
    return 0


def expected_accept_args(from_player: str, item_id: int, item_name: str, min_amount: int) -> dict:
    args = {
        "expectPartner": from_player,
        "minAmount": min_amount,
    }
    if item_id >= 0:
        args["expectItemId"] = item_id
    elif item_name:
        args["expectItem"] = item_name
    return args


def run(args: argparse.Namespace) -> int:
    profile = resolve_profile(args.profile)
    from_player = args.from_player
    item_id, item_name = resolve_expected_item(args.item, args.item_id)
    if item_id < 0 and not item_name:
        emit({"ok": False, "error": "--item or --item-id is required"})
        return 2

    accept_args = expected_accept_args(from_player, item_id, item_name, args.min_amount)
    deadline = time.time() + max(1.0, args.timeout_seconds)
    first_status = call_tool(profile, "trade_status_XS", {})
    before_count = inventory_count(first_status, item_id, item_name)
    last_status = first_status
    last_result: dict = {}

    while time.time() <= deadline:
        status = call_tool(profile, "trade_status_XS", {})
        last_status = status
        current_count = inventory_count(status, item_id, item_name)
        if not trade_open(status) and current_count >= before_count + args.min_amount:
            emit({
                "ok": True,
                "completed": True,
                "profile": profile,
                "from": from_player,
                "itemId": item_id if item_id >= 0 else None,
                "item": item_name,
                "before": before_count,
                "after": current_count,
                "delta": current_count - before_count,
                "phase": phase(status),
            })
            return 0

        if trade_open(status):
            actual_partner = partner_name(status)
            if normalized(actual_partner) != normalized(from_player):
                emit({
                    "ok": False,
                    "error": "unexpected_trade_partner",
                    "expectedPartner": from_player,
                    "actualPartner": actual_partner,
                    "phase": phase(status),
                })
                return 1
            offered = partner_offered_amount(status, item_id, item_name)
            if offered >= args.min_amount:
                last_result = call_tool(profile, "accept_trade_XS", accept_args)
                if not last_result.get("success", False):
                    emit({
                        "ok": False,
                        "error": "accept_failed",
                        "result": last_result,
                        "phase": phase(status),
                    })
                    return 1
                after = int(last_result.get("itemCountAfter") or current_count)
                before = int(last_result.get("itemCountBefore") or before_count)
                delta = int(last_result.get("itemDelta") or (after - before))
                if not bool(last_result.get("tradeOpen", True)) or delta >= args.min_amount:
                    emit({
                        "ok": True,
                        "completed": delta >= args.min_amount or not bool(last_result.get("tradeOpen", True)),
                        "profile": profile,
                        "from": from_player,
                        "itemId": item_id if item_id >= 0 else last_result.get("expectedItemId"),
                        "item": item_name or last_result.get("expectedItemName"),
                        "before": before,
                        "after": after,
                        "delta": delta,
                        "phase": last_result.get("phase"),
                        "result": last_result,
                    })
                    return 0
            else:
                last_result = {
                    "waitingForOffer": True,
                    "partnerOfferedExpectedAmount": offered,
                    "minAmount": args.min_amount,
                    "phase": phase(status),
                }
        else:
            request_args = {
                "name": from_player,
                "maxDistance": 3,
                "autoWalk": True,
                "autoWalkMaxDistance": args.auto_walk_max_distance,
            }
            last_result = call_tool(profile, "request_player_trade_XS", request_args)
            if not last_result.get("success", False) and not last_result.get("tooFar", False):
                emit({
                    "ok": False,
                    "error": "request_failed",
                    "result": last_result,
                    "phase": phase(status),
                })
                return 1

        time.sleep(max(0.2, args.poll_seconds))

    final_status = call_tool(profile, "trade_status_XS", {})
    emit({
        "ok": False,
        "error": "timeout",
        "profile": profile,
        "from": from_player,
        "itemId": item_id if item_id >= 0 else None,
        "item": item_name,
        "minAmount": args.min_amount,
        "before": before_count,
        "after": inventory_count(final_status, item_id, item_name),
        "phase": phase(final_status),
        "lastStatus": last_status,
        "lastResult": last_result,
    })
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Receive an expected player trade using compact trade primitives.")
    parser.add_argument("--profile", default="", help="Profile to control. Defaults to RS_PROFILE/RSBRIDGE_PROFILE.")
    parser.add_argument("--from", dest="from_player", required=True, help="Expected trading partner/player name.")
    parser.add_argument("--item", default="coins", help="Expected item name. Common aliases include coins/gp.")
    parser.add_argument("--item-id", type=int, default=-1, help="Expected item id. Overrides --item for matching.")
    parser.add_argument("--min-amount", type=int, required=True, help="Minimum partner-offered amount to accept.")
    parser.add_argument("--timeout-seconds", type=float, default=60.0, help="Maximum time to wait for request/offer/completion.")
    parser.add_argument("--poll-seconds", type=float, default=1.2, help="Polling interval while waiting on the other player.")
    parser.add_argument("--auto-walk-max-distance", type=int, default=12, help="Maximum nearby distance for request auto-walk.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.min_amount <= 0:
        parser.error("--min-amount must be positive")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
