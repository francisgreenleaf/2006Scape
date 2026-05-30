#!/usr/bin/env python3
"""Normal-gameplay adamant armour upgrade trip for MrFlame."""

import argparse
import datetime as dt
import json
import os
import time
import uuid
from pathlib import Path

import bridge_script as bridge


ROOT = bridge.ROOT
RUNS_DIR = ROOT / "data" / "upgrade-trips" / "runs"

COINS = 995
LOBSTER = 379

STEEL_MED_HELM = 1141
MITHRIL_ARROW = 888
ADAMANT_ARROW = 890
STEEL_SWORD = 1281
IRON_LONGSWORD = 1293
MITHRIL_SCIMITAR = 1329

ADAMANT_CHAINBODY = 1111
ADAMANT_FULL_HELM = 1161
ADAMANT_PLATELEGS = 1073

SALE_ITEMS = (
    {"itemId": STEEL_MED_HELM, "amount": 17, "shop": "peksa", "target": "3077,3428,0"},
    {"itemId": STEEL_SWORD, "amount": 15, "shop": "sword", "target": "varrock_sword_shop"},
    {"itemId": IRON_LONGSWORD, "amount": 20, "shop": "sword", "target": "varrock_sword_shop"},
    # Varrock Swordshop does not stock scimitars on this server, so it will not buy them.
    {"itemId": MITHRIL_SCIMITAR, "amount": 1, "shop": "zeke", "target": "al_kharid_scimitar_shop"},
)

ARROW_SALES = (
    {"itemId": MITHRIL_ARROW, "amount": 186, "shop": "lowe", "target": "3233,3425,0"},
    {"itemId": ADAMANT_ARROW, "amount": 34, "shop": "lowe", "target": "3233,3425,0"},
)

PURCHASES = (
    {"itemId": ADAMANT_CHAINBODY, "amount": 1, "shop": "wayne", "target": "2971,3312,0"},
    {"itemId": ADAMANT_FULL_HELM, "amount": 1, "shop": "peksa", "target": "3077,3428,0"},
    {"itemId": ADAMANT_PLATELEGS, "amount": 1, "shop": "louie", "target": "al_kharid_legs_shop"},
)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_event(handle, event, data):
    record = {"event": event, "timestamp": utc_now()}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def log(args, message, force=False):
    if force or not args.quiet:
        print(message, flush=True)


def call_tool(name, args=None, profile=""):
    return bridge.call_tool(name, args or {}, profile=profile)


def observe(args):
    return bridge.observe(profile=args.profile)


def inventory(player):
    return player.get("inventory") or []


def equipment(player):
    return player.get("equipment") or []


def bank(player):
    return player.get("bank") or []


def count_items(items, item_id):
    total = 0
    for item in items or []:
        if int(item.get("id", item.get("itemId", -1)) or -1) == int(item_id):
            total += int(item.get("amount", 1) or 1)
    return total


def count_inventory(player, item_id):
    return count_items(inventory(player), item_id)


def count_bank(player, item_id):
    return count_items(bank(player), item_id)


def has_equipped(player, item_id):
    return count_items(equipment(player), item_id) > 0


def noted_item_id(item_id):
    return int(item_id) + 1


def compact_player(player):
    skills = player.get("skills") or {}
    return {
        "tile": "{},{},{}".format(player.get("x"), player.get("y"), player.get("height")),
        "hp": player.get("hitpoints"),
        "maxHp": player.get("maxHitpoints"),
        "runEnergy": player.get("runEnergy"),
        "inBankArea": bool(player.get("inBankArea", False)),
        "inventoryCoins": count_inventory(player, COINS),
        "bankCoins": count_bank(player, COINS),
        "food": sum(int(item.get("amount", 1) or 1) for item in inventory(player) if item.get("foodHeal")),
        "freeSlots": player.get("freeInventorySlots"),
        "levels": {
            "attack": (skills.get("attack") or {}).get("baseLevel"),
            "strength": (skills.get("strength") or {}).get("baseLevel"),
            "defence": (skills.get("defence") or {}).get("baseLevel"),
            "hitpoints": (skills.get("hitpoints") or {}).get("baseLevel"),
        },
        "equipment": [
            {"id": item.get("id"), "name": item.get("name"), "slotName": item.get("slotName")}
            for item in equipment(player)
        ],
    }


def close_interfaces(args, handle, reason):
    result = call_tool("close_interfaces", {}, profile=args.profile)
    player = result.get("player") or observe(args)
    write_event(handle, "close_interfaces", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return player


def route_to(target, args, handle, reason):
    player = close_interfaces(args, handle, "before_route_" + reason)
    write_event(handle, "route_start", {"reason": reason, "target": str(target), "player": compact_player(player)})
    bridge.route_to(
        str(target),
        profile=args.profile,
        handle=handle,
        reason=reason,
        extra_args={"runner_max_batches": args.route_max_batches, "max_batch_distance": args.max_batch_distance},
    )
    player = observe(args)
    write_event(handle, "route_finish", {"reason": reason, "target": str(target), "player": compact_player(player)})
    return player


def ensure_bank(args, handle, reason, target="falador_west_bank"):
    player = observe(args)
    if not bool(player.get("inBankArea", False)):
        player = route_to(target, args, handle, reason)
    return player


def open_bank(args, handle, reason):
    player = ensure_bank(args, handle, reason)
    result = call_tool("deposit_inventory_items", {"name": "__codex_open_bank_only__"}, profile=args.profile)
    player = result.get("player") or player
    write_event(handle, "open_bank", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return player


def set_withdraw_mode(args, handle, take_notes, reason):
    player = open_bank(args, handle, reason)
    button = 21010 if take_notes else 21011
    result = call_tool("click_interface_button", {"buttonId": button}, profile=args.profile)
    player = result.get("player") or player
    write_event(handle, "set_withdraw_mode", {
        "reason": reason,
        "takeNotes": take_notes,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    return player


def deposit_inventory_all(args, handle, reason):
    player = open_bank(args, handle, reason)
    item_ids = sorted({int(item.get("id", item.get("itemId", -1)) or -1) for item in inventory(player)})
    item_ids = [item_id for item_id in item_ids if item_id >= 0]
    if not item_ids:
        return player
    result = call_tool("deposit_inventory_items", {"itemIds": item_ids}, profile=args.profile)
    player = result.get("player") or observe(args)
    write_event(handle, "deposit_inventory_all", {
        "reason": reason,
        "itemIds": item_ids,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "depositedAmount": result.get("depositedAmount"),
        "player": compact_player(player),
    })
    return player


def withdraw_item(args, handle, item_id, amount, reason):
    player = set_withdraw_mode(args, handle, False, reason)
    before = count_inventory(player, item_id)
    result = call_tool("withdraw_bank_items", {"itemId": int(item_id), "amount": int(amount)}, profile=args.profile)
    player = observe(args)
    moved = max(0, count_inventory(player, item_id) - before)
    write_event(handle, "withdraw_item", {
        "reason": reason,
        "itemId": int(item_id),
        "requestedAmount": int(amount),
        "moved": moved,
        "toolSuccess": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    if moved < int(amount):
        raise RuntimeError("withdrew {} of {} item {}".format(moved, amount, item_id))
    return player


def withdraw_note(args, handle, item_id, amount, reason):
    player = set_withdraw_mode(args, handle, True, reason)
    note_id = noted_item_id(item_id)
    before_note = count_inventory(player, note_id)
    before_normal = count_inventory(player, item_id)
    result = call_tool("withdraw_bank_items", {"itemId": int(item_id), "amount": int(amount)}, profile=args.profile)
    player = observe(args)
    moved_note = max(0, count_inventory(player, note_id) - before_note)
    moved_normal = max(0, count_inventory(player, item_id) - before_normal)
    moved = moved_note + moved_normal
    write_event(handle, "withdraw_note", {
        "reason": reason,
        "itemId": int(item_id),
        "noteId": note_id,
        "requestedAmount": int(amount),
        "moved": moved,
        "movedNote": moved_note,
        "movedNormal": moved_normal,
        "toolSuccess": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    if moved < int(amount):
        raise RuntimeError("withdrew {} of {} noted item {}".format(moved, amount, item_id))
    return player


def prepare_inventory(args, handle):
    player = ensure_bank(args, handle, "initial_bank")
    player = deposit_inventory_all(args, handle, "initial_bank_all")
    player = observe(args)
    write_event(handle, "pre_withdraw_bank_counts", {
        "player": compact_player(player),
        "counts": {
            "coins": count_bank(player, COINS),
            "steelMedHelm": count_bank(player, STEEL_MED_HELM),
            "steelSword": count_bank(player, STEEL_SWORD),
            "ironLongsword": count_bank(player, IRON_LONGSWORD),
            "mithrilScimitar": count_bank(player, MITHRIL_SCIMITAR),
            "mithrilArrow": count_bank(player, MITHRIL_ARROW),
            "adamantArrow": count_bank(player, ADAMANT_ARROW),
        },
    })
    bank_coins = count_bank(player, COINS)
    if bank_coins <= 0:
        raise RuntimeError("no bank coins available for upgrade trip")
    player = withdraw_item(args, handle, COINS, bank_coins, "all_upgrade_coins")
    player = withdraw_item(args, handle, LOBSTER, int(args.food), "travel_food")
    for item in SALE_ITEMS:
        player = withdraw_note(args, handle, item["itemId"], item["amount"], "sale_stock")
    player = set_withdraw_mode(args, handle, False, "restore_item_withdraw_mode")
    player = close_interfaces(args, handle, "after_prepare_inventory")
    return player


def open_shop(target, shop_name, args, handle, reason):
    player = route_to(target, args, handle, reason + "_route")
    result = call_tool("open_nearest_shop", {"name": shop_name, "maxDistance": int(args.shop_max_distance)}, profile=args.profile)
    player = result.get("player") or observe(args)
    write_event(handle, "open_shop", {
        "reason": reason,
        "shopName": shop_name,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "player": compact_player(player),
    })
    if not result.get("success"):
        raise RuntimeError("could not open shop {} near {}".format(shop_name, target))
    return player


def sell_item(args, handle, item):
    player = open_shop(item["target"], item["shop"], args, handle, "sell_{}".format(item["itemId"]))
    before_coins = count_inventory(player, COINS)
    result = call_tool("sell_inventory_items", {
        "itemIds": [int(item["itemId"]), noted_item_id(item["itemId"])],
        "amount": int(item["amount"]),
    }, profile=args.profile)
    player = result.get("player") or observe(args)
    sold = int(result.get("sold", 0) or 0)
    coins = max(0, count_inventory(player, COINS) - before_coins)
    write_event(handle, "sell_item", {
        "itemId": int(item["itemId"]),
        "requestedAmount": int(item["amount"]),
        "sold": sold,
        "coinsReceived": result.get("coinsReceived", coins),
        "toolSuccess": bool(result.get("success")),
        "message": result.get("message"),
        "soldItems": result.get("soldItems", []),
        "player": compact_player(player),
    })
    if sold < int(item["amount"]):
        raise RuntimeError("sold {} of {} item {}".format(sold, item["amount"], item["itemId"]))
    return player


def buy_item(args, handle, item):
    player = open_shop(item["target"], item["shop"], args, handle, "buy_{}".format(item["itemId"]))
    result = call_tool("buy_shop_item", {"itemId": int(item["itemId"]), "amount": int(item["amount"])}, profile=args.profile)
    player = result.get("player") or observe(args)
    bought = int(result.get("bought", 0) or 0)
    write_event(handle, "buy_item", {
        "itemId": int(item["itemId"]),
        "requestedAmount": int(item["amount"]),
        "bought": bought,
        "toolSuccess": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    if bought < int(item["amount"]) and count_inventory(player, item["itemId"]) < int(item["amount"]):
        raise RuntimeError("bought {} of {} item {}".format(bought, item["amount"], item["itemId"]))
    return player


def equip_upgrade(args, handle, item_id):
    player = close_interfaces(args, handle, "before_equip_{}".format(item_id))
    if has_equipped(player, item_id):
        return player
    result = call_tool("equip_item", {"itemId": int(item_id)}, profile=args.profile)
    player = result.get("player") or observe(args)
    write_event(handle, "equip_upgrade", {
        "itemId": int(item_id),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact_player(player),
    })
    if not has_equipped(player, item_id):
        raise RuntimeError("item {} was not equipped".format(item_id))
    return player


def maybe_sell_arrows(args, handle):
    player = observe(args)
    needed_for_remaining = 0
    for item in PURCHASES:
        if not has_equipped(player, item["itemId"]) and count_inventory(player, item["itemId"]) <= 0:
            if item["itemId"] == ADAMANT_CHAINBODY:
                needed_for_remaining += 4800
            elif item["itemId"] == ADAMANT_FULL_HELM:
                needed_for_remaining += 3520
            elif item["itemId"] == ADAMANT_PLATELEGS:
                needed_for_remaining += 6400
    if count_inventory(player, COINS) >= needed_for_remaining:
        write_event(handle, "arrow_sales_skipped", {
            "reason": "non_arrow_sales_afford_upgrades",
            "neededForRemaining": needed_for_remaining,
            "player": compact_player(player),
        })
        return player
    if not args.allow_arrow_fallback:
        raise RuntimeError("non-arrow sales did not leave enough coins, and arrow fallback is disabled")
    write_event(handle, "arrow_sales_needed", {"neededForRemaining": needed_for_remaining, "player": compact_player(player)})
    player = ensure_bank(args, handle, "arrow_fallback_bank", target="varrock_west_bank")
    for item in ARROW_SALES:
        player = withdraw_note(args, handle, item["itemId"], item["amount"], "arrow_fallback")
    player = close_interfaces(args, handle, "after_arrow_withdraw")
    for item in ARROW_SALES:
        player = sell_item(args, handle, item)
    return player


def final_bank_and_verify(args, handle):
    player = route_to(args.final_bank, args, handle, "final_bank")
    player = deposit_inventory_all(args, handle, "final_bank_inventory")
    player = set_withdraw_mode(args, handle, False, "final_restore_item_mode")
    player = close_interfaces(args, handle, "final_close_bank")
    player = observe(args)
    result = {
        "player": compact_player(player),
        "bankCounts": {
            "coins": count_bank(player, COINS),
            "mithrilArrow": count_bank(player, MITHRIL_ARROW),
            "adamantArrow": count_bank(player, ADAMANT_ARROW),
            "steelMedHelm": count_bank(player, STEEL_MED_HELM),
            "steelSword": count_bank(player, STEEL_SWORD),
            "ironLongsword": count_bank(player, IRON_LONGSWORD),
            "mithrilScimitar": count_bank(player, MITHRIL_SCIMITAR),
        },
        "equipped": {
            "adamantChainbody": has_equipped(player, ADAMANT_CHAINBODY),
            "adamantFullHelm": has_equipped(player, ADAMANT_FULL_HELM),
            "adamantPlatelegs": has_equipped(player, ADAMANT_PLATELEGS),
        },
    }
    write_event(handle, "final_verify", result)
    missing = [name for name, present in result["equipped"].items() if not present]
    if missing:
        raise RuntimeError("missing equipped upgrades: {}".format(", ".join(missing)))
    return result


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-addy-upgrade-trip-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    with run_path.open("a", encoding="utf-8") as handle:
        try:
            write_event(handle, "run_start", {"args": vars(args), "runLog": str(run_path)})
            player = prepare_inventory(args, handle)
            log(args, "prepared upgrade inventory", force=True)
            # Buy the nearby chainbody before leaving Falador, then do the sales.
            player = buy_item(args, handle, PURCHASES[0])
            for item in SALE_ITEMS:
                player = sell_item(args, handle, item)
                if int(item["itemId"]) == STEEL_MED_HELM:
                    player = buy_item(args, handle, PURCHASES[1])
            player = maybe_sell_arrows(args, handle)
            player = buy_item(args, handle, PURCHASES[2])
            for item_id in (ADAMANT_CHAINBODY, ADAMANT_FULL_HELM, ADAMANT_PLATELEGS):
                player = equip_upgrade(args, handle, item_id)
            result = final_bank_and_verify(args, handle)
            write_event(handle, "run_finish", {"success": True, "result": result, "runLog": str(run_path)})
            print(json.dumps({"ok": True, "runLog": str(run_path), "result": result}, sort_keys=True))
            return 0
        except Exception as exc:
            player = {}
            try:
                player = compact_player(observe(args))
            except Exception:
                pass
            write_event(handle, "run_error", {
                "success": False,
                "error": str(exc),
                "player": player,
                "runLog": str(run_path),
            })
            print(json.dumps({"ok": False, "error": str(exc), "runLog": str(run_path), "player": player}, sort_keys=True))
            return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sell surplus gear and buy adamant armour upgrades.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE", "MrFlame"))
    parser.add_argument("--food", type=int, default=2)
    parser.add_argument("--shop-max-distance", type=int, default=12)
    parser.add_argument("--route-max-batches", type=int, default=24)
    parser.add_argument("--max-batch-distance", type=int, default=48)
    parser.add_argument("--final-bank", default="al_kharid_bank")
    parser.add_argument("--allow-arrow-fallback", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
