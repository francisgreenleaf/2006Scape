# canvrno's Additions So Far

This fork adds a local Codex agent layer, route-learning tools, and documentation around a 2006Scape development workflow. The main goal is to let multiple local characters use the same tooling without sharing bridge sessions, route traces, saved runtime state, or agent memory by accident.

## Agent Bridge

- Added a local Codex agent flow from the Java client through `/agent ...`.
- Added a server-side bridge on `127.0.0.1:43610` that scopes each bridge token to the logged-in player that claimed it.
- Added dynamic `rs` tools for observation, walking, landmark travel, dialogue, objects, NPC combat, food, shops, banking, mining, woodcutting, smelting, smithing, and longer batch actions.
- Kept actions server-authoritative: tools route through existing game systems instead of teleports, item spawning, direct stat edits, or screen automation.

## Multi-Character Isolation

- `MrFlame` remains the default local profile for backward compatibility.
- Other profiles, such as `MrGem`, use profile-specific bridge session files, client pid files, client logs, saved-password character files, recorder files, and trace filters.
- Repo-side tools can be scoped with `RS_PROFILE=<name>`, `RS_TRACE_PROFILE=<name>`, or command flags such as `--profile` and `--trace-profile`.
- Tests cover the bridge session boundary so a token claimed by one player is not accepted for another player.

## Navigation Harness

- Added `agent-navigation/` as the repo-local movement memory system.
- Added route data for places, routes, hazards, and route regression tests.
- Added `navdb.py`, `router.py`, `route_runner.py`, `route_eval.py`, and `marathon_runner.py` for validating routes, planning paths, running learned routes, and evaluating route behavior.
- Added `script_registry.py` and `agent-navigation/data/script_registry.json` so agents can find helper scripts by fuzzy name, wildcard, tag, description, or alias without loading broad docs.
- Added screenshot helpers and compact observation tools for route debugging.

## Movement Telemetry And Maps

- Added passive server-side movement trace logging for active players.
- Added a fallback route recorder that can write profile-specific movement traces.
- Added cache-backed map rendering and active topology renderers for route maps, movement heat maps, and profile fog maps.
- Added generated-output ignores so traces, screenshots, topology PNG/JSON files, local session tokens, and marathon artifacts stay out of commits unless explicitly curated.

## Codex Skills And Runbooks

- Added repo-local `.codex/skills/2006scape*` skills for bridge development, local runtime management, route planning, route execution, map visualization, screenshot capture, object transitions, gameplay progression, cache maps, frontier exploration, and session logs.
- Added `docs/local-agent-startup.md` for the reliable profile-aware server/client/login/bridge claim flow.
- Added `docs/movement-telemetry.md`, `agent-navigation/README.md`, and `agent-navigation/cache-world-map.md` for the route and map systems.
- Updated `AGENTS.md` and `README.md` with the new agent workflow and multi-profile conventions.

## Gameplay Content

- Added Pantry Panic quest content and related game hooks.
- Added pathfinding and interaction support needed by the agent tools and route-learning workflow.

## What Should Stay Local

The fork is intended to be shared without local secrets or personal runtime state. Do not commit:

- API keys, bridge tokens, nonces, passwords, or secret config files.
- `agent-navigation/.local/`.
- Generated movement traces, screenshots, topology renders, marathon logs, and local observations.
- Character saves or generated server/client build artifacts.

Before sharing, run the focused checks in `AGENTS.md`, then review `git status --short` and the staged diff for accidental generated files.
