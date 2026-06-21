# 2006Scape Deployment Networking

This repo's external-player MVP keeps the legacy RuneScape protocol unchanged. The recommended turnkey encrypted private path is Tailscale: the Java client still uses the normal game/cache sockets, but those sockets are reachable only through the tailnet. Tailscale handles network encryption and user/device access; PBKDF2 account records still handle in-game authentication. The simplest no-install public path is `direct_tcp`, where the Java client connects directly to the configured public host over plaintext TCP game/cache sockets with PBKDF2 account auth, host firewall rules, and a loopback-only agent bridge as the safety boundary. Use WireGuard, a generic VPN, or `client_tls_tunnel` when Tailscale is not the right operator fit.

If you are doing the first live test, start with the short operator path in `docs/external-deployment-quickstart.md`. Use this document when you need the full rationale, verifier details, hosting tradeoffs, or non-direct variants.

## Recommended Turnkey Encrypted Path: Tailscale

Use this for a private beta where players can install Tailscale or accept a tailnet invite/share. It gives the easiest encrypted network boundary without changing the 2006Scape game protocol.

1. Install Tailscale on the server and confirm the server has a stable Tailscale IP or MagicDNS name.
2. Copy `2006Scape Server/ServerConfig.Tailscale.Sample.json` to ignored `ServerConfig.json`.
3. Replace `example-tailnet-host` with the MagicDNS name or Tailscale IP that players should connect to.
4. Replace `REPLACE_WITH_TAILSCALE_IP` with the server's Tailscale interface IP in `game_bind_hosts`, `http_bind_hosts`, and `jaggrab_bind_hosts`.
5. Keep `external_transport_mode: "tailscale"`, `require_secure_external_transport: true`, `secure_external_transport_confirmed: true`, and `direct_tcp_external_transport_confirmed: false`.
6. Keep PBKDF2 account auth enabled, auto-create disabled, legacy fallback disabled, and the agent bridge bound to loopback.
7. In Tailscale policy, grant players only the game/cache ports they need, normally TCP `43594`, `43595`, and `8080` when `file_server=true`. Do not grant or expose TCP `43610`.
8. Preflight the config before starting the server:

```sh
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.json"
```

9. Package from the same config:

```sh
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" scripts/package-client.sh
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json" --require-encrypted-external
```

Use `--require-encrypted-external` for a player package that is supposed to satisfy the encrypted-transport goal. It refuses `direct_tcp`, rejects configs that have not confirmed secure external transport, and passes the same guard into `package-client.sh` so a plaintext client zip is not produced accidentally.

An example Tailscale grants shape is:

```json
{
  "grants": [
    {
      "src": ["group:players"],
      "dst": ["tag:2006scape-server"],
      "ip": ["tcp:43594", "tcp:43595", "tcp:8080"]
    }
  ]
}
```

Adapt the `src` and `dst` selectors to your tailnet. `scripts/prepare-external-deployment.py` and `scripts/render-server-deployment-files.py` include `server-deployment/tailscale-policy-grants.example.json` for Tailscale configs, generated from the selected game/cache ports and deliberately omitting the agent bridge port. Keep Tailscale ACL/grant policy and PBKDF2 account records aligned: Tailscale controls who can reach the server network path, while account records control who can log in as a game character.

## Plaintext Direct TCP Smoke Path

Use this only for the simplest public-host smoke test with regular players who should only need the packaged Java client and account credentials. It is not encrypted; do not treat it as the final player-distributable encrypted path. For the recommended encrypted path, use Tailscale above. For public non-VPN encryption, use the `client_tls_tunnel` path below.

1. Copy `2006Scape Server/ServerConfig.External.Sample.json` to ignored `ServerConfig.json`.
2. Replace `server.example.com` with the public DNS name or IP that players should connect to.
3. Replace `REPLACE_WITH_PUBLIC_INTERFACE_IP` with the server interface IP that should accept game/cache traffic.
4. Keep `external_transport_mode: "direct_tcp"`, `require_secure_external_transport: false`, `secure_external_transport_confirmed: false`, and `direct_tcp_external_transport_confirmed: true`.
5. Keep PBKDF2 account auth enabled, auto-create disabled, legacy fallback disabled, and the agent bridge bound to loopback.
6. Open only the intended game/cache ports in the host firewall.
7. Preflight the config before starting the server:

```sh
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.json"
```

8. Package the client from the same server config:

```sh
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" scripts/package-client.sh
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"
```

`package-client.sh` preflights `CLIENT_SERVER_CONFIG` before writing artifacts, so unsafe external configs fail before a zip is produced. Host, port, and transport values must be single-line strings; the package script rejects control characters before writing `client.properties` or `MANIFEST.txt`. Publish `dist/agent-scape-client.zip` plus the generated `MANIFEST.txt`/`SHA256SUMS` contents for operators or testers who want to verify the download. The zip writer preserves the macOS double-click `.command` wrappers plus the macOS/Linux launcher and setup-checker executable bits in archive metadata, the Windows `.bat` launch/check scripts are written with CRLF line endings, and the launchers/checkers print a Java 8+ install hint when `java` is missing. The macOS launcher searches Homebrew OpenJDK paths, `/usr/libexec/java_home`, `JAVA_HOME`, and PATH so Finder-launched apps do not silently miss Java. Packaged launchers pass `-no-java-warnings` to suppress the old Parabot-focused Java-version dialogs for normal external players using current 64-bit Java runtimes. The top-level client README includes a first-run checklist, a transport-specific setup section, setup-check commands, login guidance to use the server operator's supplied account, and a no-password-reuse warning. macOS players can double-click `run-agent-scape.command` or `Check-Setup.command`; those wrappers delegate to the shared shell scripts so Terminal users can still run `run-macos-linux.sh` and `check-setup-macos-linux.sh`. DMG packages additionally expose a normal iconed `agent-scape.app` plus one concise player-facing `README.md` sidecar; if the Finder-launched app cannot start, it shows a macOS alert and writes details to `~/Library/Logs/agent-scape/agent-scape-launch.log`. The manifest records `server_host`, `public_game_host`, a `source_server_config` label, and `source_server_config_sha256`. `check-setup-macos-linux.sh` and `check-setup-windows.bat` verify Java, print the packaged `client.properties`, and attempt game/cache TCP checks without logging in or mutating server state. Tailscale packages also print non-fatal Tailscale CLI/status hints on both checker paths before the TCP probes. This matters for `direct_tcp`, where the packaged Java client connects to `public_game_host` directly over plaintext, for `client_tls_tunnel`, where the Java client connects to loopback while the tunnel connects to the public TLS endpoint, and for deployment verification, where the client package must match the exact config file content being verified. The manifest and `client.properties` should show the selected external transport; the client reads `secure.transport` and prints a startup reminder when it is direct plaintext or when it expects a VPN/tunnel. For `client_tls_tunnel`, the package additionally includes `client-tls-tunnel/README.txt` and `client-tls-tunnel/stunnel-client.conf`; the packaged launchers try to start that local tunnel automatically when `stunnel` is installed, and the README still documents the manual command. Generate and verify the operator-side `client-tls-tunnel-operator/` folder too; `prepare-external-deployment.py` creates it automatically and readiness passes it through as `--client-tls-tunnel-dir`. If you package through manual `CLIENT_SERVER_HOST` overrides instead of `CLIENT_SERVER_CONFIG`, non-local hosts require an allowed `CLIENT_SECURE_TRANSPORT` value: `direct_tcp`, `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`. Wildcard hosts such as `0.0.0.0` are rejected because clients need a real reachable host, and `client_tls_tunnel` client targets must remain loopback. Packaged clients also include `agent.bridge.url`; keep the local default `http://127.0.0.1:43610` for development, but package an HTTPS gateway URL with `CLIENT_AGENT_BRIDGE_URL` or an ignored real config key such as `agent_bridge_public_url` when remote player-agent mode should work. See `docs/agent-bridge-gateway.md`.

When manually packaging an encrypted-only external client, set `CLIENT_REQUIRE_ENCRYPTED_EXTERNAL=1`; it allows only `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel` and refuses `direct_tcp` before writing package artifacts.

`scripts/prepare-external-deployment.py` is the normal operator bundle command once the final config exists. It calls the same package script, writes the client folder and zip under `dist/external-deployment/`, renders operator-side stunnel templates for `client_tls_tunnel`, writes `server-deployment/` with a systemd unit, environment file, copied `ServerConfig.json`, dry-run UFW helper, README with account/secrets install guidance plus runtime-data backup notes, `player-handoff-template.md` for private player instructions, and fill-in proof note templates, then writes a redacted readiness report. It does not start, stop, restart, or relaunch any server or client. For a single friend-test package, `scripts/prepare-player-package.py PLAYER --character CHARACTER --config "2006Scape Server/ServerConfig.json" --mac-dmg` prepares that bundle when needed, provisions the ignored PBKDF2 account record, writes the generated password only to an owner-only ignored credentials env file under `dist/external-deployment/private/`, creates and verifies the public-safe player kit, and optionally builds an iconed macOS `.app` plus compressed DMG. Use `--prepare-policy never` when the prepared bundle already exists and should not be rebuilt. Lower-level commands remain available: `scripts/provision-player-account.py PLAYER --character CHARACTER --prepared-dir dist/external-deployment` creates/audits the account and renders the public-safe handoff note; `scripts/package-player-kit.py PLAYER --character CHARACTER --prepared-dir dist/external-deployment` creates and self-verifies the public-safe player zip containing the client archive, README-first handoff note, and checksums while excluding passwords, private credentials, account records, secrets, runtime data, and bridge tokens; `scripts/package-macos-player-app.py PLAYER --character CHARACTER --prepared-dir dist/external-deployment --dmg` builds the Finder-friendly Mac wrapper with app icon, launch log, and failure alert handling; and `scripts/verify-player-kit.py --kit dist/external-deployment/player-kit-PLAYER.zip --prepared-dir dist/external-deployment --username PLAYER --character CHARACTER` re-checks copied kits before distribution. Use `scripts/render-player-handoff.py --prepared-dir dist/external-deployment --username PLAYER --character CHARACTER` when the account/password already exists and only the note needs rendering. Use `scripts/install-player-account-record.py PLAYER --ssh-target user@example.com --remote-accounts-dir '/opt/2006scape/2006Scape Server/data/accounts'` to print a dry-run VPS account-record install plan; add `--apply` only during an intentional deployment step. It copies one account JSON record and never restarts runtime.

Packaged desktop clients default to `client.scale=2` and `show_navbar=false`. Keep that default for normal external tester packages; it uses the client-owned scale path and avoids macOS HiDPI mouse-coordinate offsets caused by JVM UI scaling.

8. Verify the packaged client folder, matching zip archive, and external config before distributing the zip:

```sh
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/agent-scape-client --server-deployment-dir dist/server-deployment
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/agent-scape-client --server-deployment-dir dist/server-deployment
```

The verifier rejects symlinked client package files or nested package directories, symlink-type zip archive entries, unexpected files in the client folder or zip, checksum mismatches, incomplete or unexpected `SHA256SUMS` entries, archive-content mismatches, launcher/setup-checker executable-metadata mismatches including macOS `.command` wrappers, Windows launch/check line-ending regressions, missing `public_game_host` manifest metadata, and missing launcher/setup-checker/README/manifest guidance. Distribution artifacts stay constrained to the known launchers, setup checkers, config, manifest, checksum, README, and jar files, plus the two generated `client-tls-tunnel/` player files only when the config uses `client_tls_tunnel`. The package must keep the Java install, setup-check, and external-transport safety text intact.

When `--server-deployment-dir` is supplied, the verifier also checks the generated systemd unit, env file, copied `ServerConfig.json`, dry-run UFW helper, operator README, and player handoff template. It parses key systemd/env values and rejects unsafe service names, root service execution, malformed deployment paths, mismatched `ExecStart`, and tampered Java/config/run-dir paths. The handoff template is public-safe scaffolding for telling one player how to download, verify, connect, and log in while keeping passwords, account records, runtime backups, bridge tokens, claim nonces, API keys, and Discord bot tokens out of Git and proof bundles. `scripts/prepare-external-deployment.py` passes its generated `server-deployment/` directory into the readiness report automatically.

`scripts/deployment-readiness-report.py` composes preflight, strict `scripts/account-admin.py --require-password-policy audit`, deployment verification, optional desktop-client proof, optional runtime-data backup proof, optional direct agent/player delivery proof, optional Discord-to-server chat-log proof, and optional Discord channel mirror proof, then writes a redacted Markdown report to `dist/deployment-readiness-report.md`. Add `--json-output PATH` when an operator script or handoff needs the same status, command summaries, proof coverage, and remaining proof list as machine-readable JSON. It is useful for deployment notes and handoff evidence; it does not build, package, start, stop, or restart anything. Pass the same `--live`, `--live-login-*`, `--live-local-login-*`, `--live-reject-login-*`, `--live-discord`, `--require-encrypted-external`, placeholder, wildcard, TLS, `--desktop-client-proof-file`, `--runtime-data-backup-proof-file`, `--agent-chat-delivery-log-*`, `--agent-chat-log-*`, `--discord-channel-message-*`, `--server-deployment-dir`, or `--client-tls-tunnel-dir` flags you would pass to the verifier, chat-log helper, or Discord mirror helper when you want those checks recorded in the report. For a final proof run, prefer collecting those proof values in a JSON manifest and pass `--proof-manifest PATH` to `deployment-readiness-report.py` or `prepare-external-deployment.py`; CLI flags override manifest fields, unknown manifest fields are rejected, and password entries must be environment-variable names such as `EXTERNAL_PASSWORD`, not password values. Use `--update-proof-manifest PATH` after copying the template when a successful readiness-report run should write supplied live proof fields into a manifest that may still contain unrelated placeholders. The generated server deployment bundle includes `proof-templates/deployment-proof-manifest.json` as a fill-in starting point; after copying and filling it, run `scripts/check-deployment-proof-manifest.py PATH --config "2006Scape Server/ServerConfig.json" --secrets "2006Scape Server/data/secrets.json" --require-full-proof --check-files` to catch placeholder, secret-key, missing-field, missing-proof-file, bad desktop-proof evidence, bad runtime-backup archive/checksum, and plaintext-transport mistakes before the heavier readiness/prep command. Final-gate manifests must keep `require_full_proof:true` and `require_encrypted_external:true` in the manifest itself so the handoff remains self-describing. Manifest-owned proof-note file paths are resolved relative to the manifest file unless they are absolute or overridden by CLI flags, so completed proof notes can sit beside the copied manifest. `prepare-external-deployment.py --require-full-proof` runs the same proof check against the merged manifest plus CLI values, with proof-file, password-env, encrypted-transport, and `live_reject_login_expected_statuses` presence checks, before it builds or packages anything. Desktop proof files must mention the same-host/local Java client, the external Java client, the external transport path, and that both clients were online concurrently; they must also include an `evidence` line pointing to a real non-symlink screenshot/log file. Placeholder notes, symlinked proof paths, and missing/symlinked/empty evidence files are rejected. Runtime backup proof files must mention character saves, account records, Discord secrets, a backup/archive artifact, date or timestamp, `backup archive sha256`, and that the backup did not start, stop, or restart the runtime; the readiness report and manifest checker reject symlinked proof notes, verify proof and archive owner-only POSIX modes when supported, check that the archive path exists and is not a symlink, match the SHA-256 in the proof, and require tar entries for `characters`, `accounts`, and `secrets.json`. For `client_tls_tunnel`, the verifier checks the operator-side stunnel folder when `--client-tls-tunnel-dir` is supplied, including TLS 1.2 minimum, client certificate-chain/hostname verification, server cert/key paths, and public-to-loopback forwarding. Prefer generating desktop proof with `scripts/write-desktop-client-proof.py --same-host-client LOCAL --external-client EXTERNAL --transport TRANSPORT --public-host HOST --evidence PATH`; add `--proof-manifest PATH` so the helper fills only `desktop_client_proof_file` after writing the proof note. Prefer generating backup proof with `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"` on the deployed host; it writes the archive and proof note without starting, stopping, or restarting the runtime. If the copied proof manifest already exists, add `--proof-manifest PATH` so the helper fills only `runtime_data_backup_proof_file` after the backup runs. The server deployment bundle also includes `proof-templates/desktop-client-proof.md` and `proof-templates/runtime-data-backup-proof.md` as fill-in starting points; copy them, replace every placeholder, then pass the completed notes to the readiness report directly or through the manifest. The report separates command success from deployment proof: `status: PASS` means the requested commands passed, while `deploymentProofStatus` and the proof coverage table say whether live network/login/client/chat/backup/Discord evidence is still missing. Add `--require-full-proof` only for a final deployment gate; it exits non-zero unless `deploymentProofStatus` is a full live proof status, and refuses source/test-only flags such as `--allow-placeholder-network-config`, `--allow-placeholder-discord-secrets`, `--allow-empty-accounts`, or `--allow-untrusted-client-tls`. A full-ready report also requires the encrypted/private transport gate; use `--require-encrypted-external` so the verifier rejects plaintext `direct_tcp` and requires package manifest `encrypted_external_required=1`. If the config has `agent_chat_discord_enabled=true`, Discord bot/channel, Discord-to-server, and server-to-Discord proof are required automatically before the report can claim full readiness. A live partial report uses `LIVE_PROOF_PARTIAL_NEEDS_...` with concrete missing categories; a complete network/auth/client/chat/backup proof with Discord disabled and no Discord flags reports `LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_PROOF_RECORDED_DISCORD_NOT_REQUESTED`; a complete live network/auth/client/chat/backup plus Discord round-trip report uses `FULL_LIVE_NETWORK_AUTH_CLIENT_CHAT_BACKUP_AND_DISCORD_PROOF_RECORDED`.

The readiness/prep path treats chat evidence as deployment proof, so it is stricter than the low-level helpers. Direct agent/player chat delivery proof is required for full readiness even when Discord is disabled: send one unique marker to an online player, verify the `agent_chat_player_delivery` audit event, and pass `--agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER --agent-chat-delivery-log-channel agent` to the readiness or prepare command. Prefer adding `--proof-manifest PATH` to `scripts/verify-agent-chat-log.py`; after a successful check it records the direct delivery, Discord ingestion, or blocked-routing fields in the copied manifest automatically. Discord-to-server proof is separate: `--agent-chat-log-text` must also include `--agent-chat-log-from-type discord --agent-chat-log-from-bot false`, and server-to-Discord proof cannot use `--discord-channel-message-allow-human-author`; `scripts/verify-discord-channel-message.py --proof-manifest PATH` records the server-to-Discord mirror fields. When `agent_chat_discord_enabled=true`, missing Discord proof keeps `deploymentProofStatus` partial even if the network/auth checks pass. When Discord routing allow-lists are configured, a full Discord readiness status also requires blocked-routing absence proof: send a blocked human/non-bot Discord marker and prove it stayed out of `AgentChatService` with `--agent-chat-blocked-log-text BLOCKED_MARKER` or the low-level `scripts/verify-agent-chat-log.py --text-contains BLOCKED_MARKER --from-type discord --from-bot false --expect-absent --proof-manifest PATH`.

After the remote server is intentionally running, use `scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"` for a focused network-only proof that public game/cache ports are reachable through the selected external transport and that the configured local agent bridge port, default `43610`, is not reachable at `public_game_host`. If remote player-agent mode is enabled, also run `scripts/probe-agent-bridge-gateway.py --gateway-url https://AGENT_GATEWAY_HOST` to prove the HTTPS gateway is reachable, approved endpoints work, unapproved `/agent/` paths are rejected, and raw bridge TCP is still private. The helpers do not package, build, log in, start, stop, or restart runtime. Use the full verifier/readiness `--live` path when the same network proof should be recorded with packaged artifacts and the rest of the deployment evidence. For `client_tls_tunnel`, `--live` performs a TLS 1.2+ handshake on the public game/cache tunnel endpoints instead of accepting plain TCP reachability. Use `--tls-sni-host HOST` if the tunnel certificate name differs from `public_game_host`; `--allow-untrusted-client-tls` exists for private self-signed tunnel tests, but a trusted certificate is preferred for real players. To prove account auth through the same path, pass `--live-login-username NAME --live-login-password-env ENV_VAR` with a throwaway PBKDF2 account. To prove simultaneous local and external play, also pass `--live-local-login-username LOCAL --live-local-login-password-env LOCAL_ENV`; the verifier keeps the external login socket open while it logs in over the same-host local path, defaulting to `127.0.0.1` and the configured game port unless `--live-local-host/--live-local-port` are supplied. For a focused protocol-only version of that coexistence check, run `scripts/probe-concurrent-logins.py --external-host HOST --external-username EXTERNAL --external-password-env EXTERNAL_PASSWORD --local-username LOCAL --local-password-env LOCAL_PASSWORD`; add `--tls --tls-sni-host HOST` when the external endpoint is a public `client_tls_tunnel`. `--live-local-host` and `--local-host` must remain `localhost` or a loopback IP address, so the same-host proof cannot be satisfied through a remote/private interface. To prove fail-closed auth over the same live path, pass `--live-reject-login-username NAME --live-reject-login-password-env ENV_VAR` with a wrong password, missing throwaway account, or disabled throwaway account; add `--live-reject-login-expected-statuses 3,4` for final readiness so the allowed rejection codes are pinned. Keep the emitted `live-check:`, `gateway-check:`, or `ok: concurrent game logins...` lines with deployment notes; they list the exact game/cache endpoints checked, the TCP/TLS mode, SNI when relevant, the bridge port confirmed non-reachable, and optional password-redacted login/rejection proof.

`verify-external-deployment.py` also rejects tracked sample network placeholders such as `server.example.com`, `REPLACE_WITH_PUBLIC_INTERFACE_IP`, `example-tailnet-host`, and `100.64.0.10`. Replace them with the actual public or private host and interface IP before distributing a client. `--allow-placeholder-network-config` exists only for source/sample validation and should not be used for a real deployment.

## Standalone Client And Browser Feasibility

The supported MVP client distribution is the packaged Java desktop client produced by `scripts/package-client.sh`. It is intentionally boring: a fat client jar, launcher scripts, macOS double-click `.command` wrappers, setup-check scripts, `client.properties`, manifest/checksum files, and a README that starts with a first-run checklist and names the expected external transport. That keeps the game protocol unchanged while making the connection target, cache ports, Java requirement, and direct/Tailscale/WireGuard/VPN/tunnel expectation visible to testers. The packaged launchers suppress only the legacy Java-version warning dialog; they still fail clearly when no `java` command is available. The setup checkers provide a no-login Java/config/TCP reachability check for player troubleshooting; Tailscale packages include non-fatal CLI/status hints before those checks. In `client_tls_tunnel` packages, the macOS/Linux setup checker starts the bundled stunnel config temporarily when `stunnel` is installed so it can test the encrypted path without a manual pre-step; the Windows setup checker keeps the simpler diagnostic path and expects the local tunnel endpoint to be reachable first. Those packages also include `client-tls-tunnel/INSTALL-STUNNEL.txt` because the client zip does not bundle stunnel binaries.

Package generation also refuses symlinked output directories, archive paths, or output parent directories before deleting or writing package artifacts.

The old browser/applet path is not viable for a modern deployment. Modern browsers do not run Java applets, and the current client still relies on `java.applet.Applet`, AWT/Swing frame and input handling, and raw Java sockets for the game, JAGGRAB, and on-demand cache protocols. A real browser version would be a separate client project: either a new web renderer plus WebSocket/WebTransport protocol adapter, a Java-to-WebAssembly/JVM-in-browser compatibility effort that replaces the desktop and socket layers, or a hosted streaming/remote-desktop style client. Treat that as future research, not part of the external-player MVP.

For `direct_tcp`, expose only the ports that the selected game/cache services actually need through the host firewall:

- `43594`: game and on-demand cache handshake
- `43595`: JAGGRAB cache fallback
- `8080`: HTTP cache fallback, if enabled

For Tailscale, WireGuard, or another VPN, keep those ports private to that transport instead of the public Internet.

Never expose:

- `43610`: local Codex agent bridge default; `agent_bridge_port` may be changed for isolated test deployments, but `agent_bridge_bind_host` must stay loopback-only

The agent bridge has bounded local HTTP workers, request backpressure, bounded JSON request bodies, and a bounded game-tick action queue for multi-agent development, but it is still a localhost control plane with bearer session tokens. It is not a public API or remote-agent transport.

The tracked `docker-compose.yml` server service is a local development helper. Its published game/cache ports are pinned to `127.0.0.1`, including game `43594`, JAGGRAB `43595`, and HTTP cache `8080`, so running Compose does not accidentally expose a plaintext game server on every host interface. For a remote deployment, use the explicit `ServerConfig.json` plus the selected `direct_tcp`, Tailscale, WireGuard, VPN, or tunnel setup in this document instead of treating the local Compose service as the production recipe.

## Live Proof Checklist

Source validation and static deployment verification are not live proof. Before calling an external deployment ready, prove these items on the actual host after an intentional rebuild/restart:

1. Run `scripts/preflight-external-config.py "2006Scape Server/ServerConfig.json"` on the final config.
2. Create at least one test PBKDF2 account with `scripts/create-account.py`, using a disposable 12+ character password passed through `ACCOUNT_PASSWORD` or an interactive prompt, then run `scripts/account-admin.py --require-password-policy audit` to validate account records before packaging.
3. Package the client from the same config with `CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" scripts/package-client.sh`, or use `scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"` to package, verify, and write a readiness report in one command.
4. Run `scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"` from a machine that has the selected external transport path if you need to isolate public game/cache reachability or bridge non-exposure problems before the full verifier. Then run `scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/agent-scape-client --server-deployment-dir dist/server-deployment --live`, or run the same check through `scripts/prepare-external-deployment.py --live` / `scripts/deployment-readiness-report.py --server-deployment-dir dist/server-deployment --live` when you want one Markdown evidence file. In `client_tls_tunnel` mode, this must complete TLS handshakes to the public tunnel endpoints; pass `--tls-sni-host` only when the certificate name intentionally differs from `public_game_host`. If Discord agent chat is enabled and real ignored secrets are present, add `--live-discord` to prove each bot token authenticates and can read its configured `channelId`; readiness reports require this proof automatically for Discord-enabled configs. Save the emitted `live-check:`, `discord-check:`, chat-log, and Discord mirror proof output lines or the readiness report as evidence.
5. Prove account auth over the same live path with a throwaway PBKDF2 account. Set the password in an environment variable, then pass `--live-login-username NAME --live-login-password-env ENV_VAR` to `verify-external-deployment.py --live`. The verifier logs in through the game protocol and prints a `live-check:` line without printing the password. For automated coexistence proof, add `--live-local-login-username LOCAL --live-local-login-password-env LOCAL_ENV` with a second account so the verifier keeps the external login open while it logs in locally. For a focused version of just that coexistence proof, use `scripts/probe-concurrent-logins.py --external-host HOST --external-username EXTERNAL --external-password-env EXTERNAL_PASSWORD --local-username LOCAL --local-password-env LOCAL_PASSWORD`. For automated fail-closed proof, add `--live-reject-login-username NAME --live-reject-login-password-env ENV_VAR --live-reject-login-expected-statuses 3,4` using a wrong password, missing throwaway account, or disabled throwaway account; final readiness requires pinned rejection status codes, and the verifier fails if that login is accepted.
6. For a focused login-only check, use `scripts/probe-game-login.py --host HOST --port 43594 --username NAME --password-env ENV_VAR`. Add `--tls --tls-sni-host HOST` for a `client_tls_tunnel` public endpoint, `--expect-failure` for wrong-password, missing-account, or disabled-account fail-closed checks, and `--expect-statuses 3,4` when you want to pin the allowed protocol rejection codes. Use `scripts/probe-concurrent-logins.py` when the focused proof needs the external login held open while a same-host loopback login succeeds.
7. Connect one local same-host client and one external client through the selected transport at the same time, then confirm both can remain online together after normal client login. The verifier's concurrent login proof covers the protocol path, not the whole desktop-client session. Prefer `scripts/write-desktop-client-proof.py --same-host-client LOCAL --external-client EXTERNAL --transport TRANSPORT --public-host HOST --evidence PATH --proof-manifest PATH` to record the operator note after the observation and update `desktop_client_proof_file`; it validates the existing screenshot/log evidence file and writes a readiness-compatible `--desktop-client-proof-file` without starting, stopping, restarting, logging in, or probing anything. The readiness report verifies that the evidence path exists, is a regular non-symlink file, and is not empty. A minimal accepted note looks like:

```markdown
# Desktop Client Coexistence Proof

- date: 2026-06-12
- server config: 2006Scape Server/ServerConfig.json
- same-host client: LocalTest connected through 127.0.0.1
- external client: ExternalTest connected through direct_tcp/Tailscale/WireGuard/client_tls_tunnel
- observed: both desktop clients remained online at the same time
- evidence: /path/to/desktop-client-coexistence-screenshot.png
```
8. Before replacing the deployed repo, rotating credentials, or restarting into new deployment bits, back up `data/characters`, `data/accounts`, and `data/secrets.json` with `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"` on the deployed host. Pass the generated `runtime-data-backup-proof-*.md` note to the readiness report with `--runtime-data-backup-proof-file PATH`; if the proof manifest already exists, add `--proof-manifest PATH` to update `runtime_data_backup_proof_file` automatically. The helper writes owner-only archive/proof files on POSIX systems and refuses symlinked runtime-data paths and symlinked archive/proof/manifest output paths, including symlinked output directories or parent directories, so the proof names real files and records that the helper did not start, stop, or restart the runtime. The readiness report rejects symlinked proof notes, verifies owner-only proof/archive modes where supported, and checks the archive path, `backup archive sha256`, required tar entries, no runtime start/stop/restart proof line, and readiness argument line. If the helper cannot be used, copy the generated template and fill in the same paths, archive artifact, archive checksum, date/timestamp, `readiness argument: --runtime-data-backup-proof-file PATH`, and runtime-unchanged statement manually.
9. Confirm a wrong password, missing account record, disabled account, or weak/tampered account record fails login instead of falling back to legacy character auth. Use the verifier's `--live-reject-login-*` flags plus `--live-reject-login-expected-statuses 3,4` for at least one live rejection proof, then use focused probes or account-record edits for additional rejection classes as needed.
10. Confirm the packaged client warns about the expected `secure.transport` value. For `direct_tcp`, Tailscale, WireGuard, and VPN modes it should connect to `public_game_host`; for `client_tls_tunnel` it should connect to loopback `client_connect_host` or `127.0.0.1` while the local plaintext tunnel connects encrypted TLS to `public_game_host`.
11. Prove direct agent/player chat delivery, even when Discord is disabled. Send a unique marker from an active agent bridge session with `agent_chat_send`/`agent_chat_send_XS` using a `player` target, or from a client with `::agentchat @player:PLAYER MARKER`, then verify the delivery audit event with `scripts/verify-agent-chat-log.py --event agent_chat_player_delivery --text-contains MARKER --to-type player --to-name PLAYER --delivered-to PLAYER --no-undelivered --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json`. Without a manifest, add the same marker to readiness/prep with `--agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER --agent-chat-delivery-log-channel agent`.
12. If `agent_chat_discord_enabled=true`, run `scripts/probe-discord-agent-bots.py --secrets "2006Scape Server/data/secrets.json"` to prove each configured bot token authenticates and can read its configured `channelId`. Add `--send-test-message` only when you intentionally want one sanitized probe message posted to each bot channel; bot-authored probe messages are ignored by the runtime and do not prove Discord-to-game ingestion. Then send a real human/non-bot Discord message with a unique marker and prove the running server logged it with `scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --discord-message-id DISCORD_MESSAGE_ID --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json` when the Discord message id is available. For server-to-Discord proof, send a unique in-game/agent chat marker and run `scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE --proof-manifest dist/external-deployment/deployment-proof-manifest.json`; the default requires the matching Discord message to be authored by the configured bot. If routing allow-lists are configured, full Discord readiness also requires a blocked human/non-bot Discord marker proven absent with `scripts/verify-agent-chat-log.py --text-contains BLOCKED_MARKER --from-type discord --from-bot false --channel agent --expect-absent --proof-manifest dist/external-deployment/deployment-proof-manifest.json`, or readiness-report `--agent-chat-blocked-log-text BLOCKED_MARKER --agent-chat-blocked-log-channel agent`.
13. Confirm the configured loopback agent bridge, default `127.0.0.1:43610`, is still only reachable from the server host and not from the external player network path.
14. After the final readiness report and proof manifest are written, run `scripts/package-deployment-proof.py --prepared-dir dist/external-deployment` for the normal `prepare-external-deployment.py` output, or pass explicit `--readiness-report`, `--readiness-json`, `--proof-manifest`, `--client-dist`, and `--server-deployment-dir` paths if you used lower-level commands. Add `--require-full-proof` for the final external-ready handoff; it fails unless the readiness JSON records a full live proof status and the proof manifest passes full-proof, encrypted-transport, and proof-file validation. The helper creates a non-secret handoff tarball for review, includes readiness/proof metadata plus selected client/server metadata such as `player-handoff-template.md`, and deliberately excludes runtime backup archives, character saves, PBKDF2 account records, `data/secrets.json`, passwords, bridge tokens, and Discord bot tokens.

At any point after a JSON readiness report exists, run `scripts/deployment-readiness-status.py --prepared-dir dist/external-deployment` or `--readiness-json PATH` to get a compact read-only summary of `deploymentProofStatus`, `externallyReady`, proof coverage, and remaining live proof. Add `--show-next-commands` to print command templates for the missing live/manual proof categories from that existing JSON; those templates preserve the report's config, account, secret, client, and deployment paths, create the proof manifest parent directory, copy the template only when the manifest is missing, write manual proof notes beside that manifest, pass that manifest to the desktop-proof and runtime-backup helpers with `--proof-manifest`, pass `--update-proof-manifest` to live readiness reports after successful checks, and pass the recorded `--secrets` path to the final proof-manifest check. Add `--fail-if-not-ready` when a wrapper should exit non-zero until the report proves full external readiness; this helper only reads the existing JSON and never probes, packages, starts, stops, or restarts runtime.

The external sample uses `game_bind_hosts`, `http_bind_hosts`, and `jaggrab_bind_hosts` with both `127.0.0.1` and `REPLACE_WITH_PUBLIC_INTERFACE_IP`. Replace the placeholder before real verification. That supports local same-host clients and external clients in one server process. If `file_server=true`, HTTP and JAGGRAB must also include at least one non-loopback bind host so packaged clients can reach the cache services over the selected external transport. If you instead bind `0.0.0.0`, bind wildcard alone for that listener, set `wildcard_bind_confirmed=true` in the config only after firewall or private-network rules are in place, then run the preflight with `--allow-wildcard-bind`. Use the same acknowledgement for dependent tooling: set `CLIENT_ALLOW_WILDCARD_BIND=1` when packaging from that config and pass `--allow-wildcard-bind` to `scripts/verify-external-deployment.py`.

Account records under `2006Scape Server/data/accounts/` are authoritative when account auth is enabled. Create them with `scripts/create-account.py`; it writes `PBKDF2WithHmacSHA256` records by default, rejects passwords shorter than 12 characters unless `--allow-weak-password` is explicitly passed for local throwaway/source-validation accounts, stamps `passwordPolicy` metadata on new or rotated records, and supports `--algorithm sha1` only as an older-Java-8 compatibility fallback. Use `scripts/account-admin.py list`, `show`, or `audit` to inspect records without full deployment verification; use `scripts/account-admin.py --require-password-policy audit` before external deployment, and use `scripts/account-admin.py disable USERNAME` or `enable USERNAME` to toggle access without rotating the password. Optional account metadata can be written with `--role`, `--allowed-character`, and `--discord-user-id`; a non-empty `allowedCharacters` list is enforced as a character-name allow-list during Java auth. Password verification uses the algorithm and iteration count stored in each account record; external-mode minimum iterations are enforced before verification as a fail-closed strength policy. Account audits cannot cryptographically recover the original password length from an existing PBKDF2 hash, so create or rotate real external accounts with the helper instead of hand-writing records; deployment verification rejects records missing helper-stamped `passwordPolicy` metadata or records created with the weak-password override. A wrong password, disabled account, disallowed character, weak external account record, symlinked account path, missing or weak-override password policy metadata, or invalid/tampered account JSON fails closed instead of falling back to legacy character-password auth. The in-game `::password` command is blocked after account-auth login because it cannot update PBKDF2 account records; use `scripts/create-account.py --overwrite --preserve-metadata` or an equivalent operator workflow to rotate external account passwords without dropping roles, allowed characters, Discord user id, or disabled state. Repeated failed account-auth attempts are temporarily rate-limited per account and per connecting source address; missing-account attempts are source-throttled when legacy fallback is disabled. The in-memory throttle table is bounded and prunes expired entries. The helper, account admin tool, Java auth service, and deployment verifier all reject symlinked account records; deployment verification and strict `account-admin.py` audit also reject account files that the Java auth service cannot load, including invalid usernames, filename/username mismatches, malformed base64 hash or salt fields, wrong hash/salt sizes, weak iteration counts, unsupported algorithms, non-boolean `disabled` flags, malformed `roles` or `allowedCharacters` arrays, malformed or missing external password policy metadata, non-numeric Discord user ids, and group/world-readable account directories or records on POSIX systems.

## Future Public Self-Signup

External deployments should keep `account_auth_auto_create=false`. The game
login path is not the right public registration surface because it cannot safely
enforce invite policy, rate-limit unauthenticated signup attempts, or provide
operator audit context. A real self-service flow should be a separate HTTPS
registration service or operator panel that:

- requires invite codes or an allow-listed identity before account creation;
- rate-limits by source address, invite code, username, and failed attempts;
- enforces the same minimum password policy and PBKDF2 account-file schema as
  `scripts/create-account.py`;
- writes owner-only account JSON files with roles, allowed-character metadata,
  Discord user id when applicable, and helper-stamped `passwordPolicy`;
- writes redacted audit logs for invite use, created account, source, timestamp,
  and operator/user identity without logging passwords;
- never exposes `data/secrets.json`, runtime backups, character saves, or raw
  AgentBridge port `43610`.

That is future work. For the current MVP, operators create accounts with
`scripts/prepare-player-package.py`, `scripts/provision-player-account.py`, or
`scripts/create-account.py`, then install the generated account record on the
deployment host.

## Tailscale

Tailscale is the preferred turnkey encrypted private-beta transport. Use `external_transport_mode: "tailscale"` and bind game/cache services to the server's Tailscale interface IP. For same-host local clients plus Tailscale clients, set the plural bind arrays to `["127.0.0.1", "<tailscale-interface-ip>"]`.

Pros:

- Encryption and identity are handled by a mature tool.
- No game protocol changes.
- Minimal operational burden.

Cons:

- Players need Tailscale.
- Not a public-server onboarding flow.

## WireGuard

WireGuard is similar to Tailscale but more manual.

Pros:

- Mature, fast, simple encrypted tunnel.
- You control keys and firewall rules directly.

Cons:

- More setup/admin work than Tailscale.
- No built-in invite UX or MagicDNS unless you add it.

Use `external_transport_mode: "wireguard"` or `"vpn"` and bind game/cache services to the WireGuard interface IP.

For same-host local clients plus WireGuard clients, set the plural bind arrays to `["127.0.0.1", "<wireguard-interface-ip>"]`.

## Public VPS With Client TLS Tunnel

A server-only TLS proxy does not encrypt this client by itself, because the game client does not initiate TLS. A public TLS setup needs either:

- a client-side tunnel such as stunnel/HAProxy on each player machine, connecting TLS to the VPS and forwarding localhost plaintext to the game client, or
- future in-protocol TLS support in both `Game.openSocket` and the Netty pipeline.

This can work, but it is more moving parts than the VPN MVP. Use `external_transport_mode: "client_tls_tunnel"` only when both sides of the tunnel are deployed and tested. Start from `2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json` when you want a concrete tracked template for this path. Replace `REPLACE_WITH_PUBLIC_TLS_HOST` with the DNS name that has a certificate and stunnel listener before packaging a real client. The deployment verifier's `--live` mode requires TLS handshakes on the public tunnel endpoints so a plain TCP proxy cannot accidentally satisfy the tunnel proof.

For this mode, `public_game_host` is the remote TLS tunnel endpoint used by deployment checks and operator docs. The Java client still speaks plaintext, so packaged clients connect only to loopback `client_connect_host`, defaulting to `127.0.0.1`, where the player-side plaintext tunnel listens. The preflight and package script reject non-loopback `client_tls_tunnel` client targets so a downloadable client cannot accidentally send plaintext to the public TLS endpoint. The server game/cache listeners may be loopback-only because the server-side tunnel terminates encrypted external traffic and forwards it locally. The server-side tunnel accept host defaults to `public_game_host`; set `client_tls_tunnel_server_accept_host` to a real, non-placeholder, specific public interface address or hostname if the certificate hostname is not bindable locally. Do not use wildcard here, because `0.0.0.0:<port>` can collide with the Java server's required `127.0.0.1:<port>` listener.

Generate concrete stunnel templates from the same server config:

```sh
scripts/render-client-tls-tunnel-config.py --config "2006Scape Server/ServerConfig.json" --output-dir dist/client-tls-tunnel-operator
```

`stunnel-client.conf` listens on the configured loopback `client_connect_host` and forwards TLS to `public_game_host` on the game/cache ports. The generated player-side config verifies the certificate chain, checks the certificate hostname, and requires TLS 1.2 or newer. `stunnel-server.conf` listens on `client_tls_tunnel_server_accept_host` or `public_game_host` on those same ports, uses the Let's Encrypt-style certificate paths for the certificate host, requires TLS 1.2 or newer, and forwards plaintext to `127.0.0.1`. If `--tls-sni-host` is supplied to render or verify a different certificate hostname, it must be a real non-placeholder certificate host, not localhost or wildcard. `package-client.sh` includes the player-side README, `INSTALL-STUNNEL.txt`, and `stunnel-client.conf` automatically for `client_tls_tunnel` packages, and generated launchers try to start that config before opening the Java client when `stunnel` is available; keep the server-side template with operator deployment notes instead of sending it as the normal player client.

## Server Service Templates

For VPS/GCE-style hosts, generate server-side operator files from the same config:

```sh
scripts/render-server-deployment-files.py --config "2006Scape Server/ServerConfig.json" --output-dir dist/server-deployment
```

The generated systemd unit runs `scripts/start-server.sh` from the deployed repo as a non-root `2006scape` service user, uses an immutable copied jar through `SERVER_RUN_DIR`, reads `/etc/2006scape/ServerConfig.json`, sets a restrictive `UMask`, drops ambient and bounding capabilities, restricts address families to IPv4/IPv6/Unix sockets, enables systemd sandboxing for devices, temp files, kernel/control-group settings, and keeps the agent bridge loopback-only by config. Java startup and the Python deployment tools reject network host/transport values containing control characters before they can become listener addresses, package properties, manifests, or stunnel lines. The renderer rejects malformed service user/group names, root service identity, deployment paths with whitespace/control characters, and unsafe VPN interface names before writing deployment artifacts. The bundle also includes a dry-run UFW helper for the selected transport; generated UFW commands and README install snippets are argument-quoted. For Tailscale configs, it also includes `tailscale-policy-grants.example.json` with only the configured game/cache ports and no agent bridge grant. The generated README shows where to create/copy owner-only PBKDF2 account records and `data/secrets.json` under the deployed `2006Scape Server/data/` tree; do not symlink either path. It also names `data/characters`, `data/accounts`, and `data/secrets.json` as runtime data to back up before a deployment replacement, credential rotation, config migration, or intentional remote restart, recommends `scripts/backup-runtime-data.py` for archive/proof creation, and includes fill-in proof templates under `proof-templates/`. The firewall helper must be reviewed first; execute it only with `APPLY=1` after Tailscale/WireGuard/stunnel is intentionally ready.

`render-server-deployment-files.py` runs `scripts/preflight-external-config.py` before creating the output directory, so malformed external configs do not leave partial systemd/firewall artifacts. If a deployment deliberately uses wildcard bind hosts, pass `--allow-wildcard-bind` to the renderer or to `scripts/prepare-external-deployment.py`; the config still must set `wildcard_bind_confirmed=true`.

## Hosting Choice

VPS:

- Best first public host if using Tailscale/WireGuard or a paired client TLS tunnel.
- Pros: simple static IP, direct TCP support, low cost, straightforward systemd/firewall setup, and compatibility with Tailscale, WireGuard, stunnel, HAProxy, and the generated deployment templates.
- Cons: you own OS patching, firewall policy, backup discipline, TLS certificate renewal, monitoring, log retention, and incident response.

Google Cloud Compute Engine:

- Good if infrastructure discipline matters early.
- Pros: stronger IAM, firewall controls, snapshots, logging, monitoring, static IPs, and a cleaner path to infrastructure-as-code.
- Cons: more setup, more cost, and still effectively a VM running a long-lived custom TCP game server.

Tailscale/WireGuard overlay:

- Best initial encrypted external-player test, including local plus remote players on one server process.
- Pros: no public plaintext game port exposure, mature encryption/identity, and no game protocol changes.
- Cons: players must install or join the overlay; this is a private-beta UX, not open public onboarding.

Public VPS with client TLS tunnel:

- Useful when players should not join a VPN but the Java client still cannot speak TLS itself.
- Pros: public hostname, standard TLS certificates, and no Java game-protocol changes.
- Cons: every player must run a local tunnel, both client/server tunnel configs must be managed, and live verification must prove TLS handshakes on the public endpoints.

Cloud Run/serverless:

- Not recommended for the game server.
- Pros: good for stateless HTTP services.
- Cons: poor fit for long-lived custom TCP sessions, local character/account data, the current Java runtime model, and the existing game/cache socket protocols.

## Config Guardrails

When `external_players_enabled=true`, startup requires fail-closed account auth and an explicit external transport acknowledgement. The simple direct public mode is:

```json
"secure_external_transport_confirmed": false,
"direct_tcp_external_transport_confirmed": true,
"external_transport_mode": "direct_tcp",
"require_secure_external_transport": false,
"wildcard_bind_confirmed": false,
"account_auth_enabled": true,
"account_auth_auto_create": false,
"account_auth_legacy_fallback": false,
"account_auth_pbkdf2_iterations": 120000
```

Allowed modes are:

- `direct_tcp`
- `tailscale`
- `wireguard`
- `vpn`
- `client_tls_tunnel`

The transport fields are an explicit operator acknowledgement. `direct_tcp` is allowed only when `require_secure_external_transport=false` and `direct_tcp_external_transport_confirmed=true`; it does not encrypt the legacy protocol. Tailscale, WireGuard, VPN, and `client_tls_tunnel` require `require_secure_external_transport=true` and `secure_external_transport_confirmed=true`, but those fields do not magically encrypt traffic; the named transport must actually be deployed. `wildcard_bind_confirmed` is a separate acknowledgement for broad bind addresses such as `0.0.0.0`; leave it `false` unless the host firewall or private-network boundary has already been verified. Do not mix wildcard bind hosts with specific hosts in the same listener array; use wildcard alone or list the exact interfaces. The account-auth fields are enforced by Java startup for external-player mode so external logins use pre-created PBKDF2 account records with at least 120,000 iterations and fail closed instead of falling back to legacy character-password auth. Java startup also rejects malformed typed bind-host config, external-player configs with a loopback/wildcard `public_game_host`, wildcard-plus-specific bind arrays, or unconfirmed wildcard bind hosts. Direct TCP and overlay VPN modes require non-loopback game/cache bind hosts; `client_tls_tunnel` may use loopback-only game/cache binds because the encrypted tunnel endpoint forwards into the local listener, and its packaged client target must be loopback. `client_tls_tunnel_server_accept_host` must be a specific non-loopback, non-wildcard, non-placeholder host so the public stunnel listener can coexist with the loopback Java listener on the same ports.

A generic private network is not an allowed `external_transport_mode` by itself. If the private path is encrypted, describe it as `tailscale`, `wireguard`, `vpn`, or `client_tls_tunnel`; if it is only a LAN/VPC/public plaintext path, describe it as `direct_tcp` and keep the plaintext acknowledgement fields explicit.

Java startup also validates effective game, HTTP, and JAGGRAB ports, rejects overlapping listener ports when `file_server=true`, and rejects external `file_server=true` configs whose HTTP or JAGGRAB bind hosts are loopback-only unless `external_transport_mode` is `client_tls_tunnel`. The preflight performs the same distinct-port and cache-bind checks before packaging or deployment and allows overlapping or loopback-only cache ports only when `file_server=false` or when a client/server TLS tunnel is the configured secure transport. For `client_tls_tunnel`, preflight and packaging additionally require the packaged client host to be loopback. At runtime, local/dev servers may still tolerate HTTP cache bind failure and fall back to JAGGRAB, but external-player mode treats HTTP cache bind failure as fatal so the deployment does not silently lose a configured cache listener.

PBKDF2 account passwords are exact strings. The external-account path does not trim leading or trailing spaces before verification; the old trim behavior and in-game `::password` command remain only for legacy character-password fallback.

If an explicit `-c` / `-config` file cannot be read or fails this validation, server startup exits instead of silently falling back to local defaults. Validate the source-side implementation without starting the live runtime:

```sh
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.External.Sample.json"
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.Tailscale.Sample.json"
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/agent-scape-client --server-deployment-dir dist/server-deployment
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/agent-scape-client --server-deployment-dir dist/server-deployment
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"
scripts/render-server-deployment-files.py --config "2006Scape Server/ServerConfig.json" --output-dir dist/server-deployment
scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --discord-message-id DISCORD_MESSAGE_ID --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/validate-network-auth-chat.sh
scripts/smoke-network-auth-chat-runtime.py
```

The isolated smoke uses random alternate localhost ports, creates unique throwaway PBKDF2 account records, logs two accounts in through the game TCP protocol concurrently, proves one account rejects a wrong password, proves one disabled account rejects a correct password, removes the throwaway account/character files it created, and kills only its own child server. It is useful before a live deployment test, but it does not prove a real external transport path or packaged GUI client login.

## Discord Agent Transport

Per-agent Discord bots are configured in ignored `2006Scape Server/data/secrets.json`. Start by copying the tracked placeholder:

```sh
cp "2006Scape Server/data/secrets.External.Sample.json" "2006Scape Server/data/secrets.json"
```

Then replace every placeholder token/channel value locally and keep the real `secrets.json` owner-only, for example `chmod 600 "2006Scape Server/data/secrets.json"` on POSIX systems. If the server creates a missing default secrets file on first run, it writes that file owner-only where the filesystem supports POSIX permissions; when it loads an existing regular file, it tightens permissions to owner-only before reading; symlinked secrets are refused. The real file is ignored and must not be committed. `scripts/verify-external-deployment.py` rejects placeholder, symlinked, or group/world-readable Discord secrets by default; `--allow-placeholder-discord-secrets` is only for source/sample validation and must not be used for a real deployment.

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

Enable mirroring in server config:

```json
"agent_chat_discord_enabled": true
```

Enable the server-side structured chat audit log independently:

```json
"agent_chat_log_enabled": true
```

When enabled, sanitized message envelopes are appended under `2006Scape Server/data/logs/agent-chat/<yyyy-MM-dd>/agent-chat.jsonl`. The external sample enables this because it helps debug player/agent/Discord routing without exposing bridge tokens or Discord bot tokens.

Discord channel messages enter `AgentChatService` for the configured agent. Plain Discord text is addressed to that agent. Use `@agent:Name message` for another agent, `@player:Name message` to queue delivery to an online player's game chatbox on the next server tick, and `@all message` to broadcast to the shared agent channel and queue delivery to online game clients. The in-game player command supports the same routing shape through `::agentchat @agent:Name message`, `::agentchat @player:Name message`, `::agentchat @all message`, and `::agentchat #channel message`. Optional `allowedAgents` and `allowedPlayers` restrict Discord-originated target names; omit them for compatible open routing. If present, each allow list must be a comma-separated string or JSON array of non-empty names. Set `allowBroadcast:false` as a real JSON boolean to disable `@all`. Agent chat messages mirror back through the matching agent bot with Discord mentions escaped so in-game/agent text cannot ping `@everyone`, `@here`, users, or roles. Discord callbacks only enqueue chat messages; they do not execute gameplay actions or write client packets directly.

Keep exactly one `agent-discord-bots` entry per agent/profile name. `scripts/verify-external-deployment.py` rejects duplicate agent bot configs, malformed Discord field types, empty explicit allow lists, non-boolean broadcast flags, unreplaced placeholder token/channel values, symlinked secrets files, and group/world-readable real secrets before deployment. The runtime keeps the first usable config if duplicates are accidentally present and ignores malformed bot configs rather than coercing them.

Use `scripts/probe-discord-agent-bots.py --secrets "2006Scape Server/data/secrets.json"` for the focused Discord live check. It uses Discord REST to authenticate each bot token and verify `channelId` reachability without sending messages by default. `--agent NAME` narrows the check to one profile, `--send-test-message` posts one sanitized probe message to each configured `channelId`, and `--dry-run --allow-placeholder-discord-secrets` is only for validating tracked sample shape without network calls. To prove server-to-Discord mirroring, send a unique marker through real in-game/player or agent chat and run `scripts/verify-discord-channel-message.py --text-contains MARKER --agent NAME`; by default it only accepts messages authored by the configured bot, so a human-authored Discord message cannot satisfy mirror proof.
