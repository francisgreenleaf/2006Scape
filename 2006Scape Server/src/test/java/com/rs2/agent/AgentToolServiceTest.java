package com.rs2.agent;

import com.rs2.game.content.StaticObjectList;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class AgentToolServiceTest {

    @Test
    public void prefersCombatWeaponsOverGatheringToolsOnTies() {
        assertTrue(AgentToolService.weaponPreferenceBonus("Bronze sword")
                > AgentToolService.weaponPreferenceBonus("Bronze axe"));
        assertTrue(AgentToolService.weaponPreferenceBonus("Iron scimitar")
                > AgentToolService.weaponPreferenceBonus("Bronze sword"));
        assertTrue(AgentToolService.weaponPreferenceBonus("Bronze pickaxe") < 0);
    }

    @Test
    public void combatTargetOutsideScanDistanceIsStale() {
        assertFalse(AgentToolService.isStaleCombatTargetDistance(30));
        assertTrue(AgentToolService.isStaleCombatTargetDistance(31));
    }

    @Test
    public void foodToolsRecognizeNormalFishingAndCookingResources() {
        assertTrue(AgentToolService.isNetFishingSpot(316));
        assertFalse(AgentToolService.isNetFishingSpot(309));
        assertTrue(AgentToolService.isCookingObject(2728));
        assertTrue(AgentToolService.isCookingFireObject(StaticObjectList.FIRE));
        assertTrue(AgentToolService.isRawCookableFood(317));
        assertFalse(AgentToolService.isRawCookableFood(315));
        assertTrue(AgentToolService.isFiremakingLog(1511));
        assertFalse(AgentToolService.isFiremakingLog(2132));
    }

    @Test
    public void walkTargetsStayInsideLoadedMapRegion() {
        int[] target = AgentToolService.boundedWalkTarget(3252, 3236, 400, 394, 3252, 3266);

        assertEquals(3252, target[0]);
        assertEquals(3252, target[1]);
    }

    @Test
    public void nearbyWalkTargetsAreLeftAlone() {
        int[] target = AgentToolService.boundedWalkTarget(3252, 3236, 400, 398, 3252, 3245);

        assertEquals(3252, target[0]);
        assertEquals(3245, target[1]);
    }
}
