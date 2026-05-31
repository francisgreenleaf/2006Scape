# Trader Stan's Trading Post Customization

This note covers the local Catherby implementation of Trader Stan's Trading Post.

## Current Scope

- Only the Catherby charter trader is wired.
- The shop uses existing local shop id `348`.
- The custom NPC spawn is Trader Crewmember `4651` at `2792,3415,0`.
- Other charter locations are intentionally not added yet.

## Player Flow

1. Travel to the Catherby charter dock near `2792,3415,0`.
2. Talk to or trade with the Trader Crewmember.
3. Buy glassblowing pipe `1785`, bucket of sand `1783`, and soda ash `1781`.
4. Use bucket of sand or soda ash on a supported furnace, such as the Ardougne furnace object `2781` near `2601,3310,0`.
5. The furnace converts one bucket of sand and one soda ash into molten glass `1775` for 20 Crafting XP.
6. Use glassblowing pipe `1785` on molten glass `1775` to open the existing glassblowing interface.

## Architecture

- `CustomShops` owns the Catherby Trader Crewmember to shop `348` mapping and explicit glass-supply prices.
- `CustomNpcSpawns` owns the Catherby Trader Crewmember spawn record.
- `CustomGlassmaking` owns the sand plus soda ash furnace behavior.
- Core files contain only generic hooks into custom content.

## Future Charter Ports

Modern OSRS charter trading posts have identical inventory but location-specific shop instances. The local server currently has one Trading Post shop id, so future ports can reuse shop `348` if shared local stock is acceptable. If we want modern per-port independence, add separate shop ids and map each custom spawn to its own shop id.

Source references:

- `https://oldschool.runescape.wiki/w/Trader_Stan%27s_Trading_Post`
- `https://oldschool.runescape.wiki/w/Charter_ship`
- `https://oldschool.runescape.wiki/w/Molten_glass`
