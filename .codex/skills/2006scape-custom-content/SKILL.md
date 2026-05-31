---
name: 2006scape-custom-content
description: "Use when adding, refactoring, reviewing, or documenting custom gameplay content in /Users/kevin/Documents/2006Scape, including custom quests, shop/store stock and price changes, custom rewards, NPC/object/item interactions, quest guides, and the custom-game-changes ledger."
---

# 2006Scape Custom Content

## Overview

Use this skill for gameplay content layered on top of the stock 2006Scape server. It keeps custom quests, shops, rewards, and player-facing changes segmented under the custom-content package, with only minimal generic wiring in older core handlers.

For source edits, also use `2006scape-dev-editing`.

## First Reads

- `AGENTS.md`: repo guardrails, build commands, runtime cautions, and no-secrets rules.
- `docs/custom-game-changes.md`: the living ledger for intentional gameplay customizations. Update it for every player-facing custom change.
- `2006Scape Server/src/main/java/com/rs2/game/content/custom/README.md`: custom-content architecture, quest hooks, save-state conventions, and test expectations.
- For store or shop work: `2006Scape Server/src/main/java/com/rs2/game/content/custom/shops/README.md` and `CustomShops.java`.
- For quest work: inspect the nearest existing custom quest folder and its `GUIDE.md`, such as `quests/lumbridge/pantrypanic/`.

## Architecture Rules

- Put feature-specific code under `com.rs2.game.content.custom` whenever possible.
- Core server classes should contain generic hooks only, such as `CustomContent.handleNpcClick(...)` or `CustomShops.applyStockOverrides()`.
- Do not import a specific custom quest or one-off feature into older handlers like `DialogueHandler`, `NpcActions`, `ObjectsActions`, `ShopAssistant`, or `PlayerSave`.
- Add one generic custom-content hook when a new event surface is required, then route feature behavior from the custom package.
- Prefer normal game mechanics: dialogue handlers, inventory add/delete, existing shop loading, object/NPC click paths, reward helpers, and skill XP APIs.
- Fail closed for unrelated NPCs, objects, item ids, button ids, dialogue ids, and shop ids.
- Do not restart the running server/client unless the user explicitly asks for live validation.

## Quest Workflow

1. Create a standalone folder by area and quest name under `custom/quests/<area>/<questname>/`.
2. Keep the quest implementation responsible for its constants, dialogue ids, stage constants, NPC/object/item ids, reward logic, and quest journal text.
3. Store progress through `CustomQuestState` and stable `customQuestStage-*` save keys, not new fields on `Player`.
4. Register the quest through `CustomContent`, not through feature-specific imports in core handlers.
5. Add or update a `GUIDE.md` when agents need coordinates, item ids, dialogue flow, or troubleshooting notes to play the quest.
6. Test registration, quest tab dispatch, dialogue/options, stage transitions, item hand-ins, object clicks, reward delivery, save/load, and unrelated hook behavior.

## Shop Workflow

1. Identify the existing shop id and base stock source before changing behavior.
2. Prefer custom stock and price overrides in `custom/shops/CustomShops.java`.
3. Preserve the shop's existing identity unless the user asks for a replacement.
4. Use explicit item ids, quantities, and prices. Record the balance/source rationale in the shop docs or ledger.
5. Add focused tests that prove the target shop changed and unrelated shops remain unchanged.

## Documentation

Update `docs/custom-game-changes.md` for every custom gameplay change. Each entry should include:

- Player-facing behavior.
- Reasoning and scope boundaries.
- Implementation links.
- Test commands and live-runtime caveats.
- Known follow-up items or validation gaps.

Keep detailed implementation notes close to the code under `custom/`; keep the ledger focused on what changed in the game and why.

## Validation

Use focused tests first, then broaden when shared behavior changed:

```sh
mvn -q -pl "2006Scape Server" -Dtest=CustomContentTest test
mvn -q -pl "2006Scape Server" -Dtest=CustomShopsTest test
mvn -q -pl "2006Scape Server" test
git diff --check
```

These commands compile and test source code only. Source changes will not appear in the running game until the server is deliberately rebuilt and restarted.

## Finish Check

- Custom code is segmented under `com.rs2.game.content.custom`.
- Core wiring is generic and minimal.
- Rewards and economy changes cannot be duplicated or exploited through repeated interactions.
- Tests cover the new behavior and unrelated negative paths.
- The customization ledger and any targeted guide/docs are current.
