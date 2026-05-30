#!/usr/bin/env python3
"""Clean grimy guams from the bank until only two remain grimy."""

import argparse
import json

import bridge_script as bridge


GRIMY_GUAM = 199
CLEAN_GUAM = 249
KEEP_GRIMY_GUAMS = 2


def call_tool(name, arguments, profile):
    return bridge.call_tool(name, arguments, profile=profile)


def observe(profile):
    return bridge.observe(profile)


def inventory(player):
    return player.get("inventory") or []


def bank(player):
    return player.get("bank") or []


def item_id(entry):
    return int(entry.get("id", entry.get("itemId", -1)) or -1)


def item_amount(entry):
    return int(entry.get("amount", 1) or 1)


def count_inventory(player, wanted_id):
    return sum(item_amount(entry) for entry in inventory(player) if item_id(entry) == int(wanted_id))


def count_bank(player, wanted_id):
    return sum(item_amount(entry) for entry in bank(player) if item_id(entry) == int(wanted_id))


def open_bank(profile):
    call_tool("deposit_inventory_items_XS", {"name": "__codex_open_bank_only__"}, profile)
    return observe(profile)


def route_to_bank_if_needed(player, profile, bank_target):
    if bool(player.get("inBankArea", False)):
        return player
    bridge.route_to(bank_target, profile=profile, reason="clean_bank_guams_bank")
    return observe(profile)


def close_interfaces(profile):
    call_tool("close_interfaces", {}, profile)
    return observe(profile)


def clean_withdrawn_guams(player, profile):
    cleaned = 0
    while count_inventory(player, GRIMY_GUAM) > 0:
        result = call_tool("use_inventory_item", {"itemId": GRIMY_GUAM}, profile)
        player = bridge.player_from(result)
        if count_inventory(player, GRIMY_GUAM) <= 0:
            cleaned += 1
            continue
        before = int(result.get("itemCountBefore", 0) or 0)
        after = int(result.get("itemCountAfter", before) or before)
        if after >= before:
            raise RuntimeError("Guam clean action made no progress.")
        cleaned += before - after
    return player, cleaned


def main():
    parser = argparse.ArgumentParser(description="Clean banked guams, leaving two grimy guams in the bank.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--bank-target", default="falador_west_bank")
    args = parser.parse_args()

    player = observe(args.profile)
    player = route_to_bank_if_needed(player, args.profile, args.bank_target)
    player = open_bank(args.profile)

    total_grimy = count_bank(player, GRIMY_GUAM)
    to_clean = max(0, total_grimy - KEEP_GRIMY_GUAMS)
    cleaned_total = 0

    while cleaned_total < to_clean:
        player = observe(args.profile)
        if count_inventory(player, GRIMY_GUAM) > 0:
            player = close_interfaces(args.profile)
            player, cleaned = clean_withdrawn_guams(player, args.profile)
            cleaned_total += cleaned
            player = open_bank(args.profile)
            if count_inventory(player, CLEAN_GUAM) > 0:
                result = call_tool("deposit_inventory_items_XS", {"itemId": CLEAN_GUAM}, args.profile)
                player = bridge.player_from(result)
            continue
        player = open_bank(args.profile)
        free_slots = int(player.get("freeInventorySlots", 0) or 0)
        if free_slots <= 0:
            raise RuntimeError("No inventory space available for guam cleaning.")
        withdraw_amount = min(to_clean - cleaned_total, free_slots)
        result = call_tool("withdraw_bank_items_XS", {"itemId": GRIMY_GUAM, "amount": withdraw_amount}, args.profile)
        player = bridge.player_from(result)

    player = open_bank(args.profile)
    print(json.dumps({
        "ok": True,
        "cleaned": cleaned_total,
        "bankGrimyGuamsRemaining": count_bank(player, GRIMY_GUAM),
        "bankCleanGuams": count_bank(player, CLEAN_GUAM),
        "player": {
            "tile": "{},{},{}".format(player.get("x"), player.get("y"), player.get("height")),
            "hp": player.get("hitpoints"),
            "maxHp": player.get("maxHitpoints"),
            "freeSlots": player.get("freeInventorySlots"),
            "inBankArea": bool(player.get("inBankArea", False)),
        },
    }, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
