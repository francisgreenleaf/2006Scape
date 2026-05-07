# Agent Combat Training Log

## 2026-05-06

- Goal: start efficient melee training toward 50 attack, strength, and defence without carrying unnecessary capital.
- Starting combat state observed this session: 30 attack, 30 strength, 30 defence, 29 hitpoints base.
- Bought and equipped an adamant longsword, replacing a mithril longsword.
- Bought and equipped adamant platelegs, replacing steel platelegs.
- Bought 20 kebabs through the normal Al Kharid shop flow.
- Deposited leftover coins and replaced gear, leaving no inventory coins for training.
- Trained on Al-Kharid warriors because they are close to a bank, have 19 hitpoints, and only max hit 3.
- Result: attack reached 31, hitpoints base reached 30, strength and defence remained 30.
- Stopped out of combat at Al Kharid bank with 20 kebabs remaining.

Continuation run:

- Restarted from Al Kharid bank with 31 attack, 30 strength, 30 defence, 30 hitpoints base, 20 kebabs, and 0 inventory coins.
- Continued training on Al-Kharid warriors for the same safety/efficiency balance: 19 hitpoints, max hit 3, and close bank access.
- Detected a stale combat-target state where the player still had an NPC target but was no longer in melee range, causing XP to stop.
- Added a `train_combat` fix so remembered targets are repositioned or reacquired through normal attack mechanics instead of idling.
- Ran a guarded training loop with XP-stall detection, low-HP stopping, and food-count stopping.
- Result: attack reached 34, hitpoints base reached 31, strength and defence remained 30.
- No kebabs were consumed; food stayed at 20 and inventory coins stayed at 0.
- Stopped out of combat at Al Kharid bank.

Future changes to improve efficiency:

- Add first-class route support for toll gates and other obstacle/dialogue gates; Al Kharid required manual dialogue handling.
- Replace the Varrock-to-Al-Kharid reverse route near the cow field; it can oscillate around the fence at `(3252,3267)`.
- Add an Al Kharid bank landmark so restocking and coin deposit do not require raw tile waypoints.
- Add price-aware gear shopping so the planner chooses purchasable upgrades from actual shop stock, not only ideal equipment.
- Add XP/hour and food-used tracking per NPC so target scoring can learn from real kill speed and damage taken.
- Add a proper combat progress watchdog inside the bridge, not only in the external loop, so a lack of XP gain can trigger retargeting.
- Start testing the next target tier from a banked state: Varrock guards are higher HP, but their max hit 6 and route/restock flow need verification.
- Re-test the rock crab route after adding obstacle-aware travel; the first attempt stalled west of Varrock.
