package com.rs2.agent;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class AgentCombatPlannerTest {

    @Test
    public void prioritizesAttackUntilWeaponUnlocks() {
        assertEquals("attack", AgentCombatPlanner.nextTrainingStyle(29, 34, 30, 50));
        assertEquals("strength", AgentCombatPlanner.nextTrainingStyle(40, 36, 35, 50));
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
}
