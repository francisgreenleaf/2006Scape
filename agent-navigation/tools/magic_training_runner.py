#!/usr/bin/env python3
"""Primitive-backed Magic combat training runner."""

import argparse
import datetime as dt
import json
import uuid
from pathlib import Path

import bridge_script as bridge
from profile_utils import resolve_profile


RUNS_DIR = bridge.ROOT / "data" / "magic" / "runs"

AIR = 556
WATER = 555
EARTH = 557
FIRE = 554
MIND = 558
CHAOS = 562
DEATH = 560
LAW = 563
BLOOD = 565
STAFF_OF_AIR = 1381
SWORDFISH = 373
COINS = 995

SPELLS = [
    {"name": "Wind Strike", "spellId": 1152, "level": 1, "xp": 5, "runes": {MIND: 1}, "autocastButton": 7038},
    {"name": "Water Strike", "spellId": 1154, "level": 5, "xp": 7, "runes": {MIND: 1, WATER: 1}, "autocastButton": 7039},
    {"name": "Earth Strike", "spellId": 1156, "level": 9, "xp": 9, "runes": {MIND: 1, EARTH: 2}, "autocastButton": 7040},
    {"name": "Fire Strike", "spellId": 1158, "level": 13, "xp": 11, "runes": {MIND: 1, FIRE: 3}, "autocastButton": 7041},
    {"name": "Wind Bolt", "spellId": 1160, "level": 17, "xp": 13, "runes": {CHAOS: 1}, "autocastButton": 7042},
    {"name": "Water Bolt", "spellId": 1163, "level": 23, "xp": 16, "runes": {CHAOS: 1, WATER: 2}, "autocastButton": 7043},
    {"name": "Earth Bolt", "spellId": 1166, "level": 29, "xp": 20, "runes": {CHAOS: 1, EARTH: 3}, "autocastButton": 7044},
    {"name": "Fire Bolt", "spellId": 1169, "level": 35, "xp": 22, "runes": {CHAOS: 1, FIRE: 4}, "autocastButton": 7045},
    {"name": "Wind Blast", "spellId": 1172, "level": 41, "xp": 25, "runes": {DEATH: 1}, "autocastButton": 7046},
    {"name": "Water Blast", "spellId": 1175, "level": 47, "xp": 28, "runes": {DEATH: 1, WATER: 3}, "autocastButton": 7047},
    {"name": "Earth Blast", "spellId": 1177, "level": 53, "xp": 31, "runes": {DEATH: 1, EARTH: 4}, "autocastButton": 7048},
    {"name": "Fire Blast", "spellId": 1181, "level": 59, "xp": 35, "runes": {DEATH: 1, FIRE: 5}, "autocastButton": 7049},
    {"name": "Wind Wave", "spellId": 1183, "level": 62, "xp": 36, "runes": {BLOOD: 1}, "autocastButton": 7050},
    {"name": "Water Wave", "spellId": 1185, "level": 65, "xp": 37, "runes": {BLOOD: 1, WATER: 7}, "autocastButton": 7051},
    {"name": "Earth Wave", "spellId": 1188, "level": 70, "xp": 40, "runes": {BLOOD: 1, EARTH: 7}, "autocastButton": 7052},
    {"name": "Fire Wave", "spellId": 1189, "level": 75, "xp": 42, "runes": {BLOOD: 1, FIRE: 7}, "autocastButton": 7053},
]

RUNE_ITEM_IDS = [AIR, WATER, EARTH, FIRE, MIND, CHAOS, DEATH, LAW, BLOOD]
DEFAULT_WITHDRAW = {
    WATER: 1200,
    EARTH: 1200,
    FIRE: 1200,
    MIND: 300,
    CHAOS: 300,
    DEATH: 300,
    BLOOD: 300,
    LAW: 30,
}


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def hp(player):
    return int(player.get("hitpoints", player.get("hp", 0)) or 0)


def max_hp(player):
    return int(player.get("maxHitpoints", player.get("maxHp", hp(player))) or hp(player))


def in_combat(player):
    return bool(player.get("isInCombat") or player.get("inCombat"))


def magic_level(player):
    level = bridge.skill_level(player, "magic")
    if level > 0:
        return level
    return 1


def magic_xp(player):
    return bridge.skill_xp(player, "magic")


def inventory_counts(player):
    return bridge.inventory_counts(player)


def equipment_ids(player):
    ids = set()
    for item in bridge.equipment(player):
        item_id = int(item.get("id", item.get("itemId", -1)) or -1)
        if item_id >= 0:
            ids.add(item_id)
    return ids


def safe_magic_state(profile):
    try:
        return bridge.observe_full(profile=profile)
    except Exception:
        return bridge.observe_xs(profile=profile)


def write(handle, event, data):
    bridge.write_event(handle, event, data)


def has_staff(player):
    return STAFF_OF_AIR in equipment_ids(player)


def player_from_or_observe(result, profile, fallback=None):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return fallback or bridge.observe_xs(profile=profile)


def ensure_staff(player, profile, handle):
    if has_staff(player):
        return player
    inv = inventory_counts(player)
    if inv.get(STAFF_OF_AIR, 0) <= 0:
        if not bool(player.get("inBankArea", False)):
            raise RuntimeError("staff of air is not equipped and player is not at a bank")
        result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": STAFF_OF_AIR, "amount": 1}, profile=profile)
        player = player_from_or_observe(result, profile, player)
    result = bridge.call_tool("equip_item", {"itemId": STAFF_OF_AIR}, profile=profile)
    player = player_from_or_observe(result, profile, player)
    if not has_staff(player):
        raise RuntimeError("failed to equip staff of air")
    write(handle, "equip_staff", {"player": bridge.compact_player(player, ("magic",))})
    return player


def setup_bank_loadout(player, args, handle):
    if not bool(player.get("inBankArea", False)):
        return player
    player, summary = bridge.execute_bank_policy(
        player,
        profile=args.profile,
        handle=handle,
        reason="magic_setup",
        deposit_all_ids=[COINS],
        food_item_ids=[SWORDFISH],
        keep_food_count=args.food_count,
    )
    write(handle, "bank_policy_summary", summary)
    player = ensure_staff(player, args.profile, handle)

    inv = inventory_counts(player)
    for item_id, target in DEFAULT_WITHDRAW.items():
        carried = inv.get(item_id, 0)
        amount = max(0, int(target) - carried)
        if amount <= 0:
            continue
        result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": item_id, "amount": amount}, profile=args.profile)
        player = player_from_or_observe(result, args.profile, player)
        inv = inventory_counts(player)
        write(handle, "withdraw_runes", {
            "itemId": item_id,
            "requested": amount,
            "player": bridge.compact_player(player, ("magic",)),
        })

    carried_food = inventory_counts(player).get(SWORDFISH, 0)
    if carried_food < args.food_count:
        result = bridge.call_tool("withdraw_bank_items_XS", {
            "itemId": SWORDFISH,
            "amount": args.food_count - carried_food,
        }, profile=args.profile)
        player = player_from_or_observe(result, args.profile, player)
    return player


def choose_spell(player, args):
    counts = inventory_counts(player)
    level = magic_level(player)
    usable = []
    for spell in SPELLS:
        if level < spell["level"]:
            continue
        if any(counts.get(item_id, 0) < amount for item_id, amount in spell["runes"].items()):
            continue
        usable.append(spell)
    if not usable:
        return None
    if args.max_spell:
        allowed = {args.max_spell.lower(), args.max_spell.lower().replace("_", " ")}
        usable = [spell for spell in usable if spell["name"].lower() in allowed] or usable
    return usable[-1]


def remaining_casts(player, spell):
    counts = inventory_counts(player)
    possible = []
    for item_id, amount in spell["runes"].items():
        possible.append(counts.get(item_id, 0) // amount)
    return min(possible) if possible else 0


def ensure_autocast(spell, args, handle):
    button = spell.get("autocastButton")
    if not args.use_autocast or not button:
        return None
    result = bridge.call_tool("click_interface_button", {"buttonId": int(button)}, profile=args.profile)
    write(handle, "select_autocast", {
        "spell": spell["name"],
        "spellId": spell["spellId"],
        "buttonId": int(button),
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "autocasting": result.get("autocasting"),
        "autocastId": result.get("autocastId"),
        "selectedSpellId": result.get("spellId"),
    })
    if not result.get("success"):
        raise RuntimeError(result.get("message", "failed to select autocast spell"))
    return result


def maybe_eat(player, args, handle):
    if hp(player) > args.eat_at_hitpoints:
        return player
    result = bridge.call_tool("eat_best_food_XXS", {"emergency": hp(player) <= args.retreat_at_hitpoints}, profile=args.profile)
    player = player_from_or_observe(result, args.profile, player)
    write(handle, "eat", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(player, ("magic", "hitpoints")),
    })
    return player


def parse_item_ids(value):
    if not value:
        return []
    return [int(part.strip()) for part in str(value).split(",") if part.strip()]


def pickup_loot(player, args, handle):
    for item_id in args.loot_item_ids:
        try:
            result = bridge.call_tool("pickup_ground_item_XXS", {
                "itemId": int(item_id),
                "maxDistance": args.loot_distance,
            }, profile=args.profile)
        except RuntimeError as exc:
            if "No matching ground item found nearby" in str(exc):
                continue
            raise
        if result.get("success"):
            player = bridge.observe_xs(profile=args.profile)
            write(handle, "loot", {
                "itemId": int(item_id),
                "message": result.get("message"),
                "player": bridge.compact_player(player, ("magic", "hitpoints")),
            })
    return player


def find_target(args):
    query = {
        "name": args.npc,
        "maxDistance": args.npc_max_distance,
        "minHitpoints": args.min_npc_hitpoints,
        "maxNpcMaxHit": args.max_npc_max_hit,
        "reachable": True,
        "allowUnderAttack": args.allow_under_attack,
    }
    if not args.npc:
        query.pop("name")
    result = bridge.call_tool("find_training_npc", query, profile=args.profile)
    if not result.get("success") and not args.allow_under_attack:
        retry = dict(query)
        retry["allowUnderAttack"] = True
        result = bridge.call_tool("find_training_npc", retry, profile=args.profile)
    if not result.get("success"):
        raise RuntimeError(result.get("message", "no suitable Magic target found"))
    npc = result.get("npc") or {}
    if "npcIndex" not in npc:
        raise RuntimeError("target search did not return npcIndex")
    return npc


def training_round(player, args, handle, round_no):
    player = maybe_eat(player, args, handle)
    if hp(player) <= args.retreat_at_hitpoints and args.stop_when_unsafe:
        raise RuntimeError("hitpoints are unsafe and food did not recover enough")
    spell = choose_spell(player, args)
    if spell is None:
        return {"complete": True, "reason": "out_of_runes_or_level", "player": player}

    npc = find_target(args)
    before_xp = magic_xp(player)
    autocast = ensure_autocast(spell, args, handle)
    if args.use_autocast:
        cast = bridge.call_tool("attack_npc_XXS", {
            "npcIndex": int(npc["npcIndex"]),
        }, profile=args.profile)
    else:
        cast = bridge.call_tool("cast_spell_on_npc_XS", {
            "npcIndex": int(npc["npcIndex"]),
            "spellId": int(spell["spellId"]),
            "requireReachable": True,
        }, profile=args.profile)
    cast_player = player_from_or_observe(cast, args.profile, player)
    max_wait_ticks = max(args.cast_wait_ticks, args.autocast_wait_ticks) if args.use_autocast else args.cast_wait_ticks
    wait = bridge.call_tool("wait_until_combat_event_smart_XS", {
        "maxTicks": max_wait_ticks,
        "hpAtOrBelow": args.eat_at_hitpoints,
        "stopOnXpGain": not args.use_autocast,
        "stopOnTargetDead": True,
        "stopOnCombatEnd": True,
    }, profile=args.profile)
    player = player_from_or_observe(wait, args.profile, cast_player)
    cancel = None
    if not args.use_autocast and args.cancel_after_cast and in_combat(player):
        cancel = bridge.call_tool("cancel_current_action", {}, profile=args.profile)
        player = player_from_or_observe(cancel, args.profile, player)
    player = pickup_loot(player, args, handle)
    write(handle, "magic_round", {
        "round": round_no,
        "spell": spell["name"],
        "spellId": spell["spellId"],
        "castsRemaining": remaining_casts(player, spell),
        "npc": npc,
        "castSuccess": bool(cast.get("success")),
        "castMessage": cast.get("message"),
        "useAutocast": bool(args.use_autocast),
        "autocastSelected": bool(autocast and autocast.get("success")),
        "waitStatus": wait.get("batchStatus", wait.get("status")),
        "cancelAfterCast": bool(cancel),
        "cancelSuccess": bool(cancel and cancel.get("success")),
        "cancelMessage": cancel.get("message") if cancel else None,
        "xpEvents": wait.get("skillChanges", wait.get("xp")),
        "magicXpBefore": before_xp,
        "magicXpAfter": magic_xp(player),
        "player": bridge.compact_player(player, ("magic", "hitpoints")),
    })
    return {"complete": False, "player": player, "spell": spell}


def run(args):
    args.loot_item_ids = parse_item_ids(args.loot_item_ids)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    try:
        player = safe_magic_state(args.profile)
        write(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("magic", "hitpoints")),
        })
        if args.setup_bank:
            player = setup_bank_loadout(player, args, handle)
        else:
            player = ensure_staff(player, args.profile, handle)

        start_xp = magic_xp(player)
        start_level = magic_level(player)
        completed_reason = ""
        for round_no in range(1, args.max_rounds + 1):
            result = training_round(player, args, handle, round_no)
            player = result["player"]
            if result.get("complete"):
                completed_reason = result.get("reason", "complete")
                break
            if round_no % args.refresh_every == 0:
                player = safe_magic_state(args.profile)
            log("round {} spell={} magic={} xp={} hp={}/{}".format(
                round_no,
                result.get("spell", {}).get("name", "?"),
                magic_level(player),
                magic_xp(player),
                hp(player),
                max_hp(player),
            ), args)

        finish_player = safe_magic_state(args.profile)
        write(handle, "run_finish", {
            "reason": completed_reason or "max_rounds",
            "startMagicLevel": start_level,
            "finishMagicLevel": magic_level(finish_player),
            "startMagicXp": start_xp,
            "finishMagicXp": magic_xp(finish_player),
            "xpGained": max(0, magic_xp(finish_player) - start_xp),
            "player": bridge.compact_player(finish_player, ("magic", "hitpoints")),
        })
        log("magic log: {}".format(run_path), args)
        log("magic {} xp {} gained {}".format(
            magic_level(finish_player),
            magic_xp(finish_player),
            max(0, magic_xp(finish_player) - start_xp),
        ), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train Magic by casting combat spells on nearby safe NPCs.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--npc", default="goblin")
    parser.add_argument("--max-rounds", type=int, default=100)
    parser.add_argument("--npc-max-distance", type=int, default=25)
    parser.add_argument("--min-npc-hitpoints", type=int, default=1)
    parser.add_argument("--max-npc-max-hit", type=int, default=3)
    parser.add_argument("--allow-under-attack", action="store_true")
    parser.add_argument("--cast-wait-ticks", type=int, default=24)
    parser.add_argument("--eat-at-hitpoints", type=int, default=24)
    parser.add_argument("--retreat-at-hitpoints", type=int, default=14)
    parser.add_argument("--stop-when-unsafe", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--setup-bank", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--food-count", type=int, default=8)
    parser.add_argument("--max-spell", default="", help="Optional exact spell cap such as 'Wind Strike'.")
    parser.add_argument("--use-autocast", action=argparse.BooleanOptionalAction, default=True,
                        help="Select staff autocast and use normal NPC attack instead of manual cast clicks.")
    parser.add_argument("--autocast-wait-ticks", type=int, default=24)
    parser.add_argument("--cancel-after-cast", action=argparse.BooleanOptionalAction, default=True,
                        help="Cancel combat after each spell XP event so staff melee does not continue between casts.")
    parser.add_argument("--loot-item-ids", default="558,556,555,557,554,562,560,561,563,565",
                        help="Comma-separated useful rune item IDs to pick up after combat events.")
    parser.add_argument("--loot-distance", type=int, default=4)
    parser.add_argument("--refresh-every", type=int, default=10)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
