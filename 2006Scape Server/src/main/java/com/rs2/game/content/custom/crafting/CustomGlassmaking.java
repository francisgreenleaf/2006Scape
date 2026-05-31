package com.rs2.game.content.custom.crafting;

import com.rs2.Constants;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.players.Player;

public final class CustomGlassmaking {

    public static final int MOLTEN_GLASS_XP = 20;

    private static final int[] FURNACES = {
            14921, 9390, 2781, 2785, 2966, 3294, 3413, 4304, 4305, 6189, 6190, 11009, 11010, 11666, 12100, 12809
    };

    private CustomGlassmaking() {
    }

    public static boolean handleItemOnObject(Player player, int itemId, int objectId) {
        if (!isGlassIngredient(itemId) || !isFurnace(objectId)) {
            return false;
        }
        if (!player.getItemAssistant().playerHasItem(StaticItemList.BUCKET_OF_SAND, 1)
                || !player.getItemAssistant().playerHasItem(StaticItemList.SODA_ASH, 1)) {
            player.getPacketSender().sendMessage("You need a bucket of sand and some soda ash to make molten glass.");
            return true;
        }
        player.startAnimation(899);
        player.getPacketSender().sendSound(352, 100, 1);
        player.getItemAssistant().deleteItem(StaticItemList.BUCKET_OF_SAND, 1);
        player.getItemAssistant().deleteItem(StaticItemList.SODA_ASH, 1);
        player.getItemAssistant().addItem(StaticItemList.MOLTEN_GLASS, 1);
        player.getPlayerAssistant().addSkillXP(MOLTEN_GLASS_XP, Constants.CRAFTING);
        player.getPacketSender().sendMessage("You make molten glass.");
        return true;
    }

    public static boolean isFurnace(int objectId) {
        for (int furnace : FURNACES) {
            if (furnace == objectId) {
                return true;
            }
        }
        return false;
    }

    private static boolean isGlassIngredient(int itemId) {
        return itemId == StaticItemList.BUCKET_OF_SAND || itemId == StaticItemList.SODA_ASH;
    }
}
