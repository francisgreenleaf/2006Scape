#!/usr/bin/env python3
"""Alternate Seers yew fletching, flax spinning, and yew-longbow stringing.

This wrapper delegates to existing profile-scoped runners:
- seers_yew_longbow_runner.py for chopping yews and fletching yew longbow (u)
- seers_flax_spin_fast_runner.py for picking flax and spinning bow strings
- yew_longbow_stringer.py for making finished yew longbows
"""

import argparse
import datetime as dt
import json
import math
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
REPO_ROOT = SCRIPT_DIR.parents[1]
CONTROL_DIR = ROOT / ".local" / "runners"
RUNS_DIR = ROOT / "data" / "fletching" / "seers-yew-complete-bow-master-runs"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
from profile_utils import resolve_profile, safe_profile  # noqa: E402


YEW_RUNNER = SCRIPT_DIR / "seers_yew_longbow_runner.py"
FLAX_RUNNER = SCRIPT_DIR / "seers_flax_spin_fast_runner.py"
STRINGER = SCRIPT_DIR / "yew_longbow_stringer.py"

FLAX = 1779
BOW_STRING = 1777
YEW_LOGS = 1515
YEW_LONGBOW_U = 66
YEW_LONGBOW = 855
KNIFE = 946
BRONZE_AXE = 1351
RUNE_AXE = 1359
AXE_IDS = (RUNE_AXE, BRONZE_AXE)
SEERS_BANK_TARGET = "2727,3493,0"
TERMINAL_PHASES = {"blocked", "complete", "stopped"}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def run_stem(profile):
    return "seers-yew-complete-bow-master-{}".format(safe_profile(profile or "default"))


def status_path(profile):
    return CONTROL_DIR / "{}.status.json".format(run_stem(profile))


def stop_path(profile):
    return CONTROL_DIR / "{}.stop".format(run_stem(profile))


def child_env(profile):
    env = os.environ.copy()
    env["PROFILE"] = profile
    env["RS_PROFILE"] = profile
    env["RS_TRACE_PROFILE"] = profile
    return env


def write_jsonl(handle, event, data):
    payload = {"ts": utc_now(), "event": event}
    payload.update(data)
    handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def player_compact(profile):
    try:
        player = bridge.observe_xs(profile=profile)
    except Exception:
        return None
    data = bridge.compact_player(player, ("woodcutting", "fletching", "crafting"))
    data.update({
        "flax": bridge.count_inventory_item(player, FLAX),
        "bowStrings": bridge.count_inventory_item(player, BOW_STRING),
        "yewLogs": bridge.count_inventory_item(player, YEW_LOGS),
        "yewLongbowU": bridge.count_inventory_item(player, YEW_LONGBOW_U),
        "yewLongbows": bridge.count_inventory_item(player, YEW_LONGBOW),
    })
    return data


def material_counts(profile):
    result = bridge.call_tool("bank_item_count_XS", {
        "itemIds": [FLAX, BOW_STRING, YEW_LOGS, YEW_LONGBOW_U, YEW_LONGBOW, KNIFE, RUNE_AXE, BRONZE_AXE],
    }, profile=profile)
    counts = {
        FLAX: {"bank": 0, "inventory": 0, "total": 0},
        BOW_STRING: {"bank": 0, "inventory": 0, "total": 0},
        YEW_LOGS: {"bank": 0, "inventory": 0, "total": 0},
        YEW_LONGBOW_U: {"bank": 0, "inventory": 0, "total": 0},
        YEW_LONGBOW: {"bank": 0, "inventory": 0, "total": 0},
        KNIFE: {"bank": 0, "inventory": 0, "equipment": 0, "total": 0},
        RUNE_AXE: {"bank": 0, "inventory": 0, "equipment": 0, "total": 0},
        BRONZE_AXE: {"bank": 0, "inventory": 0, "equipment": 0, "total": 0},
    }
    for item in result.get("items") or []:
        item_id = int(item.get("itemId", item.get("id", -1)) or -1)
        if item_id not in counts:
            continue
        counts[item_id] = {
            "bank": int(item.get("bankAmount", item.get("amount", 0)) or 0),
            "inventory": int(item.get("inventoryAmount", 0) or 0),
            "equipment": int(item.get("equipmentAmount", 0) or 0),
            "total": int(item.get("totalAmount", item.get("amount", 0)) or 0),
        }
    return counts


def compact_counts(counts):
    yew_u = counts.get(YEW_LONGBOW_U, {}).get("total", 0)
    strings = counts.get(BOW_STRING, {}).get("total", 0)
    return {
        "bankedFlax": counts.get(FLAX, {}).get("bank", 0),
        "bankedBowStrings": counts.get(BOW_STRING, {}).get("bank", 0),
        "bankedYewLogs": counts.get(YEW_LOGS, {}).get("bank", 0),
        "bankedYewLongbowU": counts.get(YEW_LONGBOW_U, {}).get("bank", 0),
        "bankedYewLongbows": counts.get(YEW_LONGBOW, {}).get("bank", 0),
        "carriedFlax": counts.get(FLAX, {}).get("inventory", 0),
        "carriedBowStrings": counts.get(BOW_STRING, {}).get("inventory", 0),
        "carriedYewLogs": counts.get(YEW_LOGS, {}).get("inventory", 0),
        "carriedYewLongbowU": counts.get(YEW_LONGBOW_U, {}).get("inventory", 0),
        "carriedYewLongbows": counts.get(YEW_LONGBOW, {}).get("inventory", 0),
        "carriedKnife": counts.get(KNIFE, {}).get("inventory", 0),
        "carriedAxe": sum(counts.get(item_id, {}).get("inventory", 0) for item_id in AXE_IDS),
        "equippedAxe": sum(counts.get(item_id, {}).get("equipment", 0) for item_id in AXE_IDS),
        "possibleCompleteBows": min(yew_u, strings),
    }


def write_status(args, phase, run_path=None, counts=None, extra=None):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    if counts is None:
        counts = material_counts(args.profile)
    payload = {
        "ok": True,
        "runner": "seers_yew_complete_bow_master",
        "updatedAt": utc_now(),
        "phase": phase,
        "profile": args.profile,
        "pid": os.getpid(),
        "stopRequested": stop_path(args.profile).exists(),
        "runLog": str(run_path) if run_path else None,
        "player": player_compact(args.profile),
        "args": vars(args),
    }
    payload.update(compact_counts(counts))
    if extra:
        payload.update(extra)
    status_path(args.profile).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
                                         encoding="utf-8")


def print_status(args):
    path = status_path(args.profile)
    if path.exists():
        print(path.read_text(encoding="utf-8").strip())
        return 0
    print(json.dumps({
        "ok": False,
        "runner": "seers_yew_complete_bow_master",
        "error": "no_status",
        "statusPath": str(path),
    }, sort_keys=True, separators=(",", ":")))
    return 1


def print_shutdown_status(args):
    path = status_path(args.profile)
    stop = stop_path(args.profile)
    if not path.exists():
        print(json.dumps({
            "ok": False,
            "runner": "seers_yew_complete_bow_master",
            "error": "no_status",
            "profile": args.profile,
            "stopRequested": stop.exists(),
            "shutdownComplete": False,
        }, sort_keys=True, separators=(",", ":")))
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    phase = str(data.get("phase") or "")
    print(json.dumps({
        "ok": True,
        "runner": "seers_yew_complete_bow_master",
        "profile": data.get("profile") or args.profile,
        "phase": phase,
        "stopRequested": bool(data.get("stopRequested")) or stop.exists(),
        "shutdownComplete": phase in TERMINAL_PHASES,
        "pid": data.get("pid"),
        "updatedAt": data.get("updatedAt"),
    }, sort_keys=True, separators=(",", ":")))
    return 0


def request_child_stop(script, profile):
    subprocess.run([sys.executable, str(script), "--profile", profile, "--request-stop"],
                   cwd=str(REPO_ROOT), env=child_env(profile),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def request_stop(args):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    stop_path(args.profile).write_text(utc_now() + "\n", encoding="utf-8")
    for script in (YEW_RUNNER, FLAX_RUNNER, STRINGER):
        request_child_stop(script, args.profile)
    print(json.dumps({
        "ok": True,
        "runner": "seers_yew_complete_bow_master",
        "stopRequested": True,
        "stopPath": str(stop_path(args.profile)),
    }, sort_keys=True, separators=(",", ":")))
    return 0


def should_stop(args):
    return stop_path(args.profile).exists()


def run_child(args, handle, label, command, counts, cycle):
    write_status(args, label + "_running", counts=counts, run_path=handle.name, extra={
        "cycle": cycle,
        "childCommand": command,
    })
    write_jsonl(handle, "child_start", {"label": label, "cycle": cycle, "command": command})
    proc = subprocess.run(command, cwd=str(REPO_ROOT), text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=child_env(args.profile))
    write_jsonl(handle, "child_done", {
        "label": label,
        "cycle": cycle,
        "returncode": proc.returncode,
        "stdoutTail": proc.stdout.strip().splitlines()[-6:],
        "stderrTail": proc.stderr.strip().splitlines()[-6:],
    })
    counts = material_counts(args.profile)
    write_status(args, label + "_done", counts=counts, run_path=handle.name, extra={
        "cycle": cycle,
        "childReturncode": proc.returncode,
    })
    return proc.returncode, counts


def withdraw_items(profile, handle, requests, reason):
    result = bridge.call_tool("withdraw_bank_items_XS", {"items": requests}, profile=profile)
    write_jsonl(handle, "tool_withdraw", {
        "reason": reason,
        "items": requests,
        "success": bool(result.get("success")),
        "message": result.get("message"),
        "withdrawnAmount": result.get("withdrawnAmount"),
        "resultItems": result.get("items"),
    })
    return result


def ensure_yew_tools(args, handle, counts):
    compact = compact_counts(counts)
    if compact["carriedKnife"] > 0 and (compact["carriedAxe"] > 0 or compact["equippedAxe"] > 0):
        return counts

    write_jsonl(handle, "ensure_yew_tools_start", {"counts": compact})
    requests = []
    reasons = []
    if compact["carriedKnife"] <= 0:
        if counts[KNIFE]["bank"] <= 0:
            raise RuntimeError("No knife found in inventory or bank.")
        requests.append({"itemId": KNIFE, "amount": 1})
        reasons.append("missing_knife")

    if compact["carriedAxe"] <= 0 and compact["equippedAxe"] <= 0:
        axe_id = None
        for candidate in AXE_IDS:
            if counts[candidate]["bank"] > 0:
                axe_id = candidate
                break
        if axe_id is None:
            raise RuntimeError("No axe found in inventory, equipment, or bank.")
        requests.append({"itemId": axe_id, "amount": 1})
        reasons.append("missing_axe")

    if requests:
        withdraw_items(args.profile, handle, requests, "+".join(reasons))
        counts = material_counts(args.profile)

    write_jsonl(handle, "ensure_yew_tools_done", {"counts": compact_counts(counts)})
    return counts


def yew_command(args):
    return [
        sys.executable,
        str(YEW_RUNNER),
        "--profile",
        args.profile,
        "--max-cycles",
        str(args.yew_cycles_per_pass),
        "--bank-products",
        "--no-final-sell",
        "--pickup-bird-nests",
        "--quiet",
    ]


def flax_command(args):
    return [
        sys.executable,
        str(FLAX_RUNNER),
        "--profile",
        args.profile,
        "--max-cycles",
        str(args.flax_cycles_per_pass),
        "--quiet",
        "--pick-wait-ticks",
        str(args.pick_wait_ticks),
        "--pick-global-cooldown-ticks",
        str(args.pick_global_cooldown_ticks),
        "--spin-wait-chunk-ticks",
        str(args.spin_wait_chunk_ticks),
    ]


def string_command(args, target):
    max_cycles = max(1, int(math.ceil(float(target) / float(args.string_batch_size))))
    return [
        sys.executable,
        str(STRINGER),
        "--profile",
        args.profile,
        "--bank",
        args.string_bank,
        "--batch-size",
        str(args.string_batch_size),
        "--target-count",
        str(target),
        "--max-cycles",
        str(max_cycles),
    ]


def choose_phase(args, counts, forced):
    if forced in ("yew", "flax", "string"):
        return forced
    compact = compact_counts(counts)
    if compact["carriedYewLogs"] > 0:
        return "yew"
    possible = compact["possibleCompleteBows"]
    if possible >= int(args.min_stringing_bows):
        return "string"
    if counts[BOW_STRING]["total"] < int(args.min_bowstrings_before_yew):
        return "flax"
    return "yew"


def phase_reason(args, counts, forced):
    if forced in ("yew", "flax", "string"):
        return "forced_{}".format(forced)
    compact = compact_counts(counts)
    if compact["carriedYewLogs"] > 0:
        return "carried_yew_logs"
    if compact["possibleCompleteBows"] >= int(args.min_stringing_bows):
        return "complete_bow_inputs_ready"
    if counts[BOW_STRING]["total"] < int(args.min_bowstrings_before_yew):
        return "low_bowstrings"
    return "need_yew_materials"


def run_loop(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if stop_path(args.profile).exists():
        stop_path(args.profile).unlink()
    run_path = RUNS_DIR / "{}-seers-yew-complete-bow-master-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        os.getpid(),
    )
    cycles = 0
    forced = args.start_with
    with run_path.open("a", encoding="utf-8") as handle:
        counts = material_counts(args.profile)
        write_jsonl(handle, "run_start", {"args": vars(args), "counts": compact_counts(counts)})
        write_status(args, "started", counts=counts, run_path=run_path, extra={"cycle": cycles})
        while args.max_master_cycles <= 0 or cycles < args.max_master_cycles:
            if should_stop(args):
                write_status(args, "stopped", counts=counts, run_path=run_path, extra={"cycle": cycles})
                return 0
            cycles += 1
            counts = material_counts(args.profile)
            reason = phase_reason(args, counts, forced)
            phase = choose_phase(args, counts, forced)
            forced = "auto"
            write_jsonl(handle, "cycle_start", {
                "cycle": cycles,
                "selectedPhase": phase,
                "phaseReason": reason,
                "counts": compact_counts(counts),
            })
            if phase == "string":
                possible = compact_counts(counts)["possibleCompleteBows"]
                target = min(possible, int(args.string_target_per_pass))
                rc, counts = run_child(args, handle, "string", string_command(args, target), counts, cycles)
            elif phase == "flax":
                rc, counts = run_child(args, handle, "flax", flax_command(args), counts, cycles)
            else:
                try:
                    counts = ensure_yew_tools(args, handle, counts)
                except RuntimeError as exc:
                    write_status(args, "blocked", counts=counts, run_path=run_path, extra={
                        "cycle": cycles,
                        "error": str(exc),
                    })
                    write_jsonl(handle, "blocked", {"cycle": cycles, "error": str(exc), "phase": phase})
                    return 2
                rc, counts = run_child(args, handle, "yew", yew_command(args), counts, cycles)

            if rc != 0:
                write_status(args, "blocked", counts=counts, run_path=run_path, extra={
                    "cycle": cycles,
                    "error": "{}_child_failed".format(phase),
                    "returncode": rc,
                })
                return rc
            if args.target_complete_bows > 0 and counts[YEW_LONGBOW]["bank"] >= int(args.target_complete_bows):
                write_status(args, "complete", counts=counts, run_path=run_path, extra={
                    "cycle": cycles,
                    "reason": "target_complete_bows",
                })
                return 0
        counts = material_counts(args.profile)
        write_status(args, "complete", counts=counts, run_path=run_path, extra={
            "cycle": cycles,
            "reason": "max_master_cycles",
        })
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make complete Seers yew longbows by switching between yew, flax, and stringing runners.")
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--max-master-cycles", type=int, default=0, help="0 means run until cooperative stop.")
    parser.add_argument("--yew-cycles-per-pass", type=int, default=1)
    parser.add_argument("--flax-cycles-per-pass", type=int, default=1)
    parser.add_argument("--string-target-per-pass", type=int, default=28)
    parser.add_argument("--string-batch-size", type=int, default=14)
    parser.add_argument("--string-bank", default=SEERS_BANK_TARGET)
    parser.add_argument("--min-stringing-bows", type=int, default=1)
    parser.add_argument("--min-bowstrings-before-yew", type=int, default=28)
    parser.add_argument("--target-complete-bows", type=int, default=0)
    parser.add_argument("--start-with", choices=("auto", "yew", "flax", "string"), default="auto")
    parser.add_argument("--pick-wait-ticks", type=int, default=2)
    parser.add_argument("--pick-global-cooldown-ticks", type=int, default=1)
    parser.add_argument("--spin-wait-chunk-ticks", type=int, default=25)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--shutdown-status", action="store_true")
    parser.add_argument("--request-stop", action="store_true")
    args = parser.parse_args(argv)

    if args.status:
        return print_status(args)
    if args.shutdown_status:
        return print_shutdown_status(args)
    if args.request_stop:
        return request_stop(args)
    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
