---
name: 2006scape
description: "Use as the single entry skill for work in $REPO_ROOT, especially when a task broadly mentions 2006Scape or the right specialized workflow is unclear. Provides routing guidance, boundaries, starter commands, and child-skill pointers for runtime/bridge sessions, script discovery, route exploration, route-planner/ML graph development, object transitions, frontier exploration, compact screenshots, gameplay progression, custom quests/shops/gameplay content, profile-scoped character memories/goals, cache maps, map visualization, session logs, bridge-tool development, and general repo editing without preloading every specialized skill body."
---

# 2006Scape

Use this as the umbrella skill for `$REPO_ROOT`. Load this first when a task is broadly about 2006Scape or when you are unsure which repo-local skill applies.

## How To Use This Skill

Skill links are routing pointers, not inherited context. Available skills expose their `name`, `description`, and `path`; the full body of a child `SKILL.md` is read only when the agent chooses that child skill. Keep this file useful enough to orient a new agent, then load the smallest relevant child skill before doing specialized work.

Other agents may be editing code or playing the game. Keep work scoped to the user's task, avoid process restarts unless requested, and do not touch runtime/game code when the task is only about skills or docs. Never interrupt another player's active automation, movement, skilling, combat, trade, or interface state in order to make your task faster. If another player must participate, make the request from your controlled profile and wait patiently; only control, stop, move, bank, or close interfaces on the other profile when the user explicitly names that profile and asks you to take it over.

Always keep bridge tokens, API keys, saved-character secrets, passwords, and nonces out of messages, logs, screenshots, and committed files.

## Profile-Agnostic Tool Rule

The legacy default local gameplay profile exists for backward compatibility only. Any new or modified tool, runner, wrapper, status command, map renderer, log reader, or skill workflow must work for any selected profile unless the user explicitly asks for a one-off profile-specific check.

- Accept `--profile PROFILE` or honor `RS_PROFILE`/`RSBRIDGE_PROFILE`, and pass the resolved profile through to child processes, bridge calls, route trace readers, map helpers, and evidence writers. Set `RS_TRACE_PROFILE` when reading profile-filtered movement traces.
- Write mutable local artifacts under profile-scoped names or directories, or include `profile`, `playerName`, and `sessionId` metadata when data is intentionally shared.
- Treat legacy default-profile paths, especially the default bridge session file, as compatibility read fallbacks only. Do not create new profile-specific defaults.
- Keep Java bridge additions primitive and player/session scoped; put route, skilling, combat, banking, and recovery strategy in Python scripts and data that resolve the selected profile at their boundary.

## Context Budget Rule

For live gameplay and navigation, use the smallest state surface that can support the next decision. Use XXS for confirmation, status, health, position, and stable polling: `observe_XXS.sh`, `rs.observe_state_XXS`, `rs.observe_state_if_changed_XXS`, and `rs-tool_XXS.sh`. Use XS when planning needs compact inventory, equipment, bank, nearby NPC/object, route, or skill context; use `bank_item_count_XS` for exact counts of specific bank items. Use full/legacy tools only for a named missing field, evidence capture, or debugging a new workflow. Do not call full `observe_state`, `observe-slim.sh`, or base `rs-tool.sh` in normal loops or immediately after every compact action result just to be safe; treat compact batch/tool results as the next observation whenever they include the state needed for the next decision. Direct `rs-tool.sh observe_state` is blocked unless `RS_ALLOW_FULL_OBSERVE=1` is set for an explicit debug/evidence command.

For Python runners, prefer `bridge_script.observe_xxs()` for confirmation or `bridge_script.observe_xs()`/`bridge_script.observe()` for compact decision state, and carry forward compact `player` results from action/wait tools. Use `bridge_script.observe_full()` only for complete bank contents, complete evidence, profile/personality context, or a named missing field; do not print the full result into the Codex context unless that is the actual evidence being collected.

When a live route fails near a building, door, gate, ladder, or other object blocker, do not leave the fix as a one-off manual recovery. Inspect compact nearby object evidence first, then use server data such as `2006Scape Server/data/doors.json`, context maps, or passive traces to identify the exact object id/tile/approach/post-state. Once proved, encode the transition in the runner or a location-specific `bridge_script` helper and document it in `2006scape-object-transitions` or `scripting-primitives.md` so the next run uses the learned primitive automatically.

## Skill Router

| Need | Read | Good first move | Boundary |
| --- | --- | --- | --- |
| General repo edits, Java/Maven work, maintenance, tests, code review, or durable lessons | `.codex/skills/2006scape-dev-editing/SKILL.md` | Read `AGENTS.md`; for edits, inspect `references/actionable-lessons.md` when relevant | Do not touch unrelated dirty files or add broad lessons from stale context |
| Modern OSRS reference lookups for item, NPC, object, quest, location, or mechanic names | `.codex/skills/2006scape-osrs-wiki/SKILL.md` | Search the wiki for exact modern OSRS names first, then verify against local cache/server data | Treat the wiki as a modern hint source only; it may describe content that does not exist or differs in 2006Scape |
| Custom gameplay content, quests, shop/store stock or price changes, rewards, NPC/object/item interactions, guides, or the customization ledger | `.codex/skills/2006scape-custom-content/SKILL.md` | Read `docs/custom-game-changes.md`, the custom content README, and targeted quest/shop docs | Keep feature code under `com.rs2.game.content.custom`; core hooks generic and minimal; update tests and the ledger |
| Starting, stopping, relaunching, diagnosing, or claiming the local server/client/bridge runtime | `.codex/skills/2006scape-local-runtime/SKILL.md` | `python3 agent-navigation/tools/runtime_doctor.py status --observe` | Do not kill/restart active runtimes unless asked or clearly stale; keep profile sessions scoped; never print tokens |
| Adding, debugging, reviewing, or documenting `rs.*` bridge primitives or compatibility tools | `.codex/skills/2006scape-agent-bridge-dev/SKILL.md` | Read `agent-navigation/scripting-primitives.md`, then inspect `AgentActionService`, `AgentToolService`, and `CodexAppServerClient` | Prefer external scripts for strategy; build success is not live proof; restart through `runtime_doctor.py` only when live validation is requested |
| External-player networking, standalone client packaging, account auth, direct_tcp/secure transport design, deployment readiness, runtime-data backup proof, Discord transport proof, or remote VPS/GCE/Tailscale/WireGuard/client_tls_tunnel setup | `.codex/skills/2006scape-external-deployment/SKILL.md` plus `.codex/skills/2006scape-agent-bridge-dev/SKILL.md` only when changing bridge primitives | For first setup, read `docs/external-deployment-quickstart.md`; use `docs/network-auth-agent-chat-design.md` or `docs/deployment-networking.md` for deeper detail, then inspect `FileServer`, `ConfigLoader`, `Main`, `LoginSession`, `AgentChatService`, and `DiscordAgentTransport` as needed | Keep local dev defaults intact; do not expose `AgentBridgeServer`; source/static checks are not live readiness; restart only for explicit live proof |
| Live route exploration, route DB edits, hazards, blockers, doors, gates, stairs, trapdoors, or topology from navigation data | `.codex/skills/2006scape-route-agent/SKILL.md` | `agent-navigation/tools/observe_XS.sh`, then prefer `agent-navigation/ml2-routing/route_ml_XS.py define` for A-to-B routing | Use bridge tools only; do not use admin teleports, direct state edits, or visual guesses without evidence |
| Route-planner implementation, graph semantics, `router.py`, `route_runner.py`, passive trace weighting, reverse edges, coordinate targets, ML/GNN route planning, cache-direct candidates, planner evaluation, route-definition API, or route feedback capture | `.codex/skills/2006scape-route-planner-dev/SKILL.md` | `python3 agent-navigation/ml2-routing/route_ml_XS.py define --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled` | Keep learned models explainable and constrained by deterministic safety gates; frontier-only routes are not complete benchmark wins |
| Doors, gates, ladders, trapdoors, stairs, ships, portals, tolls, or member gates | `.codex/skills/2006scape-object-transitions/SKILL.md` | Observe XS state, identify object id/tile, preview/walk to interaction target, interact once, then prove post-state; use full state only when a proof field is missing | Do not model object transitions as ordinary walk edges or accept a successful click as proof |
| Live unknown-area expansion, short probes, frontier naming, coordinate targets, and hazard/death evidence | `.codex/skills/2006scape-frontier-exploration/SKILL.md` | `python3 agent-navigation/ml2-routing/route_ml_XS.py define --from X,Y,H --to TARGET --combat-level N --food N --run-energy N --run-enabled` | Avoid destination gambling; every probe should produce reusable route, blocker, hazard, or frontier evidence |
| Compact visual debugging of the live Java client | `.codex/skills/2006scape-screenshot-capture/SKILL.md` | `agent-navigation/tools/capture-cardinal-screenshots.sh --prefix reason` | Prefer `765x503` client captures; do not load full desktop screenshots unless compact capture fails |
| Normal gameplay progression through in-game mechanics | `.codex/skills/2006scape-gameplay-progression/SKILL.md` | `agent-navigation/tools/observe_XS.sh`, then search `script_registry.py` for a primitive-backed runner | Not for route DB schema edits, bridge source changes, spawned items, or direct player-state edits |
| Runner tick analysis, timing instrumentation, idle-gap profiling, item-arrival logs, or compact performance reports | `.codex/skills/2006scape-tick-analysis/SKILL.md` | `python3 agent-navigation/tools/tick_analysis_report.py --latest --runner seers-flax-spin-fast --profile PROFILE` | Do not add bridge observes just for logs; logging must be local and cheap |
| Intentional long-term memories, equipment goals, preferences, recurring blockers, or strategic reminders for one character | `.codex/skills/2006scape-character-memory/SKILL.md` | `python3 agent-navigation/tools/character_memory.py show --profile PROFILE --json` | Keep entries sparse and profile-scoped; route facts belong in nav data, routine progress belongs in session logs |
| Discovering or running repo helper scripts by fuzzy name, wildcard, tag, or metadata | `.codex/skills/2006scape-script-registry/SKILL.md` | `python3 agent-navigation/tools/script_registry.py search QUERY` | Keep script descriptions in `agent-navigation/data/script_registry.json`, not in this umbrella skill |
| Static cache-backed world map decoding/rendering, GameCache terrain/water/object/mapscene layers, bounded context maps, or map data export | `.codex/skills/2006scape-cache-map/SKILL.md` | For agent context, use `python3 agent-navigation/tools/render_agent_context_map_XS.py --center latest` | Do not recreate the retired screenshot/minimap fog sampler or require a live client for static map work |
| Map presentation, route overlays, topology styling, labels, legends, visual QA, recent-path/segment context maps, or sharing map images | `.codex/skills/2006scape-map-visualization/SKILL.md` | For agent segment context, use `python3 agent-navigation/tools/render_agent_context_map_XS.py --segment-from FROM_PLACE --segment-to TO_PLACE` | Do not restart gameplay runtime for visual-only work; use `cache-map` for renderer internals |
| Agent session logs, rollout transcript enrichment, Markdown summaries, reports, redaction, or profile/personality artifacts | `.codex/skills/2006scape-agent-session-logs/SKILL.md` | Read targeted `2006Scape Server/data/logs/agent-sessions/...` files and matching `~/.codex/sessions/.../rollout-*.jsonl` | Treat logs as evidence, not controls; do not expose secrets or mutate live gameplay |

## Starter Commands

Run these from the repo root only as orientation. Open the relevant child skill before making changes, restarting processes, or running live gameplay actions. Commands with uppercase placeholders need task-specific values.

```sh
# 2006scape-dev-editing: common validation after repo edits
mvn -q -DskipTests package
mvn -q clean test

# 2006scape-custom-content: focused custom content validation
mvn -q -pl "2006Scape Server" -Dtest=CustomContentTest test
mvn -q -pl "2006Scape Server" -Dtest=CustomShopsTest test

# 2006scape-local-runtime: inspect or repair the local runtime/bridge
python3 agent-navigation/tools/runtime_doctor.py status --observe
python3 agent-navigation/tools/runtime_doctor.py status --profile PROFILE --observe
python3 agent-navigation/tools/server_tick_report.py --json
python3 agent-navigation/tools/runtime_doctor.py claim --verify
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify

# 2006scape-agent-bridge-dev: prove bridge tools through the wrapper
agent-navigation/tools/observe_XXS.sh
agent-navigation/tools/observe_XS.sh
RS_PROFILE=PROFILE agent-navigation/tools/observe_XXS.sh
RS_PROFILE=PROFILE agent-navigation/tools/observe_XS.sh
agent-navigation/tools/rs-tool_XS.sh TOOL_NAME 'JSON_ARGS'
agent-navigation/tools/rs-tool_XXS.sh TOOL_NAME 'JSON_ARGS'
agent-navigation/tools/rs-tool_XXS.sh wait_until_combat_event_smart '{"maxTicks":50,"hpAtOrBelow":10}'
agent-navigation/tools/rs-tool_XXS.sh bury_bones '{}'
agent-navigation/tools/rs-tool_XXS.sh pickup_ground_item '{"itemId":ID,"maxDistance":8}'
agent-navigation/tools/rs-tool_XS.sh observe_state_XS '{}'
agent-navigation/tools/rs-tool_XS.sh observe_state_if_changed_XS '{"key":"agent-loop"}'
agent-navigation/tools/rs-tool_XS.sh combat_state_XS '{}'
agent-navigation/tools/rs-tool_XS.sh walk_to_tile_until_arrived_XS '{"x":X,"y":Y,"height":0,"maxTicks":95}'
agent-navigation/tools/rs-tool_XS.sh travel_to_landmark_until_arrived_XS '{"name":"PLACE","maxTicks":95}'
agent-navigation/tools/rs-tool_XS.sh wait_ticks_XS '{"ticks":5}'
agent-navigation/tools/rs-tool_XS.sh wait_until_idle_XS '{"maxTicks":120}'
agent-navigation/tools/rs-tool_XS.sh wait_until_combat_event_smart_XS '{"maxTicks":50,"hpAtOrBelow":10}'
agent-navigation/tools/rs-tool_XS.sh bury_bones_XS '{}'
agent-navigation/tools/rs-tool_XS.sh bank_item_count '{"names":["coal","iron ore"]}'
agent-navigation/tools/rs-tool_XS.sh deposit_inventory_items_XS '{"itemIds":[ID1,ID2],"keepFoodCount":N}'
agent-navigation/tools/rs-tool_XS.sh withdraw_bank_items_XS '{"itemId":ID,"amount":N}'
agent-navigation/tools/rs-tool_XS.sh withdraw_bank_items_XS '{"items":[{"itemId":440,"amount":9},{"itemId":453,"amount":18}]}'
agent-navigation/tools/rs-tool_XS.sh unequip_items_XS '{"slotNames":["weapon","shield"]}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_status '{"sinceId":0}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_send '{"message":"hello","channel":"agent"}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_send '{"message":"need a hand","agent":"OTHER_PROFILE"}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_send '{"message":"hello from the agent","player":"PLAYER_NAME"}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_read '{"sinceId":0,"limit":10}'
python3 agent-navigation/tools/agent_chat_XS.py --profile PROFILE send "hello"
python3 agent-navigation/tools/agent_chat_XS.py --profile PROFILE send "need a hand" --agent OTHER_PROFILE
python3 agent-navigation/tools/agent_chat_XS.py --profile PROFILE send "hello from the agent" --player PLAYER_NAME
agent-navigation/tools/rs-tool_XS.sh request_player_trade_XS '{"name":"OTHER_PROFILE","maxDistance":3,"autoWalk":true}'
agent-navigation/tools/rs-tool_XS.sh offer_trade_item_XS '{"itemId":995,"amount":100000}'
agent-navigation/tools/rs-tool_XS.sh accept_trade_XS '{"expectPartner":"OTHER_PROFILE","expectItemId":995,"minAmount":100000}'
agent-navigation/tools/rs-tool_XS.sh trade_status_XS '{}'
python3 agent-navigation/tools/receive_trade.py --profile PROFILE --from OTHER_PROFILE --item coins --min-amount 100000
python3 agent-navigation/tools/food_bank_XS.py
python3 agent-navigation/tools/object_search_XS.py --name NAME --max-distance 20
# Debug/evidence fallback only; do not use these in normal loops.
agent-navigation/tools/observe-slim.sh
RS_ALLOW_FULL_OBSERVE=1 agent-navigation/tools/rs-tool.sh observe_state '{}'
agent-navigation/tools/rs-tool.sh TOOL_NAME 'JSON_ARGS'

# External-player networking/auth/client packaging design
sed -n '1,260p' docs/external-deployment-quickstart.md
sed -n '1,260p' docs/network-auth-agent-chat-design.md
sed -n '1,260p' docs/deployment-networking.md
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.External.Sample.json"
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json"
scripts/validate-network-auth-chat.sh
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.External.Sample.json" scripts/package-client.sh
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json" CLIENT_ALLOW_PLACEHOLDER_NETWORK_CONFIG=1 scripts/package-client.sh
# Packaged launchers/checkers must keep Java-missing guidance, transport-specific setup text, operator-provided-login guidance, no-password-reuse warnings, external transport metadata, setup-check TCP diagnostics, `source_server_config_sha256`, `-no-java-warnings`, macOS double-click `.command` wrappers, executable macOS/Linux scripts, and CRLF Windows `.bat` line endings for external testers. `direct_tcp` packages connect to `public_game_host` over plaintext TCP; `client_tls_tunnel` packages connect to loopback, include player-side stunnel config, their launchers try to start stunnel automatically when installed, and the macOS/Linux setup checker can start stunnel temporarily for no-login diagnostics. Prepare/readiness should include `--client-tls-tunnel-dir` so operator-side stunnel templates are verified too. The server-side stunnel accept host and any `--tls-sni-host` certificate override must be specific/non-wildcard/non-placeholder so they do not collide with loopback Java listeners or ship unusable tunnel configs.
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.External.Sample.json" --allow-empty-accounts --allow-placeholder-network-config
# Manual CLIENT_SERVER_HOST overrides for non-local packages require CLIENT_SECURE_TRANSPORT (`direct_tcp`, `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`); wildcard client hosts and symlinked package output paths are rejected.
scripts/render-server-deployment-files.py --config "2006Scape Server/ServerConfig.External.Sample.json" --output-dir dist/server-deployment
# Generated server-deployment files must keep hardened systemd sandboxing, argument-quoted firewall/README commands, input validation plus verifier parsing for service names/paths/interfaces, owner-only account/secrets install guidance, runtime-data backup notes, and fill-in proof templates under the deployed `2006Scape Server/data/` tree.
scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"
scripts/backup-runtime-data.py --data-dir "2006Scape Server/data" --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/write-desktop-client-proof.py --same-host-client LOCAL --external-client EXTERNAL --transport TRANSPORT --public-host HOST --evidence PATH
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.External.Sample.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --allow-empty-accounts --allow-placeholder-network-config
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --client-tls-tunnel-dir dist/client-tls-tunnel-operator
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.External.Sample.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --allow-empty-accounts --allow-placeholder-network-config --json-output dist/deployment-readiness-report.json
scripts/deployment-readiness-status.py --readiness-json dist/deployment-readiness-report.json
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --desktop-client-proof-file PATH --runtime-data-backup-proof-file PATH
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --proof-manifest PATH
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --update-proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/check-deployment-proof-manifest.py PATH --config "2006Scape Server/ServerConfig.json" --secrets "2006Scape Server/data/secrets.json" --require-full-proof --check-files
scripts/package-deployment-proof.py --prepared-dir dist/external-deployment
scripts/deployment-readiness-status.py --prepared-dir dist/external-deployment --show-next-commands
scripts/deployment-readiness-status.py --prepared-dir dist/external-deployment --fail-if-not-ready
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER --agent-chat-delivery-log-channel agent
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --require-full-proof
# In readiness reports, `status: PASS` is command status; check `deploymentProofStatus` and `Proof Coverage` before calling a deployment live-ready.
# Add `--json-output PATH` when scripts or handoff notes need machine-readable proof coverage and remaining live-proof items.
# Use `--require-full-proof` only as a final deployment gate; it refuses placeholder/source-test allowances, and partial/static evidence reports should stay allowed while proof is being gathered.
# Complete live network/auth/client/chat/backup plus Discord round-trip proof reports `FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED`.
# Desktop proof files must name the same-host client, external client, external transport path, concurrent-online observation, and an `evidence` path to a real non-symlink screenshot/log file. Prefer `scripts/write-desktop-client-proof.py` after real clients are online together; it validates the existing evidence file and writes the proof note without touching runtime.
# Runtime data backup proof should usually come from `scripts/backup-runtime-data.py`; add `--proof-manifest PATH` when a copied proof manifest should have `runtime_data_backup_proof_file` filled automatically. It writes owner-only archive/proof files on POSIX systems, refuses symlinked runtime data and symlinked archive/proof/manifest output paths including output parent directories, and readiness validation rejects symlinked proof notes, checks proof/archive owner-only modes where supported, the archive path, `backup archive sha256`, required tar entries for characters/accounts/secrets, the no runtime start/stop/restart proof line, and the `readiness argument: --runtime-data-backup-proof-file ...` line.
# Proof bundles are handoff artifacts only; `package-deployment-proof.py` includes non-secret readiness/proof metadata and excludes runtime backup archives, character saves, account records, secrets, passwords, bridge tokens, and Discord bot tokens. Add `--require-full-proof` for the final external-ready bundle.
# Proof templates under `server-deployment/proof-templates/` must be copied and filled; unfilled placeholders are rejected. Prefer `deployment-proof-manifest.json` for final live/manual proof arguments, but store only password env var names, never password values or Discord tokens. Use `--update-proof-manifest PATH` on successful readiness-report live proof runs to write supplied proof fields into a copied manifest that may still contain unrelated placeholders. Final-gate manifests must keep `require_full_proof:true` in the manifest itself. Use the full `scripts/check-deployment-proof-manifest.py PATH --config ... --secrets ... --require-full-proof --check-files` form for a quick manifest completeness check that also validates Discord routing requirements plus desktop proof evidence and runtime-backup archive/checksum details; `prepare-external-deployment.py --require-full-proof` runs the merged proof check before packaging. This is not a substitute for live readiness proof.
# Manifest-owned proof-note file paths resolve relative to the manifest file unless absolute or overridden on the CLI, so normal `dist/external-deployment/` handoffs can keep proof notes beside `deployment-proof-manifest.json` and use short filenames.
# Direct agent/player chat delivery proof is required even when Discord is disabled; verify `agent_chat_player_delivery` and pass `--agent-chat-delivery-log-text` plus `--agent-chat-delivery-log-to-name` to readiness/prep.
# Live only after an intentional remote restart; add --live-local-login-* to prove concurrent external/local login, keep --live-local-host on localhost/loopback, and add --live-reject-login-* plus --live-reject-login-expected-statuses 3,4 to prove a pinned rejected account path.
# Use probe-deployment-network.py first when only public game/cache reachability plus agent bridge non-exposure need isolation; full verifier/readiness still records final deployment proof.
scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"
EXTERNAL_PASSWORD="throwaway external password" LOCAL_PASSWORD="throwaway local password" scripts/probe-concurrent-logins.py --external-host HOST --external-username EXTERNAL_TEST --external-password-env EXTERNAL_PASSWORD --local-host 127.0.0.1 --local-username LOCAL_TEST --local-password-env LOCAL_PASSWORD
scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/verify-agent-chat-log.py --event agent_chat_player_delivery --text-contains MARKER --to-type player --to-name PLAYER --delivered-to PLAYER --no-undelivered --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE --proof-manifest dist/external-deployment/deployment-proof-manifest.json
# This also checks packaged client integrity, rejects symlinked client package paths and symlink-type zip entries, zip launcher/setup-checker executable metadata, Windows launch/check CRLF endings, public host manifest metadata, Java/transport/setup-checker guidance, and, when present, PBKDF2 account shape, metadata, and owner-only POSIX permissions; if Discord is enabled, it checks secret-file permissions, one bot per agent/profile, typed bot fields, non-empty allow lists, and boolean allowBroadcast.
scripts/create-account.py USERNAME
# Real external accounts need 12+ character passwords; --allow-weak-password is only for local throwaway/source-validation records.
scripts/create-account.py USERNAME --algorithm sha1  # Compatibility fallback only for older Java 8 runtimes.
scripts/account-admin.py --require-password-policy audit
scripts/account-admin.py list --json
scripts/account-admin.py disable USERNAME
scripts/account-admin.py enable USERNAME

# 2006scape-route-agent: observe, route, validate, and render route topology
agent-navigation/tools/observe_XS.sh
python3 agent-navigation/ml2-routing/route_ml_XS.py define --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/ml2-routing/tools/execute_route_definition.py --route-definition agent-navigation/.local/ml2-route-definitions/ROUTE.json --run-mode auto --eat-at 10
python3 agent-navigation/tools/navdb_XS.py validate
python3 agent-navigation/tools/navdb_XS.py self-test
agent-navigation/tools/render_navigation_png.py --region all --output agent-navigation/.local/map-summaries/surface-routes.png

# 2006scape-route-planner-dev: graph planning and planner validation
python3 agent-navigation/ml2-routing/route_ml_XS.py define --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/ml2-routing/tools/execute_route_definition.py --route-definition agent-navigation/.local/ml2-route-definitions/ROUTE.json --run-mode auto --eat-at 10
python3 agent-navigation/ml2-routing/route_ml_XS.py route --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled --json
python3 agent-navigation/ml2-routing/route_ml_XS.py compare-maps --case CASE_NAME --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/ml2-routing/route_ml_XS.py record-outcome --route-id ROUTE_ID --from X,Y,H --to PLACE --status blocked --final X,Y,H --problem-kind enemy_contact --enemy-name NAME --enemy-level N --enemy-tile X,Y,H
python3 agent-navigation/tools/render_agent_context_map_XS.py --center X,Y,H --radius-tiles 72 --pixels-per-tile 5 --recent-seconds 60
python3 agent-navigation/tools/navdb_XS.py graph-summary
python3 agent-navigation/tools/navdb_XS.py trace-tests

# 2006scape-object-transitions: prove object-chain blockers
agent-navigation/tools/rs-tool_XS.sh find_nearest_object '{"name":"gate","maxDistance":20}'
agent-navigation/tools/rs-tool_XS.sh preview_local_path '{"x":X,"y":Y,"height":0,"moveNear":true,"applyBounds":true,"maxWalkDistance":48}'
agent-navigation/tools/rs-tool_XS.sh object_transition_step_XS '{"objectId":OBJECT_ID,"x":X,"y":Y,"option":"first","maxTicks":20}'

# 2006scape-frontier-exploration: probe unknown graph edges
python3 agent-navigation/ml2-routing/route_ml_XS.py define --from X,Y,H --to TARGET --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/ml2-routing/tools/execute_route_definition.py --route-definition agent-navigation/.local/ml2-route-definitions/ROUTE.json --run-mode auto --eat-at 10
agent-navigation/tools/rs-tool_XS.sh walk_to_tile_until_arrived_XS '{"x":X,"y":Y,"height":H,"maxTicks":60,"maxWalkDistance":32,"stopOnStall":true,"stopOnCombat":true}'

# 2006scape-screenshot-capture: compact visual evidence
agent-navigation/tools/capture-cardinal-screenshots.sh --prefix reason
agent-navigation/tools/capture-client-screenshot.sh --prefix reason --native-size

# 2006scape-gameplay-progression: normal gameplay through rs tools
agent-navigation/tools/observe_XS.sh
python3 agent-navigation/tools/script_registry.py search combat
python3 agent-navigation/tools/cowhide_combat_runner.py --status
python3 agent-navigation/tools/cowhide_combat_runner.py --request-stop
python3 agent-navigation/tools/mining_runner.py --target-mining-level 20 --auto-buy-bronze-pickaxe
python3 agent-navigation/tools/combat_runner.py --npc goblin --target-level 10 --quiet
python3 agent-navigation/tools/bank_loadout.py --preset cowhide-trip --dry-run --json
python3 agent-navigation/tools/food_runner.py --mode fish-cook --quiet
python3 agent-navigation/tools/catherby_food_runner.py --cycles 1 --quiet
python3 agent-navigation/tools/catherby_food_runner_XS.py --profile PROFILE
python3 agent-navigation/tools/runner_status_XS.py --profile PROFILE
python3 agent-navigation/tools/catherby_food_runner.py --efficiency-report --quiet
python3 agent-navigation/tools/smithing_runner.py --mode smith --item sword --amount 10
python3 agent-navigation/tools/woodcutting_runner.py --tree oak --stop-when-inventory-full --quiet

# 2006scape-character-memory: sparse profile-scoped memories and goals
python3 agent-navigation/tools/character_memory.py show --profile PROFILE --json
python3 agent-navigation/tools/character_memory.py remember --profile PROFILE --kind resource --priority high --tags equipment --text "A better axe is a useful near-term upgrade before long woodcutting or fletching sessions."
python3 agent-navigation/tools/character_memory.py goal --profile PROFILE --priority normal --tags gear --text "Upgrade from a bronze axe when the character has enough coins and shop access."

# 2006scape-script-registry: discover or run known helper scripts
python3 agent-navigation/tools/script_registry.py list
python3 agent-navigation/tools/script_registry.py search "agility"
python3 agent-navigation/tools/script_registry.py search "mining"
python3 agent-navigation/tools/script_registry.py search "fletching"
python3 agent-navigation/tools/script_registry.py search "woodcutting"
python3 agent-navigation/tools/script_registry.py search "combat"
python3 agent-navigation/tools/script_registry.py search "food"
python3 agent-navigation/tools/script_registry.py search "smithing"
python3 agent-navigation/tools/script_registry.py search "bank"
python3 agent-navigation/tools/script_registry.py search "chat"
python3 agent-navigation/tools/script_registry.py search "backup"
python3 agent-navigation/tools/script_registry.py search "cowhide"
python3 agent-navigation/tools/script_registry.py search "memory"
python3 agent-navigation/tools/script_registry.py show route --json
python3 agent-navigation/tools/script_registry.py show agent_chat_xs --json
python3 agent-navigation/tools/script_registry.py run agility -- --laps 10

# 2006scape-cache-map: static cache-backed map rendering
agent-navigation/tools/cache_world_map.py --bounds 3200,3200,3210,3210 --output /tmp/2006scape-cache-map-smoke.png --summary /tmp/2006scape-cache-map-smoke.json
agent-navigation/tools/cache_world_map.py --bounds all --pixels-per-tile 4 --labels --output agent-navigation/topology/cache-world-map-full.png --summary agent-navigation/.local/map-summaries/cache-world-map-full.json
python3 agent-navigation/tools/map_grid.py locate --tile X,Y,H
python3 agent-navigation/tools/render_agent_context_map_XS.py --center latest
python3 agent-navigation/tools/render_agent_context_map_XS.py --grid-cell AU21 --grid-padding-tiles 4

# 2006scape-map-visualization: canonical map visuals
agent-navigation/tools/render_profile_map.py
agent-navigation/tools/render_heat_map.py
agent-navigation/tools/render_fog_map.py
agent-navigation/tools/active_map_refresher.py status
python3 agent-navigation/tools/render_agent_context_map_XS.py --segment-from FROM_PLACE --segment-to TO_PLACE

# 2006scape-agent-session-logs: inspect logs and summarize event types
python3 agent-navigation/tools/agent_session_XS.py --profile PROFILE --latest
find "2006Scape Server/data/logs/agent-sessions" -type f | sort
sed -n '1,220p' "2006Scape Server/data/logs/agent-sessions/DATE/SESSION.md"
jq -r '.event' "2006Scape Server/data/logs/agent-sessions/DATE/SESSION.jsonl" | sort | uniq -c
```

## Default Starting Points

For read-only questions, inspect the relevant docs or source first and answer without changing files.

For file edits, use `2006scape-dev-editing` plus the subsystem skill. Keep edits away from unrelated dirty files and preserve generated/local-only files.

When a task needs modern OSRS context for naming, requirements, or likely item/object locations, load `2006scape-osrs-wiki` first, but keep verifying against this repo's actual behavior.

For live navigation, use XXS/XS tool surfaces by default: XXS for repeated confirmation and survival/status checks, XS for route planning and compact decision context. Main route surfaces are `observe_XXS.sh`, `observe_XS.sh`, dynamic `rs.observe_state_XXS`, dynamic `rs.observe_state_if_changed_XXS`, dynamic `rs.observe_state_XS`, dynamic `rs.observe_state_if_changed_XS`, dynamic `rs.combat_state_XS`, dynamic `rs.walk_path_steps_XS`, dynamic `rs.walk_path_steps_XXS`, dynamic `rs.walk_to_tile_until_arrived_XS`, dynamic `rs.walk_to_tile_until_arrived_XXS`, dynamic `rs.travel_to_landmark_until_arrived_XS`, dynamic `rs.travel_to_landmark_until_arrived_XXS`, dynamic `rs.wait_ticks_XS`, dynamic `rs.wait_ticks_XXS`, dynamic `rs.wait_until_idle_XS`, dynamic `rs.wait_until_idle_XXS`, dynamic `rs.wait_until_combat_event_smart_XS`, dynamic `rs.wait_until_combat_event_smart_XXS`, dynamic `rs.object_transition_step_XS`, dynamic `rs.object_transition_step_XXS`, `rs-tool_XS.sh`, `rs-tool_XXS.sh`, `agent-navigation/ml2-routing/route_ml_XS.py`, `navdb_XS.py`, `route_failure_XS.py`, and `render_agent_context_map_XS.py`. The full tools remain available only when compact output omits a specific field needed for debugging, evidence capture, or a new workflow.

ML2 is the preferred A-to-B routing method for surface routes and same-cache-area underground routes: `agent-navigation/ml2-routing/route_ml_XS.py define --from X,Y,H --to PLACE_OR_TILE ...`. Use it after `observe_XS` whenever the character needs to travel to a known same-layer place or coordinate target. Treat the returned `2006scape.route-definition` as the routing contract: inspect `decision`, `status`, `evidence`, `safety`, `steps`, `run`, and `cmd`; if `cmd` is present, run it when live movement is intended. The XS route definition intentionally omits developer-only `quality`, wrong-way, and detour fields so normal agents do not overreact to planner internals. `safety.review=true` means pay attention to the note, not that the route is rejected.

ML2 route steps can include typed `object_transition` steps for known inline doors/gates/stairs/ladders; execute the returned command rather than flattening them into walk tiles. If `status` is `requires-object-transition`, identify the door/ladder/stairs/trapdoor/entrance/gate and use `object_transition_step_XS` or the existing object-transition workflow before requesting the next route on the destination layer or underground area. For low-level White Wolf Mountain crossings, route/cross to `taverley_white_wolf_gate_west_side` first, then request `catherby_bank` with run enabled and at least 70 run energy; execute only when the returned definition includes `cmd`. If `status` is `unsupported-coordinate-layer`, do not execute it; the tile is outside a supported cache route area. `evidence.proven=false` is not a rejection when `status=ok`, `cmd` is present, and `safety.review=false`; it means model/cache-planned but not player-proven yet.

The returned command uses `agent-navigation/ml2-routing/tools/execute_route_definition.py --route-definition ...`, treats selected walk steps as guide rails with bounded lookahead by default, stops before typed object transitions, defaults to `--eat-at 10`, observes nearby NPC context on combat/HP loss, and writes route evidence; use `--no-lookahead` only for deliberate old one-step diagnostics. On movement failure or recovery, read `route_failure_XS.py` before loading full evidence JSONL. The old bare Route Runner method and ML1 are deprecated for normal agent travel. Do not call `route_runner.py --to ...` as the routing API. Use `navdb_XS.py next-step`, `router.py plan`, `route_eval.py`, ML1, and `route_runner_XS.py --orient` only after loading `2006scape-route-planner-dev` for deliberate legacy diagnostics. `define` uses current route/place anchors even when the trained model artifact is older. Context-map JSON includes level-0 grid fields; use `map_grid.py locate --tile X,Y,H` for shorthand such as `AU21` and `render_agent_context_map_XS.py --grid-cell CELL` to request that exact cell. Use compact screenshots only for live visual ambiguity such as gate/door state, wrong-side positioning, object failures, or API/map disagreement.

For live gameplay, observe first and use XXS/XS bridge wrappers. The main dynamic-agent defaults are now `rs.observe_state_XXS`, `rs.observe_state_if_changed_XXS`, `rs.observe_state_XS`, `rs.observe_state_if_changed_XS`, `rs.combat_state_XXS`, `rs.combat_state_XS`, `rs.walk_path_steps_XS`, `rs.walk_to_tile_until_arrived_XS`, `rs.travel_to_landmark_until_arrived_XS`, `rs.wait_ticks_XS`, `rs.wait_until_idle_XS`, `rs.wait_until_combat_event_smart_XS`, `rs.object_transition_step_XS`, `rs.find_nearest_object_XS`, `rs.bury_bones_XS`, `rs.deposit_inventory_items_XS`, `rs.withdraw_bank_items_XS`, `rs.bank_item_count_XS`, `rs.agent_chat_send_XS`, `rs.agent_chat_read_XS`, `rs.agent_chat_status_XS`, `rs.unequip_items_XS`, and `rs.food_bank_XS`; use legacy full tools only when compact output omitted a specific field needed for evidence or debugging. Use `agent_chat_status_XS`/`agent_chat_read_XS` sparingly for coordination with agents/players, and `agent_chat_send_XS` when the task actually requires structured coordination; prefer `agent:"Name"` or `player:"Name"` alias fields for named targets, while generic callers can still use `to` plus `toType`. Target shortcuts are mutually exclusive: use either `agent`/`player` or generic `to` plus `toType`, not both. Players can send to the same bus with `::agentchat message`, `::agentchat @agent:Name message`, `::agentchat @player:Name message`, `::agentchat @all message`, or `::agentchat #channel message`, and direct player delivery is queued on the server tick so `agent_chat_send_XS` may return `deliveryPending:true`; if the target player is offline when the queue drains, later `agent_chat_read_XS` output records the target in `undeliveredTo`. Use XXS aliases such as `rs.set_run_XXS`, `rs.walk_path_steps_XXS`, `rs.wait_until_combat_event_smart_XXS`, `rs.wait_until_idle_XXS`, `rs.object_transition_step_XXS`, `rs.interact_object_XXS`, `rs.click_interface_button_XXS`, `rs.attack_npc_XXS`, `rs.eat_best_food_XXS`, `rs.pickup_ground_item_XXS`, `rs.bury_bones_XXS`, `rs.deposit_inventory_items_XXS`, `rs.withdraw_bank_items_XXS`, and `rs.unequip_items_XXS` when the next decision only needs confirmation plus critical survival state: tile, HP/max HP, run energy/enabled, combat, poison, death, free slots, food, and short XP deltas. Full `observe_state`, `observe-slim.sh`, and `rs-tool.sh` are not normal gameplay loop tools. `rs-tool_XS.sh TOOL ...` and `rs-tool_XXS.sh TOOL ...` append `_XS`/`_XXS` automatically for known compact aliases, so repo-side callers can pass either `wait_until_idle` or `wait_until_idle_XS`. `skillChanges` reports XP/base/current changes from the current call, and `xpRecent` keeps recent gains for a few minutes; XXS exposes these as a tiny `xp` array. Prayer `points`/`current` are current prayer points while `base` is the true XP-derived Prayer level, so bone burial may show base/XP gains without refilling points. `deposit_inventory_items_XS` accepts `itemIds` to deposit multiple item types at once and `keepFoodCount` to trim excess food safely. `withdraw_bank_items_XS` accepts legacy `itemIds`/`itemId` plus shared `amount`; for mixed exact quantities use `items:[{"itemId":440,"amount":9},{"itemId":453,"amount":18}]`. `bank_item_count_XS` answers exact bank counts for specific ids/names without full `observe_state`. `unequip_items_XS` accepts `equipmentSlots`, `slotNames`, `itemIds`, `names`/`items`, or `all=true` to unequip several items in one action. Prefer primitive/wait tools and treat their returned state as the next observation; during combat, prefer `wait_until_combat_event_smart_XXS` for HP/XP/event checks, `wait_until_combat_event_smart_XS` when loot or target detail matters, `pickup_ground_item_XXS` for selected drops, and `bury_bones_XS`/`XXS` for selected bones. If a long command is already running, wait near the expected completion interval before polling output instead of short-polling every few seconds. For manual route requests, use ML2 first and record feedback with `agent-navigation/ml2-routing/route_ml_XS.py record-outcome` for route-level problems like enemy contact, death, stalls, blockers, bad run policy, or wrong destinations. Some existing primitive-backed runners still route internally through `bridge_script.route_to` and ML1 until migrated; do not rewrite their behavior during gameplay unless the user asks. For Catherby fishing/cooking/banking, prefer `catherby_food_runner.py` or the `catherby-food` registry entry; use `catherby_food_runner_XS.py` or `runner_status_XS.py` for compact status/control. It targets `catherby_fishing_shore`, `catherby_range`, and `catherby_bank`, handles south range-house Door 1530 between deeper range-house tiles and the shore/bank approach area, gates fish-method upgrades by Cooking requirements as well as Fishing unlocks, banks uncookable raw leftovers during recovery, and treats `inBankArea=true`/bank action success as arrival proof rather than chasing old exact bank coordinates. Use its `--efficiency-report --quiet` mode before assuming stale status means idle, because it reads passive server activity traces directly. `catherby_range` is anchored at the pathable cooking tile `2819,3443`; route to `catherby_fishing_shop` for Harry's Fishing Shop and open it with `open_nearest_shop` using name `harry` or `fishing`. Use `food_bank_XS.py` before cooking/banking decisions and `object_search_XS.py` after failed object searches. Legacy Route Runner batch diagnostics such as `runReq`, `runBefore`, `runAfter`, `runSpent`, `expectedRunSpend`, `tps`, `tilesPerTick`, and `runWarn` remain useful only when a compatibility executor is deliberately used for old-planner debugging; treat non-`none` `runWarn` values as evidence that run was requested but not effective. Expect `mining_runner.py` to write a sibling `.routes.jsonl` automatically for its route legs.

For player-to-player trades, use the compact trade primitives and keep control scoped to the claimed profile. Each agent controls only its own trade window: use `request_player_trade_XS` to request or answer a nearby player's trade request and auto-walk a short nearby distance into the 3-tile trade range, `offer_trade_item_XS` to offer this player's inventory item, validated `accept_trade_XS '{"expectPartner":"NAME","expectItemId":995,"minAmount":N}'` once to accept this player's side, and `trade_status_XS` to inspect phase, partner, offers, confirmations, and auto-final intent. `accept_trade_XS` validates expected partner/item/amount before accepting and records this player's auto-final intent; when both parties have each called it once, the normal second confirmation screen is completed automatically for both opted-in sides. If you control only one profile, initiate/request/offer/accept for that profile and tell the user or other agent exactly what the other player must do. For receiving-only flows, prefer `receive_trade.py`.

For new gameplay automation, keep strategy in Python scripts and data. Read `agent-navigation/scripting-primitives.md`; use stable primitives such as `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, `interact_object`, `interact_npc`, bank/shop tools, combat tools, and `wait_until_idle_XS`/`wait_until_idle_XXS` before adding Java. Existing Java skill tools are quarantined compatibility surfaces, not the default place for new loops, and require `legacyCompatibility=true` for deliberate stale-runtime paths. Current primitive-backed runners cover mining, woodcutting/fletching, food, smithing, combat, and compact bank loadout policies. When a long runner exposes cooperative control, prefer its control-file modes over process inspection or `pkill`; use `--status` for occasional diagnosis, `--request-stop` to ask for a safe-boundary stop, and a tiny `--shutdown-status`/XS control wrapper for repeated stop polling so agents do not dump full runner status JSON every second. These modes use ignored files under `agent-navigation/.local/runners/` and let the runner stop at a safe boundary.

For long autonomous gameplay or progression, load the selected character's sparse memory with `character_memory.py show --profile PROFILE --json`. Write new memory only for durable, decision-changing goals or lessons; do not log routine progress, temporary route details, secrets, or facts that belong in route data/session logs. Character memory is profile-scoped so each character stays separate.

For visual route ambiguity, use compact screenshots through `agent-navigation/tools/capture-cardinal-screenshots.sh --prefix REASON`; open only the angle(s) needed to answer the question, and do not load oversized full-screen captures.

For runtime management, prefer `agent-navigation/tools/runtime_doctor.py` plus `docs/local-agent-startup.md`, and avoid interrupting active agents unless the user asked for a restart or stop. Use `python3 agent-navigation/tools/server_tick_report.py --json` when the server log is noisy with cycle-duration warnings and you need a compact health summary instead of dumping the raw log.

For maps, use cache-backed tools and keep the retired screenshot/minimap fog collector retired. Agents should use `render_agent_context_map_XS.py` for current-tile, grid-cell, and route-segment context; it draws all cache mapfunction icons in bounds, overlays the level-0 32-tile grid, keeps nearby segment geometry such as docks/ports visible, and writes unique ignored PNG/JSON artifacts under `agent-navigation/.local/context-maps/<date>/` by default. Use the returned JSON path for marker/place/grid labels instead of assuming a stable topology filename, and open the PNG only when visual geometry is needed. Use the full `render_agent_context_map.py` only when the XS output omits a marker/count/path detail needed for debugging. For ML2 route-quality visuals, use `agent-navigation/ml2-routing/route_ml_XS.py compare-maps` for compact fast-route reports or full `agent-navigation/ml2-routing/route_ml.py compare-maps` when you need the full JSON; both reuse the same static context layers and write aggregate reports plus per-case marker sidecars under `agent-navigation/ml2-routing/artifacts/comparisons/`. These maps render the selected ML2 route by default; add `--include-ml1-planner` only for explicit regression comparisons against ML1. The active full movement maps are the profile movement map, `Heat Map`, and profile fog; they are user-facing analysis tools unless the user explicitly asks for them. Cache-map work is static and should not need a live client.

XS/full agent-facing CLI usage is logged out-of-band to ignored JSONL files under `agent-navigation/.local/usage/<yyyy-MM-dd>.jsonl`. XS wrappers mark delegated full-tool calls with `delegatedBy:"xs"` so direct full fallback usage can be counted separately. This log is for later auditing of which fields agents actually use; do not load it into context unless explicitly inspecting tool usage. Set `AGENT_NAV_USAGE_LOG=0` to disable it for a one-off command.

For session logs, start with `agent_session_XS.py --profile PROFILE --latest`; it returns latest session id, top tools, recent outcomes, failures, current player state, and log paths without loading large logs. Load full Markdown/JSONL only when the compact reader omits a needed detail. Summarize observable events from logs and rollout transcripts. Do not invent hidden reasoning; describe decisions through visible messages, tool calls, retries, results, and outcomes.

## Skill Maintenance

If a child skill gains a new primary script, boundary, or repeated workflow, update this entry skill so fresh agents can discover it without preloading every child body. If you notice a missing routing rule, stale pointer, or better workflow, surface it to the user and ask whether to make the skill edit.
