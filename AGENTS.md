# 2006Scape Agent Guide

This repository is a Java/Maven RuneScape private-server project split into a client module and a server module. Use this guide to get oriented quickly and to avoid redoing local setup work.

## Repository Layout

- `pom.xml`: Maven aggregator for both modules.
- `2006Scape Client/`: desktop Java client in the default package.
  - Main entrypoints: `src/main/java/Main.java` and `src/main/java/Client.java`.
  - `Client.java` forces localhost and delegates to `Main`.
  - `Game.java` and `LocalGame.java` are intentionally duplicated for local Parabot support. If behavior in `Game.java` changes, check whether `LocalGame.java` must be kept in sync.
  - Codex agent client bridge classes live in the default package: `AgentClientController.java`, `AgentBridgeHttpClient.java`, and `CodexAppServerClient.java`.
- `2006Scape Server/`: game server.
  - Main entrypoint: `src/main/java/com/rs2/GameEngine.java`.
  - Packet routing: `src/main/java/com/rs2/net/packets/PacketHandler.java`.
  - Game content: `src/main/java/com/rs2/game/content/`.
  - Players/NPCs/items/objects: `src/main/java/com/rs2/game/players`, `npcs`, `items`, `objects`.
  - Cache/data/config: `data/cache`, `data/cfg`, `data/bans`, `data/logs`.
  - Plugins: `plugins/`, added as a Maven source root by the server `pom.xml`.
  - Codex agent server bridge classes live in `src/main/java/com/rs2/agent/`.
- `docker-compose.yml`: Java 8 build/runtime helpers.

## Local Development Environment

This machine was set up during the initial repo exploration:

- Homebrew is installed at `/opt/homebrew/bin/brew`.
- Maven is installed through Homebrew.
- Homebrew OpenJDK is installed and available through:
  - `/opt/homebrew/opt/openjdk/bin/java`
  - `/opt/homebrew/opt/openjdk/bin/javac`
  - `/opt/homebrew/opt/openjdk/bin/jar`
- `~/.zprofile` and `~/.zshrc` add Homebrew OpenJDK to `PATH` for new zsh sessions.
- Immediate command resolution in this Codex environment is provided by symlinks:
  - `~/.local/bin/java`
  - `~/.local/bin/javac`
  - `~/.local/bin/jar`
- Docker Desktop is installed and can run the repo's Java 8 compose build.

Native local Java is newer than the project target, but `mvn -B clean install` has been verified to compile successfully. The stricter compatibility check is the Docker Compose build, which uses Maven 3.8.2 with Java 8.

## Build Commands

From the repo root:

```sh
mvn -B clean install
```

Java 8 compatibility build:

```sh
docker compose run --rm rsps-2006scape-build
```

Expected current behavior:

- The build succeeds for root, client, and server.
- Focused server-side JUnit tests exist for the Codex agent bridge.
- Maven emits warnings about:
  - missing client `maven-compiler-plugin` version,
  - server `systemPath` dependency on `libs/everythingrs-api.jar`,
  - Java 8 source/target warnings under newer native JDKs.
- Docker Compose emits a warning that the top-level `version` key is obsolete.

Useful focused checks:

```sh
mvn -q clean test
mvn -q -DskipTests package
```

## Run Commands

Build first, then run the server from the server module directory. The working directory matters because the server expects `data/` relative to the current directory.

```sh
cd "2006Scape Server"
java -jar target/server-1.0-jar-with-dependencies.jar -c ServerConfig.json
```

For active local development, prefer `./scripts/start-server.sh` from the repo root. It runs a copied jar from `/tmp/2006scape-run/` so Maven package builds do not replace the jar under a running Java 8 process. Do not rebuild `target/server-1.0-jar-with-dependencies.jar` while a live server is running directly from that same path; this previously caused a native `libzip` crash during lazy class loading after an object/bank click.

For the reliable Codex-controlled server/client/login/bridge startup flow, use `docs/local-agent-startup.md`. The default local profile is `MrFlame`, but the helper is profile-aware: pass `--profile MrGem` or set `RS_PROFILE=MrGem` to use that character's saved password file, session file, client pid file, and route trace filter. Never print or inspect bridge tokens.

The server listens on:

- `43594`: game service for world 1.
- `8080`: HTTP cache/file service when enabled.
- `43595`: JAGGRAB cache/file service when enabled.

Run the local client:

```sh
cd "2006Scape Client"
java -jar target/client-1.0-jar-with-dependencies.jar -local
```

Useful client flags include:

- `-local`, `-dev`, or `-offline`: connect to localhost and disable CRC checking.
- `-s <host>`: set server host.
- `-u <username>` and `-p <password>`: prefill login details.
- `-w <world>`: set world id.
- `-scale <n>` or `-double-size`: scale the client canvas for visibility; use `-scale 2 -no-nav` for the current larger testing window.

## Codex RuneScape Agent

The base agent implementation lets a logged-in player type `/agent ...` in the existing client chatbox. The client intercepts those messages locally before public chat or `::` command handling, launches `codex app-server --listen stdio://`, and exposes RuneScape dynamic tools under the `rs` namespace.

Client controls:

- `/agent key`: opens a Swing password dialog and sends the API key to Codex auth through `account/login/start`. Do not persist API keys in repo files or game config.
- `/agent status`: reports Codex app-server/auth/session state.
- `/agent stop`: interrupts the active Codex turn and clears the current server-side action.
- `/agent <task>`: starts a Codex turn for gameplay tasks such as `travel to varrock`, `attack goblin`, or `mine iron ore`.

Agent testing profiles:

- The default local testing profile is `MrFlame`. Use another profile only when the user asks or when validating multi-character behavior.
- Keep repo-side tool calls scoped to the intended character. Use `RS_PROFILE=<name>` or `runtime_doctor.py --profile <name>` so `rs-tool.sh`, route traces, recorder output, and context maps use the matching session/profile.
- New or modified tools, runners, status commands, map renderers, and evidence readers must be profile-capable. Accept `--profile` or honor `RS_PROFILE`/`RSBRIDGE_PROFILE`, pass the resolved profile to bridge calls and child processes, and avoid new MrFlame-only assumptions.
- Writable status, evidence, logs, screenshots, maps, and caches should be profile-scoped or include explicit `profile`, `playerName`, and `sessionId` metadata when intentionally shared.
- `MrFlame` keeps the legacy session file `agent-navigation/.local/rsbridge-session.json`; other profiles use `agent-navigation/.local/rsbridge-session-<profile>.json`.
- For unattended agent relaunches, prefer the documented startup flow in `docs/local-agent-startup.md`; it uses `-password-character-save`, `-agent-auto-login`, and `-agent-claim` so the local bridge session is claimed without manual typing.
- Do not stop, replace, or relaunch an active client/server owned by another agent unless the user explicitly asks. Profile-specific launches should avoid clobbering the default client.

Navigation project:

- Repo-local route memory lives in `agent-navigation/`.
- For repo-side gameplay control, prefer `agent-navigation/tools/rs-tool.sh <tool> '<json-args>'`; it reads the active profile session file and posts to the local bridge.
- For new gameplay automation, read `agent-navigation/scripting-primitives.md` and compose stable bridge primitives in Python instead of adding new bespoke Java `rs.*` tools. Keep Java changes for missing general primitives only; route choice, skilling loops, combat trip policy, banking strategy, and recovery behavior belong in profile-aware Python scripts and data.
- Use ML1 `python3 agent-navigation/ml-routing/route_ml.py define --from X,Y,H --to PLACE_OR_TILE --combat-level N --food N --run-energy N --run-enabled` for normal A-to-B route selection. Bare `route_runner.py --to ...`, `navdb.py next-step`, and `router.py plan` are legacy diagnostics/fallback debugging, not the preferred agent route method.
- Use `agent-navigation/tools/navdb.py validate`, `self-test`, `next-step`, `route-risk`, and `record-observation` while learning or validating route data.
- Use `agent-navigation/tools/script_registry.py search <query>` to find helper scripts by fuzzy name, wildcard, tag, or description before guessing filenames.
- Use `agent-navigation/tools/character_memory.py show --profile <name> --json` at the start of long gameplay/progression turns when durable profile context could matter. Write sparse memories/goals only for noteworthy, future-useful lessons such as equipment upgrades, strategic preferences, or recurring blockers. The files are profile-scoped under ignored `agent-navigation/.local/character-memory/<profile>/`; route facts belong in `agent-navigation/data/`, and routine progress belongs in session logs.
- Use `agent-navigation/tools/capture-client-screenshot.sh --prefix <short-reason>` when route state is visually ambiguous, especially doors, walls, gates, stairs, blocked movement, wrong side of an object, or unexpected HP/combat changes. Record useful screenshots through `record-observation --screenshot`.
- Current focus: safe routing with hazards, food/combat checks, run-energy checks, and verified south Varrock movement around the dark-wizard approach.

Runtime bridge:

- `AgentBridgeServer` starts on `127.0.0.1:43610` from `GameEngine.main`.
- `POST /agent/session/claim` consumes a nonce created by the client.
- The client authenticates ownership by sending packet-103 command `agentbridge claim <nonce>` while logged in.
- `POST /agent/tool` requires the returned session token in `X-Agent-Token`.
- HTTP handlers must never mutate game state directly. Queue gameplay work through `AgentActionService`, which drains at the start of the server tick.

Agent session logging:

- Every agent bridge session must write both raw JSONL events and a human-readable Markdown summary under `2006Scape Server/data/logs/agent-sessions/<yyyy-MM-dd>/`.
- Use matching file stems per session: `<sessionId>.jsonl` for raw events and `<sessionId>.md` for the readable summary.
- The Markdown summary must focus on the task, what was built or done, obstacles encountered, the solution/result, and a logical next step.
- Write the Markdown summary as a short, readable story of the session: what the agent set out to do, what it tried, where the world pushed back, how it adapted, and where the player ended up.
- When available, read the corresponding Codex rollout transcript under `~/.codex/sessions/<yyyy>/<MM>/<dd>/` and weave the agent's reasoning process into the story. Use the visible transcript events: user goal, assistant updates, tool calls, tool results, retries, course corrections, and final outcome.
- Summarize the reasoning process as an observable decision trail, not as raw hidden chain-of-thought. It should explain why the agent chose each major step, what evidence changed its plan, and how it interpreted tool results.
- Include a concise operational reflection only when it explains a decision, blocker, or future safety constraint. Keep the tone serious and factual; do not add persona, self-talk, or emotional color for routine progress.
- Include a concise assessment of what the harness is learning over time: which patterns are becoming easier, which failures repeated, and what would make the next session more capable.
- Logs and summaries must explicitly capture in-game failures and blockers, including player death, missing required tools or equipment, insufficient inventory space, missing skill requirements, unreachable targets, unavailable objects/NPCs/items, closed or wrong interfaces, and any state that prevented normal gameplay execution.
- Do not write session tokens, API keys, passwords, secrets, or other credentials to either log format; redact sensitive fields before logging.
- Use `com.rs2.agent.AgentSessionReport` for rollups over existing JSONL logs. It writes short reports to `2006Scape Server/data/logs/agent-sessions/reports/<yyyy-MM-dd>/summary-<HHMMSS>Z.md` and keeps `2006Scape Server/data/logs/agent-sessions/reports/canonical-agent-log-index.md` as the canonical index. Reports should call out new or interesting behavior, top tools, repeated blockers, death/failure observations, connected multi-day sessions, and concrete harness improvements.
- Every logged-in profile should also maintain a derived profile-memory artifact under `2006Scape Server/data/logs/agent-sessions/profiles/<profile>/agent-personality.md`. This is operational profile memory, not a raw transcript or character voice: durable risk notes, preparation habits, repeated blockers, and bounded recent notes synthesized from sanitized session events. Keep it account-scoped, redact secrets, and expose it through `rs.observe_state` as `agentPersonality` so autonomous turns can use it for preparation, caution, and route choice without quoting it, roleplaying it, or overriding the player's command. This memory is available after `rs.observe_state`; it is not a separate preloaded `AGENTS.md`-style instruction file.

Dynamic tools currently supported:

- `rs.observe_state`
- `rs.observe_state_XS`
- `rs.observe_state_XXS`
- `rs.observe_state_if_changed_XS`
- `rs.observe_state_if_changed_XXS`
- `rs.combat_state_XS`
- `rs.combat_state_XXS`
- `rs.set_run`
- `rs.set_run_XXS`
- `rs.send_public_chat`
- `rs.plan_combat_training`
- `rs.continue_dialogue`
- `rs.select_dialogue_option`
- `rs.close_interfaces`
- `rs.use_item_on_item`
- `rs.use_item_on_object`
- `rs.click_interface_button`
- `rs.click_interface_button_XXS`
- `rs.select_interface_item`
- `rs.walk_to_tile`
- `rs.walk_path_steps`
- `rs.walk_path_steps_XS`
- `rs.walk_path_steps_XXS`
- `rs.walk_to_tile_until_arrived`
- `rs.walk_to_tile_until_arrived_XS`
- `rs.walk_to_tile_until_arrived_XXS`
- `rs.travel_to_landmark`
- `rs.travel_to_landmark_until_arrived`
- `rs.travel_to_landmark_until_arrived_XS`
- `rs.travel_to_landmark_until_arrived_XXS`
- `rs.wait_ticks`
- `rs.wait_ticks_XS`
- `rs.wait_ticks_XXS`
- `rs.wait_until_idle`
- `rs.wait_until_idle_XS`
- `rs.wait_until_idle_XXS`
- `rs.wait_until_combat_event_XS`
- `rs.wait_until_combat_event_XXS`
- `rs.wait_until_combat_event_smart_XS`
- `rs.wait_until_combat_event_smart_XXS`
- `rs.find_nearest_npc`
- `rs.find_training_npc`
- `rs.interact_npc`
- `rs.attack_npc`
- `rs.attack_npc_XXS`
- `rs.find_nearest_object`
- `rs.find_nearest_object_XS`
- `rs.find_nearest_rock`
- `rs.find_nearest_tree`
- `rs.set_combat_style`
- `rs.set_combat_style_XXS`
- `rs.equip_item`
- `rs.unequip_item`
- `rs.unequip_item_XS`
- `rs.unequip_items_XS`
- `rs.unequip_items_XXS`
- `rs.eat_item`
- `rs.eat_best_food`
- `rs.eat_best_food_XXS`
- `rs.bury_bones`
- `rs.bury_bones_XS`
- `rs.bury_bones_XXS`
- `rs.pickup_ground_item`
- `rs.pickup_ground_item_XXS`
- `rs.open_nearest_shop`
- `rs.buy_shop_item`
- `rs.sell_inventory_item`
- `rs.sell_inventory_items`
- `rs.interact_object`
- `rs.interact_object_XS`
- `rs.interact_object_XXS`
- `rs.object_transition_step_XS`
- `rs.object_transition_step_XXS`
- `rs.drop_inventory_items`
- `rs.deposit_inventory_items`
- `rs.deposit_inventory_items_XS`
- `rs.deposit_inventory_items_XXS`
- `rs.withdraw_bank_items`
- `rs.withdraw_bank_items_XS`
- `rs.withdraw_bank_items_XXS`
- `rs.food_bank_XS`
- `rs.food_bank_XXS`
- `rs.deposit_excess_coins`
- `rs.deposit_excess_coins_XXS`
- `rs.cancel_current_action`

Gameplay guardrails:

- Keep actions server-authoritative and routed through existing mechanics such as `PlayerAssistant.playerWalk`, `CombatAssistant.attackNpc`, `ClickObject`, and `Mining.startMining`.
- Prefer primitive-backed external scripts for new skill loops. Use `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, `interact_object`, `interact_npc`, bank/shop tools, combat tools, and `wait_until_idle` before adding Java skill-specific tools. Hidden legacy strategy tools are quarantined compatibility paths and require explicit `legacyCompatibility=true`; do not use them for new behavior.
- Prefer XXS dynamic tools when confirmation plus critical survival state is enough: `observe_state_XXS`, `observe_state_if_changed_XXS`, `combat_state_XXS`, `set_run_XXS`, `walk_path_steps_XXS`, `walk_to_tile_until_arrived_XXS`, `travel_to_landmark_until_arrived_XXS`, `wait_ticks_XXS`, `wait_until_idle_XXS`, `wait_until_combat_event_smart_XXS`, `object_transition_step_XXS`, `interact_object_XXS`, `click_interface_button_XXS`, `attack_npc_XXS`, `eat_best_food_XXS`, `pickup_ground_item_XXS`, `bury_bones_XXS`, `deposit_inventory_items_XXS`, `withdraw_bank_items_XXS`, `unequip_items_XXS`, and `food_bank_XXS`. XXS includes only success/message/status/event counters, tile, HP/max HP, run energy/enabled, combat, poison, death, free slots, food, and tiny XP deltas. Prefer XS dynamic tools when compact decision context is needed: `observe_state_XS`, `observe_state_if_changed_XS`, `combat_state_XS`, `walk_path_steps_XS`, `walk_to_tile_until_arrived_XS`, `travel_to_landmark_until_arrived_XS`, `wait_ticks_XS`, `wait_until_idle_XS`, `wait_until_combat_event_smart_XS`, `object_transition_step_XS`, `interact_object_XS`, `find_nearest_object_XS`, `bury_bones_XS`, `deposit_inventory_items_XS`, `withdraw_bank_items_XS`, `unequip_items_XS`, and `food_bank_XS`. Use full tools only when XS omits a field needed for debugging, complete evidence, or a new workflow.
- Prefer server-side batch or wait primitives for long-running actions. Use `travel_to_landmark_until_arrived_XS`/`travel_to_landmark_until_arrived_XXS` or `walk_to_tile_until_arrived_XS`/`walk_to_tile_until_arrived_XXS` instead of travel/walk plus repeated one-tick waits, `walk_path_steps_XS`/`walk_path_steps_XXS` for short adjacent route segments, `object_transition_step_XS`/`object_transition_step_XXS` for doors/gates/stairs/ladders, `wait_until_combat_event_smart_XXS` during combat when only HP/XP/event status matters, `wait_until_combat_event_smart_XS` when loot or target detail matters, and `wait_until_idle_XS`/`wait_until_idle_XXS` after production actions such as smelting, smithing, cooking, fishing, or non-combat waits. Keep mining, woodcutting, fletching, combat cleanup, and bank-restock policy in Python scripts that compose these primitives.
- XP-affecting tool results include `skillChanges` and short-lived `xpRecent` summaries when XP changed recently. For Prayer, treat `points`/`current` as current prayer points and `base` as the real Prayer level from XP.
- For banking and equipment cleanup, batch intent into one call. `deposit_inventory_items_XS` accepts `itemIds` to deposit multiple item types at once and `keepFoodCount` to preserve food; `withdraw_bank_items_XS` accepts `itemIds`/`itemId` plus `amount`; `unequip_items_XS` accepts `equipmentSlots`, `slotNames`, `itemIds`, `names`/`items`, or `all=true` to unequip several items without looping. Route-to-bank, loot policy, coin reserve, food target, and return routing belong in Python.
- Treat a batch tool response as the next observation; do not immediately call `observe_state` unless the returned state is missing needed context. When waiting on a long-running batch command, estimate the likely completion interval from `maxTicks` or the action loop and poll near that time instead of every few seconds, unless combat, death, a blocker, or near-term completion is likely.
- Do not add screen automation, admin teleports, item spawning, or direct player state edits for agent behavior.
- Preserve session scoping: reject offline, disconnected, dead, expired-token, and wrong-player sessions.
- Keep the Codex thread read-only with `approvalPolicy: "never"` and no network access at turn time. The model should use only `rs` dynamic tools for gameplay.
- Initial world knowledge is in `AgentKnowledgeBase` and covers Lumbridge, Lumbridge goblins/cows, Varrock, Varrock east mine/banks, combat shops, Barbarian Village, Falador, rock crabs, and short waypoint routes.

## Runtime Config Files

- `2006Scape Server/ServerConfig.Sample.json` is tracked.
- `2006Scape Server/ServerConfig.json` is ignored by git and can be local-only.
- `2006Scape Server/data/secrets.json` is ignored by git and is auto-created on first server run if missing.
- Do not commit generated `target/` directories, logs, local configs, secrets, or built jars.

## Server Startup Flow

`GameEngine.main`:

1. Loads optional external config from `-c` / `-config`.
2. Verifies it is running from `2006Scape Server` by checking `data/`.
3. Loads secrets and optional Discord integration.
4. Starts the Apollo/Netty file and game services.
5. Opens the cache from `data/cache`.
6. Loads regions, doors, item definitions, global drops, bans, player shops, and plugins.
7. Starts the main game loop on a fixed 600ms tick.

Plugin discovery walks `2006Scape Server/plugins`, converts file paths to class names, instantiates concrete `EventSubscriber` classes, and registers them against `Player`.

## Development Notes

- Preserve the existing Java 8-compatible style unless a task explicitly modernizes it.
- Keep changes tightly scoped; much of the client is deobfuscated/decompiled-era code in the default package.
- Prefer adding behavior through existing packet handlers, content handlers, or event plugins instead of introducing parallel systems.
- Server data paths are relative and fragile; run server commands from `2006Scape Server`.
- If touching networking or login code, test with both a native build and the Java 8 Docker build.
- If touching gameplay behavior, include at least a server startup smoke test when no automated tests exist.
- If touching the Codex agent bridge, run `mvn -q clean test` and `mvn -q -DskipTests package` from the repo root.

## Verified Smoke Test

The server was verified with:

```sh
cd "2006Scape Server"
java -jar target/server-1.0-jar-with-dependencies.jar -c ServerConfig.Sample.json
```

It successfully loaded cache/data, registered 21 plugins, and listened on `0.0.0.0:43594`. Stop the process after smoke testing so the port is free for later runs.
