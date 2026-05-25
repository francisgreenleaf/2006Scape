package com.rs2.agent;

import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.game.content.quests.QuestAssistant;
import com.rs2.game.players.Player;
import org.junit.Test;

import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class AgentActionServiceTest {

    @Test
    public void queuedActionRunsWhenServiceIsProcessed() throws Exception {
        FutureTask<JsonObject> task = new FutureTask<JsonObject>(new Callable<JsonObject>() {
            @Override
            public JsonObject call() {
                return AgentActionService.INSTANCE.submitOnGameTick("test", new Callable<JsonObject>() {
                    @Override
                    public JsonObject call() {
                        JsonObject result = AgentToolService.success("processed");
                        result.addProperty("value", 42);
                        return result;
                    }
                });
            }
        });
        Thread thread = new Thread(task, "AgentActionServiceTest");
        thread.start();

        for (int i = 0; i < 20 && !task.isDone(); i++) {
            AgentActionService.INSTANCE.processPendingActions();
            Thread.sleep(10L);
        }

        JsonObject result = task.get(1, TimeUnit.SECONDS);
        assertTrue(result.get("success").getAsBoolean());
        assertEquals(42, result.get("value").getAsInt());
    }

    @Test
    public void waitActionCompletesOnRequestedGameTickWithoutSleepingFirst() throws Exception {
        FutureTask<JsonObject> task = new FutureTask<JsonObject>(new Callable<JsonObject>() {
            @Override
            public JsonObject call() {
                return AgentActionService.INSTANCE.submitAfterGameTicks(2, new Callable<JsonObject>() {
                    @Override
                    public JsonObject call() {
                        JsonObject result = AgentToolService.success("waited");
                        result.addProperty("value", 7);
                        return result;
                    }
                });
            }
        });
        Thread thread = new Thread(task, "AgentActionServiceWaitTest");
        thread.start();

        for (int i = 0; i < 20 && AgentActionService.INSTANCE.pendingActionCountForTests() == 0; i++) {
            Thread.sleep(5L);
        }
        assertTrue(AgentActionService.INSTANCE.pendingActionCountForTests() > 0);

        AgentActionService.INSTANCE.processPendingActions();
        assertFalse(task.isDone());

        AgentActionService.INSTANCE.processPendingActions();
        JsonObject result = task.get(1, TimeUnit.SECONDS);
        assertTrue(result.get("success").getAsBoolean());
        assertEquals(7, result.get("value").getAsInt());
    }

    @Test
    public void goalArgumentsAreClampedToSafeBounds() {
        assertEquals(1, AgentActionService.clampGoalTargetLevel(-10));
        assertEquals(60, AgentActionService.clampGoalTargetLevel(60));
        assertEquals(99, AgentActionService.clampGoalTargetLevel(120));

        assertEquals(2, AgentActionService.clampGoalStepInterval(0));
        assertEquals(5, AgentActionService.clampGoalStepInterval(5));
        assertEquals(100, AgentActionService.clampGoalStepInterval(250));

        assertEquals(1, AgentActionService.clampGoalMaxActions(0));
        assertEquals(10000, AgentActionService.clampGoalMaxActions(10000));
        assertEquals(250000, AgentActionService.clampGoalMaxActions(500000));
    }

    @Test
    public void durableGoalPreferencesAreFlexibleUnlessExplicitlyLocked() {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("style", "attack");
        arguments.addProperty("area", "lumbridge cows");
        assertFalse(AgentActionService.isGoalPreferenceLocked(arguments, "fixedStyle", "lockStyle"));
        assertFalse(AgentActionService.isGoalPreferenceLocked(arguments, "fixedArea", "lockArea"));

        arguments.addProperty("fixedStyle", true);
        arguments.addProperty("lockArea", true);
        assertTrue(AgentActionService.isGoalPreferenceLocked(arguments, "fixedStyle", "lockStyle"));
        assertTrue(AgentActionService.isGoalPreferenceLocked(arguments, "fixedArea", "lockArea"));
    }

    @Test
    public void durableGoalAutosavesLoggedProgressAndTerminalEvents() {
        assertTrue(AgentActionService.shouldAutosaveGoalEvent("goal_progress"));
        assertTrue(AgentActionService.shouldAutosaveGoalEvent("goal_completed"));
        assertTrue(AgentActionService.shouldAutosaveGoalEvent("goal_blocked"));
        assertFalse(AgentActionService.shouldAutosaveGoalEvent("session_claimed"));
        assertFalse(AgentActionService.shouldAutosaveGoalEvent(null));
    }

    @Test
    public void durableGoalBanksCommonCombatSupplies() {
        assertTrue(AgentActionService.isCombatSupplyItemForBanking(526)); // bones
        assertTrue(AgentActionService.isCombatSupplyItemForBanking(1739)); // cowhide
        assertTrue(AgentActionService.isCombatSupplyItemForBanking(2132)); // raw beef
    }

    @Test
    public void durableGoalStoresStarterClutterForMainAccount() {
        assertTrue(AgentActionService.isAccountStorageItemForBanking(590)); // tinderbox
        assertTrue(AgentActionService.isAccountStorageItemForBanking(1265)); // bronze pickaxe
        assertTrue(AgentActionService.isAccountStorageItemForBanking(556)); // air rune
        assertFalse(AgentActionService.isAccountStorageItemForBanking(315)); // shrimps stay as food
        assertFalse(AgentActionService.isAccountStorageItemForBanking(2309)); // bread stays as food
    }

    @Test
    public void durableGoalBanksAnyNonCombatToolOutsideGearMoneyRuns() {
        assertFalse(AgentActionService.shouldStoreAccountItemCount(0, false, false));
        assertTrue(AgentActionService.shouldStoreAccountItemCount(1, false, false));
        assertFalse(AgentActionService.shouldStoreAccountItemCount(1, true, false));
        assertFalse(AgentActionService.shouldStoreAccountItemCount(1, false, true));
        assertFalse(AgentActionService.shouldStoreAccountItemCount(1, false, false, true));
    }

    @Test
    public void durableGoalTreatsApproachStepsAsRecoverable() {
        assertTrue(AgentActionService.isRecoverableGoalFailure("Repositioning to continue combat with Cow."));
        assertTrue(AgentActionService.isRecoverableGoalFailure("Walking into melee range to attack Cow."));
        assertTrue(AgentActionService.isRecoverableGoalFailure("No suitable Guard is nearby; moving toward varrock guards."));
    }

    @Test
    public void durableGoalUsesShortLootBreaksDuringCombat() {
        assertEquals(4, AgentActionService.combatSupplyPickupDistance(true));
        assertEquals(12, AgentActionService.combatSupplyPickupDistance(false));
    }

    @Test
    public void durableGoalRecognizesFoodRestockTools() {
        assertTrue(AgentActionService.isFoodToolForRestocking(303)); // small fishing net
        assertFalse(AgentActionService.isFoodToolForRestocking(1265)); // pickaxe
    }

    @Test
    public void durableGoalCanResumeWithPartialCookedFoodLoad() {
        assertEquals(5, AgentActionService.minimumReturnFood(10));
        assertEquals(9, AgentActionService.minimumReturnFood(18));
    }

    @Test
    public void durableGoalClosesPreparationInterfaceAfterFoodRestock() {
        assertTrue(AgentActionService.shouldClosePreparationInterface(true, false));
        assertTrue(AgentActionService.shouldClosePreparationInterface(false, true));
        assertFalse(AgentActionService.shouldClosePreparationInterface(false, false));
    }

    @Test
    public void durableGoalRestocksWhenFoodUnlocksBetterTrainingArea() {
        assertTrue(AgentActionService.shouldRestockForBetterTrainingArea(41, 32, 30, 35,
                4, 12, true, false, false));
        assertTrue(AgentActionService.shouldRestockForBetterTrainingArea(41, 32, 30, 35,
                4, 12, false, false, false));
        assertFalse(AgentActionService.shouldRestockForBetterTrainingArea(41, 32, 30, 35,
                4, 0, false, false, false));
        assertFalse(AgentActionService.shouldRestockForBetterTrainingArea(41, 32, 30, 35,
                8, 12, true, false, false));
        assertFalse(AgentActionService.shouldRestockForBetterTrainingArea(42, 40, 35, 38,
                9, 0, true, true, false));
        assertFalse(AgentActionService.shouldRestockForBetterTrainingArea(41, 32, 30, 35,
                4, 12, true, false, true));
    }

    @Test
    public void durableGoalPreservesMainAccountSuppliesInsteadOfSellingThem() {
        assertTrue(AgentActionService.isCombatSupplyItemForBanking(1739)); // cowhide
        assertTrue(AgentActionService.isCombatSupplyItemForBanking(526)); // bones
        assertTrue(AgentActionService.isCombatSupplyItemForBanking(2132)); // raw beef
        assertFalse(AgentActionService.isCombatSupplyItemForBanking(995)); // coins are saved, but do not trigger a solo bank trip
    }

    @Test
    public void durableGoalChoosesCloserSupplyBankForTrainingArea() {
        assertEquals("varrock east bank", AgentActionService.supplyBankLandmark("lumbridge goblins"));
        assertEquals("varrock east bank", AgentActionService.supplyBankLandmark("lumbridge cows"));
        assertEquals("varrock west bank", AgentActionService.supplyBankLandmark("barbarian village"));
        assertEquals("varrock west bank", AgentActionService.supplyBankLandmark("varrock guards"));
        assertEquals("varrock east bank", AgentActionService.supplyBankLandmark("rock crabs"));
        assertEquals("varrock east bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3253, 3322, true));
        assertEquals("al kharid bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3275, 3180, true));
        assertEquals("al kharid bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3268, 3215, true));
        assertEquals("al kharid bank",
                AgentActionService.supplyBankLandmark("varrock guards", 3268, 3227, false));
        assertEquals("varrock east bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3284, 3412, true));
        assertEquals("varrock east bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3288, 3393, false));
        assertEquals("varrock east bank",
                AgentActionService.supplyBankLandmark("varrock guards", 3274, 3428, false));
        assertEquals("varrock west bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3081, 3429, true));
        assertEquals("varrock east bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3253, 3322, false));
    }

    @Test
    public void durableGoalPrefersReachableSwordUpgradesWhenAttackUnlocksThem() {
        assertEquals(1279, AgentActionService.recommendedWeaponUpgradeId(1, 0)); // iron sword
        assertEquals(1281, AgentActionService.recommendedWeaponUpgradeId(10, 1)); // steel sword
        assertEquals(1285, AgentActionService.recommendedWeaponUpgradeId(20, 2)); // mithril sword
        assertEquals(1301, AgentActionService.recommendedWeaponUpgradeId(30, 3)); // adamant longsword
        assertEquals(1289, AgentActionService.recommendedWeaponUpgradeId(40, 4)); // rune sword
        assertEquals(-1, AgentActionService.recommendedWeaponUpgradeId(40, 5));
    }

    @Test
    public void durableGoalSavesForUnlockedWeaponBeforeArmour() {
        assertTrue(AgentActionService.shouldSaveForWeaponBeforeArmor(18, 300, 1)); // save for steel sword before armour
        assertFalse(AgentActionService.shouldSaveForWeaponBeforeArmor(18, 325, 1)); // steel sword is affordable
        assertFalse(AgentActionService.shouldSaveForWeaponBeforeArmor(18, 0, 2)); // steel sword is already equipped
        assertTrue(AgentActionService.shouldSaveForWeaponBeforeArmor(40, 1261, 4)); // earn rune money once rune is unlocked
        assertFalse(AgentActionService.shouldSaveForWeaponBeforeArmor(40, 15, 1261, 4)); // strength first when damage lags
        assertTrue(AgentActionService.shouldSaveForWeaponBeforeArmor(40, 15000, 4)); // close enough to finish rune saving
    }

    @Test
    public void durableGoalDefersExpensiveOneTierWeaponSavingsWhileAttackTraining() {
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(40, 60, 1261, 4, 1289));
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(40, 60, 15000, 4, 1289));
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(60, 60, 1261, 4, 1289));
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(40, 60, 1261, 3, 1289));
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(30, 60, 1261, 3, 1301));
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(40, 60, 1261, 4, 1121));
        assertTrue(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(41, 15, 60, 1682, 4, 1289));
        assertTrue(AgentActionService.shouldTrainStrengthBeforeExpensiveWeapon(41, 15, 60));
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(41, 31, 60, 1261, 4, 1289));
        assertFalse(AgentActionService.shouldTrainStrengthBeforeExpensiveWeapon(41, 31, 60));
        assertFalse(AgentActionService.shouldTrainStrengthBeforeExpensiveWeapon(41, 37, 60));
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(41, 15, 60, 15000, 4, 1289));
    }

    @Test
    public void durableGoalFallsThroughToDefensiveGearWhenRuneSwordSavingsAreDeferred() {
        assertEquals(1193, AgentActionService.recommendedGearMoneyUpgradeId(41, 22, 14, 189,
                4, 2, 0, 2, 1, 60)); // steel kiteshield before long rune saving
        assertEquals(1289, AgentActionService.recommendedGearMoneyUpgradeId(41, 31, 14, 189,
                4, 2, 0, 2, 1, 60)); // rune sword once Strength is sturdy enough for the long savings run
        assertEquals(1289, AgentActionService.recommendedGearMoneyUpgradeId(41, 22, 14, 15000,
                4, 2, 0, 2, 1, 60)); // finish rune saving when already close enough
        assertEquals(1121, AgentActionService.recommendedGearMoneyUpgradeId(41, 30, 20, 189,
                4, 2, 0, 2, 1, 60)); // mithril body as Defence unlocks it
        assertEquals(1157, AgentActionService.recommendedGearMoneyUpgradeId(41, 22, 14, 189,
                4, 2, 0, 2, 3, 60)); // helm upgrade once shield is caught up
    }

    @Test
    public void durableGoalDoesNotSaveForChampionsGuildGearBeforeQuestPoints() {
        int requiredQuestPoints = Math.min(32, QuestAssistant.MAXIMUM_QUESTPOINTS);
        assertFalse(AgentActionService.isChampionsGuildGearAvailable(1289, 0));
        assertFalse(AgentActionService.isChampionsGuildGearAvailable(1289, requiredQuestPoints - 1));
        assertTrue(AgentActionService.isChampionsGuildGearAvailable(1289, requiredQuestPoints));
        assertEquals(-1, AgentActionService.recommendedGearMoneyUpgradeId(41, 32, 30, 21710,
                4, 3, 4, 4, 3, 60, false)); // already has the reachable upgrades
        assertEquals(1289, AgentActionService.recommendedGearMoneyUpgradeId(41, 32, 30, 21710,
                4, 3, 4, 4, 3, 60, true)); // Scavvo is valid once Champions' Guild is available
    }

    @Test
    public void durableGoalBuysAffordableIntermediateWeaponBeforeSavingForNextSword() {
        assertTrue(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1279, 1281)); // iron before steel
        assertTrue(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1281, 1285)); // steel before mithril
        assertTrue(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1173, 1175)); // iron shield before steel shield
        assertFalse(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1115, 1281)); // armour does not delay sword
        assertFalse(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1173, 1281)); // shield does not delay sword
        assertFalse(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1281, 1281)); // target is already affordable
    }

    @Test
    public void durableGoalUsesCacheMatchedGearPriceEstimates() {
        assertEquals(91, AgentActionService.gearTargetEstimatedPrice(1279)); // iron sword
        assertEquals(325, AgentActionService.gearTargetEstimatedPrice(1281)); // steel sword
        assertEquals(845, AgentActionService.gearTargetEstimatedPrice(1285)); // mithril sword
        assertEquals(3200, AgentActionService.gearTargetEstimatedPrice(1301)); // adamant longsword
        assertEquals(20800, AgentActionService.gearTargetEstimatedPrice(1289)); // rune sword
        assertEquals(560, AgentActionService.gearTargetEstimatedPrice(1115)); // iron platebody
        assertEquals(750, AgentActionService.gearTargetEstimatedPrice(1105)); // steel chainbody
        assertEquals(5200, AgentActionService.gearTargetEstimatedPrice(1121)); // mithril platebody
        assertEquals(50000, AgentActionService.gearTargetEstimatedPrice(1113)); // rune chainbody
        assertEquals(65000, AgentActionService.gearTargetEstimatedPrice(1127)); // rune platebody
        assertEquals(154, AgentActionService.gearTargetEstimatedPrice(1153)); // iron full helm
        assertEquals(550, AgentActionService.gearTargetEstimatedPrice(1157)); // steel full helm
        assertEquals(1430, AgentActionService.gearTargetEstimatedPrice(1159)); // mithril full helm
        assertEquals(3520, AgentActionService.gearTargetEstimatedPrice(1161)); // adamant full helm
        assertEquals(35200, AgentActionService.gearTargetEstimatedPrice(1163)); // rune full helm
        assertEquals(280, AgentActionService.gearTargetEstimatedPrice(1067)); // iron platelegs
        assertEquals(1000, AgentActionService.gearTargetEstimatedPrice(1069)); // steel platelegs
        assertEquals(2600, AgentActionService.gearTargetEstimatedPrice(1071)); // mithril platelegs
        assertEquals(6400, AgentActionService.gearTargetEstimatedPrice(1073)); // adamant platelegs
        assertEquals(64000, AgentActionService.gearTargetEstimatedPrice(1079)); // rune platelegs
        assertEquals(168, AgentActionService.gearTargetEstimatedPrice(1173)); // bronze sq shield
        assertEquals(500, AgentActionService.gearTargetEstimatedPrice(1175)); // iron sq shield
        assertEquals(1200, AgentActionService.gearTargetEstimatedPrice(1193)); // steel kiteshield
        assertEquals(22000, AgentActionService.gearTargetEstimatedPrice(1185)); // rune sq shield
    }

    @Test
    public void shantayPassPurchaseRequiresInventoryAndCoinChanges() {
        assertTrue(AgentActionService.shantayPassPurchaseSucceeded(0, 1, 1508, 1503));
        assertFalse(AgentActionService.shantayPassPurchaseSucceeded(0, 0, 1508, 1508));
        assertFalse(AgentActionService.shantayPassPurchaseSucceeded(0, 1, 1508, 1508));
        assertFalse(AgentActionService.shantayPassPurchaseSucceeded(1, 1, 1508, 1503));
    }

    @Test
    public void nardahGearCostDropsTransitFareAfterTransitIsPaid() {
        assertEquals(1405, AgentActionService.estimatedNardahGearAcquisitionCost(1200, 3303, 3124, 0));
        assertEquals(1400, AgentActionService.estimatedNardahGearAcquisitionCost(1200, 3311, 3109, 0));
        assertEquals(1200, AgentActionService.estimatedNardahGearAcquisitionCost(1200, 3369, 2947, 0));
        assertEquals(1200, AgentActionService.estimatedNardahGearAcquisitionCost(1200, 3407, 2921, 0));
        assertTrue(AgentActionService.isNardahTransitComplete(3369, 2947, 0));
        assertFalse(AgentActionService.isNardahTransitComplete(3303, 3124, 0));
    }

    @Test
    public void durableGoalCanOpenGearShopBeforeExactLandmarkCompletion() {
        assertTrue(AgentActionService.isNearLandmarkTarget("al kharid legs shop", 3305, 3185, 0, 12));
        assertTrue(AgentActionService.isNearLandmarkTarget("al kharid legs shop", 3304, 3184, 0, 12));
        assertFalse(AgentActionService.isNearLandmarkTarget("al kharid legs shop", 3299, 3185, 0, 12));
        assertFalse(AgentActionService.isNearLandmarkTarget("al kharid legs shop", 3305, 3185, 1, 12));
    }

    @Test
    public void durableGoalUsesCarpetChainForDesertReturnRoutes() {
        assertTrue(AgentActionService.shouldUseDesertReturnTransit("varrock east bank"));
        assertFalse(AgentActionService.shouldUseDesertReturnTransit("nardah adventurer store"));
        assertFalse(AgentActionService.shouldUseDesertReturnTransit("shantay rug merchant"));

        assertTrue(AgentActionService.shouldRideNardahCarpetToPollnivneach(3407, 2921, 0,
                "varrock east bank"));
        assertTrue(AgentActionService.shouldWalkToPollnivneachRugStation(3369, 2947, 0,
                "varrock east bank"));
        assertFalse(AgentActionService.shouldWalkToPollnivneachRugStation(3347, 2944, 0,
                "varrock east bank"));
        assertTrue(AgentActionService.shouldRidePollnivneachCarpetToShantay(3347, 2944, 0,
                "varrock east bank"));
        assertTrue(AgentActionService.shouldWalkToShantayGateFromSouth(3308, 3108, 0,
                "varrock east bank"));
        assertTrue(AgentActionService.shouldUseShantayGateFromSouth(3304, 3115, 0,
                "varrock east bank"));
    }

    @Test
    public void shantayPassDialogueIsAdvancedInsteadOfReclicked() {
        assertTrue(AgentActionService.shouldContinueShantayPassDialogue(1323, 0, 836));
        assertTrue(AgentActionService.shouldContinueShantayPassDialogue(1326, 0, 836));
        assertFalse(AgentActionService.shouldContinueShantayPassDialogue(1323, 146, 836));
        assertFalse(AgentActionService.shouldContinueShantayPassDialogue(1323, 0, 837));

        assertTrue(AgentActionService.shouldSelectShantayPassShopOption(1323, 146, 836));
        assertFalse(AgentActionService.shouldSelectShantayPassShopOption(1323, 0, 836));
        assertFalse(AgentActionService.shouldSelectShantayPassShopOption(1323, 146, 837));
    }

    @Test
    public void durableGoalTreatsOnlyMinedResourcesAsGearMoneyItems() {
        assertTrue(AgentActionService.isGearMoneyItem(436)); // copper ore
        assertTrue(AgentActionService.isGearMoneyItem(438)); // tin ore
        assertTrue(AgentActionService.isGearMoneyItem(440)); // iron ore
        assertTrue(AgentActionService.isGearMoneyItem(453)); // coal
        assertTrue(AgentActionService.isGearMoneyItem(2349)); // bronze bar
        assertTrue(AgentActionService.isGearMoneyItem(2353)); // steel bar
        assertFalse(AgentActionService.isGearMoneySaleItem(2349)); // bars must be smithed before sale
        assertFalse(AgentActionService.isGearMoneySaleItem(2351)); // leftover bars are staged, not liquidated raw
        assertTrue(AgentActionService.isGearMoneyProductItem(1422)); // bronze mace can be smithed for sale
        assertTrue(AgentActionService.isGearMoneySaleItem(1422)); // smithed products are saleable
        assertFalse(AgentActionService.isGearMoneyProductItem(4820)); // nails are low-value components
        assertFalse(AgentActionService.isGearMoneyProductItem(820)); // darts are low-value ammo
        assertFalse(AgentActionService.isGearMoneyProductItem(40)); // arrow tips are low-value components
        assertFalse(AgentActionService.isGearMoneyProductItem(863)); // knives are low-value ammo
        assertTrue(AgentActionService.isGearMoneyProductItem(1293)); // iron longsword is a quality sale product
        assertFalse(AgentActionService.isGearMoneyProductItem(1351)); // starter axe/tool is preserved
        assertFalse(AgentActionService.isGearMoneyProductItem(1279)); // combat gear is preserved
        assertTrue(AgentActionService.isGearMoneySmithingCandidateItem(1281)); // freshly smithed steel swords are efficient
        assertFalse(AgentActionService.isGearMoneySaleItem(1281)); // old banked combat gear is not a generic sale item
        assertTrue(AgentActionService.isTrackedGearMoneyProductItem(1279, 1279)); // current-run products can be banked
        assertFalse(AgentActionService.isTrackedGearMoneyProductItem(1281, 1279)); // unrelated old gear stays protected
        assertTrue(AgentActionService.isStackedGearMoneyProductItem(1325, 8)); // batched scimitars can survive restart
        assertTrue(AgentActionService.isStackedGearMoneyProductItem(1157, 8)); // batched full helms can be sold
        assertFalse(AgentActionService.isStackedGearMoneyProductItem(1325, 7)); // small old stacks stay protected
        assertTrue(AgentActionService.shouldExcludeGearMoneySaleItemFromCombatSupplyBanking(true,
                false, 1289, true));
        assertTrue(AgentActionService.shouldExcludeGearMoneySaleItemFromCombatSupplyBanking(false,
                true, 1289, true));
        assertTrue(AgentActionService.shouldExcludeGearMoneySaleItemFromCombatSupplyBanking(false,
                false, 1289, true));
        assertFalse(AgentActionService.shouldExcludeGearMoneySaleItemFromCombatSupplyBanking(true,
                false, 1289, false));
        assertFalse(AgentActionService.shouldExcludeGearMoneySaleItemFromCombatSupplyBanking(false,
                false, 0, true));
        assertFalse(AgentActionService.isGearMoneyItem(526)); // bones stay banked for the account
        assertFalse(AgentActionService.isGearMoneyItem(1739)); // cowhide stays banked for the account
    }

    @Test
    public void durableGoalRanksSmithingForGearMoneyByHighestUnlockedProduct() {
        assertEquals(640, AgentActionService.estimatedGearMoneySmithingBatchSellCoins(1137, 10)); // 10 iron med helms
        assertEquals(535, AgentActionService.estimatedGearMoneySmithingBatchSellCoins(1293, 10)); // 5 iron longswords
        assertEquals(AgentActionService.estimatedGearMoneySmithingBatchSellCoins(1281, 10),
                AgentActionService.estimatedGearMoneySmithingPotentialSellCoins(34, 2353, 10));
        assertTrue(AgentActionService.estimatedGearMoneySmithingBatchSellCoins(1281, 10) > 0);
        assertTrue(AgentActionService.isBetterGearMoneySmithingItem(1293, 1137, 10));
        assertTrue(AgentActionService.isBetterGearMoneySmithingItem(1363, 1293, 10));
        assertFalse(AgentActionService.isBetterGearMoneySmithingItem(1137, 1293, 10));
    }

    @Test
    public void durableGoalBanksNonMiningClutterBeforeGearMoneyRuns() {
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(1265)); // keep the pickaxe
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(2347)); // keep the hammer
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(436)); // keep copper ore
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(438)); // keep tin ore
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(440)); // keep iron ore
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(1422)); // sell smithed mace for gear money
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(995)); // keep toll/buying coins during runs
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(2142)); // food is only banked when above buffer
        assertTrue(AgentActionService.isGearMoneyClutterItemForBanking(1277)); // bank old combat gear
        assertTrue(AgentActionService.isGearMoneyClutterItemForBanking(1623)); // bank gems for later
        assertFalse(AgentActionService.shouldBankExcessGearMoneyFood(4));
        assertTrue(AgentActionService.shouldBankExcessGearMoneyFood(18));
        assertEquals(14, AgentActionService.excessGearMoneyFoodCount(18));
    }

    @Test
    public void durableGoalBanksMiningByproductsBeforeProcessingOreNearVarrockBanks() {
        assertTrue(AgentActionService.shouldBankGearMoneyClutterBeforeProcessing(2, 3286, 3368));
        assertTrue(AgentActionService.shouldBankGearMoneyClutterBeforeProcessing(1, 3216, 3415));
        assertFalse(AgentActionService.shouldBankGearMoneyClutterBeforeProcessing(0, 3286, 3368));
        assertFalse(AgentActionService.shouldBankGearMoneyClutterBeforeProcessing(2, 3275, 3186));
        assertEquals("varrock east bank", AgentActionService.gearMoneyClutterBankLandmark(3286, 3368));
        assertEquals("varrock west bank", AgentActionService.gearMoneyClutterBankLandmark(3216, 3415));
        assertEquals("al kharid bank", AgentActionService.gearMoneyClutterBankLandmark(3274, 3186));
        assertEquals("al kharid bank", AgentActionService.gearMoneyClutterBankLandmark(3259, 3229));
    }

    @Test
    public void durableGoalBanksObsoleteCarriedPickaxesDuringGearMoneyRuns() {
        assertFalse(AgentActionService.isObsoleteGearMoneyPickaxeForBanking(1269, 3)); // keep best steel
        assertTrue(AgentActionService.isObsoleteGearMoneyPickaxeForBanking(1269, 4)); // bank steel once mithril carried
        assertFalse(AgentActionService.isObsoleteGearMoneyPickaxeForBanking(1273, 4)); // keep best mithril
        assertFalse(AgentActionService.isObsoleteGearMoneyPickaxeForBanking(1279, 4)); // ignore non-pickaxe gear
    }

    @Test
    public void durableGoalMinesBronzeInputsUntilIronSmeltingUnlocks() {
        assertEquals("copper", AgentActionService.gearMoneyOreForMiningLevel(1, 1, 0, 0));
        assertEquals("tin", AgentActionService.gearMoneyOreForMiningLevel(1, 1, 3, 1));
        assertEquals("copper", AgentActionService.gearMoneyOreForMiningLevel(21, 3, 100, 100));
        assertEquals("tin", AgentActionService.gearMoneyOreForMiningLevel(21, 3, 5, 4));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(15, 15, 100, 0));
    }

    @Test
    public void durableGoalMinesIronUntilSteelProductsCanBeSmithed() {
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(30, 20, 0, 0, 0, 0));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(30, 20, 0, 0, 1, 0));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(32, 22, 0, 0, 9, 17));
    }

    @Test
    public void durableGoalMinesCoalForSteelOnceSteelItemSmithingUnlocks() {
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(30, 30, 0, 0, 0, 0));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(30, 30, 0, 0, 1, 0));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(30, 30, 0, 0, 1, 1));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(30, 30, 0, 0, 1, 2));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(32, 30, 0, 0, 9, 17));
    }

    @Test
    public void durableGoalBalancesIronAndCoalBeforeSteelSmelting() {
        assertFalse(AgentActionService.shouldUseSteelForGearMoney(22));
        assertTrue(AgentActionService.shouldUseSteelForGearMoney(30));

        assertTrue(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                22, 0, 0, 117, 0, 0, 0, false));
        assertTrue(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                0, 0, 22, 117, 22, 0, 0, false));
        assertTrue(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                7, 0, 0, 14, 14, 0, 0, false));
        assertFalse(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                7, 14, 0, 0, 0, 0, 0, false));
        assertFalse(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                22, 0, 0, 117, 0, 1, 0, false));
        assertFalse(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                22, 0, 0, 117, 0, 0, 0, true));
        assertFalse(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                4, 6, 0, 117, 11, 0, 0, false));
        assertFalse(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                3, 4, 0, 1, 15, 0, 0, false));
        assertFalse(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                5, 9, 0, 1, 7, 0, 0, false, 3304, 3317));
        assertTrue(AgentActionService.shouldPrepareSteelSmeltingInputs(31,
                5, 9, 0, 1, 7, 0, 0, false, 3288, 3396));

        assertEquals(14, AgentActionService.steelCoalNeededForIron(7, 0));
        assertEquals(0, AgentActionService.steelCoalNeededForIron(7, 14));
        assertTrue(AgentActionService.shouldDelaySteelCoalPairingForIronBatch(4, 6, 117, 11));
        assertTrue(AgentActionService.shouldDelaySteelCoalPairingForIronBatch(3, 4, 1, 15));
        assertFalse(AgentActionService.shouldDelaySteelCoalPairingForIronBatch(7, 6, 117, 8));
        assertTrue(AgentActionService.shouldMineCoalInsteadOfBankingForPairing(5, 9, 7, 3304, 3317));
        assertFalse(AgentActionService.shouldMineCoalInsteadOfBankingForPairing(5, 9, 7, 3288, 3396));
        assertEquals(7, AgentActionService.targetSteelIronMiningBatch(4, 6, 117, 11));
        assertEquals(7, AgentActionService.targetSteelSmeltingBars(22, 22, 117));
        assertEquals(0, AgentActionService.targetSteelSmeltingBars(2, 22, 117));
    }

    @Test
    public void durableGoalFallsBackToIronWhenCoalRouteIsUnsafe() {
        assertEquals("iron", AgentActionService.gearMoneyOreForRouteSafety("coal", 0, 30, 30));
        assertEquals("iron", AgentActionService.gearMoneyOreForRouteSafety("coal", 4, 15, 30));
        assertEquals("coal", AgentActionService.gearMoneyOreForRouteSafety("coal", 4, 30, 30));
        assertEquals("iron", AgentActionService.gearMoneyOreForRouteSafety("iron", 0, 15, 30));
    }

    @Test
    public void durableGoalRoutesCoalMiningToVarrockCoalRocks() {
        assertEquals("varrock east mine", AgentActionService.gearMoneyMineLandmark("iron"));
        assertEquals("varrock east coal mine", AgentActionService.gearMoneyMineLandmark("coal"));
    }

    @Test
    public void durableGoalKeepsMiningClicksLocalInsideMoneyMine() {
        JsonObject coalArgs = AgentActionService.gearMoneyOreArgs("coal", 3304, 3317);
        assertEquals("coal", coalArgs.get("ore").getAsString());
        assertEquals(8, coalArgs.get("maxDistance").getAsInt());
        assertTrue(coalArgs.get("waitForLocalRespawn").getAsBoolean());

        JsonObject travelArgs = AgentActionService.gearMoneyOreArgs("coal", 3253, 3420);
        assertEquals("coal", travelArgs.get("ore").getAsString());
        assertFalse(travelArgs.has("maxDistance"));
        assertFalse(travelArgs.has("waitForLocalRespawn"));
    }

    @Test
    public void durableGoalBanksNearFullLoadInsteadOfCrossMineTopOff() {
        assertTrue(AgentActionService.shouldBankNearFullGearMoneyBatchBeforeOreSwitch(23, 1,
                "iron", 3303, 3300));
        assertTrue(AgentActionService.shouldBankNearFullGearMoneyBatchBeforeOreSwitch(23, 4,
                "coal", 3285, 3365));
        assertFalse(AgentActionService.shouldBankNearFullGearMoneyBatchBeforeOreSwitch(23, 5,
                "iron", 3303, 3300));
        assertFalse(AgentActionService.shouldBankNearFullGearMoneyBatchBeforeOreSwitch(0, 1,
                "iron", 3303, 3300));
        assertFalse(AgentActionService.shouldBankNearFullGearMoneyBatchBeforeOreSwitch(23, 1,
                "coal", 3303, 3300));
        assertFalse(AgentActionService.shouldBankNearFullGearMoneyBatchBeforeOreSwitch(23, 1,
                "coal", 3253, 3420));
    }

    @Test
    public void durableGoalBatchesSteelOreByCurrentMine() {
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(34, 22, 0, 0, 7, 10,
                5, 3304, 3317));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(34, 30, 0, 0, 0, 0,
                22, 3285, 3365));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(34, 30, 0, 0, 2, 4,
                18, 3304, 3317));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(34, 30, 0, 0, 2, 16,
                6, 3285, 3365));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(34, 30, 0, 0, 7, 0,
                15, 3253, 3420));
        assertTrue(AgentActionService.isGearMoneyCoalMine(3304, 3317));
        assertTrue(AgentActionService.isGearMoneyCoalMine(3309, 3310));
        assertTrue(AgentActionService.isGearMoneyMine("coal", 3309, 3310));
        assertFalse(AgentActionService.isGearMoneyMine("iron", 3309, 3310));
        assertTrue(AgentActionService.isGearMoneyIronMine(3285, 3365));
        assertTrue(AgentActionService.isGearMoneyMine("iron", 3285, 3365));
    }

    @Test
    public void durableGoalAggregatesOreForWholeFundingTargetBeforeProcessing() {
        int targetBars = AgentActionService.requiredGearMoneyBatchBars(37, 2353, 32000);
        assertTrue(targetBars > 28);
        assertEquals(2353, AgentActionService.preferredGearMoneyBatchBar(46, 37));
        assertFalse(AgentActionService.isPreferredGearMoneyBatchStaged(46, 37,
                0, 0, targetBars, targetBars * 2 - 1, 0, 0, 0, 0, 32000, 0));
        assertTrue(AgentActionService.isPreferredGearMoneyBatchStaged(46, 37,
                0, 0, targetBars, targetBars * 2, 0, 0, 0, 0, 32000, 0));

        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(46, 37,
                0, 0, 22, 0, 0, 3285, 3365, 0, 32000, 0, 0, 0, 0));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(46, 37,
                0, 0, targetBars, 0, 0, 3285, 3365, 0, 32000, 0, 0, 0, 0));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(46, 37,
                0, 0, targetBars, 28, 0, 3304, 3317, 0, 32000, 0, 0, 0, 0));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(46, 37,
                0, 0, targetBars - 1, targetBars * 2, 0, 3285, 3365, 0, 32000, 0, 0, 0, 0));
    }

    @Test
    public void durableGoalUsesGenericMaterialBatchPlans() {
        assertEquals(516, AgentActionService.stagedBatchOutputCount(17,
                AgentActionService.batchMaterialNeed("iron", 500, 1),
                AgentActionService.batchMaterialNeed("coal", 999, 2)));

        assertEquals("iron", AgentActionService.nextBatchMaterialSource(500, 3285, 3365,
                AgentActionService.batchMaterialNeed("iron", 499, 1),
                AgentActionService.batchMaterialNeed("coal", 1000, 2)));
        assertEquals("coal", AgentActionService.nextBatchMaterialSource(500, 3304, 3317,
                AgentActionService.batchMaterialNeed("iron", 500, 1),
                AgentActionService.batchMaterialNeed("coal", 998, 2)));
        assertEquals("coal", AgentActionService.nextBatchMaterialSource(500, 3200, 3200,
                AgentActionService.batchMaterialNeed("iron", 470, 1),
                AgentActionService.batchMaterialNeed("coal", 920, 2)));
        assertEquals("", AgentActionService.nextBatchMaterialSource(500, 3200, 3200,
                AgentActionService.batchMaterialNeed("iron", 500, 1),
                AgentActionService.batchMaterialNeed("coal", 1000, 2)));
    }

    @Test
    public void durableGoalFinishesSmeltingBeforeSmithingBars() {
        assertEquals(AgentActionService.GEAR_MONEY_PRODUCTION_SMELT,
                AgentActionService.gearMoneyProductionAction(true, true));
        assertEquals(AgentActionService.GEAR_MONEY_PRODUCTION_SMELT,
                AgentActionService.gearMoneyProductionAction(true, false));
        assertEquals(AgentActionService.GEAR_MONEY_PRODUCTION_SMITH,
                AgentActionService.gearMoneyProductionAction(false, true));
        assertEquals(AgentActionService.GEAR_MONEY_PRODUCTION_NONE,
                AgentActionService.gearMoneyProductionAction(false, false));
    }

    @Test
    public void durableGoalDoesNotSellProductsBeforeProcessingRemainingBars() {
        assertFalse(AgentActionService.shouldSellGearMoneyProductsBeforeProduction(1, true, false));
        assertFalse(AgentActionService.shouldSellGearMoneyProductsBeforeProduction(1, false, true));
        assertTrue(AgentActionService.shouldSellGearMoneyProductsBeforeProduction(1, false, false));
        assertFalse(AgentActionService.shouldSellGearMoneyProductsBeforeProduction(0, false, false));

        assertFalse(AgentActionService.shouldSellReadyGearMoneyBatchBeforeProcessing(22, true,
                AgentActionService.GEAR_MONEY_PRODUCTION_SMITH));
        assertFalse(AgentActionService.shouldSellReadyGearMoneyBatchBeforeProcessing(22, true,
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT));
        assertTrue(AgentActionService.shouldSellReadyGearMoneyBatchBeforeProcessing(22, true,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE));
        assertFalse(AgentActionService.shouldSellReadyGearMoneyBatchBeforeProcessing(0, true,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE));
        assertFalse(AgentActionService.shouldSellReadyGearMoneyBatchBeforeProcessing(22, false,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE));
        assertFalse(AgentActionService.shouldSellReadyGearMoneyBatchBeforeProcessing(22, true,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE, true, true));
        assertTrue(AgentActionService.shouldSellReadyGearMoneyBatchBeforeProcessing(22, true,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE, true, false));
        assertFalse(AgentActionService.shouldSellGearMoneyProductsBeforeProduction(1, false, false,
                true, true));
        assertTrue(AgentActionService.shouldSellGearMoneyProductsBeforeProduction(1, false, false,
                true, false));
        assertTrue(AgentActionService.shouldFinishStagedMaterialsBeforeSelling(true, true));
        assertFalse(AgentActionService.shouldFinishStagedMaterialsBeforeSelling(true, false));
        assertFalse(AgentActionService.shouldFinishStagedMaterialsBeforeSelling(false, true));
    }

    @Test
    public void durableGoalBatchesGearMoneyUntilUpgradeIsFunded() {
        assertFalse(AgentActionService.shouldSellGearMoneyBatch(340, 320, 4000, 5200));
        assertTrue(AgentActionService.shouldSellGearMoneyBatch(340, 900, 4000, 5200));
        assertTrue(AgentActionService.shouldSellGearMoneyBatch(5200, 0, 0, 5200));

        int pickaxeLiquidityTarget = AgentActionService.gearMoneyLiquidityTargetCost(5200, 3200);
        assertEquals(3200, pickaxeLiquidityTarget);
        assertFalse(AgentActionService.shouldSellGearMoneyBatch(340, 320, 2539, pickaxeLiquidityTarget));
        assertTrue(AgentActionService.shouldSellGearMoneyBatch(340, 320, 2540, pickaxeLiquidityTarget));
        assertEquals(5200, AgentActionService.gearMoneyLiquidityTargetCost(5200, -1));
        assertEquals(5200, AgentActionService.gearMoneyLiquidityTargetCost(5200, 6400));

        assertTrue(AgentActionService.shouldBankGearMoneyBatchBeforeTarget(5, 340, 320, 4000, 5200));
        assertFalse(AgentActionService.shouldBankGearMoneyBatchBeforeTarget(5, 340, 900, 4000, 5200));
        assertFalse(AgentActionService.shouldBankGearMoneyBatchBeforeTarget(0, 340, 0, 4000, 5200));

        assertTrue(AgentActionService.shouldBankGearMoneyCarryoverBeforeCombat(21, false, false));
        assertFalse(AgentActionService.shouldBankGearMoneyCarryoverBeforeCombat(0, false, false));
        assertFalse(AgentActionService.shouldBankGearMoneyCarryoverBeforeCombat(21, true, false));
        assertFalse(AgentActionService.shouldBankGearMoneyCarryoverBeforeCombat(21, false, true));
        assertFalse(AgentActionService.shouldBankGearMoneyCarryoverBeforeCombat(1, false, false, true));
    }

    @Test
    public void durableGoalOnlyPreparesSmithingGateTollOnAlKharidSide() {
        assertTrue(AgentActionService.shouldPrepareAlKharidGateTollForSmithing(3275, 3186));
        assertTrue(AgentActionService.shouldPrepareAlKharidGateTollForSmithing(3268, 3227));
        assertFalse(AgentActionService.shouldPrepareAlKharidGateTollForSmithing(3257, 3322));
        assertFalse(AgentActionService.shouldPrepareAlKharidGateTollForSmithing(3188, 3425));

        assertTrue(AgentActionService.shouldPrepareAlKharidGateTollForCombat(3268, 3227, 1,
                "varrock guards"));
        assertFalse(AgentActionService.shouldPrepareAlKharidGateTollForCombat(3268, 3227, 10,
                "varrock guards"));
        assertFalse(AgentActionService.shouldPrepareAlKharidGateTollForCombat(3252, 3236, 1,
                "varrock guards"));
        assertFalse(AgentActionService.shouldPrepareAlKharidGateTollForCombat(3268, 3227, 1,
                "al kharid kebab shop"));
        assertTrue(AgentActionService.shouldReserveAlKharidReturnTollForTarget("varrock guards"));
        assertFalse(AgentActionService.shouldReserveAlKharidReturnTollForTarget("al kharid kebab shop"));
    }

    @Test
    public void durableGoalOnlyWithdrawsStagedMaterialsWhenTheProcessingBatchIsFunded() {
        assertFalse(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, true, 12, false, 21));
        assertTrue(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, true, 0, true, 21));
        assertFalse(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, false, 7, false, 21));
        assertFalse(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, false, 8, false, 21));
        assertFalse(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, false, 12, false, 21));
        assertTrue(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, false, 1, true, 21));
        assertFalse(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                1, true, 12, false, 21));
        assertFalse(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, true, 0, false, 21));
        assertFalse(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, true, 12, false, 0));
        assertTrue(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, true, 12, false, 21, true));
        assertTrue(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, true, 0, false, 21, true));
        assertFalse(AgentActionService.shouldWithdrawBankedGearMoneyMaterialsForProcessing(
                0, false, 0, false, 21, true));

        assertEquals(440, AgentActionService.gearMoneyProcessableWithdrawalItem(true, 440, 2351));
        assertEquals(2351, AgentActionService.gearMoneyProcessableWithdrawalItem(false, 440, 2351));
        assertEquals(2351, AgentActionService.gearMoneyProcessableWithdrawalItem(true, -1, 2351));
        assertTrue(AgentActionService.hasProcessableGearMoneyMaterials(true, 0));
        assertTrue(AgentActionService.hasProcessableGearMoneyMaterials(false, 7));
        assertFalse(AgentActionService.hasProcessableGearMoneyMaterials(false, 0));
    }

    @Test
    public void durableGoalCountsStagedOreAndBarsTowardFundedProcessingBatch() {
        Player player = new Player(0) {
        };
        player.playerXP[Constants.SMITHING] = 25368;
        player.bankItems[0] = 441; // Iron ore.
        player.bankItemsN[0] = 10;
        player.bankItems[1] = 454; // Coal.
        player.bankItemsN[1] = 20;
        player.bankItems[2] = 2354; // Steel bar.
        player.bankItemsN[2] = 8;

        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        assertEquals(1000 + AgentActionService.estimatedGearMoneySmithingPotentialSellCoins(
                smithingLevel, 2353, 18), AgentActionService.estimatedProcessedGearMoneyPotentialCoins(player, 1000));
    }

    @Test
    public void bankItemCountsIgnoreRetainedEmptyBankSlots() {
        Player player = new Player(0) {
        };
        player.bankItems[0] = 441;
        player.bankItemsN[0] = 0;
        player.bankItems[1] = 441;
        player.bankItemsN[1] = 11;

        assertEquals(11, AgentToolService.countBankItem(player, 440));

        player.bankItemsN[1] = 0;
        assertEquals(0, AgentToolService.countBankItem(player, 440));
    }

    @Test
    public void inventoryItemCountsIgnoreRetainedEmptyInventorySlots() {
        Player player = new Player(0) {
        };
        player.playerItems[0] = 2354;
        player.playerItemsN[0] = 0;
        player.playerItems[1] = 2354;
        player.playerItemsN[1] = 13;

        assertEquals(13, AgentToolService.countInventoryItem(player, 2353));

        player.playerItemsN[1] = 0;
        assertEquals(0, AgentToolService.countInventoryItem(player, 2353));
    }

    @Test
    public void durableGoalWaitsForFullerOreRunsBeforeWalkingToFurnace() {
        assertFalse(AgentActionService.shouldSmeltGearMoneyOres(5, 8, false));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(5, 8, true));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(8, 8, true));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(5, 8, false, true));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(4, 9, false, false, true));
        assertFalse(AgentActionService.shouldSmeltGearMoneyOres(10, 8, false));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(21, 4, false));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(24, 8, false));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(1, 3, false));
        assertFalse(AgentActionService.shouldSmeltGearMoneyOres(0, 3, true));
    }

    @Test
    public void durableGoalRestocksFoodBeforeRiskyGearMoneyRuns() {
        assertFalse(AgentActionService.shouldCarryFoodForGearMoney(4, 0, 0, false));
        assertFalse(AgentActionService.shouldCarryFoodForGearMoney(0, 0, 0, false));
        assertTrue(AgentActionService.shouldCarryFoodForGearMoney(3, 0, 8, false));
        assertTrue(AgentActionService.shouldCarryFoodForGearMoney(0, 0, 0, true));
        assertTrue(AgentActionService.shouldBuyKebabsForFood(2, 18, 25, 0, 10));
        assertTrue(AgentActionService.shouldBuyKebabsForFood(2, 18, 0, 120, 10));
        assertFalse(AgentActionService.shouldBuyKebabsForFood(18, 18, 25, 120, 10));
        assertFalse(AgentActionService.shouldBuyKebabsForFood(2, 18, 25, 120, 0));
        assertEquals(16, AgentActionService.targetAcquisitionBatchAmount(18, 2, 16));
        assertEquals(0, AgentActionService.targetAcquisitionBatchAmount(18, 18, 16));
        assertEquals(10, AgentActionService.targetAcquisitionBatchAmount(500, 0, 10));
        assertEquals(8, AgentActionService.targetAcquisitionBatchAmount(18, 0, 28, 5, 10, 51));
        assertEquals(0, AgentActionService.targetAcquisitionBatchAmount(18, 0, 28, 5, 10, 9));
        assertEquals(28, AgentActionService.targetAcquisitionBatchAmount(500, 0, 28, 0, 10, 0));
        assertEquals(26, AgentActionService.targetAcquisitionEffectiveFreeSlots(0, 26));
        assertEquals(28, AgentActionService.targetAcquisitionEffectiveFreeSlots(4, 30));
        assertEquals(4, AgentActionService.targetAcquisitionEffectiveFreeSlots(4, -1));
        assertTrue(AgentActionService.shouldBankSuppliesBeforeTargetAcquisition(17, 4, 18, 4, true));
        assertTrue(AgentActionService.shouldBankSuppliesBeforeTargetAcquisition(17, 14, 18, 4, true));
        assertTrue(AgentActionService.shouldBankSuppliesBeforeTargetAcquisition(6, 20, 18, 2, true));
        assertFalse(AgentActionService.shouldBankSuppliesBeforeTargetAcquisition(2, 24, 18, 2, true));
        assertFalse(AgentActionService.shouldBankSuppliesBeforeTargetAcquisition(0, 4, 18, 4, true));
        assertFalse(AgentActionService.shouldBankSuppliesBeforeTargetAcquisition(17, 4, 18, 4, false));
        assertFalse(AgentActionService.shouldBankSuppliesBeforeTargetAcquisition(17, 4, 18, 18, true));
        assertEquals(120, AgentActionService.kebabCoinFloat(18, 2, 10, 1720));
        assertEquals(120, AgentActionService.kebabCoinFloat(18, 2, 10, 1720, 10, 10));
        assertEquals(20, AgentActionService.kebabCoinFloat(18, 2, 10, 20));
        assertEquals(120, AgentActionService.targetAcquisitionRequiredCoins(18, 2, 10, 10, 10, 3, 120));
        assertEquals(336, AgentActionService.targetAcquisitionRequiredCoins(500, 0, 28, 0, 0, 12, 120));
        assertEquals(20, AgentActionService.kebabCoinFloat(18, 0, 24, 10, 10, 0, 10, 3));
        assertEquals(20, AgentActionService.targetAcquisitionCoinFloat(18, 0, 24, 10, 10, 0, 10, 3, 120));
        assertEquals(3, AgentActionService.targetAcquisitionBatchAmount(18, 0, 24, 3, 10, 20));
        assertEquals(336, AgentActionService.targetAcquisitionCoinFloat(500, 0, 28, 50, 5000, 0, 0, 12, 120));
        assertEquals(28, AgentActionService.targetAcquisitionBatchAmount(500, 0, 28, 12, 0, 386));
        assertEquals(6, AgentActionService.targetAcquisitionBatchAmount(500, 0, 28, 12, 10, 82));
        assertTrue(AgentActionService.shouldEarnShopFoodMoneyForTargetAcquisition(2, 18, 0, 0, 120, true));
        assertTrue(AgentActionService.shouldEarnShopFoodMoneyForTargetAcquisition(2, 18, 20, 0, 120, true));
        assertFalse(AgentActionService.shouldEarnShopFoodMoneyForTargetAcquisition(18, 18, 0, 0, 120, true));
        assertFalse(AgentActionService.shouldEarnShopFoodMoneyForTargetAcquisition(2, 18, 120, 0, 120, true));
        assertFalse(AgentActionService.shouldEarnShopFoodMoneyForTargetAcquisition(2, 18, 0, 0, 120, false));
        assertTrue(AgentActionService.shouldDelayTargetAcquisitionTripForFundedBatch(2, 18,
                20, 0, 120, true));
        assertFalse(AgentActionService.shouldDelayTargetAcquisitionTripForFundedBatch(2, 18,
                120, 0, 120, true));
        assertFalse(AgentActionService.shouldDelayTargetAcquisitionTripForFundedBatch(2, 18,
                20, 0, 120, false));
        assertTrue(AgentActionService.shouldPreferTargetFoodAcquisitionOverSmallRawBatch(2, 18, 6, true));
        assertFalse(AgentActionService.shouldPreferTargetFoodAcquisitionOverSmallRawBatch(18, 18, 6, true));
        assertFalse(AgentActionService.shouldPreferTargetFoodAcquisitionOverSmallRawBatch(2, 18, 8, true));
        assertFalse(AgentActionService.shouldPreferTargetFoodAcquisitionOverSmallRawBatch(2, 18, 6, false));
        assertTrue(AgentActionService.shouldPreferTargetShopFoodRestockBeforeBank(2, 18, 0, 6, true, 25));
        assertFalse(AgentActionService.shouldPreferTargetShopFoodRestockBeforeBank(2, 18, 16, 0, true, 25));
        assertFalse(AgentActionService.shouldPreferTargetShopFoodRestockBeforeBank(2, 18, 0, 16, true, 25));
        assertFalse(AgentActionService.shouldPreferTargetShopFoodRestockBeforeBank(2, 18, 0, 6, false, 25));
        assertFalse(AgentActionService.shouldPreferTargetShopFoodRestockBeforeBank(2, 18, 0, 6, true, 10));
        assertTrue(AgentActionService.shouldLiquidateStagedGearMoneyItemsForTarget(1971));
        assertFalse(AgentActionService.shouldLiquidateStagedGearMoneyItemsForTarget(1301));
        assertFalse(AgentActionService.isTargetAcquisitionBlockingSupplyItem(2132)); // Raw beef is restock input.
        assertFalse(AgentActionService.isTargetAcquisitionBlockingSupplyItem(1971)); // Kebabs are current food.
        assertTrue(AgentActionService.isTargetAcquisitionBlockingSupplyItem(526)); // Bones can be banked.
        assertEquals(3, AgentActionService.currentShopItemPrice(null, 1971, 3));
        assertTrue(AgentActionService.hasEnoughCoinsForTargetAcquisitionTrip(10, 15, 10, 10, 5));
        assertFalse(AgentActionService.hasEnoughCoinsForTargetAcquisitionTrip(10, 14, 10, 10, 5));
        assertTrue(AgentActionService.hasEnoughCoinsForTargetAcquisitionTrip(10, 13, 10, 10, 3));
        assertFalse(AgentActionService.hasEnoughCoinsForTargetAcquisitionTrip(10, 12, 10, 10, 3));
        assertTrue(AgentActionService.shouldWithdrawKebabCoinFloat(7, 120, 21742, 11, false, false));
        assertTrue(AgentActionService.shouldWithdrawKebabCoinFloat(7, 120, 21742, 0, true, false));
        assertFalse(AgentActionService.shouldWithdrawKebabCoinFloat(7, 120, 0, 11, false, false));
        assertFalse(AgentActionService.shouldWithdrawKebabCoinFloat(120, 120, 21742, 11, true, false));
        assertFalse(AgentActionService.shouldWithdrawKebabCoinFloat(7, 120, 21742, 11, false, true));
    }

    @Test
    public void durableGoalUsesGenericTargetAcquisitionBatchPlans() {
        AgentActionService.TargetAcquisitionPlan plan = AgentActionService.targetAcquisitionPlan(
                1971, "kebab restock", 18, 2, 6, 10, 120, 0, 10, 10, 3, 120, true);

        assertEquals(1971, plan.itemId());
        assertEquals("kebab restock", plan.targetName());
        assertEquals(16, plan.effectiveFreeSlots());
        assertEquals(16, plan.desiredBatchAmount());
        assertEquals(6, plan.immediateBatchAmount());
        assertEquals(6, plan.affordableBatchAmount());
        assertEquals(120, plan.requiredCoins());
        assertEquals(120, plan.coinFloat());
        assertFalse(plan.shouldEarnMoneyBeforeTrip());
        assertFalse(plan.shouldDelayTripForFundedBatch());
        assertTrue(plan.hasEnoughCoinsForTrip());
        assertTrue(plan.shouldSellCarriedItemsBeforeShopTrip());

        AgentActionService.TargetAcquisitionPlan unfunded = AgentActionService.targetAcquisitionPlan(
                1971, "kebab restock", 18, 2, 16, 0, 20, 0, 10, 10, 3, 120, true);
        assertTrue(unfunded.shouldEarnMoneyBeforeTrip());
        assertTrue(unfunded.shouldDelayTripForFundedBatch());
        assertFalse(unfunded.hasEnoughCoinsForTrip());
        assertFalse(unfunded.shouldSellCarriedItemsBeforeShopTrip());

        AgentActionService.TargetAcquisitionPlan partialKebabTrip = AgentActionService.targetAcquisitionPlan(
                1971, "kebab restock", 18, 2, 16, 0, 35, 0, 10, 10, 3, 120, false);
        assertFalse(partialKebabTrip.shouldEarnMoneyBeforeTrip());
        assertFalse(partialKebabTrip.hasEnoughCoinsForTrip());

        AgentActionService.TargetAcquisitionPlan arrows = AgentActionService.targetAcquisitionPlan(
                882, "bronze arrow restock", 500, 120, 9, 20, 1000, 0, 0, 50, 2, 0, true);
        assertEquals(882, arrows.itemId());
        assertEquals("bronze arrow restock", arrows.targetName());
        assertEquals(28, arrows.desiredBatchAmount());
        assertEquals(9, arrows.immediateBatchAmount());
        assertEquals(9, arrows.affordableBatchAmount());
        assertEquals(106, arrows.requiredCoins());
        assertFalse(arrows.shouldEarnMoneyBeforeTrip());
        assertTrue(arrows.shouldSellCarriedItemsBeforeShopTrip());
    }

    @Test
    public void durableGoalSkipsEmptyPeriodicGearChecks() {
        assertFalse(AgentActionService.shouldCheckCarriedCombatGear(60, 0));
        assertFalse(AgentActionService.shouldCheckCarriedCombatGear(61, 1));
        assertTrue(AgentActionService.shouldCheckCarriedCombatGear(60, 1));
    }

    @Test
    public void durableGoalDoesNotRebankRawFoodDuringTargetAcquisitionPrep() {
        Player player = new Player(0) {
        };
        player.playerItems[0] = 2133; // Raw beef.
        player.playerItemsN[0] = 6;
        player.playerItems[1] = 527; // Bones.
        player.playerItemsN[1] = 4;
        player.playerItems[2] = 1972; // Kebab.
        player.playerItemsN[2] = 1;

        assertEquals(4, AgentActionService.countInventoryTargetAcquisitionBlockingSupplies(player));
    }

    @Test
    public void durableGoalCountsStagedMaterialsTowardTargetAcquisitionFunding() {
        Player player = new Player(0) {
        };
        player.playerItems[0] = 441; // Iron ore.
        player.playerItemsN[0] = 25;
        player.bankItems[0] = 441; // Iron ore.
        player.bankItemsN[0] = 25;
        player.bankItems[1] = 2354; // Steel bar.
        player.bankItemsN[1] = 1;

        assertEquals(75, AgentActionService.estimatedInventoryStagedGearMoneyItemCoins(player));
        assertEquals(120, AgentActionService.estimatedBankStagedGearMoneyItemCoins(player));
        assertEquals(26, AgentActionService.countBankStagedGearMoneyItems(player));
        assertEquals(2353, AgentActionService.bestBankStagedGearMoneyItem(player));
        assertTrue(AgentActionService.shouldSellGearMoneyBatch(0,
                AgentActionService.estimatedInventoryStagedGearMoneyItemCoins(player),
                AgentActionService.estimatedBankStagedGearMoneyItemCoins(player), 120));
        assertFalse(AgentActionService.shouldSellGearMoneyBatch(0,
                AgentActionService.estimatedInventoryStagedGearMoneyItemCoins(player), 0, 120));
    }

    @Test
    public void durableGoalReattachesOnlyToMatchingOnlinePlayer() {
        Player player = new Player(7) {
        };
        player.playerId = 7;
        player.playerName = "MrGem";
        player.isActive = true;
        player.disconnected = false;

        assertTrue(AgentActionService.isGoalPlayer(player, 7, "mrgem"));
        assertFalse(AgentActionService.isGoalPlayer(player, 8, "mrgem"));
        assertFalse(AgentActionService.isGoalPlayer(player, 7, "Other"));

        player.disconnected = true;
        assertFalse(AgentActionService.isGoalPlayer(player, 7, "mrgem"));
    }

    @Test
    public void durableGoalRetreatsFromNonCombatThreatWhenOutOfFood() {
        assertTrue(AgentActionService.shouldRetreatNonCombatThreatForFood(15, 30, 0, 9));
        assertFalse(AgentActionService.shouldRetreatNonCombatThreatForFood(21, 30, 0, 9));
        assertFalse(AgentActionService.shouldRetreatNonCombatThreatForFood(15, 30, 1, 9));
    }

    @Test
    public void restockFoodSkipsStalledSupplyDeposit() {
        JsonObject stackedDeposit = new JsonObject();
        stackedDeposit.addProperty("deposited", 3);
        stackedDeposit.addProperty("depositedAmount", 55);
        assertEquals(3, AgentActionService.depositedInventoryItems(stackedDeposit));
        JsonObject legacyDeposit = new JsonObject();
        legacyDeposit.addProperty("depositedAmount", 55);
        assertEquals(55, AgentActionService.depositedInventoryItems(legacyDeposit));

        assertTrue(AgentActionService.supplyDepositMadeProgress(10, 3, 7));
        assertFalse(AgentActionService.supplyDepositMadeProgress(10, 10, 10));
        assertFalse(AgentActionService.supplyDepositMadeProgress(10, 0, 10));
        assertFalse(AgentActionService.shouldDepositSuppliesDuringFoodRestock(3, 4));
        assertTrue(AgentActionService.shouldDepositSuppliesDuringFoodRestock(3, 0));
        assertTrue(AgentActionService.shouldDepositSuppliesDuringFoodRestock(18, 4));
        assertFalse(AgentActionService.shouldDepositSuppliesDuringFoodRestock(10, 20));
        assertFalse(AgentActionService.shouldDepositSuppliesDuringFoodRestock(0, 0));
        assertFalse(AgentActionService.shouldBankCombatSupplyCount(1, 4));
        assertTrue(AgentActionService.shouldBankCombatSupplyCount(1, 0));
        assertFalse(AgentActionService.shouldBankCombatSupplyCount(18, 4));
        assertTrue(AgentActionService.shouldBankCombatSupplyCount(18, 2));
        assertFalse(AgentActionService.shouldVisitBankForFood(10, 0, 2, true, true, 0, 8, false));
        assertFalse(AgentActionService.shouldVisitBankForFood(7, 0, 2, true, true, 0, 16, false));
        assertTrue(AgentActionService.shouldVisitBankForFood(2, 0, 8, true, true, 0, 16, true));
        assertTrue(AgentActionService.shouldVisitBankForFood(0, 0, 0, false, true, 0, 16, false));
        assertTrue(AgentActionService.shouldCookCarriedRawFood(3, 8, 3, 18, false, true, false, true));
        assertTrue(AgentActionService.shouldCookCarriedRawFood(1, 12, 9, 18, false, false, false, false));
        assertFalse(AgentActionService.shouldCookCarriedRawFood(3, 8, 3, 18, false, false, false, false));
    }

    @Test
    public void restockFoodCanFallbackToLumbridgeCowsWhenFishingRouteIsBlocked() {
        assertTrue(AgentActionService.shouldGatherBeefInsteadOfFishingFromLumbridgeSouth(3266, 3206, 1, 0, 18));
        assertTrue(AgentActionService.shouldGatherBeefInsteadOfFishingFromLumbridgeSouth(3261, 3227, 1, 0, 18));
        assertFalse(AgentActionService.shouldGatherBeefInsteadOfFishingFromLumbridgeSouth(3266, 3206, 10, 0, 18));
        assertFalse(AgentActionService.shouldGatherBeefInsteadOfFishingFromLumbridgeSouth(3266, 3206, 1, 8, 18));
        assertFalse(AgentActionService.shouldGatherBeefInsteadOfFishingFromLumbridgeSouth(3230, 3219, 1, 0, 18));
        assertTrue(AgentActionService.isRestockRawFoodItem(2132)); // raw beef
        assertTrue(AgentActionService.isRestockRawFoodItem(2138)); // raw chicken
        assertFalse(AgentActionService.isRestockRawFoodItem(1739)); // cowhide is banked separately
        assertTrue(AgentActionService.isCombatSupplyItemForBanking(1739)); // cowhide
        assertTrue(AgentActionService.isCombatSupplyItemForBanking(526)); // bones
    }

    @Test
    public void durableGoalStepsWestOutOfCoalScorpionPocketBeforeBankRoute() {
        assertTrue(AgentActionService.isVarrockCoalMineDangerRetreatTile(3301, 3283));
        assertTrue(AgentActionService.isVarrockCoalMineDangerRetreatTile(3301, 3317));
        assertFalse(AgentActionService.isVarrockCoalMineDangerRetreatTile(3285, 3317));
        assertTrue(AgentActionService.isVarrockCoalMineEscapeCorridor(3289, 3277));
        assertTrue(AgentActionService.isVarrockCoalMineEscapeCorridor(3285, 3283));
        assertFalse(AgentActionService.isVarrockCoalMineEscapeCorridor(3250, 3275));
        assertFalse(AgentActionService.isVarrockCoalMineEscapeCorridor(3261, 3322));
        assertEquals(3283, AgentActionService.varrockCoalMineWestRetreatY(3278));
        assertEquals(3317, AgentActionService.varrockCoalMineWestRetreatY(3317));
        assertEquals(3325, AgentActionService.varrockCoalMineWestRetreatY(3330));
        assertRetreatTarget(3285, 3283, AgentActionService.varrockCoalMineRetreatTarget(3301, 3278));
        assertRetreatTarget(3285, 3317, AgentActionService.varrockCoalMineRetreatTarget(3301, 3317));
        assertRetreatTarget(3261, 3322, AgentActionService.varrockCoalMineRetreatTarget(3269, 3275));
    }

    private static void assertRetreatTarget(int expectedX, int expectedY, int[] actual) {
        assertTrue(actual != null);
        assertEquals(expectedX, actual[0]);
        assertEquals(expectedY, actual[1]);
    }

    @Test
    public void durableGoalProcessesPartialCarriedMoneyBatchWhenReturningToCombat() {
        assertFalse(AgentActionService.shouldSmithGearMoneyBars(3, 5, 10, false));
        assertTrue(AgentActionService.shouldSmithGearMoneyBars(3, 5, 10, true));
        assertFalse(AgentActionService.shouldSmithGearMoneyBars(0, 5, 1, true));
    }

    @Test
    public void durableGoalWaitsForHigherQualitySmithingBatchDuringGearMoney() {
        assertFalse(AgentActionService.shouldSmithGearMoneyBars(1, 1, 3, 10, false));
        assertFalse(AgentActionService.shouldSmithGearMoneyBars(2, 1, 3, 10, false));
        assertTrue(AgentActionService.shouldSmithGearMoneyBars(3, 1, 3, 10, false));
        assertTrue(AgentActionService.shouldSmithGearMoneyBars(1, 1, 3, 10, true));
    }

    @Test
    public void durableGoalCapsLocalMiningRespawnWaits() {
        JsonObject waitArgs = AgentActionService.gearMoneyOreArgs("iron", 3285, 3351, true);
        assertTrue(waitArgs.get("waitForLocalRespawn").getAsBoolean());
        assertEquals(8, waitArgs.get("maxDistance").getAsInt());

        JsonObject widerScanArgs = AgentActionService.gearMoneyOreArgs("iron", 3285, 3351, false);
        assertFalse(widerScanArgs.has("waitForLocalRespawn"));
        assertFalse(widerScanArgs.has("maxDistance"));
    }

    @Test
    public void durableGoalReacquiresCurrentAttackerBeforeNonCombatWork() {
        assertEquals(12, AgentActionService.activeCombatNpcIndex(12, 34, 56, 78));
        assertEquals(34, AgentActionService.activeCombatNpcIndex(0, 34, 56, 78));
        assertEquals(78, AgentActionService.activeCombatNpcIndex(0, 0, 56, 78));
        assertEquals(56, AgentActionService.activeCombatNpcIndex(0, 0, 56, 0));
        assertEquals(-1, AgentActionService.activeCombatNpcIndex(0, 0, 0, 0));

        assertTrue(AgentActionService.shouldWaitForActiveCombatThreatClearance(12, 12, 12, 0, 12, true));
        assertTrue(AgentActionService.shouldWaitForActiveCombatThreatClearance(12, 12, 0, 0, 12, true));
        assertFalse(AgentActionService.shouldWaitForActiveCombatThreatClearance(12, 0, 0, 0, 12, true));
        assertFalse(AgentActionService.shouldWaitForActiveCombatThreatClearance(12, 12, 12, 0, 12, false));
        assertFalse(AgentActionService.shouldWaitForActiveCombatThreatClearance(-1, 0, 0, 0, 0, true));
    }

    @Test
    public void durableGoalUsesOnlyActiveThreatFieldsForNonCombatWork() {
        assertFalse(AgentActionService.hasActiveCombatThreat(0, 0, 0));
        assertTrue(AgentActionService.hasActiveCombatThreat(918, 0, 0));
        assertTrue(AgentActionService.hasActiveCombatThreat(0, 12, 0));
        assertTrue(AgentActionService.hasActiveCombatThreat(0, 0, 12));
    }

    @Test
    public void durableGoalCarriesFoodForRiskyGearMoneyRoutes() {
        assertTrue(AgentActionService.shouldCarryFoodForGearMoney(0, 5));
        assertTrue(AgentActionService.shouldCarryFoodForGearMoney(1, 5));
        assertFalse(AgentActionService.shouldCarryFoodForGearMoney(4, 5));
        assertFalse(AgentActionService.shouldCarryFoodForGearMoney(0, 0));
    }

    @Test
    public void durableGoalRecoversStaleMovementInsteadOfWaitingForever() {
        assertFalse(AgentActionService.isStaleMovementWait(3275, 3195, 3275, 3195, 3));
        assertTrue(AgentActionService.isStaleMovementWait(3275, 3195, 3275, 3195, 4));
        assertFalse(AgentActionService.isStaleMovementWait(3276, 3195, 3275, 3195, 4));
        assertFalse(AgentActionService.isExceededMovementWait(19));
        assertTrue(AgentActionService.isExceededMovementWait(20));
    }

    @Test
    public void durableGoalDetectsRouteOscillationInsteadOfRunningBackAndForth() {
        assertTrue(AgentActionService.isRouteOscillation(3305, 3185, 3289, 3189, 3305, 3185));
        assertFalse(AgentActionService.isRouteOscillation(3313, 3183, 3305, 3185, 3289, 3189));
        assertFalse(AgentActionService.shouldBlockRouteOscillation(1));
        assertTrue(AgentActionService.shouldBlockRouteOscillation(2));
    }

    @Test
    public void durableGoalDetectsStaleRoutesInsteadOfRepeatingWalks() {
        assertFalse(AgentActionService.isRouteStale(3013, 3390, 3013, 3390, 3));
        assertTrue(AgentActionService.isRouteStale(3013, 3390, 3013, 3390, 4));
        assertFalse(AgentActionService.isRouteStale(3014, 3390, 3013, 3390, 4));
        assertFalse(AgentActionService.shouldBlockRouteStale(3));
        assertTrue(AgentActionService.shouldBlockRouteStale(4));
    }

    @Test
    public void durableGoalDefersRepeatedNoMovePickaxeRoutes() {
        assertFalse(AgentActionService.shouldDeferPickaxeRoute(7));
        assertTrue(AgentActionService.shouldDeferPickaxeRoute(8));
    }

    @Test
    public void durableGoalRecognizesDwarvenMinePickaxeRouteStates() {
        assertTrue(AgentActionService.isNearDwarvenMineSurfaceLadder(3019, 3450));
        assertTrue(AgentActionService.isNearDwarvenMineSurfaceLadder(3024, 3450));
        assertFalse(AgentActionService.isNearDwarvenMineSurfaceLadder(3023, 3420));
        assertTrue(AgentActionService.isDwarvenMineSurfaceTrapTile(3078, 3493));
        assertFalse(AgentActionService.isDwarvenMineSurfaceTrapTile(3076, 3492));
        assertTrue(AgentActionService.isNearDwarvenMineUndergroundLadder(3020, 9850));
        assertTrue(AgentActionService.isNearDwarvenMineUndergroundLadder(3018, 9849));
        assertFalse(AgentActionService.isNearDwarvenMineUndergroundLadder(2998, 9843));
        assertTrue(AgentActionService.isInDwarvenMine(2998, 9843));
        assertTrue(AgentActionService.isInDwarvenMine(3077, 9893));
        assertFalse(AgentActionService.isInDwarvenMine(2998, 3443));
    }

    @Test
    public void durableGoalUsesAlKharidStoreWhenStrandedEastOfGate() {
        assertEquals("al kharid general store", AgentActionService.gearMoneyGeneralStoreLandmark(3268, 3227));
        assertEquals("al kharid general store", AgentActionService.gearMoneyGeneralStoreLandmark(3274, 3186));
        assertEquals("varrock general store", AgentActionService.gearMoneyGeneralStoreLandmark(3252, 3236));
        assertEquals("varrock general store", AgentActionService.gearMoneyGeneralStoreLandmark(3285, 3365));
    }

    @Test
    public void durableGoalUsesBankCoinsBeforeSellingBarsForHammer() {
        assertFalse(AgentActionService.shouldSellMaterialsForHammerCoins(0, 25, true, 6));
        assertFalse(AgentActionService.shouldSellMaterialsForHammerCoins(1, 0, true, 6));
        assertFalse(AgentActionService.shouldSellMaterialsForHammerCoins(0, 0, false, 6));
        assertFalse(AgentActionService.shouldSellMaterialsForHammerCoins(0, 0, true, 0));
        assertTrue(AgentActionService.shouldSellMaterialsForHammerCoins(0, 0, true, 6));
    }

    @Test
    public void durableGoalSellsOneLocalOreForHammerBeforeDumpingBars() {
        assertTrue(AgentActionService.shouldSellLocalSeedItemForHammerCoins(0, true, 440));
        assertTrue(AgentActionService.shouldSellLocalSeedItemForHammerCoins(1, true, 440));
        assertTrue(AgentActionService.shouldSellLocalSeedItemForHammerCoins(24, true, 2349));
        assertFalse(AgentActionService.shouldSellLocalSeedItemForHammerCoins(25, true, 2349));
        assertFalse(AgentActionService.shouldSellLocalSeedItemForHammerCoins(0, false, 440));
        assertFalse(AgentActionService.shouldSellLocalSeedItemForHammerCoins(0, true, -1));
        assertEquals(440, AgentActionService.hammerSeedItemForCoins(12, 0, 0, 6, 350));
        assertEquals(436, AgentActionService.hammerSeedItemForCoins(0, 4, 2, 6, 350));
        assertEquals(438, AgentActionService.hammerSeedItemForCoins(0, 2, 4, 6, 350));
        assertEquals(2349, AgentActionService.hammerSeedItemForCoins(0, 0, 0, 6, 350));
        assertEquals(2349, AgentActionService.hammerSeedItemForCoins(0, 0, 0, 6, 0));
    }

    @Test
    public void durableGoalSellsOneLocalOreForAlKharidGateToll() {
        assertTrue(AgentActionService.shouldSellLocalSeedItemForGateToll(0, true, 2349));
        assertTrue(AgentActionService.shouldSellLocalSeedItemForGateToll(9, true, 2349));
        assertFalse(AgentActionService.shouldSellLocalSeedItemForGateToll(10, true, 2349));
        assertFalse(AgentActionService.shouldSellLocalSeedItemForGateToll(0, false, 2349));
        assertFalse(AgentActionService.shouldSellLocalSeedItemForGateToll(0, true, -1));
    }

    @Test
    public void durableGoalWithdrawsBankedCoinsForAlKharidTravelFloat() {
        assertTrue(AgentActionService.shouldWithdrawGearMoneyTravelCoins(0, 25, 1, true));
        assertTrue(AgentActionService.shouldWithdrawGearMoneyTravelCoins(9, 25, 1, true));
        assertTrue(AgentActionService.shouldWithdrawGearMoneyTravelCoins(10, 25, 1, true));
        assertTrue(AgentActionService.shouldWithdrawGearMoneyTravelCoins(24, 25, 1, true));
        assertTrue(AgentActionService.shouldWithdrawGearMoneyTravelCoins(17, 25, 0, true));
        assertFalse(AgentActionService.shouldWithdrawGearMoneyTravelCoins(25, 25, 1, true));
        assertFalse(AgentActionService.shouldWithdrawGearMoneyTravelCoins(0, 0, 1, true));
        assertFalse(AgentActionService.shouldWithdrawGearMoneyTravelCoins(0, 25, 0, true));
        assertFalse(AgentActionService.shouldWithdrawGearMoneyTravelCoins(0, 25, 1, false));
    }

    @Test
    public void durableGoalSellsCarriedOresAfterRepeatedFurnaceRouteStalls() {
        assertTrue(AgentActionService.shouldSellCarriedGearMoneyAfterFurnaceStall(8, 27, false));
        assertFalse(AgentActionService.shouldSellCarriedGearMoneyAfterFurnaceStall(8, 27, true));
        assertFalse(AgentActionService.shouldSellCarriedGearMoneyAfterFurnaceStall(2, 27, false));
        assertFalse(AgentActionService.shouldSellCarriedGearMoneyAfterFurnaceStall(8, 1, false));
    }

    @Test
    public void durableGoalBanksUnsmithedBarsBeforeAnotherOreRun() {
        assertTrue(AgentActionService.shouldBankProcessedBarsBeforeMoreMining(1, false, false, true));
        assertTrue(AgentActionService.shouldBankProcessedBarsBeforeMoreMining(4, false, false, false));
        assertFalse(AgentActionService.shouldBankProcessedBarsBeforeMoreMining(3, false, false, false));
        assertFalse(AgentActionService.shouldBankProcessedBarsBeforeMoreMining(4, true, false, true));
        assertFalse(AgentActionService.shouldBankProcessedBarsBeforeMoreMining(4, false, true, true));
        assertFalse(AgentActionService.shouldBankProcessedBarsBeforeMoreMining(0, false, false, true));
    }

    @Test
    public void durableGoalStagesMiningMaterialsBeforeProcessingForTarget() {
        assertFalse(AgentActionService.shouldProcessGearMoneyBatch(false, false));
        assertTrue(AgentActionService.shouldProcessGearMoneyBatch(true, false));
        assertTrue(AgentActionService.shouldProcessGearMoneyBatch(false, true));
        assertTrue(AgentActionService.shouldProcessGearMoneyBatch(false, false, true));
        assertTrue(AgentActionService.shouldProcessGearMoneyBatch(true, false, false));
        assertTrue(AgentActionService.shouldProcessGearMoneyBatch(false, true, false));
        assertFalse(AgentActionService.shouldProcessGearMoneyBatch(false, false, false));
        assertTrue(AgentActionService.shouldStopMiningForFundedGearMoneyProcessing(true, true));
        assertFalse(AgentActionService.shouldStopMiningForFundedGearMoneyProcessing(true, false));
        assertFalse(AgentActionService.shouldStopMiningForFundedGearMoneyProcessing(false, true));

        assertTrue(AgentActionService.shouldBankGearMoneyMaterialsBeforeProcessing(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, false, false, false, 0, false));
        assertTrue(AgentActionService.shouldBankGearMoneyMaterialsBeforeProcessing(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, false, false, false, 0, true));
        assertFalse(AgentActionService.shouldBankGearMoneyMaterialsBeforeProcessing(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, false, false, false, 5, false));
        assertFalse(AgentActionService.shouldBankGearMoneyMaterialsBeforeProcessing(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, true, false, false, 0, false));
        assertFalse(AgentActionService.shouldBankGearMoneyMaterialsBeforeProcessing(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, false, true, false, 0, false));
        assertFalse(AgentActionService.shouldBankGearMoneyMaterialsBeforeProcessing(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, false, false, true, 0, false));
        assertFalse(AgentActionService.shouldBankGearMoneyMaterialsBeforeProcessing(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 0, false, false, false, 0, false));
        assertFalse(AgentActionService.shouldBankGearMoneyMaterialsBeforeProcessing(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMITH, 18, false, false, false, 0, false));
        assertTrue(AgentActionService.isBalancedSteelSmeltingBatch(7, 14));
        assertFalse(AgentActionService.isBalancedSteelSmeltingBatch(7, 13));
        assertFalse(AgentActionService.shouldPrepareSteelSmeltingInputs(35, 6, 10, 33, 64, 5, 0, 0,
                false, 3303, 3300));
        assertTrue(AgentActionService.shouldPrepareSteelSmeltingInputs(35, 6, 10, 33, 64, 5, 0, 0,
                false, 3303, 3300, true));
    }

    @Test
    public void durableGoalDelaysProductionUntilMiningLoadIsFuller() {
        assertTrue(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, 4, false, false, false, false, 3286, 3368));
        assertFalse(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMITH, 18, 4, false, false, false, false, 3286, 3368));
        assertFalse(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, 0, false, false, false, false, 3286, 3368));
        assertFalse(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, 4, true, false, false, false, 3286, 3368));
        assertTrue(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, 4, false, true, false, false, 3286, 3368));
        assertTrue(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, 4, false, true, false, false, 3286, 3368, true));
        assertFalse(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, 4, false, true, false, false, 3274, 3186));
        assertFalse(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 18, 4, false, false, true, false, 3286, 3368));
        assertFalse(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 21, 1, false, false, false, true, 3260, 3420));
        assertFalse(AgentActionService.shouldDelayGearMoneyProductionForFullerLoad(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 0, 4, false, false, false, false, 3286, 3368));
    }

    @Test
    public void durableGoalSmeltsStagedOreBeforeSmithingBars() {
        assertTrue(AgentActionService.shouldBankSmeltedBarsBeforeStagedSmithing(8, true, false));
        assertFalse(AgentActionService.shouldBankSmeltedBarsBeforeStagedSmithing(0, true, false));
        assertFalse(AgentActionService.shouldBankSmeltedBarsBeforeStagedSmithing(8, false, false));
        assertFalse(AgentActionService.shouldBankSmeltedBarsBeforeStagedSmithing(8, true, true));
        assertTrue(AgentActionService.shouldBankSmeltedBarsBeforeStagedSmithing(8, true, false, true));
        assertTrue(AgentActionService.shouldBankSmeltedBarsBeforeStagedSmithing(8, true, false, true, 14));
        assertFalse(AgentActionService.shouldBankSmeltedBarsBeforeStagedSmithing(21, true, false, true, 0));
        assertTrue(AgentActionService.shouldSmithCarriedBarsBeforeResidualSmelting(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, true, 21, 0, 0, true));
        assertFalse(AgentActionService.shouldSmithCarriedBarsBeforeResidualSmelting(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, true, 21, 3, 0, true));
        assertFalse(AgentActionService.shouldSmithCarriedBarsBeforeResidualSmelting(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, true, 21, 0, 14, true));
        assertFalse(AgentActionService.shouldSmithCarriedBarsBeforeResidualSmelting(
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, false, 21, 0, 0, true));

        Player player = new Player(0) {
        };
        player.playerXP[Constants.SMITHING] = 28076;
        player.bankItems[0] = 441; // Iron ore.
        player.bankItemsN[0] = 9;
        player.bankItems[1] = 454; // Coal.
        player.bankItemsN[1] = 1;
        assertFalse(AgentActionService.hasBankedSmeltableGearMoneyOresForBar(player, 2353));
        assertTrue(AgentActionService.hasBankedSmeltableGearMoneyOresForBar(player, 2351));

        player.bankItemsN[1] = 2;
        assertTrue(AgentActionService.hasBankedSmeltableGearMoneyOresForBar(player, 2353));
    }

    @Test
    public void durableGoalDoesNotRestartMiningAfterProcessingLatch() {
        assertTrue(AgentActionService.shouldBankCarriedBatchAfterProcessingStarted(true, 7));
        assertFalse(AgentActionService.shouldBankCarriedBatchAfterProcessingStarted(false, 7));
        assertFalse(AgentActionService.shouldBankCarriedBatchAfterProcessingStarted(true, 0));
        assertFalse(AgentActionService.shouldBankCarriedBatchAfterProcessingStarted(true, 7, true));

        assertEquals(2353, AgentActionService.gearMoneyProcessableWithdrawalItem(true, 440, 2353));
        assertEquals(440, AgentActionService.gearMoneyProcessableWithdrawalItem(true, 440, -1));
        assertFalse(AgentActionService.shouldRememberRawMaterialsBankedAfterProcessingStarted(true, 0));
        assertFalse(AgentActionService.shouldRememberRawMaterialsBankedAfterProcessingStarted(false, 1));
        assertTrue(AgentActionService.shouldRememberRawMaterialsBankedAfterProcessingStarted(true, 1));

        assertTrue(AgentActionService.shouldBankCarriedMaterialsAfterProcessingStarted(true, 7,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE, 50));
        assertFalse(AgentActionService.shouldBankCarriedMaterialsAfterProcessingStarted(false, 7,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE, 50));
        assertFalse(AgentActionService.shouldBankCarriedMaterialsAfterProcessingStarted(true, 0,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE, 50));
        assertFalse(AgentActionService.shouldBankCarriedMaterialsAfterProcessingStarted(true, 7,
                AgentActionService.GEAR_MONEY_PRODUCTION_SMELT, 50));
        assertFalse(AgentActionService.shouldBankCarriedMaterialsAfterProcessingStarted(true, 7,
                AgentActionService.GEAR_MONEY_PRODUCTION_NONE, 0));
    }

    @Test
    public void durableGoalTopsUpCarriedSaleBatchBeforeSelling() {
        assertTrue(AgentActionService.shouldWithdrawMoreStoredGearMoneySaleItems(15, 10, 6,
                false, true, false));
        assertTrue(AgentActionService.shouldWithdrawMoreStoredGearMoneySaleItems(15, 10, 6,
                true, false, false));
        assertFalse(AgentActionService.shouldWithdrawMoreStoredGearMoneySaleItems(0, 10, 6,
                false, true, false));
        assertFalse(AgentActionService.shouldWithdrawMoreStoredGearMoneySaleItems(15, 0, 6,
                false, true, false));
        assertFalse(AgentActionService.shouldWithdrawMoreStoredGearMoneySaleItems(15, 10, 0,
                false, true, false));
        assertFalse(AgentActionService.shouldWithdrawMoreStoredGearMoneySaleItems(15, 10, 6,
                false, true, true));
        assertFalse(AgentActionService.shouldWithdrawMoreStoredGearMoneySaleItems(15, 10, 6,
                false, false, false));

        assertTrue(AgentActionService.shouldStopMiningForFundedTargetAcquisitionSale(true, true, true));
        assertFalse(AgentActionService.shouldStopMiningForFundedTargetAcquisitionSale(false, true, true));
        assertFalse(AgentActionService.shouldStopMiningForFundedTargetAcquisitionSale(true, false, true));
        assertFalse(AgentActionService.shouldStopMiningForFundedTargetAcquisitionSale(true, true, false));

        assertTrue(AgentActionService.shouldWithdrawTargetAcquisitionSaleBatch(true, true, 23, 75, 4));
        assertTrue(AgentActionService.shouldWithdrawTargetAcquisitionSaleBatch(true, true, 0, 75, 20));
        assertFalse(AgentActionService.shouldWithdrawTargetAcquisitionSaleBatch(false, true, 23, 75, 4));
        assertFalse(AgentActionService.shouldWithdrawTargetAcquisitionSaleBatch(true, false, 23, 75, 4));
        assertFalse(AgentActionService.shouldWithdrawTargetAcquisitionSaleBatch(true, true, 23, 0, 4));
        assertFalse(AgentActionService.shouldWithdrawTargetAcquisitionSaleBatch(true, true, 23, 75, 0));

        assertTrue(AgentActionService.shouldSellTargetAcquisitionSaleBatch(true, true, 23));
        assertFalse(AgentActionService.shouldSellTargetAcquisitionSaleBatch(false, true, 23));
        assertFalse(AgentActionService.shouldSellTargetAcquisitionSaleBatch(true, false, 23));
        assertFalse(AgentActionService.shouldSellTargetAcquisitionSaleBatch(true, true, 0));
    }

    @Test
    public void durableGoalTopsUpBarsBeforeWalkingToAnvils() {
        assertTrue(AgentActionService.shouldTopUpGearMoneySmithingBars(5, 49, 16, false));
        assertFalse(AgentActionService.shouldTopUpGearMoneySmithingBars(0, 49, 16, false));
        assertFalse(AgentActionService.shouldTopUpGearMoneySmithingBars(5, 0, 16, false));
        assertFalse(AgentActionService.shouldTopUpGearMoneySmithingBars(5, 49, 0, false));
        assertFalse(AgentActionService.shouldTopUpGearMoneySmithingBars(5, 49, 16, true));
    }

    @Test
    public void durableGoalKeepsMiningUntilFundedSteelBatchIsStaged() {
        int targetBars = AgentActionService.requiredGearMoneyBatchBars(37, 2353, 5000);

        assertTrue(targetBars > 9);
        assertFalse(AgentActionService.isPreferredGearMoneyBatchStaged(46, 37,
                0, 0, 9, 18, 0, 0, 0, 0, 5000, 0));
        assertTrue(AgentActionService.isPreferredGearMoneyBatchStaged(46, 37,
                0, 0, targetBars, targetBars * 2, 0, 0, 0, 0, 5000, 0));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(46, 37,
                0, 0, 9, 18, 24, 3285, 3355, 0, 5000, 0, 0, 0, 0));
    }

    @Test
    public void durableGoalLeavesSmallBankedBarFragmentsForLaterBatches() {
        assertFalse(AgentActionService.shouldUseBankedGearMoneyBarsForProcessing(37, 2351, 2));
        assertTrue(AgentActionService.shouldUseBankedGearMoneyBarsForProcessing(37, 2351, 3));
        assertTrue(AgentActionService.shouldUseBankedGearMoneyBarsForProcessing(37, 2353, 2));
        assertFalse(AgentActionService.shouldUseBankedGearMoneyBarsForProcessing(37, 2353, 1));
    }

    @Test
    public void durableGoalEstimatesSmithingPotentialFromStagedBars() {
        assertEquals(55, AgentActionService.estimatedGearMoneySmithingPotentialSellCoins(1, 2351, 5));
        assertTrue(AgentActionService.estimatedGearMoneySmithingPotentialSellCoins(26, 2351, 12) >= 132);
    }

    @Test
    public void durableGoalEstimatesMinedSellValueConservatively() {
        assertEquals(2, AgentActionService.estimatedGearMoneySellCoins(436)); // copper ore
        assertEquals(2, AgentActionService.estimatedGearMoneySellCoins(438)); // tin ore
        assertEquals(3, AgentActionService.estimatedGearMoneySellCoins(440)); // iron ore
        assertEquals(5, AgentActionService.estimatedGearMoneySellCoins(2349)); // bronze bar
        assertEquals(11, AgentActionService.estimatedGearMoneySellCoins(2351)); // iron bar
        assertEquals(45, AgentActionService.estimatedGearMoneySellCoins(2353)); // steel bar
        assertEquals(5, AgentActionService.estimatedGearMoneySellCoins(1422)); // bronze mace, one bronze bar
        assertEquals(0, AgentActionService.estimatedGearMoneySellCoins(526)); // bones are not sold for gear money
    }

    @Test
    public void durableGoalPrioritizesFundedPickaxeUpgradeBeforeArmor() {
        assertTrue(AgentActionService.shouldPrioritizePickaxeUpgradeOverGear(1159, 1271)); // mithril helm, adamant pickaxe
        assertTrue(AgentActionService.shouldPrioritizePickaxeUpgradeOverGear(1121, 1271)); // mithril platebody, adamant pickaxe
        assertFalse(AgentActionService.shouldPrioritizePickaxeUpgradeOverGear(1301, 1271)); // adamant longsword stays first
        assertFalse(AgentActionService.shouldPrioritizePickaxeUpgradeOverGear(1159, -1));
        assertFalse(AgentActionService.shouldPrioritizePickaxeUpgradeOverGear(-1, 1271));
    }

    @Test
    public void durableGoalKnowsPickaxeMiningRequirements() {
        assertEquals(1, AgentActionService.requiredMiningLevelForPickaxe(1265)); // bronze pickaxe
        assertEquals(6, AgentActionService.requiredMiningLevelForPickaxe(1269)); // steel pickaxe
        assertEquals(21, AgentActionService.requiredMiningLevelForPickaxe(1273)); // mithril pickaxe
        assertEquals(31, AgentActionService.requiredMiningLevelForPickaxe(1271)); // adamant pickaxe
        assertEquals(41, AgentActionService.requiredMiningLevelForPickaxe(1275)); // rune pickaxe
    }

    @Test
    public void durableGoalBuysBestAffordableUnlockedPickaxeUpgrade() {
        assertEquals(1, AgentActionService.pickaxeTier(1265)); // bronze pickaxe
        assertEquals(2, AgentActionService.pickaxeTier(1267)); // iron pickaxe
        assertEquals(3, AgentActionService.pickaxeTier(1269)); // steel pickaxe
        assertEquals(5, AgentActionService.pickaxeTier(1271)); // adamant pickaxe

        assertEquals(1265, AgentActionService.recommendedPickaxeUpgradeId(1, 0, 1)); // replace lost starter pickaxe
        assertEquals(1265, AgentActionService.recommendedPickaxeUpgradeId(21, 0, 351)); // rebuy starter before gated upgrades
        assertEquals(1267, AgentActionService.recommendedPickaxeUpgradeId(1, 1, 140)); // iron
        assertEquals(1269, AgentActionService.recommendedPickaxeUpgradeId(18, 1, 500)); // steel
        assertEquals(1269, AgentActionService.recommendedPickaxeUpgradeId(23, 1, 500)); // steel before long gear grinds
        assertEquals(1273, AgentActionService.recommendedPickaxeUpgradeId(23, 1, 1300)); // mithril when affordable
        assertEquals(-1, AgentActionService.recommendedPickaxeUpgradeId(18, 3, 5000)); // already has steel
        assertEquals(1273, AgentActionService.recommendedPickaxeUpgradeId(21, 3, 1300)); // mithril
        assertEquals(-1, AgentActionService.recommendedPickaxeUpgradeId(31, 4, 3199)); // one coin short of adamant
        assertEquals(1271, AgentActionService.recommendedPickaxeUpgradeId(31, 4, 3200)); // adamant
        assertEquals(1275, AgentActionService.recommendedPickaxeUpgradeId(41, 5, 32000)); // rune
    }

    @Test
    public void durableGoalSavesForUnlockedUnfundedPickaxeUpgrade() {
        assertEquals(1267, AgentActionService.recommendedPickaxeMoneyUpgradeId(1, 1, 139)); // save for iron
        assertEquals(-1, AgentActionService.recommendedPickaxeMoneyUpgradeId(1, 1, 140)); // iron is already funded
        assertEquals(-1, AgentActionService.recommendedPickaxeMoneyUpgradeId(30, 4, 1000)); // adamant mining not unlocked
        assertEquals(1275, AgentActionService.recommendedPickaxeMoneyUpgradeId(45, 5, 21725)); // save for rune
        assertEquals(-1, AgentActionService.recommendedPickaxeMoneyUpgradeId(45, 5, 32000)); // rune is already funded
    }

    @Test
    public void durableGoalStartsPickaxeMoneyWhenNoCombatGearMoneyTargetExists() {
        assertFalse(AgentActionService.shouldEarnGearMoneyForTargetCosts(21725, -1, -1));
        assertTrue(AgentActionService.shouldEarnGearMoneyForTargetCosts(21725, 50000, -1));
        assertFalse(AgentActionService.shouldEarnGearMoneyForTargetCosts(50000, 50000, -1));
        assertTrue(AgentActionService.shouldEarnGearMoneyForTargetCosts(21725, -1, 32000));
        assertFalse(AgentActionService.shouldEarnGearMoneyForTargetCosts(32000, -1, 32000));
    }

    @Test
    public void durableGoalBuysAffordablePickaxeUpgradeAfterMoneyBatch() {
        assertTrue(AgentActionService.shouldAcquirePickaxeUpgrade(80, 0, false, true, false));
        assertFalse(AgentActionService.shouldAcquirePickaxeUpgrade(79, 0, false, true, false));
        assertFalse(AgentActionService.shouldAcquirePickaxeUpgrade(80, 0, true, true, false));
        assertFalse(AgentActionService.shouldAcquirePickaxeUpgrade(80, 0, false, false, false));
        assertFalse(AgentActionService.shouldAcquirePickaxeUpgrade(80, 0, false, true, true));
    }
}
