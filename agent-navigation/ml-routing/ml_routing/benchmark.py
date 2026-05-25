"""Offline benchmarks for ML-ranked routing candidates."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from .common import utcnow, write_json
from .paths import ARTIFACT_ROOT, ensure_artifact_dirs, timestamp_id
from .planner import rank_routes


DEFAULT_CASES = [
    {"name": "lumbridge_to_varrock", "from": "lumbridge_castle_courtyard", "to": "varrock_square"},
    {"name": "lumbridge_to_falador", "from": "lumbridge_castle_courtyard", "to": "falador_shield_shop"},
    {"name": "falador_to_port_sarim", "from": "falador_shield_shop", "to": "port_sarim_dock"},
    {"name": "port_sarim_to_draynor", "from": "port_sarim_dock", "to": "draynor_bank"},
    {"name": "rimmington_to_port_sarim_south", "from": "rimmington_center", "to": "port_sarim_south_coast_frontier"},
    {"name": "varrock_to_barbarian_village", "from": "varrock_east_bank", "to": "barbarian_village"},
    {"name": "varrock_bank_to_general_store", "from": "varrock_west_bank", "to": "varrock_general_store"},
    {"name": "lumbridge_store_to_tree_stand", "from": "lumbridge_general_store", "to": "lumbridge_tree_stand"},
    {"name": "varrock_to_falador", "from": "varrock_square", "to": "falador_shield_shop"},
    {"name": "lumbridge_to_draynor_bank", "from": "lumbridge_castle_courtyard", "to": "draynor_bank"},
    {"name": "port_sarim_to_varrock", "from": "port_sarim_dock", "to": "varrock_square"},
    {"name": "rimmington_to_varrock", "from": "rimmington_center", "to": "varrock_square"},
    {"name": "falador_to_draynor_bank", "from": "falador_shield_shop", "to": "draynor_bank"},
    {"name": "draynor_bank_to_varrock", "from": "draynor_bank", "to": "varrock_square"},
    {"name": "barbarian_village_to_port_sarim", "from": "barbarian_village", "to": "port_sarim_dock"},
    {"name": "lumbridge_to_barbarian_village", "from": "lumbridge_castle_courtyard", "to": "barbarian_village"},
    {"name": "al_kharid_bank_to_scimitar_shop", "from": "al_kharid_bank", "to": "al_kharid_scimitar_shop"},
    {"name": "al_kharid_bank_to_varrock_east_bank", "from": "al_kharid_bank", "to": "varrock_east_bank"},
    {"name": "varrock_west_bank_to_sword_shop", "from": "varrock_west_bank", "to": "varrock_sword_shop"},
    {"name": "varrock_west_bank_to_falador_west_bank", "from": "varrock_west_bank", "to": "falador_west_bank"},
    {"name": "falador_west_bank_to_shield_shop", "from": "falador_west_bank", "to": "falador_shield_shop"},
    {"name": "falador_east_bank_to_port_sarim", "from": "falador_east_bank", "to": "port_sarim_dock"},
    {"name": "falador_west_bank_to_rimmington", "from": "falador_west_bank", "to": "rimmington_center"},
    {"name": "draynor_bank_to_port_sarim", "from": "draynor_bank", "to": "port_sarim_dock"},
    {"name": "draynor_bank_to_lumbridge_general_store", "from": "draynor_bank", "to": "lumbridge_general_store"},
    {"name": "edgeville_bank_to_varrock_west_bank", "from": "edgeville_bank", "to": "varrock_west_bank"},
    {"name": "edgeville_bank_to_barbarian_village", "from": "edgeville_bank", "to": "barbarian_village"},
    {"name": "catherby_bank_to_falador_west_bank", "from": "catherby_bank", "to": "falador_west_bank"},
    {"name": "ardougne_south_to_north_bank", "from": "ardougne_south_bank", "to": "ardougne_north_bank"},
    {"name": "ardougne_north_bank_to_gnome_agility", "from": "ardougne_north_bank", "to": "gnome_agility_course"},
]


def _case_args(base: SimpleNamespace, case: Dict[str, Any]) -> SimpleNamespace:
    values = vars(base).copy()
    values["from_tile"] = case["from"]
    values["to"] = case["to"]
    return SimpleNamespace(**values)


def run_benchmark(args: SimpleNamespace) -> Dict[str, Any]:
    ensure_artifact_dirs()
    cases = DEFAULT_CASES
    if args.limit:
        cases = cases[:args.limit]
    results = []
    for case in cases:
        ranked = rank_routes(_case_args(args, case))
        recommended = ranked.get("recommended", {})
        results.append({
            "name": case["name"],
            "from": case["from"],
            "to": case["to"],
            "actionable": recommended.get("actionable"),
            "status": recommended.get("status"),
            "quality": recommended.get("quality"),
            "score": recommended.get("score"),
            "estimatedTicks": recommended.get("estimatedTicks"),
            "routeDistance": recommended.get("routeDistance"),
            "detourRatio": recommended.get("detourRatio"),
            "targetDistanceIncreases": recommended.get("targetDistanceIncreases"),
            "mode": recommended.get("mode"),
            "edgeSources": recommended.get("edgeSources"),
            "selectedOverLearned": recommended.get("selectedOverLearned"),
            "directCandidate": recommended.get("directCandidate"),
            "routeStepCount": recommended.get("routeStepCount"),
            "routeSteps": recommended.get("routeSteps"),
            "runPlan": recommended.get("runPlan"),
            "runSegments": recommended.get("runSegments"),
            "mlScore": recommended.get("mlScore"),
            "next": recommended.get("next"),
            "routeRunnerCommand": recommended.get("routeRunnerCommand"),
        })
    ok_count = sum(1 for item in results if item.get("status") == "ok")
    actionable_count = sum(1 for item in results if item.get("actionable") is True)
    suspicious = sum(1 for item in results if item.get("quality") in ("suspicious", "bad"))
    now = utcnow()
    run_id = args.run_id or timestamp_id(now)
    report = {
        "schemaVersion": 1,
        "runId": run_id,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "caseCount": len(results),
        "okCount": ok_count,
        "actionableCount": actionable_count,
        "suspiciousOrBadCount": suspicious,
        "results": results,
    }
    output_dir = Path(args.output_dir).resolve() if args.output_dir else ARTIFACT_ROOT / "benchmarks" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    report["outputDir"] = str(output_dir)
    write_json(output_dir / "benchmark.json", report)
    write_json(ARTIFACT_ROOT / "benchmarks" / "latest.json", report)
    return report
