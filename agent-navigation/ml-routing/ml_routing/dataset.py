"""Dataset export for learned 2006Scape route intelligence."""

from __future__ import annotations

from collections import Counter
import datetime as dt
import math
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from . import VERSION
from .common import compact_counter, distance, iter_jsonl, parse_tile, tile_key, utcnow, write_json, write_jsonl
from .paths import ARTIFACT_ROOT, NAV_ROOT, ensure_artifact_dirs, ensure_tool_imports, portable_artifact_path, timestamp_id


def _load_nav_modules():
    ensure_tool_imports()
    import navdb  # type: ignore

    return navdb


def _status_penalty(status: str) -> float:
    if status in ("verified", "learned-graph"):
        return 0.0
    if status == "learned-partial":
        return 80.0
    if status == "derived-from-existing-landmark":
        return 300.0
    if status == "needs-verification":
        return 900.0
    return 2000.0


def _finite_tile_distance(left: Dict[str, int], right: Dict[str, int]) -> float:
    navdb = _load_nav_modules()
    dist = navdb.distance(left, right)
    if math.isfinite(dist):
        return dist
    return max(abs(left["x"] - right["x"]), abs(left["y"] - right["y"]), 1)


def _nearest_hazard(db: Dict[str, Any], tile: Dict[str, int]) -> Dict[str, Any]:
    navdb = _load_nav_modules()
    best = None
    for hazard in db.get("hazards", []):
        dist = navdb.distance(tile, hazard.get("center", {}))
        if best is None or dist < best["distance"]:
            best = {
                "id": hazard.get("id"),
                "risk": hazard.get("risk", "unknown"),
                "distance": dist,
                "radius": hazard.get("radius", 0),
            }
    return best or {"id": None, "risk": "none", "distance": None, "radius": 0}


def _edge_record(db: Dict[str, Any], edge: Dict[str, Any], profile: str, generated_at: str) -> Dict[str, Any]:
    navdb = _load_nav_modules()
    from_tile = navdb.tile_from_key(edge["from"])
    to_tile = navdb.tile_from_key(edge["to"])
    edge_distance = _finite_tile_distance(from_tile, to_tile)
    attempts = int(edge.get("attempts") or 0)
    successes = int(edge.get("successes") or 0)
    failures = int(edge.get("failures") or 0)
    ticks = int(edge.get("ticks") or 0)
    combat_ticks = int(edge.get("combatTicks") or 0)
    hp_lost = int(edge.get("hitpointsLost") or 0)
    object_interactions = int(edge.get("objectInteractions") or 0)
    hazard = _nearest_hazard(db, to_tile)
    avg_ticks = float(ticks) / max(1, successes)
    failure_rate = float(failures) / max(1, attempts)
    combat_rate = float(combat_ticks) / max(1, ticks)
    hp_loss_per_attempt = float(hp_lost) / max(1, attempts)
    risk_score = min(1.0, failure_rate + (combat_rate * 0.6) + min(0.4, hp_loss_per_attempt / 20.0))
    confidence = min(0.99, (float(successes) + 1.0) / (float(attempts) + 3.0))
    return {
        "schemaVersion": 1,
        "recordType": "edge_example",
        "generatedAt": generated_at,
        "profile": profile or "",
        "from": edge["from"],
        "to": edge["to"],
        "fromTile": from_tile,
        "toTile": to_tile,
        "distance": edge_distance,
        "samePlane": from_tile.get("height", 0) == to_tile.get("height", 0),
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "ticks": ticks,
        "averageTicks": round(avg_ticks, 4),
        "baseCost": round(navdb.edge_cost(edge), 4),
        "runTicks": int(edge.get("runTicks") or 0),
        "walkTicks": int(edge.get("walkTicks") or 0),
        "energySpent": int(edge.get("energySpent") or 0),
        "combatTicks": combat_ticks,
        "hitpointsLost": hp_lost,
        "failureRate": round(failure_rate, 6),
        "combatRate": round(combat_rate, 6),
        "hpLossPerAttempt": round(hp_loss_per_attempt, 4),
        "riskScore": round(risk_score, 6),
        "confidence": round(confidence, 6),
        "events": edge.get("events", {}),
        "tools": edge.get("tools", {}),
        "traceIds": compact_counter(edge.get("traceIds", {}), limit=8),
        "objectInteractions": object_interactions,
        "objects": compact_counter(edge.get("objects", {}), limit=8),
        "objectOptions": edge.get("objectOptions", {}),
        "objectPhases": edge.get("objectPhases", {}),
        "routeBatchSamples": int(edge.get("routeBatchSamples") or 0),
        "runRequestedBatches": int(edge.get("runRequestedBatches") or 0),
        "runEffectiveBatches": int(edge.get("runEffectiveBatches") or 0),
        "runIneffectiveBatches": int(edge.get("runIneffectiveBatches") or 0),
        "expectedRunSpend": int(edge.get("expectedRunSpend") or 0),
        "expectedSavedTicksFromRun": int(edge.get("expectedSavedTicksFromRun") or 0),
        "observedSavedTicksVsWalkEstimate": int(edge.get("observedSavedTicksVsWalkEstimate") or 0),
        "observedExtraTicksVsRunEstimate": int(edge.get("observedExtraTicksVsRunEstimate") or 0),
        "inferredReverse": int(edge.get("inferredReverse") or 0),
        "nearestHazard": hazard,
        "lastSeen": edge.get("lastSeen", ""),
    }


def edge_examples(profile: str = "", include_unscoped: bool = False,
                  include_agent_batch: bool = False, include_legacy_recorder: bool = False,
                  extra_trace_paths: Optional[List[str]] = None, generated_at: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    navdb = _load_nav_modules()
    db = navdb.load_db()
    generated_at = generated_at or utcnow().isoformat().replace("+00:00", "Z")
    graph = navdb.build_trace_graph(
        extra_paths=extra_trace_paths,
        profile=profile,
        include_unscoped=include_unscoped,
        include_agent_batch=include_agent_batch,
        include_legacy_recorder=include_legacy_recorder,
    )
    records = [
        _edge_record(db, edge, profile, generated_at)
        for _key, edge in sorted(graph["edges"].items(), key=lambda item: (item[0][0], item[0][1]))
    ]
    summary = {
        "traceRecords": graph["recordCount"],
        "traceSessions": graph["traceCount"],
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "blockers": len(graph["blockers"]),
    }
    return records, summary


def route_hint_edges(generated_at: Optional[str] = None) -> List[Dict[str, Any]]:
    navdb = _load_nav_modules()
    db = navdb.load_db()
    generated_at = generated_at or utcnow().isoformat().replace("+00:00", "Z")
    records = []
    for route in db["routes"]:
        from_place = navdb.find_place(db, route.get("from", ""))
        to_place = navdb.find_place(db, route.get("to", ""))
        tiles = []
        if from_place:
            tiles.append(from_place["tile"])
        for _step, tile in navdb.route_walk_tiles(route):
            if not tiles or navdb.tile_key(tiles[-1]) != navdb.tile_key(tile):
                tiles.append(tile)
        if to_place and (not tiles or navdb.tile_key(tiles[-1]) != navdb.tile_key(to_place["tile"])):
            tiles.append(to_place["tile"])
        for index, (left, right) in enumerate(zip(tiles, tiles[1:])):
            dist = _finite_tile_distance(left, right)
            records.append({
                "schemaVersion": 1,
                "recordType": "route_hint_edge",
                "generatedAt": generated_at,
                "routeId": route.get("id"),
                "routeStatus": route.get("status", "unknown"),
                "routeIndex": index,
                "from": navdb.tile_key(left),
                "to": navdb.tile_key(right),
                "fromTile": left,
                "toTile": right,
                "distance": dist,
                "bidirectional": bool(route.get("bidirectional")),
                "objectStepCount": sum(1 for step in route.get("steps", []) if navdb.is_object_step(step)),
                "statusPenalty": _status_penalty(route.get("status", "unknown")),
                "hintCost": max(1.0, dist) + _status_penalty(route.get("status", "unknown")),
            })
    return records


def _route_evidence_files(include_local: bool = True) -> List[Path]:
    candidates = []
    if include_local:
        candidates.extend((NAV_ROOT / ".local" / "run-evidence").glob("*.jsonl"))
    candidates.extend((NAV_ROOT / "data").rglob("*.routes.jsonl"))
    candidates.extend((NAV_ROOT / "data" / "marathons").glob("*.jsonl"))
    seen = set()
    files = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        files.append(path)
    return sorted(files)


def _extract_tile(record: Dict[str, Any], *keys: str) -> Optional[Dict[str, int]]:
    for key in keys:
        value = record.get(key)
        tile = parse_tile(value)
        if tile:
            return tile
        if isinstance(value, dict):
            for nested in ("tile", "currentTile", "finalTile"):
                tile = parse_tile(value.get(nested))
                if tile:
                    return tile
    return None


def route_attempts(include_local: bool = True, generated_at: Optional[str] = None) -> List[Dict[str, Any]]:
    generated_at = generated_at or utcnow().isoformat().replace("+00:00", "Z")
    records = []
    for path in _route_evidence_files(include_local=include_local):
        for record in iter_jsonl(path):
            event = str(record.get("event") or "")
            if event not in ("route_batch", "batch", "leg_end", "leg_preflight", "route_outcome"):
                continue
            status = str(record.get("batchStatus") or record.get("status") or record.get("resultStatus") or "")
            success = status in ("arrived", "ok", "success", "complete") or record.get("success") is True
            start_tile = _extract_tile(record, "playerBefore", "startState", "previousTile")
            final_tile = _extract_tile(record, "playerAfter", "finalTile", "tile", "currentTile")
            target_tile = _extract_tile(record, "targetTile", "target", "targetPlaceTile")
            run_efficiency = record.get("runEfficiency") if isinstance(record.get("runEfficiency"), dict) else {}
            records.append({
                "schemaVersion": 1,
                "recordType": "route_attempt",
                "generatedAt": generated_at,
                "sourcePath": str(path),
                "sourceLine": record.get("_sourceLine"),
                "event": event,
                "status": status or "unknown",
                "success": bool(success),
                "targetPlace": record.get("targetPlace") or record.get("target"),
                "from": tile_key(start_tile),
                "to": tile_key(target_tile),
                "final": tile_key(final_tile),
                "fromTile": start_tile,
                "targetTile": target_tile,
                "finalTile": final_tile,
                "batchTicks": int(record.get("batchTicks") or record.get("gameTicks") or 0),
                "durationSeconds": record.get("durationSeconds"),
                "hitpointsLost": int(record.get("hitpointsLost") or 0),
                "isDead": bool(record.get("isDead")),
                "isInCombat": bool(record.get("isInCombat")),
                "runEnabled": record.get("runEnabled"),
                "runEnergySpent": int(record.get("runEnergySpent") or 0),
                "runEfficiency": run_efficiency,
                "preview": record.get("preview") if isinstance(record.get("preview"), dict) else {},
                "planStatus": (record.get("plan") or {}).get("status") if isinstance(record.get("plan"), dict) else None,
                "routeId": record.get("routeId"),
                "routeQuality": record.get("routeQuality"),
                "routeMode": record.get("routeMode"),
                "routeDistance": record.get("routeDistance"),
                "routeStepCount": record.get("routeStepCount"),
                "failureKind": record.get("failureKind"),
                "problemKind": record.get("problemKind"),
                "hazardIds": record.get("hazardIds") or [],
                "enemy": record.get("enemy") if isinstance(record.get("enemy"), dict) else {},
                "notes": record.get("notes"),
            })
    return records


def object_transitions(profile: str = "", include_unscoped: bool = False,
                       generated_at: Optional[str] = None) -> List[Dict[str, Any]]:
    navdb = _load_nav_modules()
    generated_at = generated_at or utcnow().isoformat().replace("+00:00", "Z")
    records = []
    for record in navdb.iter_movement_traces(profile=profile, include_unscoped=include_unscoped):
        info = navdb.object_info_from_record(record)
        if info is None:
            continue
        tile = navdb.tile_from_record(record, "tile")
        previous = navdb.tile_from_record(record, "previousTile")
        records.append({
            "schemaVersion": 1,
            "recordType": "object_transition",
            "generatedAt": generated_at,
            "profile": profile or "",
            "sourcePath": record.get("_sourcePath"),
            "sourceLine": record.get("_sourceLine"),
            "event": record.get("event"),
            "phase": info.get("phase"),
            "option": info.get("option"),
            "objectId": info.get("objectId"),
            "objectName": info.get("name"),
            "objectTile": info.get("tile"),
            "from": navdb.tile_key(previous) if previous else "",
            "to": navdb.tile_key(tile) if tile else "",
            "fromTile": previous,
            "toTile": tile,
            "success": not navdb.is_trace_failure(record),
            "hitpointsLost": int(record.get("hitpointsLost") or 0),
            "isInCombat": navdb.record_in_combat(record),
        })
    return records


def export_dataset(args: SimpleNamespace) -> Dict[str, Any]:
    ensure_artifact_dirs()
    now = utcnow()
    run_id = args.run_id or timestamp_id(now)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else ARTIFACT_ROOT / "datasets" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = now.isoformat().replace("+00:00", "Z")

    edges, graph_summary = edge_examples(
        profile=args.profile,
        include_unscoped=args.include_unscoped_traces,
        include_agent_batch=args.include_agent_batch_traces,
        include_legacy_recorder=args.include_legacy_recorder_traces,
        extra_trace_paths=args.trace_file,
        generated_at=generated_at,
    )
    hints = route_hint_edges(generated_at=generated_at)
    attempts = route_attempts(include_local=not args.no_local_evidence, generated_at=generated_at)
    transitions = object_transitions(
        profile=args.profile,
        include_unscoped=args.include_unscoped_traces,
        generated_at=generated_at,
    )

    counts = {
        "edgeExamples": write_jsonl(output_dir / "edge_examples.jsonl", edges),
        "routeHintEdges": write_jsonl(output_dir / "route_hint_edges.jsonl", hints),
        "routeAttempts": write_jsonl(output_dir / "route_attempts.jsonl", attempts),
        "objectTransitions": write_jsonl(output_dir / "object_transitions.jsonl", transitions),
    }
    statuses = Counter(str(item.get("status") or "") for item in attempts)
    qualities = Counter(str((item.get("runEfficiency") or {}).get("warning") or "") for item in attempts)
    summary = {
        "schemaVersion": 1,
        "pipelineVersion": VERSION,
        "runId": run_id,
        "generatedAt": generated_at,
        "profile": args.profile or "",
        "outputDir": portable_artifact_path(output_dir),
        "counts": counts,
        "graph": graph_summary,
        "routeAttemptStatuses": dict(statuses),
        "routeAttemptRunWarnings": dict(qualities),
        "inputs": {
            "includeAgentBatchTraces": args.include_agent_batch_traces,
            "includeLegacyRecorderTraces": args.include_legacy_recorder_traces,
            "includeUnscopedTraces": args.include_unscoped_traces,
            "traceFile": args.trace_file or [],
        },
    }
    write_json(output_dir / "summary.json", summary)
    write_json(ARTIFACT_ROOT / "datasets" / "latest.json", summary)
    return summary
