package com.rs2.agent;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

public class AgentKnowledgeBaseTest {

    @Test
    public void resolvesKnownLandmarkAliases() {
        assertNotNull(AgentKnowledgeBase.findLandmark("varrock"));
        assertNotNull(AgentKnowledgeBase.findLandmark("iron mine"));
        assertNotNull(AgentKnowledgeBase.findLandmark("lumbridge oaks"));
        assertNotNull(AgentKnowledgeBase.findLandmark("varrock east bank"));
        assertNotNull(AgentKnowledgeBase.findLandmark("barbarian pickaxe"));
        assertNotNull(AgentKnowledgeBase.findLandmark("varrock sword shop"));
        assertNotNull(AgentKnowledgeBase.findLandmark("lumbridge cows"));
        assertNotNull(AgentKnowledgeBase.findLandmark("varrock guards"));
        assertNotNull(AgentKnowledgeBase.findLandmark("kebab shop"));
        assertNotNull(AgentKnowledgeBase.findLandmark("varrock general store"));
        assertNotNull(AgentKnowledgeBase.findLandmark("falador white knights"));
        assertNotNull(AgentKnowledgeBase.findLandmark("rock crabs"));
        assertEquals(3285, AgentKnowledgeBase.findLandmark("iron mine").getTarget().x);
        assertEquals(3365, AgentKnowledgeBase.findLandmark("iron mine").getTarget().y);
        assertEquals(3256, AgentKnowledgeBase.findLandmark("east bank").getTarget().x);
        assertEquals(3418, AgentKnowledgeBase.findLandmark("east bank").getTarget().y);
        assertEquals(3275, AgentKnowledgeBase.findLandmark("kebab shop").getTarget().x);
        assertEquals(3180, AgentKnowledgeBase.findLandmark("kebab shop").getTarget().y);
        assertEquals(3216, AgentKnowledgeBase.findLandmark("varrock general store").getTarget().x);
        assertEquals(3415, AgentKnowledgeBase.findLandmark("varrock general store").getTarget().y);
        assertEquals(2666, AgentKnowledgeBase.findLandmark("rock crabs").getTarget().x);
        assertEquals(3716, AgentKnowledgeBase.findLandmark("rock crabs").getTarget().y);
    }

    @Test
    public void furnaceRouteCanLeaveVarrockBank() {
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3260, 3420, 0,
                AgentKnowledgeBase.findLandmark("al kharid furnace"));

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3417, step.getTile().y);
    }

    @Test
    public void varrockAnvilRouteCanResumeFromAlKharidGateJoin() {
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3252, 3236, 0,
                AgentKnowledgeBase.findLandmark("varrock west anvils"));

        assertFalse(step.isComplete());
        assertEquals(3252, step.getTile().x);
        assertEquals(3266, step.getTile().y);
    }

    @Test
    public void varrockAnvilRouteDoesNotCompleteBeforeAnvils() {
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3196, 3428, 0,
                AgentKnowledgeBase.findLandmark("varrock west anvils"));

        assertFalse(step.isComplete());
        assertEquals(3188, step.getTile().x);
        assertEquals(3425, step.getTile().y);
    }

    @Test
    public void choosesNextWaypointTowardVarrockFromLumbridge() {
        AgentKnowledgeBase.Landmark varrock = AgentKnowledgeBase.findLandmark("varrock");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3222, 3218, 0, varrock);

        assertFalse(step.isComplete());
        assertEquals(3234, step.getTile().x);
        assertEquals(3238, step.getTile().y);
    }

    @Test
    public void choosesEasternApproachForVarrockEastMine() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3234, 3238, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3252, step.getTile().x);
        assertEquals(3236, step.getTile().y);
    }

    @Test
    public void routesFromMineToVarrockEastBank() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3285, 3365, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3289, step.getTile().x);
        assertEquals(3388, step.getTile().y);
    }

    @Test
    public void varrockEastMineRouteStopsAtMine() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3280, 3343, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3285, step.getTile().x);
        assertEquals(3365, step.getTile().y);
    }

    @Test
    public void completesWhenAlreadyAtDestination() {
        AgentKnowledgeBase.Landmark varrock = AgentKnowledgeBase.findLandmark("varrock");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3210, 3424, 0, varrock);

        assertTrue(step.isComplete());
    }

    @Test
    public void continuesFromBarbarianVillageTowardRockCrabs() {
        AgentKnowledgeBase.Landmark crabs = AgentKnowledgeBase.findLandmark("rock crabs");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3154, 3426, 0, crabs);

        assertFalse(step.isComplete());
        assertEquals(3148, step.getTile().x);
        assertEquals(3429, step.getTile().y);
    }

    @Test
    public void routesFromVarrockSideTowardKebabShop() {
        AgentKnowledgeBase.Landmark kebabs = AgentKnowledgeBase.findLandmark("kebab shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3154, 3426, 0, kebabs);

        assertFalse(step.isComplete());
        assertEquals(3158, step.getTile().x);
        assertEquals(3426, step.getTile().y);
    }
}
