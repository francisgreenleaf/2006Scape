---
name: 2006scape
description: "Use as the single entry skill for work in /Users/kevin/Documents/2006Scape, especially when a task broadly mentions 2006Scape or the right specialized workflow is unclear. Provides routing guidance, boundaries, starter commands, and child-skill pointers for runtime/bridge sessions, script discovery, route exploration, route-planner/ML graph development, object transitions, frontier exploration, compact screenshots, gameplay progression, profile-scoped character memories/goals, cache maps, map visualization, session logs, bridge-tool development, and general repo editing without preloading every specialized skill body."
---

# 2006Scape

Use this as the umbrella skill for `/Users/kevin/Documents/2006Scape`. Load this first when a task is broadly about 2006Scape or when you are unsure which repo-local skill applies.

## How To Use This Skill

Skill links are routing pointers, not inherited context. Available skills expose their `name`, `description`, and `path`; the full body of a child `SKILL.md` is read only when the agent chooses that child skill. Keep this file useful enough to orient a new agent, then load the smallest relevant child skill before doing specialized work.

Other agents may be editing code or playing the game. Keep work scoped to the user's task, avoid process restarts unless requested, and do not touch runtime/game code when the task is only about skills or docs.

Always keep bridge tokens, API keys, saved-character secrets, passwords, and nonces out of messages, logs, screenshots, and committed files. `MrFlame` is the default local gameplay profile; use `RS_PROFILE=<name>` or `--profile <name>` when the user wants another character.

## Context Budget Rule

For live gameplay and navigation, use the smallest state surface that can support the next decision. Use XXS for confirmation, status, health, position, and stable polling: `observe_XXS.sh`, `rs.observe_state_XXS`, `rs.observe_state_if_changed_XXS`, and `rs-tool_XXS.sh`. Use XS when planning needs compact inventory, equipment, bank, nearby NPC/object, route, or skill context. Use full/legacy tools only for a named missing field, evidence capture, or debugging a new workflow. Do not call full `observe_state`, `observe-slim.sh`, or `rs-tool.sh` in normal loops or immediately after every compact action result just to be safe; treat compact batch/tool results as the next observation whenever they include the state needed for the next decision.

## Skill Router

| Need | Read | Good first move | Boundary |
| --- | --- | --- | --- |
| General repo edits, Java/Maven work, maintenance, tests, code review, or durable lessons | `.codex/skills/2006scape-dev-editing/SKILL.md` | Read `AGENTS.md`; for edits, inspect `references/actionable-lessons.md` when relevant | Do not touch unrelated dirty files or add broad lessons from stale context |
| Starting, stopping, relaunching, diagnosing, or claiming the local server/client/bridge runtime | `.codex/skills/2006scape-local-runtime/SKILL.md` | `python3 agent-navigation/tools/runtime_doctor.py status --observe` | Do not kill/restart active runtimes unless asked or clearly stale; keep profile sessions scoped; never print tokens |
| Adding, debugging, reviewing, or documenting `rs.*` bridge primitives or compatibility tools | `.codex/skills/2006scape-agent-bridge-dev/SKILL.md` | Read `agent-navigation/scripting-primitives.md`, then inspect `AgentActionService`, `AgentToolService`, and `CodexAppServerClient` | Prefer external scripts for strategy; build success is not live proof; restart through `runtime_doctor.py` only when live validation is requested |
| Live route exploration, route DB edits, hazards, blockers, doors, gates, stairs, trapdoors, or topology from navigation data | `.codex/skills/2006scape-route-agent/SKILL.md` | `agent-navigation/tools/observe_XS.sh`, then prefer `route_ml_XS.py define` for A-to-B routing | Use bridge tools only; do not use admin teleports, direct state edits, or visual guesses without evidence |
| Route-planner implementation, graph semantics, `router.py`, `route_runner.py`, passive trace weighting, reverse edges, coordinate targets, ML/GNN route planning, cache-direct candidates, planner evaluation, route-definition API, or route feedback capture | `.codex/skills/2006scape-route-planner-dev/SKILL.md` | `python3 agent-navigation/ml-routing/route_ml_XS.py define --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled` | Keep learned models explainable and constrained by deterministic safety gates; frontier-only routes are not complete benchmark wins |
| Doors, gates, ladders, trapdoors, stairs, ships, portals, tolls, or member gates | `.codex/skills/2006scape-object-transitions/SKILL.md` | Observe XS state, identify object id/tile, preview/walk to interaction target, interact once, then prove post-state; use full state only when a proof field is missing | Do not model object transitions as ordinary walk edges or accept a successful click as proof |
| Live unknown-area expansion, short probes, frontier naming, coordinate targets, and hazard/death evidence | `.codex/skills/2006scape-frontier-exploration/SKILL.md` | `python3 agent-navigation/ml-routing/route_ml_XS.py define --from X,Y,H --to TARGET --combat-level N --food N --run-energy N --run-enabled` | Avoid destination gambling; every probe should produce reusable route, blocker, hazard, or frontier evidence |
| Compact visual debugging of the live Java client | `.codex/skills/2006scape-screenshot-capture/SKILL.md` | `agent-navigation/tools/capture-cardinal-screenshots.sh --prefix reason` | Prefer `765x503` client captures; do not load full desktop screenshots unless compact capture fails |
| Normal gameplay progression through in-game mechanics | `.codex/skills/2006scape-gameplay-progression/SKILL.md` | `agent-navigation/tools/observe_XS.sh`, then search `script_registry.py` for a primitive-backed runner | Not for route DB schema edits, bridge source changes, spawned items, or direct player-state edits |
| Intentional long-term memories, equipment goals, preferences, recurring blockers, or strategic reminders for one character | `.codex/skills/2006scape-character-memory/SKILL.md` | `python3 agent-navigation/tools/character_memory.py show --profile PROFILE --json` | Keep entries sparse and profile-scoped; route facts belong in nav data, routine progress belongs in session logs |
| Discovering or running repo helper scripts by fuzzy name, wildcard, tag, or metadata | `.codex/skills/2006scape-script-registry/SKILL.md` | `python3 agent-navigation/tools/script_registry.py search QUERY` | Keep script descriptions in `agent-navigation/data/script_registry.json`, not in this umbrella skill |
| Static cache-backed world map decoding/rendering, GameCache terrain/water/object/mapscene layers, bounded context maps, or map data export | `.codex/skills/2006scape-cache-map/SKILL.md` | For agent context, use `python3 agent-navigation/tools/render_agent_context_map_XS.py --center latest` | Do not recreate the retired screenshot/minimap fog sampler or require a live client for static map work |
| Map presentation, route overlays, topology styling, labels, legends, visual QA, recent-path/segment context maps, or sharing map images | `.codex/skills/2006scape-map-visualization/SKILL.md` | For agent segment context, use `python3 agent-navigation/tools/render_agent_context_map_XS.py --segment-from FROM_PLACE --segment-to TO_PLACE` | Do not restart gameplay runtime for visual-only work; use `cache-map` for renderer internals |
| Agent session logs, rollout transcript enrichment, Markdown summaries, reports, redaction, or profile/personality artifacts | `.codex/skills/2006scape-agent-session-logs/SKILL.md` | Read targeted `2006Scape Server/data/logs/agent-sessions/...` files and matching `~/.codex/sessions/.../rollout-*.jsonl` | Treat logs as evidence, not controls; do not expose secrets or mutate live gameplay |

## Starter Commands

Run these from the repo root only as orientation. Open the relevant child skill before making changes, restarting processes, or running live gameplay actions. Commands with uppercase placeholders need task-specific values.

```sh
# 2006scape-dev-editing: common validation after repo edits
mvn -q -DskipTests package
mvn -q clean test

# 2006scape-local-runtime: inspect or repair the local runtime/bridge
python3 agent-navigation/tools/runtime_doctor.py status --observe
python3 agent-navigation/tools/runtime_doctor.py status --profile PROFILE --observe
python3 agent-navigation/tools/server_tick_report.py --json
python3 agent-navigation/tools/runtime_doctor.py claim --verify
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify

# 2006scape-agent-bridge-dev: prove bridge tools through the wrapper
agent-navigation/tools/observe_XXS.sh
agent-navigation/tools/observe_XS.sh
RS_PROFILE=PROFILE agent-navigation/tools/observe_XXS.sh
RS_PROFILE=PROFILE agent-navigation/tools/observe_XS.sh
agent-navigation/tools/rs-tool_XS.sh TOOL_NAME 'JSON_ARGS'
agent-navigation/tools/rs-tool_XXS.sh TOOL_NAME 'JSON_ARGS'
agent-navigation/tools/rs-tool_XXS.sh wait_until_combat_event_smart '{"maxTicks":50,"hpAtOrBelow":10}'
agent-navigation/tools/rs-tool_XXS.sh combat_cleanup '{"maxTicks":20}'
agent-navigation/tools/rs-tool_XXS.sh bury_bones '{}'
agent-navigation/tools/rs-tool_XS.sh observe_state_XS '{}'
agent-navigation/tools/rs-tool_XS.sh observe_state_if_changed_XS '{"key":"agent-loop"}'
agent-navigation/tools/rs-tool_XS.sh combat_state_XS '{}'
agent-navigation/tools/rs-tool_XS.sh walk_to_tile_until_arrived_XS '{"x":X,"y":Y,"height":0,"maxTicks":95}'
agent-navigation/tools/rs-tool_XS.sh travel_to_landmark_until_arrived_XS '{"name":"PLACE","maxTicks":95}'
agent-navigation/tools/rs-tool_XS.sh wait_ticks_XS '{"ticks":5}'
agent-navigation/tools/rs-tool_XS.sh wait_until_idle_XS '{"maxTicks":120}'
agent-navigation/tools/rs-tool_XS.sh wait_until_combat_event_smart_XS '{"maxTicks":50,"hpAtOrBelow":10}'
agent-navigation/tools/rs-tool_XS.sh bury_bones_XS '{}'
agent-navigation/tools/rs-tool_XS.sh deposit_inventory_items_XS '{"itemIds":[ID1,ID2],"keepFoodCount":N}'
agent-navigation/tools/rs-tool_XS.sh withdraw_bank_items_XS '{"itemId":ID,"amount":N}'
agent-navigation/tools/rs-tool_XS.sh unequip_items_XS '{"slotNames":["weapon","shield"]}'
python3 agent-navigation/tools/food_bank_XS.py
python3 agent-navigation/tools/object_search_XS.py --name NAME --max-distance 20
# Debug/evidence fallback only; do not use these in normal loops.
agent-navigation/tools/observe-slim.sh
agent-navigation/tools/rs-tool.sh observe_state '{}'
agent-navigation/tools/rs-tool.sh TOOL_NAME 'JSON_ARGS'

# 2006scape-route-agent: observe, route, validate, and render route topology
agent-navigation/tools/observe_XS.sh
python3 agent-navigation/ml-routing/route_ml_XS.py define --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/execute_route_definition.py --route-definition agent-navigation/.local/ml-route-definitions/ROUTE.json --run-mode auto --eat-at 10
python3 agent-navigation/tools/navdb_XS.py validate
python3 agent-navigation/tools/navdb_XS.py self-test
agent-navigation/tools/render_navigation_png.py --region all --output agent-navigation/.local/map-summaries/surface-routes.png

# 2006scape-route-planner-dev: graph planning and planner validation
python3 agent-navigation/ml-routing/route_ml_XS.py define --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/execute_route_definition.py --route-definition agent-navigation/.local/ml-route-definitions/ROUTE.json --run-mode auto --eat-at 10
python3 agent-navigation/ml-routing/route_ml_XS.py route --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled --json
python3 agent-navigation/ml-routing/route_ml_XS.py compare-maps --case CASE_NAME --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/ml-routing/route_ml_XS.py record-outcome --route-id ROUTE_ID --from X,Y,H --to PLACE --status blocked --final X,Y,H --problem-kind enemy_contact --enemy-name NAME --enemy-level N --enemy-tile X,Y,H
python3 agent-navigation/tools/render_agent_context_map_XS.py --center X,Y,H --radius-tiles 72 --pixels-per-tile 5 --recent-seconds 60
python3 agent-navigation/tools/navdb_XS.py graph-summary
python3 agent-navigation/tools/navdb_XS.py trace-tests

# 2006scape-object-transitions: prove object-chain blockers
agent-navigation/tools/rs-tool_XS.sh find_nearest_object '{"name":"gate","maxDistance":20}'
agent-navigation/tools/rs-tool_XS.sh preview_local_path '{"x":X,"y":Y,"height":0,"moveNear":true,"applyBounds":true,"maxWalkDistance":48}'
agent-navigation/tools/rs-tool_XS.sh object_transition_step_XS '{"objectId":OBJECT_ID,"x":X,"y":Y,"option":"first","maxTicks":20}'

# 2006scape-frontier-exploration: probe unknown graph edges
python3 agent-navigation/ml-routing/route_ml_XS.py define --from X,Y,H --to TARGET --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/execute_route_definition.py --route-definition agent-navigation/.local/ml-route-definitions/ROUTE.json --run-mode auto --eat-at 10
agent-navigation/tools/rs-tool_XS.sh walk_to_tile_until_arrived_XS '{"x":X,"y":Y,"height":H,"maxTicks":60,"maxWalkDistance":32,"stopOnStall":true,"stopOnCombat":true}'

# 2006scape-screenshot-capture: compact visual evidence
agent-navigation/tools/capture-cardinal-screenshots.sh --prefix reason
agent-navigation/tools/capture-client-screenshot.sh --prefix reason --native-size

# 2006scape-gameplay-progression: normal gameplay through rs tools
agent-navigation/tools/observe_XS.sh
python3 agent-navigation/tools/script_registry.py search combat
python3 agent-navigation/tools/cowhide_combat_runner.py --status
python3 agent-navigation/tools/cowhide_combat_runner.py --request-stop
python3 agent-navigation/tools/mining_runner.py --target-mining-level 20 --auto-buy-bronze-pickaxe
python3 agent-navigation/tools/combat_runner.py --npc goblin --target-level 10 --quiet
python3 agent-navigation/tools/bank_loadout.py --preset cowhide-trip --dry-run --json
python3 agent-navigation/tools/food_runner.py --mode fish-cook --quiet
python3 agent-navigation/tools/catherby_food_runner.py --cycles 1 --quiet
python3 agent-navigation/tools/catherby_food_runner_XS.py --profile PROFILE
python3 agent-navigation/tools/runner_status_XS.py --profile PROFILE
python3 agent-navigation/tools/catherby_food_runner.py --efficiency-report --quiet
python3 agent-navigation/tools/smithing_runner.py --mode smith --item sword --amount 10
python3 agent-navigation/tools/woodcutting_runner.py --tree oak --stop-when-inventory-full --quiet

# 2006scape-character-memory: sparse profile-scoped memories and goals
python3 agent-navigation/tools/character_memory.py show --profile PROFILE --json
python3 agent-navigation/tools/character_memory.py remember --profile PROFILE --kind resource --priority high --tags equipment --text "A better axe is a useful near-term upgrade before long woodcutting or fletching sessions."
python3 agent-navigation/tools/character_memory.py goal --profile PROFILE --priority normal --tags gear --text "Upgrade from a bronze axe when the character has enough coins and shop access."

# 2006scape-script-registry: discover or run known helper scripts
python3 agent-navigation/tools/script_registry.py list
python3 agent-navigation/tools/script_registry.py search "agility"
python3 agent-navigation/tools/script_registry.py search "mining"
python3 agent-navigation/tools/script_registry.py search "fletching"
python3 agent-navigation/tools/script_registry.py search "woodcutting"
python3 agent-navigation/tools/script_registry.py search "combat"
python3 agent-navigation/tools/script_registry.py search "food"
python3 agent-navigation/tools/script_registry.py search "smithing"
python3 agent-navigation/tools/script_registry.py search "bank"
python3 agent-navigation/tools/script_registry.py search "cowhide"
python3 agent-navigation/tools/script_registry.py search "memory"
python3 agent-navigation/tools/script_registry.py show route --json
python3 agent-navigation/tools/script_registry.py run agility -- --laps 10

# 2006scape-cache-map: static cache-backed map rendering
agent-navigation/tools/cache_world_map.py --bounds 3200,3200,3210,3210 --output /tmp/2006scape-cache-map-smoke.png --summary /tmp/2006scape-cache-map-smoke.json
agent-navigation/tools/cache_world_map.py --bounds all --pixels-per-tile 4 --labels --output agent-navigation/topology/cache-world-map-full.png --summary agent-navigation/.local/map-summaries/cache-world-map-full.json
python3 agent-navigation/tools/map_grid.py locate --tile X,Y,H
python3 agent-navigation/tools/render_agent_context_map_XS.py --center latest
python3 agent-navigation/tools/render_agent_context_map_XS.py --grid-cell AU21 --grid-padding-tiles 4

# 2006scape-map-visualization: canonical map visuals
agent-navigation/tools/render_profile_map.py
agent-navigation/tools/render_heat_map.py
agent-navigation/tools/render_fog_map.py
agent-navigation/tools/active_map_refresher.py status
python3 agent-navigation/tools/render_agent_context_map_XS.py --segment-from FROM_PLACE --segment-to TO_PLACE

# 2006scape-agent-session-logs: inspect logs and summarize event types
python3 agent-navigation/tools/agent_session_XS.py --profile PROFILE --latest
find "2006Scape Server/data/logs/agent-sessions" -type f | sort
sed -n '1,220p' "2006Scape Server/data/logs/agent-sessions/DATE/SESSION.md"
jq -r '.event' "2006Scape Server/data/logs/agent-sessions/DATE/SESSION.jsonl" | sort | uniq -c
```

## Default Starting Points

For read-only questions, inspect the relevant docs or source first and answer without changing files.

For file edits, use `2006scape-dev-editing` plus the subsystem skill. Keep edits away from unrelated dirty files and preserve generated/local-only files.

For live navigation, use XXS/XS tool surfaces by default: XXS for repeated confirmation and survival/status checks, XS for route planning and compact decision context. Main route surfaces are `observe_XXS.sh`, `observe_XS.sh`, dynamic `rs.observe_state_XXS`, dynamic `rs.observe_state_if_changed_XXS`, dynamic `rs.observe_state_XS`, dynamic `rs.observe_state_if_changed_XS`, dynamic `rs.combat_state_XS`, dynamic `rs.walk_path_steps_XS`, dynamic `rs.walk_path_steps_XXS`, dynamic `rs.walk_to_tile_until_arrived_XS`, dynamic `rs.walk_to_tile_until_arrived_XXS`, dynamic `rs.travel_to_landmark_until_arrived_XS`, dynamic `rs.travel_to_landmark_until_arrived_XXS`, dynamic `rs.wait_ticks_XS`, dynamic `rs.wait_ticks_XXS`, dynamic `rs.wait_until_idle_XS`, dynamic `rs.wait_until_idle_XXS`, dynamic `rs.wait_until_combat_event_smart_XS`, dynamic `rs.wait_until_combat_event_smart_XXS`, dynamic `rs.object_transition_step_XS`, dynamic `rs.object_transition_step_XXS`, `rs-tool_XS.sh`, `rs-tool_XXS.sh`, `route_ml_XS.py`, `navdb_XS.py`, `route_failure_XS.py`, and `render_agent_context_map_XS.py`. The full tools remain available only when compact output omits a specific field needed for debugging, evidence capture, or a new workflow. ML1 is the preferred A-to-B routing method for surface routes and same-cache-area underground routes: `route_ml_XS.py define --from X,Y,H --to PLACE_OR_TILE ...`. Use it after `observe_XS` whenever the character needs to travel to a known same-layer place or coordinate target. Treat the returned `2006scape.route-definition` as the routing contract: inspect `status`, `quality`, `evidence`, `safety`, `steps`, `run`, and `runSegments`, then run `cmd`/the persisted route-definition path when live movement is intended. If `status` is `requires-object-transition`, identify the door/ladder/stairs/trapdoor/entrance/gate and use `object_transition_step_XS` or the existing object-transition workflow before requesting the next route on the destination layer or underground area. If `status` is `unsupported-coordinate-layer`, do not execute it; the tile is outside a supported cache route area. `quality` is a geometry/detour signal; if `evidence.proven=true`, trust `safety.review` rather than rejecting a route solely because `quality` is `bad`. That command uses `execute_route_definition.py --route-definition ...`, follows the selected route steps through normal bridge walking primitives, defaults to `--eat-at 10`, observes nearby NPC context on combat/HP loss, and writes route evidence. On movement failure or recovery, read `route_failure_XS.py` before loading full evidence JSONL. The old bare Route Runner method is deprecated for normal agent travel. Do not call `route_runner.py --to ...` as the routing API. Use `navdb_XS.py next-step`, `router.py plan`, `route_eval.py`, and `route_runner_XS.py --orient` only after loading `2006scape-route-planner-dev` for deliberate legacy diagnostics. `define` uses current route/place anchors even when the trained model artifact is older. Context-map JSON includes level-0 grid fields; use `map_grid.py locate --tile X,Y,H` for shorthand such as `AU21` and `render_agent_context_map_XS.py --grid-cell CELL` to request that exact cell. Use compact screenshots only for live visual ambiguity such as gate/door state, wrong-side positioning, object failures, or API/map disagreement.

For live gameplay, observe first and use XXS/XS bridge wrappers. The main dynamic-agent defaults are now `rs.observe_state_XXS`, `rs.observe_state_if_changed_XXS`, `rs.observe_state_XS`, `rs.observe_state_if_changed_XS`, `rs.combat_state_XXS`, `rs.combat_state_XS`, `rs.walk_path_steps_XS`, `rs.walk_to_tile_until_arrived_XS`, `rs.travel_to_landmark_until_arrived_XS`, `rs.wait_ticks_XS`, `rs.wait_until_idle_XS`, `rs.wait_until_combat_event_smart_XS`, `rs.object_transition_step_XS`, `rs.find_nearest_object_XS`, `rs.combat_cleanup_XS`, `rs.bury_bones_XS`, `rs.deposit_inventory_items_XS`, `rs.withdraw_bank_items_XS`, `rs.unequip_items_XS`, `rs.combat_restock_trip_XS`, and `rs.food_bank_XS`; use legacy full tools only when compact output omitted a specific field needed for evidence or debugging. Use XXS aliases such as `rs.set_run_XXS`, `rs.walk_path_steps_XXS`, `rs.wait_until_combat_event_smart_XXS`, `rs.wait_until_idle_XXS`, `rs.object_transition_step_XXS`, `rs.interact_object_XXS`, `rs.click_interface_button_XXS`, `rs.attack_npc_XXS`, `rs.eat_best_food_XXS`, `rs.pickup_ground_item_XXS`, `rs.combat_cleanup_XXS`, `rs.bury_bones_XXS`, `rs.deposit_inventory_items_XXS`, `rs.withdraw_bank_items_XXS`, and `rs.unequip_items_XXS` when the next decision only needs confirmation plus critical survival state: tile, HP/max HP, run energy/enabled, combat, poison, death, free slots, food, and short XP deltas. Full `observe_state`, `observe-slim.sh`, and `rs-tool.sh` are not normal gameplay loop tools. `rs-tool_XXS.sh TOOL ...` appends the `_XXS` suffix automatically for repo-side calls. `skillChanges` reports XP/base/current changes from the current call, and `xpRecent` keeps recent gains for a few minutes; XXS exposes these as a tiny `xp` array. Prayer `points`/`current` are current prayer points while `base` is the true XP-derived Prayer level, so bone burial may show base/XP gains without refilling points. `deposit_inventory_items_XS` accepts `itemIds` to deposit multiple item types at once and `keepFoodCount` to trim excess food safely. `withdraw_bank_items_XS` accepts `itemIds`/`itemId` plus `amount`. `combat_restock_trip_XS` can route to a supplied bank target, deposit non-food loot, trim coins, withdraw food, and optionally return. `unequip_items_XS` accepts `equipmentSlots`, `slotNames`, `itemIds`, `names`/`items`, or `all=true` to unequip several items in one action. Prefer batch tools and treat their returned state as the next observation; during combat, prefer `wait_until_combat_event_smart_XXS` for HP/XP/event checks, `wait_until_combat_event_smart_XS` when loot or target detail matters, and `combat_cleanup_XXS`/`XS` after kills. If a long batch command is already running, wait near the expected completion interval before polling output instead of short-polling every few seconds. For route/mining/fletching movement, request the route through ML1 first and record feedback with `route_ml_XS.py record-outcome` for route-level problems like enemy contact, death, stalls, blockers, bad run policy, or wrong destinations. The fletching runner now routes through `bridge_script.route_to`, which defines ML1 route steps and executes the persisted route definition before continuing primitive gameplay. For Catherby fishing/cooking/banking, prefer `catherby_food_runner.py` or the `catherby-food` registry entry; use `catherby_food_runner_XS.py` or `runner_status_XS.py` for compact status/control. It targets `catherby_fishing_shore`, `catherby_range`, and `catherby_bank`, handles south range-house Door 1530 between deeper range-house tiles and the shore/bank approach area, gates fish-method upgrades by Cooking requirements as well as Fishing unlocks, banks uncookable raw leftovers during recovery, and treats `inBankArea=true`/bank action success as arrival proof rather than chasing old exact bank coordinates. Use its `--efficiency-report --quiet` mode before assuming stale status means idle, because it reads passive server activity traces directly. `catherby_range` is anchored at the pathable cooking tile `2819,3443`; route to `catherby_fishing_shop` for Harry's Fishing Shop and open it with `open_nearest_shop` using name `harry` or `fishing`. Use `food_bank_XS.py` before cooking/banking decisions and `object_search_XS.py` after failed object searches. Legacy Route Runner batch diagnostics such as `runReq`, `runBefore`, `runAfter`, `runSpent`, `expectedRunSpend`, `tps`, `tilesPerTick`, and `runWarn` remain useful when a compatibility executor is deliberately used; treat non-`none` `runWarn` values as evidence that run was requested but not effective. Expect `mining_runner.py` to write a sibling `.routes.jsonl` automatically for its route legs until those runners migrate fully to ML1 execution.

For new gameplay automation, keep strategy in Python scripts and data. Read `agent-navigation/scripting-primitives.md`; use stable primitives such as `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, `interact_object`, `interact_npc`, bank/shop tools, combat tools, and `wait_until_idle` before adding Java. Existing Java skill tools are compatibility surfaces, not the default place for new loops. Current primitive-backed runners cover mining, woodcutting/fletching, food, smithing, combat, and compact bank loadout policies. When a long runner exposes cooperative control, prefer its `--status` and `--request-stop` modes over process inspection or `pkill`; these modes use ignored files under `agent-navigation/.local/runners/` and let the runner stop at a safe boundary.

For long autonomous gameplay or progression, load the selected character's sparse memory with `character_memory.py show --profile PROFILE --json`. Write new memory only for durable, decision-changing goals or lessons; do not log routine progress, temporary route details, secrets, or facts that belong in route data/session logs. Character memory is profile-scoped so `MrFlame` and `MrGem` stay separate.

For visual route ambiguity, use compact screenshots through `agent-navigation/tools/capture-cardinal-screenshots.sh --prefix REASON`; open only the angle(s) needed to answer the question, and do not load oversized full-screen captures.

For runtime management, prefer `agent-navigation/tools/runtime_doctor.py` plus `docs/local-agent-startup.md`, and avoid interrupting active agents unless the user asked for a restart or stop. Use `python3 agent-navigation/tools/server_tick_report.py --json` when the server log is noisy with cycle-duration warnings and you need a compact health summary instead of dumping the raw log.

For maps, use cache-backed tools and keep the retired screenshot/minimap fog collector retired. Agents should use `render_agent_context_map_XS.py` for current-tile, grid-cell, and route-segment context; it draws all cache mapfunction icons in bounds, overlays the level-0 32-tile grid, keeps nearby segment geometry such as docks/ports visible, and writes unique ignored PNG/JSON artifacts under `agent-navigation/.local/context-maps/<date>/` by default. Use the returned JSON path for marker/place/grid labels instead of assuming a stable topology filename, and open the PNG only when visual geometry is needed. Use the full `render_agent_context_map.py` only when the XS output omits a marker/count/path detail needed for debugging. For ML route-quality visuals, use `route_ml_XS.py compare-maps` for compact fast-route reports or full `route_ml.py compare-maps` when you need the full JSON; both reuse the same static context layers and write aggregate reports plus per-case marker sidecars under `agent-navigation/ml-routing/artifacts/comparisons/`. These maps render the selected ML route by default; add `--include-old-planner` only for explicit regression comparisons against the deprecated full planner. The active full movement maps are the profile movement map, `Heat Map`, and profile fog; they are user-facing analysis tools unless the user explicitly asks for them. Cache-map work is static and should not need a live client.

XS/full agent-facing CLI usage is logged out-of-band to ignored JSONL files under `agent-navigation/.local/usage/<yyyy-MM-dd>.jsonl`. XS wrappers mark delegated full-tool calls with `delegatedBy:"xs"` so direct full fallback usage can be counted separately. This log is for later auditing of which fields agents actually use; do not load it into context unless explicitly inspecting tool usage. Set `AGENT_NAV_USAGE_LOG=0` to disable it for a one-off command.

For session logs, start with `agent_session_XS.py --profile PROFILE --latest`; it returns latest session id, top tools, recent outcomes, failures, current player state, and log paths without loading large logs. Load full Markdown/JSONL only when the compact reader omits a needed detail. Summarize observable events from logs and rollout transcripts. Do not invent hidden reasoning; describe decisions through visible messages, tool calls, retries, results, and outcomes.

## Skill Maintenance

If a child skill gains a new primary script, boundary, or repeated workflow, update this entry skill so fresh agents can discover it without preloading every child body. If you notice a missing routing rule, stale pointer, or better workflow, surface it to the user and ask whether to make the skill edit.
