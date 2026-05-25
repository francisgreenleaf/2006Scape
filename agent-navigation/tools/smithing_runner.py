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
    "bronze": 9110,
    "iron": 15148,
    "steel": 15156,
    "mithril": 16062,
    "mith": 16062,
    "adamant": 29018,
    "addy": 29018,
    "rune": 29023,
    "silver": 15152,
    "gold": 15160,
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


def smelt_round(profile, args, handle):
    bar = normalize(args.bar)
    if bar not in SMELT_BUTTONS:
        raise RuntimeError("unknown bar '{}'; use bronze, iron, steel, mithril, adamant, rune, silver, or gold".format(args.bar))
    if bridge.count_inventory_item(bridge.observe(profile), SMELT_PRIMARY_ITEM[bar]) < 1:
        raise RuntimeError("no primary ore carried for {} smelting".format(bar))
    if args.furnace:
        bridge.route_to(args.furnace, profile=profile, handle=handle, reason="furnace")
    furnace = find_object(FURNACE_IDS, args.object_max_distance, profile)
    open_result = bridge.call_tool("interact_object", {
        "objectId": furnace.get("objectId"),
        "x": furnace.get("x"),
        "y": furnace.get("y"),
        "option": "first",
    }, profile=profile)
    button = bridge.call_tool("click_interface_button", {"buttonId": SMELT_BUTTONS[bar]}, profile=profile)
    wait = bridge.call_tool("wait_until_idle", {
        "maxTicks": args.max_ticks,
        "movement": True,
        "skilling": True,
        "combat": False,
    }, profile=profile)
    player = bridge.player_from(wait)
    bridge.write_event(handle, "smelt_round", {
        "bar": bar,
        "furnace": furnace,
        "openSuccess": bool(open_result.get("success")),
        "buttonSuccess": bool(button.get("success")),
        "waitStatus": wait.get("batchStatus"),
        "player": bridge.compact_player(player, ("smithing",)),
    })
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
