package com.rs2.agent;

import static com.rs2.game.content.StaticItemList.KEBAB;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.function.Consumer;

import org.apollo.cache.def.ObjectDefinition;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.GameEngine;
import com.rs2.agent.AgentCombatPlanner.TrainingArea;
import com.rs2.game.content.StaticObjectList;
import com.rs2.game.content.consumables.Food;
import com.rs2.game.content.consumables.Kebabs;
import com.rs2.game.content.skills.SkillHandler;
import com.rs2.game.content.skills.cooking.Cooking;
import com.rs2.game.content.skills.core.Fishing;
import com.rs2.game.content.skills.core.Mining;
import com.rs2.game.content.skills.firemaking.Firemaking;
import com.rs2.game.content.skills.firemaking.LogData;
import com.rs2.agent.AgentSmithingPlanner.SmithingChoice;
import com.rs2.agent.AgentSmithingPlanner.Strategy;
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
import com.rs2.game.objects.impl.OtherObjects;
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
    private static final int MAX_WALK_CHUNK_DISTANCE = 16;
    private static final int MAP_REGION_SIZE = 104;
    private static final int MAP_REGION_MARGIN = 2;
    private static final int COINS = AgentCombatPlanner.coinsItemId();
    private static final int SMALL_FISHING_NET = 303;
    private static final int TINDERBOX = 590;
    private static final int[] NET_FISHING_SPOT_IDS = {
            316, 319, 323, 325, 326, 327, 329, 330, 333, 404
    };
    private static final int[] COOKING_FIRE_OBJECT_IDS = {
            StaticObjectList.FIRE, 11404, 11405, 11406
    };
    private static final int[] RAW_COOKABLE_FOOD_IDS = {
            377, 335, 331, 321, 317, 2132, 2138
    };
    private static final int[] COOKING_OBJECT_IDS = {
            114, 2728, 2729, 2730, 2731, StaticObjectList.FIRE, 2859, 3039, 4172,
            5275, 8750, 9682, 12102, 13539, 13540, 13541, 13542, 13543, 13544, 14919
    };
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
        if ("plan_combat_training".equals(tool)) {
            return planCombatTraining(player, arguments);
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
        if ("find_training_npc".equals(tool)) {
            return findTrainingNpc(player, arguments);
        }
        if ("attack_npc".equals(tool)) {
            return attackNpc(player, arguments);
        }
        if ("train_combat".equals(tool)) {
            return trainCombat(player, arguments);
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
        if ("eat_best_food".equals(tool)) {
            return eatBestFood(player, arguments);
        }
        if ("pickup_ground_item".equals(tool)) {
            return pickupGroundItem(player, arguments);
        }
        if ("fish_food".equals(tool)) {
            return fishFood(player, arguments);
        }
        if ("cook_food".equals(tool)) {
            return cookFood(player, arguments);
        }
        if ("light_fire".equals(tool)) {
            return lightFire(player, arguments);
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
        if ("sell_inventory_items".equals(tool)) {
            return sellInventoryItems(player, arguments);
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
        if ("deposit_excess_coins".equals(tool)) {
            return depositExcessCoins(player, arguments);
        }
        if ("smelt_bar".equals(tool)) {
            return smeltBar(player, arguments);
        }
        if ("smith_item".equals(tool)) {
            return smithItem(player, arguments);
        }
        if ("smith_best_item".equals(tool)) {
            return smithBestItem(player, arguments);
        }
        if ("plan_smithing".equals(tool)) {
            return planSmithing(player, arguments);
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

    private static JsonObject planCombatTraining(Player player, JsonObject arguments) {
        int targetLevel = getInt(arguments, "targetLevel", AgentCombatPlanner.TARGET_MELEE_LEVEL);
        int attackLevel = baseLevel(player, Constants.ATTACK);
        int strengthLevel = baseLevel(player, Constants.STRENGTH);
        int defenceLevel = baseLevel(player, Constants.DEFENCE);
        int hitpointsLevel = baseLevel(player, Constants.HITPOINTS);
        int foodCount = countInventoryFood(player);
        String nextStyle = AgentCombatPlanner.nextTrainingStyle(attackLevel, strengthLevel, defenceLevel, targetLevel);
        TrainingArea area = AgentCombatPlanner.recommendedArea(attackLevel, strengthLevel, defenceLevel, hitpointsLevel, foodCount);
        int coinBudget = AgentCombatPlanner.recommendedCoinBudget(attackLevel, defenceLevel, foodCount);

        JsonObject result = success("Planned combat training.");
        result.addProperty("targetLevel", targetLevel);
        result.addProperty("nextStyle", nextStyle);
        result.addProperty("allTargetsReached", "complete".equals(nextStyle));
        result.addProperty("eatAtHitpoints", AgentCombatPlanner.eatAtHitpoints(hitpointsLevel));
        result.addProperty("retreatAtHitpoints", AgentCombatPlanner.retreatAtHitpoints(hitpointsLevel));
        result.add("recommendedArea", trainingAreaJson(area));
        result.add("trainingAreas", trainingAreasJson());
        result.add("loadout", combatLoadoutJson(player));
        result.add("supplies", combatSuppliesJson(player));

        JsonObject money = new JsonObject();
        int inventoryCoins = countInventoryItem(player, COINS);
        money.addProperty("inventoryCoins", inventoryCoins);
        money.addProperty("bankCoins", countBankItem(player, COINS));
        money.addProperty("recommendedInventoryCoinBudget", coinBudget);
        money.addProperty("carryingExcessCoins", inventoryCoins > coinBudget);
        money.addProperty("excessCoins", Math.max(0, inventoryCoins - coinBudget));
        result.add("money", money);

        JsonArray futureLog = new JsonArray();
        futureLog.add("Measure XP per hour by target and feed observed kill time back into training scores.");
        futureLog.add("Add exact shop price lookup to the loadout planner so it can buy only the cheapest missing upgrades.");
        futureLog.add("Add bank-object routing for restocking food from any training area instead of relying on nearby bank areas.");
        futureLog.add("Record target deaths, food used, and forced retreats in session summaries to tune risk thresholds.");
        result.add("futureEfficiencyLog", futureLog);
        addPlayerState(result, player);
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
        player.getPacketSender().closeAllWindows();
        player.isBanking = false;
        player.isShopping = false;
        int[] walkTarget = boundedWalkTarget(player, x, y);
        player.getPlayerAssistant().playerWalk(walkTarget[0], walkTarget[1]);
        JsonObject result = success("Walking toward tile.");
        addPlayerState(result, player);
        result.add("target", tile(x, y, height));
        if (walkTarget[0] != x || walkTarget[1] != y) {
            result.add("walkTarget", tile(walkTarget[0], walkTarget[1], height));
        }
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
        JsonObject gateResult = maybeUseAlKharidGate(player, landmark, step);
        if (gateResult != null) {
            return gateResult;
        }
        if (!step.isComplete()) {
            player.getPlayerAssistant().resetFollow();
            player.getCombatAssistant().resetPlayerAttack();
            player.endCurrentTask();
            SkillHandler.resetSkills(player);
            player.getPacketSender().closeAllWindows();
            player.isBanking = false;
            player.isShopping = false;
            int[] walkTarget = boundedWalkTarget(player, step.getTile().x, step.getTile().y);
            if (walkTarget[0] != step.getTile().x || walkTarget[1] != step.getTile().y) {
                result.add("walkTarget", tile(walkTarget[0], walkTarget[1], step.getTile().height));
            }
            player.getPlayerAssistant().playerWalk(walkTarget[0], walkTarget[1]);
        }
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject maybeUseAlKharidGate(Player player, AgentKnowledgeBase.Landmark landmark,
            AgentKnowledgeBase.TravelStep step) {
        if (step.isComplete() || !isAlKharidGateCrossingStep(player.absX, player.absY, step.getTile().x,
                step.getTile().y)) {
            return null;
        }
        int coins = countInventoryItem(player, COINS);
        if (coins < 10) {
            JsonObject result = failure("Al Kharid gate crossing needs 10 carried coins.");
            result.addProperty("complete", false);
            result.addProperty("landmark", landmark.getName());
            result.add("target", tile(landmark.getTarget().x, landmark.getTarget().y, landmark.getTarget().height));
            result.add("nextWaypoint", tile(step.getTile().x, step.getTile().y, step.getTile().height));
            addPlayerState(result, player);
            return result;
        }

        int beforeX = player.absX;
        int beforeY = player.absY;
        int beforeCoins = coins;
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        player.endCurrentTask();
        SkillHandler.resetSkills(player);
        player.getPacketSender().closeAllWindows();
        player.isBanking = false;
        player.isShopping = false;
        player.objectId = player.getY() == 3228 ? 2883 : 2882;
        player.objectX = player.absX == 3268 ? 3267 : 3268;
        player.objectY = player.absY;
        OtherObjects.initKharid(player, player.objectId);

        boolean movedNow = player.absX != beforeX || player.absY != beforeY;
        boolean queuedMove = (player.teleportToX != -1 || player.teleportToY != -1)
                && (player.teleportToX != beforeX || player.teleportToY != beforeY);
        JsonObject result = movedNow || queuedMove
                ? success("Paid the Al Kharid gate toll and passed through.")
                : failure("Tried to pay the Al Kharid gate toll, but the gate did not move the player.");
        result.addProperty("complete", false);
        result.addProperty("landmark", landmark.getName());
        result.add("target", tile(landmark.getTarget().x, landmark.getTarget().y, landmark.getTarget().height));
        result.add("nextWaypoint", tile(step.getTile().x, step.getTile().y, step.getTile().height));
        result.addProperty("coinsSpent", Math.max(0, beforeCoins - countInventoryItem(player, COINS)));
        result.add("previousTile", tile(beforeX, beforeY, player.heightLevel));
        addPlayerState(result, player);
        return result;
    }

    static boolean isAlKharidGateCrossingStep(int playerX, int playerY, int targetX, int targetY) {
        if (!isAlKharidGateLine(playerX, playerY)) {
            return false;
        }
        return playerX >= 3268 && targetX <= 3267 || playerX <= 3267 && targetX >= 3268;
    }

    private static boolean isAlKharidGateLine(int x, int y) {
        return (x == 3267 || x == 3268) && (y == 3227 || y == 3228);
    }

    private static int[] boundedWalkTarget(Player player, int targetX, int targetY) {
        return boundedWalkTarget(player.absX, player.absY, player.getMapRegionX(), player.getMapRegionY(),
                targetX, targetY);
    }

    static boolean isWithinObjectInteractionRange(int playerX, int playerY, Objects object) {
        int[] size = objectSize(object);
        int xMin = object.objectX - 1;
        int xMax = object.objectX + size[0];
        int yMin = object.objectY - 1;
        int yMax = object.objectY + size[1];
        return playerX >= xMin && playerX <= xMax && playerY >= yMin && playerY <= yMax;
    }

    static int[] objectInteractionWalkTarget(int playerX, int playerY, int mapRegionX, int mapRegionY,
            Objects object) {
        return objectInteractionWalkTarget(playerX, playerY, mapRegionX, mapRegionY, -1, object, false);
    }

    private static int[] objectInteractionWalkTarget(Player player, Objects object) {
        return objectInteractionWalkTarget(player.absX, player.absY, player.getMapRegionX(), player.getMapRegionY(),
                player.heightLevel, object, true);
    }

    private static boolean isObjectInteractionReachable(Player player, Objects object) {
        if (isWithinObjectInteractionRange(player.absX, player.absY, object)) {
            return true;
        }
        return objectInteractionWalkTarget(player.absX, player.absY, player.getMapRegionX(), player.getMapRegionY(),
                player.heightLevel, object, true) != null;
    }

    private static int[] objectInteractionWalkTarget(int playerX, int playerY, int mapRegionX, int mapRegionY,
            int height, Objects object, boolean requireReachable) {
        int[] size = objectSize(object);
        int bestX = object.objectX;
        int bestY = object.objectY;
        int bestDistance = Integer.MAX_VALUE;
        int bestAxisPenalty = Integer.MAX_VALUE;
        boolean found = false;
        int xMin = object.objectX - 1;
        int xMax = object.objectX + size[0];
        int yMin = object.objectY - 1;
        int yMax = object.objectY + size[1];
        for (int x = xMin; x <= xMax; x++) {
            for (int y = yMin; y <= yMax; y++) {
                boolean insideObject = x >= object.objectX && x < object.objectX + size[0]
                        && y >= object.objectY && y < object.objectY + size[1];
                if (insideObject) {
                    continue;
                }
                if (requireReachable && !isReachableTile(playerX, playerY, height, x, y)) {
                    continue;
                }
                int distance = AgentKnowledgeBase.distance(playerX, playerY, x, y);
                int axisPenalty = (x == object.objectX || y == object.objectY) ? 0 : 1;
                if (distance < bestDistance || (distance == bestDistance && axisPenalty < bestAxisPenalty)) {
                    bestX = x;
                    bestY = y;
                    bestDistance = distance;
                    bestAxisPenalty = axisPenalty;
                    found = true;
                }
            }
        }
        if (!found) {
            return requireReachable ? null : boundedWalkTarget(playerX, playerY, mapRegionX, mapRegionY, bestX, bestY);
        }
        return boundedWalkTarget(playerX, playerY, mapRegionX, mapRegionY, bestX, bestY);
    }

    private static int[] objectSize(Objects object) {
        try {
            return object.getObjectSize();
        } catch (RuntimeException ignored) {
            return new int[] {1, 1};
        }
    }

    private static boolean isReachableTile(int playerX, int playerY, int height, int x, int y) {
        if (height < 0) {
            return true;
        }
        if (playerX == x && playerY == y) {
            return true;
        }
        try {
            return PathFinder.getPathFinder().accessible(playerX, playerY, height, x, y);
        } catch (RuntimeException ignored) {
            return false;
        }
    }

    static int[] boundedWalkTarget(int playerX, int playerY, int mapRegionX, int mapRegionY,
            int targetX, int targetY) {
        int walkX = targetX;
        int walkY = targetY;
        int dx = targetX - playerX;
        int dy = targetY - playerY;
        if (Math.max(Math.abs(dx), Math.abs(dy)) > MAX_WALK_CHUNK_DISTANCE) {
            walkX = playerX + clamp(dx, -MAX_WALK_CHUNK_DISTANCE, MAX_WALK_CHUNK_DISTANCE);
            walkY = playerY + clamp(dy, -MAX_WALK_CHUNK_DISTANCE, MAX_WALK_CHUNK_DISTANCE);
        }
        if (mapRegionX >= 0 && mapRegionY >= 0) {
            int minX = mapRegionX * 8 + MAP_REGION_MARGIN;
            int minY = mapRegionY * 8 + MAP_REGION_MARGIN;
            int maxX = mapRegionX * 8 + MAP_REGION_SIZE - 1 - MAP_REGION_MARGIN;
            int maxY = mapRegionY * 8 + MAP_REGION_SIZE - 1 - MAP_REGION_MARGIN;
            walkX = clamp(walkX, minX, maxX);
            walkY = clamp(walkY, minY, maxY);
        }
        if (walkX == playerX && walkY == playerY && (targetX != playerX || targetY != playerY)) {
            walkX = playerX + Integer.signum(targetX - playerX);
            walkY = playerY + Integer.signum(targetY - playerY);
        }
        return new int[] { walkX, walkY };
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
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

    private static JsonObject findTrainingNpc(Player player, JsonObject arguments) {
        String name = normalize(getString(arguments, "name", getString(arguments, "npc", "")));
        int maxDistance = getInt(arguments, "maxDistance", DEFAULT_SCAN_DISTANCE);
        int minHitpoints = getInt(arguments, "minHitpoints", 1);
        int maxNpcMaxHit = getInt(arguments, "maxNpcMaxHit", Integer.MAX_VALUE);
        boolean reachableOnly = getBoolean(arguments, "reachable", true);
        boolean allowUnderAttack = getBoolean(arguments, "allowUnderAttack", false);
        ArrayList<TrainingNpcMatch> matches = new ArrayList<TrainingNpcMatch>();
        for (Npc npc : NpcHandler.npcs) {
            if (!isNpcCandidate(player, npc)) {
                continue;
            }
            String npcName = normalize(npc.name());
            if (!name.isEmpty() && !npcName.contains(name)) {
                continue;
            }
            if (npc.MaxHP < minHitpoints) {
                continue;
            }
            int npcMaxHit = npcMaxHit(npc);
            if (npcMaxHit > maxNpcMaxHit) {
                continue;
            }
            boolean busy = npc.underAttack && npc.killedBy != player.playerId;
            if (busy && !allowUnderAttack) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, npc.absX, npc.absY);
            if (distance > maxDistance) {
                continue;
            }
            if (reachableOnly && !isReachableNpc(player, npc)) {
                continue;
            }
            int score = trainingScore(player, npc, distance);
            matches.add(new TrainingNpcMatch(npc, distance, score));
        }
        Collections.sort(matches, new Comparator<TrainingNpcMatch>() {
            @Override
            public int compare(TrainingNpcMatch left, TrainingNpcMatch right) {
                if (left.score != right.score) {
                    return right.score - left.score;
                }
                return left.distance - right.distance;
            }
        });
        if (matches.isEmpty()) {
            return failure("No suitable combat training NPC found nearby.");
        }
        JsonObject result = success("Found suitable combat training NPC.");
        TrainingNpcMatch best = matches.get(0);
        result.add("npc", npcJson(best.npc, best.distance, best.score));
        JsonArray candidates = new JsonArray();
        for (int i = 0; i < matches.size() && i < 8; i++) {
            TrainingNpcMatch match = matches.get(i);
            candidates.add(npcJson(match.npc, match.distance, match.score));
        }
        result.add("candidates", candidates);
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

    private static JsonObject trainCombat(Player player, JsonObject arguments) {
        int targetLevel = getInt(arguments, "targetLevel", AgentCombatPlanner.TARGET_MELEE_LEVEL);
        int maxHitpoints = baseLevel(player, Constants.HITPOINTS);
        int eatAt = getInt(arguments, "eatAtHitpoints", AgentCombatPlanner.eatAtHitpoints(maxHitpoints));
        int retreatAt = getInt(arguments, "retreatAtHitpoints", AgentCombatPlanner.retreatAtHitpoints(maxHitpoints));
        if (player.playerLevel[Constants.HITPOINTS] <= eatAt && countInventoryFood(player) > 0) {
            JsonObject eatArgs = new JsonObject();
            eatArgs.addProperty("emergency", player.playerLevel[Constants.HITPOINTS] <= retreatAt);
            eatArgs.addProperty("messagePrefix", "Combat safety");
            return eatBestFood(player, eatArgs);
        }
        if (player.playerLevel[Constants.HITPOINTS] <= retreatAt) {
            JsonObject result = cancelCurrentAction(player);
            result.addProperty("success", false);
            result.addProperty("message", "Hitpoints are unsafe and no food is available. Stopped combat; restock food before continuing.");
            return result;
        }

        int attackLevel = baseLevel(player, Constants.ATTACK);
        int strengthLevel = baseLevel(player, Constants.STRENGTH);
        int defenceLevel = baseLevel(player, Constants.DEFENCE);
        String nextStyle = AgentCombatPlanner.nextTrainingStyle(attackLevel, strengthLevel, defenceLevel, targetLevel);
        String requestedStyle = normalizeCombatStyle(getString(arguments, "style", getString(arguments, "trainingStyle", "")));
        if (!requestedStyle.isEmpty()) {
            nextStyle = requestedStyle;
        }
        if ("complete".equals(nextStyle)) {
            JsonObject result = success("Attack, strength, and defence have reached the target level.");
            addPlayerState(result, player);
            return result;
        }
        if (!combatStyleName(player.fightMode).equals(nextStyle)) {
            JsonObject styleArgs = new JsonObject();
            styleArgs.addProperty("style", nextStyle);
            setCombatStyle(player, styleArgs);
        }

        Npc currentTarget = targetNpc(player);
        if (currentTarget != null && isStaleCombatTargetDistance(
                AgentKnowledgeBase.distance(player.absX, player.absY, currentTarget.absX, currentTarget.absY))) {
            player.getPlayerAssistant().resetFollow();
            player.getCombatAssistant().resetPlayerAttack();
            currentTarget = null;
        }
        if (currentTarget != null) {
            if (!player.goodDistance(player.getX(), player.getY(), currentTarget.getX(), currentTarget.getY(), 1)) {
                JsonObject attackArgs = new JsonObject();
                attackArgs.addProperty("npcIndex", currentTarget.npcId);
                JsonObject result = attackNpc(player, attackArgs);
                result.addProperty("message", "Repositioning to continue combat with " + currentTarget.name() + ".");
                result.addProperty("trainingStyle", nextStyle);
                return result;
            }
            if (!isActivelyTargeting(player, currentTarget) && player.attackTimer <= 0) {
                JsonObject attackArgs = new JsonObject();
                attackArgs.addProperty("npcIndex", currentTarget.npcId);
                JsonObject result = attackNpc(player, attackArgs);
                result.addProperty("message", "Reacquiring stalled combat target " + currentTarget.name() + ".");
                result.addProperty("trainingStyle", nextStyle);
                return result;
            }
            if (!currentTarget.underAttack && currentTarget.killedBy != player.playerId && player.attackTimer <= 0) {
                JsonObject attackArgs = new JsonObject();
                attackArgs.addProperty("npcIndex", currentTarget.npcId);
                JsonObject result = attackNpc(player, attackArgs);
                result.addProperty("message", "Reacquiring combat target " + currentTarget.name() + ".");
                result.addProperty("trainingStyle", nextStyle);
                return result;
            }
            JsonObject result = success("Continuing combat while monitoring hitpoints.");
            result.add("npc", npcJson(currentTarget,
                    AgentKnowledgeBase.distance(player.absX, player.absY, currentTarget.absX, currentTarget.absY)));
            addPlayerState(result, player);
            return result;
        }

        TrainingArea area = AgentCombatPlanner.recommendedArea(attackLevel, strengthLevel, defenceLevel, maxHitpoints,
                countInventoryFood(player));
        String requestedArea = getString(arguments, "area", getString(arguments, "landmark", ""));
        if (!requestedArea.trim().isEmpty()) {
            area = AgentCombatPlanner.findArea(requestedArea);
        }

        JsonObject findArgs = new JsonObject();
        String requestedNpc = getString(arguments, "name", getString(arguments, "npc", ""));
        findArgs.addProperty("name", requestedNpc.trim().isEmpty() ? area.getNpcName() : requestedNpc);
        findArgs.addProperty("maxDistance", getInt(arguments, "maxDistance", DEFAULT_SCAN_DISTANCE));
        findArgs.addProperty("minHitpoints", getInt(arguments, "minHitpoints", Math.max(1, area.getTypicalHitpoints())));
        findArgs.addProperty("maxNpcMaxHit", getInt(arguments, "maxNpcMaxHit", Math.max(2, Math.max(area.getMaxHit(), maxHitpoints / 4))));
        JsonObject found = findTrainingNpc(player, findArgs);
        if (found.has("success") && found.get("success").getAsBoolean() && found.has("npc")) {
            JsonObject npc = found.get("npc").getAsJsonObject();
            JsonObject attackArgs = new JsonObject();
            attackArgs.addProperty("npcIndex", npc.get("npcIndex").getAsInt());
            JsonObject result = attackNpc(player, attackArgs);
            result.addProperty("trainingStyle", nextStyle);
            result.add("trainingPlan", trainingAreaJson(area));
            return result;
        }

        JsonObject travelArgs = new JsonObject();
        travelArgs.addProperty("name", area.getLandmark());
        JsonObject result = travelToLandmark(player, travelArgs);
        result.addProperty("message", "No suitable " + area.getNpcName() + " is nearby; moving toward " + area.getName() + ".");
        result.addProperty("trainingStyle", nextStyle);
        result.add("trainingPlan", trainingAreaJson(area));
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
        if (!isAgentFood(item.itemId)) {
            return failure(DeprecatedItems.getItemName(item.itemId) + " is not edible food.");
        }
        int before = player.playerLevel[Constants.HITPOINTS];
        eatFood(player, item.itemId, item.slot);
        JsonObject result = success("Ate " + DeprecatedItems.getItemName(item.itemId) + ".");
        result.addProperty("healed", Math.max(0, player.playerLevel[Constants.HITPOINTS] - before));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject eatBestFood(Player player, JsonObject arguments) {
        int maxHitpoints = baseLevel(player, Constants.HITPOINTS);
        if (player.playerLevel[Constants.HITPOINTS] >= maxHitpoints) {
            JsonObject result = failure("Hitpoints are already full; eating would waste food.");
            addPlayerState(result, player);
            return result;
        }
        boolean emergency = getBoolean(arguments, "emergency", false);
        FoodMatch food = bestFood(player, emergency);
        if (food == null) {
            JsonObject result = failure("No edible food found in inventory.");
            addPlayerState(result, player);
            return result;
        }
        int beforeHp = player.playerLevel[Constants.HITPOINTS];
        int beforeAmount = countInventoryItem(player, food.itemId);
        eatFood(player, food.itemId, food.slot);
        int afterAmount = countInventoryItem(player, food.itemId);
        int healed = Math.max(0, player.playerLevel[Constants.HITPOINTS] - beforeHp);
        boolean consumed = afterAmount < beforeAmount;
        String prefix = getString(arguments, "messagePrefix", "").trim();
        JsonObject result = consumed
                ? success((prefix.isEmpty() ? "Ate" : prefix + ": ate") + " " + DeprecatedItems.getItemName(food.itemId) + ".")
                : failure("Unable to eat " + DeprecatedItems.getItemName(food.itemId) + " yet; food delay may still be active.");
        result.addProperty("itemId", food.itemId);
        result.addProperty("itemName", DeprecatedItems.getItemName(food.itemId));
        result.addProperty("healAmount", food.healAmount);
        result.addProperty("healed", healed);
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

    private static JsonObject fishFood(Player player, JsonObject arguments) {
        if (player.playerSkilling[Constants.FISHING]) {
            JsonObject result = success("Continuing to fish for food.");
            addPlayerState(result, player);
            return result;
        }
        if (!player.getItemAssistant().playerHasItem(SMALL_FISHING_NET)) {
            JsonObject result = failure("A small fishing net is required to net fish for food.");
            addPlayerState(result, player);
            return result;
        }
        if (player.getItemAssistant().freeSlots() < 1) {
            JsonObject result = failure("Inventory is full. Cook or bank food before fishing more.");
            addPlayerState(result, player);
            return result;
        }
        int maxDistance = getInt(arguments, "maxDistance", DEFAULT_SCAN_DISTANCE);
        Npc spot = findNearestNetFishingSpot(player, maxDistance);
        if (spot == null) {
            JsonObject travelArgs = new JsonObject();
            travelArgs.addProperty("name", "lumbridge fishing spot");
            JsonObject result = travelToLandmark(player, travelArgs);
            result.addProperty("message", "No net fishing spot is nearby; moving toward Lumbridge fishing spot.");
            return result;
        }
        int distance = AgentKnowledgeBase.distance(player.absX, player.absY, spot.absX, spot.absY);
        player.endCurrentTask();
        player.getCombatAssistant().resetPlayerAttack();
        player.getPlayerAssistant().resetFollow();
        if (!player.goodObjectDistance(player.absX, player.absY, spot.absX, spot.absY, 1)) {
            SkillHandler.resetSkills(player);
            player.getPlayerAssistant().playerWalk(spot.absX, spot.absY);
            JsonObject result = success("Walking toward net fishing spot.");
            result.add("npc", npcJson(spot, distance));
            addPlayerState(result, player);
            return result;
        }
        Fishing.fishingNPC(player, 1, spot.npcType);
        JsonObject result = success("Started net fishing for food.");
        result.add("npc", npcJson(spot, distance));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject cookFood(Player player, JsonObject arguments) {
        if (player.playerIsCooking) {
            JsonObject result = success("Continuing to cook food.");
            addPlayerState(result, player);
            return result;
        }
        int itemId = getInt(arguments, "itemId", -1);
        if (itemId < 0) {
            itemId = bestRawCookableFood(player);
        }
        if (itemId < 0 || !isRawCookableFood(itemId) || !player.getItemAssistant().playerHasItem(itemId)) {
            JsonObject result = failure("No cookable raw food is in inventory.");
            addPlayerState(result, player);
            return result;
        }
        ObjectMatch cookingObject = findCookingObject(player, getInt(arguments, "maxDistance", 8),
                getBoolean(arguments, "fireOnly", false));
        if (cookingObject == null) {
            if (getBoolean(arguments, "fireOnly", false)) {
                JsonObject result = failure("No cooking fire is close enough to cook food.");
                addPlayerState(result, player);
                return result;
            }
            JsonObject travelArgs = new JsonObject();
            travelArgs.addProperty("name", "lumbridge range");
            JsonObject result = travelToLandmark(player, travelArgs);
            result.addProperty("message", "No range or fire is close enough to cook food; moving toward Lumbridge range.");
            return result;
        }
        if (!player.goodObjectDistance(player.absX, player.absY, cookingObject.object.objectX, cookingObject.object.objectY, 2)) {
            player.endCurrentTask();
            player.getCombatAssistant().resetPlayerAttack();
            player.getPlayerAssistant().resetFollow();
            SkillHandler.resetSkills(player);
            player.getPlayerAssistant().playerWalk(cookingObject.object.objectX, cookingObject.object.objectY);
            JsonObject result = success("Walking toward cooking object.");
            result.add("object", objectJson(cookingObject.object, cookingObject.distance));
            addPlayerState(result, player);
            return result;
        }
        int amount = Math.max(1, Math.min(countInventoryItem(player, itemId), getInt(arguments, "amount", 28)));
        player.stopMovement();
        player.endCurrentTask();
        player.getCombatAssistant().resetPlayerAttack();
        player.getPlayerAssistant().resetFollow();
        SkillHandler.resetSkills(player);
        player.objectX = cookingObject.object.objectX;
        player.objectY = cookingObject.object.objectY;
        player.turnPlayerTo(cookingObject.object.objectX, cookingObject.object.objectY);
        if (!Cooking.startCooking(player, itemId, cookingObject.object.objectId) && !player.playerIsCooking) {
            JsonObject result = failure("Unable to start cooking " + DeprecatedItems.getItemName(itemId) + ".");
            result.add("object", objectJson(cookingObject.object, cookingObject.distance));
            addPlayerState(result, player);
            return result;
        }
        Cooking.cookItem(player, itemId, amount, cookingObject.object.objectId);
        JsonObject result = success("Started cooking " + DeprecatedItems.getItemName(itemId) + ".");
        result.addProperty("itemId", itemId);
        result.addProperty("amount", amount);
        result.add("object", objectJson(cookingObject.object, cookingObject.distance));
        addPlayerState(result, player);
        return result;
    }

    private static JsonObject lightFire(Player player, JsonObject arguments) {
        if (player.isFiremaking) {
            JsonObject result = success("Continuing to light a fire.");
            addPlayerState(result, player);
            return result;
        }
        if (hasCookingFireNearby(player, 2)) {
            JsonObject result = success("A cooking fire is already nearby.");
            addPlayerState(result, player);
            return result;
        }
        if (!player.getItemAssistant().playerHasItem(TINDERBOX)) {
            JsonObject result = failure("A tinderbox is required to light a fire.");
            addPlayerState(result, player);
            return result;
        }
        int logId = getInt(arguments, "logId", -1);
        if (logId < 0) {
            logId = bestFiremakingLog(player);
        }
        if (logId < 0 || !isFiremakingLog(logId) || !player.getItemAssistant().playerHasItem(logId)) {
            JsonObject result = failure("Logs are required to light a cooking fire.");
            addPlayerState(result, player);
            return result;
        }
        if (!canLightFireHere(player)) {
            JsonObject result = failure("Cannot light a fire on the current tile.");
            addPlayerState(result, player);
            return result;
        }
        player.endCurrentTask();
        player.getCombatAssistant().resetPlayerAttack();
        player.getPlayerAssistant().resetFollow();
        SkillHandler.resetSkills(player);
        Firemaking.attemptFire(player, TINDERBOX, logId, player.absX, player.absY, false);
        JsonObject result = player.isFiremaking ? success("Lighting a cooking fire.")
                : failure("Unable to start lighting a cooking fire here.");
        result.addProperty("logId", logId);
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

    private static JsonObject sellInventoryItems(Player player, JsonObject arguments) {
        if (!player.isShopping) {
            return failure("The player must have a shop open before selling items.");
        }
        String category = normalize(getString(arguments, "category", ""));
        String name = normalize(getString(arguments, "name", ""));
        List<Integer> itemIds = getIntList(arguments, "itemIds");
        int requestedId = getInt(arguments, "itemId", -1);
        if (requestedId >= 0) {
            itemIds.add(requestedId);
        }
        int maxAmount = Math.max(1, getInt(arguments, "amount", Integer.MAX_VALUE));
        int sold = 0;
        int coinsReceived = 0;
        JsonArray soldItems = new JsonArray();
        boolean smithingProducts = "smithing products".equals(category) || "smithing_products".equals(category)
                || "smithing".equals(category) || "armor".equals(category) || "armour".equals(category);
        for (int i = 0; i < player.playerItems.length && sold < maxAmount; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (!itemIds.isEmpty() && !itemIds.contains(itemId)) {
                continue;
            }
            if (smithingProducts && !AgentSmithingPlanner.isSmithingProduct(itemId)) {
                continue;
            }
            String itemName = normalize(DeprecatedItems.getItemName(itemId));
            if (!name.isEmpty() && !itemName.contains(name)) {
                continue;
            }
            if (itemIds.isEmpty() && name.isEmpty() && !smithingProducts) {
                continue;
            }
            int amount = Math.min(Math.max(1, player.playerItemsN[i]), maxAmount - sold);
            int before = countInventoryItem(player, itemId);
            int beforeCoins = countInventoryItem(player, 995);
            boolean soldItem = player.getShopAssistant().sellItem(itemId, i, amount);
            int moved = Math.max(0, before - countInventoryItem(player, itemId));
            int coins = Math.max(0, countInventoryItem(player, 995) - beforeCoins);
            if (!soldItem || moved <= 0) {
                continue;
            }
            JsonObject soldJson = new JsonObject();
            soldJson.addProperty("id", itemId);
            soldJson.addProperty("name", DeprecatedItems.getItemName(itemId));
            soldJson.addProperty("amount", moved);
            soldJson.addProperty("coinsReceived", coins);
            soldItems.add(soldJson);
            sold += moved;
            coinsReceived += coins;
            i = -1;
        }
        JsonObject result = sold > 0 ? success("Sold " + sold + " inventory item" + (sold == 1 ? "." : "s."))
                : failure("No matching inventory items were sold.");
        result.addProperty("sold", sold);
        result.addProperty("coinsReceived", coinsReceived);
        result.add("soldItems", soldItems);
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
        player.isBanking = false;
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
                String landmark = "coal".equals(ore) ? "varrock east coal mine" : "varrock east mine";
                travelArgs.addProperty("name", landmark);
                JsonObject result = travelToLandmark(player, travelArgs);
                result.addProperty("message", "No " + (ore.isEmpty() ? "mineable" : ore)
                        + " rock is nearby; moving toward " + landmark + ".");
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
        boolean inRange = isWithinObjectInteractionRange(player.absX, player.absY, match.object);
        int[] walkTarget = inRange ? null : objectInteractionWalkTarget(player, match.object);
        mineRock(player, match.object);
        String rockName = rock.name().toLowerCase(Locale.ENGLISH);
        String message;
        if (!inRange) {
            message = "Walking into range to mine " + rockName + " ore.";
        } else if (player.isMining) {
            message = "Mining " + rockName + " ore.";
        } else {
            message = "Starting to mine " + rockName + " ore.";
        }
        JsonObject result = success(message);
        result.addProperty("approaching", !inRange);
        result.addProperty("startedMining", player.isMining);
        if (walkTarget != null) {
            result.add("walkTarget", tile(walkTarget[0], walkTarget[1], player.heightLevel));
        }
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
        int requestedId = getInt(arguments, "itemId", -1);
        if (requestedId >= 0) {
            itemIds.add(requestedId);
        }
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
        int requestedId = getInt(arguments, "itemId", -1);
        if (requestedId >= 0) {
            itemIds.add(requestedId);
        }
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

    private static JsonObject depositExcessCoins(Player player, JsonObject arguments) {
        int attackLevel = baseLevel(player, Constants.ATTACK);
        int defenceLevel = baseLevel(player, Constants.DEFENCE);
        int keepAmount = Math.max(0, getInt(arguments, "keepAmount",
                AgentCombatPlanner.recommendedCoinBudget(attackLevel, defenceLevel, countInventoryFood(player))));
        int inventoryCoins = countInventoryItem(player, COINS);
        if (inventoryCoins <= keepAmount) {
            JsonObject result = success("Coin stack is already within the combat budget.");
            result.addProperty("inventoryCoins", inventoryCoins);
            result.addProperty("keptCoins", inventoryCoins);
            result.addProperty("depositedCoins", 0);
            addPlayerState(result, player);
            return result;
        }
        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            return failure("The player must be in a bank area before depositing excess coins.");
        }
        player.stopMovement();
        player.endCurrentTask();
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        SkillHandler.resetSkills(player);
        player.getPacketSender().openUpBank();

        int toDeposit = inventoryCoins - keepAmount;
        int deposited = 0;
        for (int i = 0; i < player.playerItems.length && deposited < toDeposit; i++) {
            if (player.playerItems[i] != COINS + 1) {
                continue;
            }
            int amount = Math.min(toDeposit - deposited, Math.max(1, player.playerItemsN[i]));
            if (player.getItemAssistant().bankItem(COINS, i, amount)) {
                deposited += amount;
                i = -1;
            }
        }
        JsonObject result = deposited > 0 ? success("Deposited excess coins for safer combat training.")
                : failure("Unable to deposit excess coins.");
        result.addProperty("inventoryCoinsBefore", inventoryCoins);
        result.addProperty("keptCoins", countInventoryItem(player, COINS));
        result.addProperty("depositedCoins", deposited);
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
        player.isBanking = false;
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

    private static JsonObject smithBestItem(Player player, JsonObject arguments) {
        int barItemId = getInt(arguments, "barItemId", -1);
        if (barItemId < 0) {
            barItemId = AgentSmithingPlanner.barItemId(getString(arguments, "bar", getString(arguments, "name", "")));
        }
        if (barItemId < 0) {
            barItemId = bestAvailableBar(player);
        }
        if (barItemId < 0) {
            return failure("No recognized bars are available to smith.");
        }
        int availableBars = countInventoryItem(player, barItemId);
        Strategy strategy = AgentSmithingPlanner.strategy(getString(arguments, "strategy", "xp_per_bar"));
        String category = getString(arguments, "category", "");
        SmithingChoice choice = AgentSmithingPlanner.bestSmithableItem(player.playerLevel[Constants.SMITHING], barItemId,
                availableBars, strategy, category);
        if (choice == null) {
            return failure("No smithable item is available for the current Smithing level and bars.");
        }
        int maxActions = availableBars / Math.max(1, choice.getBarsNeeded());
        int amount = Math.max(1, Math.min(maxActions, getInt(arguments, "amount", maxActions)));
        JsonObject smithArgs = new JsonObject();
        smithArgs.addProperty("itemId", choice.getItemId());
        smithArgs.addProperty("amount", amount);
        JsonObject result = smithItem(player, smithArgs);
        result.addProperty("selectedBy", strategy == Strategy.XP_PER_ACTION ? "xp_per_action" : "xp_per_bar");
        result.add("smithingChoice", smithingChoiceJson(player, choice, barItemId, amount));
        return result;
    }

    private static JsonObject planSmithing(Player player, JsonObject arguments) {
        Strategy strategy = AgentSmithingPlanner.strategy(getString(arguments, "strategy", "xp_per_bar"));
        String category = getString(arguments, "category", "");
        JsonObject result = success("Planned smithing options.");
        result.addProperty("strategy", strategy == Strategy.XP_PER_ACTION ? "xp_per_action" : "xp_per_bar");
        result.addProperty("category", category.isEmpty() ? "any" : category);
        JsonArray bars = new JsonArray();
        int[] barIds = {2349, 2351, 2353, 2359, 2361, 2363};
        for (int barId : barIds) {
            int inventoryAmount = countInventoryItem(player, barId);
            int bankAmount = countBankItem(player, barId);
            int availableBars = inventoryAmount + bankAmount;
            JsonObject bar = new JsonObject();
            bar.addProperty("id", barId);
            bar.addProperty("name", DeprecatedItems.getItemName(barId));
            bar.addProperty("inventoryAmount", inventoryAmount);
            bar.addProperty("bankAmount", bankAmount);
            bar.addProperty("availableAmount", availableBars);
            SmithingChoice best = AgentSmithingPlanner.bestSmithableItem(player.playerLevel[Constants.SMITHING], barId,
                    availableBars, strategy, category);
            if (best != null) {
                int actions = availableBars / Math.max(1, best.getBarsNeeded());
                bar.add("bestItem", smithingChoiceJson(player, best, barId, actions));
            }
            JsonArray candidates = new JsonArray();
            for (SmithingChoice choice : AgentSmithingPlanner.smithableItems(player.playerLevel[Constants.SMITHING], barId,
                    Math.max(availableBars, 1), category)) {
                candidates.add(smithingChoiceJson(player, choice, barId, 1));
            }
            bar.add("smithableItems", candidates);
            bars.add(bar);
        }
        result.add("bars", bars);
        result.add("smelting", smeltingPlan(player));
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
        player.isBanking = false;
        player.isShopping = false;
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
        Objects object = Region.getObject(objectId, x, y, player.heightLevel);
        if (object == null) {
            object = new Objects(objectId, x, y, player.heightLevel, 0, 10, 0);
        }
        player.clickObjectType = option;
        player.objectId = objectId;
        player.objectX = x;
        player.objectY = y;
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        player.getPlayerAssistant().requestUpdates();
        player.endCurrentTask();
        if (!isWithinObjectInteractionRange(player.absX, player.absY, object)) {
            int[] walkTarget = objectInteractionWalkTarget(player, object);
            if (walkTarget == null && isNearbyMineableRock(player.absX, player.absY, object)) {
                action.accept(player);
                return;
            }
            if (walkTarget == null) {
                walkTarget = objectInteractionWalkTarget(player.absX, player.absY, player.getMapRegionX(),
                        player.getMapRegionY(), object);
            }
            player.getPlayerAssistant().playerWalk(walkTarget[0], walkTarget[1]);
        }
        ClickObject clickObject = new ClickObject();
        clickObject.onObjectReached(player, action);
    }

    static boolean isNearbyMineableRock(int playerX, int playerY, Objects object) {
        return object != null
                && Mining.rockData.getRock(object.objectId) != null
                && AgentKnowledgeBase.distance(playerX, playerY, object.objectX, object.objectY) <= 2;
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
        boolean nearestReachable = false;
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
            boolean reachable = isObjectInteractionReachable(player, object);
            if (nearest == null || (reachable && !nearestReachable)
                    || (reachable == nearestReachable && distance < nearest.distance)) {
                nearest = new ObjectMatch(object, distance);
                nearestReachable = reachable;
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

    private static Npc findNearestNetFishingSpot(Player player, int maxDistance) {
        Npc nearest = null;
        int nearestDistance = Integer.MAX_VALUE;
        for (Npc npc : NpcHandler.npcs) {
            if (!isNpcPresent(player, npc) || !isNetFishingSpot(npc.npcType)) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, npc.absX, npc.absY);
            if (distance <= maxDistance && distance < nearestDistance) {
                nearest = npc;
                nearestDistance = distance;
            }
        }
        return nearest;
    }

    static boolean isNetFishingSpot(int npcType) {
        for (int spotId : NET_FISHING_SPOT_IDS) {
            if (npcType == spotId) {
                return true;
            }
        }
        return false;
    }

    private static ObjectMatch findCookingObject(Player player, int maxDistance, boolean fireOnly) {
        ObjectMatch temporaryFire = findTemporaryCookingFire(player, maxDistance);
        JsonObject objectArgs = new JsonObject();
        JsonArray objectIds = new JsonArray();
        int[] ids = fireOnly ? COOKING_FIRE_OBJECT_IDS : COOKING_OBJECT_IDS;
        for (int objectId : ids) {
            objectIds.add(objectId);
        }
        objectArgs.add("objectIds", objectIds);
        ObjectMatch staticObject = findObject(player, objectArgs, maxDistance);
        if (temporaryFire == null) {
            return staticObject;
        }
        if (staticObject == null || temporaryFire.distance <= staticObject.distance) {
            return temporaryFire;
        }
        return staticObject;
    }

    static boolean isCookingObject(int objectId) {
        for (int cookingObjectId : COOKING_OBJECT_IDS) {
            if (objectId == cookingObjectId) {
                return true;
            }
        }
        return false;
    }

    static boolean isCookingFireObject(int objectId) {
        for (int fireObjectId : COOKING_FIRE_OBJECT_IDS) {
            if (objectId == fireObjectId) {
                return true;
            }
        }
        return false;
    }

    static boolean hasCookingFireNearby(Player player, int maxDistance) {
        return findTemporaryCookingFire(player, maxDistance) != null;
    }

    private static ObjectMatch findTemporaryCookingFire(Player player, int maxDistance) {
        ObjectMatch nearest = null;
        for (com.rs2.game.objects.Object object : GameEngine.objectManager.objects) {
            if (object == null || object.height != player.heightLevel || !isCookingFireObject(object.objectId)) {
                continue;
            }
            int distance = AgentKnowledgeBase.distance(player.absX, player.absY, object.objectX, object.objectY);
            if (distance > maxDistance) {
                continue;
            }
            Objects wrapped = new Objects(object.objectId, object.objectX, object.objectY, object.height,
                    object.face, object.type, object.tick);
            if (nearest == null || distance < nearest.distance) {
                nearest = new ObjectMatch(wrapped, distance);
            }
        }
        return nearest;
    }

    static boolean canLightFireHere(Player player) {
        return !Boundary.isIn(player, Boundary.BANK_AREA)
                && !Boundary.isIn(player, Boundary.LUMB_BUILDING)
                && !Boundary.isIn(player, Boundary.DRAYNOR_BUILDING)
                && !Boundary.isIn(player, Boundary.DWARF_NO_FIREMAKING)
                && !GameEngine.objectManager.objectExists(player.absX, player.absY);
    }

    static boolean hasWoodcuttingAxe(Player player) {
        return Woodcutting.hasAxe(player);
    }

    static boolean isFiremakingLog(int itemId) {
        for (LogData log : LogData.values()) {
            if (itemId == log.getLogId()) {
                return true;
            }
        }
        return false;
    }

    private static int bestFiremakingLog(Player player) {
        int bestLogId = -1;
        int bestLevel = -1;
        for (LogData log : LogData.values()) {
            if (log.getLevel() > player.playerLevel[Constants.FIREMAKING]) {
                continue;
            }
            if (countInventoryItem(player, log.getLogId()) <= 0) {
                continue;
            }
            if (log.getLevel() > bestLevel) {
                bestLogId = log.getLogId();
                bestLevel = log.getLevel();
            }
        }
        return bestLogId;
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
                || "tin".equals(resource) || "iron".equals(resource) || "coal".equals(resource);
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

    private static boolean isActivelyTargeting(Player player, Npc npc) {
        return npc != null && (player.npcIndex == npc.npcId || player.followNpcId == npc.npcId);
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

    static boolean isStaleCombatTargetDistance(int distance) {
        return distance > DEFAULT_SCAN_DISTANCE;
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
        playerJson.add("combatReadiness", combatReadiness(player));
        if (player.isShopping) {
            playerJson.add("shop", shop(player));
        }
        result.add("player", playerJson);
    }

    private static JsonObject combatReadiness(Player player) {
        int attackLevel = baseLevel(player, Constants.ATTACK);
        int strengthLevel = baseLevel(player, Constants.STRENGTH);
        int defenceLevel = baseLevel(player, Constants.DEFENCE);
        int hitpointsLevel = baseLevel(player, Constants.HITPOINTS);
        int foodCount = countInventoryFood(player);
        JsonObject json = new JsonObject();
        json.addProperty("nextStyle", AgentCombatPlanner.nextTrainingStyle(attackLevel, strengthLevel, defenceLevel,
                AgentCombatPlanner.TARGET_MELEE_LEVEL));
        json.addProperty("eatAtHitpoints", AgentCombatPlanner.eatAtHitpoints(hitpointsLevel));
        json.addProperty("retreatAtHitpoints", AgentCombatPlanner.retreatAtHitpoints(hitpointsLevel));
        json.addProperty("inventoryFoodCount", foodCount);
        json.addProperty("inventoryFoodHealing", totalInventoryFoodHealing(player));
        json.addProperty("bankFoodCount", countBankFood(player));
        json.add("recommendedArea", trainingAreaJson(AgentCombatPlanner.recommendedArea(attackLevel, strengthLevel,
                defenceLevel, hitpointsLevel, foodCount)));
        int coinBudget = AgentCombatPlanner.recommendedCoinBudget(attackLevel, defenceLevel, foodCount);
        json.addProperty("recommendedInventoryCoinBudget", coinBudget);
        json.addProperty("inventoryCoins", countInventoryItem(player, COINS));
        json.addProperty("bankCoins", countBankItem(player, COINS));
        json.addProperty("carryingExcessCoins", countInventoryItem(player, COINS) > coinBudget);
        return json;
    }

    private static JsonObject trainingAreaJson(TrainingArea area) {
        JsonObject json = new JsonObject();
        json.addProperty("name", area.getName());
        json.addProperty("landmark", area.getLandmark());
        json.addProperty("npcName", area.getNpcName());
        json.addProperty("typicalHitpoints", area.getTypicalHitpoints());
        json.addProperty("highHitpoints", area.getHighHitpoints());
        json.addProperty("maxHit", area.getMaxHit());
        json.addProperty("recommendedMeleeLevel", area.getRecommendedMeleeLevel());
        json.addProperty("recommendedUntilLevel", area.getRecommendedUntilLevel());
        return json;
    }

    private static JsonArray trainingAreasJson() {
        JsonArray array = new JsonArray();
        for (TrainingArea area : AgentCombatPlanner.trainingAreas()) {
            array.add(trainingAreaJson(area));
        }
        return array;
    }

    private static JsonObject combatSuppliesJson(Player player) {
        JsonObject json = new JsonObject();
        json.addProperty("inventoryFoodCount", countInventoryFood(player));
        json.addProperty("inventoryFoodHealing", totalInventoryFoodHealing(player));
        json.addProperty("bankFoodCount", countBankFood(player));
        json.addProperty("bankFoodHealing", totalBankFoodHealing(player));
        json.add("inventoryFood", foodInventory(player));
        return json;
    }

    private static JsonObject combatLoadoutJson(Player player) {
        JsonObject json = new JsonObject();
        json.add("weapon", recommendedGearJson(player, "weapon", AgentCombatPlanner.recommendedWeaponId(
                baseLevel(player, Constants.ATTACK)), ItemConstants.WEAPON));
        json.add("body", recommendedGearJson(player, "body", AgentCombatPlanner.recommendedBodyId(
                baseLevel(player, Constants.DEFENCE)), ItemConstants.CHEST));
        json.add("legs", recommendedGearJson(player, "legs", AgentCombatPlanner.recommendedLegsId(
                baseLevel(player, Constants.DEFENCE)), ItemConstants.LEGS));
        json.add("shield", recommendedGearJson(player, "shield", AgentCombatPlanner.recommendedShieldId(
                baseLevel(player, Constants.DEFENCE)), ItemConstants.SHIELD));
        return json;
    }

    private static JsonObject recommendedGearJson(Player player, String slotName, int itemId, int equipmentSlot) {
        JsonObject json = new JsonObject();
        json.addProperty("slotName", slotName);
        json.addProperty("recommendedItemId", itemId);
        json.addProperty("recommendedItemName", AgentCombatPlanner.itemName(itemId));
        json.addProperty("currentlyEquippedItemId", player.playerEquipment[equipmentSlot]);
        json.addProperty("currentlyEquippedItemName", AgentCombatPlanner.itemName(player.playerEquipment[equipmentSlot]));
        json.addProperty("inInventory", itemId >= 0 && countInventoryItem(player, itemId) > 0);
        json.addProperty("inBank", itemId >= 0 && countBankItem(player, itemId) > 0);
        json.addProperty("equipped", itemId >= 0 && player.playerEquipment[equipmentSlot] == itemId);
        return json;
    }

    private static JsonArray foodInventory(Player player) {
        JsonArray array = new JsonArray();
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (!isAgentFood(itemId)) {
                continue;
            }
            JsonObject food = new JsonObject();
            food.addProperty("slot", i);
            food.addProperty("id", itemId);
            food.addProperty("name", DeprecatedItems.getItemName(itemId));
            food.addProperty("amount", player.playerItemsN[i]);
            food.addProperty("heal", agentFoodHealAmount(itemId));
            array.add(food);
        }
        return array;
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
            if (isAgentFood(itemId)) {
                item.addProperty("foodHeal", agentFoodHealAmount(itemId));
            }
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
            if (isAgentFood(itemId)) {
                item.addProperty("foodHeal", agentFoodHealAmount(itemId));
            }
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
        return npcJson(npc, distance, Integer.MIN_VALUE);
    }

    private static JsonObject npcJson(Npc npc, int distance, int trainingScore) {
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
        object.addProperty("combatLevel", npcCombatLevel(npc));
        object.addProperty("maxHit", npcMaxHit(npc));
        object.addProperty("attack", npc.attack);
        object.addProperty("defence", npc.defence);
        object.addProperty("aggressive", npc.aggressive);
        if (trainingScore != Integer.MIN_VALUE) {
            object.addProperty("trainingScore", trainingScore);
        }
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

    private static String normalizeCombatStyle(String value) {
        String style = normalize(value);
        if ("accurate".equals(style)) {
            return "attack";
        }
        if ("aggressive".equals(style)) {
            return "strength";
        }
        if ("defense".equals(style) || "defensive".equals(style)) {
            return "defence";
        }
        if ("shared".equals(style)) {
            return "controlled";
        }
        if ("attack".equals(style) || "strength".equals(style)
                || "defence".equals(style) || "controlled".equals(style)) {
            return style;
        }
        return "";
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

    private static int baseLevel(Player player, int skill) {
        return player.getPlayerAssistant().getLevelForXP(player.playerXP[skill]);
    }

    static int countInventoryFood(Player player) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId > 0 && isAgentFood(storedId - 1)) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    private static int totalInventoryFoodHealing(Player player) {
        int healing = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId > 0 && isAgentFood(storedId - 1)) {
                healing += Math.max(1, player.playerItemsN[i]) * agentFoodHealAmount(storedId - 1);
            }
        }
        return healing;
    }

    static int countBankFood(Player player) {
        int count = 0;
        for (int i = 0; i < player.bankItems.length; i++) {
            int storedId = player.bankItems[i];
            if (storedId > 0 && isAgentFood(storedId - 1)) {
                count += Math.max(1, player.bankItemsN[i]);
            }
        }
        return count;
    }

    private static int totalBankFoodHealing(Player player) {
        int healing = 0;
        for (int i = 0; i < player.bankItems.length; i++) {
            int storedId = player.bankItems[i];
            if (storedId > 0 && isAgentFood(storedId - 1)) {
                healing += Math.max(1, player.bankItemsN[i]) * agentFoodHealAmount(storedId - 1);
            }
        }
        return healing;
    }

    private static FoodMatch bestFood(Player player, boolean emergency) {
        int maxHitpoints = baseLevel(player, Constants.HITPOINTS);
        int missing = Math.max(1, maxHitpoints - player.playerLevel[Constants.HITPOINTS]);
        FoodMatch best = null;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (!isAgentFood(itemId)) {
                continue;
            }
            int heal = agentFoodHealAmount(itemId);
            FoodMatch candidate = new FoodMatch(i, itemId, heal);
            if (best == null) {
                best = candidate;
                continue;
            }
            if (emergency) {
                if (candidate.healAmount > best.healAmount) {
                    best = candidate;
                }
                continue;
            }
            boolean candidateCovers = candidate.healAmount >= missing;
            boolean bestCovers = best.healAmount >= missing;
            if (candidateCovers && (!bestCovers || candidate.healAmount < best.healAmount)) {
                best = candidate;
            } else if (!candidateCovers && !bestCovers && candidate.healAmount > best.healAmount) {
                best = candidate;
            }
        }
        return best;
    }

    static boolean isAgentFood(int itemId) {
        return itemId == KEBAB || Food.isFood(itemId);
    }

    static int agentFoodHealAmount(int itemId) {
        if (itemId == KEBAB) {
            return 5;
        }
        return Food.getHealAmount(itemId);
    }

    static boolean isRawCookableFood(int itemId) {
        for (int rawFoodId : RAW_COOKABLE_FOOD_IDS) {
            if (itemId == rawFoodId) {
                return true;
            }
        }
        return false;
    }

    static int countInventoryRawCookableFood(Player player) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId > 0 && isRawCookableFood(storedId - 1)) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    static int countBankRawCookableFood(Player player) {
        int count = 0;
        for (int i = 0; i < player.bankItems.length; i++) {
            int storedId = player.bankItems[i];
            if (storedId > 0 && isRawCookableFood(storedId - 1)) {
                count += Math.max(1, player.bankItemsN[i]);
            }
        }
        return count;
    }

    static int bestRawCookableFood(Player player) {
        for (int rawFoodId : RAW_COOKABLE_FOOD_IDS) {
            if (countInventoryItem(player, rawFoodId) > 0) {
                return rawFoodId;
            }
        }
        return -1;
    }

    static int bestBankRawCookableFood(Player player) {
        for (int rawFoodId : RAW_COOKABLE_FOOD_IDS) {
            if (countBankItem(player, rawFoodId) > 0) {
                return rawFoodId;
            }
        }
        return -1;
    }

    static int bestBankFood(Player player) {
        int bestItemId = -1;
        int bestHeal = -1;
        for (int i = 0; i < player.bankItems.length; i++) {
            int storedId = player.bankItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (!isAgentFood(itemId)) {
                continue;
            }
            int heal = agentFoodHealAmount(itemId);
            if (heal > bestHeal) {
                bestItemId = itemId;
                bestHeal = heal;
            }
        }
        return bestItemId;
    }

    private static void eatFood(Player player, int itemId, int slot) {
        if (itemId == KEBAB) {
            Kebabs.eat(player, slot);
            return;
        }
        Food.eat(player, itemId, slot);
    }

    private static int trainingScore(Player player, Npc npc, int distance) {
        return AgentCombatPlanner.scoreNpc(npc.name(), npc.MaxHP, npcCombatLevel(npc), npcMaxHit(npc), npc.attack,
                npc.defence, player.combatLevel, baseLevel(player, Constants.HITPOINTS), distance, npc.underAttack);
    }

    private static int npcCombatLevel(Npc npc) {
        return npc == null ? 0 : NpcHandler.getNpcListCombat(npc.npcType);
    }

    private static int npcMaxHit(Npc npc) {
        if (npc == null) {
            return 0;
        }
        if (npc.maxHit > 0) {
            return npc.maxHit;
        }
        return NpcHandler.getMaxHit(npc.npcId);
    }

    static int countInventoryItem(Player player, int itemId) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            if (player.playerItems[i] == itemId + 1) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    static int countBankItem(Player player, int itemId) {
        int count = 0;
        for (int i = 0; i < player.bankItems.length; i++) {
            if (player.bankItems[i] == itemId + 1) {
                count += Math.max(1, player.bankItemsN[i]);
            }
        }
        return count;
    }

    private static int bestAvailableBar(Player player) {
        int[] barIds = {2363, 2361, 2359, 2353, 2351, 2349};
        for (int barId : barIds) {
            int amount = countInventoryItem(player, barId);
            if (amount <= 0) {
                continue;
            }
            if (AgentSmithingPlanner.bestSmithableItem(player.playerLevel[Constants.SMITHING], barId, amount,
                    Strategy.XP_PER_BAR) != null) {
                return barId;
            }
        }
        return -1;
    }

    private static JsonObject smithingChoiceJson(Player player, SmithingChoice choice, int barItemId, int actions) {
        JsonObject json = new JsonObject();
        json.addProperty("itemId", choice.getItemId());
        json.addProperty("name", choice.getItemName());
        json.addProperty("barItemId", barItemId);
        json.addProperty("barName", DeprecatedItems.getItemName(barItemId));
        json.addProperty("barsNeeded", choice.getBarsNeeded());
        json.addProperty("requiredLevel", choice.getRequiredLevel());
        json.addProperty("xp", choice.getXp());
        json.addProperty("xpPerThousandBars", choice.getXpPerThousandBars());
        json.addProperty("actions", Math.max(0, actions));
        json.addProperty("totalBars", Math.max(0, actions) * choice.getBarsNeeded());
        json.addProperty("totalXp", Math.max(0, actions) * choice.getXp());
        json.addProperty("estimatedSellValueEach", estimatedSellValue(player, choice.getItemId()));
        json.addProperty("estimatedSellValueTotal", Math.max(0, actions) * estimatedSellValue(player, choice.getItemId()));
        return json;
    }

    private static JsonArray smeltingPlan(Player player) {
        JsonArray array = new JsonArray();
        for (int[] row : Smelting.data) {
            int primaryItemId = row[3];
            int secondaryItemId = row[4];
            int secondaryAmount = row[5];
            int outputItemId = row[6];
            int levelRequired = row[1];
            int possible = countInventoryItem(player, primaryItemId) + countBankItem(player, primaryItemId);
            if (secondaryItemId > 0 && secondaryAmount > 0) {
                int secondaryPossible = (countInventoryItem(player, secondaryItemId) + countBankItem(player, secondaryItemId))
                        / secondaryAmount;
                possible = Math.min(possible, secondaryPossible);
            }
            JsonObject json = new JsonObject();
            json.addProperty("barType", row[0]);
            json.addProperty("barItemId", outputItemId);
            json.addProperty("barName", DeprecatedItems.getItemName(outputItemId));
            json.addProperty("requiredLevel", levelRequired);
            json.addProperty("xp", row[2]);
            json.addProperty("possibleAmount", player.playerLevel[Constants.SMITHING] >= levelRequired ? Math.max(0, possible) : 0);
            json.addProperty("primaryOreId", primaryItemId);
            json.addProperty("primaryOreName", DeprecatedItems.getItemName(primaryItemId));
            if (secondaryItemId > 0) {
                json.addProperty("secondaryOreId", secondaryItemId);
                json.addProperty("secondaryOreName", DeprecatedItems.getItemName(secondaryItemId));
                json.addProperty("secondaryOreAmount", secondaryAmount);
            }
            array.add(json);
        }
        return array;
    }

    private static int estimatedSellValue(Player player, int itemId) {
        if (player.isShopping) {
            return player.getShopAssistant().getItemShopValue(itemId, 0, true);
        }
        return 0;
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
            return meleeAttack * 4 + bonuses[10] * 6 + weaponPreferenceBonus(itemId);
        }
        return meleeDefence * 4 + bonuses[10] * 2 + bonuses[9] + bonuses[8] + meleeAttack;
    }

    private static int weaponPreferenceBonus(int itemId) {
        return weaponPreferenceBonus(DeprecatedItems.getItemName(itemId));
    }

    static int weaponPreferenceBonus(String itemName) {
        String name = normalize(itemName);
        if (name.contains("scimitar")) {
            return 8;
        }
        if (name.contains("sword")) {
            return 5;
        }
        if (name.contains("dagger")) {
            return 3;
        }
        if (name.contains("mace")) {
            return 2;
        }
        if (name.contains("battleaxe")) {
            return 1;
        }
        if (name.contains("pickaxe")) {
            return -10;
        }
        if (name.endsWith(" axe") || name.contains(" hatchet")) {
            return -8;
        }
        return 0;
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

    private static class FoodMatch {
        private final int slot;
        private final int itemId;
        private final int healAmount;

        private FoodMatch(int slot, int itemId, int healAmount) {
            this.slot = slot;
            this.itemId = itemId;
            this.healAmount = healAmount;
        }
    }

    private static class TrainingNpcMatch {
        private final Npc npc;
        private final int distance;
        private final int score;

        private TrainingNpcMatch(Npc npc, int distance, int score) {
            this.npc = npc;
            this.distance = distance;
            this.score = score;
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
