package com.rs2.game.content.custom;

import com.rs2.game.players.Player;

public interface CustomQuest {

    String getKey();

    String getName();

    int getQuestButton();

    int getQuestTabLine();

    int getQuestPoints();

    default boolean handlesLegacySaveKey(String key) {
        return false;
    }

    default void sendQuestTab(Player player) {
    }

    default void showInformation(Player player) {
    }

    default boolean handleDialogue(Player player, int dialogue, int npcId) {
        return false;
    }

    default boolean handleDialogueOption(Player player, int buttonId) {
        return false;
    }

    default boolean handleNpcClick(Player player, int npcType) {
        return false;
    }

    default boolean handleObjectClick(Player player, int objectType, int objectX, int objectY) {
        return false;
    }

    default boolean handleItemOnNpc(Player player, int itemId, int npcId) {
        return false;
    }
}
