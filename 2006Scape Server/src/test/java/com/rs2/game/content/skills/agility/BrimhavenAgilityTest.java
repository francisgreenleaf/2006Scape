package com.rs2.game.content.skills.agility;

import com.rs2.Constants;
import com.rs2.event.CycleEventHandler;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.players.Client;
import com.rs2.game.shops.ShopAssistant;
import com.rs2.game.shops.ShopHandler;
import com.rs2.util.Stream;
import org.apollo.cache.def.ItemDefinition;
import org.apollo.util.security.IsaacRandom;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;

import java.lang.reflect.Field;
import java.lang.reflect.Method;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class BrimhavenAgilityTest {

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
        definitions[StaticItemList.AGILITY_ARENA_TICKET].setStackable(true);
        definitions[StaticItemList.AGILITY_ARENA_TICKET].setName("Agility arena ticket");
    }

    @Before
    public void setUp() {
        player = new TestClient();
        player.playerName = "brimhaventester";
        setPosition(2809, 3193, 0);
    }

    @Test
    public void brimhavenCourseRegistersArenaObjectsOnly() {
        assertTrue(BrimhavenAgility.isArenaObject(BrimhavenAgility.TICKET_DISPENSER));
        assertTrue(BrimhavenAgility.isArenaObject(BrimhavenAgility.INACTIVE_TICKET_DISPENSER));
        assertTrue(BrimhavenAgility.isArenaObject(BrimhavenAgility.BALANCING_ROPE_1));
        assertTrue(BrimhavenAgility.isArenaObject(BrimhavenAgility.PRESSURE_PAD));
        assertTrue(BrimhavenAgility.isArenaObject(BrimhavenAgility.EXIT_LADDER));
        assertFalse(BrimhavenAgility.isArenaObject(1));
    }

    @Test
    public void brimhavenArenaUsesLowMediumAndHighObstacleTiers() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();

        assertEquals(1, requiredLevel(agility, BrimhavenAgility.ROPE_SWING));
        assertEquals(1, requiredLevel(agility, BrimhavenAgility.PILLAR_1));
        assertEquals(1, requiredLevel(agility, BrimhavenAgility.LOW_WALL));
        assertEquals(1, requiredLevel(agility, BrimhavenAgility.LOG_BALANCE_1));
        assertEquals(1, requiredLevel(agility, BrimhavenAgility.BALANCING_LEDGE_1));
        assertEquals(1, requiredLevel(agility, BrimhavenAgility.MONKEY_BARS_1));
        assertEquals(1, requiredLevel(agility, BrimhavenAgility.BALANCING_ROPE_1));
        assertEquals(1, requiredLevel(agility, BrimhavenAgility.PLANK_1));
        assertEquals(1, requiredLevel(agility, BrimhavenAgility.BLADE_1));

        assertEquals(20, requiredLevel(agility, BrimhavenAgility.FLOOR_SPIKES));
        assertEquals(20, requiredLevel(agility, BrimhavenAgility.PRESSURE_PAD));
        assertEquals(20, requiredLevel(agility, BrimhavenAgility.HAND_HOLDS_1));

        assertEquals(40, requiredLevel(agility, BrimhavenAgility.SPINNING_BLADES));
    }

    @Test
    public void brimhavenObstacleXpMatchesGuideTableForCacheObjects() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();

        assertEquals(8.0, obstacleXp(agility, BrimhavenAgility.LOW_WALL), 0.0);
        assertEquals(20.0, obstacleXp(agility, BrimhavenAgility.ROPE_SWING), 0.0);
        assertEquals(18.0, obstacleXp(agility, BrimhavenAgility.PILLAR_1), 0.0);
        assertEquals(12.0, obstacleXp(agility, BrimhavenAgility.LOG_BALANCE_1), 0.0);
        assertEquals(16.0, obstacleXp(agility, BrimhavenAgility.BALANCING_LEDGE_1), 0.0);
        assertEquals(14.0, obstacleXp(agility, BrimhavenAgility.MONKEY_BARS_1), 0.0);
        assertEquals(10.0, obstacleXp(agility, BrimhavenAgility.BALANCING_ROPE_1), 0.0);
        assertEquals(6.0, obstacleXp(agility, BrimhavenAgility.PLANK_1), 0.0);
        assertEquals(0.0, obstacleXp(agility, BrimhavenAgility.BLADE_1), 0.0);
        assertEquals(24.0, obstacleXp(agility, BrimhavenAgility.FLOOR_SPIKES), 0.0);
        assertEquals(26.0, obstacleXp(agility, BrimhavenAgility.PRESSURE_PAD), 0.0);
        assertEquals(22.0, obstacleXp(agility, BrimhavenAgility.HAND_HOLDS_1), 0.0);
        assertEquals(28.0, obstacleXp(agility, BrimhavenAgility.SPINNING_BLADES), 0.0);
    }

    @Test
    public void capnIzzyChargesEntryFeeAndMovesPlayerIntoArena() {
        addInventoryItem(StaticItemList.COINS_995, 500);

        assertTrue(BrimhavenAgility.enterArena(player));

        assertEquals(300, player.getItemAssistant().getItemAmount(StaticItemList.COINS_995));
        assertEquals(2809, player.teleportToX);
        assertEquals(9562, player.teleportToY);
        assertEquals(3, player.teleHeight);
    }

    @Test
    public void capnIzzyRefusesEntryWithoutCoins() {
        assertTrue(BrimhavenAgility.enterArena(player));

        assertEquals(2809, player.absX);
        assertEquals(3193, player.absY);
        assertEquals(0, player.heightLevel);
    }

    @Test
    public void firstActiveDispenserTagPrimesAndDifferentNextTagAwardsTicket() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setPosition(2809, 9562, 3);
        int active = activeDispenserIndex(agility);
        clickDispenser(active);

        assertTrue(agility.brimhavenCourse(player.objectId));
        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));

        setPrivateField(agility, "lastTaggedWindow", Long.valueOf(currentWindow(agility) - 1L));
        setPrivateField(agility, "lastTaggedDispenser", Integer.valueOf((active + 1) % dispenserCount()));
        setPrivateField(agility, "hasTaggedFirstDispenser", Boolean.TRUE);
        clickDispenser(active);

        assertTrue(agility.brimhavenCourse(player.objectId));
        assertEquals(1, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
    }

    @Test
    public void wrongDispenserBreaksTicketStreak() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setPosition(2809, 9562, 3);
        int active = activeDispenserIndex(agility);
        int wrong = (active + 1) % dispenserCount();
        setPrivateField(agility, "lastTaggedWindow", Long.valueOf(currentWindow(agility) - 1L));
        setPrivateField(agility, "lastTaggedDispenser", Integer.valueOf((active + 2) % dispenserCount()));
        setPrivateField(agility, "hasTaggedFirstDispenser", Boolean.TRUE);
        clickDispenser(wrong);

        assertTrue(agility.brimhavenCourse(player.objectId));

        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
        assertFalse(((Boolean) privateField(agility, "hasTaggedFirstDispenser")).booleanValue());
    }

    @Test
    public void inactiveCacheDispenserObjectUsesSameTagLogic() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setPosition(2809, 9562, 3);
        int active = activeDispenserIndex(agility);
        clickDispenser(active);
        player.objectId = BrimhavenAgility.INACTIVE_TICKET_DISPENSER;
        setPrivateField(agility, "lastTaggedWindow", Long.valueOf(currentWindow(agility) - 1L));
        setPrivateField(agility, "lastTaggedDispenser", Integer.valueOf((active + 1) % dispenserCount()));
        setPrivateField(agility, "hasTaggedFirstDispenser", Boolean.TRUE);

        assertEquals(BrimhavenAgility.INACTIVE_TICKET_DISPENSER, player.objectId);
        assertTrue(agility.brimhavenCourse(player.objectId));

        assertEquals(1, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
    }

    @Test
    public void arenaUsesAllCacheTicketDispenserPlatformsExceptExitLadder() throws Exception {
        assertEquals(24, dispenserCount());
    }

    @Test
    public void sameDispenserDoesNotAwardTicketAcrossWindows() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setPosition(2809, 9562, 3);
        int active = activeDispenserIndex(agility);
        setPrivateField(agility, "lastTaggedWindow", Long.valueOf(currentWindow(agility) - 1L));
        setPrivateField(agility, "lastTaggedDispenser", Integer.valueOf(active));
        setPrivateField(agility, "hasTaggedFirstDispenser", Boolean.TRUE);
        clickDispenser(active);

        assertTrue(agility.brimhavenCourse(player.objectId));

        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
        assertFalse(((Boolean) privateField(agility, "hasTaggedFirstDispenser")).booleanValue());
    }

    @Test
    public void missedActiveWindowPrimesAgainInsteadOfAwardingTicket() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setPosition(2809, 9562, 3);
        int active = activeDispenserIndex(agility);
        setPrivateField(agility, "lastTaggedWindow", Long.valueOf(currentWindow(agility) - 2L));
        setPrivateField(agility, "lastTaggedDispenser", Integer.valueOf((active + 1) % dispenserCount()));
        setPrivateField(agility, "hasTaggedFirstDispenser", Boolean.TRUE);
        clickDispenser(active);

        assertTrue(agility.brimhavenCourse(player.objectId));

        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
        assertTrue(((Boolean) privateField(agility, "hasTaggedFirstDispenser")).booleanValue());
        assertEquals(currentWindow(agility), ((Long) privateField(agility, "lastTaggedWindow")).longValue());
        assertEquals(active, ((Integer) privateField(agility, "lastTaggedDispenser")).intValue());
    }

    @Test
    public void leavingArenaBreaksTicketStreak() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setPosition(2809, 9562, 3);
        setPrivateField(agility, "lastTaggedWindow", Long.valueOf(currentWindow(agility)));
        setPrivateField(agility, "lastTaggedDispenser", Integer.valueOf(1));
        setPrivateField(agility, "hasTaggedFirstDispenser", Boolean.TRUE);
        clickObject(BrimhavenAgility.EXIT_LADDER, 2805, 9590);

        assertTrue(agility.brimhavenCourse(BrimhavenAgility.EXIT_LADDER));

        assertEquals(2809, player.teleportToX);
        assertEquals(3192, player.teleportToY);
        assertEquals(0, player.teleHeight);
        assertFalse(((Boolean) privateField(agility, "hasTaggedFirstDispenser")).booleanValue());
    }

    @Test
    public void enteringArenaBreaksOldTicketStreak() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        addInventoryItem(StaticItemList.COINS_995, 500);
        setPrivateField(agility, "lastTaggedWindow", Long.valueOf(currentWindow(agility)));
        setPrivateField(agility, "lastTaggedDispenser", Integer.valueOf(1));
        setPrivateField(agility, "hasTaggedFirstDispenser", Boolean.TRUE);

        assertTrue(BrimhavenAgility.enterArena(player));

        assertFalse(((Boolean) privateField(agility, "hasTaggedFirstDispenser")).booleanValue());
    }

    @Test
    public void activeDispenserHintRefreshesOnlyWhileInsideArena() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();

        setPosition(2809, 3193, 0);
        setPrivateField(agility, "lastHintWindow", Long.valueOf(currentWindow(agility)));
        agility.process();

        assertEquals(-1L, ((Long) privateField(agility, "lastHintWindow")).longValue());

        setPosition(2809, 9562, 3);
        agility.process();

        assertEquals(currentWindow(agility), ((Long) privateField(agility, "lastHintWindow")).longValue());
    }

    @Test
    public void activeDispenserHintDoesNotRefreshEveryTickInSameWindow() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setPosition(2809, 9562, 3);
        long window = currentWindow(agility);
        setPrivateField(agility, "lastHintWindow", Long.valueOf(window));

        agility.process();

        assertEquals(window, ((Long) privateField(agility, "lastHintWindow")).longValue());
    }

    @Test
    public void entryLowWallMovesPlayerOntoCoursePlatform() {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setAgilityLevel(89);
        setPosition(2809, 9562, 3);
        clickObject(BrimhavenAgility.LOW_WALL, 2805, 9562);

        assertTrue(agility.brimhavenCourse(BrimhavenAgility.LOW_WALL));
        processCycles(2);

        assertEquals(8, player.playerXP[Constants.AGILITY]);
        assertEquals(2805, player.teleportToX);
        assertEquals(9568, player.teleportToY);
        assertEquals(3, player.teleHeight);
    }

    @Test
    public void brimhavenObstaclesCanBeClickedFromFiveTilesAway() {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        setAgilityLevel(99);
        setPosition(2800, 9562, 3);
        clickObject(BrimhavenAgility.LOW_WALL, 2805, 9562);

        assertTrue(agility.brimhavenCourse(BrimhavenAgility.LOW_WALL));
        processCycles(2);

        assertEquals(2805, player.teleportToX);
        assertEquals(9568, player.teleportToY);
        assertEquals(3, player.teleHeight);
    }

    @Test
    public void centralLowWallMovesBetweenTicketPlatformsInsteadOfWallEdges() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();

        setPosition(2783, 9557, 3);
        clickObject(BrimhavenAgility.LOW_WALL, 2783, 9562);
        int[] northToSouth = obstacleDestination(agility);

        assertEquals(2783, northToSouth[0]);
        assertEquals(9568, northToSouth[1]);
        assertEquals(3, northToSouth[2]);

        setPosition(2783, 9568, 3);
        clickObject(BrimhavenAgility.LOW_WALL, 2783, 9562);
        int[] southToNorth = obstacleDestination(agility);

        assertEquals(2783, southToNorth[0]);
        assertEquals(9557, southToNorth[1]);
        assertEquals(3, southToNorth[2]);
    }

    @Test
    public void centralLowWallRecoversPlayerFromFormerEdgeTrap() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();

        setPosition(2784, 9562, 3);
        clickObject(BrimhavenAgility.LOW_WALL, 2783, 9562);
        int[] destination = obstacleDestination(agility);

        assertEquals(2783, destination[0]);
        assertEquals(9568, destination[1]);
        assertEquals(3, destination[2]);
    }

    @Test
    public void longVerticalObstacleMovesAcrossFullSpan() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();

        setPosition(2772, 9568, 3);
        clickObject(BrimhavenAgility.BALANCING_ROPE_1, 2772, 9566);
        int[] northToSouth = obstacleDestination(agility);

        assertEquals(2772, northToSouth[0]);
        assertEquals(9558, northToSouth[1]);
        assertEquals(3, northToSouth[2]);

        setPosition(2772, 9557, 3);
        clickObject(BrimhavenAgility.BALANCING_ROPE_2, 2772, 9559);
        int[] southToNorth = obstacleDestination(agility);

        assertEquals(2772, southToNorth[0]);
        assertEquals(9567, southToNorth[1]);
        assertEquals(3, southToNorth[2]);
    }

    @Test
    public void spinningBladeMovesAcrossFullCacheLength() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();

        setPosition(2776, 9556, 3);
        clickObject(BrimhavenAgility.SPINNING_BLADES, 2777, 9556);
        int[] westToEast = obstacleDestination(agility);

        assertEquals(2780, westToEast[0]);
        assertEquals(9556, westToEast[1]);
        assertEquals(3, westToEast[2]);

        setPosition(2782, 9576, 3);
        clickObject(BrimhavenAgility.SPINNING_BLADES, 2782, 9575);
        int[] northToSouth = obstacleDestination(agility);

        assertEquals(2782, northToSouth[0]);
        assertEquals(9572, northToSouth[1]);
        assertEquals(3, northToSouth[2]);
    }

    @Test
    public void longHorizontalObstacleMovesAcrossFullSpan() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();

        setPosition(2772, 9557, 3);
        clickObject(BrimhavenAgility.PLANK_1, 2769, 9557);
        int[] eastToWest = obstacleDestination(agility);

        assertEquals(2763, eastToWest[0]);
        assertEquals(9557, eastToWest[1]);
        assertEquals(3, eastToWest[2]);

        setPosition(2761, 9557, 3);
        clickObject(BrimhavenAgility.PLANK_8, 2764, 9557);
        int[] westToEast = obstacleDestination(agility);

        assertEquals(2770, westToEast[0]);
        assertEquals(9557, westToEast[1]);
        assertEquals(3, westToEast[2]);
    }

    @Test
    public void pirateJackieExchangesTicketsUsingTieredXp() {
        addInventoryItem(StaticItemList.AGILITY_ARENA_TICKET, 25);

        assertTrue(BrimhavenAgility.exchangeTickets(player));

        assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
        assertEquals(6500, player.playerXP[Constants.AGILITY]);
    }

    @Test
    public void pirateJackieTicketXpUsesAllBulkTiers() throws Exception {
        assertEquals(240, ticketXp(1));
        assertEquals(2480, ticketXp(10));
        assertEquals(6500, ticketXp(25));
        assertEquals(28000, ticketXp(100));
        assertEquals(320000, ticketXp(1000));
        assertEquals(329220, ticketXp(1036));
    }

    @Test
    public void brimhavenRewardShopPricesUseArenaTickets() {
        ShopAssistant shop = player.getShopAssistant();

        assertEquals(151, ShopAssistant.BRIMHAVEN_AGILITY_SHOP);
        assertEquals(3, shop.getBrimhavenTicketItemValue(StaticItemList.TOADFLAX));
        assertEquals(10, shop.getBrimhavenTicketItemValue(StaticItemList.SNAPDRAGON));
        assertEquals(800, shop.getBrimhavenTicketItemValue(StaticItemList.PIRATES_HOOK));
        assertEquals(0, shop.getBrimhavenTicketItemValue(StaticItemList.COINS_995));
    }

    @Test
    public void brimhavenRewardShopBuysRewardsWithArenaTickets() {
        ShopSnapshot snapshot = seedBrimhavenRewardShop();
        try {
            enableShopStream();
            player.playerRights = 2;
            player.isShopping = true;
            player.shopId = ShopAssistant.BRIMHAVEN_AGILITY_SHOP;
            addInventoryItem(StaticItemList.AGILITY_ARENA_TICKET, 13);

            assertTrue(player.getShopAssistant().buyItem(StaticItemList.TOADFLAX, 0, 1));
            assertTrue(player.getShopAssistant().buyItem(StaticItemList.SNAPDRAGON, 1, 1));

            assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
            assertEquals(1, player.getItemAssistant().getItemAmount(StaticItemList.TOADFLAX));
            assertEquals(1, player.getItemAssistant().getItemAmount(StaticItemList.SNAPDRAGON));
            assertEquals(9, ShopHandler.getStock(ShopAssistant.BRIMHAVEN_AGILITY_SHOP, StaticItemList.TOADFLAX));
            assertEquals(9, ShopHandler.getStock(ShopAssistant.BRIMHAVEN_AGILITY_SHOP, StaticItemList.SNAPDRAGON));
        } finally {
            restoreBrimhavenRewardShop(snapshot);
        }
    }

    @Test
    public void brimhavenRewardShopRefusesMissingTicketsAndUnsupportedItems() {
        ShopSnapshot snapshot = seedBrimhavenRewardShop();
        try {
            enableShopStream();
            player.isShopping = true;
            player.shopId = ShopAssistant.BRIMHAVEN_AGILITY_SHOP;
            addInventoryItem(StaticItemList.AGILITY_ARENA_TICKET, 2);

            assertFalse(player.getShopAssistant().buyItem(StaticItemList.TOADFLAX, 0, 1));
            assertFalse(player.getShopAssistant().buyItem(StaticItemList.COINS_995, 0, 1));

            assertEquals(2, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
            assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.TOADFLAX));
            assertEquals(10, ShopHandler.getStock(ShopAssistant.BRIMHAVEN_AGILITY_SHOP, StaticItemList.TOADFLAX));
        } finally {
            restoreBrimhavenRewardShop(snapshot);
        }
    }

    @Test
    public void brimhavenRewardShopDoesNotBuyRewardsBack() {
        ShopSnapshot snapshot = seedBrimhavenRewardShop();
        try {
            enableShopStream();
            player.isShopping = true;
            player.shopId = ShopAssistant.BRIMHAVEN_AGILITY_SHOP;
            addInventoryItem(StaticItemList.TOADFLAX, 1);

            assertFalse(player.getShopAssistant().sellItem(StaticItemList.TOADFLAX, 0, 1));

            assertEquals(1, player.getItemAssistant().getItemAmount(StaticItemList.TOADFLAX));
            assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.COINS_995));
            assertEquals(0, player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET));
            assertEquals(10, ShopHandler.getStock(ShopAssistant.BRIMHAVEN_AGILITY_SHOP, StaticItemList.TOADFLAX));
        } finally {
            restoreBrimhavenRewardShop(snapshot);
        }
    }

    @Test
    public void pirateJackieExchangeBreaksTicketStreak() throws Exception {
        BrimhavenAgility agility = player.getBrimhavenAgility();
        addInventoryItem(StaticItemList.AGILITY_ARENA_TICKET, 1);
        setPrivateField(agility, "lastTaggedWindow", Long.valueOf(currentWindow(agility)));
        setPrivateField(agility, "lastTaggedDispenser", Integer.valueOf(1));
        setPrivateField(agility, "hasTaggedFirstDispenser", Boolean.TRUE);

        assertTrue(BrimhavenAgility.exchangeTickets(player));

        assertFalse(((Boolean) privateField(agility, "hasTaggedFirstDispenser")).booleanValue());
    }

    private long currentWindow(BrimhavenAgility agility) throws Exception {
        Method method = BrimhavenAgility.class.getDeclaredMethod("currentWindow");
        method.setAccessible(true);
        return ((Long) method.invoke(agility)).longValue();
    }

    private int activeDispenserIndex(BrimhavenAgility agility) throws Exception {
        Method current = BrimhavenAgility.class.getDeclaredMethod("currentWindow");
        current.setAccessible(true);
        long window = ((Long) current.invoke(agility)).longValue();
        Method active = BrimhavenAgility.class.getDeclaredMethod("activeDispenserIndex", Long.TYPE);
        active.setAccessible(true);
        return ((Integer) active.invoke(agility, Long.valueOf(window))).intValue();
    }

    private int dispenserCount() throws Exception {
        Field field = BrimhavenAgility.class.getDeclaredField("DISPENSERS");
        field.setAccessible(true);
        return ((Object[]) field.get(null)).length;
    }

    private int requiredLevel(BrimhavenAgility agility, int objectId) throws Exception {
        Method method = BrimhavenAgility.class.getDeclaredMethod("requiredLevel", Integer.TYPE);
        method.setAccessible(true);
        return ((Integer) method.invoke(agility, Integer.valueOf(objectId))).intValue();
    }

    private int ticketXp(int tickets) throws Exception {
        Method method = BrimhavenAgility.class.getDeclaredMethod("ticketXp", Integer.TYPE);
        method.setAccessible(true);
        return ((Integer) method.invoke(null, Integer.valueOf(tickets))).intValue();
    }

    private int[] obstacleDestination(BrimhavenAgility agility) throws Exception {
        Method method = BrimhavenAgility.class.getDeclaredMethod("obstacleDestination");
        method.setAccessible(true);
        Object tile = method.invoke(agility);
        Field x = tile.getClass().getDeclaredField("x");
        Field y = tile.getClass().getDeclaredField("y");
        Field h = tile.getClass().getDeclaredField("h");
        x.setAccessible(true);
        y.setAccessible(true);
        h.setAccessible(true);
        return new int[] {
                ((Integer) x.get(tile)).intValue(),
                ((Integer) y.get(tile)).intValue(),
                ((Integer) h.get(tile)).intValue()
        };
    }

    private double obstacleXp(BrimhavenAgility agility, int objectId) throws Exception {
        Method method = BrimhavenAgility.class.getDeclaredMethod("obstacleFor", Integer.TYPE);
        method.setAccessible(true);
        Object obstacle = method.invoke(agility, Integer.valueOf(objectId));
        Field xp = obstacle.getClass().getDeclaredField("xp");
        xp.setAccessible(true);
        return ((Double) xp.get(obstacle)).doubleValue();
    }

    private void setPrivateField(BrimhavenAgility agility, String name, Object value) throws Exception {
        Field field = BrimhavenAgility.class.getDeclaredField(name);
        field.setAccessible(true);
        field.set(agility, value);
    }

    private Object privateField(BrimhavenAgility agility, String name) throws Exception {
        Field field = BrimhavenAgility.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(agility);
    }

    private void clickDispenser(int index) {
        int[][] dispensers = {
                {3608, 2761, 9546},
                {3608, 2772, 9546},
                {3608, 2783, 9546},
                {3608, 2794, 9546},
                {3608, 2805, 9546},
                {3608, 2761, 9557},
                {3608, 2772, 9557},
                {3581, 2783, 9557},
                {3581, 2794, 9557},
                {3608, 2805, 9557},
                {3608, 2761, 9568},
                {3581, 2772, 9568},
                {3581, 2783, 9568},
                {3581, 2794, 9568},
                {3608, 2805, 9568},
                {3608, 2761, 9579},
                {3608, 2772, 9579},
                {3608, 2783, 9579},
                {3581, 2794, 9579},
                {3608, 2805, 9579},
                {3608, 2761, 9590},
                {3608, 2772, 9590},
                {3608, 2783, 9590},
                {3608, 2794, 9590}
        };
        player.objectId = dispensers[index][0];
        player.objectX = dispensers[index][1];
        player.objectY = dispensers[index][2];
    }

    private ShopSnapshot seedBrimhavenRewardShop() {
        int shopId = ShopAssistant.BRIMHAVEN_AGILITY_SHOP;
        ShopSnapshot snapshot = new ShopSnapshot(shopId);
        for (int slot = 0; slot < ShopHandler.MAX_SHOP_ITEMS; slot++) {
            ShopHandler.shopItems[shopId][slot] = 0;
            ShopHandler.shopItemsN[shopId][slot] = 0;
            ShopHandler.shopItemsSN[shopId][slot] = 0;
            ShopHandler.shopItemsDelay[shopId][slot] = 0;
        }
        ShopHandler.shopName[shopId] = "Brimhaven Agility Arena Ticket Exchange";
        ShopHandler.shopSModifier[shopId] = 2;
        ShopHandler.shopBModifier[shopId] = 2;
        ShopHandler.shopItemsStandard[shopId] = 3;
        seedShopItem(shopId, 0, StaticItemList.TOADFLAX, 10);
        seedShopItem(shopId, 1, StaticItemList.SNAPDRAGON, 10);
        seedShopItem(shopId, 2, StaticItemList.PIRATES_HOOK, 1);
        return snapshot;
    }

    private void seedShopItem(int shopId, int slot, int itemId, int amount) {
        ShopHandler.shopItems[shopId][slot] = itemId + 1;
        ShopHandler.shopItemsN[shopId][slot] = amount;
        ShopHandler.shopItemsSN[shopId][slot] = amount;
    }

    private void enableShopStream() {
        player.outStream = new Stream(new byte[Constants.BUFFER_SIZE]);
        player.outStream.packetEncryption = new IsaacRandom(new int[] {0, 0, 0, 0});
    }

    private void restoreBrimhavenRewardShop(ShopSnapshot snapshot) {
        System.arraycopy(snapshot.items, 0, ShopHandler.shopItems[snapshot.shopId], 0, ShopHandler.MAX_SHOP_ITEMS);
        System.arraycopy(snapshot.itemAmounts, 0, ShopHandler.shopItemsN[snapshot.shopId], 0, ShopHandler.MAX_SHOP_ITEMS);
        System.arraycopy(snapshot.standardAmounts, 0, ShopHandler.shopItemsSN[snapshot.shopId], 0, ShopHandler.MAX_SHOP_ITEMS);
        System.arraycopy(snapshot.delays, 0, ShopHandler.shopItemsDelay[snapshot.shopId], 0, ShopHandler.MAX_SHOP_ITEMS);
        ShopHandler.shopItemsStandard[snapshot.shopId] = snapshot.standard;
        ShopHandler.shopName[snapshot.shopId] = snapshot.name;
        ShopHandler.shopSModifier[snapshot.shopId] = snapshot.sellModifier;
        ShopHandler.shopBModifier[snapshot.shopId] = snapshot.buyModifier;
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

    private void setPosition(int x, int y, int height) {
        player.absX = x;
        player.absY = y;
        player.heightLevel = height;
        player.teleportToX = -1;
        player.teleportToY = -1;
        player.teleHeight = -1;
    }

    private void setAgilityLevel(int level) {
        player.playerLevel[Constants.AGILITY] = level;
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
            // Avoid bootstrapping world data while testing Brimhaven movement.
        }
    }

    private static final class ShopSnapshot {
        private final int shopId;
        private final int[] items;
        private final int[] itemAmounts;
        private final int[] standardAmounts;
        private final int[] delays;
        private final int standard;
        private final String name;
        private final int sellModifier;
        private final int buyModifier;

        private ShopSnapshot(int shopId) {
            this.shopId = shopId;
            this.items = ShopHandler.shopItems[shopId].clone();
            this.itemAmounts = ShopHandler.shopItemsN[shopId].clone();
            this.standardAmounts = ShopHandler.shopItemsSN[shopId].clone();
            this.delays = ShopHandler.shopItemsDelay[shopId].clone();
            this.standard = ShopHandler.shopItemsStandard[shopId];
            this.name = ShopHandler.shopName[shopId];
            this.sellModifier = ShopHandler.shopSModifier[shopId];
            this.buyModifier = ShopHandler.shopBModifier[shopId];
        }
    }
}
