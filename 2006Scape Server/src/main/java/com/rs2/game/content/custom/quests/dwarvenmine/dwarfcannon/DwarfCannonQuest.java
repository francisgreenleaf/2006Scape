package com.rs2.game.content.custom.quests.dwarvenmine.dwarfcannon;

import com.rs2.Constants;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.content.StaticNpcList;
import com.rs2.game.content.custom.CustomQuest;
import com.rs2.game.content.custom.CustomQuestState;
import com.rs2.game.content.quests.QuestAssistant;
import com.rs2.game.content.quests.QuestRewards;
import com.rs2.game.players.Player;

public final class DwarfCannonQuest implements CustomQuest {

    public static final DwarfCannonQuest INSTANCE = new DwarfCannonQuest();

    private static final String KEY = "dwarfCannon";

    public static final String NAME = "Dwarf Cannon";
    public static final int QUEST_BUTTON = 28188;
    public static final int QUEST_TAB_LINE = 7356;

    public static final int NOT_STARTED = 0;
    public static final int NEEDS_CANNONBALL = 1;
    public static final int COMPLETE = 2;

    private static final int NULODION = StaticNpcList.NULODION;
    private static final int SHOP_ID = 144;
    private static final int CANNONBALL = StaticItemList.CANNONBALL;

    private static final int START_INTRO = 8400;
    private static final int START_INFO = 8401;
    private static final int START_OPTIONS = 8402;
    private static final int START_ACCEPT = 8403;
    private static final int START_ACCEPT_2 = 8404;

    private static final int REMINDER_INFO = 8410;
    private static final int REMINDER_OPTIONS = 8411;

    private static final int RECOVERY_INFO = 8420;
    private static final int RECOVERY_OPTIONS = 8421;
    private static final int RECOVERY_CONFIRM = 8422;

    private static final int COMPLETE_PLAYER = 8430;
    private static final int COMPLETE_INFO = 8431;
    private static final int COMPLETE_FINISH = 8432;

    private static final int ACTION_START = 8400;
    private static final int ACTION_REMINDER = 8410;
    private static final int ACTION_RECOVERY = 8420;

    private DwarfCannonQuest() {
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
    public boolean handleNpcClick(Player player, int npcType) {
        if (npcType != NULODION) {
            return false;
        }

        if (player.lostCannon) {
            player.getDialogueHandler().sendDialogues(RECOVERY_INFO, NULODION);
            return true;
        }

        if (stage(player) == COMPLETE) {
            player.dialogueAction = 0;
            player.nextChat = 0;
            player.getShopAssistant().openShop(SHOP_ID);
            return true;
        }

        if (stage(player) == NEEDS_CANNONBALL) {
            if (player.getItemAssistant().playerHasItem(CANNONBALL, 1)) {
                player.getDialogueHandler().sendDialogues(COMPLETE_PLAYER, NULODION);
            } else {
                player.getDialogueHandler().sendDialogues(REMINDER_INFO, NULODION);
            }
            return true;
        }

        player.getDialogueHandler().sendDialogues(START_INTRO, NULODION);
        return true;
    }

    @Override
    public boolean handleDialogue(Player player, int dialogue, int npcId) {
        switch (dialogue) {
            case START_INTRO:
                player.getDialogueHandler().sendNpcChat2(
                        "Aye. If you're after a dwarf cannon, you need to know",
                        "how to make cannonballs first.",
                        NULODION, "Nulodion");
                player.nextChat = START_INFO;
                return true;
            case START_INFO:
                player.getDialogueHandler().sendNpcChat2(
                        "Take an ammo mould and a steel bar to a furnace.",
                        "If you can make a cannonball, I'll trust you with the rest.",
                        NULODION, "Nulodion");
                player.nextChat = START_OPTIONS;
                return true;
            case START_OPTIONS:
                player.getDialogueHandler().sendOption("Teach me.", "Can I buy parts?");
                player.dialogueAction = ACTION_START;
                return true;
            case START_ACCEPT:
                player.getDialogueHandler().sendPlayerChat("Teach me.");
                player.nextChat = START_ACCEPT_2;
                return true;
            case START_ACCEPT_2:
                setStage(player, NEEDS_CANNONBALL);
                QuestAssistant.sendStages(player);
                player.getDialogueHandler().sendNpcChat2(
                        "Good. Come back when you've made one cannonball.",
                        "The shop stays open if you need the parts.",
                        NULODION, "Nulodion");
                player.dialogueAction = 0;
                player.nextChat = 0;
                return true;
            case REMINDER_INFO:
                player.getDialogueHandler().sendNpcChat2(
                        "You've got the basics now.",
                        "Make one cannonball with an ammo mould and steel bar, then return.",
                        NULODION, "Nulodion");
                player.nextChat = REMINDER_OPTIONS;
                return true;
            case REMINDER_OPTIONS:
                player.getDialogueHandler().sendOption("Open the shop.", "Got it.");
                player.dialogueAction = ACTION_REMINDER;
                return true;
            case RECOVERY_INFO:
                player.getDialogueHandler().sendNpcChat2(
                        "I see you've lost your cannon.",
                        "If you've got four free inventory spaces, I can put the parts back together.",
                        NULODION, "Nulodion");
                player.nextChat = RECOVERY_OPTIONS;
                return true;
            case RECOVERY_OPTIONS:
                player.getDialogueHandler().sendOption("Recover it.", "Can I buy parts?");
                player.dialogueAction = ACTION_RECOVERY;
                return true;
            case RECOVERY_CONFIRM:
                if (player.getItemAssistant().freeSlots() >= 4) {
                    player.getDialogueHandler().sendNpcChat1(
                            "There you are. Try not to lose it again.",
                            NULODION, "Nulodion");
                    for (int i = 0; i < 4; i++) {
                        player.getItemAssistant().addItem(player.getCannon().ITEM_PARTS[i], 1);
                    }
                    player.lostCannon = false;
                } else {
                    player.getDialogueHandler().sendNpcChat1(
                            "You need at least 4 free inventory spots.",
                            NULODION, "Nulodion");
                }
                player.dialogueAction = 0;
                player.nextChat = 0;
                return true;
            case COMPLETE_PLAYER:
                player.getDialogueHandler().sendPlayerChat("I've made a cannonball.");
                player.nextChat = COMPLETE_INFO;
                return true;
            case COMPLETE_INFO:
                player.getDialogueHandler().sendNpcChat2(
                        "Good. You've got the basics.",
                        "I'll mark the quest complete and keep the shop open.",
                        NULODION, "Nulodion");
                player.nextChat = COMPLETE_FINISH;
                return true;
            case COMPLETE_FINISH:
                complete(player);
                player.dialogueAction = 0;
                player.nextChat = 0;
                return true;
            default:
                return false;
        }
    }

    @Override
    public boolean handleDialogueOption(Player player, int buttonId) {
        if (player.dialogueAction == ACTION_START) {
            if (buttonId == 9167) {
                player.getDialogueHandler().sendDialogues(START_ACCEPT, NULODION);
                return true;
            }
            if (buttonId == 9168) {
                player.dialogueAction = 0;
                player.nextChat = 0;
                player.getShopAssistant().openShop(SHOP_ID);
                return true;
            }
            return false;
        }
        if (player.dialogueAction == ACTION_REMINDER) {
            if (buttonId == 9167) {
                player.dialogueAction = 0;
                player.nextChat = 0;
                player.getShopAssistant().openShop(SHOP_ID);
                return true;
            }
            if (buttonId == 9168) {
                player.dialogueAction = 0;
                player.nextChat = 0;
                player.getPacketSender().closeAllWindows();
                return true;
            }
            return false;
        }
        if (player.dialogueAction == ACTION_RECOVERY) {
            if (buttonId == 9167) {
                player.getDialogueHandler().sendDialogues(RECOVERY_CONFIRM, NULODION);
                return true;
            }
            if (buttonId == 9168) {
                player.dialogueAction = 0;
                player.nextChat = 0;
                player.getShopAssistant().openShop(SHOP_ID);
                return true;
            }
            return false;
        }
        return false;
    }

    @Override
    public boolean handleItemOnNpc(Player player, int itemId, int npcId) {
        if (npcId != NULODION || itemId != CANNONBALL) {
            return false;
        }
        if (stage(player) != NEEDS_CANNONBALL) {
            return false;
        }
        player.getDialogueHandler().sendDialogues(COMPLETE_PLAYER, npcId);
        return true;
    }

    @Override
    public void showInformation(Player player) {
        clearQuestInterface(player);
        player.getPacketSender().sendString(NAME, 8144);
        player.getPacketSender().sendString("", 8145);
        if (stage(player) == NOT_STARTED) {
            player.getPacketSender().sendString("I can start this quest by speaking to Nulodion.", 8147);
            player.getPacketSender().sendString("He can sell me cannon parts and explain the", 8148);
            player.getPacketSender().sendString("cannonball process.", 8149);
        } else if (stage(player) == NEEDS_CANNONBALL) {
            player.getPacketSender().sendString("@str@I spoke to Nulodion about the dwarf cannon.", 8147);
            player.getPacketSender().sendString("I need to make one cannonball with an ammo mould", 8148);
            player.getPacketSender().sendString("and a steel bar, then bring it back to him.", 8149);
        } else {
            player.getPacketSender().sendString("@str@I proved I can make cannonballs.", 8147);
            player.getPacketSender().sendString("@str@Nulodion is satisfied with my work.", 8148);
            player.getPacketSender().sendString("@gre@     QUEST COMPLETE", 8151);
            player.getPacketSender().sendString("As a reward, I gained 1 Quest Point,", 8152);
            player.getPacketSender().sendString("750 Smithing XP, and 25 cannonballs.", 8153);
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

    private static int stage(Player player) {
        return CustomQuestState.get(player, KEY);
    }

    private static void setStage(Player player, int stage) {
        CustomQuestState.set(player, KEY, stage);
    }

    private static void complete(Player player) {
        if (stage(player) == COMPLETE) {
            player.getPacketSender().closeAllWindows();
            return;
        }
        setStage(player, COMPLETE);
        player.questPoints++;
        player.getPlayerAssistant().addSkillXP(750, Constants.SMITHING);
        player.getItemAssistant().addOrDropItem(CANNONBALL, 25);
        QuestAssistant.sendStages(player);
        QuestRewards.questReward(player, NAME, "1 Quest Point", "750 Smithing XP", "25 Cannonballs", "", "", "", CANNONBALL);
        player.getPacketSender().sendString("@gre@" + NAME, QUEST_TAB_LINE);
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
