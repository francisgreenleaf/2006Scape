# Architecture

## Design Boundary

This package is an offline/local intelligence layer. It must not mutate game state except through explicit live-control commands. ML1 (`route_ml.py define`) is the preferred route-selection API; the older bare `route_runner.py --to ...` method is deprecated for agent travel. All normal movement still goes through bridge/server mechanics, whether an agent follows ML1 `routeSteps` through movement primitives or deliberately uses the legacy compatibility executor.

The model ranks and explains candidate routes; it does not click, teleport, spawn items, rewrite the player, or bypass mechanics.

## Data Flow

```text
passive traces + route evidence + route DB + hazards
        |
        v
route_ml.py export
        |
        +-- edge_examples.jsonl
        +-- route_hint_edges.jsonl
        +-- route_attempts.jsonl
        +-- object_transitions.jsonl
        |
        v
route_ml.py train --workers N
        |
        v
models/<modelId>/model.json
        |
        v
route_ml.py define/route/go/benchmark
        |
        v
cache-derived clipped path expansion for selected macro routes
        |
        v
optional hazard-costed cache-direct candidate when learned evidence detours or only reaches a frontier
```

## Modules

- `ml_routing.dataset`: converts existing navigation evidence into stable training/evaluation records.
- `ml_routing.model`: trains and loads the empirical edge-cost/risk scorer.
- `ml_routing.fast_planner`: answers live agent route requests from the trained model graph without rebuilding all passive traces.
- `ml_routing.collision`: mirrors the server cache clipping rules for terrain flags, walls, solid objects, and object footprints, then expands macro route edges into adjacent walk tiles.
- `ml_routing.planner`: chooses fast or full planning, applies model ranking, and emits compact agent output.
- `ml_routing.feedback`: appends manual route outcome/problem feedback to ignored run-evidence JSONL.
- `ml_routing.benchmark`: runs fixed offline route cases and writes reports.
- `ml_routing.comparison_maps`: renders old-vs-new route overlays and metric sidecars for benchmark cases, using the shared cache/context-map base layers for terrain, objects, mapfunction icons, and place labels.
- `route_ml.py`: single CLI entrypoint for export, train, define, route, go, benchmark, record-outcome, and loop.

## Why The First Model Is Simple

The current data volume is enough for a useful edge/risk scorer but not enough to justify an opaque neural graph model.
The MVP needs to make routing better immediately, while keeping route choices inspectable. The empirical model gives:

- learned tick/cost expectations;
- failure/combat/HP-loss risk signals;
- confidence from evidence density;
- object-transition awareness;
- region fallback when an exact edge has not been seen.

This creates a clean training/evaluation surface for later gradient-boosted models, node embeddings, or a heterogeneous GNN.

## Fast And Full Planning

`--planner fast` is the default agent-facing path. It loads the latest trained model, builds an in-memory graph from learned edge statistics and route hints, applies deterministic hazard checks, expands the selected macro path through cache-derived clipping, and returns a compact recommendation. If the learned graph is incomplete or clearly detouring, it can also test a cache-clipped direct path with hazard costs and select it over the learned candidate. This is the low-token, low-latency path agents should call during play.

`--planner full` wraps the existing `router.py` and `route_eval.py` logic. It is slower because it rebuilds trace-backed graphs, but it is useful for diagnostics and parity checks against the older deterministic planner.

## Candidate Ranking

The full route tool asks the existing deterministic route evaluator for a small set of route modes:

- safe verified traces/routes;
- safe plus partial routes;
- broad hints when the graph needs help.

Each candidate is scored by:

- predicted ticks;
- learned risk;
- low confidence;
- detour ratio;
- wrong-way/target-distance increases;
- stale building/shop/bank route hints;
- object-transition cost;
- deterministic route quality.

Bad or suspicious routes are not hidden. They are returned with an improvement note and route definition fields that let the agent inspect or prove a better path. Legacy compatibility commands may still attempt direct preview/probe learning, but they are no longer the preferred agent route method.

The fast planner can also return `status=no-learned-route` with `actionable=true` when a safe frontier/probe is better than replaying a risky historical detour. Agents should treat that as a usable learning route, not as a hard error.

If a frontier is not the actual requested target, benchmark code does not treat it as a route-quality win. The cache-direct candidate can replace that frontier when it reaches the target, and `selectedOverLearned` records whether the replacement saved tiles or simply completed a route the learned graph could not finish.

## Cache Collision Layer

The game does not walk straight lines between waypoints. `PlayerAssistant.playerWalk` delegates to `PathFinder`, which searches adjacent tiles inside a 104x104 local window and checks `Region.getClipping` masks for every cardinal and diagonal move. `RegionFactory` builds those masks from the game cache: terrain settings add full-tile clips, loc.dat wall objects add directional clips, and solid multi-tile objects add footprint clips.

`ml_routing.collision` mirrors those rules offline. The planner keeps its compact learned graph for speed, but after choosing a macro route it expands route-hint and snap edges into adjacent cache-clipped tiles. It tries each macro waypoint exactly first, then allows a small near-waypoint stop when the saved click target itself is clipped, matching `moveNear=true` walking. This makes map overlays and `recommended.next` follow bridges, docks, fences, walls, and buildings. Object-transition edges are reported and left as transitions rather than pretending a closed door or gate is ordinary walking.

For large detours, the same collision grid can be searched directly from start to target. That `cache_direct` path adds soft costs around hazard radii and buffers, so the planner can discover unrecorded shortcuts while still preferring a wide path around death/high-risk NPC zones. This is not a replacement for learned route evidence; it is a target-aware candidate generator that gives the agent a better route to prove and record.

`cache_direct` also produces a compact execution shape: `routeSteps` are the every-N-tile/turn waypoints, and `runPlan`/`runSegments` identify hazard-adjacent stretches where the agent should spend run energy instead of walking. `route_ml.py define` wraps those fields in the stable `2006scape.route-definition` API, including compatibility execution metadata and feedback instructions. Benchmark maps draw those run segments in yellow over the fast-route line.

Route execution feedback is intentionally low-friction. Legacy compatibility executor commands append `route_batch` records under ignored `.local/run-evidence/`, and agents can add `route_outcome` records with `record-outcome` for higher-level problems such as enemy contact, death, stalls, blockers, wrong destinations, or bad detours. Dataset export folds both into `route_attempts.jsonl`.

## Benchmark Map Rendering

`route_ml.py compare-maps` is the standard way to produce visual route evidence. It should not hand-roll a new base map for each experiment. It loads bounded cache terrain through `cache_world_map.py`, then draws the reusable static context layers from `render_context_map.py` so banks, stores, docks, mapfunction icons, and known places are consistent with live agent context maps. It renders the fast ML route by default; use `--include-old-planner` only for explicit regression checks against the deprecated full planner.

The aggregate comparison report is intentionally compact. Use it for metrics and image paths. Open a per-case JSON sidecar only when marker coordinates or labels are needed, and open the PNG only when route geometry needs visual inspection.

## Async Improvement Loop

`route_ml.py loop` is designed to be run from a scheduler, automation, or separate shell. One iteration:

1. exports the latest feature lake;
2. trains a new model using multiple worker threads;
3. runs offline benchmarks;
4. writes artifacts under `artifacts/`.

The loop is safe to run while an agent is playing because it only reads evidence files and writes under this folder.

## Next Refactors

- Persist a compact binary or sqlite model graph so fast planner startup does less JSON parsing.
- Add a route-cache layer keyed by profile/start/target/model id for repeated agent calls.
- Promote shortcut-probe results into first-class route-improvement benchmark cases.
- Train a second-stage ranker from route attempts once there are enough success/failure outcomes.
- Persist a compact cache-collision graph for common regions so repeated fast-planner calls do not rebuild clips.
- Add explicit inside-building, doorway, and object-transition features from cache object definitions to `edge_examples.jsonl`.
- Feed successful `cache_direct` executions back into the learned graph so repeated long routes become fast evidence-backed routes instead of repeated cache searches.
