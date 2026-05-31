# 2006Scape ML2 Routing

ML2 is the preferred agent-facing route ML service for new A-to-B route requests. It lives beside ML1 while older scripts are migrated, but agents should call ML2 directly for normal route definitions. Use ML2 especially for routes that cross doors, gates, ladders, stairs, trapdoors, ropes, and similar object chains because it preserves those transitions as typed route steps.

ML1 under `agent-navigation/ml-routing/` is now a legacy fallback and regression-comparison surface.

## Main Command

Run commands from the repo root:

```sh
python3 agent-navigation/ml2-routing/route_ml.py --help
```

Define a route:

```sh
python3 agent-navigation/ml2-routing/route_ml.py define \
  --from CURRENT_X,CURRENT_Y,0 \
  --to TARGET_PLACE_OR_TILE \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled
```

For compact agent use, prefer the XS wrapper:

```sh
python3 agent-navigation/ml2-routing/route_ml_XS.py define \
  --from CURRENT_X,CURRENT_Y,0 \
  --to TARGET_PLACE_OR_TILE \
  --combat-level 20 \
  --food 6 \
  --run-energy 70 \
  --run-enabled
```

Persisted ML2 route definitions default to:

```text
agent-navigation/.local/ml2-route-definitions/
```

ML2 execution evidence defaults to:

```text
agent-navigation/.local/run-evidence/ml2-route-executor.routes.jsonl
```

## What Changed From ML1

ML1 flattened route hints into ordinary tile waypoints. That made a known gate look like a normal walk edge, so the executor could try to path through a closed or timed object.

ML2 preserves typed route steps:

- `type: "walk"` for normal movement guide rails.
- `type: "object_transition"` for object-chain movement.

An `object_transition` step carries durable proof fields:

- `objectId`
- `objectName`
- `objectTile`
- `preTile` or `approachTile`
- `postTile` or `postCondition`
- `option`
- optional `walkSteps` for immediate crossing after opening/clicking
- `transitionProof`

The Tree Gnome Stronghold south gate is included from verified route data:

- route id: `tree_gnome_stronghold_south_gate_transition_static_source`
- object: Gate `190`
- object tile: `2459,3383,0`
- south/outside tile: `2459,3382,0`
- north/inside tile: `2459,3385,0`

## Executor Behavior

ML2 has its own executor:

```sh
python3 agent-navigation/ml2-routing/tools/execute_route_definition.py --route-definition PATH
```

For walk steps, it keeps bounded lookahead:

- `--lookahead-distance 30`
- `--lookahead-step-limit 4`

For object transitions, it stops lookahead before the object step, walks to `preTile` or `approachTile`, calls `object_transition_step_XS`, optionally queues immediate `walk_path_steps_XS` with `allowObjectTransition=true`, then proves the post side before continuing. If proof fails, it writes `problemKind: "object_transition_failed"` in the route outcome.

## Validation

Run ML2 validation:

```sh
python3 agent-navigation/ml2-routing/tools/validate_ml2.py
```

The validator checks that known transition crossings are not represented as plain walk-only route steps and that object transition steps include object/pre/post proof fields.

## Benchmark And Comparison Renders

Render the original ML benchmark set with ML1 in red and ML2 in cyan:

```sh
python3 agent-navigation/ml2-routing/route_ml.py compare-maps \
  --case-set default \
  --include-ml1-planner \
  --combat-level 61 \
  --food 8 \
  --run-energy 90 \
  --run-enabled \
  --allow-lethal
```

Render the 10-route ML2 showcase set:

```sh
python3 agent-navigation/ml2-routing/route_ml.py compare-maps \
  --case-set showcase \
  --combat-level 61 \
  --food 8 \
  --run-energy 90 \
  --run-enabled \
  --allow-lethal \
  --collision-padding-tiles 96 \
  --direct-max-expansions 2000000 \
  --collision-max-expansions 800000
```

The comparison renderer writes ignored artifacts under `agent-navigation/ml2-routing/artifacts/comparisons/<run-id>/`.
Read `comparison-report.json` first for route status, mode, distance, and quality; open the PNGs when route geometry needs visual review. ML2 showcase cases are intentionally mostly long cache-derived routes to places with little or no player trace coverage, such as Wilderness, Morytania, Castle Wars approach, and western Kandarin/Ardougne routes.

## Tests

```sh
python3 -m py_compile \
  agent-navigation/ml2-routing/route_ml.py \
  agent-navigation/ml2-routing/route_ml_XS.py \
  agent-navigation/ml2-routing/ml_routing/*.py \
  agent-navigation/ml2-routing/tools/execute_route_definition.py \
  agent-navigation/ml2-routing/tools/validate_ml2.py

python3 agent-navigation/ml2-routing/tests/test_ml_routing.py
python3 agent-navigation/ml2-routing/tools/validate_ml2.py
```

Smoke-check the Tree Gnome gate:

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

The returned `routeSteps` should include an explicit `object_transition` for Gate `190`.
