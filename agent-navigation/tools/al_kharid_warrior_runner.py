#!/usr/bin/env python3
"""Bespoke Al Kharid Warrior combat runner."""

import argparse

from combat_trip_lib import (
    BONES,
    COINS,
    HERB_IDS,
    KEBAB,
    LOBSTER,
    RUNE_IDS,
    TUNA,
    USEFUL_STACKABLES,
    add_common_arguments,
    run_enemy,
)


PLAN = {
    "runnerId": "al-kharid-warrior-combat",
    "npcName": "Al-Kharid warrior",
    "npcIds": (18,),
    "bankTarget": "al_kharid_bank",
    "bankBounds": (3264, 3162, 3272, 3171, 0),
    "bankStageTargets": (
        {
            "target": "falador_west_bank",
            "fromBounds": (2750, 3350, 2960, 3525, 0),
            "targetBounds": (2943, 3366, 2950, 3373, 0),
        },
        {
            "target": "lumbridge_castle_courtyard",
            "fromBounds": (2940, 3200, 3105, 3405, 0),
            "targetBounds": (3217, 3214, 3226, 3225, 0),
        },
    ),
    "areaTarget": "3288,3168,0",
    "areaBounds": (3280, 3166, 3304, 3179, 0),
    "targetAttack": 25,
    "targetStrength": 25,
    "targetDefence": 25,
    "foodTarget": 6,
    "foodOrder": (KEBAB, TUNA, LOBSTER),
    "coinFloat": 100,
    "eatAtHitpoints": 10,
    "retreatAtHitpoints": 6,
    "npcMaxDistance": 24,
    "minNpcHitpoints": 1,
    "maxNpcMaxHit": 3,
    "lootItemIds": tuple(sorted(set((COINS,) + RUNE_IDS + HERB_IDS + USEFUL_STACKABLES))),
    "boneItemIds": (BONES,),
    "bankAtLootItems": 12,
    "routeMaxBatches": 90,
    "routeMaxBatchDistance": 48,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Al Kharid Warrior combat trips near the Al Kharid bank.")
    add_common_arguments(parser, PLAN)
    return run_enemy(parser.parse_args(argv), PLAN)


if __name__ == "__main__":
    raise SystemExit(main())
