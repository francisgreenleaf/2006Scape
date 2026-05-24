---
name: 2006scape-object-transitions
description: "Use when learning, debugging, recording, or validating 2006Scape route transitions through doors, gates, ladders, stairs, trapdoors, ships, portals, tolls, member gates, or other object-chain blockers in /Users/kevin/Documents/2006Scape. Covers approach tiles, object ids, interactionWalkTarget, interact_object, post-state proof, screenshots, and transitionProof records for agent-navigation routes."
---

# 2006Scape Object Transitions

Use this skill when movement depends on an object or interface transition. Do not model doors, gates, ladders, trapdoors, stairs, ships, or member gates as ordinary walk edges.

## Proof Rule

A successful `interact_object` response is not enough. A transition is verified only when the post-state proves it: changed tile, changed height, opened/closed state, interface/dialogue state, or a documented failure condition.

Record:

- pre-interaction player tile;
- object id, name, tile, face/type when available;
- reachable `interactionWalkTarget` or approach tile;
- action/option used;
- post-tile or post-condition;
- screenshot path if visual geometry mattered;
- fallback if the interaction fails or leads somewhere unsafe.

Passive telemetry now records manual and bridge-driven object clicks as `object_interaction` events in `2006Scape Server/data/logs/player-movement-traces/`. Use those records as evidence: `queued` is the raw click target, `completed` is the reached/post-handler state, and object-backed graph edges are intentionally not treated as reversible walking edges.

## Starter Commands

```sh
agent-navigation/tools/rs-tool.sh observe_state '{}'
agent-navigation/tools/rs-tool.sh find_nearest_object '{"name":"gate","maxDistance":20}'
agent-navigation/tools/rs-tool.sh preview_local_path '{"x":X,"y":Y,"height":0,"moveNear":true,"applyBounds":true,"maxWalkDistance":48}'
agent-navigation/tools/rs-tool.sh walk_to_tile_until_arrived '{"x":X,"y":Y,"height":0,"stopDistance":0,"maxTicks":80,"maxWalkDistance":48,"stopOnCombat":true,"stopOnStall":true}'
agent-navigation/tools/rs-tool.sh interact_object '{"objectId":OBJECT_ID,"x":X,"y":Y,"option":"first"}'
agent-navigation/tools/rs-tool.sh wait_until_idle '{"maxTicks":10,"movement":true,"skilling":false,"combat":false}'
agent-navigation/tools/capture-cardinal-screenshots.sh --prefix transition-reason
python3 agent-navigation/tools/navdb.py validate
python3 agent-navigation/tools/navdb.py self-test
```

## Workflow

1. Observe full state and identify the object from bridge data.
2. Preview or walk to the object's interaction target; do not click from an unknown side.
3. Capture compact screenshots if object geometry is ambiguous.
4. Interact once with the intended option.
5. Wait/observe and compare pre-state to post-state.
6. Record the transition in route data only after proof exists.
7. Validate `navdb.py`; unresolved object transitions should fail validation or remain clearly marked as unverified.

## Boundaries

Do not force member gates or tolls without explicit user approval and required items/coins. Do not admin-teleport, spawn keys/items, or directly mutate route state to pretend a transition was solved.

Use `2006scape-route-planner-dev` when changing how transitions are represented in the graph. Use `2006scape-frontier-exploration` when deciding whether to explore around a blocked transition.
