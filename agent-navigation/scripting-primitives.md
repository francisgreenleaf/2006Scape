# Agent Scripting Primitives

This repo now treats Java bridge tools as a stable control surface and external
Python scripts as the place for gameplay strategy. Do not add a new Java
`rs.*` tool for every skill loop. Add Java only when the bridge is missing a
general gameplay primitive.

## Stable Java Primitives

Use these from external scripts through `agent-navigation/tools/rs-tool.sh`, prefer `rs-tool_XS.sh` or the dynamic `*_XS` aliases when compact decision context is enough, and use `rs-tool_XXS.sh` / dynamic `*_XXS` aliases when confirmation plus critical survival state is enough:

- Observation and waiting: `observe_state`, `observe_state_XS`,
  `observe_state_XXS`, `observe_state_if_changed_XS`,
  `observe_state_if_changed_XXS`, `combat_state_XS`, `combat_state_XXS`,
  `wait_ticks`, `wait_ticks_XXS`, `wait_until_idle`,
  `wait_until_idle_XS`, `wait_until_idle_XXS`,
  `wait_until_combat_event_smart_XS`, `wait_until_combat_event_smart_XXS`,
  `wait_until_combat_event_XS`, `wait_until_combat_event_XXS`
- Movement and routing support: `set_run`, `set_run_XXS`, `preview_local_path`, `walk_to_tile`,
  `walk_path_steps`, `walk_path_steps_XS`, `walk_path_steps_XXS`,
  `walk_to_tile_until_arrived`, `travel_to_landmark`,
  `travel_to_landmark_until_arrived`, `object_transition_step_XS`,
  `object_transition_step_XXS`
- Game interactions: `interact_object`, `interact_object_XS`,
  `interact_object_XXS`, `interact_npc`, `attack_npc`,
  `attack_npc_XXS`,
  `continue_dialogue`, `select_dialogue_option`, `close_interfaces`
- Item and UI primitives: `use_item_on_item`, `use_item_on_object`,
  `click_interface_button`, `click_interface_button_XXS`, `select_interface_item`
- Inventory/equipment/economy primitives: `equip_item`, `unequip_item`,
  `unequip_items_XS`, `unequip_items_XXS`,
  `equip_best_items`, `equip_best_items_XS`, `equip_best_items_XXS`,
  `eat_item`, `eat_best_food`, `eat_best_food_XXS`, `pickup_ground_item`,
  `pickup_ground_item_XXS`, `combat_cleanup_XS`, `combat_cleanup_XXS`,
  `bury_bones`, `bury_bones_XS`, `bury_bones_XXS`, `drop_inventory_items`, `deposit_inventory_items`, `deposit_inventory_items_XS`, `deposit_inventory_items_XXS`,
  `withdraw_bank_items`, `withdraw_bank_items_XS`, `withdraw_bank_items_XXS`,
  `combat_restock_trip_XS`, `combat_restock_trip_XXS`,
  `open_nearest_shop`, `buy_shop_item`, `sell_inventory_item`,
  `sell_inventory_items`, `deposit_excess_coins`

The main compact dynamic surfaces are `observe_state_XS`,
`observe_state_if_changed_XS`, `combat_state_XS`, `walk_path_steps_XS`,
`walk_to_tile_until_arrived_XS`, `travel_to_landmark_until_arrived_XS`,
`wait_ticks_XS`, `wait_until_idle_XS`, `wait_until_combat_event_smart_XS`,
`wait_until_combat_event_XS`, `object_transition_step_XS`,
`interact_object_XS`, `find_nearest_object_XS`, `combat_cleanup_XS`,
`bury_bones_XS`, `deposit_inventory_items_XS`, `withdraw_bank_items_XS`,
`unequip_items_XS`, `combat_restock_trip_XS`, and `food_bank_XS`.
They use the same mechanics as their
full counterparts and return smaller status/player/inventory summaries. Use
full tools only for missing debug fields or complete evidence capture.

The XXS aliases use the same mechanics again but reduce the result to
confirmation/status, critical player state (`tile`, `hp`, `maxHp`,
`runEnergy`, `runEnabled`, `isInCombat`, `isPoisoned`, `isDead`,
`freeInventorySlots`, `food`), and tiny XP deltas. Prefer them for tight confirmation loops after an action when
inventory, bank, nearby objects/NPCs, route evidence, or loot detail is not
needed. `rs-tool_XXS.sh bury_bones '{}'` automatically calls
`bury_bones_XXS`; passing a name that already ends in `_XXS` is also accepted.

XP-producing tool calls add `skillChanges` when a skill changed during the
call, and compact results carry `xpRecent` for recent gains in the last few
minutes. For Prayer, read `points`/`current` as the current prayer points and
`base` as the actual Prayer level from XP; burying bones raises XP/base but
does not refill current points.

The item/UI primitives are the key abstraction for new skilling scripts. For
example, fletching should use a knife on logs with `use_item_on_item`, click the
make-all button with `click_interface_button`, and wait through
`wait_until_idle`. The choice of logs, products, targets, banking, selling, and
retry policy belongs in Python or JSON data.

For cooking, use a raw cookable item on a cooking object with
`use_item_on_object`, click the make-all cooking button with
`click_interface_button`, then wait through `wait_until_idle`. On current source
builds, the bridge primitive opens the normal Cooking interface itself for raw
cookable items used on known cooking objects, so scripts should not need to
fall back to the legacy `cook_food` tool except on stale runtimes or failures.

Use `walk_path_steps` only for short adjacent client-style step queues. It
enforces clipping by default; pass `allowObjectTransition=true` only directly
after an object proof such as an opened gate where the server-side pathfinder
cannot see the temporary opening yet.

For dynamic agents and restarted runtimes, prefer `object_transition_step_XS`
or `_XXS` for single object transitions where the only required follow-up is
waiting until movement/skilling clears. It performs the same `interact_object`
click, records transition evidence, waits for idle, and returns compact phase
status. Use full `interact_object` plus explicit route proof only when the
compact result omits needed side, object, or evidence detail.

For combat loops, prefer `wait_until_combat_event_smart_XXS` when HP/XP/event
status is enough and `wait_until_combat_event_smart_XS` when target or loot
detail matters. After a kill, prefer `combat_cleanup_XXS` or `_XS` to bury
bones, pick up whitelisted useful drops, optionally equip upgrades, and return
counts without a full observe. For bank-food refreshes, `combat_restock_trip_XS`
or `_XXS` can route to a supplied bank target, deposit non-food loot, trim
coins, withdraw food, and optionally route back.

For repeat object/dialogue transitions, put the learned sequence in
`bridge_script.py` instead of copying it into each runner. The current reusable
example is `bridge_script.cross_al_kharid_toll_gate(...)`: route close to the
gate, stand on the exact side tile (`3267,3227,0` eastbound or `3268,3227,0`
westbound), discover the live Gate object, open it, step through the toll
dialogue, and prove the post-side before returning control. Keep these helpers
small and evidence-backed; do not automatically generalize one gate's behavior
to unrelated gates.

The Falador/Taverley White Wolf Mountain gate has an MVP helper:
`bridge_script.cross_taverley_white_wolf_gate(...)`. It stands at
`2936,3451,0` when crossing west, opens Gate `1596`/`1597` around
`2935,3451,0`, immediately queues adjacent steps through the gate with
`allowObjectTransition=true`, and proves the side changed. Use it before the
White Wolf Mountain high combat-contact segment; do not model the gate as a
normal walk edge.

For ordinary timed doors, use the generic
`bridge_script.open_object_then_walk_steps(...)` building block from a
location-specific helper. The Catherby southern range door proof starts at
`2817,3439,0`, opens Door `1530` at `2816,3438,0`, then uses the southern
range from `2817,3443,0` against Range `2728` at `2817,3444,0`. Keep exact approach and proof coordinates in the
location helper instead of assuming every door swings the same way.

For ML1 route definitions, prefer
`agent-navigation/tools/execute_route_definition.py --route-definition PATH`
over one-off inline Python. It follows the persisted `routeSteps` through
normal bridge walking primitives, eats before the next step at a configurable
HP threshold, captures nearby NPC context on combat/HP loss, and writes route
evidence for the next ML export.

## Bank Loadout Policies

Use `bridge_script.execute_bank_policy` or `bank_loadout.py` for repeatable bank
cleanup. A bank policy reads observed inventory/bank state first, skips items
that are not present, then executes only the needed primitive calls: one
`deposit_inventory_items` or `deposit_inventory_items_XS` call for listed
junk/resources using `itemIds` for multiple item types, one
`deposit_inventory_items` call with `keepFoodCount` for excess food, and one
coin-float adjustment through `deposit_excess_coins` or `withdraw_bank_items`.

Do not loop over the same bank item several times unless the bridge returns a
real partial-move failure. For the current cow trip loadout, run this only when
already in a bank area:

```sh
python3 agent-navigation/tools/bank_loadout.py --preset cowhide-trip --json
python3 agent-navigation/tools/bank_loadout.py --preset cowhide-trip --dry-run --json
```

## Legacy Compatibility Tools

The older skill-specific tools remain available so existing scripts and live
agents do not break:

- `mine_ore`, `mine_ore_until_inventory_full`
- `chop_tree`, `chop_tree_until_inventory_full`
- `fletch_logs`, `fletch_logs_until_inventory_empty`
- `fish_food`, `cook_food`, `light_fire`
- `smelt_bar`, `smith_item`, `smith_best_item`, `plan_smithing`
- `plan_combat_training`, `train_combat`, `train_smithing_profit`
- durable goal tools such as `start_combat_goal`, `observe_goal`, `stop_goal`

Use these for compatibility and recovery, but prefer primitive-backed scripts
for new behavior. When a script needs behavior the primitive layer cannot
express, add the smallest missing primitive instead of a full strategy tool.

## Bridge Script State Shapes

`bridge_script.call_tool("observe_state", {}, profile=PROFILE)` returns the
raw bridge response. Unwrap it with `bridge_script.player_from(result)` when
you need the player object.

`bridge_script.observe(profile=PROFILE)` already returns the unwrapped player
dict from full `observe_state`; do not pass that value back through
`player_from`.

Use full `observe_state` or `bridge_script.observe` when a script needs complete
bank contents. XS and XXS observe variants are preferred for normal control
loops, but they may omit or compact bank details.

## External Script Pattern

1. Read state with `observe_state`.
2. Request normal A-to-B routes through ML1 (`route_ml.py define`) and follow the returned `routeSteps` with movement primitives. Use bare `route_runner.py` only for legacy diagnostics or compatibility-executor regression checks.
3. Use one primitive action, such as item-on-item, object interaction, shop buy,
   or NPC attack.
4. Wait with `wait_until_idle` or a movement batch.
5. Re-observe from the returned state and decide the next script step.
6. Record JSONL evidence under an ignored `agent-navigation/data/<domain>/runs/`
   directory.

Keep profile scoping by passing `--profile PROFILE` to scripts or setting
`RS_PROFILE`. Do not print bridge tokens.

## Current Script Entry Points

Discover scripts through:

```sh
python3 agent-navigation/tools/script_registry.py search QUERY
```

Current gameplay runners include:

- `agility_runner.py`: obstacle-course runner driven by object interaction
  variants and post-state proof.
- `mining_runner.py`: mine-site selection, route learning, primitive rock
  interaction loops, and banking. Legacy mining tools are fallback only.
- `woodcutting_runner.py`: standalone primitive tree chopping with optional
  banking and bird-nest pickup.
- `fletching_runner.py`: primitive-first woodcutting/fletching loop with
  fallback to legacy fletching/chop tools for old live runtimes.
- `food_runner.py`: fishing, cooking, fish-cook, and firemaking through
  `interact_npc`, item-use, interface-button, and idle-wait primitives.
- `smithing_runner.py`: smelting and smithing through furnace/anvil object
  primitives, interface buttons, and interface item selection.
- `combat_runner.py`: generic combat through style, target-finding, attack,
  food, loot, and wait primitives.
- `al_kharid_warrior_runner.py`, `chaos_druid_runner.py`,
  `white_knight_runner.py`, and `moss_giant_runner.py`: bespoke enemy trip
  runners sharing the primitive combat trip loop for loadout, ML1 route
  execution, food, direct style cycling, useful loot banking, and bone burying.
- `bank_loadout.py`: compact state-derived bank loadouts for scripts and manual
  recovery, including the cowhide-trip preset.
- `cowhide_combat_runner.py`: cow combat, hide pickup, food restock, and banking
  through existing combat, item, shop, bank-policy, and route primitives.
- `marathon_runner.py`: route endurance/testing runner.
- `route_ml.py define`: preferred ML1 route-definition API for normal A-to-B routing.
- `route_runner.py`: deprecated standalone route execution and local path preflight; keep it for legacy diagnostics and compatibility executor checks.

Map, memory, and support scripts are also registered in
`agent-navigation/data/script_registry.json`.
