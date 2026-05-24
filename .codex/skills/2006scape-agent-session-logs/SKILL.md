---
name: 2006scape-agent-session-logs
description: "Use when reading, summarizing, debugging, or improving 2006Scape agent session logging in /Users/kevin/Documents/2006Scape, including 2006Scape Server/data/logs/agent-sessions JSONL and Markdown files, AgentSessionLog, AgentSessionReport, rollout transcript enrichment, redaction, canonical reports, and profile/personality artifacts exposed through rs.observe_state."
---

# 2006Scape Agent Session Logs

Use this skill for the local agent-session memory system. Treat the files as logs and derived artifacts, not gameplay controls.

## Safety

Do not reveal tokens, API keys, passwords, saved-character secrets, nonces, or raw bridge session files. If a log contains sensitive fields, summarize around them and call out that they are redacted or should be redacted.

Do not mutate live gameplay or restart the runtime while inspecting logs. Other agents may be active.

## Main Locations

- `2006Scape Server/data/logs/agent-sessions/<yyyy-MM-dd>/<sessionId>.jsonl`: raw session events.
- `2006Scape Server/data/logs/agent-sessions/<yyyy-MM-dd>/<sessionId>.md`: readable per-session summary.
- `2006Scape Server/data/logs/agent-sessions/reports/<yyyy-MM-dd>/summary-<HHMMSS>Z.md`: generated rollup reports.
- `2006Scape Server/data/logs/agent-sessions/reports/canonical-agent-log-index.md`: canonical report index.
- `2006Scape Server/data/logs/agent-sessions/profiles/<profile>/agent-personality.md`: derived first-person profile memory.
- `2006Scape Server/data/logs/agent-sessions/profiles/<profile>/agent-personality-state.json`: structured profile state.
- `~/.codex/sessions/<yyyy>/<MM>/<dd>/rollout-*.jsonl`: Codex rollout transcript source, when available.

## Source Files

- `2006Scape Server/src/main/java/com/rs2/agent/AgentSessionLog.java`: raw JSONL events and per-session Markdown.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentSessionReport.java`: rollup reports and canonical index.
- `2006Scape Server/src/main/java/com/rs2/agent/AgentProfileMemory.java`: profile/personality artifacts and `agentPersonality` context.

## Reading Logs

Prefer targeted reads. Logs can contain very large `observe_state` payloads, bank contents, nearby objects, and profile memory.

```sh
find "2006Scape Server/data/logs/agent-sessions" -type f | sort
sed -n '1,220p' "2006Scape Server/data/logs/agent-sessions/<date>/<session>.md"
```

For JSONL, summarize event types before reading whole entries:

```sh
jq -r '.event' "2006Scape Server/data/logs/agent-sessions/<date>/<session>.jsonl" | sort | uniq -c
```

When using a Codex rollout transcript, extract observable events only: user goal, assistant updates, tool calls, tool results, retries, course corrections, and final outcome. Do not invent hidden reasoning.

## What Good Summaries Include

Per-session Markdown should capture:

- task and player/profile;
- what was attempted and what succeeded;
- obstacles, in-game blockers, death, missing items, unsafe state, or unavailable objects/NPCs;
- observable decision trail from logs and rollout events;
- outcome, next step, reflection, and what the harness appears to be learning.

Profile memory should be durable and account-scoped. It should synthesize repeated sanitized session patterns into beliefs, slow drift, self-formed goals, and bounded self-talk without overriding the player's command.

## Validation

After changing log/report code, compile and run focused checks where available:

```sh
mvn -q -DskipTests package
mvn -q clean test
```

If generating a report manually, run from the server context expected by the code and inspect the report path printed by `AgentSessionReport`.

## Skill Maintenance

If you find a better redaction rule, report structure, rollout-matching method, or profile-memory boundary while using this skill, surface it to the user and ask whether to make the skill edit.
