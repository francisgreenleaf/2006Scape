package com.rs2.game.content.skills.agility;

import com.rs2.Constants;
import com.rs2.event.CycleEventHandler;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.players.Client;
import org.apollo.cache.def.ItemDefinition;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;

import java.lang.reflect.Field;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class PyramidAgilityTest {

    private TestClient player;

    @BeforeClass
    public static void initialiseItemDefinitions() {
        ItemDefinition[] definitions = ItemDefinition.getDefinitions();
        if (definitions == null) {
            definitions = new ItemDefinition[10000];
            for (int id = 0; id < definitions.length; id++) {
                definitions[id] = new ItemDefinition(id);
                definitions[id].setName("item-" + id);
            }
            ItemDefinition.init(definitions);
        }
        definitions[StaticItemList.COINS_995].setStackable(true);
        definitions[StaticItemList.PYRAMID_TOP].setName("Pyramid top");
    }

    @Before
    public void setUp() {
        player = new TestClient();
        player.playerName = "pyramidtester";
    }

    @Test
    public void pyramidCourseRegistersRealAndCacheLocalObjects() {
        assertTrue(PyramidAgility.isPyramidObject(PyramidAgility.PYRAMID_STAIRCE_OBJECT));
        assertTrue(PyramidAgility.isPyramidObject(PyramidAgility.PYRAMID_WALL_OBJECT));
        assertTrue(PyramidAgility.isPyramidObject(PyramidAgility.PYRAMID_JUMP));
        assertTrue(PyramidAgility.isPyramidObject(PyramidAgility.PYRAMID_PLANK_OBJECT));
        assertTrue(PyramidAgility.isPyramidObject(PyramidAgility.PYRAMID_DOORWAY_2));
        assertTrue(PyramidAgility.isPyramidObject(PyramidAgility.PYRAMID_CACHE_NULL_BLOCK));
        assertTrue(PyramidAgility.isPyramidObject(PyramidAgility.PYRAMID_CACHE_NULL_EAST_BLOCK));
        assertFalse(PyramidAgility.isPyramidObject(1));
    }

    @Test
    public void genericAgilityMappingCoversRepresentativePyramidAssets() {
        Agility agility = new Agility(player);

        assertEquals(0.0, agility.getXp(PyramidAgility.PYRAMID_STAIRCE_OBJECT), 0.001);
        assertEquals(8.0, agility.getXp(PyramidAgility.PYRAMID_WALL_OBJECT), 0.001);
        assertEquals(22.0, agility.getXp(PyramidAgility.PYRAMID_JUMP), 0.001);
        assertEquals(52.0, agility.getXp(PyramidAgility.LEDGE_3), 0.001);
        assertEquals(56.4, agility.getXp(PyramidAgility.PYRAMID_GAP_4), 0.001);
        assertEquals(56.4, agility.getXp(PyramidAgility.PYRAMID_PLANK_OBJECT), 0.001);
        assertEquals(12.0, agility.getXp(PyramidAgility.PYRAMID_BLOCK_2), 0.001);
        assertEquals(0.0, agility.getXp(PyramidAgility.PYRAMID_CACHE_NULL_BLOCK), 0.001);
    }

    @Test
    public void implementedRunnerRoutePreservesCleanLapXpTotal() throws Exception {
        int[][] route = {
                {PyramidAgility.PYRAMID_STAIRCE_OBJECT, 3354, 2831, 0},
                {PyramidAgility.PYRAMID_CACHE_NULL_BLOCK, 3355, 2841, 1},
                {PyramidAgility.PYRAMID_WALL_OBJECT, 3354, 2849, 1},
                {PyramidAgility.LEDGE, 3364, 2851, 1},
                {PyramidAgility.PYRAMID_BLOCK_2, 3368, 2849, 1},
                {PyramidAgility.PYRAMID_CACHE_NULL_EAST_BLOCK, 3372, 2849, 1},
                {PyramidAgility.PYRAMID_PLANK_OBJECT, 3375, 2845, 1},
                {PyramidAgility.PYRAMID_CACHE_NULL_BLOCK, 3374, 2835, 1},
                {PyramidAgility.PYRAMID_GAP_4, 3372, 2832, 1},
                {PyramidAgility.LEDGE_2, 3362, 2831, 1},
                {PyramidAgility.PYRAMID_STAIRCE_OBJECT, 3356, 2833, 1},
                {PyramidAgility.PYRAMID_GAP_4, 3357, 2836, 2},
                {PyramidAgility.PYRAMID_JUMP, 3356, 2847, 2},
                {PyramidAgility.PYRAMID_GAP_4, 3359, 2849, 2},
                {PyramidAgility.PYRAMID_CACHE_NULL_BLOCK, 3368, 2849, 2},
                {PyramidAgility.LEDGE, 3372, 2839, 2},
                {PyramidAgility.PYRAMID_WALL_OBJECT, 3370, 2833, 2},
                {PyramidAgility.PYRAMID_JUMP, 3364, 2833, 2},
                {PyramidAgility.PYRAMID_STAIRCE_OBJECT, 3358, 2835, 2},
                {PyramidAgility.PYRAMID_WALL_OBJECT, 3358, 2839, 3},
                {PyramidAgility.LEDGE_3, 3358, 2843, 3},
                {PyramidAgility.PYRAMID_JUMP, 3370, 2841, 3},
                {PyramidAgility.PYRAMID_PLANK_OBJECT, 3370, 2835, 3},
                {PyramidAgility.PYRAMID_STAIRCE_OBJECT, 3360, 2837, 3},
        };

        int storedXp = 0;
        for (int[] stepKey : route) {
            storedXp += (int) stepXp(stepKey[0], stepKey[1], stepKey[2], stepKey[3]);
        }
        storedXp += 300;

        assertEquals(1014, storedXp);
    }

    @Test
    public void levelThirtyIsRequiredForPyramidObstacles() {
        setAgilityLevel(29);
        setPosition(3354, 2848, 1);
        clickObject(PyramidAgility.PYRAMID_WALL_OBJECT, 3354, 2849);

        assertTrue(new PyramidAgility(player).pyramidCourse(PyramidAgility.PYRAMID_WALL_OBJECT));
        processCycles(2);

        assertEquals(0, player.playerXP[Constants.AGILITY]);
        assertEquals(-1, player.teleportToX);
        assertEquals(3354, player.absX);
        assertEquals(2848, player.absY);
        assertEquals(1, player.heightLevel);
    }

    @Test
    public void highLevelPlayerCompletesFailureProneObstacleWithoutRandomFailure() {
        setAgilityLevel(75);
        setPosition(3354, 2848, 1);
        clickObject(PyramidAgility.PYRAMID_WALL_OBJECT, 3354, 2849);

        assertTrue(new PyramidAgility(player).pyramidCourse(PyramidAgility.PYRAMID_WALL_OBJECT));
        processCycles(2);

        assertEquals(16, player.playerXP[Constants.AGILITY]);
        assertEquals(3354, player.teleportToX);
        assertEquals(2850, player.teleportToY);
        assertEquals(1, player.teleHeight);
    }

    @Test
    public void summitRequiresFreeInventorySpaceBeforeAwardingTop() {
        setAgilityLevel(75);
        setPosition(3360, 2836, 3);
        clickObject(PyramidAgility.PYRAMID_STAIRCE_OBJECT, 3360, 2837);
        fillInventoryWith(1971);

        assertTrue(new PyramidAgility(player).pyramidCourse(PyramidAgility.PYRAMID_STAIRCE_OBJECT));
        processCycles(2);

        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.PYRAMID_TOP));
        assertEquals(0, player.playerXP[Constants.AGILITY]);
        assertEquals(-1, player.teleportToX);
    }

    @Test
    public void summitAwardsTopAndCompletionBonusWhenInventoryHasSpace() {
        setAgilityLevel(75);
        setPosition(3360, 2836, 3);
        clickObject(PyramidAgility.PYRAMID_STAIRCE_OBJECT, 3360, 2837);

        assertTrue(new PyramidAgility(player).pyramidCourse(PyramidAgility.PYRAMID_STAIRCE_OBJECT));
        processCycles(2);

        assertEquals(1, player.getItemAssistant().getItemAmount(StaticItemList.PYRAMID_TOP));
        assertEquals(300, player.playerXP[Constants.AGILITY]);
        assertEquals(3363, player.teleportToX);
        assertEquals(2830, player.teleportToY);
        assertEquals(0, player.teleHeight);
    }

    @Test
    public void doorwayExitsToSimonSideBase() {
        setAgilityLevel(75);
        setPosition(3363, 2830, 0);
        clickObject(PyramidAgility.PYRAMID_DOORWAY_2, 3364, 2830);

        assertTrue(new PyramidAgility(player).pyramidCourse(PyramidAgility.PYRAMID_DOORWAY_2));
        processCycles(2);

        assertEquals(3351, player.teleportToX);
        assertEquals(2838, player.teleportToY);
        assertEquals(0, player.teleHeight);
    }

    @Test
    public void goingBackwardsAcrossObstacleDropsPlayerAndDamagesOneHitpoint() {
        setAgilityLevel(75);
        setHitpoints(10);
        setPosition(3354, 2850, 1);
        clickObject(PyramidAgility.PYRAMID_WALL_OBJECT, 3354, 2849);

        assertTrue(new PyramidAgility(player).pyramidCourse(PyramidAgility.PYRAMID_WALL_OBJECT));
        processCycles(2);

        assertEquals(9, player.playerLevel[Constants.HITPOINTS]);
        assertEquals(3355, player.teleportToX);
        assertEquals(2830, player.teleportToY);
        assertEquals(0, player.teleHeight);
    }

    @Test
    public void simonBuysAllPyramidTopsForOneThousandCoinsEach() {
        addInventoryItem(StaticItemList.PYRAMID_TOP, 1);
        addInventoryItem(StaticItemList.PYRAMID_TOP, 1);

        assertTrue(PyramidAgility.sellPyramidTops(player));

        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.PYRAMID_TOP));
        assertEquals(2000, player.getItemAssistant().getItemAmount(StaticItemList.COINS_995));
    }

    @Test
    public void simonDoesNotMintCoinsWithoutPyramidTops() {
        assertTrue(PyramidAgility.sellPyramidTops(player));

        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.PYRAMID_TOP));
        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.COINS_995));
    }

    private static double stepXp(int objectId, int objectX, int objectY, int height) throws Exception {
        Object step = findStep(objectId, objectX, objectY, height);
        Field xp = step.getClass().getDeclaredField("xp");
        xp.setAccessible(true);
        return ((Double) xp.get(step)).doubleValue();
    }

    private static Object findStep(int objectId, int objectX, int objectY, int height) throws Exception {
        Field stepsField = PyramidAgility.class.getDeclaredField("STEPS");
        stepsField.setAccessible(true);
        Object[] steps = (Object[]) stepsField.get(null);
        for (Object step : steps) {
            if (intField(step, "objectId") == objectId
                    && intField(step, "objectX") == objectX
                    && intField(step, "objectY") == objectY
                    && intField(step, "height") == height) {
                return step;
            }
        }
        throw new AssertionError("No Pyramid step for " + objectId + " at " + objectX + "," + objectY + "," + height);
    }

    private static int intField(Object instance, String name) throws Exception {
        Field field = instance.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.getInt(instance);
    }

    private void addInventoryItem(int itemId, int amount) {
        for (int slot = 0; slot < player.playerItems.length; slot++) {
            if (player.playerItems[slot] == 0) {
                player.playerItems[slot] = itemId + 1;
                player.playerItemsN[slot] = amount;
                return;
            }
        }
        throw new AssertionError("No free inventory slot for item " + itemId);
    }

    private void setAgilityLevel(int level) {
        player.playerLevel[Constants.AGILITY] = level;
    }

    private void setHitpoints(int hitpoints) {
        player.playerLevel[Constants.HITPOINTS] = hitpoints;
    }

    private void setPosition(int x, int y, int height) {
        player.absX = x;
        player.absY = y;
        player.heightLevel = height;
        player.teleportToX = -1;
        player.teleportToY = -1;
        player.teleHeight = -1;
    }

    private void clickObject(int objectId, int x, int y) {
        player.objectId = objectId;
        player.objectX = x;
        player.objectY = y;
    }

    private void processCycles(int count) {
        for (int cycle = 0; cycle < count; cycle++) {
            CycleEventHandler.getSingleton().process();
        }
    }

    private void fillInventoryWith(int itemId) {
        for (int slot = 0; slot < player.playerItems.length; slot++) {
            player.playerItems[slot] = itemId + 1;
            player.playerItemsN[slot] = 1;
        }
    }

    private static final class TestClient extends Client {
        private TestClient() {
            super(null, 17);
            outStream = null;
        }

        @Override
        public void flushOutStream() {
            // Keep this unit test independent from a network session.
        }

        @Override
        public void updateWalkEntities() {
            // Avoid bootstrapping world data while testing delayed Pyramid movement.
        }
    }
}
