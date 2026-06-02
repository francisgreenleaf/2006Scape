#!/usr/bin/env python3
"""Pick flax, spin it into bowstrings, and bank products in Seers Village."""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
ML2_DEFINE = ROOT / "ml2-routing" / "route_ml_XS.py"
RUNS_DIR = ROOT / "data" / "crafting" / "runs"
CONTROL_DIR = ROOT / ".local" / "runners"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
from profile_utils import resolve_profile, safe_profile  # noqa: E402


FLAX = 1779
BOW_STRING = 1777
SPINNING_WHEEL_OBJECT = 2644
FLAX_OBJECT = 2646
GROUND_LADDER_OBJECT = 1747
UPSTAIRS_LADDER_OBJECT = 1746

SEERS_BANK = "seers_bank"
SEERS_BANK_TILE = {"x": 2727, "y": 3493, "height": 0}
FLAX_FIELD_TILE = {"x": 2741, "y": 3451, "height": 0}
GROUND_LADDER_TILE = {"x": 2715, "y": 3470, "height": 0}
UPSTAIRS_LADDER_TILE = {"x": 2715, "y": 3470, "height": 1}
SPINNING_WHEEL_TILE = {"x": 2710, "y": 3471, "height": 1}

BANK_TO_FLAX = [
    {"x": 2731, "y": 3484, "height": 0},
    {"x": 2738, "y": 3469, "height": 0},
    FLAX_FIELD_TILE,
]
FLAX_TO_LADDER = [
    {"x": 2737, "y": 3461, "height": 0},
    {"x": 2724, "y": 3464, "height": 0},
    GROUND_LADDER_TILE,
]
BANK_TO_LADDER = [
    {"x": 2723, "y": 3486, "height": 0},
    {"x": 2716, "y": 3476, "height": 0},
    GROUND_LADDER_TILE,
]
LADDER_TO_BANK = [
    {"x": 2717, "y": 3478, "height": 0},
    {"x": 2724, "y": 3488, "height": 0},
    SEERS_BANK_TILE,
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def run_stem(profile):
    return "seers-flax-bowstring-{}".format(safe_profile(profile))


def status_path(profile):
    return CONTROL_DIR / "{}.status.json".format(run_stem(profile))


def stop_path(profile):
    return CONTROL_DIR / "{}.stop".format(run_stem(profile))


def compact(player):
    data = bridge.compact_player(player, ("crafting",))
    data.update({
        "flax": bridge.count_inventory_item(player, FLAX),
        "bowstrings": bridge.count_inventory_item(player, BOW_STRING),
        "bankedFlax": bridge.count_bank_item(player, FLAX),
        "bankedBowstrings": bridge.count_bank_item(player, BOW_STRING),
    })
    return data


def write_status(args, phase, player, run_path=None, extra=None):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": True,
        "runner": "seers_flax_bowstring_runner",
        "updatedAt": utc_now(),
        "phase": phase,
        "profile": args.profile,
        "pid": os.getpid(),
        "stopRequested": stop_path(args.profile).exists(),
        "runLog": str(run_path) if run_path else None,
        "player": compact(player) if player else None,
        "targetBowstrings": args.target_bowstrings,
        "args": vars(args),
    }
    if extra:
        payload.update(extra)
    status_path(args.profile).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                                         encoding="utf-8")


def print_status(args):
    path = status_path(args.profile)
    payload = {
        "statusPath": str(path),
        "stopPath": str(stop_path(args.profile)),
        "stopRequested": stop_path(args.profile).exists(),
    }
    if path.exists():
        payload["status"] = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload["error"] = "no_status"
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def request_stop(args):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    path = stop_path(args.profile)
    path.write_text(utc_now() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "stopRequested": True, "stopPath": str(path)}, indent=2, sort_keys=True))
    return 0


def clear_stop(args):
    path = stop_path(args.profile)
    if path.exists():
        path.unlink()
    print(json.dumps({"ok": True, "stopRequested": False, "stopPath": str(path)}, indent=2, sort_keys=True))
    return 0


def write(handle, event, data):
    bridge.write_event(handle, event, data)


def observe(profile):
    return bridge.observe_xs(profile=profile)


def tile(player):
    return bridge.tile_from_player(player)


def chebyshev(a, b):
    return bridge.chebyshev(a, b)


def in_seers(player):
    current = tile(player)
    return int(current["height"]) in (0, 1) and 2695 <= int(current["x"]) <= 2750 and 3440 <= int(current["y"]) <= 3505


def run_command(command, profile, handle, event, data, expect_json=True):
    env = os.environ.copy()
    if profile:
        env["RS_PROFILE"] = profile
        env["RSBRIDGE_PROFILE"] = profile
        env["RS_TRACE_PROFILE"] = profile
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    write(handle, event, {
        **data,
        "command": command,
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout.strip().splitlines()[-8:],
        "stderrTail": proc.stderr.strip().splitlines()[-8:],
    })
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(event, proc.stderr.strip() or proc.stdout.strip()))
    if not expect_json:
        return {"success": True}
    for line in proc.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise RuntimeError("{} returned no JSON object".format(event))


def tile_string(value):
    return "{},{},{}".format(int(value["x"]), int(value["y"]), int(value.get("height", 0) or 0))


def parse_target_tile(value):
    parts = str(value).split(",")
    if len(parts) not in (2, 3):
        return None
    try:
        return {"x": int(parts[0]), "y": int(parts[1]), "height": int(parts[2]) if len(parts) == 3 else 0}
    except ValueError:
        return None


def ml2_route_to(target, args, handle, reason, arrival_radius=1):
    player = observe(args.profile)
    target_tile = parse_target_tile(target)
    if target_tile and chebyshev(tile(player), target_tile) <= arrival_radius:
        return player
    command = [
        "python3",
        str(ML2_DEFINE),
        "define",
        "--from",
        tile_string(tile(player)),
        "--to",
        str(target),
        "--combat-level",
        str(args.combat_level or int(player.get("combatLevel", player.get("cb", 3)) or 3)),
        "--food",
        str(args.food),
        "--run-energy",
        str(int(player.get("runEnergy", 0) or 0)),
    ]
    if player.get("runEnabled"):
        command.append("--run-enabled")
    definition = run_command(command, args.profile, handle, "ml2_route_define", {
        "reason": reason,
        "target": str(target),
        "player": compact(player),
    })
    if definition.get("status") != "ok" or not definition.get("path"):
        raise RuntimeError("ML2 route to {} was not executable: {}".format(target, definition.get("status")))
    route_path = REPO_ROOT / definition["path"]
    route_definition = json.loads(route_path.read_text(encoding="utf-8"))
    exec_command = route_definition.get("execution", {}).get("command")
    if not exec_command:
        raise RuntimeError("ML2 route definition did not contain an execution command: {}".format(route_path))
    close_interfaces(args, handle, reason + "_before_execute")
    run_command(exec_command, args.profile, handle, "ml2_route_execute", {
        "reason": reason,
        "target": str(target),
        "routePath": str(route_path),
        "routeId": definition.get("id"),
    }, expect_json=False)
    return observe(args.profile)


def safety_check(player):
    if player.get("isDead"):
        raise RuntimeError("player is dead")
    if player.get("isInCombat"):
        raise RuntimeError("player is in combat")


def player_from_or(result, profile, fallback):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return fallback or observe(profile)


def close_interfaces(args, handle, reason):
    result = bridge.call_tool("close_interfaces", {}, profile=args.profile)
    player = player_from_or(result, args.profile, None)
    write(handle, "close_interfaces", {
        "reason": reason,
        "success": bool(result.get("success")),
        "player": compact(player),
    })
    return player


def walk_tile(destination, args, handle, reason, max_ticks=50, stop_distance=0):
    player = observe(args.profile)
    safety_check(player)
    if chebyshev(tile(player), destination) <= stop_distance:
        return player
    close_interfaces(args, handle, reason + "_before_walk")
    result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
        "x": int(destination["x"]),
        "y": int(destination["y"]),
        "height": int(destination.get("height", 0) or 0),
        "stopDistance": int(stop_distance),
        "maxTicks": int(max_ticks),
        "maxWalkDistance": 96,
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=args.profile)
    updated = player_from_or(result, args.profile, player)
    write(handle, "walk_tile", {
        "reason": reason,
        "destination": destination,
        "success": bool(result.get("success")),
        "batchStatus": result.get("batchStatus"),
        "player": compact(updated),
    })
    safety_check(updated)
    return updated


def walk_path(path, args, handle, reason):
    player = observe(args.profile)
    for index, destination in enumerate(path):
        player = walk_tile(destination, args, handle, "{}_{}".format(reason, index), max_ticks=60, stop_distance=0)
    return player


def click_ladder(object_id, object_tile, expected_height, args, handle, reason):
    player = observe(args.profile)
    result = bridge.call_tool("interact_object_XS", {
        "objectId": int(object_id),
        "x": int(object_tile["x"]),
        "y": int(object_tile["y"]),
        "height": int(object_tile.get("height", tile(player).get("height", 0)) or 0),
        "option": "first",
        "requireReachable": True,
    }, profile=args.profile)
    player = player_from_or(result, args.profile, player)
    wait = bridge.call_tool("wait_until_idle_XS", {
        "maxTicks": 12,
        "movement": True,
        "skilling": False,
        "combat": False,
    }, profile=args.profile)
    player = player_from_or(wait, args.profile, player)
    write(handle, "ladder_transition", {
        "reason": reason,
        "objectId": object_id,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact(player),
    })
    if int(tile(player)["height"]) != int(expected_height):
        player = observe(args.profile)
    if int(tile(player)["height"]) != int(expected_height):
        raise RuntimeError("{} did not reach height {}".format(reason, expected_height))
    return player


def ensure_ground(player, args, handle, reason):
    if int(tile(player)["height"]) == 0:
        return player
    walk_tile(UPSTAIRS_LADDER_TILE, args, handle, reason + "_to_upstairs_ladder", max_ticks=30, stop_distance=1)
    return click_ladder(UPSTAIRS_LADDER_OBJECT, UPSTAIRS_LADDER_TILE, 0, args, handle, reason + "_down")


def ensure_upstairs(player, args, handle, reason):
    if int(tile(player)["height"]) == 1:
        return player
    walk_tile(GROUND_LADDER_TILE, args, handle, reason + "_to_ground_ladder", max_ticks=30, stop_distance=1)
    return click_ladder(GROUND_LADDER_OBJECT, GROUND_LADDER_TILE, 1, args, handle, reason + "_up")


def ensure_seers_bank(player, args, handle, reason):
    player = ensure_ground(player, args, handle, reason + "_ground")
    if not in_seers(player) and args.allow_ml2_route:
        player = ml2_route_to(SEERS_BANK, args, handle, reason + "_ml2", arrival_radius=2)
    if chebyshev(tile(player), SEERS_BANK_TILE) > 3:
        if in_seers(player):
            player = walk_path(LADDER_TO_BANK, args, handle, reason + "_local")
        else:
            player = ml2_route_to(SEERS_BANK, args, handle, reason + "_ml2_fallback", arrival_radius=2)
    if not bool(player.get("inBankArea", False)):
        player = walk_tile(SEERS_BANK_TILE, args, handle, reason + "_bank_tile", max_ticks=40, stop_distance=1)
    open_result = bridge.call_tool("deposit_inventory_items_XS", {"name": "__codex_open_bank_only__"}, profile=args.profile)
    player = player_from_or(open_result, args.profile, player)
    write(handle, "open_bank", {"reason": reason, "success": bool(open_result.get("success")), "player": compact(player)})
    return player


def deposit_products(player, args, handle, reason, include_flax=False):
    player = ensure_seers_bank(player, args, handle, reason)
    item_ids = [BOW_STRING]
    if include_flax:
        item_ids.append(FLAX)
    result = bridge.call_tool("deposit_inventory_items_XS", {"itemIds": item_ids}, profile=args.profile)
    player = player_from_or(result, args.profile, player)
    write(handle, "deposit_products", {
        "reason": reason,
        "itemIds": item_ids,
        "success": bool(result.get("success")),
        "depositedAmount": result.get("depositedAmount"),
        "player": compact(player),
    })
    return player


def withdraw_banked_flax(player, args, handle):
    player = ensure_seers_bank(player, args, handle, "withdraw_flax")
    amount = min(28, int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0))
    if amount <= 0:
        return player
    result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": FLAX, "amount": amount}, profile=args.profile)
    player = player_from_or(result, args.profile, player)
    write(handle, "withdraw_flax", {
        "amount": amount,
        "success": bool(result.get("success")),
        "withdrawnAmount": result.get("withdrawnAmount"),
        "player": compact(player),
    })
    return player


def go_to_flax_field(player, args, handle):
    player = ensure_ground(player, args, handle, "flax_field")
    if not in_seers(player) and args.allow_ml2_route:
        player = ml2_route_to(tile_string(FLAX_FIELD_TILE), args, handle, "flax_field_ml2", arrival_radius=2)
    if chebyshev(tile(player), FLAX_FIELD_TILE) > 3:
        player = walk_path(BANK_TO_FLAX, args, handle, "bank_to_flax")
    return player


def pick_flax_inventory(player, args, handle):
    player = go_to_flax_field(player, args, handle)
    picked = 0
    while int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0) > 0:
        safety_check(player)
        before = bridge.count_inventory_item(player, FLAX)
        find = bridge.call_tool("find_nearest_object_XS", {
            "objectIds": [FLAX_OBJECT],
            "maxDistance": 12,
        }, profile=args.profile)
        obj = find.get("object") or {}
        if not find.get("success") or not obj:
            raise RuntimeError("no flax object nearby")
        result = bridge.call_tool("interact_object_XS", {
            "objectId": int(obj.get("id", obj.get("objectId", FLAX_OBJECT))),
            "x": int(obj["x"]),
            "y": int(obj["y"]),
            "height": int(obj.get("height", tile(player).get("height", 0)) or 0),
            "option": "first",
        }, profile=args.profile)
        player = player_from_or(result, args.profile, player)
        wait = bridge.call_tool("wait_until_idle_XS", {
            "maxTicks": 6,
            "movement": True,
            "skilling": False,
            "combat": False,
        }, profile=args.profile)
        player = player_from_or(wait, args.profile, player)
        after = bridge.count_inventory_item(player, FLAX)
        if after > before:
            picked += after - before
        write(handle, "pick_flax", {
            "success": bool(result.get("success")),
            "beforeFlax": before,
            "afterFlax": after,
            "pickedThisInventory": picked,
            "player": compact(player),
        })
        if after <= before:
            time.sleep(0.2)
            player = observe(args.profile)
    return player


def go_to_spinning_wheel(player, args, handle):
    if int(tile(player)["height"]) == 1:
        return walk_tile(SPINNING_WHEEL_TILE, args, handle, "to_spinning_wheel_upstairs", max_ticks=30, stop_distance=1)
    player = ensure_ground(player, args, handle, "wheel_ground")
    if not in_seers(player) and args.allow_ml2_route:
        player = ml2_route_to(tile_string(GROUND_LADDER_TILE), args, handle, "wheel_ml2", arrival_radius=2)
    if chebyshev(tile(player), GROUND_LADDER_TILE) > 3:
        if chebyshev(tile(player), FLAX_FIELD_TILE) <= 10:
            player = walk_path(FLAX_TO_LADDER, args, handle, "flax_to_ladder")
        else:
            player = walk_path(BANK_TO_LADDER, args, handle, "bank_to_ladder")
    player = ensure_upstairs(player, args, handle, "wheel_upstairs")
    return walk_tile(SPINNING_WHEEL_TILE, args, handle, "to_spinning_wheel", max_ticks=30, stop_distance=1)


def spin_flax_inventory(player, args, handle):
    if bridge.skill_level(player, "crafting") < 10 and not args.allow_below_level:
        raise RuntimeError("Crafting level 10 is required to spin flax")
    if bridge.count_inventory_item(player, FLAX) <= 0:
        return player
    player = go_to_spinning_wheel(player, args, handle)
    before_flax = bridge.count_inventory_item(player, FLAX)
    before_strings = bridge.count_inventory_item(player, BOW_STRING)
    before_xp = bridge.skill_xp(player, "crafting")
    use_result = bridge.call_tool("use_item_on_object", {
        "itemId": FLAX,
        "objectId": SPINNING_WHEEL_OBJECT,
        "x": SPINNING_WHEEL_TILE["x"],
        "y": SPINNING_WHEEL_TILE["y"],
        "height": SPINNING_WHEEL_TILE["height"],
    }, profile=args.profile)
    player = player_from_or(use_result, args.profile, player)
    button = bridge.call_tool("click_interface_button_XXS", {"buttonId": 34186}, profile=args.profile)
    player = player_from_or(button, args.profile, player)
    wait = bridge.call_tool("wait_until_idle_XS", {
        "maxTicks": max(30, before_flax * 4 + 12),
        "movement": False,
        "skilling": True,
        "combat": False,
    }, profile=args.profile)
    player = player_from_or(wait, args.profile, player)
    write(handle, "spin_flax_inventory", {
        "beforeFlax": before_flax,
        "afterFlax": bridge.count_inventory_item(player, FLAX),
        "beforeBowstrings": before_strings,
        "afterBowstrings": bridge.count_inventory_item(player, BOW_STRING),
        "beforeCraftingXp": before_xp,
        "afterCraftingXp": bridge.skill_xp(player, "crafting"),
        "openedSpinningInterface": use_result.get("openedSpinningInterface"),
        "player": compact(player),
    })
    return player


def bowstring_total(player):
    return bridge.count_inventory_item(player, BOW_STRING) + bridge.count_bank_item(player, BOW_STRING)


def stop_requested(args):
    return stop_path(args.profile).exists()


def run_loop(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-seers-flax-bowstring-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    if stop_path(args.profile).exists():
        stop_path(args.profile).unlink()
    cycles = 0
    with run_path.open("a", encoding="utf-8") as handle:
        player = observe(args.profile)
        write(handle, "run_start", {"profile": args.profile, "player": compact(player), "args": vars(args)})
        write_status(args, "running", player, run_path=run_path, extra={"cycles": cycles})
        while args.max_cycles <= 0 or cycles < args.max_cycles:
            player = observe(args.profile)
            safety_check(player)
            if args.target_bowstrings > 0 and bowstring_total(player) >= args.target_bowstrings:
                player = deposit_products(player, args, handle, "target_reached", include_flax=True)
                write_status(args, "complete", player, run_path=run_path, extra={"cycles": cycles})
                return 0
            if stop_requested(args):
                player = deposit_products(player, args, handle, "stop_requested", include_flax=True)
                write_status(args, "stopped", player, run_path=run_path, extra={"cycles": cycles})
                return 0

            if bridge.count_inventory_item(player, BOW_STRING) > 0:
                player = deposit_products(player, args, handle, "bank_strings")
            elif bridge.count_inventory_item(player, FLAX) > 0:
                player = spin_flax_inventory(player, args, handle)
            else:
                player = ensure_seers_bank(player, args, handle, "cycle_start_bank")
                if bridge.count_bank_item(player, FLAX) > 0 and not args.pick_only:
                    player = withdraw_banked_flax(player, args, handle)
                else:
                    player = pick_flax_inventory(player, args, handle)
                if not args.pick_only:
                    player = spin_flax_inventory(player, args, handle)
            cycles += 1
            write_status(args, "running", player, run_path=run_path, extra={
                "cycles": cycles,
                "bowstringTotal": bowstring_total(player),
            })
            log("cycle {} bowstrings={} crafting={}".format(
                cycles, bowstring_total(player), bridge.skill_level(player, "crafting")), args)

        player = observe(args.profile)
        write_status(args, "complete", player, run_path=run_path, extra={"cycles": cycles, "reason": "max_cycles"})
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="", help="Bridge profile. Defaults to RS_PROFILE, then MrFlame.")
    parser.add_argument("--target-bowstrings", type=int, default=5000)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means loop until target/stop request.")
    parser.add_argument("--combat-level", type=int, default=0)
    parser.add_argument("--food", type=int, default=0)
    parser.add_argument("--allow-ml2-route", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-below-level", action="store_true",
                        help="Try spinning even if compact state says Crafting is below 10.")
    parser.add_argument("--pick-only", action="store_true", help="Pick and bank flax without spinning.")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--status", action="store_true", help="Print cooperative runner status and exit.")
    parser.add_argument("--request-stop", action="store_true", help="Ask the runner to stop at a safe bank boundary.")
    parser.add_argument("--clear-stop", action="store_true", help="Clear a pending stop request.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.profile = resolve_profile(args.profile)
    if args.status:
        return print_status(args)
    if args.request_stop:
        return request_stop(args)
    if args.clear_stop:
        return clear_stop(args)
    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
