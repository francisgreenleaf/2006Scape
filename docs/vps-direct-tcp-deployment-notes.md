# VPS Direct TCP Deployment Notes

- Active VPS: supplied privately by the server operator.
- SSH from the repo machine: use the private operator command or local alias supplied out of band.
- Shell alias available in fresh shells: `2006scape-vps`.
- Deployment worktree on the Mac: `/Users/kevin/Documents/2006Scape-network-auth-chat`.
- VPS deploy directory: `/root/2006Scape-network-auth-chat`.
- Transport: `direct_tcp` for the first live test. This is plaintext game/cache TCP; use only throwaway or unique passwords.
- Agent bridge boundary: `43610` must stay loopback-only and must not be exposed.

## Live State

- 2026-06-14: VPS was rebooted, SSH recovered, and the external server was started from `/root/2006Scape-network-auth-chat`.
- 2026-06-14: Opened only `22/tcp`, `43594/tcp`, `8080/tcp`, and `43595/tcp` with UFW. Port `43610` remains closed externally.
- 2026-06-14: Server process listens on the private public host for `{43594,8080,43595}`, loopback `127.0.0.1:{43594,8080,43595}`, and loopback-only agent bridge `127.0.0.1:43610`.
- 2026-06-14: Config preflight passed on VPS for `2006Scape Server/ServerConfig.json`.
- 2026-06-14: Strict account audit passed for `ExternalTest`, `LocalTest`, and disabled `RejectTest`.
- 2026-06-14: Mac-side `scripts/probe-deployment-network.py --config "2006Scape Server/ServerConfig.json"` passed.
- 2026-06-14: Mac-side live verifier accepted `ExternalTest` and rejected disabled `RejectTest`.
- 2026-06-14: VPS-side concurrent login probe accepted external `ExternalTest` and local `LocalTest` at the same time.
- 2026-06-14: Packaged Mac setup checker passed from `dist/external-deployment/2006scape-client/check-setup-macos-linux.sh`.
- 2026-06-14: Rotated `ExternalTest` to an 8-character convenience password for manual testing. Live game login accepted it, but strict deployment account audit now flags that account as weak-policy. Rotate to a 12+ character password before treating this deployment as final-readiness-grade.
- 2026-06-14: Added VPS PBKDF2 accounts and copied character saves for `MrFlame`, `MrFish`, `MrWood`, and `MrAthlete`. Live protocol login probes accepted all four over the private public host and game port.
- 2026-06-14: Packaged client launch defaults were changed to `client.scale=2` and `show_navbar=false` so the larger testing window uses repo-native canvas scaling instead of macOS JVM UI scaling.
- 2026-06-14: A later SSH check from the Mac to port `22` timed out briefly, while public game/cache checks and `MrFlame` login still passed. A follow-up check recovered and `ssh` is currently reachable again.

## Local Test Credentials

- Passwords are not stored in this note.
- The ignored local env file is `dist/external-deployment/private/live-test-credentials.env`.
- Use `ExternalTest` for a normal external packaged-client login.
- The ignored local env file for the four named profile accounts is `dist/external-deployment/private/vps-character-credentials.env`.
- The same private file is copied on the VPS at `/root/2006Scape-network-auth-chat/dist/external-deployment/private/vps-character-credentials.env`.

To print the profile credentials on the repo machine:

```sh
cd /Users/kevin/Documents/2006Scape-network-auth-chat
set -a
source dist/external-deployment/private/vps-character-credentials.env
set +a
printf 'MrFlame: %s\n' "$MRFLAME_PASSWORD"
printf 'MrFish: %s\n' "$MRFISH_PASSWORD"
printf 'MrWood: %s\n' "$MRWOOD_PASSWORD"
printf 'MrAthlete: %s\n' "$MRATHLETE_PASSWORD"
```

These are eight-character direct-TCP convenience passwords. They are fine for manual smoke testing with unique throwaway credentials, but they intentionally do not satisfy strict final deployment password policy.

## Player Connect Steps

1. From the repo machine, use the packaged client folder:

   ```sh
   cd /Users/kevin/Documents/2006Scape-network-auth-chat/dist/external-deployment/2006scape-client
   ./check-setup-macos-linux.sh
   ./run-macos-linux.sh
   ```

2. On macOS Finder, the same flow is double-click `Check-Setup.command`, then double-click `Run-2006Scape.command`.
3. On Windows, use `check-setup-windows.bat`, then `run-windows.bat`.
4. Log in with one of `MrFlame`, `MrFish`, `MrWood`, or `MrAthlete` and the matching password from the private env file.

The packaged client connects to the privately supplied server host on world `1`, game port `43594`, HTTP cache port `8080`, and JAGGRAB port `43595`.

## AI Agent Connect Steps

Remote `/agent` use needs the private bridge on the VPS, but port `43610` must not be exposed publicly. Use an SSH local port forward from the repo machine or another trusted operator machine:

```sh
ssh -i ~/.ssh/2006scape-do-nopass -N -L 43610:127.0.0.1:43610 root@SERVER_HOST
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
cd /Users/kevin/Documents/2006Scape-network-auth-chat
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
python3 scripts/probe-game-login.py --host "$HOST" --port 43594 --username "$MRFLAME_USERNAME" --password-env MRFLAME_PASSWORD --hold-seconds 1
```
