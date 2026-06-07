#!/usr/bin/env python3
"""String banked yew longbow (u) into yew longbows using bow strings."""

import argparse
import datetime as dt
import json
import os
import sys
import time
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
from profile_utils import resolve_profile, safe_profile  # noqa: E402


YEW_LONGBOW_U = 66
BOW_STRING = 1777
YEW_LONGBOW = 855
WITHDRAW_ITEM_BUTTON = 21011
RUNS_DIR = ROOT / "data" / "fletching" / "yew-stringing-runs"
CONTROL_DIR = ROOT / ".local" / "runners"


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def run_stem(profile):
    return "yew-longbow-stringer-{}".format(safe_profile(profile or "default"))


def status_path(profile):
    return CONTROL_DIR / "{}.status.json".format(run_stem(profile))


def stop_path(profile):
    return CONTROL_DIR / "{}.stop".format(run_stem(profile))


def write_event(handle, event, data):
    payload = {"ts": utc_now(), "event": event}
    payload.update(data)
    handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def timed_tool(profile, handle, event, tool, arguments=None, extra=None):
    started = time.monotonic()
    result = bridge.call_tool(tool, arguments or {}, profile=profile)
    wall_ms = int((time.monotonic() - started) * 1000)
    if handle is not None and event:
        payload = {
            "tool": tool,
            "wallMs": wall_ms,
            "success": bool(result.get("success", True)),
            "message": result.get("message"),
            "serverTick": result.get("serverTick"),
        }
        if extra:
            payload.update(extra)
        write_event(handle, event, payload)
    result["_wallMs"] = wall_ms
    return result


def player_from(result, profile, fallback=None):
    try:
        return bridge.player_from(result)
    except RuntimeError:
        return fallback or bridge.observe_xs(profile=profile)


def inventory_count(player, item_id):
    return bridge.count_inventory_item(player, item_id)


def compact(player):
    data = bridge.compact_player(player, ("fletching",))
    data.update({
        "yewLongbowU": inventory_count(player, YEW_LONGBOW_U),
        "bowStrings": inventory_count(player, BOW_STRING),
        "yewLongbows": inventory_count(player, YEW_LONGBOW),
    })
    return data


def bank_counts(profile):
    result = bridge.call_tool("bank_item_count_XS", {
        "itemIds": [YEW_LONGBOW_U, BOW_STRING, YEW_LONGBOW],
    }, profile=profile)
    counts = {YEW_LONGBOW_U: 0, BOW_STRING: 0, YEW_LONGBOW: 0}
    for item in result.get("items") or []:
        item_id = int(item.get("itemId", item.get("id", -1)) or -1)
        if item_id in counts:
            counts[item_id] = int(item.get("bankAmount", item.get("amount", 0)) or 0)
    return counts


def write_status(args, phase, player, run_path=None, extra=None, counts=None, refresh_counts=True):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    if counts is None and refresh_counts:
        counts = bank_counts(args.profile)
    if counts is None:
        counts = {YEW_LONGBOW_U: None, BOW_STRING: None, YEW_LONGBOW: None}
    possible_bows = None
    if counts[YEW_LONGBOW_U] is not None and counts[BOW_STRING] is not None:
        possible_bows = min(counts[YEW_LONGBOW_U], counts[BOW_STRING])
    payload = {
        "ok": True,
        "runner": "yew_longbow_stringer",
        "updatedAt": utc_now(),
        "phase": phase,
        "profile": args.profile,
        "pid": os.getpid(),
        "stopRequested": stop_path(args.profile).exists(),
        "runLog": str(run_path) if run_path else None,
        "player": compact(player) if player else None,
        "bankedYewLongbowU": counts[YEW_LONGBOW_U],
        "bankedBowStrings": counts[BOW_STRING],
        "bankedYewLongbows": counts[YEW_LONGBOW],
        "possibleBows": possible_bows,
        "args": vars(args),
    }
    if extra:
        payload.update(extra)
    status_path(args.profile).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                                         encoding="utf-8")


def print_status(args):
    payload = {
        "statusPath": str(status_path(args.profile)),
        "stopPath": str(stop_path(args.profile)),
        "stopRequested": stop_path(args.profile).exists(),
    }
    if status_path(args.profile).exists():
        payload["status"] = json.loads(status_path(args.profile).read_text(encoding="utf-8"))
    else:
        payload["error"] = "no_status"
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def request_stop(args):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    stop_path(args.profile).write_text(utc_now() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "stopRequested": True, "stopPath": str(stop_path(args.profile))},
                     indent=2, sort_keys=True))
    return 0


def clear_stop(args):
    path = stop_path(args.profile)
    if path.exists():
        path.unlink()
    print(json.dumps({"ok": True, "stopRequested": False, "stopPath": str(path)}, indent=2, sort_keys=True))
    return 0


def close_interfaces(profile, handle, reason):
    result = timed_tool(profile, handle, "tool_timing", "close_interfaces", {}, {"reason": reason})
    player = player_from(result, profile)
    write_event(handle, "close_interfaces", {
        "reason": reason,
        "success": bool(result.get("success")),
        "player": compact(player),
    })
    return player


def ensure_bank_area(args, handle, reason, player=None):
    if player is None:
        player = bridge.observe_xs(profile=args.profile)
    if not bool(player.get("inBankArea", False)):
        close_interfaces(args.profile, handle, reason + "_before_route")
        bridge.route_to(args.bank, profile=args.profile, handle=handle, reason=reason + "_route",
                        extra_args={"runner_max_batches": args.route_max_batches,
                                    "max_batch_distance": args.max_batch_distance})
        player = bridge.observe_xs(profile=args.profile)
    return player


def open_bank_only(args, handle, reason, player=None):
    player = ensure_bank_area(args, handle, reason, player=player)
    result = timed_tool(args.profile, handle, "tool_timing", "deposit_inventory_items_XS",
                        {"name": "__codex_open_bank_only__"}, {"reason": reason, "bankOpenOnly": True})
    player = player_from(result, args.profile, player)
    write_event(handle, "open_bank", {
        "reason": reason,
        "success": bool(result.get("success")),
        "player": compact(player),
    })
    return player


def deposit_relevant_inventory(args, handle, player, reason):
    before_counts = {
        YEW_LONGBOW_U: inventory_count(player, YEW_LONGBOW_U),
        BOW_STRING: inventory_count(player, BOW_STRING),
        YEW_LONGBOW: inventory_count(player, YEW_LONGBOW),
    }
    item_ids = [
        item_id for item_id in (YEW_LONGBOW_U, BOW_STRING, YEW_LONGBOW)
        if inventory_count(player, item_id) > 0
    ]
    if not item_ids:
        return player, {YEW_LONGBOW_U: 0, BOW_STRING: 0, YEW_LONGBOW: 0}
    result = timed_tool(args.profile, handle, "tool_timing", "deposit_inventory_items_XS",
                        {"itemIds": item_ids}, {"reason": reason, "itemIds": item_ids})
    player = player_from(result, args.profile, player)
    deposited = {
        item_id: max(0, before_counts[item_id] - inventory_count(player, item_id))
        for item_id in before_counts
    }
    write_event(handle, "deposit_relevant_inventory", {
        "reason": reason,
        "itemIds": item_ids,
        "success": bool(result.get("success")),
        "depositedAmount": result.get("depositedAmount"),
        "depositedById": deposited,
        "wallMs": result.get("_wallMs"),
        "player": compact(player),
    })
    return player, deposited


def set_item_withdraw_mode(args, handle, player):
    result = timed_tool(args.profile, handle, "tool_timing", "click_interface_button_XXS",
                        {"buttonId": WITHDRAW_ITEM_BUTTON}, {"reason": "set_withdraw_item_mode"})
    player = player_from(result, args.profile, player)
    write_event(handle, "set_withdraw_item_mode", {
        "buttonId": WITHDRAW_ITEM_BUTTON,
        "success": bool(result.get("success")),
        "player": compact(player),
    })
    return player


def withdraw_batch(args, handle, player, counts, withdraw_mode_ready, bank_interface_ready=False):
    possible = min(counts[YEW_LONGBOW_U], counts[BOW_STRING], int(args.batch_size))
    free_slots = int(player.get("freeInventorySlots", player.get("freeSlots", 0)) or 0)
    possible = min(possible, free_slots // 2)
    if possible <= 0:
        return player, 0, counts, withdraw_mode_ready
    if not withdraw_mode_ready:
        if not bank_interface_ready:
            player = open_bank_only(args, handle, "before_set_withdraw_mode", player=player)
        player = set_item_withdraw_mode(args, handle, player)
        withdraw_mode_ready = True
    for item_id, label in ((YEW_LONGBOW_U, "yew_longbow_u"), (BOW_STRING, "bow_string")):
        before = inventory_count(player, item_id)
        result = timed_tool(args.profile, handle, "tool_timing", "withdraw_bank_items_XS", {
            "itemId": item_id,
            "amount": possible,
        }, {"label": label, "itemId": item_id, "amount": possible})
        player = player_from(result, args.profile, player)
        write_event(handle, "withdraw_batch_item", {
            "label": label,
            "itemId": item_id,
            "amount": possible,
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "withdrawnAmount": result.get("withdrawnAmount"),
            "wallMs": result.get("_wallMs"),
            "before": before,
            "after": inventory_count(player, item_id),
            "player": compact(player),
        })
    actual = min(inventory_count(player, YEW_LONGBOW_U), inventory_count(player, BOW_STRING))
    return player, actual, counts, withdraw_mode_ready


def string_inventory(args, handle, player, batch_count):
    if batch_count <= 0:
        return player, 0
    before_u = inventory_count(player, YEW_LONGBOW_U)
    before_strings = inventory_count(player, BOW_STRING)
    before_bows = inventory_count(player, YEW_LONGBOW)
    before_xp = bridge.skill_xp(player, "fletching")
    result = timed_tool(args.profile, handle, "tool_timing", "use_item_on_item", {
        "itemId": BOW_STRING,
        "targetItemId": YEW_LONGBOW_U,
    }, {"batchCount": batch_count})
    player = player_from(result, args.profile, player)
    expected_ticks = max(1, int(batch_count) * int(args.string_ticks_per_bow) + int(args.string_startup_ticks))
    remaining_ticks = expected_ticks
    wait_wall_ms = 0
    wait_chunks = []
    wait = {}
    while remaining_ticks > 0:
        chunk = min(25, remaining_ticks)
        wait = timed_tool(args.profile, handle, "tool_timing", "wait_ticks_XS", {"ticks": chunk},
                          {"batchCount": batch_count, "expectedTicks": expected_ticks, "chunkTicks": chunk})
        player = player_from(wait, args.profile, player)
        wait_wall_ms += int(wait.get("_wallMs", 0) or 0)
        wait_chunks.append({
            "requested": chunk,
            "waitedTicks": wait.get("waitedTicks"),
            "serverTick": wait.get("serverTick"),
            "wallMs": wait.get("_wallMs"),
        })
        remaining_ticks -= chunk
    fallback_wait = None
    if args.verify_stringing:
        player = bridge.observe_xs(profile=args.profile)
    made = max(0, inventory_count(player, YEW_LONGBOW) - before_bows)
    if made < int(batch_count) and inventory_count(player, YEW_LONGBOW_U) > 0 and inventory_count(player, BOW_STRING) > 0:
        fallback_wait = timed_tool(args.profile, handle, "tool_timing", "wait_until_idle_XS", {
            "maxTicks": max(6, (int(batch_count) - made) * int(args.string_ticks_per_bow) + 6),
            "movement": False,
            "skilling": True,
            "combat": False,
        }, {"batchCount": batch_count, "reason": "stringing_fallback"})
        player = player_from(fallback_wait, args.profile, player)
        made = max(0, inventory_count(player, YEW_LONGBOW) - before_bows)
    write_event(handle, "string_inventory", {
        "requested": batch_count,
        "useSuccess": bool(result.get("success")),
        "useMessage": result.get("message"),
        "waitMode": "exact_ticks",
        "verified": bool(args.verify_stringing),
        "expectedTicks": expected_ticks,
        "waitChunks": wait_chunks,
        "waitStatus": wait.get("batchStatus"),
        "waitTicks": wait.get("batchTicks", wait.get("ticks")),
        "waitWallMs": wait_wall_ms,
        "fallbackWaitStatus": fallback_wait.get("batchStatus") if fallback_wait else None,
        "fallbackWaitTicks": fallback_wait.get("batchTicks") if fallback_wait else None,
        "fallbackWaitWallMs": fallback_wait.get("_wallMs") if fallback_wait else None,
        "beforeYewLongbowU": before_u,
        "afterYewLongbowU": inventory_count(player, YEW_LONGBOW_U),
        "beforeBowStrings": before_strings,
        "afterBowStrings": inventory_count(player, BOW_STRING),
        "beforeYewLongbows": before_bows,
        "afterYewLongbows": inventory_count(player, YEW_LONGBOW),
        "made": made,
        "beforeFletchingXp": before_xp,
        "afterFletchingXp": bridge.skill_xp(player, "fletching"),
        "player": compact(player),
    })
    return player, made


def run(args, handle, run_path):
    started = bridge.observe_xs(profile=args.profile)
    counts = bank_counts(args.profile)
    write_status(args, "started", started, run_path, counts=counts)
    total_made = 0
    cycles = 0
    player = started
    withdraw_mode_ready = False
    while cycles < int(args.max_cycles):
        if stop_path(args.profile).exists():
            write_event(handle, "stop_requested", {"totalMade": total_made, "player": compact(player)})
            write_status(args, "stopped", player, run_path, {"totalMade": total_made})
            return total_made, "stopped"
        cycle_started = time.monotonic()
        player = ensure_bank_area(args, handle, "cycle_bank", player=player)
        player, deposited = deposit_relevant_inventory(args, handle, player, "cycle_start")
        bank_interface_ready = any(int(amount or 0) > 0 for amount in deposited.values())
        for item_id, amount in deposited.items():
            counts[item_id] = max(0, int(counts.get(item_id, 0) or 0) + int(amount))
        possible = min(counts[YEW_LONGBOW_U], counts[BOW_STRING])
        remaining_target = None
        if args.target_count > 0:
            remaining_target = max(0, int(args.target_count) - total_made)
            possible = min(possible, remaining_target)
        write_status(args, "cycle_start", player, run_path, {
            "cycle": cycles + 1,
            "totalMade": total_made,
            "possibleThisRun": possible,
        }, counts=counts)
        if possible <= 0:
            write_event(handle, "done_no_supplies", {
                "totalMade": total_made,
                "bankCounts": counts,
                "remainingTarget": remaining_target,
                "player": compact(player),
            })
            write_status(args, "done", player, run_path, {"totalMade": total_made, "reason": "no_supplies"})
            return total_made, "no_supplies"
        player, batch_count, counts, withdraw_mode_ready = withdraw_batch(
            args, handle, player, counts, withdraw_mode_ready, bank_interface_ready=bank_interface_ready)
        if batch_count <= 0:
            write_event(handle, "blocked", {"reason": "could_not_withdraw_batch", "bankCounts": counts,
                                            "player": compact(player)})
            write_status(args, "blocked", player, run_path, {"totalMade": total_made,
                                                             "reason": "could_not_withdraw_batch"})
            return total_made, "blocked"
        counts[YEW_LONGBOW_U] = max(0, counts[YEW_LONGBOW_U] - batch_count)
        counts[BOW_STRING] = max(0, counts[BOW_STRING] - batch_count)
        write_status(args, "withdrawing", player, run_path, {
            "cycle": cycles + 1,
            "totalMade": total_made,
            "batchCount": batch_count,
        }, counts=counts, refresh_counts=False)
        close_interfaces(args.profile, handle, "before_string_inventory")
        expected_ticks = max(1, int(batch_count) * int(args.string_ticks_per_bow) + int(args.string_startup_ticks))
        write_status(args, "stringing", player, run_path, {
            "cycle": cycles + 1,
            "totalMade": total_made,
            "batchCount": batch_count,
            "expectedTicks": expected_ticks,
            "expectedSeconds": round(expected_ticks * 0.6, 1),
        }, counts=counts, refresh_counts=False)
        player, made = string_inventory(args, handle, player, batch_count)
        total_made += made
        cycles += 1
        cycle_ms = int((time.monotonic() - cycle_started) * 1000)
        write_event(handle, "cycle_done", {
            "cycle": cycles,
            "totalMade": total_made,
            "made": made,
            "cycleWallMs": cycle_ms,
            "bowsPerHour": int((made * 3600000) / cycle_ms) if cycle_ms > 0 else None,
            "cachedBankCounts": counts,
            "player": compact(player),
        })
        if made <= 0:
            write_event(handle, "blocked", {"reason": "no_bows_stringed", "player": compact(player)})
            write_status(args, "blocked", player, run_path, {"totalMade": total_made,
                                                             "reason": "no_bows_stringed"})
            return total_made, "blocked"
        if float(args.cycle_delay) > 0:
            time.sleep(float(args.cycle_delay))
    player = ensure_bank_area(args, handle, "final_bank", player=player)
    player, deposited = deposit_relevant_inventory(args, handle, player, "final")
    for item_id, amount in deposited.items():
        counts[item_id] = max(0, int(counts.get(item_id, 0) or 0) + int(amount))
    write_status(args, "done", player, run_path, {"totalMade": total_made, "reason": "max_cycles"}, counts=counts)
    return total_made, "max_cycles"


def main(argv=None):
    parser = argparse.ArgumentParser(description="String banked yew longbow (u) using banked bow strings.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--bank", default="falador_east_bank")
    parser.add_argument("--batch-size", type=int, default=14)
    parser.add_argument("--target-count", type=int, default=0,
                        help="Stop after this many yew longbows; 0 means all currently possible supplies.")
    parser.add_argument("--max-cycles", type=int, default=100000)
    parser.add_argument("--route-max-batches", type=int, default=10)
    parser.add_argument("--max-batch-distance", type=int, default=32)
    parser.add_argument("--cycle-delay", type=float, default=0.0)
    parser.add_argument("--string-ticks-per-bow", type=int, default=3,
                        help="Server stringing cadence. wait_ticks_XS is chunked because the bridge caps one call at 25 ticks.")
    parser.add_argument("--string-startup-ticks", type=int, default=0,
                        help="Extra ticks before banking after the expected final product appears.")
    parser.add_argument("--verify-stringing", action=argparse.BooleanOptionalAction, default=False,
                        help="Observe and fall back to wait_until_idle after exact ticks. Slower, useful for debugging.")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--request-stop", action="store_true")
    parser.add_argument("--clear-stop", action="store_true")
    args = parser.parse_args(argv)

    if args.status:
        return print_status(args)
    if args.request_stop:
        return request_stop(args)
    if args.clear_stop:
        return clear_stop(args)
    if stop_path(args.profile).exists():
        stop_path(args.profile).unlink()

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / "{}-yew-stringing-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        uuid.uuid4().hex[:8],
    )
    with run_path.open("a", encoding="utf-8") as handle:
        write_event(handle, "start", {"args": vars(args), "runLog": str(run_path)})
        made, reason = run(args, handle, run_path)
        player = bridge.observe_xs(profile=args.profile)
        summary = {
            "ok": reason not in ("blocked",),
            "reason": reason,
            "made": made,
            "player": compact(player),
            "runLog": str(run_path),
        }
        write_event(handle, "summary", summary)
        print(json.dumps(summary, sort_keys=True))
        return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
