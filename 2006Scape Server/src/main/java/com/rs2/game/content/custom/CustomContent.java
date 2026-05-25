package com.rs2.game.content.custom;

import java.io.BufferedWriter;
import java.io.IOException;

import com.rs2.game.content.custom.quests.lumbridge.pantrypanic.PantryPanicQuest;
import com.rs2.game.players.Player;

public final class CustomContent {

    private static final String SAVE_PREFIX = "customQuestStage-";

    private static final CustomQuest[] QUESTS = {
            PantryPanicQuest.INSTANCE
    };

    private CustomContent() {
    }

    public static int getTotalQuestPoints() {
        int total = 0;
        for (CustomQuest quest : QUESTS) {
            total += quest.getQuestPoints();
        }
        return total;
    }

    public static void sendQuestTabs(Player player) {
        for (CustomQuest quest : QUESTS) {
            quest.sendQuestTab(player);
        }
    }

    public static boolean showQuestInformation(Player player, int buttonId) {
        for (CustomQuest quest : QUESTS) {
            if (quest.getQuestButton() == buttonId) {
                quest.showInformation(player);
                return true;
            }
        }
        return false;
    }

    public static boolean handleDialogue(Player player, int dialogue, int npcId) {
        for (CustomQuest quest : QUESTS) {
            if (quest.handleDialogue(player, dialogue, npcId)) {
                return true;
            }
        }
        return false;
    }

    public static boolean handleDialogueOption(Player player, int buttonId) {
        for (CustomQuest quest : QUESTS) {
            if (quest.handleDialogueOption(player, buttonId)) {
                return true;
            }
        }
        return false;
    }

    public static boolean handleNpcClick(Player player, int npcType) {
        for (CustomQuest quest : QUESTS) {
            if (quest.handleNpcClick(player, npcType)) {
                return true;
            }
        }
        return false;
    }

    public static boolean handleObjectClick(Player player, int objectType, int objectX, int objectY) {
        for (CustomQuest quest : QUESTS) {
            if (quest.handleObjectClick(player, objectType, objectX, objectY)) {
                return true;
            }
        }
        return false;
    }

    public static boolean handleItemOnNpc(Player player, int itemId, int npcId) {
        for (CustomQuest quest : QUESTS) {
            if (quest.handleItemOnNpc(player, itemId, npcId)) {
                return true;
            }
        }
        return false;
    }

    public static boolean loadPlayerSaveValue(Player player, String key, String value) {
        if (key.startsWith(SAVE_PREFIX)) {
            CustomQuestState.set(player, key.substring(SAVE_PREFIX.length()), Integer.parseInt(value));
            return true;
        }
        for (CustomQuest quest : QUESTS) {
            if (quest.handlesLegacySaveKey(key)) {
                CustomQuestState.set(player, quest.getKey(), Integer.parseInt(value));
                return true;
            }
        }
        return false;
    }

    public static void savePlayerQuestStages(BufferedWriter characterfile, Player player) throws IOException {
        for (CustomQuest quest : QUESTS) {
            int stage = CustomQuestState.get(player, quest.getKey());
            if (stage > 0) {
                characterfile.write(SAVE_PREFIX + quest.getKey() + " = " + stage);
                characterfile.newLine();
            }
        }
    }
}
