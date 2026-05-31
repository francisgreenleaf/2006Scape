# ML2 Object Transition Routing Plan

This checklist is the working contract for ML2. Re-read it before evaluating completion, and only check items when current files and tests prove the item is done.

## Scope Rules

- [x] Keep ML1 under `agent-navigation/ml-routing/` intact and usable by running agents.
- [x] Build ML2 under `agent-navigation/ml2-routing/` as a separate service.
- [x] Do not wire ML2 into agent skills, live agents, or runtime startup.
- [x] Do not restart or replace active runtimes.

## Implementation Checklist

- [x] Copy the ML1 routing service into `agent-navigation/ml2-routing/` and rename/adjust only ML2-local entry points, docs, artifact defaults, and test imports.
- [x] Define a mixed route-step contract that supports legacy walk steps plus typed `walk` and `object_transition` steps.
- [x] Extract a verified transition catalog from `agent-navigation/data/routes.json`, keyed by durable object id, object tile, and side/proof tiles.
- [x] Include the Tree Gnome Stronghold south gate transition:
  - route id `tree_gnome_stronghold_south_gate_transition_static_source`
  - Gate object `190`
  - object tile `2459,3383,0`
  - south/outside tile `2459,3382,0`
  - north/inside tile `2459,3385,0`
- [x] Preserve verified transition metadata through ML2 route hints / graph edges / planner candidates.
- [x] Produce ML2 route definitions with mixed `routeSteps`, including explicit `object_transition` steps when a selected route crosses a known object transition.
- [x] Keep normal walk-only routes compatible with bounded lookahead and existing route-definition structure.
- [x] Make ML2 `status=requires-object-transition` mean the planner cannot automatically include/execute that transition yet, not that every inline gate is unsupported.
- [x] Update the ML2 route executor to preserve full step dictionaries instead of normalizing every step to tiles.
- [x] Stop walk lookahead before an `object_transition` step.
- [x] Execute `object_transition` steps by walking to `preTile`/`approachTile`, calling `object_transition_step_XS`, optionally crossing immediate `walkSteps` with `allowObjectTransition=true`, proving `postTile`/post condition, and recording evidence.
- [x] On transition proof failure, stop execution and write a route outcome with `problemKind=object_transition_failed`.
- [x] Add ML2 validation that flags known object transitions represented as plain walking and transition steps missing required proof fields.
- [x] Add focused tests for Tree Gnome gate preservation, mixed route-definition JSON, executor transition dispatch/lookahead boundary, and validation for plain-walk gate crossings.
- [x] Update ML2 `README.md`, `API.md`, and an ML2 changes document explaining the new service and differences from ML1.
- [x] Keep agent-facing skills unmodified so ML2 is documented as a separate test service but not wired into live agents.

## Required Checks

- [x] `python3 -m py_compile agent-navigation/ml2-routing/route_ml.py agent-navigation/ml2-routing/route_ml_XS.py agent-navigation/ml2-routing/ml_routing/*.py agent-navigation/ml2-routing/tools/execute_route_definition.py`
- [x] `python3 agent-navigation/ml2-routing/tests/test_ml_routing.py`
- [x] ML2 validation command for transition catalog and route data passes.
- [x] ML2 Tree Gnome gate route-definition smoke command emits an explicit `object_transition` route step for Gate `190`.
- [x] ML2 executor unit test proves it dispatches `object_transition_step_XS` and does not look ahead across that step.

## Completion Audit

- [x] Re-read this file and verify every checked item against current file contents and command output.
- [x] Confirm ML1 files were not modified for ML2 behavior.
- [x] Confirm no runtime restart/replacement occurred.
