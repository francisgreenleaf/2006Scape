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
    public void choosesRockCrabsForMidLevelFoodBackedTraining() {
        AgentCombatPlanner.TrainingArea area = AgentCombatPlanner.recommendedArea(35, 36, 35, 38, 12);

        assertEquals("rock crabs", area.getName());
        assertEquals("Rock Crab", area.getNpcName());
    }

    @Test
    public void scoresRockCrabAboveRiskierLowValueTarget() {
        int rockCrab = AgentCombatPlanner.scoreNpc("Rock Crab", 50, 13, 2, 20, 10, 45, 38, 4, false);
        int darkWizard = AgentCombatPlanner.scoreNpc("Dark wizard", 24, 20, 4, 40, 40, 45, 38, 2, false);

        assertTrue(rockCrab > darkWizard);
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
}
