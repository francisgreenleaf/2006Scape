"""Agent-facing route ranking over deterministic candidates plus ML scores."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Tuple

from .common import distance, parse_tile, tile_key
from .model import load_model, segment_prediction
from .paths import ensure_tool_imports


DEFAULT_ROUTE_EVIDENCE_JSONL = "agent-navigation/.local/run-evidence/ml-route-runner.routes.jsonl"
DEFAULT_ROUTE_EXECUTOR_EVIDENCE_JSONL = "agent-navigation/.local/run-evidence/ml-route-executor.routes.jsonl"


def _load_nav_modules():
    ensure_tool_imports()
    import navdb  # type: ignore
    import router  # type: ignore
    import route_eval  # type: ignore

    return navdb, router, route_eval


def _install_route_call_caches(navdb: Any, router: Any):
    """Cache expensive trace graph reads inside one route request."""
    original_build_trace_graph = navdb.build_trace_graph
    original_failure_tiles = router.failure_tiles
    trace_graph_cache: Dict[Tuple[Any, ...], Any] = {}
    failure_cache: Dict[Tuple[Any, ...], Any] = {}

    def trace_key(extra_paths=None, profile=None, include_unscoped=False,
                  include_agent_batch=None, include_legacy_recorder=None):
        return (
            tuple(str(path) for path in (extra_paths or [])),
            profile or "",
            bool(include_unscoped),
            include_agent_batch,
            include_legacy_recorder,
        )

    def cached_build_trace_graph(extra_paths=None, profile=None, include_unscoped=False,
                                 include_agent_batch=None, include_legacy_recorder=None):
        key = trace_key(extra_paths, profile, include_unscoped, include_agent_batch, include_legacy_recorder)
        if key not in trace_graph_cache:
            trace_graph_cache[key] = original_build_trace_graph(
                extra_paths=extra_paths,
                profile=profile,
                include_unscoped=include_unscoped,
                include_agent_batch=include_agent_batch,
                include_legacy_recorder=include_legacy_recorder,
            )
        return trace_graph_cache[key]

    def cached_failure_tiles(args):
        key = (
            tuple(str(path) for path in (args.trace_file or [])),
            args.trace_profile or "",
            bool(args.include_unscoped_traces),
        )
        if key not in failure_cache:
            failure_cache[key] = original_failure_tiles(args)
        return failure_cache[key]

    navdb.build_trace_graph = cached_build_trace_graph
    router.failure_tiles = cached_failure_tiles

    def restore():
        navdb.build_trace_graph = original_build_trace_graph
        router.failure_tiles = original_failure_tiles

    return restore


def _base_args(args: SimpleNamespace, include_partial=False, include_derived=False,
               include_unverified=False, allow_failed=False) -> SimpleNamespace:
    return SimpleNamespace(
        from_tile=args.from_tile,
        to=args.to,
        combat_level=args.combat_level,
        food=args.food,
        coins=args.coins,
        run_energy=args.run_energy,
        run_enabled=args.run_enabled,
        allow_lethal=args.allow_lethal,
        allow_failed_traces=allow_failed,
        include_partial=include_partial,
        include_derived=include_derived,
        include_unverified=include_unverified,
        trace_file=args.trace_file,
        trace_profile=args.trace_profile,
        include_unscoped_traces=args.include_unscoped_traces,
        graph_snap_distance=args.graph_snap_distance,
        hazard_buffer=args.hazard_buffer,
        failure_buffer=args.failure_buffer,
        max_static_leg=args.max_static_leg,
        max_batch_distance=args.max_batch_distance,
        compress_gap=args.compress_gap,
        no_cache_collision=getattr(args, "no_cache_collision", False),
        collision_padding_tiles=getattr(args, "collision_padding_tiles", 64),
        collision_max_expansions=getattr(args, "collision_max_expansions", 250000),
        waypoint_arrival_radius=getattr(args, "waypoint_arrival_radius", 1),
        no_shortcut_optimize=getattr(args, "no_shortcut_optimize", False),
        shortcut_max_span=getattr(args, "shortcut_max_span", 128),
        shortcut_min_savings=getattr(args, "shortcut_min_savings", 4),
        shortcut_corridor_radius=getattr(args, "shortcut_corridor_radius", 18),
        route_step_gap=getattr(args, "route_step_gap", 10),
        no_cache_direct=getattr(args, "no_cache_direct", False),
        direct_candidate_min_detour=getattr(args, "direct_candidate_min_detour", 1.22),
        direct_candidate_min_savings=getattr(args, "direct_candidate_min_savings", 24),
        direct_hazard_buffer=getattr(args, "direct_hazard_buffer", 10),
        direct_max_expansions=getattr(args, "direct_max_expansions", 350000),
        direct_combat_margin=getattr(args, "direct_combat_margin", 5),
        runnable_hazard_cost_factor=getattr(args, "runnable_hazard_cost_factor", 0.15),
        terminal_hazard_cost_factor=getattr(args, "terminal_hazard_cost_factor", 0.25),
        max_warnings=args.max_warnings,
        max_suspects=args.max_suspects,
        json=True,
    )


def _candidate_modes(args: SimpleNamespace) -> List[Tuple[str, SimpleNamespace]]:
    modes = [
        ("safe", _base_args(args)),
        ("safe_partial", _base_args(args, include_partial=True)),
        ("broad_hints", _base_args(args, include_partial=True, include_derived=True, include_unverified=True)),
        ("partial_derived", _base_args(args, include_partial=True, include_derived=True)),
        ("partial_unverified", _base_args(args, include_partial=True, include_unverified=True)),
    ]
    if args.allow_failed_candidate:
        modes.append(("failed_trace_tolerant", _base_args(args, include_partial=True, allow_failed=True)))
    return modes[:max(1, args.max_candidates)]


def _waypoint_signature(candidate: Dict[str, Any]) -> str:
    waypoints = candidate.get("waypoints") or []
    if not waypoints:
        frontier = candidate.get("frontierTile")
        return "frontier:" + tile_key(frontier)
    return "|".join(tile_key(tile) for tile in waypoints)


def _quality_penalty(quality: str) -> float:
    return {
        "ok": 0.0,
        "watch": 60.0,
        "suspicious": 420.0,
        "bad": 1600.0,
    }.get(quality or "", 250.0)


def _building_like_penalty(candidate: Dict[str, Any]) -> float:
    routes = " ".join(sorted((candidate.get("routesUsed") or {}).keys())).lower()
    objects = candidate.get("objectSteps") or []
    penalty = 0.0
    if any(word in routes for word in ("bank", "store", "shop", "kitchen", "castle", "basement")):
        penalty += 120.0
    if objects:
        penalty += 80.0 + (25.0 * len(objects))
    return penalty


def _model_score(model: Dict[str, Any] | None, candidate: Dict[str, Any]) -> Dict[str, Any]:
    waypoints = candidate.get("waypoints") or []
    if not model or len(waypoints) < 2:
        return {
            "predictedTicks": float(candidate.get("estimatedTicks") or candidate.get("cost") or 9999.0),
            "riskScore": 0.0,
            "confidence": 0.0,
            "sourceMix": {"fallback": max(0, len(waypoints) - 1)},
        }
    ticks = 0.0
    risks = []
    confidences = []
    source_mix: Dict[str, int] = {}
    for left, right in zip(waypoints, waypoints[1:]):
        prediction = segment_prediction(model, left, right)
        ticks += prediction["predictedTicks"]
        risks.append(prediction["riskScore"])
        confidences.append(prediction["confidence"])
        source_mix[prediction["source"]] = source_mix.get(prediction["source"], 0) + 1
    risk = max(risks) if risks else 0.0
    confidence = sum(confidences) / max(1, len(confidences))
    return {
        "predictedTicks": round(ticks, 2),
        "riskScore": round(risk, 6),
        "confidence": round(confidence, 6),
        "sourceMix": source_mix,
    }


def _score_candidate(model: Dict[str, Any] | None, candidate: Dict[str, Any]) -> Dict[str, Any]:
    model_part = _model_score(model, candidate)
    weights = (model or {}).get("weights", {})
    tick_weight = float(weights.get("tick", 1.0))
    risk_penalty = float(weights.get("riskPenalty", 950.0))
    confidence_penalty = float(weights.get("lowConfidencePenalty", 140.0))
    detour_penalty = float(weights.get("detourPenalty", 220.0))
    building_penalty = float(weights.get("insideBuildingPenalty", 180.0))
    direct = float(candidate.get("directDistance") or 0.0)
    route_distance = float(candidate.get("routeDistance") or direct or 0.0)
    detour_ratio = float(candidate.get("detourRatio") or (route_distance / max(1.0, direct)))
    score = model_part["predictedTicks"] * tick_weight
    score += model_part["riskScore"] * risk_penalty
    score += (1.0 - min(1.0, model_part["confidence"])) * confidence_penalty
    score += max(0.0, detour_ratio - 1.0) * detour_penalty
    score += _quality_penalty(candidate.get("quality"))
    score += _building_like_penalty(candidate) * (building_penalty / 180.0)
    if candidate.get("status") != "ok":
        score += 4500.0
    if candidate.get("targetDistanceIncreases", 0) > 0:
        score += float(candidate.get("targetDistanceIncreases")) * 25.0
    if candidate.get("hazardWarnings"):
        score += len(candidate["hazardWarnings"]) * 450.0
    model_part["score"] = round(score, 3)
    return model_part


def _route_runner_command(args: SimpleNamespace, candidate: Dict[str, Any]) -> List[str]:
    command = [
        "python3",
        "agent-navigation/tools/route_runner.py",
        "--to",
        args.to,
        "--run-reserve",
        "auto",
        "--max-batches",
        str(args.runner_max_batches),
        "--max-batch-distance",
        str(args.max_batch_distance),
    ]
    if candidate.get("includes", {}).get("partialRoutes"):
        command.append("--include-partial")
    if candidate.get("includes", {}).get("derivedRoutes"):
        command.append("--include-derived")
    if candidate.get("includes", {}).get("unverifiedRoutes"):
        command.append("--include-unverified")
    if args.trace_profile:
        command.extend(["--trace-profile", args.trace_profile])
    evidence_jsonl = getattr(args, "route_evidence_jsonl", DEFAULT_ROUTE_EVIDENCE_JSONL)
    if evidence_jsonl and not bool(getattr(args, "no_route_evidence", False)):
        command.extend(["--evidence-jsonl", evidence_jsonl])
    wants_shortcut_probe = (
        candidate.get("mode") == "cache_direct"
        or candidate.get("status") != "ok"
        or candidate.get("quality") in ("suspicious", "bad")
        or float(candidate.get("detourRatio") or 0.0) >= 1.35
        or int(candidate.get("targetDistanceIncreases") or 0) >= 3
    )
    if wants_shortcut_probe:
        command.extend(["--allow-frontier", "--direct-if-preview", "--probe-toward-target"])
    return command


def _route_executor_command(args: SimpleNamespace, evidence_jsonl: str) -> List[str]:
    command = [
        "python3",
        "agent-navigation/tools/execute_route_definition.py",
        "--to",
        args.to,
        "--run-mode",
        "auto",
        "--eat-at",
        "10",
    ]
    if args.trace_profile:
        command.extend(["--profile", args.trace_profile])
    if evidence_jsonl and not bool(getattr(args, "no_route_evidence", False)):
        command.extend(["--evidence-jsonl", evidence_jsonl])
    return command


def _route_id(args: SimpleNamespace, candidate: Dict[str, Any]) -> str:
    source = "{}->{}:{}:{}:{}".format(
        args.from_tile,
        args.to,
        candidate.get("mode") or "learned",
        candidate.get("routeDistance") or "na",
        candidate.get("routeStepCount") or len(candidate.get("routeSteps") or candidate.get("waypoints") or []),
    )
    safe = []
    for char in source.lower():
        if char.isalnum() or char in ("-", "_"):
            safe.append(char)
        else:
            safe.append("-")
    text = "".join(safe).strip("-")
    while "--" in text:
        text = text.replace("--", "-")
    return text[:160] or "route"


def _route_evidence(candidate: Dict[str, Any]) -> Dict[str, Any]:
    sources = candidate.get("edgeSources") or {}
    routes_used = candidate.get("routesUsed") or {}
    trace_edges = int(sources.get("model_trace") or 0)
    route_hint_edges = int(sources.get("route_hint") or 0)
    cache_direct_edges = int(sources.get("cache_direct") or 0)
    status_ok = candidate.get("status") == "ok"
    if status_ok and trace_edges:
        level = "trace_proven"
        proven = True
        summary = "Selected route is built from successful movement-trace edges; routeSteps are a compact execution form of trace-backed movement."
    elif status_ok and route_hint_edges and routes_used:
        level = "verified_route_hint"
        proven = True
        summary = "Selected route is backed by curated route hints from the navigation database."
    elif status_ok and route_hint_edges:
        level = "route_hint_backed"
        proven = False
        summary = "Selected route is backed by navigation route hints, but no specific verified route id was attached."
    elif cache_direct_edges:
        level = "cache_planned"
        proven = False
        summary = "Selected route is planned from cache collision data rather than a successful movement trace."
    else:
        level = "unproven"
        proven = False
        summary = "Selected route has no successful movement-trace or verified-route evidence attached."
    return {
        "level": level,
        "proven": proven,
        "edgeSources": sources,
        "routesUsed": routes_used,
        "summary": summary,
    }


def route_definition(args: SimpleNamespace, candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Stable compact contract for agents that just need a route to execute."""
    route_id = candidate.get("routeId") or _route_id(args, candidate)
    legacy_command = candidate.get("routeRunnerCommand") or _route_runner_command(args, candidate)
    evidence_jsonl = ""
    if "--evidence-jsonl" in legacy_command:
        index = legacy_command.index("--evidence-jsonl")
        if index + 1 < len(legacy_command):
            evidence_jsonl = legacy_command[index + 1]
    if not evidence_jsonl:
        evidence_jsonl = DEFAULT_ROUTE_EXECUTOR_EVIDENCE_JSONL
    command = _route_executor_command(args, evidence_jsonl)
    route_steps = candidate.get("routeSteps") or candidate.get("waypoints") or []
    run_plan = candidate.get("runPlan") or {
        "policy": "default",
        "routeDistance": candidate.get("routeDistance"),
        "runTileDistance": 0,
        "walkTileDistance": candidate.get("routeDistance"),
        "segmentCount": 0,
    }
    hazard_warnings = candidate.get("hazardWarnings") or []
    quality = candidate.get("quality")
    evidence = _route_evidence(candidate)
    review_reasons = []
    if quality in ("suspicious", "bad") and not evidence.get("proven"):
        review_reasons.append("route quality is {}".format(quality))
    if hazard_warnings:
        review_reasons.append("hazard warnings present")
    return {
        "schemaVersion": 1,
        "api": "2006scape.route-definition",
        "routeId": route_id,
        "planner": candidate.get("planner") or getattr(args, "planner", "fast"),
        "mode": candidate.get("mode") or "learned",
        "status": candidate.get("status"),
        "quality": quality,
        "actionable": _is_actionable(candidate),
        "from": args.from_tile,
        "to": args.to,
        "targetTile": candidate.get("targetTile"),
        "arrivalRadius": candidate.get("arrivalRadius"),
        "distanceTiles": candidate.get("routeDistance"),
        "estimatedTicks": candidate.get("estimatedTicks"),
        "next": candidate.get("next"),
        "routeSteps": route_steps,
        "routeStepCount": len(route_steps),
        "evidence": evidence,
        "runPlan": run_plan,
        "runSegments": candidate.get("runSegments") or [],
        "safety": {
            "allowLethal": bool(getattr(args, "allow_lethal", False)),
            "requiresReview": bool(review_reasons),
            "reviewReasons": review_reasons,
            "hazardWarnings": hazard_warnings[:8],
            "wrongWayFlags": (candidate.get("wrongWayFlags") or [])[:5],
            "detourSegments": (candidate.get("detourSegments") or [])[:5],
        },
        "execution": {
            "strategy": "ml_route_steps",
            "command": command,
            "legacyRouteRunnerCommand": legacy_command,
            "maxBatchDistance": getattr(args, "max_batch_distance", None),
            "runnerMaxBatches": getattr(args, "runner_max_batches", None),
            "notes": "Run this only when live movement is intended; it follows routeSteps through bridge primitives and appends route-batch evidence automatically.",
        },
        "feedback": {
            "automaticEvidenceJsonl": evidence_jsonl,
            "automaticEvents": ["route_batch"],
            "manualOutcomeCommand": [
                "python3",
                "agent-navigation/ml-routing/route_ml.py",
                "record-outcome",
                "--route-id",
                route_id,
                "--from",
                args.from_tile,
                "--to",
                args.to,
                "--status",
                "success|blocked|combat|death|stalled|bad_route",
                "--final",
                "X,Y,H",
            ],
            "manualFields": [
                "failure-kind",
                "problem-kind",
                "enemy-name",
                "enemy-level",
                "enemy-tile",
                "enemy-aggressive",
                "hazard-id",
                "notes",
            ],
        },
    }


def attach_route_api(args: SimpleNamespace, candidate: Dict[str, Any]) -> None:
    candidate["routeId"] = _route_id(args, candidate)
    candidate["routeRunnerCommand"] = _route_runner_command(args, candidate)
    candidate["routeDefinition"] = route_definition(args, candidate)
    candidate["routeExecutionCommand"] = candidate["routeDefinition"]["execution"]["command"]


def _should_recommend_shortcut_probe(candidate: Dict[str, Any]) -> bool:
    if candidate.get("quality") not in ("suspicious", "bad"):
        return False
    route_definition_data = candidate.get("routeDefinition") or {}
    evidence = route_definition_data.get("evidence") if isinstance(route_definition_data, dict) else {}
    return not bool((evidence or {}).get("proven"))


def rank_routes(args: SimpleNamespace) -> Dict[str, Any]:
    navdb, router, route_eval = _load_nav_modules()
    model = load_model(args.model)
    if getattr(args, "planner", "fast") == "fast":
        try:
            from .fast_planner import fast_route

            best = fast_route(args, model)
            score = _score_candidate(model, best)
            best["mlScore"] = score
            best["score"] = score["score"]
            attach_route_api(args, best)
            if _should_recommend_shortcut_probe(best):
                best["improvement"] = {
                    "shortcutProbeRecommended": True,
                    "reason": "route quality is {}; direct preview/probe flags are included to learn a shorter path instead of replaying a stale detour".format(best.get("quality")),
                }
        except Exception as exc:
            best = {
                "planner": "fast",
                "status": "error",
                "error": str(exc),
                "score": 999999.0,
            }
        return {
            "schemaVersion": 1,
            "tool": "2006scape-ml-routing",
            "model": {
                "loaded": model is not None,
                "modelId": (model or {}).get("modelId"),
                "trainedAt": (model or {}).get("trainedAt"),
            },
            "request": {
                "from": args.from_tile,
                "to": args.to,
                "combatLevel": args.combat_level,
                "food": args.food,
                "coins": args.coins,
                "runEnergy": args.run_energy,
                "runEnabled": args.run_enabled,
                "traceProfile": args.trace_profile,
                "planner": "fast",
            },
            "recommended": _compact_candidate(best),
            "candidates": [],
            "agentUsage": {
                "summary": "Use recommended.routeDefinition.execution.command to run the selected ML1 route steps, or recommended.next for the next low-token waypoint.",
                "safety": "Fast planner uses the trained model graph plus deterministic hazard checks; use --planner full for the slower router/route_eval wrapper.",
            },
        }

    restore_caches = _install_route_call_caches(navdb, router)
    candidates = []
    seen = set()
    mode_args_by_name = {}
    try:
        mode_items = _candidate_modes(args)
        for mode_name, mode_args in mode_items:
            mode_args_by_name[mode_name] = mode_args
            try:
                evaluation = route_eval.evaluate(mode_args)
            except Exception as exc:
                candidates.append({
                    "mode": mode_name,
                    "status": "error",
                    "error": str(exc),
                    "score": 999999.0,
                })
                continue
            candidate = dict(evaluation)
            candidate.update({
                "mode": mode_name,
                "includes": {
                    "partialRoutes": mode_args.include_partial,
                    "derivedRoutes": mode_args.include_derived,
                    "unverifiedRoutes": mode_args.include_unverified,
                },
                "hazardWarnings": [],
                "objectSteps": [],
            })
            signature = _waypoint_signature(candidate)
            if signature in seen:
                continue
            seen.add(signature)
            score = _score_candidate(model, candidate)
            candidate["mlScore"] = score
            candidate["score"] = score["score"]
            attach_route_api(args, candidate)
            if _should_recommend_shortcut_probe(candidate):
                candidate["improvement"] = {
                    "shortcutProbeRecommended": True,
                    "reason": "route quality is {}; direct preview/probe flags are included to learn a shorter path instead of replaying a stale detour".format(candidate.get("quality")),
                }
            candidates.append(candidate)
        candidates.sort(key=lambda item: item.get("score", 999999.0))
        best = candidates[0] if candidates else {"status": "error", "error": "no candidates"}
        if best.get("mode") in mode_args_by_name:
            try:
                plan = router.build_plan(mode_args_by_name[best["mode"]])
                for key in ("hazardWarnings", "objectSteps", "endTile", "cost", "next", "routesUsed", "edgeSources"):
                    if key in plan:
                        best[key] = plan[key]
                attach_route_api(args, best)
                if _should_recommend_shortcut_probe(best):
                    best["improvement"] = {
                        "shortcutProbeRecommended": True,
                        "reason": "route quality is {}; direct preview/probe flags are included to learn a shorter path instead of replaying a stale detour".format(best.get("quality")),
                    }
            except Exception as exc:
                best["planEnrichmentError"] = str(exc)
    finally:
        restore_caches()
    compact_candidates = [_compact_candidate(candidate) for candidate in candidates[:max(0, args.output_candidates)]]
    return {
        "schemaVersion": 1,
        "tool": "2006scape-ml-routing",
        "model": {
            "loaded": model is not None,
            "modelId": (model or {}).get("modelId"),
            "trainedAt": (model or {}).get("trainedAt"),
        },
        "request": {
            "from": args.from_tile,
            "to": args.to,
            "combatLevel": args.combat_level,
            "food": args.food,
            "coins": args.coins,
            "runEnergy": args.run_energy,
            "runEnabled": args.run_enabled,
            "traceProfile": args.trace_profile,
        },
        "recommended": _compact_candidate(best),
        "candidates": compact_candidates,
        "agentUsage": {
            "summary": "Use recommended.routeDefinition.execution.command to run the selected ML1 route steps, or recommended.next for the next low-token waypoint.",
            "safety": "Model scores rank deterministic candidates; normal router hazard gates still apply.",
        },
    }


def _compact_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    waypoints = candidate.get("waypoints") or []
    keep = [
        "mode", "status", "quality", "score", "mlScore", "from", "to", "targetTile",
        "next", "endTile", "frontierTile", "frontierDistanceToTarget", "estimatedTicks",
        "directDistance", "routeDistance", "macroRouteDistance", "collisionPathDistance",
        "collisionExpanded", "collision", "collisionWarnings", "collisionFailures",
        "detourRatio", "targetDistanceIncreases",
        "edgeSources", "routesUsed", "hazardWarnings", "objectSteps", "wrongWayFlags",
        "detourSegments", "frontierScore", "routeExecutionCommand", "routeRunnerCommand", "includes", "error",
        "planEnrichmentError", "improvement", "directCandidate", "selectedOverLearned",
        "learnedCandidate", "runPlan", "runSegments", "routeId", "routeDefinition",
    ]
    compact = {key: candidate[key] for key in keep if key in candidate and candidate[key] not in (None, [], {})}
    compact["actionable"] = _is_actionable(candidate)
    if "hazardWarnings" in compact:
        compact["hazardWarnings"] = _dedupe_warnings(compact["hazardWarnings"])[:4]
    if "detourSegments" in compact:
        compact["detourSegments"] = compact["detourSegments"][:3]
    if "wrongWayFlags" in compact:
        compact["wrongWayFlags"] = compact["wrongWayFlags"][:3]
    if waypoints:
        compact["waypointCount"] = len(waypoints)
        compact["waypointsPreview"] = waypoints[:4]
        if len(waypoints) > 4:
            compact["waypointsPreview"].append(waypoints[-1])
    route_steps = candidate.get("routeSteps") or []
    if route_steps:
        compact["routeStepCount"] = len(route_steps)
        if len(route_steps) <= 160:
            compact["routeSteps"] = route_steps
        compact["routeStepsPreview"] = route_steps[:5]
        if len(route_steps) > 5:
            compact["routeStepsPreview"].append(route_steps[-1])
    if "runSegments" in compact:
        compact["runSegments"] = compact["runSegments"][:8]
    return compact


def _is_actionable(candidate: Dict[str, Any]) -> bool:
    if candidate.get("status") == "ok":
        return True
    if candidate.get("status") == "no-learned-route" and candidate.get("next"):
        return True
    return False


def _dedupe_warnings(warnings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for warning in warnings:
        key = (
            warning.get("id"),
            warning.get("risk"),
            tuple(warning.get("warnings") or []),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(warning)
    return result
