"""Route outcome feedback capture for ML routing."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from .common import parse_tile, tile_key, utcnow
from .planner import DEFAULT_ROUTE_EVIDENCE_JSONL


SUCCESS_STATUSES = set(["success", "arrived", "ok", "complete"])


def _split_values(values: List[str] | None) -> List[str]:
    result: List[str] = []
    for value in values or []:
        for part in str(value).split(","):
            text = part.strip()
            if text:
                result.append(text)
    return result


def _enemy(args: SimpleNamespace) -> Dict[str, Any]:
    tile = parse_tile(args.enemy_tile)
    enemy = {
        "name": args.enemy_name or "",
        "combatLevel": args.enemy_level,
        "tile": tile,
        "aggressive": args.enemy_aggressive,
    }
    return {key: value for key, value in enemy.items() if value not in (None, "", [], {})}


def outcome_record(args: SimpleNamespace) -> Dict[str, Any]:
    status = str(args.status or "unknown").strip().lower()
    final_tile = parse_tile(args.final)
    target_tile = parse_tile(args.target_tile)
    start_tile = parse_tile(args.from_tile)
    record = {
        "schemaVersion": 1,
        "event": "route_outcome",
        "timestamp": utcnow().isoformat().replace("+00:00", "Z"),
        "source": args.source,
        "profile": args.profile or "",
        "routeId": args.route_id or "",
        "status": status,
        "success": bool(args.success or status in SUCCESS_STATUSES),
        "failureKind": args.failure_kind or "",
        "problemKind": args.problem_kind or "",
        "targetPlace": args.to,
        "from": tile_key(start_tile),
        "to": tile_key(target_tile),
        "final": tile_key(final_tile),
        "fromTile": start_tile,
        "targetTile": target_tile,
        "finalTile": final_tile,
        "hitpointsLost": int(args.hitpoints_lost or 0),
        "isDead": bool(args.is_dead or status == "death"),
        "isInCombat": bool(args.is_in_combat or status == "combat"),
        "runEnabled": args.run_enabled,
        "runEnergySpent": int(args.run_energy_spent or 0),
        "routeQuality": args.route_quality or "",
        "routeMode": args.route_mode or "",
        "routeDistance": args.route_distance,
        "routeStepCount": args.route_step_count,
        "hazardIds": _split_values(args.hazard_id),
        "enemy": _enemy(args),
        "notes": args.notes or "",
    }
    return {key: value for key, value in record.items() if value not in (None, "", [], {})}


def record_outcome(args: SimpleNamespace) -> Dict[str, Any]:
    path = Path(args.evidence_jsonl or DEFAULT_ROUTE_EVIDENCE_JSONL)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = outcome_record(args)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    return {
        "success": True,
        "output": str(path),
        "record": record,
    }
