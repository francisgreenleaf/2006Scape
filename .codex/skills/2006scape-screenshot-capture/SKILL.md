---
name: 2006scape-screenshot-capture
description: "Use when visually debugging the live 2006Scape Java client from /Users/kevin/Documents/2006Scape with compact screenshots, especially when an agent needs north/east/south/west camera angles around the selected profile, route blockers, walls, gates, doors, stairs, or ambiguous object geometry without loading oversized desktop screenshots."
---

# 2006Scape Screenshot Capture

Use this skill only when API state, route JSON, and cache/context maps are not enough and live visual route evidence is needed.

## Four-Angle Capture

Run the cardinal capture helper from the repo root:

```sh
agent-navigation/tools/capture-cardinal-screenshots.sh --prefix route-debug
```

It uses the current local client pid when available, faces north, captures `north`, `east`, `south`, and `west`, then restores north. It writes PNGs under `agent-navigation/screenshots/captures/<date>/` and prints one JSON summary with file paths.

The default output size is `765x503` via `capture-client-screenshot.sh --native-size`. Do not request full-screen or high-resolution captures unless the user explicitly asks.

## When To Use

- Use after `observe-slim`, route orient JSON, preview, or a context map leaves ambiguous live geometry, such as a wall pocket, wrong side of a gate, hidden door, staircase, ladder, trapdoor, or unreachable object.
- Use when the current visible client state matters: open/closed gates and doors, player side of a fence, object click failure, unexpected stuck/oscillation near scenery, or API/cache-map disagreement.
- Do not use screenshots for ordinary A-to-B planning, static terrain/mapfunction lookup, or route quality checks that `route_runner --orient`, `route_eval.py`, or `render_agent_context_map.py` can answer.
- Use before changing route data based on visual assumptions.
- Use a single `capture-client-screenshot.sh --prefix REASON --native-size` when one angle is enough.

## Permissions

macOS may block process inspection, window focus, keyboard events, or `screencapture` inside the Codex sandbox. If the helper fails with `Operation not permitted`, rerun the same helper with a narrow escalation for the screenshot command.

Prefer the four-angle helper because it reads `agent-navigation/.local/client.pid` first and avoids `/bin/ps` when the runtime helper started the client.

## Review

Open only the needed PNG paths returned in JSON. Use high detail for the compact `765x503` files. Do not load full desktop screenshots into context unless there is no client-window capture available.
