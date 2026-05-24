# Local Agent Startup

This is the reliable restart path for local 2006Scape agent work. `MrFlame` is the default local profile, and alternate profiles such as `MrGem` are selected with `--profile <name>` or `RS_PROFILE=<name>`.

Profile-specific runs keep bridge session files, client pid files, client logs, recorder output, and trace filtering separate. The default `MrFlame` session remains `agent-navigation/.local/rsbridge-session.json`; other profiles use `agent-navigation/.local/rsbridge-session-<profile>.json`.

## Quick Human Launch

Use this when you want to play or manually type `/agent ...` in the client:

```sh
./scripts/run-local.sh -u "MrFlame"
./scripts/run-local.sh -u "MrGem"
```

This builds if needed, starts the server, waits for port `43594`, and launches the client against localhost. Log in when the client opens. If you only need the client attached to an already-running server:

```sh
./scripts/start-client.sh -u "MrFlame" -scale 2 -no-nav
CLIENT_SINGLE_INSTANCE=0 ./scripts/start-client.sh -u "MrGem" -scale 2 -no-nav
```

## Agent-Owned Relaunch

Use this when Codex needs to operate the route harness from the repo with `agent-navigation/tools/rs-tool.sh`. This is the path that has been the most reliable.

### Preferred Helper

Use the runtime helper instead of retyping the nonce/claim flow:

```sh
python3 agent-navigation/tools/runtime_doctor.py status --observe
python3 agent-navigation/tools/runtime_doctor.py status --profile MrGem --observe
```

If the status check shows a usable `observe-slim` session for the intended profile, reuse it. If the user asked for a clean restart or the runtime is stale, run:

```sh
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify
```

For a second profile against an existing server, prefer claiming only that profile so the default active client is not replaced:

```sh
python3 agent-navigation/tools/runtime_doctor.py claim --profile MrGem --verify
```

For route learning sessions that still need the fallback recorder because passive server telemetry is unavailable or a deliberate debug recording needs extra NPC snapshots, add:

```sh
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify --start-recorder
```

Do not use the fallback recorder during normal passive telemetry sessions. `AgentPassiveTraceLog` is the default movement source, and `route_recorder.py` refuses to start when recent passive telemetry exists unless explicitly forced for debugging.

Useful focused commands:

```sh
python3 agent-navigation/tools/runtime_doctor.py claim --profile MrFlame --verify
python3 agent-navigation/tools/runtime_doctor.py verify --profile MrFlame --navdb --recorder-status
python3 agent-navigation/tools/runtime_doctor.py recorder --profile MrFlame status
python3 agent-navigation/tools/runtime_doctor.py recorder --profile MrFlame start
python3 agent-navigation/tools/runtime_doctor.py recorder --profile MrFlame stop
```

`runtime_doctor.py` launches the server/client with Python `subprocess.Popen(..., start_new_session=True)`, writes logs under `/tmp/`, writes pid files under `agent-navigation/.local/`, claims the bridge, and writes only ignored session token files. It never prints bridge tokens.

### Manual Fallback

Use this only if the helper needs debugging.

1. Clean up stale client-side agent processes before starting a fresh client:

   ```sh
   pkill -f 'codex app-server --listen stdio://' 2>/dev/null || true
   rm -f agent-navigation/.local/rsbridge-session.json
   rm -f agent-navigation/.local/rsbridge-session-mrgem.json
   mkdir -p agent-navigation/.local
   ```

2. Start the server from the repo root:

   ```sh
   ./scripts/start-server.sh
   ```

   For detached agent work, prefer `runtime_doctor.py` or another Python `subprocess.Popen(..., start_new_session=True)` launcher and log to `/tmp/2006scape-server.log`. In Codex threads, `nohup ./scripts/start-server.sh ... &` has exited silently more than once. `start-server.sh` copies the built server jar to `/tmp/2006scape-run/` before launch; keep that behavior so Maven rebuilds do not replace a jar under a running Java process.

3. Wait until both ports are open:

   ```sh
   nc -z 127.0.0.1 43594
   nc -z 127.0.0.1 43610
   ```

   `43594` is the game service. `43610` is the local agent bridge started by `GameEngine.main`.

4. Launch the client with the intended profile, auto-login, a saved-character password, and a one-time bridge claim nonce:

   ```sh
   nonce="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"

   profile="MrFlame"
   profile_file="$(printf '%s' "$profile" | tr '[:upper:]' '[:lower:]')"

   ./scripts/start-client.sh \
     -u "$profile" \
     -password-character-save "2006Scape Server/data/characters/${profile_file}.txt" \
     -agent-auto-login \
     -agent-claim "$nonce" \
     -scale 2 \
     -no-nav
   ```

   Do not print, save, or commit the nonce. It is short-lived and only proves that the logged-in client owns the server-side session claim.

5. Claim the bridge session and write the ignored profile session file.

   The claim response contains a bridge token. Do not display the response in a terminal, paste it into chat, or write it anywhere except the ignored `.local` session file used by `rs-tool.sh`.

   ```sh
   python3 - "$nonce" <<'PY'
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

nonce = sys.argv[1]
profile = "MrFlame"
safe_profile = "".join(ch for ch in profile.lower() if ch.isalnum() or ch in ("-", "_"))
session_file = Path("agent-navigation/.local/rsbridge-session.json")
if safe_profile != "mrflame":
    session_file = Path("agent-navigation/.local/rsbridge-session-%s.json" % safe_profile)
session_file.parent.mkdir(parents=True, exist_ok=True)
body = json.dumps({"nonce": nonce}).encode("utf-8")
request = urllib.request.Request(
    "http://127.0.0.1:43610/agent/session/claim",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)

last_error = None
for _ in range(180):
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("success"):
            payload = {
                "token": data["token"],
                "sessionId": data.get("sessionId", ""),
                "playerId": data.get("playerId"),
                "playerName": data.get("playerName", ""),
                "createdAt": int(time.time()),
            }
            tmp = session_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
            os.replace(tmp, session_file)
            print("session_ready")
            raise SystemExit(0)
    except urllib.error.HTTPError as exc:
        last_error = "HTTP %s" % exc.code
    except Exception as exc:
        last_error = str(exc)
    time.sleep(0.5)

raise SystemExit("bridge session claim timed out: %s" % last_error)
PY
   ```

6. Verify with the wrapper, not raw `curl`:

   ```sh
   agent-navigation/tools/observe-slim.sh
   ```

   A successful response should show `player.name` as the intended profile, current tile, HP, inventory food, nearby NPCs, and `success:true`.

   For non-default profiles, set `RS_PROFILE` so `rs-tool.sh` validates and uses the matching session:

   ```sh
   RS_PROFILE=MrGem agent-navigation/tools/observe-slim.sh
   RS_PROFILE=MrGem agent-navigation/tools/rs-tool.sh observe_state '{}'
   ```

## What Made This Reliable

- Prefer `agent-navigation/tools/runtime_doctor.py` for agent-owned restart, claim, verify, and recorder control.
- Use the tracked launcher scripts instead of hand-running jars. They choose the right working directories and server config fallback.
- Use Python detached launch with `start_new_session=True` for Codex-owned background server/client processes; avoid relying on `nohup ... &` from a transient shell.
- Start the server before the client and wait for both `43594` and `43610`.
- Use `-password-character-save "2006Scape Server/data/characters/<profile>.txt"` with `-agent-auto-login` so the client logs in without manual typing when the saved profile exists.
- Use `-agent-claim <nonce>` and then claim through `POST /agent/session/claim`; this creates the scoped local bridge session for repo tools.
- Write only ignored files under `agent-navigation/.local/`. Never print or inspect the bridge token.
- Prefer `agent-navigation/tools/rs-tool.sh` and `agent-navigation/tools/observe-slim.sh` after startup. They read the active profile session file and keep tool calls consistent.
- Do not stack idle clients. Reuse a logged-in client or stop only the stale client for the intended profile before starting over.

## Troubleshooting

- `bridge session file not found`: the client did not claim a session yet, or the selected profile session file was removed. Relaunch with `-agent-claim` and run the claim step again.
- `No pending agent bridge claim was found`: the nonce expired or the client has not logged in and sent the claim packet yet. Relaunch with a new nonce.
- `Invalid or expired agent session`: the player logged out, the client closed, or the server restarted. Remove the old session file and repeat the agent-owned relaunch.
- Port `43594` already in use: a server is already running. Attach a client with `./scripts/start-client.sh ...` or stop the old server first.
- The client opens but does not log in: verify `2006Scape Server/data/characters/<profile>.txt` exists and the client was launched with `-password-character-save`.
