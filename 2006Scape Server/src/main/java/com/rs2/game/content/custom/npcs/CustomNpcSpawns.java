package com.rs2.game.content.custom.npcs;

import com.rs2.game.content.custom.CustomFeatureFlags;
import com.rs2.game.content.custom.shops.CustomShops;
import com.rs2.game.npcs.NpcHandler;

public final class CustomNpcSpawns {

    private static final CustomSpawn[] SPAWNS = {
            new CustomSpawn(CustomShops.CATHERBY_TRADER_CREWMEMBER, 2804, 3422, 0, 1, 0, 0, 0)
    };

    private CustomNpcSpawns() {
    }

    public static void spawnAll(NpcHandler npcHandler) {
        for (CustomSpawn spawn : getSpawns()) {
            npcHandler.newNPC(spawn.npcId, spawn.x, spawn.y, spawn.height, spawn.walkingType,
                    NpcHandler.getNpcListHP(spawn.npcId), spawn.maxHit, spawn.attack, spawn.defence);
        }
    }

    public static CustomSpawn[] getSpawns() {
        if (!CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED) {
            return new CustomSpawn[0];
        }
        return SPAWNS.clone();
    }

    public static final class CustomSpawn {
        public final int npcId;
        public final int x;
        public final int y;
        public final int height;
        public final int walkingType;
        public final int maxHit;
        public final int attack;
        public final int defence;

        private CustomSpawn(int npcId, int x, int y, int height, int walkingType, int maxHit, int attack, int defence) {
            this.npcId = npcId;
            this.x = x;
            this.y = y;
            this.height = height;
            this.walkingType = walkingType;
            this.maxHit = maxHit;
            this.attack = attack;
            this.defence = defence;
        }
    }
}
