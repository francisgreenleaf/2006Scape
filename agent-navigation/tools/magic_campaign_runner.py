#!/usr/bin/env python3
"""Long-running Magic training campaign with rune restocks."""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bridge_script as bridge
from magic_training_runner import DEFAULT_WITHDRAW
from profile_utils import resolve_profile, safe_profile


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
ML2_DEFINE = ROOT / "ml2-routing" / "route_ml_XS.py"
RUNS_DIR = ROOT / "data" / "magic" / "campaign-runs"
STATUS_DIR = ROOT / ".local" / "runners"

COINS = 995
FIRE = 554
WATER = 555
AIR = 556
EARTH = 557
MIND = 558
DEATH = 560
CHAOS = 562
LAW = 563
STAFF_OF_AIR = 1381
SWORDFISH = 373

FALADOR_TELEPORT_BUTTON = 4146
BETTY_TILE = {"x": 3015, "y": 3259, "height": 0}
DRAYNOR_BANK = "draynor_bank"
DRAYNOR_JAIL_GUARDS_TILE = "3113,3240,0"

BETTY_BUYS = [
    (DEATH, 250),
    (CHAOS, 250),
    (FIRE, 5000),
    (WATER, 5000),
    (EARTH, 5000),
    (MIND, 3000),
]


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_event(handle, event, data):
    if handle is None:
        return
    row = {"ts": utc_now(), "event": event}
    row.update(data or {})
    handle.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")
    handle.flush()


def update_status(args, **data):
    path = status_path(args.profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updatedAt": utc_now(), "profile": args.profile}
    payload.update(data)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def status_path(profile):
    return STATUS_DIR / "magic-campaign-{}.status.json".format(safe_profile(profile))


def compact(player):
    return bridge.compact_player(player, ("magic", "hitpoints"))


def tile(player):
    return {
        "x": int(player.get("x", 0) or 0),
        "y": int(player.get("y", 0) or 0),
        "height": int(player.get("height", player.get("h", 0)) or 0),
    }


def tile_string(value):
    return "{},{},{}".format(int(value["x"]), int(value["y"]), int(value.get("height", 0) or 0))


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


def chebyshev(a, b):
    if int(a.get("height", 0) or 0) != int(b.get("height", 0) or 0):
        return 999999
    return max(abs(int(a["x"]) - int(b["x"])), abs(int(a["y"]) - int(b["y"])))


def run_command(command, profile, handle, event, meta=None, expect_json=True):
    env = os.environ.copy()
    if profile:
        env["RS_PROFILE"] = profile
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    data = {
        "command": command,
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout[-2000:],
        "stderrTail": proc.stderr[-2000:],
    }
    if meta:
        data.update(meta)
    write_event(handle, event, data)
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(event, proc.stderr.strip() or proc.stdout.strip()))
    if not expect_json:
        return proc.stdout
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("{} returned invalid JSON: {}".format(event, exc))


def observe(profile):
    return bridge.observe_xs(profile=profile)


def player_from_or_observe(result, profile, fallback=None):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return fallback or observe(profile)


def bank_counts(profile):
    result = bridge.call_tool("bank_item_count_XS", {
        "itemIds": [COINS, FIRE, WATER, AIR, EARTH, MIND, DEATH, CHAOS, LAW, STAFF_OF_AIR, SWORDFISH],
    }, profile=profile)
    counts = {}
    for item in result.get("items") or []:
        item_id = int(item.get("itemId", item.get("id", -1)) or -1)
        counts[item_id] = {
            "bank": int(item.get("bankAmount", 0) or 0),
            "inventory": int(item.get("inventoryAmount", 0) or 0),
            "equipment": int(item.get("equipmentAmount", 0) or 0),
            "total": int(item.get("totalAmount", item.get("amount", 0)) or 0),
        }
    return counts, player_from_or_observe(result, profile)


def banked_coins(profile):
    counts, _player = bank_counts(profile)
    return counts.get(COINS, {}).get("bank", 0)


def can_falador_teleport(player):
    if bridge.skill_level(player, "magic") < 37:
        return False
    inv = bridge.inventory_counts(player)
    if inv.get(LAW, 0) < 1 or inv.get(WATER, 0) < 1:
        return False
    has_air_staff = any(int(item.get("id", item.get("itemId", -1)) or -1) == STAFF_OF_AIR for item in bridge.equipment(player))
    return has_air_staff or inv.get(AIR, 0) >= 3


def maybe_falador_teleport(player, args, handle, reason):
    if not args.use_teleports:
        return player
    if chebyshev(tile(player), BETTY_TILE) < 220:
        return player
    if not can_falador_teleport(player):
        return player
    result = bridge.call_tool("click_interface_button_XS", {"buttonId": FALADOR_TELEPORT_BUTTON}, profile=args.profile)
    player = player_from_or_observe(result, args.profile, player)
    before = tile(player)
    write_event(handle, "falador_teleport", {
        "reason": reason,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact(player),
    })
    time.sleep(2.5)
    player = observe(args.profile)
    write_event(handle, "falador_teleport_result", {
        "reason": reason,
        "changedTile": tile(player) != before,
        "player": compact(player),
    })
    return player


def maybe_cross_taverley_gate_east(args, handle):
    player = observe(args.profile)
    if tile_string(tile(player)) not in ("2934,3451,0", "2935,3451,0"):
        return player
    try:
        result = bridge.call_tool("object_transition_step_XS", {
            "objectId": 1596,
            "x": 2935,
            "y": 3451,
            "height": 0,
            "postX": 2936,
            "postY": 3451,
            "postHeight": 0,
            "maxTicks": 20,
        }, profile=args.profile)
        player = player_from_or_observe(result, args.profile, player)
        write_event(handle, "taverley_gate_recovery_interact", {
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact(player),
        })
    except RuntimeError as exc:
        write_event(handle, "taverley_gate_recovery_interact_failed", {"error": str(exc), "player": compact(player)})
    result = bridge.call_tool("walk_path_steps_XS", {
        "steps": [
            {"x": 2935, "y": 3451, "height": 0},
            {"x": 2936, "y": 3451, "height": 0},
        ],
        "allowObjectTransition": True,
        "run": False,
        "maxTicks": 20,
    }, profile=args.profile)
    player = player_from_or_observe(result, args.profile, player)
    bridge.call_tool("wait_ticks_XXS", {"ticks": 4}, profile=args.profile)
    player = observe(args.profile)
    write_event(handle, "taverley_gate_recovery_walk", {"player": compact(player)})
    return player


def ml2_route_to(target, args, handle, reason, arrival_radius=2):
    target_tile = parse_tile(target) or (BETTY_TILE if str(target) == tile_string(BETTY_TILE) else None)
    last_tile = ""
    last_error = None
    for attempt in range(1, args.route_attempts + 1):
        player = observe(args.profile)
        if target_tile and chebyshev(tile(player), target_tile) <= arrival_radius:
            return player
        if args.enable_run and int(player.get("runEnergy", 0) or 0) >= args.min_route_run_energy and not player.get("runEnabled"):
            result = bridge.call_tool("set_run_XXS", {"enabled": True}, profile=args.profile)
            player = player_from_or_observe(result, args.profile, player)
        current_tile = tile_string(tile(player))
        if current_tile == last_tile and attempt > 1:
            maybe_cross_taverley_gate_east(args, handle)
            player = observe(args.profile)
            current_tile = tile_string(tile(player))
        last_tile = current_tile
        carried_food = bridge.inventory_counts(player).get(SWORDFISH, int(player.get("foodCount", player.get("food", 0)) or 0))
        command = [
            "python3",
            str(ML2_DEFINE),
            "define",
            "--from",
            current_tile,
            "--to",
            str(target),
            "--combat-level",
            str(int(player.get("combatLevel", player.get("cb", 3)) or 3)),
            "--food",
            str(int(carried_food)),
            "--run-energy",
            str(int(player.get("runEnergy", 0) or 0)),
        ]
        if player.get("runEnabled"):
            command.append("--run-enabled")
        definition = run_command(command, args.profile, handle, "ml2_route_define", {
            "attempt": attempt,
            "reason": reason,
            "target": str(target),
            "player": compact(player),
        })
        if definition.get("status") not in ("ok", "no-learned-route") or not definition.get("path"):
            raise RuntimeError("ML2 route to {} was not executable: {}".format(target, definition.get("status")))
        if definition.get("safety", {}).get("review"):
            write_event(handle, "ml2_safety_review", {
                "attempt": attempt,
                "reason": reason,
                "target": str(target),
                "notes": definition.get("safety", {}).get("notes"),
                "decision": definition.get("decision"),
            })
        route_path = REPO_ROOT / definition["path"]
        route_definition = json.loads(route_path.read_text(encoding="utf-8"))
        exec_command = route_definition.get("execution", {}).get("command")
        if not exec_command:
            raise RuntimeError("ML2 route definition did not contain an execution command: {}".format(route_path))
        bridge.call_tool("close_interfaces", {}, profile=args.profile)
        try:
            run_command(exec_command, args.profile, handle, "ml2_route_execute", {
                "attempt": attempt,
                "reason": reason,
                "target": str(target),
                "routePath": str(route_path),
                "routeId": definition.get("id"),
            }, expect_json=False)
            return observe(args.profile)
        except RuntimeError as exc:
            last_error = exc
            write_event(handle, "ml2_route_retry", {
                "attempt": attempt,
                "reason": reason,
                "target": str(target),
                "error": str(exc)[-1000:],
                "player": compact(observe(args.profile)),
            })
            maybe_cross_taverley_gate_east(args, handle)
            continue
    raise RuntimeError("ML2 route to {} failed after {} attempts: {}".format(target, args.route_attempts, last_error))


def route_to_betty(args, handle):
    player = observe(args.profile)
    player = maybe_falador_teleport(player, args, handle, "supply_trip")
    return ml2_route_to(tile_string(BETTY_TILE), args, handle, "betty_supply_shop", arrival_radius=5)


def withdraw_purchase_coins(args, handle):
    counts, player = bank_counts(args.profile)
    bank_gp = counts.get(COINS, {}).get("bank", 0)
    spendable = max(0, bank_gp - args.min_bank_gp)
    if spendable <= 0:
        raise RuntimeError("banked gp is at or below configured floor")
    amount = min(args.purchase_budget, spendable)
    try:
        result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": COINS, "amount": amount}, profile=args.profile)
        if not result.get("success"):
            raise RuntimeError(result.get("message", "withdraw coins failed"))
        player = player_from_or_observe(result, args.profile, player)
    except RuntimeError:
        player = ml2_route_to(args.supply_bank, args, handle, "bank_before_supply", arrival_radius=4)
        result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": COINS, "amount": amount}, profile=args.profile)
        if not result.get("success"):
            raise RuntimeError(result.get("message", "withdraw coins failed"))
        player = player_from_or_observe(result, args.profile, player)
    write_event(handle, "withdraw_purchase_coins", {
        "amount": amount,
        "bankGpBefore": bank_gp,
        "player": compact(player),
    })
    return player


def buy_runes_at_betty(args, handle):
    player = withdraw_purchase_coins(args, handle)
    player = route_to_betty(args, handle)
    opened = bridge.call_tool("open_nearest_shop", {"name": "betty", "maxDistance": 12}, profile=args.profile)
    player = player_from_or_observe(opened, args.profile, player)
    write_event(handle, "open_betty_shop", {
        "success": bool(opened.get("success")),
        "message": opened.get("message"),
        "player": compact(player),
    })
    if not opened.get("success"):
        raise RuntimeError("could not open Betty's rune shop")
    for item_id, amount in BETTY_BUYS:
        result = bridge.call_tool("buy_shop_item", {"itemId": item_id, "amount": amount}, profile=args.profile)
        player = player_from_or_observe(result, args.profile, player)
        write_event(handle, "buy_runes", {
            "itemId": item_id,
            "requested": amount,
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "player": compact(player),
        })
    bridge.call_tool("close_interfaces", {}, profile=args.profile)
    player = ml2_route_to(DRAYNOR_BANK, args, handle, "bank_after_supply", arrival_radius=4)
    result = bridge.call_tool("deposit_inventory_items_XS", {"itemIds": [COINS], "keepFoodCount": args.food_count}, profile=args.profile)
    player = player_from_or_observe(result, args.profile, player)
    write_event(handle, "deposit_leftover_coins", {
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "player": compact(player),
    })
    return player


def needs_supply(args):
    counts, _player = bank_counts(args.profile)
    return supply_low(args, counts) and counts.get(COINS, {}).get("bank", 0) > args.min_bank_gp


def supply_low(args, counts):
    total_death = counts.get(DEATH, {}).get("total", 0)
    total_chaos = counts.get(CHAOS, {}).get("total", 0)
    total_fire = counts.get(FIRE, {}).get("total", 0)
    total_earth = counts.get(EARTH, {}).get("total", 0)
    return (
        total_death < args.min_death_runes
        or total_chaos < args.min_chaos_runes
        or total_fire < args.min_elemental_runes
        or total_earth < args.min_elemental_runes
    )


def has_staff(player):
    return any(int(item.get("id", item.get("itemId", -1)) or -1) == STAFF_OF_AIR for item in bridge.equipment(player))


def prepare_bank_loadout(args, handle):
    player = observe(args.profile)
    if not args.setup_bank:
        return player
    try:
        player, summary = bridge.execute_bank_policy(
            player,
            profile=args.profile,
            handle=handle,
            reason="magic_campaign_setup",
            deposit_all_ids=[COINS],
            food_item_ids=[SWORDFISH],
            keep_food_count=args.food_count,
        )
    except RuntimeError:
        player = ml2_route_to(DRAYNOR_BANK, args, handle, "bank_before_training", arrival_radius=4)
        player, summary = bridge.execute_bank_policy(
            player,
            profile=args.profile,
            handle=handle,
            reason="magic_campaign_setup",
            deposit_all_ids=[COINS],
            food_item_ids=[SWORDFISH],
            keep_food_count=args.food_count,
        )
    write_event(handle, "bank_policy_summary", summary)
    if not has_staff(player):
        inv = bridge.inventory_counts(player)
        if inv.get(STAFF_OF_AIR, 0) <= 0:
            result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": STAFF_OF_AIR, "amount": 1}, profile=args.profile)
            player = player_from_or_observe(result, args.profile, player)
        result = bridge.call_tool("equip_item", {"itemId": STAFF_OF_AIR}, profile=args.profile)
        player = player_from_or_observe(result, args.profile, player)
    inv = bridge.inventory_counts(player)
    for item_id, target in DEFAULT_WITHDRAW.items():
        carried = inv.get(item_id, 0)
        amount = max(0, int(target) - int(carried))
        if amount <= 0:
            continue
        result = bridge.call_tool("withdraw_bank_items_XS", {"itemId": int(item_id), "amount": int(amount)}, profile=args.profile)
        player = player_from_or_observe(result, args.profile, player)
        inv = bridge.inventory_counts(player)
        write_event(handle, "withdraw_training_runes", {
            "itemId": int(item_id),
            "requested": int(amount),
            "player": compact(player),
        })
    carried_food = bridge.inventory_counts(player).get(SWORDFISH, 0)
    if carried_food < args.food_count:
        result = bridge.call_tool("withdraw_bank_items_XS", {
            "itemId": SWORDFISH,
            "amount": args.food_count - carried_food,
        }, profile=args.profile)
        player = player_from_or_observe(result, args.profile, player)
    write_event(handle, "setup_bank_before_training", {"player": compact(player)})
    return player


def inventory_ready_for_training(player):
    inv = bridge.inventory_counts(player)
    if inv.get(COINS, 0) > 0:
        return False
    if inv.get(SWORDFISH, 0) < 3:
        return False
    if not has_staff(player):
        return False
    if inv.get(DEATH, 0) >= 10:
        return True
    if inv.get(CHAOS, 0) >= 10:
        return True
    return inv.get(MIND, 0) >= 20 and (inv.get(WATER, 0) >= 20 or inv.get(FIRE, 0) >= 20)


def run_training_batch(args, handle):
    player = observe(args.profile)
    if inventory_ready_for_training(player):
        write_event(handle, "skip_bank_ready_for_training", {"player": compact(player)})
    else:
        player = prepare_bank_loadout(args, handle)
    player = ml2_route_to(DRAYNOR_JAIL_GUARDS_TILE, args, handle, "draynor_jail_guards", arrival_radius=8)
    command = [
        "python3",
        str(SCRIPT_DIR / "magic_training_runner.py"),
        "--profile",
        args.profile,
        "--npc",
        args.npc,
        "--npc-max-distance",
        str(args.npc_max_distance),
        "--max-npc-max-hit",
        str(args.max_npc_max_hit),
        "--allow-under-attack",
        "--max-rounds",
        str(args.training_rounds),
        "--cast-wait-ticks",
        str(args.cast_wait_ticks),
        "--eat-at-hitpoints",
        str(args.eat_at_hitpoints),
        "--retreat-at-hitpoints",
        str(args.retreat_at_hitpoints),
        "--food-count",
        str(args.food_count),
        "--quiet",
    ]
    result = run_command(command, args.profile, handle, "magic_training_batch", {
        "player": compact(player),
    }, expect_json=False)
    return result


def run(args):
    if args.status:
        path = status_path(args.profile)
        if path.exists():
            print(path.read_text(encoding="utf-8").strip())
        else:
            print(json.dumps({"status": "missing", "path": str(path)}))
        return 0
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    with run_path.open("a", encoding="utf-8") as handle:
        update_status(args, phase="starting", log=str(run_path))
        write_event(handle, "campaign_start", {"args": vars(args), "player": compact(observe(args.profile))})
        batch = 0
        while batch < args.max_batches:
            counts, player = bank_counts(args.profile)
            gp = counts.get(COINS, {}).get("bank", 0)
            if gp <= args.min_bank_gp and supply_low(args, counts):
                update_status(args, phase="complete_gp_floor", bankGp=gp, log=str(run_path))
                write_event(handle, "campaign_stop", {"reason": "gp_floor", "bankGp": gp, "player": compact(player)})
                return 0
            if needs_supply(args):
                update_status(args, phase="buying_runes", bankGp=gp, log=str(run_path))
                buy_runes_at_betty(args, handle)
            batch += 1
            update_status(args, phase="training", batch=batch, bankGp=banked_coins(args.profile), log=str(run_path))
            run_training_batch(args, handle)
            time.sleep(max(0.0, args.batch_pause_seconds))
        update_status(args, phase="max_batches", batch=batch, bankGp=banked_coins(args.profile), log=str(run_path))
        write_event(handle, "campaign_stop", {"reason": "max_batches", "batches": batch})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Buy runes and train Magic until the configured gp floor.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--min-bank-gp", type=int, default=500000)
    parser.add_argument("--purchase-budget", type=int, default=220000)
    parser.add_argument("--supply-bank", default=DRAYNOR_BANK)
    parser.add_argument("--use-teleports", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--enable-run", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-route-run-energy", type=int, default=35)
    parser.add_argument("--route-attempts", type=int, default=6)
    parser.add_argument("--min-death-runes", type=int, default=150)
    parser.add_argument("--min-chaos-runes", type=int, default=100)
    parser.add_argument("--min-elemental-runes", type=int, default=300)
    parser.add_argument("--training-rounds", type=int, default=900)
    parser.add_argument("--max-batches", type=int, default=1000000)
    parser.add_argument("--batch-pause-seconds", type=float, default=1.0)
    parser.add_argument("--npc", default="Jail Guard")
    parser.add_argument("--npc-max-distance", type=int, default=45)
    parser.add_argument("--max-npc-max-hit", type=int, default=3)
    parser.add_argument("--cast-wait-ticks", type=int, default=8)
    parser.add_argument("--eat-at-hitpoints", type=int, default=24)
    parser.add_argument("--retreat-at-hitpoints", type=int, default=14)
    parser.add_argument("--food-count", type=int, default=8)
    parser.add_argument("--setup-bank", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    args.profile = resolve_profile(args.profile, default="")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
