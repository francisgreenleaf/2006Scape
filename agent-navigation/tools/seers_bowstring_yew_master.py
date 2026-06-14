#!/usr/bin/env python3
"""Alternate Seers bowstring production with yew-longbow stringing."""

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
RUNS_DIR = ROOT / "data" / "crafting" / "seers-bowstring-yew-master-runs"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bridge_script as bridge  # noqa: E402
from profile_utils import resolve_profile, safe_profile  # noqa: E402


FLAX_RUNNER = SCRIPT_DIR / "seers_flax_spin_fast_runner.py"
YEW_STRINGER = SCRIPT_DIR / "yew_longbow_stringer.py"
YEW_LONGBOW_U = 66
BOW_STRING = 1777
YEW_LONGBOW = 855
SEERS_BANK_TARGET = "2727,3493,0"
TERMINAL_PHASES = {"blocked", "complete", "stopped"}


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def run_stem(profile):
    return "seers-bowstring-yew-master-{}".format(safe_profile(profile or "default"))


def status_path(profile):
    return CONTROL_DIR / "{}.status.json".format(run_stem(profile))


def stop_path(profile):
    return CONTROL_DIR / "{}.stop".format(run_stem(profile))


def write_jsonl(handle, event, data):
    payload = {"ts": utc_now(), "event": event}
    payload.update(data)
    handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


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


def compact_counts(counts):
    return {
        "bankedYewLongbowU": counts.get(YEW_LONGBOW_U, 0),
        "bankedBowStrings": counts.get(BOW_STRING, 0),
        "bankedYewLongbows": counts.get(YEW_LONGBOW, 0),
        "possibleYewLongbows": min(counts.get(YEW_LONGBOW_U, 0), counts.get(BOW_STRING, 0)),
    }


def player_compact(profile):
    try:
        player = bridge.observe_xs(profile=profile)
    except Exception:
        return None
    data = bridge.compact_player(player, ("crafting", "fletching"))
    data.update({
        "flax": bridge.count_inventory_item(player, 1779),
        "bowStrings": bridge.count_inventory_item(player, BOW_STRING),
        "yewLongbowU": bridge.count_inventory_item(player, YEW_LONGBOW_U),
        "yewLongbows": bridge.count_inventory_item(player, YEW_LONGBOW),
    })
    return data


def write_status(args, phase, run_path=None, counts=None, extra=None):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    if counts is None:
        counts = bank_counts(args.profile)
    payload = {
        "ok": True,
        "runner": "seers_bowstring_yew_master",
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
    print(json.dumps({"ok": False, "runner": "seers_bowstring_yew_master", "error": "no_status",
                      "statusPath": str(path)}, sort_keys=True, separators=(",", ":")))
    return 1


def print_shutdown_status(args):
    path = status_path(args.profile)
    stop = stop_path(args.profile)
    if not path.exists():
        print(json.dumps({"ok": False, "runner": "seers_bowstring_yew_master", "error": "no_status",
                          "profile": args.profile, "stopRequested": stop.exists(),
                          "shutdownComplete": False}, sort_keys=True, separators=(",", ":")))
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    phase = str(data.get("phase") or "")
    print(json.dumps({
        "ok": True,
        "runner": "seers_bowstring_yew_master",
        "profile": data.get("profile") or args.profile,
        "phase": phase,
        "stopRequested": bool(data.get("stopRequested")) or stop.exists(),
        "shutdownComplete": phase in TERMINAL_PHASES,
        "pid": data.get("pid"),
        "updatedAt": data.get("updatedAt"),
    }, sort_keys=True, separators=(",", ":")))
    return 0


def request_stop(args):
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    stop_path(args.profile).write_text(utc_now() + "\n", encoding="utf-8")
    env = child_env(args.profile)
    for script in (FLAX_RUNNER, YEW_STRINGER):
        subprocess.run([sys.executable, str(script), "--profile", args.profile, "--request-stop"],
                       cwd=str(REPO_ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(json.dumps({"ok": True, "runner": "seers_bowstring_yew_master", "stopRequested": True,
                      "stopPath": str(stop_path(args.profile))}, sort_keys=True, separators=(",", ":")))
    return 0


def child_env(profile):
    env = os.environ.copy()
    env["PROFILE"] = profile
    env["RS_PROFILE"] = profile
    env["RS_TRACE_PROFILE"] = profile
    return env


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
    counts = bank_counts(args.profile)
    write_status(args, label + "_done", counts=counts, run_path=handle.name, extra={
        "cycle": cycle,
        "childReturncode": proc.returncode,
    })
    return proc.returncode, counts


def should_stop(args):
    return stop_path(args.profile).exists()


def flax_command(args):
    command = [
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
    return command


def string_command(args, target):
    max_cycles = max(1, int(math.ceil(float(target) / float(args.string_batch_size))))
    return [
        sys.executable,
        str(YEW_STRINGER),
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


def run_loop(args):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if stop_path(args.profile).exists():
        stop_path(args.profile).unlink()
    run_path = RUNS_DIR / "{}-seers-bowstring-yew-master-{}.jsonl".format(
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        os.getpid(),
    )
    cycles = 0
    with run_path.open("a", encoding="utf-8") as handle:
        counts = bank_counts(args.profile)
        write_jsonl(handle, "run_start", {"args": vars(args), "counts": compact_counts(counts)})
        write_status(args, "started", counts=counts, run_path=run_path, extra={"cycle": cycles})
        while args.max_master_cycles <= 0 or cycles < args.max_master_cycles:
            if should_stop(args):
                write_status(args, "stopped", counts=counts, run_path=run_path, extra={"cycle": cycles})
                return 0
            cycles += 1
            counts = bank_counts(args.profile)
            possible = min(counts[YEW_LONGBOW_U], counts[BOW_STRING])
            write_jsonl(handle, "cycle_start", {"cycle": cycles, "counts": compact_counts(counts)})

            should_make_strings = args.start_with != "string"

            if should_make_strings:
                rc, counts = run_child(args, handle, "flax", flax_command(args), counts, cycles)
                if rc != 0:
                    write_status(args, "blocked", counts=counts, run_path=run_path,
                                 extra={"cycle": cycles, "error": "flax_child_failed", "returncode": rc})
                    return rc

            if should_stop(args):
                write_status(args, "stopped", counts=counts, run_path=run_path, extra={"cycle": cycles})
                return 0

            counts = bank_counts(args.profile)
            possible = min(counts[YEW_LONGBOW_U], counts[BOW_STRING])
            if possible >= int(args.min_stringing_bows):
                target = min(possible, int(args.string_target_per_pass))
                rc, counts = run_child(args, handle, "string", string_command(args, target), counts, cycles)
                if rc != 0:
                    write_status(args, "blocked", counts=counts, run_path=run_path,
                                 extra={"cycle": cycles, "error": "string_child_failed", "returncode": rc})
                    return rc
            else:
                write_jsonl(handle, "string_skip", {
                    "cycle": cycles,
                    "reason": "insufficient_pairable_supplies",
                    "counts": compact_counts(counts),
                })

            if args.target_bowstrings > 0 and counts[BOW_STRING] >= int(args.target_bowstrings):
                write_status(args, "complete", counts=counts, run_path=run_path,
                             extra={"cycle": cycles, "reason": "target_bowstrings"})
                return 0
            args.start_with = "auto"
        write_status(args, "complete", counts=counts, run_path=run_path,
                     extra={"cycle": cycles, "reason": "max_master_cycles"})
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=resolve_profile(default=""))
    parser.add_argument("--max-master-cycles", type=int, default=0, help="0 means run until cooperative stop.")
    parser.add_argument("--flax-cycles-per-pass", type=int, default=2)
    parser.add_argument("--string-target-per-pass", type=int, default=56)
    parser.add_argument("--string-batch-size", type=int, default=14)
    parser.add_argument("--string-bank", default=SEERS_BANK_TARGET)
    parser.add_argument("--min-bowstrings-before-stringing", type=int, default=28)
    parser.add_argument("--min-stringing-bows", type=int, default=14)
    parser.add_argument("--target-bowstrings", type=int, default=0)
    parser.add_argument("--start-with", choices=("auto", "flax", "string"), default="auto")
    parser.add_argument("--pick-wait-ticks", type=int, default=2)
    parser.add_argument("--pick-global-cooldown-ticks", type=int, default=1)
    parser.add_argument("--spin-wait-chunk-ticks", type=int, default=25)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--shutdown-status", action="store_true")
    parser.add_argument("--request-stop", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.profile = resolve_profile(args.profile)
    if args.status:
        return print_status(args)
    if args.shutdown_status:
        return print_shutdown_status(args)
    if args.request_stop:
        return request_stop(args)
    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
