package com.rs2.agent;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class AgentCombatPlannerTest {

    @Test
    public void prioritizesAttackUntilWeaponUnlocks() {
        assertEquals("attack", AgentCombatPlanner.nextTrainingStyle(18, 12, 3, 60));
        assertEquals("attack", AgentCombatPlanner.nextTrainingStyle(29, 34, 30, 50));
    }

    @Test
    public void catchesStrengthUpAfterWeaponUnlocksForFasterKills() {
        assertEquals("strength", AgentCombatPlanner.nextTrainingStyle(40, 36, 35, 50));
        assertEquals("strength", AgentCombatPlanner.nextTrainingStyle(50, 36, 35, 50));
        assertEquals("strength", AgentCombatPlanner.nextTrainingStyle(42, 39, 30, 60));
    }

    @Test
    public void stopsPrioritizingAttackAfterFinalKnownWeaponTier() {
        assertEquals("attack", AgentCombatPlanner.nextTrainingStyle(39, 39, 35, 60));
        assertEquals("strength", AgentCombatPlanner.nextTrainingStyle(42, 39, 30, 60));
        assertEquals("defence", AgentCombatPlanner.nextTrainingStyle(45, 45, 30, 60));
    }

    @Test
    public void catchesDefenceUpWhenArmorAndDamageIntakeLag() {
        assertEquals("defence", AgentCombatPlanner.nextTrainingStyle(20, 12, 3, 60));
        assertEquals("defence", AgentCombatPlanner.nextTrainingStyle(30, 12, 3, 60));
        assertEquals("defence", AgentCombatPlanner.nextTrainingStyle(41, 22, 3, 60));
        assertEquals("strength", AgentCombatPlanner.nextTrainingStyle(41, 22, 20, 60));
        assertEquals("defence", AgentCombatPlanner.nextTrainingStyle(41, 30, 20, 60));
    }

    @Test
    public void avoidsGuardsUntilDefenceAndFoodAreReady() {
        AgentCombatPlanner.TrainingArea lowDefenceArea = AgentCombatPlanner.recommendedArea(41, 22, 3, 31, 10);
        AgentCombatPlanner.TrainingArea readyArea = AgentCombatPlanner.recommendedArea(41, 22, 20, 31, 10);

        assertEquals("barbarian village", lowDefenceArea.getName());
        assertEquals("varrock guards", readyArea.getName());
    }

    @Test
    public void keepsMidLevelTrainingOnReachableGuardsBeforeWhiteKnights() {
        AgentCombatPlanner.TrainingArea area = AgentCombatPlanner.recommendedArea(35, 36, 35, 38, 12);

        assertEquals("varrock guards", area.getName());
        assertEquals("Guard", area.getNpcName());
    }

    @Test
    public void keepsHighDamageMidLevelTrainingOnReachableGuardsBeforeWhiteKnights() {
        AgentCombatPlanner.TrainingArea area = AgentCombatPlanner.recommendedArea(42, 39, 30, 37, 13);

        assertEquals("varrock guards", area.getName());
        assertEquals("Guard", area.getNpcName());
    }

    @Test
    public void foodGateKeepsMidLevelPlayerLocalUntilRestocked() {
        AgentCombatPlanner.TrainingArea lowFoodArea = AgentCombatPlanner.recommendedArea(41, 32, 30, 35, 4);
        AgentCombatPlanner.TrainingArea restockedArea = AgentCombatPlanner.recommendedArea(41, 32, 30, 35, 8);

        assertEquals("barbarian village", lowFoodArea.getName());
        assertEquals("varrock guards", restockedArea.getName());
    }

    @Test
    public void unlocksWhiteKnightsAfterDefenceAndFoodCatchUp() {
        AgentCombatPlanner.TrainingArea area = AgentCombatPlanner.recommendedArea(42, 38, 35, 38, 12);

        assertEquals("falador white knights", area.getName());
        assertEquals("White Knight", area.getNpcName());
    }

    @Test
    public void scoresRockCrabAboveRiskierLowValueTarget() {
        int rockCrab = AgentCombatPlanner.scoreNpc("Rock Crab", 50, 13, 2, 20, 10, 45, 38, 4, false);
        int darkWizard = AgentCombatPlanner.scoreNpc("Dark wizard", 24, 20, 4, 40, 40, 45, 38, 2, false);

        assertTrue(rockCrab > darkWizard);
    }

    @Test
    public void scoresFortressDistractionsAsBadTrainingTargets() {
        int rockCrab = AgentCombatPlanner.scoreNpc("Rock Crab", 50, 13, 2, 20, 10, 45, 38, 4, false);
        int blackKnight = AgentCombatPlanner.scoreNpc("Black Knight", 42, 33, 4, 20, 20, 45, 38, 1, false);
        int fortressGuard = AgentCombatPlanner.scoreNpc("Fortress Guard", 22, 20, 3, 15, 15, 45, 38, 1, false);

        assertTrue(rockCrab > blackKnight);
        assertTrue(rockCrab > fortressGuard);
    }

    @Test
    public void recommendsOnlySmallCoinStackForEarlyCombat() {
        int budget = AgentCombatPlanner.recommendedCoinBudget(20, 20, 10);

        assertTrue(budget < 15000);
    }

    @Test
    public void recommendsRealMeleeWeaponsAtHigherAttackLevels() {
        assertEquals(1301, AgentCombatPlanner.recommendedWeaponId(30)); // adamant longsword
        assertEquals(1289, AgentCombatPlanner.recommendedWeaponId(40)); // rune sword
    }

    @Test
    public void recommendsDefensiveHeadGearAlongsideArmor() {
        assertEquals(1157, AgentCombatPlanner.recommendedHelmId(5)); // steel full helm
        assertEquals(1159, AgentCombatPlanner.recommendedHelmId(20)); // mithril full helm
        assertEquals(1161, AgentCombatPlanner.recommendedHelmId(30)); // adamant full helm
    }
}
