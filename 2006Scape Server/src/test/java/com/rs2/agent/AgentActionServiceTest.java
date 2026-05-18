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
    }

    @Test
    public void durableGoalPrefersReachableSwordUpgradesWhenAttackUnlocksThem() {
        assertEquals(1279, AgentActionService.recommendedWeaponUpgradeId(1, 0)); // iron sword
        assertEquals(1281, AgentActionService.recommendedWeaponUpgradeId(10, 1)); // steel sword
        assertEquals(1285, AgentActionService.recommendedWeaponUpgradeId(20, 2)); // mithril sword
        assertEquals(-1, AgentActionService.recommendedWeaponUpgradeId(20, 3));
    }

    @Test
    public void durableGoalSavesForUnlockedWeaponBeforeArmour() {
        assertTrue(AgentActionService.shouldSaveForWeaponBeforeArmor(18, 300, 1)); // save for steel sword before armour
        assertFalse(AgentActionService.shouldSaveForWeaponBeforeArmor(18, 325, 1)); // steel sword is affordable
        assertFalse(AgentActionService.shouldSaveForWeaponBeforeArmor(18, 0, 2)); // steel sword is already equipped
    }

    @Test
    public void durableGoalBuysAffordableIntermediateWeaponBeforeSavingForNextSword() {
        assertTrue(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1279, 1281)); // iron before steel
        assertTrue(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1281, 1285)); // steel before mithril
        assertFalse(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1115, 1281)); // armour does not delay sword
        assertFalse(AgentActionService.shouldInterruptGearMoneyForAffordableUpgrade(1281, 1281)); // target is already affordable
    }

    @Test
    public void durableGoalUsesCacheMatchedGearPriceEstimates() {
        assertEquals(91, AgentActionService.gearTargetEstimatedPrice(1279)); // iron sword
        assertEquals(325, AgentActionService.gearTargetEstimatedPrice(1281)); // steel sword
        assertEquals(845, AgentActionService.gearTargetEstimatedPrice(1285)); // mithril sword
        assertEquals(560, AgentActionService.gearTargetEstimatedPrice(1115)); // iron platebody
        assertEquals(750, AgentActionService.gearTargetEstimatedPrice(1105)); // steel chainbody
        assertEquals(5200, AgentActionService.gearTargetEstimatedPrice(1121)); // mithril platebody
        assertEquals(280, AgentActionService.gearTargetEstimatedPrice(1067)); // iron platelegs
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
        assertFalse(AgentActionService.isGearMoneyProductItem(1351)); // starter axe/tool is preserved
        assertFalse(AgentActionService.isGearMoneyProductItem(1279)); // combat gear is preserved
        assertFalse(AgentActionService.isGearMoneyItem(526)); // bones stay banked for the account
        assertFalse(AgentActionService.isGearMoneyItem(1739)); // cowhide stays banked for the account
    }

    @Test
    public void durableGoalBanksNonMiningClutterBeforeGearMoneyRuns() {
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(1265)); // keep the pickaxe
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(2347)); // keep the hammer
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(436)); // keep copper ore
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(438)); // keep tin ore
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(440)); // keep iron ore
        assertFalse(AgentActionService.isGearMoneyClutterItemForBanking(1422)); // sell smithed mace for gear money
        assertTrue(AgentActionService.isGearMoneyClutterItemForBanking(2142)); // bank food during mining trips
        assertTrue(AgentActionService.isGearMoneyClutterItemForBanking(1277)); // bank old combat gear
        assertTrue(AgentActionService.isGearMoneyClutterItemForBanking(1623)); // bank gems for later
    }

    @Test
    public void durableGoalMinesBronzeOresBeforeIronUnlocks() {
        assertEquals("copper", AgentActionService.gearMoneyOreForMiningLevel(1, 1, 0, 0));
        assertEquals("tin", AgentActionService.gearMoneyOreForMiningLevel(1, 1, 3, 1));
        assertEquals("copper", AgentActionService.gearMoneyOreForMiningLevel(15, 1, 100, 100));
        assertEquals("iron", AgentActionService.gearMoneyOreForMiningLevel(15, 15, 100, 0));
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
}
