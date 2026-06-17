#!/usr/bin/env python3
"""Mine and bank coal through the Falador Dwarven Mine trapdoor."""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
ML2_DEFINE = ROOT / "ml2-routing" / "route_ml_XS.py"
RUNS_DIR = ROOT / "data" / "mining" / "runs"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
import mining_runner  # noqa: E402
from profile_utils import resolve_profile  # noqa: E402


FALADOR_EAST_BANK = "falador_east_bank"
FALADOR_EAST_BANK_TILE = {"x": 3015, "y": 3355, "height": 0}
TRAPDOOR_APPROACH = {"x": 3019, "y": 3450, "height": 0}
TRAPDOOR = {"objectId": 11867, "x": 3019, "y": 3450, "height": 0}
UNDERGROUND_LADDER_APPROACH = {"x": 3018, "y": 9851, "height": 0}
UNDERGROUND_LADDER = {"objectId": 1755, "x": 3019, "y": 9850, "height": 0}
DEFAULT_COAL_SITE_TILE = {"x": 3040, "y": 9790, "height": 0}
MAX_SURFACE_DIRECT_WALK = 32

ALL_MINING_PRODUCT_IDS = [
    definition["itemId"] for definition in mining_runner.ORE_DEFS.values()
] + mining_runner.MINING_BYPRODUCT_ITEM_IDS


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write(handle, event, data):
    if handle is None:
        return
    record = {"event": event, "timestamp": utc_now()}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def log(message, args):
    if not args.quiet:
        print(message, flush=True)


def tile_string(tile):
    return "{},{},{}".format(int(tile["x"]), int(tile["y"]), int(tile.get("height", 0) or 0))


def tile_from_player(player):
    return {
        "x": int(player.get("x", 0) or 0),
        "y": int(player.get("y", 0) or 0),
        "height": int(player.get("height", player.get("h", 0)) or 0),
    }


def chebyshev(a, b):
    if int(a.get("height", 0) or 0) != int(b.get("height", 0) or 0):
        return 100000
    return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))


def is_underground(player):
    tile = tile_from_player(player)
    return tile["height"] == 0 and 9700 <= tile["y"] <= 9900 and 2990 <= tile["x"] <= 3070


def observe(profile):
    return bridge.observe_xs(profile=profile)


def observe_full(profile):
    return bridge.observe_full(profile=profile)


def player_from_or_observe(result, profile, fallback=None):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return fallback or observe(profile)


def compact(player):
    return mining_runner.compact_player(player)


def inventory_ids(player):
    ids = []
    seen = set()
    for item in bridge.inventory(player):
        item_id = int(item.get("id", item.get("itemId", -1)) or -1)
        if item_id >= 0 and item_id not in seen:
            ids.append(item_id)
            seen.add(item_id)
    return ids


def same_plane_near(player, target, max_distance):
    return (
        int(tile_from_player(player).get("height", 0)) == int(target.get("height", 0))
        and chebyshev(tile_from_player(player), target) <= int(max_distance)
    )


def run_command(command, profile, handle, event, data, expect_json=True, allow_nonzero=False):
    env = os.environ.copy()
    if profile:
        env["RS_PROFILE"] = profile
        env["RSBRIDGE_PROFILE"] = profile
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
    if proc.returncode != 0 and not allow_nonzero:
        raise RuntimeError("{} failed: {}".format(event, proc.stderr.strip() or proc.stdout.strip()))
    if not expect_json:
        return {"success": True}
    for line in proc.stdout.strip().splitlines():
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise RuntimeError("{} returned no JSON object".format(event))


def ml2_route_to(target, args, handle, reason, arrival_radius=1):
    player = observe(args.profile)
    command = [
        "python3",
        str(ML2_DEFINE),
        "define",
        "--from",
        tile_string(tile_from_player(player)),
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
    run_command(exec_command, args.profile, handle, "ml2_route_execute", {
        "reason": reason,
        "target": str(target),
        "routePath": str(route_path),
        "routeId": definition.get("id"),
    }, expect_json=False, allow_nonzero=True)
    player = observe(args.profile)
    target_tile = parse_tile(target)
    if target_tile and chebyshev(tile_from_player(player), target_tile) > arrival_radius:
        write(handle, "ml2_route_arrival_miss", {
            "reason": reason,
            "target": target_tile,
            "arrivalRadius": arrival_radius,
            "player": compact(player),
        })
    return player


def parse_tile(value):
    parts = str(value).split(",")
    if len(parts) not in (2, 3):
        return None
    try:
        return {
            "x": int(parts[0]),
            "y": int(parts[1]),
            "height": int(parts[2]) if len(parts) == 3 else 0,
        }
    except ValueError:
        return None


def walk_exact(tile, args, handle, reason, max_ticks=80, current_player=None):
    player = current_player or observe(args.profile)
    if chebyshev(tile_from_player(player), tile) == 0:
        return player
    result = bridge.call_tool("walk_to_tile_until_arrived_XS", {
        "x": int(tile["x"]),
        "y": int(tile["y"]),
        "height": int(tile.get("height", 0) or 0),
        "stopDistance": 0,
        "maxTicks": int(max_ticks),
        "maxWalkDistance": int(args.direct_walk_max_distance),
        "stopOnCombat": True,
        "stopOnStall": True,
    }, profile=args.profile)
    player = player_from_or_observe(result, args.profile, player)
    write(handle, "walk_exact", {
        "reason": reason,
        "target": tile,
        "success": bool(result.get("success")),
        "batchStatus": result.get("batchStatus"),
        "message": result.get("message"),
        "player": compact(player),
    })
    if chebyshev(tile_from_player(player), tile) != 0:
        player = observe(args.profile)
    if chebyshev(tile_from_player(player), tile) != 0:
        raise RuntimeError("could not walk exactly to {} for {}".format(tile_string(tile), reason))
    return player


def transition(object_ref, option, args, handle, reason, expected_underground):
    result = bridge.call_tool("interact_object_XS", {
        "objectId": int(object_ref["objectId"]),
        "x": int(object_ref["x"]),
        "y": int(object_ref["y"]),
        "height": int(object_ref.get("height", 0) or 0),
        "option": option,
        "requireReachable": True,
    }, profile=args.profile)
    player = player_from_or_observe(result, args.profile)
    waited = None
    ticks_waited = 0
    ok = is_underground(player) == expected_underground
    for _attempt in range(8):
        if ok:
            break
        waited = bridge.call_tool("wait_ticks_XS", {"ticks": 1}, profile=args.profile)
        ticks_waited += 1
        player = player_from_or_observe(waited, args.profile, player)
        ok = is_underground(player) == expected_underground
    if not ok:
        player = observe(args.profile)
        ok = is_underground(player) == expected_underground
    write(handle, "object_transition", {
        "reason": reason,
        "object": object_ref,
        "option": option,
        "interactSuccess": bool(result.get("success")),
        "waitStatus": (waited or {}).get("batchStatus"),
        "waitTicks": ticks_waited,
        "proved": ok,
        "player": compact(player),
    })
    if not ok:
        raise RuntimeError("failed to prove transition for {}".format(reason))
    return player


def enter_mine(args, handle, player=None):
    player = player or observe(args.profile)
    if is_underground(player):
        return player
    if chebyshev(tile_from_player(player), TRAPDOOR_APPROACH) <= 1:
        return transition(TRAPDOOR, "Climb-down", args, handle, "dwarven_mine_descend", True)
    if same_plane_near(player, TRAPDOOR_APPROACH, MAX_SURFACE_DIRECT_WALK):
        player = walk_exact(TRAPDOOR_APPROACH, args, handle, "trapdoor_direct", current_player=player)
    else:
        player = ml2_route_to(tile_string(TRAPDOOR_APPROACH), args, handle, "trapdoor_route")
        if chebyshev(tile_from_player(player), TRAPDOOR_APPROACH) > 1:
            player = walk_exact(TRAPDOOR_APPROACH, args, handle, "trapdoor_exact", current_player=player)
    return transition(TRAPDOOR, "Climb-down", args, handle, "dwarven_mine_descend", True)


def exit_mine(args, handle, player=None):
    player = player or observe(args.profile)
    if not is_underground(player):
        return player
    if chebyshev(tile_from_player(player), UNDERGROUND_LADDER_APPROACH) != 0:
        player = walk_exact(
            UNDERGROUND_LADDER_APPROACH,
            args,
            handle,
            "underground_ladder_approach",
            max_ticks=140,
            current_player=player,
        )
    return transition(UNDERGROUND_LADDER, "Climb-up", args, handle, "dwarven_mine_climb_out", False)


def route_bank(args, handle, player=None):
    player = player or observe(args.profile)
    if is_underground(player):
        player = exit_mine(args, handle, player)
    if player.get("inBankArea"):
        return player
    if same_plane_near(player, FALADOR_EAST_BANK_TILE, MAX_SURFACE_DIRECT_WALK):
        player = walk_exact(FALADOR_EAST_BANK_TILE, args, handle, "falador_east_bank_direct", current_player=player)
    else:
        player = ml2_route_to(FALADOR_EAST_BANK, args, handle, "falador_east_bank", arrival_radius=4)
    if not player.get("inBankArea"):
        player = walk_exact(FALADOR_EAST_BANK_TILE, args, handle, "falador_east_bank_exact", current_player=player)
    if not player.get("inBankArea"):
        player = observe(args.profile)
    if not player.get("inBankArea"):
        raise RuntimeError("reached Falador East Bank route target but not a bank area")
    return player


def mine_args(args):
    return SimpleNamespace(
        profile=args.profile,
        no_enable_run=args.no_enable_run,
        min_run_energy=args.min_run_energy,
        auto_upgrade_pickaxe=False,
        auto_buy_bronze_pickaxe=False,
        pickaxe_shop_name="",
        pickaxe_shop_tile="",
        rock_scan_distance=args.rock_scan_distance,
        mine_max_ticks=args.mine_max_ticks,
        wait_for_local_respawn=True,
        legacy_mining_tool=False,
        legacy_mining_fallback=False,
        strategy="fastest",
        xp_weight=2.0,
        rock_distance_weight=1.0,
        respawn_weight=0.15,
        same_ore_density_weight=0.75,
        bank_all_ores=True,
        bank=FALADOR_EAST_BANK,
        bank_tile=tile_string(FALADOR_EAST_BANK_TILE),
        arrival_radius=args.arrival_radius,
        max_batches_per_leg=8,
        max_walk_distance=96,
        route_max_ticks=180,
        stop_on_blocked=args.stop_on_blocked,
        loop_delay=args.loop_delay,
        prefer_known_rocks=True,
        run_off_when_full=True,
    )


def coal_site(args):
    rocks = []
    try:
        rocks = mining_runner.rock_objects(
            mining_runner.bounds_around(DEFAULT_COAL_SITE_TILE, args.rock_scan_distance),
            ["coal"],
            99,
        )
    except Exception:
        rocks = []
    return {
        "id": "dwarven_mine_coal",
        "source": "manual-wrapper",
        "bankPlace": FALADOR_EAST_BANK,
        "bankName": "Falador East Bank",
        "bankTile": FALADOR_EAST_BANK_TILE,
        "tile": DEFAULT_COAL_SITE_TILE,
        "arrivalRadius": args.arrival_radius,
        "rockScanDistance": args.rock_scan_distance,
        "oreCounts": {"coal": len(rocks) or 10},
        "rockCount": len(rocks) or 10,
        "bankDistance": 0,
        "currentDistance": 0,
        "score": 0,
        "rocks": rocks,
    }


def ensure_pickaxe_when_needed(player, args, mining_args_obj, site, handle, reason):
    equipped_pickaxe = mining_runner.best_usable_pickaxe(player, equipped=True)
    carried_pickaxes = [item_id for item_id in inventory_ids(player) if item_id in mining_runner.PICKAXE_ITEM_IDS]
    if equipped_pickaxe and not carried_pickaxes:
        write(handle, "pickaxe_check", {
            "reason": reason,
            "decision": "skip_equipped_clean",
            "pickaxe": equipped_pickaxe,
            "player": compact(player),
        })
        return player
    full_player = observe_full(args.profile)
    player = mining_runner.ensure_pickaxe(full_player, site, mining_args_obj, handle)
    write(handle, "pickaxe_check", {
        "reason": reason,
        "decision": "ensure_pickaxe",
        "player": compact(player),
    })
    return player


def bank_inventory(args, mining_args_obj, site, handle, force=False):
    player = observe(args.profile)
    item_ids = [item_id for item_id in inventory_ids(player) if item_id not in mining_runner.PICKAXE_ITEM_IDS]
    if not force and not item_ids:
        return player
    player = mining_runner.ensure_run(player, mining_args_obj, handle, "bank_trip")
    player = route_bank(args, handle, player)
    item_ids = [item_id for item_id in inventory_ids(player) if item_id not in mining_runner.PICKAXE_ITEM_IDS]
    for item_id in ALL_MINING_PRODUCT_IDS:
        if item_id in inventory_ids(player) and item_id not in item_ids:
            item_ids.append(item_id)
    if item_ids:
        result = bridge.call_tool("deposit_inventory_items_XS", {"itemIds": item_ids}, profile=args.profile)
        player = player_from_or_observe(result, args.profile, player)
        write(handle, "bank_inventory", {
            "itemIds": item_ids,
            "success": bool(result.get("success")),
            "deposited": result.get("deposited"),
            "depositedAmount": result.get("depositedAmount"),
            "message": result.get("message"),
            "player": compact(player),
        })
    return ensure_pickaxe_when_needed(player, args, mining_args_obj, site, handle, "after_bank")


def run(args):
    mining_runner.RUN_PROFILE = args.profile or ""
    mining_args_obj = mine_args(args)
    site = coal_site(args)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-dwarven-mine-coal-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    handle = None if args.no_log else run_path.open("a", encoding="utf-8")
    loads_done = 0
    batches_done = 0
    try:
        player = observe(args.profile)
        write(handle, "run_start", {
            "args": vars(args),
            "site": site,
            "player": compact(player),
            "logPath": str(run_path),
        })
        log("Dwarven Mine coal runner log: {}".format(run_path), args)
        if int(player.get("freeInventorySlots", 0) or 0) < 1 or (
            not is_underground(player)
            and any(item_id not in mining_runner.PICKAXE_ITEM_IDS for item_id in inventory_ids(player))
        ):
            player = bank_inventory(args, mining_args_obj, site, handle, force=True)
        else:
            player = ensure_pickaxe_when_needed(player, args, mining_args_obj, site, handle, "startup")
        while True:
            if args.target_mining_level and mining_runner.mining_level(player) >= args.target_mining_level:
                write(handle, "target_reached", {"player": compact(player)})
                log("target mining level reached: {}".format(mining_runner.mining_level(player)), args)
                break
            if args.max_loads is not None and loads_done >= args.max_loads:
                break
            if args.max_mining_batches is not None and batches_done >= args.max_mining_batches:
                break
            if bool(player.get("isDead")) or bool(player.get("isInCombat")):
                write(handle, "safety_stop", {"player": compact(player)})
                raise RuntimeError("stopping because the player is dead or in combat")
            player = mining_runner.ensure_run(player, mining_args_obj, handle, "dwarven_coal_loop")
            player = enter_mine(args, handle, player)
            player = walk_exact(site["tile"], args, handle, "coal_site", max_ticks=140, current_player=player)
            result = mining_runner.mine_batch("coal", site, mining_args_obj, handle, player)
            player = mining_runner.player_from(result)
            batches_done += 1
            if args.target_mining_level and mining_runner.mining_level(player) >= args.target_mining_level:
                player = bank_inventory(args, mining_args_obj, site, handle, force=True)
                write(handle, "target_reached", {"player": compact(player)})
                log("target mining level reached: {}".format(mining_runner.mining_level(player)), args)
                break
            if int(player.get("freeInventorySlots", 0) or 0) < 1:
                player = bank_inventory(args, mining_args_obj, site, handle, force=True)
                loads_done += 1
                log("banked Dwarven Mine coal load {} level={} xp={} run={}".format(
                    loads_done,
                    mining_runner.mining_level(player),
                    mining_runner.mining_xp(player),
                    player.get("runEnergy"),
                ), args)
            elif result.get("batchStatus") == "blocked":
                write(handle, "blocked", {"message": result.get("message"), "player": compact(player)})
                if args.stop_on_blocked:
                    raise RuntimeError("mining blocked: {}".format(result.get("message")))
                time.sleep(max(0.0, args.loop_delay))
            else:
                time.sleep(max(0.0, args.loop_delay))
        write(handle, "run_finish", {
            "loadsDone": loads_done,
            "batchesDone": batches_done,
            "player": compact(player),
        })
        return 0
    finally:
        if handle is not None:
            handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mine coal in Dwarven Mine and bank at Falador East Bank.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--target-mining-level", type=int, default=0)
    parser.add_argument("--max-loads", type=int)
    parser.add_argument("--max-mining-batches", type=int)
    parser.add_argument("--arrival-radius", type=int, default=24)
    parser.add_argument("--rock-scan-distance", type=int, default=28)
    parser.add_argument("--mine-max-ticks", type=int, default=300)
    parser.add_argument("--direct-walk-max-distance", type=int, default=96)
    parser.add_argument("--min-run-energy", type=int, default=1)
    parser.add_argument("--no-enable-run", action="store_true")
    parser.add_argument("--combat-level", type=int, default=0)
    parser.add_argument("--food", type=int, default=0)
    parser.add_argument("--loop-delay", type=float, default=0.05)
    parser.add_argument("--stop-on-blocked", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
