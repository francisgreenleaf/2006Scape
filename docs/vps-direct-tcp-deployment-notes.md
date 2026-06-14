# VPS Direct TCP Deployment Notes

- Active VPS: supplied privately by the server operator.
- SSH from the repo machine: use the private operator command or local alias supplied out of band.
- Optional shell alias: supplied privately by the server operator.
- Deployment worktree on the local machine: `<local-worktree>`.
- VPS deploy directory: `<vps-deploy-dir>`.
- Transport: `direct_tcp` for the first live test. This is plaintext game/cache TCP; use only throwaway or unique passwords.
- Agent bridge boundary: `43610` must stay loopback-only and must not be exposed.

## Live State

- 2026-06-14: VPS was rebooted, SSH recovered, and the external server was started from `<vps-deploy-dir>`.
- 2026-06-14: Opened only `22/tcp`, `43594/tcp`, `8080/tcp`, and `43595/tcp` with UFW. Port `43610` remains closed externally.
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
- 2026-06-14: A later SSH check from the local machine to port `22` timed out briefly, while public game/cache checks and a profile login still passed. A follow-up check recovered and `ssh` is currently reachable again.

## Local Test Credentials

- Passwords are not stored in this note.
- The ignored local env file is `dist/external-deployment/private/live-test-credentials.env`.
- Use `ExternalTest` for a normal external packaged-client login.
- The ignored local env file for the four named profile accounts is `dist/external-deployment/private/vps-character-credentials.env`.
- The same private file is copied on the VPS at `<vps-deploy-dir>/dist/external-deployment/private/vps-character-credentials.env`.

To inspect profile credentials on the repo machine, read the private env file locally. Do not paste those values into docs, logs, or pull requests:

```sh
cd <local-worktree>
set -a
source dist/external-deployment/private/vps-character-credentials.env
set +a
env | LC_ALL=C sort | grep -E '(_USERNAME|_PASSWORD)='
```

These are eight-character direct-TCP convenience passwords. They are fine for manual smoke testing with unique throwaway credentials, but they intentionally do not satisfy strict final deployment password policy.

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

The packaged client connects to the privately supplied server host on world `1`, game port `43594`, HTTP cache port `8080`, and JAGGRAB port `43595`.

## AI Agent Connect Steps

Legacy remote `/agent` use can still use a trusted private SSH local port forward, but the preferred player-agent mode is now an HTTPS `/agent` gateway packaged as `agent.bridge.url`. In both cases, port `43610` must not be exposed publicly. For a private SSH fallback from the repo machine or another trusted operator machine:

```sh
ssh -i <path-to-private-key> -N -L 43610:127.0.0.1:43610 <user>@<vps-host>
```

With that tunnel running:

1. Launch the packaged client.
2. Log in to the desired profile.
3. Type `/agent status`.
4. If Codex auth is needed, type `/agent key` and enter the API key in the Swing dialog.
5. Start a task with `/agent <task>`.

External players who do not have the private SSH/VPN/tunnel path should play normally and should not use `/agent`.

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
python3 scripts/probe-game-login.py --host "$HOST" --port 43594 --username "$PROFILE_USERNAME" --password-env PROFILE_PASSWORD --hold-seconds 1
```
