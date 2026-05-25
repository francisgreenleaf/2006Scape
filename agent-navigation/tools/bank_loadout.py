#!/usr/bin/env python3
"""Apply compact primitive-backed bank loadout policies."""

import argparse
import json
import os

import bridge_script as bridge


COWHIDE = 1739
IRON_SCIMITAR = 1323
KEBAB = 1971


def parse_item_ids(values):
    ids = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                ids.append(int(part))
    return ids


def unique(values):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def build_policy(args):
    deposit_ids = parse_item_ids(args.deposit_item_id)
    food_ids = parse_item_ids(args.food_item_id)
    keep_food_count = args.keep_food_count
    coin_float = args.coin_float

    if args.preset == "cowhide-trip":
        deposit_ids.extend([COWHIDE, IRON_SCIMITAR])
        if not food_ids:
            food_ids = [KEBAB]
        if keep_food_count is None:
            keep_food_count = 3
        if coin_float is None:
            coin_float = 100

    return {
        "depositAllIds": unique(deposit_ids),
        "foodItemIds": unique(food_ids),
        "keepFoodCount": keep_food_count,
        "coinFloat": coin_float,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply a state-derived bank loadout with bridge primitives.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE", ""))
    parser.add_argument("--preset", choices=("custom", "cowhide-trip"), default="custom")
    parser.add_argument("--deposit-item-id", action="append",
                        help="Inventory item id to deposit if carried. May be repeated or comma-separated.")
    parser.add_argument("--food-item-id", action="append",
                        help="Food item id to trim with --keep-food-count. May be repeated or comma-separated.")
    parser.add_argument("--keep-food-count", type=int,
                        help="Keep this many matching food items, depositing excess in one primitive call.")
    parser.add_argument("--coin-float", type=int,
                        help="Carry exactly this many coins when bank coins are available.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Observe and print the planned primitive actions without changing bank state.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    player = bridge.observe(profile=args.profile)
    policy = build_policy(args)
    plan = bridge.bank_policy_plan(
        player,
        deposit_all_ids=policy["depositAllIds"],
        food_item_ids=policy["foodItemIds"],
        keep_food_count=policy["keepFoodCount"],
        coin_float=policy["coinFloat"],
    )
    output = {
        "success": True,
        "preset": args.preset,
        "dryRun": bool(args.dry_run),
        "policy": policy,
        "plan": plan,
        "player": bridge.compact_player(player),
    }

    if not bool(player.get("inBankArea", False)):
        output["success"] = False
        output["message"] = "Player must already be in a bank area before applying a bank loadout."
    elif not args.dry_run:
        updated, summary = bridge.execute_bank_policy(
            player,
            profile=args.profile,
            reason="bank_loadout_{}".format(args.preset),
            deposit_all_ids=policy["depositAllIds"],
            food_item_ids=policy["foodItemIds"],
            keep_food_count=policy["keepFoodCount"],
            coin_float=policy["coinFloat"],
        )
        output["summary"] = summary
        output["player"] = bridge.compact_player(updated)
        output["message"] = "Applied {} bank policy action{}.".format(
            len(summary["actions"]),
            "" if len(summary["actions"]) == 1 else "s",
        )
    else:
        output["message"] = "Planned {} bank policy action{}.".format(
            len(plan["actions"]),
            "" if len(plan["actions"]) == 1 else "s",
        )

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(output["message"])
        if output["success"]:
            for action in plan["actions"]:
                print("- {tool}: {arguments}".format(
                    tool=action["tool"],
                    arguments=json.dumps(action["arguments"], sort_keys=True),
                ))
    return 0 if output["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
