---
name: 2006scape-local-runtime
description: "Use when managing the local 2006Scape runtime in /Users/kevin/Documents/2006Scape: starting, stopping, relaunching, or diagnosing the server, Java client, local agent bridge, profile auto-login, session claim flow, stale Codex app-server processes, ports 43594/43610, or agent-navigation/.local/rsbridge-session*.json. Use before touching running processes, launcher scripts, or bridge session files."
---

# 2006Scape Local Runtime

Use this skill for runtime lifecycle work only. Other agents may be playing or editing the repo, so do not stop, restart, kill, rebuild, or replace the server/client unless the user explicitly asked for runtime management or evidence shows the runtime is stale and unusable.

## Main Rule

Keep runtime work separate from code work. Prefer `agent-navigation/tools/runtime_doctor.py` and the documented launch path in `docs/local-agent-startup.md`; do not modify game source, route data, or map renderers while doing a runtime task unless the user asks.

Never print, paste, inspect, log, or commit bridge tokens. The only allowed token destination is an ignored `agent-navigation/.local/rsbridge-session*.json` file read by `agent-navigation/tools/rs-tool_XS.sh` or the full fallback `agent-navigation/tools/rs-tool.sh`.

## Current Runtime Pieces

- Game server: listens on `127.0.0.1:43594` for the game service.
- Agent bridge: listens on `127.0.0.1:43610` from `AgentBridgeServer`.
- Default profile: `MrFlame`; pass `--profile <name>` or set `RS_PROFILE=<name>` for another character.
- Server launcher: `./scripts/start-server.sh`, which runs from the repo root and copies the jar to `/tmp/2006scape-run/`.
- Client launcher: `./scripts/start-client.sh`.
- Bridge wrappers: use `agent-navigation/tools/observe_XS.sh` and `agent-navigation/tools/rs-tool_XS.sh` by default; `observe-slim.sh` and `rs-tool.sh` remain full/fallback surfaces.
- Runtime helper: `agent-navigation/tools/runtime_doctor.py`.
- Server tick log summarizer: `agent-navigation/tools/server_tick_report.py`.

## Preflight

First determine whether a usable runtime already exists:

```sh
python3 agent-navigation/tools/runtime_doctor.py status --observe
python3 agent-navigation/tools/runtime_doctor.py status --profile MrGem --observe
python3 agent-navigation/tools/server_tick_report.py --json
```

If `observe_XS.sh` succeeds for the intended profile, reuse the current session. Do not relaunch just to make the environment look clean.

Use `server_tick_report.py` when the server log is noisy with cycle-duration messages. It reads recent `/tmp/2006scape-server.log` lines and summarizes warning/error counts, sampled cycle durations, and recent slow cycles without restarting or touching the JVM.

If process inspection is needed and macOS denies it, do not invent a workaround. Report the permission issue or use a narrow approved process-management path when approvals are available.

## Agent-Owned Relaunch

Use the helper when the user asks Codex to make the bridge usable from the repo:

```sh
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify
```

For a second profile against an existing server, claim that profile instead of replacing the whole runtime:

```sh
python3 agent-navigation/tools/runtime_doctor.py claim --profile MrGem --verify
```

If route learning needs the fallback recorder because passive server telemetry is unavailable or extra NPC snapshots are explicitly useful:

```sh
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify --start-recorder
```

Do not start or leave the fallback recorder running during normal passive telemetry sessions. It polls `rs.observe_state`, can duplicate the server passive stream, defaults to no stationary idle heartbeats, and now refuses to start when recent passive telemetry exists unless `--allow-passive-duplicate` is deliberately passed to `route_recorder.py`.

Use focused commands for smaller repairs:

```sh
python3 agent-navigation/tools/runtime_doctor.py claim --verify
python3 agent-navigation/tools/runtime_doctor.py verify --navdb --recorder-status
python3 agent-navigation/tools/runtime_doctor.py recorder status
python3 agent-navigation/tools/runtime_doctor.py recorder --profile MrGem status
```

The helper implements this flow:

1. Stop only stale client-side agent helpers, then clear the ignored local session file.
2. Start `./scripts/start-server.sh`.
3. Wait for both `43594` and `43610`.
4. Launch the client with the selected profile, saved-character login, `-agent-auto-login`, and a fresh `-agent-claim <nonce>`.
5. Claim through `POST /agent/session/claim` and write only the ignored profile session file.
6. Verify with `agent-navigation/tools/observe_XS.sh` or `RS_PROFILE=<name> agent-navigation/tools/observe_XS.sh`, not raw token-bearing `curl`.

Read `docs/local-agent-startup.md` for details or manual fallback. Do not retype the nonce-safe claim block from memory unless the helper itself is being debugged.

## Safe Stop Or Restart

Before stopping anything, identify who owns the runtime:

- If another user/agent is actively exploring, ask before interrupting unless the user already requested a stop.
- If ports are occupied but `observe_XS.sh` works, attach to the current runtime.
- If the bridge token is invalid after a server/client restart, remove only that profile's ignored session file and re-claim.

Do not rebuild while a server is running directly from `2006Scape Server/target/server-1.0-jar-with-dependencies.jar`. Use the launcher path that copies the jar to `/tmp/2006scape-run/`.

For detached Codex-owned runtime processes, use `runtime_doctor.py` or Python `subprocess.Popen(..., start_new_session=True)`. Do not rely on `nohup ./scripts/start-server.sh ... &`; it has exited silently in Codex threads.

## Common Failures

- `bridge session file not found`: relaunch or re-claim; the wrapper has no local session file.
- `No pending agent bridge claim was found`: the nonce expired or the client has not logged in and sent its claim.
- `Invalid or expired agent session`: player logged out, client closed, or server restarted; clear the session file and re-claim.
- `43594 already in use`: a server is already running; attach or ask before stopping it.
- Client opens but does not log in: check `2006Scape Server/data/characters/<profile>.txt` and the `-password-character-save` launch flag.

## Skill Maintenance

If you discover a better launch, stop, claim, or verification workflow while using this skill, surface it to the user and ask whether to make the skill edit.
