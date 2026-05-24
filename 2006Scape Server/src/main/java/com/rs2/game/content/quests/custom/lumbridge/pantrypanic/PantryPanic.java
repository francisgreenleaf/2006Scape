package com.rs2.game.content.quests.custom.lumbridge.pantrypanic;

import com.rs2.Constants;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.content.StaticNpcList;
import com.rs2.game.content.quests.QuestAssistant;
import com.rs2.game.content.quests.QuestRewards;
import com.rs2.game.players.Player;
import com.rs2.world.Boundary;

public class PantryPanic {

    public static final String NAME = "Pantry Panic";
    public static final int QUEST_BUTTON = 28200;
    public static final int QUEST_TAB_LINE = 7368;

    public static final int NOT_STARTED = 0;
    public static final int SPEAK_TO_COOK = 1;
    public static final int SEARCH_PANTRY = 2;
    public static final int RETURN_TO_COOK = 3;
    public static final int REPORT_TO_DUKE = 4;
    public static final int COMPLETE = 5;

    private static final int HANS = StaticNpcList.HANS;
    private static final int COOK = StaticNpcList.COOK;
    private static final int DUKE_HORACIO = StaticNpcList.DUKE_HORACIO;

    private static final int CABBAGE = StaticItemList.CABBAGE;
    private static final int BREAD = StaticItemList.BREAD;
    private static final int COINS = StaticItemList.COINS_995;

    private static final int START = 8000;
    private static final int START_2 = 8001;
    private static final int START_OPTION = 8002;
    private static final int ACCEPT = 8003;
    private static final int ACCEPT_2 = 8004;
    private static final int DECLINE = 8005;
    private static final int HANS_REMINDER_COOK = 8006;
    private static final int HANS_REMINDER_DUKE = 8007;

    private static final int COOK_START = 8010;
    private static final int COOK_START_2 = 8011;
    private static final int COOK_SEARCH_REMINDER = 8012;
    private static final int COOK_HAND_IN = 8013;
    private static final int COOK_HAND_IN_2 = 8014;
    private static final int COOK_DUKE_REMINDER = 8015;
    private static final int COOK_LOST_CABBAGE = 8016;

    private static final int DUKE_COMPLETE = 8020;
    private static final int DUKE_COMPLETE_2 = 8021;
    private static final int DUKE_COMPLETE_3 = 8022;

    private static final int ACTION_START = 8000;

    private static final int[] PANTRY_OBJECTS = {
            354, 355, 356, 357, 358, 365, 1013
    };

    private PantryPanic() {
    }

    public static boolean handleNpcClick(Player player, int npcType) {
        if (npcType == HANS) {
            handleHans(player);
            return true;
        }
        if (npcType == COOK && player.pantryPanic > NOT_STARTED && player.pantryPanic < COMPLETE) {
            handleCook(player);
            return true;
        }
        if (npcType == DUKE_HORACIO && player.pantryPanic == REPORT_TO_DUKE) {
            player.getDialogueHandler().sendDialogues(DUKE_COMPLETE, npcType);
            return true;
        }
        return false;
    }

    public static boolean handleDialogue(Player player, int dialogue, int npcId) {
        switch (dialogue) {
            case START:
                player.getDialogueHandler().sendNpcChat3(
                        "Good day. I am walking the castle rounds, but the",
                        "Duke's supper has run into a small panic.",
                        "The pantry count and the cook's count do not match.",
                        HANS, "Hans");
                player.nextChat = START_2;
                return true;
            case START_2:
                player.getDialogueHandler().sendNpcChat3(
                        "The cook needs a calm pair of hands before the Duke",
                        "asks awkward questions. Could you speak with him",
                        "and see what is missing?",
                        HANS, "Hans");
                player.nextChat = START_OPTION;
                return true;
            case START_OPTION:
                player.getDialogueHandler().sendOption(
                        "I'll help with the pantry.",
                        "That sounds like kitchen trouble.");
                player.dialogueAction = ACTION_START;
                return true;
            case ACCEPT:
                player.getDialogueHandler().sendPlayerChat("I'll help with the pantry.");
                player.nextChat = ACCEPT_2;
                return true;
            case ACCEPT_2:
                player.pantryPanic = SPEAK_TO_COOK;
                QuestAssistant.sendStages(player);
                player.getDialogueHandler().sendNpcChat2(
                        "Thank you. The cook is in the Lumbridge Castle",
                        "kitchen. He will know what needs finding.",
                        HANS, "Hans");
                player.nextChat = 0;
                return true;
            case DECLINE:
                player.getDialogueHandler().sendPlayerChat("That sounds like kitchen trouble.");
                player.nextChat = 0;
                return true;
            case HANS_REMINDER_COOK:
                player.getDialogueHandler().sendNpcChat2(
                        "Please speak with the cook in the castle kitchen.",
                        "He was muttering about a missing vegetable.",
                        HANS, "Hans");
                player.nextChat = 0;
                return true;
            case HANS_REMINDER_DUKE:
                player.getDialogueHandler().sendNpcChat2(
                        "The cook says the matter is settled. Please report",
                        "to Duke Horacio upstairs.",
                        HANS, "Hans");
                player.nextChat = 0;
                return true;
            case COOK_START:
                player.getDialogueHandler().sendNpcChat3(
                        "Hans sent you? Excellent! I counted the pantry twice,",
                        "and I am one cabbage short for the Duke's supper.",
                        "I know it is somewhere in this castle.",
                        COOK, "Cook");
                player.nextChat = COOK_START_2;
                return true;
            case COOK_START_2:
                player.pantryPanic = SEARCH_PANTRY;
                QuestAssistant.sendStages(player);
                player.getDialogueHandler().sendNpcChat3(
                        "Search the sacks, shelves, or crates around the",
                        "Lumbridge pantry. Bring me one cabbage and I can",
                        "finish the meal before anyone notices.",
                        COOK, "Cook");
                player.nextChat = 0;
                return true;
            case COOK_SEARCH_REMINDER:
                player.getDialogueHandler().sendNpcChat2(
                        "Still no cabbage? Search the sacks, shelves, or",
                        "crates around Lumbridge Castle's kitchen.",
                        COOK, "Cook");
                player.nextChat = 0;
                return true;
            case COOK_HAND_IN:
                player.getDialogueHandler().sendPlayerChat("I found this cabbage for the pantry.");
                player.nextChat = COOK_HAND_IN_2;
                return true;
            case COOK_HAND_IN_2:
                if (!player.getItemAssistant().playerHasItem(CABBAGE, 1)) {
                    player.pantryPanic = SEARCH_PANTRY;
                    QuestAssistant.sendStages(player);
                    player.getDialogueHandler().sendDialogues(COOK_LOST_CABBAGE, COOK);
                    return true;
                }
                player.getItemAssistant().deleteItem(CABBAGE, 1);
                player.pantryPanic = REPORT_TO_DUKE;
                QuestAssistant.sendStages(player);
                player.getDialogueHandler().sendNpcChat3(
                        "Perfect! The Duke's supper is saved. Please tell",
                        "Duke Horacio that the pantry is balanced and the",
                        "meal will be ready on time.",
                        COOK, "Cook");
                player.nextChat = 0;
                return true;
            case COOK_DUKE_REMINDER:
                player.getDialogueHandler().sendNpcChat2(
                        "Please tell Duke Horacio that the pantry is balanced.",
                        "He should be upstairs in Lumbridge Castle.",
                        COOK, "Cook");
                player.nextChat = 0;
                return true;
            case COOK_LOST_CABBAGE:
                player.getDialogueHandler().sendNpcChat2(
                        "You seem to have misplaced it. Search the pantry",
                        "again and bring me a cabbage.",
                        COOK, "Cook");
                player.nextChat = 0;
                return true;
            case DUKE_COMPLETE:
                player.getDialogueHandler().sendPlayerChat(
                        "The cook says the pantry is balanced and supper is safe.");
                player.nextChat = DUKE_COMPLETE_2;
                return true;
            case DUKE_COMPLETE_2:
                player.getDialogueHandler().sendNpcChat3(
                        "Splendid. Lumbridge depends on small duties done",
                        "well. Please accept a modest reward from the castle",
                        "stores, and my thanks.",
                        DUKE_HORACIO, "Duke Horacio");
                player.nextChat = DUKE_COMPLETE_3;
                return true;
            case DUKE_COMPLETE_3:
                complete(player);
                return true;
            default:
                return false;
        }
    }

    public static boolean handleDialogueOption(Player player, int buttonId) {
        if (player.dialogueAction != ACTION_START) {
            return false;
        }
        if (buttonId == 9167) {
            player.getDialogueHandler().sendDialogues(ACCEPT, HANS);
            return true;
        }
        if (buttonId == 9168) {
            player.getDialogueHandler().sendDialogues(DECLINE, HANS);
            return true;
        }
        return false;
    }

    public static boolean handleObjectClick(Player player, int objectType, int objectX, int objectY) {
        if (player.pantryPanic != SEARCH_PANTRY && player.pantryPanic != RETURN_TO_COOK) {
            return false;
        }
        if (!isPantryObject(objectType) || !Boundary.isIn(objectX, objectY, Boundary.LUMBRIDGE)) {
            return false;
        }
        if (player.getItemAssistant().playerHasItem(CABBAGE, 1)) {
            player.pantryPanic = RETURN_TO_COOK;
            QuestAssistant.sendStages(player);
            player.getDialogueHandler().sendStatement("You already have a cabbage for the cook.");
            return true;
        }
        player.getItemAssistant().addOrDropItem(CABBAGE, 1);
        player.pantryPanic = RETURN_TO_COOK;
        QuestAssistant.sendStages(player);
        player.getDialogueHandler().sendItemChat(CABBAGE, 150, "",
                "You search carefully and find a firm cabbage",
                "wedged behind the pantry sacks.");
        return true;
    }

    public static boolean handleItemOnNpc(Player player, int itemId, int npcId) {
        if (npcId != COOK || itemId != CABBAGE) {
            return false;
        }
        if (player.pantryPanic != SEARCH_PANTRY && player.pantryPanic != RETURN_TO_COOK) {
            return false;
        }
        player.getDialogueHandler().sendDialogues(COOK_HAND_IN, npcId);
        return true;
    }

    public static void showInformation(Player player) {
        clearQuestInterface(player);
        player.getPacketSender().sendString(NAME, 8144);
        player.getPacketSender().sendString("", 8145);
        if (player.pantryPanic == NOT_STARTED) {
            player.getPacketSender().sendString("I can start this quest by speaking to Hans in", 8147);
            player.getPacketSender().sendString("Lumbridge Castle.", 8148);
            player.getPacketSender().sendString("", 8149);
            player.getPacketSender().sendString("There are no minimum requirements.", 8150);
        } else if (player.pantryPanic == SPEAK_TO_COOK) {
            player.getPacketSender().sendString("@str@Hans asked me to help with the castle pantry.", 8147);
            player.getPacketSender().sendString("I should speak to the Cook in Lumbridge Castle's", 8148);
            player.getPacketSender().sendString("kitchen.", 8149);
        } else if (player.pantryPanic == SEARCH_PANTRY) {
            player.getPacketSender().sendString("@str@I spoke to the Cook.", 8147);
            player.getPacketSender().sendString("He needs one cabbage for the Duke's supper.", 8148);
            player.getPacketSender().sendString("I should search sacks, shelves, or crates around", 8149);
            player.getPacketSender().sendString("Lumbridge Castle's kitchen.", 8150);
        } else if (player.pantryPanic == RETURN_TO_COOK) {
            player.getPacketSender().sendString("@str@I found a cabbage in Lumbridge Castle.", 8147);
            player.getPacketSender().sendString("I should bring it back to the Cook.", 8148);
        } else if (player.pantryPanic == REPORT_TO_DUKE) {
            player.getPacketSender().sendString("@str@I gave the Cook a cabbage.", 8147);
            player.getPacketSender().sendString("I should tell Duke Horacio the pantry problem", 8148);
            player.getPacketSender().sendString("has been solved.", 8149);
        } else {
            player.getPacketSender().sendString("@str@I helped Hans check the pantry.", 8147);
            player.getPacketSender().sendString("@str@I found a cabbage for the Cook.", 8148);
            player.getPacketSender().sendString("@str@I reported the good news to Duke Horacio.", 8149);
            player.getPacketSender().sendString("@red@     QUEST COMPLETE", 8151);
            player.getPacketSender().sendString("As a reward, I gained 250 Cooking XP,", 8152);
            player.getPacketSender().sendString("150 coins, and a loaf of bread.", 8153);
        }
        player.getPacketSender().showInterface(8134);
    }

    public static void sendQuestTab(Player player) {
        if (player.pantryPanic == NOT_STARTED) {
            player.getPacketSender().sendString(NAME, QUEST_TAB_LINE);
        } else if (player.pantryPanic == COMPLETE) {
            player.getPacketSender().sendString("@gre@" + NAME, QUEST_TAB_LINE);
        } else {
            player.getPacketSender().sendString("@yel@" + NAME, QUEST_TAB_LINE);
        }
    }

    private static void handleHans(Player player) {
        if (player.pantryPanic == NOT_STARTED) {
            player.getDialogueHandler().sendDialogues(START, HANS);
        } else if (player.pantryPanic == REPORT_TO_DUKE) {
            player.getDialogueHandler().sendDialogues(HANS_REMINDER_DUKE, HANS);
        } else if (player.pantryPanic == COMPLETE) {
            player.getDialogueHandler().sendNpcChat1(
                    "The castle pantry is still in good order, thanks to you.",
                    HANS, "Hans");
            player.nextChat = 0;
        } else {
            player.getDialogueHandler().sendDialogues(HANS_REMINDER_COOK, HANS);
        }
    }

    private static void handleCook(Player player) {
        if (player.pantryPanic == SPEAK_TO_COOK) {
            player.getDialogueHandler().sendDialogues(COOK_START, COOK);
        } else if (player.pantryPanic == SEARCH_PANTRY && player.getItemAssistant().playerHasItem(CABBAGE, 1)) {
            player.getDialogueHandler().sendDialogues(COOK_HAND_IN, COOK);
        } else if (player.pantryPanic == SEARCH_PANTRY) {
            player.getDialogueHandler().sendDialogues(COOK_SEARCH_REMINDER, COOK);
        } else if (player.pantryPanic == RETURN_TO_COOK && player.getItemAssistant().playerHasItem(CABBAGE, 1)) {
            player.getDialogueHandler().sendDialogues(COOK_HAND_IN, COOK);
        } else if (player.pantryPanic == RETURN_TO_COOK) {
            player.pantryPanic = SEARCH_PANTRY;
            QuestAssistant.sendStages(player);
            player.getDialogueHandler().sendDialogues(COOK_LOST_CABBAGE, COOK);
        } else {
            player.getDialogueHandler().sendDialogues(COOK_DUKE_REMINDER, COOK);
        }
    }

    private static void complete(Player player) {
        if (player.pantryPanic == COMPLETE) {
            player.getPacketSender().closeAllWindows();
            return;
        }
        player.pantryPanic = COMPLETE;
        player.questPoints++;
        player.getPlayerAssistant().addSkillXP(250, Constants.COOKING);
        player.getItemAssistant().addOrDropItem(COINS, 150);
        player.getItemAssistant().addOrDropItem(BREAD, 1);
        QuestRewards.questReward(player, NAME, "1 Quest Point", "250 Cooking XP", "150 Coins",
                "A loaf of bread", "", "", BREAD);
        player.getPacketSender().sendString("@gre@" + NAME, QUEST_TAB_LINE);
    }

    private static boolean isPantryObject(int objectType) {
        for (int pantryObject : PANTRY_OBJECTS) {
            if (pantryObject == objectType) {
                return true;
            }
        }
        return false;
    }

    private static void clearQuestInterface(Player player) {
        for (int i = 8144; i < 8196; i++) {
            player.getPacketSender().sendString("", i);
        }
        for (int i = 12174; i < (12174 + 50); i++) {
            player.getPacketSender().sendString("", i);
        }
        for (int i = 14945; i < (14945 + 100); i++) {
            player.getPacketSender().sendString("", i);
        }
    }
}
