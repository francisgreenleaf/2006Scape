---
name: 2006scape-tick-analysis
description: "Use when instrumenting, analyzing, or optimizing 2006Scape gameplay runner timing, tick efficiency, idle gaps, action-to-item latency, per-item arrival logs, lap timing, or compact performance reports. Applies to scripts such as Seers flax spinning and future skilling runners where raw JSONL logs should be summarized by tooling instead of read directly."
---

# 2006Scape Tick Analysis

Use this skill for timing instrumentation and performance tuning of primitive-backed gameplay runners in `$REPO_ROOT`.

## Core Workflow

1. Keep gameplay traffic compact. Do not add bridge observes just for logging. Reuse compact XS/XXS action results, inventory deltas, wait results, and local monotonic timestamps.
2. Log local JSONL events with consistent fields: `event`, `ts`, `seq`, `runElapsedMs`, `sincePrevEventMs`, and phase-specific fields such as `durationMs`, `reason`, `attempt`, `before*`, `after*`, and `batchTicks`.
3. Emit `action_start` before meaningful actions such as resource clicks, object transitions, interface clicks, banking, or production starts.
4. Emit `item_arrived` whenever an item count increases or a produced item appears in compact state. Include `phase`, `itemId`, `itemName`, `deltaCount`, source action, and latency fields such as `clickToObservedMs` or `sinceAttemptUseMs` when available.
5. Analyze with a compact report before reading raw logs:

```sh
PROFILE=PROFILE RS_PROFILE=PROFILE RS_TRACE_PROFILE=PROFILE python3 agent-navigation/tools/tick_analysis_report.py --latest --runner seers-flax-spin-fast --profile PROFILE
```

Use raw JSONL only when the report points to a specific suspicious event, missing field, or malformed span.

## Instrumentation Rules

- Local logging must be cheap: no sleeps, no extra bridge calls, no full observe, no screenshots, and no server mutations.
- Prefer one event per actual bridge action, one event per wait/progress chunk, and one `item_arrived` per detected item. If several items arrive between compact polls, log each event with the same timestamp and a shared `deltaCount`.
- Carry bridge result players forward. Treat returned compact player state as the next observation when it contains the fields required for the log.
- For route and transition timing, mark approach movement, arrival/skips, `action_start`, transition result, and post-state proof fields such as tile/height.
- For production timing, capture first-item latency, per-chunk progress, final inventory delta, and total inventory duration.

## Report Expectations

The report should make the next optimization decision obvious. It should include:

- cycle/lap duration min/avg/max;
- pick or gather action latency, no-progress clicks, and item-arrival intervals;
- production item intervals, first-item latency, chunks, and reclicks;
- route/transition spans such as field-to-ladder, ladder arrival-to-click, ladder transition, upstairs-to-first-product, and bank legs;
- slowest timed events.

When a log predates the `item_arrived` schema, the analyzer may show fallback estimates, but do not treat those as exact item timing.

## Runner Changes

Keep changes narrow and runner-local unless multiple scripts already need the same helper. Reusable helpers belong under `agent-navigation/tools/`, currently `tick_analysis.py` for event metadata and `tick_analysis_report.py` for compact summaries.

When updating a live runner, use cooperative controls and restart only at a safe boundary if the user wants the new code active immediately. After `--request-stop`, poll a tiny `--shutdown-status`/XS control surface when available instead of repeatedly printing verbose `--status` output. Do not stop/restart the server, client, runtime, or other profiles for tick analysis.
