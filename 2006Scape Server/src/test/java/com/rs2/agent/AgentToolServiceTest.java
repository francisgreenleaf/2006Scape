package com.rs2.agent;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
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
        assertEquals(28, AgentToolService.cookingAmountForButton(53149));
        assertEquals(0, AgentToolService.cookingAmountForButton(12345));
    }

    @Test
    public void bonePrimitiveRecognizesBuryableBones() {
        assertTrue(AgentToolService.isBuryableBone(526));
        assertTrue(AgentToolService.isBuryableBone(532));
        assertFalse(AgentToolService.isBuryableBone(379));
    }

    @Test
    public void interfaceItemPrimitiveAllowsNormalSmithingSelectionWidgets() {
        assertTrue(AgentToolService.isSmithingSelectionInterface(1119));
        assertTrue(AgentToolService.isSmithingSelectionInterface(1123));
        assertFalse(AgentToolService.isSmithingSelectionInterface(3900));
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
    public void explicitWalkStepsMustBeCardinalAndAdjacent() {
        assertTrue(AgentToolService.isAdjacentCardinalStep(3253, 3266, 3252, 3266));
        assertTrue(AgentToolService.isAdjacentCardinalStep(3253, 3266, 3253, 3267));
        assertFalse(AgentToolService.isAdjacentCardinalStep(3253, 3266, 3252, 3267));
        assertFalse(AgentToolService.isAdjacentCardinalStep(3253, 3266, 3251, 3266));
        assertFalse(AgentToolService.isAdjacentCardinalStep(3253, 3266, 3253, 3266));
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

    @Test
    public void xsToolNamesMapToBaseToolNames() {
        assertTrue(AgentToolService.isXsTool("observe_state_XS"));
        assertFalse(AgentToolService.isXsTool("observe_state_XXS"));
        assertTrue(AgentToolService.isXxsTool("observe_state_XXS"));
        assertTrue(AgentToolService.isCompactTool("observe_state_XXS"));
        assertFalse(AgentToolService.isXsTool("observe_state"));
        assertEquals("observe_state", AgentToolService.baseToolName("observe_state_XS"));
        assertEquals("observe_state", AgentToolService.baseToolName("observe_state_XXS"));
        assertEquals("bury_bones", AgentToolService.baseToolName("bury_bones_XXS"));
        assertEquals("deposit_inventory_items", AgentToolService.baseToolName("deposit_inventory_items"));
    }

    @Test
    public void xsCompactorKeepsDecisionFieldsAndDropsFullStateShape() {
        JsonObject result = AgentToolService.success("Observed current game state.");
        JsonObject player = new JsonObject();
        player.addProperty("name", "mrflame");
        player.addProperty("x", 2814);
        player.addProperty("y", 3440);
        player.addProperty("height", 0);
        player.addProperty("hitpoints", 20);
        player.addProperty("maxHitpoints", 20);
        player.addProperty("freeInventorySlots", 26);
        player.addProperty("runEnergy", 31);
        player.addProperty("runEnabled", false);
        player.addProperty("inBankArea", true);
        JsonObject skills = new JsonObject();
        JsonObject cooking = new JsonObject();
        cooking.addProperty("level", 43);
        cooking.addProperty("xp", 52520);
        cooking.addProperty("baseLevel", 43);
        skills.add("cooking", cooking);
        JsonObject prayer = new JsonObject();
        prayer.addProperty("level", 1);
        prayer.addProperty("currentLevel", 1);
        prayer.addProperty("xp", 720);
        prayer.addProperty("baseLevel", 7);
        prayer.addProperty("points", 1);
        skills.add("prayer", prayer);
        player.add("skills", skills);
        JsonArray inventory = new JsonArray();
        JsonObject lobster = new JsonObject();
        lobster.addProperty("slot", 0);
        lobster.addProperty("id", 379);
        lobster.addProperty("amount", 2);
        lobster.addProperty("name", "Lobster");
        lobster.addProperty("foodHeal", 12);
        inventory.add(lobster);
        player.add("inventory", inventory);
        player.add("equipment", new JsonArray());
        JsonArray bank = new JsonArray();
        JsonObject coins = new JsonObject();
        coins.addProperty("slot", 0);
        coins.addProperty("id", 995);
        coins.addProperty("amount", 100);
        coins.addProperty("name", "Coins");
        bank.add(coins);
        player.add("bank", bank);
        result.add("player", player);
        JsonArray skillChanges = new JsonArray();
        JsonObject prayerChange = new JsonObject();
        prayerChange.addProperty("skill", "prayer");
        prayerChange.addProperty("xpGained", 5);
        prayerChange.addProperty("xpBefore", 715);
        prayerChange.addProperty("xpAfter", 720);
        prayerChange.addProperty("currentBefore", 1);
        prayerChange.addProperty("currentAfter", 1);
        prayerChange.addProperty("baseBefore", 7);
        prayerChange.addProperty("baseAfter", 7);
        prayerChange.addProperty("pointsBefore", 1);
        prayerChange.addProperty("pointsAfter", 1);
        skillChanges.add(prayerChange);
        result.add("skillChanges", skillChanges);
        JsonArray xpRecent = new JsonArray();
        JsonObject recentPrayer = new JsonObject();
        recentPrayer.addProperty("skill", "prayer");
        recentPrayer.addProperty("xpGained", 5);
        recentPrayer.addProperty("xp", 720);
        recentPrayer.addProperty("base", 7);
        recentPrayer.addProperty("points", 1);
        xpRecent.add(recentPrayer);
        result.add("xpRecent", xpRecent);
        result.addProperty("buried", 1);

        JsonObject compact = AgentToolService.compactXsResult("observe_state", result);

        assertTrue(compact.get("success").getAsBoolean());
        assertTrue(compact.get("compact").getAsBoolean());
        assertEquals("observe_state_XS", compact.get("tool").getAsString());
        assertEquals("2814,3440,0", compact.getAsJsonObject("player").get("tile").getAsString());
        assertEquals(2, compact.getAsJsonObject("inventory").get("food").getAsInt());
        assertEquals(100, compact.getAsJsonObject("bank").get("coins").getAsInt());
        assertFalse(compact.getAsJsonObject("player").has("inventory"));
        assertTrue(compact.getAsJsonObject("player").getAsJsonObject("skills").has("cooking"));
        JsonObject compactPrayer = compact.getAsJsonObject("player").getAsJsonObject("skills").getAsJsonObject("prayer");
        assertEquals(1, compactPrayer.get("points").getAsInt());
        assertEquals(7, compactPrayer.get("base").getAsInt());
        assertEquals(1, compact.get("buried").getAsInt());
        assertEquals("prayer", compact.getAsJsonArray("skillChanges").get(0).getAsJsonObject()
                .get("skill").getAsString());
        assertEquals(5, compact.getAsJsonArray("xpRecent").get(0).getAsJsonObject()
                .get("xpGained").getAsInt());
    }

    @Test
    public void xxsCompactorKeepsOnlyConfirmationCriticalPlayerAndXp() {
        JsonObject result = AgentToolService.success("Buried Bones.");
        result.addProperty("buried", 1);
        result.addProperty("itemCountAfter", 0);

        JsonObject player = new JsonObject();
        player.addProperty("name", "mrflame");
        player.addProperty("x", 3222);
        player.addProperty("y", 3218);
        player.addProperty("height", 0);
        player.addProperty("hitpoints", 8);
        player.addProperty("maxHitpoints", 10);
        player.addProperty("isInCombat", true);
        player.addProperty("isPoisoned", true);
        player.addProperty("isDead", false);
        player.addProperty("freeInventorySlots", 4);
        JsonArray inventory = new JsonArray();
        JsonObject food = new JsonObject();
        food.addProperty("id", 379);
        food.addProperty("name", "Lobster");
        food.addProperty("amount", 2);
        food.addProperty("foodHeal", 12);
        inventory.add(food);
        player.add("inventory", inventory);
        result.add("player", player);
        result.add("inventory", new JsonObject());
        result.add("skills", new JsonObject());

        JsonArray skillChanges = new JsonArray();
        JsonObject prayerChange = new JsonObject();
        prayerChange.addProperty("skill", "prayer");
        prayerChange.addProperty("xpGained", 5);
        prayerChange.addProperty("xpAfter", 720);
        prayerChange.addProperty("currentAfter", 1);
        prayerChange.addProperty("baseAfter", 7);
        prayerChange.addProperty("pointsAfter", 1);
        skillChanges.add(prayerChange);
        result.add("skillChanges", skillChanges);

        JsonObject compact = AgentToolService.compactXxsResult("bury_bones", result, null);

        assertTrue(compact.get("success").getAsBoolean());
        assertTrue(compact.get("xxs").getAsBoolean());
        assertEquals("bury_bones_XXS", compact.get("tool").getAsString());
        assertEquals(1, compact.get("buried").getAsInt());
        assertEquals(0, compact.get("itemCountAfter").getAsInt());
        assertEquals("3222,3218,0", compact.getAsJsonObject("player").get("tile").getAsString());
        assertEquals(8, compact.getAsJsonObject("player").get("hp").getAsInt());
        assertTrue(compact.getAsJsonObject("player").get("isInCombat").getAsBoolean());
        assertTrue(compact.getAsJsonObject("player").get("isPoisoned").getAsBoolean());
        assertEquals(2, compact.getAsJsonObject("player").get("food").getAsInt());
        assertEquals("prayer", compact.getAsJsonArray("xp").get(0).getAsJsonObject().get("skill").getAsString());
        assertEquals(5, compact.getAsJsonArray("xp").get(0).getAsJsonObject().get("gained").getAsInt());
        assertFalse(compact.has("inventory"));
        assertFalse(compact.has("skills"));
        assertFalse(compact.getAsJsonObject("player").has("inventory"));
    }
}
