# 2006Scape - an open source, actively developed emulation server. Pull requests welcome! ![Gameplay Image](https://i.imgur.com/WHnQz2W.png)

## Discord Link: https://discord.gg/hZ6VfWG

## How to Play

### Client/Launcher Download: https://2006Scape.org/
### Rune-Server project thread: [Project thread](https://www.rune-server.ee/runescape-development/rs2-server/projects/686444-2006rebotted-remake-server-will-allow-supply-creatable-bots.html)

# About This Fork

This fork adds a local Codex RuneScape agent bridge on top of the 2006Scape client and server. After logging into a local world, a player can type `/agent ...` in the normal chatbox to ask Codex to perform gameplay tasks through server-authoritative tools instead of screen automation or admin shortcuts.

The agent bridge currently supports:

- Local client-to-Codex app-server sessions started from the game client.
- A server-side HTTP bridge on loopback only, defaulting to `127.0.0.1:43610`, that exposes only the logged-in player's scoped session.
- Dynamic `rs` tools for observing state, walking to known landmarks, dialogue/object interaction, NPC combat, food use, shops, banking, mining, woodcutting, smelting, and smithing.
- Server-side batch tools for long-running actions such as landmark travel, tile walking, mining to a full inventory, woodcutting to a full inventory, and waiting until movement/skilling/combat activity settles. These avoid slow one-tick polling from the client or in-app chat.
- Combat-training planning toward melee goals, including training-style selection, safer target choice, food thresholds, gear recommendations, and excess-coin banking.
- Structured agent/player chat through `::agentchat` in the game client and compact `agent_chat_*_XS` bridge tools, with optional Discord mirroring for deployed agent coordination.
- Starter world knowledge for Lumbridge, Varrock, Barbarian Village, Al Kharid shops, Falador, rock crabs, banks, mines, trees, and combat areas.
- Agent session logs under `2006Scape Server/data/logs/agent-sessions/<yyyy-MM-dd>/`, with raw JSONL events and a readable Markdown summary.

The bridge is intentionally constrained. Agent actions go through existing game mechanics such as walking, combat, shops, banking, mining, and smithing. It does not add admin teleports, item spawning, direct player-stat edits, or screen automation.

For structured chat, players can type `::agentchat message`, `::agentchat @agent:Name message`, `::agentchat @player:Name message`, `::agentchat @all message`, or `::agentchat #channel message` in the game client. Agents should use compact calls such as `agent-navigation/tools/rs-tool_XS.sh agent_chat_status '{"sinceId":0}'`, `agent-navigation/tools/rs-tool_XS.sh agent_chat_send '{"message":"need a hand","agent":"MrGem"}'`, or `python3 agent-navigation/tools/agent_chat_XS.py --profile MrFlame read --since-id 0`. Target shortcuts are mutually exclusive: use either `agent`/`player` or generic `to` plus `toType`, not both. Use these for coordination, not as a public chat replacement or a hot-loop polling primitive.

For a contributor-oriented summary of the fork work, see [canvrno's additions so far](docs/canvrno-additions.md).

For the quickest regular-player external setup path, start with [External Deployment Quickstart](docs/external-deployment-quickstart.md). The default sample uses `direct_tcp`: the Java client connects directly to the configured public host over plaintext TCP, while PBKDF2 account auth, a host firewall, and a loopback-only agent bridge provide the MVP safety boundary. For the planned external-player networking, authentication, standalone client, agent chat, Discord transport, and hosting design, see [Network, Authentication, Client Distribution, And Agent Chat Design](docs/network-auth-agent-chat-design.md). For concrete `direct_tcp`, VPN/tunnel, and hosting notes, see [Deployment Networking](docs/deployment-networking.md).

For external-player experiments, keep the local dev flow unchanged and start from an explicit sample config. Use `2006Scape Server/ServerConfig.External.Sample.json` for the simplest `direct_tcp` public test, or `2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json` when players will run a local stunnel client and the VPS terminates TLS before forwarding to loopback. Copy the chosen sample to the ignored runtime config, replace placeholders such as `REPLACE_WITH_PUBLIC_INTERFACE_IP`, `server.example.com`, and `REPLACE_WITH_PUBLIC_TLS_HOST`, then preflight before starting:

```sh
cp "2006Scape Server/ServerConfig.External.Sample.json" "2006Scape Server/ServerConfig.json"
$EDITOR "2006Scape Server/ServerConfig.json"
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.json"
SERVER_CONFIG="2006Scape Server/ServerConfig.json" ./scripts/start-server.sh
```

Do not expose the local agent bridge port. It defaults to `127.0.0.1:43610`; `agent_bridge_port` may be changed for isolated local test deployments, but `agent_bridge_bind_host` must remain localhost/loopback. `direct_tcp` intentionally exposes the game/cache sockets as plaintext TCP for the simplest public-server test, so use PBKDF2 account auth, firewall only the required game/cache ports, and keep the bridge loopback-only. Use Tailscale, WireGuard, a generic VPN, or a paired client/server TLS tunnel when external traffic must be encrypted or private; the legacy Java client does not speak TLS by itself.

The direct external sample binds both `127.0.0.1` and a public interface placeholder through plural bind arrays, so same-host local clients and external clients can connect to one server process. It sets `external_transport_mode` to `direct_tcp`, `direct_tcp_external_transport_confirmed=true`, and `require_secure_external_transport=false` as an explicit plaintext acknowledgement. The client TLS tunnel sample keeps game/cache binds on loopback, sets `external_transport_mode=client_tls_tunnel`, and uses `REPLACE_WITH_PUBLIC_TLS_HOST` for the public stunnel endpoint. Keep bind host values as strings. For Tailscale/WireGuard/VPN modes with `file_server=true`, keep HTTP and JAGGRAB cache binds on the private/VPN interface too; Java startup and preflight reject malformed bind arrays or overlay configs whose cache services are loopback-only. `client_tls_tunnel` is the exception: the server game/cache listeners may stay loopback-only because the server-side tunnel forwards encrypted external traffic into those local listeners.

Package a standalone client folder:

```sh
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.External.Sample.json" scripts/package-client.sh
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"
```

The package script preflights `CLIENT_SERVER_CONFIG`, reads `public_game_host`, game/cache ports, world id, and `external_transport_mode` from it, then writes `dist/2006scape-client/`, `dist/2006scape-client.zip`, `client.properties`, `MANIFEST.txt`, and `SHA256SUMS`. Host, port, and transport values must be single-line strings so malformed config or environment overrides cannot inject extra package properties. For `direct_tcp`, the packaged Java client targets `public_game_host` directly and its README/manifest call out that the game/cache sockets are plaintext. For `client_tls_tunnel`, the packaged Java client targets loopback `client_connect_host` or defaults to `127.0.0.1`, because the local plaintext tunnel owns the encrypted connection to `public_game_host`; non-loopback `client_tls_tunnel` client targets are rejected. Those packages also include `client-tls-tunnel/README.txt` and `client-tls-tunnel/stunnel-client.conf`; the packaged launchers try to start that tunnel automatically when `stunnel` is installed, and still document the manual command as a fallback. The macOS/Linux setup checker can start the bundled stunnel config temporarily for its no-login TCP checks; the Windows setup checker expects the local tunnel endpoint to be reachable first. Generated stunnel configs require certificate-chain verification, hostname checking, and TLS 1.2 or newer. Generate the matching operator-side template with `scripts/render-client-tls-tunnel-config.py --config "2006Scape Server/ServerConfig.json" --output-dir dist/client-tls-tunnel-operator`; it binds the public stunnel accept side to `client_tls_tunnel_server_accept_host` or `public_game_host`, using a real non-placeholder, non-wildcard host so it does not collide with the loopback Java listener on the same ports. `prepare-external-deployment.py` does this automatically for `client_tls_tunnel` and passes the folder to readiness verification. `CLIENT_ALLOW_PLACEHOLDER_NETWORK_CONFIG=1` exists only so source validation can package tracked placeholder samples such as `ServerConfig.ClientTlsTunnel.Sample.json`; do not use it for real player packages. The top-level client README includes transport-specific launch guidance, login guidance to use the server operator's supplied account, a no-password-reuse warning for regular players, and setup-check commands. macOS players can double-click `Run-2006Scape.command` and `Check-Setup.command`; those macOS double-click .command wrappers delegate to `run-macos-linux.sh` and `check-setup-macos-linux.sh`, while Windows players use the `.bat` files. `check-setup-macos-linux.sh` and `check-setup-windows.bat` verify Java, print `client.properties`, and attempt TCP checks without logging in or changing server state. `MANIFEST.txt` records the client socket target, `public_game_host`, source config path, and `source_server_config_sha256` so deployment verification can tie a client package to the exact config file content that produced it. The zip preserves the macOS `.command` wrappers plus the macOS/Linux launcher and setup-checker executable bits, the Windows launch/check scripts are written with CRLF line endings, and the launchers/checkers print a Java 8+ install hint if `java` is missing from PATH. Packaged launchers also pass `-no-java-warnings` so external testers using a modern 64-bit Java runtime do not see the old Parabot-focused Java-version dialog. `client.properties` includes `secure.transport`/external transport metadata so the launcher can warn testers whether they are connecting directly or must connect a VPN/tunnel before login. `CLIENT_SERVER_HOST`, `CLIENT_SERVER_PORT`, `CLIENT_HTTP_PORT`, `CLIENT_JAGGRAB_PORT`, `CLIENT_WORLD`, and `CLIENT_SECURE_TRANSPORT` remain available as explicit overrides, but non-local hosts require `CLIENT_SECURE_TRANSPORT` to be one of `direct_tcp`, `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`; `client_tls_tunnel` targets must still stay loopback. The script refuses wildcard client targets such as `0.0.0.0`; use the actual host clients should connect to.

Package generation also refuses symlinked output directories, archive paths, or output parent directories before deleting or writing package artifacts.

Browser play is documented as future research, not the external-player MVP. Modern browsers do not run the old Java applet path, and this client still uses AWT/Swing plus raw game/cache sockets, so the supported downloadable client is the packaged desktop Java client.

For a deployment bundle, prefer `scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"`. It packages the client under `dist/external-deployment/`, writes `2006scape-client.zip`, renders `client-tls-tunnel-operator/` when the config uses `client_tls_tunnel`, writes `server-deployment/` hardened systemd/firewall templates plus account/secrets install guidance, runtime-data backup notes, and fill-in proof note templates, and writes a readiness report without starting, stopping, or restarting the runtime.

The deployment verifier rejects tracked sample network placeholders such as `server.example.com`, `REPLACE_WITH_PUBLIC_INTERFACE_IP`, `example-tailnet-host`, and `100.64.0.10`. Replace them with the real public or private host and interface IP before distributing a client. `--allow-placeholder-network-config` is only for source/sample validation.

Create PBKDF2 account records for external auth:

```sh
scripts/create-account.py username
# Compatibility fallback only for older Java 8 runtimes:
scripts/create-account.py username --algorithm sha1
# Rotate a password without dropping roles, allowed characters, or Discord metadata:
scripts/create-account.py username --overwrite --preserve-metadata
# Audit/list or disable/enable existing records without changing passwords:
scripts/account-admin.py --require-password-policy audit
scripts/account-admin.py list --json
scripts/account-admin.py disable username
scripts/account-admin.py enable username
```

Account records are written under ignored `2006Scape Server/data/accounts/` with owner-only permissions where the filesystem supports them. The helper, Java auth service, account admin tool, and deployment verifier reject symlinked account records; deployment verification also rejects group/world-readable account directories or records on POSIX systems. The create helper uses `PBKDF2WithHmacSHA256` by default, rejects passwords shorter than 12 characters unless `--allow-weak-password` is explicitly passed for local throwaway/source-validation accounts, preserves the password exactly instead of trimming it before hashing, and stamps `passwordPolicy` metadata on new or rotated records. Deployment verification and `scripts/account-admin.py --require-password-policy audit` reject records that are missing that metadata or were created with the weak-password override. `--algorithm sha1` is only for a Java 8 runtime that cannot verify SHA-256 PBKDF2 records. Use `--overwrite --preserve-metadata` for password rotation so roles, allowed characters, Discord user id, and disabled state survive unless explicitly overridden. Use the strict account audit before deployment to check exact account-file shape without requiring a packaged client verification run, and use `disable`/`enable` for access control changes that should not rotate the password. Password verification uses each record's stored algorithm and iteration count; external-mode minimum iterations are enforced separately as a strength policy. Existing account-record audits cannot cryptographically prove the original plain-text password length, so create or rotate real external accounts through `scripts/create-account.py` instead of hand-writing hashes. External PBKDF2 account passwords are exact strings; unlike legacy character-password login, they are not trimmed before verification. The in-game `::password` command is blocked after an account-auth login because it only edits the legacy character save token; update PBKDF2 account records out of game. Repeated failed account-auth attempts are temporarily rate-limited per account and per connecting source address; missing-account attempts are source-throttled when legacy fallback is disabled. The in-memory throttle table is bounded and prunes expired entries.

Real Discord bot secrets live in ignored `2006Scape Server/data/secrets.json`. If the server creates the default file because it is missing, it writes it owner-only where POSIX permissions are supported; when loading an existing regular file, the runtime tightens it to owner-only before reading. Symlinked secrets are refused. Use `scripts/probe-discord-agent-bots.py --secrets "2006Scape Server/data/secrets.json"` to prove configured bot tokens and `channelId` reachability without sending messages; add `--send-test-message` only when you intentionally want one sanitized probe message posted. To prove server-to-Discord mirroring, send a unique in-game/agent chat marker through the running server, then run `scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE --proof-manifest dist/external-deployment/deployment-proof-manifest.json`.

For deployment proof collection, add `--proof-manifest dist/external-deployment/deployment-proof-manifest.json` to `scripts/verify-agent-chat-log.py` and `scripts/verify-discord-channel-message.py` so successful direct-delivery, Discord-ingress, blocked-routing, and Discord-mirror checks update the copied proof manifest automatically.

Remote character saves live in ignored `2006Scape Server/data/characters/`. Treat that directory, `data/accounts/`, and `data/secrets.json` as operator-owned runtime data: back them up before replacing a deployed repo, rotating credentials, or restarting into a new config, and do not copy local development character saves to the remote host unless that is intentional. Prefer `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"` on the deployed host; it writes an owner-only archive plus a readiness-compatible owner-only proof note for `--runtime-data-backup-proof-file` without starting, stopping, or restarting the runtime, and records that fact in the proof note. If a copied deployment proof manifest already exists, pass `--proof-manifest PATH` to update only its `runtime_data_backup_proof_file` field with the generated proof note path. The helper refuses symlinked runtime-data paths and symlinked archive/proof/manifest output paths, including symlinked output directories or parent directories. Readiness validation rejects symlinked proof notes, verifies owner-only proof/archive modes where supported, and checks the proof's archive path, `backup archive sha256`, required tar entries for `characters`, `accounts`, and `secrets.json`, the no runtime start/stop/restart proof line, and the `readiness argument: --runtime-data-backup-proof-file ...` line.

Server startup rejects external-player configs unless PBKDF2 account auth is enabled with at least 120,000 iterations, account auto-create is disabled, and legacy auth fallback is disabled. `direct_tcp` configs must explicitly set `require_secure_external_transport=false`, `secure_external_transport_confirmed=false`, and `direct_tcp_external_transport_confirmed=true`; secure/private modes such as Tailscale, WireGuard, VPN, and `client_tls_tunnel` must set `require_secure_external_transport=true` and `secure_external_transport_confirmed=true`. Java startup and the Python deployment tools also reject network host/transport values containing control characters before they can become listener addresses, package properties, manifests, or stunnel lines. Direct TCP, Tailscale, WireGuard, and VPN modes require game binds to include a non-loopback host and, when `file_server=true`, HTTP/JAGGRAB cache binds to include a non-loopback host too. `client_tls_tunnel` may use loopback-only game/cache binds because the encrypted tunnel endpoint owns the external listener; its server-side stunnel accept host must be a specific public interface host, not loopback or wildcard. Wildcard bind hosts such as `0.0.0.0` require `wildcard_bind_confirmed=true` in the config plus `--allow-wildcard-bind`/`CLIENT_ALLOW_WILDCARD_BIND=1` in the helper tooling, and wildcard hosts must not be mixed with specific hosts in the same listener array.

Preflight an external config before starting a remote server:

```sh
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.json"
```

Verify that the packaged client folder and matching zip archive match the external config before distributing it:

```sh
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --json-output dist/deployment-readiness-report.json
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"
```

Deployment verification also rejects symlinked client package files or nested package directories before trusting checksum or zip evidence, and the matching zip archive must contain ordinary file/directory entries rather than symlink-type entries, so the distributed client artifacts stay under the expected package tree.

The readiness report wraps preflight, account audit, and deployment verification, then writes a redacted Markdown artifact to `dist/deployment-readiness-report.md`; add `--json-output PATH` when automation or deployment handoff needs the same status, command summaries, proof coverage, and remaining live-proof list as structured JSON. Use `--server-deployment-dir` when you have rendered the systemd/firewall bundle separately; use `--client-tls-tunnel-dir` when you have rendered operator-side stunnel templates for `client_tls_tunnel`; `prepare-external-deployment.py` passes its generated `server-deployment/` and `client-tls-tunnel-operator/` directories automatically, and can pass `--json-output` through. It does not package, start, stop, or restart the server. Use `scripts/deployment-readiness-status.py --readiness-json dist/deployment-readiness-report.json` or `--prepared-dir dist/external-deployment` to read an existing JSON report and print the current `deploymentProofStatus`, `externallyReady` decision, proof coverage, and remaining live proof without rerunning probes or touching runtime; add `--show-next-commands` when you want command templates for the missing live/manual proof categories. Those templates preserve the report's config, account, secret, client, and deployment paths, create the proof manifest parent directory, copy the template only when the manifest is missing, write manual proof notes beside that manifest, pass that manifest to the desktop-proof and runtime-backup helpers with `--proof-manifest`, pass `--update-proof-manifest` to live readiness reports after successful checks, and the final manifest check passes the recorded secrets path so Discord routing-filter requirements are not skipped. For final evidence collection, put live/manual proof paths, usernames, markers, and password environment-variable names in a JSON proof manifest and pass `--proof-manifest PATH`; use `--update-proof-manifest PATH` when a successful readiness-report run should write supplied live proof fields into a copied manifest that may still contain unrelated placeholders. The generated server bundle includes `proof-templates/deployment-proof-manifest.json` as a fill-in starting point, and explicit CLI flags override manifest fields. Run `scripts/check-deployment-proof-manifest.py PATH --config "2006Scape Server/ServerConfig.json" --require-full-proof --check-files --secrets "2006Scape Server/data/secrets.json"` for a quick manifest completeness check before the heavier readiness/prep command. With `--check-files`, it validates desktop proof evidence and runtime-backup archive/checksum details, not just path existence. Final-gate manifests must keep `require_full_proof:true` in the manifest itself so the handoff remains self-describing. When `scripts/prepare-external-deployment.py` is run with `--require-full-proof`, it also runs this proof check early against the merged manifest plus CLI values, including proof-file, password-environment-variable, and `live_reject_login_expected_statuses` presence, before packaging. Unedited placeholder values in that template are rejected before proof checks run. Do not put passwords, tokens, or secrets in that manifest. Read both `status` and `deploymentProofStatus`: `status: PASS` means the requested commands passed, while `deploymentProofStatus: STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF` means the package is still not live-proven. Add `--require-full-proof` to `scripts/deployment-readiness-report.py` or `scripts/prepare-external-deployment.py` only for a final deployment gate; it exits non-zero unless all required live/manual proof categories are recorded, and it refuses source/test-only allowances such as placeholder config/secrets, empty account dirs, or untrusted TLS checks. If `agent_chat_discord_enabled=true`, Discord bot/channel, Discord-to-server, and server-to-Discord proof are required automatically before readiness can report full Discord proof. Live reports use `LIVE_PROOF_PARTIAL_NEEDS_...` to name missing evidence, `LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED` when network/auth/client/chat/backup proof is recorded with Discord disabled and no Discord flags, and `FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED` when the live network/auth/client/chat/backup plus Discord round-trip proof set is recorded.

After the final readiness report exists, `scripts/package-deployment-proof.py --prepared-dir dist/external-deployment` creates a non-secret handoff tarball from the normal `prepare-external-deployment.py` output directory. If you used lower-level commands, pass explicit paths instead, for example `--readiness-report dist/deployment-readiness-report.md --readiness-json dist/deployment-readiness-report.json --proof-manifest dist/deployment-proof-manifest.json`. For the final external-ready handoff, add `--require-full-proof`; it fails unless the readiness JSON records a full live proof status and the proof manifest passes full-proof plus proof-file validation. The bundle includes readiness reports, the filled proof manifest when present, proof notes, and selected client/server metadata, while deliberately excluding runtime backup archives, character saves, account records, `data/secrets.json`, passwords, bridge tokens, and Discord bot tokens.

Direct player chatbox delivery proof is required even when Discord is disabled: verify an `agent_chat_player_delivery` audit event and pass `--agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER --agent-chat-delivery-log-channel agent` to readiness/prep, or add `--proof-manifest deployment-proof-manifest.json` to `scripts/verify-agent-chat-log.py` so it records those manifest fields automatically after a successful check. For Discord proof in readiness/prep reports, `--agent-chat-log-text` must also include `--agent-chat-log-from-type discord --agent-chat-log-from-bot false`; the same verifier can write those manifest fields with `--proof-manifest`. Server-to-Discord proof must use the default bot-author verification, not `--discord-channel-message-allow-human-author`; `scripts/verify-discord-channel-message.py --proof-manifest deployment-proof-manifest.json` records the mirror proof fields after success. If routing allow-lists are configured, full Discord readiness also requires `--agent-chat-blocked-log-text BLOCKED_MARKER` proof that a blocked human/non-bot Discord marker did not enter `AgentChatService`; the blocked absence verifier can record that marker with `--expect-absent --proof-manifest`.

After the remote server is intentionally running, use `scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"` when you want a focused network-only check for public game/cache reachability and agent bridge non-exposure before running login or packaging proof. Add `--live` to the full verifier to record the same network proof with the deployment artifacts. For `client_tls_tunnel`, live verification performs TLS 1.2+ handshakes against the public tunnel endpoints; use `--tls-sni-host` only when the certificate name intentionally differs from `public_game_host`. To prove account auth through the same path, create a throwaway PBKDF2 account and pass `--live-login-username NAME --live-login-password-env ENV_VAR`; the password is read from the environment instead of the command line. To prove local and external players can coexist, add a second throwaway account with `--live-local-login-username LOCAL --live-local-login-password-env LOCAL_ENV`; the verifier keeps the external socket open while it logs in locally through `127.0.0.1` or the supplied `--live-local-host/--live-local-port`, and `--live-local-host` must remain `localhost` or a loopback IP address. For a focused protocol-only coexistence check, use `scripts/probe-concurrent-logins.py --external-host HOST --external-username EXTERNAL --external-password-env EXTERNAL_PASSWORD --local-username LOCAL --local-password-env LOCAL_PASSWORD`; this does not replace the desktop-client proof. After one same-host Java client and one external Java client are both online through the selected external transport, prefer `scripts/write-desktop-client-proof.py --same-host-client LOCAL --external-client EXTERNAL --transport TRANSPORT --public-host HOST --evidence PATH` to write the proof note for `--desktop-client-proof-file`; add `--proof-manifest deployment-proof-manifest.json` to update `desktop_client_proof_file` directly. The helper validates the existing non-symlink screenshot/log evidence file and writes the local client, external client, transport path, and concurrent-online observation without starting, stopping, restarting, logging in, or probing anything. The server deployment bundle includes `proof-templates/desktop-client-proof.md` as a fill-in fallback; unfilled placeholders are rejected. Run `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"` before replacement/restart and pass its generated proof note with `--runtime-data-backup-proof-file PATH`, or add `--proof-manifest deployment-proof-manifest.json` to update that manifest field directly; the note names character saves, account records, Discord secrets, the backup archive, timestamp, `backup archive sha256`, the readiness argument, and that the helper did not start, stop, or restart the runtime, and readiness validation verifies that archive checksum and required tar entries. The bundle includes `proof-templates/runtime-data-backup-proof.md` as a manual fallback; unfilled placeholders are rejected. To prove fail-closed auth through the same live path, pass `--live-reject-login-username NAME --live-reject-login-password-env ENV_VAR` with a wrong password, missing throwaway account, or disabled throwaway account; add `--live-reject-login-expected-statuses 3,4` for final readiness so the accepted rejection codes are pinned. For direct in-game player delivery proof, verify the delivery-status audit event with `scripts/verify-agent-chat-log.py --event agent_chat_player_delivery --text-contains MARKER --to-type player --to-name PLAYER --delivered-to PLAYER --no-undelivered --channel agent --proof-manifest deployment-proof-manifest.json`; this records the equivalent readiness manifest fields. If Discord agent chat is enabled, add `--live-discord` with real ignored secrets to authenticate bot tokens and check `channelId` reachability; readiness reports require it automatically for Discord-enabled configs. Then send a real human/non-bot Discord test message with a unique marker and prove the running server logged it with `scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --discord-message-id DISCORD_MESSAGE_ID --channel agent --proof-manifest deployment-proof-manifest.json` when the Discord id is available. For configured blocked routing filters, send a blocked human/non-bot Discord marker and prove absence with `scripts/verify-agent-chat-log.py --text-contains BLOCKED_MARKER --from-type discord --from-bot false --channel agent --expect-absent --proof-manifest deployment-proof-manifest.json`; without that absence proof, full Discord readiness remains partial. For the reverse direction, send a unique in-game/agent chat marker and prove the bot-authored mirror appeared in Discord with `scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE --proof-manifest deployment-proof-manifest.json`. Save the emitted `live-check:`, `discord-check:`, desktop-client proof, runtime-data backup proof, player-delivery proof, chat-log proof, blocked-routing proof, and Discord mirror proof lines as deployment evidence.

For focused rejection-only auth checks, use `scripts/probe-game-login.py --host HOST --port 43594 --username NAME --password-env ENV_VAR --expect-failure --expect-statuses 3,4`. Add `--tls --tls-sni-host HOST` when probing a public `client_tls_tunnel` endpoint.

For focused coexistence checks, use `scripts/probe-concurrent-logins.py --external-host HOST --external-username EXTERNAL_TEST --external-password-env EXTERNAL_PASSWORD --local-host 127.0.0.1 --local-username LOCAL_TEST --local-password-env LOCAL_PASSWORD`. Add `--tls --tls-sni-host HOST` when the external path is a public `client_tls_tunnel` endpoint.

Validate these source-side changes without restarting the live runtime:

```sh
scripts/validate-network-auth-chat.sh
```

When Docker Desktop is running, include the Java 8 compatibility build:

```sh
RUN_DOCKER_BUILD=1 scripts/validate-network-auth-chat.sh
```

The validation wrapper can use Docker Desktop's bundled macOS CLI and Compose plugin even when `docker` is not on the shell `PATH`.

For a narrower runtime check after packaging, run the isolated smoke. It starts a child server from this worktree on random alternate localhost ports, checks game/cache listeners and bridge health, creates four unique throwaway PBKDF2 account records, proves two accounts can log in through the game TCP protocol at the same time, proves one rejects a wrong password, proves one disabled account rejects a correct password, then terminates that child process and removes the throwaway files without touching the active local runtime:

```sh
scripts/smoke-network-auth-chat-runtime.py
```

# Installation + Running (Developers)

## One-command local launch on macOS

From the repository root:

```sh
./scripts/run-local.sh
```

This builds both Maven modules, starts the server from `2006Scape Server`, waits for the local game port, and launches the client with `-local -s localhost`. Closing the client stops the background server process started by the script.

The server uses `2006Scape Server/ServerConfig.json` when it exists, otherwise it falls back to `2006Scape Server/ServerConfig.Sample.json`. To use a specific config:

```sh
SERVER_CONFIG="2006Scape Server/ServerConfig.Sample.json" ./scripts/run-local.sh
```

Useful focused scripts:

```sh
./scripts/build-local.sh
./scripts/start-server.sh
./scripts/start-client.sh
```

`start-server.sh` copies the built server jar to `/tmp/2006scape-run/` before launching it. Keep that behavior on during local work: do not run the live server directly from `2006Scape Server/target/server-1.0-jar-with-dependencies.jar` while rebuilding with Maven, because replacing a jar under a running Java 8 process can crash lazy class loading.

Launcher JVM options can be passed through environment variables:

```sh
SERVER_JAVA_OPTS="-Dsun.zip.disableMemoryMapping=true" ./scripts/start-server.sh
CLIENT_JAVA_OPTS="-Dsun.java2d.uiScale=2" ./scripts/start-client.sh -u "MrFlame"
CLIENT_SINGLE_INSTANCE=0 ./scripts/start-client.sh -u "MrGem"
```

The client also supports a repo-native scale flag that doubles the game canvas while preserving normal in-game mouse coordinates:

```sh
./scripts/start-client.sh -u "MrFlame" -scale 2 -no-nav
```

Client arguments can be appended to either client launcher, for example:

```sh
./scripts/run-local.sh -u myname -p mypass
```

For current agent testing, prefill the default local profile, or choose another profile explicitly:

```sh
./scripts/run-local.sh -u "MrFlame"
./scripts/run-local.sh -u "MrGem"
```

For Codex-controlled exploration where repo tools such as `agent-navigation/tools/rs-tool.sh` need an active bridge session, use the dedicated startup runbook:

- [Local Agent Startup](docs/local-agent-startup.md)

## Using the Codex Agent Bridge

Prerequisites:

- Build and run both modules locally.
- Start the client with `-local`, `-dev`, or `-offline` so it connects to localhost and disables CRC checking.
- Log into a local account before using `/agent`.
- Have the Codex CLI/app-server available on your `PATH`; the client launches `codex app-server --listen stdio://` when an agent session starts.

Basic flow:

1. Start the local server and client:

   ```sh
   ./scripts/run-local.sh -u "MrFlame"
   ```

   For another profile, use that profile name and set `RS_PROFILE=<name>` for repo-side bridge tools.

2. Log into the game world.
3. Type `/agent key` once per local setup and enter your API key in the Swing password dialog. The key is passed to Codex auth and is not written to repository files.
4. Type `/agent status` to confirm the app-server, auth, and session state.
5. Type a task, for example:

   ```text
   /agent travel to varrock east bank
   /agent mine iron ore and bank it
   /agent smelt bronze bars
   /agent train combat safely toward 50 attack strength and defence
   /agent buy kebabs, bank extra coins, then train on a safe nearby target
   ```

6. Use `/agent stop` to interrupt the active turn and clear the current server-side action.

Agent sessions are local gameplay runs. The model is expected to observe first, prefer server-side batch tools for repeated travel and resource gathering, use `wait_until_idle` for production batches such as smelting or smithing, and adapt to game state such as missing tools, low hitpoints, full inventory, unreachable targets, closed interfaces, or insufficient skill levels.

Current navigation work is tracked in `agent-navigation/`. That folder stores places, route memories, hazards, route tests, and live observations. The most recent focus is safe travel, including run-energy requirements around south Varrock and the verified Varrock square to Champions' Guild stairs route.

To discover repo helper scripts without knowing exact filenames, use the lightweight registry:

```sh
python3 agent-navigation/tools/script_registry.py search "route*"
python3 agent-navigation/tools/script_registry.py show agility --json
```

Useful checks while developing the bridge:

```sh
mvn -q clean test
mvn -q -DskipTests package
```

1. Import Project in IntelliJ

2. Hit File > Project Settings > Set SDK to Java 8 (Download [Java 8 SDK](https://adoptopenjdk.net/?variant=openjdk8) if you don't have one already)

3. Navigate to `2006Scape Server` > `src` > `main` > `java` > `com.rs2`, right click GameEngine and hit Run [Image](https://i.imgur.com/HHooeVu.png)

   [(You Can Also Run The Server With The -c/-config Argument)](https://wiki.2006scape.org/books/getting-setup/page/server-arguments)
5. Navigate to `2006Scape Client` > `src` > `main` > `java`, right click Client and hit Run [Image](https://i.imgur.com/gSmqGLn.png)

*Advanced*

To compile any module from the command line, run `mvn clean install`

## Using Parabot with your local server:
- **1:** Download the latest Parabot Client from [here](https://github.com/2006-Scape/Parabot/releases)
- **2:** Run the parabot client with the following arg:
```fix
java -jar Parabot.jar -local
```
- **3:** ???
- **4:** PROFIT

### Server source layout

- `2006Scape Server` contains all the server code; mark `src` as the Sources directory
- `2006Scape Client` contains all the client code; likewise mark `src`
  - If more than 2 arguments are passed in (can be anything), the client runs locally

## Building from command line

Run `mvn -B clean install`
