#!/usr/bin/env python3
"""Bespoke Edgeville dungeon Chaos Druid combat runner."""

import argparse

from combat_trip_lib import (
    BONES,
    COINS,
    HERB_IDS,
    LOBSTER,
    RUNE_IDS,
    SEED_IDS,
    SWORDFISH,
    TUNA,
    add_common_arguments,
    run_enemy,
)


PLAN = {
    "runnerId": "chaos-druid-combat",
    "npcName": "Chaos druid",
    "npcIds": (181,),
    "bankTarget": "edgeville_bank",
    "bankBounds": (3089, 3488, 3098, 3499, 0),
    "dungeonTransition": "edgeville_trapdoor",
    "areaTransition": "edgeville_druid_gates",
    "disableAutoRetaliate": True,
    "areaTarget": "3111,9934,0",
    "areaBounds": (3103, 9924, 3119, 9946, 0),
    "areaWaypoints": ("3103,9915,0",),
    "areaWaypointMaxTicks": 90,
    "areaWaypointMaxDistance": 48,
    "targetAttack": 35,
    "targetStrength": 35,
    "targetDefence": 35,
    "foodTarget": 6,
    "foodOrder": (TUNA, LOBSTER, SWORDFISH),
    "coinFloat": 0,
    "eatAtHitpoints": 12,
    "retreatAtHitpoints": 7,
    "npcMaxDistance": 24,
    "minNpcHitpoints": 1,
    "maxNpcMaxHit": 3,
    "alwaysLootItemIds": tuple(sorted(set((COINS,) + HERB_IDS + RUNE_IDS))),
    "valuableSolidItemIds": (),
    "solidLootShopThreshold": 100,
    "solidLootShopValues": {
        227: 1,
        538: 30,
        540: 30,
        1137: 64,
        1291: 24,
        1454: 1,
        1594: 1,
        1627: 19,
    },
    "lootItemIds": tuple(sorted(set((COINS,) + HERB_IDS + RUNE_IDS))),
    "boneItemIds": (BONES,),
    "buryBoneLoot": True,
    "bankAtLootItems": 9999,
    "bankWhenFreeSlotsAtOrBelow": 0,
    "fightPollTicks": 28,
    "fightPollAttempts": 20,
    "routeMaxBatches": 100,
    "routeMaxBatchDistance": 48,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Chaos Druid combat trips from Edgeville bank.")
    add_common_arguments(parser, PLAN)
    return run_enemy(parser.parse_args(argv), PLAN)


if __name__ == "__main__":
    raise SystemExit(main())
