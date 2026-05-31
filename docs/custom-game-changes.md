# Custom Game Changes

This is the living tracker for intentional gameplay changes made on top of the stock 2006Scape server. Use it to explain what changed, why it changed, where the implementation lives, and how future agents should verify or extend the work.

Custom content should still keep its implementation details close to the code under `2006Scape Server/src/main/java/com/rs2/game/content/custom/`. This file is the higher-level product and design ledger.

## Tracking Rules

- Add an entry for every user-requested gameplay customization that changes quests, shops, rewards, NPC behavior, world interactions, progression, or economy.
- Record the player-facing behavior and the reason for the change, not only the files touched.
- Link the implementation, docs, and tests so a future agent can inspect the full change without searching blindly.
- Note any live-runtime caveats. Source changes are not visible in the running server until it is deliberately rebuilt and restarted.
- Keep custom content segmented behind generic hooks. Core server files should contain minimal wiring, not feature-specific behavior.

## Current Customizations

| Area | Change | Status | Notes |
| --- | --- | --- | --- |
| Lumbridge quests | `Pantry Panic` custom quest | Implemented in source | Adds a short Lumbridge story quest with NPC dialogue, item gathering, hand-in, reward, and agent guide. |
| Lumbridge shops | Bob's Brilliant Axes stock expansion | Implemented in source | Adds better standard axes to Bob's shop at OSRS shop prices; black and dragon axes are excluded by request. |

## Pantry Panic

Type: Custom Lumbridge quest.

Player-facing behavior:

- Players start `Pantry Panic` by talking to Hans in Lumbridge Castle.
- The quest sends the player to the Cook, has them collect cabbage, egg, and bucket of milk, then report success to Duke Horacio.
- The reward is 1 Quest Point, 1,154 Cooking XP, 10,000 coins, and 50 cooked lobsters.
- A dedicated guide gives Codex agents coordinates, item IDs, dialogue flow, and troubleshooting notes.

Reasoning:

- Proves that we can safely add authored custom game content to 2006Scape without scattering feature-specific logic through the older server code.
- Gets our toes wet with the full custom quest loop: NPC dialogue, dialogue options, item collection, item hand-in, quest journal updates, save/load, and rewards.
- Establishes a small working example future custom content can follow: standalone custom files, minimal generic core hooks, focused tests, and an agent-readable guide.

Implementation:

- Quest: `2006Scape Server/src/main/java/com/rs2/game/content/custom/quests/lumbridge/pantrypanic/PantryPanicQuest.java`
- Agent guide: `2006Scape Server/src/main/java/com/rs2/game/content/custom/quests/lumbridge/pantrypanic/GUIDE.md`
- Custom framework docs: `2006Scape Server/src/main/java/com/rs2/game/content/custom/README.md`
- Test coverage: `2006Scape Server/src/test/java/com/rs2/game/content/custom/CustomContentTest.java`

Validation:

- `mvn -q -pl "2006Scape Server" -Dtest=CustomContentTest test`
- `mvn -q -pl "2006Scape Server" test`
- `git diff --check`

## Bob's Brilliant Axes Stock Expansion

Type: Custom Lumbridge shop/economy change.

Player-facing behavior:

- Bob's Brilliant Axes in Lumbridge now stocks standard woodcutting axes up through rune.
- Stocked axes and prices:

| Item | Id | Stock | Price |
| --- | ---: | ---: | ---: |
| Bronze axe | `1351` | 10 | 16 coins |
| Iron axe | `1349` | 5 | 56 coins |
| Steel axe | `1353` | 3 | 200 coins |
| Mithril axe | `1355` | 1 | 1,664 coins |
| Adamant axe | `1357` | 1 | 4,096 coins |
| Rune axe | `1359` | 1 | 40,960 coins |

- Bob's existing basic shop identity is preserved: the bronze pickaxe and battleaxes remain in stock.
- Black axe `1361` and dragon axe `6739` are intentionally not stocked.

Reasoning:

- Woodcutting progression should not stall because useful axes are effectively unavailable from local shops.
- Perry's Chop-chop Shop is not currently a practical source in this server setup, so Bob is the safest early-game place to expose the progression path.
- Prices use OSRS shop values for the equivalent standard axes: Bob sells bronze, iron, and steel in OSRS; Perry sells mithril, adamant, and rune in OSRS.
- Excluding black and dragon axes keeps the change conservative. Black is not normally shop-sold in OSRS, and dragon is a higher-tier special case that the user explicitly removed from scope.

Implementation:

- Custom shop registry and overrides: `2006Scape Server/src/main/java/com/rs2/game/content/custom/shops/CustomShops.java`
- Shop customization docs: `2006Scape Server/src/main/java/com/rs2/game/content/custom/shops/README.md`
- Minimal stock hook: `2006Scape Server/src/main/java/com/rs2/game/shops/ShopHandler.java`
- Minimal price hook: `2006Scape Server/src/main/java/com/rs2/game/shops/ShopAssistant.java`
- Test coverage: `2006Scape Server/src/test/java/com/rs2/game/content/custom/shops/CustomShopsTest.java`

Validation:

- `mvn -q -pl "2006Scape Server" -Dtest=CustomShopsTest test`
- `mvn -q -pl "2006Scape Server" test`
- `git diff --check`

Reference prices:

- `https://oldschool.runescape.wiki/w/Axe`
- `https://oldschool.runescape.wiki/w/Bob`

## Template For Future Entries

```markdown
## Change Name

Type: Quest, shop, NPC, area, item, object, skill, economy, or agent-facing guide.

Player-facing behavior:

- What players can now do or see.

Reasoning:

- Why this belongs in the game.
- What problem it solves.
- What scope boundaries were chosen.

Implementation:

- Main source files.
- Generic hooks.
- Docs or guides.
- Tests.

Validation:

- Focused test command.
- Broader test command, if shared behavior changed.
- Live-runtime proof, if requested and performed.

Known follow-up:

- Risks, blockers, spawn checks, balance decisions, or runtime restart notes.
```
