# Pantry Panic Quest Guide

Agent-facing guide for completing the custom Lumbridge quest `Pantry Panic`.

## Summary

- Start NPC: Hans, NPC id `0`, in or around Lumbridge Castle.
- Main NPC: Cook, NPC id `278`, Lumbridge Castle kitchen at `(3207,3215,0)`.
- Finish NPC: Duke Horacio, NPC id `741`, Lumbridge Castle upper floor at `(3209,3222,1)`.
- Requirements: none.
- Items needed: cabbage `1965`, egg `1944`, bucket of milk `1927`.
- Rewards: 1 Quest Point, 1,154 Cooking XP, 10,000 coins, 50 cooked lobsters.

## Important Coordinates

| Target | Id | Coordinates | Notes |
| --- | ---: | --- | --- |
| Cook | NPC `278` | `(3207,3215,0)` | Ground floor Lumbridge Castle kitchen. |
| Duke Horacio | NPC `741` | `(3209,3222,1)` | Upstairs in Lumbridge Castle. |
| Castle stairs | Object `1738/1739` | `(3204,3207,0/1)` | Use to move between Cook and Duke floors. |
| Egg | Item `1944` | `(3226,3301,0)` or `(3229,3299,0)` | Chicken area north of the Lumbridge cow pen. |
| Empty bucket | Item `1925` | `(3225,3294,0)` | Near the Lumbridge cow/chicken area. |
| Dairy cow | Object `8689` | `(3252,3275,0)` or `(3254,3272,0)` | Click it with an empty bucket, or use bucket on it. |
| Cabbage source | Object `357` | `(3211,3209,1)` | Reliable castle crate after speaking to the Cook. |
| Cabbage source | Object `365` | `(3205,3218,2)` or `(3205,3222,2)` | Castle sacks after speaking to the Cook. |
| Cabbage source | Object `355` | `(3209,3243,0)` | Ground-floor Lumbridge container option. |

Hans is defined as NPC id `0`, but the static spawn file may not contain a fixed Hans tile. Use `find_nearest_npc` by name or id around Lumbridge Castle ground floor and courtyard. If no Hans exists in the live world, stop and report `missing Hans spawn for Pantry Panic`; do not substitute a generic man or woman.

## Walkthrough

1. Find Hans in or around Lumbridge Castle and talk to him.
   - Accept the quest option: `I'll help save the supper.`
   - Quest stage becomes `SPEAK_TO_COOK`.

2. Go to the Cook in the castle kitchen at `(3207,3215,0)` and talk to him.
   - He asks for a cabbage, an egg, and a bucket of milk.
   - Quest stage becomes `SEARCH_PANTRY`.

3. Get the egg.
   - Walk to the Lumbridge chicken area north of the cow pen.
   - Pick up egg `1944` at `(3226,3301,0)` or `(3229,3299,0)`.

4. Get the bucket of milk.
   - Pick up empty bucket `1925` at `(3225,3294,0)`.
   - Go to a dairy cow object `8689` at `(3252,3275,0)` or `(3254,3272,0)`.
   - Click the dairy cow, or use the empty bucket on the dairy cow.
   - Wait for the milking action to finish; the bucket becomes bucket of milk `1927`.
   - Do not use an ordinary cow NPC. Milking is handled by dairy cow objects.

5. Get the cabbage.
   - This only works after the Cook has asked for ingredients.
   - Search any accepted pantry/container object inside the Lumbridge boundary.
   - Good castle targets are crate `357` at `(3211,3209,1)` or sacks `365` at `(3205,3218,2)` / `(3205,3222,2)`.
   - The object click adds cabbage `1965` to the inventory or drops it if the inventory is full.

6. Return to the Cook at `(3207,3215,0)`.
   - Have cabbage `1965`, egg `1944`, and bucket of milk `1927` in inventory.
   - Click the Cook. If item-on-NPC is available, using any ingredient on the Cook also starts the hand-in.
   - The Cook consumes all three ingredients and sends you to Duke Horacio.
   - Quest stage becomes `REPORT_TO_DUKE`.

7. Go upstairs and talk to Duke Horacio at `(3209,3222,1)`.
   - Continue the dialogue until the quest reward screen appears.
   - Quest stage becomes `COMPLETE`.

## Useful Agent Tool Pattern

- Use `rs.find_nearest_npc` and `rs.interact_npc` for Hans, the Cook, and Duke Horacio.
- Use `rs.walk_to_tile_until_arrived` for the fixed coordinates above when route landmarks are unavailable.
- Use `rs.pickup_ground_item` for egg `1944` and empty bucket `1925`.
- Use `rs.find_nearest_object`, `rs.interact_object`, or `rs.use_item_on_object` for dairy cow `8689` and the cabbage container object.
- Use `rs.continue_dialogue` and `rs.select_dialogue_option` until each dialogue closes.

## Troubleshooting

- If the Cook talks about his normal Cook's Assistant quest, Pantry Panic has not been started with Hans yet.
- If a cabbage container does nothing, verify the quest stage is `SEARCH_PANTRY` or `RETURN_TO_COOK` and the object id is one of `354`, `355`, `356`, `357`, `358`, `365`, or `1013`.
- If milking fails, verify the player has empty bucket `1925` and is using dairy cow object `8689`, not cow NPC `81`.
- If the Cook refuses the hand-in, re-check all three inventory items: cabbage `1965`, egg `1944`, bucket of milk `1927`.
- If the reward inventory is full, coins stack but cooked lobsters may be dropped under the player by `addOrDropItem`.
