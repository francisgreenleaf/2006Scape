# Network, Authentication, Client Distribution, And Agent Chat Design

This document is the first design pass for making the local 2006Scape fork suitable for a small remote server with external players, local developer clients, agent/player chat, and Discord transport.

No runtime restart is needed for this document. Code changes in this area will require a rebuilt server and client before they are live.

## Current Architecture Findings

### Game And Cache Networking

- The game service is a Netty TCP listener created by `org.apollo.jagcached.FileServer`.
- World 1 listens on TCP `43594`; other worlds use `43596 + world`.
- HTTP cache service and JAGGRAB are optionally enabled by `Constants.FILE_SERVER`, using `Constants.HTTP_PORT` and `Constants.JAGGRAB_PORT`.
- Before this work, `FileServer` bound with `new InetSocketAddress(port)`, which meant wildcard binding with no explicit deployment intent. It now resolves service, HTTP, and JAGGRAB bind hosts from config so local and external deployments are deliberate.
- The service pipeline currently starts with `HandshakeDecoder`, `IdleStateHandler`, and the Apollo handler. There is no TLS handler.
- The client opens a plain `Socket` through `Game.openSocket(...)`. The game login, on-demand cache fetcher, and JAGGRAB path all use that same socket-opening path.

### Login And Authentication

- Login uses the legacy RuneScape protocol: plaintext TCP, server seed exchange, RSA-encrypted credential block, then ISAAC opcode obfuscation.
- `LoginDecoder` decrypts the RSA block and extracts username/password. Username/password validation in the decoder is currently commented out.
- `LoginSession` lowercases the username, checks basic character/length rules, checks bans/online/max players, then loads the character file.
- `PlayerSave` verifies `character-password` against either the raw supplied password or `passwordHash(password)`.
- `passwordHash` is an unsalted MD5-then-SHA-256 Base64 digest. This is better than saving only plaintext but is not a modern password storage design.
- Missing character files are treated as first-login/new-player flows. That makes the game convenient locally, but it is not a controlled external account system.

### Client Distribution

- `ClientSettings.SERVER_IP` defaults to `server.2006scape.org`, but the local `Client` entrypoint forces localhost.
- `Main` accepts `-s`/`-server` and local flags.
- `scripts/start-client.sh` always launches with `-local -s localhost`.
- Maven already produces `client-1.0-jar-with-dependencies.jar` with `Main` as the entrypoint.
- Browser-era classes still extend `Applet`, but modern browsers do not run Java applets. The current source also depends on AWT/Swing frame/input handling and raw Java `Socket` connections for game and cache traffic, so a browser version would require a separate web client, a remote streaming client, or a compatibility layer. It should not be treated as the MVP path.

### Agent Bridge

- `AgentBridgeServer` binds only to loopback, defaulting to `127.0.0.1:43610`.
- Bridge sessions are claimed by a logged-in player through a nonce and scoped token. `AgentSessionManager` keeps per-player sessions, expires idle sessions, and invalidates replaced sessions for the same player.
- This is the right shape for local agent control. The bridge should not be exposed as a public Internet endpoint.
- New agent primitives should stay player/session scoped and route through the existing bridge tool metadata and `AgentToolService` / `AgentActionService` boundary.

### Player Chat

- Public chat from the client is packet `4`, handled by `com.rs2.net.packets.impl.Chat`.
- `Chat` decodes text, records report text, applies anti-spam and mute checks, then marks the player chat update.
- Player update blocks distribute speech using `Player.appendPlayerChatText`.
- Server-side system messages use `PacketSender.sendMessage`, frame `253`.
- The bridge already has `send_public_chat`, which makes an agent speak as its controlled player by filling the normal chat update fields.

### Discord

- Discord support is currently a single global `JavaCord` singleton loaded from `data/secrets.json` key `bot-token`.
- Existing Discord commands are mostly command-response utilities and admin commands.
- `JavaCord.sendMessage(channel, msg)` looks up a channel by name and sends through the singleton API. That is too narrow for one Discord bot per agent.

## Design Goals

- Preserve current local developer flow by default.
- Make external exposure explicit and documented.
- Keep the game server as the authoritative source of player state.
- Do not expose the local agent bridge publicly.
- Use modern password storage for external accounts.
- Avoid a one-off networking hack that only works on this laptop.
- Keep agent chat compact and script-friendly.
- Stage risky networking/auth work so local agents are not disrupted.

## Recommended Staged Design

### Phase 1: Explicit Network Configuration And Deployment Docs

Add config fields with conservative defaults:

- `game_bind_host`: default `127.0.0.1` for local configs; external configs should prefer a private/VPN interface IP or plural `game_bind_hosts` over wildcard binds.
- `game_port`: default `43594` for world 1.
- `http_bind_host`, `http_port`.
- `jaggrab_bind_host`, `jaggrab_port`.
- `public_game_host`: remote host for external deployment checks and docs. Packaged clients use this directly for `direct_tcp`, Tailscale/WireGuard/VPN modes; `client_tls_tunnel` packages instead use loopback `client_connect_host`, defaulting to `127.0.0.1`.
- `external_players_enabled`: false by default.
- `external_transport_mode`: explicit operator choice, currently `direct_tcp`, `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`.
- `require_secure_external_transport`: false only for `direct_tcp`; true for encrypted/private transport modes.
- `direct_tcp_external_transport_confirmed`: true only when the operator intentionally accepts plaintext public game/cache sockets.

Implementation scope:

- Update `Constants`, `ConfigLoader`, and `FileServer` to bind to configured host/port.
- Add sample configs:
  - `ServerConfig.Local.json` or document current local default.
  - `ServerConfig.External.Sample.json` with explicit public/server settings.
  - `ServerConfig.Tailscale.Sample.json` with explicit tailnet bind/client settings.
  - `ServerConfig.ClientTlsTunnel.Sample.json` with loopback Java listeners and a public stunnel endpoint placeholder.
- Update Docker Compose or add a deployment compose file that only publishes intended ports.
- Keep login-path host decisions on numeric remote addresses from the login decoder. Do not use reverse DNS during login for blacklist or rate-limit keys.
- Normalize blacklist entries and lookups by trimming and lowercasing; ignore blank/comment lines so external IP/private-host entries are predictable.

Safety:

- Low risk if local sample behavior is preserved.
- No gameplay logic changes.

### Phase 2: External Transport Strategy

Recommended encrypted MVP: use Tailscale for the first private player test, with PBKDF2 account auth, explicit tailnet bind hosts, Tailscale ACLs, and the agent bridge kept loopback-only. This is the lowest-risk encrypted path because the packaged Java client still uses the normal game/cache sockets, but those sockets are reachable only through the tailnet.

Plaintext smoke path: `direct_tcp` remains useful for the simplest no-install public-host test when the operator intentionally accepts plaintext game/cache sockets. It is not the final player-distributable encrypted path, and final encrypted packages should use the explicit guard below.

For any deployment where the operator's intent is encrypted external play, package through `scripts/prepare-external-deployment.py --require-encrypted-external` or set `CLIENT_REQUIRE_ENCRYPTED_EXTERNAL=1` when calling `scripts/package-client.sh` directly. That guard allows Tailscale, WireGuard/VPN, and `client_tls_tunnel`, and refuses `direct_tcp` before producing a downloadable client zip.

Encrypted/private alternatives remain supported when the operator wants that extra boundary:

- Private beta: WireGuard, Tailscale, or another VPN. Game/cache ports stay private; clients connect over the overlay network.
- Public small server with encryption: `client_tls_tunnel`, a paired client/server tunnel, or future in-protocol TLS.

Why not protocol-level TLS first:

- The client and server currently expect the first bytes to be the legacy game/update handshake.
- Netty `SslHandler` and Java `SSLSocket` are feasible, but they require client changes for game, on-demand, and JAGGRAB sockets, plus certificate trust/distribution handling.
- Tailscale keeps the first encrypted external-player path easy to distribute for a private beta. `direct_tcp` remains the lowest-friction plaintext smoke path, while VPN/overlay and `client_tls_tunnel` give encryption and firewall control without destabilizing the 2006-era protocol. A server-only TLS proxy is not enough with the current client because `Game.openSocket(...)` does not initiate TLS.

Later integrated TLS option:

- Add `game_tls_enabled`, keystore config, and Netty `SslHandler` before `HandshakeDecoder`.
- Add client-side TLS socket factory and trust options.
- Keep plaintext local mode for developer use.

Safety:

- Proxy/VPN is medium-low risk.
- In-protocol TLS is medium-high risk because it touches every client connection path.

### Phase 3: Account Authentication

Recommended MVP: introduce a server-side account-auth service that verifies credentials before character load, using Java 8-compatible PBKDF2.

Data shape:

- Store account records under ignored server data, for example `data/accounts/<normalizedUsername>.json`.
- Fields:
  - `username`
  - `passwordHash`
  - `passwordSalt`
  - `passwordIterations`
  - `algorithm`
  - `createdAt`
  - `createdBy`
  - `passwordPolicy`
  - `disabled`
  - `roles`
  - optional `discordUserId`
  - optional `allowedCharacters`

Password hashing:

- Use `PBKDF2WithHmacSHA256` when available, with per-account random salt and a high iteration count appropriate for Java 8 server cost.
- Do not run expensive password hashing on the 600 ms game tick. Login is in the Netty/login path, but keep cost bounded and test with multiple concurrent login attempts.
- Rate-limit repeated failed PBKDF2 auth attempts against accounts and connecting source addresses in bounded in-memory state so external deployments are not unlimited brute-force, username-enumeration, or memory-growth targets. Missing accounts still use legacy fallback when that compatibility mode is enabled.

Compatibility:

- Preserve existing local character-password login behind config, such as `account_auth_legacy_fallback`.
- For external mode, disable auto-create by arbitrary game credentials unless explicit registration has happened.
- On successful legacy login, optionally migrate to the new account record if config allows it.
- Public self-signup should not use the game login protocol directly. The future path is a separate HTTPS registration service or operator panel with invite codes, source/account/invite rate limits, the same 12+ character password policy and PBKDF2 schema, owner-only account-file creation, allowed-character metadata, redacted audit logs, and no access to raw runtime data or AgentBridge port `43610`.
- Until that registration service exists, keep `account_auth_auto_create=false` for external mode and provision accounts explicitly through `scripts/prepare-player-package.py`, `scripts/provision-player-account.py`, or `scripts/create-account.py`.

Safety:

- Medium risk. Login is fragile and user-facing.
- Add focused tests for hash verify, account file load/save, legacy migration, disabled accounts, invalid username/password, and new-account disabled behavior.

### Phase 4: Standalone Client Packaging

MVP:

- Keep the Maven fat jar as the base.
- Add a `scripts/package-client.sh` that builds the client and writes a distributable folder with:
  - client jar
  - launch scripts for macOS/Linux/Windows
  - setup-check scripts that verify Java/config/TCP reachability without logging in
  - server host/port defaults
  - README for connecting
- Add a client config path or command-line profile such as `-client-config client.properties`.
- Add a remote launcher script that does not force `-local`.
- Let the package script preflight and derive host, ports, world id, and expected transport from `CLIENT_SERVER_CONFIG` so the downloadable client matches the deployed server config by default and unsafe external configs do not produce client zips. For `client_tls_tunnel`, derive the client host from loopback `client_connect_host` or `127.0.0.1` because the player-side plaintext tunnel owns the encrypted remote connection, and include `client-tls-tunnel/README.txt`, `client-tls-tunnel/INSTALL-STUNNEL.txt`, and `client-tls-tunnel/stunnel-client.conf` in the player package. Generate the matching operator-side `stunnel-server.conf` with `scripts/render-client-tls-tunnel-config.py --config CONFIG --output-dir OUTPUT_DIR`; it binds the public accept side to `client_tls_tunnel_server_accept_host` or `public_game_host`, not wildcard, so it can coexist with the loopback Java listener. Keep explicit env vars as overrides for operator-controlled one-off packages, but require non-local env-targeted packages to name an allowed overlay transport, reject non-loopback `client_tls_tunnel` client targets, and reject wildcard client targets such as `0.0.0.0`.

Later:

- Use `jpackage` for native installers where a modern JDK is available, while keeping Java 8 runtime compatibility in mind.
- Add auto-update only after auth/networking is stable.

Browser feasibility:

- Java applet mode is not viable in modern browsers.
- Current-code blockers are concrete, not just packaging friction:
  - `RSApplet` extends `java.applet.Applet` and builds the desktop UI with AWT/Swing event listeners and `RSFrame`.
  - `Game.openSocket(...)`, `Game.openJagGrabInputStream(...)`, and `OnDemandFetcher` use raw Java sockets for the game, JAGGRAB, and on-demand cache protocols; browsers cannot open arbitrary TCP sockets from page JavaScript.
  - `Main` is a desktop entrypoint that loads local `client.properties`, configures desktop properties, and launches the Java client jar.
- Real browser play would therefore require one of three separate tracks:
  - a new web renderer plus a WebSocket/WebTransport protocol adapter on the server side;
  - a Java-to-WebAssembly or JVM-in-browser compatibility effort that replaces the desktop UI and socket layers;
  - a hosted streaming/remote-desktop style client where the Java client still runs server-side or on a managed host.
- Recommendation: do not pursue browser play for the external-player MVP. Use the packaged desktop Java client, then revisit browser support only as its own project with a dedicated protocol/security design.

### Phase 5: Agent/Player Chat Service

Add a server-side `AgentChatService` as the shared source of truth for structured agent chat.

Message model:

- `id`
- `createdAt`
- `fromType`: `player`, `agent`, `discord`
- `fromName`
- `fromProfile`
- `toType`: `broadcast`, `player`, `agent`, `channel`
- `toName`
- `channel`: default `agent`
- `text`
- `deliveredTo`
- `undeliveredTo`
- `discordMessageId` optional

Bridge primitives:

- `agent_chat_send_XS`
  - args: `message`, optional `to`, `toType`, `channel`, `alsoPublic`.
  - returns: `success`, `messageId`, `delivered`, compact player state.
- `agent_chat_read_XS`
  - args: optional `sinceId`, `channel`, `limit`.
  - returns compact unread/recent messages for the claimed agent/player.
- `agent_chat_status_XS`
  - returns channel, unread count, connected Discord transport status.

Player interaction:

- Add a player command such as `::agentchat <message>` or support normal public chat prefix such as `@agent <message>`.
- Player messages enter `AgentChatService` and are optionally shown to agents through `agent_chat_read_XS`.
- Agent messages to a player should call `PacketSender.sendMessage` for direct chatbox delivery. If `alsoPublic=true`, they can also call the existing public speech path.

Agent-to-agent:

- Agents use the bridge primitives and do not need to speak through public chat unless desired.
- The service stores a short bounded in-memory backlog and, when `agent_chat_log_enabled=true`, JSONL logs under `data/logs/agent-chat/<yyyy-MM-dd>/agent-chat.jsonl` for audit/debug.

Safety:

- Medium risk but well-contained if it is a service plus bridge tools.
- Avoid driving another player's state. A chat tool sends messages only from the claimed session.

### Phase 6: Discord Transport

Add a transport layer instead of expanding the current singleton.

MVP shape:

- `DiscordAgentTransport`
- `DiscordAgentBotConfig`
- `DiscordAgentRegistry`

Secrets shape:

- Keep `data/secrets.json` ignored.
- Support:
  - existing `bot-token` for legacy global bot.
  - `agent-discord-bots`: array of `{ "agent": "ExampleAgent", "token": "...", "channelId": "..." }`.

Behavior:

- Each configured agent bot logs in separately.
- Discord messages from that bot/channel are normalized into `AgentChatService`.
- Agent/player chat messages can be mirrored to the configured channel.
- If no token is configured, the chat service still works in-game and through bridge tools.

Safety:

- Medium-high risk due to async Discord callbacks and multiple bot tokens.
- Keep Discord callbacks off direct gameplay mutation paths. They should enqueue chat messages only.

## Hosting Options

### VPS

Pros:

- Simple static IP and direct TCP support.
- Easy firewall rules for game/cache ports.
- Cheapest and easiest for a small private server.
- Works with HAProxy, stunnel, WireGuard, Tailscale, and systemd.

Cons:

- You own patching, backups, firewall, TLS cert renewal, and monitoring.
- Less managed identity/logging than cloud platforms.

Recommendation:

- Best first external deployment target.

### Google Cloud Compute Engine

Pros:

- Strong firewall/IAM model, snapshots, logging, monitoring, static IPs.
- Easier to grow into managed backups and infrastructure-as-code.

Cons:

- More setup overhead and cost.
- Still a VM for this custom TCP game server.

Recommendation:

- Good if we want more operational discipline early.

### Tailscale/WireGuard Overlay

Pros:

- Very safe private beta.
- No public game port exposure.
- Encryption and identity handled by mature networking tools.

Cons:

- Players must install/join the overlay.
- Not a public-server UX.

Recommendation:

- Best initial encrypted external-player test.

### Cloud Run / Serverless Containers

Pros:

- Good for HTTP services.

Cons:

- Bad fit for long-lived custom TCP game sessions and this local-data server model.

Recommendation:

- Not recommended for the game server.

### Browser Client

Pros:

- Easiest player onboarding if eventually achieved.

Cons:

- Existing Java applet approach is obsolete.
- The current client is tied to `java.applet.Applet`, AWT/Swing rendering/input, and raw TCP game/cache sockets, so a browser client is effectively a new client project or streaming layer.
- A real web client would need new server-facing transport work, most likely WebSocket/WebTransport, plus an explicit auth/session model separate from the legacy desktop login socket.

Recommendation:

- Document as research/future, not MVP.

## Recommended First Implementation Batch

The first implementation batch in this worktree follows this staged plan before in-protocol TLS work:

1. Network config fields and external sample config.
2. Deployment/security docs for VPS, GCP VM, direct TCP, and encrypted/private alternatives.
3. Client remote launcher/package script that does not force localhost.
4. `AgentChatService` plus compact bridge tools for in-game/agent chat.
5. Account auth service with PBKDF2 and legacy local compatibility.
6. Discord transport registry with one bot per configured agent.
7. Optional in-protocol TLS after proxy/VPN deployment is proven.

## Implemented Surfaces

### Network Config

`ServerConfig.Sample.json` stays local-first. It binds game, HTTP cache, and JAGGRAB to `127.0.0.1`.

`ServerConfig.External.Sample.json` is the direct public deployment starting point. It binds the game, HTTP cache, and JAGGRAB services to `127.0.0.1` plus `REPLACE_WITH_PUBLIC_INTERFACE_IP`, sets `public_game_host` to `server.example.com`, enables external-player intent, and uses `external_transport_mode=direct_tcp` with explicit plaintext acknowledgement fields. Replace those placeholders with the real public interface address and DNS name or public IP before a real deployment.

`ServerConfig.Tailscale.Sample.json` is the recommended turnkey encrypted private-beta starting point. It binds the game, HTTP cache, and JAGGRAB services to `127.0.0.1` plus `REPLACE_WITH_TAILSCALE_IP`, sets `public_game_host` to `example-tailnet-host`, enables external-player intent, and uses `external_transport_mode=tailscale` with secure-transport acknowledgement fields. Replace those placeholders with the server's Tailscale interface IP and MagicDNS name or Tailscale IP before packaging a real client. Tailscale ACLs or grants should allow only game/cache TCP ports, not the raw agent bridge.

`ServerConfig.ClientTlsTunnel.Sample.json` is the tracked encrypted-path starting point. It keeps game/cache listeners on `127.0.0.1`, sets `external_transport_mode=client_tls_tunnel`, sets secure-transport acknowledgements, and uses `REPLACE_WITH_PUBLIC_TLS_HOST` for both `public_game_host` and the server-side stunnel accept host. Replace that placeholder with the real certificate hostname before packaging for players. Source validation may use `--allow-placeholder-network-config` or `CLIENT_ALLOW_PLACEHOLDER_NETWORK_CONFIG=1`; real deployments must not.

The plural bind arrays let a remote server accept local same-host client connections and external client connections at the same time without binding every public interface. If a deployment deliberately uses `0.0.0.0`, bind wildcard alone for that listener, keep it behind a host firewall or private network, set `wildcard_bind_confirmed=true`, and acknowledge that choice in the preflight/package/verify commands.

New server config keys:

- `game_bind_host`, `game_port`
- `http_bind_host`, `http_port`
- `jaggrab_bind_host`, `jaggrab_port`
- Optional `game_bind_hosts`, `http_bind_hosts`, and `jaggrab_bind_hosts` arrays for explicit multi-bind deployments.
- `public_game_host`
- `external_players_enabled`
- `require_secure_external_transport`
- `secure_external_transport_confirmed`
- `direct_tcp_external_transport_confirmed`
- `wildcard_bind_confirmed`
- `external_transport_mode`
- `agent_chat_discord_enabled`
- `agent_chat_log_enabled`
- `account_auth_enabled`
- `account_auth_auto_create`
- `account_auth_legacy_fallback`
- `account_auth_pbkdf2_iterations`

### External Transport

The implemented MVP supports two transport classes around the legacy plaintext game protocol:

- Simple public test: `direct_tcp`, with plaintext game/cache sockets, PBKDF2 account auth, a host firewall, and the agent bridge kept loopback-only.
- Encrypted/private alternatives: Tailscale, WireGuard, a generic VPN, or a paired client/server TLS tunnel. Future protocol TLS remains a separate option.

The Java protocol remains plaintext internally so the old client handshake and cache fetchers are not destabilized. Do not expose `AgentBridgeServer`; it remains a local-only loopback control plane and defaults to `127.0.0.1:43610`. `agent_bridge_port` can be changed for isolated test deployments, but `agent_bridge_bind_host` must stay localhost/loopback and must not overlap a loopback game/cache listener. Remote player-agent mode uses an HTTPS gateway that forwards only approved `/agent/*` endpoints to that loopback bridge; packaged clients read `agent.bridge.url`, and repo-side Codex threads can claim through `agent-navigation/tools/remote_claim.py`. The bridge uses a bounded worker pool, bounded HTTP request queue, bounded JSON request bodies, and bounded game-tick action queue so local agent bursts apply backpressure instead of creating unbounded HTTP worker threads, unbounded request parsing, or unbounded pending gameplay actions; gameplay mutations still run through the server tick queue. Unexpected tool runtime failures are shaped into compact JSON `success:false` responses so callers do not receive raw handler failures.

Startup now fails when `external_players_enabled=true` unless external account auth is locked down with `account_auth_enabled=true`, `account_auth_auto_create=false`, and `account_auth_legacy_fallback=false`, unless `external_transport_mode` is one of `direct_tcp`, `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`, and unless `public_game_host` is a real non-loopback/non-wildcard host name or address. `direct_tcp` must explicitly set `require_secure_external_transport=false`, `secure_external_transport_confirmed=false`, and `direct_tcp_external_transport_confirmed=true` because the Java client connects over plaintext TCP. Tailscale, WireGuard, VPN, and `client_tls_tunnel` modes must set `require_secure_external_transport=true` and `secure_external_transport_confirmed=true`, but those fields are acknowledgements rather than encryption by themselves. Network host and transport values must be single-line strings without control characters in both Java startup and deployment tooling. Direct TCP and overlay VPN modes require at least one non-loopback game bind host, and with `file_server=true` they also require non-loopback HTTP and JAGGRAB cache bind hosts. `client_tls_tunnel` may use loopback-only game/cache binds because the encrypted server-side tunnel endpoint forwards into those local listeners; its operator-side stunnel accept host must be a specific non-loopback, non-wildcard, non-placeholder host. A generic private network is not accepted as an encrypted/private transport unless it is represented by one of the encrypted modes; otherwise model it as `direct_tcp` with explicit plaintext acknowledgement. Wildcard bind hosts require `wildcard_bind_confirmed=true` and must not be mixed with specific hosts in the same listener array. These are guardrails; they do not replace the actual PBKDF2 account records, host firewall, or VPN/tunnel deployment.

In local/dev mode, HTTP cache bind failure can still fall back to JAGGRAB, matching the old server tolerance. In external-player mode, HTTP cache bind failure is fatal so a packaged client is not distributed against a server whose intended cache listener silently failed.

An explicitly provided `-c` / `-config` file is fail-closed: if the file cannot be read or the network/security validation rejects it, `GameEngine` exits instead of continuing with default local settings.

See [Deployment Networking](deployment-networking.md) for concrete setup notes.
That document also owns the live proof checklist. Source tests, package checks, and static verification are necessary but not sufficient; external readiness still requires an intentional rebuilt runtime, public game/cache reachability over the selected external transport, PBKDF2 login attempts, concurrent local/external clients, bridge non-exposure, direct agent/player chat delivery proof, runtime-data backup proof, and Discord round-trip proof when Discord is enabled.

`scripts/smoke-network-auth-chat-runtime.py` is the no-interference runtime proof for source validation. It starts a child server from the built jar on random alternate localhost game/cache/bridge ports with external-player guardrails enabled in `client_tls_tunnel` mode, verifies bridge health plus local game/cache TCP listeners, creates four unique throwaway PBKDF2 account records plus one deliberately uncreated username, logs two accounts in through the legacy game TCP protocol at the same time, proves one account rejects a wrong password, proves one disabled account rejects a correct password, proves the missing account is rejected, and terminates only that child process. It removes only the throwaway account/character files it created. This proves startup wiring, port configurability, account-auth login wiring, concurrent-login acceptance, and fail-closed wrong-password, disabled-account, and missing-account behavior without restarting the active local server; it is still not a substitute for the final remote VPN/tunnel, packaged-client GUI, and real external-client proof.

### Standalone Client

The client now supports:

- `-client-config PATH`
- `-port` / `-game-port`
- `-http-port` / `-cache-http-port`
- `-jaggrab-port`

`Main` uses `ClientSettings.SERVER_IP` when initializing `Signlink`, so packaged clients actually connect to the configured remote host instead of the desktop's localhost.

Package a distributable client folder:

```sh
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" scripts/package-client.sh
```

The output is `dist/2006scape-client/` with `2006scape-client.jar`, `client.properties`, macOS double-click `.command` wrappers, macOS/Linux/Windows launchers, `MANIFEST.txt`, and `SHA256SUMS`, plus `dist/2006scape-client.zip` for download. The package writer stores the macOS .command wrappers plus macOS/Linux launcher/setup-checker scripts with executable archive metadata so extracted zips stay runnable on Unix-like systems and writes the Windows `.bat` launcher with CRLF line endings. The launchers check that `java` is available and print a short Java 8+ install hint instead of failing with a raw shell or Windows command error, and packaged launchers pass `-no-java-warnings` so normal external players using current 64-bit Java do not see the old Parabot-focused Java-version dialog. The top-level client README includes transport-specific setup guidance, such as connecting Tailscale or letting the launcher start `client-tls-tunnel/stunnel-client.conf` when `client_tls_tunnel` and `stunnel` are available, plus login guidance to use the server operator's supplied account and avoid password reuse. macOS players can double-click `Run-2006Scape.command` and `Check-Setup.command`; both delegate to the shared shell scripts. For a more normal Mac handoff, `scripts/package-macos-player-app.py PLAYER --character CHARACTER --prepared-dir dist/external-deployment --dmg` wraps the same prepared client folder in `2006Scape.app` and uses `hdiutil` to create a compressed DMG that contains the app and README-first handoff note, but no passwords, account records, private credentials, runtime data, secrets, or bridge tokens. `scripts/prepare-player-package.py PLAYER --character CHARACTER --config CONFIG --mac-dmg` is the one-command operator path that prepares the bundle if needed, provisions the account, creates the public-safe player kit, and optionally builds that Mac package. The macOS/Linux setup checker can start the bundled stunnel config temporarily for no-login TCP diagnostics; the Windows setup checker stays conservative and expects the local tunnel endpoint to be reachable first. The manifest records build time, git revision, source server config path, `source_server_config_sha256`, target client host, `public_game_host`, game/HTTP/JAGGRAB ports, expected external transport, and the client jar SHA-256. The deployment verifier compares that config hash to the `--config` file so a distributed client can be tied back to the exact external config content used to build it. `client.properties` also records `secure.transport`, and `Main` prints a startup reminder when that value is not local so testers know the required VPN/tunnel must be connected before login. `CLIENT_SERVER_CONFIG` is preflighted before packaging; for `client_tls_tunnel`, `server.host` is loopback `client_connect_host` or `127.0.0.1`, while `public_game_host` remains the remote TLS tunnel endpoint for deployment checks. The generated stunnel configs require certificate-chain verification, hostname checking, and TLS 1.2 or newer; packaged launchers try to start the player-side config automatically and print the manual stunnel command if the binary is missing. `CLIENT_SERVER_HOST`, `CLIENT_SERVER_PORT`, `CLIENT_HTTP_PORT`, `CLIENT_JAGGRAB_PORT`, `CLIENT_WORLD`, and `CLIENT_SECURE_TRANSPORT` can still override config-derived values when deliberately packaging a variant. If an override targets a non-local host, `CLIENT_SECURE_TRANSPORT` must be one of `direct_tcp`, `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`; `client_tls_tunnel` targets must stay loopback because the Java client is still plaintext. The local dev launcher still forces `-local -s localhost`.

### Account Auth

`AccountAuthService` stores PBKDF2 account records under ignored `2006Scape Server/data/accounts/`. The Java auth service and `scripts/create-account.py` set owner-only directory/file permissions where the filesystem supports them, and both refuse symlinked account directories or records. The deployment verifier also rejects account symlinks and group/world-readable account directories or records on POSIX systems.

Create an account record:

```sh
scripts/create-account.py username
ACCOUNT_PASSWORD='long test password' scripts/create-account.py username --password-env ACCOUNT_PASSWORD
# Compatibility fallback only, for older Java 8 runtimes that cannot verify PBKDF2WithHmacSHA256 records:
ACCOUNT_PASSWORD='long test password' scripts/create-account.py username --password-env ACCOUNT_PASSWORD --algorithm sha1
# Optional metadata:
ACCOUNT_PASSWORD='long test password' scripts/create-account.py username --password-env ACCOUNT_PASSWORD --role player --allowed-character username --discord-user-id 123456789012345678
# Password rotation that preserves optional metadata:
ACCOUNT_PASSWORD='new longer secret' scripts/create-account.py username --password-env ACCOUNT_PASSWORD --overwrite --preserve-metadata
# Operator inspection and access toggles:
scripts/account-admin.py audit
scripts/account-admin.py list --json
scripts/account-admin.py disable username
scripts/account-admin.py enable username
```

The helper writes `PBKDF2WithHmacSHA256` records by default, rejects passwords shorter than 12 characters unless `--allow-weak-password` is explicitly passed for local throwaway/source-validation accounts, and stamps `passwordPolicy` metadata on new or rotated records. `--algorithm sha1` exists only to match the Java service's `PBKDF2WithHmacSHA1` fallback on older Java 8 runtimes; keep SHA-256 as the normal external-account format. Java auth and account audits can verify stored hash shape, algorithm, salt size, and iteration strength, but they cannot cryptographically recover the original plain-text password length from a PBKDF2 hash; create or rotate real external accounts through the helper rather than hand-writing account records. Deployment verification and `scripts/account-admin.py --require-password-policy audit` reject missing `passwordPolicy` metadata and records created with the weak-password override.
Optional `roles` are short labels using letters, numbers, underscore, dot, colon, or hyphen. Optional `allowedCharacters` entries use the same 1-12 character username rules as game logins; when the list is non-empty, Java auth only allows login for a character name present in that list. Optional `discordUserId` must be a numeric Discord snowflake string. The Java auth service and deployment verifier both reject malformed optional metadata so hand-edited account records fail closed before login.

Local sample config leaves `account_auth_enabled=false` and keeps legacy character-password login. If account auth is enabled with legacy fallback, fallback is only allowed when no PBKDF2 account record exists; existing account records are authoritative, so wrong passwords, disabled accounts, and invalid/tampered account records do not fall through to legacy character auth. Account-auth passwords are verified exactly as submitted, without legacy trim behavior; the old trimmed password path is retained only for legacy character-password fallback. The in-game `::password` command is blocked for account-authenticated sessions because it only updates the legacy character save token, not the PBKDF2 account record. Repeated failed account-auth attempts are temporarily rate-limited per account and per connecting source address; missing-account attempts are source-throttled when legacy fallback is disabled. The in-memory throttle table is bounded and prunes expired entries. External sample config sets:

```json
"account_auth_enabled": true,
"account_auth_auto_create": false,
"account_auth_legacy_fallback": false,
"account_auth_pbkdf2_iterations": 120000
```

This means external usernames must have an account JSON record before login, and external account records below 120,000 PBKDF2 iterations fail closed. Password verification uses the PBKDF2 algorithm and iteration count stored in each record; the external minimum is a separate strength policy check, not a rehash migration shortcut. A valid account may still create its character file on first login.

PBKDF2 account passwords are not copied into legacy character saves. When account auth verifies an existing character, the loader preserves the existing `character-password` token without validating against the submitted account password. When account auth creates a new character, the server writes a random account-auth-only legacy placeholder so `data/characters/<name>.txt` never stores a hash derived from the PBKDF2 login password. Updating an external account password is an operator action against `data/accounts/<username>.json`, normally by rerunning `scripts/create-account.py --overwrite --preserve-metadata` so roles, allowed characters, Discord user id, and disabled state are not accidentally dropped. Access toggles that should not rotate a password use `scripts/account-admin.py disable USERNAME` or `enable USERNAME`, and `scripts/account-admin.py audit` is the focused pre-deployment account-shape check. `::password` remains a legacy character-password feature only.

### Agent Chat

Server-side structured chat is handled by `AgentChatService`.
Messages are kept in a bounded in-memory backlog, capped at 500 characters, stripped of control characters, and routed through normalized channel names before they can be read by agents, delivered to player chatboxes, written to the optional JSONL audit log, or mirrored to Discord. Direct messages are visible to the target, the sender name, and the sender profile; for Discord ingress, `fromName` is the Discord display name, `fromProfile` is the configured agent/profile whose bot received the message, and `discordMessageId` records the source Discord message id when Javacord provides it.

Bridge tools:

```sh
agent-navigation/tools/rs-tool_XS.sh agent_chat_send '{"message":"hello","channel":"agent"}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_send '{"message":"need a hand at bank","agent":"SecondAgent"}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_send '{"message":"hello from the agent","player":"ExampleAgent"}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_read '{"sinceId":0,"limit":10}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_status '{"sinceId":0}'
python3 agent-navigation/tools/agent_chat_XS.py --profile ExampleAgent send "hello"
python3 agent-navigation/tools/agent_chat_XS.py --profile ExampleAgent send "need a hand at bank" --agent SecondAgent
python3 agent-navigation/tools/agent_chat_XS.py --profile ExampleAgent send "hello from the agent" --player ExampleAgent
```

Players can send a structured message from the game client:

```text
::agentchat hello agents
::agentchat @agent:SecondAgent hello
::agentchat @player:ExampleAgent hello
::agentchat @all hello
::agentchat #ops hello
```

Player `::agentchat` prefixes mirror the Discord routing shape: plain text uses
the shared `agent` channel, `@agent:Name` sends a direct agent-visible message,
`@player:Name` queues direct delivery to an online player's game chatbox,
`@all` broadcasts to the shared `agent` channel and queues delivery to online
game clients, and `#channel` selects another normalized channel. Direct
agent-to-player messages use system chat delivery when `player:"Name"` or
`toType:"player"` targets an online player. For named targets, prefer
`agent:"Name"` or `player:"Name"` in bridge JSON and `--agent NAME` or
`--player NAME` in `agent_chat_XS.py`; keep `to` plus `toType` for generic
callers that need the explicit target shape. Target shortcuts are mutually exclusive: use either `agent`/`player` or generic `to` plus `toType`, not both.
Valid explicit `toType` values are `agent`, `player`, `channel`, and
`broadcast`; invalid values fail closed instead of being normalized to channel
visibility. Direct `agent` and `player` targets require a target name, and
`deliverToPlayers` is valid only for `player` or `broadcast` targets.
Delivery is queued in a bounded server-side queue and drained on the server
tick so Discord callbacks and HTTP handler threads do not write client packets
directly. `agent_chat_send_XS` reports `deliveryPending:true` when a direct
player delivery is queued. Direct player delivery is not an offline inbox: if
the target player is not online when the server tick drains the queue, the
message envelope records that name in `undeliveredTo` so later
`agent_chat_read_XS` output exposes the failed delivery attempt. A live-client
chatbox send failure is handled the same way for that player, and does not
abort the remaining queued deliveries.
`alsoPublic:true` makes the agent's player also speak the message through normal
public chat.

Discord fan-out is implemented as a transport boundary, not direct gameplay control. Messages are committed to the in-game chat backlog and optional JSONL audit log before Discord mirroring runs, and Discord mirror failures are treated as transport failures rather than chat-send failures. `agent_chat_status_XS` reports whether Discord transport is enabled, whether chat logging is enabled, and how many bot workers are configured/connected.

### Discord Agent Transport

`DiscordAgentTransport` implements the first transport batch:

- `data/secrets.json` may contain `agent-discord-bots`.
- Each configured agent logs in as its own Discord bot.
- Each agent/profile name must appear at most once in `agent-discord-bots`; deployment verification rejects duplicates and the runtime keeps the first usable config if duplicates are accidentally present.
- Malformed bot fields fail closed: the runtime ignores configs with non-string required fields, object-shaped allow lists, empty explicit allow lists, or non-boolean `allowBroadcast` values.
- Messages in the configured bot channel enter `AgentChatService` as `fromType:"discord"` for that agent.
- Discord text defaults to a direct message for the configured agent. Prefixes route intentionally:
  - `@agent:SecondAgent hello` sends to another agent.
  - `@player:ExampleAgent hello` queues delivery to an online player's game chatbox through `AgentChatService`.
  - `@all hello` broadcasts to the shared agent channel and queues delivery to online game clients.
- Optional `allowedAgents`, `allowedPlayers`, and `allowBroadcast` fields restrict Discord-originated target routing before messages enter `AgentChatService`. Omit allow lists for compatible open routing; if present, they must contain at least one non-empty name as a JSON array or comma-separated string, and `allowBroadcast` must be a JSON boolean.
- Agent/player messages mirror to the relevant configured bot channel with Discord mentions escaped so in-game/agent text cannot ping `@everyone`, `@here`, users, or roles.
- Discord callbacks enqueue chat only; direct player chatbox delivery is drained by the normal server tick, and callbacks do not execute gameplay or bridge actions.

Example ignored secrets shape. Copy `2006Scape Server/data/secrets.External.Sample.json` to ignored `2006Scape Server/data/secrets.json`, make the real file owner-only on POSIX systems, then replace the placeholder Discord token and channel values locally. If the server creates a missing default secrets file on first run, it writes the file owner-only where POSIX permissions are supported; when it loads an existing regular file, it tightens permissions to owner-only before reading; symlinked secrets are refused. The deployment verifier rejects placeholders, symlinked real secrets, and group/world-readable real secrets by default; `--allow-placeholder-discord-secrets` is only for source/sample validation:

```json
{
  "bot-token": "",
  "agent-discord-bots": [
    {
      "agent": "ExampleAgent",
      "token": "DISCORD_BOT_TOKEN",
      "channelId": "123456789012345678",
      "channel": "agent",
      "allowedAgents": ["ExampleAgent", "SecondAgent"],
      "allowedPlayers": ["ExampleAgent", "SecondAgent"],
      "allowBroadcast": true
    }
  ],
  "websitepass": "",
  "erssecret": ""
}
```

Enable it with:

```json
"agent_chat_discord_enabled": true
```

Enable the lightweight chat audit log separately:

```json
"agent_chat_log_enabled": true
```

This writes sanitized message envelopes to `data/logs/agent-chat/<yyyy-MM-dd>/agent-chat.jsonl`. It records the routed message after server-side sanitization, including the optional `discordMessageId` for Discord ingress correlation; it does not include bridge tokens, Discord bot tokens, or raw bridge request payloads.

## Validation Plan

Compile/test without touching the live runtime:

```sh
scripts/validate-network-auth-chat.sh
```

That wrapper runs the focused checks below, the full Maven test suite, package creation, the isolated alternate-port runtime smoke with two concurrent PBKDF2 protocol logins plus wrong-password, disabled-account, and missing-account rejection, temporary standalone-client package smoke tests for both explicit env vars and `CLIENT_SERVER_CONFIG`, Python helper syntax checks, script-registry metadata checks, and representative Java 8 classfile target checks:

```sh
mvn -q -pl "2006Scape Client" -Dtest=MainClientConfigTest test
mvn -q -pl "2006Scape Server" -Dtest=AgentToolServiceTest,AgentSessionManagerTest test
mvn -q -pl "2006Scape Server" -Dtest=AccountAuthServiceTest,AgentChatServiceTest,AgentToolServiceTest,ConfigLoaderNetworkTest,FileServerNetworkConfigTest,DiscordAgentTransportTest test
mvn -q clean test
mvn -q clean -DskipTests package
python3 -m py_compile scripts/account-admin.py scripts/backup-runtime-data.py scripts/check-deployment-proof-manifest.py scripts/create-account.py scripts/deployment-readiness-report.py scripts/deployment-readiness-status.py scripts/install-player-account-record.py scripts/package-deployment-proof.py scripts/package-macos-player-app.py scripts/package-player-kit.py scripts/prepare-external-deployment.py scripts/prepare-player-package.py scripts/preflight-external-config.py scripts/probe-agent-bridge-gateway.py scripts/probe-concurrent-logins.py scripts/probe-deployment-network.py scripts/probe-game-login.py scripts/probe-discord-agent-bots.py scripts/provision-player-account.py scripts/render-agent-bridge-gateway-config.py scripts/render-client-tls-tunnel-config.py scripts/render-player-handoff.py scripts/render-server-deployment-files.py scripts/verify-agent-chat-log.py scripts/verify-discord-channel-message.py scripts/verify-external-deployment.py scripts/verify-player-kit.py scripts/write-desktop-client-proof.py scripts/smoke-network-auth-chat-runtime.py scripts/lib/deployment_proof_manifest.py scripts/lib/game_login_probe.py scripts/lib/discord_bot_probe.py agent-navigation/tools/agent_chat_XS.py agent-navigation/tools/remote_claim.py agent-navigation/tools/rs-tool_XS.py
python3 -m json.tool agent-navigation/data/script_registry.json
python3 agent-navigation/tools/script_registry.py search "agent chat" --json
```

`ConfigLoaderNetworkTest` also loads the tracked local and external sample configs so the loopback/local defaults and `direct_tcp` account-auth external defaults stay valid.

`scripts/preflight-external-config.py` performs a static operator check for external configs before startup. It verifies typed bind-host arrays, non-loopback/non-wildcard public hosts, non-loopback external game/cache bind hosts when required, loopback-only `client_tls_tunnel` packaged client targets, non-wildcard/non-loopback `client_tls_tunnel_server_accept_host`, explicit external-transport acknowledgement, allowed transport modes, distinct ports, and external-account-auth defaults. Java startup also enforces string-only bind-host config, valid game/HTTP/JAGGRAB ports, distinct listener ports when `file_server=true`, non-loopback HTTP/JAGGRAB cache binds when external `file_server=true` unless `external_transport_mode=client_tls_tunnel`, external transport acknowledgement, external account-auth fail-closed settings, non-loopback/non-wildcard `public_game_host`, and at least one non-loopback game bind host unless the configured transport is a client/server TLS tunnel. `direct_tcp` requires `require_secure_external_transport=false`, `secure_external_transport_confirmed=false`, and `direct_tcp_external_transport_confirmed=true`; Tailscale, WireGuard, VPN, and `client_tls_tunnel` require `require_secure_external_transport=true` and `secure_external_transport_confirmed=true`. Deployment verification also rejects placeholder `client_tls_tunnel_server_accept_host` values and placeholder or loopback `--tls-sni-host` values unless source/sample placeholder allowances are explicitly used. Wildcard binds require both `wildcard_bind_confirmed=true` in the config and `--allow-wildcard-bind` in preflight/package/verify so operators make the firewall/VPN boundary explicit, and wildcard entries cannot be mixed with specific hosts in a single listener array.

`scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"` is the focused live network helper. It reuses the verifier's config loading, preflight, placeholder checks, TLS/SNI validation, public game/cache reachability checks, and raw agent bridge non-exposure check, but it does not package, build, log in, start, stop, or restart runtime. Use it to isolate direct TCP, VPN/tunnel, firewall, or accidental raw bridge exposure failures before running the heavier artifact verifier. When remote player-agent mode is enabled, `scripts/probe-agent-bridge-gateway.py --gateway-url https://AGENT_GATEWAY_HOST` separately proves the approved HTTPS `/agent` gateway is reachable, unapproved `/agent/` paths are rejected, and raw TCP `43610` remains private.

`scripts/verify-external-deployment.py` performs the post-package deployment check without starting or stopping anything. It reruns preflight, verifies that `client.properties` and `MANIFEST.txt` match the effective client host (`public_game_host` for `direct_tcp` and overlay VPN modes, loopback `client_connect_host` or `127.0.0.1` for `client_tls_tunnel`), game/cache ports, world id, `external_transport_mode` including `secure.transport`, and `source_server_config_sha256` for the exact `--config` file being verified, rejects tracked sample network placeholders unless `--allow-placeholder-network-config` is deliberately passed for source validation, verifies `SHA256SUMS` digest values and exact file coverage, rejects symlinked client package files or nested package directories, rejects symlink-type zip archive entries, rejects unexpected client folder or zip entries, checks that the distributable client zip is valid, matches the packaged folder files, keeps only the macOS `.command` wrappers plus the macOS/Linux launcher and setup checker executable in archive metadata, rejects Windows launch/check CRLF regressions, and checks setup-checker guidance for Java, `client.properties`, `secure.transport`, and TCP reachability diagnostics. It checks the generated player-side `client-tls-tunnel/stunnel-client.conf` when `client_tls_tunnel` is configured including certificate-chain verification, hostname checking, and TLS 1.2 minimum settings, checks that PBKDF2 account records are loadable by the Java auth service and have valid hash/salt/iteration/algorithm/disabled plus optional metadata fields, rejects missing or weak-override password policy metadata, rejects account symlinks and too-open POSIX account permissions, and validates required Discord bot secret shape, one-bot-per-agent uniqueness, non-placeholder token/channel values, non-symlinked secret files, and owner-only POSIX secret permissions when Discord chat is enabled. With `--server-deployment-dir`, it also verifies the generated systemd unit, env file, copied config, dry-run UFW helper, README, and proof note/manifest templates, including non-root service execution, capability dropping, restrictive address families, systemd sandboxing, owner-only account/secrets installation guidance, and runtime-data backup guidance, so operator server artifacts are checked with the same package evidence. For Tailscale server bundles, it also requires `tailscale-policy-grants.example.json` and verifies that it grants only the configured game/cache ports, never the agent bridge port. With `--client-tls-tunnel-dir` in `client_tls_tunnel` mode, it verifies the operator-side stunnel templates too: exact file set, TLS 1.2 minimum, client certificate-chain and hostname checks, server cert/key paths, specific non-wildcard public accept host, and public TLS listener forwarding to loopback game/cache listeners. The Java auth service, account helper, and account admin tool also refuse symlinked account paths at use/write time. With `--live`, it probes the public game/cache ports for `direct_tcp` and overlay modes, performs TLS 1.2+ handshakes for `client_tls_tunnel` public endpoints, and fails if the configured local agent bridge port, default `43610`, is reachable at `public_game_host`. If `--live-login-username NAME --live-login-password-env ENV_VAR` is supplied, it also performs a game-protocol login over that same live path and prints a password-redacted `live-check:` line on success. If `--live-local-login-username LOCAL --live-local-login-password-env LOCAL_ENV` is supplied too, it keeps the external login socket open while logging in over the same-host local path, defaulting to `127.0.0.1` and the configured game port unless `--live-local-host/--live-local-port` override it; `--live-local-host` must remain `localhost` or a loopback IP address. If `--live-reject-login-username NAME --live-reject-login-password-env ENV_VAR` is supplied, it performs a game-protocol rejection proof over the same live path with a wrong password, missing throwaway account, or disabled throwaway account and fails if that login succeeds; `--live-reject-login-expected-statuses 3,4` is required for final readiness so acceptable rejection status codes are pinned. If `--live-discord` is supplied while Discord agent chat is enabled, it authenticates configured bot tokens through Discord REST and verifies `channelId` reachability without sending messages. Successful live runs print `live-check:` lines naming each checked game/cache endpoint, TCP/TLS mode, SNI when relevant, bridge non-exposure result, and optional login/concurrent-login/rejection proof, plus `discord-check:` lines for bot/channel proof. `scripts/verify-agent-chat-log.py` proves that the running server wrote a sanitized AgentChatService JSONL entry containing a chosen marker, which is useful after a real non-bot Discord message or in-game/agent chat test; pass `--event agent_chat_player_delivery --delivered-to PLAYER --no-undelivered` when the proof needs a direct player-delivery status event instead of the original message event. `scripts/verify-discord-channel-message.py` proves a configured bot can see a recent bot-authored Discord channel message containing a chosen marker after server-to-Discord mirroring. `scripts/deployment-readiness-report.py` wraps preflight, strict `scripts/account-admin.py --require-password-policy audit`, optional desktop-client proof-file validation, optional runtime-data backup proof-file validation, optional direct agent/player delivery proof with `scripts/verify-agent-chat-log.py`, optional Discord-to-server proof with `scripts/verify-agent-chat-log.py`, optional `scripts/verify-discord-channel-message.py`, and the same verifier into one redacted Markdown artifact, can also write a machine-readable JSON companion with `--json-output PATH`, accepts the same live, local-live-login, reject-live-login, Discord, chat-log, Discord mirror, placeholder, wildcard, TLS, `--server-deployment-dir`, and `--client-tls-tunnel-dir` flags, including `--desktop-client-proof-file PATH`, `--runtime-data-backup-proof-file PATH`, `--agent-chat-delivery-log-text MARKER`, `--agent-chat-delivery-log-to-name PLAYER`, `--agent-chat-log-text MARKER`, `--agent-chat-log-from-bot false`, and `--discord-channel-message-text MARKER`, and records both command `status` and `deploymentProofStatus` plus a proof coverage table so static pass/fail evidence is not confused with full live readiness. `scripts/deployment-readiness-status.py` is the cheap follow-up reader for that JSON companion: it prints `externallyReady`, proof coverage, and remaining live proof from an existing report without rerunning checks or touching runtime, `--show-next-commands` prints read-only command templates for missing live/manual proof categories while preserving the report's config/account/secret/client/deployment paths, creating the proof manifest parent directory, copying the template only when the manifest is missing, writing manual proof notes beside that manifest, passing that manifest to the desktop-proof and runtime-backup helpers with `--proof-manifest`, and passing the recorded `--secrets` path to the final proof-manifest check; `--fail-if-not-ready` exits non-zero until the report has a full live-proof status. `--proof-manifest PATH` can supply those live/manual proof values from one JSON file; CLI flags override manifest fields, unknown fields are rejected apart from underscore-prefixed notes, and password fields must contain environment-variable names, not password values. Add `--require-full-proof` to make the readiness command exit non-zero unless all required live/manual proof categories are recorded; it cannot be combined with source/test-only allowances such as placeholder config/secrets, empty account dirs, or untrusted TLS checks. Live partial reports use `LIVE_PROOF_PARTIAL_NEEDS_...` with concrete missing categories, complete network/auth/client/chat/backup reports without Discord proof flags use `LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED`, and complete live network/auth/client/chat/backup plus Discord round-trip reports use `FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED`. Desktop proof-file validation rejects vague placeholders and symlinked proof paths, requires the note to identify the same-host/local Java client, external Java client, external transport path, and concurrent-online observation, and verifies the note's `evidence` path points to a real non-symlink non-empty screenshot/log file. Runtime backup proof-file validation requires the note to identify character saves, PBKDF2 account records, Discord secrets, a backup/archive artifact, date or timestamp, and `backup archive sha256`; it then rejects symlinked proof notes, verifies proof and archive owner-only POSIX modes when supported, checks that the archive path exists and is not a symlink, matches the recorded SHA-256, and contains tar entries for `characters`, `accounts`, and `secrets.json`. Generated templates under `server-deployment/proof-templates/` provide fill-in starting points; unfilled proof notes are rejected if passed directly. `scripts/prepare-external-deployment.py` is the one-command operator bundle path: it packages the client, renders operator-side tunnel templates for `client_tls_tunnel`, writes server-side systemd/firewall templates with account/secrets guidance, runtime-data backup notes, proof note and manifest templates, plus Tailscale grants examples when applicable, passes the server deployment directory and, when applicable, the client TLS tunnel operator directory into the readiness report, and writes the report without touching the live runtime; pass its `--proof-manifest` and `--require-full-proof` flags only after real live/manual proof evidence exists. `scripts/render-server-deployment-files.py` can render only the server-side systemd/UFW/proof-template files. `scripts/account-admin.py --require-password-policy audit` is the focused external account-record check and `scripts/account-admin.py disable/enable` toggles access without changing password hashes. `scripts/probe-game-login.py` is the focused login-only helper and supports direct/overlay TCP, TLS tunnel mode, `--expect-failure` for wrong-password, missing-account, or disabled-account checks, and `--expect-statuses 3,4` for pinned rejection-code proof. `scripts/probe-concurrent-logins.py` is the focused coexistence helper: it opens the external game login first, keeps that socket open, then proves a same-host loopback login succeeds; it supports `--tls --tls-sni-host HOST` for `client_tls_tunnel` public endpoints and keeps `--local-host` loopback-only. `scripts/probe-discord-agent-bots.py` is the focused Discord helper; by default it authenticates bot tokens and checks `channelId` reachability without posting, while `--send-test-message` posts one sanitized bot-authored message only when explicitly requested. The runtime ignores bot-authored Discord messages, so use `scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --channel agent` after a real human/non-bot Discord test message to prove ingestion, and use `scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE` after a real in-game/agent marker to prove mirroring. `scripts/render-client-tls-tunnel-config.py` renders player and operator stunnel templates from the same config. `--tls-sni-host` can name a deliberate certificate hostname, and `--allow-untrusted-client-tls` is only for private self-signed tunnel tests.

Package generation also refuses symlinked output directories, archive paths, or output parent directories before deleting or writing package artifacts.

Chat proof helpers can write their successful proof markers back into the copied proof manifest. Use `scripts/verify-agent-chat-log.py --proof-manifest PATH` for direct agent/player delivery, real Discord-to-server ingress, or blocked-routing absence proof; it updates only the matching `agent_chat_*` manifest fields after the log check succeeds. Use `scripts/verify-discord-channel-message.py --proof-manifest PATH` for server-to-Discord mirror proof; it updates only the `discord_channel_message_*` fields and refuses to record weak `--allow-human-author` evidence.

Because readiness status can claim full Discord round-trip proof, `deployment-readiness-report.py` and `prepare-external-deployment.py` reject weak chat evidence and inspect the supplied config. When `agent_chat_discord_enabled=true`, missing Discord bot/channel, Discord-to-server, or server-to-Discord proof keeps `deploymentProofStatus` partial. `--agent-chat-log-text` must be paired with `--agent-chat-log-from-type discord --agent-chat-log-from-bot false`, and `--discord-channel-message-allow-human-author` is not accepted for server-to-Discord proof. When Discord routing allow-lists or disabled broadcast are configured in secrets, full Discord readiness also requires blocked-routing evidence from `scripts/verify-agent-chat-log.py --expect-absent --proof-manifest PATH` or readiness `--agent-chat-blocked-log-text`, proving a blocked human/non-bot Discord marker did not enter `AgentChatService`.

For desktop-client coexistence proof, prefer `scripts/write-desktop-client-proof.py --same-host-client LOCAL --external-client EXTERNAL --transport TRANSPORT --public-host HOST --evidence PATH --proof-manifest PATH` after one same-host Java client and one external Java client are actually online together. It validates the existing non-symlink screenshot/log evidence file, writes a readiness-compatible note for `--desktop-client-proof-file`, and updates only `desktop_client_proof_file` when a proof manifest is supplied; it does not start, stop, restart, log in, or probe runtime. The generated proof template remains a manual fallback when the helper cannot be used.

The Docker Java 8 compatibility build is optional in that wrapper because some local Codex environments do not have Docker installed. Run it through the wrapper with `RUN_DOCKER_BUILD=1` on a host with Docker. The wrapper uses `launcher_docker_compose`, which can find Docker Desktop's bundled macOS CLI, Compose plugin, and credential helper even when `docker` is not on the shell `PATH`:

Before a final proof manifest is handed to readiness/prep, run `scripts/check-deployment-proof-manifest.py PATH --config "2006Scape Server/ServerConfig.json" --secrets "2006Scape Server/data/secrets.json" --require-full-proof --check-files`. It reuses the shared manifest parser, rejects placeholder values and raw secret-looking keys, checks the live/manual proof field set including Discord and blocked-routing requirements when configured, and can verify referenced proof files or password environment variables without running network probes or starting/stopping runtime. With `--check-files`, it calls the same desktop-proof and runtime-backup proof validators used by the readiness report, including evidence-file checks, archive checksum checks, required tar entries, and owner-only permission checks where supported. For final-gate checks, the manifest itself must keep `require_full_proof:true` and `require_encrypted_external:true`; do not rely on only the caller's CLI flag to make the proof bundle self-describing. `deployment-readiness-status.py --show-next-commands` creates the proof manifest parent directory, copies the template only when the manifest is missing, writes manual proof notes beside that manifest, passes that manifest to the desktop-proof, runtime-backup, direct chat, and Discord chat proof helpers with `--proof-manifest` when those proof steps are missing, and uses readiness-report `--update-proof-manifest` for successful live proof fields. `prepare-external-deployment.py --require-full-proof` runs the same check early against the merged manifest plus CLI values, including proof-file, password-env, encrypted-transport, and `live_reject_login_expected_statuses` presence, before package/build work begins.

For runtime-data backup proof, prefer `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"` on the deployed host. It archives `data/characters`, `data/accounts`, and `data/secrets.json`, writes owner-only archive/proof files on POSIX systems, writes a readiness-compatible proof note for `--runtime-data-backup-proof-file`, refuses symlinked runtime-data paths and symlinked archive/proof/manifest output paths, including symlinked output directories or parent directories, and does not start, stop, or restart the runtime. If the copied deployment proof manifest already exists, add `--proof-manifest PATH` so the helper updates only `runtime_data_backup_proof_file` with the generated proof-note path. The readiness report rejects symlinked proof notes, verifies owner-only proof/archive modes where supported, and checks the proof's archive path, `backup archive sha256`, required tar entries, a no runtime start/stop/restart proof line, and the `readiness argument: --runtime-data-backup-proof-file ...` line, so keep the archive with the proof or use an absolute archive path. The generated proof template remains a manual fallback when the helper cannot be used.

For deployment proof handoff, use `scripts/package-deployment-proof.py --prepared-dir dist/external-deployment` after the readiness Markdown/JSON report and filled proof manifest exist in the normal prepared bundle directory. If lower-level commands wrote artifacts elsewhere, pass the explicit readiness, manifest, client, and server-deployment paths. Add `--require-full-proof` for the final external-ready handoff; it fails unless the readiness JSON records a full live proof status and the proof manifest passes full-proof, encrypted-transport, and proof-file validation. It packages non-secret readiness reports, the filled proof manifest, proof notes, and selected client/server metadata, including `server-deployment/player-handoff-template.md`, while deliberately excluding runtime backup archives, character saves, PBKDF2 account records, `data/secrets.json`, passwords, bridge tokens, and Discord bot tokens. This is a review/handoff convenience, not a substitute for live proof.

```sh
RUN_DOCKER_BUILD=1 scripts/validate-network-auth-chat.sh
```

Runtime proof later, only when explicitly approved:

```sh
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live
LIVE_LOGIN_PASSWORD="throwaway password" scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --live-login-username THROWAWAY --live-login-password-env LIVE_LOGIN_PASSWORD
EXTERNAL_PASSWORD="throwaway external password" LOCAL_PASSWORD="throwaway local password" scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --live-login-username EXTERNAL_TEST --live-login-password-env EXTERNAL_PASSWORD --live-local-login-username LOCAL_TEST --live-local-login-password-env LOCAL_PASSWORD
REJECT_PASSWORD="wrong or disabled-account password" scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --live-reject-login-username REJECT_TEST --live-reject-login-password-env REJECT_PASSWORD --live-reject-login-expected-statuses 3,4
LIVE_LOGIN_PASSWORD="wrong password" scripts/probe-game-login.py --host HOST --port 43594 --username THROWAWAY --password-env LIVE_LOGIN_PASSWORD --expect-failure --expect-statuses 3,4
EXTERNAL_PASSWORD="throwaway external password" LOCAL_PASSWORD="throwaway local password" scripts/probe-concurrent-logins.py --external-host HOST --external-username EXTERNAL_TEST --external-password-env EXTERNAL_PASSWORD --local-host 127.0.0.1 --local-username LOCAL_TEST --local-password-env LOCAL_PASSWORD
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live-discord
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --update-proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json" --live
scripts/render-server-deployment-files.py --config "2006Scape Server/ServerConfig.json" --output-dir dist/server-deployment
scripts/probe-discord-agent-bots.py --secrets "2006Scape Server/data/secrets.json"
scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --discord-message-id DISCORD_MESSAGE_ID --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/render-client-tls-tunnel-config.py --config "2006Scape Server/ServerConfig.json" --output-dir dist/client-tls-tunnel-operator
# For client_tls_tunnel with a certificate name that differs from public_game_host:
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --tls-sni-host play.example.com
agent-navigation/tools/rs-tool_XS.sh agent_chat_send_XS '{"message":"hello","channel":"agent"}'
agent-navigation/tools/rs-tool_XS.sh agent_chat_read_XS '{"limit":5}'
```

## Completion And Proof Status

### Requirement Evidence Matrix

| Requirement | Current implementation evidence | Current proof status |
| --- | --- | --- |
| Multiple local and external players | Config-driven `game_bind_hosts`, `http_bind_hosts`, and `jaggrab_bind_hosts`; external sample binds loopback plus `REPLACE_WITH_PUBLIC_INTERFACE_IP`; `smoke-network-auth-chat-runtime.py` logs in two throwaway PBKDF2 accounts concurrently on alternate local ports; readiness reports validate structured `--desktop-client-proof-file` operator evidence. | Source-proven for multi-bind configuration and concurrent protocol login. Still needs real same-host desktop client plus external client proof after deployment. |
| External transport | `direct_tcp` is the simple public plaintext mode with explicit acknowledgement; encrypted/private modes are `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`; startup/preflight reject mismatched acknowledgement flags; client TLS tunnel packaging writes player and operator stunnel templates. | Source-proven guardrails and packaging. Still needs real direct TCP/VPN/tunnel/TLS endpoint proof with `--live`. |
| Better authentication | `AccountAuthService`, `scripts/create-account.py`, and `scripts/account-admin.py` implement PBKDF2 account records, owner-only files, symlink rejection, disabled accounts, metadata validation, helper-stamped password policy metadata, failed-login throttling, no account-password copy into character saves, and external fail-closed settings. | Source-proven by account tests, strict account tooling smoke, deployment verifier, and isolated runtime accept/wrong-password/disabled-account/missing-account login smoke. Still needs live external login and rejection proof against real account records. |
| Good networking support and docs | `ConfigLoader`, `FileServer`, sample configs, preflight, verifier, readiness report, deployment renderer, and docs cover explicit bind hosts, ports, wildcard acknowledgement, bridge non-exposure, cache listener behavior, Docker Compose loopback publishing, and hosting options. | Source-proven by validation and docs coverage. Still needs operator selection of final host/network values. |
| Standalone downloadable client | `scripts/package-client.sh` builds a distributable client folder/zip with `client.properties`, launchers, macOS double-click wrappers, setup checkers, manifest, checksum file, Java guidance, transport-specific setup text, legacy Java-warning suppression, and optional `client-tls-tunnel/` files including stunnel install guidance. `scripts/render-server-deployment-files.py` emits `player-handoff-template.md`; `scripts/prepare-player-package.py` orchestrates bundle prep, PBKDF2 provisioning, public-safe kit creation, and optional macOS `.app`/DMG generation; `scripts/provision-player-account.py` creates/audits ignored PBKDF2 accounts, writes passwords only to ignored private credentials env files, and renders player handoff notes; `scripts/package-player-kit.py` creates and self-verifies a public-safe player zip with the client archive, README-first handoff note, checksums, and no passwords/private runtime data; `scripts/package-macos-player-app.py` wraps the prepared client in a Finder-friendly app and optional hdiutil DMG without private files; `scripts/verify-player-kit.py` re-checks copied player kit zips, embedded checksums, nested client archive safety, and optional prepared-artifact matches before distribution; `scripts/install-player-account-record.py` prints a dry-run VPS account-record install plan; `scripts/render-player-handoff.py` renders notes when the account already exists without accepting or printing the password. | Source-proven by package smoke tests and deployment verifier. Still needs final production package from real config and GUI client login proof. |
| Browser feasibility investigation | `docs/deployment-networking.md` and this design doc document why Java applet mode is not viable in modern browsers and why a browser client is future research, not the MVP path. | Documentation complete for the investigation outcome. |
| Agent/player chat primitive | `AgentChatService`, bridge metadata, XS tools, `agent_chat_XS.py`, player `::agentchat`, bounded backlog, direct player delivery queue, delivery-status audit events, compact status/read/send tools, and script registry entry are implemented. | Source-proven by Java tests and script metadata checks. Live bridge proof still needs a restarted runtime running this jar. |
| Discord transport | `DiscordAgentTransport`, `agent-discord-bots` secrets shape, bot uniqueness, routing filters, mention escaping, bot-auth ignore behavior, JSONL audit logging, Discord probe helper, chat-log verifier, and channel mirror verifier are implemented. | Source-proven with Java tests and fake Discord API smoke. Still needs real ignored Discord secrets and live Discord-to-server plus server-to-Discord proof. |
| Hosting tradeoffs | `docs/deployment-networking.md` covers Tailscale, WireGuard, Google Cloud Compute Engine, public VPS with client TLS tunnel, and Cloud Run/serverless tradeoffs. | Documentation complete for current hosting decision support. |
| Minimal local disruption | Local defaults keep legacy account auth off, local launchers remain localhost-oriented, Docker Compose binds only loopback, and all live proof tooling avoids restarting the active runtime unless explicitly invoked. | Source-proven by config tests, Docker Compose checks, and validation harness behavior. |

Implemented in this worktree:

- Config-driven bind hosts/ports, external-player intent flags, and secure-transport startup guardrails.
- PBKDF2 account records with local legacy compatibility, Java-enforced external fail-closed settings, and account creation tooling.
- Standalone client configuration and packaging.
- Structured agent/player chat bridge primitives and player `::agentchat` command.
- Optional one-bot-per-agent Discord transport that mirrors chat without executing gameplay from Discord callbacks.
- Optional structured chat JSONL audit logs for external deployments.
- Networking/security/deployment docs and repo skill pointers.

Still requires operator/runtime proof before external use:

- Rebuild and restart the server/client through the normal runtime flow.
- Prove login against real PBKDF2 account records.
- Prove real external connectivity over the selected Tailscale/WireGuard/tunnel transport.
- Prove one same-host Java desktop client and one external packaged Java desktop client online together.
- Prove deployed runtime-data backup evidence before replacement/restart.
- Prove direct agent/player chat delivery through an `agent_chat_player_delivery` audit event.
- Prove Discord bot login and channel reachability with real ignored `data/secrets.json` tokens through `--live-discord` or `scripts/probe-discord-agent-bots.py`, then prove Discord-to-server ingestion with `scripts/verify-agent-chat-log.py --proof-manifest PATH` after a real human/non-bot Discord marker, blocked routing with `scripts/verify-agent-chat-log.py --expect-absent --proof-manifest PATH` after a blocked marker when allow-lists are configured, and server-to-Discord mirroring with `scripts/verify-discord-channel-message.py --proof-manifest PATH` after a real in-game/agent marker.

## Future Decisions

These are not blockers for the external-player MVP described above. The current encrypted player-distributable MVP uses Tailscale for private-beta onboarding, operator-created PBKDF2 account records, tailnet access policy, a loopback-only agent bridge, and the structured `AgentChatService` bus. `direct_tcp` remains available only as an explicit plaintext smoke/no-install path when the operator accepts that tradeoff; WireGuard, VPN, and the packaged `client_tls_tunnel` path remain supported alternatives when Tailscale is not the right fit.

- Registration can stay operator-managed through `scripts/create-account.py` for the MVP. A separate HTTPS account page/API would be a future onboarding project and would need its own CSRF, rate-limit, password-reset, audit, and Discord-linking design.
- Agents should keep using structured agent chat for coordination. If agent messages are mirrored into normal public chat later, decide whether they appear as the player name or with a visible source prefix such as `[Agent:ExampleAgent]`; that is a UX/moderation choice, not required for bridge or Discord transport correctness.
- Public non-VPN play can use `direct_tcp` when plaintext game/cache sockets are acceptable with PBKDF2 account auth, firewalling, and bridge non-exposure. If public non-VPN traffic must be encrypted, use the packaged client-side tunnel until a separate in-protocol TLS project exists. In-protocol TLS would require coordinated changes in the Java client's socket/cache layers and the server/Netty pipeline, plus downgrade and certificate handling rules.
