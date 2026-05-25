---
name: 2006scape-route-agent
description: "Use when working in the /Users/kevin/Documents/2006Scape repo on the RuneScape navigation harness for the selected profile: observing state with slim output, using learned routes, updating route/places/hazards data, rendering topology PNGs, or continuing heartbeat-driven navigation. Pair with 2006scape-route-planner-dev for router.py/route_runner.py graph semantics, 2006scape-frontier-exploration for unknown-area probes, and 2006scape-object-transitions for doors/gates/stairs/trapdoors."
---

# 2006Scape Route Agent

Use this skill for local exploration and route-learning work in `/Users/kevin/Documents/2006Scape`. `MrFlame` is the default profile; set `RS_PROFILE=<name>` or pass profile-aware tool flags when working as another character.

## When To Switch Skills

- Use `2006scape-route-planner-dev` for `router.py`, `route_runner.py`, `navdb.py` graph semantics, passive trace weighting, reverse-edge inference, coordinate targets, or ML/GNN route planning.
- Use `2006scape-frontier-exploration` for live unknown-area expansion, short probes, frontier naming, and hazard/death evidence.
- Use `2006scape-object-transitions` for doors, gates, ladders, trapdoors, stairs, ships, portals, member gates, or any object-chain blocker.
- Use `2006scape-screenshot-capture` when API state is insufficient and compact visual proof is needed.

## Routine observe

Prefer the slim wrapper for normal decisions:

```sh
agent-navigation/tools/observe-slim.sh
RS_PROFILE=MrGem agent-navigation/tools/observe-slim.sh
```

Use full state only for deep debugging, missing fields, session/personality context, or when recording complete evidence:

```sh
agent-navigation/tools/rs-tool.sh observe_state '{}'
RS_PROFILE=MrGem agent-navigation/tools/rs-tool.sh observe_state '{}'
```

Treat unexpected state changes as possibly user-driven. Always observe before deciding after a pause, heartbeat, manual user action, combat, death, inventory change, or movement you did not initiate.

If observe fails because the local runtime or bridge session is stale, switch to `2006scape-local-runtime` and prefer:

```sh
python3 agent-navigation/tools/runtime_doctor.py status --observe
python3 agent-navigation/tools/runtime_doctor.py claim --verify
```

## Gameplay control rules

Use repo-side bridge tools only:

```sh
agent-navigation/tools/rs-tool.sh walk_to_tile_until_arrived '{"x":3222,"y":3218,"height":0}'
agent-navigation/tools/rs-tool.sh interact_object '{"objectId":14879,"x":3209,"y":3216,"height":0}'
agent-navigation/tools/rs-tool.sh cancel_current_action '{}'
```

Do not use admin teleports, spawned items, direct player-state edits, raw bridge tokens, or unrelated repo work.

For long movement, prefer batch tools and treat their response as the next observation. Do not poll one tick at a time unless no batch tool fits.

## Doors and object chains

Model doors, gates, stairs, ladders, trapdoors, and floors as explicit object-chain steps, not as a single click.

For each object transition record:

- pre-interaction player tile
- object id, name, and tile
- approach side
- reachability fields from the bridge
- post-condition or post-tile
- fallback/recovery if it fails

A click returning `success:true` is not proof. A route is verified only when post-state proves the transition.

Known Lumbridge trapdoor pattern:

```text
stand 3208,3216,0 west of trapdoor
open 14879 at 3209,3216,0
use 10698 at 3209,3216,0
arrive 3208,9616,0
```

## Route DB workflow

Use navdb for route decisions and validation:

```sh
python3 agent-navigation/tools/navdb.py next-step --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled true
python3 agent-navigation/tools/navdb.py hazards --near X,Y,H --radius 20 --combat-level N --food N --run-energy N --run-enabled true
python3 agent-navigation/tools/navdb.py record-observation ...
python3 agent-navigation/tools/navdb.py validate
python3 agent-navigation/tools/navdb.py self-test
```

After evidence-backed DB edits, run `validate` and `self-test`.

Record useful observations with player tile, HP, run energy, combat state, food, relevant NPC/object details, route/place, and screenshot path/resolution when used.

Passive server telemetry is the default source for route graph learning when the running build includes `AgentPassiveTraceLog`. It writes authoritative movement/activity events without an AI poll loop to `2006Scape Server/data/logs/player-movement-traces/`. `navdb.py`, `router.py`, and movement topology renderers now use that passive stream by default, drop stationary idle `state` heartbeats from route/map inputs, and exclude duplicate agent batch / legacy fallback polling traces unless explicitly opted in. Use `agent-navigation/tools/route_recorder.py` only as a fallback/dev supplement for older runtimes or extra NPC snapshots, and do not leave it running during normal passive telemetry sessions. The fallback recorder refuses to start when recent passive telemetry exists unless explicitly forced for debugging.

Use `runtime_doctor.py` for fallback recorder control:

```sh
python3 agent-navigation/tools/runtime_doctor.py recorder status
python3 agent-navigation/tools/runtime_doctor.py recorder start
python3 agent-navigation/tools/runtime_doctor.py recorder stop
```

For low-token route orientation without movement, use:

```sh
python3 agent-navigation/tools/route_runner.py --to PLACE --orient --json --run-reserve auto
```

It performs one observe, graph plan, route evaluation, clipped-path preview, optional suspicious-route context map, and compact run-policy summary. Use it before uncertain long legs instead of manually chaining observe, route-eval, preview, and map commands.

For low-token long-route execution, prefer `agent-navigation/tools/route_runner.py --to PLACE --run-reserve auto` after observing current state. It wraps `router.py`, preflights local legs, preserves energy for known run-required hazards using preview length before each batch, issues batch movement, and treats each batch result as the next observation. While it runs, poll terminal output at the expected batch duration (`maxTicks * 600ms` plus a small buffer) instead of every few seconds unless there is a safety reason to short-poll.

Coordinate targets are valid for frontier/routing work:

```sh
python3 agent-navigation/tools/route_runner.py --to X,Y,H --max-walk-distance 48 --max-batches 6 --dry-run
python3 agent-navigation/tools/route_runner.py --to X,Y,H --max-walk-distance 48 --max-batches 6 --run-reserve auto
```

## Screenshots and Maps

Use screenshots only when API state is insufficient. For visual route ambiguity, switch to `2006scape-screenshot-capture` and prefer compact four-angle captures.

Four-angle evidence command:

```sh
agent-navigation/tools/capture-cardinal-screenshots.sh --prefix reason
```

Single-angle evidence command:

```sh
agent-navigation/tools/capture-client-screenshot.sh --prefix reason --native-size
```

Do not load high-resolution screenshots into context unless visually debugging and the compact capture failed.

The old screenshot-based minimap map collector has been removed. Do not start any background screen sampler or focus-stealing client capture loop.

Render the canonical map by overwriting one file:

```sh
agent-navigation/tools/render_navigation_png.py --region all --output agent-navigation/topology/surface-routes.png
```

The map is surface-only and uses `6 px = 1 step tile` unless changed deliberately.

For local map context around the player or a route segment, prefer bounded cache-backed renders:

```sh
python3 agent-navigation/tools/render_agent_context_map.py --center latest
python3 agent-navigation/tools/render_agent_context_map.py --segment-from FROM_PLACE --segment-to TO_PLACE
```

Use these before accepting a suspicious long detour. The output is lossless, north-up, includes every cache mapfunction icon in bounds, keeps nearby segment geometry such as docks/ports visible, writes place/mapfunction marker metadata to JSON, and stays small enough to inspect in the thread without loading the full cache-world map.
By default these commands write uniquely named PNG/JSON pairs under ignored `agent-navigation/.local/context-maps/<date>/`; use the returned JSON path instead of assuming a stable topology filename. Read the JSON summary and markers first, and load the PNG only when visual geometry is needed.

Do not run the full profile movement map, `Heat Map`, profile fog map, or full cache-world map during live routing unless the user explicitly asks for a player-facing map. Agents should use the fast context wrapper for tactical route debugging.

## Safety

Keep HP safe. If combat starts unexpectedly, prioritize survival, cancel route learning, eat/retreat if needed, then record the hazard or user-driven state change.

Non-aggressive NPCs can still become route-contact risks if the player/user attacks or clicks them. Do not assume `aggressive:false` means route-safe.

## Current learned lessons

- Use `observe-slim` for routine state checks to avoid verbose context.
- Use `runtime_doctor.py` for stale bridge/runtime repair instead of retyping the session-claim flow.
- Use `capture-cardinal-screenshots.sh` for compact visual proof when route geometry is ambiguous.
- Use `route_runner.py` for long learned routes when a route graph path exists.
- Use `route_runner.py --orient --json --run-reserve auto` to get compact route context before uncertain long legs without moving.
- Check orient `frontierScore` for coordinate targets; if the proposed frontier's first step goes away from the target, prefer a target-directed probe or local preview.
- Use `--run-reserve auto` when moving through long or hazard-adjacent routes so normal travel does not drain energy needed for hazards.
- Use `render_agent_context_map.py` to inspect current location, recent movement, and route segments before replaying inefficient detours. Its default artifacts are timestamped under `.local/context-maps`.
- Do not treat `Bank table` objects as proof of a bank; they are often decorative. Prefer minimap bank symbols from context maps, actual Bank booth/chest/Banker evidence, `inBankArea=true`, or a proven bank interface.
- Always re-observe after user intervention.
- Door routes need multi-object chain proof.
- Keep topology PNGs canonical: replace `agent-navigation/topology/surface-routes.png`, do not create timestamp/version clutter.
