#!/usr/bin/env python3
"""Primitive-backed smelting and smithing runner."""

import argparse
import datetime as dt
import re
import uuid

import bridge_script as bridge


RUNS_DIR = bridge.ROOT / "data" / "smithing" / "runs"
SMITHING_DATA = bridge.REPO_ROOT / "2006Scape Server" / "src" / "main" / "java" / "com" / "rs2" / "game" / "content" / "skills" / "smithing" / "SmithingData.java"

HAMMER = 2347
FURNACE_IDS = [14921, 9390, 2781, 2785, 2966, 3294, 3413, 4304, 4305, 6189, 6190, 11009, 11010, 11666, 12100, 12809]
ANVIL_IDS = [2782, 2783]
BAR_IDS = {
    "bronze": 2349,
    "iron": 2351,
    "steel": 2353,
    "mithril": 2359,
    "mith": 2359,
    "adamant": 2361,
    "addy": 2361,
    "rune": 2363,
}
SMELT_BUTTONS = {
    "bronze": {1: 15147, 5: 15146, 10: 10247},
    "iron": {1: 15151, 5: 15150, 10: 15149},
    "steel": {1: 15159, 5: 15158, 10: 15157},
    "mithril": {1: 29017, 5: 29016, 10: 24253},
    "mith": {1: 29017, 5: 29016, 10: 24253},
    "adamant": {1: 29022, 5: 29020, 10: 29019},
    "addy": {1: 29022, 5: 29020, 10: 29019},
    "rune": {1: 29026, 5: 29025, 10: 29024},
    "silver": {1: 15155, 5: 15154, 10: 15153},
    "gold": {1: 15163, 5: 15162, 10: 15161},
}
SMELT_PRIMARY_ITEM = {
    "bronze": 436,
    "iron": 440,
    "steel": 440,
    "mithril": 447,
    "mith": 447,
    "adamant": 449,
    "addy": 449,
    "rune": 451,
    "silver": 442,
    "gold": 444,
}
SMELT_REQUIREMENTS = {
    "bronze": {436: 1, 438: 1},
    "iron": {440: 1},
    "steel": {440: 1, 453: 2},
    "mithril": {447: 1, 453: 4},
    "mith": {447: 1, 453: 4},
    "adamant": {449: 1, 453: 6},
    "addy": {449: 1, 453: 6},
    "rune": {451: 1, 453: 8},
    "silver": {442: 1},
    "gold": {444: 1},
}
PREFIX_BARS = {
    "BRONZE": 2349,
    "IRON": 2351,
    "STEEL": 2353,
    "MITH": 2359,
    "ADDY": 2361,
    "RUNE": 2363,
}


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def normalize(value):
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def load_smithing_data():
    text = SMITHING_DATA.read_text(encoding="utf-8")
    items = []
    for match in re.finditer(r"^\s*([A-Z0-9_]+)\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", text, re.MULTILINE):
        enum_name = match.group(1)
        item_id = int(match.group(2))
        xp = int(match.group(3))
        level = int(match.group(4))
        bars = int(match.group(5))
        bar_id = None
        for prefix, candidate_bar in PREFIX_BARS.items():
            if enum_name.startswith(prefix + "_"):
                bar_id = candidate_bar
                break
        if bar_id is None:
            continue
        items.append({
            "enum": enum_name,
            "name": normalize(enum_name),
            "itemId": item_id,
            "xp": xp,
            "level": level,
            "bars": bars,
            "barId": bar_id,
        })
    return items


def choose_smith_item(player, args):
    items = load_smithing_data()
    if args.item_id:
        for item in items:
            if item["itemId"] == args.item_id:
                return item
        raise RuntimeError("smithing item id {} is not in SmithingData".format(args.item_id))
    query = normalize(args.item)
    if query:
        matches = [item for item in items if query in item["name"]]
        if not matches:
            raise RuntimeError("no smithing item matches '{}'".format(args.item))
        items = matches
    level = bridge.skill_level(player, "smithing")
    available = [
        item for item in items
        if item["level"] <= level and bridge.count_inventory_item(player, item["barId"]) >= item["bars"]
    ]
    if not available:
        raise RuntimeError("no requested smithing item is available for level and carried bars")
    available.sort(key=lambda item: (-item["xp"], -item["level"], item["bars"], item["itemId"]))
    return available[0]


def find_object(object_ids, max_distance, profile):
    result = bridge.call_tool("find_nearest_object", {
        "objectIds": object_ids,
        "maxDistance": max_distance,
    }, profile=profile)
    if not result.get("success"):
        raise RuntimeError(result.get("message", "object not found"))
    return result.get("object") or {}


def object_interaction_tile(obj):
    walk_target = obj.get("interactionWalkTarget") or obj.get("nearestInteractionTile") or {}
    x = walk_target.get("x")
    y = walk_target.get("y")
    if x is None or y is None:
        return None
    return {
        "x": int(x),
        "y": int(y),
        "height": int(walk_target.get("height", 0) or 0),
    }


def walk_to_tile(profile, tile, max_ticks):
    if not tile:
        return None
    return bridge.call_tool("walk_to_tile_until_arrived", {
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0) or 0),
        "stopDistance": 0,
        "maxTicks": int(max_ticks),
        "maxWalkDistance": 64,
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=profile)


def smelt_progress(player, primary_item, bar_item, before_primary, before_bars, before_xp):
    after_primary = bridge.count_inventory_item(player, primary_item)
    after_bars = bridge.count_inventory_item(player, bar_item) if bar_item else 0
    after_xp = bridge.skill_xp(player, "smithing")
    return {
        "afterPrimary": after_primary,
        "afterBars": after_bars,
        "afterXp": after_xp,
        "madeProgress": after_primary < before_primary or after_bars > before_bars or after_xp > before_xp,
    }


def smelt_chunk_button(bar, remaining):
    buttons = SMELT_BUTTONS[bar]
    if int(remaining) >= 10:
        return 10, int(buttons[10])
    if int(remaining) >= 5:
        return 5, int(buttons[5])
    return 1, int(buttons[1])


def smelt_possible_actions(player, bar):
    requirements = SMELT_REQUIREMENTS.get(bar) or {}
    possible = None
    for item_id, count in requirements.items():
        carried = bridge.count_inventory_item(player, int(item_id))
        actions = carried // max(1, int(count))
        possible = actions if possible is None else min(possible, actions)
    return int(possible or 0)


def smelt_round(profile, args, handle):
    bar = normalize(args.bar)
    if bar not in SMELT_PRIMARY_ITEM:
        raise RuntimeError("unknown bar '{}'; use bronze, iron, steel, mithril, adamant, rune, silver, or gold".format(args.bar))
    player = bridge.observe(profile)
    primary_item = SMELT_PRIMARY_ITEM[bar]
    bar_item = BAR_IDS.get(bar)
    before_primary = bridge.count_inventory_item(player, primary_item)
    before_bars = bridge.count_inventory_item(player, bar_item) if bar_item else 0
    before_xp = bridge.skill_xp(player, "smithing")
    possible = smelt_possible_actions(player, bar)
    if possible < 1:
        raise RuntimeError("no primary ore carried for {} smelting".format(bar))
    if args.furnace:
        bridge.route_to(args.furnace, profile=profile, handle=handle, reason="furnace")
    furnace = find_object(FURNACE_IDS, args.object_max_distance, profile)
    amount = max(1, min(int(args.amount), int(possible), 27))
    chunk_amount, button_id = smelt_chunk_button(bar, amount)
    use = bridge.call_tool("use_item_on_object", {
        "itemId": int(primary_item),
        "objectId": int(furnace.get("objectId")),
        "x": int(furnace.get("x")),
        "y": int(furnace.get("y")),
        "height": int(furnace.get("height", 0) or 0),
    }, profile=profile)
    button = bridge.call_tool("click_interface_button", {
        "buttonId": int(button_id),
    }, profile=profile)
    player = bridge._player_from_or(button, bridge._player_from_or(use, player))
    wait = bridge.call_tool("wait_until_idle", {
        "maxTicks": args.max_ticks,
        "movement": True,
        "skilling": True,
        "combat": False,
    }, profile=profile)
    player = bridge.player_from(wait)
    progress = smelt_progress(player, primary_item, bar_item, before_primary, before_bars, before_xp)
    bridge.write_event(handle, "smelt_round", {
        "bar": bar,
        "amount": int(amount),
        "chunkAmount": int(chunk_amount),
        "furnace": furnace,
        "useSuccess": bool(use.get("success")),
        "useMessage": use.get("message"),
        "buttonId": int(button_id),
        "buttonSuccess": bool(button.get("success")),
        "buttonMessage": button.get("message"),
        "waitStatus": wait.get("batchStatus"),
        "beforePrimary": before_primary,
        "afterPrimary": progress["afterPrimary"],
        "beforeBars": before_bars,
        "afterBars": progress["afterBars"],
        "beforeXp": before_xp,
        "afterXp": progress["afterXp"],
        "madeProgress": bool(progress["madeProgress"]),
        "player": bridge.compact_player(player, ("smithing",)),
    })
    if not progress["madeProgress"]:
        raise RuntimeError("smelting made no ore, bar, or XP progress")
    return player


def smith_round(profile, args, handle):
    player = bridge.observe(profile)
    if not bridge.has_inventory_item(player, HAMMER):
        raise RuntimeError("hammer is required for smithing")
    item = choose_smith_item(player, args)
    if args.anvil:
        bridge.route_to(args.anvil, profile=profile, handle=handle, reason="anvil")
    anvil = find_object(ANVIL_IDS, args.object_max_distance, profile)
    use = bridge.call_tool("use_item_on_object", {
        "itemId": item["barId"],
        "objectId": anvil.get("objectId"),
        "x": anvil.get("x"),
        "y": anvil.get("y"),
    }, profile=profile)
    select = bridge.call_tool("select_interface_item", {
        "interfaceId": 1119,
        "itemId": item["itemId"],
        "amount": args.amount,
    }, profile=profile)
    wait = bridge.call_tool("wait_until_idle", {
        "maxTicks": args.max_ticks,
        "movement": True,
        "skilling": True,
        "combat": False,
    }, profile=profile)
    player = bridge.player_from(wait)
    bridge.write_event(handle, "smith_round", {
        "item": item,
        "anvil": anvil,
        "useSuccess": bool(use.get("success")),
        "selectSuccess": bool(select.get("success")),
        "waitStatus": wait.get("batchStatus"),
        "player": bridge.compact_player(player, ("smithing",)),
    })
    return player


def run(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), uuid.uuid4().hex[:8])
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    profile = args.profile
    try:
        player = bridge.observe(profile)
        player = bridge.ensure_run(player, args.min_run_energy, profile=profile, handle=handle, reason="smithing_runner")
        bridge.write_event(handle, "run_start", {
            "args": vars(args),
            "player": bridge.compact_player(player, ("smithing",)),
        })
        for cycle in range(1, args.max_cycles + 1):
            if args.target_smithing_level and bridge.skill_level(player, "smithing") >= args.target_smithing_level:
                break
            if args.mode == "smelt":
                player = smelt_round(profile, args, handle)
            else:
                player = smith_round(profile, args, handle)
            log("cycle {} mode={} smithing={} xp={} free={}".format(
                cycle,
                args.mode,
                bridge.skill_level(player, "smithing"),
                bridge.skill_xp(player, "smithing"),
                player.get("freeInventorySlots"),
            ), args)
            if args.stop_when_inputs_empty:
                if args.mode == "smelt" and bridge.count_inventory_item(player, SMELT_PRIMARY_ITEM[normalize(args.bar)]) < 1:
                    break
                if args.mode == "smith":
                    try:
                        choose_smith_item(player, args)
                    except RuntimeError:
                        break
        bridge.write_event(handle, "run_finish", {"player": bridge.compact_player(player, ("smithing",))})
        if handle is not None:
            log("smithing log: {}".format(run_path), args)
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run primitive-backed smelting or smithing.")
    parser.add_argument("--profile", default="")
    parser.add_argument("--mode", choices=["smelt", "smith"], default="smith")
    parser.add_argument("--bar", default="bronze")
    parser.add_argument("--item", default="", help="SmithingData enum/name substring, e.g. sword, scim, plate.")
    parser.add_argument("--item-id", type=int, default=0)
    parser.add_argument("--amount", type=int, default=28)
    parser.add_argument("--target-smithing-level", type=int, default=0)
    parser.add_argument("--max-cycles", type=int, default=20)
    parser.add_argument("--max-ticks", type=int, default=260)
    parser.add_argument("--object-max-distance", type=int, default=20)
    parser.add_argument("--furnace", default="")
    parser.add_argument("--anvil", default="")
    parser.add_argument("--stop-when-inputs-empty", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-run-energy", type=int, default=10)
    parser.add_argument("--quiet", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
