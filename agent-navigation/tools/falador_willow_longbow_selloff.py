#!/usr/bin/env python3
"""Sell Mrwood's banked willow longbow (u) stock at Falador general store.

This is intentionally narrow: it withdraws only willow longbow (u) as notes,
keeps yew bow stock untouched, sells the noted willow bows, and optionally
banks the sale coins back at Falador east bank.
"""

import argparse
import datetime as dt
import json
import os
import sys
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
from profile_utils import resolve_profile  # noqa: E402


WILLOW_LONGBOW_U = 58
WILLOW_LONGBOW_U_NOTE = 59
COINS = 995
WITHDRAW_NOTE_BUTTON = 21010
RUNS_DIR = ROOT / "data" / "fletching" / "falador-selloff-runs"


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_event(handle, event, data):
    payload = {"ts": utc_now(), "event": event}
    payload.update(data)
    handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def compact(player):
    data = bridge.compact_player(player)
    data.update({
        "willowLongbowU": bridge.count_inventory_item(player, WILLOW_LONGBOW_U),
        "notedWillowLongbowU": bridge.count_inventory_item(player, WILLOW_LONGBOW_U_NOTE),
        "coins": bridge.count_inventory_item(player, COINS),
    })
    return data


def player_from(result, profile, fallback=None):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return fallback or bridge.observe_xs(profile=profile)


def bank_count(profile, item_id):
    result = bridge.call_tool("bank_item_count_XS", {"itemIds": [int(item_id)]}, profile=profile)
    for item in result.get("items") or []:
        if int(item.get("itemId", item.get("id", -1)) or -1) == int(item_id):
            return int(item.get("bankAmount", item.get("amount", 0)) or 0)
    return 0


def close_interfaces(profile, handle, reason):
    result = bridge.call_tool("close_interfaces", {}, profile=profile)
    player = player_from(result, profile)
    write_event(handle, "close_interfaces", {
        "reason": reason,
        "success": bool(result.get("success")),
        "player": compact(player),
    })
    return player


def ensure_bank(profile, bank_target, handle, reason):
    player = bridge.observe_xs(profile=profile)
    if not bool(player.get("inBankArea", False)):
        close_interfaces(profile, handle, reason + "_before_route")
        bridge.route_to(bank_target, profile=profile, handle=handle, reason=reason + "_route",
                        extra_args={"runner_max_batches": 10, "max_batch_distance": 32})
        player = bridge.observe_xs(profile=profile)
    result = bridge.call_tool("deposit_inventory_items_XS", {"name": "__codex_open_bank_only__"}, profile=profile)
    player = player_from(result, profile, player)
    write_event(handle, "open_bank", {
        "reason": reason,
        "success": bool(result.get("success")),
        "player": compact(player),
    })
    return player


def withdraw_willow_notes(args, handle):
    player = ensure_bank(args.profile, args.bank, handle, "withdraw_willow_notes")
    banked = bank_count(args.profile, WILLOW_LONGBOW_U)
    carried_notes = bridge.count_inventory_item(player, WILLOW_LONGBOW_U_NOTE)
    if banked <= 0 and carried_notes > 0:
        write_event(handle, "withdraw_skip", {
            "reason": "already_holding_notes",
            "notedWillowLongbowU": carried_notes,
            "player": compact(player),
        })
        return player, carried_notes
    if banked <= 0:
        write_event(handle, "withdraw_skip", {"reason": "none_banked", "player": compact(player)})
        return player, 0
    note_mode = bridge.call_tool("click_interface_button_XXS", {"buttonId": WITHDRAW_NOTE_BUTTON}, profile=args.profile)
    player = player_from(note_mode, args.profile, player)
    write_event(handle, "set_withdraw_note_mode", {
        "buttonId": WITHDRAW_NOTE_BUTTON,
        "success": bool(note_mode.get("success")),
        "player": compact(player),
    })
    before_note = bridge.count_inventory_item(player, WILLOW_LONGBOW_U_NOTE)
    before_normal = bridge.count_inventory_item(player, WILLOW_LONGBOW_U)
    result = {"success": False, "message": "withdraw not attempted"}
    try:
        result = bridge.call_tool("withdraw_bank_items_XS", {
            "itemId": WILLOW_LONGBOW_U,
            "amount": banked,
        }, profile=args.profile)
        player = player_from(result, args.profile, player)
    except RuntimeError as exc:
        player = bridge.observe_xs(profile=args.profile)
        result = {
            "success": False,
            "message": str(exc),
            "withdrawnAmount": 0,
        }
    moved_note = max(0, bridge.count_inventory_item(player, WILLOW_LONGBOW_U_NOTE) - before_note)
    moved_normal = max(0, bridge.count_inventory_item(player, WILLOW_LONGBOW_U) - before_normal)
    moved = moved_note + moved_normal
    write_event(handle, "withdraw_willow_notes", {
        "bankedBefore": banked,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "withdrawnAmount": result.get("withdrawnAmount"),
        "movedNote": moved_note,
        "movedNormal": moved_normal,
        "player": compact(player),
    })
    if moved <= 0 and bank_count(args.profile, WILLOW_LONGBOW_U) <= 0 and bridge.count_inventory_item(player, WILLOW_LONGBOW_U_NOTE) > 0:
        moved = bridge.count_inventory_item(player, WILLOW_LONGBOW_U_NOTE)
        write_event(handle, "withdraw_recovered_from_carried_notes", {
            "recoveredAmount": moved,
            "player": compact(player),
        })
    if moved <= 0:
        raise RuntimeError("withdrew no willow longbow (u) stock")
    if moved_normal > 0 and moved_note <= 0:
        raise RuntimeError("withdraw produced unnoted willow bows; refusing to run hundreds of manual sale trips")
    return player, moved


def route_to_shop(args, handle):
    close_interfaces(args.profile, handle, "before_shop_route")
    bridge.route_to(args.shop_target, profile=args.profile, handle=handle, reason="falador_general_store",
                    extra_args={"runner_max_batches": args.route_max_batches, "max_batch_distance": args.max_batch_distance})
    player = bridge.observe_xs(profile=args.profile)
    write_event(handle, "route_to_shop", {"target": args.shop_target, "player": compact(player)})
    return player


def sell_willow(args, handle, player):
    result = bridge.call_tool("open_nearest_shop", {
        "name": args.shop_name,
        "maxDistance": args.shop_max_distance,
    }, profile=args.profile)
    player = player_from(result, args.profile, player)
    write_event(handle, "open_shop", {
        "shopName": args.shop_name,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "player": compact(player),
    })
    if not result.get("success"):
        raise RuntimeError(result.get("message", "could not open Falador general store"))
    before_coins = bridge.count_inventory_item(player, COINS)
    before_willow = bridge.count_inventory_item(player, WILLOW_LONGBOW_U_NOTE)
    result = bridge.call_tool("sell_inventory_items", {
        "itemIds": [WILLOW_LONGBOW_U, WILLOW_LONGBOW_U_NOTE],
        "amount": int(args.sell_amount),
    }, profile=args.profile)
    player = player_from(result, args.profile, player)
    sold = int(result.get("sold", 0) or 0)
    coins = int(result.get("coinsReceived", 0) or 0)
    if coins <= 0:
        coins = max(0, bridge.count_inventory_item(player, COINS) - before_coins)
    write_event(handle, "sell_willow", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "requestedAmount": int(args.sell_amount),
        "notedWillowBefore": before_willow,
        "sold": sold,
        "coinsReceived": coins,
        "soldItems": result.get("soldItems", []),
        "player": compact(player),
    })
    return player, sold, coins


def bank_coins(args, handle, player):
    if not args.bank_coins or bridge.count_inventory_item(player, COINS) <= 0:
        return player
    close_interfaces(args.profile, handle, "before_bank_coins_route")
    bridge.route_to(args.bank, profile=args.profile, handle=handle, reason="bank_sale_coins",
                    extra_args={"runner_max_batches": args.route_max_batches, "max_batch_distance": args.max_batch_distance})
    player = ensure_bank(args.profile, args.bank, handle, "bank_sale_coins")
    coins = bridge.count_inventory_item(player, COINS)
    if coins <= 0:
        return player
    result = bridge.call_tool("deposit_inventory_items_XS", {"itemIds": [COINS], "amount": coins}, profile=args.profile)
    player = player_from(result, args.profile, player)
    write_event(handle, "bank_coins", {
        "success": bool(result.get("success")),
        "depositedAmount": result.get("depositedAmount"),
        "player": compact(player),
    })
    return player


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sell banked willow longbow (u) stock at Falador general store.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--bank", default="falador_east_bank")
    parser.add_argument("--shop-target", default="2958,3387,0")
    parser.add_argument("--shop-name", default="shop keeper")
    parser.add_argument("--shop-max-distance", type=int, default=10)
    parser.add_argument("--route-max-batches", type=int, default=12)
    parser.add_argument("--max-batch-distance", type=int, default=36)
    parser.add_argument("--sell-amount", type=int, default=28000)
    parser.add_argument("--bank-coins", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args(argv)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-falador-willow-selloff-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    with run_path.open("a", encoding="utf-8") as handle:
        write_event(handle, "start", {"args": vars(args), "runLog": str(run_path)})
        player, withdrawn = withdraw_willow_notes(args, handle)
        if withdrawn <= 0:
            summary = {"ok": True, "sold": 0, "coinsReceived": 0, "runLog": str(run_path)}
            print(json.dumps(summary, sort_keys=True))
            return 0
        player = route_to_shop(args, handle)
        player, sold, coins = sell_willow(args, handle, player)
        player = bank_coins(args, handle, player)
        remaining = bank_count(args.profile, WILLOW_LONGBOW_U)
        summary = {
            "ok": True,
            "withdrawn": withdrawn,
            "sold": sold,
            "coinsReceived": coins,
            "remainingBankedWillowLongbowU": remaining,
            "player": compact(player),
            "runLog": str(run_path),
        }
        write_event(handle, "done", summary)
        print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
