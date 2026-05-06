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
        assertEquals(3285, AgentKnowledgeBase.findLandmark("iron mine").getTarget().x);
        assertEquals(3365, AgentKnowledgeBase.findLandmark("iron mine").getTarget().y);
        assertEquals(3253, AgentKnowledgeBase.findLandmark("east bank").getTarget().x);
        assertEquals(3420, AgentKnowledgeBase.findLandmark("east bank").getTarget().y);
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
    public void completesWhenAlreadyAtDestination() {
        AgentKnowledgeBase.Landmark varrock = AgentKnowledgeBase.findLandmark("varrock");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3210, 3424, 0, varrock);

        assertTrue(step.isComplete());
    }
}
