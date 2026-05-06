package com.rs2.agent;

import com.rs2.agent.AgentSmithingPlanner.SmithingChoice;
import com.rs2.agent.AgentSmithingPlanner.Strategy;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

public class AgentSmithingPlannerTest {

    @Test
    public void normalizesBarNames() {
        assertEquals(2353, AgentSmithingPlanner.barItemId("steel bar"));
        assertEquals(2359, AgentSmithingPlanner.barItemId("mith"));
        assertEquals(2361, AgentSmithingPlanner.barItemId("addy"));
    }

    @Test
    public void choosesBestUnlockedSteelItemByXpPerBar() {
        SmithingChoice choice = AgentSmithingPlanner.bestSmithableItem(48, 2353, 5, Strategy.XP_PER_BAR);

        assertNotNull(choice);
        assertEquals(865, choice.getItemId());
        assertEquals(1, choice.getBarsNeeded());
        assertTrue(choice.getXpPerThousandBars() > 0);
    }

    @Test
    public void respectsLevelAndAvailableBars() {
        SmithingChoice choice = AgentSmithingPlanner.bestSmithableItem(40, 2353, 2, Strategy.XP_PER_BAR);

        assertNotNull(choice);
        assertEquals(865, choice.getItemId());
        assertEquals(1, choice.getBarsNeeded());
    }

    @Test
    public void canRestrictToArmorWhenRequested() {
        SmithingChoice choice = AgentSmithingPlanner.bestSmithableItem(18, 2349, 5, Strategy.XP_PER_BAR, "armor");

        assertNotNull(choice);
        assertEquals(1139, choice.getItemId());
        assertEquals(1, choice.getBarsNeeded());
    }
}
