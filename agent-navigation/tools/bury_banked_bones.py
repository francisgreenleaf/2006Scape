#!/usr/bin/env python3
"""Withdraw and bury every buryable bone stack from the bank."""

import argparse
import json

import bridge_script as bridge


KEEP_FOOD_COUNT = 1


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


def item_name(entry):
    return str(entry.get("name", "") or "")


def count_inventory(player, wanted_id):
    return sum(item_amount(entry) for entry in inventory(player) if item_id(entry) == int(wanted_id))


def open_bank(profile):
    call_tool("deposit_inventory_items_XS", {"name": "__codex_open_bank_only__"}, profile)
    return observe(profile)


def route_to_bank_if_needed(player, profile, bank_target):
    if bool(player.get("inBankArea", False)):
        return player
    bridge.route_to(bank_target, profile=profile, reason="bury_banked_bones_bank")
    return observe(profile)


def deposit_non_food(player, profile):
    carried = []
    for entry in inventory(player):
        if entry.get("foodHeal"):
            continue
        name = item_name(entry).lower()
        if "bones" in name:
            continue
        iid = item_id(entry)
        if iid >= 0:
            carried.append(iid)
    if carried:
        call_tool("deposit_inventory_items_XS", {"itemIds": sorted(set(carried))}, profile)
        player = observe(profile)
    return player


def first_bone_stack(player):
    for entry in bank(player):
        name = item_name(entry).lower()
        if "bones" in name:
            return entry
    return None


def bury_inventory_stack(player, profile, bone_id):
    buried = 0
    while count_inventory(player, bone_id) > 0:
        try:
            result = call_tool("bury_bones_XS", {"itemId": int(bone_id)}, profile)
            moved = int(result.get("buried", 0) or 0)
            if moved <= 0:
                raise RuntimeError("Could not bury inventory bones for itemId {}".format(bone_id))
            buried += moved
            player = observe(profile)
        except RuntimeError as exc:
            if "Could not bury" not in str(exc):
                raise
            call_tool("wait_ticks_XS", {"ticks": 2}, profile)
            player = observe(profile)
    return player, buried


def first_inventory_bone(player):
    for entry in inventory(player):
        if "bones" in item_name(entry).lower():
            return entry
    return None


def main():
    parser = argparse.ArgumentParser(description="Bury all banked bones while preserving one food.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--bank-target", default="falador_west_bank")
    args = parser.parse_args()

    total_buried = 0
    buried_by_item = {}
    player = observe(args.profile)
    player = route_to_bank_if_needed(player, args.profile, args.bank_target)
    player = open_bank(args.profile)
    while True:
        carried_bone = first_inventory_bone(player)
        if carried_bone is None:
            break
        player, buried = bury_inventory_stack(player, args.profile, item_id(carried_bone))
        total_buried += buried
        buried_by_item[str(item_id(carried_bone))] = buried_by_item.get(str(item_id(carried_bone)), 0) + buried
    player = deposit_non_food(player, args.profile)
    player = open_bank(args.profile)

    while True:
        player = open_bank(args.profile)
        stack = first_bone_stack(player)
        if stack is None:
            break
        free_slots = int(player.get("freeInventorySlots", 0) or 0)
        if free_slots <= 0:
            raise RuntimeError("Not enough free inventory slots to withdraw bones safely.")
        withdraw_amount = min(item_amount(stack), free_slots)
        call_tool("withdraw_bank_items_XS", {"itemId": item_id(stack), "amount": withdraw_amount}, args.profile)
        player = observe(args.profile)
        player, buried = bury_inventory_stack(player, args.profile, item_id(stack))
        total_buried += buried
        buried_by_item[str(item_id(stack))] = buried_by_item.get(str(item_id(stack)), 0) + buried

    print(json.dumps({
        "ok": True,
        "totalBuried": total_buried,
        "buriedByItemId": buried_by_item,
        "player": {
            "tile": "{},{},{}".format(player.get("x"), player.get("y"), player.get("height")),
            "hp": player.get("hitpoints"),
            "maxHp": player.get("maxHitpoints"),
            "food": sum(item_amount(entry) for entry in inventory(player) if entry.get("foodHeal")),
            "freeSlots": player.get("freeInventorySlots"),
            "inBankArea": bool(player.get("inBankArea", False)),
        },
    }, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
