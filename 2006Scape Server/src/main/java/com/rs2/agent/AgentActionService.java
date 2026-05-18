package com.rs2.agent;

import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.agent.AgentSmithingPlanner.SmithingChoice;
import com.rs2.game.content.skills.SkillHandler;
import com.rs2.game.content.skills.smithing.SmithingData;
import com.rs2.game.players.Player;
import com.rs2.game.shops.ShopHandler;
import com.rs2.world.Boundary;

public class AgentActionService {

    public static final AgentActionService INSTANCE = new AgentActionService();

    private static final long ACTION_TIMEOUT_MS = 5000L;
    private static final int DEFAULT_GOAL_TARGET_LEVEL = 60;
    private static final int DEFAULT_GOAL_STEP_INTERVAL_TICKS = 5;
    private static final int DEFAULT_GOAL_MAX_ACTIONS = 250000;
    private static final int SMALL_FISHING_NET = 303;
    private static final int TINDERBOX = 590;
    private static final int BRONZE_AXE = 1351;
    private static final int LOGS = 1511;
    private static final int COINS = 995;
    private static final int COWHIDE = 1739;
    private static final int BONES = 526;
    private static final int RAW_BEEF = 2132;
    private static final int HAMMER = 2347;
    private static final int BRONZE_PICKAXE = 1265;
    private static final int IRON_PICKAXE = 1267;
    private static final int STEEL_PICKAXE = 1269;
    private static final int ADAMANT_PICKAXE = 1271;
    private static final int MITHRIL_PICKAXE = 1273;
    private static final int RUNE_PICKAXE = 1275;
    private static final int COPPER_ORE = 436;
    private static final int TIN_ORE = 438;
    private static final int IRON_ORE = 440;
    private static final int COAL = 453;
    private static final int BRONZE_BAR = 2349;
    private static final int IRON_BAR = 2351;
    private static final int STEEL_BAR = 2353;
    private static final int MITHRIL_BAR = 2359;
    private static final int ADAMANT_BAR = 2361;
    private static final int RUNE_BAR = 2363;
    private static final int[] COMBAT_SUPPLY_ITEM_IDS = {
            BONES, 532, COINS, COWHIDE, RAW_BEEF, 2138, 314
    };
    private static final int[] BANK_TRIGGER_COMBAT_SUPPLY_ITEM_IDS = {
            BONES, 532, COWHIDE, RAW_BEEF, 2138, 314
    };
    private static final int[] COMBAT_GEAR_ITEM_IDS = {
            1277, 1279, 1281, 1285, 1287, 1291,
            1323, 1325, 1329, 1115, 1105, 1121, 1067, 1069, 1071, 1171, 1173, 1175, 1181
    };
    private static final int[] ACCOUNT_STORAGE_ITEM_IDS = {
            303, 590, 841, 882, 1205, 1265, 1351, 1925, 1931, HAMMER,
            555, 556, 557, 558, 559
    };
    private static final int[] FOOD_TOOL_ITEM_IDS = {
            SMALL_FISHING_NET
    };
    private static final int MIN_FREE_SLOTS_BEFORE_BANKING = 4;
    private static final int SUPPLY_COUNT_BEFORE_BANKING = 18;
    private static final int ACCOUNT_STORAGE_COUNT_BEFORE_BANKING = 6;
    private static final int MIN_FOOD_BEFORE_RESTOCK = 3;
    private static final int MIN_RAW_FOOD_BEFORE_COOKING = 8;
    private static final int DESIRED_LOW_LEVEL_FOOD = 10;
    private static final int DESIRED_HIGH_LEVEL_FOOD = 18;
    private static final int GEAR_CHECK_INTERVAL_ACTIONS = 80;
    private static final int MIN_GEAR_MONEY_ITEMS_BEFORE_SELLING = 27;
    private static final int MIN_BARS_BEFORE_SMITHING = 8;
    private static final int MIN_ORE_SETS_BEFORE_SMELTING = 10;
    private static final int[] PICKAXE_ITEM_IDS = {
            BRONZE_PICKAXE, IRON_PICKAXE, STEEL_PICKAXE, MITHRIL_PICKAXE, ADAMANT_PICKAXE, RUNE_PICKAXE
    };
    private static final int[] GEAR_MONEY_ITEM_IDS = {
            COPPER_ORE, TIN_ORE, IRON_ORE, COAL, BRONZE_BAR, IRON_BAR,
            STEEL_BAR, MITHRIL_BAR, ADAMANT_BAR, RUNE_BAR
    };
    private static final GearTarget[] WEAPON_GEAR_TARGETS = {
            new GearTarget(1279, 1, 1, "varrock sword shop", "sword", 91),
            new GearTarget(1281, 5, 2, "varrock sword shop", "sword", 325),
            new GearTarget(1285, 20, 3, "varrock sword shop", "sword", 845)
    };
    private static final GearTarget[] BODY_GEAR_TARGETS = {
            new GearTarget(1115, 1, 1, "varrock armour shop", "armour", 560),
            new GearTarget(1105, 5, 2, "varrock armour shop", "armour", 750),
            new GearTarget(1121, 20, 3, "varrock armour shop", "armour", 5200)
    };
    private static final GearTarget[] LEGS_GEAR_TARGETS = {
            new GearTarget(1067, 1, 1, "varrock armour shop", "armour", 280)
    };

    private final ConcurrentLinkedQueue<QueuedAction> queuedActions = new ConcurrentLinkedQueue<QueuedAction>();
    private final AtomicLong serverTick = new AtomicLong(0L);
    private final ConcurrentHashMap<Integer, CombatGoal> combatGoals = new ConcurrentHashMap<Integer, CombatGoal>();

    public JsonObject submitTool(String token, String tool, JsonObject arguments) {
        if ("walk_to_tile_until_arrived".equals(tool)) {
            return walkToTileUntilArrived(token, arguments == null ? new JsonObject() : arguments);
        }
        if ("travel_to_landmark_until_arrived".equals(tool)) {
            return travelToLandmarkUntilArrived(token, arguments == null ? new JsonObject() : arguments);
        }
        if ("mine_ore_until_inventory_full".equals(tool)) {
            return mineOreUntilInventoryFull(token, arguments == null ? new JsonObject() : arguments);
        }
        if ("chop_tree_until_inventory_full".equals(tool)) {
            return chopTreeUntilInventoryFull(token, arguments == null ? new JsonObject() : arguments);
        }
        if ("wait_until_idle".equals(tool)) {
            return waitUntilIdle(token, arguments == null ? new JsonObject() : arguments);
        }
        if ("wait_ticks".equals(tool)) {
            int ticks = Math.max(1, Math.min(25, getInt(arguments, "ticks", 1)));
            final long submittedTick = serverTick.get();
            final long targetTick = submittedTick + ticks;
            long timeoutMs = Math.max(ACTION_TIMEOUT_MS, (long) (ticks + 2) * Constants.CYCLE_TIME);
            return submitForTick(targetTick, new Callable<JsonObject>() {
                @Override
                public JsonObject call() {
                    AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                    if (session == null || session.getPlayer() == null) {
                        return AgentToolService.failure("Agent session is no longer valid.");
                    }
                    JsonObject result = AgentToolService.observeState(session.getPlayer());
                    result.addProperty("waitedTicks", ticks);
                    result.addProperty("submittedTick", submittedTick);
                    result.addProperty("targetTick", targetTick);
                    return result;
                }
            }, timeoutMs);
        }
        if ("start_combat_goal".equals(tool) || "observe_goal".equals(tool) || "stop_goal".equals(tool)) {
            return submitOnGameTick(token, new Callable<JsonObject>() {
                @Override
                public JsonObject call() {
                    AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                    if (session == null) {
                        return AgentToolService.failure("Agent session is no longer valid.");
                    }
                    Player player = session.getPlayer();
                    if (player == null) {
                        return AgentToolService.failure("The claimed player is no longer online.");
                    }
                    JsonObject safeArguments = arguments == null ? new JsonObject() : arguments;
                    if ("start_combat_goal".equals(tool)) {
                        return startCombatGoal(session, player, safeArguments);
                    }
                    if ("stop_goal".equals(tool)) {
                        return stopGoal(session, player);
                    }
                    return observeGoal(player);
                }
            });
        }
        return submitOnGameTick(token, new Callable<JsonObject>() {
            @Override
            public JsonObject call() {
                AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                if (session == null) {
                    return AgentToolService.failure("Agent session is no longer valid.");
                }
                Player player = session.getPlayer();
                if (player == null) {
                    return AgentToolService.failure("The claimed player is no longer online.");
                }
                return AgentToolService.handle(player, tool, arguments == null ? new JsonObject() : arguments);
            }
        });
    }

    private JsonObject walkToTileUntilArrived(final String token, final JsonObject arguments) {
        int maxTicks = Math.max(1, Math.min(250, getInt(arguments, "maxTicks", 120)));
        final int x = getInt(arguments, "x", -1);
        final int y = getInt(arguments, "y", -1);
        final int height = getInt(arguments, "height", 0);
        final int stopDistance = Math.max(0, Math.min(20, getInt(arguments, "stopDistance", 0)));
        if (x < 0 || y < 0) {
            return AgentToolService.failure("x and y are required.");
        }
        JsonObject lastResult = null;
        for (int tick = 0; tick < maxTicks; tick++) {
            lastResult = submitOnGameTick(token, new Callable<JsonObject>() {
                @Override
                public JsonObject call() {
                    AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                    if (session == null) {
                        return AgentToolService.failure("Agent session is no longer valid.");
                    }
                    Player player = session.getPlayer();
                    if (player == null) {
                        return AgentToolService.failure("The claimed player is no longer online.");
                    }
                    if (tileArrived(player, x, y, height, stopDistance)) {
                        JsonObject result = AgentToolService.observeState(player);
                        result.addProperty("complete", true);
                        return result;
                    }
                    if (player.isMoving) {
                        JsonObject result = AgentToolService.observeState(player);
                        result.addProperty("complete", false);
                        return result;
                    }
                    JsonObject result = AgentToolService.handle(player, "walk_to_tile", arguments);
                    result.addProperty("complete", tileArrived(player, x, y, height, stopDistance));
                    return result;
                }
            });
            if (!isSuccess(lastResult)) {
                return addBatchStatus(lastResult, "blocked", tick + 1);
            }
            if (getBoolean(lastResult, "complete", false)) {
                return addBatchStatus(lastResult, "arrived", tick + 1);
            }
            JsonObject player = playerObject(lastResult);
            if (player != null && getBoolean(player, "isDead", false)) {
                return addBatchStatus(lastResult, "player_dead", tick + 1);
            }
        }
        return addBatchStatus(lastResult == null ? AgentToolService.failure("No walk action was attempted.") : lastResult,
                "max_ticks_reached", maxTicks);
    }

    private JsonObject travelToLandmarkUntilArrived(final String token, final JsonObject arguments) {
        int maxTicks = Math.max(1, Math.min(250, getInt(arguments, "maxTicks", 120)));
        JsonObject lastResult = null;
        for (int tick = 0; tick < maxTicks; tick++) {
            lastResult = submitOnGameTick(token, new Callable<JsonObject>() {
                @Override
                public JsonObject call() {
                    AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                    if (session == null) {
                        return AgentToolService.failure("Agent session is no longer valid.");
                    }
                    Player player = session.getPlayer();
                    if (player == null) {
                        return AgentToolService.failure("The claimed player is no longer online.");
                    }
                    if (player.isMoving) {
                        return AgentToolService.observeState(player);
                    }
                    return AgentToolService.handle(player, "travel_to_landmark", arguments);
                }
            });
            if (!isSuccess(lastResult)) {
                return addBatchStatus(lastResult, "blocked", tick + 1);
            }
            if (getBoolean(lastResult, "complete", false)) {
                return addBatchStatus(lastResult, "arrived", tick + 1);
            }
            JsonObject player = playerObject(lastResult);
            if (player != null && getBoolean(player, "isDead", false)) {
                return addBatchStatus(lastResult, "player_dead", tick + 1);
            }
        }
        return addBatchStatus(lastResult == null ? AgentToolService.failure("No travel action was attempted.") : lastResult,
                "max_ticks_reached", maxTicks);
    }

    private JsonObject mineOreUntilInventoryFull(final String token, final JsonObject arguments) {
        int maxTicks = Math.max(1, Math.min(250, getInt(arguments, "maxTicks", 180)));
        JsonObject lastResult = null;
        for (int tick = 0; tick < maxTicks; tick++) {
            lastResult = submitOnGameTick(token, new Callable<JsonObject>() {
                @Override
                public JsonObject call() {
                    AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                    if (session == null) {
                        return AgentToolService.failure("Agent session is no longer valid.");
                    }
                    Player player = session.getPlayer();
                    if (player == null) {
                        return AgentToolService.failure("The claimed player is no longer online.");
                    }
                    if (player.getItemAssistant().freeSlots() < 1) {
                        return AgentToolService.observeState(player);
                    }
                    if (player.isMoving || player.isMining || player.miningRock) {
                        return AgentToolService.observeState(player);
                    }
                    return AgentToolService.handle(player, "mine_ore", arguments);
                }
            });
            if (!isSuccess(lastResult)) {
                return addBatchStatus(lastResult, "blocked", tick + 1);
            }
            JsonObject player = playerObject(lastResult);
            if (player != null && getBoolean(player, "isDead", false)) {
                return addBatchStatus(lastResult, "player_dead", tick + 1);
            }
            if (player != null && getInt(player, "freeInventorySlots", 1) < 1) {
                return addBatchStatus(lastResult, "inventory_full", tick + 1);
            }
        }
        return addBatchStatus(lastResult == null ? AgentToolService.failure("No mining action was attempted.") : lastResult,
                "max_ticks_reached", maxTicks);
    }

    private JsonObject chopTreeUntilInventoryFull(final String token, final JsonObject arguments) {
        int maxTicks = Math.max(1, Math.min(250, getInt(arguments, "maxTicks", 180)));
        JsonObject lastResult = null;
        for (int tick = 0; tick < maxTicks; tick++) {
            lastResult = submitOnGameTick(token, new Callable<JsonObject>() {
                @Override
                public JsonObject call() {
                    AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                    if (session == null) {
                        return AgentToolService.failure("Agent session is no longer valid.");
                    }
                    Player player = session.getPlayer();
                    if (player == null) {
                        return AgentToolService.failure("The claimed player is no longer online.");
                    }
                    if (player.getItemAssistant().freeSlots() < 1) {
                        return AgentToolService.observeState(player);
                    }
                    if (player.isMoving || player.isWoodcutting) {
                        return AgentToolService.observeState(player);
                    }
                    return AgentToolService.handle(player, "chop_tree", arguments);
                }
            });
            if (!isSuccess(lastResult)) {
                return addBatchStatus(lastResult, "blocked", tick + 1);
            }
            JsonObject player = playerObject(lastResult);
            if (player != null && getBoolean(player, "isDead", false)) {
                return addBatchStatus(lastResult, "player_dead", tick + 1);
            }
            if (player != null && getInt(player, "freeInventorySlots", 1) < 1) {
                return addBatchStatus(lastResult, "inventory_full", tick + 1);
            }
        }
        return addBatchStatus(lastResult == null ? AgentToolService.failure("No woodcutting action was attempted.") : lastResult,
                "max_ticks_reached", maxTicks);
    }

    private JsonObject waitUntilIdle(final String token, final JsonObject arguments) {
        int maxTicks = Math.max(1, Math.min(250, getInt(arguments, "maxTicks", 60)));
        final boolean includeMovement = getBoolean(arguments, "movement", getBoolean(arguments, "includeMovement", true));
        final boolean includeSkilling = getBoolean(arguments, "skilling", getBoolean(arguments, "includeSkilling", true));
        final boolean includeCombat = getBoolean(arguments, "combat", getBoolean(arguments, "includeCombat", false));
        JsonObject lastResult = null;
        for (int tick = 0; tick < maxTicks; tick++) {
            lastResult = submitOnGameTick(token, new Callable<JsonObject>() {
                @Override
                public JsonObject call() {
                    AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                    if (session == null) {
                        return AgentToolService.failure("Agent session is no longer valid.");
                    }
                    Player player = session.getPlayer();
                    if (player == null) {
                        return AgentToolService.failure("The claimed player is no longer online.");
                    }
                    JsonObject result = AgentToolService.observeState(player);
                    result.addProperty("complete", playerIsIdle(player, includeMovement, includeSkilling, includeCombat));
                    return result;
                }
            });
            if (!isSuccess(lastResult)) {
                return addBatchStatus(lastResult, "blocked", tick + 1);
            }
            if (getBoolean(lastResult, "complete", false)) {
                return addBatchStatus(lastResult, "idle", tick + 1);
            }
            JsonObject player = playerObject(lastResult);
            if (player != null && getBoolean(player, "isDead", false)) {
                return addBatchStatus(lastResult, "player_dead", tick + 1);
            }
        }
        return addBatchStatus(lastResult == null ? AgentToolService.failure("No idle wait was attempted.") : lastResult,
                "max_ticks_reached", maxTicks);
    }

    public JsonObject submitOnGameTick(String token, Callable<JsonObject> action) {
        return submitForTick(serverTick.get() + 1L, action);
    }

    JsonObject submitAfterGameTicks(int ticks, Callable<JsonObject> action) {
        int clampedTicks = Math.max(1, Math.min(25, ticks));
        return submitForTick(serverTick.get() + clampedTicks, action);
    }

    private JsonObject submitForTick(long targetTick, Callable<JsonObject> action) {
        return submitForTick(targetTick, action, ACTION_TIMEOUT_MS);
    }

    private JsonObject submitForTick(long targetTick, Callable<JsonObject> action, long timeoutMs) {
        QueuedAction queuedAction = new QueuedAction(targetTick, action);
        queuedActions.add(queuedAction);
        try {
            if (!queuedAction.await(timeoutMs)) {
                return AgentToolService.failure("Timed out waiting for the next game tick.");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return AgentToolService.failure("Interrupted while waiting for game tick.");
        }
        return queuedAction.getResult();
    }

    public void processPendingActions() {
        long tick = serverTick.incrementAndGet();
        int processed = 0;
        int queuedAtStart = queuedActions.size();
        QueuedAction queuedAction;
        for (int scanned = 0; scanned < queuedAtStart && processed < 100; scanned++) {
            queuedAction = queuedActions.poll();
            if (queuedAction == null) {
                break;
            }
            if (queuedAction.isReady(tick)) {
                queuedAction.execute(tick);
                processed++;
            } else {
                queuedActions.add(queuedAction);
            }
        }
        processCombatGoals();
    }

    private JsonObject startCombatGoal(AgentSession session, Player player, JsonObject arguments) {
        int targetLevel = clampGoalTargetLevel(getInt(arguments, "targetLevel",
                getInt(arguments, "level", DEFAULT_GOAL_TARGET_LEVEL)));
        int stepIntervalTicks = clampGoalStepInterval(getInt(arguments, "stepIntervalTicks",
                getInt(arguments, "ticksBetweenSteps", DEFAULT_GOAL_STEP_INTERVAL_TICKS)));
        int maxActions = clampGoalMaxActions(getInt(arguments, "maxActions", DEFAULT_GOAL_MAX_ACTIONS));
        boolean fixedArea = isGoalPreferenceLocked(arguments, "fixedArea", "lockArea");
        boolean fixedStyle = isGoalPreferenceLocked(arguments, "fixedStyle", "lockStyle");
        String area = fixedArea ? getString(arguments, "area", getString(arguments, "landmark", "")) : "";
        String npc = fixedArea ? getString(arguments, "npc", getString(arguments, "name", "")) : "";
        String style = fixedStyle ? getString(arguments, "style", getString(arguments, "trainingStyle", "")) : "";
        CombatGoal goal = new CombatGoal(session.getToken(), session.getSessionId(), player.playerId, player.playerName,
                targetLevel, stepIntervalTicks, maxActions, area, npc, style, fixedArea, fixedStyle);
        goal.updateLevels(player);
        goal.rememberLoggedLevels();
        combatGoals.put(Integer.valueOf(player.playerId), goal);
        JsonObject result = AgentToolService.success("Started combat goal toward base " + targetLevel + ".");
        result.add("goal", goal.toJson());
        result.add("state", AgentToolService.observeState(player));
        logGoalEvent(session, "goal_started", goal, null);
        return result;
    }

    private JsonObject observeGoal(Player player) {
        CombatGoal goal = combatGoals.get(Integer.valueOf(player.playerId));
        if (goal == null) {
            JsonObject result = AgentToolService.failure("No active goal is registered for this player.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        JsonObject result = AgentToolService.success(goal.statusMessage());
        result.add("goal", goal.toJson());
        result.add("state", AgentToolService.observeState(player));
        return result;
    }

    private JsonObject stopGoal(AgentSession session, Player player) {
        CombatGoal goal = combatGoals.get(Integer.valueOf(player.playerId));
        if (goal == null) {
            JsonObject result = AgentToolService.failure("No active goal is registered for this player.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        goal.block("Goal stopped by player request.");
        JsonObject result = AgentToolService.success("Stopped combat goal.");
        result.add("goal", goal.toJson());
        result.add("state", AgentToolService.observeState(player));
        logGoalEvent(session, "goal_stopped", goal, null);
        return result;
    }

    private void processCombatGoals() {
        for (CombatGoal goal : combatGoals.values()) {
            if (goal.isTerminal()) {
                continue;
            }
            AgentSession session = AgentSessionManager.INSTANCE.getSession(goal.token);
            Player player = session == null ? null : session.getPlayer();
            if (session == null || player == null) {
                goal.block("Agent session ended or player went offline.");
                continue;
            }
            if (player.isDead) {
                goal.block("Player death stopped the combat goal.");
                logGoalEvent(session, "goal_blocked", goal, null);
                continue;
            }
            goal.ticksElapsed++;
            if (goal.ticksElapsed - goal.lastStepTick < goal.stepIntervalTicks) {
                continue;
            }
            goal.lastStepTick = goal.ticksElapsed;
            if (player.isMoving) {
                continue;
            }
            if (goal.actionsRun >= goal.maxActions) {
                goal.block("Combat goal reached its max action limit before completion.");
                logGoalEvent(session, "goal_blocked", goal, null);
                continue;
            }

            JsonObject actionArguments = new JsonObject();
            actionArguments.addProperty("targetLevel", goal.targetLevel);
            goal.refreshPlannerDisplay(player);
            if (goal.fixedArea && !goal.area.isEmpty()) {
                actionArguments.addProperty("area", goal.area);
            }
            if (goal.fixedArea && !goal.npc.isEmpty()) {
                actionArguments.addProperty("npc", goal.npc);
            }
            if (goal.fixedStyle && !goal.style.isEmpty()) {
                actionArguments.addProperty("style", goal.style);
            }

            JsonObject result;
            result = runCombatGoalStep(player, goal, actionArguments);
            goal.actionsRun++;
            goal.lastResult = result;
            goal.updateLevels(player);
            goal.rememberPlanFromResult(result);

            if (goal.targetReached()) {
                goal.complete("Attack, strength, and defence reached base " + goal.targetLevel + ".");
                logGoalEvent(session, "goal_completed", goal, result);
            } else if (result == null || !result.has("success") || !result.get("success").getAsBoolean()) {
                String message = result == null ? "Combat goal step failed." : getString(result, "message", "Combat goal step failed.");
                if (isRecoverableGoalFailure(message)) {
                    if (goal.shouldLogProgress()) {
                        logGoalEvent(session, "goal_progress", goal, result);
                    }
                } else {
                    goal.block(message);
                    logGoalEvent(session, "goal_blocked", goal, result);
                }
            } else if (goal.shouldLogProgress()) {
                logGoalEvent(session, "goal_progress", goal, result);
            }
        }
    }

    private JsonObject runCombatGoalStep(Player player, CombatGoal goal, JsonObject actionArguments) {
        if (goal.checkGear) {
            goal.checkGear = false;
            JsonObject result = AgentToolService.handle(player, "equip_best_items", new JsonObject());
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                goal.gearItemsEquipped += getInt(result, "equipped", 0);
                String message = getString(result, "message", "Checked combat gear.");
                result.addProperty("message", "Equipping useful combat loot: " + message);
            }
            return result;
        }

        if (goal.bankingSupplies || shouldBankCombatSupplies(player) || shouldStoreAccountItems(player, goal)) {
            goal.bankingSupplies = true;
            return bankCombatSuppliesStep(player, goal);
        }

        if (goal.gearingUp || shouldAcquireCombatGear(player, goal)) {
            goal.gearingUp = true;
            return acquireCombatGearStep(player, goal);
        }

        if (goal.earningGearMoney || shouldEarnGearMoney(player, goal)) {
            goal.earningGearMoney = true;
            return earnGearMoneyStep(player, goal);
        }

        if (goal.restockingFood || shouldRestockFood(player, goal)) {
            goal.restockingFood = true;
            return restockFoodStep(player, goal);
        }

        if (player.getItemAssistant().freeSlots() > 0) {
            JsonObject pickup = AgentToolService.handle(player, "pickup_ground_item",
                    combatLootArgs(combatSupplyPickupDistance(isPlayerInCombat(player))));
            if (pickup != null && pickup.has("success") && pickup.get("success").getAsBoolean()) {
                goal.lootedSupplyItems += getInt(pickup, "pickedUp", 0);
                if (isCombatGearItem(getPickedUpItemId(pickup))) {
                    goal.checkGear = true;
                }
                return pickup;
            }
            String pickupMessage = pickup == null ? "" : getString(pickup, "message", "");
            if (pickupMessage.toLowerCase().contains("not enough inventory space")) {
                goal.bankingSupplies = true;
                return bankCombatSuppliesStep(player, goal);
            }
        }

        if (goal.actionsRun % 60 == 0) {
            return AgentToolService.handle(player, "equip_best_items", new JsonObject());
        }
        return AgentToolService.handle(player, "train_combat", actionArguments);
    }

    private JsonObject bankCombatSuppliesStep(Player player, CombatGoal goal) {
        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            JsonObject travelArgs = new JsonObject();
            travelArgs.addProperty("name", supplyBankLandmark(goal.area));
            JsonObject result = AgentToolService.handle(player, "travel_to_landmark", travelArgs);
            String message = getString(result, "message", "Walking toward bank.");
            result.addProperty("message", "Banking combat supplies: " + message);
            return result;
        }

        int supplyCount = countInventoryCombatSupplies(player);
        if (supplyCount > 0) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", combatSupplyArgs(0));
            int depositedAmount = getInt(result, "depositedAmount", 0);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                goal.bankingSupplies = shouldStoreAccountItems(player, goal);
                if (depositedAmount > 0) {
                    goal.bankTrips++;
                    goal.bankedSupplyItems += depositedAmount;
                }
                String message = getString(result, "message", "Deposited combat supplies.");
                result.addProperty("message", "Banked combat supplies for later account progression: " + message);
            }
            return result;
        }

        if (shouldStoreAccountItems(player, goal)) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", accountStorageArgs());
            int depositedAmount = getInt(result, "depositedAmount", 0);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                goal.bankingSupplies = false;
                if (depositedAmount > 0) {
                    goal.accountStorageBankTrips++;
                    goal.bankedAccountItems += depositedAmount;
                }
                goal.accountItemsStored = true;
                String message = getString(result, "message", "Deposited account supplies.");
                result.addProperty("message", "Banked starter account supplies for later: " + message);
            }
            return result;
        }

        goal.bankingSupplies = false;
        return AgentToolService.success("No bankable combat supplies are currently in inventory.");
    }

    private JsonObject acquireCombatGearStep(Player player, CombatGoal goal) {
        GearTarget target = goal.gearTargetItemId > 0 ? gearTargetByItemId(goal.gearTargetItemId)
                : nextGearTarget(player);
        goal.lastGearAttemptAction = goal.actionsRun;
        if (target == null) {
            goal.clearGearTarget();
            return AgentToolService.success("Combat gear is already appropriate for the current levels.");
        }
        goal.rememberGearTarget(target);

        if (isPlayerInCombat(player)) {
            if (goal.gearCombatCancelAttempts >= 2) {
                goal.clearGearTarget();
                return AgentToolService.success("Gearing up: combat did not fully clear after stopping; resuming training and deferring upgrades.");
            }
            goal.gearCombatCancelAttempts++;
            JsonObject result = AgentToolService.handle(player, "cancel_current_action", new JsonObject());
            result.addProperty("message", "Gearing up: stopped combat before visiting shops.");
            return result;
        }
        goal.gearCombatCancelAttempts = 0;

        if (AgentToolService.countInventoryItem(player, target.itemId) > 0) {
            JsonObject result = AgentToolService.handle(player, "equip_best_items", new JsonObject());
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                goal.gearItemsEquipped += getInt(result, "equipped", 0);
                goal.clearGearTarget();
                String message = getString(result, "message", "Equipped combat upgrades.");
                result.addProperty("message", "Gearing up: " + message);
            }
            return result;
        }

        if (AgentToolService.countBankItem(player, target.itemId) > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, "varrock east bank");
                result.addProperty("message", "Gearing up: returning to the bank for " + target.itemName() + ".");
                return result;
            }
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(target.itemId, 1));
            String message = getString(result, "message", "Withdrew banked gear.");
            result.addProperty("message", "Gearing up: withdrew " + target.itemName() + " from the bank: " + message);
            return result;
        }

        int inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        int bankCoins = AgentToolService.countBankItem(player, COINS);
        if (inventoryCoins < target.estimatedPrice && bankCoins > 0
                && inventoryCoins + bankCoins < target.estimatedPrice) {
            goal.beginGearMoney(target);
            return AgentToolService.success("Gearing up: saved " + (inventoryCoins + bankCoins)
                    + " spendable coins toward " + target.itemName() + ", estimated around "
                    + target.estimatedPrice + "; switching to normal Varrock mining money-making.");
        }
        if (inventoryCoins < target.estimatedPrice && bankCoins > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, "varrock east bank");
                result.addProperty("message", "Gearing up: returning to the bank for coins.");
                return result;
            }
            int amount = Math.min(Math.max(target.estimatedPrice * 2, 1), bankCoins);
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(COINS, amount));
            String message = getString(result, "message", "Withdrew coins.");
            result.addProperty("message", "Gearing up: withdrew coins for " + target.itemName() + ": " + message);
            return result;
        }

        inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        if (inventoryCoins <= 0) {
            goal.beginGearMoney(target);
            return AgentToolService.success("Gearing up: no spendable coins are available yet; switching to normal Varrock mining money-making.");
        }
        if (inventoryCoins < target.estimatedPrice) {
            goal.beginGearMoney(target);
            return AgentToolService.success("Gearing up: saved " + inventoryCoins + " coins, but " + target.itemName()
                    + " is estimated around " + target.estimatedPrice
                    + "; switching to normal Varrock mining money-making.");
        }

        JsonObject travel = travelTo(player, target.landmark);
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Gearing up: walking toward " + target.landmark + " for "
                    + target.itemName() + ".");
            return travel;
        }

        if (!currentShopNameContains(player, target.shopName)) {
            JsonObject result = openShop(player, target.shopName);
            String message = getString(result, "message", "Opened shop.");
            result.addProperty("message", "Gearing up: " + message);
            return result;
        }

        int beforeCoins = AgentToolService.countInventoryItem(player, COINS);
        JsonObject bought = AgentToolService.handle(player, "buy_shop_item", itemAmountArgs(target.itemId, 1));
        if (bought != null && bought.has("success") && bought.get("success").getAsBoolean()) {
            int boughtAmount = getInt(bought, "bought", 0);
            int coinsSpent = Math.max(0, beforeCoins - AgentToolService.countInventoryItem(player, COINS));
            goal.gearShopTrips++;
            goal.gearItemsBought += boughtAmount;
            goal.gearCoinsSpent += coinsSpent;
            String message = getString(bought, "message", "Bought combat gear.");
            bought.addProperty("message", "Gearing up: " + message + " Will equip it next.");
            return bought;
        }

        String failure = getString(bought, "message", "shop purchase failed");
        goal.clearGearTarget();
        return AgentToolService.success("Gearing up: could not buy " + target.itemName() + " yet (" + failure
                + "); resuming combat until more coins or supplies are available.");
    }

    private JsonObject earnGearMoneyStep(Player player, CombatGoal goal) {
        GearTarget target = goal.gearMoneyTargetItemId > 0 ? gearTargetByItemId(goal.gearMoneyTargetItemId)
                : nextDesiredGearTarget(player);
        if (target == null) {
            goal.clearGearMoney();
            return AgentToolService.success("Gear money-making is not needed; no unlocked gear upgrade is pending.");
        }
        goal.beginGearMoney(target);

        int spendableCoins = AgentToolService.countInventoryItem(player, COINS) + AgentToolService.countBankItem(player, COINS);
        GearTarget affordableUpgrade = nextGearTarget(player);
        if (shouldInterruptGearMoneyForAffordableUpgrade(affordableUpgrade, target)) {
            goal.clearGearMoney();
            goal.rememberGearTarget(affordableUpgrade);
            goal.gearingUp = true;
            if (player.isShopping || player.isBanking) {
                JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
                result.addProperty("message", "Saved enough coins for " + affordableUpgrade.itemName()
                        + "; closing interfaces before buying the upgrade.");
                return result;
            }
            return AgentToolService.success("Saved enough coins for " + affordableUpgrade.itemName()
                    + " while working toward " + target.itemName() + "; buying the intermediate upgrade first.");
        }
        if (spendableCoins >= target.estimatedPrice) {
            goal.clearGearMoney();
            goal.gearingUp = true;
            if (player.isShopping || player.isBanking) {
                JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
                result.addProperty("message", "Earned enough coins for " + target.itemName()
                        + "; closing interfaces before buying the upgrade.");
                return result;
            }
            return AgentToolService.success("Earned enough coins for " + target.itemName()
                    + "; resuming the gear upgrade step.");
        }

        if (isPlayerInCombat(player)) {
            JsonObject result = AgentToolService.handle(player, "cancel_current_action", new JsonObject());
            result.addProperty("message", "Earning gear money: stopped combat before mining.");
            return result;
        }
        if (player.isMining) {
            JsonObject result = AgentToolService.success("Earning gear money: continuing to mine ore.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        if (player.isSmelting || player.isSmithing || player.playerSkilling[Constants.SMITHING]) {
            JsonObject result = AgentToolService.success("Earning gear money: continuing smithing work.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }

        if (countInventoryGearMoneyProducts(player) > 0) {
            return sellGearMoneyItemsStep(player, goal, target);
        }

        if (Boundary.isIn(player, Boundary.BANK_AREA) && countInventoryGearMoneyClutterItems(player) > 0) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", gearMoneyClutterArgs(player));
            int depositedAmount = getInt(result, "depositedAmount", 0);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                if (depositedAmount > 0) {
                    goal.accountStorageBankTrips++;
                    goal.bankedAccountItems += depositedAmount;
                }
                String message = getString(result, "message", "Deposited non-mining items.");
                result.addProperty("message", "Earning gear money: banked non-mining items for a fuller ore run: " + message);
            }
            return result;
        }

        int inventoryMoneyItems = countInventoryGearMoneyItems(player);
        if (inventoryMoneyItems > 0
                && spendableCoins + estimatedInventoryGearMoneyCoins(player) >= target.estimatedPrice) {
            return sellGearMoneyItemsStep(player, goal, target);
        }

        int smithableBar = bestSmithableGearMoneyBar(player);
        if (smithableBar > 0 && shouldSmithGearMoneyBars(player, smithableBar)) {
            SmithingChoice smithingChoice = bestGearMoneySmithingChoice(player, smithableBar);
            JsonObject hammerPrep = prepareGearMoneyHammer(player, goal, target);
            if (hammerPrep != null) {
                return hammerPrep;
            }
            JsonObject travel = travelTo(player, "varrock west anvils");
            if (!getBoolean(travel, "complete", false)) {
                travel.addProperty("message", "Earning gear money: walking to Varrock anvils to smith saleable gear.");
                return travel;
            }
            JsonObject result = AgentToolService.handle(player, "smith_item", smithItemArgs(smithingChoice.getItemId()));
            result.addProperty("message", "Earning gear money for " + target.itemName() + ": "
                    + getString(result, "message", "smithing the best available item."));
            return result;
        }

        int smeltableBar = bestSmeltableGearMoneyBar(player);
        if (smeltableBar > 0 && shouldSmeltGearMoneyOres(player, smeltableBar)) {
            JsonObject travel = travelTo(player, "al kharid furnace");
            if (!getBoolean(travel, "complete", false)) {
                travel.addProperty("message", "Earning gear money: walking to Al Kharid furnace to smelt mined ores.");
                return travel;
            }
            JsonObject result = AgentToolService.handle(player, "smelt_bar", smeltArgs(smeltableBar,
                    smeltableGearMoneyBars(player, smeltableBar)));
            result.addProperty("message", "Earning gear money for " + target.itemName() + ": "
                    + getString(result, "message", "smelting mined ores."));
            return result;
        }

        if (inventoryMoneyItems > 0
                && (player.getItemAssistant().freeSlots() <= 0
                        || inventoryMoneyItems >= MIN_GEAR_MONEY_ITEMS_BEFORE_SELLING)) {
            return sellGearMoneyItemsStep(player, goal, target);
        }

        if (!hasPickaxeInInventory(player)) {
            int bankPickaxe = bestBankPickaxe(player);
            if (bankPickaxe > 0) {
                if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                    JsonObject result = travelTo(player, "varrock east bank");
                    result.addProperty("message", "Earning gear money: returning to the bank for a pickaxe.");
                    return result;
                }
                JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(bankPickaxe, 1));
                result.addProperty("message", "Earning gear money: withdrew a pickaxe for Varrock east mine.");
                return result;
            }
            return AgentToolService.failure("Earning gear money requires a pickaxe, but no banked or carried pickaxe is available.");
        }

        if (inventoryMoneyItems <= 0 && countBankGearMoneyItems(player) > 0
                && player.getItemAssistant().freeSlots() > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, "varrock east bank");
                result.addProperty("message", "Earning gear money: returning to bank for stored ores or bars to sell.");
                return result;
            }
            int itemId = bestBankGearMoneyItem(player);
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(itemId, Math.max(1, player.getItemAssistant().freeSlots())));
            result.addProperty("message", "Earning gear money: withdrew stored money-making items to sell.");
            return result;
        }

        if (player.isShopping || player.isBanking) {
            JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
            result.addProperty("message", "Earning gear money: closing interfaces before mining.");
            return result;
        }

        if (player.getItemAssistant().freeSlots() <= 0) {
            if (inventoryMoneyItems > 0) {
                return sellGearMoneyItemsStep(player, goal, target);
            }
            JsonObject result = travelTo(player, "varrock east bank");
            result.addProperty("message", "Earning gear money: inventory is full, returning to bank before mining.");
            return result;
        }

        int miningLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.MINING]);
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        String ore = gearMoneyOreForMiningLevel(miningLevel, smithingLevel,
                AgentToolService.countInventoryItem(player, COPPER_ORE) + AgentToolService.countBankItem(player, COPPER_ORE),
                AgentToolService.countInventoryItem(player, TIN_ORE) + AgentToolService.countBankItem(player, TIN_ORE));
        JsonObject result = AgentToolService.handle(player, "mine_ore", oreArgs(ore));
        result.addProperty("message", "Earning gear money for " + target.itemName() + ": "
                + getString(result, "message", "mining ore."));
        return result;
    }

    private static JsonObject prepareGearMoneyHammer(Player player, CombatGoal goal, GearTarget target) {
        if (AgentToolService.countInventoryItem(player, HAMMER) > 0) {
            return null;
        }
        if (player.getItemAssistant().freeSlots() <= 0) {
            return sellGearMoneyItemsStep(player, goal, target);
        }
        if (AgentToolService.countBankItem(player, HAMMER) > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, "varrock east bank");
                result.addProperty("message", "Earning gear money: returning to the bank for a smithing hammer.");
                return result;
            }
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(HAMMER, 1));
            result.addProperty("message", "Earning gear money: withdrew a hammer for smithing saleable gear.");
            return result;
        }

        int inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        int bankCoins = AgentToolService.countBankItem(player, COINS);
        if (inventoryCoins <= 0 && bankCoins > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, "varrock east bank");
                result.addProperty("message", "Earning gear money: returning to the bank for hammer money.");
                return result;
            }
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(COINS, Math.min(25, bankCoins)));
            result.addProperty("message", "Earning gear money: withdrew coins to buy a smithing hammer.");
            return result;
        }
        if (inventoryCoins <= 0 && (countInventoryGearMoneyItems(player) > 0
                || countInventoryGearMoneyProducts(player) > 0)) {
            return sellGearMoneyItemsStep(player, goal, target);
        }
        if (inventoryCoins <= 0) {
            return null;
        }

        JsonObject travel = travelTo(player, "varrock general store");
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Earning gear money: walking to Varrock general store to buy a hammer.");
            return travel;
        }
        if (!currentShopNameContains(player, "general")) {
            JsonObject result = openShop(player, "general");
            result.addProperty("message", "Earning gear money: opening the general store to buy a hammer.");
            return result;
        }
        JsonObject result = AgentToolService.handle(player, "buy_shop_item", itemAmountArgs(HAMMER, 1));
        result.addProperty("message", "Earning gear money: bought a hammer so mined bars can become higher-value gear.");
        return result;
    }

    private static JsonObject sellGearMoneyItemsStep(Player player, CombatGoal goal, GearTarget target) {
        JsonObject travel = travelTo(player, "varrock general store");
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Earning gear money: walking to Varrock general store to sell mined or smithed items.");
            return travel;
        }

        if (!currentShopNameContains(player, "general")) {
            JsonObject result = openShop(player, "general");
            result.addProperty("message", "Earning gear money: " + getString(result, "message", "opened general store."));
            return result;
        }

        JsonObject result = AgentToolService.handle(player, "sell_inventory_items", gearMoneySellArgs());
        if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
            int sold = getInt(result, "sold", 0);
            int coins = getInt(result, "coinsReceived", 0);
            goal.gearMoneyTrips++;
            goal.gearMoneyItemsSold += sold;
            goal.gearMoneyCoinsEarned += coins;
            result.addProperty("message", "Earning gear money for " + target.itemName() + ": sold " + sold
                    + " mined/smithed item(s) for " + coins + " coins.");
        }
        return result;
    }

    private JsonObject restockFoodStep(Player player, CombatGoal goal) {
        if (isPlayerInCombat(player)) {
            JsonObject result = AgentToolService.handle(player, "cancel_current_action", new JsonObject());
            result.addProperty("message", "Restocking food: stopped combat before leaving the training area.");
            return result;
        }
        if (player.playerSkilling[Constants.FISHING]) {
            JsonObject result = AgentToolService.success("Restocking food: continuing to fish.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        if (player.isWoodcutting) {
            JsonObject result = AgentToolService.success("Restocking food: continuing to chop logs for cooking.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        if (player.isFiremaking) {
            JsonObject result = AgentToolService.success("Restocking food: continuing to light a cooking fire.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        if (player.playerIsCooking) {
            JsonObject result = AgentToolService.success("Restocking food: continuing to cook.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }

        int desiredFood = desiredCombatFood(player);
        int inventoryFood = AgentToolService.countInventoryFood(player);
        int inventoryRawFood = AgentToolService.countInventoryRawCookableFood(player);
        if (inventoryFood >= desiredFood) {
            goal.restockingFood = false;
            JsonObject result = AgentToolService.success("Restocked food for combat training.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        if (inventoryFood >= minimumReturnFood(desiredFood)
                && AgentToolService.countInventoryRawCookableFood(player) <= 0
                && AgentToolService.countBankFood(player) <= 0) {
            goal.restockingFood = false;
            JsonObject result = AgentToolService.success("Restocked enough cooked food to resume combat training.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }

        if (shouldVisitBankForFood(player, inventoryRawFood)) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject travelArgs = new JsonObject();
                travelArgs.addProperty("name", "varrock east bank");
                JsonObject result = AgentToolService.handle(player, "travel_to_landmark", travelArgs);
                result.addProperty("message", "Restocking food: walking toward varrock east bank.");
                return result;
            }
            JsonObject bankResult = prepareFoodFromBank(player, goal, desiredFood);
            if (bankResult != null) {
                return bankResult;
            }
        }

        inventoryRawFood = AgentToolService.countInventoryRawCookableFood(player);
        if (inventoryRawFood >= MIN_RAW_FOOD_BEFORE_COOKING
                || (inventoryRawFood > 0 && player.getItemAssistant().freeSlots() <= MIN_FREE_SLOTS_BEFORE_BANKING)) {
            JsonObject firePrep = prepareOutdoorCookingFire(player);
            if (firePrep != null) {
                return firePrep;
            }
            JsonObject result = AgentToolService.handle(player, "cook_food", cookFoodArgs(inventoryRawFood, true));
            result.addProperty("message", "Restocking food: " + getString(result, "message", "cooking food."));
            return result;
        }

        if (!hasFoodToolInInventory(player)) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject travelArgs = new JsonObject();
                travelArgs.addProperty("name", "varrock east bank");
                JsonObject result = AgentToolService.handle(player, "travel_to_landmark", travelArgs);
                result.addProperty("message", "Restocking food: returning to bank for fishing tools.");
                return result;
            }
            JsonObject bankResult = prepareFoodFromBank(player, goal, desiredFood);
            return bankResult == null ? AgentToolService.failure("No fishing tool or cookable food is available for restocking.") : bankResult;
        }

        if (player.getItemAssistant().freeSlots() <= MIN_FREE_SLOTS_BEFORE_BANKING && inventoryRawFood > 0) {
            JsonObject firePrep = prepareOutdoorCookingFire(player);
            if (firePrep != null) {
                return firePrep;
            }
            JsonObject result = AgentToolService.handle(player, "cook_food", cookFoodArgs(inventoryRawFood, true));
            result.addProperty("message", "Restocking food: " + getString(result, "message", "cooking food."));
            return result;
        }

        JsonObject result = AgentToolService.handle(player, "fish_food", new JsonObject());
        result.addProperty("message", "Restocking food: " + getString(result, "message", "fishing food."));
        return result;
    }

    private JsonObject prepareFoodFromBank(Player player, CombatGoal goal, int desiredFood) {
        int supplyCount = countInventoryCombatSupplies(player);
        if (supplyCount > 0) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", combatSupplyArgs(0));
            int depositedAmount = getInt(result, "depositedAmount", 0);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                if (depositedAmount > 0) {
                    goal.bankTrips++;
                    goal.bankedSupplyItems += depositedAmount;
                }
                String message = getString(result, "message", "Deposited combat supplies.");
                result.addProperty("message", "Restocking food: banked combat supplies for later account progression: " + message);
            }
            return result;
        }

        if (shouldStoreAccountItems(player, goal)) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", accountStorageArgs());
            int depositedAmount = getInt(result, "depositedAmount", 0);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                if (depositedAmount > 0) {
                    goal.accountStorageBankTrips++;
                    goal.bankedAccountItems += depositedAmount;
                }
                goal.accountItemsStored = true;
                String message = getString(result, "message", "Deposited account supplies.");
                result.addProperty("message", "Restocking food: banked starter account supplies for later: " + message);
            }
            return result;
        }

        int inventoryFood = AgentToolService.countInventoryFood(player);
        if (inventoryFood >= desiredFood) {
            goal.restockingFood = false;
            JsonObject result = AgentToolService.success("Restocked food for combat training.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }

        int availableRawFood = AgentToolService.countInventoryRawCookableFood(player)
                + AgentToolService.countBankRawCookableFood(player);
        if (availableRawFood > 0) {
            JsonObject fireSupplyResult = prepareFireSuppliesFromBank(player);
            if (fireSupplyResult != null) {
                return fireSupplyResult;
            }
        }

        int bankFood = AgentToolService.bestBankFood(player);
        if (bankFood >= 0 && player.getItemAssistant().freeSlots() > 0) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(bankFood, Math.max(1, desiredFood - inventoryFood)));
            int withdrawnAmount = getInt(result, "withdrawnAmount", 0);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                goal.foodBankTrips++;
                goal.withdrawnFoodItems += withdrawnAmount;
                String message = getString(result, "message", "Withdrew food.");
                result.addProperty("message", "Restocking food: withdrew combat food from bank: " + message);
            }
            return result;
        }

        if (AgentToolService.countInventoryRawCookableFood(player) <= 0) {
            int bankRawFood = AgentToolService.bestBankRawCookableFood(player);
            if (bankRawFood >= 0 && player.getItemAssistant().freeSlots() > 0) {
                JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                        itemAmountArgs(bankRawFood, Math.max(1, player.getItemAssistant().freeSlots())));
                String message = getString(result, "message", "Withdrew raw food.");
                result.addProperty("message", "Restocking food: withdrew raw food to cook: " + message);
                return result;
            }
        }

        if (!hasFoodToolInInventory(player) && hasFoodToolInBank(player) && player.getItemAssistant().freeSlots() > 0) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(SMALL_FISHING_NET, 1));
            String message = getString(result, "message", "Withdrew fishing tool.");
            result.addProperty("message", "Restocking food: withdrew fishing tool: " + message);
            return result;
        }

        return null;
    }

    private static JsonObject combatSupplyArgs(int maxDistance) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        addItemIds(itemIds, COMBAT_SUPPLY_ITEM_IDS);
        addItemIds(itemIds, COMBAT_GEAR_ITEM_IDS);
        arguments.add("itemIds", itemIds);
        if (maxDistance > 0) {
            arguments.addProperty("maxDistance", maxDistance);
        }
        return arguments;
    }

    private static JsonObject combatLootArgs(int maxDistance) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        addItemIds(itemIds, COMBAT_SUPPLY_ITEM_IDS);
        addItemIds(itemIds, COMBAT_GEAR_ITEM_IDS);
        arguments.add("itemIds", itemIds);
        if (maxDistance > 0) {
            arguments.addProperty("maxDistance", maxDistance);
        }
        return arguments;
    }

    private static void addItemIds(JsonArray itemIds, int[] ids) {
        for (int itemId : ids) {
            itemIds.add(itemId);
        }
    }

    private static JsonObject itemAmountArgs(int itemId, int amount) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("itemId", itemId);
        arguments.addProperty("amount", amount);
        return arguments;
    }

    private static JsonObject oreArgs(String ore) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("ore", ore);
        return arguments;
    }

    private static JsonObject smeltArgs(int barItemId, int amount) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("itemId", barItemId);
        arguments.addProperty("amount", Math.max(1, amount));
        return arguments;
    }

    private static JsonObject smithItemArgs(int itemId) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("itemId", itemId);
        arguments.addProperty("amount", Integer.MAX_VALUE);
        return arguments;
    }

    private static JsonObject gearMoneySellArgs() {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        addItemIds(itemIds, GEAR_MONEY_ITEM_IDS);
        addSmithingProductItemIds(itemIds);
        arguments.add("itemIds", itemIds);
        arguments.addProperty("amount", Integer.MAX_VALUE);
        return arguments;
    }

    private static void addSmithingProductItemIds(JsonArray itemIds) {
        for (SmithingData data : SmithingData.values()) {
            if (isGearMoneyProductItem(data.getId())) {
                itemIds.add(data.getId());
            }
        }
    }

    private static JsonObject gearMoneyClutterArgs(Player player) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (isGearMoneyClutterItemForBanking(itemId)) {
                itemIds.add(itemId);
            }
        }
        arguments.add("itemIds", itemIds);
        return arguments;
    }

    private JsonObject prepareOutdoorCookingFire(Player player) {
        if (AgentToolService.hasCookingFireNearby(player, 4)) {
            return null;
        }
        boolean hasTinderbox = AgentToolService.countInventoryItem(player, TINDERBOX) > 0;
        boolean hasLogs = AgentToolService.countInventoryItem(player, LOGS) > 0;
        if (hasTinderbox && hasLogs) {
            if (!AgentToolService.canLightFireHere(player)) {
                JsonObject travelArgs = new JsonObject();
                travelArgs.addProperty("name", "lumbridge trees");
                JsonObject result = AgentToolService.handle(player, "travel_to_landmark", travelArgs);
                result.addProperty("message", "Restocking food: moving outside to light a cooking fire.");
                return result;
            }
            JsonObject result = AgentToolService.handle(player, "light_fire", new JsonObject());
            result.addProperty("message", "Restocking food: " + getString(result, "message", "lighting a cooking fire."));
            return result;
        }
        if (!hasTinderbox || (!hasLogs && !AgentToolService.hasWoodcuttingAxe(player))) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject travelArgs = new JsonObject();
                travelArgs.addProperty("name", "varrock east bank");
                JsonObject result = AgentToolService.handle(player, "travel_to_landmark", travelArgs);
                result.addProperty("message", "Restocking food: returning to bank for firemaking supplies.");
                return result;
            }
            JsonObject bankResult = prepareFireSuppliesFromBank(player);
            return bankResult == null ? AgentToolService.failure("No firemaking supplies are available for cooking raw food.")
                    : bankResult;
        }
        if (player.getItemAssistant().freeSlots() <= 0) {
            return AgentToolService.failure("Inventory is full; cannot chop logs for cooking.");
        }
        JsonObject chopArgs = new JsonObject();
        chopArgs.addProperty("tree", "tree");
        JsonObject result = AgentToolService.handle(player, "chop_tree", chopArgs);
        result.addProperty("message", "Restocking food: " + getString(result, "message", "gathering logs for a cooking fire."));
        return result;
    }

    private static JsonObject prepareFireSuppliesFromBank(Player player) {
        if (AgentToolService.countInventoryItem(player, TINDERBOX) <= 0
                && AgentToolService.countBankItem(player, TINDERBOX) > 0
                && player.getItemAssistant().freeSlots() > 0) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(TINDERBOX, 1));
            result.addProperty("message", "Restocking food: withdrew tinderbox for cooking fires: "
                    + getString(result, "message", "Withdrew tinderbox."));
            return result;
        }
        if (AgentToolService.countInventoryItem(player, LOGS) <= 0
                && AgentToolService.countBankItem(player, LOGS) > 0
                && player.getItemAssistant().freeSlots() > 0) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(LOGS, 1));
            result.addProperty("message", "Restocking food: withdrew logs for cooking fire: "
                    + getString(result, "message", "Withdrew logs."));
            return result;
        }
        if (AgentToolService.countInventoryItem(player, LOGS) <= 0
                && !AgentToolService.hasWoodcuttingAxe(player)
                && AgentToolService.countBankItem(player, BRONZE_AXE) > 0
                && player.getItemAssistant().freeSlots() > 0) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(BRONZE_AXE, 1));
            result.addProperty("message", "Restocking food: withdrew axe for cooking-fire logs: "
                    + getString(result, "message", "Withdrew axe."));
            return result;
        }
        return null;
    }

    private static JsonObject cookFoodArgs(int amount, boolean fireOnly) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("amount", amount);
        if (fireOnly) {
            arguments.addProperty("fireOnly", true);
            arguments.addProperty("maxDistance", 4);
        }
        return arguments;
    }

    private static JsonObject travelTo(Player player, String landmark) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("name", landmark);
        return AgentToolService.handle(player, "travel_to_landmark", arguments);
    }

    private static JsonObject openShop(Player player, String name) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("name", name);
        arguments.addProperty("maxDistance", 12);
        return AgentToolService.handle(player, "open_nearest_shop", arguments);
    }

    private static boolean shouldAcquireCombatGear(Player player, CombatGoal goal) {
        if (goal == null || player == null) {
            return false;
        }
        if (goal.actionsRun - goal.lastGearAttemptAction < GEAR_CHECK_INTERVAL_ACTIONS) {
            return false;
        }
        if (isPlayerInCombat(player)) {
            return false;
        }
        GearTarget target = nextGearTarget(player);
        if (target == null) {
            return false;
        }
        return true;
    }

    private static boolean shouldEarnGearMoney(Player player, CombatGoal goal) {
        if (goal == null || player == null) {
            return false;
        }
        if (goal.actionsRun - goal.lastGearAttemptAction < GEAR_CHECK_INTERVAL_ACTIONS) {
            return false;
        }
        if (isPlayerInCombat(player)) {
            return false;
        }
        GearTarget target = nextDesiredGearTarget(player);
        if (target == null) {
            return false;
        }
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        return spendableCoins < target.estimatedPrice;
    }

    private static GearTarget nextGearTarget(Player player) {
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int defenceLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.DEFENCE]);
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        GearTarget weapon = bestActionableGearTarget(player, WEAPON_GEAR_TARGETS, attackLevel, spendableCoins);
        if (weapon != null) {
            return weapon;
        }
        if (shouldSaveForWeaponBeforeArmor(attackLevel, spendableCoins,
                bestEquippedGearTier(player, WEAPON_GEAR_TARGETS))) {
            return null;
        }
        GearTarget body = bestActionableGearTarget(player, BODY_GEAR_TARGETS, defenceLevel, spendableCoins);
        if (body != null) {
            return body;
        }
        GearTarget legs = bestActionableGearTarget(player, LEGS_GEAR_TARGETS, defenceLevel, spendableCoins);
        if (legs != null) {
            return legs;
        }
        return null;
    }

    private static GearTarget nextDesiredGearTarget(Player player) {
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int defenceLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.DEFENCE]);
        GearTarget weapon = bestDesiredGearTarget(player, WEAPON_GEAR_TARGETS, attackLevel);
        if (weapon != null) {
            return weapon;
        }
        GearTarget body = bestDesiredGearTarget(player, BODY_GEAR_TARGETS, defenceLevel);
        if (body != null) {
            return body;
        }
        GearTarget legs = bestDesiredGearTarget(player, LEGS_GEAR_TARGETS, defenceLevel);
        if (legs != null) {
            return legs;
        }
        return null;
    }

    static boolean shouldInterruptGearMoneyForAffordableUpgrade(int affordableItemId, int desiredItemId) {
        return shouldInterruptGearMoneyForAffordableUpgrade(gearTargetByItemId(affordableItemId),
                gearTargetByItemId(desiredItemId));
    }

    private static boolean shouldInterruptGearMoneyForAffordableUpgrade(GearTarget affordable, GearTarget desired) {
        return affordable != null
                && desired != null
                && affordable.itemId != desired.itemId
                && sameGearFamily(affordable, desired);
    }

    private static boolean sameGearFamily(GearTarget first, GearTarget second) {
        return containsGearTarget(WEAPON_GEAR_TARGETS, first) && containsGearTarget(WEAPON_GEAR_TARGETS, second)
                || containsGearTarget(BODY_GEAR_TARGETS, first) && containsGearTarget(BODY_GEAR_TARGETS, second)
                || containsGearTarget(LEGS_GEAR_TARGETS, first) && containsGearTarget(LEGS_GEAR_TARGETS, second);
    }

    private static boolean containsGearTarget(GearTarget[] targets, GearTarget candidate) {
        if (candidate == null) {
            return false;
        }
        for (GearTarget target : targets) {
            if (target.itemId == candidate.itemId) {
                return true;
            }
        }
        return false;
    }

    private static GearTarget bestActionableGearTarget(Player player, GearTarget[] targets, int level,
            int spendableCoins) {
        int bestEquippedTier = bestEquippedGearTier(player, targets);
        GearTarget best = null;
        for (GearTarget target : targets) {
            if (level < target.minLevel || target.tier <= bestEquippedTier) {
                continue;
            }
            if (AgentToolService.countInventoryItem(player, target.itemId) > 0
                    || AgentToolService.countBankItem(player, target.itemId) > 0
                    || spendableCoins >= target.estimatedPrice) {
                best = target;
            }
        }
        return best;
    }

    private static GearTarget bestDesiredGearTarget(Player player, GearTarget[] targets, int level) {
        int bestEquippedTier = bestEquippedGearTier(player, targets);
        GearTarget best = null;
        for (GearTarget target : targets) {
            if (level >= target.minLevel && target.tier > bestEquippedTier) {
                best = target;
            }
        }
        return best;
    }

    static int recommendedWeaponUpgradeId(int attackLevel, int bestOwnedTier) {
        GearTarget target = recommendedGearTarget(WEAPON_GEAR_TARGETS, attackLevel);
        return target != null && target.tier > bestOwnedTier ? target.itemId : -1;
    }

    static boolean shouldSaveForWeaponBeforeArmor(int attackLevel, int spendableCoins, int bestWeaponTier) {
        GearTarget target = recommendedGearTarget(WEAPON_GEAR_TARGETS, attackLevel);
        return target != null && target.tier > bestWeaponTier && spendableCoins < target.estimatedPrice;
    }

    private static GearTarget recommendedGearTarget(GearTarget[] targets, int level) {
        GearTarget best = null;
        for (GearTarget target : targets) {
            if (level >= target.minLevel) {
                best = target;
            }
        }
        return best;
    }

    private static int bestOwnedGearTier(Player player, GearTarget[] targets) {
        int best = 0;
        for (GearTarget target : targets) {
            if (hasGearItem(player, target.itemId)) {
                best = Math.max(best, target.tier);
            }
        }
        return best;
    }

    private static int bestEquippedGearTier(Player player, GearTarget[] targets) {
        int best = 0;
        for (GearTarget target : targets) {
            if (isGearItemEquipped(player, target.itemId)) {
                best = Math.max(best, target.tier);
            }
        }
        return best;
    }

    private static boolean isGearItemEquipped(Player player, int itemId) {
        for (int equipped : player.playerEquipment) {
            if (equipped == itemId) {
                return true;
            }
        }
        return false;
    }

    private static boolean hasGearItem(Player player, int itemId) {
        if (AgentToolService.countInventoryItem(player, itemId) > 0 || AgentToolService.countBankItem(player, itemId) > 0) {
            return true;
        }
        for (int equipped : player.playerEquipment) {
            if (equipped == itemId) {
                return true;
            }
        }
        return false;
    }

    private static GearTarget gearTargetByItemId(int itemId) {
        GearTarget target = gearTargetByItemId(WEAPON_GEAR_TARGETS, itemId);
        if (target != null) {
            return target;
        }
        target = gearTargetByItemId(BODY_GEAR_TARGETS, itemId);
        if (target != null) {
            return target;
        }
        return gearTargetByItemId(LEGS_GEAR_TARGETS, itemId);
    }

    static int gearTargetEstimatedPrice(int itemId) {
        GearTarget target = gearTargetByItemId(itemId);
        return target == null ? -1 : target.estimatedPrice;
    }

    private static GearTarget gearTargetByItemId(GearTarget[] targets, int itemId) {
        for (GearTarget target : targets) {
            if (target.itemId == itemId) {
                return target;
            }
        }
        return null;
    }

    private static boolean currentShopNameContains(Player player, String name) {
        if (!player.isShopping || player.shopId < 0 || player.shopId >= ShopHandler.shopName.length) {
            return false;
        }
        String shopName = ShopHandler.shopName[player.shopId];
        if (shopName == null) {
            return false;
        }
        return shopName.toLowerCase().contains(name.toLowerCase());
    }

    private static JsonObject accountStorageArgs() {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        for (int itemId : ACCOUNT_STORAGE_ITEM_IDS) {
            itemIds.add(itemId);
        }
        arguments.add("itemIds", itemIds);
        return arguments;
    }

    private static boolean shouldBankCombatSupplies(Player player) {
        int supplyCount = countInventoryCombatSupplies(player);
        return supplyCount > 0
                && (player.getItemAssistant().freeSlots() <= MIN_FREE_SLOTS_BEFORE_BANKING
                        || supplyCount >= SUPPLY_COUNT_BEFORE_BANKING);
    }

    private static boolean shouldStoreAccountItems(Player player, CombatGoal goal) {
        return goal != null
                && !goal.accountItemsStored
                && countInventoryAccountStorageItems(player) >= ACCOUNT_STORAGE_COUNT_BEFORE_BANKING;
    }

    private static boolean shouldRestockFood(Player player, CombatGoal goal) {
        if (goal == null) {
            return false;
        }
        int inventoryFood = AgentToolService.countInventoryFood(player);
        int retreatAt = AgentCombatPlanner.retreatAtHitpoints(player.getPlayerAssistant().getLevelForXP(
                player.playerXP[Constants.HITPOINTS]));
        if (player.playerLevel[Constants.HITPOINTS] <= retreatAt + 2 && inventoryFood <= 0) {
            return true;
        }
        return inventoryFood <= MIN_FOOD_BEFORE_RESTOCK && hasFoodRestockSource(player);
    }

    private static boolean shouldVisitBankForFood(Player player, int inventoryRawFood) {
        if (countInventoryCombatSupplies(player) > 0 && player.getItemAssistant().freeSlots() <= MIN_FREE_SLOTS_BEFORE_BANKING) {
            return true;
        }
        if (AgentToolService.countBankFood(player) > 0 || AgentToolService.countBankRawCookableFood(player) > 0) {
            return true;
        }
        return !hasFoodToolInInventory(player) && hasFoodToolInBank(player) && inventoryRawFood <= 0;
    }

    private static boolean hasFoodRestockSource(Player player) {
        return AgentToolService.countBankFood(player) > 0
                || AgentToolService.countBankRawCookableFood(player) > 0
                || AgentToolService.countInventoryRawCookableFood(player) > 0
                || hasFoodToolInInventory(player)
                || hasFoodToolInBank(player);
    }

    private static int desiredCombatFood(Player player) {
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int strengthLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.STRENGTH]);
        int defenceLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.DEFENCE]);
        int meleeAverage = (attackLevel + strengthLevel + defenceLevel) / 3;
        return meleeAverage >= 20 ? DESIRED_HIGH_LEVEL_FOOD : DESIRED_LOW_LEVEL_FOOD;
    }

    static int minimumReturnFood(int desiredFood) {
        return Math.max(MIN_FOOD_BEFORE_RESTOCK + 2, desiredFood / 2);
    }

    private static boolean hasFoodToolInInventory(Player player) {
        for (int toolId : FOOD_TOOL_ITEM_IDS) {
            if (AgentToolService.countInventoryItem(player, toolId) > 0) {
                return true;
            }
        }
        return false;
    }

    private static boolean hasFoodToolInBank(Player player) {
        for (int toolId : FOOD_TOOL_ITEM_IDS) {
            if (AgentToolService.countBankItem(player, toolId) > 0) {
                return true;
            }
        }
        return false;
    }

    private static int countInventoryCombatSupplies(Player player) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            if (isCombatSupplyItemForBanking(storedId - 1)) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    static boolean isCombatSupplyItemForBanking(int itemId) {
        for (int supplyId : BANK_TRIGGER_COMBAT_SUPPLY_ITEM_IDS) {
            if (itemId == supplyId) {
                return true;
            }
        }
        return isCombatGearItem(itemId);
    }

    private static boolean isCombatGearItem(int itemId) {
        for (int gearId : COMBAT_GEAR_ITEM_IDS) {
            if (itemId == gearId) {
                return true;
            }
        }
        return false;
    }

    static boolean isGearMoneyItem(int itemId) {
        for (int moneyItemId : GEAR_MONEY_ITEM_IDS) {
            if (itemId == moneyItemId) {
                return true;
            }
        }
        return false;
    }

    static boolean isGearMoneyProductItem(int itemId) {
        return AgentSmithingPlanner.isSmithingProduct(itemId)
                && !isAccountStorageItemForBanking(itemId)
                && !isCombatGearItem(itemId);
    }

    static boolean isGearMoneyClutterItemForBanking(int itemId) {
        return itemId > 0
                && !isGearMoneyItem(itemId)
                && !isGearMoneyProductItem(itemId)
                && !isPickaxeItem(itemId)
                && itemId != HAMMER;
    }

    private static int countInventoryGearMoneyItems(Player player) {
        int count = 0;
        for (int moneyItemId : GEAR_MONEY_ITEM_IDS) {
            count += AgentToolService.countInventoryItem(player, moneyItemId);
        }
        return count;
    }

    private static int countInventoryGearMoneyProducts(Player player) {
        int count = 0;
        for (SmithingData data : SmithingData.values()) {
            count += AgentToolService.countInventoryItem(player, data.getId());
        }
        return count;
    }

    static int estimatedGearMoneySellCoins(int itemId) {
        if (itemId == COPPER_ORE || itemId == TIN_ORE) {
            return 2;
        }
        if (itemId == COAL) {
            return 15;
        }
        if (itemId == IRON_ORE) {
            return 3;
        }
        if (itemId == BRONZE_BAR) {
            return 5;
        }
        if (itemId == IRON_BAR) {
            return 11;
        }
        if (itemId == STEEL_BAR) {
            return 45;
        }
        if (itemId == MITHRIL_BAR) {
            return 140;
        }
        if (itemId == ADAMANT_BAR) {
            return 325;
        }
        if (itemId == RUNE_BAR) {
            return 3200;
        }
        if (isGearMoneyProductItem(itemId)) {
            return Math.max(1, smithingProductBars(itemId) * estimatedGearMoneySellCoins(
                    AgentSmithingPlanner.requiredBarForItem(itemId)));
        }
        return 0;
    }

    private static int estimatedInventoryGearMoneyCoins(Player player) {
        int coins = 0;
        for (int moneyItemId : GEAR_MONEY_ITEM_IDS) {
            coins += AgentToolService.countInventoryItem(player, moneyItemId)
                    * estimatedGearMoneySellCoins(moneyItemId);
        }
        for (SmithingData data : SmithingData.values()) {
            coins += AgentToolService.countInventoryItem(player, data.getId())
                    * estimatedGearMoneySellCoins(data.getId());
        }
        return coins;
    }

    private static int countBankGearMoneyItems(Player player) {
        int count = 0;
        for (int moneyItemId : GEAR_MONEY_ITEM_IDS) {
            count += AgentToolService.countBankItem(player, moneyItemId);
        }
        return count;
    }

    private static int countInventoryGearMoneyClutterItems(Player player) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (isGearMoneyClutterItemForBanking(itemId)) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    private static int bestBankGearMoneyItem(Player player) {
        for (int i = GEAR_MONEY_ITEM_IDS.length - 1; i >= 0; i--) {
            int itemId = GEAR_MONEY_ITEM_IDS[i];
            if (AgentToolService.countBankItem(player, itemId) > 0) {
                return itemId;
            }
        }
        return -1;
    }

    private static int bestSmithableGearMoneyBar(Player player) {
        int[] barIds = {RUNE_BAR, ADAMANT_BAR, MITHRIL_BAR, STEEL_BAR, IRON_BAR, BRONZE_BAR};
        for (int barId : barIds) {
            int availableBars = AgentToolService.countInventoryItem(player, barId);
            if (availableBars <= 0) {
                continue;
            }
            SmithingChoice choice = bestGearMoneySmithingChoice(player, barId);
            if (choice != null) {
                return barId;
            }
        }
        return -1;
    }

    private static boolean shouldSmithGearMoneyBars(Player player, int barItemId) {
        int bars = AgentToolService.countInventoryItem(player, barItemId);
        if (bars <= 0) {
            return false;
        }
        SmithingChoice choice = bestGearMoneySmithingChoice(player, barItemId);
        if (choice == null) {
            return false;
        }
        return player.getItemAssistant().freeSlots() <= MIN_FREE_SLOTS_BEFORE_BANKING
                || bars >= MIN_BARS_BEFORE_SMITHING
                || bars >= choice.getBarsNeeded();
    }

    private static SmithingChoice bestGearMoneySmithingChoice(Player player, int barItemId) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        int availableBars = AgentToolService.countInventoryItem(player, barItemId);
        SmithingChoice best = null;
        for (SmithingChoice choice : AgentSmithingPlanner.smithableItems(smithingLevel, barItemId, availableBars, "")) {
            if (!isGearMoneyProductItem(choice.getItemId())) {
                continue;
            }
            if (best == null || isBetterGearMoneySmithingChoice(choice, best)) {
                best = choice;
            }
        }
        return best;
    }

    private static boolean isBetterGearMoneySmithingChoice(SmithingChoice candidate, SmithingChoice current) {
        int candidatePrimary = candidate.getXp();
        int currentPrimary = current.getXp();
        if (candidatePrimary != currentPrimary) {
            return candidatePrimary > currentPrimary;
        }
        if (candidate.getRequiredLevel() != current.getRequiredLevel()) {
            return candidate.getRequiredLevel() > current.getRequiredLevel();
        }
        if (candidate.getBarsNeeded() != current.getBarsNeeded()) {
            return candidate.getBarsNeeded() > current.getBarsNeeded();
        }
        return candidate.getItemId() > current.getItemId();
    }

    private static int bestSmeltableGearMoneyBar(Player player) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        if (smithingLevel >= 20 && smeltableGearMoneyBars(player, STEEL_BAR) > 0) {
            return STEEL_BAR;
        }
        if (smithingLevel >= 15 && smeltableGearMoneyBars(player, IRON_BAR) > 0) {
            return IRON_BAR;
        }
        if (smeltableGearMoneyBars(player, BRONZE_BAR) > 0) {
            return BRONZE_BAR;
        }
        return -1;
    }

    private static int smeltableGearMoneyBars(Player player, int barItemId) {
        if (barItemId == BRONZE_BAR) {
            return Math.min(AgentToolService.countInventoryItem(player, COPPER_ORE),
                    AgentToolService.countInventoryItem(player, TIN_ORE));
        }
        if (barItemId == IRON_BAR) {
            int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
            return smithingLevel >= 15 ? AgentToolService.countInventoryItem(player, IRON_ORE) : 0;
        }
        if (barItemId == STEEL_BAR) {
            int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
            return smithingLevel >= 20 ? Math.min(AgentToolService.countInventoryItem(player, IRON_ORE),
                    AgentToolService.countInventoryItem(player, COAL) / 2) : 0;
        }
        return 0;
    }

    private static boolean shouldSmeltGearMoneyOres(Player player, int barItemId) {
        int possibleBars = smeltableGearMoneyBars(player, barItemId);
        if (possibleBars <= 0) {
            return false;
        }
        return player.getItemAssistant().freeSlots() <= MIN_FREE_SLOTS_BEFORE_BANKING
                || possibleBars >= MIN_ORE_SETS_BEFORE_SMELTING;
    }

    private static int smithingProductBars(int itemId) {
        SmithingData data = SmithingData.forId(itemId);
        return data == null ? 0 : data.getAmount();
    }

    private static boolean hasPickaxeInInventory(Player player) {
        for (int pickaxeId : PICKAXE_ITEM_IDS) {
            if (AgentToolService.countInventoryItem(player, pickaxeId) > 0
                    && canUsePickaxe(player, pickaxeId)) {
                return true;
            }
        }
        return false;
    }

    private static boolean isPickaxeItem(int itemId) {
        for (int pickaxeId : PICKAXE_ITEM_IDS) {
            if (itemId == pickaxeId) {
                return true;
            }
        }
        return false;
    }

    private static int bestBankPickaxe(Player player) {
        for (int i = PICKAXE_ITEM_IDS.length - 1; i >= 0; i--) {
            int pickaxeId = PICKAXE_ITEM_IDS[i];
            if (AgentToolService.countBankItem(player, pickaxeId) > 0
                    && canUsePickaxe(player, pickaxeId)) {
                return pickaxeId;
            }
        }
        return -1;
    }

    private static boolean canUsePickaxe(Player player, int pickaxeId) {
        return player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.MINING])
                >= requiredMiningLevelForPickaxe(pickaxeId);
    }

    static int requiredMiningLevelForPickaxe(int pickaxeId) {
        if (pickaxeId == STEEL_PICKAXE) {
            return 6;
        }
        if (pickaxeId == MITHRIL_PICKAXE) {
            return 21;
        }
        if (pickaxeId == ADAMANT_PICKAXE) {
            return 31;
        }
        if (pickaxeId == RUNE_PICKAXE) {
            return 41;
        }
        return 1;
    }

    static String gearMoneyOreForMiningLevel(int miningLevel, int smithingLevel, int copperCount, int tinCount) {
        if (smithingLevel >= 15 && miningLevel >= 15) {
            return "iron";
        }
        return copperCount <= tinCount ? "copper" : "tin";
    }

    private static int getPickedUpItemId(JsonObject pickup) {
        if (pickup == null || !pickup.has("groundItem") || !pickup.get("groundItem").isJsonObject()) {
            return -1;
        }
        JsonObject groundItem = pickup.get("groundItem").getAsJsonObject();
        return getInt(groundItem, "id", -1);
    }

    private static int countInventoryAccountStorageItems(Player player) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            if (isAccountStorageItemForBanking(storedId - 1)) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    static boolean isAccountStorageItemForBanking(int itemId) {
        for (int storageId : ACCOUNT_STORAGE_ITEM_IDS) {
            if (itemId == storageId) {
                return true;
            }
        }
        return false;
    }

    static boolean isFoodToolForRestocking(int itemId) {
        for (int toolId : FOOD_TOOL_ITEM_IDS) {
            if (itemId == toolId) {
                return true;
            }
        }
        return false;
    }

    static String supplyBankLandmark(String trainingArea) {
        String area = trainingArea == null ? "" : trainingArea.trim().toLowerCase();
        if (area.contains("barbarian") || area.contains("varrock")) {
            return "varrock west bank";
        }
        return "varrock east bank";
    }

    private static boolean isPlayerInCombat(Player player) {
        return player.npcIndex > 0 || player.killingNpcIndex > 0 || player.underAttackBy > 0 || player.underAttackBy2 > 0;
    }

    static int combatSupplyPickupDistance(boolean inCombat) {
        return inCombat ? 4 : 12;
    }

    static boolean isRecoverableGoalFailure(String message) {
        String lower = message == null ? "" : message.toLowerCase();
        return lower.contains("repositioning to continue combat")
                || lower.contains("walking into melee range to attack")
                || lower.contains("reacquiring combat target");
    }

    private void logGoalEvent(AgentSession session, String event, CombatGoal goal, JsonObject result) {
        if (session == null || goal == null) {
            return;
        }
        JsonObject data = new JsonObject();
        data.add("goal", goal.toJson());
        if (result != null) {
            data.add("result", result);
        }
        AgentSessionLog.INSTANCE.clientEvent(session, event, data);
    }

    int pendingActionCountForTests() {
        return queuedActions.size();
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

    private static String getString(JsonObject object, String name, String fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            String value = object.get(name).getAsString();
            return value == null ? fallback : value.trim();
        }
        return fallback;
    }

    private static boolean isSuccess(JsonObject result) {
        return result != null && result.has("success") && result.get("success").isJsonPrimitive()
                && result.get("success").getAsBoolean();
    }

    private static JsonObject playerObject(JsonObject result) {
        if (result != null && result.has("player") && result.get("player").isJsonObject()) {
            return result.get("player").getAsJsonObject();
        }
        return null;
    }

    private static JsonObject addBatchStatus(JsonObject result, String status, int ticks) {
        JsonObject output = result == null ? AgentToolService.failure("Batched action did not return a result.") : result;
        output.addProperty("batchStatus", status);
        output.addProperty("batchTicks", ticks);
        return output;
    }

    private static boolean tileArrived(Player player, int x, int y, int height, int stopDistance) {
        if (player.heightLevel != height) {
            return false;
        }
        return Math.max(Math.abs(player.absX - x), Math.abs(player.absY - y)) <= stopDistance;
    }

    private static boolean playerIsIdle(Player player, boolean includeMovement, boolean includeSkilling,
            boolean includeCombat) {
        if (includeMovement && player.isMoving) {
            return false;
        }
        if (includeSkilling && SkillHandler.isSkilling(player)) {
            return false;
        }
        if (includeCombat && (player.npcIndex > 0 || player.killingNpcIndex > 0
                || player.underAttackBy > 0 || player.underAttackBy2 > 0)) {
            return false;
        }
        return true;
    }

    static int clampGoalTargetLevel(int targetLevel) {
        return Math.max(1, Math.min(99, targetLevel));
    }

    static int clampGoalStepInterval(int ticks) {
        return Math.max(2, Math.min(100, ticks));
    }

    static int clampGoalMaxActions(int maxActions) {
        return Math.max(1, Math.min(250000, maxActions));
    }

    static boolean isGoalPreferenceLocked(JsonObject arguments, String primaryName, String aliasName) {
        return getBoolean(arguments, primaryName, getBoolean(arguments, aliasName, false));
    }

    private static boolean getBoolean(JsonObject object, String name, boolean fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            try {
                return object.get(name).getAsBoolean();
            } catch (UnsupportedOperationException ignored) {
            } catch (NumberFormatException ignored) {
            } catch (IllegalStateException ignored) {
            }
        }
        return fallback;
    }

    private static class GearTarget {
        private final int itemId;
        private final int minLevel;
        private final int tier;
        private final String landmark;
        private final String shopName;
        private final int estimatedPrice;

        private GearTarget(int itemId, int minLevel, int tier, String landmark, String shopName, int estimatedPrice) {
            this.itemId = itemId;
            this.minLevel = minLevel;
            this.tier = tier;
            this.landmark = landmark;
            this.shopName = shopName;
            this.estimatedPrice = estimatedPrice;
        }

        private String itemName() {
            return AgentCombatPlanner.itemName(itemId);
        }
    }

    private static class QueuedAction {
        private final long targetTick;
        private final Callable<JsonObject> action;
        private final CountDownLatch latch = new CountDownLatch(1);
        private JsonObject result;

        private QueuedAction(long targetTick, Callable<JsonObject> action) {
            this.targetTick = targetTick;
            this.action = action;
        }

        private boolean isReady(long tick) {
            return tick >= targetTick;
        }

        private void execute(long tick) {
            try {
                result = action.call();
                if (result != null && !result.has("serverTick")) {
                    result.addProperty("serverTick", tick);
                }
            } catch (Exception e) {
                result = AgentToolService.failure("Agent action failed: " + e.getMessage());
                result.addProperty("serverTick", tick);
            } finally {
                latch.countDown();
            }
        }

        private boolean await(long timeoutMs) throws InterruptedException {
            return latch.await(timeoutMs, TimeUnit.MILLISECONDS);
        }

        private JsonObject getResult() {
            return result == null ? AgentToolService.failure("Agent action did not return a result.") : result;
        }
    }

    private static class CombatGoal {
        private final String token;
        private final String sessionId;
        private final int playerId;
        private final String playerName;
        private final int targetLevel;
        private final int stepIntervalTicks;
        private final int maxActions;
        private String area;
        private String npc;
        private String style;
        private final boolean fixedArea;
        private final boolean fixedStyle;
        private final long startedAt = System.currentTimeMillis();
        private int ticksElapsed;
        private int lastStepTick;
        private int actionsRun;
        private int attackLevel;
        private int strengthLevel;
        private int defenceLevel;
        private int lastLoggedAttackLevel;
        private int lastLoggedStrengthLevel;
        private int lastLoggedDefenceLevel;
        private int bankTrips;
        private int bankedSupplyItems;
        private int lootedSupplyItems;
        private int accountStorageBankTrips;
        private int bankedAccountItems;
        private int foodBankTrips;
        private int withdrawnFoodItems;
        private int gearShopTrips;
        private int gearItemsBought;
        private int gearItemsEquipped;
        private int gearSuppliesSold;
        private int gearCoinsEarned;
        private int gearCoinsSpent;
        private int gearMoneyTrips;
        private int gearMoneyItemsSold;
        private int gearMoneyCoinsEarned;
        private int gearMoneyTargetCoins;
        private int lastLoggedBankTrips;
        private int lastLoggedBankedSupplyItems;
        private int lastLoggedLootedSupplyItems;
        private int lastLoggedAccountStorageBankTrips;
        private int lastLoggedBankedAccountItems;
        private int lastLoggedFoodBankTrips;
        private int lastLoggedWithdrawnFoodItems;
        private int lastLoggedGearShopTrips;
        private int lastLoggedGearItemsBought;
        private int lastLoggedGearItemsEquipped;
        private int lastLoggedGearSuppliesSold;
        private int lastLoggedGearCoinsEarned;
        private int lastLoggedGearCoinsSpent;
        private int lastLoggedGearMoneyTrips;
        private int lastLoggedGearMoneyItemsSold;
        private int lastLoggedGearMoneyCoinsEarned;
        private int lastGearAttemptAction = -GEAR_CHECK_INTERVAL_ACTIONS;
        private int gearCombatCancelAttempts;
        private int gearTargetItemId;
        private String gearTargetName = "";
        private int gearMoneyTargetItemId;
        private String gearMoneyTargetName = "";
        private String status = "running";
        private String message = "Combat goal is running.";
        private boolean bankingSupplies;
        private boolean accountItemsStored;
        private boolean restockingFood;
        private boolean gearingUp;
        private boolean earningGearMoney;
        private boolean checkGear;
        private JsonObject lastResult;

        private CombatGoal(String token, String sessionId, int playerId, String playerName, int targetLevel,
                int stepIntervalTicks, int maxActions, String area, String npc, String style, boolean fixedArea,
                boolean fixedStyle) {
            this.token = token;
            this.sessionId = sessionId;
            this.playerId = playerId;
            this.playerName = playerName;
            this.targetLevel = targetLevel;
            this.stepIntervalTicks = stepIntervalTicks;
            this.maxActions = maxActions;
            this.area = area == null ? "" : area.trim();
            this.npc = npc == null ? "" : npc.trim();
            this.style = style == null ? "" : style.trim();
            this.fixedArea = fixedArea;
            this.fixedStyle = fixedStyle;
        }

        private boolean isTerminal() {
            return "completed".equals(status) || "blocked".equals(status);
        }

        private void updateLevels(Player player) {
            attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
            strengthLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.STRENGTH]);
            defenceLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.DEFENCE]);
        }

        private void refreshPlannerDisplay(Player player) {
            int hitpointsLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.HITPOINTS]);
            if (!fixedArea) {
                AgentCombatPlanner.TrainingArea recommendedArea = AgentCombatPlanner.recommendedArea(attackLevel,
                        strengthLevel, defenceLevel, hitpointsLevel, AgentToolService.countInventoryFood(player));
                area = recommendedArea.getName();
                npc = recommendedArea.getNpcName();
            }
            if (!fixedStyle) {
                String recommendedStyle = AgentCombatPlanner.nextTrainingStyle(attackLevel, strengthLevel, defenceLevel,
                        targetLevel);
                style = "complete".equals(recommendedStyle) ? "" : recommendedStyle;
            }
        }

        private void rememberPlanFromResult(JsonObject result) {
            if (result == null) {
                return;
            }
            if (!fixedStyle && result.has("trainingStyle") && result.get("trainingStyle").isJsonPrimitive()) {
                style = result.get("trainingStyle").getAsString();
            }
            if (!fixedArea && result.has("trainingPlan") && result.get("trainingPlan").isJsonObject()) {
                JsonObject trainingPlan = result.get("trainingPlan").getAsJsonObject();
                if (trainingPlan.has("name") && trainingPlan.get("name").isJsonPrimitive()) {
                    area = trainingPlan.get("name").getAsString();
                }
                if (trainingPlan.has("npcName") && trainingPlan.get("npcName").isJsonPrimitive()) {
                    npc = trainingPlan.get("npcName").getAsString();
                }
            }
        }

        private void rememberGearTarget(GearTarget target) {
            if (gearTargetItemId != target.itemId) {
                gearCombatCancelAttempts = 0;
            }
            gearTargetItemId = target.itemId;
            gearTargetName = target.itemName();
        }

        private void clearGearTarget() {
            gearingUp = false;
            gearCombatCancelAttempts = 0;
            gearTargetItemId = 0;
            gearTargetName = "";
        }

        private void beginGearMoney(GearTarget target) {
            earningGearMoney = true;
            gearingUp = false;
            gearMoneyTargetItemId = target.itemId;
            gearMoneyTargetName = target.itemName();
            gearMoneyTargetCoins = target.estimatedPrice;
            gearTargetItemId = target.itemId;
            gearTargetName = target.itemName();
        }

        private void clearGearMoney() {
            earningGearMoney = false;
            gearMoneyTargetItemId = 0;
            gearMoneyTargetName = "";
            gearMoneyTargetCoins = 0;
        }

        private boolean targetReached() {
            return attackLevel >= targetLevel && strengthLevel >= targetLevel && defenceLevel >= targetLevel;
        }

        private void complete(String message) {
            status = "completed";
            this.message = message;
        }

        private void block(String message) {
            status = "blocked";
            this.message = message;
        }

        private boolean shouldLogProgress() {
            if (actionsRun == 1 || actionsRun % 100 == 0) {
                rememberLoggedLevels();
                rememberLoggedSupplies();
                return true;
            }
            if (attackLevel != lastLoggedAttackLevel || strengthLevel != lastLoggedStrengthLevel
                    || defenceLevel != lastLoggedDefenceLevel) {
                rememberLoggedLevels();
                rememberLoggedSupplies();
                return true;
            }
            if (bankTrips != lastLoggedBankTrips || bankedSupplyItems != lastLoggedBankedSupplyItems
                    || lootedSupplyItems != lastLoggedLootedSupplyItems
                    || accountStorageBankTrips != lastLoggedAccountStorageBankTrips
                    || bankedAccountItems != lastLoggedBankedAccountItems
                    || foodBankTrips != lastLoggedFoodBankTrips
                    || withdrawnFoodItems != lastLoggedWithdrawnFoodItems
                    || gearShopTrips != lastLoggedGearShopTrips
                    || gearItemsBought != lastLoggedGearItemsBought
                    || gearItemsEquipped != lastLoggedGearItemsEquipped
                    || gearSuppliesSold != lastLoggedGearSuppliesSold
                    || gearCoinsEarned != lastLoggedGearCoinsEarned
                    || gearCoinsSpent != lastLoggedGearCoinsSpent
                    || gearMoneyTrips != lastLoggedGearMoneyTrips
                    || gearMoneyItemsSold != lastLoggedGearMoneyItemsSold
                    || gearMoneyCoinsEarned != lastLoggedGearMoneyCoinsEarned) {
                rememberLoggedSupplies();
                return true;
            }
            return false;
        }

        private void rememberLoggedLevels() {
            lastLoggedAttackLevel = attackLevel;
            lastLoggedStrengthLevel = strengthLevel;
            lastLoggedDefenceLevel = defenceLevel;
        }

        private void rememberLoggedSupplies() {
            lastLoggedBankTrips = bankTrips;
            lastLoggedBankedSupplyItems = bankedSupplyItems;
            lastLoggedLootedSupplyItems = lootedSupplyItems;
            lastLoggedAccountStorageBankTrips = accountStorageBankTrips;
            lastLoggedBankedAccountItems = bankedAccountItems;
            lastLoggedFoodBankTrips = foodBankTrips;
            lastLoggedWithdrawnFoodItems = withdrawnFoodItems;
            lastLoggedGearShopTrips = gearShopTrips;
            lastLoggedGearItemsBought = gearItemsBought;
            lastLoggedGearItemsEquipped = gearItemsEquipped;
            lastLoggedGearSuppliesSold = gearSuppliesSold;
            lastLoggedGearCoinsEarned = gearCoinsEarned;
            lastLoggedGearCoinsSpent = gearCoinsSpent;
            lastLoggedGearMoneyTrips = gearMoneyTrips;
            lastLoggedGearMoneyItemsSold = gearMoneyItemsSold;
            lastLoggedGearMoneyCoinsEarned = gearMoneyCoinsEarned;
        }

        private String statusMessage() {
            return "Combat goal " + status + ": " + message;
        }

        private JsonObject toJson() {
            JsonObject json = new JsonObject();
            json.addProperty("type", "combat");
            json.addProperty("status", status);
            json.addProperty("message", message);
            json.addProperty("sessionId", sessionId);
            json.addProperty("playerId", playerId);
            json.addProperty("playerName", playerName);
            json.addProperty("targetLevel", targetLevel);
            json.addProperty("stepIntervalTicks", stepIntervalTicks);
            json.addProperty("maxActions", maxActions);
            json.addProperty("actionsRun", actionsRun);
            json.addProperty("ticksElapsed", ticksElapsed);
            json.addProperty("startedAt", startedAt);
            json.addProperty("attackLevel", attackLevel);
            json.addProperty("strengthLevel", strengthLevel);
            json.addProperty("defenceLevel", defenceLevel);
            json.addProperty("bankingSupplies", bankingSupplies);
            json.addProperty("bankTrips", bankTrips);
            json.addProperty("bankedSupplyItems", bankedSupplyItems);
            json.addProperty("lootedSupplyItems", lootedSupplyItems);
            json.addProperty("accountStorageBankTrips", accountStorageBankTrips);
            json.addProperty("bankedAccountItems", bankedAccountItems);
            json.addProperty("accountItemsStored", accountItemsStored);
            json.addProperty("restockingFood", restockingFood);
            json.addProperty("foodBankTrips", foodBankTrips);
            json.addProperty("withdrawnFoodItems", withdrawnFoodItems);
            json.addProperty("gearingUp", gearingUp);
            json.addProperty("gearShopTrips", gearShopTrips);
            json.addProperty("gearItemsBought", gearItemsBought);
            json.addProperty("gearItemsEquipped", gearItemsEquipped);
            json.addProperty("gearSuppliesSold", gearSuppliesSold);
            json.addProperty("gearCoinsEarned", gearCoinsEarned);
            json.addProperty("gearCoinsSpent", gearCoinsSpent);
            json.addProperty("earningGearMoney", earningGearMoney);
            json.addProperty("gearMoneyTrips", gearMoneyTrips);
            json.addProperty("gearMoneyItemsSold", gearMoneyItemsSold);
            json.addProperty("gearMoneyCoinsEarned", gearMoneyCoinsEarned);
            json.addProperty("gearMoneyTargetCoins", gearMoneyTargetCoins);
            json.addProperty("gearCombatCancelAttempts", gearCombatCancelAttempts);
            if (gearTargetItemId > 0) {
                json.addProperty("gearTargetItemId", gearTargetItemId);
                json.addProperty("gearTargetName", gearTargetName);
            }
            if (gearMoneyTargetItemId > 0) {
                json.addProperty("gearMoneyTargetItemId", gearMoneyTargetItemId);
                json.addProperty("gearMoneyTargetName", gearMoneyTargetName);
            }
            json.addProperty("fixedArea", fixedArea);
            json.addProperty("fixedStyle", fixedStyle);
            if (!area.isEmpty()) {
                json.addProperty("area", area);
            }
            if (!npc.isEmpty()) {
                json.addProperty("npc", npc);
            }
            if (!style.isEmpty()) {
                json.addProperty("style", style);
            }
            if (lastResult != null) {
                json.add("lastResult", lastResult);
            }
            return json;
        }
    }
}
