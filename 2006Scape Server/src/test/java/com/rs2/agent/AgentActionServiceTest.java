package com.rs2.agent;

import com.google.gson.JsonObject;
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
        assertEquals("varrock east bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3284, 3412, true));
        assertEquals("varrock east bank",
                AgentActionService.supplyBankLandmark("barbarian village", 3288, 3393, false));
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
        assertFalse(AgentActionService.shouldTrainStrengthBeforeExpensiveWeapon(41, 37, 60));
        assertFalse(AgentActionService.shouldDeferExpensiveWeaponUpgradeForCombat(41, 15, 60, 15000, 4, 1289));
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
    public void durableGoalTreatsOnlyMinedResourcesAsGearMoneyItems() {
        assertTrue(AgentActionService.isGearMoneyItem(436)); // copper ore
        assertTrue(AgentActionService.isGearMoneyItem(438)); // tin ore
        assertTrue(AgentActionService.isGearMoneyItem(440)); // iron ore
        assertTrue(AgentActionService.isGearMoneyItem(453)); // coal
        assertTrue(AgentActionService.isGearMoneyItem(2349)); // bronze bar
        assertTrue(AgentActionService.isGearMoneyItem(2353)); // steel bar
        assertTrue(AgentActionService.isGearMoneyProductItem(1422)); // bronze mace can be smithed for sale
        assertFalse(AgentActionService.isGearMoneyProductItem(4820)); // nails are low-value components
        assertFalse(AgentActionService.isGearMoneyProductItem(820)); // darts are low-value ammo
        assertFalse(AgentActionService.isGearMoneyProductItem(40)); // arrow tips are low-value components
        assertFalse(AgentActionService.isGearMoneyProductItem(863)); // knives are low-value ammo
        assertTrue(AgentActionService.isGearMoneyProductItem(1293)); // iron longsword is a quality sale product
        assertFalse(AgentActionService.isGearMoneyProductItem(1351)); // starter axe/tool is preserved
        assertFalse(AgentActionService.isGearMoneyProductItem(1279)); // combat gear is preserved
        assertFalse(AgentActionService.isGearMoneyItem(526)); // bones stay banked for the account
        assertFalse(AgentActionService.isGearMoneyItem(1739)); // cowhide stays banked for the account
    }

    @Test
    public void durableGoalRanksSmithingForGearMoneyByBatchSellValue() {
        assertEquals(640, AgentActionService.estimatedGearMoneySmithingBatchSellCoins(1137, 10)); // 10 iron med helms
        assertEquals(535, AgentActionService.estimatedGearMoneySmithingBatchSellCoins(1293, 10)); // 5 iron longswords
        assertTrue(AgentActionService.isBetterGearMoneySmithingItem(1137, 1293, 10));
        assertFalse(AgentActionService.isBetterGearMoneySmithingItem(1293, 1137, 10));
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
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(2142)); // keep food for risky mining trips
        assertTrue(AgentActionService.isGearMoneyClutterItemForBanking(1277)); // bank old combat gear
        assertTrue(AgentActionService.isGearMoneyClutterItemForBanking(1623)); // bank gems for later
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
    public void durableGoalMinesCoalForSteelOnceSteelSmeltingUnlocks() {
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(30, 20, 0, 0, 0, 0));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(30, 20, 0, 0, 1, 0));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(30, 20, 0, 0, 1, 1));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(30, 20, 0, 0, 1, 2));
        assertEquals("coal", AgentActionService.gearMoneyOreForMiningLevel(32, 22, 0, 0, 9, 17));
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
    public void durableGoalWaitsForFullerOreRunsBeforeWalkingToFurnace() {
        assertFalse(AgentActionService.shouldSmeltGearMoneyOres(5, 8, false));
        assertFalse(AgentActionService.shouldSmeltGearMoneyOres(5, 8, true));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(8, 8, true));
        assertTrue(AgentActionService.shouldSmeltGearMoneyOres(5, 8, false, true));
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
        assertEquals(120, AgentActionService.kebabCoinFloat(18, 2, 10, 1720));
        assertEquals(20, AgentActionService.kebabCoinFloat(18, 2, 10, 20));
    }

    @Test
    public void durableGoalRetreatsFromNonCombatThreatWhenOutOfFood() {
        assertTrue(AgentActionService.shouldRetreatNonCombatThreatForFood(15, 30, 0, 9));
        assertFalse(AgentActionService.shouldRetreatNonCombatThreatForFood(21, 30, 0, 9));
        assertFalse(AgentActionService.shouldRetreatNonCombatThreatForFood(15, 30, 1, 9));
    }

    @Test
    public void restockFoodSkipsStalledSupplyDeposit() {
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
        assertTrue(AgentActionService.shouldBankCombatSupplyCount(18, 8));
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
    public void durableGoalReacquiresCurrentAttackerBeforeNonCombatWork() {
        assertEquals(12, AgentActionService.activeCombatNpcIndex(12, 34, 56, 78));
        assertEquals(34, AgentActionService.activeCombatNpcIndex(0, 34, 56, 78));
        assertEquals(78, AgentActionService.activeCombatNpcIndex(0, 0, 56, 78));
        assertEquals(56, AgentActionService.activeCombatNpcIndex(0, 0, 56, 0));
        assertEquals(-1, AgentActionService.activeCombatNpcIndex(0, 0, 0, 0));
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
        assertFalse(AgentActionService.isStaleMovementWait(3275, 3195, 3275, 3195, 19));
        assertTrue(AgentActionService.isStaleMovementWait(3275, 3195, 3275, 3195, 20));
        assertFalse(AgentActionService.isStaleMovementWait(3276, 3195, 3275, 3195, 20));
        assertFalse(AgentActionService.isExceededMovementWait(19));
        assertTrue(AgentActionService.isExceededMovementWait(20));
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
        assertFalse(AgentActionService.shouldWithdrawGearMoneyTravelCoins(10, 25, 1, true));
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
        assertEquals(1271, AgentActionService.recommendedPickaxeUpgradeId(31, 4, 3200)); // adamant
        assertEquals(1275, AgentActionService.recommendedPickaxeUpgradeId(41, 5, 32000)); // rune
    }
}
