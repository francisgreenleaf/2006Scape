# Orphaned Shop Data And Era Accuracy

## Issue

Some shop records in `2006Scape Server/data/cfg/shops.json` appear to be imported reference data rather than reachable, normal-gameplay shops in the local 2006Scape world. This can mislead route, economy, and progression tooling into believing an item is buyable when no mapped NPC or object can actually open that store.

The immediate example is `Perry's Chop-chop Shop`:

- `shops.json` contains shop id `306`, `Perry's Chop-chop Shop`, with bronze through rune axes, including Adamant axe `1357` and Rune axe `1359`.
- `2006Scape Server/src/main/java/com/rs2/game/shops/Shops.java` does not map any NPC to shop id `306`.
- No direct `openShop(306)` call was found in normal NPC/dialogue shop paths.
- NPC id `306` is `Golrie`, not Perry, so the shop id is not naturally tied to a Perry NPC.
- The bridge `open_nearest_shop` path only opens shops through live NPCs that resolve through `Shops.Shop.forId(npc.npcType)`, so this shop is not reachable through normal bridge gameplay.

## History

- `Perry's Chop-chop Shop` was added to old `shops.cfg` in commit `680a0c2e` (`2019-11-29`, Danial / RedSparr0w), in "Add more shop definitions, Add legends guild stores (#217)".
- That commit added a large block of shops under a note equivalent to "NPC not added yet, Shop may not be 317".
- The shop data was converted to JSON in commit `8a6cf6f1` (`2020-08-13`, Sandro Coutinho), which is why current `git blame` on `shops.json` points to the JSON conversion rather than the original shop import.
- The warning/comment did not survive the JSON conversion, leaving orphaned or non-era shop rows looking authoritative.

## Broader Signal

A rough static pass over current `shops.json` found 275 shops total. About 149 have obvious static or direct shop-opening paths, while about 126 are orphaned or dynamic-unknown from a static scan. Some suspicious or clearly later-era names include:

- `Grace's Graceful Clothing`
- `Mythical Cape Store`
- `Myths' Guild Herbalist`
- `Myths' Guild Armoury`
- `Myths' Guild Weaponry`
- `Bounty Hunter Store`
- `Logava Gricoller's Cooking Supplies`
- `Perry's Chop-chop Shop`

This does not prove every unmatched shop is wrong; some may be opened through dynamic systems or unfinished content. It does mean consumers should not treat `shops.json` alone as proof of buyability.

## Suggested Future Work

- Add a small audit tool that classifies shops as:
  - reachable via `Shops.java` NPC mapping,
  - reachable via direct `openShop(...)` code path,
  - dynamically reachable/needs manual proof,
  - orphaned/import-only,
  - era-suspicious.
- Generate a machine-readable allowlist for progression/routing tools so they only plan purchases from proven reachable shops.
- Add a separate review list for post-2006 or OSRS-specific imports, especially Great Kourend/Hosidius, Myths' Guild, graceful outfit, and other later-era content.
- Preserve historical context from old `shops.cfg` comments somewhere structured so future JSON consumers can see whether a shop was known incomplete or out of scope.

## Current Practical Rule

For gameplay automation, do not infer that an item is buyable just because it appears in `shops.json`. Treat a shop as buyable only after confirming a reachable NPC/object/dialogue path and, ideally, observing it live through normal gameplay.
