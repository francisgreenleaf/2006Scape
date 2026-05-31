package com.rs2.game.content.custom.shops;

import com.rs2.game.content.StaticItemList;
import com.rs2.game.players.Client;
import com.rs2.game.shops.ShopAssistant;
import com.rs2.game.shops.ShopHandler;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

public class CustomShopsTest {

    private int[] originalItems;
    private int[] originalAmounts;
    private int[] originalStandardAmounts;
    private int[] originalDelays;
    private long[] originalRestocks;
    private int originalStandardCount;

    @Before
    public void setUp() {
        int shopId = CustomShops.BOBS_BRILLIANT_AXES;
        originalItems = ShopHandler.shopItems[shopId].clone();
        originalAmounts = ShopHandler.shopItemsN[shopId].clone();
        originalStandardAmounts = ShopHandler.shopItemsSN[shopId].clone();
        originalDelays = ShopHandler.shopItemsDelay[shopId].clone();
        originalRestocks = ShopHandler.shopItemsRestock[shopId].clone();
        originalStandardCount = ShopHandler.shopItemsStandard[shopId];
    }

    @After
    public void tearDown() {
        int shopId = CustomShops.BOBS_BRILLIANT_AXES;
        System.arraycopy(originalItems, 0, ShopHandler.shopItems[shopId], 0, originalItems.length);
        System.arraycopy(originalAmounts, 0, ShopHandler.shopItemsN[shopId], 0, originalAmounts.length);
        System.arraycopy(originalStandardAmounts, 0, ShopHandler.shopItemsSN[shopId], 0, originalStandardAmounts.length);
        System.arraycopy(originalDelays, 0, ShopHandler.shopItemsDelay[shopId], 0, originalDelays.length);
        System.arraycopy(originalRestocks, 0, ShopHandler.shopItemsRestock[shopId], 0, originalRestocks.length);
        ShopHandler.shopItemsStandard[shopId] = originalStandardCount;
    }

    @Test
    public void bobsBrilliantAxesStockOverrideAddsBetterAxesWithoutBlackOrDragon() {
        int shopId = CustomShops.BOBS_BRILLIANT_AXES;
        ShopHandler.shopItems[shopId][0] = StaticItemList.BLACK_AXE + 1;
        ShopHandler.shopItems[shopId][1] = StaticItemList.DRAGON_AXE + 1;
        ShopHandler.shopItemsN[shopId][0] = 1;
        ShopHandler.shopItemsN[shopId][1] = 1;
        ShopHandler.shopItemsSN[shopId][0] = 1;
        ShopHandler.shopItemsSN[shopId][1] = 1;
        ShopHandler.shopItemsStandard[shopId] = 2;

        CustomShops.applyStockOverrides();

        assertStock(0, StaticItemList.BRONZE_PICKAXE, 5);
        assertStock(1, StaticItemList.BRONZE_AXE, 10);
        assertStock(2, StaticItemList.IRON_AXE, 5);
        assertStock(3, StaticItemList.STEEL_AXE, 3);
        assertStock(4, StaticItemList.MITHRIL_AXE, 1);
        assertStock(5, StaticItemList.ADAMANT_AXE, 1);
        assertStock(6, StaticItemList.RUNE_AXE, 1);
        assertStock(7, StaticItemList.IRON_BATTLEAXE, 5);
        assertStock(8, StaticItemList.STEEL_BATTLEAXE, 2);
        assertStock(9, StaticItemList.MITHRIL_BATTLEAXE, 1);
        assertEquals(10, ShopHandler.shopItemsStandard[shopId]);
        assertEquals(0, stockAmount(StaticItemList.BLACK_AXE));
        assertEquals(0, stockAmount(StaticItemList.DRAGON_AXE));
    }

    @Test
    public void bobsBrilliantAxesUsesExpectedCustomAxePrices() {
        TestClient player = new TestClient(1);
        player.shopId = CustomShops.BOBS_BRILLIANT_AXES;
        ShopAssistant shopAssistant = new ShopAssistant(player);

        assertEquals(16, shopAssistant.getItemShopValue(StaticItemList.BRONZE_AXE, 0, false));
        assertEquals(56, shopAssistant.getItemShopValue(StaticItemList.IRON_AXE, 0, false));
        assertEquals(200, shopAssistant.getItemShopValue(StaticItemList.STEEL_AXE, 0, false));
        assertEquals(1664, shopAssistant.getItemShopValue(StaticItemList.MITHRIL_AXE, 0, false));
        assertEquals(4096, shopAssistant.getItemShopValue(StaticItemList.ADAMANT_AXE, 0, false));
        assertEquals(40960, shopAssistant.getItemShopValue(StaticItemList.RUNE_AXE, 0, false));
        assertEquals(34816, shopAssistant.getItemShopValue(StaticItemList.RUNE_AXE, 0, true));

        assertNull(CustomShops.getShopValue(CustomShops.BOBS_BRILLIANT_AXES, StaticItemList.BLACK_AXE, false));
        assertNull(CustomShops.getShopValue(CustomShops.BOBS_BRILLIANT_AXES, StaticItemList.DRAGON_AXE, false));
        assertNull(CustomShops.getShopValue(1, StaticItemList.RUNE_AXE, false));
    }

    @Test
    public void catherbyTraderCrewmemberMapsToTraderStansTradingPostOnly() {
        assertEquals(Integer.valueOf(CustomShops.TRADER_STANS_TRADING_POST),
                CustomShops.getShopIdForNpc(CustomShops.CATHERBY_TRADER_CREWMEMBER));
        assertNull(CustomShops.getShopIdForNpc(4650));
        assertNull(CustomShops.getShopIdForNpc(4652));
        assertNull(CustomShops.getShopIdForNpc(563));
    }

    @Test
    public void traderStansTradingPostUsesExpectedGlassSupplyPrices() {
        TestClient player = new TestClient(1);
        player.shopId = CustomShops.TRADER_STANS_TRADING_POST;
        ShopAssistant shopAssistant = new ShopAssistant(player);

        assertEquals(5, shopAssistant.getItemShopValue(StaticItemList.GLASSBLOWING_PIPE, 0, false));
        assertEquals(5, shopAssistant.getItemShopValue(StaticItemList.BUCKET_OF_SAND, 0, false));
        assertEquals(5, shopAssistant.getItemShopValue(StaticItemList.SEAWEED, 0, false));
        assertEquals(5, shopAssistant.getItemShopValue(StaticItemList.SODA_ASH, 0, false));
        assertEquals(4, shopAssistant.getItemShopValue(StaticItemList.SODA_ASH, 0, true));

        assertNull(CustomShops.getShopValue(CustomShops.TRADER_STANS_TRADING_POST, StaticItemList.MOLTEN_GLASS, false));
        assertNull(CustomShops.getShopValue(1, StaticItemList.SODA_ASH, false));
    }

    private static void assertStock(int slot, int itemId, int amount) {
        int shopId = CustomShops.BOBS_BRILLIANT_AXES;
        assertEquals(itemId + 1, ShopHandler.shopItems[shopId][slot]);
        assertEquals(amount, ShopHandler.shopItemsN[shopId][slot]);
        assertEquals(amount, ShopHandler.shopItemsSN[shopId][slot]);
    }

    private static int stockAmount(int itemId) {
        int shopId = CustomShops.BOBS_BRILLIANT_AXES;
        int total = 0;
        for (int slot = 0; slot < ShopHandler.MAX_SHOP_ITEMS; slot++) {
            if (ShopHandler.shopItems[shopId][slot] == itemId + 1) {
                total += ShopHandler.shopItemsN[shopId][slot];
            }
        }
        return total;
    }

    private static final class TestClient extends Client {
        private TestClient(int playerId) {
            super(null, playerId);
        }
    }
}
