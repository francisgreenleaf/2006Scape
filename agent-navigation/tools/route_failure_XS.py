#!/usr/bin/env python3
"""Compact route execution failure/status summary from route evidence JSONL."""

import argparse
import json
from pathlib import Path

from usage_log import log_usage
from xs_common import ROOT, dump, tile


DEFAULT_EVIDENCE = ROOT / "agent-navigation" / ".local" / "run-evidence" / "ml-route-executor.routes.jsonl"


def latest_evidence_path():
    root = ROOT / "agent-navigation" / ".local" / "run-evidence"
    if not root.exists():
        return DEFAULT_EVIDENCE
    paths = sorted(root.glob("*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    return paths[0] if paths else DEFAULT_EVIDENCE


def compact_player(value):
    if not isinstance(value, dict):
        return {}
    return {
        "tile": tile(value.get("tile") if isinstance(value.get("tile"), dict) else value),
        "hp": value.get("hitpoints", value.get("hp")),
        "max": value.get("maxHitpoints", value.get("maxHp")),
        "run": value.get("runEnergy"),
        "runOn": value.get("runEnabled"),
        "food": value.get("foodCount"),
        "coins": value.get("coins"),
        "combat": value.get("isInCombat"),
        "dead": value.get("isDead"),
    }


def summarize(path, route_id="", limit=8):
    batches = []
    outcomes = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if route_id and record.get("routeId") != route_id:
                continue
            if record.get("event") == "route_batch":
                batches.append(record)
            elif record.get("event") == "route_outcome":
                outcomes.append(record)
    last_outcome = outcomes[-1] if outcomes else {}
    recent_batches = batches[-limit:]
    failures = [
        item for item in batches
        if not item.get("success") or item.get("isDead") or item.get("isInCombat")
        or int(item.get("hitpointsLost") or 0) > 0
    ][-limit:]
    last_batch = batches[-1] if batches else {}
    return {
        "ok": bool(batches or outcomes),
        "path": str(path),
        "routeId": route_id or last_outcome.get("routeId") or last_batch.get("routeId"),
        "status": last_outcome.get("status") or last_batch.get("batchStatus"),
        "success": last_outcome.get("success"),
        "target": last_outcome.get("targetPlace") or last_batch.get("targetPlace"),
        "from": last_outcome.get("from"),
        "to": last_outcome.get("to"),
        "final": last_outcome.get("final") or tile(last_batch.get("finalTile")),
        "hpLost": last_outcome.get("hitpointsLost"),
        "dead": last_outcome.get("isDead") or last_batch.get("isDead"),
        "combat": last_outcome.get("isInCombat") or last_batch.get("isInCombat"),
        "enemy": last_outcome.get("enemy") or last_batch.get("enemy"),
        "routeQuality": last_outcome.get("routeQuality") or last_batch.get("routeQuality"),
        "routeMode": last_outcome.get("routeMode") or last_batch.get("routeMode"),
        "stepCount": last_outcome.get("routeStepCount"),
        "lastBatch": compact_batch(last_batch),
        "failures": [compact_batch(item) for item in failures],
        "recent": [compact_batch(item) for item in recent_batches],
    }


def compact_batch(item):
    if not isinstance(item, dict):
        return {}
    return {
        "at": item.get("timestamp"),
        "batch": item.get("batch"),
        "ok": item.get("success"),
        "status": item.get("batchStatus"),
        "from": tile(item.get("currentTile")),
        "target": tile(item.get("targetTile")),
        "final": tile(item.get("finalTile")),
        "ticks": item.get("batchTicks"),
        "hpLost": item.get("hitpointsLost"),
        "dead": item.get("isDead"),
        "combat": item.get("isInCombat"),
        "enemy": item.get("enemy"),
        "before": compact_player(item.get("playerBefore")),
        "after": compact_player(item.get("playerAfter")),
    }


def main():
    parser = argparse.ArgumentParser(description="Summarize route executor evidence in compact form.")
    parser.add_argument("--evidence-jsonl", default="")
    parser.add_argument("--route-id", default="")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    log_usage("route_failure_XS", surface="xs", argv=vars(args))
    path = Path(args.evidence_jsonl) if args.evidence_jsonl else latest_evidence_path()
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        dump({"ok": False, "error": "route evidence JSONL not found", "path": str(path)})
        return 1
    dump(summarize(path, route_id=args.route_id, limit=max(1, args.limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
