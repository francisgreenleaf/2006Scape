---
name: 2006scape-route-planner-dev
description: "Use when designing, editing, debugging, or validating the 2006Scape route-planning system in /Users/kevin/Documents/2006Scape, including agent-navigation/tools/router.py, route_runner.py, navdb.py graph semantics, passive movement traces, server clipped-path previews, hazard/failure weighting, reverse-edge inference, coordinate targets, future ML/GNN routing datasets, evaluation metrics, and low-token A-to-B planning."
---

# 2006Scape Route Planner Dev

Use this skill for route-planning system work. Use `2006scape-route-agent` or `2006scape-frontier-exploration` for live gameplay exploration, and use `2006scape-agent-bridge-dev` if bridge tool source or metadata must change.

## Core Direction

The long-term goal is a self-improving routing system: passive telemetry first, deterministic graph planning now, learned edge/risk models next, and eventually graph neural network ranking on top of the evidence database. Read `references/advanced-route-planner.md` when changing data shape, training/evaluation plans, or long-term model direction.

Do not replace evidence-backed planning with an opaque model. Learned models should score costs, risks, confidence, and frontiers; deterministic search should still enforce safety constraints and explainable route choices.

## Main Files

- `agent-navigation/tools/router.py`: learned graph planner over places, routes, hazards, passive traces, and route traces.
- `agent-navigation/tools/route_eval.py`: deterministic route-quality scorer for cost/tick estimates, detour ratios, wrong-way flags, and shortcut/map-inspection triggers before live movement.
- `agent-navigation/tools/route_runner.py`: low-token bridge executor that can compactly orient with observe+plan+route-eval+preview, preserve run energy with `--run-reserve`, and run movement batches.
- `agent-navigation/tools/marathon_runner.py`: timed repeated-route benchmark runner that preflights each leg with `route_eval.py`, renders suspicious/bad detour context maps, delegates movement to `route_runner.py`, passes through run-reserve policy, and writes JSONL route-performance events.
- `agent-navigation/tools/render_agent_context_map.py`: fast agent-facing cache map wrapper for inspecting current tile, recent movement, latest segment paths, cache mapfunction icons, and place labels without loading full-world images. Default outputs are unique ignored artifacts under `agent-navigation/.local/context-maps/<date>/`.
- `agent-navigation/tools/render_context_map.py`: lower-level bounded cache-backed context renderer used by the agent wrapper.
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
- Long routes should be run through `route_runner.py` with flushed batch output and small enough batch windows to preserve feedback. While the process is running, poll at the expected batch interval instead of every few seconds; use `maxTicks * 600ms` plus a small buffer as the first estimate, then shorten only near expected completion or when safety signals are likely.
- Tile/batch limits are execution guardrails, not permanent navigation limits. Raise them on open, well-proven road segments and clamp them near hazards, object transitions, stalls, or low-confidence traces.
- Use `route_runner.py --orient --json` before uncertain long legs. It performs one observe, graph plan, `route_eval`, clipped preview, optional suspicious-route context map, and compact run-policy summary without moving.
- For coordinate targets with no learned route, frontier selection now scores directional progress from the current tile to the target. Inspect `frontierScore` in orient/route-eval JSON: negative `firstStepDistanceProgress` or nonzero `firstStepWrongWayDistance` means the graph frontier is probably pointing away from the objective, so prefer a target-directed probe or local preview instead of following that frontier blindly.
- Use `--run-reserve auto` on long or hazard-adjacent route execution. It scans planned waypoints for hazards with `minRunEnergy`/`requiresRun`, conserves that reserve on normal batches using the previewed path length as the estimated spend, and spends it only inside/near the hazard band. Batch output includes `runReq`, `runBefore`, `runAfter`, `runSpent`, `expectedRunSpend`, `tps`, `tilesPerTick`, and `runWarn`; treat non-`none` `runWarn` values as evidence that run did not actually save ticks. Pass `--evidence-jsonl PATH` when you need structured route-batch run-efficiency records for ML/router analysis; `mining_runner.py` writes a sibling `.routes.jsonl` automatically for its route legs.
- If a planned route makes a wide detour, render a bounded context or segment map with `render_agent_context_map.py` and actively look for a locally previewable shortcut/frontier instead of blindly replaying the long historical path.
- Treat context-map PNGs/JSON as disposable agent artifacts. Read the JSON summary and marker fields first; open the PNG only when visual layout is actually needed. Let the renderer auto-name outputs by default; pass `--output`/`--summary` only for deliberate smoke tests or user-facing comparison files.
- Do not use `Mr. Flame`, `Heat Map`, `Mr. Flame Fog`, or any full topology render as part of routine agent routing. Those are human-facing analysis maps unless the user explicitly requests them.

## Starter Commands

```sh
python3 agent-navigation/tools/router.py plan --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled --json
python3 agent-navigation/tools/route_eval.py --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/route_runner.py --to PLACE --orient --json --run-reserve auto
python3 agent-navigation/tools/route_runner.py --to PLACE --max-walk-distance 48 --max-batches 6 --dry-run
python3 agent-navigation/tools/route_runner.py --to PLACE --max-walk-distance 48 --max-batches 6 --run-reserve auto
python3 agent-navigation/tools/route_runner.py --to X,Y,H --allow-frontier --direct-if-preview --probe-toward-target --dry-run
python3 agent-navigation/tools/marathon_runner.py --laps 10 --run-reserve auto
python3 agent-navigation/tools/render_agent_context_map.py --center X,Y,H --radius-tiles 72 --pixels-per-tile 5 --recent-seconds 60
python3 agent-navigation/tools/render_agent_context_map.py --segment-from FROM_PLACE --segment-to TO_PLACE
agent-navigation/tools/rs-tool.sh preview_local_path '{"x":X,"y":Y,"height":0,"moveNear":true,"applyBounds":true,"maxWalkDistance":48}'
python3 agent-navigation/tools/navdb.py graph-summary
python3 agent-navigation/tools/navdb.py validate
python3 agent-navigation/tools/navdb.py self-test
python3 agent-navigation/tools/navdb.py trace-tests
```

## Validation

After planner edits, run:

```sh
python3 -m py_compile agent-navigation/tools/router.py agent-navigation/tools/route_eval.py agent-navigation/tools/route_runner.py agent-navigation/tools/marathon_runner.py agent-navigation/tools/navdb.py agent-navigation/tools/render_context_map.py agent-navigation/tools/render_agent_context_map.py
python3 agent-navigation/tools/navdb.py validate
python3 agent-navigation/tools/navdb.py self-test
python3 agent-navigation/tools/router.py plan --from 3222,3218,0 --to lumbridge_castle_courtyard
```

If route execution changed, dry-run first, then prove one short route through `route_runner.py`. Do not restart runtime unless live bridge behavior requires it.

## Daily Improvement Loop

Each route-planner development pass should improve at least one of: data capture, graph correctness, safety filtering, route reuse, frontier selection, low-token execution, evaluation, or ML-readiness. Prefer durable data/model pipeline improvements over one-off route fixes.
