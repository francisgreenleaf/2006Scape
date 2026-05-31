package com.rs2.game.content.custom.shops;

import com.rs2.game.content.StaticItemList;
import com.rs2.game.shops.ShopHandler;

public final class CustomShops {

    public static final int BOBS_BRILLIANT_AXES = 8;

    private static final StockItem[] BOBS_BRILLIANT_AXES_STOCK = {
            new StockItem(StaticItemList.BRONZE_PICKAXE, 5),
            new StockItem(StaticItemList.BRONZE_AXE, 10),
            new StockItem(StaticItemList.IRON_AXE, 5),
            new StockItem(StaticItemList.STEEL_AXE, 3),
            new StockItem(StaticItemList.MITHRIL_AXE, 1),
            new StockItem(StaticItemList.ADAMANT_AXE, 1),
            new StockItem(StaticItemList.RUNE_AXE, 1),
            new StockItem(StaticItemList.IRON_BATTLEAXE, 5),
            new StockItem(StaticItemList.STEEL_BATTLEAXE, 2),
            new StockItem(StaticItemList.MITHRIL_BATTLEAXE, 1)
    };

    private CustomShops() {
    }

    public static void applyStockOverrides() {
        replaceStandardStock(BOBS_BRILLIANT_AXES, BOBS_BRILLIANT_AXES_STOCK);
    }

    public static Integer getShopValue(int shopId, int itemId, boolean isSelling) {
        if (shopId != BOBS_BRILLIANT_AXES) {
            return null;
        }
        int price = getBobsBrilliantAxesValue(itemId);
        if (price <= 0) {
            return null;
        }
        if (isSelling) {
            return Math.max(1, (int) Math.floor(price * 0.85));
        }
        return price;
    }

    private static int getBobsBrilliantAxesValue(int itemId) {
        switch (itemId) {
            case StaticItemList.BRONZE_AXE:
                return 16;
            case StaticItemList.IRON_AXE:
                return 56;
            case StaticItemList.STEEL_AXE:
                return 200;
            case StaticItemList.MITHRIL_AXE:
                return 1664;
            case StaticItemList.ADAMANT_AXE:
                return 4096;
            case StaticItemList.RUNE_AXE:
                return 40960;
            default:
                return 0;
        }
    }

    private static void replaceStandardStock(int shopId, StockItem[] stock) {
        if (shopId < 0 || shopId >= ShopHandler.MAX_SHOPS) {
            return;
        }
        int limit = Math.min(stock.length, ShopHandler.MAX_SHOP_ITEMS);
        for (int slot = 0; slot < ShopHandler.MAX_SHOP_ITEMS; slot++) {
            ShopHandler.shopItems[shopId][slot] = 0;
            ShopHandler.shopItemsN[shopId][slot] = 0;
            ShopHandler.shopItemsSN[shopId][slot] = 0;
            ShopHandler.shopItemsDelay[shopId][slot] = 0;
            ShopHandler.shopItemsRestock[shopId][slot] = 0L;
        }
        ShopHandler.shopItemsStandard[shopId] = 0;
        for (int slot = 0; slot < limit; slot++) {
            StockItem item = stock[slot];
            if (item.itemId <= 0 || item.amount < 0) {
                continue;
            }
            ShopHandler.shopItems[shopId][slot] = item.itemId + 1;
            ShopHandler.shopItemsN[shopId][slot] = item.amount;
            ShopHandler.shopItemsSN[shopId][slot] = item.amount;
            ShopHandler.shopItemsDelay[shopId][slot] = 0;
            ShopHandler.shopItemsRestock[shopId][slot] = 0L;
            ShopHandler.shopItemsStandard[shopId]++;
        }
    }

    private static final class StockItem {
        private final int itemId;
        private final int amount;

        private StockItem(int itemId, int amount) {
            this.itemId = itemId;
            this.amount = amount;
        }
    }
}
