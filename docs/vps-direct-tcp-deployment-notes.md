# VPS Direct TCP Deployment Notes

This is the public-safe runbook for the current first VPS deployment path. Keep
real IPs, hostnames, credentials, bridge tokens, private keys, account files,
and self-signed cert/key material out of tracked docs and PRs.

The operator-local version with the active host, SSH command, cert path, and
profile env-file details lives in the ignored file:

```text
dist/external-deployment/private/vps-operator-runbook.md
```

- Active VPS: supplied privately by the server operator.
- SSH from the repo machine: use the private operator command or local alias supplied out of band.
- Optional shell alias: supplied privately by the server operator.
- Deployment worktree on the local machine: `<local-worktree>`.
- VPS deploy directory: `<vps-deploy-dir>`.
- Transport: `direct_tcp` for the first live test. This is plaintext game/cache TCP; use only throwaway or unique passwords.
- Agent bridge boundary: `43610` must stay loopback-only and must not be exposed.

## Rollout Sources

The setup was reconstructed from existing repo docs, live VPS checks, and Codex
rollout searches for the remote deployment side threads. Useful searched
strings included `direct_tcp`, `vps-character-credentials`,
`agent.bridge.url`, `AGENT_BRIDGE_URL`, `remote_claim.py`, `agent-gateway`,
`self-signed`, `Nginx`, `UFW`, and `43610`.

The relevant side-thread work covered these phases:

- prepare and validate the external-player direct-TCP packaging path;
- deploy the repo to the VPS and run it under systemd;
- open only the game/cache ports plus SSH and HTTPS;
- create PBKDF2 account records and copy character saves for named test profiles;
- package a desktop client configured for the VPS;
- add the HTTPS `/agent` gateway in front of loopback-only `43610`;
- prove normal game login and remote repo-side claim/observe flows.

## Architecture

The current VPS path has three separate surfaces:

- **Game/cache TCP:** public `43594`, `8080`, and `43595` for the packaged Java client.
- **Agent gateway HTTPS:** public `443`, served by Nginx, forwarding only approved `/agent/*` routes to the server bridge.
- **Raw agent bridge:** `127.0.0.1:43610` only. This is a bearer-token control plane and must never be exposed publicly.

The server runs under a systemd service from the deployed repo directory. The
service should run as a non-root service user, start with
`scripts/start-server.sh`, and use the deployed
`2006Scape Server/ServerConfig.json`.

## Setup History

The first live path used `direct_tcp` because it is the simplest thing regular
players can connect to with the existing Java client. The external config was
preflighted, server deployment files were generated, account auth was enabled,
and a packaged client was produced from the same config.

On the VPS:

1. Install Java/Maven/git runtime dependencies required by this repo.
2. Put the repo under the deploy directory.
3. Install a systemd service that starts `scripts/start-server.sh` from that deploy directory.
4. Create/copy `2006Scape Server/ServerConfig.json` with external-player mode enabled, account auth enabled, direct-TCP acknowledgements set, and `agent_bridge_bind_host` left on loopback.
5. Create PBKDF2 account records under `2006Scape Server/data/accounts/`.
6. Copy character saves under `2006Scape Server/data/characters/`.
7. Open `22/tcp`, `43594/tcp`, `8080/tcp`, `43595/tcp`, and later `443/tcp` with UFW.
8. Start or restart `2006scape-server.service`.
9. Install Nginx for the `/agent` gateway.
10. Install a temporary self-signed gateway certificate if no real domain cert is available yet.
11. Enable the generated Nginx gateway config and reload Nginx.
12. Verify public game/cache reachability, login success, login rejection, concurrent local/external login, gateway health, and raw bridge non-exposure.

Before replacing deployed files, rotating credentials, migrating config, or
intentionally restarting into new bits, back up runtime data on the deployed
host with `scripts/backup-runtime-data.py`.

## Live State

- 2026-06-14: VPS was rebooted, SSH recovered, and the external server was started from `<vps-deploy-dir>`.
- 2026-06-14: Opened only `22/tcp`, `43594/tcp`, `8080/tcp`, `43595/tcp`, and later `443/tcp` with UFW. Port `43610` remains closed externally.
- 2026-06-14: Server process listens on the private public host for `{43594,8080,43595}`, loopback `127.0.0.1:{43594,8080,43595}`, and loopback-only agent bridge `127.0.0.1:43610`.
- 2026-06-14: Config preflight passed on VPS for `2006Scape Server/ServerConfig.json`.
- 2026-06-14: Strict account audit passed for `ExternalTest`, `LocalTest`, and disabled `RejectTest`.
- 2026-06-14: Mac-side `scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"` passed.
- 2026-06-14: Mac-side live verifier accepted `ExternalTest` and rejected disabled `RejectTest`.
- 2026-06-14: VPS-side concurrent login probe accepted external `ExternalTest` and local `LocalTest` at the same time.
- 2026-06-14: Packaged Mac setup checker passed from `dist/external-deployment/2006scape-client/check-setup-macos-linux.sh`.
- 2026-06-14: Rotated `ExternalTest` to an 8-character convenience password for manual testing. Live game login accepted it, but strict deployment account audit now flags that account as weak-policy. Rotate to a 12+ character password before treating this deployment as final-readiness-grade.
- 2026-06-14: Added VPS PBKDF2 accounts and copied character saves for the named test profiles. Live protocol login probes accepted all of them over the private public host and game port.
- 2026-06-14: Packaged client launch defaults were changed to `client.scale=2` and `show_navbar=false` so the larger testing window uses repo-native canvas scaling instead of macOS JVM UI scaling.
- 2026-06-14: The packaged `client.properties` now contains `agent.bridge.url` for the HTTPS gateway, so repo-side Codex control can use the same gateway URL as the packaged client.
- 2026-06-14: Temporary HTTPS `/agent` gateway on the operator-provided host was enabled with a self-signed IP certificate. Gateway probe with `--allow-untrusted-tls` passed, `remote_claim.py --verify` passed for a logged-in profile, and raw TCP `43610` remained private.
- 2026-06-14: The clean main checkout restored the ignored private credential env file and ignored local gateway certificate for operator use. The temporary one-off HTTPS file-handoff endpoint used for that restore was removed afterward; it is not part of the normal gateway.

## Local Test Credentials

- Passwords are not stored in this note.
- The ignored local env file is `dist/external-deployment/private/live-test-credentials.env`.
- Use `ExternalTest` for a normal external packaged-client login.
- The ignored local env file for the named profile accounts is `dist/external-deployment/private/vps-character-credentials.env`.
- The same private file may also exist on the VPS under the deploy or staging checkout.

To inspect profile credential variable names on the repo machine without
printing values:

```sh
cd <local-worktree>
awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{print $1}' dist/external-deployment/private/vps-character-credentials.env
```

These are eight-character direct-TCP convenience passwords. They are fine for
manual smoke testing with unique throwaway credentials, but they intentionally
do not satisfy strict final deployment password policy.

## Player Connect Steps

1. From the repo machine, use the packaged client folder:

   ```sh
   cd <local-worktree>/dist/external-deployment/2006scape-client
   ./check-setup-macos-linux.sh
   ./run-macos-linux.sh
   ```

2. On macOS Finder, the same flow is double-click `Check-Setup.command`, then double-click `Run-2006Scape.command`.
3. On Windows, use `check-setup-windows.bat`, then `run-windows.bat`.
4. Log in with one of the named test profiles and the matching password from the private env file.

The packaged client connects to the privately supplied server host on world `1`,
game port `43594`, HTTP cache port `8080`, and JAGGRAB port `43595`.

If the packaged client was built with `agent.bridge.url`, in-client `/agent`
commands can use the HTTPS gateway. If it was not, normal play still works, but
repo-side agent control needs `AGENT_BRIDGE_URL` supplied in the environment.

## AI Agent Connect Steps

Direct TCP game login and Codex repo control are separate paths. The game client
connects to the VPS over `43594`/`8080`/`43595`; repo-side Codex tools need a
claimed bridge session through the HTTPS `/agent` gateway configured as
`agent.bridge.url`. The raw bridge port `43610` must stay loopback-only.

For one named profile from the repo machine:

1. Source the private credentials only into the current shell. Do not print or paste passwords into prompts, docs, logs, or PRs.

   ```sh
   cd <local-worktree>
   set -a
   source dist/external-deployment/private/vps-character-credentials.env
   set +a
   ```

2. Launch the packaged client and log in as the target profile, such as `MrFlame`, with the matching env vars from the private file.
3. Claim the profile-scoped remote bridge session through the operator gateway:

   ```sh
   export AGENT_BRIDGE_URL=https://AGENT_GATEWAY_HOST
   python3 agent-navigation/tools/remote_claim.py \
     --profile MrFlame \
     --bridge-url "$AGENT_BRIDGE_URL" \
     --verify
   ```

   If the operator gateway is using a temporary self-signed certificate, also set
   `SSL_CERT_FILE` to the ignored local certificate copy before running
   `remote_claim.py`. Do not commit the certificate or session file.

   ```sh
   export SSL_CERT_FILE=agent-navigation/.local/certs/agent-gateway-selfsigned.crt
   ```

4. Type the exact claim command printed by `remote_claim.py` in the logged-in game client when prompted.
5. Use profile-scoped compact tools from the repo:

   ```sh
   RS_PROFILE=MrFlame agent-navigation/tools/observe_XS.sh
   RS_PROFILE=MrFlame agent-navigation/tools/rs-tool_XS.sh bank_item_count_XS '{"names":["coal","iron ore"]}'
   ```

If there is no HTTPS gateway URL yet, a trusted operator machine can still use a
temporary private SSH local port forward for legacy `/agent` testing:

```sh
ssh -i <path-to-private-key> -N -L 43610:127.0.0.1:43610 <user>@<vps-host>
```

With that tunnel running, launch the packaged client, log in to the desired
profile, type `/agent status`, use `/agent key` if Codex auth is needed, and
start a task with `/agent <task>`. External players who do not have the HTTPS
gateway or private SSH/VPN/tunnel path should play normally and should not use
`/agent`.

## Operator Commands

Use private host/key values from the ignored operator runbook:

```sh
ssh -i <private-key> <user>@<vps-host>
```

On the VPS, useful non-secret checks are:

```sh
systemctl status 2006scape-server.service --no-pager -l
journalctl -u 2006scape-server.service -n 100 --no-pager
ufw status verbose
ss -ltnp | grep -E ':(22|443|43594|43595|8080|43610)'
nginx -t
grep -R 'ssl_certificate' -n /etc/nginx/sites-enabled /etc/nginx/conf.d /etc/2006scape 2>/dev/null
```

The expected listener shape is:

- public SSH `22`;
- public HTTPS gateway `443`;
- public game/cache `43594`, `43595`, and `8080`;
- loopback-only `43610`.

Do not publish the gateway certificate private key, account JSON records,
character saves, `data/secrets.json`, bridge session files, or private env
files.

## Useful Live Checks

```sh
cd <local-worktree>
scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"
HOST="$(python3 - <<'PY'
import json
with open("2006Scape Server/ServerConfig.json", "r", encoding="utf-8") as handle:
    print(json.load(handle)["public_game_host"])
PY
)"
set -a
source dist/external-deployment/private/vps-character-credentials.env
set +a
PROFILE_USERNAME="$MRFLAME_USERNAME"
PROFILE_PASSWORD_ENV=MRFLAME_PASSWORD
python3 scripts/probe-game-login.py --host "$HOST" --port 43594 --username "$PROFILE_USERNAME" --password-env "$PROFILE_PASSWORD_ENV" --hold-seconds 1
```

Example profile login probes without printing passwords:

```sh
python3 scripts/probe-game-login.py --host "$HOST" --port 43594 --username "$MRFLAME_USERNAME" --password-env MRFLAME_PASSWORD --hold-seconds 1
python3 scripts/probe-game-login.py --host "$HOST" --port 43594 --username "$MRFISH_USERNAME" --password-env MRFISH_PASSWORD --hold-seconds 1
python3 scripts/probe-game-login.py --host "$HOST" --port 43594 --username "$MRWOOD_USERNAME" --password-env MRWOOD_PASSWORD --hold-seconds 1
python3 scripts/probe-game-login.py --host "$HOST" --port 43594 --username "$MRATHLETE_USERNAME" --password-env MRATHLETE_PASSWORD --hold-seconds 1
```

Gateway proof for a temporary self-signed cert:

```sh
scripts/probe-agent-bridge-gateway.py --gateway-url https://AGENT_GATEWAY_HOST --allow-untrusted-tls
curl -kfsS https://AGENT_GATEWAY_HOST/agent/health
nc -vz -G 5 AGENT_GATEWAY_HOST 43610  # should fail from outside the VPS
```

Repo-side remote control proof:

```sh
export AGENT_BRIDGE_URL=https://AGENT_GATEWAY_HOST
export SSL_CERT_FILE=agent-navigation/.local/certs/agent-gateway-selfsigned.crt
python3 agent-navigation/tools/remote_claim.py --profile PROFILE --bridge-url "$AGENT_BRIDGE_URL" --verify
RS_PROFILE=PROFILE agent-navigation/tools/observe_XS.sh
```

## Adding Another Character

For a new deployed character such as a friend's profile:

1. Get a private zip containing the character save and, if applicable, account metadata from the player/operator.
2. Back up deployed runtime data before making changes.
3. Install the character save under `2006Scape Server/data/characters/`.
4. Create or update the PBKDF2 account record under `2006Scape Server/data/accounts/`.
5. Add only local ignored credential env vars for operator launches, such as `MRGEM_USERNAME` and `MRGEM_PASSWORD`; do not commit them.
6. Restart only when the deployed server needs to reload account/character state.
7. Probe login with `scripts/probe-game-login.py`, then test a packaged-client login.

## Moving Past The Temporary Gateway

The self-signed IP certificate is only for early operator testing. Before wider
sharing, prefer a real DNS name and trusted TLS certificate for the `/agent`
gateway. Repackage the client with the stable gateway URL so users do not need
to set `SSL_CERT_FILE` manually.
