---
name: 2006scape-dev-editing
description: Use at the start of any coding, debugging, reviewing, building, testing, maintenance, or file-changing task in /Users/kevin/Documents/2006Scape. Provides repo-specific development workflow rules and curated actionable lessons learned from actual agent experience in this repository, including Java/Maven client-server work, the Codex agent bridge, route tooling, tests, runtime processes, generated files, and validation habits. Also use after completing repo edits to decide whether to add a durable lesson for future agents.
---

# 2006Scape Dev Editing

This skill is the repo-specific "learn from mistakes" layer. Use it with `AGENTS.md`, not instead of it.

## Before Editing

Read `AGENTS.md` for baseline repo rules, then read `references/actionable-lessons.md` before the first file mutation. If the lesson file grows large, search it for the subsystem you are touching before reading broadly.

Keep the lesson file out of the hot path unless it is relevant. Do not load or quote it when the user only asks a narrow read-only question.

## During Work

Prefer repo-local workflows and validation from `AGENTS.md`. Treat this skill as operational memory for issues agents have actually hit while working here.

When a known lesson applies, follow its corrected workflow before improvising. If current evidence contradicts a lesson, re-verify and update the lesson after the task.

When changing runtime bridge behavior, remember that a compiled jar is not live code. Build first, restart through the documented launcher flow, then prove the behavior through the bridge wrapper.

When creating or changing repo tools, make profile agnosticism part of the design check. Runnable helpers should accept `--profile PROFILE` or honor `RS_PROFILE`/`RSBRIDGE_PROFILE`, propagate the resolved profile to child commands and bridge calls, and avoid new MrFlame-only path assumptions. Writable status, evidence, logs, maps, and caches should be profile-scoped or carry explicit `profile`, `playerName`, and `sessionId` metadata when intentionally shared.

For bridge-facing work, keep Java changes to reusable player/session-scoped primitives. Put route choice, skilling loops, combat trip policy, banking strategy, and recovery decisions in Python scripts or data so the strategy layer can select the profile independently of the Java tool surface.

## Updating Lessons

After completing repo edits or debugging, consider whether to update `references/actionable-lessons.md`.

Add a lesson only when all are true:

- You personally hit the issue, verified the cause, or fixed it during this task.
- The lesson would have changed your actions earlier in the task.
- The issue is likely to recur for future agents in this repo.
- The note can include a concrete file path, command, symptom, validation step, or decision rule.

Do not add:

- Hypothetical advice.
- General software engineering wisdom.
- Notes copied from `AGENTS.md`.
- One-off task summaries.
- Vague warnings such as "be careful".
- Lessons from stale context unless re-verified during the current task.

Use this format:

```markdown
### Short action-oriented title

- **Observed:** What happened, with the exact symptom or command when useful.
- **Cause:** The verified reason.
- **Use instead:** The corrected workflow or decision rule.
- **Validation:** The check that proves the fix or avoids the failure.
```

Keep entries short. Merge or replace stale lessons instead of accumulating duplicates.
