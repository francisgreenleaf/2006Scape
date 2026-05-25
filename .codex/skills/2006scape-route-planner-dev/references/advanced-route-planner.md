# Advanced Route Planner Plan

This is the long-term technical plan for turning 2006Scape navigation into a self-improving routing system that can eventually learn from every movement, failure, death, object transition, and successful trip.

The near-term system remains deterministic and explainable. The model layer should learn costs, risks, confidence, and frontier value; it should not directly click the game or bypass normal mechanics.

## Target Outcome

Build a local route intelligence stack that can answer:

- What is the fastest safe route from A to B for the selected profile's current level, inventory, run energy, food, and known hazards?
- Which parts of a route are proven, inferred, risky, blocked, or unknown?
- Which frontier should be explored next to maximize map connectivity and reduce future travel time?
- Which object transitions, NPC contacts, map-region crossings, and terrain features change movement cost or safety?
- How confident are we that a route will complete without death, combat, oscillation, or wasted clicks?

## Hardware Envelope

Assume local training on a MacBook Pro with M5 Max and 128 GB unified memory. Design for this class of machine:

- Train route-specific models locally, not giant general language models.
- Keep datasets columnar and incremental so daily training is cheap.
- Use Apple Silicon-friendly stacks when implemented, such as PyTorch MPS or MLX, after checking the current local library support.
- Target small to medium graph/tabular models first: thousands to millions of route examples, not internet-scale training.
- Favor frequent retraining and evaluation over one large brittle model.

## Data Sources

Primary evidence:

- Passive server player traces from `2006Scape Server/data/logs/player-movement-traces/`.
- Bridge batch traces from `2006Scape Server/data/logs/agent-movement-traces/`.
- Curated `agent-navigation/data/places.json`, `routes.json`, and `hazards.json`.
- Bridge tool results from `walk_to_tile_until_arrived`, `preview_local_path`, `interact_object`, `wait_until_idle`, and combat/death observations.
- Cache-backed world map data from `agent-navigation/tools/cache_world_map.py`.

Secondary evidence:

- Compact screenshots for ambiguous visual geometry, linked by path and resolution.
- Session logs and rollout summaries for high-level failure causes.
- Player profile state such as skills, equipment, inventory, food, run energy, and recent deaths.

Do not use ad hoc screenshots as the primary map source. The retired minimap fog workflow must remain retired.

## Canonical Event Schema

Every future training record should preserve:

- `eventType`: movement, state, preview, object_transition, combat_contact, death, stall, oscillation, teleport, map_region_change, route_start, route_end.
- `tile`, `previousTile`, `targetTile`, `height`, `timestampMs`, `serverTick`.
- `actionSource`: passive_tick, route_runner, bridge_batch, manual_record, object_interaction.
- `playerState`: combat level, HP, max HP, food count, run energy, run enabled, inventory space, equipment summary.
- `environment`: nearby NPCs, nearby objects, hazard ids, map cache features, region id.
- `result`: success, partial, blocked, combat, damage, death, timeout, no_progress, transition.
- `evidence`: trace file, session id, screenshot path, bridge tool result id, route id, place id.

Keep raw events immutable. Build derived datasets from them.

## Graph Representation

Use a heterogeneous graph:

- Tile nodes: `x,y,height`.
- Place nodes: banks, towns, route anchors, shops, frontier labels.
- Object nodes: doors, gates, ladders, trapdoors, stairs, ships, toll gates, portals.
- Hazard nodes: NPC contact zones, death sites, combat areas, high entropy routing zones.
- Route/session nodes: completed trips, failed probes, exploration sweeps.

Edges:

- Movement edge: adjacent or short-step tile transition.
- Batch edge: route_runner/walk batch from start to final tile.
- Transition edge: object interaction with pre/object/post proof.
- Hazard edge: tile/place proximity to risk source.
- Membership/requirement edge: item, quest, level, coin, run-energy, or dialogue requirement.

Each edge should carry distance, ticks, run-energy cost, failure count, combat count, HP loss, deaths, source, confidence, and recency.

## Current Baseline

ML1 (`route_ml_XS.py define`) is now the preferred route-selection surface for agents. Full `route_ml.py define` remains available when XS omits fields needed for debugging. The older deterministic stack should stay strong as a benchmark and fallback diagnostic path:

1. `navdb.py` validates places/routes/hazards and loads unified traces.
2. `router.py` builds a hybrid graph from passive traces, curated routes, and hazards.
3. `route_runner.py` is a deprecated standalone live-routing method and compatibility executor. It can still preflight batches through server `preview_local_path`, but agents should not use bare `route_runner.py --to ...` as normal travel.
4. Object transitions are recorded as explicit route steps, never inferred from a successful click alone.

This baseline is the benchmark ML1 must beat or explain.

## Model Roadmap

Phase 1: Feature Lake

- Convert traces and route DB into stable tabular datasets.
- Generate edge-level examples: attempted edge, context, outcome, cost, risk.
- Generate route-level examples: start, target, chosen path, completion status, travel time, damage, death.
- Build daily dataset summaries: graph size, new edges, deaths, blocked zones, route success rate.

Phase 2: Learned Edge Cost

- Train a small supervised model to predict edge cost and risk from current state plus map/trace features.
- Good first models: gradient boosted trees, random forest, logistic/Poisson heads, or compact MLP.
- Targets: expected ticks, failure probability, combat probability, death probability, confidence.
- Use predictions as penalties inside Dijkstra/A*, not as direct actions.

Phase 3: Graph Embeddings

- Train node embeddings for tiles/places/objects/hazards from movement co-occurrence and route outcomes.
- Use embeddings for frontier scoring, route compression, and cluster discovery.
- Keep embeddings inspectable through nearest-neighbor reports and map overlays.

Phase 4: Heterogeneous GNN

- Train a GraphSAGE/GAT-style model over tile/place/object/hazard nodes.
- Inputs: map cache features, trace stats, hazards, object definitions, player state, and requirements.
- Outputs: edge cost, risk, confidence, and route-frontier value.
- Use mini-batch neighbor sampling so training fits comfortably in 128 GB unified memory.

Phase 5: Planner-Ranker Hybrid

- Generate candidate routes with deterministic search.
- Rank candidates with learned models.
- Explain route choice through top costs/risks: distance, hazards, failed traces, low confidence, object transitions, food/run constraints.
- Preserve safety gates that can veto a model-ranked route.

Phase 6: Active Learning

- Pick frontiers that maximize graph connectivity and reduce uncertainty, not just distance.
- Prefer probes that are locally previewable, bounded, and likely to produce reusable edges.
- Feed every success/failure back into the daily feature lake.

## Evaluation

Every planner/model change should report:

- Route success rate by target class.
- Median and p90 travel ticks.
- Deaths per 100 route attempts.
- Combat contacts per 100 route attempts.
- HP lost per route.
- No-progress/oscillation/stall count.
- Number of new reusable graph edges.
- Reuse rate for reverse-inferred edges.
- Frontier information gain: new connected nodes per risky probe.

Keep test routes fixed for regression:

- Lumbridge courtyard to Varrock approach.
- Lumbridge courtyard to Falador shield shop.
- Falador shield shop to Port Sarim dock.
- Port Sarim dock to Draynor southwest tree opening.
- Rimmington to Port Sarim south coast frontier.

## Daily Work Pattern

1. Validate the DB and current deterministic router.
2. Summarize new passive traces and failures.
3. Add only durable schema or graph improvements.
4. Run fixed benchmark routes in dry-run mode.
5. Render a bounded context or segment map with `render_agent_context_map_XS.py` when a route looks indirect, overly historical, or likely to hide a shortcut. Use the full renderer only when XS omits needed marker/detail fields.
6. If live proof is needed, request ML1 with `route_ml_XS.py define` and follow the returned `steps`/route definition through normal bridge movement primitives. Use Route Runner only for compatibility-executor regression checks.
7. Render global topology only when the user needs a human-facing graph review or the graph changed materially.
8. Record any repeatable planner lesson in the relevant skill or reference.

## Non-Goals

- Do not train a model that bypasses the bridge or mutates player state directly.
- Do not depend on full desktop screenshots for navigation memory.
- Do not let a model hide why a route was chosen.
- Do not require cloud training for the normal daily loop.
- Do not treat F2P/member gates, doors, ladders, or ships as normal movement edges.

## First Implementation Milestones

- Stable route feature export command.
- Deterministic benchmark command and JSON report.
- Fast bounded current-location and route-segment cache-map wrapper for agent shortcut inspection.
- Explicit object-transition dataset records.
- Frontier scoring report for unconnected target areas.
- Edge-risk baseline model trained from current traces.
- Route-ranker prototype that reorders deterministic candidate paths.
