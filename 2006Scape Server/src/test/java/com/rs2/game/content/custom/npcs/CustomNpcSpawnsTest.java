package com.rs2.game.content.custom.npcs;

import com.rs2.game.content.custom.shops.CustomShops;
import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class CustomNpcSpawnsTest {

    @Test
    public void catherbyTraderCrewmemberSpawnIsConfiguredForTraderStansShop() {
        CustomNpcSpawns.CustomSpawn[] spawns = CustomNpcSpawns.getSpawns();

        assertEquals(1, spawns.length);
        assertEquals(CustomShops.CATHERBY_TRADER_CREWMEMBER, spawns[0].npcId);
        assertEquals(Integer.valueOf(CustomShops.TRADER_STANS_TRADING_POST),
                CustomShops.getShopIdForNpc(spawns[0].npcId));
        assertEquals(2792, spawns[0].x);
        assertEquals(3415, spawns[0].y);
        assertEquals(0, spawns[0].height);
        assertEquals(1, spawns[0].walkingType);
    }
}
