package com.rs2.game.content.skills.core;

import com.rs2.game.content.StaticItemList;
import com.rs2.game.content.StaticObjectList;
import org.junit.Test;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;

public class MiningTest {

    @Test
    public void exposesMineableRockMetadataForAgentTools() {
        Mining.rockData copper = Mining.rockData.getRock(StaticObjectList.ROCKS_2091);
        assertEquals(Mining.rockData.COPPER, copper);
        assertEquals(1, copper.getRequiredLevel());
        assertEquals(18, copper.getXp());
        assertArrayEquals(new int[] {StaticItemList.COPPER_ORE}, copper.getOreIds());

        Mining.rockData iron = Mining.rockData.getRock(StaticObjectList.ROCKS_2093);
        assertEquals(Mining.rockData.IRON, iron);
        assertEquals(15, iron.getRequiredLevel());
        assertEquals(35, iron.getXp());
        assertArrayEquals(new int[] {StaticItemList.IRON_ORE}, iron.getOreIds());
    }
}
