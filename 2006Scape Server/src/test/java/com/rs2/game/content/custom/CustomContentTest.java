package com.rs2.game.content.custom;

import com.rs2.Constants;
import com.rs2.GameEngine;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.content.StaticNpcList;
import com.rs2.game.content.custom.quests.lumbridge.pantrypanic.PantryPanicQuest;
import com.rs2.game.content.quests.QuestAssistant;
import com.rs2.game.items.GroundItem;
import com.rs2.game.players.Client;
import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import org.apollo.cache.def.ItemDefinition;
import org.junit.After;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;

import java.io.BufferedWriter;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.util.Map;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

public class CustomContentTest {

    private static final int TEST_PLAYER_ID = 1;
    private static final int LUMBRIDGE_X = 3209;
    private static final int LUMBRIDGE_Y = 3214;

    private TestClient player;

    @BeforeClass
    public static void initialiseItemDefinitions() {
        if (ItemDefinition.getDefinitions() != null) {
            return;
        }
        ItemDefinition[] definitions = new ItemDefinition[10000];
        for (int id = 0; id < definitions.length; id++) {
            definitions[id] = new ItemDefinition(id);
            definitions[id].setName("item-" + id);
        }
        definitions[StaticItemList.COINS_995].setStackable(true);
        ItemDefinition.init(definitions);
    }

    @Before
    public void setUp() {
        player = new TestClient(TEST_PLAYER_ID);
        player.playerName = "questtester";
        player.playerRights = 2;
        player.absX = LUMBRIDGE_X;
        player.absY = LUMBRIDGE_Y;
        player.heightLevel = 0;
        PlayerHandler.players[TEST_PLAYER_ID] = player;
        GameEngine.itemHandler.items.clear();
    }

    @After
    public void tearDown() {
        PlayerHandler.players[TEST_PLAYER_ID] = null;
        GameEngine.itemHandler.items.clear();
    }

    @Test
    public void registryContributesQuestPointsAndQuestButtonInformation() throws Exception {
        assertEquals(1, CustomContent.getTotalQuestPoints());
        assertEquals(QuestAssistant.BASE_QUESTPOINTS + 1, QuestAssistant.MAXIMUM_QUESTPOINTS);

        assertFalse(CustomContent.showQuestInformation(player, -1));
        assertTrue(CustomContent.showQuestInformation(player, PantryPanicQuest.QUEST_BUTTON));
        assertEquals(PantryPanicQuest.NAME, interfaceText(player, 8144));
    }

    @Test
    public void saveLayerReadsLegacyAndGenericStagesButWritesGenericKeysOnly() throws Exception {
        assertTrue(CustomContent.loadPlayerSaveValue(player, "pantryPanic", "4"));
        assertEquals(PantryPanicQuest.REPORT_TO_DUKE, CustomQuestState.get(player, "pantryPanic"));

        TestClient genericPlayer = new TestClient(TEST_PLAYER_ID);
        assertTrue(CustomContent.loadPlayerSaveValue(genericPlayer, "customQuestStage-pantryPanic", "3"));
        assertEquals(PantryPanicQuest.RETURN_TO_COOK, CustomQuestState.get(genericPlayer, "pantryPanic"));
        assertFalse(CustomContent.loadPlayerSaveValue(genericPlayer, "cookAss", "1"));

        StringWriter output = new StringWriter();
        BufferedWriter writer = new BufferedWriter(output);
        CustomContent.savePlayerQuestStages(writer, genericPlayer);
        writer.flush();

        assertEquals("customQuestStage-pantryPanic = 3" + System.lineSeparator(), output.toString());
        assertFalse(output.toString().startsWith("pantryPanic = "));
    }

    @Test
    public void pantryPanicQuestCompletesThroughCustomRegistryHooks() {
        assertEquals(PantryPanicQuest.NOT_STARTED, CustomQuestState.get(player, "pantryPanic"));

        assertTrue(CustomContent.handleNpcClick(player, StaticNpcList.HANS));
        continueDialogue();
        continueDialogue();
        assertTrue(player.dialogueAction != 0);

        assertTrue(CustomContent.handleDialogueOption(player, 9167));
        continueDialogue();
        assertEquals(PantryPanicQuest.SPEAK_TO_COOK, CustomQuestState.get(player, "pantryPanic"));

        assertTrue(CustomContent.handleNpcClick(player, StaticNpcList.COOK));
        continueDialogue();
        assertEquals(PantryPanicQuest.SEARCH_PANTRY, CustomQuestState.get(player, "pantryPanic"));

        addInventoryItem(StaticItemList.EGG, 1);
        addInventoryItem(StaticItemList.BUCKET_OF_MILK, 1);
        assertTrue(CustomContent.handleObjectClick(player, 354, LUMBRIDGE_X, LUMBRIDGE_Y));
        assertEquals(PantryPanicQuest.RETURN_TO_COOK, CustomQuestState.get(player, "pantryPanic"));
        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.CABBAGE, 1));

        assertTrue(CustomContent.handleItemOnNpc(player, StaticItemList.CABBAGE, StaticNpcList.COOK));
        continueDialogue();
        assertEquals(PantryPanicQuest.REPORT_TO_DUKE, CustomQuestState.get(player, "pantryPanic"));
        assertFalse(player.getItemAssistant().playerHasItem(StaticItemList.CABBAGE, 1));
        assertFalse(player.getItemAssistant().playerHasItem(StaticItemList.EGG, 1));
        assertFalse(player.getItemAssistant().playerHasItem(StaticItemList.BUCKET_OF_MILK, 1));

        assertTrue(CustomContent.handleNpcClick(player, StaticNpcList.DUKE_HORACIO));
        continueDialogue();
        continueDialogue();

        assertEquals(PantryPanicQuest.COMPLETE, CustomQuestState.get(player, "pantryPanic"));
        assertEquals(1, player.questPoints);
        assertEquals(1154, player.playerXP[Constants.COOKING]);
        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.COINS_995, 10000));
        assertEquals(50, totalInventoryAndGroundItems(StaticItemList.LOBSTER));
    }

    @Test
    public void customInteractionHooksIgnoreUnrelatedContent() {
        assertFalse(CustomContent.handleDialogue(player, -1, -1));
        assertFalse(CustomContent.handleDialogueOption(player, 9167));
        assertFalse(CustomContent.handleNpcClick(player, -1));
        assertFalse(CustomContent.handleObjectClick(player, 354, 1, 1));
        assertFalse(CustomContent.handleItemOnNpc(player, StaticItemList.CABBAGE, StaticNpcList.HANS));
    }

    private void continueDialogue() {
        assertTrue("Expected custom dialogue " + player.nextChat + " to continue",
                CustomContent.handleDialogue(player, player.nextChat, player.talkingNpc));
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

    private int totalInventoryAndGroundItems(int itemId) {
        int total = 0;
        for (int slot = 0; slot < player.playerItems.length; slot++) {
            if (player.playerItems[slot] == itemId + 1) {
                total += player.playerItemsN[slot];
            }
        }
        for (GroundItem item : GameEngine.itemHandler.items) {
            if (item.getItemId() == itemId && item.getItemX() == LUMBRIDGE_X && item.getItemY() == LUMBRIDGE_Y) {
                total += item.getItemAmount();
            }
        }
        return total;
    }

    private static String interfaceText(Player player, int id) throws Exception {
        Field field = Player.class.getDeclaredField("interfaceText");
        field.setAccessible(true);
        Map<?, ?> textById = (Map<?, ?>) field.get(player);
        Object text = textById.get(id);
        assertNotNull("Expected interface text for id " + id, text);
        Field state = text.getClass().getDeclaredField("currentState");
        state.setAccessible(true);
        return (String) state.get(text);
    }

    private static final class TestClient extends Client {
        private TestClient(int playerId) {
            super(null, playerId);
            outStream = null;
        }
    }
}
