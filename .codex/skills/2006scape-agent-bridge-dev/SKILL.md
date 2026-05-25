---
name: 2006scape-agent-bridge-dev
description: "Use when adding, debugging, reviewing, or documenting 2006Scape Codex agent bridge tools in /Users/kevin/Documents/2006Scape, including rs.* dynamic tools, AgentBridgeServer, AgentActionService, AgentToolService, AgentSessionManager, CodexAppServerClient tool metadata, bridge HTTP endpoints, session scoping, Maven checks, runtime restarts, and proving tools through agent-navigation/tools/rs-tool.sh."
---

# 2006Scape Agent Bridge Dev

Use this skill for bridge/tool development. Pair it with `2006scape-dev-editing` for general repo edit rules and `2006scape-local-runtime` when live restart or session-claim work is required.

## Boundaries

Other agents may be using the game. Do not restart the server/client, kill processes, or replace running jars while editing bridge code unless the user explicitly asks for runtime validation. Compile-time validation is not live validation.

Keep tools server-authoritative. HTTP handlers must not mutate gameplay directly; queue or execute through `AgentActionService`, which runs against the claimed player and existing game mechanics.

Never print or copy bridge tokens. Use `agent-navigation/tools/rs-tool.sh` for live proof.

## Main Files

- `2006Scape Server/src/main/java/com/rs2/agent/AgentBridgeServer.java`: local HTTP bridge, health, session claim, and tool endpoint.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentSessionManager.java`: nonce/session ownership and token validation.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentActionService.java`: batch tools, durable goals, tick-aware action orchestration.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentToolService.java`: immediate tool handlers and `observe_state`.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentKnowledgeBase.java`: built-in landmarks and static gameplay knowledge.
- `2006Scape Client/src/main/java/CodexAppServerClient.java`: dynamic tool metadata and prompt text exposed to Codex.
- `2006Scape Client/src/main/java/AgentClientController.java` and `AgentBridgeHttpClient.java`: client-side `/agent` control and claim communication.

## Tool-Change Checklist

When adding or changing an `rs.*` tool:

1. Define or update the tool metadata in `CodexAppServerClient.java`.
2. Route the server-side tool name in `AgentToolService` or `AgentActionService`.
3. Use existing mechanics such as `PlayerAssistant.playerWalk`, `CombatAssistant.attackNpc`, `ClickObject`, Mining, Woodcutting, shops, banking, or dialogue handlers.
4. Preserve session scoping: reject offline, disconnected, dead, expired-token, and wrong-player sessions.
5. Return a useful JSON result with `success`, a concise message, and state when it helps the next decision.
6. Add or update focused tests when behavior is shared, risky, or has already regressed.

Prefer batch tools for long-running actions. `walk_to_tile_until_arrived`, `travel_to_landmark_until_arrived`, `mine_ore_until_inventory_full`, `chop_tree_until_inventory_full`, `wait_until_idle`, and durable goal tools exist to avoid one-tick polling. When observing an already-running batch command from a terminal session, estimate the likely completion interval and wait near that duration instead of polling every few seconds.

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
