# Custom Shops

This package is the home for user-requested shop stock and price changes that should stay separate from the older core shop data and handlers.

The core shop system still owns normal loading, restocking, buying, and selling. Custom shop code should only describe the custom stock or custom price rules, then plug into `ShopHandler` and `ShopAssistant` through small generic hooks.

## How Shops Work

- Static shop stock is loaded from `2006Scape Server/data/cfg/shops.json`.
- `ShopHandler.loadShops()` copies that JSON into static arrays such as `shopItems`, `shopItemsN`, `shopItemsSN`, and `shopItemsStandard`.
- Items are stored internally as `itemId + 1`, matching the older inventory/shop convention.
- `itemAmount` is both current stock and normal restock target when the shop loads.
- `ShopAssistant.getItemShopValue(...)` prices normal coin shops from the cache `ItemDefinition` value, not from `shops.json`.
- There is no per-item price field in `shops.json`.

Because stock and price are separate, a custom shop change that needs exact prices should usually add:

- a stock override in `CustomShops.applyStockOverrides()`
- a price override in `CustomShops.getShopValue(...)`
- one focused test that proves the stock and price path

## Bob's Brilliant Axes

The custom Bob's Brilliant Axes override keeps Bob's original basic shop identity, preserves the bronze pickaxe and battleaxes, and adds better standard woodcutting axes without editing `shops.json` directly.

Bob now stocks:

| Item | Id | Stock | Buy price |
| --- | ---: | ---: | ---: |
| Bronze pickaxe | `1265` | 5 | cache price |
| Bronze axe | `1351` | 10 | 16 coins |
| Iron axe | `1349` | 5 | 56 coins |
| Steel axe | `1353` | 3 | 200 coins |
| Mithril axe | `1355` | 1 | 1,664 coins |
| Adamant axe | `1357` | 1 | 4,096 coins |
| Rune axe | `1359` | 1 | 40,960 coins |
| Iron battleaxe | `1363` | 5 | cache price |
| Steel battleaxe | `1365` | 2 | cache price |
| Mithril battleaxe | `1369` | 1 | cache price |

Black axe `1361` and dragon axe `6739` are deliberately not stocked. If a future request changes that, add them explicitly with a price decision in `CustomShops` and update the tests and this README.

The bronze, iron, steel, mithril, adamant, and rune axe prices use OSRS shop prices from the OSRS Wiki axe table. Bob sells bronze/iron/steel in OSRS; Perry sells mithril/adamant/rune in OSRS. Dragon and black were excluded by request.

Useful source pages:

- `https://oldschool.runescape.wiki/w/Axe`
- `https://oldschool.runescape.wiki/w/Bob`

## Catherby Trader Stan's Trading Post

The Catherby charter trader uses the existing local shop id `348`, named `Trader Stan's Trading Post` in `shops.json`.

Modern OSRS has Trader Stan at Port Sarim and Trader Crewmembers at other charter docks, including Catherby. The modern wiki says charter Trading Posts have identical inventory across locations, but each location is its own shop instance. The local server currently has one shop id for the Trading Post, so this first pass wires only a Catherby Trader Crewmember to that existing shared shop. Future charter ports can either reuse shop `348` for shared local stock or introduce separate shop ids if we want modern per-port stock independence.

Custom behavior added for Catherby:

| Item | Id | Local stock | Buy price |
| --- | ---: | ---: | ---: |
| Glassblowing pipe | `1785` | 10 | 5 coins |
| Bucket of sand | `1783` | 10 | 5 coins |
| Seaweed | `401` | 20 | 5 coins |
| Soda ash | `1781` | 20 | 5 coins |

The local stock quantities are preserved because the existing `shops.json` already has the needed glass supplies. The explicit prices keep these supplies from falling back to missing or one-coin item-definition values.

The Catherby shop access path is:

- `CustomNpcSpawns` adds a Trader Crewmember `4651` at `2792,3415,0`, the Catherby charter dock coordinate from the OSRS charter map.
- `CustomShops.getShopIdForNpc(4651)` maps that NPC to shop `348`.
- Generic `NpcActions` hooks call `CustomShops.dialogueShop(...)` on first-click and `CustomShops.openShop(...)` on second-click.

Related crafting support:

- `CustomGlassmaking` handles bucket of sand `1783` or soda ash `1781` used on supported furnace object ids.
- One bucket of sand plus one soda ash creates molten glass `1775` and grants 20 Crafting XP.
- Existing `GlassBlowing` code then supports glassblowing pipe `1785` plus molten glass `1775`.

Useful source pages:

- `https://oldschool.runescape.wiki/w/Trader_Stan%27s_Trading_Post`
- `https://oldschool.runescape.wiki/w/Charter_ship`
- `https://oldschool.runescape.wiki/w/Molten_glass`
- `https://oldschool.runescape.wiki/w/Glassblowing_pipe`

## Adding A Custom Shop Change

1. Identify the existing shop id in `shops.json` and the NPC mapping in `Shops.java`.
2. Decide whether the change is pure stock, pure price, or both.
3. Put the custom rule in `CustomShops`, not directly in `ShopAssistant` or unrelated content classes.
4. For stock overrides, replace the standard stock with a full intended list so removed items stay removed.
5. For price overrides, return a value only for the exact shop id and item id. Return `null` for unrelated content.
6. Preserve normal server mechanics: shop open, buy, sell, restock, inventory checks, and logging should stay in the core shop classes.
7. Add or update a focused test under `src/test/java/com/rs2/game/content/custom/shops/`.

## Testing

Use focused tests first:

```sh
mvn -q -pl "2006Scape Server" -Dtest=CustomShopsTest test
```

Then run the broader server test suite when the change touches shared shop code:

```sh
mvn -q -pl "2006Scape Server" test
git diff --check
```

These checks compile and test source code only. They do not restart the running server. Live gameplay will not see shop changes until the server is deliberately rebuilt and restarted.
