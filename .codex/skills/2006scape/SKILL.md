---
name: 2006scape
description: "Use as the single entry skill for work in /Users/kevin/Documents/2006Scape, especially when a task broadly mentions 2006Scape or the right specialized workflow is unclear. Provides routing guidance, boundaries, starter commands, and child-skill pointers for runtime/bridge sessions, script discovery, route exploration, route-planner/ML graph development, object transitions, frontier exploration, compact screenshots, gameplay progression, profile-scoped character memories/goals, cache maps, map visualization, session logs, bridge-tool development, and general repo editing without preloading every specialized skill body."
---

# 2006Scape

Use this as the umbrella skill for `/Users/kevin/Documents/2006Scape`. Load this first when a task is broadly about 2006Scape or when you are unsure which repo-local skill applies.

## How To Use This Skill

Skill links are routing pointers, not inherited context. Available skills expose their `name`, `description`, and `path`; the full body of a child `SKILL.md` is read only when the agent chooses that child skill. Keep this file useful enough to orient a new agent, then load the smallest relevant child skill before doing specialized work.

Other agents may be editing code or playing the game. Keep work scoped to the user's task, avoid process restarts unless requested, and do not touch runtime/game code when the task is only about skills or docs.

Always keep bridge tokens, API keys, saved-character secrets, passwords, and nonces out of messages, logs, screenshots, and committed files. `MrFlame` is the default local gameplay profile; use `RS_PROFILE=<name>` or `--profile <name>` when the user wants another character.

## Skill Router

| Need | Read | Good first move | Boundary |
| --- | --- | --- | --- |
| General repo edits, Java/Maven work, maintenance, tests, code review, or durable lessons | `.codex/skills/2006scape-dev-editing/SKILL.md` | Read `AGENTS.md`; for edits, inspect `references/actionable-lessons.md` when relevant | Do not touch unrelated dirty files or add broad lessons from stale context |
| Starting, stopping, relaunching, diagnosing, or claiming the local server/client/bridge runtime | `.codex/skills/2006scape-local-runtime/SKILL.md` | `python3 agent-navigation/tools/runtime_doctor.py status --observe` | Do not kill/restart active runtimes unless asked or clearly stale; keep profile sessions scoped; never print tokens |
| Adding, debugging, reviewing, or documenting `rs.*` bridge primitives or compatibility tools | `.codex/skills/2006scape-agent-bridge-dev/SKILL.md` | Read `agent-navigation/scripting-primitives.md`, then inspect `AgentActionService`, `AgentToolService`, and `CodexAppServerClient` | Prefer external scripts for strategy; build success is not live proof; restart through `runtime_doctor.py` only when live validation is requested |
| Live route exploration, route DB edits, hazards, blockers, doors, gates, stairs, trapdoors, or topology from navigation data | `.codex/skills/2006scape-route-agent/SKILL.md` | `agent-navigation/tools/observe-slim.sh`; validate with `python3 agent-navigation/tools/navdb.py validate` | Use bridge tools only; do not use admin teleports, direct state edits, or visual guesses without evidence |
| Route-planner implementation, graph semantics, `router.py`, `route_runner.py`, passive trace weighting, reverse edges, coordinate targets, ML/GNN route planning, or planner evaluation | `.codex/skills/2006scape-route-planner-dev/SKILL.md` | `python3 agent-navigation/tools/router.py plan --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled` | Keep learned models explainable and constrained by deterministic safety gates |
| Doors, gates, ladders, trapdoors, stairs, ships, portals, tolls, or member gates | `.codex/skills/2006scape-object-transitions/SKILL.md` | Observe full state, identify object id/tile, preview/walk to interaction target, interact once, then prove post-state | Do not model object transitions as ordinary walk edges or accept a successful click as proof |
| Live unknown-area expansion, short probes, frontier naming, coordinate targets, and hazard/death evidence | `.codex/skills/2006scape-frontier-exploration/SKILL.md` | Dry-run `route_runner.py --to X,Y,H --allow-frontier --direct-if-preview --probe-toward-target` before moving | Avoid destination gambling; every probe should produce reusable route, blocker, hazard, or frontier evidence |
| Compact visual debugging of the live Java client | `.codex/skills/2006scape-screenshot-capture/SKILL.md` | `agent-navigation/tools/capture-cardinal-screenshots.sh --prefix reason` | Prefer `765x503` client captures; do not load full desktop screenshots unless compact capture fails |
| Normal gameplay progression through in-game mechanics | `.codex/skills/2006scape-gameplay-progression/SKILL.md` | `agent-navigation/tools/observe-slim.sh`, then search `script_registry.py` for a primitive-backed runner | Not for route DB schema edits, bridge source changes, spawned items, or direct player-state edits |
| Intentional long-term memories, equipment goals, preferences, recurring blockers, or strategic reminders for one character | `.codex/skills/2006scape-character-memory/SKILL.md` | `python3 agent-navigation/tools/character_memory.py show --profile PROFILE --json` | Keep entries sparse and profile-scoped; route facts belong in nav data, routine progress belongs in session logs |
| Discovering or running repo helper scripts by fuzzy name, wildcard, tag, or metadata | `.codex/skills/2006scape-script-registry/SKILL.md` | `python3 agent-navigation/tools/script_registry.py search QUERY` | Keep script descriptions in `agent-navigation/data/script_registry.json`, not in this umbrella skill |
| Static cache-backed world map decoding/rendering, GameCache terrain/water/object/mapscene layers, bounded context maps, or map data export | `.codex/skills/2006scape-cache-map/SKILL.md` | For agent context, use `python3 agent-navigation/tools/render_agent_context_map.py --center latest` | Do not recreate the retired screenshot/minimap fog sampler or require a live client for static map work |
| Map presentation, route overlays, topology styling, labels, legends, visual QA, recent-path/segment context maps, or sharing map images | `.codex/skills/2006scape-map-visualization/SKILL.md` | For agent segment context, use `python3 agent-navigation/tools/render_agent_context_map.py --segment-from FROM_PLACE --segment-to TO_PLACE` | Do not restart gameplay runtime for visual-only work; use `cache-map` for renderer internals |
| Agent session logs, rollout transcript enrichment, Markdown summaries, reports, redaction, or profile/personality artifacts | `.codex/skills/2006scape-agent-session-logs/SKILL.md` | Read targeted `2006Scape Server/data/logs/agent-sessions/...` files and matching `~/.codex/sessions/.../rollout-*.jsonl` | Treat logs as evidence, not controls; do not expose secrets or mutate live gameplay |

## Starter Commands

Run these from the repo root only as orientation. Open the relevant child skill before making changes, restarting processes, or running live gameplay actions. Commands with uppercase placeholders need task-specific values.

```sh
# 2006scape-dev-editing: common validation after repo edits
mvn -q -DskipTests package
mvn -q clean test

# 2006scape-local-runtime: inspect or repair the local runtime/bridge
python3 agent-navigation/tools/runtime_doctor.py status --observe
python3 agent-navigation/tools/runtime_doctor.py status --profile PROFILE --observe
python3 agent-navigation/tools/runtime_doctor.py claim --verify
python3 agent-navigation/tools/runtime_doctor.py restart --replace-runtime --build --verify

# 2006scape-agent-bridge-dev: prove bridge tools through the wrapper
agent-navigation/tools/observe-slim.sh
RS_PROFILE=PROFILE agent-navigation/tools/observe-slim.sh
agent-navigation/tools/rs-tool.sh observe_state '{}'
agent-navigation/tools/rs-tool.sh TOOL_NAME 'JSON_ARGS'

# 2006scape-route-agent: observe, route, validate, and render route topology
agent-navigation/tools/observe-slim.sh
python3 agent-navigation/tools/navdb.py next-step --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled true
python3 agent-navigation/tools/navdb.py validate
python3 agent-navigation/tools/navdb.py self-test
python3 agent-navigation/tools/route_runner.py --to PLACE --orient --json --run-reserve auto
agent-navigation/tools/route_runner.py --to PLACE --run-reserve auto
agent-navigation/tools/render_navigation_png.py --region all --output agent-navigation/topology/surface-routes.png

# 2006scape-route-planner-dev: graph planning and planner validation
python3 agent-navigation/tools/router.py plan --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/route_eval.py --from X,Y,H --to PLACE --combat-level N --food N --run-energy N --run-enabled
python3 agent-navigation/tools/route_runner.py --to PLACE --orient --json --run-reserve auto
python3 agent-navigation/tools/route_runner.py --to PLACE --max-walk-distance 48 --max-batches 6 --dry-run
python3 agent-navigation/tools/route_runner.py --to PLACE --run-reserve auto --evidence-jsonl agent-navigation/.local/run-evidence/route.routes.jsonl
python3 agent-navigation/tools/marathon_runner.py --laps 10 --run-reserve auto
python3 agent-navigation/tools/render_agent_context_map.py --center X,Y,H --radius-tiles 72 --pixels-per-tile 5 --recent-seconds 60
python3 agent-navigation/tools/navdb.py graph-summary
python3 agent-navigation/tools/navdb.py trace-tests

# 2006scape-object-transitions: prove object-chain blockers
agent-navigation/tools/rs-tool.sh find_nearest_object '{"name":"gate","maxDistance":20}'
agent-navigation/tools/rs-tool.sh preview_local_path '{"x":X,"y":Y,"height":0,"moveNear":true,"applyBounds":true,"maxWalkDistance":48}'
agent-navigation/tools/rs-tool.sh interact_object '{"objectId":OBJECT_ID,"x":X,"y":Y,"option":"first"}'

# 2006scape-frontier-exploration: probe unknown graph edges
python3 agent-navigation/tools/route_runner.py --to X,Y,H --allow-frontier --direct-if-preview --probe-toward-target --orient --json --run-reserve auto
python3 agent-navigation/tools/route_runner.py --to X,Y,H --allow-frontier --direct-if-preview --probe-toward-target --max-walk-distance 48 --max-batches 4 --dry-run
python3 agent-navigation/tools/route_runner.py --to X,Y,H --allow-frontier --direct-if-preview --probe-toward-target --max-walk-distance 48 --max-batches 4 --run-reserve auto

# 2006scape-screenshot-capture: compact visual evidence
agent-navigation/tools/capture-cardinal-screenshots.sh --prefix reason
agent-navigation/tools/capture-client-screenshot.sh --prefix reason --native-size

# 2006scape-gameplay-progression: normal gameplay through rs tools
agent-navigation/tools/observe-slim.sh
python3 agent-navigation/tools/script_registry.py search combat
python3 agent-navigation/tools/mining_runner.py --target-mining-level 20 --auto-buy-bronze-pickaxe
python3 agent-navigation/tools/combat_runner.py --npc goblin --target-level 10 --quiet
python3 agent-navigation/tools/bank_loadout.py --preset cowhide-trip --dry-run --json
python3 agent-navigation/tools/food_runner.py --mode fish-cook --quiet
python3 agent-navigation/tools/smithing_runner.py --mode smith --item sword --amount 10
python3 agent-navigation/tools/woodcutting_runner.py --tree oak --stop-when-inventory-full --quiet

# 2006scape-character-memory: sparse profile-scoped memories and goals
python3 agent-navigation/tools/character_memory.py show --profile PROFILE --json
python3 agent-navigation/tools/character_memory.py remember --profile PROFILE --kind resource --priority high --tags equipment --text "A better axe is a useful near-term upgrade before long woodcutting or fletching sessions."
python3 agent-navigation/tools/character_memory.py goal --profile PROFILE --priority normal --tags gear --text "Upgrade from a bronze axe when the character has enough coins and shop access."

# 2006scape-script-registry: discover or run known helper scripts
python3 agent-navigation/tools/script_registry.py list
python3 agent-navigation/tools/script_registry.py search "agility"
python3 agent-navigation/tools/script_registry.py search "mining"
python3 agent-navigation/tools/script_registry.py search "fletching"
python3 agent-navigation/tools/script_registry.py search "woodcutting"
python3 agent-navigation/tools/script_registry.py search "combat"
python3 agent-navigation/tools/script_registry.py search "food"
python3 agent-navigation/tools/script_registry.py search "smithing"
python3 agent-navigation/tools/script_registry.py search "bank"
python3 agent-navigation/tools/script_registry.py search "cowhide"
python3 agent-navigation/tools/script_registry.py search "memory"
python3 agent-navigation/tools/script_registry.py show route --json
python3 agent-navigation/tools/script_registry.py run agility -- --laps 10

# 2006scape-cache-map: static cache-backed map rendering
agent-navigation/tools/cache_world_map.py --bounds 3200,3200,3210,3210 --output /tmp/2006scape-cache-map-smoke.png --summary /tmp/2006scape-cache-map-smoke.json
agent-navigation/tools/cache_world_map.py --output agent-navigation/topology/cache-world-map.png --summary agent-navigation/topology/cache-world-map.json
python3 agent-navigation/tools/render_agent_context_map.py --center latest

# 2006scape-map-visualization: canonical map visuals
agent-navigation/tools/render_movement_topology_v4.py
agent-navigation/tools/render_movement_topology_v5.py
agent-navigation/tools/render_movement_topology_v6.py
python3 agent-navigation/tools/render_agent_context_map.py --segment-from FROM_PLACE --segment-to TO_PLACE

# 2006scape-agent-session-logs: inspect logs and summarize event types
find "2006Scape Server/data/logs/agent-sessions" -type f | sort
sed -n '1,220p' "2006Scape Server/data/logs/agent-sessions/DATE/SESSION.md"
jq -r '.event' "2006Scape Server/data/logs/agent-sessions/DATE/SESSION.jsonl" | sort | uniq -c
```

## Default Starting Points

For read-only questions, inspect the relevant docs or source first and answer without changing files.

For file edits, use `2006scape-dev-editing` plus the subsystem skill. Keep edits away from unrelated dirty files and preserve generated/local-only files.

For live navigation, use this context ladder before spending tokens: `observe-slim` for current state, `route_runner.py --to PLACE --orient --json --run-reserve auto` for non-moving A-to-B context, `render_agent_context_map.py` JSON/PNG for suspicious detours or static geometry, then compact screenshots only for live visual ambiguity such as gate/door state, wrong-side positioning, object failures, or API/map disagreement.

For live gameplay, observe first and use repo-side bridge wrappers. Prefer batch tools and treat their returned state as the next observation. If a long batch command is already running, wait near the expected completion interval before polling output instead of short-polling every few seconds. For route/mining movement, `route_runner.py` refreshes `set_run true` before long run-approved legs, unless reserve policy says not to run. Batch lines expose `runReq`, `runBefore`, `runAfter`, `runSpent`, `expectedRunSpend`, `tps`, `tilesPerTick`, and `runWarn`; if `runWarn` is not `none`, treat it as evidence that run was requested but not effective. Use `--evidence-jsonl PATH` for structured route-batch run-efficiency evidence, and expect `mining_runner.py` to write a sibling `.routes.jsonl` automatically.

For new gameplay automation, keep strategy in Python scripts and data. Read `agent-navigation/scripting-primitives.md`; use stable primitives such as `use_item_on_item`, `use_item_on_object`, `click_interface_button`, `select_interface_item`, `interact_object`, `interact_npc`, bank/shop tools, combat tools, and `wait_until_idle` before adding Java. Existing Java skill tools are compatibility surfaces, not the default place for new loops. Current primitive-backed runners cover mining, woodcutting/fletching, food, smithing, combat, and compact bank loadout policies.

For long autonomous gameplay or progression, load the selected character's sparse memory with `character_memory.py show --profile PROFILE --json`. Write new memory only for durable, decision-changing goals or lessons; do not log routine progress, temporary route details, secrets, or facts that belong in route data/session logs. Character memory is profile-scoped so `MrFlame` and `MrGem` stay separate.

For visual route ambiguity, use compact screenshots through `agent-navigation/tools/capture-cardinal-screenshots.sh --prefix REASON`; open only the angle(s) needed to answer the question, and do not load oversized full-screen captures.

For runtime management, prefer `agent-navigation/tools/runtime_doctor.py` plus `docs/local-agent-startup.md`, and avoid interrupting active agents unless the user asked for a restart or stop.

For maps, use cache-backed tools and keep the retired screenshot/minimap fog collector retired. Agents should use `render_agent_context_map.py` for current-tile and route-segment context; it draws all cache mapfunction icons in bounds, keeps nearby segment geometry such as docks/ports visible, and writes unique ignored PNG/JSON artifacts under `agent-navigation/.local/context-maps/<date>/` by default. Use the returned JSON path for marker/place labels instead of assuming a stable topology filename, and open the PNG only when visual geometry is needed. The active full movement maps are the profile movement map, `Heat Map`, and profile fog; they are user-facing analysis tools unless the user explicitly asks for them. Cache-map work is static and should not need a live client.

For session logs, summarize observable events from logs and rollout transcripts. Do not invent hidden reasoning; describe decisions through visible messages, tool calls, retries, results, and outcomes.

## Skill Maintenance

If a child skill gains a new primary script, boundary, or repeated workflow, update this entry skill so fresh agents can discover it without preloading every child body. If you notice a missing routing rule, stale pointer, or better workflow, surface it to the user and ask whether to make the skill edit.
