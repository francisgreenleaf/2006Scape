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

- `routeSteps`: compact every-N-tile/turn waypoints for the whole route. They are execution guide rails, not mandatory stop-and-replan checkpoints.
- `runPlan` and `runSegments`: where to conserve run and where to spend it.
- `evidence`: whether the selected route is trace-proven, backed by a verified route hint, cache-planned, or unproven.
- `safety`: hazard warnings, detour/wrong-way review flags, and whether review is required.
- `execution.command`: the preferred live executor command. It invokes `execute_route_definition.py --route-definition ...` so the agent walks ahead across bounded chunks of the selected `routeSteps` through bridge walking primitives and records evidence.
- `feedback`: automatic evidence path plus a `record-outcome` command template.

The XS wrapper also adds a compact `decision` field. Treat `decision` as the first action hint: `execute` means run `cmd`, `transition_first` means use the required object transition before requesting the next route, and `do_not_execute` means the result is not a live route.

The fast planner reads curated route hints from the current navigation DB on each call. Models supply learned costs, combat-exposure costs, and risk priors. Route hints can prove useful transitions, but cache-derived candidates may replace destination-irrelevant learned detours when the cache collision graph can produce a shorter walkable route.

ML1 supports the level-0 surface map and same-cache-area underground routes. Surface coordinates are `x=1728..3839`, `y=2560..4031`; underground-style areas use high Y offsets such as `+6400`. Surface/underground crossings and routes between separate underground cache areas return `actionable:false`, no execution command, and `status:"requires-object-transition"`; route to the relevant entrance/exit/ladder/stairs/trapdoor/gate first, use it, then request the next route. `status:"unsupported-coordinate-layer"` means the tile is outside a supported cache route area. Underground cache-direct routes use cache-derived clipping plus hard valid-region boundaries so missing underground cache regions are not treated as walkable floor.

Trust ladder:

1. Call `define` for normal route selection.
2. Execute the returned `execution.command` or `execute_route_definition.py --route-definition PATH`.
3. Use `route`/context maps/route-failure readers only for debugging the ML1 answer.
4. Use bare Route Runner only for explicit legacy diagnostics; it is not the route API.

`quality` is a geometry/detour signal, not the same as proof. A route can be geometrically indirect but still proven if `evidence.proven` is `true`; in that case follow `safety.requiresReview` rather than rejecting the route just because `quality` is `bad`.

`evidence.proven:false` means "not player/route-hint proven yet"; it is not automatically a no. If `status:"ok"`, `actionable:true`, `execution.command` is present, and `safety.requiresReview:false`, the route is valid to try and should record outcome evidence. `evidence.level == "cache_planned"` is the normal model/cache-validated state for this: `cache_direct` searches the cache collision grid from start to target, and `cache_mesh` keeps required learned object-transition crossings, then replans normal walking legs from cache-derived terrain/object clipping so remembered banks or shops do not become mandatory stops unless they are the target.

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
    "lookaheadDistance": 30,
    "lookaheadStepLimit": 4,
    "routeDefinitionPath": "agent-navigation/.local/ml-route-definitions/port_sarim_dock-draynor_bank_hazard_checkpoint-cache_direct-143-17.json",
    "command": ["python3", "agent-navigation/tools/execute_route_definition.py", "--to", "draynor_bank_hazard_checkpoint", "--run-mode", "auto", "--eat-at", "10", "--route-definition", "agent-navigation/.local/ml-route-definitions/port_sarim_dock-draynor_bank_hazard_checkpoint-cache_direct-143-17.json"]
  },
  "feedback": {
    "automaticEvidenceJsonl": "agent-navigation/.local/run-evidence/ml-route-executor.routes.jsonl",
    "automaticEvents": ["route_batch"]
  }
}
```

Preferred live execution is `execution.command`, or equivalently `execute_route_definition.py --route-definition PATH`. The executor treats `routeSteps` as route guide rails, walks ahead by default with `--lookahead-distance 30` and `--lookahead-step-limit 4`, observes nearby NPC context on combat/HP loss, and appends `route_batch` plus `route_outcome` evidence. Use `--no-lookahead` or `--lookahead-distance 0` only for deliberate old one-step diagnostics. Do not replace ML1 with a bare `route_runner.py --to ...` command. Bare Route Runner is the deprecated route method and should only be used for legacy diagnostics.

`routeDefinitionPath` defaults to the legacy shared directory `agent-navigation/.local/ml-route-definitions/`. The generated execution evidence path is profile-scoped when `--trace-profile` is set, but route-definition artifacts themselves use the shared default unless the caller passes `--route-definition-dir` or runs the returned `execution.command` path as emitted.

Use `record-outcome` when the agent detects a route-level problem not already obvious from batch output, especially enemy contact, death, stalls, object blockers, wrong destination, or an obviously bad detour. The next `export` includes those records in `route_attempts.jsonl`, and training folds them into empirical risk stats.
