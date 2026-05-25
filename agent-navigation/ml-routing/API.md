# 2006Scape Route Definition API

ML1 is the fast `route_ml.py define` route-definition API. Agents should call `define` when they need a route and do not need planner debug internals:

```sh
python3 agent-navigation/ml-routing/route_ml.py define \
  --from CURRENT_X,CURRENT_Y,0 \
  --to TARGET_PLACE_OR_TILE \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled
```

The response is a single JSON object with:

- `routeSteps`: compact every-N-tile/turn waypoints for the whole route.
- `runPlan` and `runSegments`: where to conserve run and where to spend it.
- `evidence`: whether the selected route is trace-proven, backed by a verified route hint, cache-planned, or unproven.
- `safety`: hazard warnings, detour/wrong-way review flags, and whether review is required.
- `execution.command`: the preferred live executor command. It invokes `execute_route_definition.py --route-definition ...` so the agent follows the selected `routeSteps` through bridge walking primitives and records evidence.
- `feedback`: automatic evidence path plus a `record-outcome` command template.

The fast planner reads curated route hints from the current navigation DB on each call. Models supply learned costs and risk priors, but current `places.json` / `routes.json` anchors remain authoritative.

`quality` is a geometry/detour signal, not the same as proof. A route can be geometrically indirect but still proven if `evidence.proven` is `true`; in that case follow `safety.requiresReview` rather than rejecting the route just because `quality` is `bad`.

Example shape:

```json
{
  "api": "2006scape.route-definition",
  "schemaVersion": 1,
  "routeId": "port_sarim_dock-draynor_bank_hazard_checkpoint-cache_direct-143-17",
  "status": "ok",
  "quality": "bad",
  "actionable": true,
  "from": "port_sarim_dock",
  "to": "draynor_bank_hazard_checkpoint",
  "distanceTiles": 143,
  "routeStepCount": 17,
  "evidence": {
    "level": "cache_planned",
    "proven": false,
    "edgeSources": {"cache_direct": 143},
    "routesUsed": {}
  },
  "routeSteps": [
    {"x": 3045, "y": 3204, "height": 0},
    {"x": 3030, "y": 3203, "height": 0},
    {"x": 3027, "y": 3210, "height": 0}
  ],
  "runPlan": {
    "policy": "conserve_run_until_hazard_segments",
    "routeDistance": 143,
    "runTileDistance": 59,
    "walkTileDistance": 84,
    "segmentCount": 2
  },
  "execution": {
    "strategy": "ml_route_steps",
    "routeDefinitionPath": "agent-navigation/.local/ml-route-definitions/port_sarim_dock-draynor_bank_hazard_checkpoint-cache_direct-143-17.json",
    "command": ["python3", "agent-navigation/tools/execute_route_definition.py", "--to", "draynor_bank_hazard_checkpoint", "--run-mode", "auto", "--eat-at", "10", "--route-definition", "agent-navigation/.local/ml-route-definitions/port_sarim_dock-draynor_bank_hazard_checkpoint-cache_direct-143-17.json"]
  },
  "feedback": {
    "automaticEvidenceJsonl": "agent-navigation/.local/run-evidence/ml-route-runner.routes.jsonl",
    "automaticEvents": ["route_batch"]
  }
}
```

Preferred live execution is `execution.command`, or equivalently `execute_route_definition.py --route-definition PATH`. The executor follows `routeSteps` through normal bridge movement primitives, defaults to `--eat-at 10`, observes nearby NPC context on combat/HP loss, and appends `route_batch` plus `route_outcome` evidence. Do not replace ML1 with a bare `route_runner.py --to ...` command. Bare Route Runner is the deprecated route method and should only be used for legacy diagnostics.

Use `record-outcome` when the agent detects a route-level problem not already obvious from batch output, especially enemy contact, death, stalls, object blockers, wrong destination, or an obviously bad detour. The next `export` includes those records in `route_attempts.jsonl`, and training folds them into empirical risk stats.
