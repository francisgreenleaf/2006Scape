---
name: 2006scape-gameplay-progression
description: "Use when controlling the selected 2006Scape profile through normal gameplay for combat, food, banking, shops, smithing, mining, woodcutting, fishing, cooking, durable combat goals, gear upgrades, money-making, or character-growth automation through rs tools and agent-navigation/tools/rs-tool.sh. Use for progression tasks rather than route database editing or bridge development."
---

# 2006Scape Gameplay Progression

Use this skill for in-game character growth with normal mechanics. Pair it with `2006scape-route-agent` for route learning and with `2006scape-local-runtime` if the bridge session itself is broken.

## Ground Rules

Use only repo-side bridge tools:

```sh
agent-navigation/tools/observe-slim.sh
RS_PROFILE=MrGem agent-navigation/tools/observe-slim.sh
agent-navigation/tools/rs-tool.sh <tool> '<json-args>'
```

Do not use admin teleports, item spawning, direct player-state edits, raw bridge tokens, screen automation, or game-source changes. Other agents may be active; observe first and treat unexpected state as possibly user-driven.

## First Observation

Start with `observe-slim` for routine state. Use full `observe_state` only when you need bank, skills, equipment, interfaces, `agentPersonality`, nearby objects, or detailed combat readiness.

Check:

- HP, max HP, combat, death, movement, and active interfaces;
- run energy and run enabled;
- inventory food, tools, coins, free slots, and gear;
- bank access if the player is in a bank area;
- nearby NPC/object risks and current route context.

## Efficient Tool Choices

Prefer batch or planner tools over tiny polling loops:

- Movement: `travel_to_landmark_until_arrived`, `walk_to_tile_until_arrived`, then treat the returned state as the next observation.
- Combat: `plan_combat_training`, `train_combat`, `wait_until_idle '{"combat":true}'`, `eat_best_food`, `equip_best_items`.
- Durable combat: `start_combat_goal`, `observe_goal`, `stop_goal` for long grinds that should continue after the turn.
- Mining: prefer `python3 agent-navigation/tools/mining_runner.py --target-mining-level N --auto-buy-bronze-pickaxe` for long mining goals because it discovers cache-backed mine sites, routes with `route_runner.py`, chooses live ore targets, mines with `mine_ore_until_inventory_full`, and banks ores. Use direct `mine_ore_until_inventory_full` for short local batches.
- Woodcutting: `chop_tree_until_inventory_full`; bank logs unless the user explicitly asks to drop them.
- Food: `fish_food`, `light_fire`, `cook_food`, and bank/carry cooked food as supplies.
- Shops: travel to a shop, `open_nearest_shop`, then buy/sell through shop tools.
- Smithing profit: `plan_smithing`, `train_smithing_profit`, and `wait_until_idle` when smelting or smithing starts.

Use direct single-action tools only for setup, recovery, or a specific user request.

## Progression Policy

Keep death-risk items minimal. Before training or shopping, bank unnecessary coins with `deposit_excess_coins` and withdraw only what the next purchase or toll requires.

Combat should respect the planner. Stop or restock if food runs out, HP approaches the retreat threshold, combat starts unexpectedly, or a high-level/aggressive NPC enters the decision.

Mining, smithing, woodcutting, fishing, and cooking should be inventory-aware. A full pack is a blocker unless the next action is banking, selling, cooking, dropping by explicit request, or using resources.

Let `agentPersonality` gently guide preparation and risk choices when present, but never let it override the user's command.

## Reporting

During long server-side actions, report only material progress, blockers, death, safety changes, or completed goals. Do not narrate every tick.

Final responses should state:

- where the player ended;
- levels, items, coins, food, or gear materially changed;
- whether the goal is complete, still running, or blocked;
- any concrete blocker such as missing tool, no food, no inventory space, unreachable bank/shop/object, insufficient level, active combat, or death.

## Skill Maintenance

If you discover a better progression loop, safer tool sequence, durable-goal pattern, or recurring blocker while using this skill, surface it to the user and ask whether to make the skill edit.
