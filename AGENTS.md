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

## Codex RuneScape Agent

The base agent implementation lets a logged-in player type `/agent ...` in the existing client chatbox. The client intercepts those messages locally before public chat or `::` command handling, launches `codex app-server --listen stdio://`, and exposes RuneScape dynamic tools under the `rs` namespace.

Client controls:

- `/agent key`: opens a Swing password dialog and sends the API key to Codex auth through `account/login/start`. Do not persist API keys in repo files or game config.
- `/agent status`: reports Codex app-server/auth/session state.
- `/agent stop`: interrupts the active Codex turn and clears the current server-side action.
- `/agent <task>`: starts a Codex turn for gameplay tasks such as `travel to varrock`, `attack goblin`, or `mine iron ore`.

Agent testing account:

- When running agent sessions or acting inside the client for testing, use one shared player profile named `MrGem`.
- Do not create or switch to alternate testing profiles for agent work unless the user explicitly asks for a different account.
- When launching the local client for agent testing, prefer `-u "MrGem"` so the intended profile is prefilled.

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
- Include a brief reflection on how the session felt from inside the harness, grounded in observable events rather than exaggerated emotion. It should describe confidence, uncertainty, friction, surprise, or satisfaction when those reactions help explain the agent's behavior.
- Include a concise assessment of what the agent appears to be learning over time in the harness: which patterns are becoming easier, which failures repeated, and what would make the next session more capable.
- Logs and summaries must explicitly capture in-game failures and blockers, including player death, missing required tools or equipment, insufficient inventory space, missing skill requirements, unreachable targets, unavailable objects/NPCs/items, closed or wrong interfaces, and any state that prevented normal gameplay execution.
- Do not write session tokens, API keys, passwords, secrets, or other credentials to either log format; redact sensitive fields before logging.

Dynamic tools currently supported:

- `rs.observe_state`
- `rs.plan_combat_training`
- `rs.continue_dialogue`
- `rs.select_dialogue_option`
- `rs.close_interfaces`
- `rs.walk_to_tile`
- `rs.travel_to_landmark`
- `rs.wait_ticks`
- `rs.find_nearest_npc`
- `rs.find_training_npc`
- `rs.attack_npc`
- `rs.train_combat`
- `rs.find_nearest_object`
- `rs.find_nearest_rock`
- `rs.find_nearest_tree`
- `rs.set_combat_style`
- `rs.equip_item`
- `rs.unequip_item`
- `rs.equip_best_items`
- `rs.eat_item`
- `rs.eat_best_food`
- `rs.pickup_ground_item`
- `rs.open_nearest_shop`
- `rs.buy_shop_item`
- `rs.sell_inventory_item`
- `rs.sell_inventory_items`
- `rs.interact_object`
- `rs.chop_tree`
- `rs.drop_inventory_items`
- `rs.deposit_inventory_items`
- `rs.withdraw_bank_items`
- `rs.deposit_excess_coins`
- `rs.mine_ore`
- `rs.smelt_bar`
- `rs.smith_item`
- `rs.smith_best_item`
- `rs.plan_smithing`
- `rs.cancel_current_action`

Gameplay guardrails:

- Keep actions server-authoritative and routed through existing mechanics such as `PlayerAssistant.playerWalk`, `CombatAssistant.attackNpc`, `ClickObject`, and `Mining.startMining`.
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
