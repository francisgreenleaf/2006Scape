package com.rs2.agent;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.game.content.StaticObjectList;
import com.rs2.game.objects.Objects;
import com.rs2.game.players.Client;
import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import com.rs2.util.Misc;
import com.rs2.util.Stream;
import org.apollo.cache.def.ItemDefinition;
import org.apollo.util.security.IsaacRandom;
import org.junit.BeforeClass;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class AgentToolServiceTest {

    @BeforeClass
    public static void initialiseItemDefinitions() {
        if (ItemDefinition.getDefinitions() != null) {
            return;
        }
        ItemDefinition[] definitions = new ItemDefinition[10000];
        for (int id = 0; id < definitions.length; id++) {
            definitions[id] = new ItemDefinition(id);
            definitions[id].setName("item-" + id);
        }
        definitions[995].setStackable(true);
        ItemDefinition.init(definitions);
    }

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
    public void ardougneSpellButtonStartsTeleportAndConsumesRunes() {
        Player player = readySpellTeleportPlayer(20, "MrMage", 60);
        addInventoryItem(player, 563, 2);
        addInventoryItem(player, 555, 2);
        JsonObject arguments = new JsonObject();
        arguments.addProperty("buttonId", 6004);

        JsonObject result = AgentToolService.handle(player, "click_interface_button", arguments);

        assertTrue(result.get("success").getAsBoolean());
        assertTrue(result.get("teleportStarted").getAsBoolean());
        assertTrue(result.get("actionVerified").getAsBoolean());
        assertEquals("started", result.get("teleportStatus").getAsString());
        assertEquals("MagicTeleports.handleSpellTeleport", result.get("handler").getAsString());
        assertEquals(2662, player.teleX);
        assertEquals(3304, player.teleY);
        assertTrue(player.teleTimer > 0);
        assertEquals(0, inventoryCount(player, 563));
        assertEquals(0, inventoryCount(player, 555));

        JsonObject compact = AgentToolService.compactXsResult("click_interface_button", result, player, arguments);
        assertTrue(compact.get("teleportStarted").getAsBoolean());
        assertEquals("started", compact.get("teleportStatus").getAsString());
        assertEquals("2662,3304,0", compact.get("destination").getAsString());
    }

    @Test
    public void camelotSpellButtonReportsMissingRunesWithoutStarting() {
        Player player = readySpellTeleportPlayer(21, "MrMage", 60);
        JsonObject arguments = new JsonObject();
        arguments.addProperty("buttonId", 4150);

        JsonObject result = AgentToolService.handle(player, "click_interface_button", arguments);

        assertFalse(result.get("success").getAsBoolean());
        assertFalse(result.get("teleportStarted").getAsBoolean());
        assertFalse(result.get("actionVerified").getAsBoolean());
        assertEquals("missing_runes", result.get("teleportStatus").getAsString());
        assertEquals(0, player.teleTimer);
    }

    @Test
    public void spellTeleportReportsLevelAndWildernessRejections() {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("buttonId", 4150);
        Player lowMagic = readySpellTeleportPlayer(24, "MrLowMagic", 44);

        JsonObject levelResult = AgentToolService.handle(lowMagic, "click_interface_button", arguments);

        assertFalse(levelResult.get("success").getAsBoolean());
        assertEquals("level_too_low", levelResult.get("teleportStatus").getAsString());

        Player wilderness = readySpellTeleportPlayer(25, "MrWild", 60);
        wilderness.wildLevel = 21;

        JsonObject wildernessResult = AgentToolService.handle(wilderness, "click_interface_button", arguments);

        assertFalse(wildernessResult.get("success").getAsBoolean());
        assertEquals("wilderness_blocked", wildernessResult.get("teleportStatus").getAsString());
    }

    @Test
    public void rejectedSpellTeleportDoesNotConsumeRunes() {
        Player player = testPlayer(22, "MrMage");
        player.playerLevel[Constants.MAGIC] = 60;
        player.respawnTimer = -6;
        player.randomEventsEnabled = false;
        addInventoryItem(player, 563, 2);
        addInventoryItem(player, 555, 2);
        JsonObject arguments = new JsonObject();
        arguments.addProperty("buttonId", 6004);

        JsonObject result = AgentToolService.handle(player, "click_interface_button", arguments);

        assertFalse(result.get("success").getAsBoolean());
        assertEquals("gameplay_rejected", result.get("teleportStatus").getAsString());
        assertEquals(2, inventoryCount(player, 563));
        assertEquals(2, inventoryCount(player, 555));
        assertEquals(0, player.teleTimer);
    }

    @Test
    public void genericInterfaceButtonDoesNotClaimGameplayCompletion() {
        Player player = testPlayer(23, "MrButton");
        JsonObject arguments = new JsonObject();
        arguments.addProperty("buttonId", 99999);

        JsonObject result = AgentToolService.handle(player, "click_interface_button", arguments);

        assertTrue(result.get("success").getAsBoolean());
        assertFalse(result.get("actionVerified").getAsBoolean());
        assertTrue(result.get("message").getAsString().contains("not verified"));
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
    public void brimhavenDirectObjectDispatchAllowsOnlyNearbyArenaObstacles() {
        Player player = testPlayer(10, "MrAthlete");
        player.absX = 2809;
        player.absY = 9562;
        player.heightLevel = 3;

        assertTrue(AgentToolService.isBrimhavenArenaDirectObject(player, 3565, 2805, 9562));
        player.absX = 2800;
        player.absY = 9562;
        assertTrue(AgentToolService.isBrimhavenArenaDirectObject(player, 3565, 2805, 9562));

        player.absX = 2799;
        player.absY = 9562;
        assertFalse(AgentToolService.isBrimhavenArenaDirectObject(player, 3565, 2805, 9562));

        player.absX = 2783;
        player.absY = 9568;
        assertTrue(AgentToolService.isBrimhavenArenaDirectObject(player, 3581, 2783, 9568));

        player.absX = 2761;
        player.absY = 9546;
        assertTrue(AgentToolService.isBrimhavenArenaDirectObject(player, 3608, 2761, 9546));

        player.absX = 2809;
        player.absY = 9562;
        assertFalse(AgentToolService.isBrimhavenArenaDirectObject(player, 3581, 2794, 9568));
        assertFalse(AgentToolService.isBrimhavenArenaDirectObject(player, 3608, 2805, 9590));
        assertFalse(AgentToolService.isBrimhavenArenaDirectObject(player, 3565, 2805, 9562 + 40));
    }

    @Test
    public void brimhavenDirectObjectDispatchRequiresArenaHeightAndBounds() {
        Player player = testPlayer(11, "MrAthlete");
        player.absX = 2809;
        player.absY = 9562;
        player.heightLevel = 0;

        assertFalse(AgentToolService.isBrimhavenArenaDirectObject(player, 3565, 2805, 9562));

        player.heightLevel = 3;
        player.absX = 2811;
        player.absY = 9562;

        assertFalse(AgentToolService.isBrimhavenArenaDirectObject(player, 3565, 2809, 9562));
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
    public void miningCooldownKeysAreScopedPerPlayer() {
        Player flame = testPlayer(4, "MrFlame");
        Player gem = testPlayer(4, "MrGem");

        assertEquals("mrflame:4", AgentToolService.miningCooldownKey(flame));
        assertEquals("mrgem:4", AgentToolService.miningCooldownKey(gem));
        assertFalse(AgentToolService.miningCooldownKey(flame).equals(AgentToolService.miningCooldownKey(gem)));
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
    public void depositKeepingZeroFoodDepositsEveryNonStackableFoodItem() {
        Player player = testPlayer(7, "Mrfish");
        player.absX = 2814;
        player.absY = 3439;
        player.heightLevel = 0;
        player.playerItems[0] = 996;
        player.playerItemsN[0] = 33;
        player.playerItems[1] = 304;
        player.playerItemsN[1] = 1;
        for (int slot = 2; slot < 17; slot++) {
            player.playerItems[slot] = 316;
            player.playerItemsN[slot] = 1;
        }

        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        itemIds.add(315);
        arguments.add("itemIds", itemIds);
        arguments.addProperty("keepFoodCount", 0);

        JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", arguments);

        assertTrue(result.get("success").getAsBoolean());
        assertEquals(15, result.get("depositedAmount").getAsInt());
        assertEquals(0, inventoryCount(player, 315));
        assertEquals(15, bankCount(player, 315));
    }

    @Test
    public void bankItemCountXsCountsSpecificBankItemsWithoutFullObserve() {
        ItemDefinition.lookup(440).setName("Iron ore");
        ItemDefinition.lookup(453).setName("Coal");
        Player player = testPlayer(8, "MrBank");
        player.bankItems[0] = 441;
        player.bankItemsN[0] = 8568;
        player.bankItems[1] = 454;
        player.bankItemsN[1] = 289;
        player.playerItems[0] = 454;
        player.playerItemsN[0] = 2;
        player.playerEquipment[0] = 440;
        player.playerEquipmentN[0] = 0;

        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        itemIds.add(440);
        arguments.add("itemIds", itemIds);
        JsonArray names = new JsonArray();
        names.add("coal");
        names.add("definitely missing");
        arguments.add("names", names);

        JsonObject result = AgentToolService.handle(player, "bank_item_count", arguments);

        assertTrue(result.get("success").getAsBoolean());
        assertTrue(result.get("compact").getAsBoolean());
        assertEquals("bank_item_count_XS", result.get("tool").getAsString());
        assertEquals("Iron ore: 8568, Coal: 289", result.get("summary").getAsString());
        JsonArray items = result.getAsJsonArray("items");
        assertEquals(2, items.size());
        JsonObject iron = items.get(0).getAsJsonObject();
        assertEquals(440, iron.get("itemId").getAsInt());
        assertEquals("Iron ore", iron.get("canonicalName").getAsString());
        assertEquals(8568, iron.get("bankAmount").getAsInt());
        assertEquals(0, iron.get("inventoryAmount").getAsInt());
        assertEquals(1, iron.get("equipmentAmount").getAsInt());
        JsonObject coal = items.get(1).getAsJsonObject();
        assertEquals(453, coal.get("itemId").getAsInt());
        assertEquals(289, coal.get("bankAmount").getAsInt());
        assertEquals(2, coal.get("inventoryAmount").getAsInt());
        assertTrue(result.has("missing"));
        assertFalse(result.has("bank"));
        assertEquals(8, result.getAsJsonObject("player").get("playerId").getAsInt());
        assertEquals("MrBank", result.getAsJsonObject("player").get("name").getAsString());
    }

    @Test
    public void withdrawBankItemsSupportsMixedQuantitiesInOneCall() {
        Player player = testPlayer(9, "MrSteel");
        player.absX = 3270;
        player.absY = 3167;
        player.heightLevel = 0;
        player.bankItems[0] = 441;
        player.bankItemsN[0] = 100;
        player.bankItems[1] = 454;
        player.bankItemsN[1] = 200;

        JsonObject arguments = new JsonObject();
        JsonArray items = new JsonArray();
        JsonObject iron = new JsonObject();
        iron.addProperty("itemId", 440);
        iron.addProperty("amount", 9);
        items.add(iron);
        JsonObject coal = new JsonObject();
        coal.addProperty("itemId", 453);
        coal.addProperty("amount", 18);
        items.add(coal);
        arguments.add("items", items);

        JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", arguments);

        assertTrue(result.get("success").getAsBoolean());
        assertEquals(2, result.get("withdrawn").getAsInt());
        assertEquals(27, result.get("withdrawnAmount").getAsInt());
        assertEquals(2, result.get("requested").getAsInt());
        assertEquals(9, inventoryCount(player, 440));
        assertEquals(18, inventoryCount(player, 453));
        assertEquals(91, bankCount(player, 440));
        assertEquals(182, bankCount(player, 453));
        JsonArray summaries = result.getAsJsonArray("items");
        assertEquals(2, summaries.size());
        assertEquals(440, summaries.get(0).getAsJsonObject().get("itemId").getAsInt());
        assertEquals(9, summaries.get(0).getAsJsonObject().get("requested").getAsInt());
        assertEquals(9, summaries.get(0).getAsJsonObject().get("withdrawnAmount").getAsInt());
        assertEquals(453, summaries.get(1).getAsJsonObject().get("itemId").getAsInt());
        assertEquals(18, summaries.get(1).getAsJsonObject().get("requested").getAsInt());
        assertEquals(18, summaries.get(1).getAsJsonObject().get("withdrawnAmount").getAsInt());

        JsonObject compact = AgentToolService.compactXsResult("withdraw_bank_items", result, player, arguments);
        assertTrue(compact.get("success").getAsBoolean());
        assertTrue(compact.get("compact").getAsBoolean());
        assertEquals("withdraw_bank_items_XS", compact.get("tool").getAsString());
        assertEquals(27, compact.get("withdrawnAmount").getAsInt());
        assertEquals(2, compact.getAsJsonArray("items").size());
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
    public void explicitObserveStateKeysAreScopedPerPlayer() {
        Player flame = testPlayer(0, "MrFlame");
        Player gem = testPlayer(1, "MrGem");
        JsonObject arguments = new JsonObject();
        arguments.addProperty("key", "agent-loop");

        String flameKey = AgentToolService.observeStateHashKey(flame, arguments);
        String gemKey = AgentToolService.observeStateHashKey(gem, arguments);

        assertFalse(flameKey.equals(gemKey));
        assertEquals("mrflame:0:agent-loop", flameKey);
        assertEquals("mrgem:1:agent-loop", gemKey);
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

    @Test
    public void publicChatUsesOnlyPackedTextBytes() {
        Player player = testPlayer(44, "speaker");
        JsonObject arguments = new JsonObject();
        arguments.addProperty("message", "A little better. That is how the grind sneaks up on you.");

        JsonObject result = AgentToolService.handle(player, "send_public_chat", arguments);

        assertTrue(result.get("success").getAsBoolean());
        int packedSize = player.getChatTextSize() & 0xff;
        assertEquals(packedSize, player.getChatText().length);
        assertTrue(player.isChatTextEchoToSelfRequired());
        assertEquals("A little better. That is how the grind sneaks up on you.",
                Misc.optimizeText(Misc.textUnpack(player.getChatText(), packedSize)));
        Stream update = new Stream(new byte[256]);
        ((TestPlayer) player).appendPublicChatForTest(update);
        assertEquals(4 + packedSize, update.currentOffset);
        assertEquals(0, update.buffer[0] & 0xff);
        assertEquals(0, update.buffer[1] & 0xff);
        assertEquals(0, update.buffer[2] & 0xff);
        assertEquals(packedSize, -update.buffer[3] & 0xff);
        byte[] decoded = new byte[packedSize];
        for (int i = 0; i < packedSize; i++) {
            decoded[packedSize - 1 - i] = update.buffer[4 + i];
        }
        assertEquals("A little better. That is how the grind sneaks up on you.",
                Misc.optimizeText(Misc.textUnpack(decoded, packedSize)));
    }

    private static Player testPlayer(int playerId, String playerName) {
        Player player = new TestPlayer(playerId);
        player.playerName = playerName;
        player.outStream.packetEncryption = new IsaacRandom(new int[] {0, 0, 0, 0});
        return player;
    }

    private static Player readySpellTeleportPlayer(int playerId, String playerName, int magicLevel) {
        Player player = testPlayer(playerId, playerName);
        player.playerLevel[Constants.MAGIC] = magicLevel;
        player.tutorialProgress = 36;
        player.respawnTimer = -6;
        player.randomEventsEnabled = false;
        player.absX = 3200;
        player.absY = 3200;
        player.heightLevel = 0;
        return player;
    }

    private static void addInventoryItem(Player player, int itemId, int amount) {
        for (int slot = 0; slot < player.playerItems.length; slot++) {
            if (player.playerItems[slot] <= 0) {
                player.playerItems[slot] = itemId + 1;
                player.playerItemsN[slot] = amount;
                return;
            }
        }
        throw new IllegalStateException("test inventory is full");
    }

    private static int inventoryCount(Player player, int itemId) {
        int count = 0;
        for (int slot = 0; slot < player.playerItems.length; slot++) {
            if (player.playerItems[slot] == itemId + 1) {
                count += player.playerItemsN[slot];
            }
        }
        return count;
    }

    private static int bankCount(Player player, int itemId) {
        int count = 0;
        for (int slot = 0; slot < player.bankItems.length; slot++) {
            if (player.bankItems[slot] == itemId + 1) {
                count += player.bankItemsN[slot];
            }
        }
        return count;
    }

    private static class TestPlayer extends Client {
        private TestPlayer(int playerId) {
            super(null, playerId);
        }

        @Override
        public void stopMovement() {
            // Keep bridge tool tests independent from Client-only movement internals.
        }

        @Override
        public void flushOutStream() {
            // Keep bridge tool tests independent from an attached network session.
        }

        private void appendPublicChatForTest(Stream stream) {
            appendPlayerChatText(stream);
        }
    }
}
