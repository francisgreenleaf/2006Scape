# Harness Context Improvement Report

This is a retrospective on context usage from the first 2006Scape character-control sessions through the current XS/XXS harness. It is intentionally separate from `docs/Harness Improvement Opportunities.md`, which remains the live backlog.

The main story is progression, not just reduction. The early direct-control era proved the bridge could play the game but exposed how much context full state snapshots consumed. The Python route-learning era deliberately spent more context on screenshots, maps, rollout evidence, and source reads so the harness could learn the world and improve itself. The current XS/XXS era turns that learning into compact defaults for normal gameplay.

## Scope And Method

The early samples came from local Codex rollout transcripts under `~/.codex/sessions/2026/05/23`, `2026/05/24`, and `2026/05/25`. The first true character-control rollout found was already using `rs.*` dynamic tools; no clean Java-only gameplay era was found in the sampled files. A search across the available session tree found only two rollouts with direct dynamic `namespace:"rs"` calls, so this report uses their percentages but does not cite a large aggregate token count for direct bridge play.

Token estimates are approximate. For tool output buckets, the estimate is serialized output characters divided by four. Peak live input tokens come from rollout `token_count` events where available. Percentages should be treated as directional, not exact accounting.

## Era Summary

| Era | Sampled evidence | Dominant context shape | Step forward |
| --- | --- | --- | --- |
| Direct bridge play | May 23 local / May 24 UTC, two available direct dynamic `rs.*` rollouts | Full `observe_state` dominated the available direct bridge output | Proved the agent could control the character through real mechanics |
| Python route and world learning | May 23-25, including a 28.2M-token route-learning sample and a 14.7M-token early harness sample | Screenshots/maps, raw rollouts/session logs, route/planner output, and source reads dominated | Converted direct control into reusable world knowledge and harness improvements |
| Current XS/XXS harness | Current docs/tools/rollout audits | Compact status, compact decision context, batch waits/actions, and targeted evidence reads | Turns the Python-era learning into normal-loop efficiency |

## Era 1: Direct Bridge Play

This era was the first successful proof that the agent could control the character through real game mechanics. It was a big capability step, but its context shape made the next improvement obvious.

| Category | Rough share |
| --- | ---:|
| Full `rs.observe_state` snapshots | 70% |
| `travel_to_landmark_until_arrived` results | 10% |
| `interact_object` result | 10% |
| `set_run` result | 10% |
| `find_nearest_object` / `observe_goal` | <1% |

- The agent was already using dynamic `rs.*` tools; no clean Java-only gameplay era was found in the sampled rollouts.
- Only two available rollout files contained direct dynamic `rs` namespace calls, so the total direct-play sample is too small to cite as a headline volume.
- In those available direct bridge outputs, full `rs.observe_state` snapshots made up about 70% of the returned content.
- The first direct `observe_state` calls returned about 1.8k-2.2k tokens each.
- Normal action results such as `set_run`, `travel_to_landmark_until_arrived`, and `interact_object` often returned roughly 800-900 tokens because they included broad player state.
- This context was not useless; it gave the agent enough information to act safely in early Lumbridge movement and object interaction.
- The problem was that confirmation-level actions carried decision-level or evidence-level state by default.
- The key lesson was that the bridge needed compact state contracts, not that the agent needed less information blindly.

## Era 2: Python Route And World Learning

This era used much more total context, but it was a productive investment. The agent was learning the world, reading its own rollouts, examining evidence, and turning fragile direct control into reusable route and harness knowledge. The breakdown below is from the first route-learning sample; the beginning Python/harness day showed the same pattern, with screenshots/maps, rollout evidence, route output, and code/docs reads doing most of the useful work.

| Category | Rough share |
| --- | ---:|
| Screenshots/maps/visual context | 42% |
| Raw rollout/session log evidence | 18% |
| Code/docs/data reads and diffs | 13% |
| Full bridge observe / `rs-tool` JSON | 7% |
| Python route/planner harness output | 6% |
| Broad repo searches | 6% |
| Server/runtime/build diagnostics | 3% |
| Bridge action wrapper output | 2% |

- Screenshots and maps were large, but they were useful: they let the agent understand geometry, doors, blocked movement, route shape, and ambiguous world state that the early tools could not yet express compactly.
- Raw rollout and session-log reads were also useful: the harness was being improved by inspecting what agents actually did, where they failed, and which tool results were too large.
- Full bridge observe / `rs-tool` JSON dropped from about 70% of the available direct bridge output to about 7% in the first Python route-learning sample.
- That roughly 70% to 7% shift was the first major context win: broad bridge snapshots stopped dominating the whole session.
- The beginning Python/harness day kept the same useful pattern: about 39% screenshots/maps, 21% rollout/session evidence, 14% route/planner output, and 14% code/docs/data reads.
- Python route/planner output became a meaningful share because routing logic, route definitions, navigation data, and helper scripts were being created and debugged.
- The tradeoff was that visual evidence, raw logs, and route dumps were still too heavy to keep in normal gameplay loops once their lessons had been extracted.
- The durable result was reusable world knowledge and tooling: route data, map evidence, compact wrappers, session-log readers, and the foundation for XS/XXS contracts.

## Era 3: Current XS/XXS Harness

The current era is another step forward: it preserves the useful learning from the Python period while making normal play compact by default.

- XXS tools now cover confirmation, survival, and status checks: tile, HP, run, combat, poison, death, food, free slots, and tiny XP deltas.
- XS tools now cover compact decision context for inventory, equipment, nearby NPC/object, bank, route, and skill decisions.
- `observe_state_if_changed_XS` and `_XXS` reduce repeated stable-state observations.
- Compact action and wait results are treated as the next observation when they include the fields needed for the next decision.
- `skillChanges` and `xpRecent` make XP updates event-based instead of forcing broad state refreshes.
- Batch banking, equipment, food, movement, object-transition, and combat-wait tools reduce both call count and payload size.
- Session and rollout audits now have compact reader paths so raw logs stay available for analysis without becoming routine context.
- Full tools remain available for debugging, complete evidence, and new workflows, but they are no longer the normal loop surface.

## After: Current Harness Shape

The current harness has shifted normal gameplay toward compact, purpose-built surfaces:

| Area | Before | After |
| --- | --- | --- |
| State checks | Full `observe_state` was routine. | `observe_state_XXS`, `observe_state_XS`, and `observe_state_if_changed_*` are the default choices. |
| Action confirmations | Many simple actions returned broad player snapshots. | XXS actions return confirmation plus critical survival/status state only. |
| Movement and routing | Walk/travel calls were often paired with full observes or route dumps. | `walk_path_steps_*`, `walk_to_tile_until_arrived_*`, `travel_to_landmark_until_arrived_*`, and ML1 route definitions keep route context compact. |
| Waiting and polling | Agents frequently used repeated waits and follow-up observes. | `wait_until_idle_*` and `wait_until_combat_event_smart_*` let the server wait to meaningful boundaries. |
| XP updates | Agents needed broader state or extra calls to notice XP changes. | `skillChanges` and short-lived `xpRecent` expose compact deltas, including Prayer-specific base/current semantics. |
| Banking/equipment | Single-item loops and post-action full observes were common. | Batch XS/XXS deposit, withdraw, unequip, food-bank, and excess-coin tools reduce both calls and payloads. |
| Session/rollout audits | Raw JSONL and rollout files were often read directly. | `agent_session_XS.py`, reports, and targeted reads are documented defaults. |
| Visual evidence | Large screenshots and maps could dominate a session. | Compact screenshots/context maps are reserved for ambiguity or evidence. |
| Tool adoption tracking | There was little visibility into which compact surfaces were used. | Out-of-band usage logging records XS/full access without adding it to normal context. |

## Net Improvement

For normal live gameplay loops, the practical improvement is roughly 80-95% less context per repeated observe/action cycle. In per-call terms, compact XS/XXS state usually saves about 10x-30x compared with the early full-state default.

The largest structural change is behavioral: full `observe_state`, full `rs-tool.sh`, and `observe-slim.sh` moved from normal-loop tools to fallback/debug tools. Compact action results are now treated as the next observation when they include the state needed for the next decision.

Learning/debug sessions can still justify larger context when the evidence buys durable world knowledge or harness improvements. The current harness reduces the need to repeat those large reads through compact route readers, compact map summaries, XS session-log readers, and stronger skill/docs wording, so the expensive evidence path becomes targeted analysis instead of normal gameplay context.

## Remaining Watch Points

- Runners should not call full `observe_state` after a compact wait/action result unless a named required field is missing.
- Large image/map loads should be explicit evidence, not routine route context.
- Raw JSONL and rollout reads should start with compact summaries and event counts.
- Full bridge tools should remain available for debugging, complete evidence, and new workflows, but not normal gameplay loops.
- Continued audits should compare compact share, full observe count, and large visual/log loads per hour rather than only counting tool calls.
