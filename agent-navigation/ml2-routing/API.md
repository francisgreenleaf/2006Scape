# ML2 Route Definition API

ML2 returns the same top-level route-definition shape as ML1, but `routeSteps` may now be mixed typed steps. This is the preferred route-definition API for active agents making new A-to-B route requests. ML1 remains available only as a legacy fallback or regression comparison.

## Define

```sh
python3 agent-navigation/ml2-routing/route_ml.py define \
  --from CURRENT_X,CURRENT_Y,0 \
  --to TARGET_PLACE_OR_TILE \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled
```

Agents should normally use the compact wrapper:

```sh
python3 agent-navigation/ml2-routing/route_ml_XS.py define \
  --from CURRENT_X,CURRENT_Y,0 \
  --to TARGET_PLACE_OR_TILE \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled
```

The full response is a single JSON object with:

- `routeSteps`: mixed typed route steps.
- `routeStepSchema`: currently `mixed_walk_object_transition_v1`.
- `runPlan` and `runSegments`: run conservation and spend guidance.
- `evidence`: trace-proven, verified route hint, cache-planned, or unproven status.
- `safety`: review flags, hazards, wrong-way flags, and detour hints.
- `execution.command`: ML2 executor command to run exactly when live movement is intended.
- `feedback`: ML2 evidence path and manual outcome command template.

The compact `route_ml_XS.py define` response intentionally hides developer-only route-quality, wrong-way, detour, and feedback-plumbing fields. Agents should key off `status`, `decision`, `evidence.summary`, `safety.review`, and especially the presence of `cmd`. If `cmd` is present, the route is meant to be executable; `safety.review=true` is an attention flag, not a rejection by itself.

## Route Integrity

Every emitted definition includes a `geometry` summary. Ordinary walk steps must form a continuous same-plane chain with no untyped gap above 64 tiles. Doors, ladders, ships, teleports, and other discontinuities are valid only when represented by an explicit typed transition step.

```json
{
  "status": "invalid-route-geometry",
  "actionable": false,
  "geometry": {
    "valid": false,
    "largestDiscontinuity": {
      "index": 42,
      "from": {"x": 3269, "y": 3167, "height": 0},
      "to": {"x": 2662, "y": 3295, "height": 0},
      "distance": 607
    }
  },
  "execution": {"command": []}
}
```

The compact XS response always exposes `geometry.valid` and the largest invalid jump, even when that step would otherwise be hidden by the route-step preview limit. Never construct a command for `invalid-route-geometry`.

`evidence.proven=true` applies to the complete validated route, not merely to the presence of one successful trace edge. Cache-planned routes remain valid to try but are not player-proven.

## Step Types

Walk step:

```json
{
  "type": "walk",
  "x": 2459,
  "y": 3382,
  "height": 0,
  "to": {"x": 2459, "y": 3382, "height": 0}
}
```

Object transition step:

```json
{
  "type": "object_transition",
  "objectId": 190,
  "objectName": "Gate",
  "objectTile": {"x": 2459, "y": 3383, "height": 0},
  "preTile": {"x": 2459, "y": 3382, "height": 0},
  "approachTile": {"x": 2459, "y": 3382, "height": 0},
  "postTile": {"x": 2459, "y": 3385, "height": 0},
  "option": "open",
  "transitionProof": {
    "preTile": {"x": 2459, "y": 3382, "height": 0},
    "objectTile": {"x": 2459, "y": 3383, "height": 0},
    "postTile": {"x": 2459, "y": 3385, "height": 0}
  },
  "x": 2459,
  "y": 3385,
  "height": 0,
  "to": {"x": 2459, "y": 3385, "height": 0}
}
```

The top-level `x/y/height` and `to` fields point to the completion tile so compact renderers and older route-step consumers can still preview the route. The executor uses the typed fields for behavior.

## Executor Contract

`execution.command` points at:

```text
agent-navigation/ml2-routing/tools/execute_route_definition.py
```

Normal walk steps are batched with bounded lookahead. Lookahead stops before an `object_transition` step.

For `object_transition`, the executor:

1. walks to `preTile` or `approachTile`;
2. calls `object_transition_step_XS` with `objectId`, `objectTile`, `option`, and tick budget;
3. optionally calls `walk_path_steps_XS` with `allowObjectTransition=true` for immediate crossing steps;
4. proves `postTile` or post condition;
5. writes `route_transition`, `route_batch`, and `route_outcome` evidence.

If proof fails, execution stops and the outcome uses:

```json
{"problemKind": "object_transition_failed"}
```

Before any bridge observation or action, the executor validates the complete persisted definition again. This protects against stale definitions created by older models. Invalid definitions stop with:

```json
{"status": "route_data_corruption", "problemKind": "route_data_corruption"}
```

After geometry validation and still before any bridge action, the executor
acquires the selected profile's gameplay-controller lease. A standalone route
cannot compete with an active runner:

```json
{"status": "controller_conflict", "problemKind": "controller_conflict"}
```

An executor launched by the active supervised runner inherits that runner's
opaque lease id and is allowed to proceed. The lease id is process plumbing;
agents should use `gameplay_controller_XS.py status/stop`, not read or edit the
lease file directly.

## Status Semantics

`status: "requires-object-transition"` means ML2 cannot automatically include or execute the needed transition in this route definition yet, usually because the request crosses surface/underground layers or separate underground cache areas without a known transition chain. It does not mean every inline gate is unsupported. Known inline transitions should appear directly in `routeSteps` as `object_transition`.

`evidence.proven: false` still means "not player/route-hint proven yet"; it is not automatically a rejection when `status` is `ok`, an execution command is present, and `safety.requiresReview`/`safety.review` is `false`.

## Model Release Check

Training rejects any untyped model walk edge above the same integrity limit. Validate a committed or freshly trained model with:

```sh
python3 agent-navigation/ml2-routing/route_ml.py validate-model
```

The command must report `valid: true` and `invalidEdges: 0` before updating the active model manifest.

## Tree Gnome Gate Example

```sh
python3 agent-navigation/ml2-routing/route_ml.py define \
  --from 2459,3382,0 \
  --to 2459,3385,0 \
  --combat-level 3 \
  --food 0 \
  --run-energy 0 \
  --no-cache-direct \
  --no-cache-mesh
```

Expected key fields:

```json
{
  "routeStepSchema": "mixed_walk_object_transition_v1",
  "routeSteps": [
    {"type": "walk", "x": 2459, "y": 3382, "height": 0},
    {
      "type": "object_transition",
      "objectId": 190,
      "objectName": "Gate",
      "objectTile": {"x": 2459, "y": 3383, "height": 0},
      "preTile": {"x": 2459, "y": 3382, "height": 0},
      "postTile": {"x": 2459, "y": 3385, "height": 0}
    }
  ]
}
```
