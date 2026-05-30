---
name: 2006scape-gameplay-progression
description: "Use when controlling the selected 2006Scape profile through normal gameplay for combat, food, banking, shops, smithing, mining, woodcutting, fishing, cooking, durable combat goals, gear upgrades, money-making, or character-growth automation through rs tools and agent-navigation/tools/rs-tool_XS.sh. Use for progression tasks rather than route database editing or bridge development."
---

# 2006Scape Gameplay Progression

Use this skill for in-game character growth with normal mechanics. Pair it with `2006scape-route-agent` for route learning, `2006scape-character-memory` for sparse long-term profile goals, and `2006scape-local-runtime` if the bridge session itself is broken.

## Ground Rules

Use only repo-side bridge tools:

```sh
agent-navigation/tools/observe_XXS.sh
agent-navigation/tools/observe_XS.sh
RS_PROFILE=MrGem agent-navigation/tools/observe_XXS.sh
RS_PROFILE=MrGem agent-navigation/tools/observe_XS.sh
agent-navigation/tools/rs-tool_XS.sh <tool> '<json-args>'
agent-navigation/tools/rs-tool_XXS.sh <tool-or-tool_XXS> '<json-args>'
agent-navigation/tools/rs-tool_XS.sh observe_state_XS '{}'
agent-navigation/tools/rs-tool_XS.sh observe_state_if_changed_XS '{"key":"progression-loop"}'
agent-navigation/tools/rs-tool_XS.sh combat_state_XS '{}'
agent-navigation/tools/rs-tool_XXS.sh wait_until_combat_event_smart '{"maxTicks":50,"hpAtOrBelow":10}'
agent-navigation/tools/rs-tool_XS.sh wait_until_combat_event_smart_XS '{"maxTicks":50,"hpAtOrBelow":10}'
agent-navigation/tools/rs-tool_XXS.sh combat_cleanup '{"maxTicks":20}'
agent-navigation/tools/rs-tool_XXS.sh bury_bones '{}'
agent-navigation/tools/rs-tool_XS.sh bury_bones_XS '{}'
agent-navigation/tools/rs-tool_XS.sh deposit_inventory_items_XS '{"itemIds":[ID1,ID2],"keepFoodCount":N}'
agent-navigation/tools/rs-tool_XS.sh unequip_items_XS '{"slotNames":["weapon","shield"]}'
python3 agent-navigation/tools/food_bank_XS.py
```

Default order is XXS, then XS, then full. Use XXS for confirmation, health, position, survival, event, and stable status polls. Use XS when the next decision needs compact inventory, equipment, bank, nearby NPC/object, route, or skill context. Use `observe-slim.sh`, full `observe_state`, or `rs-tool.sh` only when compact output omits a named field needed for debugging, complete evidence, or a new workflow. Do not call full state in loops or immediately after every compact action result just to refresh; treat compact batch/tool results as the next observation when they contain the needed state.

Do not use admin teleports, item spawning, direct player-state edits, raw bridge tokens, screen automation, or game-source changes. Other agents may be active; observe first and treat unexpected state as possibly user-driven.

## First Observation

For a fresh planning turn, start with `observe_XS.sh` for repo-side turns or `rs.observe_state_XS` for dynamic main-agent turns. Both keep compact player, combat, inventory, nearby object/NPC, bank, equipment, and XP/skill context while dropping bulky repeated fields. For heartbeat checks, post-action confirmation, or stable polling after known context, start smaller with `observe_XXS.sh`, `rs.observe_state_XXS`, `rs.observe_state_if_changed_XXS`, or `rs.combat_state_XXS`; these are enough when tile, HP, run energy, combat, poison, death, free slots, food, and recent XP answer the next question. Use `observe_state_if_changed_XS` when repeated polling still needs compact decision context. Use full `observe_state` only when you can name the missing bank/skill/equipment/interface/profile field, `agentPersonality`, or complete evidence requirement.

Check:

- HP, max HP, combat, death, movement, and active interfaces;
- run energy and run enabled;
- inventory food, tools, coins, free slots, and gear;
- bank access if the player is in a bank area;
- nearby NPC/object risks and current route context.

## Efficient Tool Choices

For new or long gameplay automation, prefer registered external scripts and primitive composition over inventing Java bridge tools. The primitive boundary is documented in `agent-navigation/scripting-primitives.md`; use compact aliases for `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, object/NPC interactions, bank/shop tools, `wait_until_combat_event_smart_XXS`/`XS`, `combat_cleanup_XXS`/`XS`, and `wait_until_idle_XXS`/`XS` from Python where possible.

Prefer batch or planner tools over tiny polling loops:

- Movement: `walk_to_tile_until_arrived_XS` or `travel_to_landmark_until_arrived_XS` for dynamic turns, or `rs-tool_XS.sh walk_to_tile_until_arrived_XS ...` / `rs-tool_XS.sh travel_to_landmark_until_arrived_XS ...` for repo-side turns, then treat the returned compact state as the next observation. Use `_XXS` variants when only arrival/blocker status plus critical player state is needed. Use `walk_path_steps_XS` / `_XXS` for short adjacent path queues and `object_transition_step_XS` / `_XXS` for doors, gates, stairs, ladders, and trapdoors where one click plus idle wait is enough. Use full movement/object tools only when compact output omits a field needed for route evidence.
- Combat: prefer `python3 agent-navigation/tools/combat_runner.py ...` or a more specialized registered runner. In direct `rs` tool recovery, use `combat_state_XS`, `set_combat_style_XXS`, `find_training_npc`, `attack_npc_XXS`, `wait_until_combat_event_smart_XXS` for HP/XP/event confirmation, `wait_until_combat_event_smart_XS` when loot or target details matter, `eat_best_food_XXS`, `combat_cleanup_XXS` after kills, `combat_cleanup_XS` when loot context matters, and `equip_best_items_XS`; `wait_until_combat_event_XS`, `wait_until_idle '{"combat":true}'`, `train_combat`, and durable combat goals are compatibility fallbacks.
- Durable combat: use `combat_runner.py` with explicit target levels, kill counts, or max actions. `start_combat_goal`, `observe_goal`, and `stop_goal` remain compatibility tools for old runtime sessions only.
- Cowhide combat: if `cowhide_combat_runner.py` is already running, check `python3 agent-navigation/tools/cowhide_combat_runner.py --status` first. To pause it, use `python3 agent-navigation/tools/cowhide_combat_runner.py --request-stop` so it stops at a safe non-combat boundary; do not use process kills unless the runner is wedged and the user has asked for interruption.
- Mining: prefer `python3 agent-navigation/tools/mining_runner.py --target-mining-level N --auto-buy-bronze-pickaxe` for long mining goals because it discovers cache-backed mine sites, chooses live ore targets, mines with primitive `find_nearest_rock`/`interact_object`/`wait_until_idle`, and banks ores. Its route legs currently use legacy Route Runner compatibility paths; new route work should migrate those legs toward ML1 `route_ml_XS.py define`. Legacy mining tools are compatibility fallback only.
- Woodcutting/fletching: prefer `python3 agent-navigation/tools/fletching_runner.py ...` for chop/fletch loops or `woodcutting_runner.py` for standalone logs. The fletching runner uses ML1 route definitions through `bridge_script.route_to` for travel, executes persisted route steps with normal bridge movement, and uses primitive tree interaction plus primitive fletching on restarted runtimes, with legacy fallback only for old runtimes.
- Food: use `rs.food_bank_XS` or `python3 agent-navigation/tools/food_bank_XS.py` before cooking/fishing/banking decisions when a full observation would mostly be bank/inventory noise. For Catherby fish/cook/bank loops, prefer `python3 agent-navigation/tools/catherby_food_runner.py --cycles 1 --quiet` or `script_registry.py run catherby-food -- ...`. It uses ML1 place targets (`catherby_fishing_shore`, `catherby_range`, `catherby_bank`), opens the Catherby south range-house door when needed, reacquires live fishing spots, gates method upgrades by both Fishing and Cooking requirements, drops burnt fish, banks cooked fish with one compact bank policy, and banks uncookable raw leftovers during recovery. Use `python3 agent-navigation/tools/catherby_food_runner_XS.py --profile PROFILE` or `python3 agent-navigation/tools/runner_status_XS.py --profile PROFILE` for combined cooperative state and passive-trace active/idle time before assuming the player is stuck; long productive fishing waits can leave the status timestamp older than a minute by design. For fishing supplies, route to `catherby_fishing_shop` and use `open_nearest_shop` with name `harry` or `fishing`. For other food loops, prefer `python3 agent-navigation/tools/food_runner.py --mode fish-cook`, `--mode cook`, `--mode fish`, or `--mode firemake`; direct `fish_food`, `light_fire`, and `cook_food` are compatibility fallback only.
- Banking/loadouts: prefer `python3 agent-navigation/tools/bank_loadout.py --preset cowhide-trip --json` for known presets or `bridge_script.execute_bank_policy` inside runners. Do not loop deposits one item type at a time. `deposit_inventory_items_XS` accepts `itemIds` for multiple item types in one call and `keepFoodCount` when preserving carried food; `withdraw_bank_items_XS` accepts `itemIds`/`itemId` plus `amount`; `combat_restock_trip_XS` can route to a supplied bank target, deposit non-food loot, trim coins, withdraw food, and optionally return. Use XXS variants only when the counts are already known and confirmation plus critical player state is enough.
- Equipment cleanup: use `unequip_items_XS` when removing multiple equipped items. It accepts `equipmentSlots`, `slotNames`, `itemIds`, `names`/`items`, or `all=true`; use `unequip_items_XXS` for confirmation-only cleanup and legacy `unequip_item` only as a full-output fallback.
- Shops: travel to a shop, `open_nearest_shop`, then buy/sell through shop tools.
- Smithing: prefer `python3 agent-navigation/tools/smithing_runner.py --mode smelt` or `--mode smith`; it uses furnace/anvil primitives, smelting buttons, interface item selection, and `wait_until_idle`. Java smithing strategy tools are compatibility fallback only.

Use direct single-action tools only for setup, recovery, or a specific user request.

When a long batch command is already running, estimate its completion time from `maxTicks` or the tool's expected loop duration and wait close to that interval before polling terminal output. A 250-tick mining batch can take about 150 seconds; if the expected next material output is 60-90 seconds away, use a long wait instead of polling every few seconds. Short-poll only when combat, death, a blocker, movement uncertainty, or near-term completion is likely.

## Progression Policy

Keep death-risk items minimal. Before training or shopping, bank unnecessary coins with `deposit_excess_coins` and withdraw only what the next purchase or toll requires.

Combat should respect the planner. Stop or restock if food runs out, HP approaches the retreat threshold, combat starts unexpectedly, or a high-level/aggressive NPC enters the decision.

Mining, smithing, woodcutting, fishing, and cooking should be inventory-aware. A full pack is a blocker unless the next action is banking, selling, cooking, dropping by explicit request, or using resources.

Use `agentPersonality` only as operational memory for preparation and risk choices when present. Do not quote it, roleplay it, or let it override the user's command.

For long progression work, read intentional character memory before planning:

```sh
python3 agent-navigation/tools/character_memory.py show --profile PROFILE --json
```

Write memory only for durable facts a future agent should consider, such as equipment upgrades, useful supply habits, recurring blockers, or user preferences. Do not record every level, trip, inventory, or batch result.

## Reporting

During long server-side actions, report only material progress, blockers, death, safety changes, or completed goals. Do not narrate every tick.

Final responses should state:

- where the player ended;
- levels, items, coins, food, or gear materially changed;
- whether the goal is complete, still running, or blocked;
- any concrete blocker such as missing tool, no food, no inventory space, unreachable bank/shop/object, insufficient level, active combat, or death.

## Skill Maintenance

If you discover a better progression loop, safer tool sequence, durable-goal pattern, or recurring blocker while using this skill, surface it to the user and ask whether to make the skill edit.
