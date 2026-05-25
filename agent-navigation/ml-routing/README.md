# 2006Scape ML Routing

This folder contains the repo-local machine-learning routing pipeline for `agent-navigation`.
It is intentionally separate from the existing live agent/runtime code: it reads route evidence,
trains local artifacts under `artifacts/`, ranks route candidates, and emits compact ML1 route
definitions that agents can execute through normal bridge movement primitives.

The immediate goal is practical routing quality:

- faster A-to-B travel;
- fewer stale detours through old saved-memory routes;
- safer avoidance of combat/death/hazard zones;
- lower token use for agents;
- continuous improvement from passive movement evidence and route outcomes.

## Main Command

Run all commands from the repo root:

```sh
python3 agent-navigation/ml-routing/route_ml.py --help
```

Agent-facing route request, also called ML1:

```sh
python3 agent-navigation/ml-routing/route_ml.py define \
  --from CURRENT_X,CURRENT_Y,0 \
  --to TARGET_PLACE_OR_TILE \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled
```

`define` is the stable agent-facing API and preferred normal routing method: it returns one route definition with compact
`routeSteps`, `runPlan`, `runSegments`, safety review fields, an execution command, and
feedback instructions. Use `route` when debugging planner internals; it wraps the same
definition under `recommended.routeDefinition`.

The old route method is deprecated for agents. Do not call bare `agent-navigation/tools/route_runner.py --to ...`
as the normal routing API. Follow the ML1 `routeSteps` with normal bridge movement primitives, or use a purpose-built ML executor when one exists. Any generated `route_runner.py --route-definition` command is a compatibility executor, not the planner interface.

The route/debug response is compact by default. Use:

- `recommended.next` for the next low-token waypoint;
- `recommended.routeRunnerCommand` only for legacy compatibility execution;
- `recommended.routeDefinition` for the stable JSON contract agents should pass around;
- `recommended.improvement.shortcutProbeRecommended` to identify stale detours where the runner should try direct preview/probe flags and learn a better path.
- `recommended.actionable` to tell whether the result is usable. This is true for full routes and for safe frontier/probe recommendations.
- `recommended.collision` to see whether the macro route was expanded through cache-derived clipped tiles.
- `recommended.mode == "cache_direct"` when the planner replaced a stale learned detour/frontier with a cache-clipped direct candidate.
- `recommended.selectedOverLearned` to see why a cache-direct candidate replaced learned graph evidence.
- `recommended.routeSteps`, `recommended.runPlan`, and `recommended.runSegments` for the compact full route and the stretches where run should be saved/spent.

Add `--output-candidates N` only when debugging alternatives; the default omits alternatives to keep agent context small.

Use `--planner fast` by default. It answers from the trained model graph and is intended for live agent calls.
Use `--planner full` only for slower diagnostics through the existing `router.py` / `route_eval.py` wrapper.
Fast planning expands selected macro edges through cache-derived clipping by default, mirroring the server's terrain/object clip masks from `RegionFactory` and `Region`. It can also try a hazard-costed cache-direct candidate when learned evidence is incomplete or clearly taking the long way. Use `--no-cache-collision` or `--no-cache-direct` only for diagnostics.
Curated route hints are read from the current navigation DB at request time. The trained model still provides edge timing/risk priors, but a stale model artifact should not resurrect old route anchors after `places.json` or `routes.json` changes.

Compatibility execution surface:

```sh
python3 agent-navigation/ml-routing/route_ml.py go \
  --from CURRENT_X,CURRENT_Y,0 \
  --to TARGET_PLACE_OR_TILE \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled \
  --dry-run
```

Prefer `define` plus direct bridge movement over `go` for agent autonomy. Remove `--dry-run` only when the caller deliberately wants the legacy compatibility executor. This command delegates to `agent-navigation/tools/route_runner.py`; it does not bypass normal game mechanics, but it is not the preferred ML1 live-control path.
Generated execution commands include `--evidence-jsonl agent-navigation/.local/run-evidence/ml-route-runner.routes.jsonl`
by default, so every route batch contributes run efficiency, HP loss, combat/death, preview, and final-tile evidence.
Use `--no-route-evidence` only for diagnostics where no local evidence should be written.

Manual outcome feedback, for example after an agent notices a bad route, enemy, stall, or blocker:

```sh
python3 agent-navigation/ml-routing/route_ml.py record-outcome \
  --route-id ROUTE_ID \
  --from START_X,START_Y,0 \
  --to TARGET_PLACE \
  --status combat \
  --final FINAL_X,FINAL_Y,0 \
  --problem-kind enemy_contact \
  --enemy-name "Highwayman" \
  --enemy-level 5 \
  --enemy-tile ENEMY_X,ENEMY_Y,0 \
  --enemy-aggressive \
  --notes "Route was technically short but crossed an aggressive NPC band."
```

## Pipeline

Export the feature lake from existing evidence:

```sh
python3 agent-navigation/ml-routing/route_ml.py export --profile mrflame
```

Train the current model with threaded aggregation:

```sh
python3 agent-navigation/ml-routing/route_ml.py train --workers 16
```

Run offline route-ranking benchmarks:

```sh
python3 agent-navigation/ml-routing/route_ml.py benchmark \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled
```

Render before/after maps for benchmark routes:

```sh
python3 agent-navigation/ml-routing/route_ml.py compare-maps \
  --case lumbridge_to_varrock \
  --case port_sarim_to_draynor \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled
```

Comparison maps use red for the older full planner, cyan for the fast ML planner, and yellow overlays for run-worthy hazard segments.
They reuse the same cache-backed context base as the agent context-map tools: terrain, water,
mapscene buildings, large object footprints, cache mapfunction icons, and place labels.
Both overlays are expanded through the cache clipping grid when possible, so the lines should follow
walkable bridges, docks, walls, and object footprints instead of drawing straight shortcuts through blocked geometry.
The aggregate `comparison-report.json` stays compact; each per-case JSON sidecar has the compact
`routeSteps`, `runPlan`/`runSegments`, and full mapfunction/place marker metadata when a route needs
execution or visual debugging without loading the PNG first.

Useful comparison-map options:

- `--no-place-labels` when labels make a dense benchmark image too busy.
- `--mapfunction-labels` only when inspecting icon identity visually; otherwise read labels from the sidecar JSON.
- `--pixels-per-tile N` and `--padding-tiles N` to trade image size against local geometry context.

Run one asynchronous improvement cycle:

```sh
python3 agent-navigation/ml-routing/route_ml.py loop \
  --profile mrflame \
  --workers 16 \
  --once
```

Run a repeated background-style loop from a scheduler or separate shell:

```sh
python3 agent-navigation/ml-routing/route_ml.py loop \
  --profile mrflame \
  --workers 16 \
  --interval-seconds 1800
```

The loop exports fresh evidence, trains a new model, and writes a benchmark report. It does not move the player.

## Artifacts

Generated files live under ignored `agent-navigation/ml-routing/artifacts/`:

- `datasets/<runId>/edge_examples.jsonl`
- `datasets/<runId>/route_hint_edges.jsonl`
- `datasets/<runId>/route_attempts.jsonl`
- `datasets/<runId>/object_transitions.jsonl`
- `models/<modelId>/model.json`
- `benchmarks/<runId>/benchmark.json`
- `comparisons/<runId>/*.png`
- `comparisons/<runId>/*.json`

Ignored local feedback from live route execution and manual outcome records lives under
`agent-navigation/.local/run-evidence/*.jsonl` and is pulled into `route_attempts.jsonl`
on the next `export`. Training folds those route attempts into empirical risk stats, so
enemy contact, stalls, death, and bad-route feedback can affect later route scoring.

Tracked source files and docs live outside `artifacts/`.

## Current MVP Behavior

The first model is an interpretable empirical edge-cost/risk model. It is not a neural graph model yet.
It aggregates observed trace edges, route batches, object transitions, run efficiency, combat/HP/death signals,
and hazard proximity. Route selection still uses deterministic safety gates, then the ML model ranks candidate paths.
The fast planner then runs a deterministic cache-collision pass over the selected macro route. It builds tile clips
from terrain flags plus loc.dat object solidity/interactivity/footprints, expands long route-hint edges into adjacent
walk tiles, tries exact waypoints first, and falls back to a small near-waypoint radius when a saved target is clipped.
That matches the server's normal `playerWalk(... moveNear=true ...)` behavior better than treating a blocked straight
line as a valid route.

When the learned graph is missing the actual target or has a large detour ratio, the fast planner may build a
`cache_direct` candidate. That path searches the cache collision grid from start to target and adds soft costs around
hazards, so it can discover routes such as Lumbridge-to-Falador without replaying a stale Varrock detour while still
skirting highwaymen, dark wizards, and other danger zones. The output includes compact `routeSteps` so agents do not
need every adjacent tile in prompt context. It also includes a `runPlan`: normal stretches conserve run, while hazard
segments are marked for running when combat, food, and run energy make the shortcut plausible.

Named benchmark places should use practical walkable anchors. For example, `barbarian_village`
uses the road/shop-area tile rather than an interior-looking shop marker so cache-direct routing
can leave the village without inheriting an old learned loop.

Legacy compatibility commands for suspicious or bad routes may add:

```sh
--allow-frontier --direct-if-preview --probe-toward-target
```

to the generated `route_runner.py` command. This applies only to the deprecated compatibility executor; agents should still request ML1 first and treat `routeSteps` as the route contract.

## Validation Commands

```sh
python3 -m py_compile agent-navigation/ml-routing/route_ml.py agent-navigation/ml-routing/ml_routing/*.py agent-navigation/ml-routing/tests/test_ml_routing.py
python3 agent-navigation/ml-routing/tests/test_ml_routing.py
python3 agent-navigation/ml-routing/route_ml.py export --profile mrflame
python3 agent-navigation/ml-routing/route_ml.py train --workers 16
python3 agent-navigation/ml-routing/route_ml.py benchmark --limit 4 --combat-level 20 --food 6 --run-energy 70 --run-enabled
```

## Implementation Log

- Created a standalone `ml-routing` folder under `agent-navigation`.
- Added dataset export for edge examples, route hints, route attempts, and object transitions.
- Added threaded empirical model training with `ThreadPoolExecutor`.
- Added compact agent-facing route ranking.
- Added `go --dry-run` / `go` execution surface around the existing route runner.
- Added offline benchmark reports and an asynchronous export/train/benchmark loop.
- Added `compare-maps` before/after route visualizations for benchmark routes.
- Updated `compare-maps` to use the shared cache/context-map base layers so benchmark images include mapfunction icons and place labels without custom map work.
- Added cache-derived collision expansion so benchmark maps and fast-planner `next` targets follow clipped walkable geometry instead of straight macro edges.
- First export produced about 17.9k edge examples, 793 object transitions, and 566 route attempts from current evidence.
- Full initial benchmark reached all 8 fixed targets, but 6 routes were suspicious/bad. Fast planner calls now distinguish full routes from actionable frontier/probe recommendations so hazardous stale paths do not have to be treated as ideal.
- Worst initial detours included Port Sarim dock to Draynor southwest tree opening, Lumbridge courtyard to Falador shield shop, and Lumbridge general store to tree stand. The generated commands include direct preview/probe flags for those cases.
- Added the fast model-backed planner after the first pass. A full 8-case fast benchmark completed in about 1.3 seconds with 8/8 actionable recommendations: 7 complete routes and 1 safe frontier/probe recommendation where the slower historical route crossed a death-confirmed Draynor hazard.
- Added hazard-costed `cache_direct` candidates and expanded the registry to 12 benchmark routes. Port Sarim-to-Draynor now targets the Draynor bank checkpoint instead of a southwest tree opening/frontier.
