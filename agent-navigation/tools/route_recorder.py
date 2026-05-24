#!/usr/bin/env python3
"""Background movement/combat recorder for the local 2006Scape bridge.

This is deliberately not AI-powered. It polls the bridge through rs-tool.sh,
writes compact JSONL movement records, and stays quiet unless asked for stats.
The server-side passive player trace logger is the primary producer when the
runtime includes it; this script is a fallback/dev supplement for old builds or
extra NPC snapshots.

The output defaults to agent-navigation/data/movement_traces.jsonl, which is
already consumed by navdb.py and router.py.
"""

import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DATA = ROOT / "data"
PASSIVE_TRACE_ROOT = ROOT.parent / "2006Scape Server" / "data" / "logs" / "player-movement-traces"
DEFAULT_OUTPUT = DATA / "movement_traces.jsonl"
DEFAULT_PID = ROOT / ".local" / "route-recorder.pid"
DEFAULT_LOG = ROOT / ".local" / "route-recorder.log"


def safe_profile(value):
    text = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum() or ch in ("-", "_"))
    return text or "default"


def default_output_for_profile(profile):
    if not profile or safe_profile(profile) == "mrflame":
        return DEFAULT_OUTPUT
    return DATA / "movement_traces-{}.jsonl".format(safe_profile(profile))


def default_pid_for_profile(profile):
    if not profile or safe_profile(profile) == "mrflame":
        return DEFAULT_PID
    return ROOT / ".local" / "route-recorder-{}.pid".format(safe_profile(profile))


def default_log_for_profile(profile):
    if not profile or safe_profile(profile) == "mrflame":
        return DEFAULT_LOG
    return ROOT / ".local" / "route-recorder-{}.log".format(safe_profile(profile))


def resolve_path(value, default_path):
    if value:
        return Path(value).expanduser()
    return default_path


def recent_passive_trace(profile=None, max_age_seconds=300):
    if not PASSIVE_TRACE_ROOT.exists():
        return None
    expected = safe_profile(profile)
    now = time.time()
    newest = None
    for path in PASSIVE_TRACE_ROOT.rglob("*.jsonl"):
        if profile and safe_profile(path.stem) != expected:
            continue
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age <= max_age_seconds and (newest is None or age < newest[0]):
            newest = (age, path)
    return newest[1] if newest else None


def ensure_fallback_allowed(args):
    if args.allow_passive_duplicate:
        return
    passive = recent_passive_trace(args.profile)
    if passive:
        raise SystemExit(
            "refusing to start fallback route_recorder because recent passive server telemetry exists: {}. "
            "Use AgentPassiveTraceLog as the route source, or pass --allow-passive-duplicate for a deliberate "
            "debug recording.".format(passive))


def process_exists(pid):
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False


def utc_now():
    now = dt.datetime.now(dt.timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def timestamp_ms():
    return int(time.time() * 1000)


def run_tool(tool, payload, profile=None):
    env = os.environ.copy()
    if profile:
        env["RS_PROFILE"] = profile
    proc = subprocess.run(
        [str(TOOLS / "rs-tool.sh"), tool, json.dumps(payload, separators=(",", ":"))],
        cwd=str(ROOT.parent),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "rs-tool failed")
    return json.loads(proc.stdout)


def slim_npc(npc, player_combat):
    level = int(npc.get("combatLevel") or npc.get("level") or 0)
    under_attack = bool(npc.get("underAttack"))
    aggressive = bool(npc.get("aggressive"))
    distance = int(npc.get("distance") or npc.get("dist") or 0)
    if not (under_attack or aggressive or level >= player_combat + 5 or distance <= 2):
        return None
    return {
        "name": npc.get("name"),
        "level": level,
        "x": npc.get("x"),
        "y": npc.get("y"),
        "height": npc.get("height", npc.get("h", 0)),
        "distance": distance,
        "aggressive": aggressive,
        "underAttack": under_attack,
        "npcIndex": npc.get("npcIndex", npc.get("idx")),
    }


def inventory_food_count(player):
    readiness = player.get("combatReadiness") or {}
    if readiness.get("inventoryFoodCount") is not None:
        return readiness.get("inventoryFoodCount")
    food_names = ("bread", "shark", "lobster", "trout", "salmon", "tuna", "cake", "meat")
    count = 0
    for item in player.get("inventory") or []:
        name = str(item.get("name") or "").lower()
        if any(food in name for food in food_names):
            count += int(item.get("amount") or 1)
    return count


def make_record(state, previous, trace_id, profile=None):
    player = state.get("player") or {}
    tile = {
        "x": int(player.get("x")),
        "y": int(player.get("y")),
        "height": int(player.get("height", player.get("h", 0))),
    }
    previous_tile = previous.get("tile") if previous else None
    hp = int(player.get("hitpoints", player.get("hp", 0)))
    run_energy = int(player.get("runEnergy", 0))
    prev_hp = previous.get("hitpoints") if previous else hp
    prev_run = previous.get("runEnergy") if previous else run_energy
    player_combat = int(player.get("combatLevel") or 3)
    nearby_npcs = []
    for npc in state.get("nearbyNpcs") or []:
        slim = slim_npc(npc, player_combat)
        if slim:
            nearby_npcs.append(slim)

    target_npc = state.get("targetNpc")
    if not target_npc and player.get("targetNpc"):
        target_npc = player.get("targetNpc")

    moved = previous_tile is not None and previous_tile != tile
    in_combat = bool(player.get("isInCombat"))
    dead = bool(player.get("isDead"))
    hp_lost = max(0, int(prev_hp) - hp)
    run_spent = max(0, int(prev_run) - run_energy)
    if dead:
        event = "player_dead"
    elif in_combat:
        event = "combat"
    elif hp_lost:
        event = "hitpoints_lost"
    elif moved:
        event = "movement"
    else:
        event = "state"

    record = {
        "schemaVersion": 1,
        "traceId": trace_id,
        "event": event,
        "tool": "route_recorder",
        "timestamp": utc_now(),
        "timestampMs": timestamp_ms(),
        "tile": tile,
        "previousTile": previous_tile,
        "moved": moved,
        "runEnabled": bool(player.get("runEnabled")),
        "runEnergy": run_energy,
        "runEnergySpent": run_spent,
        "hitpoints": hp,
        "maxHitpoints": int(player.get("maxHitpoints", player.get("maxHp", hp))),
        "hitpointsLost": hp_lost,
        "isMoving": bool(player.get("isMoving")),
        "isDead": dead,
        "isInCombat": in_combat,
        "npcIndex": int(player.get("npcIndex") or 0),
        "killingNpcIndex": int(player.get("killingNpcIndex") or 0),
        "underAttackBy": int(player.get("underAttackBy") or 0),
        "underAttackBy2": int(player.get("underAttackBy2") or 0),
        "foodCount": inventory_food_count(player),
        "nearbyNpcs": nearby_npcs[:8],
    }
    player_name = player.get("name") or profile
    if player_name:
        record["playerName"] = player_name
    player_id = player.get("playerId", player.get("id"))
    if player_id is not None:
        record["playerId"] = player_id
    if target_npc:
        record["targetNpc"] = {
            "name": target_npc.get("name"),
            "combatLevel": target_npc.get("combatLevel", target_npc.get("level")),
            "x": target_npc.get("x"),
            "y": target_npc.get("y"),
            "height": target_npc.get("height", target_npc.get("h", 0)),
            "distance": target_npc.get("distance", target_npc.get("dist")),
            "npcIndex": target_npc.get("npcIndex", target_npc.get("idx")),
            "underAttack": target_npc.get("underAttack"),
        }
    return record


def should_write(record, previous_written, last_idle_write, idle_every):
    if previous_written is None:
        return True, time.time()
    if record["event"] != "state":
        return True, last_idle_write
    if idle_every <= 0:
        return False, last_idle_write
    now = time.time()
    if now - last_idle_write >= idle_every:
        return True, now
    return False, last_idle_write


def run_recorder(args):
    ensure_fallback_allowed(args)
    output = resolve_path(args.output, default_output_for_profile(args.profile))
    output.parent.mkdir(parents=True, exist_ok=True)
    trace_id = args.trace_id or "route-recorder-{}".format(uuid.uuid4().hex[:12])
    previous = None
    previous_written = None
    last_idle_write = 0.0
    stop = {"value": False}

    def handle_stop(_signum, _frame):
        stop["value"] = True

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    with output.open("a", encoding="utf-8") as handle:
        while not stop["value"]:
            try:
                state = run_tool("observe_state", {}, profile=args.profile)
                record = make_record(state, previous, trace_id, profile=args.profile)
                write, last_idle_write = should_write(record, previous_written, last_idle_write, args.idle_every)
                if write:
                    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                    handle.flush()
                    previous_written = record
                previous = {
                    "tile": record["tile"],
                    "hitpoints": record["hitpoints"],
                    "runEnergy": record["runEnergy"],
                }
            except Exception as exc:
                error = {
                    "schemaVersion": 1,
                    "traceId": trace_id,
                    "event": "recorder_error",
                    "timestamp": utc_now(),
                    "timestampMs": timestamp_ms(),
                    "message": str(exc),
                }
                if args.profile:
                    error["playerName"] = args.profile
                handle.write(json.dumps(error, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush()
            time.sleep(args.interval)
    return 0


def cmd_run(args):
    return run_recorder(args)


def cmd_start(args):
    ensure_fallback_allowed(args)
    pid_path = resolve_path(args.pid_file, default_pid_for_profile(args.profile))
    log_path = resolve_path(args.log_file, default_log_for_profile(args.profile))
    output = resolve_path(args.output, default_output_for_profile(args.profile))
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if pid_path.exists():
        try:
            existing = int(pid_path.read_text(encoding="utf-8").strip())
            if process_exists(existing):
                print("route recorder already running: pid={}".format(existing))
                return 0
        except Exception:
            pid_path.unlink(missing_ok=True)
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run",
        "--interval",
        str(args.interval),
        "--idle-every",
        str(args.idle_every),
        "--output",
        str(output),
    ]
    if args.profile:
        cmd.extend(["--profile", args.profile])
    env = os.environ.copy()
    if args.profile:
        env["RS_PROFILE"] = args.profile
    log = log_path.open("ab", buffering=0)
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT.parent),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    print("route recorder started: pid={} output={}".format(proc.pid, output))
    return 0


def cmd_stop(args):
    pid_path = resolve_path(args.pid_file, default_pid_for_profile(args.profile))
    if not pid_path.exists():
        print("route recorder not running")
        return 0
    pid = int(pid_path.read_text(encoding="utf-8").strip())
    try:
        os.kill(pid, signal.SIGTERM)
    except PermissionError:
        raise SystemExit("permission denied stopping route recorder pid={}; stop it from the owning shell".format(pid))
    except ProcessLookupError:
        pass
    pid_path.unlink(missing_ok=True)
    print("route recorder stopped: pid={}".format(pid))
    return 0


def cmd_status(args):
    pid_path = resolve_path(args.pid_file, default_pid_for_profile(args.profile))
    running = False
    pid = None
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            running = process_exists(pid)
        except Exception:
            running = False
    output = resolve_path(args.output, default_output_for_profile(args.profile))
    records = 0
    last = None
    if output.exists():
        with output.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                records += 1
                last = text
    summary = {"running": running, "pid": pid, "output": str(output), "records": records}
    if last:
        try:
            record = json.loads(last)
            summary["lastEvent"] = record.get("event")
            summary["lastTile"] = record.get("tile")
            summary["lastTimestamp"] = record.get("timestamp")
        except Exception:
            summary["lastRaw"] = last[:160]
    print(json.dumps(summary, sort_keys=True))
    return 0


def add_common(parser):
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE"))
    parser.add_argument("--output")
    parser.add_argument("--pid-file")
    parser.add_argument("--log-file")
    parser.add_argument("--interval", type=float, default=1.2)
    parser.add_argument("--idle-every", type=float, default=0.0,
                        help="Seconds between stationary state heartbeats; 0 disables idle writes.")
    parser.add_argument("--allow-passive-duplicate", action="store_true",
                        help="Allow fallback polling even when recent passive server telemetry exists.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Background recorder for movement/routing traces.")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run in the foreground.")
    add_common(run)
    run.add_argument("--trace-id")
    run.set_defaults(func=cmd_run)

    start = sub.add_parser("start", help="Start a detached background recorder.")
    add_common(start)
    start.set_defaults(func=cmd_start)

    stop = sub.add_parser("stop", help="Stop a detached background recorder.")
    add_common(stop)
    stop.set_defaults(func=cmd_stop)

    status = sub.add_parser("status", help="Report recorder status and output stats.")
    add_common(status)
    status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
