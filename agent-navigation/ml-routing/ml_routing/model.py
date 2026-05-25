"""Training and scoring for the first 2006Scape route edge model."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Tuple

from . import VERSION
from .common import chunked, distance, iter_jsonl, parse_tile, tile_key, utcnow, write_json
from .paths import ARTIFACT_ROOT, ensure_artifact_dirs, latest_json, portable_artifact_path, resolve_artifact_path, timestamp_id


MODEL_TYPE = "empirical_edge_cost_risk_v1"


def _region_key(tile: Dict[str, int], size: int = 8) -> str:
    return "{},{},{}".format(int(tile["x"]) // size, int(tile["y"]) // size, int(tile.get("height", 0)))


def _empty_stats() -> Dict[str, float]:
    return {
        "count": 0.0,
        "attempts": 0.0,
        "successes": 0.0,
        "failures": 0.0,
        "ticks": 0.0,
        "distance": 0.0,
        "combatTicks": 0.0,
        "hitpointsLost": 0.0,
        "objectInteractions": 0.0,
        "routeBatchSamples": 0.0,
        "runEffectiveBatches": 0.0,
        "runIneffectiveBatches": 0.0,
    }


def _merge_stats(left: Dict[str, float], right: Dict[str, float]) -> Dict[str, float]:
    for key, value in right.items():
        left[key] = left.get(key, 0.0) + float(value)
    return left


def _record_stats(record: Dict[str, Any]) -> Dict[str, float]:
    stats = _empty_stats()
    stats["count"] = 1.0
    for key in ("attempts", "successes", "failures", "ticks", "distance", "combatTicks",
                "hitpointsLost", "objectInteractions", "routeBatchSamples",
                "runEffectiveBatches", "runIneffectiveBatches"):
        value = float(record.get(key) or 0.0)
        stats[key] = value if math.isfinite(value) else 0.0
    return stats


def _aggregate_chunk(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    edge_stats = {}
    region_stats = defaultdict(_empty_stats)
    object_stats = defaultdict(_empty_stats)
    global_stats = _empty_stats()
    for record in records:
        stats = _record_stats(record)
        _merge_stats(global_stats, stats)
        edge_key = "{}>{}".format(record.get("from"), record.get("to"))
        edge_stats[edge_key] = _merge_stats(edge_stats.get(edge_key, _empty_stats()), stats)
        to_tile = parse_tile(record.get("toTile"))
        if to_tile:
            _merge_stats(region_stats[_region_key(to_tile)], stats)
        if int(record.get("objectInteractions") or 0) > 0:
            for item in record.get("objects") or []:
                _merge_stats(object_stats[str(item.get("key") or "unknown")], stats)
    return {
        "global": global_stats,
        "edges": edge_stats,
        "regions": dict(region_stats),
        "objects": dict(object_stats),
    }


def _finalize_stats(stats: Dict[str, float], prior: Dict[str, float] | None = None) -> Dict[str, Any]:
    prior = prior or {}
    attempts = stats.get("attempts", 0.0)
    successes = stats.get("successes", 0.0)
    failures = stats.get("failures", 0.0)
    ticks = stats.get("ticks", 0.0)
    distance_total = stats.get("distance", 0.0)
    count = stats.get("count", 0.0)
    avg_ticks = ticks / max(1.0, successes)
    avg_distance = distance_total / max(1.0, count)
    failure_rate = (failures + prior.get("failures", 1.0)) / max(1.0, attempts + prior.get("attempts", 8.0))
    combat_rate = stats.get("combatTicks", 0.0) / max(1.0, ticks)
    hp_per_attempt = stats.get("hitpointsLost", 0.0) / max(1.0, attempts)
    object_rate = stats.get("objectInteractions", 0.0) / max(1.0, attempts)
    run_batches = stats.get("runEffectiveBatches", 0.0) + stats.get("runIneffectiveBatches", 0.0)
    run_effective_rate = stats.get("runEffectiveBatches", 0.0) / max(1.0, run_batches)
    risk = min(1.0, failure_rate + (combat_rate * 0.6) + min(0.35, hp_per_attempt / 20.0))
    confidence = min(0.99, (successes + 1.0) / (attempts + 3.0))
    return {
        "count": int(count),
        "attempts": int(attempts),
        "successes": int(successes),
        "failures": int(failures),
        "averageTicks": round(avg_ticks, 5),
        "averageDistance": round(avg_distance, 5),
        "failureRate": round(failure_rate, 6),
        "combatRate": round(combat_rate, 6),
        "hpLossPerAttempt": round(hp_per_attempt, 5),
        "objectInteractionRate": round(object_rate, 6),
        "runEffectiveRate": round(run_effective_rate, 6),
        "riskScore": round(risk, 6),
        "confidence": round(confidence, 6),
    }


def _finite_distance(left: Dict[str, int], right: Dict[str, int]) -> float:
    dist = distance(left, right)
    if math.isfinite(dist):
        return dist
    return max(abs(left["x"] - right["x"]), abs(left["y"] - right["y"]), 1)


def _route_attempt_training_record(record: Dict[str, Any]) -> Dict[str, Any] | None:
    from_tile = parse_tile(record.get("fromTile") or record.get("from"))
    enemy = record.get("enemy") if isinstance(record.get("enemy"), dict) else {}
    to_tile = parse_tile(enemy.get("tile")) if enemy else None
    if not to_tile:
        to_tile = parse_tile(record.get("finalTile") or record.get("final"))
    if not to_tile:
        to_tile = parse_tile(record.get("targetTile") or record.get("to"))
    if not from_tile or not to_tile:
        return None
    success = bool(record.get("success"))
    status = str(record.get("status") or "")
    combat = bool(record.get("isInCombat")) or bool(enemy) or status == "combat"
    return {
        "from": tile_key(from_tile),
        "to": tile_key(to_tile),
        "fromTile": from_tile,
        "toTile": to_tile,
        "attempts": 1,
        "successes": 1 if success else 0,
        "failures": 0 if success else 1,
        "ticks": int(record.get("batchTicks") or max(1, _finite_distance(from_tile, to_tile))),
        "distance": _finite_distance(from_tile, to_tile),
        "combatTicks": 1 if combat else 0,
        "hitpointsLost": int(record.get("hitpointsLost") or 0),
        "objectInteractions": 0,
        "routeBatchSamples": 1,
        "runEffectiveBatches": 0,
        "runIneffectiveBatches": 0,
    }


def _load_edges(dataset_dir: Path) -> List[Dict[str, Any]]:
    records = list(iter_jsonl(dataset_dir / "edge_examples.jsonl"))
    for attempt in iter_jsonl(dataset_dir / "route_attempts.jsonl"):
        training_record = _route_attempt_training_record(attempt)
        if training_record:
            records.append(training_record)
    return records


def train_model(args: SimpleNamespace) -> Dict[str, Any]:
    ensure_artifact_dirs()
    dataset_dir = Path(args.dataset_dir).resolve() if args.dataset_dir else None
    if dataset_dir is None:
        latest = latest_json(ARTIFACT_ROOT / "datasets", "latest.json")
        if not latest:
            raise SystemExit("no dataset found; run export first")
        summary = __import__("json").load(latest.open())
        dataset_dir = resolve_artifact_path(summary["outputDir"])
    records = _load_edges(dataset_dir)
    if not records:
        raise SystemExit("dataset has no edge examples: {}".format(dataset_dir))
    workers = max(1, int(args.workers or 1))
    pieces = chunked(records, workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        partials = list(executor.map(_aggregate_chunk, pieces))

    global_stats = _empty_stats()
    edge_stats: Dict[str, Dict[str, float]] = {}
    region_stats: Dict[str, Dict[str, float]] = {}
    object_stats: Dict[str, Dict[str, float]] = {}
    for partial in partials:
        _merge_stats(global_stats, partial["global"])
        for key, stats in partial["edges"].items():
            edge_stats[key] = _merge_stats(edge_stats.get(key, _empty_stats()), stats)
        for key, stats in partial["regions"].items():
            region_stats[key] = _merge_stats(region_stats.get(key, _empty_stats()), stats)
        for key, stats in partial["objects"].items():
            object_stats[key] = _merge_stats(object_stats.get(key, _empty_stats()), stats)

    global_final = _finalize_stats(global_stats, prior={"attempts": 0.0, "failures": 0.0})
    prior = {
        "attempts": max(4.0, global_stats.get("attempts", 0.0) / max(1.0, global_stats.get("count", 1.0))),
        "failures": max(0.25, global_final["failureRate"]),
    }
    finalized_edges = {key: _finalize_stats(stats, prior=prior) for key, stats in edge_stats.items()}
    finalized_regions = {key: _finalize_stats(stats, prior=prior) for key, stats in region_stats.items()}
    finalized_objects = {key: _finalize_stats(stats, prior=prior) for key, stats in object_stats.items()}

    now = utcnow()
    model_id = args.model_id or timestamp_id(now)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else ARTIFACT_ROOT / "models" / model_id
    output_dir.mkdir(parents=True, exist_ok=True)
    model = {
        "schemaVersion": 1,
        "pipelineVersion": VERSION,
        "modelType": MODEL_TYPE,
        "modelId": model_id,
        "trainedAt": now.isoformat().replace("+00:00", "Z"),
        "datasetDir": portable_artifact_path(dataset_dir),
        "modelPath": portable_artifact_path(output_dir / "model.json"),
        "training": {
            "workers": workers,
            "records": len(records),
            "threadedChunks": len(pieces),
            "method": "empirical Bayes edge/region/object aggregation plus route-attempt outcome risk",
        },
        "global": global_final,
        "edgeStats": finalized_edges,
        "regionStats": finalized_regions,
        "objectStats": finalized_objects,
        "weights": {
            "tick": 1.0,
            "riskPenalty": 950.0,
            "lowConfidencePenalty": 140.0,
            "detourPenalty": 220.0,
            "insideBuildingPenalty": 180.0,
            "objectInteractionPenalty": 25.0,
            "staleRoutePenalty": 90.0,
        },
    }
    write_json(output_dir / "model.json", model)
    if getattr(args, "update_latest", True):
        write_json(ARTIFACT_ROOT / "models" / "latest.json", {
            "modelPath": portable_artifact_path(output_dir / "model.json"),
            "modelId": model_id,
            "trainedAt": model["trainedAt"],
            "datasetDir": portable_artifact_path(dataset_dir),
        })
    return model


def load_model(path: str | None = None) -> Dict[str, Any] | None:
    import json

    if path:
        model_path = Path(path)
    else:
        latest = latest_json(ARTIFACT_ROOT / "models", "latest.json")
        if not latest:
            return None
        latest_payload = json.load(latest.open())
        model_path = resolve_artifact_path(latest_payload["modelPath"])
    if not model_path.exists():
        return None
    with model_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def segment_prediction(model: Dict[str, Any], from_tile: Dict[str, int], to_tile: Dict[str, int]) -> Dict[str, Any]:
    key = "{}>{}".format(tile_key(from_tile), tile_key(to_tile))
    edge = model.get("edgeStats", {}).get(key)
    source = "edge"
    if edge is None:
        region = model.get("regionStats", {}).get(_region_key(to_tile))
        edge = region
        source = "region"
    if edge is None:
        edge = model.get("global", {})
        source = "global"
    dist = distance(from_tile, to_tile)
    if not math.isfinite(dist):
        dist = max(abs(from_tile["x"] - to_tile["x"]), abs(from_tile["y"] - to_tile["y"]), 1)
    avg_distance = max(1.0, float(edge.get("averageDistance") or 1.0))
    avg_ticks = float(edge.get("averageTicks") or model.get("global", {}).get("averageTicks") or 1.0)
    predicted_ticks = avg_ticks * max(1.0, float(dist) / avg_distance)
    return {
        "source": source,
        "predictedTicks": round(predicted_ticks, 4),
        "riskScore": float(edge.get("riskScore") or 0.0),
        "confidence": float(edge.get("confidence") or 0.0),
        "failureRate": float(edge.get("failureRate") or 0.0),
        "combatRate": float(edge.get("combatRate") or 0.0),
    }
