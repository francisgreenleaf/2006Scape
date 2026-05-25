#!/usr/bin/env python3
"""Primitive-backed combat training runner."""

import argparse
import datetime as dt
import uuid

import bridge_script as bridge


RUNS_DIR = bridge.ROOT / "data" / "combat" / "runs"


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def combat_level(player, skill):
    return bridge.skill_level(player, skill)


def choose_style(player, target_level, fixed_style):
    if fixed_style:
        return fixed_style
    attack = combat_level(player, "attack")
    strength = combat_level(player, "strength")
    defence = combat_level(player, "defence")
    if attack < target_level and attack <= strength and attack <= defence:
        return "attack"
    if strength < target_level and strength <= attack + 5:
        return "strength"
    if defence < target_level:
        return "defence"
    if attack < target_level:
        return "attack"
    if strength < target_level:
        return "strength"
    return "complete"


def hp(player):
    return int(player.get("hitpoints", player.get("hp", 0)) or 0)


def max_hp(player):
    return int(player.get("maxHitpoints", player.get("maxHp", hp(player))) or hp(player))


def safe_eat(player, profile, args, handle):
    if hp(player) > args.eat_at_hitpoints:
        return player
    result = bridge.call_tool("eat_best_food", {"emergency": hp(player) <= args.retreat_at_hitpoints}, profile=profile)
    next_player = bridge.player_from(result)
    bridge.write_event(handle, "eat", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": bridge.compact_player(next_player, ("attack", "strength", "defence", "hitpoints")),
    })
    return next_player


def pickup_loot(profile, args, handle):
    if not args.loot_item_ids:
        return bridge.observe(profile)
    player = bridge.observe(profile)
    nearby = player.get("nearbyGroundItems") or []
    wanted = {int(item_id) for item_id in args.loot_item_ids}
    for item in nearby:
        item_id = int(item.get("id", item.get("itemId", -1)) or -1)
        if item_id not in wanted or int(item.get("distance", 999) or 999) > args.loot_distance:
            continue
        result = bridge.call_tool("pickup_ground_item", {
            "itemId": item_id,
            "x": int(item["x"]),
            "y": int(item["y"]),
            "maxDistance": args.loot_distance,
        }, profile=profile)
        player = bridge.player_from(result)
        bridge.write_event(handle, "loot", {
            "item": item,
            "success": bool(result.get("success")),
            "player": bridge.compact_player(player, ("attack", "strength", "defence", "hitpoints")),
        })
    return player


def attack_round(profile, args, handle):
    player = bridge.observe(profile)
    if bool(player.get("isDead", False)):
        raise RuntimeError("player is dead")
    player = safe_eat(player, profile, args, handle)
    if hp(player) <= args.retreat_at_hitpoints and args.stop_when_unsafe:
        raise RuntimeError("hitpoints are unsafe and food did not recover enough")
    style = choose_style(player, args.target_level, args.style)
    if style == "complete":
        return {"complete": True, "player": player}
    bridge.call_tool("set_combat_style", {"style": style}, profile=profile)
    if args.area:
        bridge.route_to(args.area, profile=profile, handle=handle, reason="combat_area")
        player = bridge.observe(profile)
    find_result = bridge.call_tool("find_training_npc", {
        "name": args.npc,
        "maxDistance": args.npc_max_distance,
        "minHitpoints": args.min_npc_hitpoints,
        "maxNpcMaxHit": args.max_npc_max_hit,
        "reachable": True,
        "allowUnderAttack": args.allow_under_attack,
    }, profile=profile)
    if not find_result.get("success"):
        raise RuntimeError(find_result.get("message", "no combat target found"))
    npc = find_result.get("npc") or {}
    attack = bridge.call_tool("attack_npc", {"npcIndex": int(npc["npcIndex"])}, profile=profile)
    wait = bridge.call_tool("wait_until_idle", {
        "maxTicks": args.fight_ticks,
        "movement": True,
        "skilling": False,
        "combat": True,
    }, profile=profile)
    player = bridge.player_from(wait)
    player = pickup_loot(profile, args, handle)
    bridge.write_event(handle, "combat_round", {
        "style": style,
        "npc": npc,
        "attackSuccess": bool(attack.get("success")),
        "waitStatus": wait.get("batchStatus"),
        "player": bridge.compact_player(player, ("attack", "strength", "defence", "hitpoints")),
    })
    return {"complete": False, "player": player}


def parse_item_ids(value):
    if not value:
        return []
    return [int(part.strip()) for part in str(value).split(",") if part.strip()]


def run(args):
    args.loot_item_ids = parse_item_ids(args.loot_item_ids)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = bridge.observe(profile)
        player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason="combat_runner")
        bridge.write_event(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("attack", "strength", "defence", "hitpoints")),
        })
        for round_no in range(1, args.max_rounds + 1):
            result = attack_round(profile, args, handle)
            player = result["player"]
            log("round {} npc={} hp={}/{} atk={} str={} def={} complete={}".format(
                round_no,
                args.npc,
                hp(player),
                max_hp(player),
                combat_level(player, "attack"),
                combat_level(player, "strength"),
                combat_level(player, "defence"),
                result["complete"],
            ), args)
            if result["complete"]:
                break
        bridge.write_event(handle, "run_finish", {
            "player": bridge.compact_player(player, ("attack", "strength", "defence", "hitpoints")),
        })
        if handle is not None:
            log("combat log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run primitive-backed combat training.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--npc", default="goblin")
    parser.add_argument("--area", default="", help="Optional route target before each combat round.")
    parser.add_argument("--target-level", type=int, default=10)
    parser.add_argument("--style", choices=["", "attack", "strength", "defence", "controlled"], default="")
    parser.add_argument("--max-rounds", type=int, default=50)
    parser.add_argument("--fight-ticks", type=int, default=80)
    parser.add_argument("--npc-max-distance", type=int, default=25)
    parser.add_argument("--min-npc-hitpoints", type=int, default=1)
    parser.add_argument("--max-npc-max-hit", type=int, default=999)
    parser.add_argument("--allow-under-attack", action="store_true")
    parser.add_argument("--eat-at-hitpoints", type=int, default=5)
    parser.add_argument("--retreat-at-hitpoints", type=int, default=3)
    parser.add_argument("--stop-when-unsafe", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--loot-item-ids", default="", help="Comma-separated item IDs to loot after fights.")
    parser.add_argument("--loot-distance", type=int, default=12)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
