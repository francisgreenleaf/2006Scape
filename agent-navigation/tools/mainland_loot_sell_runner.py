#!/usr/bin/env python3
"""Sell mainland-friendly loot to the best nearby shop categories."""

import argparse
import datetime as dt
import json
import uuid
from pathlib import Path

import bridge_script as bridge


ROOT = bridge.ROOT
RUNS_DIR = ROOT / "data" / "sell-trips" / "runs"

COINS = 995
LOBSTER = 379

ADAMANT_SWORD = 1288
MITHRIL_SWORD = 1286
IRON_LONGSWORD = 1294
STEEL_SWORD = 1282
MAGIC_STAFF = 1390
BLACK_FULL_HELM = 1166
STEEL_MED_HELM = 1142
BLACK_SQ_SHIELD = 1180
IRON_SQ_SHIELD = 1176
MITHRIL_SPEAR = 1244

SALE_GROUPS = (
    {
        "label": "shields",
        "attempts": (
            {"target": "falador_shield_shop", "shop": "shield"},
            {"target": "falador_shield_shop", "shop": "cassie"},
        ),
        "itemIds": (BLACK_SQ_SHIELD, IRON_SQ_SHIELD),
    },
    {
        "label": "helms",
        "attempts": (
            {"target": "3077,3428,0", "shop": "peksa"},
            {"target": "3077,3428,0", "shop": "helmet"},
        ),
        "itemIds": (BLACK_FULL_HELM, STEEL_MED_HELM),
    },
    {
        "label": "swords",
        "attempts": (
            {"target": "varrock_sword_shop", "shop": "sword"},
        ),
        "itemIds": (ADAMANT_SWORD, MITHRIL_SWORD, IRON_LONGSWORD, STEEL_SWORD),
    },
    {
        "label": "staves",
        "attempts": (
            {"target": "varrock_square", "shop": "zaff"},
            {"target": "varrock_square", "shop": "staff"},
            {"target": "varrock_general_store", "shop": "general"},
        ),
        "itemIds": (MAGIC_STAFF,),
    },
    {
        "label": "spears",
        "attempts": (
            {"target": "varrock_general_store", "shop": "general"},
        ),
        "itemIds": (MITHRIL_SPEAR,),
    },
    {
        "label": "general_cleanup",
        "attempts": (
            {"target": "varrock_general_store", "shop": "general"},
        ),
        "itemIds": (
            BLACK_SQ_SHIELD,
            BLACK_FULL_HELM,
            STEEL_MED_HELM,
            ADAMANT_SWORD,
            MITHRIL_SWORD,
            IRON_LONGSWORD,
            STEEL_SWORD,
            MAGIC_STAFF,
            MITHRIL_SPEAR,
        ),
    },
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
    return bridge.observe(args.profile)


def inventory(player):
    return player.get("inventory") or []


def count_items(items, item_id):
    total = 0
    for item in items or []:
        if int(item.get("id", item.get("itemId", -1)) or -1) == int(item_id):
            total += int(item.get("amount", 1) or 1)
    return total


def count_inventory(player, item_id):
    return count_items(inventory(player), item_id)


def compact_player(player):
    tile = player.get("tile")
    return {
        "tile": tile if tile else "{},{},{}".format(player.get("x"), player.get("y"), player.get("height")),
        "hp": player.get("hitpoints"),
        "maxHp": player.get("maxHitpoints"),
        "runEnergy": player.get("runEnergy"),
        "runEnabled": bool(player.get("runEnabled", False)),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "inBankArea": bool(player.get("inBankArea", False)),
        "inventoryCoins": count_inventory(player, COINS),
        "inventoryFood": sum(int(item.get("amount", 1) or 1) for item in inventory(player) if item.get("foodHeal")),
        "freeSlots": player.get("freeInventorySlots"),
    }


def noted_item_id(item_id):
    return int(item_id) + 1


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
    player = bridge.ensure_run(player, int(args.min_run_energy), profile=args.profile, handle=handle, reason=reason)
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


def open_shop(args, handle, label, attempts):
    last_error = "no attempts made"
    for index, attempt in enumerate(attempts, start=1):
        player = route_to(attempt["target"], args, handle, "{}_{}_route".format(label, index))
        result = call_tool("open_nearest_shop", {
            "name": attempt["shop"],
            "maxDistance": int(args.shop_max_distance),
        }, profile=args.profile)
        player = result.get("player") or observe(args)
        write_event(handle, "open_shop", {
            "label": label,
            "attempt": index,
            "target": attempt["target"],
            "shopName": attempt["shop"],
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "npc": result.get("npc"),
            "player": compact_player(player),
        })
        if result.get("success"):
            return player, attempt
        last_error = result.get("message") or "open_nearest_shop failed"
    raise RuntimeError("could not open shop for {}: {}".format(label, last_error))


def sell_item(args, handle, player, item_id, amount, label, shop_name):
    if amount <= 0:
        return player, 0, 0
    before_coins = count_inventory(player, COINS)
    try:
        result = call_tool("sell_inventory_items", {
            "itemIds": [int(item_id), noted_item_id(item_id)],
            "amount": int(amount),
        }, profile=args.profile)
        player = result.get("player") or observe(args)
    except RuntimeError as exc:
        player = observe(args)
        result = {
            "success": False,
            "message": str(exc),
            "sold": 0,
            "coinsReceived": 0,
            "soldItems": [],
            "player": player,
        }
    sold = int(result.get("sold", 0) or 0)
    coins_received = int(result.get("coinsReceived", 0) or 0)
    if coins_received <= 0:
        coins_received = max(0, count_inventory(player, COINS) - before_coins)
    write_event(handle, "sell_item", {
        "label": label,
        "shopName": shop_name,
        "itemId": int(item_id),
        "requestedAmount": int(amount),
        "sold": sold,
        "coinsReceived": coins_received,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "soldItems": result.get("soldItems", []),
        "player": compact_player(player),
    })
    return player, sold, coins_received


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sell mainland-friendly loot to specialist shops where practical.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--shop-max-distance", type=int, default=14)
    parser.add_argument("--route-max-batches", type=int, default=90)
    parser.add_argument("--max-batch-distance", type=int, default=48)
    parser.add_argument("--min-run-energy", type=int, default=15)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args(argv)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-mainland-sell-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = run_path.open("a", encoding="utf-8")

    total_sold = 0
    total_coins = 0
    try:
        player = observe(args)
        write_event(handle, "run_start", {"args": vars(args), "player": compact_player(player), "runLog": str(run_path)})
        for group in SALE_GROUPS:
            pending = []
            for item_id in group["itemIds"]:
                amount = count_inventory(player, item_id)
                if amount > 0:
                    pending.append({"itemId": item_id, "amount": amount})
            if not pending:
                write_event(handle, "skip_group", {"label": group["label"], "reason": "no_items", "player": compact_player(player)})
                continue
            player, used_attempt = open_shop(args, handle, group["label"], group["attempts"])
            group_sold = 0
            group_coins = 0
            for entry in pending:
                player, sold, coins = sell_item(
                    args,
                    handle,
                    player,
                    entry["itemId"],
                    entry["amount"],
                    group["label"],
                    used_attempt["shop"],
                )
                group_sold += sold
                group_coins += coins
                total_sold += sold
                total_coins += coins
            write_event(handle, "group_finish", {
                "label": group["label"],
                "shopName": used_attempt["shop"],
                "target": used_attempt["target"],
                "sold": group_sold,
                "coinsReceived": group_coins,
                "player": compact_player(player),
            })
            log(args, "{} sold {} items for {} coins".format(group["label"], group_sold, group_coins))
            player = close_interfaces(args, handle, "after_" + group["label"])

        remaining = [
            {"id": int(item.get("id", item.get("itemId", -1)) or -1), "name": item.get("name"), "amount": int(item.get("amount", 1) or 1)}
            for item in inventory(player)
            if int(item.get("id", item.get("itemId", -1)) or -1) not in (LOBSTER, COINS)
        ]
        write_event(handle, "run_finish", {
            "sold": total_sold,
            "coinsReceived": total_coins,
            "remainingNonFoodItems": remaining,
            "player": compact_player(player),
            "runLog": str(run_path),
        })
        log(args, "mainland sell log: {}".format(run_path), force=True)
        print(json.dumps({
            "ok": True,
            "sold": total_sold,
            "coinsReceived": total_coins,
            "remainingNonFoodItems": remaining,
            "runLog": str(run_path),
            "player": compact_player(player),
        }, sort_keys=True))
        return 0
    finally:
        handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
