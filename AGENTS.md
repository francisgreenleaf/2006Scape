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

If Docker Desktop is installed but the `docker` CLI or Compose plugin is not on the non-interactive shell `PATH`, use the repo validation wrapper instead; it discovers Docker Desktop's bundled macOS CLI/plugin:

```sh
RUN_DOCKER_BUILD=1 scripts/validate-network-auth-chat.sh
```

Expected current behavior:

- The build succeeds for root, client, and server.
- Focused server-side JUnit tests exist for the Codex agent bridge.
- Maven emits warnings about:
  - missing client `maven-compiler-plugin` version,
  - server `systemPath` dependency on `libs/everythingrs-api.jar`,
  - Java 8 source/target warnings under newer native JDKs.

Useful focused checks:

```sh
mvn -q clean test
mvn -q -DskipTests package
```

## GitHub And Pull Requests

- For this checkout, pull requests should be created on the `francisgreenleaf/2006Scape` fork only.
- Do not create pull requests against the original/upstream `2006-Scape/2006Scape` repository unless the user explicitly asks for that in the same request.
- When remotes include `origin` as `francisgreenleaf/2006Scape` and `upstream` as `2006-Scape/2006Scape`, push branches to `origin` and target PRs within the fork.

## Run Commands

Build first, then run the server from the server module directory. The working directory matters because the server expects `data/` relative to the current directory.

```sh
cd "2006Scape Server"
java -jar target/server-1.0-jar-with-dependencies.jar -c ServerConfig.json
```

For active local development, prefer `./scripts/start-server.sh` from the repo root. It runs a copied jar from `/tmp/2006scape-run/` so Maven package builds do not replace the jar under a running Java 8 process. Do not rebuild `target/server-1.0-jar-with-dependencies.jar` while a live server is running directly from that same path; this previously caused a native `libzip` crash during lazy class loading after an object/bank click.

For the reliable Codex-controlled server/client/login/bridge startup flow, use `docs/local-agent-startup.md`. The helper is profile-aware: pass `--profile PROFILE` or set `RS_PROFILE=PROFILE` to use that character's saved password file, session file, client pid file, and route trace filter. Never print or inspect bridge tokens.

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

- Use the profile selected by the user or task. When validating multi-character behavior, name each profile explicitly.
- Keep repo-side tool calls scoped to the intended character. Use `RS_PROFILE=<name>` or `runtime_doctor.py --profile <name>` so `rs-tool.sh`, route traces, recorder output, and context maps use the matching session/profile.
- New or modified tools, runners, status commands, map renderers, and evidence readers must be profile-capable. Accept `--profile` or honor `RS_PROFILE`/`RSBRIDGE_PROFILE`, pass the resolved profile to bridge calls and child processes, and avoid new single-profile assumptions.
- Writable status, evidence, logs, screenshots, maps, and caches should be profile-scoped or include explicit `profile`, `playerName`, and `sessionId` metadata when intentionally shared.
- The legacy default session file is `agent-navigation/.local/rsbridge-session.json`; named profiles use `agent-navigation/.local/rsbridge-session-<profile>.json`.
- For unattended agent relaunches, prefer the documented startup flow in `docs/local-agent-startup.md`; it uses `-password-character-save`, `-agent-auto-login`, and `-agent-claim` so the local bridge session is claimed without manual typing.
- Do not stop, replace, or relaunch an active client/server owned by another agent unless the user explicitly asks. Profile-specific launches should avoid clobbering the default client.

Navigation project:

- Repo-local route memory lives in `agent-navigation/`.
- For repo-side gameplay control, prefer `agent-navigation/tools/rs-tool.sh <tool> '<json-args>'`; it reads the active profile session file and posts to the local bridge or the session file's remote `bridgeUrl`.
- For repo-side control of a remote logged-in character, use `python3 agent-navigation/tools/remote_claim.py --profile <name> --bridge-url https://AGENT_GATEWAY --verify`, then type the printed `::agent claim ...` command in that character's game client. The helper writes a profile-scoped ignored session file containing `bridgeUrl`, so XS/XXS wrappers and Python scripts post to the HTTPS gateway instead of local `127.0.0.1`.
- For new gameplay automation, read `agent-navigation/scripting-primitives.md` and compose stable bridge primitives in Python instead of adding new bespoke Java `rs.*` tools. Keep Java changes for missing general primitives only; route choice, skilling loops, combat trip policy, banking strategy, and recovery behavior belong in profile-aware Python scripts and data.
- Use ML2 `python3 agent-navigation/ml2-routing/route_ml_XS.py define --from X,Y,H --to PLACE_OR_TILE --combat-level N --food N --run-energy N --run-enabled` for normal A-to-B route selection. Run the returned `cmd`/`execution.command` exactly when live movement is intended. Bare `route_runner.py --to ...`, `navdb.py next-step`, `router.py plan`, and ML1 are legacy diagnostics/fallback debugging, not the preferred agent route method.
- Use `agent-navigation/tools/navdb.py validate`, `self-test`, `next-step`, `route-risk`, and `record-observation` while learning or validating route data.
- Use `agent-navigation/tools/script_registry.py search <query>` to find helper scripts by fuzzy name, wildcard, tag, or description before guessing filenames.
- Use `agent-navigation/tools/character_memory.py show --profile <name> --json` at the start of long gameplay/progression turns when durable profile context could matter. Write sparse memories/goals only for noteworthy, future-useful lessons such as equipment upgrades, strategic preferences, or recurring blockers. The files are profile-scoped under ignored `agent-navigation/.local/character-memory/<profile>/`; route facts belong in `agent-navigation/data/`, and routine progress belongs in session logs.
- Use `agent-navigation/tools/capture-client-screenshot.sh --prefix <short-reason>` when route state is visually ambiguous, especially doors, walls, gates, stairs, blocked movement, wrong side of an object, or unexpected HP/combat changes. Record useful screenshots through `record-observation --screenshot`.
- Current focus: safe routing with hazards, food/combat checks, run-energy checks, and verified south Varrock movement around the dark-wizard approach.

Runtime bridge:

- `AgentBridgeServer` starts on loopback from `GameEngine.main`, defaulting to `127.0.0.1:43610`. `agent_bridge_port` may be changed for isolated local test deployments, but `agent_bridge_bind_host` must stay localhost/loopback.
- Packaged clients read `agent.bridge.url` from `client.properties`. The default `http://127.0.0.1:43610` preserves local dev behavior; remote packages should use an operator HTTPS gateway that forwards only approved `/agent/*` endpoints to the loopback bridge.
- `POST /agent/session/claim` consumes a nonce created by the client.
- The client authenticates ownership by sending packet-103 command `agentbridge claim <nonce>` while logged in.
- `POST /agent/tool` requires the returned session token in `X-Agent-Token`.
- The local bridge uses bounded HTTP workers, request-queue backpressure, bounded JSON request bodies, and a bounded game-tick action queue; it is still localhost-only and must never be exposed publicly.
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
- `rs.bank_item_count_XS`
- `rs.agent_chat_send_XS`
- `rs.agent_chat_read_XS`
- `rs.agent_chat_status_XS`
- `rs.food_bank_XS`
- `rs.food_bank_XXS`
- `rs.deposit_excess_coins`
- `rs.deposit_excess_coins_XXS`
- `rs.cancel_current_action`

Gameplay guardrails:

- Keep actions server-authoritative and routed through existing mechanics such as `PlayerAssistant.playerWalk`, `CombatAssistant.attackNpc`, `ClickObject`, and `Mining.startMining`.
- Prefer primitive-backed external scripts for new skill loops. Use `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, `interact_object`, `interact_npc`, bank/shop tools, combat tools, and `wait_until_idle` before adding Java skill-specific tools. Hidden legacy strategy tools are quarantined compatibility paths and require explicit `legacyCompatibility=true`; do not use them for new behavior.
- Prefer XXS dynamic tools when confirmation plus critical survival state is enough: `observe_state_XXS`, `observe_state_if_changed_XXS`, `combat_state_XXS`, `set_run_XXS`, `walk_path_steps_XXS`, `walk_to_tile_until_arrived_XXS`, `travel_to_landmark_until_arrived_XXS`, `wait_ticks_XXS`, `wait_until_idle_XXS`, `wait_until_combat_event_smart_XXS`, `object_transition_step_XXS`, `interact_object_XXS`, `click_interface_button_XXS`, `attack_npc_XXS`, `eat_best_food_XXS`, `pickup_ground_item_XXS`, `bury_bones_XXS`, `deposit_inventory_items_XXS`, `withdraw_bank_items_XXS`, `unequip_items_XXS`, and `food_bank_XXS`. XXS includes only success/message/status/event counters, tile, HP/max HP, run energy/enabled, combat, poison, death, free slots, food, and tiny XP deltas. Prefer XS dynamic tools when compact decision context is needed: `observe_state_XS`, `observe_state_if_changed_XS`, `combat_state_XS`, `walk_path_steps_XS`, `walk_to_tile_until_arrived_XS`, `travel_to_landmark_until_arrived_XS`, `wait_ticks_XS`, `wait_until_idle_XS`, `wait_until_combat_event_smart_XS`, `object_transition_step_XS`, `interact_object_XS`, `find_nearest_object_XS`, `find_nearest_rock_XS`, `find_nearest_tree_XS`, `bury_bones_XS`, `deposit_inventory_items_XS`, `withdraw_bank_items_XS`, `bank_item_count_XS`, `agent_chat_send_XS`, `agent_chat_read_XS`, `agent_chat_status_XS`, `unequip_items_XS`, and `food_bank_XS`. Use full tools only when XS omits a field needed for debugging, complete evidence, or a new workflow.
- Prefer server-side batch or wait primitives for long-running actions. Use `travel_to_landmark_until_arrived_XS`/`travel_to_landmark_until_arrived_XXS` or `walk_to_tile_until_arrived_XS`/`walk_to_tile_until_arrived_XXS` instead of travel/walk plus repeated one-tick waits, `walk_path_steps_XS`/`walk_path_steps_XXS` for short adjacent route segments, `object_transition_step_XS`/`object_transition_step_XXS` for doors/gates/stairs/ladders, `wait_until_combat_event_smart_XXS` during combat when only HP/XP/event status matters, `wait_until_combat_event_smart_XS` when loot or target detail matters, and `wait_until_idle_XS`/`wait_until_idle_XXS` after production actions such as smelting, smithing, cooking, fishing, or non-combat waits. Keep mining, woodcutting, fletching, combat cleanup, and bank-restock policy in Python scripts that compose these primitives.
- XP-affecting tool results include `skillChanges` and short-lived `xpRecent` summaries when XP changed recently. For Prayer, treat `points`/`current` as current prayer points and `base` as the real Prayer level from XP.
- For banking and equipment cleanup, batch intent into one call. `bank_item_count_XS` answers exact bank counts for specific `itemIds` or names without full `observe_state`; `deposit_inventory_items_XS` accepts `itemIds` to deposit multiple item types at once and `keepFoodCount` to preserve food; `withdraw_bank_items_XS` accepts legacy `itemIds`/`itemId` plus shared `amount`, and mixed exact quantities through `items:[{"itemId":440,"amount":9},{"itemId":453,"amount":18}]`; `unequip_items_XS` accepts `equipmentSlots`, `slotNames`, `itemIds`, `names`/`items`, or `all=true` to unequip several items without looping. Route-to-bank, loot policy, coin reserve, food target, and return routing belong in Python.
- For structured coordination, use `agent_chat_status_XS`, `agent_chat_read_XS`, and `agent_chat_send_XS` only when another agent/player message actually matters. Players can send to the same bus with `::agentchat message`, `::agentchat @agent:Name message`, `::agentchat @player:Name message`, `::agentchat @all message`, or `::agentchat #channel message`. `AgentChatService` keeps bounded backlog and direct-player delivery queues, and sanitizes message text, names, and channel keys before delivery, optional JSONL logging, or Discord mirroring. `agent_chat_log_enabled=true` writes sanitized envelopes under `data/logs/agent-chat/<yyyy-MM-dd>/agent-chat.jsonl`; do not log bridge tokens or Discord bot tokens. For named bridge targets, prefer `agent:"Name"` or `player:"Name"` alias fields; keep `to` plus `toType` for generic callers. Target shortcuts are mutually exclusive: use either `agent`/`player` or generic `to` plus `toType`, not both. Valid explicit `toType` values are `agent`, `player`, `channel`, and `broadcast`; invalid values fail closed instead of becoming channel messages. Direct `agent`/`player` targets require a target name, and `deliverToPlayers` is valid only for `player`/`broadcast`. Direct messages are visible to the target, sender name, and sender profile; Discord ingress uses the Discord display name as `fromName` and the configured bot's agent/profile as `fromProfile`. Discord fan-out attaches to `AgentChatService`; Discord mirror failures must not make in-game chat sends fail, and Discord callbacks must not mutate gameplay state or write client packets directly. Direct player delivery is queued and drained on the server tick, so `agent_chat_send_XS` may report `deliveryPending:true`; if the player is offline or the client chatbox send fails when drained, later `agent_chat_read_XS` output records the target in `undeliveredTo`.
- Treat a batch tool response as the next observation; do not immediately call `observe_state` unless the returned state is missing a named field. Python runners should use `bridge_script.observe_xxs()` for confirmation loops and `bridge_script.observe_xs()`/`bridge_script.observe()` for normal compact decision state. Keep full `observe_state` and `bridge_script.observe_full()` out of hot loops; use them only for complete bank/equipment/inventory evidence, profile/personality context, or a new debug workflow. Direct `rs-tool.sh observe_state` is blocked unless `RS_ALLOW_FULL_OBSERVE=1` is set for explicit debug/evidence work. When waiting on a long-running batch command, estimate the likely completion interval from `maxTicks` or the action loop and poll near that time instead of every few seconds, unless combat, death, a blocker, or near-term completion is likely.
- Do not add screen automation, admin teleports, item spawning, or direct player state edits for agent behavior.
- Preserve session scoping: reject offline, disconnected, dead, expired-token, and wrong-player sessions.
- Keep the Codex thread read-only with `approvalPolicy: "never"` and no network access at turn time. The model should use only `rs` dynamic tools for gameplay.
- Initial world knowledge is in `AgentKnowledgeBase` and covers Lumbridge, Lumbridge goblins/cows, Varrock, Varrock east mine/banks, combat shops, Barbarian Village, Falador, rock crabs, and short waypoint routes.

## Runtime Config Files

- `2006Scape Server/ServerConfig.Sample.json` is tracked.
- `2006Scape Server/ServerConfig.External.Sample.json` is tracked as the direct public external-player starting point with explicit bind hosts, PBKDF2 account auth enabled, and `direct_tcp` plaintext acknowledgement fields set. Replace sample placeholders such as `server.example.com` and `REPLACE_WITH_PUBLIC_INTERFACE_IP` before real verification or distribution.
- `2006Scape Server/ServerConfig.Tailscale.Sample.json` is tracked as the turnkey encrypted private-beta starting point. It binds game/cache services to `127.0.0.1` plus `REPLACE_WITH_TAILSCALE_IP`, uses `example-tailnet-host` for the packaged client target, sets `external_transport_mode` to `tailscale`, and keeps the agent bridge loopback-only. Replace placeholders with the server's Tailscale IP or MagicDNS name before real verification or distribution.
- `2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json` is tracked as the encrypted client TLS tunnel starting point. It keeps Java game/cache listeners loopback-only and uses `REPLACE_WITH_PUBLIC_TLS_HOST` for the public stunnel/certificate endpoint. Replace that placeholder before real packaging or verification; `CLIENT_ALLOW_PLACEHOLDER_NETWORK_CONFIG=1` is only for source validation of this sample.
- `2006Scape Server/ServerConfig.json` is ignored by git and can be local-only.
- `2006Scape Server/data/secrets.json` is ignored by git and is auto-created owner-only on first server run if missing where POSIX permissions are supported. When loading an existing regular secrets file, Java tightens it to owner-only before reading; symlinked secrets are refused.
- `2006Scape Server/data/secrets.External.Sample.json` is tracked as a placeholder Discord-agent transport shape. Copy it to ignored `data/secrets.json`, make the real file owner-only on POSIX systems, and replace placeholder tokens/channel ids locally; never commit real tokens. Runtime loading refuses symlinked secrets and deployment verification rejects placeholder, symlinked, or group/world-readable Discord secrets by default; use `--allow-placeholder-discord-secrets` only for source/sample validation.
- `2006Scape Server/data/accounts/` is ignored and stores PBKDF2 account JSON records for external auth; create records with `scripts/create-account.py username` and inspect or toggle them with `scripts/account-admin.py audit`, `list`, `show`, `disable`, and `enable`. The helper writes `PBKDF2WithHmacSHA256` by default, rejects passwords shorter than 12 characters unless `--allow-weak-password` is explicitly passed for local throwaway/source-validation accounts, and stamps `passwordPolicy` metadata on new or rotated records; `--algorithm sha1` exists only for older Java 8 runtimes that cannot verify SHA-256 PBKDF2 records. Optional metadata can be written with `--role`, `--allowed-character`, and `--discord-user-id`; the Java auth service, account admin tool, and deployment verification reject malformed `roles`, `allowedCharacters`, and Discord user IDs before login/distribution. A non-empty `allowedCharacters` list is enforced as a character-name allow-list during Java auth. The Java auth service and Python helpers set owner-only permissions where the filesystem supports them, and deployment verification rejects account symlinks plus group/world-readable account directories or records on POSIX systems. When account auth is enabled with legacy fallback, fallback is only for missing account records; existing PBKDF2 records, disabled records, disallowed characters, invalid/tampered records, external-mode records below 120,000 PBKDF2 iterations, missing `passwordPolicy`, or weak-override password policy metadata are authoritative failures. Password verification uses each record's stored algorithm and iteration count; external iteration minimums are enforced separately before verification. Existing account-record audits cannot cryptographically prove the original plain-text password length, so create or rotate real external accounts through `scripts/create-account.py` instead of hand-writing hashes, then run `scripts/account-admin.py --require-password-policy audit` before deployment. The in-game `::password` command is blocked for account-authenticated sessions because it only edits the legacy character save token; rotate PBKDF2 account passwords out of game with `scripts/create-account.py --overwrite --preserve-metadata` or an equivalent operator workflow so roles, allowed characters, Discord user id, and disabled state are not dropped. Use `scripts/account-admin.py disable USERNAME` or `enable USERNAME` for access-control toggles that should not rotate a password. Repeated failed account-auth attempts are temporarily rate-limited per account and per connecting source address; missing-account attempts are source-throttled when legacy fallback is disabled. The in-memory throttle table is bounded and prunes expired entries. PBKDF2 account passwords are verified exactly as submitted and are not trimmed like legacy character passwords. PBKDF2 account passwords must not be copied into `data/characters/<name>.txt`; account-auth logins preserve the old legacy character-password token or generate a random account-auth-only placeholder for new characters.
- Treat `2006Scape Server/data/characters/`, `data/accounts/`, and `data/secrets.json` as operator-owned runtime data on deployed hosts. Before replacing deployment files, rotating credentials, migrating config, or intentionally restarting into new deployment bits, prefer `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"` on the deployed host; pass its generated proof note to readiness tooling with `--runtime-data-backup-proof-file PATH`, or pass `--proof-manifest PATH` when a copied deployment proof manifest should have its `runtime_data_backup_proof_file` field updated automatically. The helper writes an archive plus proof note, refuses symlinked runtime-data and output/manifest paths, records the readiness argument, and records that it did not start, stop, or restart the runtime.
- Do not commit generated `target/` directories, logs, local configs, secrets, or built jars.

External-player deployments must read `docs/deployment-networking.md`. The current Java client uses plaintext sockets. `direct_tcp` is the simplest public mode and must explicitly set `require_secure_external_transport=false`, `secure_external_transport_confirmed=false`, and `direct_tcp_external_transport_confirmed=true`; Tailscale/WireGuard/VPN/client TLS tunnel modes are the encrypted/private options and require `require_secure_external_transport=true` plus `secure_external_transport_confirmed=true`. When `external_players_enabled=true`, startup requires PBKDF2 account auth with `account_auth_enabled=true`, `account_auth_auto_create=false`, `account_auth_legacy_fallback=false`, and `account_auth_pbkdf2_iterations>=120000`, plus a valid `external_transport_mode` and a non-loopback/non-wildcard `public_game_host`. Direct TCP and overlay VPN modes also require at least one non-loopback game bind host, and when `file_server=true` at least one non-loopback HTTP/JAGGRAB cache bind host; `client_tls_tunnel` may use loopback-only game/cache binds because the server-side tunnel forwards encrypted external traffic into local listeners. Java startup also validates typed bind-host config, effective game/cache ports, rejects overlapping listener ports when `file_server=true`, treats HTTP cache bind failure as fatal in external-player mode, rejects wildcard bind hosts unless `wildcard_bind_confirmed=true`, rejects listener arrays that mix wildcard hosts with specific hosts, and keeps `agent_bridge_bind_host` loopback-only with a non-overlapping `agent_bridge_port`. The transport fields are operator acknowledgements, not a substitute for deploying firewall/VPN/tunnel controls. Explicit `-c` / `-config` files fail closed if they cannot be read or validated. Use plural bind arrays such as `game_bind_hosts`, `http_bind_hosts`, and `jaggrab_bind_hosts` to bind both `127.0.0.1` and the selected non-loopback interface when the same server process should accept local and external clients. For `client_tls_tunnel`, package clients against `client_connect_host` or the default `127.0.0.1`; `public_game_host` remains the remote TLS endpoint checked by deployment tooling. Run `scripts/preflight-external-config.py "2006Scape Server/ServerConfig.json"` before starting a remote server. Prefer `scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"` to package the downloadable client, render operator-side tunnel templates and server-side systemd/firewall/player-handoff templates when needed, and write the redacted readiness report without starting or stopping anything; add `--json-output PATH` when automation or handoff notes need machine-readable status and proof coverage. In that report, `status: PASS` is command status; `deploymentProofStatus` and the proof coverage table show whether live network/login/client/chat/backup/Discord evidence is still missing. `--require-full-proof` is only for final deployment gates and refuses source/test-only allowances such as placeholder config/secrets, empty account dirs, or untrusted TLS checks. The lower-level path remains `CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" scripts/package-client.sh`, then `scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment` or `scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment` before distribution when the server bundle exists. These checks verify the folder, exact checksum manifest, matching zip archive, macOS double-click `.command` wrappers, macOS/Linux launcher/setup-checker executable metadata, Windows launch/check CRLF endings, non-placeholder public/bind hosts, `client.properties` `secure.transport`, setup-checker Java/config/TCP guidance, and optional systemd/env/firewall/README/player-handoff server deployment artifacts. `client_tls_tunnel` packages include `client-tls-tunnel/README.txt` and `client-tls-tunnel/stunnel-client.conf`; the prepare wrapper also writes `client-tls-tunnel-operator/` for the server-side stunnel template and `server-deployment/` for systemd, env, copied config, dry-run UFW examples, and `player-handoff-template.md`. After preparing the bundle, use `scripts/provision-player-account.py PLAYER --character CHARACTER --prepared-dir dist/external-deployment` to create the ignored PBKDF2 account record, audit it, write the generated password only to an owner-only ignored credentials env file, and render a safe per-player note. Then use `scripts/package-player-kit.py PLAYER --character CHARACTER --prepared-dir dist/external-deployment` to create the public-safe player zip with the client archive, README-first handoff note, and checksums while excluding passwords, private credentials, account records, secrets, runtime data, and bridge tokens. Before sending that zip, use `scripts/verify-player-kit.py --kit dist/external-deployment/player-kit-PLAYER.zip --prepared-dir dist/external-deployment --username PLAYER --character CHARACTER` to re-check the copied artifact, embedded checksums, nested client archive, and absence of private files. Use `scripts/render-player-handoff.py --prepared-dir dist/external-deployment --username PLAYER --character CHARACTER` when the account already exists and only the note is needed. Do not send account JSON files, secrets, runtime backup archives, bridge tokens, claim nonces, API keys, or Discord bot tokens. Manual `CLIENT_SERVER_HOST` package overrides for non-local hosts require an allowed `CLIENT_SECURE_TRANSPORT` value: `direct_tcp`, `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`; wildcard client targets are rejected. If broad `0.0.0.0` binds are intentional, set `wildcard_bind_confirmed=true`, run preflight/verify with `--allow-wildcard-bind`, package with `CLIENT_ALLOW_WILDCARD_BIND=1`, and do not mix wildcard with specific hosts in that listener array. `--allow-placeholder-network-config` is only for tracked sample/source validation. Add `--live` only after the remote server is intentionally running; for `client_tls_tunnel`, that live check must complete TLS handshakes to the public game/cache tunnel endpoints, with `--tls-sni-host` available for deliberate certificate-name differences. Pair `--live-login-*` with `--live-local-login-*` to keep one external PBKDF2 login open while proving a same-host local PBKDF2 login; `--live-local-host` must stay `localhost` or a loopback IP address. Use `--live-reject-login-*` with a wrong password, missing account, or disabled throwaway account plus `--live-reject-login-expected-statuses 3,4` to prove fail-closed auth over the same live path for final readiness. Back up deployed runtime data with `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"` and pass `--runtime-data-backup-proof-file`. Prove direct player chatbox delivery with `scripts/verify-agent-chat-log.py --event agent_chat_player_delivery --text-contains MARKER --to-type player --to-name PLAYER --delivered-to PLAYER --no-undelivered --channel agent`, then pass `--agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER` to readiness/prep. Use `scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --discord-message-id DISCORD_MESSAGE_ID --channel agent`, or readiness-report `--agent-chat-log-from-type discord --agent-chat-log-from-bot false --agent-chat-log-discord-message-id DISCORD_MESSAGE_ID`, after a real human/non-bot Discord test message to prove the running server ingested chat into AgentChatService when the Discord id is available. Use `scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE`, or readiness-report `--discord-channel-message-*`, after a real in-game/agent marker to prove server-to-Discord mirroring; by default it only accepts bot-authored messages. Never expose the loopback agent bridge publicly. Use `scripts/validate-network-auth-chat.sh` for source-side validation without restarting the live runtime.

- For encrypted-only player packages, add `--require-encrypted-external` to `scripts/prepare-external-deployment.py` or set `CLIENT_REQUIRE_ENCRYPTED_EXTERNAL=1` for direct `scripts/package-client.sh` calls. This allows Tailscale, WireGuard/VPN, and `client_tls_tunnel`, and refuses plaintext `direct_tcp` before a downloadable client zip is written.

- For chat proof collection, prefer adding `--proof-manifest PATH` to `scripts/verify-agent-chat-log.py` and `scripts/verify-discord-channel-message.py`; successful direct-delivery, Discord-ingress, blocked-routing, and Discord-mirror checks update only their matching proof-manifest fields and do not touch runtime.

- For final readiness evidence, copy `server-deployment/proof-templates/deployment-proof-manifest.json`, replace placeholders, remove unused Discord fields, check it with `scripts/check-deployment-proof-manifest.py PATH --config "2006Scape Server/ServerConfig.json" --secrets "2006Scape Server/data/secrets.json" --require-full-proof --check-files`, and pass it with `--proof-manifest PATH` to `scripts/deployment-readiness-report.py` or `scripts/prepare-external-deployment.py`. Use readiness-report `--update-proof-manifest PATH` after successful live proof runs when supplied live fields should be written into a copied manifest that may still contain unrelated placeholders. With `--check-files`, the manifest checker validates desktop proof evidence, runtime-backup archive/checksum details, and the encrypted/private transport gate, not just path existence. Final-gate manifests must keep `require_full_proof:true` and `require_encrypted_external:true` in the manifest itself so handoff evidence stays self-describing. `prepare-external-deployment.py --require-full-proof` also runs the proof check against merged manifest plus CLI values before packaging, including proof-file, password-env, encrypted-transport, and `live_reject_login_expected_statuses` presence. Keep passwords, bridge tokens, Discord tokens, and secrets out of the manifest; use password environment-variable names only. CLI flags override manifest fields for one-off reruns.
- To re-check an existing readiness JSON without rerunning deployment checks or touching runtime, use `scripts/deployment-readiness-status.py --readiness-json PATH` or `--prepared-dir dist/external-deployment`; add `--show-next-commands` for read-only command templates covering missing live/manual proof. Those templates preserve the report's config, account, secret, client, and deployment paths, create the proof manifest parent directory, copy the template only when the manifest is missing, write manual proof notes beside that manifest, pass that manifest to the desktop-proof, runtime-backup, direct chat, and Discord chat proof helpers with `--proof-manifest`, add `--update-proof-manifest` to live readiness reports after successful checks, and add `--secrets` to the final manifest check so Discord routing-filter requirements are considered. Add `--fail-if-not-ready` when a wrapper should fail until `deploymentProofStatus` proves full external readiness.
- After final readiness proof is collected, `scripts/package-deployment-proof.py --prepared-dir dist/external-deployment` can create a non-secret handoff tarball from the normal prepared deployment output. Add `--require-full-proof` for the final external-ready handoff; it fails unless the readiness JSON records a full live proof status and the proof manifest passes full-proof, encrypted-transport, and proof-file validation. If lower-level commands wrote artifacts elsewhere, pass explicit readiness, manifest, client, and server-deployment paths. The bundle includes readiness reports, proof notes, and selected client/server metadata including `player-handoff-template.md`, and deliberately excludes runtime backup archives, character saves, account records, `data/secrets.json`, passwords, bridge tokens, and Discord bot tokens.
- For focused live network proof, use `scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"` after the remote server is intentionally running. It checks public game/cache reachability and confirms the agent bridge is not reachable externally without packaging, logging in, starting, stopping, or restarting runtime; it complements, but does not replace, the full verifier/readiness report.
- For remote player-agent mode, package `agent.bridge.url` through `CLIENT_AGENT_BRIDGE_URL` or an ignored config key such as `agent_bridge_public_url`, render the HTTPS gateway with `scripts/render-agent-bridge-gateway-config.py`, and prove it with `scripts/probe-agent-bridge-gateway.py --gateway-url https://AGENT_GATEWAY_HOST`. Never expose raw TCP `43610`.
- For focused protocol-level local/external coexistence proof, use `scripts/probe-concurrent-logins.py --external-host HOST --external-username EXTERNAL_TEST --external-password-env EXTERNAL_PASSWORD --local-host 127.0.0.1 --local-username LOCAL_TEST --local-password-env LOCAL_PASSWORD`; add `--tls --tls-sni-host HOST` for public `client_tls_tunnel` endpoints. This keeps the external login socket open while proving a same-host loopback login, but it does not replace the final desktop-client coexistence proof file. After a real same-host Java client and external Java client are online together, prefer `scripts/write-desktop-client-proof.py --same-host-client LOCAL --external-client EXTERNAL --transport TRANSPORT --public-host HOST --evidence PATH`; add `--proof-manifest PATH` when a copied deployment proof manifest should have its `desktop_client_proof_file` updated automatically. It validates the existing evidence file and writes the `--desktop-client-proof-file` note without starting, stopping, restarting, logging in, or probing anything.
- For `client_tls_tunnel`, packaged client `server.host` must be localhost/loopback because the Java client still speaks plaintext to a player-side local tunnel. `public_game_host` is the remote TLS endpoint for deployment checks, not the client jar's direct socket target. Packaged launchers try to start the bundled player-side stunnel config automatically when `stunnel` is installed, and still print a manual fallback when it is not. macOS packages include `Run-2006Scape.command` and `Check-Setup.command` double-click wrappers that delegate to the shared shell scripts. The macOS/Linux setup checker can start the bundled stunnel config temporarily for no-login TCP diagnostics; the Windows checker expects the local tunnel endpoint to be reachable first.
- Packaged client verification also requires transport-specific top-level README setup guidance, setup-checker scripts that print config and test TCP reachability without logging in, operator-provided login guidance, a no-password-reuse warning, and a `public_game_host` entry in `MANIFEST.txt` so operators can distinguish the Java socket target from the encrypted remote endpoint.
- Readiness/prep reports reject weak proof arguments and inspect the supplied config. Direct player chatbox delivery proof is required even with Discord disabled: `--agent-chat-delivery-log-text` must be paired with `--agent-chat-delivery-log-to-name`, and the log event must be `agent_chat_player_delivery`. When `agent_chat_discord_enabled=true`, missing Discord bot/channel, Discord-to-server, or server-to-Discord proof keeps `deploymentProofStatus` partial. `--agent-chat-log-text` must be paired with `--agent-chat-log-from-type discord --agent-chat-log-from-bot false`, and server-to-Discord proof must not use `--discord-channel-message-allow-human-author`. If Discord routing allow-lists are configured, full Discord readiness also requires `--agent-chat-blocked-log-text BLOCKED_MARKER` or `scripts/verify-agent-chat-log.py --expect-absent` proof that a blocked human/non-bot marker did not enter `AgentChatService`.
- Network host and transport values must be single-line strings. Java startup, `preflight-external-config.py`, `package-client.sh`, and the stunnel renderer reject control characters before using them as listener addresses or writing distributable `client.properties`, manifest, or tunnel config files.

Per-agent Discord bot secrets are ignored under `data/secrets.json` key `agent-discord-bots`; do not print, log, or commit tokens. Keep the real secrets file owner-only on POSIX systems, not symlinked, and at most one bot entry per agent/profile name; runtime loading refuses symlinked secrets and tightens regular files to owner-only, deployment verification rejects duplicates or too-open secret files, and the runtime keeps the first usable bot config if duplicates are accidentally present. Malformed bot configs are ignored rather than coerced, including object allow lists, empty explicit allow lists, non-string fields, and non-boolean `allowBroadcast`. `DiscordAgentTransport` mirrors `AgentChatService` messages only, escapes Discord mentions in mirrored output, and must not execute gameplay or write player packets from Discord callbacks. `agent_chat_log_enabled=true` writes sanitized structured chat envelopes under `data/logs/agent-chat/<yyyy-MM-dd>/agent-chat.jsonl` for routing/debug audit.

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
