#!/usr/bin/env python3
"""Timed route marathon runner for repeated 2006Scape navigation laps.

The marathon runner keeps the AI out of the per-tick loop. It delegates actual
movement to route_runner.py, streams compact progress, and writes a JSONL event
log that can become deterministic benchmark and ML training input.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
ROUTE_RUNNER = SCRIPT_DIR / "route_runner.py"
RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_CONTEXT_MAP = SCRIPT_DIR / "render_agent_context_map.py"
MARATHON_DIR = ROOT / "data" / "marathons"
RUN_PROFILE = ""

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import navdb  # noqa: E402
import route_eval  # noqa: E402


DEFAULT_CIRCUIT = [
    ("lumbridge", "lumbridge_castle_courtyard"),
    ("varrock", "varrock_square"),
    ("falador", "falador_shield_shop"),
    ("draynor-edge", "draynor_southwest_tree_opening"),
    ("lumbridge", "lumbridge_castle_courtyard"),
]

BATCH_RE = re.compile(
    r"^batch (?P<batch>\d+) (?P<mode>\S+) target=(?P<target>\S+) "
    r"walkTarget=(?P<walkTarget>\S+) previewSteps=(?P<previewSteps>\d+) "
    r"status=(?P<status>\S+) final=(?P<final>\S+)"
    r"(?: ticks=(?P<ticks>\d+) hp=(?P<hp>\d+) run=(?P<run>\d+) "
    r"combat=(?P<combat>\S+) dead=(?P<dead>\S+))?"
)
ARRIVED_RE = re.compile(r"^arrived target=(?P<target>\S+) tile=(?P<tile>\S+)")
MAX_BATCH_RE = re.compile(r"^max batches reached target=(?P<target>\S+) final=(?P<tile>\S+)")
NO_ROUTE_RE = re.compile(r"^no route target=(?P<target>\S+) status=(?P<status>\S+)")
PREVIEW_BLOCKED_RE = re.compile(r"^preview blocked mode=(?P<mode>\S+) target=(?P<target>\S+) message=(?P<message>.*)")
HAZARD_BLOCKED_RE = re.compile(r"^hazard blocked mode=(?P<mode>\S+) target=(?P<target>\S+)")


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_bool(value):
    return str(value).lower() == "true"


def call_tool(tool, arguments=None):
    args_json = json.dumps(arguments or {}, separators=(",", ":"))
    env = os.environ.copy()
    if RUN_PROFILE:
        env["RS_PROFILE"] = RUN_PROFILE
    proc = subprocess.run(
        [str(RS_TOOL), tool, args_json],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError("{} failed: {}".format(tool, proc.stderr.strip() or proc.stdout.strip()))
    return json.loads(proc.stdout)


def player_from(result):
    player = result.get("player")
    if not isinstance(player, dict):
        raise RuntimeError("bridge response did not include player state")
    return player


def player_tile(player):
    return {
        "x": int(player["x"]),
        "y": int(player["y"]),
        "height": int(player.get("height", player.get("h", 0))),
    }


def compact_player(player):
    return {
        "tile": player_tile(player),
        "hitpoints": int(player.get("hitpoints", player.get("hp", 0)) or 0),
        "maxHitpoints": int(player.get("maxHitpoints", player.get("maxHp", 0)) or 0),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled", False)),
        "combatLevel": int(player.get("combatLevel", 0) or 0),
        "foodCount": int((player.get("combatReadiness") or {}).get("inventoryFoodCount", 0) or 0),
        "coins": int((player.get("combatReadiness") or {}).get("inventoryCoins", 0) or 0),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
        "inBankArea": bool(player.get("inBankArea", False)),
    }


def observe_compact():
    return compact_player(player_from(call_tool("observe_state", {})))


def write_event(handle, event, data):
    record = {"event": event, "timestamp": utc_now()}
    record.update(data)
    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()


def parse_route_runner_line(line):
    match = BATCH_RE.match(line)
    if match:
        data = match.groupdict()
        return "batch", {
            "batch": int(data["batch"]),
            "mode": data["mode"],
            "target": data["target"],
            "walkTarget": data["walkTarget"],
            "previewSteps": int(data["previewSteps"]),
            "status": data["status"],
            "final": data["final"],
            "ticks": int(data["ticks"] or 0),
            "hitpoints": int(data["hp"] or 0),
            "runEnergy": int(data["run"] or 0),
            "combat": parse_bool(data["combat"] or "false"),
            "dead": parse_bool(data["dead"] or "false"),
        }
    match = ARRIVED_RE.match(line)
    if match:
        return "arrived", match.groupdict()
    match = MAX_BATCH_RE.match(line)
    if match:
        return "max_batches", match.groupdict()
    match = NO_ROUTE_RE.match(line)
    if match:
        return "no_route", match.groupdict()
    match = PREVIEW_BLOCKED_RE.match(line)
    if match:
        return "preview_blocked", match.groupdict()
    match = HAZARD_BLOCKED_RE.match(line)
    if match:
        return "hazard_blocked", match.groupdict()
    return "output", {"line": line}


def route_runner_command(target, args, max_batch_distance):
    command = [
        sys.executable,
        str(ROUTE_RUNNER),
        "--to",
        target,
        "--max-walk-distance",
        str(args.max_walk_distance),
        "--max-batches",
        str(args.max_batches_per_leg),
        "--max-ticks",
        str(args.max_ticks),
        "--graph-snap-distance",
        str(args.graph_snap_distance),
        "--max-batch-distance",
        str(max_batch_distance),
        "--compress-gap",
        str(args.compress_gap),
        "--hazard-buffer",
        str(args.hazard_buffer),
        "--failure-buffer",
        str(args.failure_buffer),
        "--max-static-leg",
        str(args.max_static_leg),
        "--max-warnings",
        str(args.max_warnings),
        "--run-reserve",
        str(args.run_reserve),
        "--run-reserve-buffer",
        str(args.run_reserve_buffer),
        "--run-reserve-waypoints",
        str(args.run_reserve_waypoints),
    ]
    if args.profile:
        command.extend(["--profile", args.profile])
    if args.no_enable_run:
        command.append("--no-enable-run")
    if args.allow_lethal:
        command.append("--allow-lethal")
    if args.allow_failed_traces:
        command.append("--allow-failed-traces")
    if args.include_partial:
        command.append("--include-partial")
    if args.include_derived:
        command.append("--include-derived")
    if args.include_unverified:
        command.append("--include-unverified")
    if args.trace_file:
        for path in args.trace_file:
            command.extend(["--trace-file", path])
    if args.trace_profile:
        command.extend(["--trace-profile", args.trace_profile])
    if args.include_unscoped_traces:
        command.append("--include-unscoped-traces")
    return command


def route_eval_args(args, start_state, target, max_batch_distance):
    return argparse.Namespace(
        from_tile=navdb.tile_str(start_state["tile"]),
        to=target,
        combat_level=start_state["combatLevel"],
        food=start_state["foodCount"],
        coins=start_state.get("coins", 0),
        run_energy=start_state["runEnergy"],
        run_enabled=start_state["runEnabled"],
        allow_lethal=args.allow_lethal,
        allow_failed_traces=args.allow_failed_traces,
        include_partial=args.include_partial,
        include_derived=args.include_derived,
        include_unverified=args.include_unverified,
        trace_file=args.trace_file,
        trace_profile=args.trace_profile,
        include_unscoped_traces=args.include_unscoped_traces,
        graph_snap_distance=args.graph_snap_distance,
        hazard_buffer=args.hazard_buffer,
        failure_buffer=args.failure_buffer,
        max_static_leg=args.max_static_leg,
        max_batch_distance=max_batch_distance,
        compress_gap=args.compress_gap,
        max_warnings=args.max_warnings,
        max_suspects=args.route_eval_max_suspects,
        json=False,
        via=None,
    )


def render_preflight_context_map(handle, run_id, lap_index, leg_index, leg_name, target, evaluation, args):
    if not args.render_detour_maps:
        return None
    quality = evaluation.get("quality")
    if quality not in set(args.detour_map_qualities):
        return None
    center = evaluation.get("next")
    if not isinstance(center, dict):
        return None
    command = [
        sys.executable,
        str(ROUTE_CONTEXT_MAP),
        "--center",
        navdb.tile_str(center),
        "--radius-tiles",
        str(args.detour_map_radius),
        "--pixels-per-tile",
        str(args.detour_map_pixels_per_tile),
        "--recent-seconds",
        "0",
    ]
    if args.trace_profile or args.profile:
        command.extend(["--player", args.trace_profile or args.profile])
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    event = {
        "runId": run_id,
        "lap": lap_index,
        "leg": leg_index,
        "legName": leg_name,
        "target": target,
        "quality": quality,
        "command": command[1:],
        "returncode": proc.returncode,
    }
    if proc.stdout.strip():
        try:
            event["summary"] = json.loads(proc.stdout)
        except json.JSONDecodeError:
            event["stdout"] = proc.stdout.strip()
    if proc.stderr.strip():
        event["stderr"] = proc.stderr.strip()
    write_event(handle, "leg_preflight_map", event)
    if proc.returncode == 0:
        print("  preflight map={}".format(
            ((event.get("summary") or {}).get("output") or "context-map-artifact")
        ), flush=True)
    return event


def preflight_leg(handle, run_id, lap_index, leg_index, leg_name, target, args, start_state, max_batch_distance):
    if not args.detour_check:
        return None
    try:
        evaluation = route_eval.evaluate(route_eval_args(args, start_state, target, max_batch_distance))
    except Exception as exc:
        write_event(handle, "leg_preflight_failed", {
            "runId": run_id,
            "lap": lap_index,
            "leg": leg_index,
            "legName": leg_name,
            "target": target,
            "start": start_state["tile"],
            "error": str(exc),
        })
        print("  preflight failed: {}".format(exc), flush=True)
        return None
    compact = {
        "runId": run_id,
        "lap": lap_index,
        "leg": leg_index,
        "legName": leg_name,
        "target": target,
        "status": evaluation.get("status"),
        "quality": evaluation.get("quality"),
        "cost": evaluation.get("cost"),
        "estimatedTicks": evaluation.get("estimatedTicks"),
        "directDistance": evaluation.get("directDistance"),
        "routeDistance": evaluation.get("routeDistance"),
        "detourRatio": evaluation.get("detourRatio"),
        "edgeSources": evaluation.get("edgeSources"),
        "next": evaluation.get("next"),
        "recommendedMapCommand": evaluation.get("recommendedMapCommand"),
    }
    write_event(handle, "leg_preflight", compact)
    if evaluation.get("status") == "ok":
        print("  preflight quality={} ratio={} estTicks={} next={}".format(
            evaluation.get("quality"),
            evaluation.get("detourRatio"),
            evaluation.get("estimatedTicks"),
            navdb.tile_str(evaluation.get("next")) if evaluation.get("next") else "none",
        ), flush=True)
    else:
        print("  preflight status={} frontier={}".format(
            evaluation.get("status"),
            navdb.tile_str(evaluation.get("frontierTile")) if evaluation.get("frontierTile") else "none",
        ), flush=True)
    if evaluation.get("status") == "ok":
        render_preflight_context_map(
            handle, run_id, lap_index, leg_index, leg_name, target, evaluation, args)
    return evaluation


def run_leg(handle, run_id, lap_index, leg_index, leg_name, target, args, max_batch_distance):
    start_state = observe_compact()
    start = time.monotonic()
    command = route_runner_command(target, args, max_batch_distance)
    write_event(handle, "leg_start", {
        "runId": run_id,
        "lap": lap_index,
        "leg": leg_index,
        "legName": leg_name,
        "target": target,
        "startState": start_state,
        "maxBatchDistance": max_batch_distance,
        "command": command[1:],
    })
    print("lap {} leg {} -> {} from {}".format(
        lap_index, leg_index, target, navdb.tile_str(start_state["tile"])), flush=True)

    preflight = preflight_leg(handle, run_id, lap_index, leg_index, leg_name, target, args, start_state, max_batch_distance)
    if preflight and args.stop_on_bad_detour:
        bad_ratio = float(preflight.get("detourRatio") or 0.0) >= args.bad_detour_ratio
        if preflight.get("status") != "ok" or bad_ratio:
            duration = time.monotonic() - start
            result = {
                "runId": run_id,
                "lap": lap_index,
                "leg": leg_index,
                "legName": leg_name,
                "target": target,
                "success": False,
                "returncode": None,
                "durationSeconds": round(duration, 3),
                "batchCount": 0,
                "gameTicks": 0,
                "hitpointsLost": 0,
                "runEnergySpent": 0,
                "startState": start_state,
                "endState": observe_compact(),
                "finalTile": navdb.tile_str(start_state["tile"]),
                "parsedEvents": [],
                "reason": "bad_detour_preflight",
                "preflight": preflight,
            }
            write_event(handle, "leg_end", result)
            print("leg {} stopped before movement: detour preflight quality={} ratio={}".format(
                leg_index, preflight.get("quality"), preflight.get("detourRatio")), flush=True)
            return result

    proc = subprocess.Popen(
        command,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    batches = []
    parsed_events = []
    arrived = False
    final_tile = None
    assert proc.stdout is not None
    for raw_line in proc.stdout:
        line = raw_line.strip()
        if not line:
            continue
        print("  {}".format(line), flush=True)
        parsed_type, parsed = parse_route_runner_line(line)
        parsed_events.append({"type": parsed_type, "data": parsed})
        if parsed_type == "batch":
            batches.append(parsed)
            final_tile = parsed.get("final")
            write_event(handle, "batch", {
                "runId": run_id,
                "lap": lap_index,
                "leg": leg_index,
                "legName": leg_name,
                **parsed,
            })
        elif parsed_type == "arrived":
            arrived = True
            final_tile = parsed.get("tile")

    stderr = proc.stderr.read() if proc.stderr is not None else ""
    returncode = proc.wait()
    duration = time.monotonic() - start
    end_state = observe_compact()
    success = returncode == 0 and arrived and not end_state["isDead"] and not end_state["isInCombat"]
    ticks = sum(batch.get("ticks", 0) for batch in batches)
    hp_loss = max(0, start_state["hitpoints"] - end_state["hitpoints"])
    energy_spent = max(0, start_state["runEnergy"] - end_state["runEnergy"])
    result = {
        "runId": run_id,
        "lap": lap_index,
        "leg": leg_index,
        "legName": leg_name,
        "target": target,
        "success": success,
        "returncode": returncode,
        "durationSeconds": round(duration, 3),
        "batchCount": len(batches),
        "gameTicks": ticks,
        "hitpointsLost": hp_loss,
        "runEnergySpent": energy_spent,
        "startState": start_state,
        "endState": end_state,
        "finalTile": final_tile,
        "parsedEvents": parsed_events[-8:],
    }
    if stderr.strip():
        result["stderr"] = stderr.strip()
    write_event(handle, "leg_end", result)
    print("leg {} {} in {:.1f}s batches={} ticks={} hpLost={} runSpent={}".format(
        leg_index,
        "ok" if success else "failed",
        duration,
        len(batches),
        ticks,
        hp_loss,
        energy_spent,
    ), flush=True)
    return result


def parse_circuit(values):
    if not values:
        return list(DEFAULT_CIRCUIT)
    if len(values) == 1 and "," in values[0]:
        values = [value.strip() for value in values[0].split(",") if value.strip()]
    circuit = []
    for index, target in enumerate(values):
        circuit.append(("waypoint_{}".format(index + 1), target))
    if len(circuit) < 2:
        raise SystemExit("marathon circuit must contain at least two waypoints")
    return circuit


def circuit_legs(circuit):
    return [
        (index, "{}->{}".format(circuit[index - 1][0], circuit[index][0]), circuit[index][1])
        for index in range(1, len(circuit))
    ]


def write_summary(summary_path, summary):
    tmp_path = summary_path.with_suffix(summary_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(summary_path)


def run(args):
    circuit = parse_circuit(args.circuit)
    MARATHON_DIR.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    log_path = MARATHON_DIR / "{}.jsonl".format(run_id)
    summary_path = MARATHON_DIR / "{}.summary.json".format(run_id)
    max_batch_distance = args.max_batch_distance
    laps = []
    best_lap_seconds = None
    all_success = True

    with log_path.open("a", encoding="utf-8") as handle:
        write_event(handle, "run_start", {
            "runId": run_id,
            "lapsRequested": args.laps,
            "circuit": [{"name": name, "target": target} for name, target in circuit],
            "settings": vars(args),
            "initialState": observe_compact(),
        })

        if args.preposition:
            start_target = circuit[0][1]
            preposition = run_leg(
                handle, run_id, 0, 0, "preposition->{}".format(circuit[0][0]),
                start_target, args, max_batch_distance)
            if not preposition["success"]:
                all_success = False
                write_event(handle, "run_end", {
                    "runId": run_id,
                    "success": False,
                    "reason": "preposition_failed",
                    "logPath": str(log_path),
                    "summaryPath": str(summary_path),
                })
                write_summary(summary_path, {
                    "runId": run_id,
                    "success": False,
                    "reason": "preposition_failed",
                    "preposition": preposition,
                    "logPath": str(log_path),
                })
                return 4

        for lap in range(1, args.laps + 1):
            lap_start = time.monotonic()
            lap_record = {
                "lap": lap,
                "maxBatchDistance": max_batch_distance,
                "legs": [],
            }
            write_event(handle, "lap_start", {
                "runId": run_id,
                "lap": lap,
                "maxBatchDistance": max_batch_distance,
                "startState": observe_compact(),
            })
            for leg_index, leg_name, target in circuit_legs(circuit):
                result = run_leg(handle, run_id, lap, leg_index, leg_name, target, args, max_batch_distance)
                lap_record["legs"].append(result)
                if not result["success"]:
                    all_success = False
                    if args.stop_on_failure:
                        break
            lap_duration = time.monotonic() - lap_start
            lap_success = all(leg["success"] for leg in lap_record["legs"]) and len(lap_record["legs"]) == len(circuit) - 1
            lap_record.update({
                "success": lap_success,
                "durationSeconds": round(lap_duration, 3),
                "legCount": len(lap_record["legs"]),
                "batchCount": sum(leg["batchCount"] for leg in lap_record["legs"]),
                "gameTicks": sum(leg["gameTicks"] for leg in lap_record["legs"]),
                "hitpointsLost": sum(leg["hitpointsLost"] for leg in lap_record["legs"]),
                "runEnergySpent": sum(leg["runEnergySpent"] for leg in lap_record["legs"]),
            })
            if lap_success:
                if best_lap_seconds is None or lap_duration < best_lap_seconds:
                    best_lap_seconds = lap_duration
                lap_record["bestLapSeconds"] = round(best_lap_seconds, 3)
                lap_record["deltaFromBestSeconds"] = round(lap_duration - best_lap_seconds, 3)
                if args.adaptive_batch_distance and lap_record["hitpointsLost"] == 0:
                    max_batch_distance = min(
                        args.batch_distance_max,
                        max_batch_distance + args.batch_distance_step,
                    )
            laps.append(lap_record)
            write_event(handle, "lap_end", {
                "runId": run_id,
                **{key: value for key, value in lap_record.items() if key != "legs"},
            })
            print("lap {} {} in {:.1f}s batches={} ticks={} nextBatchDistance={}".format(
                lap,
                "ok" if lap_success else "failed",
                lap_duration,
                lap_record["batchCount"],
                lap_record["gameTicks"],
                max_batch_distance,
            ), flush=True)
            write_summary(summary_path, {
                "runId": run_id,
                "success": all_success and len(laps) == args.laps,
                "lapsCompleted": len([item for item in laps if item.get("success")]),
                "lapsRequested": args.laps,
                "bestLapSeconds": round(best_lap_seconds, 3) if best_lap_seconds is not None else None,
                "currentMaxBatchDistance": max_batch_distance,
                "logPath": str(log_path),
                "laps": laps,
            })
            if not lap_success and args.stop_on_failure:
                break

        success = all_success and len(laps) == args.laps and all(lap.get("success") for lap in laps)
        write_event(handle, "run_end", {
            "runId": run_id,
            "success": success,
            "lapsCompleted": len([item for item in laps if item.get("success")]),
            "lapsRequested": args.laps,
            "bestLapSeconds": round(best_lap_seconds, 3) if best_lap_seconds is not None else None,
            "finalState": observe_compact(),
            "logPath": str(log_path),
            "summaryPath": str(summary_path),
        })
    return 0 if success else 5


def main(argv=None):
    global RUN_PROFILE
    parser = argparse.ArgumentParser(description="Run timed repeated 2006Scape route laps.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "",
                        help="Use this profile's bridge session and matching trace profile.")
    parser.add_argument("--laps", type=int, default=10)
    parser.add_argument("--circuit", nargs="*", help="Waypoint ids/tiles. Default is Lumbridge->Varrock->Falador->Draynor-edge->Lumbridge.")
    parser.add_argument("--run-id")
    parser.add_argument("--preposition", action="store_true", default=True)
    parser.add_argument("--no-preposition", dest="preposition", action="store_false")
    parser.add_argument("--stop-on-failure", action="store_true", default=True)
    parser.add_argument("--continue-on-failure", dest="stop_on_failure", action="store_false")
    parser.add_argument("--max-walk-distance", type=int, default=48)
    parser.add_argument("--max-batches-per-leg", type=int, default=28)
    parser.add_argument("--max-ticks", type=int, default=160)
    parser.add_argument("--graph-snap-distance", type=int, default=16)
    parser.add_argument("--max-batch-distance", type=int, default=32)
    parser.add_argument("--adaptive-batch-distance", action="store_true", default=True)
    parser.add_argument("--no-adaptive-batch-distance", dest="adaptive_batch_distance", action="store_false")
    parser.add_argument("--batch-distance-step", type=int, default=4)
    parser.add_argument("--batch-distance-max", type=int, default=48)
    parser.add_argument("--compress-gap", type=int, default=24)
    parser.add_argument("--hazard-buffer", type=int, default=10)
    parser.add_argument("--failure-buffer", type=int, default=8)
    parser.add_argument("--max-static-leg", type=int, default=32)
    parser.add_argument("--max-warnings", type=int, default=8)
    parser.add_argument("--run-reserve", default="none",
                        help="Pass-through to route_runner.py: none, auto, or fixed reserve.")
    parser.add_argument("--run-reserve-buffer", type=int, default=0)
    parser.add_argument("--run-reserve-waypoints", type=int, default=12)
    parser.add_argument("--detour-check", action="store_true", default=True)
    parser.add_argument("--no-detour-check", dest="detour_check", action="store_false")
    parser.add_argument("--bad-detour-ratio", type=float, default=2.0)
    parser.add_argument("--stop-on-bad-detour", action="store_true")
    parser.add_argument("--route-eval-max-suspects", type=int, default=5)
    parser.add_argument("--render-detour-maps", action="store_true", default=True)
    parser.add_argument("--no-render-detour-maps", dest="render_detour_maps", action="store_false")
    parser.add_argument("--detour-map-qualities", nargs="*", default=["suspicious", "bad"])
    parser.add_argument("--detour-map-radius", type=int, default=80)
    parser.add_argument("--detour-map-pixels-per-tile", type=int, default=4)
    parser.add_argument("--no-enable-run", action="store_true")
    parser.add_argument("--allow-lethal", action="store_true")
    parser.add_argument("--allow-failed-traces", action="store_true")
    parser.add_argument("--include-partial", action="store_true")
    parser.add_argument("--include-derived", action="store_true")
    parser.add_argument("--include-unverified", action="store_true")
    parser.add_argument("--trace-file", action="append")
    parser.add_argument("--trace-profile",
                        default=os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "",
                        help="Only use traces recorded by this player/profile.")
    parser.add_argument("--include-unscoped-traces", action="store_true")
    args = parser.parse_args(argv)
    if args.profile and not args.trace_profile:
        args.trace_profile = args.profile
    RUN_PROFILE = args.profile
    if args.laps < 1:
        raise SystemExit("--laps must be at least 1")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
