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
