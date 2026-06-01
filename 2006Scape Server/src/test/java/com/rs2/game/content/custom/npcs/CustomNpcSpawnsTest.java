package com.rs2.game.content.custom.npcs;

import com.rs2.game.content.custom.CustomFeatureFlags;
import com.rs2.game.content.custom.shops.CustomShops;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

public class CustomNpcSpawnsTest {

    @Before
    public void setUp() {
        CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED = false;
    }

    @After
    public void tearDown() {
        CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED = false;
    }

    @Test
    public void catherbyTraderCrewmemberSpawnIsDisabledByDefault() {
        assertEquals(0, CustomNpcSpawns.getSpawns().length);
        assertNull(CustomShops.getShopIdForNpc(CustomShops.CATHERBY_TRADER_CREWMEMBER));
    }

    @Test
    public void catherbyTraderCrewmemberSpawnIsConfiguredForTraderStansShopWhenEnabled() {
        CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED = true;
        CustomNpcSpawns.CustomSpawn[] spawns = CustomNpcSpawns.getSpawns();

        assertEquals(1, spawns.length);
        assertEquals(CustomShops.CATHERBY_TRADER_CREWMEMBER, spawns[0].npcId);
        assertEquals(Integer.valueOf(CustomShops.TRADER_STANS_TRADING_POST),
                CustomShops.getShopIdForNpc(spawns[0].npcId));
        assertEquals(2804, spawns[0].x);
        assertEquals(3422, spawns[0].y);
        assertEquals(0, spawns[0].height);
        assertEquals(1, spawns[0].walkingType);
    }
}
