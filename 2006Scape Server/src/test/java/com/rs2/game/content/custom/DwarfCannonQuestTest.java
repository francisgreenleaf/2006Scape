package com.rs2.game.content.custom;

import com.rs2.Constants;
import com.rs2.GameEngine;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.content.StaticNpcList;
import com.rs2.game.content.custom.quests.dwarvenmine.dwarfcannon.DwarfCannonQuest;
import com.rs2.game.content.quests.QuestAssistant;
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

public class DwarfCannonQuestTest {

    private static final int TEST_PLAYER_ID = 2;
    private static final int NULODION_X = 3010;
    private static final int NULODION_Y = 3452;

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
        player.playerName = "cannon-tester";
        player.playerRights = 2;
        player.absX = NULODION_X;
        player.absY = NULODION_Y;
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
        assertEquals(2, CustomContent.getTotalQuestPoints());
        assertEquals(QuestAssistant.BASE_QUESTPOINTS + 2, QuestAssistant.MAXIMUM_QUESTPOINTS);

        assertTrue(CustomContent.showQuestInformation(player, DwarfCannonQuest.QUEST_BUTTON));
        assertEquals(DwarfCannonQuest.NAME, interfaceText(player, 8144));
    }

    @Test
    public void dwarfCannonQuestCompletesThroughCustomNpcAndItemHooks() {
        assertEquals(DwarfCannonQuest.NOT_STARTED, CustomQuestState.get(player, "dwarfCannon"));

        assertTrue(CustomContent.handleNpcClick(player, StaticNpcList.NULODION));
        continueDialogue();
        continueDialogue();
        assertTrue(CustomContent.handleDialogueOption(player, 9167));
        continueDialogue();
        assertEquals(DwarfCannonQuest.NEEDS_CANNONBALL, CustomQuestState.get(player, "dwarfCannon"));

        addInventoryItem(StaticItemList.CANNONBALL, 1);
        assertTrue(CustomContent.handleItemOnNpc(player, StaticItemList.CANNONBALL, StaticNpcList.NULODION));
        continueDialogue();
        continueDialogue();

        assertEquals(DwarfCannonQuest.COMPLETE, CustomQuestState.get(player, "dwarfCannon"));
        assertEquals(1, player.questPoints);
        assertEquals(750, player.playerXP[Constants.SMITHING]);
        assertEquals(25, player.getItemAssistant().getItemAmount(StaticItemList.CANNONBALL) - 1);
    }

    @Test
    public void lostCannonRecoveryReturnsAllFourParts() {
        player.lostCannon = true;

        assertTrue(CustomContent.handleNpcClick(player, StaticNpcList.NULODION));
        continueDialogue();
        continueDialogue();
        assertTrue(CustomContent.handleDialogueOption(player, 9167));

        assertFalse(player.lostCannon);
        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.CANNON_BASE, 1));
        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.CANNON_STAND, 1));
        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.CANNON_BARRELS, 1));
        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.CANNON_FURNACE, 1));
    }

    @Test
    public void saveLayerUsesGenericQuestKeysForDwarfCannon() throws Exception {
        assertTrue(CustomContent.loadPlayerSaveValue(player, "customQuestStage-dwarfCannon", "1"));
        assertEquals(DwarfCannonQuest.NEEDS_CANNONBALL, CustomQuestState.get(player, "dwarfCannon"));

        StringWriter output = new StringWriter();
        BufferedWriter writer = new BufferedWriter(output);
        CustomContent.savePlayerQuestStages(writer, player);
        writer.flush();

        assertEquals("customQuestStage-dwarfCannon = 1" + System.lineSeparator(), output.toString());
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
