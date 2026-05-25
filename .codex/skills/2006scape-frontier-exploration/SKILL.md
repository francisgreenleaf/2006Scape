---
name: 2006scape-frontier-exploration
description: "Use when live-exploring unknown or partially known 2006Scape areas with the selected profile to expand the route graph safely and cheaply, including frontier selection, short probes, stopOnCombat route_runner use, coordinate targets, server preview checks, compact screenshots, hazard/death recording, place naming, and turning passive traces into reusable navigation data."
---

# 2006Scape Frontier Exploration

Use this skill for live exploration whose purpose is to expand route coverage. Use `2006scape-route-planner-dev` for planner implementation and `2006scape-object-transitions` when the frontier is a door, gate, ladder, trapdoor, ship, or similar object transition.

## Exploration Style

Prefer short, evidence-rich probes over destination gambling. Every movement should either prove a reusable edge, identify a blocker, record a hazard, or name a frontier.

Use passive server telemetry as the primary data source. Do not poll full state repeatedly just to collect movement data.

## Starter Commands

```sh
agent-navigation/tools/observe-slim.sh
python3 agent-navigation/tools/router.py plan --from X,Y,H --to TARGET --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/route_runner.py --to X,Y,H --orient --json --run-reserve auto --allow-frontier --direct-if-preview --probe-toward-target
python3 agent-navigation/tools/route_runner.py --to X,Y,H --allow-frontier --direct-if-preview --probe-toward-target --max-walk-distance 48 --max-batches 4 --dry-run
python3 agent-navigation/tools/route_runner.py --to X,Y,H --allow-frontier --direct-if-preview --probe-toward-target --max-walk-distance 48 --max-batches 4 --run-reserve auto
agent-navigation/tools/rs-tool.sh preview_local_path '{"x":X,"y":Y,"height":0,"moveNear":true,"applyBounds":true,"maxWalkDistance":48}'
agent-navigation/tools/capture-cardinal-screenshots.sh --prefix frontier-reason
python3 agent-navigation/tools/navdb.py hazards --near X,Y,H --radius 30 --combat-level N --food N --run-energy N --run-enabled true
python3 agent-navigation/tools/navdb.py validate
python3 agent-navigation/tools/navdb.py self-test
```

## Decision Loop

1. Observe current tile, HP, food, run energy, combat state, and nearby hazards.
2. Use `route_runner.py --orient --json --run-reserve auto` or dry-run to the target/frontier before moving. For coordinate targets, check `frontierScore`; if the frontier's next step moves away from the target, use a target-directed probe/local preview instead.
3. Preview local path for unknown legs and avoid repeated blocked vectors.
4. Move with `route_runner.py --run-reserve auto` or `walk_to_tile_until_arrived` using combat/stall stop conditions.
5. If combat, HP loss, death, stall, or oscillation happens, stop probing that line and record it as evidence.
6. If the route succeeds, name durable places/frontiers only when they are useful future targets.
7. Validate route data and keep maps current when the graph changes materially.

## Naming Frontiers

Name a frontier when it is a stable reusable waypoint, a route split, a safe edge near danger, or a dead-end worth avoiding later. Do not create named places for every temporary probe now that coordinate targets are supported.

## Safety

Death can be useful evidence when the user accepts risk, but it is still expensive. Prefer probes that are clipped-previewable, short, and likely to produce reusable graph edges. Treat non-aggressive NPCs as possible route-contact hazards if prior traces show they can engage during transit.

## Context Maps

Use context-map JSON before loading images into the thread. The JSON gives bounds, center, mapfunction markers, place labels, and artifact paths; open the PNG only when the map geometry itself is needed to resolve a route or blocker.

If a probe stalls near a wall, fence, gate, stair, ladder, trapdoor, or other object and the API/context map cannot prove the live state, switch to `2006scape-screenshot-capture` and take compact cardinal screenshots before recording route data or repeating the same vector.
