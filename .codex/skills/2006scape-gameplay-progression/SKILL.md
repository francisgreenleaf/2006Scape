---
name: 2006scape-gameplay-progression
description: "Use when controlling the selected 2006Scape profile through normal gameplay for combat, food, banking, shops, smithing, mining, woodcutting, fishing, cooking, durable combat goals, gear upgrades, money-making, or character-growth automation through rs tools and agent-navigation/tools/rs-tool_XS.sh. Use for progression tasks rather than route database editing or bridge development."
---

# 2006Scape Gameplay Progression

Use this skill for in-game character growth with normal mechanics. Pair it with `2006scape-route-agent` for route learning, `2006scape-character-memory` for sparse long-term profile goals, and `2006scape-local-runtime` if the bridge session itself is broken.

## Ground Rules

Use only repo-side bridge tools:

```sh
agent-navigation/tools/observe_XS.sh
RS_PROFILE=MrGem agent-navigation/tools/observe_XS.sh
agent-navigation/tools/rs-tool_XS.sh <tool> '<json-args>'
agent-navigation/tools/rs-tool_XS.sh observe_state_XS '{}'
agent-navigation/tools/rs-tool_XS.sh deposit_inventory_items_XS '{"itemIds":[ID1,ID2],"keepFoodCount":N}'
agent-navigation/tools/rs-tool_XS.sh unequip_items_XS '{"slotNames":["weapon","shield"]}'
python3 agent-navigation/tools/food_bank_XS.py
```

Use `observe-slim.sh` or `rs-tool.sh` only when XS omits a field needed for debugging, complete evidence, or a new workflow.

Do not use admin teleports, item spawning, direct player-state edits, raw bridge tokens, screen automation, or game-source changes. Other agents may be active; observe first and treat unexpected state as possibly user-driven.

## First Observation

Start with `observe_XS.sh` for repo-side turns or `rs.observe_state_XS` for dynamic main-agent turns. Both keep compact player, combat, inventory, nearby object/NPC, bank, equipment, and XP/skill context while dropping bulky repeated fields. Use full `observe_state` only when you need a missing bank/skill/equipment/interface/profile field, `agentPersonality`, or complete evidence.

Check:

- HP, max HP, combat, death, movement, and active interfaces;
- run energy and run enabled;
- inventory food, tools, coins, free slots, and gear;
- bank access if the player is in a bank area;
- nearby NPC/object risks and current route context.

## Efficient Tool Choices

For new or long gameplay automation, prefer registered external scripts and primitive composition over inventing Java bridge tools. The primitive boundary is documented in `agent-navigation/scripting-primitives.md`; use `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, object/NPC interactions, bank/shop tools, and `wait_until_idle_XS` from Python where possible.

Prefer batch or planner tools over tiny polling loops:

- Movement: `walk_to_tile_until_arrived_XS` or `travel_to_landmark_until_arrived_XS` for dynamic turns, or `rs-tool_XS.sh walk_to_tile_until_arrived_XS ...` / `rs-tool_XS.sh travel_to_landmark_until_arrived_XS ...` for repo-side turns, then treat the returned compact state as the next observation. Use full movement tools only when compact output omits a field needed for route evidence.
- Combat: prefer `python3 agent-navigation/tools/combat_runner.py ...` or a more specialized registered runner. In direct `rs` tool recovery, use `set_combat_style`, `find_training_npc`, `attack_npc`, `wait_until_idle '{"combat":true}'`, `eat_best_food`, and `equip_best_items`; `train_combat` and durable combat goals are compatibility fallbacks.
- Durable combat: use `combat_runner.py` with explicit target levels, kill counts, or max actions. `start_combat_goal`, `observe_goal`, and `stop_goal` remain compatibility tools for old runtime sessions only.
- Cowhide combat: if `cowhide_combat_runner.py` is already running, check `python3 agent-navigation/tools/cowhide_combat_runner.py --status` first. To pause it, use `python3 agent-navigation/tools/cowhide_combat_runner.py --request-stop` so it stops at a safe non-combat boundary; do not use process kills unless the runner is wedged and the user has asked for interruption.
- Mining: prefer `python3 agent-navigation/tools/mining_runner.py --target-mining-level N --auto-buy-bronze-pickaxe` for long mining goals because it discovers cache-backed mine sites, chooses live ore targets, mines with primitive `find_nearest_rock`/`interact_object`/`wait_until_idle`, and banks ores. Its route legs currently use legacy Route Runner compatibility paths; new route work should migrate those legs toward ML1 `route_ml_XS.py define`. Legacy mining tools are compatibility fallback only.
- Woodcutting/fletching: prefer `python3 agent-navigation/tools/fletching_runner.py ...` for chop/fletch loops or `woodcutting_runner.py` for standalone logs. The fletching runner uses ML1 route definitions through `bridge_script.route_to` for travel, executes persisted route steps with normal bridge movement, and uses primitive tree interaction plus primitive fletching on restarted runtimes, with legacy fallback only for old runtimes.
- Food: use `rs.food_bank_XS` or `python3 agent-navigation/tools/food_bank_XS.py` before cooking/fishing/banking decisions when a full observation would mostly be bank/inventory noise. For Catherby fish/cook/bank loops, prefer `python3 agent-navigation/tools/catherby_food_runner.py --cycles 1 --quiet` or `script_registry.py run catherby-food -- ...`. It uses ML1 place targets (`catherby_fishing_shore`, `catherby_range`, `catherby_bank`), opens the Catherby south range-house door when needed, reacquires live fishing spots, gates method upgrades by both Fishing and Cooking requirements, drops burnt fish, banks cooked fish with one compact bank policy, and banks uncookable raw leftovers during recovery. Use `python3 agent-navigation/tools/catherby_food_runner_XS.py --profile PROFILE` or `python3 agent-navigation/tools/runner_status_XS.py --profile PROFILE` for combined cooperative state and passive-trace active/idle time before assuming the player is stuck; long productive fishing waits can leave the status timestamp older than a minute by design. For fishing supplies, route to `catherby_fishing_shop` and use `open_nearest_shop` with name `harry` or `fishing`. For other food loops, prefer `python3 agent-navigation/tools/food_runner.py --mode fish-cook`, `--mode cook`, `--mode fish`, or `--mode firemake`; direct `fish_food`, `light_fire`, and `cook_food` are compatibility fallback only.
- Banking/loadouts: prefer `python3 agent-navigation/tools/bank_loadout.py --preset cowhide-trip --json` for known presets or `bridge_script.execute_bank_policy` inside runners. Do not loop deposits one item type at a time. `deposit_inventory_items_XS` accepts `itemIds` for multiple item types in one call and `keepFoodCount` when preserving carried food; compute the needed deposits, food trim, and coin float from observed state and execute the compact policy once.
- Equipment cleanup: use `unequip_items_XS` when removing multiple equipped items. It accepts `equipmentSlots`, `slotNames`, `itemIds`, `names`/`items`, or `all=true`; use legacy `unequip_item` only as a full-output fallback.
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
