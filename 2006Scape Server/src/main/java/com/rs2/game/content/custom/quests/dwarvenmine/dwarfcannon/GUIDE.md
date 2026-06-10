# Dwarf Cannon Quest Guide

Agent-facing guide for the custom `Dwarf Cannon` quest.

## Summary

- Start NPC: Nulodion, NPC id `209`.
- Quest button: `28188`.
- Quest tab line: `7356`.
- Shop: `Nulodion's Multicannon Parts`, shop id `144`.
- Quest requirement: make one cannonball.
- Materials needed to finish: ammo mould `4`, steel bar `2353`, and access to a furnace object that supports cannonball crafting.
- Reward: 1 Quest Point, 750 Smithing XP, 25 cannonballs.

## Important Data

| Target | Id | Notes |
| --- | ---: | --- |
| Nulodion | `209` | Custom quest start, reminder, recovery, and completion handler. |
| Cannonball | `2` | Proof item for quest completion and the quest reward icon. |
| Ammo mould | `4` | Sold by Nulodion and required to make cannonballs. |
| Steel bar | `2353` | Required to make cannonballs. |
| Cannon base | `6` | Part returned by the recovery dialogue. |
| Cannon stand | `8` | Part returned by the recovery dialogue. |
| Cannon barrels | `10` | Part returned by the recovery dialogue. |
| Cannon furnace | `12` | Part returned by the recovery dialogue. |

## Cannonball Crafting

The existing `ItemOnObject` path already routes steel bar or ammo mould on supported furnace objects to cannonball making. The canonical object ids currently wired for cannonballs are:

`2781`, `2785`, `2966`, `3294`, `3413`, `4304`, `4305`, `6189`, `6190`, `11009`, `11010`, `11666`, `12100`, `12809`

Any of those should work as long as the player has both an ammo mould and a steel bar.

## Walkthrough

1. Talk to Nulodion.
   - Choose `Teach me.` to start the quest.
   - He explains that cannonballs are required before he trusts you with the kit.

2. Make one cannonball.
   - Get an ammo mould `4` and a steel bar `2353`.
   - Use the bar or mould on a supported furnace object from the list above.
   - The cannonball item is `2`.

3. Return to Nulodion with a cannonball in inventory.
   - The quest completes through the dialogue chain.
   - Reward screen: 1 Quest Point, 750 Smithing XP, 25 cannonballs.

4. Buy cannon parts if needed.
   - Nulodion can open shop `144` from the dialogue path at any time.
   - The shop stocks the ammo mould and the four cannon parts.

5. Recover a lost cannon if needed.
   - If the player has `lostCannon = true`, Nulodion can return the four parts.
   - Recovery requires at least 4 free inventory slots.

## Troubleshooting

- If Nulodion does not open the custom dialogue, verify the custom quest registry includes `DwarfCannonQuest.INSTANCE`.
- If cannonball making appears to do nothing, verify the player is using one of the supported furnace object ids above, not an unrelated furnace-like object.
- If the recovery dialogue refuses to hand back parts, check the player has at least 4 free inventory slots.
- If the quest tab does not turn green after completion, verify `CustomContent.sendQuestTabs(...)` is still being called after quest stage changes.
