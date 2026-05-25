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
```

Use `observe-slim.sh` or `rs-tool.sh` only when XS omits a field needed for debugging, complete evidence, or a new workflow.

Do not use admin teleports, item spawning, direct player-state edits, raw bridge tokens, screen automation, or game-source changes. Other agents may be active; observe first and treat unexpected state as possibly user-driven.

## First Observation

Start with `observe_XS.sh` for routine state. It keeps compact player, combat, inventory, nearby object/NPC, bank, equipment, and recent XP context while dropping bulky repeated fields. Use full `observe_state` only when you need a missing bank/skill/equipment/interface/profile field, `agentPersonality`, or complete evidence.

Check:

- HP, max HP, combat, death, movement, and active interfaces;
- run energy and run enabled;
- inventory food, tools, coins, free slots, and gear;
- bank access if the player is in a bank area;
- nearby NPC/object risks and current route context.

## Efficient Tool Choices

For new or long gameplay automation, prefer registered external scripts and primitive composition over inventing Java bridge tools. The primitive boundary is documented in `agent-navigation/scripting-primitives.md`; use `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, object/NPC interactions, bank/shop tools, and `wait_until_idle` from Python where possible.

Prefer batch or planner tools over tiny polling loops:

- Movement: `travel_to_landmark_until_arrived`, `walk_to_tile_until_arrived`, then treat the returned state as the next observation.
- Combat: prefer `python3 agent-navigation/tools/combat_runner.py ...` or a more specialized registered runner. In direct `rs` tool recovery, use `set_combat_style`, `find_training_npc`, `attack_npc`, `wait_until_idle '{"combat":true}'`, `eat_best_food`, and `equip_best_items`; `train_combat` and durable combat goals are compatibility fallbacks.
- Durable combat: use `combat_runner.py` with explicit target levels, kill counts, or max actions. `start_combat_goal`, `observe_goal`, and `stop_goal` remain compatibility tools for old runtime sessions only.
- Mining: prefer `python3 agent-navigation/tools/mining_runner.py --target-mining-level N --auto-buy-bronze-pickaxe` for long mining goals because it discovers cache-backed mine sites, routes with `route_runner.py`, chooses live ore targets, mines with primitive `find_nearest_rock`/`interact_object`/`wait_until_idle`, and banks ores. Legacy mining tools are compatibility fallback only.
- Woodcutting/fletching: prefer `python3 agent-navigation/tools/fletching_runner.py ...` for chop/fletch loops or `woodcutting_runner.py` for standalone logs. These use primitive tree interaction and primitive fletching on restarted runtimes, with legacy fallback only for old runtimes.
- Food: prefer `python3 agent-navigation/tools/food_runner.py --mode fish-cook`, `--mode cook`, `--mode fish`, or `--mode firemake`; direct `fish_food`, `light_fire`, and `cook_food` are compatibility fallback only.
- Banking/loadouts: prefer `python3 agent-navigation/tools/bank_loadout.py --preset cowhide-trip --json` for known presets or `bridge_script.execute_bank_policy` inside runners. Do not loop `deposit_inventory_items` for the same item; compute the needed deposits, food trim, and coin float from observed state and execute the compact policy once.
- Shops: travel to a shop, `open_nearest_shop`, then buy/sell through shop tools.
- Smithing: prefer `python3 agent-navigation/tools/smithing_runner.py --mode smelt` or `--mode smith`; it uses furnace/anvil primitives, smelting buttons, interface item selection, and `wait_until_idle`. Java smithing strategy tools are compatibility fallback only.

Use direct single-action tools only for setup, recovery, or a specific user request.

When a long batch command is already running, estimate its completion time from `maxTicks` or the tool's expected loop duration and wait close to that interval before polling terminal output. A 250-tick mining batch can take about 150 seconds; if the expected next material output is 60-90 seconds away, use a long wait instead of polling every few seconds. Short-poll only when combat, death, a blocker, movement uncertainty, or near-term completion is likely.

## Progression Policy

Keep death-risk items minimal. Before training or shopping, bank unnecessary coins with `deposit_excess_coins` and withdraw only what the next purchase or toll requires.

Combat should respect the planner. Stop or restock if food runs out, HP approaches the retreat threshold, combat starts unexpectedly, or a high-level/aggressive NPC enters the decision.

Mining, smithing, woodcutting, fishing, and cooking should be inventory-aware. A full pack is a blocker unless the next action is banking, selling, cooking, dropping by explicit request, or using resources.

Let `agentPersonality` gently guide preparation and risk choices when present, but never let it override the user's command.

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
