---
name: 2006scape-agent-bridge-dev
description: "Use when adding, debugging, reviewing, or documenting 2006Scape Codex agent bridge tools in /Users/kevin/Documents/2006Scape, including rs.* dynamic tools, AgentBridgeServer, AgentActionService, AgentToolService, AgentSessionManager, CodexAppServerClient tool metadata, bridge HTTP endpoints, session scoping, Maven checks, runtime restarts, and proving tools through agent-navigation/tools/rs-tool.sh."
---

# 2006Scape Agent Bridge Dev

Use this skill for bridge/tool development. Pair it with `2006scape-dev-editing` for general repo edit rules and `2006scape-local-runtime` when live restart or session-claim work is required.

## Boundaries

Other agents may be using the game. Do not restart the server/client, kill processes, or replace running jars while editing bridge code unless the user explicitly asks for runtime validation. Compile-time validation is not live validation.

Keep tools server-authoritative. HTTP handlers must not mutate gameplay directly; queue or execute through `AgentActionService`, which runs against the claimed player and existing game mechanics.

Prefer a primitive-first bridge boundary. New gameplay strategies should usually be Python scripts that compose stable primitives such as `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, `interact_object`, `interact_npc`, movement, wait, bank, shop, and combat tools. Add Java only when the bridge is missing a reusable gameplay input primitive; do not add a new bespoke Java tool for each skill loop.

Never print or copy bridge tokens. Use `agent-navigation/tools/rs-tool.sh` for live proof.

## Main Files

- `2006Scape Server/src/main/java/com/rs2/agent/AgentBridgeServer.java`: local HTTP bridge, health, session claim, and tool endpoint.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentSessionManager.java`: nonce/session ownership and token validation.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentActionService.java`: tick-aware action queue, movement/wait batches, and legacy compatibility batches.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentToolService.java`: immediate primitive handlers, legacy tool handlers, and `observe_state`.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentKnowledgeBase.java`: built-in landmarks and static gameplay knowledge.
- `2006Scape Client/src/main/java/CodexAppServerClient.java`: dynamic tool metadata and prompt text exposed to Codex.
- `2006Scape Client/src/main/java/AgentClientController.java` and `AgentBridgeHttpClient.java`: client-side `/agent` control and claim communication.

## Tool-Change Checklist

When adding or changing an `rs.*` primitive:

1. Define or update the tool metadata in `CodexAppServerClient.java`.
2. Route the server-side tool name in `AgentToolService` or `AgentActionService`.
3. Use existing mechanics such as `PlayerAssistant.playerWalk`, `CombatAssistant.attackNpc`, `ClickObject`, `NpcActions`, `UseItem`, shops, banking, or dialogue/interface/item handlers.
4. Preserve session scoping: reject offline, disconnected, dead, expired-token, and wrong-player sessions.
5. Return a useful JSON result with `success`, a concise message, and state when it helps the next decision.
6. Add or update focused tests when behavior is shared, risky, or has already regressed.

Prefer external scripts for skill loops. Keep `mine_ore_until_inventory_full`, `chop_tree_until_inventory_full`, `fletch_logs_until_inventory_empty`, `fish_food`, `cook_food`, `light_fire`, `smelt_bar`, `smith_item`, `train_combat`, and other legacy tools working, but use them as compatibility tools behind primitive-backed scripts. See `agent-navigation/scripting-primitives.md` for the current boundary.

Prefer batch or wait primitives for long-running actions. `walk_to_tile_until_arrived`, `travel_to_landmark_until_arrived`, `wait_until_idle`, and compatibility batch tools exist to avoid one-tick polling. When observing an already-running command from a terminal session, estimate the likely completion interval and wait near that duration instead of polling every few seconds.

Dynamic XS tools are first-class bridge aliases, not separate gameplay mechanics. `*_XS` names route through the same server-authoritative handlers and compact the returned payload before it goes back to the model. Keep XS coverage in `CodexAppServerClient.java`, route aliases through `AgentActionService`, and compact through `AgentToolService.compactXsResult`. Current high-use XS aliases are `observe_state_XS`, `walk_to_tile_until_arrived_XS`, `travel_to_landmark_until_arrived_XS`, `wait_ticks_XS`, `wait_until_idle_XS`, `find_nearest_object_XS`, `deposit_inventory_items_XS`, `unequip_item_XS`, `unequip_items_XS`, and `food_bank_XS`. Full tools remain the evidence/debug fallback.

When updating bank/equipment metadata, expose array fields that already exist server-side. `deposit_inventory_items` and `deposit_inventory_items_XS` accept `itemIds` to deposit multiple item types in one call. `unequip_items_XS` accepts `equipmentSlots`, `slotNames`, `itemIds`, `names`/`items`, or `all=true` so agents do not loop one equipment slot at a time.

## Validation

For source changes, run the smallest meaningful Maven check first, then broaden if needed:

```sh
mvn -q -DskipTests package
mvn -q clean test
```

The root reactor module names include spaces. If using `-pl`, confirm the module name first; the server module is `2006Scape Server`.

After Java bridge changes, build success is not enough. Restart through the runtime helper when the user wants live proof:

```sh
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify
```

Then prove the tool through the wrapper:

```sh
agent-navigation/tools/rs-tool.sh observe_state '{}'
agent-navigation/tools/rs-tool.sh <tool_name> '<json-args>'
```

If the live JVM was not restarted, assume it is still running old code.

## Debugging Pattern

Start with `observe_state`, not a mutating action. Check whether the failure is:

- metadata missing in `CodexAppServerClient.java`;
- tool name not routed by `AgentToolService` or `AgentActionService`;
- stale running jar after a compile;
- invalid bridge session;
- in-game precondition such as bank not open, no item, wrong interface, no reachable object, combat, death, or insufficient level.

For object, door, gate, floor, and dialogue tools, a `success:true` click is not proof. Verify the post-state proves the transition.

## Skill Maintenance

If bridge development reveals a new repeatable failure mode, validation command, source file, or safer implementation pattern, surface it to the user and ask whether to make the skill edit.
