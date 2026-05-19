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
import org.apollo.cache.def.ItemDefinition;

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
    private static final int KEBAB = 1971;
    private static final int COWHIDE = 1739;
    private static final int BONES = 526;
    private static final int RAW_BEEF = 2132;
    private static final int RAW_CHICKEN = 2138;
    private static final int BURNT_CHICKEN = 2144;
    private static final int BURNT_MEAT = 2146;
    private static final int HAMMER = 2347;
    private static final int BRONZE_PICKAXE = 1265;
    private static final int IRON_PICKAXE = 1267;
    private static final int STEEL_PICKAXE = 1269;
    private static final int ADAMANT_PICKAXE = 1271;
    private static final int MITHRIL_PICKAXE = 1273;
    private static final int RUNE_PICKAXE = 1275;
    private static final int LADDER_DOWN_OBJECT = 11867;
    private static final int LADDER_UP_OBJECT = 1755;
    private static final int NORTH_LADDER_UP_OBJECT = 12265;
    private static final int DWARVEN_MINE_SURFACE_LADDER_X = 3019;
    private static final int DWARVEN_MINE_SURFACE_LADDER_Y = 3450;
    private static final int DWARVEN_MINE_SURFACE_LADDER_RADIUS = 8;
    private static final int DWARVEN_MINE_SURFACE_TRAP_X = 3078;
    private static final int DWARVEN_MINE_SURFACE_TRAP_Y = 3493;
    private static final int DWARVEN_MINE_UNDERGROUND_LADDER_X = 3019;
    private static final int DWARVEN_MINE_UNDERGROUND_LADDER_Y = 9850;
    private static final int DWARVEN_MINE_UNDERGROUND_LADDER_STAND_X = 3020;
    private static final int DWARVEN_MINE_UNDERGROUND_LADDER_RADIUS = 12;
    private static final int DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_X = 3076;
    private static final int DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_Y = 9893;
    private static final int DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_STAND_X = 3077;
    private static final int DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_RADIUS = 12;
    private static final int CHAMPIONS_GUILD_STAIRS_X = 3191;
    private static final int CHAMPIONS_GUILD_STAIRS_Y = 3363;
    private static final int CHAMPIONS_GUILD_STAIRS_RADIUS = 10;
    private static final int SCAVVO_X = 3192;
    private static final int SCAVVO_Y = 3358;
    private static final int SCAVVO_RADIUS = 16;
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
            1277, 1279, 1281, 1285, 1287, 1289, 1291, 1301, 1303,
            1323, 1325, 1329, 1115, 1105, 1121, 1123, 1113, 1127,
            1067, 1069, 1071, 1073, 1079, 1171, 1173, 1175, 1177, 1181, 1183, 1185,
            1193, 1201
    };
    private static final int[] ACCOUNT_STORAGE_ITEM_IDS = {
            303, 590, 841, 882, 1205, 1265, 1267, 1269, 1271, 1273, 1275, 1351, 1925, 1931, HAMMER,
            555, 556, 557, 558, 559
    };
    private static final int[] FOOD_TOOL_ITEM_IDS = {
            SMALL_FISHING_NET
    };
    private static final int MIN_FREE_SLOTS_BEFORE_BANKING = 4;
    private static final int SUPPLY_COUNT_BEFORE_BANKING = 18;
    private static final int ACCOUNT_STORAGE_COUNT_BEFORE_BANKING = 1;
    private static final int MIN_FOOD_BEFORE_RESTOCK = 3;
    private static final int MIN_RAW_FOOD_BEFORE_COOKING = 8;
    private static final int DESIRED_LOW_LEVEL_FOOD = 10;
    private static final int DESIRED_HIGH_LEVEL_FOOD = 18;
    private static final int GEAR_CHECK_INTERVAL_ACTIONS = 80;
    private static final int GOAL_PROGRESS_LOG_INTERVAL_ACTIONS = 20;
    private static final int MAX_MOVING_WAIT_STEPS = 20;
    private static final int MAX_PICKAXE_ROUTE_NO_MOVE_ATTEMPTS = 8;
    private static final int PICKAXE_ROUTE_DEFER_ACTIONS = 200;
    private static final int MIN_GEAR_MONEY_ITEMS_BEFORE_SELLING = 27;
    private static final int MIN_BARS_BEFORE_SMITHING = 8;
    private static final int MIN_ORE_SETS_BEFORE_SMELTING = 24;
    private static final int COAL_ROUTE_MIN_FOOD = MIN_FOOD_BEFORE_RESTOCK + 1;
    private static final int IRON_SMELTING_SMITHING_LEVEL = 15;
    private static final int STEEL_SMELTING_SMITHING_LEVEL = 20;
    private static final int STEEL_COAL_PER_BAR = 2;
    private static final int EXPENSIVE_WEAPON_UPGRADE_PRICE = 5000;
    private static final int STRONG_ENOUGH_WEAPON_TIER = 4;
    private static final int AL_KHARID_GATE_TOLL = 10;
    private static final int AL_KHARID_HAMMER_AND_GATE_COIN_BUFFER = 25;
    private static final int KEBAB_RESTOCK_COIN_FLOAT = 120;
    private static final int VARROCK_COAL_DANGER_MIN_X = 3292;
    private static final int VARROCK_COAL_DANGER_MAX_X = 3308;
    private static final int VARROCK_COAL_DANGER_MIN_Y = 3275;
    private static final int VARROCK_COAL_DANGER_MAX_Y = 3330;
    private static final int VARROCK_COAL_WEST_ESCAPE_X = 3285;
    private static final int VARROCK_COAL_WEST_ESCAPE_MIN_Y = 3283;
    private static final int VARROCK_COAL_WEST_ESCAPE_MAX_Y = 3325;
    private static final int VARROCK_COAL_ESCAPE_CORRIDOR_MIN_X = 3260;
    private static final int VARROCK_COAL_ESCAPE_CORRIDOR_MAX_X = 3291;
    private static final int VARROCK_COAL_ESCAPE_CORRIDOR_MIN_Y = 3270;
    private static final int VARROCK_COAL_ESCAPE_CORRIDOR_MAX_Y = 3295;
    private static final int VARROCK_COAL_SAFE_ROAD_X = 3261;
    private static final int VARROCK_COAL_SAFE_ROAD_Y = 3322;
    static final int GEAR_MONEY_PRODUCTION_NONE = 0;
    static final int GEAR_MONEY_PRODUCTION_SMELT = 1;
    static final int GEAR_MONEY_PRODUCTION_SMITH = 2;
    private static final int[] PICKAXE_ITEM_IDS = {
            BRONZE_PICKAXE, IRON_PICKAXE, STEEL_PICKAXE, MITHRIL_PICKAXE, ADAMANT_PICKAXE, RUNE_PICKAXE
    };
    private static final int[] CLIMBING_OBJECT_IDS = {
            96, 98, 1722, 1723, 1725, 1726, 1733, 1734, 1736, 1737, 1738, 1742, 1744, 1755, 1767,
            2147, 2148, 2405, 2408, 2711, 3432, 3443, 4383, 4413, 4568, 4569, 4570, 4755, 4756,
            4879, 5096, 5130, 5131, 5167, 5492, 6278, 6279, 6434, 6436, 6439, 7257, 9582, 9584,
            11724, 11725, 11727, 11728, 11729, 11731, 11732, 11733, 11734, 11735, 11736, 11737,
            11888, 11889, 11890, 12265, 12266
    };
    private static final int[] GEAR_MONEY_ITEM_IDS = {
            COPPER_ORE, TIN_ORE, IRON_ORE, COAL, BRONZE_BAR, IRON_BAR,
            STEEL_BAR, MITHRIL_BAR, ADAMANT_BAR, RUNE_BAR
    };
    private static final PickaxeTarget[] PICKAXE_TARGETS = {
            new PickaxeTarget(BRONZE_PICKAXE, 1, 1, 1, "lumbridge axe shop", "axes"),
            new PickaxeTarget(IRON_PICKAXE, 1, 2, 140),
            new PickaxeTarget(STEEL_PICKAXE, 6, 3, 500),
            new PickaxeTarget(MITHRIL_PICKAXE, 21, 4, 1300),
            new PickaxeTarget(ADAMANT_PICKAXE, 31, 5, 3200),
            new PickaxeTarget(RUNE_PICKAXE, 41, 6, 32000)
    };
    private static final GearTarget[] WEAPON_GEAR_TARGETS = {
            new GearTarget(1279, 1, 1, "varrock sword shop", "sword", 91),
            new GearTarget(1281, 5, 2, "varrock sword shop", "sword", 325),
            new GearTarget(1285, 20, 3, "varrock sword shop", "sword", 845),
            new GearTarget(1301, 30, 4, "varrock sword shop", "sword", 3200),
            new GearTarget(1289, 40, 5, "champions guild rune store", "scavvo", 20800)
    };
    private static final GearTarget[] BODY_GEAR_TARGETS = {
            new GearTarget(1115, 1, 1, "varrock armour shop", "armour", 560),
            new GearTarget(1105, 5, 2, "varrock armour shop", "armour", 750),
            new GearTarget(1121, 20, 3, "varrock armour shop", "armour", 5200),
            new GearTarget(1113, 40, 5, "nardah adventurer store", "adventurer", 50000),
            new GearTarget(1127, 40, 6, "oziach rune armour", "oziach", 65000)
    };
    private static final GearTarget[] LEGS_GEAR_TARGETS = {
            new GearTarget(1067, 1, 1, "varrock armour shop", "armour", 280),
            new GearTarget(1069, 5, 2, "al kharid legs shop", "legs", 1000),
            new GearTarget(1071, 20, 3, "al kharid legs shop", "legs", 2600),
            new GearTarget(1073, 30, 4, "al kharid legs shop", "legs", 6400),
            new GearTarget(1079, 40, 5, "nardah adventurer store", "adventurer", 64000)
    };
    private static final GearTarget[] SHIELD_GEAR_TARGETS = {
            new GearTarget(1173, 1, 1, "falador shield shop", "shield", 168),
            new GearTarget(1175, 5, 2, "falador shield shop", "shield", 500),
            new GearTarget(1193, 5, 3, "nardah adventurer store", "adventurer", 1200),
            new GearTarget(1185, 40, 5, "oziach rune armour", "oziach", 22000)
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
                if (goal.shouldKeepWaitingForMovement(player)) {
                    continue;
                }
                player.resetWalkingQueue();
                player.isMoving = false;
                goal.recoverFromMovementStall(player);
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

        JsonObject junkDrop = dropBurntFoodIfCrowding(player);
        if (junkDrop != null) {
            return junkDrop;
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
            travelArgs.addProperty("name", supplyBankLandmark(player, goal));
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
            goal.gearCombatCancelAttempts++;
            return escapeCombatForNonCombatWork(player, "Gearing up", "varrock east bank");
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

        int carriedGearMoneyItems = countInventoryGearMoneyItems(player) + countInventoryGearMoneyProducts(player);
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int strengthLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.STRENGTH]);
        boolean liquidatingForCombat = shouldDeferExpensiveWeaponUpgradeForCombat(
                attackLevel, strengthLevel, goal.targetLevel, spendableCoins,
                bestEquippedGearTier(player, WEAPON_GEAR_TARGETS), target);
        if (carriedGearMoneyItems == 0 && liquidatingForCombat) {
            goal.clearGearMoney();
            goal.lastGearAttemptAction = goal.actionsRun;
            return AgentToolService.success("Deferring " + target.itemName()
                    + " savings; current weapon is strong enough to keep training Attack before a long mining grind.");
        }

        if (isPlayerInCombat(player)) {
            return escapeCombatForNonCombatWork(player, "Earning gear money", "varrock east bank");
        }
        JsonObject foodPrep = prepareGearMoneyFood(player, goal);
        if (foodPrep != null) {
            return foodPrep;
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

        PickaxeTarget pickaxeUpgrade = nextPickaxeUpgrade(player);
        if (goal.isPickaxeUpgradeDeferred(pickaxeUpgrade)) {
            pickaxeUpgrade = null;
        }
        if (pickaxeUpgrade != null && countInventoryGearMoneyItems(player) == 0) {
            return acquirePickaxeUpgradeStep(player, goal, pickaxeUpgrade);
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

        JsonObject travelCoinPrep = prepareGearMoneyTravelCoins(player);
        if (travelCoinPrep != null) {
            return travelCoinPrep;
        }

        int inventoryMoneyItems = countInventoryGearMoneyItems(player);
        if (inventoryMoneyItems > 0
                && spendableCoins + estimatedInventoryGearMoneyCoins(player) >= target.estimatedPrice) {
            return sellGearMoneyItemsStep(player, goal, target);
        }

        int smeltableBar = bestSmeltableGearMoneyBar(player);
        boolean canSmeltOres = smeltableBar > 0
                && shouldSmeltGearMoneyOres(player, smeltableBar, liquidatingForCombat);
        int smithableBar = bestSmithableGearMoneyBar(player);
        boolean canSmithBars = smithableBar > 0 && shouldSmithGearMoneyBars(player, smithableBar, liquidatingForCombat);
        int productionAction = gearMoneyProductionAction(canSmeltOres, canSmithBars);
        if (shouldSellCarriedGearMoneyAfterFurnaceStall(goal.movingStallRecoveries, inventoryMoneyItems,
                productionAction != GEAR_MONEY_PRODUCTION_NONE)) {
            JsonObject result = sellGearMoneyItemsStep(player, goal, target);
            String message = getString(result, "message", "selling carried mined items.");
            result.addProperty("message", "Earning gear money: furnace route stalled; selling carried materials instead: "
                    + message);
            return result;
        }
        if (productionAction == GEAR_MONEY_PRODUCTION_SMELT) {
            JsonObject travel = travelTo(player, "al kharid furnace");
            if (!getBoolean(travel, "complete", false)) {
                travel.addProperty("message", liquidatingForCombat
                        ? "Earning gear money: walking to Al Kharid furnace to process carried ores before resuming Attack."
                        : "Earning gear money: walking to Al Kharid furnace to smelt mined ores.");
                return travel;
            }
            JsonObject result = AgentToolService.handle(player, "smelt_bar", smeltArgs(smeltableBar,
                    smeltableGearMoneyBars(player, smeltableBar)));
            result.addProperty("message", "Earning gear money for " + target.itemName() + ": "
                    + getString(result, "message", "smelting mined ores."));
            return result;
        }

        if (productionAction == GEAR_MONEY_PRODUCTION_SMITH) {
            SmithingChoice smithingChoice = bestGearMoneySmithingChoice(player, smithableBar);
            JsonObject hammerPrep = prepareGearMoneyHammer(player, goal, target);
            if (hammerPrep != null) {
                return hammerPrep;
            }
            JsonObject gatePrep = prepareGearMoneyAlKharidGateToll(player, goal, target);
            if (gatePrep != null) {
                return gatePrep;
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

        if (liquidatingForCombat && inventoryMoneyItems > 0) {
            return sellGearMoneyItemsStep(player, goal, target);
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
                AgentToolService.countInventoryItem(player, TIN_ORE) + AgentToolService.countBankItem(player, TIN_ORE),
                AgentToolService.countInventoryItem(player, IRON_ORE) + AgentToolService.countBankItem(player, IRON_ORE),
                AgentToolService.countInventoryItem(player, COAL) + AgentToolService.countBankItem(player, COAL));
        ore = gearMoneyOreForRouteSafety(ore, AgentToolService.countInventoryFood(player),
                player.playerLevel[Constants.HITPOINTS],
                player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.HITPOINTS]));
        String mineLandmark = gearMoneyMineLandmark(ore);
        JsonObject travel = travelTo(player, mineLandmark);
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Earning gear money: walking to " + mineLandmark + " to mine "
                    + ore + " for higher-value smithing.");
            return travel;
        }
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
        int inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        int bankCoins = AgentToolService.countBankItem(player, COINS);
        int carriedMoneyItems = countInventoryGearMoneyItems(player) + countInventoryGearMoneyProducts(player);
        boolean localAlKharidStore = shouldUseLocalAlKharidGeneralStore(player);
        int localHammerSeedItem = hammerSeedItemForCoins(
                AgentToolService.countInventoryItem(player, IRON_ORE),
                AgentToolService.countInventoryItem(player, COPPER_ORE),
                AgentToolService.countInventoryItem(player, TIN_ORE),
                AgentToolService.countInventoryItem(player, BRONZE_BAR),
                bankCoins);
        if (shouldSellLocalSeedItemForHammerCoins(inventoryCoins, localAlKharidStore, localHammerSeedItem)) {
            return sellHammerSeedItemForCoinsStep(player, goal, target, localHammerSeedItem);
        }
        if (localAlKharidStore && inventoryCoins > 0) {
            return buyLocalGearMoneyHammer(player);
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
        if (shouldSellMaterialsForHammerCoins(inventoryCoins, bankCoins, shouldUseLocalAlKharidGeneralStore(player),
                carriedMoneyItems)) {
            return sellGearMoneyItemsStep(player, goal, target);
        }
        if (inventoryCoins <= 0 && carriedMoneyItems > 0) {
            return sellGearMoneyItemsStep(player, goal, target);
        }
        if (inventoryCoins <= 0) {
            return null;
        }

        return buyLocalGearMoneyHammer(player);
    }

    private static JsonObject buyLocalGearMoneyHammer(Player player) {
        String storeLandmark = gearMoneyGeneralStoreLandmark(player);
        JsonObject travel = travelTo(player, storeLandmark);
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Earning gear money: walking to " + storeLandmark + " to buy a hammer.");
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

    private static JsonObject prepareGearMoneyAlKharidGateToll(Player player, CombatGoal goal, GearTarget target) {
        int inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        if (!shouldSellLocalSeedItemForGateToll(inventoryCoins, shouldUseLocalAlKharidGeneralStore(player),
                hammerSeedItemForCoins(
                        AgentToolService.countInventoryItem(player, IRON_ORE),
                        AgentToolService.countInventoryItem(player, COPPER_ORE),
                        AgentToolService.countInventoryItem(player, TIN_ORE),
                        AgentToolService.countInventoryItem(player, BRONZE_BAR),
                        AgentToolService.countBankItem(player, COINS)))) {
            return null;
        }
        int seedItemId = hammerSeedItemForCoins(
                AgentToolService.countInventoryItem(player, IRON_ORE),
                AgentToolService.countInventoryItem(player, COPPER_ORE),
                AgentToolService.countInventoryItem(player, TIN_ORE),
                AgentToolService.countInventoryItem(player, BRONZE_BAR),
                AgentToolService.countBankItem(player, COINS));
        return sellGateTollSeedItemForCoinsStep(player, goal, target, seedItemId);
    }

    private static JsonObject prepareGearMoneyTravelCoins(Player player) {
        int inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        int bankCoins = AgentToolService.countBankItem(player, COINS);
        if (!shouldWithdrawGearMoneyTravelCoins(inventoryCoins, bankCoins, player.getItemAssistant().freeSlots(),
                Boundary.isIn(player, Boundary.BANK_AREA))) {
            return null;
        }
        JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                itemAmountArgs(COINS, Math.min(AL_KHARID_HAMMER_AND_GATE_COIN_BUFFER, bankCoins)));
        result.addProperty("message",
                "Earning gear money: withdrew a small Al Kharid toll float so bars are not sold for travel coins.");
        return result;
    }

    static boolean shouldWithdrawGearMoneyTravelCoins(int inventoryCoins, int bankCoins, int freeSlots,
            boolean inBankArea) {
        return inBankArea && freeSlots > 0 && inventoryCoins < AL_KHARID_GATE_TOLL && bankCoins > 0;
    }

    static boolean shouldSellCarriedGearMoneyAfterFurnaceStall(int movingStallRecoveries, int carriedMoneyItems,
            boolean canProcessCarriedMaterials) {
        return !canProcessCarriedMaterials
                && movingStallRecoveries >= 8
                && carriedMoneyItems >= MIN_GEAR_MONEY_ITEMS_BEFORE_SELLING;
    }

    static boolean shouldSellMaterialsForHammerCoins(int inventoryCoins, int bankCoins, boolean localGeneralStore,
            int carriedMoneyItems) {
        return inventoryCoins <= 0 && bankCoins <= 0 && localGeneralStore && carriedMoneyItems > 0;
    }

    static boolean shouldSellLocalSeedItemForHammerCoins(int inventoryCoins, boolean localGeneralStore, int seedItemId) {
        return inventoryCoins < AL_KHARID_HAMMER_AND_GATE_COIN_BUFFER && localGeneralStore && seedItemId > 0;
    }

    static boolean shouldSellLocalSeedItemForGateToll(int inventoryCoins, boolean localGeneralStore, int seedItemId) {
        return inventoryCoins < AL_KHARID_GATE_TOLL && localGeneralStore && seedItemId > 0;
    }

    static int hammerSeedItemForCoins(int ironOre, int copperOre, int tinOre, int bronzeBars, int bankCoins) {
        if (ironOre > 0) {
            return IRON_ORE;
        }
        if (copperOre > tinOre && copperOre > 0) {
            return COPPER_ORE;
        }
        if (tinOre > 0) {
            return TIN_ORE;
        }
        if (copperOre > 0) {
            return COPPER_ORE;
        }
        if (bronzeBars > 0) {
            return BRONZE_BAR;
        }
        return -1;
    }

    private static JsonObject sellHammerSeedItemForCoinsStep(Player player, CombatGoal goal, GearTarget target,
            int itemId) {
        String storeLandmark = gearMoneyGeneralStoreLandmark(player);
        JsonObject travel = travelTo(player, storeLandmark);
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Earning gear money: walking to " + storeLandmark
                    + " to sell one mined item for hammer coins.");
            return travel;
        }

        if (!currentShopNameContains(player, "general")) {
            JsonObject result = openShop(player, "general");
            result.addProperty("message", "Earning gear money: opening the general store to fund a smithing hammer.");
            return result;
        }

        JsonObject result = AgentToolService.handle(player, "sell_inventory_item", itemAmountArgs(itemId, 1));
        if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
            int sold = getInt(result, "sold", 0);
            int coins = getInt(result, "coinsReceived", 0);
            goal.gearMoneyTrips++;
            goal.gearMoneyItemsSold += sold;
            goal.gearMoneyCoinsEarned += coins;
            result.addProperty("message", "Earning gear money for " + target.itemName() + ": sold " + sold
                    + " mined item(s) for " + coins
                    + " coins to buy a hammer while preserving smelted bars when possible.");
        }
        return result;
    }

    private static JsonObject sellGateTollSeedItemForCoinsStep(Player player, CombatGoal goal, GearTarget target,
            int itemId) {
        String storeLandmark = gearMoneyGeneralStoreLandmark(player);
        JsonObject travel = travelTo(player, storeLandmark);
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Earning gear money: walking to " + storeLandmark
                    + " to sell one mined item for Al Kharid gate toll coins.");
            return travel;
        }

        if (!currentShopNameContains(player, "general")) {
            JsonObject result = openShop(player, "general");
            result.addProperty("message", "Earning gear money: opening the general store to fund the Al Kharid gate toll.");
            return result;
        }

        JsonObject result = AgentToolService.handle(player, "sell_inventory_item", itemAmountArgs(itemId, 1));
        if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
            int sold = getInt(result, "sold", 0);
            int coins = getInt(result, "coinsReceived", 0);
            goal.gearMoneyTrips++;
            goal.gearMoneyItemsSold += sold;
            goal.gearMoneyCoinsEarned += coins;
            result.addProperty("message", "Earning gear money for " + target.itemName() + ": sold " + sold
                    + " mined item(s) for " + coins
                    + " Al Kharid gate toll coins before returning to Varrock.");
        }
        return result;
    }

    private JsonObject prepareGearMoneyFood(Player player, CombatGoal goal) {
        int inventoryFood = AgentToolService.countInventoryFood(player);
        if (!shouldCarryFoodForGearMoney(inventoryFood,
                AgentToolService.countBankFood(player), AgentToolService.countBankRawCookableFood(player),
                AgentToolService.countInventoryRawCookableFood(player) > 0
                        || hasFoodToolInInventory(player) || hasFoodToolInBank(player)
                        || hasKebabRestockSource(player))) {
            goal.restockingFood = false;
            return null;
        }
        if (inventoryFood <= MIN_FOOD_BEFORE_RESTOCK) {
            JsonObject localRetreat = retreatWestFromVarrockCoalDanger(player, "Earning gear money");
            if (localRetreat != null) {
                return localRetreat;
            }
        }
        goal.earningGearMoney = false;
        goal.restockingFood = true;
        JsonObject result = restockFoodStep(player, goal);
        String message = getString(result, "message", "restocking food.");
        result.addProperty("message", "Earning gear money: stocking food before risky mining or furnace travel: "
                + message);
        return result;
    }

    static boolean shouldCarryFoodForGearMoney(int inventoryFood, int bankFood) {
        return shouldCarryFoodForGearMoney(inventoryFood, bankFood, 0, false);
    }

    static boolean shouldCarryFoodForGearMoney(int inventoryFood, int bankFood, int bankRawFood,
            boolean canGatherFood) {
        return inventoryFood <= MIN_FOOD_BEFORE_RESTOCK
                && (bankFood > 0 || bankRawFood > 0 || canGatherFood);
    }

    private static JsonObject sellGearMoneyItemsStep(Player player, CombatGoal goal, GearTarget target) {
        String storeLandmark = gearMoneyGeneralStoreLandmark(player);
        JsonObject travel = travelTo(player, storeLandmark);
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Earning gear money: walking to " + storeLandmark
                    + " to sell mined or smithed items.");
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
        String failure = getString(result, "message", "No saleable mined or smithed items were sold.");
        if (failure.toLowerCase().contains("no matching inventory items")) {
            if (player.isShopping || player.isBanking) {
                JsonObject closed = AgentToolService.handle(player, "close_interfaces", new JsonObject());
                closed.addProperty("message",
                        "Earning gear money: no mined/smithed sellables are carried; closing shop before mining.");
                return closed;
            }
            JsonObject empty = AgentToolService.success(
                    "Earning gear money: no mined/smithed sellables are carried; continuing mining.");
            empty.add("state", AgentToolService.observeState(player));
            return empty;
        }
        return result;
    }

    static String gearMoneyGeneralStoreLandmark(int x, int y) {
        return isAlKharidSideForGearMoney(x, y) ? "al kharid general store" : "varrock general store";
    }

    private static String gearMoneyGeneralStoreLandmark(Player player) {
        return gearMoneyGeneralStoreLandmark(player.absX, player.absY);
    }

    private static boolean shouldUseLocalAlKharidGeneralStore(Player player) {
        return isAlKharidSideForGearMoney(player.absX, player.absY);
    }

    static boolean isAlKharidSideForGearMoney(int x, int y) {
        return x >= 3268 && x <= 3335 && y >= 3160 && y <= 3235;
    }

    private static JsonObject acquirePickaxeUpgradeStep(Player player, CombatGoal goal, PickaxeTarget target) {
        if (AgentToolService.countInventoryItem(player, target.itemId) > 0) {
            return AgentToolService.success("Earning gear money: already carrying " + target.itemName()
                    + " for faster mining.");
        }
        int inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        int bankCoins = AgentToolService.countBankItem(player, COINS);
        if (inventoryCoins < target.estimatedPrice && bankCoins > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, "varrock east bank");
                result.addProperty("message", "Earning gear money: returning to bank for " + target.itemName()
                        + " coins.");
                return result;
            }
            int needed = Math.min(bankCoins, target.estimatedPrice - inventoryCoins);
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(COINS, needed));
            result.addProperty("message", "Earning gear money: withdrew coins for " + target.itemName() + ".");
            return result;
        }

        if (inventoryCoins < target.estimatedPrice) {
            return AgentToolService.success("Earning gear money: saving for " + target.itemName()
                    + " before upgrading the mining tool.");
        }

        JsonObject travel = travelToPickaxeSeller(player, target);
        if (!getBoolean(travel, "complete", false)) {
            if (goal.deferPickaxeUpgradeIfRouteIsStuck(player, target)) {
                JsonObject result = AgentToolService.success("Earning gear money: deferred "
                        + target.itemName() + " after repeated no-move route attempts; continuing with current pickaxe.");
                result.add("state", AgentToolService.observeState(player));
                return result;
            }
            travel.addProperty("message", "Earning gear money: walking to the pickaxe shop for "
                    + target.itemName() + ".");
            return travel;
        }
        goal.clearPickaxeRouteAttempts();
        if (!currentShopNameContains(player, target.shopName)) {
            JsonObject result = openShop(player, target.shopName);
            result.addProperty("message", "Earning gear money: opening the pickaxe shop for "
                    + target.itemName() + ".");
            return result;
        }

        int beforeCoins = AgentToolService.countInventoryItem(player, COINS);
        JsonObject result = AgentToolService.handle(player, "buy_shop_item", itemAmountArgs(target.itemId, 1));
        if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
            goal.clearPickaxeRouteAttempts();
            int spent = Math.max(0, beforeCoins - AgentToolService.countInventoryItem(player, COINS));
            goal.gearShopTrips++;
            goal.gearItemsBought += getInt(result, "bought", 0);
            goal.gearCoinsSpent += spent;
            result.addProperty("message", "Earning gear money: bought " + target.itemName()
                    + " for faster mining.");
        }
        return result;
    }

    private static JsonObject travelToPickaxeSeller(Player player, PickaxeTarget target) {
        if (!"pickaxe".equals(target.shopName)) {
            return travelTo(player, target.landmarkName);
        }
        if (isInDwarvenMine(player)) {
            JsonObject travel = travelTo(player, "nurmof pickaxe shop");
            if (!getBoolean(travel, "complete", false)) {
                travel.addProperty("message", "Earning gear money: walking through Dwarven Mine to Nurmof for "
                        + target.itemName() + ".");
            }
            return travel;
        }
        if (isNearDwarvenMineSurfaceLadder(player)) {
            JsonObject result = climbDownDwarvenMineLadder(player);
            result.addProperty("message", "Earning gear money: climbing down into Dwarven Mine to reach Nurmof for "
                    + target.itemName() + ".");
            result.addProperty("complete", false);
            result.addProperty("landmark", "nurmof pickaxe shop");
            return result;
        }
        JsonObject travel = travelTo(player, "dwarven mine ladder");
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Earning gear money: walking to the Dwarven Mine ladder for "
                    + target.itemName() + ".");
        }
        return travel;
    }

    static boolean isInDwarvenMine(int x, int y) {
        return x >= 2900 && x <= 3078 && y >= 9700 && y <= 9900;
    }

    private static boolean isInDwarvenMine(Player player) {
        return isInDwarvenMine(player.absX, player.absY);
    }

    static boolean isNearDwarvenMineSurfaceLadder(int x, int y) {
        return AgentKnowledgeBase.distance(x, y, DWARVEN_MINE_SURFACE_LADDER_X,
                DWARVEN_MINE_SURFACE_LADDER_Y) <= DWARVEN_MINE_SURFACE_LADDER_RADIUS;
    }

    private static boolean isNearDwarvenMineSurfaceLadder(Player player) {
        return isNearDwarvenMineSurfaceLadder(player.absX, player.absY);
    }

    static boolean isDwarvenMineSurfaceTrapTile(int x, int y) {
        return x == DWARVEN_MINE_SURFACE_TRAP_X && y == DWARVEN_MINE_SURFACE_TRAP_Y;
    }

    private static boolean isDwarvenMineSurfaceTrapTile(Player player) {
        return isDwarvenMineSurfaceTrapTile(player.absX, player.absY);
    }

    static boolean isNearDwarvenMineUndergroundLadder(int x, int y) {
        return AgentKnowledgeBase.distance(x, y, DWARVEN_MINE_UNDERGROUND_LADDER_STAND_X,
                DWARVEN_MINE_UNDERGROUND_LADDER_Y) <= DWARVEN_MINE_UNDERGROUND_LADDER_RADIUS;
    }

    private static boolean isNearDwarvenMineUndergroundLadder(Player player) {
        return isNearDwarvenMineUndergroundLadder(player.absX, player.absY);
    }

    private static boolean isNearDwarvenMineNorthUndergroundLadder(Player player) {
        return AgentKnowledgeBase.distance(player.absX, player.absY,
                DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_STAND_X,
                DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_Y) <= DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_RADIUS;
    }

    private static JsonObject climbDownDwarvenMineLadder(Player player) {
        JsonObject found = AgentToolService.handle(player, "find_nearest_object",
                objectIdArgs(LADDER_DOWN_OBJECT, DWARVEN_MINE_SURFACE_LADDER_RADIUS));
        JsonObject object = jsonObject(found, "object");
        if (object == null) {
            JsonObject fallback = AgentToolService.handle(player, "interact_object",
                    objectArgs(LADDER_DOWN_OBJECT, DWARVEN_MINE_SURFACE_LADDER_X, DWARVEN_MINE_SURFACE_LADDER_Y));
            if (!getBoolean(fallback, "success", false)) {
                fallback.addProperty("message", "Could not find or use the Dwarven Mine ladder nearby.");
            }
            return fallback;
        }
        return AgentToolService.handle(player, "interact_object", objectArgs(
                getInt(object, "objectId", LADDER_DOWN_OBJECT),
                getInt(object, "x", DWARVEN_MINE_SURFACE_LADDER_X),
                getInt(object, "y", DWARVEN_MINE_SURFACE_LADDER_Y)));
    }

    private static JsonObject climbUpDwarvenMineLadder(Player player) {
        JsonObject found = AgentToolService.handle(player, "find_nearest_object",
                objectIdArgs(LADDER_UP_OBJECT, DWARVEN_MINE_UNDERGROUND_LADDER_RADIUS));
        JsonObject object = jsonObject(found, "object");
        if (object == null) {
            JsonObject fallback = AgentToolService.handle(player, "interact_object",
                    objectArgs(LADDER_UP_OBJECT, DWARVEN_MINE_UNDERGROUND_LADDER_X,
                            DWARVEN_MINE_UNDERGROUND_LADDER_Y));
            if (!getBoolean(fallback, "success", false)) {
                fallback.addProperty("message", "Could not find or use the Dwarven Mine ladder nearby.");
            }
            return fallback;
        }
        return AgentToolService.handle(player, "interact_object", objectArgs(
                getInt(object, "objectId", LADDER_UP_OBJECT),
                getInt(object, "x", DWARVEN_MINE_UNDERGROUND_LADDER_X),
                getInt(object, "y", DWARVEN_MINE_UNDERGROUND_LADDER_Y)));
    }

    private static JsonObject climbUpDwarvenMineNorthLadder(Player player) {
        JsonObject found = AgentToolService.handle(player, "find_nearest_object",
                objectIdArgs(NORTH_LADDER_UP_OBJECT, DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_RADIUS));
        JsonObject object = jsonObject(found, "object");
        if (object == null) {
            JsonObject fallback = AgentToolService.handle(player, "interact_object",
                    objectArgs(NORTH_LADDER_UP_OBJECT, DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_X,
                            DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_Y));
            if (!getBoolean(fallback, "success", false)) {
                fallback.addProperty("message", "Could not find or use the north Dwarven Mine ladder nearby.");
            }
            return fallback;
        }
        return AgentToolService.handle(player, "interact_object", objectArgs(
                getInt(object, "objectId", NORTH_LADDER_UP_OBJECT),
                getInt(object, "x", DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_X),
                getInt(object, "y", DWARVEN_MINE_NORTH_UNDERGROUND_LADDER_Y)));
    }

    private JsonObject restockFoodStep(Player player, CombatGoal goal) {
        if (isPlayerInCombat(player)) {
            return escapeCombatForNonCombatWork(player, "Restocking food", "varrock east bank");
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
                && AgentToolService.countBankFood(player) <= 0
                && AgentToolService.countBankRawCookableFood(player) < MIN_RAW_FOOD_BEFORE_COOKING) {
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

        JsonObject kebabRestock = buyKebabRestockStep(player, goal, desiredFood, inventoryFood);
        if (kebabRestock != null) {
            return kebabRestock;
        }

        JsonObject rawFoodPickup = pickupRestockRawFood(player);
        if (rawFoodPickup != null) {
            return rawFoodPickup;
        }
        JsonObject supplyPickup = pickupRestockCombatSupply(player, goal);
        if (supplyPickup != null) {
            return supplyPickup;
        }

        inventoryRawFood = AgentToolService.countInventoryRawCookableFood(player);
        if (shouldCookCarriedRawFood(inventoryRawFood, player.getItemAssistant().freeSlots(), inventoryFood,
                desiredFood, AgentToolService.hasCookingFireNearby(player, 4),
                AgentToolService.countInventoryItem(player, TINDERBOX) > 0,
                AgentToolService.countInventoryItem(player, LOGS) > 0, AgentToolService.hasWoodcuttingAxe(player))) {
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

        if (shouldGatherBeefInsteadOfFishingFromLumbridgeSouth(player.absX, player.absY, inventoryFood,
                inventoryRawFood, desiredFood)) {
            JsonObject combatArgs = new JsonObject();
            combatArgs.addProperty("area", "lumbridge cows");
            combatArgs.addProperty("npc", "Cow");
            combatArgs.addProperty("style", goal.style == null || goal.style.trim().isEmpty() ? "strength" : goal.style);
            JsonObject cowResult = AgentToolService.handle(player, "train_combat", combatArgs);
            String message = getString(cowResult, "message", "gathering raw beef from Lumbridge cows.");
            cowResult.addProperty("message", "Restocking food: fishing route is blocked from here; " + message);
            return cowResult;
        }

        JsonObject result = AgentToolService.handle(player, "fish_food", new JsonObject());
        result.addProperty("message", "Restocking food: " + getString(result, "message", "fishing food."));
        return result;
    }

    private JsonObject pickupRestockCombatSupply(Player player, CombatGoal goal) {
        if (player.getItemAssistant().freeSlots() <= 0) {
            return null;
        }
        JsonObject result = AgentToolService.handle(player, "pickup_ground_item",
                combatLootArgs(combatSupplyPickupDistance(isPlayerInCombat(player))));
        if (result == null || !result.has("success") || !result.get("success").getAsBoolean()) {
            return null;
        }
        goal.lootedSupplyItems += getInt(result, "pickedUp", 0);
        if (isCombatGearItem(getPickedUpItemId(result))) {
            goal.checkGear = true;
        }
        result.addProperty("message", "Restocking food: preserved combat drop for later banking: "
                + getString(result, "message", "picked up a combat supply."));
        return result;
    }

    private JsonObject pickupRestockRawFood(Player player) {
        if (player.getItemAssistant().freeSlots() <= 0) {
            return null;
        }
        JsonObject result = AgentToolService.handle(player, "pickup_ground_item", restockRawFoodArgs());
        if (result == null || !result.has("success") || !result.get("success").getAsBoolean()) {
            return null;
        }
        result.addProperty("message", "Restocking food: "
                + getString(result, "message", "picked up raw food for cooking."));
        return result;
    }

    private JsonObject buyKebabRestockStep(Player player, CombatGoal goal, int desiredFood, int inventoryFood) {
        int freeSlots = player.getItemAssistant().freeSlots();
        int inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        int bankCoins = AgentToolService.countBankItem(player, COINS);
        if (!shouldBuyKebabsForFood(inventoryFood, desiredFood, inventoryCoins, bankCoins, freeSlots)) {
            return null;
        }

        if (inventoryCoins <= 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject travel = travelTo(player, "varrock east bank");
                travel.addProperty("message", "Restocking food: returning to bank for a small kebab coin float.");
                return travel;
            }
            int amount = kebabCoinFloat(desiredFood, inventoryFood, freeSlots, bankCoins);
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(COINS, amount));
            result.addProperty("message", "Restocking food: withdrew a small coin float for Al Kharid kebabs.");
            return result;
        }

        if (player.isBanking) {
            JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
            result.addProperty("message", "Restocking food: closing bank before walking to Karim's Kebabs.");
            return result;
        }

        JsonObject travel = travelTo(player, "al kharid kebab shop");
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Restocking food: walking to Karim's Kebabs for fast combat food.");
            return travel;
        }

        if (!currentShopNameContains(player, "kebab")) {
            JsonObject result = openShop(player, "kebab");
            result.addProperty("message", "Restocking food: opening the kebab shop.");
            return result;
        }

        int amount = Math.max(1, Math.min(freeSlots, desiredFood - inventoryFood));
        JsonObject result = AgentToolService.handle(player, "buy_shop_item", itemAmountArgs(KEBAB, amount));
        int bought = getInt(result, "bought", 0);
        if (result == null) {
            return AgentToolService.failure("Restocking food: kebab purchase failed; falling back to gathered food.");
        }
        if (result.has("success") && result.get("success").getAsBoolean()) {
            goal.withdrawnFoodItems += bought;
            result.addProperty("message", "Restocking food: bought " + bought
                    + " kebab(s) for faster Strength and money-making runs.");
        } else {
            result.addProperty("message", "Restocking food: kebab purchase failed; falling back to gathered food.");
        }
        return result;
    }

    private static JsonObject dropBurntFoodIfCrowding(Player player) {
        if (countInventoryBurntFood(player) <= 0
                || player.getItemAssistant().freeSlots() > MIN_FREE_SLOTS_BEFORE_BANKING) {
            return null;
        }
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        itemIds.add(BURNT_CHICKEN);
        itemIds.add(BURNT_MEAT);
        arguments.add("itemIds", itemIds);
        JsonObject result = AgentToolService.handle(player, "drop_inventory_items", arguments);
        int dropped = getInt(result, "dropped", 0);
        if (dropped <= 0) {
            return null;
        }
        result.addProperty("message", "Cleared useless burnt food to keep inventory slots for banked supplies and ore.");
        return result;
    }

    private JsonObject prepareFoodFromBank(Player player, CombatGoal goal, int desiredFood) {
        int supplyCount = countInventoryCombatSupplies(player);
        if (shouldDepositSuppliesDuringFoodRestock(supplyCount, player.getItemAssistant().freeSlots())) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", combatSupplyArgs(0));
            int depositedAmount = getInt(result, "depositedAmount", 0);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                int remainingSupplyCount = countInventoryCombatSupplies(player);
                if (supplyDepositMadeProgress(supplyCount, depositedAmount, remainingSupplyCount)) {
                    goal.bankTrips++;
                    goal.bankedSupplyItems += depositedAmount;
                    String message = getString(result, "message", "Deposited combat supplies.");
                    result.addProperty("message", "Restocking food: banked combat supplies for later account progression: " + message);
                    return result;
                }
            } else {
                return result;
            }
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

    static boolean supplyDepositMadeProgress(int supplyCountBefore, int depositedAmount, int supplyCountAfter) {
        return depositedAmount > 0 && supplyCountAfter < supplyCountBefore;
    }

    static boolean shouldDepositSuppliesDuringFoodRestock(int supplyCount, int freeSlots) {
        return shouldBankCombatSupplyCount(supplyCount, freeSlots);
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

    private static JsonObject restockRawFoodArgs() {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        itemIds.add(RAW_BEEF);
        itemIds.add(RAW_CHICKEN);
        arguments.add("itemIds", itemIds);
        arguments.addProperty("maxDistance", 20);
        return arguments;
    }

    static boolean isRestockRawFoodItem(int itemId) {
        return itemId == RAW_BEEF || itemId == RAW_CHICKEN;
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

    private static JsonObject objectIdArgs(int objectId, int maxDistance) {
        JsonObject arguments = new JsonObject();
        JsonArray objectIds = new JsonArray();
        objectIds.add(objectId);
        arguments.add("objectIds", objectIds);
        arguments.addProperty("maxDistance", maxDistance);
        return arguments;
    }

    private static JsonObject objectIdsArgs(int[] ids, int maxDistance) {
        JsonObject arguments = new JsonObject();
        JsonArray objectIds = new JsonArray();
        for (int id : ids) {
            objectIds.add(id);
        }
        arguments.add("objectIds", objectIds);
        arguments.addProperty("maxDistance", maxDistance);
        return arguments;
    }

    private static JsonObject objectArgs(int objectId, int x, int y) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("objectId", objectId);
        arguments.addProperty("x", x);
        arguments.addProperty("y", y);
        return arguments;
    }

    private static JsonObject walkTileArgs(int x, int y, int height) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("x", x);
        arguments.addProperty("y", y);
        arguments.addProperty("height", height);
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
            if (isGearMoneyClutterItemForBanking(player, itemId)) {
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
        if (isChampionsGuildUpperFloor(player) && !isChampionsGuildRuneStoreLandmark(landmark)) {
            JsonObject result = climbNearestStairs(player, "Leaving Scavvo's Rune Store before resuming the surface route.");
            result.addProperty("complete", false);
            result.addProperty("landmark", "champions guild stairs");
            return result;
        }
        if (isInDwarvenMine(player) && !isDwarvenMineLandmark(landmark)) {
            return travelOutOfDwarvenMine(player);
        }
        if (isDwarvenMineSurfaceTrapTile(player) && !isDwarvenMineSurfaceLandmark(landmark)) {
            JsonObject result = climbDownDwarvenMineLadder(player);
            result.addProperty("message", "Recovering from the Dwarven Mine surface exit by re-climbing the ladder.");
            result.addProperty("complete", false);
            result.addProperty("landmark", "dwarven mine ladder");
            return result;
        }
        if (isChampionsGuildRuneStoreLandmark(landmark)) {
            return travelToChampionsGuildRuneStore(player);
        }
        return travelToDirect(player, landmark);
    }

    private static JsonObject travelToChampionsGuildRuneStore(Player player) {
        if (player.heightLevel > 0) {
            JsonObject result = travelToDirect(player, "champions guild rune store");
            if (!getBoolean(result, "complete", false)) {
                result.addProperty("message", "Walking across Champions' Guild upper floor toward Scavvo's Rune Store.");
            }
            return result;
        }
        if (AgentKnowledgeBase.distance(player.absX, player.absY,
                CHAMPIONS_GUILD_STAIRS_X, CHAMPIONS_GUILD_STAIRS_Y) > CHAMPIONS_GUILD_STAIRS_RADIUS) {
            JsonObject result = travelToDirect(player, "champions guild stairs");
            if (!getBoolean(result, "complete", false)) {
                result.addProperty("message", "Walking toward the Champions' Guild stairs for Scavvo's Rune Store.");
            }
            return result;
        }
        JsonObject result = climbNearestStairs(player, "Climbing to Scavvo's Rune Store for rune gear.");
        result.addProperty("complete", false);
        result.addProperty("landmark", "champions guild rune store");
        return result;
    }

    private static JsonObject climbNearestStairs(Player player, String message) {
        JsonObject nameArgs = new JsonObject();
        nameArgs.addProperty("name", "stair");
        nameArgs.addProperty("maxDistance", CHAMPIONS_GUILD_STAIRS_RADIUS);
        JsonObject found = AgentToolService.handle(player, "find_nearest_object", nameArgs);
        JsonObject object = jsonObject(found, "object");
        if (object == null) {
            found = AgentToolService.handle(player, "find_nearest_object",
                    objectIdsArgs(CLIMBING_OBJECT_IDS, CHAMPIONS_GUILD_STAIRS_RADIUS));
            object = jsonObject(found, "object");
        }
        if (object == null) {
            JsonObject result = AgentToolService.failure("No climbable stairs are nearby.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        JsonObject result = AgentToolService.handle(player, "interact_object", objectArgs(
                getInt(object, "objectId", -1),
                getInt(object, "x", player.absX),
                getInt(object, "y", player.absY)));
        result.addProperty("message", message);
        return result;
    }

    private static boolean isChampionsGuildRuneStoreLandmark(String landmark) {
        if (landmark == null) {
            return false;
        }
        String normalized = landmark.toLowerCase();
        return "champions guild rune store".equals(normalized)
                || "scavvo rune store".equals(normalized)
                || "scavvo".equals(normalized);
    }

    private static boolean isChampionsGuildUpperFloor(Player player) {
        return player != null && player.heightLevel > 0
                && AgentKnowledgeBase.distance(player.absX, player.absY, SCAVVO_X, SCAVVO_Y) <= SCAVVO_RADIUS;
    }

    private static JsonObject travelToDirect(Player player, String landmark) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("name", landmark);
        return AgentToolService.handle(player, "travel_to_landmark", arguments);
    }

    private static boolean isDwarvenMineLandmark(String landmark) {
        if (landmark == null) {
            return false;
        }
        String normalized = landmark.toLowerCase();
        return "nurmof pickaxe shop".equals(normalized)
                || "pickaxe shop".equals(normalized)
                || "dwarven mine north ladder underground".equals(normalized)
                || "dwarven mine trapdoor underground".equals(normalized);
    }

    private static boolean isDwarvenMineSurfaceLandmark(String landmark) {
        if (landmark == null) {
            return false;
        }
        String normalized = landmark.toLowerCase();
        return "dwarven mine ladder".equals(normalized)
                || "dwarven mine trapdoor".equals(normalized);
    }

    private static JsonObject travelOutOfDwarvenMine(Player player) {
        if (isNearDwarvenMineUndergroundLadder(player)) {
            JsonObject result = climbUpDwarvenMineLadder(player);
            result.addProperty("message", "Leaving Dwarven Mine before resuming the surface route.");
            result.addProperty("complete", false);
            result.addProperty("landmark", "dwarven mine ladder");
            return result;
        }
        if (isNearDwarvenMineNorthUndergroundLadder(player)) {
            JsonObject result = climbUpDwarvenMineNorthLadder(player);
            result.addProperty("message", "Leaving the north Dwarven Mine dead-end before resuming the surface route.");
            result.addProperty("complete", false);
            result.addProperty("landmark", "dwarven mine ladder");
            return result;
        }
        JsonObject travel = travelToDirect(player, "dwarven mine trapdoor underground");
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "Walking back to the Dwarven Mine trapdoor before resuming the surface route.");
        }
        return travel;
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
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int strengthLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.STRENGTH]);
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        if (shouldDeferExpensiveWeaponUpgradeForCombat(attackLevel, strengthLevel, goal.targetLevel, spendableCoins,
                bestEquippedGearTier(player, WEAPON_GEAR_TARGETS), target)
                && countInventoryGearMoneyItems(player) == 0
                && countInventoryGearMoneyProducts(player) == 0) {
            return false;
        }
        return spendableCoins < target.estimatedPrice;
    }

    private static GearTarget nextGearTarget(Player player) {
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int strengthLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.STRENGTH]);
        int defenceLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.DEFENCE]);
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        GearTarget weapon = bestActionableGearTarget(player, WEAPON_GEAR_TARGETS, attackLevel, spendableCoins);
        if (weapon != null) {
            return weapon;
        }
        if (shouldSaveForWeaponBeforeArmor(attackLevel, strengthLevel, spendableCoins,
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
        GearTarget shield = bestActionableGearTarget(player, SHIELD_GEAR_TARGETS, defenceLevel, spendableCoins);
        if (shield != null) {
            return shield;
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
        GearTarget shield = bestDesiredGearTarget(player, SHIELD_GEAR_TARGETS, defenceLevel);
        if (shield != null) {
            return shield;
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
                || containsGearTarget(LEGS_GEAR_TARGETS, first) && containsGearTarget(LEGS_GEAR_TARGETS, second)
                || containsGearTarget(SHIELD_GEAR_TARGETS, first) && containsGearTarget(SHIELD_GEAR_TARGETS, second);
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
        return shouldSaveForWeaponBeforeArmor(attackLevel, attackLevel, spendableCoins, bestWeaponTier);
    }

    static boolean shouldSaveForWeaponBeforeArmor(int attackLevel, int strengthLevel, int spendableCoins,
            int bestWeaponTier) {
        GearTarget target = recommendedGearTarget(WEAPON_GEAR_TARGETS, attackLevel);
        return target != null
                && target.tier > bestWeaponTier
                && spendableCoins < target.estimatedPrice
                && !shouldDeferExpensiveWeaponUpgradeForCombat(attackLevel, strengthLevel, DEFAULT_GOAL_TARGET_LEVEL,
                        spendableCoins, bestWeaponTier, target);
    }

    static boolean shouldDeferExpensiveWeaponUpgradeForCombat(int attackLevel, int targetLevel, int spendableCoins,
            int bestWeaponTier, int targetItemId) {
        return shouldDeferExpensiveWeaponUpgradeForCombat(attackLevel, attackLevel, targetLevel, spendableCoins,
                bestWeaponTier, gearTargetByItemId(targetItemId));
    }

    static boolean shouldDeferExpensiveWeaponUpgradeForCombat(int attackLevel, int strengthLevel, int targetLevel,
            int spendableCoins, int bestWeaponTier, int targetItemId) {
        return shouldDeferExpensiveWeaponUpgradeForCombat(attackLevel, strengthLevel, targetLevel, spendableCoins,
                bestWeaponTier, gearTargetByItemId(targetItemId));
    }

    private static boolean shouldDeferExpensiveWeaponUpgradeForCombat(int attackLevel, int strengthLevel,
            int targetLevel, int spendableCoins, int bestWeaponTier, GearTarget target) {
        if (target == null || !containsGearTarget(WEAPON_GEAR_TARGETS, target)) {
            return false;
        }
        if (bestWeaponTier < STRONG_ENOUGH_WEAPON_TIER) {
            return false;
        }
        if (target.estimatedPrice < EXPENSIVE_WEAPON_UPGRADE_PRICE) {
            return false;
        }
        if (spendableCoins * 2 >= target.estimatedPrice) {
            return false;
        }
        if (target.minLevel >= 40 && target.tier > bestWeaponTier) {
            return shouldTrainStrengthBeforeExpensiveWeapon(attackLevel, strengthLevel, targetLevel);
        }
        if (attackLevel >= targetLevel) {
            return false;
        }
        return true;
    }

    static boolean shouldTrainStrengthBeforeExpensiveWeapon(int attackLevel, int strengthLevel, int targetLevel) {
        int meaningfulStrengthTarget = Math.min(targetLevel, attackLevel);
        return strengthLevel + 8 < attackLevel || strengthLevel + 5 < meaningfulStrengthTarget;
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
        target = gearTargetByItemId(LEGS_GEAR_TARGETS, itemId);
        if (target != null) {
            return target;
        }
        return gearTargetByItemId(SHIELD_GEAR_TARGETS, itemId);
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
        return shouldBankCombatSupplyCount(supplyCount, player.getItemAssistant().freeSlots());
    }

    static boolean shouldBankCombatSupplyCount(int supplyCount, int freeSlots) {
        return supplyCount > 0 && (freeSlots <= 0 || supplyCount >= SUPPLY_COUNT_BEFORE_BANKING);
    }

    private static boolean shouldStoreAccountItems(Player player, CombatGoal goal) {
        return goal != null
                && shouldStoreAccountItemCount(countInventoryAccountStorageItems(player),
                        goal.gearingUp, goal.earningGearMoney, goal.restockingFood)
                && !shouldEarnGearMoney(player, goal);
    }

    static boolean shouldStoreAccountItemCount(int accountItemCount, boolean gearingUp, boolean earningGearMoney) {
        return shouldStoreAccountItemCount(accountItemCount, gearingUp, earningGearMoney, false);
    }

    static boolean shouldStoreAccountItemCount(int accountItemCount, boolean gearingUp, boolean earningGearMoney,
            boolean restockingFood) {
        return !gearingUp
                && !earningGearMoney
                && !restockingFood
                && accountItemCount >= ACCOUNT_STORAGE_COUNT_BEFORE_BANKING;
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
        return shouldVisitBankForFood(inventoryRawFood, AgentToolService.countBankFood(player),
                AgentToolService.countBankRawCookableFood(player), hasFoodToolInInventory(player),
                hasFoodToolInBank(player), countInventoryCombatSupplies(player),
                player.getItemAssistant().freeSlots(), Boundary.isIn(player, Boundary.BANK_AREA));
    }

    static boolean shouldVisitBankForFood(int inventoryRawFood, int bankFood, int bankRawFood,
            boolean hasFoodToolInInventory, boolean hasFoodToolInBank, int combatSupplyCount, int freeSlots,
            boolean inBankArea) {
        if (shouldBankCombatSupplyCount(combatSupplyCount, freeSlots)) {
            return true;
        }
        if (inventoryRawFood >= MIN_RAW_FOOD_BEFORE_COOKING) {
            return false;
        }
        if (inventoryRawFood > 0 && !inBankArea) {
            return false;
        }
        if (bankFood > 0 || bankRawFood > 0) {
            return true;
        }
        return !hasFoodToolInInventory && hasFoodToolInBank && inventoryRawFood <= 0;
    }

    static boolean shouldCookCarriedRawFood(int inventoryRawFood, int freeSlots, int inventoryFood,
            int desiredFood, boolean hasCookingFireNearby, boolean hasTinderbox, boolean hasLogs,
            boolean hasWoodcuttingAxe) {
        if (inventoryRawFood <= 0) {
            return false;
        }
        if (inventoryRawFood >= MIN_RAW_FOOD_BEFORE_COOKING || freeSlots <= MIN_FREE_SLOTS_BEFORE_BANKING) {
            return true;
        }
        if (inventoryFood >= minimumReturnFood(desiredFood)) {
            return true;
        }
        return hasCookingFireNearby || (hasTinderbox && (hasLogs || hasWoodcuttingAxe));
    }

    static boolean shouldGatherBeefInsteadOfFishingFromLumbridgeSouth(int x, int y, int inventoryFood,
            int inventoryRawFood, int desiredFood) {
        return x >= 3258 && x <= 3280 && y >= 3190 && y <= 3245
                && inventoryFood < minimumReturnFood(desiredFood)
                && inventoryRawFood < MIN_RAW_FOOD_BEFORE_COOKING;
    }

    private static boolean hasFoodRestockSource(Player player) {
        return AgentToolService.countBankFood(player) > 0
                || AgentToolService.countBankRawCookableFood(player) > 0
                || AgentToolService.countInventoryRawCookableFood(player) > 0
                || hasKebabRestockSource(player)
                || hasFoodToolInInventory(player)
                || hasFoodToolInBank(player);
    }

    private static boolean hasKebabRestockSource(Player player) {
        return AgentToolService.countInventoryItem(player, COINS) > 0
                || AgentToolService.countBankItem(player, COINS) > 0;
    }

    static boolean shouldBuyKebabsForFood(int inventoryFood, int desiredFood, int inventoryCoins,
            int bankCoins, int freeSlots) {
        if (inventoryFood >= desiredFood || freeSlots <= 0) {
            return false;
        }
        if (inventoryCoins > 0) {
            return true;
        }
        return bankCoins > 0;
    }

    static int kebabCoinFloat(int desiredFood, int inventoryFood, int freeSlots, int bankCoins) {
        int desiredKebabs = Math.max(1, Math.min(freeSlots, desiredFood - inventoryFood));
        int amount = Math.max(AL_KHARID_GATE_TOLL + desiredKebabs * 5, KEBAB_RESTOCK_COIN_FLOAT);
        return Math.min(Math.max(1, bankCoins), amount);
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

    private static int countInventoryBurntFood(Player player) {
        return AgentToolService.countInventoryItem(player, BURNT_CHICKEN)
                + AgentToolService.countInventoryItem(player, BURNT_MEAT);
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
                && !isLowQualityGearMoneySmithingProduct(itemId)
                && !isAccountStorageItemForBanking(itemId)
                && !isCombatGearItem(itemId);
    }

    static boolean isLowQualityGearMoneySmithingProduct(int itemId) {
        SmithingData data = SmithingData.forId(itemId);
        if (data == null) {
            return false;
        }
        String name = data.name();
        return name.contains("_DART")
                || name.contains("_NAILS")
                || name.contains("_TIPS")
                || name.contains("_KNIFE");
    }

    static boolean isGearMoneyClutterItemForBanking(int itemId) {
        return itemId > 0
                && !isGearMoneyItem(itemId)
                && !isGearMoneyProductItem(itemId)
                && !isPickaxeItem(itemId)
                && !AgentToolService.isAgentFood(itemId)
                && itemId != COINS
                && itemId != HAMMER;
    }

    private static boolean isGearMoneyClutterItemForBanking(Player player, int itemId) {
        return isGearMoneyClutterItemForBanking(itemId)
                || isObsoleteGearMoneyPickaxeForBanking(itemId, bestCarriedUsablePickaxeTier(player));
    }

    static boolean isObsoleteGearMoneyPickaxeForBanking(int itemId, int bestCarriedUsablePickaxeTier) {
        return isPickaxeItem(itemId)
                && bestCarriedUsablePickaxeTier > 0
                && pickaxeTier(itemId) < bestCarriedUsablePickaxeTier;
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
            if (isGearMoneyProductItem(data.getId())) {
                count += AgentToolService.countInventoryItem(player, data.getId());
            }
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
            int shopValue = estimatedGeneralStoreSellCoins(itemId);
            if (shopValue > 0) {
                return shopValue;
            }
            return fallbackGearMoneySmithingProductSellCoins(itemId);
        }
        return 0;
    }

    static int estimatedGearMoneySmithingBatchSellCoins(int itemId, int availableBars) {
        int bars = smithingProductBars(itemId);
        if (bars <= 0 || availableBars < bars) {
            return 0;
        }
        return (availableBars / bars) * estimatedGearMoneySellCoins(itemId);
    }

    private static int estimatedGeneralStoreSellCoins(int itemId) {
        ItemDefinition definition;
        try {
            definition = ItemDefinition.lookup(itemId);
        } catch (NullPointerException e) {
            return 0;
        }
        if (definition == null) {
            return 0;
        }
        double generalStoreSellRatio = 0.85D * 0.90D;
        return Math.max(1, (int) Math.floor(definition.getValue() * generalStoreSellRatio));
    }

    private static int fallbackGearMoneySmithingProductSellCoins(int itemId) {
        if (itemId == 1137) { // Iron med helm, observed in Varrock general store.
            return 64;
        }
        if (itemId == 1293) { // Iron longsword, observed in Varrock general store.
            return 107;
        }
        return Math.max(1, smithingProductBars(itemId) * estimatedGearMoneySellCoins(
                AgentSmithingPlanner.requiredBarForItem(itemId)));
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
            if (isGearMoneyClutterItemForBanking(player, itemId)) {
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

    private static boolean shouldSmithGearMoneyBars(Player player, int barItemId, boolean liquidatingForCombat) {
        int bars = AgentToolService.countInventoryItem(player, barItemId);
        if (bars <= 0) {
            return false;
        }
        SmithingChoice choice = bestGearMoneySmithingChoice(player, barItemId);
        if (choice == null) {
            return false;
        }
        return shouldSmithGearMoneyBars(bars, choice.getBarsNeeded(), player.getItemAssistant().freeSlots(),
                liquidatingForCombat);
    }

    static boolean shouldSmithGearMoneyBars(int bars, int choiceBarsNeeded, int freeSlots,
            boolean liquidatingForCombat) {
        if (bars <= 0 || choiceBarsNeeded <= 0) {
            return false;
        }
        return liquidatingForCombat
                || freeSlots <= MIN_FREE_SLOTS_BEFORE_BANKING
                || bars >= MIN_BARS_BEFORE_SMITHING
                || bars >= choiceBarsNeeded;
    }

    static int gearMoneyProductionAction(boolean canSmeltOres, boolean canSmithBars) {
        if (canSmeltOres) {
            return GEAR_MONEY_PRODUCTION_SMELT;
        }
        if (canSmithBars) {
            return GEAR_MONEY_PRODUCTION_SMITH;
        }
        return GEAR_MONEY_PRODUCTION_NONE;
    }

    private static SmithingChoice bestGearMoneySmithingChoice(Player player, int barItemId) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        int availableBars = AgentToolService.countInventoryItem(player, barItemId);
        SmithingChoice best = null;
        for (SmithingChoice choice : AgentSmithingPlanner.smithableItems(smithingLevel, barItemId, availableBars, "")) {
            if (!isGearMoneyProductItem(choice.getItemId())) {
                continue;
            }
            if (best == null || isBetterGearMoneySmithingChoice(choice, best, availableBars)) {
                best = choice;
            }
        }
        return best;
    }

    private static boolean isBetterGearMoneySmithingChoice(SmithingChoice candidate, SmithingChoice current,
            int availableBars) {
        return isBetterGearMoneySmithingItem(candidate.getItemId(), current.getItemId(), availableBars);
    }

    static boolean isBetterGearMoneySmithingItem(int candidateItemId, int currentItemId, int availableBars) {
        int candidateBatchCoins = estimatedGearMoneySmithingBatchSellCoins(candidateItemId, availableBars);
        int currentBatchCoins = estimatedGearMoneySmithingBatchSellCoins(currentItemId, availableBars);
        if (candidateBatchCoins != currentBatchCoins) {
            return candidateBatchCoins > currentBatchCoins;
        }

        int candidateSellCoins = estimatedGearMoneySellCoins(candidateItemId);
        int currentSellCoins = estimatedGearMoneySellCoins(currentItemId);
        int candidateBars = Math.max(1, smithingProductBars(candidateItemId));
        int currentBars = Math.max(1, smithingProductBars(currentItemId));
        int candidateValuePerBar = candidateSellCoins * currentBars;
        int currentValuePerBar = currentSellCoins * candidateBars;
        if (candidateValuePerBar != currentValuePerBar) {
            return candidateValuePerBar > currentValuePerBar;
        }

        int candidateBatchXp = smithingProductXp(candidateItemId) * (availableBars / candidateBars);
        int currentBatchXp = smithingProductXp(currentItemId) * (availableBars / currentBars);
        if (candidateBatchXp != currentBatchXp) {
            return candidateBatchXp > currentBatchXp;
        }

        int candidateRequiredLevel = smithingProductRequiredLevel(candidateItemId);
        int currentRequiredLevel = smithingProductRequiredLevel(currentItemId);
        if (candidateRequiredLevel != currentRequiredLevel) {
            return candidateRequiredLevel > currentRequiredLevel;
        }
        if (candidateBars != currentBars) {
            return candidateBars > currentBars;
        }
        return candidateItemId > currentItemId;
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

    private static boolean shouldSmeltGearMoneyOres(Player player, int barItemId, boolean liquidatingForCombat) {
        int possibleBars = smeltableGearMoneyBars(player, barItemId);
        return shouldSmeltGearMoneyOres(possibleBars, player.getItemAssistant().freeSlots(),
                isAlKharidSideForGearMoney(player.absX, player.absY), liquidatingForCombat);
    }

    static boolean shouldSmeltGearMoneyOres(int possibleBars, int freeSlots, boolean onFurnaceSide) {
        return shouldSmeltGearMoneyOres(possibleBars, freeSlots, onFurnaceSide, false);
    }

    static boolean shouldSmeltGearMoneyOres(int possibleBars, int freeSlots, boolean onFurnaceSide,
            boolean liquidatingForCombat) {
        if (possibleBars <= 0) {
            return false;
        }
        return liquidatingForCombat
                || onFurnaceSide && possibleBars >= MIN_BARS_BEFORE_SMITHING
                || freeSlots <= MIN_FREE_SLOTS_BEFORE_BANKING
                || possibleBars >= MIN_ORE_SETS_BEFORE_SMELTING;
    }

    private static int smithingProductBars(int itemId) {
        SmithingData data = SmithingData.forId(itemId);
        return data == null ? 0 : data.getAmount();
    }

    private static int smithingProductXp(int itemId) {
        SmithingData data = SmithingData.forId(itemId);
        return data == null ? 0 : data.getXp();
    }

    private static int smithingProductRequiredLevel(int itemId) {
        SmithingData data = SmithingData.forId(itemId);
        return data == null ? 0 : data.getLvl();
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

    private static PickaxeTarget nextPickaxeUpgrade(Player player) {
        int miningLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.MINING]);
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        int currentBestTier = bestOwnedPickaxeTier(player);
        int itemId = recommendedPickaxeUpgradeId(miningLevel, currentBestTier, spendableCoins);
        return itemId <= 0 ? null : pickaxeTargetByItemId(itemId);
    }

    static int recommendedPickaxeUpgradeId(int miningLevel, int currentBestTier, int spendableCoins) {
        if (currentBestTier <= 0) {
            PickaxeTarget starter = pickaxeTargetByItemId(BRONZE_PICKAXE);
            return starter != null && starter.requiredMiningLevel <= miningLevel
                    && starter.estimatedPrice <= spendableCoins ? starter.itemId : -1;
        }
        PickaxeTarget best = null;
        for (PickaxeTarget target : PICKAXE_TARGETS) {
            if (target.tier <= currentBestTier || target.requiredMiningLevel > miningLevel
                    || target.estimatedPrice > spendableCoins) {
                continue;
            }
            if (best == null || target.tier > best.tier) {
                best = target;
            }
        }
        return best == null ? -1 : best.itemId;
    }

    private static PickaxeTarget pickaxeTargetByItemId(int itemId) {
        for (PickaxeTarget target : PICKAXE_TARGETS) {
            if (target.itemId == itemId) {
                return target;
            }
        }
        return null;
    }

    private static int bestOwnedPickaxeTier(Player player) {
        int best = 0;
        for (int pickaxeId : PICKAXE_ITEM_IDS) {
            if ((AgentToolService.countInventoryItem(player, pickaxeId) > 0
                    || AgentToolService.countBankItem(player, pickaxeId) > 0)
                    && canUsePickaxe(player, pickaxeId)) {
                best = Math.max(best, pickaxeTier(pickaxeId));
            }
        }
        return best;
    }

    private static int bestCarriedUsablePickaxeTier(Player player) {
        int best = 0;
        for (int pickaxeId : PICKAXE_ITEM_IDS) {
            if (AgentToolService.countInventoryItem(player, pickaxeId) > 0
                    && canUsePickaxe(player, pickaxeId)) {
                best = Math.max(best, pickaxeTier(pickaxeId));
            }
        }
        return best;
    }

    static int pickaxeTier(int pickaxeId) {
        for (int i = 0; i < PICKAXE_ITEM_IDS.length; i++) {
            if (PICKAXE_ITEM_IDS[i] == pickaxeId) {
                return i + 1;
            }
        }
        return 0;
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
        return gearMoneyOreForMiningLevel(miningLevel, smithingLevel, copperCount, tinCount, 0, 0);
    }

    static String gearMoneyOreForMiningLevel(int miningLevel, int smithingLevel, int copperCount, int tinCount,
            int ironCount, int coalCount) {
        if (miningLevel >= 30 && smithingLevel >= STEEL_SMELTING_SMITHING_LEVEL) {
            return gearMoneySteelOreForCounts(ironCount, coalCount);
        }
        if (miningLevel >= 15 && smithingLevel >= IRON_SMELTING_SMITHING_LEVEL) {
            return "iron";
        }
        return copperCount <= tinCount ? "copper" : "tin";
    }

    static String gearMoneySteelOreForCounts(int ironCount, int coalCount) {
        if (ironCount <= 0) {
            return "iron";
        }
        return coalCount < ironCount * STEEL_COAL_PER_BAR ? "coal" : "iron";
    }

    static String gearMoneyMineLandmark(String ore) {
        return "coal".equals(ore) ? "varrock east coal mine" : "varrock east mine";
    }

    static String gearMoneyOreForRouteSafety(String ore, int inventoryFood, int currentHitpoints,
            int maxHitpoints) {
        if ("coal".equals(ore) && shouldAvoidCoalGearMoneyMining(inventoryFood, currentHitpoints, maxHitpoints)) {
            return "iron";
        }
        return ore;
    }

    static boolean shouldAvoidCoalGearMoneyMining(int inventoryFood, int currentHitpoints, int maxHitpoints) {
        int safeHitpoints = Math.max(1, (maxHitpoints * 2) / 3);
        return inventoryFood < COAL_ROUTE_MIN_FOOD || currentHitpoints <= safeHitpoints;
    }

    static boolean isStaleMovementWait(int currentX, int currentY, int lastMovingX, int lastMovingY,
            int movingWaitSteps) {
        return currentX == lastMovingX && currentY == lastMovingY && movingWaitSteps >= MAX_MOVING_WAIT_STEPS;
    }

    static boolean isExceededMovementWait(int movingWaitSteps) {
        return movingWaitSteps >= MAX_MOVING_WAIT_STEPS;
    }

    static boolean shouldDeferPickaxeRoute(int noMoveAttempts) {
        return noMoveAttempts >= MAX_PICKAXE_ROUTE_NO_MOVE_ATTEMPTS;
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

    private static String supplyBankLandmark(Player player, CombatGoal goal) {
        return supplyBankLandmark(goal == null ? null : goal.area, player.absX, player.absY,
                goal != null && goal.restockingFood);
    }

    static String supplyBankLandmark(String trainingArea, int x, int y, boolean restockingFood) {
        if (x >= 3230 && x <= 3310 && y >= 3300 && y < 3425) {
            return "varrock east bank";
        }
        if (restockingFood && x >= 3200 && x <= 3310 && y < 3425) {
            return "varrock east bank";
        }
        return supplyBankLandmark(trainingArea);
    }

    private static boolean isPlayerInCombat(Player player) {
        return hasActiveCombatThreat(player.npcIndex, player.underAttackBy, player.underAttackBy2);
    }

    static boolean hasActiveCombatThreat(int npcIndex, int underAttackBy, int underAttackBy2) {
        return npcIndex > 0 || underAttackBy > 0 || underAttackBy2 > 0;
    }

    private static JsonObject escapeCombatForNonCombatWork(Player player, String prefix, String safeLandmark) {
        int maxHitpoints = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.HITPOINTS]);
        int eatAt = Math.max(3, maxHitpoints / 2);
        int retreatAt = AgentCombatPlanner.retreatAtHitpoints(maxHitpoints);
        if (player.playerLevel[Constants.HITPOINTS] <= eatAt && AgentToolService.countInventoryFood(player) > 0) {
            JsonObject result = AgentToolService.handle(player, "eat_best_food", new JsonObject());
            String message = getString(result, "message", "Ate food.");
            result.addProperty("message", prefix + ": ate food before escaping combat: " + message);
            return result;
        }
        if (shouldRetreatNonCombatThreatForFood(player.playerLevel[Constants.HITPOINTS], maxHitpoints,
                AgentToolService.countInventoryFood(player), retreatAt)) {
            JsonObject localRetreat = retreatWestFromVarrockCoalDanger(player, prefix);
            if (localRetreat != null) {
                return localRetreat;
            }
            JsonObject result = travelTo(player, safeLandmark);
            String message = getString(result, "message", "Walking to safety.");
            result.addProperty("message", prefix
                    + ": out of food during non-combat work; retreating before clearing attacker: " + message);
            return result;
        }
        int attackerIndex = activeCombatNpcIndex(player);
        if (attackerIndex > 0 && player.playerLevel[Constants.HITPOINTS] > retreatAt) {
            JsonObject attackArgs = new JsonObject();
            attackArgs.addProperty("npcIndex", attackerIndex);
            JsonObject result = AgentToolService.handle(player, "attack_npc", attackArgs);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                String message = getString(result, "message", "Clearing current combat threat.");
                result.addProperty("message", prefix + ": clearing attacker before non-combat work: " + message);
                return result;
            }
        }
        JsonObject result = travelTo(player, safeLandmark);
        String message = getString(result, "message", "Walking to safety.");
        result.addProperty("message", prefix + ": escaping combat before non-combat work: " + message);
        return result;
    }

    static boolean shouldRetreatNonCombatThreatForFood(int currentHitpoints, int maxHitpoints, int inventoryFood,
            int retreatAt) {
        int noFoodRetreatAt = Math.max(retreatAt + 4, Math.max(3, (maxHitpoints * 2) / 3));
        return inventoryFood <= 0 && currentHitpoints <= noFoodRetreatAt;
    }

    private static JsonObject retreatWestFromVarrockCoalDanger(Player player, String prefix) {
        int[] target = varrockCoalMineRetreatTarget(player.absX, player.absY);
        if (target == null) {
            return null;
        }
        String routeDescription = isVarrockCoalMineDangerRetreatTile(player.absX, player.absY)
                ? "stepping west out of the coal scorpion pocket"
                : "following the west-side road north away from the coal scorpions";
        JsonObject result = AgentToolService.handle(player, "walk_to_tile",
                walkTileArgs(target[0], target[1], player.heightLevel));
        String message = getString(result, "message", "Walking away from the coal mine scorpions.");
        result.addProperty("message", prefix + ": " + routeDescription + " before pathing to bank: " + message);
        return result;
    }

    static int[] varrockCoalMineRetreatTarget(int x, int y) {
        if (isVarrockCoalMineDangerRetreatTile(x, y)) {
            return new int[] { VARROCK_COAL_WEST_ESCAPE_X, varrockCoalMineWestRetreatY(y) };
        }
        if (isVarrockCoalMineEscapeCorridor(x, y)) {
            return new int[] { VARROCK_COAL_SAFE_ROAD_X, VARROCK_COAL_SAFE_ROAD_Y };
        }
        return null;
    }

    static boolean isVarrockCoalMineDangerRetreatTile(int x, int y) {
        return x >= VARROCK_COAL_DANGER_MIN_X && x <= VARROCK_COAL_DANGER_MAX_X
                && y >= VARROCK_COAL_DANGER_MIN_Y && y <= VARROCK_COAL_DANGER_MAX_Y;
    }

    static int varrockCoalMineWestRetreatY(int y) {
        if (y < VARROCK_COAL_WEST_ESCAPE_MIN_Y) {
            return VARROCK_COAL_WEST_ESCAPE_MIN_Y;
        }
        if (y > VARROCK_COAL_WEST_ESCAPE_MAX_Y) {
            return VARROCK_COAL_WEST_ESCAPE_MAX_Y;
        }
        return y;
    }

    static boolean isVarrockCoalMineEscapeCorridor(int x, int y) {
        return x >= VARROCK_COAL_ESCAPE_CORRIDOR_MIN_X && x <= VARROCK_COAL_ESCAPE_CORRIDOR_MAX_X
                && y >= VARROCK_COAL_ESCAPE_CORRIDOR_MIN_Y && y <= VARROCK_COAL_ESCAPE_CORRIDOR_MAX_Y;
    }

    private static int activeCombatNpcIndex(Player player) {
        return activeCombatNpcIndex(player.npcIndex, player.killingNpcIndex, player.underAttackBy, player.underAttackBy2);
    }

    static int activeCombatNpcIndex(int npcIndex, int killingNpcIndex, int underAttackBy, int underAttackBy2) {
        if (npcIndex > 0) {
            return npcIndex;
        }
        if (killingNpcIndex > 0) {
            return killingNpcIndex;
        }
        if (underAttackBy2 > 0) {
            return underAttackBy2;
        }
        return underAttackBy > 0 ? underAttackBy : -1;
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

    private static JsonObject jsonObject(JsonObject object, String name) {
        if (object != null && object.has(name) && object.get(name).isJsonObject()) {
            return object.get(name).getAsJsonObject();
        }
        return null;
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

    private static class PickaxeTarget {
        private final int itemId;
        private final int requiredMiningLevel;
        private final int tier;
        private final int estimatedPrice;
        private final String landmarkName;
        private final String shopName;

        private PickaxeTarget(int itemId, int requiredMiningLevel, int tier, int estimatedPrice) {
            this(itemId, requiredMiningLevel, tier, estimatedPrice, "pickaxe shop", "pickaxe");
        }

        private PickaxeTarget(int itemId, int requiredMiningLevel, int tier, int estimatedPrice,
                String landmarkName, String shopName) {
            this.itemId = itemId;
            this.requiredMiningLevel = requiredMiningLevel;
            this.tier = tier;
            this.estimatedPrice = estimatedPrice;
            this.landmarkName = landmarkName;
            this.shopName = shopName;
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
        private int hitpointsLevel;
        private int miningLevel;
        private int smithingLevel;
        private int lastLoggedAttackLevel;
        private int lastLoggedStrengthLevel;
        private int lastLoggedDefenceLevel;
        private int lastLoggedHitpointsLevel;
        private int lastLoggedMiningLevel;
        private int lastLoggedSmithingLevel;
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
        private int movingWaitSteps;
        private int lastMovingX = Integer.MIN_VALUE;
        private int lastMovingY = Integer.MIN_VALUE;
        private int movingStallRecoveries;
        private int pickaxeRouteItemId;
        private int pickaxeRouteX = Integer.MIN_VALUE;
        private int pickaxeRouteY = Integer.MIN_VALUE;
        private int pickaxeRouteNoMoveAttempts;
        private int pickaxeRouteDeferrals;
        private int deferredPickaxeItemId;
        private int deferredPickaxeUntilAction;
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
        private int lastLoggedMovingStallRecoveries;
        private int lastLoggedPickaxeRouteDeferrals;
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
            hitpointsLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.HITPOINTS]);
            miningLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.MINING]);
            smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
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
            clearGearMoney();
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

        private boolean isPickaxeUpgradeDeferred(PickaxeTarget target) {
            return target != null && deferredPickaxeItemId == target.itemId
                    && actionsRun < deferredPickaxeUntilAction;
        }

        private boolean deferPickaxeUpgradeIfRouteIsStuck(Player player, PickaxeTarget target) {
            if (target == null) {
                clearPickaxeRouteAttempts();
                return false;
            }
            if (pickaxeRouteItemId != target.itemId || pickaxeRouteX != player.absX
                    || pickaxeRouteY != player.absY) {
                pickaxeRouteItemId = target.itemId;
                pickaxeRouteX = player.absX;
                pickaxeRouteY = player.absY;
                pickaxeRouteNoMoveAttempts = 1;
                return false;
            }
            pickaxeRouteNoMoveAttempts++;
            if (!shouldDeferPickaxeRoute(pickaxeRouteNoMoveAttempts)) {
                return false;
            }
            deferredPickaxeItemId = target.itemId;
            deferredPickaxeUntilAction = actionsRun + PICKAXE_ROUTE_DEFER_ACTIONS;
            pickaxeRouteDeferrals++;
            clearPickaxeRouteAttempts();
            return true;
        }

        private void deferPickaxeUpgrade(PickaxeTarget target) {
            if (target == null) {
                clearPickaxeRouteAttempts();
                return;
            }
            deferredPickaxeItemId = target.itemId;
            deferredPickaxeUntilAction = actionsRun + PICKAXE_ROUTE_DEFER_ACTIONS;
            pickaxeRouteDeferrals++;
            clearPickaxeRouteAttempts();
        }

        private void clearPickaxeRouteAttempts() {
            pickaxeRouteItemId = 0;
            pickaxeRouteX = Integer.MIN_VALUE;
            pickaxeRouteY = Integer.MIN_VALUE;
            pickaxeRouteNoMoveAttempts = 0;
        }

        private boolean shouldKeepWaitingForMovement(Player player) {
            movingWaitSteps++;
            if (isExceededMovementWait(movingWaitSteps)) {
                return false;
            }
            if (lastMovingX != player.absX || lastMovingY != player.absY) {
                lastMovingX = player.absX;
                lastMovingY = player.absY;
                return true;
            }
            return !isStaleMovementWait(player.absX, player.absY, lastMovingX, lastMovingY, movingWaitSteps);
        }

        private void recoverFromMovementStall(Player player) {
            movingWaitSteps = 0;
            lastMovingX = player.absX;
            lastMovingY = player.absY;
            movingStallRecoveries++;
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
            if (actionsRun == 1 || actionsRun % GOAL_PROGRESS_LOG_INTERVAL_ACTIONS == 0) {
                rememberLoggedLevels();
                rememberLoggedSupplies();
                return true;
            }
            if (attackLevel != lastLoggedAttackLevel || strengthLevel != lastLoggedStrengthLevel
                    || defenceLevel != lastLoggedDefenceLevel || hitpointsLevel != lastLoggedHitpointsLevel
                    || miningLevel != lastLoggedMiningLevel || smithingLevel != lastLoggedSmithingLevel) {
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
                    || gearMoneyCoinsEarned != lastLoggedGearMoneyCoinsEarned
                    || movingStallRecoveries != lastLoggedMovingStallRecoveries
                    || pickaxeRouteDeferrals != lastLoggedPickaxeRouteDeferrals) {
                rememberLoggedSupplies();
                return true;
            }
            return false;
        }

        private void rememberLoggedLevels() {
            lastLoggedAttackLevel = attackLevel;
            lastLoggedStrengthLevel = strengthLevel;
            lastLoggedDefenceLevel = defenceLevel;
            lastLoggedHitpointsLevel = hitpointsLevel;
            lastLoggedMiningLevel = miningLevel;
            lastLoggedSmithingLevel = smithingLevel;
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
            lastLoggedMovingStallRecoveries = movingStallRecoveries;
            lastLoggedPickaxeRouteDeferrals = pickaxeRouteDeferrals;
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
            json.addProperty("hitpointsLevel", hitpointsLevel);
            json.addProperty("miningLevel", miningLevel);
            json.addProperty("smithingLevel", smithingLevel);
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
            json.addProperty("movingStallRecoveries", movingStallRecoveries);
            json.addProperty("pickaxeRouteDeferrals", pickaxeRouteDeferrals);
            if (deferredPickaxeItemId > 0 && actionsRun < deferredPickaxeUntilAction) {
                json.addProperty("deferredPickaxeItemId", deferredPickaxeItemId);
                json.addProperty("deferredPickaxeUntilAction", deferredPickaxeUntilAction);
            }
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
