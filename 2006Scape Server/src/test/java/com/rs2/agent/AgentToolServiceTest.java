package com.rs2.agent;

import com.rs2.game.content.StaticObjectList;
import com.rs2.game.objects.Objects;
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

    @Test
    public void objectInteractionTargetsAdjacentTileInsteadOfObjectTile() {
        Objects rock = new Objects(2090, 3296, 3314, 0, 0, 10, 0);

        assertFalse(AgentToolService.isWithinObjectInteractionRange(3294, 3314, rock));

        int[] target = AgentToolService.objectInteractionWalkTarget(3294, 3314, -1, -1, rock);

        assertEquals(3295, target[0]);
        assertEquals(3314, target[1]);
        assertTrue(AgentToolService.isWithinObjectInteractionRange(target[0], target[1], rock));
    }

    @Test
    public void nearbyMineableRockFallbackIsLimitedToVisibleRocks() {
        Objects coal = new Objects(2096, 3302, 3317, 0, 2, 10, 0);
        Objects notRock = new Objects(100, 3302, 3317, 0, 0, 10, 0);

        assertTrue(AgentToolService.isNearbyMineableRock(3304, 3317, coal));
        assertFalse(AgentToolService.isNearbyMineableRock(3305, 3317, coal));
        assertFalse(AgentToolService.isNearbyMineableRock(3304, 3317, notRock));
    }

    @Test
    public void travelRecognizesAlKharidGateCrossingSteps() {
        assertTrue(AgentToolService.isAlKharidGateCrossingStep(3268, 3227, 3252, 3236));
        assertTrue(AgentToolService.isAlKharidGateCrossingStep(3267, 3227, 3274, 3195));
        assertFalse(AgentToolService.isAlKharidGateCrossingStep(3268, 3227, 3274, 3195));
        assertFalse(AgentToolService.isAlKharidGateCrossingStep(3268, 3233, 3252, 3236));
    }
}
