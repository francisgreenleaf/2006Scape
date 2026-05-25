#!/usr/bin/env python3
"""Bridge-backed route runner for learned 2006Scape navigation.

This is a low-token executor around router.py:

1. observe current player state through the bridge wrapper,
2. plan over learned routes/traces/hazards,
3. preflight the next movement batch with the server's clipped PathFinder,
4. execute one or more walk_to_tile_until_arrived batches.

It does not inspect bridge tokens directly and does not mutate player state
outside normal bridge gameplay tools.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import navdb  # noqa: E402
import router  # noqa: E402
import route_eval  # noqa: E402
from usage_log import log_usage  # noqa: E402


RS_TOOL = SCRIPT_DIR / "rs-tool.sh"
ROUTE_CONTEXT_MAP = SCRIPT_DIR / "render_agent_context_map.py"
RUN_PROFILE = None


def tile_str(tile):
    return navdb.tile_str(tile)


def log(*args, **kwargs):
    kwargs.setdefault("flush", True)
    print(*args, **kwargs)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_evidence(args, event, data):
    path = getattr(args, "evidence_jsonl", "") or ""
    if not path:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "timestamp": utc_now(),
    }
    profile = getattr(args, "profile", "") or getattr(args, "trace_profile", "") or os.environ.get("RS_PROFILE", "")
    if profile:
        record["profile"] = profile
    record.update(data)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


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
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("{} returned invalid JSON: {}".format(tool, exc))


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


def inventory_food_count(player):
    readiness = player.get("combatReadiness") or {}
    if readiness.get("inventoryFoodCount") is not None:
        return int(readiness.get("inventoryFoodCount") or 0)
    return sum(1 for item in player.get("inventory", []) if "heal" in str(item.get("name", "")).lower())


def inventory_coins(player):
    readiness = player.get("combatReadiness") or {}
    if readiness.get("inventoryCoins") is not None:
        return int(readiness.get("inventoryCoins") or 0)
    total = 0
    for item in player.get("inventory", []):
        if int(item.get("id", 0)) == 995:
            total += int(item.get("amount", 0))
    return total


def compact_player(player):
    return {
        "tile": player_tile(player),
        "hitpoints": int(player.get("hitpoints", player.get("hp", 0)) or 0),
        "maxHitpoints": int(player.get("maxHitpoints", player.get("maxHp", 0)) or 0),
        "runEnergy": int(player.get("runEnergy", 0) or 0),
        "runEnabled": bool(player.get("runEnabled", False)),
        "combatLevel": int(player.get("combatLevel", 0) or 0),
        "foodCount": inventory_food_count(player),
        "coins": inventory_coins(player),
        "isDead": bool(player.get("isDead", False)),
        "isInCombat": bool(player.get("isInCombat", False)),
    }


def build_router_args(args, player, start_tile):
    return SimpleNamespace(
        from_tile=tile_str(start_tile),
        to=args.to,
        combat_level=int(player.get("combatLevel", args.combat_level)),
        food=inventory_food_count(player),
        coins=inventory_coins(player),
        run_energy=int(player.get("runEnergy", 0)),
        run_enabled=bool(player.get("runEnabled", False)),
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
        max_batch_distance=args.max_batch_distance,
        compress_gap=args.compress_gap,
        max_warnings=args.max_warnings,
        json=False,
    )


def build_route_eval_args(args, player, start_tile):
    return SimpleNamespace(
        from_tile=tile_str(start_tile),
        to=args.to,
        combat_level=int(player.get("combatLevel", args.combat_level)),
        food=inventory_food_count(player),
        coins=inventory_coins(player),
        run_energy=int(player.get("runEnergy", 0)),
        run_enabled=bool(player.get("runEnabled", False)),
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
        max_batch_distance=args.max_batch_distance,
        compress_gap=args.compress_gap,
        max_warnings=args.max_warnings,
        max_suspects=args.orient_max_suspects,
        json=True,
        via=None,
    )


def frontier_next_wrong_way(plan, current_tile, tolerance):
    next_tile = plan.get("next")
    target_tile = plan.get("targetTile")
    if not isinstance(next_tile, dict) or not isinstance(target_tile, dict):
        return False
    current_distance = navdb.distance(current_tile, target_tile)
    next_distance = navdb.distance(next_tile, target_tile)
    return next_distance > current_distance + max(0, tolerance)


def target_from_plan(plan, args, current_tile):
    if plan["status"] == "ok":
        return plan["next"], "planned"
    if args.allow_frontier and plan.get("next") and navdb.distance(current_tile, plan["next"]) > 0:
        if args.probe_toward_target and frontier_next_wrong_way(
                plan, current_tile, args.frontier_wrong_way_tolerance):
            return project_toward(current_tile, plan["targetTile"], args.probe_distance), "probe"
        return plan["next"], "frontier"
    if args.direct_if_preview and plan.get("targetTile"):
        if navdb.distance(current_tile, plan["targetTile"]) <= args.direct_preview_distance:
            return plan["targetTile"], "direct-preview"
    if args.probe_toward_target and plan.get("targetTile"):
        return project_toward(current_tile, plan["targetTile"], args.probe_distance), "probe"
    return None, "no-route"


def hazard_run_requirement(hazard):
    requirements = hazard.get("requirements", {})
    min_energy = int(requirements.get("minRunEnergy") or 0)
    if requirements.get("requiresRun") and min_energy <= 0:
        min_energy = 20
    return min_energy


def run_hazards_near_tiles(db, tiles, args):
    found = {}
    for tile in tiles:
        if not isinstance(tile, dict):
            continue
        for dist, hazard in navdb.hazards_near(db, tile, args.hazard_buffer):
            min_energy = hazard_run_requirement(hazard)
            if min_energy <= 0:
                continue
            hazard_id = hazard["id"]
            previous = found.get(hazard_id)
            if previous is None or dist < previous["distance"]:
                found[hazard_id] = {
                    "id": hazard_id,
                    "risk": hazard.get("risk", "unknown"),
                    "distance": dist,
                    "minRunEnergy": min_energy,
                    "requiresRun": bool(hazard.get("requirements", {}).get("requiresRun")),
                }
    return sorted(found.values(), key=lambda item: (-item["minRunEnergy"], item["distance"], item["id"]))


def planned_tiles_for_run_policy(plan, target_place, args):
    tiles = []
    for key in ("next", "frontierTile", "endTile"):
        if isinstance(plan.get(key), dict):
            tiles.append(plan[key])
    waypoints = plan.get("waypoints") or []
    if plan.get("routeDefinition"):
        tiles.extend(waypoints)
    else:
        tiles.extend(waypoints[:args.run_reserve_waypoints])
    if isinstance(target_place.get("tile"), dict):
        tiles.append(target_place["tile"])
    return tiles


def parse_run_reserve(args, db, plan, target_place):
    setting = str(args.run_reserve or "none").strip().lower()
    if setting in ("none", "off", "false", "no", ""):
        return {
            "mode": "none",
            "reserve": 0,
            "hazards": [],
        }
    if setting == "auto":
        hazards = run_hazards_near_tiles(db, planned_tiles_for_run_policy(plan, target_place, args), args)
        reserve = max([item["minRunEnergy"] for item in hazards] or [0])
        if reserve > 0:
            reserve += int(args.run_reserve_buffer)
        return {
            "mode": "auto",
            "reserve": max(0, min(100, reserve)),
            "hazards": hazards[:5],
        }
    try:
        reserve = int(setting)
    except ValueError:
        raise RuntimeError("--run-reserve must be none, auto, or an integer")
    reserve = max(0, min(100, reserve + int(args.run_reserve_buffer)))
    return {
        "mode": "fixed",
        "reserve": reserve,
        "hazards": [],
    }


def choose_run_state(player, run_policy, batch_hazards, args, estimated_run_cost=0):
    if not args.enable_run:
        return None, "disabled"
    energy = int(player.get("runEnergy", 0) or 0)
    if energy <= 0:
        return False, "empty"
    if batch_hazards:
        return True, "hazard"
    min_useful_energy = min(10, max(3, int(estimated_run_cost or 0)))
    if energy < min_useful_energy:
        return False, "low-energy"
    reserve = int(run_policy.get("reserve", 0) or 0)
    if reserve <= 0:
        return True, "default"
    if energy - max(1, int(estimated_run_cost or 0)) > reserve:
        return True, "surplus"
    return False, "reserve"


def ensure_run_state(player, should_run, force=False, force_reason=""):
    monitor = {
        "requestedRun": should_run,
        "runEnabledBefore": bool(player.get("runEnabled", False)),
        "runEnergyBefore": int(player.get("runEnergy", 0) or 0),
        "attemptedSetRun": False,
        "forceSetRun": bool(force and should_run is True),
        "forceReason": force_reason if force and should_run is True else "",
    }
    if should_run is None:
        monitor["runEnabledAfter"] = monitor["runEnabledBefore"]
        monitor["runEnergyAfter"] = monitor["runEnergyBefore"]
        return monitor
    current = bool(player.get("runEnabled", False))
    if current != bool(should_run) or (force and bool(should_run)):
        monitor["attemptedSetRun"] = True
        result = call_tool("set_run", {"enabled": bool(should_run)})
        monitor["setRunSuccess"] = bool(result.get("success"))
        if result.get("message"):
            monitor["setRunMessage"] = result.get("message")
        updated = result.get("player")
        if isinstance(updated, dict):
            player.update(updated)
        else:
            player["runEnabled"] = bool(should_run)
    monitor["runEnabledAfter"] = bool(player.get("runEnabled", False))
    monitor["runEnergyAfter"] = int(player.get("runEnergy", 0) or 0)
    return monitor


def object_step_text(step):
    objects = ", ".join("{}x {}".format(item["count"], item["key"]) for item in step.get("objects", []))
    options = ", ".join("{}x {}".format(item["count"], item["key"]) for item in step.get("options", []))
    detail = objects or "object interaction"
    if options:
        detail += " option=" + options
    return "{} -> {} | {}".format(tile_str(step["from"]), tile_str(step["to"]), detail)


def log_object_steps(plan):
    steps = plan.get("objectSteps") or []
    if not steps:
        return
    log("plan includes object interaction evidence:")
    for step in steps[:3]:
        log("  " + object_step_text(step))


def clamp(value, low, high):
    return max(low, min(high, value))


def project_toward(current, target, distance):
    dx = target["x"] - current["x"]
    dy = target["y"] - current["y"]
    return {
        "x": current["x"] + clamp(dx, -distance, distance),
        "y": current["y"] + clamp(dy, -distance, distance),
        "height": current.get("height", 0),
    }


def preview_target(tile, args):
    return call_tool("preview_local_path", {
        "x": tile["x"],
        "y": tile["y"],
        "height": tile.get("height", 0),
        "moveNear": True,
        "applyBounds": True,
        "maxWalkDistance": args.max_walk_distance,
    })


def probe_candidates(current, target, args):
    seen = set()
    candidates = []
    current_distance = navdb.distance(current, target)
    for distance in range(args.probe_distance, 0, -max(1, args.probe_stride)):
        base = project_toward(current, target, distance)
        radius = args.probe_search_radius
        for x in range(base["x"] - radius, base["x"] + radius + 1):
            for y in range(base["y"] - radius, base["y"] + radius + 1):
                candidate = {"x": x, "y": y, "height": current.get("height", 0)}
                key = tile_str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                from_current = navdb.distance(current, candidate)
                to_target = navdb.distance(candidate, target)
                if from_current <= 0 or from_current > args.probe_distance:
                    continue
                if to_target >= current_distance:
                    continue
                candidates.append((to_target, from_current, candidate))
    candidates.sort(key=lambda item: (item[0], item[1], tile_str(item[2])))
    return [candidate for _to_target, _from_current, candidate in candidates[:args.probe_max_candidates]]


def find_reachable_probe(db, current, target, plan_args, args):
    for candidate in probe_candidates(current, target, args):
        if route_hazard_blocker(db, candidate, plan_args):
            continue
        preview = preview_target(candidate, args)
        if preview.get("reachable"):
            return candidate, preview
    return None, None


def is_success(result):
    return bool(result.get("success"))


def preview_final_tile(preview, fallback):
    final_tile = preview.get("finalTile")
    if not isinstance(final_tile, dict):
        return fallback
    return {
        "x": int(final_tile["x"]),
        "y": int(final_tile["y"]),
        "height": int(final_tile.get("height", 0)),
    }


def arrived(player, target, stop_distance):
    return navdb.distance(player_tile(player), target) <= stop_distance


def route_hazard_blocker(db, tile, plan_args):
    penalty, warnings = router.hazard_penalty(db, tile, plan_args)
    if penalty >= 8000.0 and not plan_args.allow_lethal:
        return warnings
    return []


def route_definition_path(path_text):
    path = Path(path_text)
    if path.is_absolute() or path.exists():
        return path
    repo_root = SCRIPT_DIR.parents[1]
    for candidate in (repo_root / path, ROOT / path):
        if candidate.exists():
            return candidate
    return path


def load_route_definition(path_text):
    if not path_text:
        return None
    path = route_definition_path(path_text)
    with path.open("r", encoding="utf-8") as handle:
        definition = json.load(handle)
    if definition.get("api") != "2006scape.route-definition":
        raise RuntimeError("--route-definition is not a 2006scape route definition: {}".format(path))
    return definition


def normalize_route_tile(raw):
    if isinstance(raw, dict):
        return {
            "x": int(raw["x"]),
            "y": int(raw["y"]),
            "height": int(raw.get("height", raw.get("h", 0))),
        }
    if isinstance(raw, str):
        return navdb.tile_from_arg(raw)
    return None


def route_definition_steps(definition, target_tile, arrival_radius):
    steps = []
    for raw in definition.get("routeSteps") or []:
        tile = normalize_route_tile(raw)
        if tile is not None:
            steps.append(tile)
    final_tile = normalize_route_tile(definition.get("targetTile")) if definition.get("targetTile") else target_tile
    if final_tile and (not steps or navdb.distance(steps[-1], final_tile) > max(0, arrival_radius)):
        steps.append(final_tile)
    return steps


def route_definition_target(current_tile, steps, target_tile, arrival_radius, args):
    if not steps:
        return None, {
            "status": "empty",
            "routeStepCount": 0,
        }
    nearest_index = min(
        range(len(steps)),
        key=lambda index: (navdb.distance(current_tile, steps[index]), index),
    )
    target_index = nearest_index
    if navdb.distance(current_tile, steps[target_index]) <= max(args.stop_distance, 2) and target_index + 1 < len(steps):
        target_index += 1
    while target_index + 1 < len(steps) and navdb.distance(current_tile, steps[target_index + 1]) <= args.max_batch_distance:
        target_index += 1
    target = steps[target_index]
    remaining = steps[nearest_index:]
    if navdb.distance(current_tile, target_tile) <= arrival_radius:
        target = target_tile
        target_index = len(steps) - 1
        remaining = [target_tile]
    return target, {
        "status": "ok",
        "nearestIndex": nearest_index,
        "targetIndex": target_index,
        "routeStepCount": len(steps),
        "remainingStepCount": max(0, len(steps) - nearest_index),
        "remainingWaypoints": remaining,
    }


def build_route_definition_plan(definition, current_tile, target_place, arrival_radius, args):
    steps = route_definition_steps(definition, target_place["tile"], arrival_radius)
    target, meta = route_definition_target(current_tile, steps, target_place["tile"], arrival_radius, args)
    plan = {
        "status": meta.get("status", "ok"),
        "next": target,
        "targetTile": target_place["tile"],
        "endTile": target_place["tile"],
        "waypoints": meta.get("remainingWaypoints") or [],
        "routeDefinition": {
            "routeId": definition.get("routeId"),
            "nearestIndex": meta.get("nearestIndex"),
            "targetIndex": meta.get("targetIndex"),
            "routeStepCount": meta.get("routeStepCount"),
            "remainingStepCount": meta.get("remainingStepCount"),
            "quality": definition.get("quality"),
            "mode": definition.get("mode"),
        },
    }
    if definition.get("routeId"):
        plan["routesUsed"] = [definition.get("routeId")]
    return plan


def run_batch_diagnostics(start_player, result, preview, requested_run, run_reason,
                          run_monitor, estimated_run_cost, args):
    player = player_from(result)
    steps = int(preview.get("pathLength") or 0)
    ticks = int(result.get("batchTicks") or 0)
    run_before = int(start_player.get("runEnergy", 0) or 0)
    run_after = int(player.get("runEnergy", 0) or 0)
    spent = max(0, run_before - run_after)
    moved = navdb.distance(player_tile(start_player), player_tile(player))
    expected_run_spend = int(estimated_run_cost or 0)
    expected_walk_ticks = steps if steps > 0 else None
    expected_run_ticks = (steps + 1) // 2 if steps > 0 else None
    expected_saved_ticks = (
        expected_walk_ticks - expected_run_ticks
        if expected_walk_ticks is not None and expected_run_ticks is not None else None
    )
    ticks_per_step = round(float(ticks) / float(steps), 3) if steps > 0 else None
    preview_tiles_per_tick = round(float(steps) / float(ticks), 3) if ticks > 0 else None
    tiles_per_tick = round(float(moved) / float(ticks), 3) if ticks > 0 else None
    observed_saved_vs_walk = (
        expected_walk_ticks - ticks
        if expected_walk_ticks is not None and ticks > 0 else None
    )
    observed_extra_vs_run = (
        ticks - expected_run_ticks
        if expected_run_ticks is not None and ticks > 0 else None
    )
    warnings = []
    run_enabled_at_walk_start = bool(start_player.get("runEnabled", False))
    run_enabled_after_batch = bool(player.get("runEnabled", False))
    if requested_run is True:
        if not run_enabled_at_walk_start:
            warnings.append("run_toggle_off_at_batch_start")
        if run_monitor and not bool(run_monitor.get("runEnabledAfter", run_enabled_at_walk_start)):
            warnings.append("run_disabled_before_walk_command")
        if not run_enabled_after_batch:
            warnings.append("run_disabled_after_batch")
        if steps >= args.run_diagnostics_min_steps and ticks_per_step is not None:
            slow = ticks_per_step >= args.run_walk_warning_ticks_per_step
            no_spend = spent <= args.run_warning_max_energy_spent
            if slow and no_spend:
                warnings.append("run_requested_but_speed_looks_like_walking")
    if requested_run is False and run_enabled_at_walk_start:
        warnings.append("run_enabled_despite_reserve_policy")
    if run_monitor and run_monitor.get("attemptedSetRun") and not run_monitor.get("setRunSuccess", True):
        warnings.append("set_run_failed")
    return {
        "requestedRun": requested_run,
        "requestedRunState": requested_run,
        "runReason": run_reason,
        "runBefore": {
            "enabled": bool((run_monitor or {}).get("runEnabledBefore", run_enabled_at_walk_start)),
            "energy": int((run_monitor or {}).get("runEnergyBefore", run_before) or 0),
        },
        "runAtWalkStart": {
            "enabled": run_enabled_at_walk_start,
            "energy": run_before,
        },
        "runAfter": {
            "enabled": run_enabled_after_batch,
            "energy": run_after,
        },
        "runEnabledBefore": run_enabled_at_walk_start,
        "runEnabledAfter": run_enabled_after_batch,
        "runEnabledBeforePolicy": bool((run_monitor or {}).get("runEnabledBefore", run_enabled_at_walk_start)),
        "runEnergyBefore": run_before,
        "runEnergyAfter": run_after,
        "runEnergyBeforePolicy": int((run_monitor or {}).get("runEnergyBefore", run_before) or 0),
        "runEnergySpent": spent,
        "expectedRunSpend": expected_run_spend,
        "expectedWalkTicks": expected_walk_ticks,
        "expectedRunTicks": expected_run_ticks,
        "expectedSavedTicksFromRun": expected_saved_ticks,
        "observedSavedTicksVsWalkEstimate": observed_saved_vs_walk,
        "observedExtraTicksVsRunEstimate": observed_extra_vs_run,
        "previewSteps": steps,
        "batchTicks": ticks,
        "movedDistance": moved,
        "ticksPerStep": ticks_per_step,
        "previewTilesPerTick": preview_tiles_per_tick,
        "tilesPerTick": tiles_per_tick,
        "actualTilesPerTick": tiles_per_tick,
        "setRun": run_monitor or {},
        "warnings": warnings,
    }


def print_batch_summary(batch_index, mode, target, walk_target, preview, result,
                        start_player, requested_run, run_reason, run_monitor,
                        estimated_run_cost, args):
    player = player_from(result)
    status = result.get("batchStatus") or ("arrived" if result.get("complete") else "incomplete")
    diagnostics = run_batch_diagnostics(
        start_player, result, preview, requested_run, run_reason, run_monitor,
        estimated_run_cost, args)
    ticks_per_step = diagnostics["ticksPerStep"]
    ticks_per_step_text = "{:.3f}".format(ticks_per_step) if ticks_per_step is not None else "na"
    tiles_per_tick = diagnostics["previewTilesPerTick"]
    tiles_per_tick_text = "{:.3f}".format(tiles_per_tick) if tiles_per_tick is not None else "na"
    warning_text = ",".join(diagnostics["warnings"]) if diagnostics["warnings"] else "none"
    log("batch {} {} target={} walkTarget={} previewSteps={} status={} final={} ticks={} hp={} run={} combat={} dead={} runReq={} runReason={} runBefore={} runAfter={} runSpent={} expectedRunSpend={} tps={} tilesPerTick={} walkSave={} runExtra={} runWarn={}".format(
        batch_index,
        mode,
        tile_str(target),
        tile_str(walk_target),
        int(preview.get("pathLength") or 0),
        status,
        tile_str(player_tile(player)),
        int(result.get("batchTicks") or 0),
        int(player.get("hitpoints", player.get("hp", 0)) or 0),
        int(player.get("runEnergy", 0) or 0),
        bool(player.get("isInCombat", False)),
        bool(player.get("isDead", False)),
        requested_run,
        run_reason,
        diagnostics["runEnergyBefore"],
        diagnostics["runEnergyAfter"],
        diagnostics["runEnergySpent"],
        diagnostics["expectedRunSpend"],
        ticks_per_step_text,
        tiles_per_tick_text,
        diagnostics["observedSavedTicksVsWalkEstimate"],
        diagnostics["observedExtraTicksVsRunEstimate"],
        warning_text,
    ))
    return diagnostics


def compact_route_eval(result):
    if not isinstance(result, dict):
        return None
    compact = {
        "status": result.get("status"),
        "quality": result.get("quality"),
        "estimatedTicks": result.get("estimatedTicks"),
        "directDistance": result.get("directDistance"),
        "routeDistance": result.get("routeDistance"),
        "detourRatio": result.get("detourRatio"),
        "next": result.get("next"),
        "frontierTile": result.get("frontierTile"),
        "frontierDistanceToTarget": result.get("frontierDistanceToTarget"),
        "frontierScore": result.get("frontierScore"),
        "edgeSources": result.get("edgeSources"),
        "recommendedMapCommand": result.get("recommendedMapCommand"),
    }
    return {key: value for key, value in compact.items() if value is not None}


def compact_plan(plan):
    keys = (
        "status", "cost", "next", "frontierTile", "frontierDistanceToTarget",
        "frontierScore", "edgeSources", "routesUsed", "hazardWarnings", "objectSteps",
        "routeDefinition",
    )
    compact = {key: plan.get(key) for key in keys if plan.get(key) not in (None, [], {})}
    if "objectSteps" in compact:
        compact["objectStepCount"] = len(compact.pop("objectSteps") or [])
    if "hazardWarnings" in compact:
        compact["hazardWarnings"] = compact["hazardWarnings"][:5]
    if plan.get("waypoints"):
        compact["waypoints"] = plan["waypoints"][:8]
    return compact


def compact_preview(preview, target, mode):
    if preview is None:
        return None
    return {
        "mode": mode,
        "target": target,
        "reachable": bool(preview.get("reachable")),
        "pathLength": int(preview.get("pathLength") or 0),
        "walkTarget": preview_final_tile(preview, target),
        "message": preview.get("message"),
    }


def render_orient_context_map(evaluation, plan, current_tile, args):
    if not args.orient_map:
        return None
    status = evaluation.get("status") if isinstance(evaluation, dict) else None
    quality = evaluation.get("quality") if isinstance(evaluation, dict) else None
    should_render = status != "ok" or quality in set(args.orient_map_qualities)
    if not should_render:
        return None
    center = None
    if isinstance(evaluation, dict):
        segments = evaluation.get("detourSegments") or []
        if segments and isinstance(segments[0].get("tile"), dict):
            center = segments[0]["tile"]
        elif isinstance(evaluation.get("next"), dict):
            center = evaluation["next"]
        elif isinstance(evaluation.get("frontierTile"), dict):
            center = evaluation["frontierTile"]
    if center is None:
        center = plan.get("next") if isinstance(plan.get("next"), dict) else current_tile
    command = [
        sys.executable,
        str(ROUTE_CONTEXT_MAP),
        "--center",
        tile_str(center),
        "--radius-tiles",
        str(args.orient_map_radius),
        "--pixels-per-tile",
        str(args.orient_map_pixels_per_tile),
        "--recent-seconds",
        "0",
    ]
    map_profile = args.trace_profile or args.profile
    if map_profile:
        command.extend(["--player", map_profile])
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    result = {"returncode": proc.returncode, "center": center}
    if proc.stdout.strip():
        try:
            rendered = json.loads(proc.stdout)
            result.update({
                "output": rendered.get("output"),
                "summary": rendered.get("summary"),
                "artifact": rendered.get("artifact"),
                "bounds": rendered.get("bounds"),
                "currentGridCell": rendered.get("currentGridCell"),
                "centerGridCell": rendered.get("centerGridCell"),
                "referenceGridCells": rendered.get("referenceGridCells"),
                "mapFunctionMarkerCount": rendered.get("mapFunctionMarkerCount"),
                "placeLabelsDrawn": rendered.get("placeLabelsDrawn"),
            })
        except json.JSONDecodeError:
            result["stdout"] = proc.stdout.strip()[:500]
    if proc.stderr.strip():
        result["stderr"] = proc.stderr.strip()[:500]
    return result


def orient(args):
    observed = call_tool("observe_state", {})
    player = player_from(observed)
    current_tile = player_tile(player)
    db = navdb.load_db()
    target_place = navdb.place_or_tile_target(db, args.to)
    if not target_place:
        raise RuntimeError("unknown target place or tile: {}".format(args.to))
    plan_args = build_router_args(args, player, current_tile)
    plan = router.build_plan(plan_args)
    target, mode = target_from_plan(plan, args, current_tile)
    preview = preview_target(target, args) if target is not None else None
    try:
        evaluation = route_eval.evaluate(build_route_eval_args(args, player, current_tile))
    except Exception as exc:
        evaluation = {"status": "error", "error": str(exc)}
    run_policy = parse_run_reserve(args, db, plan, target_place)
    walk_target = preview_final_tile(preview, target) if target is not None and preview else target
    batch_hazards = run_hazards_near_tiles(
        db,
        [tile for tile in (current_tile, target, walk_target) if isinstance(tile, dict)],
        args,
    )
    estimated_run_cost = int((preview or {}).get("pathLength") or 0)
    should_run, run_reason = choose_run_state(
        player, run_policy, batch_hazards, args, estimated_run_cost)
    payload = {
        "success": True,
        "target": {"id": target_place["id"], "tile": target_place["tile"]},
        "player": compact_player(player),
        "plan": compact_plan(plan),
        "routeEval": compact_route_eval(evaluation) or evaluation,
        "preview": compact_preview(preview, target, mode),
        "runPolicy": {
            **run_policy,
            "batchHazards": batch_hazards[:5],
            "wouldRun": should_run,
            "reason": run_reason,
            "estimatedRunCost": estimated_run_cost,
        },
        "contextMap": render_orient_context_map(evaluation, plan, current_tile, args),
    }
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print("orient target={} from={} status={} quality={} next={}".format(
            target_place["id"],
            tile_str(current_tile),
            plan.get("status"),
            (evaluation or {}).get("quality"),
            tile_str(target) if target else "none",
        ))
        if payload["preview"]:
            print("preview reachable={} steps={} walkTarget={}".format(
                payload["preview"]["reachable"],
                payload["preview"]["pathLength"],
                tile_str(payload["preview"]["walkTarget"])))
        print("run reserve={} mode={} wouldRun={} reason={}".format(
            run_policy.get("reserve"),
            run_policy.get("mode"),
            should_run,
            run_reason,
        ))
        if payload.get("contextMap") and payload["contextMap"].get("output"):
            print("context map:", payload["contextMap"]["output"])
    return 0 if plan.get("status") == "ok" else 2


def run(args):
    observed = call_tool("observe_state", {})
    player = player_from(observed)
    db = navdb.load_db()
    route_definition = load_route_definition(args.route_definition)
    target_place = navdb.place_or_tile_target(db, args.to)
    if not target_place:
        raise RuntimeError("unknown target place or tile: {}".format(args.to))
    arrival_radius = args.arrival_radius
    if arrival_radius is None:
        arrival_radius = int(target_place.get("arrivalRadius", 1))

    for batch in range(1, args.max_batches + 1):
        current_tile = player_tile(player)
        if arrived(player, target_place["tile"], arrival_radius):
            log("arrived target={} tile={}".format(target_place["id"], tile_str(current_tile)))
            return 0

        plan_args = build_router_args(args, player, current_tile)
        if route_definition is not None:
            plan = build_route_definition_plan(route_definition, current_tile, target_place, arrival_radius, args)
            target = plan.get("next")
            mode = "route-definition"
        else:
            plan = router.build_plan(plan_args)
            target, mode = target_from_plan(plan, args, current_tile)
        run_policy = parse_run_reserve(args, db, plan, target_place)
        log_object_steps(plan)
        if target is None:
            log("no route target={} status={}".format(target_place["id"], plan["status"]))
            if plan.get("frontierTile"):
                log("frontier {} remainingDistance={}".format(
                    tile_str(plan["frontierTile"]), plan.get("frontierDistanceToTarget")))
            return 2
        blockers = route_hazard_blocker(db, target, plan_args)
        planner_vetted_target = mode == "planned" and plan.get("status") == "ok"
        if blockers and not planner_vetted_target:
            log("hazard blocked mode={} target={}".format(mode, tile_str(target)))
            for warning in blockers[:3]:
                log("  {} risk={} dist={} {}".format(
                    warning["id"], warning["risk"], warning["distance"], "; ".join(warning["warnings"])))
            return 6

        preview = preview_target(target, args)
        if not preview.get("reachable") and mode == "probe" and args.probe_search_radius > 0:
            searched_target, searched_preview = find_reachable_probe(
                db, current_tile, target_place["tile"], plan_args, args)
            if searched_target is not None:
                target = searched_target
                preview = searched_preview
                mode = "probe-search"
        if not preview.get("reachable"):
            log("preview blocked mode={} target={} message={}".format(
                mode, tile_str(target), preview.get("message", "")))
            return 3
        walk_target = preview_final_tile(preview, target)
        batch_hazards = run_hazards_near_tiles(db, [current_tile, target, walk_target], args)
        estimated_run_cost = int(preview.get("pathLength") or 0)
        should_run, run_reason = choose_run_state(
            player, run_policy, batch_hazards, args, estimated_run_cost)
        if navdb.distance(current_tile, walk_target) <= 0 and not arrived(player, target_place["tile"], arrival_radius):
            log("preview made no progress mode={} target={} final={}".format(
                mode, tile_str(target), tile_str(walk_target)))
            return 3

        if args.dry_run:
            force_run = bool(
                should_run is True
                and args.force_run_before_long_leg
                and estimated_run_cost >= args.force_run_min_preview_steps
            )
            log("dry-run mode={} target={} walkTarget={} previewSteps={} planStatus={} run={} runReason={} reserve={} estimatedRunCost={} forceRun={}".format(
                mode, tile_str(target), tile_str(walk_target), int(preview.get("pathLength") or 0),
                plan["status"], should_run, run_reason, run_policy.get("reserve", 0), estimated_run_cost,
                force_run))
            if plan.get("waypoints"):
                log("waypoints:", " ".join(tile_str(tile) for tile in plan["waypoints"][:12]))
            return 0

        force_run = bool(
            should_run is True
            and args.force_run_before_long_leg
            and estimated_run_cost >= args.force_run_min_preview_steps
        )
        run_monitor = ensure_run_state(
            player,
            should_run,
            force=force_run,
            force_reason="long_leg_pre_batch" if force_run else "",
        )
        batch_start_player = dict(player)
        result = call_tool("walk_to_tile_until_arrived", {
            "x": walk_target["x"],
            "y": walk_target["y"],
            "height": walk_target.get("height", 0),
            "stopDistance": args.stop_distance,
            "maxTicks": args.max_ticks,
            "maxWalkDistance": args.max_walk_distance,
            "stopOnCombat": True,
            "stopOnStall": True,
        })
        diagnostics = print_batch_summary(
            batch, mode, target, walk_target, preview, result,
            batch_start_player, should_run, run_reason, run_monitor,
            estimated_run_cost, args)
        player = player_from(result)
        before_hitpoints = int(batch_start_player.get("hitpoints", batch_start_player.get("hp", 0)) or 0)
        after_hitpoints = int(player.get("hitpoints", player.get("hp", 0)) or 0)
        write_evidence(args, "route_batch", {
            "batch": batch,
            "tool": "route_runner",
            "targetPlace": target_place["id"],
            "targetPlaceTile": target_place["tile"],
            "mode": mode,
            "currentTile": current_tile,
            "previousTile": current_tile,
            "targetTile": target,
            "walkTarget": walk_target,
            "finalTile": player_tile(player),
            "tile": player_tile(player),
            "target": walk_target,
            "runEnabled": bool(diagnostics["runAtWalkStart"]["enabled"]),
            "runEnergySpent": int(diagnostics["runEnergySpent"]),
            "batchTicks": int(result.get("batchTicks") or 0),
            "hitpointsLost": max(0, before_hitpoints - after_hitpoints),
            "isDead": bool(player.get("isDead", False)),
            "isInCombat": bool(player.get("isInCombat", False)),
            "batchStatus": result.get("batchStatus"),
            "plan": compact_plan(plan),
            "preview": compact_preview(preview, target, mode),
            "runPolicy": {
                **run_policy,
                "batchHazards": batch_hazards[:5],
                "wouldRun": should_run,
                "reason": run_reason,
                "estimatedRunCost": estimated_run_cost,
                "forceRunBeforeLongLeg": force_run,
            },
            "runEfficiency": diagnostics,
            "result": {
                "success": bool(result.get("success")),
                "batchStatus": result.get("batchStatus"),
                "complete": bool(result.get("complete")),
                "message": result.get("message"),
                "batchTicks": int(result.get("batchTicks") or 0),
            },
            "playerBefore": compact_player(batch_start_player),
            "playerAfter": compact_player(player),
        })
        if not is_success(result):
            return 4
        if player.get("isDead") or player.get("isInCombat"):
            return 5
        if arrived(player, target_place["tile"], arrival_radius):
            log("arrived target={} tile={}".format(target_place["id"], tile_str(player_tile(player))))
            return 0

    current_tile = player_tile(player)
    log("max batches reached target={} final={}".format(target_place["id"], tile_str(current_tile)))
    return 1


def main(argv=None):
    global RUN_PROFILE
    argv_list = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Run learned routes with local server-path preview.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "",
                        help="Use this profile's bridge session and matching trace profile.")
    parser.add_argument("--to", required=True, help="Target place id/name or x,y,h tile.")
    parser.add_argument("--orient", action="store_true",
                        help="Observe, plan, route-eval, preview, and optionally render one context map without moving.")
    parser.add_argument("--json", action="store_true",
                        help="For --orient, emit one compact JSON object.")
    parser.add_argument("--max-batches", type=int, default=4)
    parser.add_argument("--max-ticks", type=int, default=120)
    parser.add_argument("--max-walk-distance", type=int, default=48,
                        help="Per-click bridge walk chunk. The server caps this to the local region margin.")
    parser.add_argument("--stop-distance", type=int, default=0)
    parser.add_argument("--arrival-radius", type=int, default=None)
    parser.add_argument("--enable-run", action="store_true", default=True)
    parser.add_argument("--no-enable-run", dest="enable_run", action="store_false")
    parser.add_argument("--run-reserve", default="none",
                        help="none, auto, or an integer run-energy reserve to keep before non-hazard batches.")
    parser.add_argument("--run-reserve-buffer", type=int, default=0,
                        help="Extra energy added to the fixed/auto reserve.")
    parser.add_argument("--run-reserve-waypoints", type=int, default=12,
                        help="Number of planned waypoints to scan for auto run reserve hazards.")
    parser.add_argument("--run-diagnostics-min-steps", type=int, default=8,
                        help="Minimum preview path length before warning about walking-speed run batches.")
    parser.add_argument("--run-walk-warning-ticks-per-step", type=float, default=0.85,
                        help="Warn when a run-requested batch takes at least this many ticks per preview step.")
    parser.add_argument("--run-warning-max-energy-spent", type=int, default=0,
                        help="Warn only when integer run energy spent is at or below this value.")
    parser.add_argument("--force-run-before-long-leg", action="store_true", default=True,
                        help="Issue set_run true immediately before long run-approved batches, even if run already appears enabled.")
    parser.add_argument("--no-force-run-before-long-leg", dest="force_run_before_long_leg", action="store_false",
                        help="Do not refresh run state before long run-approved batches.")
    parser.add_argument("--force-run-min-preview-steps", type=int, default=8,
                        help="Minimum preview path length that counts as a long leg for the pre-batch run refresh.")
    parser.add_argument("--evidence-jsonl", default="",
                        help="Append structured per-batch route/run-efficiency evidence to this JSONL file.")
    parser.add_argument("--route-definition", default="",
                        help="Execute compact routeSteps from a saved 2006scape route definition instead of re-planning each batch.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-frontier", action="store_true",
                        help="If the target is not connected, move to the best learned frontier.")
    parser.add_argument("--direct-if-preview", action="store_true",
                        help="If no graph route exists, allow a nearby direct target only after clipped preview.")
    parser.add_argument("--direct-preview-distance", type=int, default=24)
    parser.add_argument("--probe-toward-target", action="store_true",
                        help="If the learned graph ends here, probe one clipped batch toward the target.")
    parser.add_argument("--probe-distance", type=int, default=18)
    parser.add_argument("--probe-search-radius", type=int, default=8)
    parser.add_argument("--probe-stride", type=int, default=4)
    parser.add_argument("--probe-max-candidates", type=int, default=80)
    parser.add_argument("--frontier-wrong-way-tolerance", type=int, default=2,
                        help="Prefer a target-directed probe when a no-route frontier's next step increases target distance by more than this.")
    parser.add_argument("--combat-level", type=int, default=3)
    parser.add_argument("--allow-lethal", action="store_true")
    parser.add_argument("--allow-failed-traces", action="store_true")
    parser.add_argument("--include-partial", action="store_true")
    parser.add_argument("--include-derived", action="store_true")
    parser.add_argument("--include-unverified", action="store_true")
    parser.add_argument("--trace-file", action="append")
    parser.add_argument("--trace-profile",
                        default=os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "",
                        help="Only use traces recorded by this player/profile.")
    parser.add_argument("--include-unscoped-traces", action="store_true",
                        help="When filtering by profile, also include legacy traces with no player name.")
    parser.add_argument("--graph-snap-distance", type=int, default=16)
    parser.add_argument("--hazard-buffer", type=int, default=10)
    parser.add_argument("--failure-buffer", type=int, default=8)
    parser.add_argument("--max-static-leg", type=int, default=32)
    parser.add_argument("--max-batch-distance", type=int, default=24)
    parser.add_argument("--compress-gap", type=int, default=18)
    parser.add_argument("--max-warnings", type=int, default=8)
    parser.add_argument("--orient-max-suspects", type=int, default=5)
    parser.add_argument("--orient-map", action="store_true", default=True)
    parser.add_argument("--no-orient-map", dest="orient_map", action="store_false")
    parser.add_argument("--orient-map-qualities", nargs="*", default=["suspicious", "bad"])
    parser.add_argument("--orient-map-radius", type=int, default=80)
    parser.add_argument("--orient-map-pixels-per-tile", type=int, default=4)
    args = parser.parse_args(argv_list)
    log_usage("route_runner", surface="full", argv=argv_list)
    if args.profile and not args.trace_profile:
        args.trace_profile = args.profile
    RUN_PROFILE = args.profile
    if args.orient:
        return orient(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
