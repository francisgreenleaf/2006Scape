package com.rs2.game.content.skills.woodcutting;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class WoodcuttingTest {

    @Test
    public void exposesChoppableTreeMetadataForAgentTools() {
        assertTrue(Woodcutting.isChoppableTree(1276));
        assertEquals("tree", Woodcutting.getTreeResourceName(1276));
        assertEquals(1, Woodcutting.getTreeLevelRequirement(1276));
        assertEquals(1511, Woodcutting.getTreeLogId(1276));

        assertTrue(Woodcutting.isChoppableTree(1281));
        assertEquals("oak", Woodcutting.getTreeResourceName(1281));
        assertEquals(15, Woodcutting.getTreeLevelRequirement(1281));
        assertEquals(1521, Woodcutting.getTreeLogId(1281));
    }
}
