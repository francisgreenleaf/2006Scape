package com.rs2.agent;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.Consumer;

import org.apollo.cache.def.ObjectDefinition;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.GameEngine;
import com.rs2.game.content.consumables.Food;
import com.rs2.game.content.skills.SkillHandler;
import com.rs2.game.content.skills.core.Mining;
import com.rs2.game.content.skills.smithing.Smelting;
import com.rs2.game.content.skills.smithing.SmithingData;
import com.rs2.game.content.skills.woodcutting.Woodcutting;
import com.rs2.game.items.DeprecatedItems;
import com.rs2.game.items.GroundItem;
import com.rs2.game.items.ItemConstants;
import com.rs2.game.items.ItemData;
import com.rs2.game.items.ItemDefinitions;
import com.rs2.game.npcs.Npc;
import com.rs2.game.npcs.NpcHandler;
import com.rs2.game.objects.Objects;
import com.rs2.game.objects.impl.Climbing;
import com.rs2.game.players.Player;
import com.rs2.game.dialogues.DialogueOptions;
import com.rs2.game.shops.ShopHandler;
import com.rs2.game.shops.Shops;
import com.rs2.net.packets.impl.ClickObject;
import com.rs2.world.Boundary;
import com.rs2.world.GlobalDropsHandler;
import com.rs2.world.clip.PathFinder;
import com.rs2.world.clip.Region;

public class AgentToolService {

    private static final int DEFAULT_SCAN_DISTANCE = 30;
    private static final int DEFAULT_OBJECT_SCAN_DISTANCE = 60;
    private static final String[] SKILL_NAMES = {"attack", "defence", "strength", "hitpoints", "ranged",
            "prayer", "magic", "cooking", "woodcutting", "fletching", "fishing", "firemaking", "crafting",
            "smithing", "mining", "herblore", "agility", "thieving", "slayer", "farming", "runecraft",
            "unused21", "unused22", "unused23", "unused24"};

    public static JsonObject handle(Player player, String tool, JsonObject arguments) {
        if (tool == null) {
            return failure("Missing tool name.");
        }
        if ("observe_state".equals(tool)) {
            return observeState(player);
        }
        if ("cancel_current_action".equals(tool)) {
            return cancelCurrentAction(player);
        }
        if ("continue_dialogue".equals(tool)) {
            return continueDialogue(player);
        }
        if ("select_dialogue_option".equals(tool)) {
            return selectDialogueOption(player, arguments);
        }
        if ("close_interfaces".equals(tool)) {
            return closeInterfaces(player);
        }
        if (!canAct(player)) {
            return failure("The player cannot act right now.");
        }
        if ("walk_to_tile".equals(tool)) {
            return walkToTile(player, arguments);
        }
        if ("travel_to_landmark".equals(tool)) {
            return travelToLandmark(player, arguments);
        }
        if ("find_nearest_npc".equals(tool)) {
            return findNearestNpc(player, arguments);
        }
        if ("attack_npc".equals(tool)) {
            return attackNpc(player, arguments);
        }
        if ("find_nearest_object".equals(tool)) {
            return findNearestObject(player, arguments);
        }
        if ("find_nearest_rock".equals(tool)) {
            return findNearestRock(player, arguments);
        }
        if ("find_nearest_tree".equals(tool)) {
            return findNearestTree(player, arguments);
        }
        if ("set_combat_style".equals(tool)) {
            return setCombatStyle(player, arguments);
        }
        if ("equip_item".equals(tool)) {
            return equipItem(player, arguments);
        }
        if ("unequip_item".equals(tool)) {
            return unequipItem(player, arguments);
        }
        if ("equip_best_items".equals(tool)) {
            return equipBestItems(player);
        }
        if ("eat_item".equals(tool)) {
            return eatItem(player, arguments);
        }
        if ("pickup_ground_item".equals(tool)) {
            return pickupGroundItem(player, arguments);
        }
        if ("open_nearest_shop".equals(tool)) {
            return openNearestShop(player, arguments);
        }
        if ("buy_shop_item".equals(tool)) {
            return buyShopItem(player, arguments);
        }
        if ("sell_inventory_item".equals(tool)) {
            return sellInventoryItem(player, arguments);
        }
        if ("interact_object".equals(tool)) {
            return interactObject(player, arguments);
        }
        if ("mine_ore".equals(tool)) {
            return mineOre(player, arguments);
        }
        if ("chop_tree".equals(tool)) {
            return chopTree(player, arguments);
        }
        if ("drop_inventory_items".equals(tool)) {
            return dropInventoryItems(player, arguments);
        }
        if ("deposit_inventory_items".equals(tool)) {
            return depositInventoryItems(player, arguments);
        }
        if ("withdraw_bank_items".equals(tool)) {
            return withdrawBankItems(player, arguments);
        }
        if ("smelt_bar".equals(tool)) {
            return smeltBar(player, arguments);
        }
        if ("smith_item".equals(tool)) {
            return smithItem(player, arguments);
        }
        return failure("Unknown RuneScape agent tool: " + tool);
    }

    public static JsonObject observeState(Player player) {
        JsonObject result = success("Observed current game state.");
        addPlayerState(result, player);
        result.add("nearbyNpcs", nearbyNpcs(player, DEFAULT_SCAN_DISTANCE, 12));
        result.add("nearbyObjects", nearbyObjects(player, 20, 16));
        result.add("nearbyGroundItems", nearbyGroundItems(player, 20, 16));
        return result;
    }

    public static JsonObject success(String message) {
        JsonObject result = new JsonObject();
        result.addProperty("success", true);
        result.addProperty("message", message);
        return result;
    }

    public static JsonObject failure(String message) {
        JsonObject result = new JsonObject();
        result.addProperty("success", false);
        result.addProperty("message", message == null ? "Agent action failed." : message);
        return result;
    }

    private static boolean canAct(Player player) {
        return player != null && !player.disconnected && !player.isDead && !player.inTrade && player.duelStatus != 5;
    }

    private static JsonObject walkToTile(Player player, JsonObject arguments) {
        int x = getInt(arguments, "x", player.absX);
        int y = getInt(arguments, "y", player.absY);
        int height = getInt(arguments, "height", player.heightLevel);
        if (height != player.heightLevel) {
            return failure("Cannot walk to a different height level with normal movement.");
        }
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        player.endCurrentTask();
        SkillHandler.resetSkills(player);
        player.getPlayerAssistant().playerWalk(x, y);
        JsonObject result = success("Walking toward tile.");
        addPlayerState(result, player);
        result.add("target", tile(x, y, height));
        return result;
    }

    private static JsonObject travelToLandmark(Player player, JsonObject arguments) {
        String name = getString(arguments, "name", "");
        AgentKnowledgeBase.Landmark landmark = AgentKnowledgeBase.findLandmark(name);
        if (landmark == null) {
            JsonObject result = failure("Unknown landmark: " + name);
            JsonArray names = new JsonArray();
            for (String landmarkName : AgentKnowledgeBase.landmarkNames()) {
                names.add(landmarkName);
            }
            result.add("knownLandmarks", names);
            return result;
        }
        AgentKnowledgeBase.TravelStep step = AgentKnowledgeBase.nextTravelStep(player, landmark);
        JsonObject result = success(step.isComplete() ? "Arrived at " + landmark.getName() + "." : "Walking toward " + landmark.getName() + ".");
        result.addProperty("complete", step.isComplete());
        result.addProperty("landmark", landmark.getName());
        result.add("target", tile(landmark.getTarget().x, landmark.getTarget().y, landmark.getTarget().height));
        result.add("nextWaypoint", tile(step.getTile().x, step.getTile().y, step.getTile().height));
        result.addProperty("finalWaypoint", step.isFinalTarget());
        if (!step.isComplete()) {
            player.getPlayerAssistant().resetFollow();
            player.getCombatAssistant().resetPlayerAttack();
            player.endCurrentTask();
            SkillHandler.resetSkills(player);
            player.getPlayerAssistant().playerWalk(step.getTile().x, step.getTile().y);
        }
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject findNearestNpc(Player player, JsonObject arguments) {
        String name = normalize(getString(arguments, "name", ""));
        int maxDistance = getInt(arguments, "maxDistance", DEFAULT_SCAN_DISTANCE);
        boolean reachableOnly = getBoolean(arguments, "reachable", getBoolean(arguments, "requireReachable", false));
        Npc nearest = null;
        int nearestDistance = Integer.MAX_VALUE;
        for (Npc npc : NpcHandler.npcs) {
            if (!isNpcCandidate(player, npc)) {
                continue;
            }
            String npcName = normalize(npc.name());
            if (!name.isEmpty() && !npcName.contains(name)) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, npc.absX, npc.absY);
            if (reachableOnly && !isReachableNpc(player, npc)) {
                continue;
            }
            if (distance <= maxDistance && distance < nearestDistance) {
                nearest = npc;
                nearestDistance = distance;
            }
        }
        if (nearest == null) {
            return failure("No matching NPC found nearby.");
        }
        JsonObject result = success("Found nearest NPC.");
        result.add("npc", npcJson(nearest, nearestDistance));
        return result;
    }

    private static JsonObject attackNpc(Player player, JsonObject arguments) {
        int npcIndex = getInt(arguments, "npcIndex", -1);
        if (npcIndex < 0 || npcIndex >= NpcHandler.npcs.length) {
            return failure("Invalid NPC index.");
        }
        Npc npc = NpcHandler.npcs[npcIndex];
        if (!isNpcCandidate(player, npc) || npc.MaxHP <= 0) {
            return failure("That NPC cannot be attacked.");
        }
        if (!isReachableNpc(player, npc)) {
            player.getCombatAssistant().resetPlayerAttack();
            return failure("That NPC is not reachable with normal movement.");
        }
        player.endCurrentTask();
        SkillHandler.resetSkills(player);
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        player.npcIndex = npcIndex;
        player.followNpcId = npcIndex;
        player.followPlayerId = 0;
        player.faceUpdate(npcIndex);
        boolean inMeleeRange = player.goodDistance(player.getX(), player.getY(), npc.getX(), npc.getY(), 1);
        if (!inMeleeRange) {
            player.getPlayerAssistant().playerWalk(npc.getX(), npc.getY());
        } else {
            player.getCombatAssistant().attackNpc(npcIndex);
        }
        JsonObject result = success((inMeleeRange ? "Attacking " : "Walking into melee range to attack ") + npc.name() + ".");
        result.addProperty("approaching", !inMeleeRange);
        result.add("npc", npcJson(npc, AgentKnowledgeBase.distance(player.absX, player.absY, npc.absX, npc.absY)));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject findNearestObject(Player player, JsonObject arguments) {
        ObjectMatch match = findObject(player, arguments, getInt(arguments, "maxDistance", DEFAULT_OBJECT_SCAN_DISTANCE));
        if (match == null) {
            return failure("No matching object found nearby.");
        }
        JsonObject result = success("Found nearest object.");
        result.add("object", objectJson(match.object, match.distance));
        return result;
    }

    private static JsonObject findNearestRock(Player player, JsonObject arguments) {
        ObjectMatch match = findRock(player, arguments, getInt(arguments, "maxDistance", DEFAULT_OBJECT_SCAN_DISTANCE));
        if (match == null) {
            return failure("No matching rock found nearby.");
        }
        JsonObject result = success("Found nearest rock.");
        result.add("object", objectJson(match.object, match.distance));
        return result;
    }

    private static JsonObject findNearestTree(Player player, JsonObject arguments) {
        ObjectMatch match = findTree(player, arguments, getInt(arguments, "maxDistance", DEFAULT_OBJECT_SCAN_DISTANCE));
        if (match == null) {
            return failure("No matching tree found nearby.");
        }
        JsonObject result = success("Found nearest tree.");
        result.add("object", objectJson(match.object, match.distance));
        return result;
    }

    private static JsonObject interactObject(Player player, JsonObject arguments) {
        int objectId = getInt(arguments, "objectId", -1);
        int x = getInt(arguments, "x", -1);
        int y = getInt(arguments, "y", -1);
        String option = normalize(getString(arguments, "option", "first"));
        int optionNumber = optionToNumber(option);
        if (objectId < 0 || x < 0 || y < 0) {
            return failure("objectId, x, and y are required.");
        }
        Objects object = Region.getObject(objectId, x, y, player.heightLevel);
        if (object == null && GameEngine.objectHandler.objectExists(x, y, player.heightLevel) == null) {
            return failure("That object is not present on this height level.");
        }
        if (object != null && isTemporarilyReplaced(object)) {
            return failure("That object is temporarily unavailable.");
        }
        clickObject(player, objectId, x, y, optionNumber);
        JsonObject result = success("Interacting with object.");
        result.add("object", objectJson(object == null ? new Objects(objectId, x, y, player.heightLevel, 0, 10, 0) : object,
                AgentKnowledgeBase.distance(player.absX, player.absY, x, y)));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject setCombatStyle(Player player, JsonObject arguments) {
        String style = normalize(getString(arguments, "style", ""));
        int fightMode;
        if ("attack".equals(style) || "accurate".equals(style)) {
            fightMode = Constants.ATTACK;
        } else if ("defence".equals(style) || "defense".equals(style) || "defensive".equals(style)) {
            fightMode = Constants.DEFENCE;
        } else if ("strength".equals(style) || "aggressive".equals(style)) {
            fightMode = Constants.STRENGTH;
        } else if ("controlled".equals(style) || "shared".equals(style)) {
            fightMode = 3;
        } else {
            return failure("Unknown combat style: " + style + ". Use attack, strength, defence, or controlled.");
        }
        player.fightMode = fightMode;
        if (player.autocasting) {
            player.getPlayerAssistant().resetAutocast();
        }
        player.getPlayerAssistant().handleWeaponStyle();
        JsonObject result = success("Combat style set to " + combatStyleName(player.fightMode) + ".");
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject equipItem(Player player, JsonObject arguments) {
        ItemMatch item = findInventoryItem(player, arguments);
        if (item == null) {
            return failure("No matching inventory item found to equip.");
        }
        player.endCurrentTask();
        SkillHandler.resetSkills(player);
        boolean equipped = player.getItemAssistant().wearItem(item.itemId, item.slot);
        JsonObject result = equipped ? success("Equipped " + DeprecatedItems.getItemName(item.itemId) + ".")
                : failure("Unable to equip " + DeprecatedItems.getItemName(item.itemId) + ".");
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject unequipItem(Player player, JsonObject arguments) {
        int slot = getInt(arguments, "equipmentSlot", getInt(arguments, "slot", -1));
        String slotName = normalize(getString(arguments, "slotName", getString(arguments, "equipment", "")));
        if (slot < 0 && !slotName.isEmpty()) {
            slot = equipmentSlotByName(slotName);
        }
        int itemId = getInt(arguments, "itemId", -1);
        String name = normalize(getString(arguments, "name", getString(arguments, "item", "")));
        if (slot < 0) {
            for (int i = 0; i < player.playerEquipment.length; i++) {
                int equippedId = player.playerEquipment[i];
                if (equippedId < 0) {
                    continue;
                }
                if (itemId >= 0 && equippedId != itemId) {
                    continue;
                }
                if (!name.isEmpty() && !normalize(DeprecatedItems.getItemName(equippedId)).contains(name)) {
                    continue;
                }
                slot = i;
                break;
            }
        }
        if (slot < 0 || slot >= player.playerEquipment.length || player.playerEquipment[slot] < 0) {
            return failure("No matching equipped item found to unequip.");
        }
        int equippedId = player.playerEquipment[slot];
        if (player.getItemAssistant().freeSlots(equippedId, 1) <= 0) {
            return failure("Not enough inventory space to unequip " + DeprecatedItems.getItemName(equippedId) + ".");
        }
        player.endCurrentTask();
        SkillHandler.resetSkills(player);
        int before = countInventoryItem(player, equippedId);
        player.getItemAssistant().removeItem(equippedId, slot);
        int moved = Math.max(0, countInventoryItem(player, equippedId) - before);
        JsonObject result = moved > 0 || player.playerEquipment[slot] < 0
                ? success("Unequipped " + DeprecatedItems.getItemName(equippedId) + ".")
                : failure("Unable to unequip " + DeprecatedItems.getItemName(equippedId) + ".");
        result.addProperty("unequipped", moved > 0 ? moved : 0);
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject equipBestItems(Player player) {
        player.endCurrentTask();
        SkillHandler.resetSkills(player);
        int equipped = 0;
        JsonArray equippedItems = new JsonArray();
        boolean changed;
        do {
            changed = false;
            boolean[] attemptedSlots = new boolean[player.playerItems.length];
            while (true) {
                ItemMatch best = null;
                int bestSlot = -1;
                int bestDelta = 0;
                for (int i = 0; i < player.playerItems.length; i++) {
                    if (attemptedSlots[i]) {
                        continue;
                    }
                    int storedId = player.playerItems[i];
                    if (storedId <= 0) {
                        continue;
                    }
                    int itemId = storedId - 1;
                    int targetSlot = targetSlot(itemId);
                    if (!isUpgradeableCombatSlot(targetSlot)) {
                        continue;
                    }
                    int delta = equipmentScore(itemId, targetSlot)
                            - equipmentScore(player.playerEquipment[targetSlot], targetSlot);
                    if (delta > bestDelta) {
                        best = new ItemMatch(i, itemId, player.playerItemsN[i]);
                        bestSlot = targetSlot;
                        bestDelta = delta;
                    }
                }
                if (best == null) {
                    break;
                }
                if (player.getItemAssistant().wearItem(best.itemId, best.slot)) {
                    equipped++;
                    changed = true;
                    JsonObject item = new JsonObject();
                    item.addProperty("slot", bestSlot);
                    item.addProperty("slotName", equipmentSlotName(bestSlot));
                    item.addProperty("id", best.itemId);
                    item.addProperty("name", DeprecatedItems.getItemName(best.itemId));
                    item.addProperty("scoreDelta", bestDelta);
                    equippedItems.add(item);
                    break;
                }
                attemptedSlots[best.slot] = true;
            }
        } while (changed);
        JsonObject result = success("Equipped " + equipped + " combat upgrade" + (equipped == 1 ? "." : "s."));
        result.addProperty("equipped", equipped);
        result.add("equippedItems", equippedItems);
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject eatItem(Player player, JsonObject arguments) {
        ItemMatch item = findInventoryItem(player, arguments);
        if (item == null) {
            return failure("No matching inventory item found to eat.");
        }
        if (!Food.isFood(item.itemId)) {
            return failure(DeprecatedItems.getItemName(item.itemId) + " is not edible food.");
        }
        int before = player.playerLevel[Constants.HITPOINTS];
        Food.eat(player, item.itemId, item.slot);
        JsonObject result = success("Ate " + DeprecatedItems.getItemName(item.itemId) + ".");
        result.addProperty("healed", Math.max(0, player.playerLevel[Constants.HITPOINTS] - before));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject pickupGroundItem(Player player, JsonObject arguments) {
        int maxDistance = getInt(arguments, "maxDistance", 20);
        GroundItemMatch item = findGroundItem(player, arguments, maxDistance);
        if (item == null) {
            JsonObject globalPickup = pickupGlobalGroundItem(player, arguments, maxDistance);
            return globalPickup == null ? failure("No matching ground item found nearby.") : globalPickup;
        }
        if (player.getItemAssistant().freeSlots(item.item.getItemId(), 1) <= 0) {
            return failure("Not enough inventory space to pick up " + DeprecatedItems.getItemName(item.item.getItemId()) + ".");
        }
        player.getCombatAssistant().resetPlayerAttack();
        player.endCurrentTask();
        SkillHandler.resetSkills(player);
        if (!player.goodDistance(player.getX(), player.getY(), item.item.getItemX(), item.item.getItemY(), 1)) {
            player.getPlayerAssistant().playerWalk(item.item.getItemX(), item.item.getItemY());
            JsonObject result = success("Walking toward " + DeprecatedItems.getItemName(item.item.getItemId()) + ".");
            result.add("groundItem", groundItemJson(item.item, item.distance));
            addPlayerState(result, player);
            return result;
        }
        int before = countInventoryItem(player, item.item.getItemId());
        GameEngine.itemHandler.removeGroundItem(player, item.item.getItemId(), item.item.getItemX(), item.item.getItemY(), true);
        GlobalDropsHandler.pickup(player, item.item.getItemId(), item.item.getItemX(), item.item.getItemY());
        int moved = Math.max(0, countInventoryItem(player, item.item.getItemId()) - before);
        JsonObject result = moved > 0 ? success("Picked up " + moved + " " + DeprecatedItems.getItemName(item.item.getItemId()) + ".")
                : failure("Unable to pick up " + DeprecatedItems.getItemName(item.item.getItemId()) + ".");
        result.addProperty("pickedUp", moved);
        result.add("groundItem", groundItemJson(item.item, item.distance));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject pickupGlobalGroundItem(Player player, JsonObject arguments, int maxDistance) {
        int x = getInt(arguments, "x", -1);
        int y = getInt(arguments, "y", -1);
        int itemId = getInt(arguments, "itemId", -1);
        if (x < 0 || y < 0 || itemId < 0) {
            return null;
        }
        int distance = AgentKnowledgeBase.distance(player.absX, player.absY, x, y);
        if (distance > maxDistance) {
            return null;
        }
        if (player.getItemAssistant().freeSlots(itemId, 1) <= 0) {
            return failure("Not enough inventory space to pick up " + DeprecatedItems.getItemName(itemId) + ".");
        }
        player.getCombatAssistant().resetPlayerAttack();
        player.endCurrentTask();
        SkillHandler.resetSkills(player);
        if (!player.goodDistance(player.getX(), player.getY(), x, y, 1)) {
            player.getPlayerAssistant().playerWalk(x, y);
            JsonObject result = success("Walking toward " + DeprecatedItems.getItemName(itemId) + ".");
            result.add("groundItem", groundItemJson(itemId, 1, x, y, player.heightLevel, distance, false));
            addPlayerState(result, player);
            return result;
        }
        int before = countInventoryItem(player, itemId);
        GlobalDropsHandler.pickup(player, itemId, x, y);
        int moved = Math.max(0, countInventoryItem(player, itemId) - before);
        JsonObject result = moved > 0 ? success("Picked up " + moved + " " + DeprecatedItems.getItemName(itemId) + ".")
                : failure("Unable to pick up " + DeprecatedItems.getItemName(itemId) + ".");
        result.addProperty("pickedUp", moved);
        result.add("groundItem", groundItemJson(itemId, moved > 0 ? moved : 1, x, y, player.heightLevel, distance, false));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject openNearestShop(Player player, JsonObject arguments) {
        String name = normalize(getString(arguments, "name", ""));
        int maxDistance = getInt(arguments, "maxDistance", 10);
        Npc nearest = null;
        Shops.Shop nearestShop = null;
        int nearestDistance = Integer.MAX_VALUE;
        for (Npc npc : NpcHandler.npcs) {
            if (!isNpcPresent(player, npc)) {
                continue;
            }
            Shops.Shop shop = Shops.Shop.forId(npc.npcType);
            if (shop == null) {
                continue;
            }
            String npcName = normalize(npc.name());
            String shopName = normalize(ShopHandler.shopName[shop.getShop()]);
            if (!name.isEmpty() && !npcName.contains(name) && !shopName.contains(name)) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, npc.absX, npc.absY);
            if (distance <= maxDistance && distance < nearestDistance) {
                nearest = npc;
                nearestShop = shop;
                nearestDistance = distance;
            }
        }
        if (nearest == null || nearestShop == null) {
            return failure("No shopkeeper found nearby.");
        }
        player.stopMovement();
        player.endCurrentTask();
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        SkillHandler.resetSkills(player);
        player.npcClickIndex = nearest.npcId;
        player.npcType = nearest.npcType;
        player.talkingNpc = nearest.npcType;
        player.faceUpdate(nearest.npcId);
        Shops.openShop(player, nearest.npcType);
        JsonObject result = success("Opened " + ShopHandler.shopName[nearestShop.getShop()] + ".");
        result.add("npc", npcJson(nearest, nearestDistance));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject buyShopItem(Player player, JsonObject arguments) {
        if (!player.isShopping) {
            return failure("The player must have a shop open before buying items.");
        }
        ItemMatch item = findShopItem(player, arguments);
        if (item == null) {
            return failure("No matching shop item found to buy.");
        }
        int amount = Math.max(1, getInt(arguments, "amount", 1));
        int before = countInventoryItem(player, item.itemId);
        boolean bought = player.getShopAssistant().buyItem(item.itemId, item.slot, amount);
        int moved = countInventoryItem(player, item.itemId) - before;
        JsonObject result = bought && moved > 0 ? success("Bought " + moved + " " + DeprecatedItems.getItemName(item.itemId) + ".")
                : failure("Unable to buy " + DeprecatedItems.getItemName(item.itemId) + ".");
        result.addProperty("bought", Math.max(0, moved));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject sellInventoryItem(Player player, JsonObject arguments) {
        if (!player.isShopping) {
            return failure("The player must have a shop open before selling items.");
        }
        ItemMatch item = findInventoryItem(player, arguments);
        if (item == null) {
            return failure("No matching inventory item found to sell.");
        }
        int amount = Math.max(1, Math.min(item.amount, getInt(arguments, "amount", 1)));
        int before = countInventoryItem(player, item.itemId);
        int beforeCoins = countInventoryItem(player, 995);
        boolean sold = player.getShopAssistant().sellItem(item.itemId, item.slot, amount);
        int moved = before - countInventoryItem(player, item.itemId);
        int coins = countInventoryItem(player, 995) - beforeCoins;
        JsonObject result = sold && moved > 0 ? success("Sold " + moved + " " + DeprecatedItems.getItemName(item.itemId) + ".")
                : failure("Unable to sell " + DeprecatedItems.getItemName(item.itemId) + ".");
        result.addProperty("sold", Math.max(0, moved));
        result.addProperty("coinsReceived", Math.max(0, coins));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject continueDialogue(Player player) {
        if (player == null) {
            return failure("Player is not online.");
        }
        if (player.nextChat > 0) {
            player.getDialogueHandler().sendDialogues(player.nextChat, player.talkingNpc);
        } else {
            player.getDialogueHandler().sendDialogues(0, -1);
        }
        JsonObject result = success("Continued dialogue.");
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject selectDialogueOption(Player player, JsonObject arguments) {
        if (player == null) {
            return failure("Player is not online.");
        }
        int option = getInt(arguments, "option", 1);
        if (player.dialogueAction == 147) {
            int buttonId;
            if (option == 1) {
                buttonId = 9157;
            } else if (option == 2) {
                buttonId = 9158;
            } else {
                return failure("Ladder dialogue option must be 1 for up or 2 for down.");
            }
            Climbing.handleLadderButtons(player, buttonId);
            JsonObject result = success("Selected ladder option " + option + ".");
            addPlayerState(result, player);
            return result;
        }
        int buttonId;
        switch (option) {
            case 1:
                buttonId = 9167;
                break;
            case 2:
                buttonId = 9168;
                break;
            case 3:
                buttonId = 9169;
                break;
            case 4:
                buttonId = 9178;
                break;
            case 5:
                buttonId = 9179;
                break;
            default:
                return failure("Dialogue option must be between 1 and 5.");
        }
        DialogueOptions.handleDialogueOptions(player, buttonId);
        JsonObject result = success("Selected dialogue option " + option + ".");
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject closeInterfaces(Player player) {
        if (player == null) {
            return failure("Player is not online.");
        }
        player.getPacketSender().closeAllWindows();
        player.isShopping = false;
        player.updateShop = false;
        JsonObject result = success("Closed open interfaces.");
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject mineOre(Player player, JsonObject arguments) {
        String ore = normalize(getString(arguments, "ore", ""));
        if (ore.endsWith(" ore")) {
            ore = ore.substring(0, ore.length() - 4);
        }
        if (!hasUsablePickaxe(player)) {
            return failure("You need a usable pickaxe to mine rocks.");
        }
        if (player.getItemAssistant().freeSlots() < 1) {
            return failure("Inventory is full. Drop ores or bank them before mining more rocks.");
        }
        int maxDistance = Math.min(getInt(arguments, "maxDistance", DEFAULT_SCAN_DISTANCE), DEFAULT_SCAN_DISTANCE);
        JsonObject objectArgs = new JsonObject();
        objectArgs.addProperty("resource", ore);
        objectArgs.addProperty("maxDistance", maxDistance);
        ObjectMatch match = findRock(player, objectArgs, maxDistance);
        if (match == null) {
            if (isKnownVarrockMineResource(ore)) {
                JsonObject travelArgs = new JsonObject();
                travelArgs.addProperty("name", "varrock east mine");
                JsonObject result = travelToLandmark(player, travelArgs);
                result.addProperty("message", "No " + (ore.isEmpty() ? "mineable" : ore) + " rock is nearby; moving toward Varrock east mine.");
                return result;
            }
            return failure("No " + ore + " rock found nearby.");
        }
        Mining.rockData rock = Mining.rockData.getRock(match.object.objectId);
        if (rock == null) {
            return failure("That object is not a mineable rock.");
        }
        if (rock.getRequiredLevel() > player.playerLevel[Constants.MINING]) {
            return failure("Mining level " + rock.getRequiredLevel() + " is required for that rock.");
        }
        mineRock(player, match.object);
        JsonObject result = success("Mining " + rock.name().toLowerCase(Locale.ENGLISH) + " ore.");
        result.add("object", objectJson(match.object, match.distance));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject chopTree(Player player, JsonObject arguments) {
        String tree = normalize(getString(arguments, "tree", getString(arguments, "resource", "tree")));
        if (tree.isEmpty()) {
            tree = "tree";
        }
        if (!Woodcutting.hasAxe(player)) {
            return failure("You need an axe to cut trees.");
        }
        if (player.getItemAssistant().freeSlots() < 1) {
            return failure("Inventory is full. Drop logs or bank them before chopping more trees.");
        }
        JsonObject treeArgs = new JsonObject();
        treeArgs.addProperty("tree", tree);
        treeArgs.addProperty("maxDistance", getInt(arguments, "maxDistance", DEFAULT_OBJECT_SCAN_DISTANCE));
        ObjectMatch match = findTree(player, treeArgs, getInt(arguments, "maxDistance", DEFAULT_OBJECT_SCAN_DISTANCE));
        if (match == null) {
            JsonObject travelArgs = new JsonObject();
            travelArgs.addProperty("name", "oak".equals(tree) ? "lumbridge oaks" : "lumbridge trees");
            JsonObject result = travelToLandmark(player, travelArgs);
            result.addProperty("message", "No " + tree + " tree is nearby; moving toward a known Lumbridge woodcutting spot.");
            return result;
        }
        int requiredLevel = Woodcutting.getTreeLevelRequirement(match.object.objectId);
        if (requiredLevel > player.playerLevel[Constants.WOODCUTTING]) {
            return failure("Woodcutting level " + requiredLevel + " is required for that tree.");
        }
        clickObject(player, match.object.objectId, match.object.objectX, match.object.objectY, 1);
        JsonObject result = success("Chopping " + Woodcutting.getTreeResourceName(match.object.objectId) + ".");
        result.add("object", objectJson(match.object, match.distance));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject dropInventoryItems(Player player, JsonObject arguments) {
        String name = normalize(getString(arguments, "name", ""));
        List<Integer> itemIds = getIntList(arguments, "itemIds");
        int dropped = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (!itemIds.isEmpty() && !itemIds.contains(itemId)) {
                continue;
            }
            String itemName = normalize(DeprecatedItems.getItemName(itemId));
            if (!name.isEmpty() && !itemName.contains(name)) {
                continue;
            }
            if (itemIds.isEmpty() && name.isEmpty()) {
                continue;
            }
            player.droppedItem = itemId;
            player.getItemAssistant().dropItem(itemId);
            dropped++;
            i = -1;
        }
        JsonObject result = success("Dropped " + dropped + " inventory item" + (dropped == 1 ? "." : "s."));
        result.addProperty("dropped", dropped);
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject depositInventoryItems(Player player, JsonObject arguments) {
        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            return failure("The player must be in a bank area before depositing inventory items.");
        }
        player.stopMovement();
        player.endCurrentTask();
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        SkillHandler.resetSkills(player);
        player.getPacketSender().openUpBank();

        String name = normalize(getString(arguments, "name", ""));
        List<Integer> itemIds = getIntList(arguments, "itemIds");
        int deposited = 0;
        int depositedAmount = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (!itemIds.isEmpty() && !itemIds.contains(itemId)) {
                continue;
            }
            String itemName = normalize(DeprecatedItems.getItemName(itemId));
            if (!name.isEmpty() && !itemName.contains(name)) {
                continue;
            }
            if (itemIds.isEmpty() && name.isEmpty()) {
                continue;
            }
            int amount = Math.max(1, player.playerItemsN[i]);
            if (player.getItemAssistant().bankItem(itemId, i, amount)) {
                deposited++;
                depositedAmount += amount;
                i = -1;
            }
        }
        JsonObject result = success("Deposited " + deposited + " inventory item" + (deposited == 1 ? "." : "s."));
        result.addProperty("deposited", deposited);
        result.addProperty("depositedAmount", depositedAmount);
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject withdrawBankItems(Player player, JsonObject arguments) {
        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            return failure("The player must be in a bank area before withdrawing bank items.");
        }
        player.stopMovement();
        player.endCurrentTask();
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        SkillHandler.resetSkills(player);
        player.getPacketSender().openUpBank();

        String name = normalize(getString(arguments, "name", ""));
        int amount = Math.max(1, getInt(arguments, "amount", 1));
        List<Integer> itemIds = getIntList(arguments, "itemIds");
        int withdrawn = 0;
        int withdrawnAmount = 0;
        for (int i = 0; i < player.bankItems.length; i++) {
            int storedId = player.bankItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (!itemIds.isEmpty() && !itemIds.contains(itemId)) {
                continue;
            }
            String itemName = normalize(DeprecatedItems.getItemName(itemId));
            if (!name.isEmpty() && !itemName.contains(name)) {
                continue;
            }
            if (itemIds.isEmpty() && name.isEmpty()) {
                continue;
            }
            int before = countInventoryItem(player, itemId);
            player.getItemAssistant().fromBank(itemId, i, Math.min(amount, Math.max(1, player.bankItemsN[i])));
            int moved = countInventoryItem(player, itemId) - before;
            if (moved > 0) {
                withdrawn++;
                withdrawnAmount += moved;
            }
            break;
        }
        JsonObject result = withdrawn > 0 ? success("Withdrew " + withdrawnAmount + " bank item" + (withdrawnAmount == 1 ? "." : "s."))
                : failure("No matching bank item was withdrawn.");
        result.addProperty("withdrawn", withdrawn);
        result.addProperty("withdrawnAmount", withdrawnAmount);
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject smeltBar(Player player, JsonObject arguments) {
        int barType = smeltingBarType(arguments);
        if (barType < 0) {
            return failure("Unknown bar type. Use bronze, iron, steel, silver, gold, mithril, adamant, or rune.");
        }
        ObjectMatch furnace = findSmithingObject(player, "furnace", getInt(arguments, "maxDistance", 6));
        if (furnace == null) {
            return failure("No furnace is close enough to smelt bars with normal mechanics.");
        }
        int amount = Math.max(1, Math.min(27, getInt(arguments, "amount", 1)));
        player.stopMovement();
        player.endCurrentTask();
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        SkillHandler.resetSkills(player);
        player.turnPlayerTo(furnace.object.objectX, furnace.object.objectY);
        Smelting.startSmelting(player, furnace.object.objectId);
        Smelting.doAmount(player, amount, barType);
        JsonObject result = success("Started smelting " + smeltingBarName(barType) + ".");
        result.addProperty("amount", amount);
        result.add("object", objectJson(furnace.object, furnace.distance));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject smithItem(Player player, JsonObject arguments) {
        int itemId = getInt(arguments, "itemId", -1);
        if (itemId < 0) {
            itemId = smithingItemId(getString(arguments, "name", getString(arguments, "item", "")));
        }
        SmithingData data = SmithingData.forId(itemId);
        if (data == null) {
            return failure("Unknown smithable item.");
        }
        ObjectMatch anvil = findSmithingObject(player, "anvil", getInt(arguments, "maxDistance", 6));
        if (anvil == null) {
            return failure("No anvil is close enough to smith items with normal mechanics.");
        }
        if (!player.getItemAssistant().playerHasItem(2347)) {
            return failure("A hammer is required to smith items.");
        }
        int amount = Math.max(1, Math.min(27, getInt(arguments, "amount", 1)));
        player.stopMovement();
        player.endCurrentTask();
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        SkillHandler.resetSkills(player);
        player.turnPlayerTo(anvil.object.objectX, anvil.object.objectY);
        player.getSmithingInt().showSmithInterface(requiredBarForSmithingItem(itemId));
        player.getSmithing().readInput(player, player.playerLevel[Constants.SMITHING], itemId, amount);
        JsonObject result = success("Started smithing " + DeprecatedItems.getItemName(itemId) + ".");
        result.addProperty("amount", amount);
        result.addProperty("itemId", itemId);
        result.add("object", objectJson(anvil.object, anvil.distance));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject cancelCurrentAction(Player player) {
        if (player == null) {
            return failure("Player is not online.");
        }
        player.stopMovement();
        player.endCurrentTask();
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        player.npcIndex = 0;
        player.killingNpcIndex = 0;
        player.followNpcId = 0;
        player.followPlayerId = 0;
        player.oldNpcIndex = 0;
        player.attackTimer = 0;
        player.faceUpdate(0);
        SkillHandler.resetSkills(player);
        JsonObject result = success("Cancelled current action.");
        addPlayerState(result, player);
        return result;
    }

    private static void clickObject(Player player, int objectId, int x, int y, int option) {
        startObjectAction(player, objectId, x, y, option, new Consumer<Player>() {
            @Override
            public void accept(Player p) {
                ClickObject clickObject = new ClickObject();
                clickObject.completeObjectClick(p, option);
            }
        });
    }

    private static void mineRock(Player player, Objects object) {
        final int objectId = object.objectId;
        final int objectX = object.objectX;
        final int objectY = object.objectY;
        final int objectType = object.objectType;
        startObjectAction(player, objectId, objectX, objectY, 1, new Consumer<Player>() {
            @Override
            public void accept(Player p) {
                p.getMining().startMining(p, objectId, objectX, objectY, objectType);
            }
        });
    }

    private static void startObjectAction(Player player, int objectId, int x, int y, int option, Consumer<Player> action) {
        player.clickObjectType = option;
        player.objectId = objectId;
        player.objectX = x;
        player.objectY = y;
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        player.getPlayerAssistant().requestUpdates();
        player.endCurrentTask();
        player.getPlayerAssistant().playerWalk(x, y);
        ClickObject clickObject = new ClickObject();
        clickObject.onObjectReached(player, action);
    }

    private static ObjectMatch findObject(Player player, JsonObject arguments, int maxDistance) {
        String name = normalize(getString(arguments, "name", ""));
        String resource = normalize(getString(arguments, "resource", ""));
        List<Integer> objectIds = getIntList(arguments, "objectIds");
        ObjectMatch nearest = null;
        for (Objects object : Region.getObjectsInRadius(player.absX, player.absY, player.heightLevel, maxDistance)) {
            if (object.objectId < 0) {
                continue;
            }
            if (isTemporarilyReplaced(object)) {
                continue;
            }
            if (!objectIds.isEmpty() && !objectIds.contains(object.objectId)) {
                continue;
            }
            if (!resource.isEmpty()) {
                Mining.rockData rock = Mining.rockData.getRock(object.objectId);
                String treeResource = Woodcutting.getTreeResourceName(object.objectId);
                boolean rockMatches = rock != null && normalize(rock.name()).contains(resource);
                boolean treeMatches = treeResource != null && normalize(treeResource).contains(resource);
                if (!rockMatches && !treeMatches) {
                    continue;
                }
            }
            if (!name.isEmpty()) {
                ObjectDefinition definition = ObjectDefinition.lookup(object.objectId);
                String objectName = definition == null ? "" : normalize(definition.getName());
                if (!objectName.contains(name)) {
                    continue;
                }
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, object.objectX, object.objectY);
            if (nearest == null || distance < nearest.distance) {
                nearest = new ObjectMatch(object, distance);
            }
        }
        return nearest;
    }

    private static ObjectMatch findRock(Player player, JsonObject arguments, int maxDistance) {
        String resource = normalize(getString(arguments, "resource", getString(arguments, "ore", "")));
        if (resource.endsWith(" ore")) {
            resource = resource.substring(0, resource.length() - 4);
        }
        List<Integer> objectIds = getIntList(arguments, "objectIds");
        ObjectMatch nearest = null;
        for (Objects object : Region.getObjectsInRadius(player.absX, player.absY, player.heightLevel, maxDistance)) {
            if (object.objectId < 0) {
                continue;
            }
            if (isTemporarilyReplaced(object)) {
                continue;
            }
            if (!objectIds.isEmpty() && !objectIds.contains(object.objectId)) {
                continue;
            }
            Mining.rockData rock = Mining.rockData.getRock(object.objectId);
            if (rock == null) {
                continue;
            }
            if (!resource.isEmpty() && !normalize(rock.name()).contains(resource)) {
                continue;
            }
            if (rock.getRequiredLevel() > player.playerLevel[Constants.MINING]) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, object.objectX, object.objectY);
            if (nearest == null || distance < nearest.distance) {
                nearest = new ObjectMatch(object, distance);
            }
        }
        return nearest;
    }

    private static ObjectMatch findTree(Player player, JsonObject arguments, int maxDistance) {
        String tree = normalize(getString(arguments, "tree", getString(arguments, "resource", "tree")));
        List<Integer> objectIds = getIntList(arguments, "objectIds");
        ObjectMatch nearest = null;
        for (Objects object : Region.getObjectsInRadius(player.absX, player.absY, player.heightLevel, maxDistance)) {
            if (object.objectId < 0 || !Woodcutting.isChoppableTree(object.objectId)) {
                continue;
            }
            if (isTemporarilyReplaced(object)) {
                continue;
            }
            if (!objectIds.isEmpty() && !objectIds.contains(object.objectId)) {
                continue;
            }
            String treeResource = normalize(Woodcutting.getTreeResourceName(object.objectId));
            if ("tree".equals(tree) && !"tree".equals(treeResource)) {
                continue;
            }
            if (!tree.isEmpty() && !"tree".equals(tree) && !treeResource.contains(tree)) {
                continue;
            }
            int requiredLevel = Woodcutting.getTreeLevelRequirement(object.objectId);
            if (requiredLevel > player.playerLevel[Constants.WOODCUTTING]) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, object.objectX, object.objectY);
            if (nearest == null || distance < nearest.distance) {
                nearest = new ObjectMatch(object, distance);
            }
        }
        return nearest;
    }

    private static boolean isTemporarilyReplaced(Objects object) {
        com.rs2.game.objects.Object temporary = GameEngine.objectManager.getObject(object.objectX, object.objectY, object.objectHeight);
        return temporary != null && temporary.objectId != object.objectId;
    }

    private static boolean hasUsablePickaxe(Player player) {
        int miningLevel = player.playerLevel[Constants.MINING];
        int[][] pickSettings = player.getMining().Pick_Settings;
        for (int i = 0; i < pickSettings.length; i++) {
            int itemId = pickSettings[i][0];
            int requiredLevel = pickSettings[i][1];
            if (requiredLevel <= miningLevel
                    && (player.getItemAssistant().playerHasItem(itemId) || player.playerEquipment[player.playerWeapon] == itemId)) {
                return true;
            }
        }
        return false;
    }

    private static boolean isKnownVarrockMineResource(String resource) {
        return resource.isEmpty() || "clay".equals(resource) || "copper".equals(resource)
                || "tin".equals(resource) || "iron".equals(resource);
    }

    private static JsonArray nearbyNpcs(Player player, int maxDistance, int limit) {
        JsonArray array = new JsonArray();
        for (Npc npc : NpcHandler.npcs) {
            if (!isNpcCandidate(player, npc)) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, npc.absX, npc.absY);
            if (distance <= maxDistance) {
                array.add(npcJson(npc, distance));
                if (array.size() >= limit) {
                    break;
                }
            }
        }
        return array;
    }

    private static JsonArray nearbyObjects(Player player, int maxDistance, int limit) {
        JsonArray array = new JsonArray();
        for (Objects object : Region.getObjectsInRadius(player.absX, player.absY, player.heightLevel, maxDistance)) {
            array.add(objectJson(object, AgentKnowledgeBase.distance(player.absX, player.absY, object.objectX, object.objectY)));
            if (array.size() >= limit) {
                break;
            }
        }
        return array;
    }

    private static JsonArray nearbyGroundItems(Player player, int maxDistance, int limit) {
        JsonArray array = new JsonArray();
        for (GroundItem item : GameEngine.itemHandler.items) {
            if (!isVisibleGroundItem(player, item)) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, item.getItemX(), item.getItemY());
            if (distance <= maxDistance) {
                array.add(groundItemJson(item, distance));
                if (array.size() >= limit) {
                    break;
                }
            }
        }
        return array;
    }

    private static GroundItemMatch findGroundItem(Player player, JsonObject arguments, int maxDistance) {
        int x = getInt(arguments, "x", -1);
        int y = getInt(arguments, "y", -1);
        int requestedId = getInt(arguments, "itemId", -1);
        String name = normalize(getString(arguments, "name", getString(arguments, "item", "")));
        List<Integer> itemIds = getIntList(arguments, "itemIds");
        if (requestedId >= 0) {
            itemIds.add(requestedId);
        }
        GroundItemMatch nearest = null;
        for (GroundItem item : GameEngine.itemHandler.items) {
            if (!isVisibleGroundItem(player, item)) {
                continue;
            }
            if (x >= 0 && item.getItemX() != x) {
                continue;
            }
            if (y >= 0 && item.getItemY() != y) {
                continue;
            }
            if (!matchesItem(item.getItemId(), name, itemIds)) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, item.getItemX(), item.getItemY());
            if (distance <= maxDistance && (nearest == null || distance < nearest.distance)) {
                nearest = new GroundItemMatch(item, distance);
            }
        }
        return nearest;
    }

    private static boolean isVisibleGroundItem(Player player, GroundItem item) {
        if (item == null || item.getItemH() != player.heightLevel) {
            return false;
        }
        if (item.hideTicks > 0) {
            return item.getName().equalsIgnoreCase(player.playerName);
        }
        return player.getItemAssistant().tradeable(item.getItemId()) || item.getName().equalsIgnoreCase(player.playerName);
    }

    private static boolean isNpcCandidate(Player player, Npc npc) {
        return isNpcPresent(player, npc) && npc.HP > 0;
    }

    private static boolean isNpcPresent(Player player, Npc npc) {
        return npc != null && npc.heightLevel == player.heightLevel && !npc.isDead;
    }

    private static boolean isReachableNpc(Player player, Npc npc) {
        if (player == null || npc == null || npc.heightLevel != player.heightLevel) {
            return false;
        }
        if (player.goodObjectDistance(player.absX, player.absY, npc.absX, npc.absY, 1)) {
            return true;
        }
        for (int x = npc.absX - 1; x <= npc.absX + 1; x++) {
            for (int y = npc.absY - 1; y <= npc.absY + 1; y++) {
                if (x == npc.absX && y == npc.absY) {
                    continue;
                }
                if (PathFinder.getPathFinder().accessible(player.absX, player.absY, player.heightLevel, x, y)) {
                    return true;
                }
            }
        }
        return false;
    }

    private static boolean isInCombat(Player player) {
        return player.npcIndex > 0 || player.killingNpcIndex > 0 || player.underAttackBy > 0 || player.underAttackBy2 > 0;
    }

    private static Npc targetNpc(Player player) {
        Npc npc = npcByIndex(player.npcIndex);
        if (npc == null) {
            npc = npcByIndex(player.killingNpcIndex);
        }
        if (npc == null && player.underAttackBy2 > 0) {
            npc = npcByIndex(player.underAttackBy2);
        }
        return npc != null && isNpcPresent(player, npc) && npc.HP > 0 ? npc : null;
    }

    private static Npc npcByIndex(int npcIndex) {
        if (npcIndex <= 0 || npcIndex >= NpcHandler.npcs.length) {
            return null;
        }
        return NpcHandler.npcs[npcIndex];
    }

    private static void addPlayerState(JsonObject result, Player player) {
        JsonObject playerJson = new JsonObject();
        playerJson.addProperty("name", player.playerName);
        playerJson.addProperty("x", player.absX);
        playerJson.addProperty("y", player.absY);
        playerJson.addProperty("height", player.heightLevel);
        playerJson.addProperty("hitpoints", player.playerLevel[Constants.HITPOINTS]);
        playerJson.addProperty("maxHitpoints", player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.HITPOINTS]));
        playerJson.addProperty("freeInventorySlots", player.getItemAssistant().freeSlots());
        playerJson.addProperty("isDead", player.isDead);
        playerJson.addProperty("isMoving", player.isMoving);
        playerJson.addProperty("isMining", player.isMining);
        playerJson.addProperty("isWoodcutting", player.isWoodcutting);
        playerJson.addProperty("isSmelting", player.isSmelting);
        playerJson.addProperty("isSmithing", player.isSmithing || player.playerSkilling[Constants.SMITHING]);
        playerJson.addProperty("inBankArea", Boundary.isIn(player, Boundary.BANK_AREA));
        playerJson.addProperty("inTrade", player.inTrade);
        playerJson.addProperty("isShopping", player.isShopping);
        playerJson.addProperty("dialogueAction", player.dialogueAction);
        playerJson.addProperty("nextChat", player.nextChat);
        playerJson.addProperty("talkingNpc", player.talkingNpc);
        playerJson.addProperty("combatLevel", player.combatLevel);
        playerJson.addProperty("fightMode", player.fightMode);
        playerJson.addProperty("combatStyle", combatStyleName(player.fightMode));
        playerJson.addProperty("npcIndex", player.npcIndex);
        playerJson.addProperty("killingNpcIndex", player.killingNpcIndex);
        playerJson.addProperty("underAttackBy", player.underAttackBy);
        playerJson.addProperty("underAttackBy2", player.underAttackBy2);
        playerJson.addProperty("isInCombat", isInCombat(player));
        Npc targetNpc = targetNpc(player);
        if (targetNpc != null) {
            playerJson.add("targetNpc", npcJson(targetNpc,
                    AgentKnowledgeBase.distance(player.absX, player.absY, targetNpc.absX, targetNpc.absY)));
        }
        playerJson.add("skills", skills(player));
        playerJson.add("inventory", inventory(player));
        playerJson.add("equipment", equipment(player));
        playerJson.add("bank", bank(player));
        if (player.isShopping) {
            playerJson.add("shop", shop(player));
        }
        result.add("player", playerJson);
    }

    private static JsonObject skills(Player player) {
        JsonObject skills = new JsonObject();
        for (int i = 0; i < player.playerLevel.length && i < SKILL_NAMES.length; i++) {
            JsonObject skill = new JsonObject();
            skill.addProperty("level", player.playerLevel[i]);
            skill.addProperty("xp", player.playerXP[i]);
            skill.addProperty("baseLevel", player.getPlayerAssistant().getLevelForXP(player.playerXP[i]));
            skills.add(SKILL_NAMES[i], skill);
        }
        return skills;
    }

    private static JsonArray inventory(Player player) {
        JsonArray array = new JsonArray();
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            JsonObject item = new JsonObject();
            item.addProperty("slot", i);
            item.addProperty("id", itemId);
            item.addProperty("amount", player.playerItemsN[i]);
            item.addProperty("name", DeprecatedItems.getItemName(itemId));
            array.add(item);
        }
        return array;
    }

    private static JsonArray equipment(Player player) {
        JsonArray array = new JsonArray();
        for (int i = 0; i < player.playerEquipment.length; i++) {
            int itemId = player.playerEquipment[i];
            if (itemId < 0) {
                continue;
            }
            JsonObject item = new JsonObject();
            item.addProperty("slot", i);
            item.addProperty("slotName", equipmentSlotName(i));
            item.addProperty("id", itemId);
            item.addProperty("amount", player.playerEquipmentN[i]);
            item.addProperty("name", DeprecatedItems.getItemName(itemId));
            array.add(item);
        }
        return array;
    }

    private static JsonArray bank(Player player) {
        JsonArray array = new JsonArray();
        for (int i = 0; i < player.bankItems.length; i++) {
            int storedId = player.bankItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            JsonObject item = new JsonObject();
            item.addProperty("slot", i);
            item.addProperty("id", itemId);
            item.addProperty("amount", player.bankItemsN[i]);
            item.addProperty("name", DeprecatedItems.getItemName(itemId));
            array.add(item);
        }
        return array;
    }

    private static JsonObject shop(Player player) {
        JsonObject json = new JsonObject();
        int shopId = player.shopId;
        json.addProperty("id", shopId);
        json.addProperty("name", shopId >= 0 && shopId < ShopHandler.shopName.length ? ShopHandler.shopName[shopId] : "");
        JsonArray items = new JsonArray();
        if (shopId >= 0 && shopId < ShopHandler.shopItems.length) {
            for (int i = 0; i < ShopHandler.shopItems[shopId].length; i++) {
                int storedId = ShopHandler.shopItems[shopId][i];
                if (storedId <= 0) {
                    continue;
                }
                int itemId = storedId - 1;
                JsonObject item = new JsonObject();
                item.addProperty("slot", i);
                item.addProperty("id", itemId);
                item.addProperty("amount", ShopHandler.shopItemsN[shopId][i]);
                item.addProperty("name", DeprecatedItems.getItemName(itemId));
                item.addProperty("price", player.getShopAssistant().getItemShopValue(itemId, 0, false));
                items.add(item);
            }
        }
        json.add("items", items);
        return json;
    }

    private static JsonObject npcJson(Npc npc, int distance) {
        JsonObject object = new JsonObject();
        object.addProperty("npcIndex", npc.npcId);
        object.addProperty("type", npc.npcType);
        object.addProperty("name", npc.name());
        object.addProperty("x", npc.absX);
        object.addProperty("y", npc.absY);
        object.addProperty("height", npc.heightLevel);
        object.addProperty("hitpoints", npc.HP);
        object.addProperty("maxHitpoints", npc.MaxHP);
        object.addProperty("distance", distance);
        object.addProperty("underAttack", npc.underAttack);
        return object;
    }

    private static JsonObject objectJson(Objects object, int distance) {
        JsonObject json = new JsonObject();
        json.addProperty("objectId", object.objectId);
        json.addProperty("x", object.objectX);
        json.addProperty("y", object.objectY);
        json.addProperty("height", object.objectHeight);
        json.addProperty("face", object.objectFace);
        json.addProperty("type", object.objectType);
        json.addProperty("distance", distance);
        ObjectDefinition definition = ObjectDefinition.lookup(object.objectId);
        if (definition != null) {
            json.addProperty("name", definition.getName());
        }
        Mining.rockData rock = Mining.rockData.getRock(object.objectId);
        if (rock != null) {
            json.addProperty("resource", rock.name().toLowerCase(Locale.ENGLISH));
            json.addProperty("requiredLevel", rock.getRequiredLevel());
            json.addProperty("xp", rock.getXp());
            JsonArray oreIds = new JsonArray();
            for (int oreId : rock.getOreIds()) {
                oreIds.add(oreId);
            }
            json.add("oreIds", oreIds);
        }
        String treeResource = Woodcutting.getTreeResourceName(object.objectId);
        if (treeResource != null) {
            json.addProperty("resource", treeResource);
            json.addProperty("requiredLevel", Woodcutting.getTreeLevelRequirement(object.objectId));
            json.addProperty("logId", Woodcutting.getTreeLogId(object.objectId));
            json.addProperty("xp", Woodcutting.getTreeExperience(object.objectId));
        }
        return json;
    }

    private static JsonObject groundItemJson(GroundItem item, int distance) {
        return groundItemJson(item.getItemId(), item.getItemAmount(), item.getItemX(), item.getItemY(),
                item.getItemH(), distance, item.hideTicks > 0);
    }

    private static JsonObject groundItemJson(int itemId, int amount, int x, int y, int height, int distance,
            boolean hiddenToOthers) {
        JsonObject json = new JsonObject();
        json.addProperty("id", itemId);
        json.addProperty("name", DeprecatedItems.getItemName(itemId));
        json.addProperty("amount", amount);
        json.addProperty("x", x);
        json.addProperty("y", y);
        json.addProperty("height", height);
        json.addProperty("distance", distance);
        json.addProperty("hiddenToOthers", hiddenToOthers);
        return json;
    }

    private static JsonObject tile(int x, int y, int height) {
        JsonObject json = new JsonObject();
        json.addProperty("x", x);
        json.addProperty("y", y);
        json.addProperty("height", height);
        return json;
    }

    private static int optionToNumber(String option) {
        if ("second".equals(option) || "2".equals(option)) {
            return 2;
        }
        if ("third".equals(option) || "3".equals(option)) {
            return 3;
        }
        if ("fourth".equals(option) || "4".equals(option)) {
            return 4;
        }
        return 1;
    }

    private static String getString(JsonObject object, String name, String fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            return object.get(name).getAsString();
        }
        return fallback;
    }

    private static int getInt(JsonObject object, String name, int fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            try {
                return object.get(name).getAsInt();
            } catch (NumberFormatException ignored) {
            }
        }
        return fallback;
    }

    private static boolean getBoolean(JsonObject object, String name, boolean fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            try {
                return object.get(name).getAsBoolean();
            } catch (RuntimeException ignored) {
            }
        }
        return fallback;
    }

    private static List<Integer> getIntList(JsonObject object, String name) {
        ArrayList<Integer> values = new ArrayList<Integer>();
        if (object == null || !object.has(name) || !object.get(name).isJsonArray()) {
            return values;
        }
        for (JsonElement element : object.get(name).getAsJsonArray()) {
            if (element.isJsonPrimitive()) {
                values.add(element.getAsInt());
            }
        }
        return values;
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ENGLISH).replace('_', ' ');
    }

    private static ItemMatch findInventoryItem(Player player, JsonObject arguments) {
        int slot = getInt(arguments, "slot", -1);
        int requestedId = getInt(arguments, "itemId", -1);
        String name = normalize(getString(arguments, "name", getString(arguments, "item", "")));
        List<Integer> itemIds = getIntList(arguments, "itemIds");
        if (requestedId >= 0) {
            itemIds.add(requestedId);
        }
        if (slot >= 0 && slot < player.playerItems.length) {
            int storedId = player.playerItems[slot];
            if (storedId <= 0) {
                return null;
            }
            int itemId = storedId - 1;
            if (matchesItem(itemId, name, itemIds)) {
                return new ItemMatch(slot, itemId, player.playerItemsN[slot]);
            }
            return null;
        }
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (matchesItem(itemId, name, itemIds)) {
                return new ItemMatch(i, itemId, player.playerItemsN[i]);
            }
        }
        return null;
    }

    private static ItemMatch findShopItem(Player player, JsonObject arguments) {
        int shopId = player.shopId;
        if (shopId < 0 || shopId >= ShopHandler.shopItems.length) {
            return null;
        }
        int slot = getInt(arguments, "slot", -1);
        int requestedId = getInt(arguments, "itemId", -1);
        String name = normalize(getString(arguments, "name", getString(arguments, "item", "")));
        List<Integer> itemIds = getIntList(arguments, "itemIds");
        if (requestedId >= 0) {
            itemIds.add(requestedId);
        }
        if (slot >= 0 && slot < ShopHandler.shopItems[shopId].length) {
            int storedId = ShopHandler.shopItems[shopId][slot];
            if (storedId <= 0) {
                return null;
            }
            int itemId = storedId - 1;
            if (matchesItem(itemId, name, itemIds)) {
                return new ItemMatch(slot, itemId, ShopHandler.shopItemsN[shopId][slot]);
            }
            return null;
        }
        for (int i = 0; i < ShopHandler.shopItems[shopId].length; i++) {
            int storedId = ShopHandler.shopItems[shopId][i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (matchesItem(itemId, name, itemIds)) {
                return new ItemMatch(i, itemId, ShopHandler.shopItemsN[shopId][i]);
            }
        }
        return null;
    }

    private static boolean matchesItem(int itemId, String name, List<Integer> itemIds) {
        if (!itemIds.isEmpty() && !itemIds.contains(itemId)) {
            return false;
        }
        if (!name.isEmpty() && !normalize(DeprecatedItems.getItemName(itemId)).contains(name)) {
            return false;
        }
        return !itemIds.isEmpty() || !name.isEmpty();
    }

    private static int countInventoryItem(Player player, int itemId) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            if (player.playerItems[i] == itemId + 1) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    private static int smeltingBarType(JsonObject arguments) {
        int itemId = getInt(arguments, "itemId", -1);
        String bar = normalize(getString(arguments, "bar", getString(arguments, "name", "")));
        if (bar.endsWith(" bar")) {
            bar = bar.substring(0, bar.length() - 4);
        }
        if ("mith".equals(bar)) {
            bar = "mithril";
        } else if ("addy".equals(bar)) {
            bar = "adamant";
        } else if ("runite".equals(bar)) {
            bar = "rune";
        }
        for (int[] row : Smelting.data) {
            String rowName = normalize(DeprecatedItems.getItemName(row[6]));
            if (itemId == row[6] || (!bar.isEmpty() && rowName.contains(bar))) {
                return row[0];
            }
        }
        return -1;
    }

    private static String smeltingBarName(int barType) {
        for (int[] row : Smelting.data) {
            if (row[0] == barType) {
                return DeprecatedItems.getItemName(row[6]).toLowerCase(Locale.ENGLISH);
            }
        }
        return "bar";
    }

    private static int smithingItemId(String itemName) {
        String name = normalize(itemName);
        if (name.isEmpty()) {
            return -1;
        }
        if ("steel plate".equals(name)) {
            name = "steel platebody";
        }
        for (SmithingData item : SmithingData.values()) {
            String candidate = normalize(DeprecatedItems.getItemName(item.getId()));
            if (candidate.equals(name) || candidate.contains(name) || name.contains(candidate)) {
                return item.getId();
            }
        }
        return -1;
    }

    private static int requiredBarForSmithingItem(int itemId) {
        String name = DeprecatedItems.getItemName(itemId);
        if (name.contains("Bronze")) {
            return 2349;
        }
        if (name.contains("Iron")) {
            return 2351;
        }
        if (name.contains("Steel")) {
            return 2353;
        }
        if (name.contains("Mith")) {
            return 2359;
        }
        if (name.contains("Adam") || name.contains("Addy")) {
            return 2361;
        }
        if (name.contains("Rune") || name.contains("Runite")) {
            return 2363;
        }
        return -1;
    }

    private static ObjectMatch findSmithingObject(Player player, String name, int maxDistance) {
        JsonObject objectArgs = new JsonObject();
        objectArgs.addProperty("name", name);
        objectArgs.addProperty("maxDistance", maxDistance);
        ObjectMatch match = findObject(player, objectArgs, maxDistance);
        if (match != null) {
            return match;
        }
        if ("anvil".equals(name)) {
            JsonArray ids = new JsonArray();
            ids.add(2782);
            ids.add(2783);
            ids.add(4306);
            ids.add(6150);
            objectArgs.add("objectIds", ids);
            return findObject(player, objectArgs, maxDistance);
        }
        if ("furnace".equals(name)) {
            JsonArray ids = new JsonArray();
            ids.add(14921);
            ids.add(9390);
            ids.add(2781);
            ids.add(2785);
            ids.add(2966);
            ids.add(3294);
            ids.add(3413);
            ids.add(4304);
            ids.add(4305);
            ids.add(6189);
            ids.add(6190);
            ids.add(11009);
            ids.add(11010);
            ids.add(11666);
            ids.add(12100);
            ids.add(12809);
            objectArgs.add("objectIds", ids);
            return findObject(player, objectArgs, maxDistance);
        }
        return null;
    }

    private static String combatStyleName(int fightMode) {
        if (fightMode == Constants.ATTACK) {
            return "attack";
        }
        if (fightMode == Constants.DEFENCE) {
            return "defence";
        }
        if (fightMode == Constants.STRENGTH) {
            return "strength";
        }
        if (fightMode == 3) {
            return "controlled";
        }
        return "unknown";
    }

    private static int targetSlot(int itemId) {
        if (itemId < 0 || itemId >= ItemData.targetSlots.length) {
            return -1;
        }
        return ItemData.targetSlots[itemId];
    }

    private static boolean isUpgradeableCombatSlot(int slot) {
        return slot == ItemConstants.HAT || slot == ItemConstants.WEAPON || slot == ItemConstants.CHEST
                || slot == ItemConstants.SHIELD || slot == ItemConstants.LEGS || slot == ItemConstants.HANDS
                || slot == ItemConstants.FEET;
    }

    private static int equipmentScore(int itemId, int targetSlot) {
        if (itemId < 0) {
            return 0;
        }
        int[] bonuses = ItemDefinitions.getBonus(itemId);
        int meleeAttack = Math.max(bonuses[0], Math.max(bonuses[1], bonuses[2]));
        int meleeDefence = Math.max(bonuses[5], Math.max(bonuses[6], bonuses[7]));
        if (targetSlot == ItemConstants.WEAPON) {
            return meleeAttack * 4 + bonuses[10] * 6;
        }
        return meleeDefence * 4 + bonuses[10] * 2 + bonuses[9] + bonuses[8] + meleeAttack;
    }

    private static String equipmentSlotName(int slot) {
        switch (slot) {
            case ItemConstants.HAT:
                return "hat";
            case ItemConstants.CAPE:
                return "cape";
            case ItemConstants.AMULET:
                return "amulet";
            case ItemConstants.WEAPON:
                return "weapon";
            case ItemConstants.CHEST:
                return "chest";
            case ItemConstants.SHIELD:
                return "shield";
            case ItemConstants.LEGS:
                return "legs";
            case ItemConstants.HANDS:
                return "hands";
            case ItemConstants.FEET:
                return "feet";
            case ItemConstants.RING:
                return "ring";
            case ItemConstants.ARROWS:
                return "arrows";
            default:
                return "slot-" + slot;
        }
    }

    private static int equipmentSlotByName(String slotName) {
        if ("hat".equals(slotName) || "helm".equals(slotName) || "helmet".equals(slotName)) {
            return ItemConstants.HAT;
        }
        if ("cape".equals(slotName)) {
            return ItemConstants.CAPE;
        }
        if ("amulet".equals(slotName) || "neck".equals(slotName)) {
            return ItemConstants.AMULET;
        }
        if ("weapon".equals(slotName)) {
            return ItemConstants.WEAPON;
        }
        if ("chest".equals(slotName) || "body".equals(slotName) || "platebody".equals(slotName)) {
            return ItemConstants.CHEST;
        }
        if ("shield".equals(slotName)) {
            return ItemConstants.SHIELD;
        }
        if ("legs".equals(slotName) || "platelegs".equals(slotName)) {
            return ItemConstants.LEGS;
        }
        if ("hands".equals(slotName) || "gloves".equals(slotName)) {
            return ItemConstants.HANDS;
        }
        if ("feet".equals(slotName) || "boots".equals(slotName)) {
            return ItemConstants.FEET;
        }
        if ("ring".equals(slotName)) {
            return ItemConstants.RING;
        }
        if ("arrows".equals(slotName) || "ammo".equals(slotName)) {
            return ItemConstants.ARROWS;
        }
        return -1;
    }

    private static class ItemMatch {
        private final int slot;
        private final int itemId;
        private final int amount;

        private ItemMatch(int slot, int itemId, int amount) {
            this.slot = slot;
            this.itemId = itemId;
            this.amount = amount;
        }
    }

    private static class GroundItemMatch {
        private final GroundItem item;
        private final int distance;

        private GroundItemMatch(GroundItem item, int distance) {
            this.item = item;
            this.distance = distance;
        }
    }

    private static class ObjectMatch {
        private final Objects object;
        private final int distance;

        private ObjectMatch(Objects object, int distance) {
            this.object = object;
            this.distance = distance;
        }
    }
}
