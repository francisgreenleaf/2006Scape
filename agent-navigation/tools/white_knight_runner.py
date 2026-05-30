#!/usr/bin/env python3
"""Bespoke Falador White Knight combat runner."""

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


WHITE_KNIGHT_SELLABLE_LOOT = tuple(sorted(set(
    (COINS, 1293, 1281, 888, 890, 1141, 2351) + HERB_IDS + RUNE_IDS + SEED_IDS
)))


PLAN = {
    "runnerId": "white-knight-combat",
    "npcName": "White Knight",
    "npcIds": (3348, 3349, 3350, 19, 1092),
    "bankTarget": "2947,3368,0",
    "bankBounds": (2946, 3367, 2948, 3370, 0),
    "areaTarget": "2966,3341,0",
    "areaBounds": (2958, 3329, 2991, 3349, 0),
    "targetBounds": (2965, 3340, 2978, 3348, 0),
    "forceReachableTargetScan": True,
    "targetAttack": 70,
    "targetStrength": 70,
    "targetDefence": 70,
    "foodTarget": 1,
    "foodOrder": (LOBSTER, SWORDFISH, TUNA),
    "coinFloat": 0,
    "eatAtHitpoints": 13,
    "retreatAtHitpoints": 8,
    "npcMaxDistance": 28,
    "minNpcHitpoints": 20,
    "maxNpcMaxHit": 12,
    "lootItemIds": WHITE_KNIGHT_SELLABLE_LOOT,
    "alwaysLootItemIds": WHITE_KNIGHT_SELLABLE_LOOT,
    "boneItemIds": (BONES,),
    "bankAtLootItems": 9999,
    "bankWhenFreeSlotsAtOrBelow": 0,
    "routeMaxBatches": 90,
    "routeMaxBatchDistance": 48,
    "fastLocalLoop": True,
    "fastLocalTargetMaxDistance": 12,
    "preferNearestTarget": True,
    "attackNextAfterCleanup": True,
    "skipAreaReadyObserve": True,
    "deferNonBoneLootAfterKills": True,
    "immediateLootFreeSlotsAtOrBelow": 2,
    "eligibleIdleLogSeconds": 8,
    "lootSweepRounds": 4,
    "attackAttempts": 2,
    "fightPollTicks": 10,
    "fightPollAttempts": 200,
    "cleanupMaxTicks": 10,
    "nonBoneCleanupMaxTicks": 4,
    "postTargetDeathWaitTicks": 0,
    "stopOnXpGain": False,
    "staleCombatNoXpPolls": 2,
    "bankOnStaleCombat": False,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run White Knight combat trips from Falador bank.")
    add_common_arguments(parser, PLAN)
    return run_enemy(parser.parse_args(argv), PLAN)


if __name__ == "__main__":
    raise SystemExit(main())
