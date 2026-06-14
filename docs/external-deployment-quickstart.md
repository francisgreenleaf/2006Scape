# External Deployment Quickstart

This is the short path for a first regular-player external test. Use this when you want to get one remote 2006Scape server, one local client, and one external client online safely without reading the full design document first.

For the simplest live test, use the tracked `direct_tcp` sample. It exposes the legacy game/cache sockets as plaintext TCP to the configured public host, so keep PBKDF2 account auth enabled, open only the required game/cache ports in the host firewall, and keep the Codex agent bridge loopback-only. If you need encrypted/private external traffic instead, use Tailscale, WireGuard, a VPN, or start from `2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json` for the paired stunnel path.

## What This Sets Up

- A remote or test-host server that accepts local same-host clients and direct external Java clients.
- PBKDF2 account records for external login.
- A downloadable Java desktop client zip built from the exact server config.
- A readiness report that separates static checks from live proof.
- Optional Discord proof after the core network/auth/client path works.

## Before You Start

You need:

- A test VM, VPS, or other host where the server can run.
- A public host/IP or DNS name for `direct_tcp`, or an already chosen private/VPN/tunnel transport if not using direct TCP.
- Java and Maven available on the server.
- This repo copied or checked out on the server.
- A throwaway external test account name and password.
- A second throwaway local test account name and password for coexistence proof.

Do not expose the agent bridge. It must stay loopback-only, normally `127.0.0.1:43610`.

## 1. Create The External Config

From the repo root on the server, copy the direct public sample:

```sh
cp "2006Scape Server/ServerConfig.External.Sample.json" "2006Scape Server/ServerConfig.json"
$EDITOR "2006Scape Server/ServerConfig.json"
```

Set these values for the default `direct_tcp` path:

- `public_game_host`: the DNS name or public IP that packaged clients should connect to, replacing `server.example.com`.
- `game_bind_hosts`: include `127.0.0.1` and the public interface IP, replacing `REPLACE_WITH_PUBLIC_INTERFACE_IP`.
- `http_bind_hosts` and `jaggrab_bind_hosts`: include the same public interface IP if `file_server` is enabled.
- `external_transport_mode`: `direct_tcp`.
- `external_players_enabled`: `true`.
- `require_secure_external_transport`: `false`.
- `secure_external_transport_confirmed`: `false`.
- `direct_tcp_external_transport_confirmed`: `true`.
- `account_auth_enabled`: `true`.
- `account_auth_legacy_fallback`: `false` for external mode.
- `account_auth_auto_create`: `false`.
- `agent_bridge_bind_host`: `127.0.0.1`.

For Tailscale/WireGuard/VPN/client TLS tunnel instead, use the relevant private host/bind values, set that `external_transport_mode`, set `require_secure_external_transport=true`, and set `secure_external_transport_confirmed=true`.

For the tracked client TLS tunnel sample instead:

```sh
cp "2006Scape Server/ServerConfig.ClientTlsTunnel.Sample.json" "2006Scape Server/ServerConfig.json"
$EDITOR "2006Scape Server/ServerConfig.json"
```

Replace `REPLACE_WITH_PUBLIC_TLS_HOST` with the public DNS name that has the TLS certificate and stunnel listener. In this mode the Java game/cache listeners stay loopback-only and packaged clients connect to `127.0.0.1`; the packaged launchers try to start the bundled `client-tls-tunnel/stunnel-client.conf` automatically when `stunnel` is installed, and the README still gives the manual command as a fallback.

Then preflight:

```sh
scripts/preflight-external-config.py "2006Scape Server/ServerConfig.json"
```

Do not continue until preflight passes.

## 2. Create Test Accounts

Use environment variables so passwords do not appear in shell history:

```sh
read -s EXTERNAL_PASSWORD
export EXTERNAL_PASSWORD
scripts/create-account.py ExternalTest --password-env EXTERNAL_PASSWORD

read -s LOCAL_PASSWORD
export LOCAL_PASSWORD
scripts/create-account.py LocalTest --password-env LOCAL_PASSWORD

scripts/account-admin.py --require-password-policy audit
```

For a reject-login proof, either use a wrong password for one of those accounts or create and disable a separate throwaway account:

```sh
read -s REJECT_PASSWORD
export REJECT_PASSWORD
scripts/create-account.py RejectTest --password-env REJECT_PASSWORD
scripts/account-admin.py disable RejectTest
```

## 3. Build The Deployment Bundle

This packages the client, renders server deployment files, and writes a static readiness report. It does not start, stop, or restart the server.

```sh
scripts/prepare-external-deployment.py --config "2006Scape Server/ServerConfig.json"
```

Add `--json-output dist/external-deployment/deployment-readiness-report.json` when you also want machine-readable readiness status for scripts or handoff records.

Important outputs:

- `dist/external-deployment/2006scape-client.zip`
- `dist/external-deployment/2006scape-client/Run-2006Scape.command`
- `dist/external-deployment/2006scape-client/Check-Setup.command`
- `dist/external-deployment/2006scape-client/check-setup-macos-linux.sh`
- `dist/external-deployment/2006scape-client/check-setup-windows.bat`
- `dist/external-deployment/2006scape-client/MANIFEST.txt`
- `dist/external-deployment/2006scape-client/SHA256SUMS`
- `dist/external-deployment/server-deployment/`
- `dist/external-deployment/deployment-readiness-report.md`

Open the readiness report and check:

- `status: PASS`
- `deploymentProofStatus: STATIC_CHECKS_PASS_NEEDS_LIVE_PROOF`

That means the artifacts are statically valid but not live-proven yet.

Before a player launches the client, have them run the package's setup checker for their OS if anything is unclear. On macOS, they can double-click `Check-Setup.command`, then double-click `Run-2006Scape.command` to play; Terminal and Linux users can still run the shared shell scripts, and Windows users run the `.bat` files. The checker verifies Java, prints the packaged `client.properties`, and attempts game/cache TCP checks without logging in or changing server state. In `client_tls_tunnel` mode the macOS/Linux setup checker can start the bundled stunnel config temporarily when `stunnel` is installed; the Windows setup checker expects the local tunnel endpoint to be reachable first, while the launcher still manages stunnel when possible.

## 4. Back Up Runtime Data

Before replacing deployed files, rotating credentials, or restarting into new deployment bits:

```sh
scripts/deployment-readiness-status.py --prepared-dir dist/external-deployment --show-next-commands
```

Use the printed "Back up deployed runtime data" command on the deployed host. It will create the manifest parent directory and copy the manifest from the template if it is missing, then run `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data" --proof-file dist/external-deployment/runtime-data-backup-proof.md --proof-manifest dist/external-deployment/deployment-proof-manifest.json` so the proof note sits beside the manifest and updates `runtime_data_backup_proof_file` automatically. The lower-level helper can still be run directly as `scripts/backup-runtime-data.py --data-dir "2006Scape Server/data"` when no manifest exists yet. Save the printed proof path either way. The readiness report rejects symlinked proof notes, verifies owner-only proof/archive modes where supported, and requires the proof note to record the readiness argument plus the fact that the helper did not start, stop, or restart the runtime.

## 5. Start Or Restart Intentionally

Only do this during the planned live-test window.

If using the generated systemd files, follow:

```sh
less dist/external-deployment/server-deployment/README.md
```

If doing a simple manual test, start from the server module working directory or use the repo launcher with the final config:

```sh
SERVER_CONFIG="2006Scape Server/ServerConfig.json" ./scripts/start-server.sh
```

Do not use source/static validation as proof that the running server has changed. The live JVM must be started from the built deployment bits you intend to test.

## 6. Run Live Network And Auth Proof

From a machine that can reach the server through the selected external transport:

```sh
scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"
```

This focused check isolates public game/cache reachability and agent bridge non-exposure before login proof. It does not package, build, log in, start, stop, or restart runtime.

```sh
scripts/verify-external-deployment.py \
  --config "2006Scape Server/ServerConfig.json" \
  --client-dist dist/external-deployment/2006scape-client \
  --archive dist/external-deployment/2006scape-client.zip \
  --server-deployment-dir dist/external-deployment/server-deployment \
  --live \
  --live-login-username ExternalTest \
  --live-login-password-env EXTERNAL_PASSWORD \
  --live-local-login-username LocalTest \
  --live-local-login-password-env LOCAL_PASSWORD \
  --live-reject-login-username RejectTest \
  --live-reject-login-password-env REJECT_PASSWORD \
  --live-reject-login-expected-statuses 3,4
```

This proves:

- game/cache ports are reachable over the selected transport;
- the agent bridge is not reachable externally;
- an external PBKDF2 login works;
- a local same-host PBKDF2 login works while the external login is held open;
- a wrong-password, disabled-account, or missing-account login fails closed with pinned rejection status codes.

If only the simultaneous-login protocol proof needs isolation, run `scripts/probe-concurrent-logins.py --external-host HOST --external-username ExternalTest --external-password-env EXTERNAL_PASSWORD --local-host 127.0.0.1 --local-username LocalTest --local-password-env LOCAL_PASSWORD`; add `--tls --tls-sni-host HOST` for a public `client_tls_tunnel` endpoint.

If you are following the generated `scripts/deployment-readiness-status.py --show-next-commands` flow, use its "Record live network/auth proof" command instead; it copies the proof manifest from the template when missing and adds `--update-proof-manifest` so successful live proof fields are recorded without requiring a final full-proof manifest yet.

## 7. Prove The Desktop Client Path

Give the external tester:

- `dist/external-deployment/2006scape-client.zip`
- the selected external transport requirement, if any
- the test username and password through a private channel

Use a password unique to this 2006Scape server. The packaged README tells testers to use the operator-provided account and not to reuse RuneScape.com or other service passwords, which matters especially for `direct_tcp` because the legacy game/cache protocol is plaintext to the public host.

Then connect:

- one same-host/local Java client through `127.0.0.1`;
- one external Java client through the selected transport using the packaged zip.

After both clients are online together, prefer the helper:

```sh
scripts/write-desktop-client-proof.py \
  --config "2006Scape Server/ServerConfig.json" \
  --same-host-client LocalTest \
  --external-client ExternalTest \
  --transport direct_tcp \
  --public-host HOST \
  --evidence /path/to/desktop-client-coexistence-screenshot.png \
  --proof-manifest dist/external-deployment/deployment-proof-manifest.json
```

It validates the existing evidence file and writes a proof note without starting, stopping, restarting, logging in, or probing anything. When `--proof-manifest` is supplied, it updates only `desktop_client_proof_file` with the generated proof-note path. The generated note looks like:

```markdown
# Desktop Client Coexistence Proof

- date: 2026-06-13
- server config: 2006Scape Server/ServerConfig.json
- same-host client: LocalTest connected through 127.0.0.1
- external client: ExternalTest connected through the selected transport
- observed: both desktop clients remained online at the same time
- evidence: /path/to/desktop-client-coexistence-screenshot.png
```

Save the proof note and the referenced screenshot/log artifact somewhere outside the client zip, then pass the note to readiness as `--desktop-client-proof-file` or through the proof manifest. Readiness rejects missing, empty, or symlinked evidence files.

## 8. Prove Direct Agent/Player Chat Delivery

The external sample enables `agent_chat_log_enabled=true`, so the running server writes sanitized chat evidence under `2006Scape Server/data/logs/agent-chat/`. Send one unique structured marker to an online player, then verify the delivery audit event. Either use an active agent bridge session:

```sh
CHAT_MARKER="external readiness agent delivery $(date -u +%Y%m%dT%H%M%SZ)"
RS_PROFILE=AGENT_PROFILE agent-navigation/tools/rs-tool_XS.sh agent_chat_send "{\"message\":\"$CHAT_MARKER\",\"player\":\"LocalTest\"}"
```

Or type this from an online game client:

```text
::agentchat @player:LocalTest external readiness agent delivery YYYYMMDDTHHMMSSZ
```

Then verify the log:

```sh
scripts/verify-agent-chat-log.py \
  --event agent_chat_player_delivery \
  --text-contains "$CHAT_MARKER" \
  --to-type player \
  --to-name LocalTest \
  --delivered-to LocalTest \
  --no-undelivered \
  --channel agent \
  --proof-manifest dist/external-deployment/deployment-proof-manifest.json
```

Use the real profile/player names that are online during the test. With `--proof-manifest`, the verifier updates only the direct delivery proof fields in the copied manifest after the audit event is found. Without a manifest, pass the same marker and player name through `--agent-chat-delivery-log-text` and `--agent-chat-delivery-log-to-name`.

## 9. Write The Final Readiness Report

After live network/auth proof, runtime backup proof, desktop-client proof, and direct chat delivery proof:

```sh
cp dist/external-deployment/server-deployment/proof-templates/deployment-proof-manifest.json dist/external-deployment/deployment-proof-manifest.json
# Edit the copied manifest: replace proof paths, usernames, markers, and password env var names.
scripts/check-deployment-proof-manifest.py \
  dist/external-deployment/deployment-proof-manifest.json \
  --config "2006Scape Server/ServerConfig.json" \
  --secrets "2006Scape Server/data/secrets.json" \
  --require-full-proof \
  --check-files
scripts/deployment-readiness-report.py \
  --config "2006Scape Server/ServerConfig.json" \
  --client-dist dist/external-deployment/2006scape-client \
  --archive dist/external-deployment/2006scape-client.zip \
  --server-deployment-dir dist/external-deployment/server-deployment \
  --proof-manifest dist/external-deployment/deployment-proof-manifest.json
```

The manifest stores proof file paths, live-test usernames, unique markers, and password environment-variable names. Relative proof-note paths in the manifest resolve from the manifest's directory, so `desktop-client-proof.md` and `runtime-data-backup-proof.md` can be short filenames when they sit beside `dist/external-deployment/deployment-proof-manifest.json`. Do not put passwords, Discord tokens, or other secrets in it. CLI flags still override manifest fields when one proof value needs to be adjusted for a rerun.

For review or handoff, package the non-secret proof artifacts after the report is written:

```sh
scripts/package-deployment-proof.py \
  --prepared-dir dist/external-deployment
```

This bundle intentionally excludes runtime backup archives, character saves, account records, `data/secrets.json`, passwords, bridge tokens, and Discord bot tokens. Keep the real runtime backup archive in the operator's secure backup location. For the final external-ready handoff, add `--require-full-proof`; it fails unless the readiness JSON records a full live proof status and the proof manifest passes full-proof plus proof-file validation.

To re-check status later without rerunning probes or touching runtime:

```sh
scripts/deployment-readiness-status.py --prepared-dir dist/external-deployment
scripts/deployment-readiness-status.py --prepared-dir dist/external-deployment --show-next-commands
scripts/deployment-readiness-status.py --prepared-dir dist/external-deployment --fail-if-not-ready
```

For the final gate, add:

```sh
--require-full-proof
```

Only call the deployment ready when the report passes and `deploymentProofStatus` is a full live proof status.

## 10. Add Discord Proof Later

Do this after core networking/auth/client proof works.

With real ignored `2006Scape Server/data/secrets.json`:

```sh
scripts/probe-discord-agent-bots.py --secrets "2006Scape Server/data/secrets.json"
```

Then prove both directions:

```sh
scripts/verify-agent-chat-log.py --text-contains MARKER --from-type discord --from-bot false --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
scripts/verify-discord-channel-message.py --text-contains MARKER --agent PROFILE --proof-manifest dist/external-deployment/deployment-proof-manifest.json
```

Direct player delivery proof was already covered in step 8; keep it separate from Discord proof unless you are deliberately rechecking the player chatbox path:

```sh
scripts/verify-agent-chat-log.py --event agent_chat_player_delivery --text-contains MARKER --to-type player --to-name PLAYER --delivered-to PLAYER --no-undelivered --channel agent --proof-manifest dist/external-deployment/deployment-proof-manifest.json
```

If Discord is enabled in the config, the full readiness report will require Discord proof before reporting full Discord readiness.

## Fast Failure Checks

If something fails, check these first:

- `public_game_host` still has a placeholder value.
- The client was packaged from a different config than the verifier is using.
- For direct TCP, the public host/IP and firewall allow the game/cache ports.
- For Tailscale/WireGuard/VPN, the private transport is connected on the server and tester machine.
- Game/cache binds include the selected non-loopback interface IP, not just loopback.
- `agent_bridge_bind_host` is still loopback.
- Account records were created with `scripts/create-account.py` and pass `scripts/account-admin.py --require-password-policy audit`.
- The running server was intentionally restarted after building the deployment bits.
- The packaged client zip is from `dist/external-deployment/`, not an old `dist/2006scape-client.zip`.

## Detailed References

- Full deployment details: `docs/deployment-networking.md`
- Design rationale: `docs/network-auth-agent-chat-design.md`
- Source validation: `scripts/validate-network-auth-chat.sh`
