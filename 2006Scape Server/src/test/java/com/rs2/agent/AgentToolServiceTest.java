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
    public void observedCombatIgnoresStaleKillingTargetOnlySignals() {
        assertTrue(AgentToolService.isObservedCombatSignalActive(true, false, 200));
        assertTrue(AgentToolService.isObservedCombatSignalActive(false, true, 30));
        assertFalse(AgentToolService.isObservedCombatSignalActive(false, true, 31));
        assertFalse(AgentToolService.isObservedCombatSignalActive(false, false, 0));
    }

    @Test
    public void distantTrainingNpcDoesNotInterruptAreaTravel() {
        assertTrue(AgentToolService.shouldReachTrainingAreaBeforeCombat(
                2974, 3369, 0, "falador white knights", 29));
        assertFalse(AgentToolService.shouldReachTrainingAreaBeforeCombat(
                2977, 3343, 0, "falador white knights", 29));
        assertFalse(AgentToolService.shouldReachTrainingAreaBeforeCombat(
                2974, 3369, 0, "falador white knights", 8));
    }

    @Test
    public void combatReacquireDoesNotResetAlreadyTargetedNpc() {
        assertFalse(AgentToolService.shouldReacquireUnclaimedCombatTarget(true, false, 0, 1, 0));
        assertFalse(AgentToolService.shouldReacquireUnclaimedCombatTarget(false, true, 0, 1, 0));
        assertFalse(AgentToolService.shouldReacquireUnclaimedCombatTarget(false, false, 1, 1, 0));
        assertFalse(AgentToolService.shouldReacquireUnclaimedCombatTarget(false, false, 0, 1, 2));
        assertTrue(AgentToolService.shouldReacquireUnclaimedCombatTarget(false, false, 0, 1, 0));
    }

    @Test
    public void plannedTrainingTargetRejectsRouteDistractions() {
        assertTrue(AgentToolService.matchesPlannedTrainingTarget("Rock Crab", "Rock Crab"));
        assertTrue(AgentToolService.matchesPlannedTrainingTarget("White Knight", "White Knight"));
        assertTrue(AgentToolService.matchesPlannedTrainingTarget("Guard", "Guard"));
        assertFalse(AgentToolService.matchesPlannedTrainingTarget("Bear", "Rock Crab"));
        assertFalse(AgentToolService.matchesPlannedTrainingTarget("Black Knight", "Rock Crab"));
        assertFalse(AgentToolService.matchesPlannedTrainingTarget("Fortress Guard", "Guard"));
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
    public void fletchingPlannerChoosesBestUnlockedProductForLogs() {
        assertEquals(52, AgentToolService.bestFletchingChoiceForLog(1, 1511, "").productId);
        assertEquals(48, AgentToolService.bestFletchingChoiceForLog(10, 1511, "").productId);
        assertEquals(56, AgentToolService.bestFletchingChoiceForLog(25, 1521, "").productId);
        assertEquals(58, AgentToolService.bestFletchingChoiceForLog(40, 1519, "").productId);
        assertEquals(64, AgentToolService.bestFletchingChoiceForLog(50, 1517, "").productId);
    }

    @Test
    public void fletchingSaleCategoryRecognizesBowProductsButNotLogs() {
        assertTrue(AgentToolService.isFletchingProductItem(52));
        assertTrue(AgentToolService.isFletchingProductItem(56));
        assertFalse(AgentToolService.isFletchingProductItem(1511));
        assertFalse(AgentToolService.isFletchingProductItem(946));
    }

    @Test
    public void walkTargetsStayInsideLoadedMapRegion() {
        int[] target = AgentToolService.boundedWalkTarget(3252, 3236, 400, 394, 3252, 3266);

        assertEquals(3252, target[0]);
        assertEquals(3253, target[1]);
    }

    @Test
    public void walkTargetsCanUseSmallerRequestedChunks() {
        int[] target = AgentToolService.boundedWalkTarget(3252, 3236, 400, 394, 3252, 3266, 16);

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
    public void miningToolWaitsAfterClickBeforeReclicking() {
        assertTrue(AgentToolService.shouldWaitAfterMiningClick(1_000L, 1_500L, false, false));
        assertFalse(AgentToolService.shouldWaitAfterMiningClick(1_600L, 1_500L, false, false));
        assertFalse(AgentToolService.shouldWaitAfterMiningClick(1_000L, 1_500L, true, false));
        assertFalse(AgentToolService.shouldWaitAfterMiningClick(1_000L, 1_500L, false, true));
        assertEquals(3, AgentToolService.miningCooldownTicks());
    }

    @Test
    public void miningToolWaitsLocallyInsteadOfSwitchingDistantClusters() {
        assertTrue(AgentToolService.shouldWaitLocallyForMiningRespawn(true, false));
        assertFalse(AgentToolService.shouldWaitLocallyForMiningRespawn(true, true));
        assertFalse(AgentToolService.shouldWaitLocallyForMiningRespawn(false, false));
    }

    @Test
    public void queuedMovementIgnoresNoOpCurrentTileSteps() {
        int[] queueX = new int[] {42, 42, 41, 0};
        int[] queueY = new int[] {17, 17, 17, 0};

        assertFalse(AgentToolService.hasQueuedMovementAwayFromCurrent(42, 17, 0, 2, 4, queueX, queueY));
        assertTrue(AgentToolService.hasQueuedMovementAwayFromCurrent(42, 17, 0, 3, 4, queueX, queueY));
    }

    @Test
    public void bankWithdrawalsIgnoreRetainedEmptySlots() {
        assertFalse(AgentToolService.hasPositiveStoredItem(2352, 0));
        assertFalse(AgentToolService.hasPositiveStoredItem(0, 3));
        assertTrue(AgentToolService.hasPositiveStoredItem(2352, 2));
    }

    @Test
    public void travelRecognizesAlKharidGateCrossingSteps() {
        assertTrue(AgentToolService.isAlKharidGateCrossingStep(3268, 3227, 3252, 3236));
        assertTrue(AgentToolService.isAlKharidGateCrossingStep(3267, 3227, 3274, 3195));
        assertFalse(AgentToolService.isAlKharidGateCrossingStep(3268, 3227, 3274, 3195));
        assertFalse(AgentToolService.isAlKharidGateCrossingStep(3268, 3233, 3252, 3236));
    }
}
