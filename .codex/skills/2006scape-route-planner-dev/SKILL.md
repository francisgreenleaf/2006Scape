---
name: 2006scape-route-planner-dev
description: "Use when designing, editing, debugging, or validating the 2006Scape route-planning system in /Users/kevin/Documents/2006Scape, including ML1 route_ml_XS.py define, legacy agent-navigation/tools/router.py and route_runner.py graph semantics, navdb.py, passive movement traces, server clipped-path previews, hazard/failure weighting, reverse-edge inference, coordinate targets, future ML/GNN routing datasets, evaluation metrics, and low-token A-to-B planning."
---

# 2006Scape Route Planner Dev

Use this skill for route-planning system work. Use `2006scape-route-agent` or `2006scape-frontier-exploration` for live gameplay exploration, and use `2006scape-agent-bridge-dev` if bridge tool source or metadata must change.

## Core Direction

The long-term goal is a self-improving routing system: passive telemetry first, deterministic graph planning now, learned edge/risk models next, and eventually graph neural network ranking on top of the evidence database. Read `references/advanced-route-planner.md` when changing data shape, training/evaluation plans, or long-term model direction.

Do not replace evidence-backed planning with an opaque model. Learned models should score costs, risks, confidence, and frontiers; deterministic search should still enforce safety constraints and explainable route choices.

## Preferred Agent Interface

ML1 means the fast route-definition API. For agents and models that need a normal A-to-B route, use `route_ml_XS.py define` by default and fall back to full `route_ml.py define` only when XS omits a field needed for debugging or evidence. It returns the stable `2006scape.route-definition` contract in compact form: route steps, run/runSegments, evidence/proof fields, safety review fields, persisted artifact path, and feedback instructions.

The old route method is deprecated for agent routing: do not call bare `route_runner.py --to ...`, `router.py plan`, `route_eval.py`, or `navdb.py next-step` as the normal way to travel. Use those only for planner development, validation, or fallback debugging. The route definition's `execution.command` now invokes `execute_route_definition.py --route-definition ...`, which follows `routeSteps` through bridge movement primitives, defaults to `--eat-at 10`, captures nearby NPC context on combat/HP loss, and writes route evidence. Use this command for live ML1 execution unless you intentionally need a custom route-step script.

Use `route_ml_XS.py route --json` for compact planner internals and full `route_ml.py route --json` when debugging needs complete candidate data. Avoid `route_ml.py go` for agent autonomy while it still delegates to the legacy Route Runner executor.

## Main Files

- `agent-navigation/tools/router.py`: legacy deterministic graph planner over places, routes, hazards, passive traces, and route traces. Use for development and fallback diagnostics, not normal agent travel.
- `agent-navigation/tools/route_eval.py`: deterministic route-quality scorer for cost/tick estimates, detour ratios, wrong-way flags, and shortcut/map-inspection triggers before live movement.
- `agent-navigation/tools/route_runner_XS.py`: compact legacy orientation wrapper for debugging why the old planner disagrees with ML1.
- `agent-navigation/tools/route_runner.py`: deprecated standalone live route method and compatibility executor for `--route-definition` artifacts. Do not use bare `route_runner.py --to ...` for normal agent routing.
- `agent-navigation/tools/execute_route_definition.py`: preferred compact ML1 live executor over persisted route definitions. It follows `routeSteps` directly, can force/preserve/disable run with `--run-mode`, eats before the next step at `--eat-at` HP, and writes route-batch/outcome evidence under `.local/run-evidence/`.
- `agent-navigation/tools/marathon_runner.py`: legacy timed repeated-route benchmark runner that preflights each leg with `route_eval.py`, renders suspicious/bad detour context maps, delegates movement to `route_runner.py`, passes through run-reserve policy, and writes JSONL route-performance events. Treat it as a benchmark/compatibility tool until it migrates to ML1 execution.
- `agent-navigation/tools/map_grid.py`: level-0 32-tile map grid API for tile-to-cell shorthand, cell bounds, and bounded-cell context-map requests.
- `agent-navigation/tools/render_agent_context_map_XS.py`: default compact agent-facing cache map wrapper for current tile, recent movement, latest segment paths, cache mapfunction icons, and place labels without loading full-world images.
- `agent-navigation/tools/render_agent_context_map.py`: full cache map wrapper for debugging or user-facing map detail. Default outputs are unique ignored artifacts under `agent-navigation/.local/context-maps/<date>/`.
- `agent-navigation/tools/render_context_map.py`: lower-level bounded cache-backed context renderer used by the agent wrapper.
- `agent-navigation/ml-routing/route_ml_XS.py`: default compact wrapper for agent-facing `define`, `route`, benchmark, and comparison-map results.
- `agent-navigation/ml-routing/route_ml.py`: full one-command ML routing pipeline for export, train, route/go, benchmark, and before/after comparison maps.
- `agent-navigation/ml-routing/API.md`: stable route-definition contract for agents: `define`, compact route steps, run segments, execution command, and feedback capture.
- `agent-navigation/ml-routing/ml_routing/comparison_maps.py`: benchmark old-vs-new route image renderer. It should reuse the shared cache/context-map base layers rather than hand-rolling custom backgrounds.
- `agent-navigation/tools/navdb.py`: route/place/hazard schemas, validation, trace loading, and graph helpers.
- `agent-navigation/data/places.json`, `routes.json`, `hazards.json`: curated navigation memory.
- `2006Scape Server/data/logs/player-movement-traces/`: passive server telemetry, default training/evidence source.
- `2006Scape Server/data/logs/agent-movement-traces/`: bridge batch diagnostics; opt-in/fallback for routing because passive traces already capture the same movement.

## Planner Rules

- Treat `PathFinder`/`preview_local_path` as a local clipped-path oracle, not the global router.
- Prefer passive traces over AI-polled state for movement evidence. By default `navdb.iter_movement_traces()` consumes passive player traces when present, drops stationary idle `state` heartbeats from route/map inputs, and excludes duplicate agent batch / legacy fallback polling traces unless the relevant opt-in env var or explicit `--trace-file` is used.
- Passive traces include `object_interaction` records from object packets. Preserve those fields through graph tooling and surface them to agents; do not collapse object-backed transitions into anonymous walk edges.
- Infer reverse edges only for normal same-plane movement with short distance, no combat, no HP loss, no death, and no object/teleport transition.
- Keep death, combat, HP loss, stalls, oscillation, teleport, and map-region jumps as explicit negative/transition evidence.
- Coordinate targets such as `--to 3047,3246,0` are valid for frontier work; do not create throwaway places just to test a tile.
- Long routes should be requested through ML1 (`route_ml_XS.py define`) first. For live movement, run the returned `cmd`/`execution.command` or call `execute_route_definition.py --route-definition PATH`, keeping batch windows small enough to preserve feedback. If a compatibility executor is deliberately used, pass the persisted route definition instead of letting Route Runner re-plan.
- Tile/batch limits are execution guardrails, not permanent navigation limits. Raise them on open, well-proven road segments and clamp them near hazards, object transitions, stalls, or low-confidence traces.
- Use ML1 before uncertain long legs. With XS, inspect `status`, `quality`, `evidence`, `safety`, `steps`, `run`, and `runSegments`; in full output these correspond to `routeSteps`, `runPlan`, and `runSegments`. `quality` is a geometry/detour signal; `evidence.proven=true` means the path is backed by successful trace evidence or a verified route hint, so trust `safety.review`/`safety.requiresReview` rather than rejecting it solely because the geometry score is `bad`. Use old `route_runner_XS.py --orient --json` only when debugging why the legacy planner disagrees with ML1.
- Prefer orient JSON over manual tool chains. If it reports `quality` as `suspicious`/`bad`, nonzero wrong-way flags, large detour ratio, or a context-map path, inspect the JSON summary first and open the PNG only if the static layout needs visual review.
- For coordinate targets with no learned route, frontier selection now scores directional progress from the current tile to the target. Inspect `frontierScore` in orient/route-eval JSON: negative `firstStepDistanceProgress` or nonzero `firstStepWrongWayDistance` means the graph frontier is probably pointing away from the objective, so prefer a target-directed probe or local preview instead of following that frontier blindly.
- Use `--run-reserve auto` on long or hazard-adjacent route execution. It scans planned waypoints for hazards with `minRunEnergy`/`requiresRun`, conserves that reserve on normal batches using the previewed path length as the estimated spend, and spends it only inside/near the hazard band. Batch output includes `runReq`, `runBefore`, `runAfter`, `runSpent`, `expectedRunSpend`, `tps`, `tilesPerTick`, and `runWarn`; treat non-`none` `runWarn` values as evidence that run did not actually save ticks. Pass `--evidence-jsonl PATH` when you need structured route-batch run-efficiency records for ML/router analysis; `mining_runner.py` writes a sibling `.routes.jsonl` automatically for its route legs.
- For route execution recovery, use `python3 agent-navigation/tools/route_failure_XS.py` first. It summarizes latest route evidence, final tile, last batch, combat/death/HP-loss failures, enemy context, and the evidence path without loading the full JSONL.
- If a planned route makes a wide detour, render a bounded context or segment map with `render_agent_context_map_XS.py` and actively look for a locally previewable shortcut/frontier instead of blindly replaying the long historical path.
- Agent context maps now expose the same level-0 grid as the profile map. Use `map_grid.py locate --tile X,Y,H` to get shorthand like `AU21`; use `render_agent_context_map_XS.py --grid-cell AU21` to inspect that cell. JSON summaries include `currentGridCell`, `centerGridCell`, and `referenceGridCells` so agents can refer to cells without loading images.
- Treat context-map PNGs/JSON as disposable agent artifacts. Read the JSON summary and marker fields first; open the PNG only when visual layout is actually needed. Let the renderer auto-name outputs by default; pass `--output`/`--summary` only for deliberate smoke tests or user-facing comparison files.
- For ML benchmark visuals, use `route_ml_XS.py compare-maps` instead of building one-off map renderers. The comparison maps use the same cache/context base as tactical context maps: terrain, water, mapscene buildings, large-object footprints, mapfunction icons, and place labels. Read compact XS output first; use full `route_ml.py compare-maps` only when marker labels/coordinates, complete `routeSteps`, or full `runPlan` details are needed.
- The fast ML planner can replace a stale learned detour with a `cache_direct` candidate when the learned graph is incomplete or overly indirect. This candidate uses cache collision for walls/water/objects, a hazard-cost field for danger zones, and emits compact `routeSteps` plus `runPlan`/`runSegments` for agent execution/review. Treat `selectedOverLearned` as the reason, and remember that frontier-only learned routes are not complete benchmark wins.
- Fast ML route hints come from the current navigation DB at request time. Retraining is still needed to update learned timing/risk priors, but route/place anchor fixes in `places.json` or `routes.json` should affect `define`/`route` immediately.
- For agent-facing API calls, prefer ML1 `route_ml_XS.py define` over `route`, `router.py`, `route_eval.py`, `route_runner.py`, or `navdb.py next-step` unless debugging. `define` emits stable compact route-definition JSON: route id, compact steps, run policy, safety review fields, persisted route-definition path, preferred route-step executor command, and feedback instructions.
- Keep route execution evidence on by default. Generated ML route runner commands append to `agent-navigation/.local/run-evidence/ml-route-runner.routes.jsonl`; use `record-outcome` for route-level failures such as enemy contact, death, stalls, blockers, bad detours, or wrong destination so the next `export` can include them and training can fold them into risk stats.
- For hazard-adjacent routes, inspect `runPlan` before execution. Current policy conserves run outside hazard segments, marks runnable danger stretches, and lowers cache-direct hazard costs only when combat/food/run energy make the stretch plausible. Do not assume every hazard-adjacent shortcut is safe just because it is shorter.
- For Catherby / White Wolf Mountain routes, `taverley_white_wolf_gate_west` is not a hard lethal blocker for current MrFlame-class stats with food. A 2026-05-25 ML1 route-step crossing walked from west of the Taverley gate to Catherby, took one 5 HP hit near `2850,3495`, and arrived with HP `15/20` and all three kebabs. The west-gate-to-Catherby segment is now a verified/proven route hint (`taverley_white_wolf_gate_west_to_catherby_proven`); prefer running when available, but do not reject this route solely because run is disabled or `quality` is geometrically `bad` for current MrFlame-class stats. Record combat/HP-loss evidence so future run-zone modeling is data-driven.
- For Catherby utility routing, the main local targets are `catherby_bank`, `catherby_range`, `catherby_fishing_shore`, and `catherby_fishing_shop`. `catherby_range` uses `2819,3443` as the pathable routing anchor while staying within cooking range; older cooking proof at `2817,3443` is useful for range interaction but is clipped for east/west route expansion. The fishing-shop waypoint is an interaction tile near Harry, not the NPC's exact spawn tile; source data places Harry NPC `576` at `2835,3441`, shop id `32`, and cache mapfunction `25` at `2833,3443`. Live Catherby food-run proof opened Harry's Fishing Shop from the shop-side route tiles `2832,3438` and `2831,3438`; route to `catherby_fishing_shop`, then use `open_nearest_shop` with name `harry` or `fishing`. If a player is stuck deeper inside the range house, handle south range-house Door `1530` with the existing Catherby door helper rather than treating it as an ordinary walk edge.
- Do not use screenshots to replace planner evidence or cache maps. Use `2006scape-screenshot-capture` only for live visual facts the static map cannot know, such as current gate/door state, player side, object click failure, or a mismatch between API state and visible client geometry.
- Do not use `Mr. Flame`, `Heat Map`, `Mr. Flame Fog`, or any full topology render as part of routine agent routing. Those are human-facing analysis maps unless the user explicitly requests them.

## Starter Commands

```sh
python3 agent-navigation/ml-routing/route_ml_XS.py define --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/execute_route_definition.py --route-definition agent-navigation/.local/ml-route-definitions/ROUTE.json --run-mode auto --eat-at 10
python3 agent-navigation/ml-routing/route_ml_XS.py route --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled --json
# Deprecated normal-travel path; use only for legacy planner debugging.
python3 agent-navigation/tools/router.py plan --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled --json
python3 agent-navigation/tools/route_eval.py --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/route_runner_XS.py --to PLACE --orient --json --run-reserve auto
python3 agent-navigation/tools/route_runner.py --to PLACE --max-walk-distance 48 --max-batches 6 --dry-run
python3 agent-navigation/tools/route_runner.py --to PLACE --max-walk-distance 48 --max-batches 6 --run-reserve auto
python3 agent-navigation/tools/route_runner.py --to X,Y,H --allow-frontier --direct-if-preview --probe-toward-target --dry-run
python3 agent-navigation/tools/marathon_runner.py --laps 10 --run-reserve auto
python3 agent-navigation/tools/map_grid.py locate --tile X,Y,H
python3 agent-navigation/tools/render_agent_context_map_XS.py --center X,Y,H --radius-tiles 72 --pixels-per-tile 5 --recent-seconds 60
python3 agent-navigation/tools/render_agent_context_map_XS.py --grid-cell AU21 --grid-padding-tiles 4
python3 agent-navigation/tools/render_agent_context_map_XS.py --segment-from FROM_PLACE --segment-to TO_PLACE
python3 agent-navigation/ml-routing/route_ml_XS.py compare-maps --case CASE_NAME --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/ml-routing/route_ml_XS.py record-outcome --route-id ROUTE_ID --from X,Y,H --to PLACE --status blocked --final X,Y,H --problem-kind enemy_contact --enemy-name NAME --enemy-level N --enemy-tile X,Y,H
python3 agent-navigation/ml-routing/route_ml_XS.py route --from PLACE --to PLACE --no-cache-direct --json
agent-navigation/tools/rs-tool_XS.sh preview_local_path '{"x":X,"y":Y,"height":0,"moveNear":true,"applyBounds":true,"maxWalkDistance":48}'
python3 agent-navigation/tools/navdb_XS.py graph-summary
python3 agent-navigation/tools/navdb_XS.py validate
python3 agent-navigation/tools/navdb_XS.py self-test
python3 agent-navigation/tools/navdb_XS.py trace-tests
```

## Validation

After planner edits, run:

```sh
python3 -m py_compile agent-navigation/tools/router.py agent-navigation/tools/route_eval.py agent-navigation/tools/route_runner.py agent-navigation/tools/route_runner_XS.py agent-navigation/tools/marathon_runner.py agent-navigation/tools/navdb.py agent-navigation/tools/navdb_XS.py agent-navigation/tools/map_grid.py agent-navigation/tools/render_context_map.py agent-navigation/tools/render_agent_context_map.py agent-navigation/tools/render_agent_context_map_XS.py
python3 -m py_compile agent-navigation/ml-routing/route_ml.py agent-navigation/ml-routing/route_ml_XS.py agent-navigation/ml-routing/ml_routing/*.py agent-navigation/ml-routing/tests/test_ml_routing.py
python3 agent-navigation/ml-routing/tests/test_ml_routing.py
python3 agent-navigation/tools/navdb_XS.py validate
python3 agent-navigation/tools/navdb_XS.py self-test
python3 agent-navigation/tools/router.py plan --from 3222,3218,0 --to lumbridge_castle_courtyard
```

If route execution changed, dry-run or inspect ML1 first, then prove one short route by following the returned `routeSteps` through normal bridge movement primitives. Use Route Runner only for compatibility-executor regression checks. Do not restart runtime unless live bridge behavior requires it.

## Tool Usage Logs

XS and full agent-facing CLIs append local audit events to `agent-navigation/.local/usage/<yyyy-MM-dd>.jsonl`. XS wrappers mark delegated full-tool calls with `delegatedBy:"xs"` so direct full fallback usage can be counted separately. This log is intentionally out-of-context by default; read it only when auditing whether XS outputs are missing fields or whether agents still depend on full tools. Set `AGENT_NAV_USAGE_LOG=0` for a one-off command if needed.

## Daily Improvement Loop

Each route-planner development pass should improve at least one of: data capture, graph correctness, safety filtering, route reuse, frontier selection, low-token execution, evaluation, or ML-readiness. Prefer durable data/model pipeline improvements over one-off route fixes.
