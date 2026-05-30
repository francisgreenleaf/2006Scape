#!/usr/bin/env python3
"""Primitive-backed low-level thieving runner."""

import argparse
import datetime as dt
import uuid

import bridge_script as bridge


RUNS_DIR = bridge.ROOT / "data" / "thieving" / "runs"

COINS = 995

DRAYNOR_BANK = "draynor bank"
DRAYNOR_MARKET_PROBE = "3079,3246,0"

THIEVING_TARGETS = (
    {
        "name": "farmer",
        "level": 10,
        "npcIds": [7, 1757],
        "routeTarget": DRAYNOR_BANK,
        "maxDistance": 24,
    },
    {
        "name": "man",
        "level": 1,
        "npcIds": [1, 2, 3, 4, 5, 6, 3222],
        "routeTarget": DRAYNOR_MARKET_PROBE,
        "maxDistance": 28,
    },
)

FOOD_PREFERENCE = (373, 379, 361, 333, 385, 1969)


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def carried_count(player, item_id):
    return bridge.count_inventory_item(player, item_id)


def bank_count(player, item_id):
    return bridge.count_bank_item(player, item_id)


def current_hp(player):
    return int(player.get("hitpoints", player.get("hp", 0)) or 0)


def food_count(player):
    return sum(1 for item in bridge.inventory(player) if item.get("foodHeal"))


def choose_banked_food(player):
    bank_counts = bridge.bank_counts(player)
    for item_id in FOOD_PREFERENCE:
        if bank_counts.get(int(item_id), 0) > 0:
            return int(item_id)
    return 0


def ensure_bank_area(player, profile, handle, reason):
    if bool(player.get("inBankArea", False)):
        return bridge.observe(profile)
    bridge.route_to(DRAYNOR_BANK, profile=profile, handle=handle, reason=reason)
    return bridge.observe(profile)


def deposit_non_food(player, profile, handle, reason):
    keep = set()
    for item in bridge.inventory(player):
        if item.get("foodHeal"):
            keep.add(int(item.get("id", item.get("itemId", -1)) or -1))
    deposit_ids = []
    seen = set()
    for item in bridge.inventory(player):
        item_id = int(item.get("id", item.get("itemId", -1)) or -1)
        if item_id < 0 or item_id in keep or item_id in seen:
            continue
        seen.add(item_id)
        deposit_ids.append(item_id)
    if not deposit_ids:
        return player
    result = bridge.call_tool("deposit_inventory_items", {"itemIds": deposit_ids}, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "deposit_non_food", {
        "reason": reason,
        "itemIds": deposit_ids,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("thieving",)),
    })
    return bridge.observe(profile)


def restock_food(player, profile, handle, args, reason):
    player = ensure_bank_area(player, profile, handle, reason + "_bank")
    player = deposit_non_food(player, profile, handle, reason + "_cleanup")
    food_id = choose_banked_food(player)
    if food_id <= 0:
        raise RuntimeError("no banked food available for thieving recovery")
    if food_count(player) >= int(args.food_count):
        return player
    result = bridge.call_tool("withdraw_bank_items", {
        "itemId": food_id,
        "amount": int(args.food_count - food_count(player)),
    }, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "withdraw_food", {
        "reason": reason,
        "foodId": food_id,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(updated, ("thieving",)),
    })
    return bridge.observe(profile)


def choose_target(player):
    level = bridge.skill_level(player, "thieving")
    chosen = THIEVING_TARGETS[-1]
    for target in THIEVING_TARGETS:
        if level >= int(target["level"]):
            chosen = target
    return chosen


def route_to_thieving_area(player, profile, handle, target):
    bridge.route_to(target["routeTarget"], profile=profile, handle=handle, reason="thieving_area_" + target["name"])
    return bridge.observe(profile)


def ensure_food(player, profile, handle, args):
    if food_count(player) > 0:
        return player
    return restock_food(player, profile, handle, args, "restock_food")


def eat_if_needed(player, profile, handle, args, force=False):
    hp = current_hp(player)
    if not force and hp > int(args.eat_at_hp):
        return player
    if food_count(player) <= 0:
        return player
    result = bridge.call_tool("eat_best_food", {}, profile=profile)
    updated = bridge._player_from_or(result, player)
    bridge.write_event(handle, "eat_food", {
        "force": bool(force),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "beforeHp": hp,
        "afterHp": current_hp(updated),
        "player": bridge.compact_player(updated, ("thieving",)),
    })
    return bridge.observe(profile)


def need_bank(player, args):
    if food_count(player) <= 0 and current_hp(player) <= int(args.stop_at_hp):
        return True
    return int(player.get("freeInventorySlots", 0) or 0) < int(args.min_free_slots)


def find_target(player, profile, handle, target):
    result = bridge.call_tool("find_nearest_npc", {
        "npcIds": target["npcIds"],
        "maxDistance": int(target["maxDistance"]),
        "reachable": True,
    }, profile=profile)
    bridge.write_event(handle, "find_target", {
        "target": target["name"],
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "npc": result.get("npc"),
        "player": bridge.compact_player(player, ("thieving",)),
    })
    if not result.get("success"):
        return None
    return result.get("npc") or None


def pickpocket_once(player, profile, handle, args):
    target = choose_target(player)
    npc = find_target(player, profile, handle, target)
    if npc is None:
        player = route_to_thieving_area(player, profile, handle, target)
        npc = find_target(player, profile, handle, target)
        if npc is None:
            raise RuntimeError("no {} target found near {}".format(target["name"], target["routeTarget"]))

    before_xp = bridge.skill_xp(player, "thieving")
    before_hp = current_hp(player)
    interact = bridge.call_tool("interact_npc", {
        "npcIndex": npc.get("npcIndex", npc.get("index")),
        "option": "second",
        "requireReachable": True,
    }, profile=profile)
    updated = bridge._player_from_or(interact, player)
    if interact.get("approaching"):
        wait = bridge.call_tool("wait_until_idle", {"maxTicks": 30, "movement": True, "combat": False}, profile=profile)
        updated = bridge.player_from(wait)
        interact = bridge.call_tool("interact_npc", {
            "npcIndex": npc.get("npcIndex", npc.get("index")),
            "option": "second",
            "requireReachable": True,
        }, profile=profile)
        updated = bridge._player_from_or(interact, updated)
    bridge.call_tool("wait_ticks", {"ticks": 4}, profile=profile)
    updated = bridge.observe(profile)
    after_xp = bridge.skill_xp(updated, "thieving")
    after_hp = current_hp(updated)
    success = after_xp > before_xp
    bridge.write_event(handle, "pickpocket_attempt", {
        "target": target["name"],
        "npc": npc,
        "success": success,
        "beforeXp": before_xp,
        "afterXp": after_xp,
        "beforeHp": before_hp,
        "afterHp": after_hp,
        "player": bridge.compact_player(updated, ("thieving",)),
    })
    return updated, success


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = bridge.observe(profile)
        player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason="thieving_runner")
        bridge.write_event(handle, "run_start", {"args": vars(args), "player": bridge.compact_player(player, ("thieving",))})
        player = ensure_food(player, profile, handle, args)
        player = route_to_thieving_area(player, profile, handle, choose_target(player))

        attempts = 0
        while bridge.skill_level(player, "thieving") < int(args.target_thieving_level):
            if int(args.max_attempts) > 0 and attempts >= int(args.max_attempts):
                raise RuntimeError("reached attempt cap before target thieving level")
            if current_hp(player) <= int(args.eat_at_hp):
                player = eat_if_needed(player, profile, handle, args)
            if need_bank(player, args):
                player = restock_food(player, profile, handle, args, "loop_restock")
                player = route_to_thieving_area(player, profile, handle, choose_target(player))
            player, _success = pickpocket_once(player, profile, handle, args)
            if current_hp(player) <= int(args.stop_at_hp) and food_count(player) <= 0:
                player = restock_food(player, profile, handle, args, "safety_restock")
                player = route_to_thieving_area(player, profile, handle, choose_target(player))
            attempts += 1

        player = ensure_bank_area(player, profile, handle, "finish_bank")
        player = deposit_non_food(player, profile, handle, "finish_deposit")
        bridge.write_event(handle, "run_finish", {"attempts": attempts, "player": bridge.compact_player(player, ("thieving",))})
        if handle is not None:
            log("thieving log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run low-level pickpocket thieving with food and bank recovery.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--target-thieving-level", type=int, default=20)
    parser.add_argument("--food-count", type=int, default=8)
    parser.add_argument("--eat-at-hp", type=int, default=42)
    parser.add_argument("--stop-at-hp", type=int, default=36)
    parser.add_argument("--min-free-slots", type=int, default=2)
    parser.add_argument("--max-attempts", type=int, default=1500)
    parser.add_argument("--min-run-energy", type=int, default=8)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
