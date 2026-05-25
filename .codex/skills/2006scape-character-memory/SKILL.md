---
name: 2006scape-character-memory
description: "Use when reading, writing, reviewing, or updating sparse long-term memories and goals for a specific 2006Scape character/profile, including equipment goals, preferences, recurring blockers, strategic reminders, and future plans that should persist for MrFlame, MrGem, or another selected profile without polluting route data or session logs."
---

# 2006Scape Character Memory

Use this skill for intentional long-term character memory in `/Users/kevin/Documents/2006Scape`. This is not the route database, passive telemetry, or session-derived `agentPersonality`; it is a small profile-scoped notebook for things a future agent should deliberately remember.

## Storage

The helper stores ignored local files under:

```text
agent-navigation/.local/character-memory/<profile-slug>/
```

Each profile has separate `memories.jsonl`, `goals.jsonl`, and `summary.md` files. Always pass `--profile PROFILE` or set `RS_PROFILE=PROFILE`; the default is `MrFlame`. Known display variants such as `Mr. Flame` normalize to `MrFlame`, and `Mr. Gem` normalizes to `MrGem`.

## Read First

For long autonomous gameplay, progression, routing, or recovery work, read the selected character's compact memory before making strategic choices:

```sh
python3 agent-navigation/tools/character_memory.py show --profile MrFlame --json
python3 agent-navigation/tools/character_memory.py show --profile MrGem --json
```

Use the JSON for context. Do not load raw JSONL files unless debugging the helper.

## Write Sparingly

Write a memory only when it is durable and would change a future decision:

- a useful equipment/tool upgrade goal, such as needing a better axe or pickaxe;
- a recurring blocker, risk, route preference, or recovery lesson that does not belong in `routes.json`;
- a user or character preference that should persist across sessions;
- a strategic plan for banking, supplies, training, money-making, or unlocks;
- a noteworthy mistake or success pattern the agent should consider next time.

Do not write routine progress, every level, every inventory batch, every route leg, temporary coordinates, raw observations, secrets, bridge tokens, passwords, or anything better represented in `navdb.py`, passive movement traces, session logs, or JSON schemas.

## Commands

```sh
# Show compact current memory.
python3 agent-navigation/tools/character_memory.py show --profile MrFlame --json

# Add a durable memory.
python3 agent-navigation/tools/character_memory.py remember --profile MrFlame --kind resource --priority high --tags equipment,woodcutting --text "A better axe is a useful near-term upgrade before long woodcutting or fletching sessions."

# Add a long-term goal.
python3 agent-navigation/tools/character_memory.py goal --profile MrFlame --priority normal --tags gear,woodcutting --text "Upgrade from a bronze axe when the character has the coins and access to a suitable shop."

# Mark a goal complete, dropped, or blocked.
python3 agent-navigation/tools/character_memory.py complete-goal GOAL_ID --profile MrFlame --status done --note "Bought the upgraded axe and confirmed it is equipped."
```

Good entries are short, actionable, and evidence-backed when useful. Use one sentence unless the context genuinely needs more.

## Boundaries

Route facts, object-transition proof, and hazards belong in `agent-navigation/data/` through the route skills. Session summaries and personality drift belong in the agent-session logging system. Character memory is for intentional notes and goals that a future agent can use before deciding what to do.

