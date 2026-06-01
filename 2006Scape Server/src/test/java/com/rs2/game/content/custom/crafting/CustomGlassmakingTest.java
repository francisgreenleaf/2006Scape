package com.rs2.game.content.custom.crafting;

import com.rs2.Constants;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.content.custom.CustomContent;
import com.rs2.game.content.custom.CustomFeatureFlags;
import com.rs2.game.players.Client;
import org.apollo.cache.def.ItemDefinition;
import org.junit.After;
import org.junit.Before;
import org.junit.BeforeClass;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class CustomGlassmakingTest {

    private static final int ARDOUGNE_FURNACE = 2781;

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
        ItemDefinition.init(definitions);
    }

    @Before
    public void setUp() {
        CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED = false;
        player = new TestClient(1);
        player.playerName = "glasstester";
        player.playerLevel[Constants.CRAFTING] = 1;
    }

    @After
    public void tearDown() {
        CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED = false;
    }

    @Test
    public void glassmakingFallsThroughWhenCatherbyTraderFeatureIsDisabled() {
        addInventoryItem(StaticItemList.BUCKET_OF_SAND, 1);
        addInventoryItem(StaticItemList.SODA_ASH, 1);

        assertFalse(CustomContent.handleItemOnObject(player, StaticItemList.BUCKET_OF_SAND, ARDOUGNE_FURNACE, 2601, 3310));

        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.BUCKET_OF_SAND, 1));
        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.SODA_ASH, 1));
        assertFalse(player.getItemAssistant().playerHasItem(StaticItemList.MOLTEN_GLASS, 1));
        assertEquals(0, player.playerXP[Constants.CRAFTING]);
    }

    @Test
    public void sandAndSodaAshOnFurnaceCreatesMoltenGlassWithCraftingXp() {
        CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED = true;
        addInventoryItem(StaticItemList.BUCKET_OF_SAND, 1);
        addInventoryItem(StaticItemList.SODA_ASH, 1);

        assertTrue(CustomContent.handleItemOnObject(player, StaticItemList.BUCKET_OF_SAND, ARDOUGNE_FURNACE, 2601, 3310));

        assertFalse(player.getItemAssistant().playerHasItem(StaticItemList.BUCKET_OF_SAND, 1));
        assertFalse(player.getItemAssistant().playerHasItem(StaticItemList.SODA_ASH, 1));
        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.MOLTEN_GLASS, 1));
        assertEquals(CustomGlassmaking.MOLTEN_GLASS_XP, player.playerXP[Constants.CRAFTING]);
    }

    @Test
    public void missingIngredientIsHandledWithoutConsumingInventory() {
        CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED = true;
        addInventoryItem(StaticItemList.BUCKET_OF_SAND, 1);

        assertTrue(CustomContent.handleItemOnObject(player, StaticItemList.BUCKET_OF_SAND, ARDOUGNE_FURNACE, 2601, 3310));

        assertTrue(player.getItemAssistant().playerHasItem(StaticItemList.BUCKET_OF_SAND, 1));
        assertFalse(player.getItemAssistant().playerHasItem(StaticItemList.MOLTEN_GLASS, 1));
        assertEquals(0, player.playerXP[Constants.CRAFTING]);
    }

    @Test
    public void unrelatedItemsAndObjectsFallThrough() {
        CustomFeatureFlags.CATHERBY_TRADER_STAN_AND_GLASSMAKING_ENABLED = true;
        assertFalse(CustomContent.handleItemOnObject(player, StaticItemList.SEAWEED, ARDOUGNE_FURNACE, 2601, 3310));
        assertFalse(CustomContent.handleItemOnObject(player, StaticItemList.BUCKET_OF_SAND, 9999, 2601, 3310));
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

    private static final class TestClient extends Client {
        private TestClient(int playerId) {
            super(null, playerId);
            outStream = null;
        }
    }
}
