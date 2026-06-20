---
name: 2006scape-external-deployment
description: Use when working in $REPO_ROOT on external-player networking, direct_tcp public transport, encrypted/private transport, PBKDF2 account auth, standalone client packaging, remote player-agent HTTPS gateway, deployment readiness, live proof collection, Discord transport proof, or remote VPS/GCE/Tailscale/WireGuard/client_tls_tunnel deployment artifacts for the network-auth-chat worktree.
---

# 2006Scape External Deployment

Use this skill for the external-player deployment track: network binds, `direct_tcp` public plaintext transport, encrypted/private transport alternatives, account auth, packaged clients, remote player-agent `/agent` gateway, readiness reports, runtime-data backup proof, and Discord transport proof.

Pair with `2006scape-dev-editing` for code changes. Pair with `2006scape-agent-bridge-dev` only when changing bridge primitives such as `agent_chat_send_XS`, `agent_chat_read_XS`, or `agent_chat_status_XS`.

## Boundaries

- Do not restart, stop, relaunch, or replace the live server/client unless the user explicitly asks for live proof.
- Source validation is not live readiness. A green build, verifier, or readiness report without live proof still means the deployment is not externally ready.
- Keep local development defaults intact: local configs stay loopback-first, legacy character-password login stays available locally, and Docker Compose published ports stay loopback-only.
- Never expose raw `AgentBridgeServer`/`43610`; it is a loopback control plane with bearer session tokens, not a public API. Remote player-agent mode uses an HTTPS gateway that exposes only approved `/agent/*` endpoints.
- Do not print passwords, bridge tokens, Discord bot tokens, API keys, nonces, or real secret file contents.

## Read First

Load only the file needed for the task:

- `docs/external-deployment-quickstart.md`: short first-live-test path for the recommended Tailscale encrypted deployment, with `direct_tcp` documented only as an explicit plaintext smoke path.
- `docs/player-agent-mode/README.md`: packaged-client `/agent` and repo-side remote-claim usage.
- `docs/vps-direct-tcp-deployment-notes.md`: local operator notes for the active VPS test path, private credential env-file handling, profile login probes, and repo-side Codex control of named profiles.
- `docs/agent-bridge-gateway.md` and `docs/config/templates/agent-bridge-gateway.nginx.conf`: public-safe HTTPS gateway render/probe workflow and static Nginx template.
- `docs/network-auth-agent-chat-design.md`: design, implemented surfaces, requirement matrix, validation plan, and future decisions.
- `docs/deployment-networking.md`: operator workflow, hosting tradeoffs, `direct_tcp`, Tailscale/WireGuard/VPN/client_tls_tunnel setup, live proof checklist.
- `README.md`: short operator commands and current project entry points.
- `AGENTS.md`: repo-wide runtime, security, and local-development rules.

## Normal Source Workflow

Use this path for edits and static validation that must not disturb the live runtime:

```sh
python3 agent-navigation/tools/script_registry.py search "deployment"
python3 agent-navigation/tools/script_registry.py search "client"
python3 agent-navigation/tools/script_registry.py search "tls tunnel"
python3 agent-navigation/tools/script_registry.py search "remote bridge"
python3 agent-navigation/tools/script_registry.py search "proof"
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.External.Sample.json"
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.Tailscale.Sample.json"
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json"
scripts/validate-network-auth-chat.sh
```

When Docker Desktop is available and the normal wrapper passes:

```sh
RUN_DOCKER_BUILD=1 scripts/validate-network-auth-chat.sh
```

The validation wrapper covers focused Java tests, full Maven tests, Python helper syntax, script-registry metadata, documentation coverage, package smoke tests, deployment verifier negative tests, an isolated alternate-port runtime smoke with concurrent accepted PBKDF2 logins plus wrong-password, disabled-account, and missing-account rejection, and representative Java 8 classfile checks. The Docker mode adds the Java 8 compose build.

## Packaging And Static Deployment Checks

For a real config, use the prepare wrapper first:

```sh
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.json"
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json" --require-encrypted-external
scripts/deployment-readiness-status.py --prepared-dir dist/external-deployment --show-next-commands
```

Use `--require-encrypted-external`, or `CLIENT_REQUIRE_ENCRYPTED_EXTERNAL=1` for direct `package-client.sh` calls, when producing a downloadable player package that must satisfy the encrypted-transport goal. It allows Tailscale, WireGuard/VPN, and `client_tls_tunnel`; it refuses plaintext `direct_tcp` before package artifacts are written.

Lower-level commands:

```sh
CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" scripts/package-client.sh
CLIENT_AGENT_BRIDGE_URL=https://AGENT_GATEWAY_HOST CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" scripts/package-client.sh
scripts/render-server-deployment-files.py --config "2006Scape Server/ServerConfig.json" --output-dir dist/server-deployment
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --json-output dist/deployment-readiness-report.json
```

Use `--json-output PATH` when automation or handoff records need machine-readable `status`, `deploymentProofStatus`, command summaries, proof coverage, and remaining live-proof items alongside the Markdown report. `prepare-external-deployment.py` passes this flag through when supplied.

The generated `server-deployment/player-handoff-template.md` is the public-safe operator checklist for giving one player access. After a prepared bundle exists, prefer `scripts/provision-player-account.py PLAYER --character CHARACTER --prepared-dir dist/external-deployment`; it creates the ignored PBKDF2 account record, audits it, writes the password only to an owner-only ignored credentials env file, and renders the player handoff note without printing the password. Then run `scripts/package-player-kit.py PLAYER --character CHARACTER --prepared-dir dist/external-deployment` to create the public-safe player zip containing the client archive, README-first handoff note, and checksums while excluding passwords, private credentials, account records, secrets, runtime data, and bridge tokens. Before sending the zip, run `scripts/verify-player-kit.py --kit dist/external-deployment/player-kit-PLAYER.zip --prepared-dir dist/external-deployment --username PLAYER --character CHARACTER` to re-check required entries, embedded checksums, nested client archive safety, optional matches against the prepared bundle, and absence of private runtime data. Use `scripts/render-player-handoff.py --prepared-dir dist/external-deployment --username PLAYER --character CHARACTER --output dist/external-deployment/player-handoff-PLAYER.md` when the account/password already exists and only the note needs rendering. Do not send account JSON files, `data/secrets.json`, runtime backup archives, bridge session files, bridge tokens, claim nonces, API keys, or Discord bot tokens.

Use `scripts/deployment-readiness-status.py --readiness-json PATH` or `--prepared-dir dist/external-deployment` when you only need to reread an existing JSON report and see whether `externallyReady` is proven. Add `--show-next-commands` to print command templates for the missing live/manual proof categories from that JSON; the templates preserve the report's config, account, secret, client, and deployment paths, create the proof manifest parent directory, copy the template only when the manifest is missing, write manual proof notes beside that manifest, pass that manifest to the desktop-proof and runtime-backup helpers with `--proof-manifest`, pass `--update-proof-manifest` to live readiness reports after successful checks, and the final manifest check passes `--secrets` so Discord routing-filter requirements are considered. It is read-only and does not rerun preflight, probes, packaging, startup, shutdown, or restart. Add `--fail-if-not-ready` only in wrappers that should exit non-zero until the report has full live proof.

For collected live/manual proof, prefer a JSON manifest over a very long final command:

```sh
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --proof-manifest PATH
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --update-proof-manifest PATH
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json" --proof-manifest PATH
scripts/check-deployment-proof-manifest.py PATH --config "2006Scape Server/ServerConfig.json" --secrets "2006Scape Server/data/secrets.json" --require-full-proof --check-files
scripts/package-deployment-proof.py --prepared-dir dist/external-deployment
```

The generated server bundle includes `server-deployment/proof-templates/deployment-proof-manifest.json`. Copy it, replace placeholders, remove unused Discord fields, and store only password environment-variable names such as `EXTERNAL_PASSWORD`, never password values or Discord tokens. Use `--update-proof-manifest PATH` on a successful readiness-report run when live proof fields should be written back into a copied manifest that may still contain unrelated placeholders. Use the full `scripts/check-deployment-proof-manifest.py PATH --config ... --secrets ... --require-full-proof --check-files` form for a quick structural/full-proof completeness check before running the heavier readiness/prep command. With `--check-files`, it validates Discord routing requirements plus encrypted/private transport, desktop proof evidence, and runtime-backup archive/checksum details, not just path existence. For final-gate checks, the manifest itself must keep `require_full_proof:true` and `require_encrypted_external:true`; do not rely on only the caller's CLI flag to make the proof bundle self-describing. When `prepare-external-deployment.py` is run with `--require-full-proof`, it also runs this check early against the merged manifest plus CLI values, including proof-file, password-env, encrypted-transport, and `live_reject_login_expected_statuses` presence, before packaging. Unedited placeholder values in the template are rejected before proof checks run. CLI flags override manifest fields for one-off reruns.

Manifest-owned proof-note file paths are resolved relative to the manifest file unless they are absolute or overridden by CLI flags. In the normal `dist/external-deployment/` handoff, keep `deployment-proof-manifest.json`, `desktop-client-proof.md`, and `runtime-data-backup-proof.md` together and use short filenames in the manifest.

After the final readiness report is generated, use `scripts/package-deployment-proof.py` only for non-secret handoff evidence. Prefer `--prepared-dir dist/external-deployment` for the normal `prepare-external-deployment.py` output; add `--require-full-proof` for the final external-ready handoff so the bundle fails unless the readiness JSON records a full live proof status and the proof manifest passes full-proof, encrypted-transport, and proof-file validation. It resolves the prepared readiness report, JSON report, client metadata, server-deployment metadata, and copied `deployment-proof-manifest.json` when present. It bundles readiness Markdown/JSON, the filled proof manifest, proof notes, and selected client/server metadata including `server-deployment/player-handoff-template.md`, but deliberately excludes runtime-data backup archives, `data/characters`, `data/accounts`, `data/secrets.json`, passwords, bridge tokens, and Discord bot tokens.

Use `--allow-placeholder-network-config`, `--allow-placeholder-discord-secrets`, or `--allow-empty-accounts` only for tracked sample/source validation. Do not combine source/test-only allowances with `--require-full-proof`.

Use `2006Scape Server/ServerConfig.Tailscale.Sample.json` for the recommended turnkey encrypted private-beta source sample, `2006Scape Server/ServerConfig.External.Sample.json` for the simplest `direct_tcp` source sample, and `2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json` for the paired stunnel source sample. The Tailscale sample binds game/cache services to the tailnet interface and packages clients against the Tailscale host, so players must be connected to the tailnet first; prepared Tailscale bundles include `server-deployment/tailscale-policy-grants.example.json` with only the configured game/cache ports and no agent bridge grant. The TLS tunnel sample keeps Java listeners on loopback and uses `REPLACE_WITH_PUBLIC_TLS_HOST` for the public stunnel endpoint; replace it before real packaging. `CLIENT_ALLOW_PLACEHOLDER_NETWORK_CONFIG=1` is only for source validation of placeholder samples.

Client manifests include `source_server_config_sha256`; package and verify from the same final config file so the verifier can reject stale or mismatched client artifacts, unexpected files, symlinked client package paths, and symlink-type zip entries. For `client_tls_tunnel`, `prepare-external-deployment.py` also renders operator-side stunnel templates and passes them to readiness verification with `--client-tls-tunnel-dir`; lower-level verifier/report calls should include that directory when it exists. The operator-side stunnel accept host comes from `client_tls_tunnel_server_accept_host` or `public_game_host`; use a real non-placeholder, non-wildcard host because wildcard can collide with the loopback Java game/cache listeners on the same ports. If `--tls-sni-host` is supplied, it must be the real certificate hostname, not a placeholder, loopback host, or wildcard.

For remote player-agent mode, package `agent.bridge.url` with an HTTPS `/agent` gateway:

```sh
scripts/render-agent-bridge-gateway-config.py --server-name AGENT_GATEWAY_HOST --output /tmp/2006scape-agent-bridge.nginx.conf
CLIENT_AGENT_BRIDGE_URL=https://AGENT_GATEWAY_HOST CLIENT_SERVER_CONFIG="2006Scape Server/ServerConfig.json" scripts/package-client.sh
scripts/probe-agent-bridge-gateway.py --gateway-url https://AGENT_GATEWAY_HOST
```

The gateway proof is separate from public game/cache proof: it must show approved `/agent` endpoints reachable, unapproved `/agent/` paths rejected, and raw TCP `43610` not reachable from the external path.

For temporary self-signed IP gateways, run the gateway probe with
`--allow-untrusted-tls`. For repo-side `remote_claim.py`, set `SSL_CERT_FILE`
to an ignored local copy of the gateway certificate; do not commit the cert or
session file:

```sh
scripts/probe-agent-bridge-gateway.py --gateway-url https://AGENT_GATEWAY_HOST --allow-untrusted-tls
SSL_CERT_FILE=agent-navigation/.local/certs/agent-gateway-selfsigned.crt python3 agent-navigation/tools/remote_claim.py --profile PROFILE --bridge-url https://AGENT_GATEWAY_HOST --verify
```

For a repo Codex thread controlling one named VPS character, use the player-agent README and VPS notes. Do not paste passwords or tokens. Source private credentials only into the shell when launching or probing a client login, then claim through the HTTPS gateway:

```sh
python3 agent-navigation/tools/remote_claim.py --profile PROFILE --bridge-url https://AGENT_GATEWAY_HOST --verify
RS_PROFILE=PROFILE agent-navigation/tools/observe_XS.sh
```

When several Java clients are open, never type the printed claim into a window chosen by order, such as "last Java process" or "frontmost Java window". Current client builds include the logged-in character in the window title after login, for example `2006Scape - MrFlame World: 1`; target the window whose title contains the requested profile, or close/relaunch only that profile's client before claiming. If `remote_claim.py` reports a claimed-player mismatch, discard that nonce, rerun the helper for a fresh command, and target the correct character-titled client.

If no HTTPS gateway URL or valid profile session file is available, stop and ask the operator. Do not expose raw TCP `43610` as a shortcut.

Package generation also refuses symlinked output directories, archive paths, or output parent directories before deleting or writing package artifacts.

Packaged client README text must stay player-facing: a short first-run checklist, Java install guidance, setup-check commands, transport setup, operator-provided username/password guidance, and a no-password-reuse warning. The package includes macOS double-click `Run-2006Scape.command` and `Check-Setup.command` wrappers, plus `check-setup-macos-linux.sh` and `check-setup-windows.bat` so players can verify Java, print `client.properties`, and attempt TCP checks without logging in or changing server state. Tailscale package checkers should keep non-fatal CLI/status hints before TCP checks so player troubleshooting starts with "is the tailnet connected?" instead of login/auth guessing. For `client_tls_tunnel`, packaged launchers must try to start the bundled player-side stunnel config automatically when `stunnel` is installed and still show a clear manual fallback when it is not; the macOS/Linux setup checker may also start the bundled stunnel config temporarily for no-login TCP diagnostics, while the Windows checker expects the local tunnel endpoint to be reachable first. This matters most for `direct_tcp`, where regular players do not need a VPN/tunnel but the legacy game/cache protocol is plaintext to the public host.

The browser-client investigation is settled for this MVP: Java applet mode is not viable in modern browsers, and the current client depends on AWT/Swing plus raw game/cache sockets. Do not spend MVP implementation time trying to revive applet/browser play; treat it as a separate future web-client, protocol-adapter, WebAssembly, or streaming project.

## Runtime Data Backup

Before replacing deployed files, rotating credentials, migrating config, or intentionally restarting into new deployment bits, back up deployed runtime data:

```sh
scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"
scripts/backup-runtime-data.py --data-dir "2006Scape Server/data" --proof-manifest dist/external-deployment/deployment-proof-manifest.json
```

Pass the generated proof note to readiness tooling:

```sh
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --runtime-data-backup-proof-file PATH
```

The optional `--proof-manifest` flag updates only the manifest's `runtime_data_backup_proof_file` with the generated proof-note path; other manifest fields are preserved. The helper archives `data/characters`, `data/accounts`, and `data/secrets.json`, writes owner-only archive/proof files on POSIX systems, writes a readiness-compatible proof note, refuses symlinked runtime-data paths and symlinked archive/proof/manifest output paths, including symlinked output directories or parent directories, and does not start, stop, or restart the runtime. Readiness validation rejects symlinked proof notes, verifies the proof/archive owner-only modes where supported, and checks the proof's archive path, `backup archive sha256`, required tar entries, the no runtime start/stop/restart proof line, and the `readiness argument: --runtime-data-backup-proof-file ...` line, so keep the archive with the proof or use an absolute archive path.

## Live Proof Gate

Run these only after the remote server is intentionally built, configured, and running:

```sh
scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"
scripts/probe-agent-bridge-gateway.py --gateway-url https://AGENT_GATEWAY_HOST
scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live
```

Use `probe-deployment-network.py` first when you only need public game/cache reachability plus agent bridge non-exposure; it does not package, build, log in, start, stop, or restart runtime. Use the full verifier/readiness path to record artifact-coupled live proof.

Add live account proof with environment-held throwaway passwords:

```sh
EXTERNAL_PASSWORD="throwaway external password" LOCAL_PASSWORD="throwaway local password" scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --live-login-username EXTERNAL_TEST --live-login-password-env EXTERNAL_PASSWORD --live-local-login-username LOCAL_TEST --live-local-login-password-env LOCAL_PASSWORD
REJECT_PASSWORD="wrong or disabled-account password" scripts/verify-external-deployment.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --live --live-reject-login-username REJECT_TEST --live-reject-login-password-env REJECT_PASSWORD --live-reject-login-expected-statuses 3,4
REJECT_PASSWORD="wrong or disabled-account password" scripts/probe-game-login.py --host HOST --port 43594 --username REJECT_TEST --password-env REJECT_PASSWORD --expect-failure --expect-statuses 3,4
EXTERNAL_PASSWORD="throwaway external password" LOCAL_PASSWORD="throwaway local password" scripts/probe-concurrent-logins.py --external-host HOST --external-username EXTERNAL_TEST --external-password-env EXTERNAL_PASSWORD --local-host 127.0.0.1 --local-username LOCAL_TEST --local-password-env LOCAL_PASSWORD
```

Full external readiness still requires:

- public game/cache reachability over the selected external transport;
- bridge non-exposure from the external path;
- accepted PBKDF2 login over the external path;
- same-host local PBKDF2 login open concurrently with the external login, with `--live-local-host` still set to `localhost` or a loopback IP address;
- fail-closed rejection proof for a wrong, missing, disabled, or tampered account;
- one same-host Java desktop client and one external Java desktop client online together, with a desktop proof note that references a real non-symlink screenshot/log evidence file;
- runtime-data backup proof from the deployed host;
- structured agent/player chat delivery proof from an `AgentChatService` delivery audit event;
- if Discord is enabled, bot/channel proof plus Discord-to-server and server-to-Discord message proof.

After the real desktop-client observation, prefer:

```sh
scripts/write-desktop-client-proof.py --same-host-client LOCAL --external-client EXTERNAL --transport TRANSPORT --public-host HOST --evidence PATH --proof-manifest dist/external-deployment/deployment-proof-manifest.json
```

It validates the existing screenshot/log evidence file, writes a readiness-compatible `--desktop-client-proof-file` note, and updates only `desktop_client_proof_file` when a proof manifest is supplied, without starting, stopping, restarting, logging in, or probing runtime.

Use `scripts/deployment-readiness-report.py --require-full-proof --require-encrypted-external` only when all required live/manual proof files and encrypted/private transport flags exist, or pass a proof manifest that sets `require_encrypted_external:true`.

## Direct Agent/Player Chat Proof

Full readiness needs one direct player-delivery audit event even when Discord is disabled:

```sh
scripts/verify-agent-chat-log.py --event agent_chat_player_delivery --text-contains MARKER --to-type player --to-name PLAYER --delivered-to PLAYER --no-undelivered --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/deployment-readiness-report.py --config "2006Scape Server/ServerConfig.json" --client-dist dist/2006scape-client --server-deployment-dir dist/server-deployment --agent-chat-delivery-log-text MARKER --agent-chat-delivery-log-to-name PLAYER --agent-chat-delivery-log-channel agent
```

Create the marker from an active agent bridge session with `agent_chat_send`/`agent_chat_send_XS` targeting `player`, or from a game client with `::agentchat @player:PLAYER MARKER`. This proves the player chatbox delivery path; it is separate from Discord ingress or mirroring.

## Discord Proof

With real ignored `2006Scape Server/data/secrets.json`:

```sh
scripts/probe-discord-agent-bots.py --secrets "2006Scape Server/data/secrets.json"
scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --discord-message-id DISCORD_MESSAGE_ID --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE --proof-manifest dist/external-deployment/deployment-proof-manifest.json
```

Bot-authored probe messages do not prove runtime Discord ingress because the runtime ignores bot users. Use a real human/non-bot Discord marker for Discord-to-server proof. If routing allow-lists are configured, also prove a blocked human/non-bot marker stayed out of `AgentChatService` with `verify-agent-chat-log.py --expect-absent --proof-manifest dist/external-deployment/deployment-proof-manifest.json` or readiness `--agent-chat-blocked-log-text`.
