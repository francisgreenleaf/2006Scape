# ML2 Changes

ML2 is the preferred agent-facing route service for new A-to-B route requests. It was copied from ML1 for object-transition routing work and now lives beside ML1 while older scripts are migrated.

## Implemented

- Added a transition catalog extracted from verified `agent-navigation/data/routes.json` object-transition steps.
- Preserved object-transition metadata in ML2 route hint edges instead of carrying only `objectStepCount`.
- Added mixed `routeSteps` with `type: "walk"` and `type: "object_transition"`.
- Updated the fast planner to keep transition metadata when cache collision expands route-hint paths.
- Added an ML2 executor that stops walk lookahead before object transitions and uses `object_transition_step_XS`.
- Added transition evidence records and `problemKind: "object_transition_failed"` on failed proof.
- Added ML2 validation for plain-walk crossings of known transitions and missing transition proof fields.
- Added focused tests for the Tree Gnome Stronghold south gate, mixed route definitions, executor dispatch, and validation.

## Tree Gnome Stronghold South Gate

The verified route `tree_gnome_stronghold_south_gate_transition_static_source` now produces an explicit `object_transition` step:

- Gate object id: `190`
- object tile: `2459,3383,0`
- south/outside tile: `2459,3382,0`
- north/inside tile: `2459,3385,0`
- default option: `open`

## Files

- `ml_routing/transition_catalog.py`: extracts and reverses verified transition metadata.
- `ml_routing/dataset.py`: emits typed transition route-hint edges.
- `ml_routing/fast_planner.py`: carries transition metadata through graph and route-step generation.
- `tools/execute_route_definition.py`: executes mixed route definitions.
- `ml_routing/validation.py`: validates mixed route-step contracts.
- `tools/validate_ml2.py`: CLI validation wrapper.

## Boundaries

ML1 was left in place under `agent-navigation/ml-routing/` for fallback and regression comparisons. The ML2 executor, route definitions, evidence paths, docs, and tests use ML2-local paths so agents can choose the current route service explicitly.
