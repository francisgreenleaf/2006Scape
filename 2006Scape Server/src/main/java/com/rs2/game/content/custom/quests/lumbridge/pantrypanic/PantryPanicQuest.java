package com.rs2.game.content.custom.quests.lumbridge.pantrypanic;

import com.rs2.Constants;
import com.rs2.game.content.custom.CustomQuest;
import com.rs2.game.content.custom.CustomQuestState;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.content.StaticNpcList;
import com.rs2.game.content.quests.QuestAssistant;
import com.rs2.game.content.quests.QuestRewards;
import com.rs2.game.dialogues.ChatEmotes;
import com.rs2.game.players.Player;
import com.rs2.world.Boundary;

public class PantryPanicQuest implements CustomQuest {

    public static final PantryPanicQuest INSTANCE = new PantryPanicQuest();

    private static final String KEY = "pantryPanic";
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
    private static final int EGG = StaticItemList.EGG;
    private static final int BUCKET_OF_MILK = StaticItemList.BUCKET_OF_MILK;
    private static final int LOBSTER = StaticItemList.LOBSTER;
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

    private PantryPanicQuest() {
    }

    @Override
    public String getKey() {
        return KEY;
    }

    @Override
    public String getName() {
        return NAME;
    }

    @Override
    public int getQuestButton() {
        return QUEST_BUTTON;
    }

    @Override
    public int getQuestTabLine() {
        return QUEST_TAB_LINE;
    }

    @Override
    public int getQuestPoints() {
        return 1;
    }

    @Override
    public boolean handlesLegacySaveKey(String key) {
        return KEY.equals(key);
    }

    @Override
    public boolean handleNpcClick(Player player, int npcType) {
        if (npcType == HANS) {
            handleHans(player);
            return true;
        }
        if (npcType == COOK && stage(player) > NOT_STARTED && stage(player) < COMPLETE) {
            handleCook(player);
            return true;
        }
        if (npcType == DUKE_HORACIO && stage(player) == REPORT_TO_DUKE) {
            player.getDialogueHandler().sendDialogues(DUKE_COMPLETE, npcType);
            return true;
        }
        return false;
    }

    @Override
    public boolean handleDialogue(Player player, int dialogue, int npcId) {
        switch (dialogue) {
            case START:
                player.getDialogueHandler().sendNpcChat3(
                        "Good day. I am conducting urgent castle business.",
                        "That means walking in circles while looking",
                        "slightly more worried than usual.",
                        HANS, "Hans");
                player.nextChat = START_2;
                return true;
            case START_2:
                player.getDialogueHandler().sendNpcChat3(
                        "The Duke's Moonlit Supper is tonight.",
                        "It is an old Lumbridge tradition where nobles eat",
                        "something dreadful and call it heritage.",
                        HANS, "Hans");
                player.nextChat = START_OPTION;
                return true;
            case START_OPTION:
                player.getDialogueHandler().sendOption(
                        "I'll help save the supper.",
                        "This sounds like noble nonsense.");
                player.dialogueAction = ACTION_START;
                return true;
            case ACCEPT:
                player.getDialogueHandler().sendPlayerChat("I'll help save the supper.");
                player.nextChat = ACCEPT_2;
                return true;
            case ACCEPT_2:
                setStage(player, SPEAK_TO_COOK);
                QuestAssistant.sendStages(player);
                player.getDialogueHandler().sendNpcChat2(
                        "Good. The cook is in the kitchen, slowly",
                        "becoming soup.",
                        HANS, "Hans");
                player.nextChat = 0;
                return true;
            case DECLINE:
                player.getDialogueHandler().sendPlayerChat("This sounds like noble nonsense.");
                player.nextChat = 0;
                return true;
            case HANS_REMINDER_COOK:
                player.getDialogueHandler().sendNpcChat2(
                        "Please speak with the cook in the castle kitchen.",
                        "He has started apologising to the flour.",
                        HANS, "Hans");
                player.nextChat = 0;
                return true;
            case HANS_REMINDER_DUKE:
                player.getDialogueHandler().sendNpcChat2(
                        "The cook says the Moon-Pudding lives.",
                        "Please report this carefully to Duke Horacio.",
                        HANS, "Hans");
                player.nextChat = 0;
                return true;
            case COOK_START:
                sendCookChat(player, ChatEmotes.DRUNK_LEFT,
                        "Hansh sent you? Bless that walking coat rack.",
                        "I was yelling at flour, then the sherry",
                        "started making better points than me.");
                player.nextChat = COOK_START_2;
                return true;
            case COOK_START_2:
                setStage(player, SEARCH_PANTRY);
                QuestAssistant.sendStages(player);
                sendCookChat(player, ChatEmotes.DRUNK_RIGHT,
                        "The Moon-Pudding needs cabbage, egg, and milk.",
                        "Cabbage for body, egg for nerve, milk because",
                        "some ancestor was clearly hammered.");
                player.nextChat = 0;
                return true;
            case COOK_SEARCH_REMINDER:
                sendCookChat(player, ChatEmotes.DRUNK_LEFT,
                        "Still need the cabbage, egg, and milk.",
                        "The pudding is staring at me from the bowl.",
                        "Might be bubbles. Might be judgement.");
                player.nextChat = 0;
                return true;
            case COOK_HAND_IN:
                player.getDialogueHandler().sendPlayerChat("I've brought the cabbage, egg, and milk.");
                player.nextChat = COOK_HAND_IN_2;
                return true;
            case COOK_HAND_IN_2:
                if (!hasAllIngredients(player)) {
                    setStage(player, SEARCH_PANTRY);
                    QuestAssistant.sendStages(player);
                    player.getDialogueHandler().sendDialogues(COOK_LOST_CABBAGE, COOK);
                    return true;
                }
                player.getItemAssistant().deleteItem(CABBAGE, 1);
                player.getItemAssistant().deleteItem(EGG, 1);
                player.getItemAssistant().deleteItem(BUCKET_OF_MILK, 1);
                setStage(player, REPORT_TO_DUKE);
                QuestAssistant.sendStages(player);
                sendCookChat(player, ChatEmotes.DRUNK_RIGHT,
                        "There it is! Shit, look at it wobble.",
                        "Beautiful little culinary crime.",
                        "Tell the Duke I fought dinner and won.");
                player.nextChat = 0;
                return true;
            case COOK_DUKE_REMINDER:
                sendCookChat(player, ChatEmotes.DRUNK_LEFT,
                        "Go tell Duke Horacio the Moon-Pudding is ready.",
                        "If he asks why it blinked, you didn't see that.",
                        "Neither did I. Probably.");
                player.nextChat = 0;
                return true;
            case COOK_LOST_CABBAGE:
                sendCookChat(player, ChatEmotes.DRUNK_RIGHT,
                        "No, no, no. That's not the whole damn spell.",
                        "Cabbage, egg, milk. Three things.",
                        "Count 'em with me before the room does.");
                player.nextChat = 0;
                return true;
            case DUKE_COMPLETE:
                player.getDialogueHandler().sendPlayerChat(
                        "The cook says the Moon-Pudding is ready.");
                player.nextChat = DUKE_COMPLETE_2;
                return true;
            case DUKE_COMPLETE_2:
                player.getDialogueHandler().sendNpcChat3(
                        "Splendid. My grandmother would be proud,",
                        "and several guests will be polite.",
                        "Lumbridge remembers hard times with manners.",
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

    @Override
    public boolean handleDialogueOption(Player player, int buttonId) {
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

    @Override
    public boolean handleObjectClick(Player player, int objectType, int objectX, int objectY) {
        if (stage(player) != SEARCH_PANTRY && stage(player) != RETURN_TO_COOK) {
            return false;
        }
        if (!isPantryObject(objectType) || !Boundary.isIn(objectX, objectY, Boundary.LUMBRIDGE)) {
            return false;
        }
        if (player.getItemAssistant().playerHasItem(CABBAGE, 1)) {
            updateGatheringStage(player);
            QuestAssistant.sendStages(player);
            player.getDialogueHandler().sendStatement("The cabbage remains in your pack, plotting.");
            return true;
        }
        player.getItemAssistant().addOrDropItem(CABBAGE, 1);
        updateGatheringStage(player);
        QuestAssistant.sendStages(player);
        player.getDialogueHandler().sendItemChat(CABBAGE, 150, "",
                "You search the pantry and find a cabbage",
                "with the confidence of something that ruins dinner.");
        return true;
    }

    @Override
    public boolean handleItemOnNpc(Player player, int itemId, int npcId) {
        if (npcId != COOK || !isIngredient(itemId)) {
            return false;
        }
        if (stage(player) != SEARCH_PANTRY && stage(player) != RETURN_TO_COOK) {
            return false;
        }
        player.getDialogueHandler().sendDialogues(COOK_HAND_IN, npcId);
        return true;
    }

    @Override
    public void showInformation(Player player) {
        clearQuestInterface(player);
        player.getPacketSender().sendString(NAME, 8144);
        player.getPacketSender().sendString("", 8145);
        if (stage(player) == NOT_STARTED) {
            player.getPacketSender().sendString("I can start this quest by speaking to Hans in", 8147);
            player.getPacketSender().sendString("Lumbridge Castle.", 8148);
            player.getPacketSender().sendString("", 8149);
            player.getPacketSender().sendString("There are no minimum requirements.", 8150);
        } else if (stage(player) == SPEAK_TO_COOK) {
            player.getPacketSender().sendString("@str@Hans asked me to help with the castle pantry.", 8147);
            player.getPacketSender().sendString("I should speak to the Cook in Lumbridge Castle's", 8148);
            player.getPacketSender().sendString("kitchen.", 8149);
        } else if (stage(player) == SEARCH_PANTRY) {
            player.getPacketSender().sendString("@str@I spoke to the Cook.", 8147);
            player.getPacketSender().sendString("He needs a cabbage, an egg, and a bucket", 8148);
            player.getPacketSender().sendString("of milk for the Duke's Moonlit Supper.", 8149);
            player.getPacketSender().sendString("The cabbage should be in the castle pantry.", 8150);
        } else if (stage(player) == RETURN_TO_COOK) {
            player.getPacketSender().sendString("@str@I gathered the Moon-Pudding ingredients.", 8147);
            player.getPacketSender().sendString("I should bring them back to the Cook.", 8148);
        } else if (stage(player) == REPORT_TO_DUKE) {
            player.getPacketSender().sendString("@str@I gave the Cook the ingredients.", 8147);
            player.getPacketSender().sendString("I should tell Duke Horacio the Moonlit", 8148);
            player.getPacketSender().sendString("Supper has been saved.", 8149);
        } else {
            player.getPacketSender().sendString("@str@I helped Hans check the pantry.", 8147);
            player.getPacketSender().sendString("@str@I gathered the Moon-Pudding ingredients.", 8148);
            player.getPacketSender().sendString("@str@I reported the good news to Duke Horacio.", 8149);
            player.getPacketSender().sendString("@red@     QUEST COMPLETE", 8151);
            player.getPacketSender().sendString("As a reward, I gained 1,154 Cooking XP,", 8152);
            player.getPacketSender().sendString("10,000 coins, and 50 cooked lobsters.", 8153);
        }
        player.getPacketSender().showInterface(8134);
    }

    @Override
    public void sendQuestTab(Player player) {
        if (stage(player) == NOT_STARTED) {
            player.getPacketSender().sendString(NAME, QUEST_TAB_LINE);
        } else if (stage(player) == COMPLETE) {
            player.getPacketSender().sendString("@gre@" + NAME, QUEST_TAB_LINE);
        } else {
            player.getPacketSender().sendString("@yel@" + NAME, QUEST_TAB_LINE);
        }
    }

    private static void handleHans(Player player) {
        if (stage(player) == NOT_STARTED) {
            player.getDialogueHandler().sendDialogues(START, HANS);
        } else if (stage(player) == REPORT_TO_DUKE) {
            player.getDialogueHandler().sendDialogues(HANS_REMINDER_DUKE, HANS);
        } else if (stage(player) == COMPLETE) {
            player.getDialogueHandler().sendNpcChat1(
                    "The supper went well. The Duke smiled. That is my report.",
                    HANS, "Hans");
            player.nextChat = 0;
        } else {
            player.getDialogueHandler().sendDialogues(HANS_REMINDER_COOK, HANS);
        }
    }

    private static void handleCook(Player player) {
        if (stage(player) == SPEAK_TO_COOK) {
            player.getDialogueHandler().sendDialogues(COOK_START, COOK);
        } else if (stage(player) == SEARCH_PANTRY && hasAllIngredients(player)) {
            setStage(player, RETURN_TO_COOK);
            QuestAssistant.sendStages(player);
            player.getDialogueHandler().sendDialogues(COOK_HAND_IN, COOK);
        } else if (stage(player) == SEARCH_PANTRY) {
            player.getDialogueHandler().sendDialogues(COOK_SEARCH_REMINDER, COOK);
        } else if (stage(player) == RETURN_TO_COOK && hasAllIngredients(player)) {
            player.getDialogueHandler().sendDialogues(COOK_HAND_IN, COOK);
        } else if (stage(player) == RETURN_TO_COOK) {
            setStage(player, SEARCH_PANTRY);
            QuestAssistant.sendStages(player);
            player.getDialogueHandler().sendDialogues(COOK_LOST_CABBAGE, COOK);
        } else {
            player.getDialogueHandler().sendDialogues(COOK_DUKE_REMINDER, COOK);
        }
    }

    private static void complete(Player player) {
        if (stage(player) == COMPLETE) {
            player.getPacketSender().closeAllWindows();
            return;
        }
        setStage(player, COMPLETE);
        player.questPoints++;
        player.getPlayerAssistant().addSkillXP(1154, Constants.COOKING);
        player.getItemAssistant().addOrDropItem(COINS, 10000);
        player.getItemAssistant().addOrDropItem(LOBSTER, 50);
        QuestRewards.questReward(player, NAME, "1 Quest Point", "1,154 Cooking XP", "10,000 Coins",
                "50 Cooked Lobsters", "", "", LOBSTER);
        player.getPacketSender().sendString("@gre@" + NAME, QUEST_TAB_LINE);
    }

    private static boolean hasAllIngredients(Player player) {
        return player.getItemAssistant().playerHasItem(CABBAGE, 1)
                && player.getItemAssistant().playerHasItem(EGG, 1)
                && player.getItemAssistant().playerHasItem(BUCKET_OF_MILK, 1);
    }

    private static boolean isIngredient(int itemId) {
        return itemId == CABBAGE || itemId == EGG || itemId == BUCKET_OF_MILK;
    }

    private static void updateGatheringStage(Player player) {
        setStage(player, hasAllIngredients(player) ? RETURN_TO_COOK : SEARCH_PANTRY);
    }

    private static int stage(Player player) {
        return CustomQuestState.get(player, KEY);
    }

    private static void setStage(Player player, int stage) {
        CustomQuestState.set(player, KEY, stage);
    }

    private static void sendCookChat(Player player, ChatEmotes emote, String... lines) {
        player.getDialogueHandler().sendNpcChat(COOK, emote, lines);
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
