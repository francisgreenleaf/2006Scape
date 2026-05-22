package com.rs2.agent;

import com.rs2.agent.AgentSmithingPlanner.ItemValueProvider;
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

    @Test
    public void choosesMarginItemWithFakeShopValues() {
        SmithingChoice choice = AgentSmithingPlanner.bestSmithableItem(48, 2353, 5, Strategy.MARGIN_PER_BAR, "",
                new ItemValueProvider() {
                    @Override
                    public int value(int itemId) {
                        return itemId == 1119 ? 1000 : 1;
                    }
                });

        assertNotNull(choice);
        assertEquals(1119, choice.getItemId());
        assertEquals(5, choice.getBarsNeeded());
        assertEquals(200000, choice.getEstimatedSellValuePerThousandBars(new ItemValueProvider() {
            @Override
            public int value(int itemId) {
                return itemId == 1119 ? 1000 : 1;
            }
        }));
    }

    @Test
    public void parsesProfitStrategiesAsMargin() {
        assertEquals(Strategy.MARGIN_PER_BAR, AgentSmithingPlanner.strategy("profit"));
        assertEquals(Strategy.MARGIN_PER_ACTION, AgentSmithingPlanner.strategy("coins per action"));
        assertEquals("margin_per_bar", AgentSmithingPlanner.strategyName(Strategy.MARGIN_PER_BAR));
    }

    @Test
    public void canChooseHighestQualityUnlockedProduct() {
        SmithingChoice choice = AgentSmithingPlanner.bestSmithableItem(25, 2351, 10, Strategy.HIGHEST_QUALITY);

        assertNotNull(choice);
        assertEquals(1363, choice.getItemId());
        assertEquals(3, choice.getBarsNeeded());
    }
}
