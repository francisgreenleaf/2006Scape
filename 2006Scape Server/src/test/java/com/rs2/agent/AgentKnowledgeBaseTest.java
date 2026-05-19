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
        assertNotNull(AgentKnowledgeBase.findLandmark("al kharid general store"));
        assertNotNull(AgentKnowledgeBase.findLandmark("falador white knights"));
        assertNotNull(AgentKnowledgeBase.findLandmark("rock crabs"));
        assertNotNull(AgentKnowledgeBase.findLandmark("pickaxe shop"));
        assertNotNull(AgentKnowledgeBase.findLandmark("lumbridge axe shop"));
        assertNotNull(AgentKnowledgeBase.findLandmark("nardah adventurer store"));
        assertNotNull(AgentKnowledgeBase.findLandmark("champions guild rune store"));
        assertNotNull(AgentKnowledgeBase.findLandmark("scavvo"));
        assertEquals(3285, AgentKnowledgeBase.findLandmark("iron mine").getTarget().x);
        assertEquals(3365, AgentKnowledgeBase.findLandmark("iron mine").getTarget().y);
        assertEquals(3253, AgentKnowledgeBase.findLandmark("east bank").getTarget().x);
        assertEquals(3420, AgentKnowledgeBase.findLandmark("east bank").getTarget().y);
        assertEquals(3275, AgentKnowledgeBase.findLandmark("kebab shop").getTarget().x);
        assertEquals(3180, AgentKnowledgeBase.findLandmark("kebab shop").getTarget().y);
        assertEquals(3313, AgentKnowledgeBase.findLandmark("al kharid general store").getTarget().x);
        assertEquals(3183, AgentKnowledgeBase.findLandmark("al kharid general store").getTarget().y);
        assertEquals(2666, AgentKnowledgeBase.findLandmark("rock crabs").getTarget().x);
        assertEquals(3716, AgentKnowledgeBase.findLandmark("rock crabs").getTarget().y);
        assertEquals(2998, AgentKnowledgeBase.findLandmark("pickaxe shop").getTarget().x);
        assertEquals(9843, AgentKnowledgeBase.findLandmark("pickaxe shop").getTarget().y);
        assertEquals(3024, AgentKnowledgeBase.findLandmark("dwarven mine ladder").getTarget().x);
        assertEquals(3450, AgentKnowledgeBase.findLandmark("dwarven mine ladder").getTarget().y);
        assertEquals(3077, AgentKnowledgeBase.findLandmark("dwarven mine north ladder underground").getTarget().x);
        assertEquals(9893, AgentKnowledgeBase.findLandmark("dwarven mine north ladder underground").getTarget().y);
        assertEquals(3020, AgentKnowledgeBase.findLandmark("dwarven mine trapdoor underground").getTarget().x);
        assertEquals(9850, AgentKnowledgeBase.findLandmark("dwarven mine trapdoor underground").getTarget().y);
        assertEquals(3407, AgentKnowledgeBase.findLandmark("seddu adventurer store").getTarget().x);
        assertEquals(2921, AgentKnowledgeBase.findLandmark("seddu adventurer store").getTarget().y);
        assertEquals(3192, AgentKnowledgeBase.findLandmark("scavvo").getTarget().x);
        assertEquals(3358, AgentKnowledgeBase.findLandmark("scavvo").getTarget().y);
        assertEquals(1, AgentKnowledgeBase.findLandmark("scavvo").getTarget().height);
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
    public void routesBackToLumbridgeCowsFromVarrockEastBank() {
        AgentKnowledgeBase.Landmark cows = AgentKnowledgeBase.findLandmark("lumbridge cows");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3253, 3420, 0, cows);

        assertFalse(step.isComplete());
        assertEquals(3260, step.getTile().x);
        assertEquals(3420, step.getTile().y);
    }

    @Test
    public void stillRoutesToLumbridgeCowsFromLumbridgeStart() {
        AgentKnowledgeBase.Landmark cows = AgentKnowledgeBase.findLandmark("lumbridge cows");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3222, 3218, 0, cows);

        assertFalse(step.isComplete());
        assertEquals(3234, step.getTile().x);
        assertEquals(3230, step.getTile().y);
    }

    @Test
    public void recoversFromLumbridgeSouthEastRoadTowardCows() {
        AgentKnowledgeBase.Landmark cows = AgentKnowledgeBase.findLandmark("lumbridge cows");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3261, 3220, 0, cows);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void routesFromLumbridgeGateApproachTowardCows() {
        AgentKnowledgeBase.Landmark cows = AgentKnowledgeBase.findLandmark("lumbridge cows");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3267, 3227, 0, cows);

        assertFalse(step.isComplete());
        assertEquals(3252, step.getTile().x);
        assertEquals(3236, step.getTile().y);
    }

    @Test
    public void stagesNorthFromLumbridgeGoblinsTowardCows() {
        AgentKnowledgeBase.Landmark cows = AgentKnowledgeBase.findLandmark("lumbridge cows");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3252, 3236, 0, cows);

        assertFalse(step.isComplete());
        assertEquals(3252, step.getTile().x);
        assertEquals(3266, step.getTile().y);
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
    public void routesFromIronMineTowardVarrockCoalRocks() {
        AgentKnowledgeBase.Landmark coal = AgentKnowledgeBase.findLandmark("varrock east coal mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3285, 3365, 0, coal);

        assertFalse(step.isComplete());
        assertEquals(3291, step.getTile().x);
        assertEquals(3351, step.getTile().y);
    }

    @Test
    public void completesAtVarrockCoalRocks() {
        AgentKnowledgeBase.Landmark coal = AgentKnowledgeBase.findLandmark("coal mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3302, 3317, 0, coal);

        assertTrue(step.isComplete());
    }

    @Test
    public void routesFromAlKharidSideBackTowardVarrockEastMine() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3264, 3200, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3216, step.getTile().y);
    }

    @Test
    public void doesNotSkipAlKharidConnectorTowardLumbridge() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3267, 3216, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void routesThroughAlKharidGateLineBeforeTurningNorth() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3267, 3220, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void turnsNorthFromAlKharidGateLineTowardVarrockEastMine() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3267, 3227, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3252, step.getTile().x);
        assertEquals(3236, step.getTile().y);
    }

    @Test
    public void recoversFromLiveAlKharidGateLinePosition() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3268, 3227, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void avoidsAlKharidScorpionMineAfterGateLine() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3275, 3245, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void rejoinsLumbridgeVarrockRoadFromAlKharidSide() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3260, 3249, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void recoversFromLiveAlKharidNorthRoadPocket() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3266, 3290, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3261, step.getTile().x);
        assertEquals(3322, step.getTile().y);
    }

    @Test
    public void recoversFromLiveScorpionRoadPositionTowardCoalMine() {
        AgentKnowledgeBase.Landmark coal = AgentKnowledgeBase.findLandmark("varrock east coal mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3266, 3267, 0, coal);

        assertFalse(step.isComplete());
        assertEquals(3261, step.getTile().x);
        assertEquals(3322, step.getTile().y);
    }

    @Test
    public void recoversFromLiveAlKharidBankReturnPosition() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3265, 3249, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void recoversFromLiveAlKharidConnectorPosition() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3267, 3233, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void routesFromGateLineToAlKharidGeneralStore() {
        AgentKnowledgeBase.Landmark store = AgentKnowledgeBase.findLandmark("al kharid general store");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3268, 3227, 0, store);

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3195, step.getTile().y);
    }

    @Test
    public void routesThroughAlKharidGateBeforeCityShops() {
        AgentKnowledgeBase.Landmark store = AgentKnowledgeBase.findLandmark("al kharid general store");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3260, 3220, 0, store);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);

        step = AgentKnowledgeBase.nextTravelStep(3267, 3227, 0, store);

        assertFalse(step.isComplete());
        assertEquals(3268, step.getTile().x);
        assertEquals(3227, step.getTile().y);
    }

    @Test
    public void routesFromLiveFurnacePathToAlKharidGeneralStore() {
        AgentKnowledgeBase.Landmark store = AgentKnowledgeBase.findLandmark("al kharid general store");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3275, 3195, 0, store);

        assertFalse(step.isComplete());
        assertEquals(3289, step.getTile().x);
        assertEquals(3189, step.getTile().y);
    }

    @Test
    public void routesFromVarrockEastBankTowardAlKharidFurnace() {
        AgentKnowledgeBase.Landmark furnace = AgentKnowledgeBase.findLandmark("al kharid furnace");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3253, 3420, 0, furnace);

        assertFalse(step.isComplete());
        assertEquals(3260, step.getTile().x);
        assertEquals(3420, step.getTile().y);
    }

    @Test
    public void recoversFromLiveVarrockFurnaceNoMovePosition() {
        AgentKnowledgeBase.Landmark furnace = AgentKnowledgeBase.findLandmark("al kharid furnace");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3255, 3388, 0, furnace);

        assertFalse(step.isComplete());
        assertEquals(3289, step.getTile().x);
        assertEquals(3388, step.getTile().y);
    }

    @Test
    public void recoversFromLiveVarrockLegShopNoMovePosition() {
        AgentKnowledgeBase.Landmark legsShop = AgentKnowledgeBase.findLandmark("al kharid legs shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3259, 3396, 0, legsShop);

        assertFalse(step.isComplete());
        assertEquals(3255, step.getTile().x);
        assertEquals(3404, step.getTile().y);
    }

    @Test
    public void recoversFromWestOfAlKharidNorthRoadPocket() {
        AgentKnowledgeBase.Landmark legsShop = AgentKnowledgeBase.findLandmark("al kharid legs shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3245, 3309, 0, legsShop);

        assertFalse(step.isComplete());
        assertEquals(3240, step.getTile().x);
        assertEquals(3302, step.getTile().y);
    }

    @Test
    public void routesSouthFromNorthRoadTowardAlKharidLegsShop() {
        AgentKnowledgeBase.Landmark legsShop = AgentKnowledgeBase.findLandmark("al kharid legs shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3261, 3322, 0, legsShop);

        assertFalse(step.isComplete());
        assertEquals(3240, step.getTile().x);
        assertEquals(3302, step.getTile().y);
    }

    @Test
    public void recoversFromLivePostNorthRoadBounceTowardAlKharidLegsShop() {
        AgentKnowledgeBase.Landmark legsShop = AgentKnowledgeBase.findLandmark("al kharid legs shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3249, 3314, 0, legsShop);

        assertFalse(step.isComplete());
        assertEquals(3240, step.getTile().x);
        assertEquals(3302, step.getTile().y);
    }

    @Test
    public void doesNotSkipUnreachedVarrockFurnaceRoadWaypoint() {
        AgentKnowledgeBase.Landmark furnace = AgentKnowledgeBase.findLandmark("al kharid furnace");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3275, 3425, 0, furnace);

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3417, step.getTile().y);
    }

    @Test
    public void advancesFromReachedFurnaceRoadLandingTowardSouthRoad() {
        AgentKnowledgeBase.Landmark furnace = AgentKnowledgeBase.findLandmark("al kharid furnace");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3276, 3419, 0, furnace);

        assertFalse(step.isComplete());
        assertEquals(3278, step.getTile().x);
        assertEquals(3408, step.getTile().y);
    }

    @Test
    public void routesAcrossAlKharidShopLaneToGeneralStore() {
        AgentKnowledgeBase.Landmark store = AgentKnowledgeBase.findLandmark("al kharid general store");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3289, 3189, 0, store);

        assertFalse(step.isComplete());
        assertEquals(3305, step.getTile().x);
        assertEquals(3186, step.getTile().y);
    }

    @Test
    public void rejoinsNorthRoadAfterAlKharidConnector() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3252, 3236, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3252, step.getTile().x);
        assertEquals(3266, step.getTile().y);
    }

    @Test
    public void routesFromVarrockEastBankBackToBobAxes() {
        AgentKnowledgeBase.Landmark bob = AgentKnowledgeBase.findLandmark("lumbridge axe shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3253, 3420, 0, bob);

        assertFalse(step.isComplete());
        assertEquals(3260, step.getTile().x);
        assertEquals(3420, step.getTile().y);
    }

    @Test
    public void recoversFromVarrockEastBankNorthSideTowardLumbridgeFishing() {
        AgentKnowledgeBase.Landmark fishing = AgentKnowledgeBase.findLandmark("lumbridge fishing spot");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3274, 3426, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3417, step.getTile().y);
    }

    @Test
    public void routesSouthFromVarrockEastBankRoadTowardLumbridgeFishing() {
        AgentKnowledgeBase.Landmark fishing = AgentKnowledgeBase.findLandmark("lumbridge fishing spot");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3260, 3420, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3417, step.getTile().y);
    }

    @Test
    public void recoversFromVarrockEastBankSouthBounceTowardRoad() {
        AgentKnowledgeBase.Landmark fishing = AgentKnowledgeBase.findLandmark("lumbridge fishing spot");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3276, 3419, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3278, step.getTile().x);
        assertEquals(3408, step.getTile().y);
    }

    @Test
    public void continuesSouthRoadInsteadOfBankRecoveryTowardLumbridgeFishing() {
        AgentKnowledgeBase.Landmark fishing = AgentKnowledgeBase.findLandmark("lumbridge fishing spot");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3274, 3417, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3278, step.getTile().x);
        assertEquals(3408, step.getTile().y);
    }

    @Test
    public void backsOutNorthFromBlockedDirectLumbridgeRoute() {
        AgentKnowledgeBase.Landmark fishing = AgentKnowledgeBase.findLandmark("lumbridge fishing spot");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3255, 3388, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3255, step.getTile().x);
        assertEquals(3404, step.getTile().y);
    }

    @Test
    public void rejoinsVarrockEastBankRoadAfterBackingOutNorth() {
        AgentKnowledgeBase.Landmark fishing = AgentKnowledgeBase.findLandmark("lumbridge fishing spot");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3255, 3404, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3260, step.getTile().x);
        assertEquals(3420, step.getTile().y);
    }

    @Test
    public void routesToInRangeFishingApproachWaypointFromLumbridgeRoad() {
        AgentKnowledgeBase.Landmark fishing = AgentKnowledgeBase.findLandmark("lumbridge fishing spot");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3266, 3206, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3190, step.getTile().y);
    }

    @Test
    public void stagesFinalFishingSpotApproachWithinWalkerRange() {
        AgentKnowledgeBase.Landmark fishing = AgentKnowledgeBase.findLandmark("lumbridge fishing spot");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3274, 3195, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3190, step.getTile().y);

        step = AgentKnowledgeBase.nextTravelStep(3274, 3190, 0, fishing);

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3179, step.getTile().y);
    }

    @Test
    public void routesFromLumbridgeStartToBobAxes() {
        AgentKnowledgeBase.Landmark bob = AgentKnowledgeBase.findLandmark("bob axes");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3222, 3218, 0, bob);

        assertFalse(step.isComplete());
        assertEquals(3231, step.getTile().x);
        assertEquals(3203, step.getTile().y);
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
    public void routesFromCoalMineTowardVarrockEastBankWithoutScorpionDetour() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3302, 3317, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3301, step.getTile().x);
        assertEquals(3325, step.getTile().y);
    }

    @Test
    public void recoversFromVarrockEastScorpionPocketTowardBankRoad() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3293, 3274, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3301, step.getTile().x);
        assertEquals(3325, step.getTile().y);
    }

    @Test
    public void advancesFromVarrockEastScorpionRoadTowardBank() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3301, 3325, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3280, step.getTile().x);
        assertEquals(3343, step.getTile().y);
    }

    @Test
    public void routesFromVarrockCenterToEastBankRoad() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3213, 3424, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3238, step.getTile().x);
        assertEquals(3420, step.getTile().y);
    }

    @Test
    public void escapesSouthVarrockDarkWizardAreaTowardEastBankRoad() {
        AgentKnowledgeBase.Landmark bank = AgentKnowledgeBase.findLandmark("varrock east bank");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3223, 3370, 0, bank);

        assertFalse(step.isComplete());
        assertEquals(3260, step.getTile().x);
        assertEquals(3420, step.getTile().y);
    }

    @Test
    public void avoidsDarkWizardCircleWhenRecoveringTowardVarrockEastMine() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3223, 3370, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3238, step.getTile().x);
        assertEquals(3420, step.getTile().y);
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

    @Test
    public void stagesKebabApproachFromLiveAlKharidCorner() {
        AgentKnowledgeBase.Landmark kebabs = AgentKnowledgeBase.findLandmark("kebab shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3266, 3204, 0, kebabs);

        assertFalse(step.isComplete());
        assertEquals(3267, step.getTile().x);
        assertEquals(3227, step.getTile().y);

        step = AgentKnowledgeBase.nextTravelStep(3267, 3227, 0, kebabs);

        assertFalse(step.isComplete());
        assertEquals(3268, step.getTile().x);
        assertEquals(3227, step.getTile().y);

        step = AgentKnowledgeBase.nextTravelStep(3268, 3227, 0, kebabs);

        assertFalse(step.isComplete());
        assertEquals(3274, step.getTile().x);
        assertEquals(3195, step.getTile().y);
    }

    @Test
    public void stagesFinalKebabApproachWithinWalkerRange() {
        AgentKnowledgeBase.Landmark kebabs = AgentKnowledgeBase.findLandmark("kebab shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3274, 3195, 0, kebabs);

        assertFalse(step.isComplete());
        assertEquals(3275, step.getTile().x);
        assertEquals(3180, step.getTile().y);
    }

    @Test
    public void routesFromBarbarianVillageTowardDwarvenMineLadder() {
        AgentKnowledgeBase.Landmark ladder = AgentKnowledgeBase.findLandmark("dwarven mine ladder");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3081, 3429, 0, ladder);

        assertFalse(step.isComplete());
        assertEquals(3076, step.getTile().x);
        assertEquals(3428, step.getTile().y);
    }

    @Test
    public void recoversFromLiveFaladorNoMovePositionTowardDwarvenMineLadder() {
        AgentKnowledgeBase.Landmark ladder = AgentKnowledgeBase.findLandmark("dwarven mine ladder");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3027, 3423, 0, ladder);

        assertFalse(step.isComplete());
        assertEquals(3024, step.getTile().x);
        assertEquals(3450, step.getTile().y);
    }

    @Test
    public void routesFromSurfaceDwarvenMineExitTowardVarrockEastMine() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3065, 3492, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3058, step.getTile().x);
        assertEquals(3485, step.getTile().y);
    }

    @Test
    public void routesFromDwarvenMineSurfaceExitAlongReachableMonasterySidePath() {
        AgentKnowledgeBase.Landmark mine = AgentKnowledgeBase.findLandmark("varrock east mine");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3058, 3485, 0, mine);

        assertFalse(step.isComplete());
        assertEquals(3050, step.getTile().x);
        assertEquals(3474, step.getTile().y);
    }

    @Test
    public void routesUndergroundFromNorthEntranceBackTowardLadder() {
        AgentKnowledgeBase.Landmark ladder = AgentKnowledgeBase.findLandmark("dwarven mine north ladder underground");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3075, 9879, 0, ladder);

        assertFalse(step.isComplete());
        assertEquals(3077, step.getTile().x);
        assertEquals(9893, step.getTile().y);
    }

    @Test
    public void routesFromMiningGuildSideTowardNurmof() {
        AgentKnowledgeBase.Landmark pickaxes = AgentKnowledgeBase.findLandmark("nurmof pickaxe shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3046, 9757, 0, pickaxes);

        assertFalse(step.isComplete());
        assertEquals(3039, step.getTile().x);
        assertEquals(9765, step.getTile().y);
    }

    @Test
    public void routesFromDwarvenMineTrapdoorTowardNurmof() {
        AgentKnowledgeBase.Landmark pickaxes = AgentKnowledgeBase.findLandmark("nurmof pickaxe shop");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3020, 9850, 0, pickaxes);

        assertFalse(step.isComplete());
        assertEquals(3032, step.getTile().x);
        assertEquals(9830, step.getTile().y);
    }

    @Test
    public void routesFromAlKharidTowardNardahAdventurerStore() {
        AgentKnowledgeBase.Landmark store = AgentKnowledgeBase.findLandmark("nardah adventurer store");
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(3315, 3175, 0, store);

        assertFalse(step.isComplete());
        assertEquals(3328, step.getTile().x);
        assertEquals(3150, step.getTile().y);
    }

}
