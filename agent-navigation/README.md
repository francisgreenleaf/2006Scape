# Agent Navigation Database

This folder is the repo-local memory system for safe movement, route learning, screenshots, and map knowledge. It is separate from the current Java `AgentKnowledgeBase` so route evidence can be collected, reviewed, and improved without changing gameplay code on every discovery.

For the reliable server/client/login/bridge startup flow used before route exploration, see [Local Agent Startup](../docs/local-agent-startup.md).

## Layout

- `data/places.json`: named places, aliases, arrival radii, safety notes, and canonical tiles.
- `data/routes.json`: route memories between places, including walk tiles, door/gate/floor interactions, blockers, run policy, and evidence links.
- `data/hazards.json`: known danger zones, NPC risk, requirements, and avoidance notes.
- `data/script_registry.json`: searchable metadata for repo helper scripts, their aliases, tags, descriptions, and examples.
- `data/agility_courses.json`: agility course obstacle definitions for `tools/agility_runner.py`.
- `data/agility/policies/*.policy.json`: ignored local adaptive course timing/failure state.
- `data/agility/runs/`: ignored local agility smoke/lap JSONL evidence and summaries.
- `data/mining/runs/`: ignored local mining runner JSONL evidence for site choice, routing, mining batches, and banking.
- `data/observations.jsonl`: ignored local append-only route-learning observations from `rs.observe_state`, screenshots, and manual notes.
- `data/movement_traces*.jsonl`: ignored optional legacy/dev movement trace streams from `tools/route_recorder.py`.
- `data/route_tests.json`: regression checks for expected route selection, next steps, and safety warnings.
- `.local/character-memory/<profile>/`: ignored intentional character memories and goals, kept separate per profile.
- `screenshots/`: ignored local copied screenshots used as evidence. Commit only curated metadata, not bulk PNG captures.
- `schema/`: JSON Schemas for the data files.
- `cache-world-map.md`: notes on the cache-backed world map renderer and how to reuse it in other tools.
- `scripting-primitives.md`: bridge scripting boundary, primitive tool list, compatibility tools, and current external runner entry points.
- `tools/navdb.py`: dependency-free CLI for validation, route lookup, hazard checks, and recording observations.
- `tools/capture-client-screenshot.sh`: macOS helper that captures the running Java client window and prints the screenshot path as JSON.
- `tools/capture-cardinal-screenshots.sh`: compact four-angle screenshot helper for north/east/south/west visual route debugging.
- `tools/rs-tool.sh`: small bridge wrapper for calling `rs` tools through the active local session without hand-writing `curl` each time.
- `tools/rs-tool_XS.sh`, `tools/observe_XS.sh`, `tools/food_bank_XS.py`, and `tools/object_search_XS.py`: compact bridge wrappers for routine state, food/bank decisions, and object-search recovery.
- `tools/script_registry.py`: lightweight script catalog for listing, wildcard searching, inspecting, and running registered helper scripts by fuzzy name.
- `tools/character_memory.py`: sparse, profile-scoped long-term memories and goals for future agents.
- `tools/agility_runner.py`: bridge-backed agility course runner that keeps obstacle execution and timing evidence out of the AI token loop.
- `tools/mining_runner.py`: bridge-backed mining runner that discovers cache-backed mine clusters, routes between banks and rocks, chooses live ore targets, mines through primitive rock/object loops by default, and banks ores.
- `tools/woodcutting_runner.py`: standalone primitive tree-chopping runner with optional banking and bird-nest pickup.
- `tools/fletching_runner.py`: primitive-first woodcutting and fletching runner. It uses object interaction for chopping, `use_item_on_item`, `click_interface_button`, and `wait_until_idle` for fletching, with legacy fallback for old runtimes.
- `tools/combat_runner.py`: generic primitive combat runner for NPC targets, style selection, eating, waiting, looting, and optional route targets.
- `tools/food_runner.py`: primitive fishing, cooking, fish-cook, and firemaking runner.
- `tools/smithing_runner.py`: primitive smelting/smithing runner using furnace/anvil interactions, interface buttons, and `SmithingData`.
- `tools/bank_loadout.py`: compact primitive bank-loadout helper that plans from observed inventory and applies only needed deposit/food/coin-float actions.
- `tools/agent_session_XS.py`, `tools/runner_status_XS.py`, `tools/catherby_food_runner_XS.py`, and `tools/route_failure_XS.py`: compact readers for session usage, cooperative runner status, Catherby runner control, and route execution recovery.
- `tools/cowhide_combat_runner.py`: bounded cow combat, hide pickup, food restock, and banking runner built from route, combat, item, shop, and bank primitives.
- `tools/render_profile_map.py`, `tools/render_heat_map.py`, `tools/render_fog_map.py`: plain-name active movement map renderers for `Mr. Flame`, `Heat Map`, and `Mr. Flame Fog`.
- `tools/active_map_refresher.py`: background controller for keeping the three canonical active map PNGs current every five minutes: profile movement, `Heat Map`, and profile fog. Use it for `start`, `status`, `logs`, and `restart`.
- `tools/refresh_active_maps.py`: lower-level foreground worker used by `active_map_refresher.py`. It writes status/temp files under ignored `.local/map-refresh/`, JSON summaries under ignored `.local/map-summaries/`, and does not refresh auxiliary cache/route maps unless explicitly requested.

## Unified Movement Telemetry

The primary movement telemetry producer is server-side passive logging. When the server includes `AgentPassiveTraceLog`, each active player emits route-consumable JSONL under:

```text
2006Scape Server/data/logs/player-movement-traces/<yyyy-MM-dd>/<player>.jsonl
```

The passive stream records authoritative post-movement tiles, previous tiles, run state and energy deltas, hitpoint deltas, death/combat flags, inventory food count, interface/activity flags, object clicks, and a normalized `activity` object. It writes movement, teleport, combat, HP-loss, death, object interaction, activity-change, and periodic idle heartbeat events without requiring an AI model or bridge tool request.

Object interaction records use `event: "object_interaction"` with `objectInteractionPhase: "queued"` for the raw click target and `"completed"` for the reached/post-handler state. They include `objectId`, `objectName` when definitions are available, `objectTile`, `option`, `objectOption`, `packetOpcode`, and a compact `object` metadata block. The route graph preserves object metadata on edges and does not infer reverse edges across object-backed transitions.

`tools/navdb.py`, `tools/router.py`, and the movement topology renderers read one unified trace iterator. It prefers the passive player trace stream by default and avoids double-counting bridge batch or fallback polling traces when passive traces exist.

The user-facing active map wrappers are slightly more inclusive for historical context: they backfill agent batch traces recorded before passive player tracing began, preserving early exploration and death sites while still omitting newer duplicated batches.

- passive server player traces in `2006Scape Server/data/logs/player-movement-traces/` are the default source;
- agent batch movement traces in `2006Scape Server/data/logs/agent-movement-traces/` are diagnostics and fallback input;
- optional fallback/dev traces in `agent-navigation/data/movement_traces*.jsonl` are used only when server traces are unavailable or explicitly requested.

Set `NAVDB_INCLUDE_AGENT_BATCH_TRACES=1` or `NAVDB_INCLUDE_LEGACY_RECORDER_TRACES=1` only when deliberately inspecting those secondary streams.
Stationary `event:"state"` idle heartbeat records are also ignored by route/map consumers unless `NAVDB_INCLUDE_IDLE_STATE_TRACES=1` is set for diagnostics.

For multi-character work, set `RS_PROFILE=<name>` or pass `--trace-profile <name>` so route planning and maps use only that profile's trace evidence. Legacy unscoped traces are excluded when a trace profile is active unless `--include-unscoped-traces` is explicitly passed.

The shared schema is `schema/movement_trace.schema.json`. New producers should keep the common fields stable: `schemaVersion`, `timestamp`, `event`, `tile`, `previousTile`, `moved`, `runEnabled`, `runEnergy`, `runEnergySpent`, `hitpoints`, `hitpointsLost`, `isInCombat`, `isDead`, `tool`, `traceId`, and object fields for object interactions.

## Script Registry

Use the registry when you know what you want to do but not the exact helper script name. It searches ids, names, aliases, descriptions, tags, and wildcard patterns without loading broad repo context.

```sh
python3 agent-navigation/tools/script_registry.py list
python3 agent-navigation/tools/script_registry.py search "route*"
python3 agent-navigation/tools/script_registry.py show agility --json
python3 agent-navigation/tools/script_registry.py show mining --json
python3 agent-navigation/tools/script_registry.py run navdb -- validate
```

Keep durable descriptions and examples in `data/script_registry.json` so skills can stay short and point agents to the registry instead of duplicating script docs.

## Scripting Primitives

Use [Agent Scripting Primitives](scripting-primitives.md) before adding or changing Java bridge tools. The bridge should expose stable gameplay inputs such as item-on-item, item-on-object, interface-button clicks, interface-item selection, walking, waiting, object/NPC interaction, combat, banking, shops, and inventory management. Strategy belongs in external Python scripts and JSON data.

Legacy high-level Java tools such as `fletch_logs_until_inventory_empty`, `mine_ore_until_inventory_full`, `chop_tree_until_inventory_full`, `fish_food`, `cook_food`, `light_fire`, `smith_item`, and `train_combat` remain available for compatibility, but new runners should prefer primitive composition. Current primitive-backed runners cover mining, woodcutting/fletching, food, smithing, and combat.

For banking, prefer `tools/bank_loadout.py`, `food_bank_XS.py`, or shared `bridge_script.execute_bank_policy` instead of ad hoc repeated deposit loops. A bank policy should observe inventory once, skip absent items, deposit listed resources/junk in one `deposit_inventory_items_XS` call using `itemIds` for multiple item types, trim food with `keepFoodCount` in one call, and adjust the coin float once. For equipment cleanup, use `unequip_items_XS` rather than looping `unequip_item` across slots.

## Character Memory

Use `tools/character_memory.py` for intentional, sparse, profile-scoped notes that should affect future decisions. This is for things like equipment upgrade goals, recurring blockers, useful preferences, or strategic reminders. It is not for route graph facts, raw telemetry, session transcripts, every level-up, or every inventory batch.

```sh
python3 agent-navigation/tools/character_memory.py show --profile MrFlame --json
python3 agent-navigation/tools/character_memory.py goal --profile MrFlame --priority normal --tags gear --text "Upgrade from a bronze axe when the character has enough coins and shop access."
python3 agent-navigation/tools/character_memory.py remember --profile MrGem --kind warning --tags supplies --text "Carry food before repeating a route that previously caused low-HP recovery."
```

The default profile is `MrFlame`; pass `--profile` or set `RS_PROFILE` for another character. Known display variants such as `Mr. Flame` and `Mr. Gem` normalize to the same profile directories as `MrFlame` and `MrGem`.

## Learning Workflow

1. Observe the game state with `rs.observe_state_XS` or `tools/observe_XS.sh` and note the player tile, nearby NPCs, objects, inventory, run energy, HP, and active interfaces. Use full `rs.observe_state` only when XS omits a field needed for evidence or debugging.

```sh
agent-navigation/tools/observe_XS.sh
agent-navigation/tools/rs-tool_XS.sh observe_state_XS '{}'
RS_PROFILE=MrGem agent-navigation/tools/observe_XS.sh
```
2. Capture or locate screenshots when API state is not enough. Prefer the four-angle helper for route geometry:

```sh
agent-navigation/tools/capture-cardinal-screenshots.sh --prefix blocked-door
```

It captures north/east/south/west client-window PNGs at compact native client size and prints a JSON summary. For a single angle, use the direct capture helper:

```sh
agent-navigation/tools/capture-client-screenshot.sh --prefix blocked-door --native-size
```

The helper focuses the running Java client, captures its window rectangle when possible, and falls back to full-screen capture if macOS cannot report the window. Full-screen fallback may include other desktop content, so use it only for route evidence that needs visual review. The existing client can also save screenshots under `~/2006Scape/screenshots/`; copy either source into this database through `record-observation`.
3. Record the observation with metadata. `--state-json` accepts either a path to a JSON file or a short inline JSON object:

```sh
python3 agent-navigation/tools/navdb.py record-observation \
  --player mrflame \
  --x 3204 --y 3215 --height 0 \
  --place lumbridge_kitchen_approach \
  --route lumbridge_courtyard_to_kitchen_range \
  --screenshot agent-navigation/screenshots/captures/2026-05-24/blocked-door-20260524T042700Z.png \
  --note "Reached kitchen approach but exact range tile still needs a door/object check. Screenshot shows which side of the wall/door the player is standing on."
```

4. Update `data/routes.json` with the learned route step, interaction, or blocker. Use `validate` before relying on it.
5. Query movement before acting. For normal A-to-B route selection, use ML1 first:

```sh
python3 agent-navigation/ml-routing/route_ml.py define --from 3222,3218,0 --to lumbridge_kitchen_range --combat-level 3 --food 2 --run-energy 50 --run-enabled false
```

Use `navdb.py next-step`, `router.py`, and bare `route_runner.py` only for route DB validation and legacy planner diagnostics:

```sh
python3 agent-navigation/tools/navdb.py next-step --from 3222,3218,0 --to lumbridge_kitchen_range --combat-level 3 --food 2 --run-energy 50 --run-enabled false
python3 agent-navigation/tools/navdb.py next-step --trace-profile MrGem --from 3222,3218,0 --to lumbridge_kitchen_range --combat-level 3 --food 2 --run-energy 50 --run-enabled false
python3 agent-navigation/tools/navdb.py hazards --near 3204,3215,0 --radius 20 --combat-level 3 --food 2 --run-energy 50 --run-enabled false
python3 agent-navigation/tools/navdb.py route-risk lumbridge_courtyard_to_al_kharid_bank --combat-level 3 --food 1 --coins 0 --run-energy 50 --run-enabled false
python3 agent-navigation/tools/navdb.py run-areas --query lumbridge
python3 agent-navigation/tools/navdb.py self-test
python3 agent-navigation/tools/navdb.py coverage
```

## Safety Model

Routes should include:

- tile waypoints and the reason each exists;
- required interactions such as doors, gates, stairs, ladders, and dialogue choices;
- risk level and minimum combat/food requirements;
- run policy, including when to enable run and where to conserve energy;
- evidence links to observations and screenshots;
- known blockers and recovery steps.

Do not mark a route `verified` until it has been completed from start to destination using normal gameplay mechanics. Use `learned-partial` or `needs-verification` while the route still depends on assumptions.

## Agility Runner

`tools/agility_runner.py` runs known agility courses through normal bridge tools: it observes the player, walks to each obstacle approach tile, clicks the configured object, waits for the expected post-state, and records compact local evidence.

```sh
python3 agent-navigation/tools/agility_runner.py --course gnome_agility_course --laps 1 --dry-run
python3 agent-navigation/tools/agility_runner.py --course gnome_agility_course --laps 10
python3 agent-navigation/tools/agility_runner.py --course gnome_agility_course --target-agility-level 25 --continue-on-failure
RS_PROFILE=MrGem python3 agent-navigation/tools/agility_runner.py --course gnome_agility_course --laps 10
```

Course definitions are shareable JSON in `data/agility_courses.json`. Run logs and adaptive policy stats are local generated data under `data/agility/` and should stay ignored unless a user explicitly asks to curate a specific artifact.

## Mining Runner

`tools/mining_runner.py` runs normal-gameplay mining loops with route learning and banking. It uses the cache-backed world map to discover ore clusters near known bank places, scores sites by bank distance, current distance, rock density, ore XP, and respawn cost, currently routes through legacy `route_runner.py` compatibility paths, chooses the best currently reachable ore with `find_nearest_rock`, mines through primitive `interact_object` plus `wait_until_idle` rounds, then routes back to a bank and deposits ores. New route work should migrate runners toward ML1 `route_ml.py define` route definitions. Legacy `mine_ore_until_inventory_full` is available only through `--legacy-mining-tool` or stale-runtime fallback. Route batch output includes run diagnostics (`runReq`, `runBefore`, `runAfter`, `runSpent`, `expectedRunSpend`, `tps`, `tilesPerTick`, `runWarn`), and mining logs keep run-policy events plus any non-`none` route warnings. Each mining run also writes a sibling `.routes.jsonl` file with structured route-batch run-efficiency evidence.

```sh
python3 agent-navigation/tools/mining_runner.py --list-sites --ores copper,tin,iron
python3 agent-navigation/tools/mining_runner.py --target-mining-level 20 --auto-buy-bronze-pickaxe
python3 agent-navigation/tools/mining_runner.py --ores iron --max-loads 1 --quiet
python3 agent-navigation/tools/script_registry.py run mining -- --target-mining-level 20 --auto-buy-bronze-pickaxe
```

Use `--list-sites` for read-only site planning. For live training, the runner writes generated JSONL evidence under `data/mining/runs/`, relies on passive movement telemetry for route learning, and keeps bridge tokens hidden behind `tools/rs-tool.sh`.

## Fletching Runner

`tools/fletching_runner.py` runs normal-gameplay woodcutting and fletching loops. It chooses trees and fletching products in Python, currently routes through legacy `route_runner.py` compatibility paths, chops through primitive `find_nearest_tree`/`interact_object`/`wait_until_idle` rounds, picks up and banks bird nests, sells products when configured, and records JSONL evidence under `data/fletching/runs/`. New route work should prefer ML1 route definitions instead of adding more bare Route Runner dependencies.

```sh
python3 agent-navigation/tools/fletching_runner.py --max-cycles 10 --tree auto --quiet
python3 agent-navigation/tools/fletching_runner.py --target-woodcutting-level 50 --target-fletching-level 50 --quiet
python3 agent-navigation/tools/fletching_runner.py --legacy-fletch-tool --legacy-chop-tool --max-cycles 3
```

The default chop/fletch path is primitive-first. It calls `find_nearest_tree` and `interact_object` for logs, `use_item_on_item` for knife-on-logs, `click_interface_button` for the make-all button, and `wait_until_idle` for production. If the live game has not been restarted onto a build with those primitives, the runner falls back to legacy tools unless the corresponding `--no-legacy-*-fallback` flag is passed.

## Primitive Skilling Runners

Use these before adding Java tools for new gameplay loops:

```sh
python3 agent-navigation/tools/woodcutting_runner.py --tree oak --stop-when-inventory-full --quiet
python3 agent-navigation/tools/food_runner.py --mode fish-cook --quiet
python3 agent-navigation/tools/food_runner.py --mode firemake --max-fires 10
python3 agent-navigation/tools/smithing_runner.py --mode smelt --bar bronze --quiet
python3 agent-navigation/tools/smithing_runner.py --mode smith --item sword --amount 10
python3 agent-navigation/tools/combat_runner.py --npc goblin --target-level 10 --quiet
```

`woodcutting_runner.py`, `food_runner.py`, `smithing_runner.py`, and `combat_runner.py` are intentionally script-side strategy. They compose stable bridge primitives such as `interact_npc`, `interact_object`, `use_item_on_object`, `use_item_on_item`, `click_interface_button`, `select_interface_item`, `attack_npc`, `eat_best_food`, and `wait_until_idle`.

## Cowhide Combat Runner

`tools/cowhide_combat_runner.py` keeps early cow combat, hide pickup, kebab restocking, and banking out of the AI loop. It stays local in the Lumbridge cow pen when possible, uses route travel only for real travel legs, and writes ignored generated evidence under `data/combat/runs/`.

```sh
python3 agent-navigation/tools/cowhide_combat_runner.py --stop-when-inventory-full --no-final-bank --quiet
python3 agent-navigation/tools/cowhide_combat_runner.py --target-attack 20 --target-strength 20 --target-defence 5 --max-cycles 25
```
