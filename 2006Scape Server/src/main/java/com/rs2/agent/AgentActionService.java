package com.rs2.agent;

import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.UUID;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.agent.AgentSmithingPlanner.SmithingChoice;
import com.rs2.game.content.quests.QuestAssistant;
import com.rs2.game.content.skills.SkillHandler;
import com.rs2.game.content.skills.smithing.SmithingData;
import com.rs2.game.content.traveling.CarpetTravel;
import com.rs2.game.npcs.Npc;
import com.rs2.game.npcs.NpcHandler;
import com.rs2.game.objects.impl.OtherObjects;
import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import com.rs2.game.players.PlayerSave;
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
    private static final int SHANTAY_PASS = 1854;
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
    private static final int CHAMPIONS_GUILD_QUEST_POINTS = Math.min(32, QuestAssistant.MAXIMUM_QUESTPOINTS);
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
            1153, 1157, 1159, 1161, 1163,
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
    private static final int MIN_FREE_LOOT_SLOTS_BEFORE_SUPPLY_BANKING = 2;
    private static final int MIN_FREE_SLOTS_AFTER_TARGET_ACQUISITION = 8;
    private static final int SUPPLY_COUNT_BEFORE_BANKING = 18;
    private static final int ACCOUNT_STORAGE_COUNT_BEFORE_BANKING = 1;
    private static final int MIN_FOOD_BEFORE_RESTOCK = 3;
    private static final int MIN_RAW_FOOD_BEFORE_COOKING = 8;
    private static final int DESIRED_LOW_LEVEL_FOOD = 10;
    private static final int DESIRED_HIGH_LEVEL_FOOD = 18;
    private static final int GEAR_CHECK_INTERVAL_ACTIONS = 80;
    private static final int GOAL_PROGRESS_LOG_INTERVAL_ACTIONS = 20;
    private static final int MAX_MOVING_WAIT_STEPS = 20;
    private static final int MAX_STATIONARY_MOVING_WAIT_STEPS = 4;
    private static final int MAX_ROUTE_OSCILLATION_REVERSALS = 2;
    private static final int MAX_ROUTE_STALE_STEPS = 4;
    private static final int MAX_MOVEMENT_BATCH_STALE_TICKS = 8;
    private static final int MAX_MOVEMENT_BATCH_OSCILLATION_REVERSALS = 3;
    private static final int MAX_PICKAXE_ROUTE_NO_MOVE_ATTEMPTS = 8;
    private static final int PICKAXE_ROUTE_DEFER_ACTIONS = 200;
    private static final int MIN_GEAR_MONEY_ITEMS_BEFORE_SELLING = 27;
    private static final int MIN_STACKED_GEAR_MONEY_PRODUCTS_BEFORE_SALE = 8;
    private static final int MIN_PROCESSED_BARS_BEFORE_SELLING = 4;
    private static final int MIN_BARS_BEFORE_SMITHING = 8;
    private static final int MIN_ORE_SETS_BEFORE_SMELTING = 24;
    private static final int MAX_GEAR_MONEY_TARGET_BATCH_BARS = 10000;
    private static final int GEAR_MONEY_LOCAL_MINING_SCAN_DISTANCE = 8;
    private static final int MAX_LOCAL_MINING_RESPAWN_WAITS = 3;
    private static final int COAL_ROUTE_MIN_FOOD = MIN_FOOD_BEFORE_RESTOCK + 1;
    private static final int GEAR_MONEY_FOOD_BUFFER = COAL_ROUTE_MIN_FOOD;
    private static final int IRON_SMELTING_SMITHING_LEVEL = 15;
    private static final int STEEL_SMELTING_SMITHING_LEVEL = 20;
    private static final int STEEL_COAL_PER_BAR = 2;
    private static final int EXPENSIVE_WEAPON_UPGRADE_PRICE = 5000;
    private static final int STRONG_ENOUGH_WEAPON_TIER = 4;
    private static final int MIN_STRENGTH_BEFORE_RUNE_WEAPON_SAVINGS = 31;
    private static final int AL_KHARID_GATE_TOLL = 10;
    private static final int SHANTAY_NPC = 836;
    private static final int SHANTAY_GATE_OBJECT = 4031;
    private static final int SHANTAY_PASS_PRICE = 5;
    private static final int NARDAH_CARPET_FARE = 200;
    private static final int NARDAH_TRANSIT_COST = SHANTAY_PASS_PRICE + NARDAH_CARPET_FARE;
    private static final int NARDAH_RUG_X = 3401;
    private static final int NARDAH_RUG_Y = 2915;
    private static final int POLLNIVNEACH_RUG_X = 3347;
    private static final int POLLNIVNEACH_RUG_Y = 2944;
    private static final int SHANTAY_RUG_RETURN_X = 3308;
    private static final int SHANTAY_RUG_RETURN_Y = 3108;
    private static final int SHANTAY_GATE_SOUTH_X = 3304;
    private static final int SHANTAY_GATE_SOUTH_Y = 3115;
    private static final int AL_KHARID_HAMMER_AND_GATE_COIN_BUFFER = 25;
    private static final int KEBAB_SHOP_PRICE = 3;
    private static final int KEBAB_RESTOCK_COIN_FLOAT = 120;
    private static final String SHOP_FOOD_MONEY_TARGET_NAME = "target-sized kebab restock";
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
    private static final int[] GEAR_MONEY_RAW_MATERIAL_ITEM_IDS = {
            COPPER_ORE, TIN_ORE, IRON_ORE, COAL
    };
    private static final int[] TARGET_ACQUISITION_RAW_LIQUIDATION_ITEM_IDS = {
            KEBAB
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
    private static final GearTarget[] HELM_GEAR_TARGETS = {
            new GearTarget(1153, 1, 1, "helmet shop", "helmet", 154),
            new GearTarget(1157, 5, 2, "helmet shop", "helmet", 550),
            new GearTarget(1159, 20, 3, "helmet shop", "helmet", 1430),
            new GearTarget(1161, 30, 4, "helmet shop", "helmet", 3520),
            new GearTarget(1163, 40, 5, "oziach rune armour", "oziach", 35200)
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
        final boolean xs = AgentToolService.isXsTool(tool);
        final String effectiveTool = AgentToolService.baseToolName(tool);
        if ("walk_to_tile_until_arrived".equals(effectiveTool)) {
            JsonObject result = walkToTileUntilArrived(token, arguments == null ? new JsonObject() : arguments);
            return xs ? AgentToolService.compactXsResult(effectiveTool, result) : result;
        }
        if ("travel_to_landmark_until_arrived".equals(effectiveTool)) {
            JsonObject result = travelToLandmarkUntilArrived(token, arguments == null ? new JsonObject() : arguments);
            return xs ? AgentToolService.compactXsResult(effectiveTool, result) : result;
        }
        if ("mine_ore_until_inventory_full".equals(effectiveTool)) {
            JsonObject result = mineOreUntilInventoryFull(token, arguments == null ? new JsonObject() : arguments);
            return xs ? AgentToolService.compactXsResult(effectiveTool, result) : result;
        }
        if ("chop_tree_until_inventory_full".equals(effectiveTool)) {
            JsonObject result = chopTreeUntilInventoryFull(token, arguments == null ? new JsonObject() : arguments);
            return xs ? AgentToolService.compactXsResult(effectiveTool, result) : result;
        }
        if ("fletch_logs_until_inventory_empty".equals(effectiveTool)) {
            JsonObject result = fletchLogsUntilInventoryEmpty(token, arguments == null ? new JsonObject() : arguments);
            return xs ? AgentToolService.compactXsResult(effectiveTool, result) : result;
        }
        if ("wait_until_idle".equals(effectiveTool)) {
            JsonObject result = waitUntilIdle(token, arguments == null ? new JsonObject() : arguments);
            return xs ? AgentToolService.compactXsResult(effectiveTool, result) : result;
        }
        if ("wait_ticks".equals(effectiveTool)) {
            int ticks = Math.max(1, Math.min(25, getInt(arguments, "ticks", 1)));
            final long submittedTick = serverTick.get();
            final long targetTick = submittedTick + ticks;
            long timeoutMs = Math.max(ACTION_TIMEOUT_MS, (long) (ticks + 2) * Constants.CYCLE_TIME);
            JsonObject result = submitForTick(targetTick, new Callable<JsonObject>() {
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
            return xs ? AgentToolService.compactXsResult(effectiveTool, result) : result;
        }
        if ("start_combat_goal".equals(effectiveTool) || "observe_goal".equals(effectiveTool)
                || "stop_goal".equals(effectiveTool)) {
            JsonObject result = submitOnGameTick(token, new Callable<JsonObject>() {
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
                    if ("start_combat_goal".equals(effectiveTool)) {
                        return startCombatGoal(session, player, safeArguments);
                    }
                    if ("stop_goal".equals(effectiveTool)) {
                        return stopGoal(session, player);
                    }
                    return observeGoal(player);
                }
            });
            return xs ? AgentToolService.compactXsResult(effectiveTool, result) : result;
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
                JsonObject safeArguments = arguments == null ? new JsonObject() : arguments;
                JsonObject result = AgentToolService.handle(player, effectiveTool, safeArguments);
                recordObjectTransition(session, effectiveTool, safeArguments, result);
                return xs ? AgentToolService.compactXsResult(effectiveTool, result, player, safeArguments) : result;
            }
        });
    }

    private JsonObject walkToTileUntilArrived(final String token, final JsonObject arguments) {
        int maxTicks = Math.max(1, Math.min(250, getInt(arguments, "maxTicks", 120)));
        final int x = getInt(arguments, "x", -1);
        final int y = getInt(arguments, "y", -1);
        final int height = getInt(arguments, "height", 0);
        final int stopDistance = Math.max(0, Math.min(20, getInt(arguments, "stopDistance", 0)));
        final boolean stopOnCombat = getBoolean(arguments, "stopOnCombat", true);
        final boolean stopOnStall = getBoolean(arguments, "stopOnStall", true);
        if (x < 0 || y < 0) {
            return AgentToolService.failure("x and y are required.");
        }
        MovementBatchTrace trace = new MovementBatchTrace("walk_to_tile_until_arrived", arguments,
                serverTick.get());
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
            AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
            trace.record(session, tick + 1, serverTick.get(), lastResult, "tick");
            if (!isSuccess(lastResult)) {
                return finishMovementBatch(trace, session, arguments, lastResult, "blocked", tick + 1);
            }
            if (getBoolean(lastResult, "complete", false)) {
                return finishMovementBatch(trace, session, arguments, lastResult, "arrived", tick + 1);
            }
            JsonObject player = resultPlayer(lastResult);
            if (player != null && getBoolean(player, "isDead", false)) {
                return finishMovementBatch(trace, session, arguments, lastResult, "player_dead", tick + 1);
            }
            if (stopOnCombat && player != null && getBoolean(player, "isInCombat", false)) {
                JsonObject stopped = AgentToolService.failure("Unexpected combat during movement batch.");
                if (player != null) {
                    stopped.add("player", player);
                }
                return finishMovementBatch(trace, session, arguments, stopped, "unexpected_combat", tick + 1);
            }
            if (stopOnStall && trace.isStalled()) {
                JsonObject stopped = AgentToolService.failure("Movement batch stalled at "
                        + trace.currentTileText() + ".");
                if (player != null) {
                    stopped.add("player", player);
                }
                return finishMovementBatch(trace, session, arguments, stopped, "stalled", tick + 1);
            }
            if (stopOnStall && trace.isOscillating()) {
                JsonObject stopped = AgentToolService.failure("Movement batch oscillated around "
                        + trace.currentTileText() + ".");
                if (player != null) {
                    stopped.add("player", player);
                }
                return finishMovementBatch(trace, session, arguments, stopped, "oscillation", tick + 1);
            }
        }
        AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
        return finishMovementBatch(trace, session, arguments,
                lastResult == null ? AgentToolService.failure("No walk action was attempted.") : lastResult,
                "max_ticks_reached", maxTicks);
    }

    private JsonObject travelToLandmarkUntilArrived(final String token, final JsonObject arguments) {
        int maxTicks = Math.max(1, Math.min(250, getInt(arguments, "maxTicks", 120)));
        final boolean stopOnCombat = getBoolean(arguments, "stopOnCombat", true);
        final boolean stopOnStall = getBoolean(arguments, "stopOnStall", true);
        MovementBatchTrace trace = new MovementBatchTrace("travel_to_landmark_until_arrived", arguments,
                serverTick.get());
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
            AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
            trace.record(session, tick + 1, serverTick.get(), lastResult, "tick");
            if (!isSuccess(lastResult)) {
                return finishMovementBatch(trace, session, arguments, lastResult, "blocked", tick + 1);
            }
            if (getBoolean(lastResult, "complete", false)) {
                return finishMovementBatch(trace, session, arguments, lastResult, "arrived", tick + 1);
            }
            JsonObject player = resultPlayer(lastResult);
            if (player != null && getBoolean(player, "isDead", false)) {
                return finishMovementBatch(trace, session, arguments, lastResult, "player_dead", tick + 1);
            }
            if (stopOnCombat && player != null && getBoolean(player, "isInCombat", false)) {
                JsonObject stopped = AgentToolService.failure("Unexpected combat during landmark travel.");
                if (player != null) {
                    stopped.add("player", player);
                }
                return finishMovementBatch(trace, session, arguments, stopped, "unexpected_combat", tick + 1);
            }
            if (stopOnStall && trace.isStalled()) {
                JsonObject stopped = AgentToolService.failure("Landmark travel stalled at "
                        + trace.currentTileText() + ".");
                if (player != null) {
                    stopped.add("player", player);
                }
                return finishMovementBatch(trace, session, arguments, stopped, "stalled", tick + 1);
            }
            if (stopOnStall && trace.isOscillating()) {
                JsonObject stopped = AgentToolService.failure("Landmark travel oscillated around "
                        + trace.currentTileText() + ".");
                if (player != null) {
                    stopped.add("player", player);
                }
                return finishMovementBatch(trace, session, arguments, stopped, "oscillation", tick + 1);
            }
        }
        AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
        return finishMovementBatch(trace, session, arguments,
                lastResult == null ? AgentToolService.failure("No travel action was attempted.") : lastResult,
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

    private JsonObject fletchLogsUntilInventoryEmpty(final String token, final JsonObject arguments) {
        int maxTicks = Math.max(1, Math.min(250, getInt(arguments, "maxTicks", 120)));
        final int targetFletchingLevel = getInt(arguments, "targetFletchingLevel",
                getInt(arguments, "targetLevel", -1));
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
                    if (targetFletchingLevel > 0 && player.playerLevel[Constants.FLETCHING] >= targetFletchingLevel) {
                        return AgentToolService.observeState(player);
                    }
                    if (AgentToolService.countInventoryFletchableLogs(player) < 1) {
                        return AgentToolService.observeState(player);
                    }
                    if (player.playerIsFletching || player.isFletching || player.isMoving) {
                        return AgentToolService.observeState(player);
                    }
                    return AgentToolService.handle(player, "fletch_logs", arguments);
                }
            });
            if (!isSuccess(lastResult)) {
                return addBatchStatus(lastResult, "blocked", tick + 1);
            }
            JsonObject player = playerObject(lastResult);
            if (player != null && getBoolean(player, "isDead", false)) {
                return addBatchStatus(lastResult, "player_dead", tick + 1);
            }
            AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
            Player livePlayer = session == null ? null : session.getPlayer();
            if (livePlayer != null && targetFletchingLevel > 0
                    && livePlayer.playerLevel[Constants.FLETCHING] >= targetFletchingLevel) {
                return addBatchStatus(lastResult, "target_level_reached", tick + 1);
            }
            if (livePlayer != null && AgentToolService.countInventoryFletchableLogs(livePlayer) < 1
                    && !livePlayer.playerIsFletching && !livePlayer.isFletching) {
                return addBatchStatus(lastResult, "inventory_empty", tick + 1);
            }
        }
        return addBatchStatus(lastResult == null ? AgentToolService.failure("No fletching action was attempted.") : lastResult,
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
            try {
                processCombatGoal(goal);
            } catch (Throwable ex) {
                blockCombatGoalForException(goal, ex);
            }
        }
    }

    private void processCombatGoal(CombatGoal goal) {
        if (goal.isTerminal()) {
            return;
        }
        AgentSession session = AgentSessionManager.INSTANCE.getSession(goal.token);
        Player player = session == null ? findOnlineGoalPlayer(goal) : session.getPlayer();
        if (player == null) {
            goal.block("Agent session ended or player went offline.");
            logGoalEvent(goalLogSession(goal, session, null), "goal_blocked", goal, null);
            return;
        }
        session = goalLogSession(goal, session, player);
        if (player.isDead) {
            goal.block("Player death stopped the combat goal.");
            logGoalEvent(session, "goal_blocked", goal, null);
            return;
        }
        goal.ticksElapsed++;
        if (goal.shouldWaitForMiningClick()) {
            return;
        }
        if (goal.ticksElapsed - goal.lastStepTick < goal.stepIntervalTicks) {
            return;
        }
        goal.lastStepTick = goal.ticksElapsed;
        if (player.isMoving) {
            if (goal.shouldKeepWaitingForMovement(player)) {
                return;
            }
            player.resetWalkingQueue();
            player.isMoving = false;
            goal.recoverFromMovementStall(player);
        }
        if (goal.actionsRun >= goal.maxActions) {
            goal.block("Combat goal reached its max action limit before completion.");
            logGoalEventAndAutosave(player, session, "goal_blocked", goal, null);
            return;
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

        JsonObject result = runCombatGoalStep(player, goal, actionArguments);
        goal.actionsRun++;
        goal.lastResult = result;
        goal.updateLevels(player);
        goal.rememberPlanFromResult(result);
        goal.rememberMiningClickWait(result);
        goal.rememberLocalMiningRespawnWait(result);

        if (goal.targetReached()) {
            goal.complete("Attack, strength, and defence reached base " + goal.targetLevel + ".");
            logGoalEventAndAutosave(player, session, "goal_completed", goal, result);
        } else if (goal.recordRouteProgressAndShouldBlock(result)) {
            logGoalEventAndAutosave(player, session, "goal_blocked", goal, result);
        } else if (result == null || !result.has("success") || !result.get("success").getAsBoolean()) {
            String message = result == null ? "Combat goal step failed." : getString(result, "message", "Combat goal step failed.");
            if (isRecoverableGoalFailure(message)) {
                if (goal.shouldLogProgress()) {
                    logGoalEventAndAutosave(player, session, "goal_progress", goal, result);
                }
            } else {
                goal.block(message);
                logGoalEventAndAutosave(player, session, "goal_blocked", goal, result);
            }
        } else if (goal.shouldLogProgress()) {
            logGoalEventAndAutosave(player, session, "goal_progress", goal, result);
        }
    }

    private static Player findOnlineGoalPlayer(CombatGoal goal) {
        if (goal == null) {
            return null;
        }
        if (isValidPlayerIndex(goal.playerId)) {
            Player player = PlayerHandler.players[goal.playerId];
            if (isGoalPlayer(player, goal.playerId, goal.playerName)) {
                return player;
            }
        }
        for (int i = 0; i < PlayerHandler.players.length; i++) {
            Player player = PlayerHandler.players[i];
            if (isGoalPlayer(player, i, goal.playerName)) {
                return player;
            }
        }
        return null;
    }

    static boolean isGoalPlayer(Player player, int expectedPlayerId, String expectedPlayerName) {
        return player != null
                && !player.disconnected
                && player.isActive
                && expectedPlayerId >= 0
                && player.playerId == expectedPlayerId
                && expectedPlayerName != null
                && player.playerName != null
                && player.playerName.equalsIgnoreCase(expectedPlayerName);
    }

    private static boolean isValidPlayerIndex(int playerId) {
        return playerId >= 0 && playerId < PlayerHandler.players.length;
    }

    private static AgentSession goalLogSession(CombatGoal goal, AgentSession session, Player player) {
        if (session != null) {
            return session;
        }
        if (goal == null) {
            return null;
        }
        int playerId = player == null ? goal.playerId : player.playerId;
        String playerName = player == null ? goal.playerName : player.playerName;
        return new AgentSession(goal.token, goal.sessionId, playerId, playerName, goal.startedAt);
    }

    private void blockCombatGoalForException(CombatGoal goal, Throwable ex) {
        if (goal == null || goal.isTerminal()) {
            return;
        }
        String message = "Combat goal step crashed: " + ex.getClass().getSimpleName();
        if (ex.getMessage() != null && !ex.getMessage().trim().isEmpty()) {
            message += ": " + ex.getMessage().trim();
        }
        System.err.println(message);
        ex.printStackTrace();
        goal.block(message);
        AgentSession session = AgentSessionManager.INSTANCE.getSession(goal.token);
        Player player = session == null ? null : session.getPlayer();
        if (session != null) {
            JsonObject result = AgentToolService.failure(message);
            logGoalEventAndAutosave(player, session, "goal_blocked", goal, result);
        }
    }

    private void logGoalEventAndAutosave(Player player, AgentSession session, String event, CombatGoal goal, JsonObject result) {
        logGoalEvent(session, event, goal, result);
        autosaveGoalEvent(player, event);
    }

    private static void autosaveGoalEvent(Player player, String event) {
        if (player == null || !shouldAutosaveGoalEvent(event)) {
            return;
        }
        PlayerSave.saveGame(player);
    }

    static boolean shouldAutosaveGoalEvent(String event) {
        return "goal_progress".equals(event)
                || "goal_completed".equals(event)
                || "goal_blocked".equals(event);
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

        if (goal.bankingSupplies || shouldBankCombatSupplies(player, goal) || shouldStoreAccountItems(player, goal)) {
            goal.bankingSupplies = true;
            return bankCombatSuppliesStep(player, goal);
        }

        if (goal.gearingUp || shouldAcquireCombatGear(player, goal)) {
            goal.gearingUp = true;
            return acquireCombatGearStep(player, goal);
        }

        if (shouldAcquirePickaxeUpgrade(player, goal)) {
            return acquirePickaxeUpgradeStep(player, goal, nextPickaxeUpgrade(player));
        }

        if (goal.earningGearMoney || shouldEarnGearMoney(player, goal)) {
            goal.earningGearMoney = true;
            return earnGearMoneyStep(player, goal);
        }

        if (goal.restockingFood || shouldRestockFood(player, goal)) {
            goal.restockingFood = true;
            return restockFoodStep(player, goal);
        }

        JsonObject desertReturn = prepareDesertReturnTransit(player, goal.area);
        if (desertReturn != null) {
            String message = getString(desertReturn, "message", "returning from the desert.");
            desertReturn.addProperty("message", "Returning from desert before combat training: " + message);
            return desertReturn;
        }
        JsonObject gateToll = prepareAlKharidGateTollForCombat(player, goal);
        if (gateToll != null) {
            return gateToll;
        }

        if (shouldBankGearMoneyCarryoverBeforeCombat(countInventoryGearMoneyItems(player),
                goal.earningGearMoney, goal.gearingUp,
                shouldPrepareAlKharidGateTollForCombat(player.absX, player.absY,
                        AgentToolService.countInventoryItem(player, COINS), goal.area))) {
            return bankGearMoneyCarryoverBeforeCombatStep(player, goal);
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

        if (shouldCheckCarriedCombatGear(goal.actionsRun, countInventoryCombatGearItems(player))) {
            return AgentToolService.handle(player, "equip_best_items", new JsonObject());
        }
        return AgentToolService.handle(player, "train_combat", actionArguments);
    }

    private JsonObject bankCombatSuppliesStep(Player player, CombatGoal goal) {
        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            JsonObject result = travelTo(player, supplyBankLandmark(player, goal));
            String message = getString(result, "message", "Walking toward bank.");
            result.addProperty("message", "Banking combat supplies: " + message);
            return result;
        }

        int supplyCount = countInventoryCombatSupplies(player, goal);
        if (supplyCount > 0) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items",
                    combatSupplyArgs(0, player, goal));
            int depositedItems = depositedInventoryItems(result);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                goal.bankingSupplies = shouldStoreAccountItems(player, goal);
                if (depositedItems > 0) {
                    goal.bankTrips++;
                    goal.bankedSupplyItems += depositedItems;
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

    private JsonObject bankGearMoneyCarryoverBeforeCombatStep(Player player, CombatGoal goal) {
        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            JsonObject result = travelTo(player, supplyBankLandmark(player, goal));
            result.addProperty("message", "Banking leftover mining materials before combat: "
                    + getString(result, "message", "Walking toward bank."));
            return result;
        }

        JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", gearMoneyBatchBankArgs(player, goal));
        int depositedAmount = getInt(result, "depositedAmount", 0);
        if (result != null && result.has("success") && result.get("success").getAsBoolean()
                && depositedAmount > 0) {
            goal.accountStorageBankTrips++;
            goal.bankedAccountItems += depositedAmount;
        }
        result.addProperty("message", "Banked leftover mining materials before combat: "
                + getString(result, "message", "Deposited money-making materials."));
        return result;
    }

    private JsonObject prepareGearMoneySteelSmeltingInputs(Player player, GearTarget target, CombatGoal goal,
            boolean liquidatingForCombat, boolean processingBatchReady, boolean processingStarted) {
        if (!liquidatingForCombat && !processingBatchReady && !processingStarted) {
            return null;
        }
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        int carriedIronOre = AgentToolService.countInventoryItem(player, IRON_ORE);
        int carriedCoal = AgentToolService.countInventoryItem(player, COAL);
        int bankedIronOre = AgentToolService.countBankItem(player, IRON_ORE);
        int bankedCoal = AgentToolService.countBankItem(player, COAL);
        if (!shouldPrepareSteelSmeltingInputs(smithingLevel, carriedIronOre, carriedCoal, bankedIronOre,
                bankedCoal, player.getItemAssistant().freeSlots(), countInventoryProcessedGearMoneyBars(player),
                countInventoryGearMoneyProducts(player, goal), liquidatingForCombat, player.absX, player.absY,
                processingStarted)) {
            return null;
        }

        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            JsonObject result = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
            result.addProperty("message", "Earning gear money for " + target.itemName()
                    + ": returning to bank to pair iron ore with coal for higher-value steel.");
            return result;
        }

        int coalNeededForCarriedIron = steelCoalNeededForIron(carriedIronOre, carriedCoal);
        if (carriedIronOre > 0 && coalNeededForCarriedIron > 0
                && bankedCoal >= coalNeededForCarriedIron
                && player.getItemAssistant().freeSlots() >= coalNeededForCarriedIron) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(COAL, coalNeededForCarriedIron));
            result.addProperty("message", "Earning gear money: withdrew coal to smelt carried iron ore into steel.");
            return result;
        }

        if (carriedIronOre > 0 || carriedCoal > 0) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", gearMoneyBatchBankArgs(player, goal));
            result.addProperty("message", "Earning gear money for " + target.itemName()
                    + ": rebanking unbalanced iron/coal before withdrawing a steel smelting batch.");
            return result;
        }

        int targetSteelBars = targetSteelSmeltingBars(player.getItemAssistant().freeSlots(), bankedIronOre, bankedCoal);
        if (targetSteelBars <= 0) {
            return null;
        }
        if (carriedIronOre < targetSteelBars) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(IRON_ORE, targetSteelBars - carriedIronOre));
            result.addProperty("message", "Earning gear money: withdrew iron ore for a balanced steel smelting batch.");
            return result;
        }
        int targetCoal = targetSteelBars * STEEL_COAL_PER_BAR;
        if (carriedCoal < targetCoal) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(COAL, targetCoal - carriedCoal));
            result.addProperty("message", "Earning gear money: withdrew coal for a balanced steel smelting batch.");
            return result;
        }
        return null;
    }

    private JsonObject acquireCombatGearStep(Player player, CombatGoal goal) {
        GearTarget target = goal.gearTargetItemId > 0 ? gearTargetByItemId(goal.gearTargetItemId)
                : nextGearTarget(player);
        goal.lastGearAttemptAction = goal.actionsRun;
        if (target == null) {
            goal.clearGearTarget();
            return AgentToolService.success("Combat gear is already appropriate for the current levels.");
        }
        if (!isGearTargetAvailable(player, target)) {
            goal.clearGearTarget();
            return AgentToolService.success("Gearing up: " + target.itemName()
                    + " is not legitimately available yet; Champions' Guild gear needs "
                    + CHAMPIONS_GUILD_QUEST_POINTS + " quest points and this account has "
                    + player.questPoints + ". Resuming combat with current gear.");
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

        PickaxeTarget fundedPickaxeUpgrade = nextPickaxeUpgrade(player);
        if (goal.isPickaxeUpgradeDeferred(fundedPickaxeUpgrade)) {
            fundedPickaxeUpgrade = null;
        }
        if (fundedPickaxeUpgrade != null
                && shouldPrioritizePickaxeUpgradeOverGear(target.itemId, fundedPickaxeUpgrade.itemId)) {
            JsonObject result = acquirePickaxeUpgradeStep(player, goal, fundedPickaxeUpgrade);
            String message = getString(result, "message", "upgrading the mining pickaxe.");
            result.addProperty("message", "Gearing up: prioritizing " + fundedPickaxeUpgrade.itemName()
                    + " before " + target.itemName() + " so the next mining batch funds gear faster. "
                    + message);
            return result;
        }

        int inventoryCoins = AgentToolService.countInventoryItem(player, COINS);
        int bankCoins = AgentToolService.countBankItem(player, COINS);
        int targetCost = estimatedGearAcquisitionCost(target, player);
        if (inventoryCoins < targetCost && bankCoins > 0
                && inventoryCoins + bankCoins < targetCost) {
            goal.beginGearMoney(target);
            return AgentToolService.success("Gearing up: saved " + (inventoryCoins + bankCoins)
                    + " spendable coins toward " + target.itemName() + ", estimated around "
                    + targetCost + "; switching to normal Varrock mining money-making.");
        }
        if (inventoryCoins < targetCost && bankCoins > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, "varrock east bank");
                result.addProperty("message", "Gearing up: returning to the bank for coins.");
                return result;
            }
            int amount = Math.min(Math.max(targetCost * 2, 1), bankCoins);
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
        if (inventoryCoins < targetCost) {
            goal.beginGearMoney(target);
            return AgentToolService.success("Gearing up: saved " + inventoryCoins + " coins, but " + target.itemName()
                    + " is estimated around " + targetCost
                    + "; switching to normal Varrock mining money-making.");
        }

        JsonObject nardahTransit = prepareNardahTransit(player, target);
        if (nardahTransit != null) {
            return nardahTransit;
        }

        if (!currentShopNameContains(player, target.shopName)
                && isNearLandmarkTarget(target.landmark, player.absX, player.absY, player.heightLevel, 12)) {
            JsonObject result = openShop(player, target.shopName);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                String message = getString(result, "message", "Opened shop.");
                result.addProperty("message", "Gearing up: " + message);
                return result;
            }
        }

        JsonObject travel = travelTo(player, target.landmark);
        if (!getBoolean(travel, "complete", false) && !currentShopNameContains(player, target.shopName)) {
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

    private JsonObject prepareNardahTransit(Player player, GearTarget target) {
        if (!isNardahGearTarget(target) || isNardahTransitComplete(player)) {
            return null;
        }
        if (isNearShantayRugMerchant(player)) {
            CarpetTravel.carpetTravel(player, 3401, 2915);
            JsonObject result = AgentToolService.success(
                    "Gearing up: paid the Shantay rug merchant for a normal carpet ride toward Nardah.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        if (isSouthOfShantayGate(player)) {
            JsonObject result = travelTo(player, "shantay rug merchant");
            result.addProperty("message",
                    "Gearing up: walking from Shantay gate to the rug merchant for Nardah.");
            return result;
        }
        if (AgentToolService.countInventoryItem(player, SHANTAY_PASS) <= 0) {
            if (isNearShantayPass(player)) {
                Npc shantay = nearestNpc(player, SHANTAY_NPC, 6);
                if (shantay != null && AgentKnowledgeBase.distance(player.absX, player.absY,
                        shantay.absX, shantay.absY) <= 2) {
                    return buyShantayPass(player, shantay);
                }
            }
            JsonObject result = travelTo(player, "shantay pass");
            result.addProperty("message", "Gearing up: walking to Shantay to buy a pass for Nardah travel.");
            return result;
        }
        if (isAtShantayGateNorth(player)) {
            player.stopMovement();
            player.endCurrentTask();
            player.getPlayerAssistant().resetFollow();
            player.getCombatAssistant().resetPlayerAttack();
            player.objectX = player.absX;
            player.objectY = player.absY - 1;
            OtherObjects.initShantay(player, SHANTAY_GATE_OBJECT);
            JsonObject result = AgentToolService.success(
                    "Gearing up: used a Shantay pass to pass through the gate.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        if (isNearShantayGateNorth(player)) {
            JsonObject walkArgs = new JsonObject();
            walkArgs.addProperty("x", 3304);
            walkArgs.addProperty("y", 3117);
            walkArgs.addProperty("height", 0);
            JsonObject result = AgentToolService.handle(player, "walk_to_tile", walkArgs);
            result.addProperty("message", "Gearing up: stepping exactly to the Shantay gate before using the pass.");
            return result;
        }
        JsonObject result = travelTo(player, "shantay gate north");
        result.addProperty("message", "Gearing up: walking to the Shantay gate for Nardah travel.");
        return result;
    }

    private JsonObject buyShantayPass(Player player, Npc shantay) {
        int beforePasses = AgentToolService.countInventoryItem(player, SHANTAY_PASS);
        int beforeCoins = AgentToolService.countInventoryItem(player, COINS);
        if (beforeCoins < SHANTAY_PASS_PRICE) {
            JsonObject result = AgentToolService.failure("Gearing up: need 5 coins to buy a Shantay pass.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }

        if (currentShopNameContains(player, "shantay pass")) {
            return buyShantayPassFromOpenShop(player, beforePasses, beforeCoins);
        }
        if (shouldSelectShantayPassShopOption(player.nextChat, player.dialogueAction, player.talkingNpc)) {
            JsonObject result = AgentToolService.handle(player, "select_dialogue_option", optionArgs(1));
            result.addProperty("message", "Gearing up: selected Shantay's pass shop dialogue option.");
            return result;
        }
        if (shouldContinueShantayPassDialogue(player.nextChat, player.dialogueAction, player.talkingNpc)) {
            JsonObject result = AgentToolService.handle(player, "continue_dialogue", new JsonObject());
            result.addProperty("message", "Gearing up: continued Shantay's pass shop dialogue.");
            return result;
        }

        prepareNpcInteraction(player, shantay);
        player.getNpcs().thirdClickNpc(shantay.npcType);
        if (shantayPassPurchaseSucceeded(beforePasses, AgentToolService.countInventoryItem(player, SHANTAY_PASS),
                beforeCoins, AgentToolService.countInventoryItem(player, COINS))) {
            JsonObject result = AgentToolService.success(
                    "Gearing up: bought a Shantay pass from Shantay using the normal quick-buy interaction.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }

        JsonObject opened = openShop(player, "shantay pass");
        if (opened == null || !getBoolean(opened, "success", false)) {
            JsonObject result = AgentToolService.failure("Gearing up: Shantay quick-buy did not produce a pass, and the Shantay pass shop could not be opened.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }

        beforePasses = AgentToolService.countInventoryItem(player, SHANTAY_PASS);
        beforeCoins = AgentToolService.countInventoryItem(player, COINS);
        JsonObject bought = buyShantayPassFromOpenShop(player, beforePasses, beforeCoins);
        if (bought != null && getBoolean(bought, "success", false)) {
            return bought;
        }

        String failure = getString(bought, "message", "pass purchase did not change inventory");
        JsonObject result = AgentToolService.failure("Gearing up: Shantay pass purchase failed after normal NPC and shop attempts ("
                + failure + ").");
        result.add("state", AgentToolService.observeState(player));
        return result;
    }

    private JsonObject buyShantayPassFromOpenShop(Player player, int beforePasses, int beforeCoins) {
        JsonObject bought = AgentToolService.handle(player, "buy_shop_item", itemAmountArgs(SHANTAY_PASS, 1));
        if (bought != null && getBoolean(bought, "success", false)
                && shantayPassPurchaseSucceeded(beforePasses, AgentToolService.countInventoryItem(player, SHANTAY_PASS),
                beforeCoins, AgentToolService.countInventoryItem(player, COINS))) {
            JsonObject result = AgentToolService.success(
                    "Gearing up: bought a Shantay pass from the Shantay Pass Shop.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        return bought;
    }

    private static void prepareNpcInteraction(Player player, Npc npc) {
        player.stopMovement();
        player.endCurrentTask();
        player.getPlayerAssistant().resetFollow();
        player.getCombatAssistant().resetPlayerAttack();
        player.npcClickIndex = npc.npcId;
        player.npcType = npc.npcType;
        player.talkingNpc = npc.npcType;
        player.turnPlayerTo(npc.absX, npc.absY);
        npc.facePlayer(player);
    }

    static boolean shantayPassPurchaseSucceeded(int beforePasses, int afterPasses, int beforeCoins, int afterCoins) {
        return afterPasses > beforePasses && afterCoins < beforeCoins;
    }

    static boolean shouldContinueShantayPassDialogue(int nextChat, int dialogueAction, int talkingNpc) {
        return talkingNpc == SHANTAY_NPC && dialogueAction != 146 && (nextChat == 1323 || nextChat == 1326);
    }

    static boolean shouldSelectShantayPassShopOption(int nextChat, int dialogueAction, int talkingNpc) {
        return talkingNpc == SHANTAY_NPC && dialogueAction == 146;
    }

    private JsonObject earnGearMoneyStep(Player player, CombatGoal goal) {
        boolean shopFoodMoneyTarget = isShopFoodMoneyTarget(goal);
        GearTarget gearTarget = shopFoodMoneyTarget ? shopFoodMoneyTarget(goal.gearMoneyTargetCoins)
                : goal.gearMoneyTargetItemId > 0 ? gearTargetByItemId(goal.gearMoneyTargetItemId)
                        : nextDesiredGearMoneyTarget(player, goal);
        PickaxeTarget pickaxeMoneyTarget = shopFoodMoneyTarget ? null
                : goal.gearMoneyPickaxeTargetItemId > 0
                        ? pickaxeTargetByItemId(goal.gearMoneyPickaxeTargetItemId) : null;
        if (!shopFoodMoneyTarget && gearTarget == null && pickaxeMoneyTarget == null) {
            pickaxeMoneyTarget = nextDesiredPickaxeMoneyTarget(player, goal);
        }
        if (gearTarget == null && pickaxeMoneyTarget == null) {
            goal.clearGearMoney();
            return AgentToolService.success("Gear money-making is not needed; no unlocked gear or pickaxe upgrade is pending.");
        }
        if (!shopFoodMoneyTarget && gearTarget != null && !isGearTargetAvailable(player, gearTarget)) {
            goal.clearGearMoney();
            return AgentToolService.success("Gear money-making paused: " + gearTarget.itemName()
                    + " is not legitimately available yet; Champions' Guild gear needs "
                    + CHAMPIONS_GUILD_QUEST_POINTS + " quest points and this account has "
                    + player.questPoints + ".");
        }
        GearTarget target = gearTarget == null ? pickaxeMoneyGearTarget(pickaxeMoneyTarget) : gearTarget;
        if (shopFoodMoneyTarget) {
            goal.beginTargetMoney(KEBAB, SHOP_FOOD_MONEY_TARGET_NAME, target.estimatedPrice);
        } else if (gearTarget == null) {
            goal.beginPickaxeMoney(pickaxeMoneyTarget);
        } else {
            goal.beginGearMoney(gearTarget);
        }

        int spendableCoins = AgentToolService.countInventoryItem(player, COINS) + AgentToolService.countBankItem(player, COINS);
        int targetCost = shopFoodMoneyTarget ? Math.max(1, target.estimatedPrice)
                : gearTarget == null ? pickaxeMoneyTarget.estimatedPrice
                : estimatedGearAcquisitionCost(gearTarget, player);
        boolean targetAcquisitionRawLiquidation = shouldLiquidateStagedGearMoneyItems(goal);
        GearTarget affordableUpgrade = nextGearTarget(player);
        if (!shopFoodMoneyTarget && gearTarget == null && affordableUpgrade != null) {
            goal.clearGearMoney();
            goal.rememberGearTarget(affordableUpgrade);
            goal.gearingUp = true;
            return AgentToolService.success("Saved while working toward " + pickaxeMoneyTarget.itemName()
                    + ", but a combat upgrade is now ready; buying " + affordableUpgrade.itemName() + " first.");
        }
        if (!shopFoodMoneyTarget && gearTarget != null
                && shouldInterruptGearMoneyForAffordableUpgrade(affordableUpgrade, gearTarget)) {
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
                    + " while working toward " + gearTarget.itemName() + "; buying the intermediate upgrade first.");
        }
        if (spendableCoins >= targetCost) {
            goal.clearGearMoney();
            if (shopFoodMoneyTarget) {
                goal.restockingFood = true;
                if (player.isShopping || player.isBanking) {
                    JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
                    result.addProperty("message",
                            "Funded the target-sized kebab restock; closing interfaces before buying food.");
                    return result;
                }
                return AgentToolService.success(
                        "Funded the target-sized kebab restock; buying the food batch next.");
            }
            if (gearTarget == null) {
                return acquirePickaxeUpgradeStep(player, goal, pickaxeMoneyTarget);
            }
            goal.gearingUp = true;
            if (player.isShopping || player.isBanking) {
                JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
                result.addProperty("message", "Earned enough coins for " + gearTarget.itemName()
                        + "; closing interfaces before buying the upgrade.");
                return result;
            }
            return AgentToolService.success("Earned enough coins for " + gearTarget.itemName()
                    + "; resuming the gear upgrade step.");
        }

        int carriedGearMoneyItems = countInventoryGearMoneyItems(player) + countInventoryGearMoneyProducts(player, goal);
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int strengthLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.STRENGTH]);
        boolean liquidatingForCombat = !shopFoodMoneyTarget && gearTarget != null
                && shouldDeferExpensiveWeaponUpgradeForCombat(
                attackLevel, strengthLevel, goal.targetLevel, spendableCoins,
                bestEquippedGearTier(player, WEAPON_GEAR_TARGETS), gearTarget);
        if (carriedGearMoneyItems == 0 && liquidatingForCombat) {
            goal.clearGearMoney();
            goal.lastGearAttemptAction = goal.actionsRun;
            return AgentToolService.success("Deferring " + target.itemName()
                    + " savings; current weapon is strong enough to keep training Attack before a long mining grind.");
        }

        if (isPlayerInCombat(player)) {
            return escapeCombatForNonCombatWork(player, "Earning gear money", "varrock east bank");
        }
        if (!shopFoodMoneyTarget) {
            JsonObject foodPrep = prepareGearMoneyFood(player, goal);
            if (foodPrep != null) {
                return foodPrep;
            }
        }
        boolean targetAcquisitionSaleBatchReady = shouldSellGearMoneyBatch(spendableCoins,
                estimatedInventoryGearMoneyCoins(player, goal), estimatedBankGearMoneyCoins(player, goal),
                targetCost);
        if (shouldStopMiningForFundedTargetAcquisitionSale(player.isMining, targetAcquisitionRawLiquidation,
                targetAcquisitionSaleBatchReady)) {
            JsonObject result = AgentToolService.handle(player, "cancel_current_action", new JsonObject());
            result.addProperty("message",
                    "Earning gear money: stopping mining because the target acquisition sale batch is funded.");
            return result;
        }
        if (shouldStopMiningForFundedGearMoneyProcessing(player.isMining, goal.gearMoneyProcessingStarted)) {
            JsonObject result = AgentToolService.handle(player, "cancel_current_action", new JsonObject());
            result.addProperty("message",
                    "Earning gear money: stopping mining because the funded ore/bar batch is ready to process.");
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
        if (shouldBankCarriedBatchAfterProcessingStarted(goal.gearMoneyProcessingStarted,
                countInventoryRawGearMoneyMaterials(player), goal.gearMoneyRawMaterialsBankedAfterProcessingStarted)) {
            return bankGearMoneyRawMaterialsStep(player, goal, target,
                    "banking carried ore before continuing the funded bar/product processing batch");
        }

        int gearMoneyProducts = countInventoryGearMoneyProducts(player, goal);
        int inventoryMoneyItems = countInventoryGearMoneyItems(player);
        int carriedMoneyItems = inventoryMoneyItems + gearMoneyProducts;
        int carriedGearMoneyValue = estimatedInventoryGearMoneyCoins(player, goal);
        int bankedGearMoneyValue = estimatedBankGearMoneyCoins(player, goal);
        int potentialGearMoneyCoins = spendableCoins + carriedGearMoneyValue + bankedGearMoneyValue;
        PickaxeTarget fundedPickaxeUpgrade = shopFoodMoneyTarget ? null
                : nextPickaxeUpgrade(player, potentialGearMoneyCoins);
        if (goal.isPickaxeUpgradeDeferred(fundedPickaxeUpgrade)) {
            fundedPickaxeUpgrade = null;
        }
        int liquidityTargetCost = gearMoneyLiquidityTargetCost(targetCost,
                fundedPickaxeUpgrade == null ? -1 : fundedPickaxeUpgrade.estimatedPrice);
        boolean gearMoneyBatchReady = shouldSellGearMoneyBatch(spendableCoins, carriedGearMoneyValue,
                bankedGearMoneyValue, liquidityTargetCost);
        int gearMoneyProductValue = estimatedGearMoneyProductCoins(player, goal);
        int processedGearMoneyPotential = estimatedProcessedGearMoneyPotentialCoins(player, spendableCoins, goal);
        boolean preferredGearMoneyBatchStaged = isPreferredGearMoneyBatchStaged(player, spendableCoins,
                liquidityTargetCost, gearMoneyProductValue);
        boolean gearMoneyProcessingBatchReady = processedGearMoneyPotential >= liquidityTargetCost
                && preferredGearMoneyBatchStaged;
        if (gearMoneyProcessingBatchReady) {
            goal.rememberGearMoneyProcessingStarted();
        }

        PickaxeTarget pickaxeUpgrade = nextPickaxeUpgrade(player);
        if (goal.isPickaxeUpgradeDeferred(pickaxeUpgrade)) {
            pickaxeUpgrade = null;
        }
        if (!shopFoodMoneyTarget && pickaxeUpgrade != null && inventoryMoneyItems == 0 && gearMoneyProducts == 0) {
            return acquirePickaxeUpgradeStep(player, goal, pickaxeUpgrade);
        }

        int gearMoneyClutterItems = countInventoryGearMoneyClutterItems(player, goal);
        if (Boundary.isIn(player, Boundary.BANK_AREA) && gearMoneyClutterItems > 0) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", gearMoneyClutterArgs(player, goal));
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
        if (shouldBankGearMoneyClutterBeforeProcessing(gearMoneyClutterItems, player.absX, player.absY)) {
            String bankLandmark = gearMoneyClutterBankLandmark(player.absX, player.absY);
            JsonObject result = travelTo(player, bankLandmark);
            result.addProperty("message", "Earning gear money: banking mining byproducts before processing ore.");
            return result;
        }

        JsonObject travelCoinPrep = prepareGearMoneyTravelCoins(player);
        if (travelCoinPrep != null) {
            return travelCoinPrep;
        }

        JsonObject steelPrep = prepareGearMoneySteelSmeltingInputs(player, target, goal, liquidatingForCombat,
                gearMoneyProcessingBatchReady, goal.gearMoneyProcessingStarted);
        if (steelPrep != null) {
            return steelPrep;
        }

        boolean bankHasSmeltableGearMoneyOres = hasBankedSmeltableGearMoneyOres(player);
        int bankedProcessableGearMoneyItems = countBankProcessableGearMoneyItems(player);
        boolean bankHasProcessableGearMoneyMaterials = hasProcessableGearMoneyMaterials(
                bankHasSmeltableGearMoneyOres, bankedProcessableGearMoneyItems);
        int smeltableBar = bestSmeltableGearMoneyBar(player);
        boolean shouldProcessGearMoneyBatch = shouldProcessGearMoneyBatch(gearMoneyProcessingBatchReady,
                liquidatingForCombat, goal.gearMoneyProcessingStarted);
        boolean canSmeltOres = smeltableBar > 0
                && shouldProcessGearMoneyBatch
                && shouldSmeltGearMoneyOres(player, smeltableBar, liquidatingForCombat,
                        goal.gearMoneyProcessingStarted);
        int smithableBar = bestSmithableGearMoneyBar(player);
        boolean canSmithBars = smithableBar > 0
                && shouldProcessGearMoneyBatch
                && (shouldSmithGearMoneyBars(player, smithableBar, liquidatingForCombat)
                        || gearMoneyProcessingBatchReady);
        boolean carryingBalancedSteelSmeltingBatch = shouldUseSteelForGearMoney(
                player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]))
                && isBalancedSteelSmeltingBatch(AgentToolService.countInventoryItem(player, IRON_ORE),
                        AgentToolService.countInventoryItem(player, COAL));
        int productionAction = gearMoneyProductionAction(canSmeltOres, canSmithBars);
        if (shouldSmithCarriedBarsBeforeResidualSmelting(productionAction, canSmithBars,
                countInventoryProcessedGearMoneyBars(player), countInventoryRawGearMoneyMaterials(player),
                player.getItemAssistant().freeSlots(), goal.gearMoneyProcessingStarted)) {
            productionAction = GEAR_MONEY_PRODUCTION_SMITH;
        }
        if (shouldDelayGearMoneyProductionForFullerLoad(productionAction, carriedMoneyItems,
                player.getItemAssistant().freeSlots(), gearMoneyBatchReady, gearMoneyProcessingBatchReady,
                liquidatingForCombat, carryingBalancedSteelSmeltingBatch, player.absX, player.absY,
                goal.gearMoneyProcessingStarted)) {
            productionAction = GEAR_MONEY_PRODUCTION_NONE;
        }
        if (shouldSellReadyGearMoneyBatchBeforeProcessing(gearMoneyProducts, gearMoneyBatchReady, productionAction,
                goal.gearMoneyProcessingStarted, bankHasProcessableGearMoneyMaterials)) {
            return sellGearMoneyItemsStep(player, goal, target);
        }
        if (shouldBankGearMoneyMaterialsBeforeProcessing(productionAction, carriedMoneyItems, gearMoneyBatchReady,
                        gearMoneyProcessingBatchReady, liquidatingForCombat, player.getItemAssistant().freeSlots(),
                        carryingBalancedSteelSmeltingBatch)) {
            return bankGearMoneyBatchStep(player, goal, target,
                    "banking mined materials until enough is staged for one funded smithing batch");
        }
        if (shouldSellGearMoneyProductsBeforeProduction(gearMoneyProducts, canSmeltOres, canSmithBars,
                goal.gearMoneyProcessingStarted, bankHasProcessableGearMoneyMaterials)) {
            if (gearMoneyBatchReady) {
                return sellGearMoneyItemsStep(player, goal, target);
            }
                return bankGearMoneyBatchStep(player, goal, target,
                        "banking the partial smithed batch before another mining run");
        }
        if (shouldBankCarriedMaterialsAfterProcessingStarted(goal.gearMoneyProcessingStarted, carriedMoneyItems,
                productionAction, bankHasProcessableGearMoneyMaterials)) {
            return bankGearMoneyBatchStep(player, goal, target,
                    "banking carried materials because the funded ore/bar batch is already in processing mode");
        }
        if (shouldBankProcessedBarsBeforeMoreMining(countInventoryProcessedGearMoneyBars(player), canSmithBars,
                canSmeltOres, isAlKharidSideForGearMoney(player.absX, player.absY)
                        || isVarrockGearMoneyBankingCorridor(player.absX, player.absY)
                        || Boundary.isIn(player, Boundary.BANK_AREA))) {
            return bankGearMoneyBatchStep(player, goal, target,
                    "banking leftover bars before another mining run so they can be smithed with the next batch");
        }
        if (shouldSellCarriedGearMoneyAfterFurnaceStall(goal.movingStallRecoveries, carriedMoneyItems,
                productionAction != GEAR_MONEY_PRODUCTION_NONE)) {
            if (!gearMoneyBatchReady) {
                return bankGearMoneyBatchStep(player, goal, target,
                        "banking the partial mined batch after furnace travel trouble");
            }
            JsonObject result = sellGearMoneyItemsStep(player, goal, target);
            String message = getString(result, "message", "selling carried mined items.");
            result.addProperty("message", "Earning gear money: furnace route stalled; selling carried materials instead: "
                    + message);
            return result;
        }
        if (productionAction == GEAR_MONEY_PRODUCTION_SMELT) {
            JsonObject gatePrep = prepareGearMoneyAlKharidGateToll(player, goal, target);
            if (gatePrep != null) {
                return gatePrep;
            }
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
            if (shouldBankSmeltedBarsBeforeStagedSmithing(countInventoryProcessedGearMoneyBars(player),
                    hasBankedSmeltableGearMoneyOresForBar(player, smithableBar), liquidatingForCombat,
                    goal.gearMoneyProcessingStarted,
                    player.getItemAssistant().freeSlots())) {
                return bankGearMoneyBatchStep(player, goal, target,
                        "banking smelted bars until the staged ore pile is fully smelted");
            }
            int carriedSmithingBars = AgentToolService.countInventoryItem(player, smithableBar);
            int bankedSmithingBars = AgentToolService.countBankItem(player, smithableBar);
            if (shouldTopUpGearMoneySmithingBars(carriedSmithingBars, bankedSmithingBars,
                    player.getItemAssistant().freeSlots(), liquidatingForCombat)) {
                if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                    JsonObject travel = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
                    travel.addProperty("message", "Earning gear money: topping up banked bars before walking to Varrock anvils.");
                    return travel;
                }
                JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                        itemAmountArgs(smithableBar, Math.max(1, player.getItemAssistant().freeSlots())));
                result.addProperty("message", "Earning gear money: topped up carried bars before smithing the staged batch.");
                return result;
            }
            SmithingChoice smithingChoice = bestGearMoneySmithingChoice(player, smithableBar);
            JsonObject hammerPrep = prepareGearMoneyHammer(player, goal, target);
            if (hammerPrep != null) {
                return hammerPrep;
            }
            if (shouldPrepareAlKharidGateTollForSmithing(player.absX, player.absY)) {
                JsonObject gatePrep = prepareGearMoneyAlKharidGateToll(player, goal, target);
                if (gatePrep != null) {
                    return gatePrep;
                }
            }
            if (player.isShopping || player.isBanking) {
                JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
                result.addProperty("message", "Earning gear money: closing interfaces before walking to Varrock anvils.");
                return result;
            }
            JsonObject travel = travelTo(player, "varrock west anvils");
            if (!getBoolean(travel, "complete", false)) {
                travel.addProperty("message", "Earning gear money: walking to Varrock anvils to smith saleable gear.");
                return travel;
            }
            JsonObject result = AgentToolService.handle(player, "smith_item", smithItemArgs(smithingChoice.getItemId()));
            if (getBoolean(result, "success", false)) {
                goal.rememberGearMoneyCraftedProduct(smithingChoice.getItemId());
            }
            result.addProperty("message", "Earning gear money for " + target.itemName() + ": "
                    + getString(result, "message", "smithing the best available item."));
            return result;
        }

        if (liquidatingForCombat && inventoryMoneyItems > 0) {
            return sellGearMoneyItemsStep(player, goal, target);
        }

        int bankedGearMoneyItems = countBankGearMoneyItems(player, goal);
        if (shouldWithdrawTargetAcquisitionSaleBatch(targetAcquisitionRawLiquidation, gearMoneyBatchReady,
                carriedMoneyItems, bankedGearMoneyItems, player.getItemAssistant().freeSlots())) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
                result.addProperty("message",
                        "Earning gear money: returning to bank for the funded target-acquisition sale batch.");
                return result;
            }
            int itemId = bestBankGearMoneyItem(player, goal);
            if (itemId <= 0) {
                return sellGearMoneyItemsStep(player, goal, target);
            }
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(itemId, Math.max(1, player.getItemAssistant().freeSlots())));
            if (!getBoolean(result, "success", false) || getInt(result, "withdrawnAmount", 0) <= 0) {
                JsonObject sell = sellGearMoneyItemsStep(player, goal, target);
                sell.addProperty("message",
                        "Earning gear money: target-acquisition sale top-up was unavailable; selling the carried batch instead: "
                                + getString(sell, "message", "selling carried batch."));
                return sell;
            }
            result.addProperty("message",
                    "Earning gear money: withdrew staged target-acquisition sale items from bank storage.");
            return result;
        }
        if (shouldSellTargetAcquisitionSaleBatch(targetAcquisitionRawLiquidation, gearMoneyBatchReady,
                carriedMoneyItems)) {
            return sellGearMoneyItemsStep(player, goal, target);
        }
        if (shouldWithdrawMoreStoredGearMoneySaleItems(carriedMoneyItems, bankedGearMoneyItems,
                player.getItemAssistant().freeSlots(), gearMoneyBatchReady, goal.gearMoneyProcessingStarted,
                bankHasProcessableGearMoneyMaterials)) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
                result.addProperty("message",
                        "Earning gear money: returning to bank to top up the carried sale batch.");
                return result;
            }
            int itemId = bestBankGearMoneyItem(player, goal);
            if (itemId <= 0) {
                return sellGearMoneyItemsStep(player, goal, target);
            }
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(itemId, Math.max(1, player.getItemAssistant().freeSlots())));
            if (!getBoolean(result, "success", false) || getInt(result, "withdrawnAmount", 0) <= 0) {
                JsonObject sell = sellGearMoneyItemsStep(player, goal, target);
                sell.addProperty("message", "Earning gear money: stored sale top-up was unavailable; selling the carried batch instead: "
                        + getString(sell, "message", "selling carried batch."));
                return sell;
            }
            result.addProperty("message", "Earning gear money: topped up the carried sale batch from bank storage.");
            return result;
        }

        if (carriedMoneyItems > 0
                && (player.getItemAssistant().freeSlots() <= 0
                        || carriedMoneyItems >= MIN_GEAR_MONEY_ITEMS_BEFORE_SELLING)) {
            if (!gearMoneyBatchReady) {
                return bankGearMoneyBatchStep(player, goal, target,
                        "banking the full partial batch before another mining run");
            }
            return sellGearMoneyItemsStep(player, goal, target);
        }

        if (!hasPickaxeInInventory(player)) {
            int bankPickaxe = bestBankPickaxe(player);
            if (bankPickaxe > 0) {
                if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                    JsonObject result = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
                    result.addProperty("message", "Earning gear money: returning to the bank for a pickaxe.");
                    return result;
                }
                JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(bankPickaxe, 1));
                result.addProperty("message", "Earning gear money: withdrew a pickaxe for Varrock east mine.");
                return result;
            }
            return AgentToolService.failure("Earning gear money requires a pickaxe, but no banked or carried pickaxe is available.");
        }

        if (shouldWithdrawBankedGearMoneyMaterialsForProcessing(carriedMoneyItems, bankHasSmeltableGearMoneyOres,
                bankedProcessableGearMoneyItems, gearMoneyProcessingBatchReady, player.getItemAssistant().freeSlots(),
                goal.gearMoneyProcessingStarted)) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
                result.addProperty("message",
                        "Earning gear money: returning to bank for staged materials before more processing.");
                return result;
            }
            int itemId = gearMoneyProcessableWithdrawalItem(bankHasSmeltableGearMoneyOres,
                    bestBankSmeltableGearMoneyOre(player), bestBankProcessableGearMoneyItem(player));
            if (itemId > 0) {
                JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                        itemAmountArgs(itemId, Math.max(1, player.getItemAssistant().freeSlots())));
                result.addProperty("message", isGearMoneyBar(itemId)
                        ? "Earning gear money: withdrew staged bars to smith before selling the funded batch."
                        : "Earning gear money: withdrew staged ore to keep smelting before smithing the batch.");
                return result;
            }
        }

        if (carriedMoneyItems <= 0 && gearMoneyProcessingBatchReady
                && countBankProcessableGearMoneyItems(player) > 0
                && player.getItemAssistant().freeSlots() > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
                result.addProperty("message",
                        "Earning gear money: returning to bank for staged materials before the funded sale.");
                return result;
            }
            int itemId = gearMoneyProcessableWithdrawalItem(bankHasSmeltableGearMoneyOres,
                    bestBankSmeltableGearMoneyOre(player), bestBankProcessableGearMoneyItem(player));
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(itemId, Math.max(1, player.getItemAssistant().freeSlots())));
            result.addProperty("message", isGearMoneyBar(itemId)
                    ? "Earning gear money: withdrew staged bars to smith before selling the funded batch."
                    : "Earning gear money: withdrew staged ore to finish smelting before selling the funded batch.");
            return result;
        }

        if (carriedMoneyItems <= 0 && bankedGearMoneyItems > 0
                && (gearMoneyBatchReady || goal.gearMoneyProcessingStarted)
                && player.getItemAssistant().freeSlots() > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
                result.addProperty("message", "Earning gear money: returning to bank for the funded sale batch.");
                return result;
            }
            int itemId = bestBankGearMoneyItem(player, goal);
            if (itemId <= 0) {
                return AgentToolService.failure("Earning gear money expected a banked sale batch, but no sellable item was available.");
            }
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(itemId, Math.max(1, player.getItemAssistant().freeSlots())));
            result.addProperty("message", "Earning gear money: withdrew stored batch items to sell in one trip.");
            return result;
        }

        if (player.isShopping || player.isBanking) {
            JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
            result.addProperty("message", "Earning gear money: closing interfaces before mining.");
            return result;
        }

        if (player.getItemAssistant().freeSlots() <= 0) {
            if (carriedMoneyItems > 0) {
                if (!gearMoneyBatchReady) {
                    return bankGearMoneyBatchStep(player, goal, target,
                            "banking the full partial batch before another mining run");
                }
                return sellGearMoneyItemsStep(player, goal, target);
            }
            JsonObject result = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
            result.addProperty("message", "Earning gear money: inventory is full, returning to bank before mining.");
            return result;
        }

        int miningLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.MINING]);
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        int totalCopperOre = AgentToolService.countInventoryItem(player, COPPER_ORE)
                + AgentToolService.countBankItem(player, COPPER_ORE);
        int totalTinOre = AgentToolService.countInventoryItem(player, TIN_ORE)
                + AgentToolService.countBankItem(player, TIN_ORE);
        int totalIronOre = AgentToolService.countInventoryItem(player, IRON_ORE)
                + AgentToolService.countBankItem(player, IRON_ORE);
        int totalCoal = AgentToolService.countInventoryItem(player, COAL) + AgentToolService.countBankItem(player, COAL);
        String ore = gearMoneyOreForMiningLevel(miningLevel, smithingLevel,
                totalCopperOre, totalTinOre, totalIronOre, totalCoal,
                player.getItemAssistant().freeSlots(), player.absX, player.absY,
                spendableCoins, liquidityTargetCost, gearMoneyProductValue,
                AgentToolService.countInventoryItem(player, BRONZE_BAR) + AgentToolService.countBankItem(player, BRONZE_BAR),
                AgentToolService.countInventoryItem(player, IRON_BAR) + AgentToolService.countBankItem(player, IRON_BAR),
                AgentToolService.countInventoryItem(player, STEEL_BAR) + AgentToolService.countBankItem(player, STEEL_BAR));
        ore = gearMoneyOreForRouteSafety(ore, AgentToolService.countInventoryFood(player),
                player.playerLevel[Constants.HITPOINTS],
                player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.HITPOINTS]));
        if (shouldBankNearFullGearMoneyBatchBeforeOreSwitch(carriedMoneyItems, player.getItemAssistant().freeSlots(),
                ore, player.absX, player.absY)) {
            if (gearMoneyBatchReady) {
                return sellGearMoneyItemsStep(player, goal, target);
            }
            return bankGearMoneyBatchStep(player, goal, target,
                    "banking the nearly full mined batch instead of crossing mines for a small top-up");
        }
        String mineLandmark = gearMoneyMineLandmark(ore);
        if (!isGearMoneyMine(ore, player.absX, player.absY)) {
            JsonObject travel = travelTo(player, mineLandmark);
            if (!getBoolean(travel, "complete", false)) {
                travel.addProperty("message", "Earning gear money: walking to " + mineLandmark + " to mine "
                        + ore + " for higher-value smithing.");
                return travel;
            }
        }
        JsonObject result = AgentToolService.handle(player, "mine_ore",
                gearMoneyOreArgs(ore, player.absX, player.absY, goal.shouldWaitForLocalMiningRespawn()));
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
        if (inventoryCoins >= AL_KHARID_GATE_TOLL) {
            return null;
        }
        int bankCoins = AgentToolService.countBankItem(player, COINS);
        int seedItemId = hammerSeedItemForCoins(
                AgentToolService.countInventoryItem(player, IRON_ORE),
                AgentToolService.countInventoryItem(player, COPPER_ORE),
                AgentToolService.countInventoryItem(player, TIN_ORE),
                AgentToolService.countInventoryItem(player, BRONZE_BAR),
                bankCoins);
        if (shouldSellLocalSeedItemForGateToll(inventoryCoins, shouldUseLocalAlKharidGeneralStore(player),
                seedItemId)) {
            return sellGateTollSeedItemForCoinsStep(player, goal, target, seedItemId);
        }
        if (bankCoins > 0) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject result = travelTo(player, "varrock east bank");
                result.addProperty("message", "Earning gear money: returning to bank for Al Kharid gate toll coins.");
                return result;
            }
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(COINS, Math.min(AL_KHARID_HAMMER_AND_GATE_COIN_BUFFER, bankCoins)));
            result.addProperty("message",
                    "Earning gear money: withdrew a small Al Kharid toll float before furnace travel.");
            return result;
        }
        if (seedItemId <= 0) {
            return null;
        }
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
        return inBankArea
                && (freeSlots > 0 || inventoryCoins > 0)
                && inventoryCoins < AL_KHARID_HAMMER_AND_GATE_COIN_BUFFER
                && bankCoins > 0;
    }

    static boolean shouldSellCarriedGearMoneyAfterFurnaceStall(int movingStallRecoveries, int carriedMoneyItems,
            boolean canProcessCarriedMaterials) {
        return !canProcessCarriedMaterials
                && movingStallRecoveries >= 8
                && carriedMoneyItems >= MIN_GEAR_MONEY_ITEMS_BEFORE_SELLING;
    }

    static boolean shouldBankProcessedBarsBeforeMoreMining(int processedBars, boolean canSmithBars,
            boolean canSmeltOres, boolean onFurnaceSide) {
        return processedBars > 0
                && !canSmithBars
                && !canSmeltOres
                && (onFurnaceSide || processedBars >= MIN_PROCESSED_BARS_BEFORE_SELLING);
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

    static boolean shouldPrepareAlKharidGateTollForSmithing(int x, int y) {
        return isAlKharidSideForGearMoney(x, y);
    }

    static boolean shouldPrepareAlKharidGateTollForCombat(int x, int y, int inventoryCoins, String trainingArea) {
        return inventoryCoins < AL_KHARID_GATE_TOLL
                && isAlKharidSideForGearMoney(x, y)
                && shouldReserveAlKharidReturnTollForTarget(trainingArea);
    }

    static boolean shouldReserveAlKharidReturnTollForTarget(String targetName) {
        String target = targetName == null ? "" : targetName.trim().toLowerCase();
        if (target.contains("al kharid") || target.contains("kebab") || target.contains("shantay")
                || target.contains("nardah")) {
            return false;
        }
        return true;
    }

    static boolean hasEnoughCoinsForTargetAcquisitionTrip(int inventoryCoins, int bankCoins, int entryCost,
            int reserveCoins, int unitCost) {
        return Math.max(0, inventoryCoins) + Math.max(0, bankCoins)
                >= Math.max(0, entryCost) + Math.max(0, reserveCoins) + Math.max(1, unitCost);
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

    private static int inventoryAlKharidGateTollSeedItem(Player player, CombatGoal goal) {
        int bestItem = -1;
        int bestValue = -1;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (!isAlKharidGateTollSeedItem(player, itemId, goal)) {
                continue;
            }
            int value = estimatedGearMoneySellCoins(itemId);
            if (value > bestValue) {
                bestValue = value;
                bestItem = itemId;
            }
        }
        return bestItem;
    }

    private static int bankAlKharidGateTollSeedItem(Player player, CombatGoal goal) {
        int bestItem = -1;
        int bestValue = -1;
        for (int itemId : GEAR_MONEY_RAW_MATERIAL_ITEM_IDS) {
            if (AgentToolService.countBankItem(player, itemId) <= 0) {
                continue;
            }
            int value = estimatedGearMoneySellCoins(itemId);
            if (value > bestValue) {
                bestValue = value;
                bestItem = itemId;
            }
        }
        if (bestItem > 0) {
            return bestItem;
        }
        for (SmithingData data : SmithingData.values()) {
            int itemId = data.getId();
            if (isGearMoneySaleItem(player, itemId, goal) && AgentToolService.countBankItem(player, itemId) > 0) {
                int value = estimatedGearMoneySellCoins(itemId);
                if (value > bestValue) {
                    bestValue = value;
                    bestItem = itemId;
                }
            }
        }
        return bestItem;
    }

    private static boolean isAlKharidGateTollSeedItem(Player player, int itemId, CombatGoal goal) {
        return isGearMoneyItem(itemId)
                || isGearMoneySaleItem(player, itemId, goal)
                || itemId == LOGS;
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

    private static JsonObject prepareAlKharidGateTollForCombat(Player player, CombatGoal goal) {
        if (!shouldPrepareAlKharidGateTollForCombat(player.absX, player.absY,
                AgentToolService.countInventoryItem(player, COINS), goal == null ? "" : goal.area)) {
            return null;
        }

        int inventorySeedItem = inventoryAlKharidGateTollSeedItem(player, goal);
        if (inventorySeedItem > 0 && shouldUseLocalAlKharidGeneralStore(player)) {
            JsonObject result = sellAlKharidCombatTollSeedItemStep(player, goal, inventorySeedItem);
            result.addProperty("message", "Preparing Al Kharid gate toll before combat: "
                    + getString(result, "message", "selling local money-making item."));
            return result;
        }

        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            JsonObject result = travelTo(player, "al kharid bank");
            result.addProperty("message",
                    "Preparing Al Kharid gate toll before combat: walking to Al Kharid bank for legitimate travel coins.");
            return result;
        }

        int bankCoins = AgentToolService.countBankItem(player, COINS);
        if (bankCoins > 0 && player.getItemAssistant().freeSlots() > 0) {
            int amount = Math.min(AL_KHARID_GATE_TOLL - AgentToolService.countInventoryItem(player, COINS),
                    bankCoins);
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(COINS, Math.max(1, amount)));
            result.addProperty("message",
                    "Preparing Al Kharid gate toll before combat: withdrew banked coins for the gate.");
            return result;
        }

        int bankSeedItem = bankAlKharidGateTollSeedItem(player, goal);
        if (bankSeedItem > 0 && player.getItemAssistant().freeSlots() > 0) {
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items",
                    itemAmountArgs(bankSeedItem, targetAcquisitionBatchAmount(
                            AL_KHARID_GATE_TOLL, AgentToolService.countInventoryItem(player, COINS),
                            player.getItemAssistant().freeSlots())));
            result.addProperty("message",
                    "Preparing Al Kharid gate toll before combat: withdrew banked mined money-making items to sell locally.");
            return result;
        }

        return AgentToolService.failure(
                "Preparing Al Kharid gate toll before combat requires 10 coins, but no banked coins or mined money-making items are available.");
    }

    private static JsonObject sellAlKharidCombatTollSeedItemStep(Player player, CombatGoal goal, int itemId) {
        JsonObject travel = travelTo(player, "al kharid general store");
        if (!getBoolean(travel, "complete", false)) {
            travel.addProperty("message", "walking to Al Kharid general store to sell a money-making item.");
            return travel;
        }

        if (!currentShopNameContains(player, "general")) {
            JsonObject result = openShop(player, "general");
            result.addProperty("message", "opening the general store to fund the gate toll.");
            return result;
        }

        JsonObject result = AgentToolService.handle(player, "sell_inventory_item", itemAmountArgs(itemId, 1));
        if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
            int sold = getInt(result, "sold", 0);
            int coins = getInt(result, "coinsReceived", 0);
            if (goal != null) {
                goal.gearMoneyTrips++;
                goal.gearMoneyItemsSold += sold;
                goal.gearMoneyCoinsEarned += coins;
            }
            result.addProperty("message", "sold " + sold + " money-making item(s) for " + coins
                    + " gate-toll coins while preserving combat supplies.");
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

        JsonObject result = AgentToolService.handle(player, "sell_inventory_items", gearMoneySellArgs(player, goal));
        if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
            int sold = getInt(result, "sold", 0);
            int coins = getInt(result, "coinsReceived", 0);
            goal.gearMoneyTrips++;
            goal.gearMoneyItemsSold += sold;
            goal.gearMoneyCoinsEarned += coins;
            goal.clearGearMoneyCraftedProductIfGone(player);
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

    private static JsonObject bankGearMoneyBatchStep(Player player, CombatGoal goal, GearTarget target, String reason) {
        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            JsonObject travel = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
            travel.addProperty("message", "Earning gear money for " + target.itemName() + ": " + reason
                    + " instead of selling early.");
            return travel;
        }

        JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", gearMoneyBatchBankArgs(player, goal));
        String message = getString(result, "message", "banked carried money-making items.");
        result.addProperty("message", "Earning gear money for " + target.itemName() + ": " + reason
                + " instead of selling early: " + message);
        return result;
    }

    private static JsonObject bankGearMoneyRawMaterialsStep(Player player, CombatGoal goal, GearTarget target,
            String reason) {
        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            JsonObject travel = travelTo(player, gearMoneyClutterBankLandmark(player.absX, player.absY));
            travel.addProperty("message", "Earning gear money for " + target.itemName() + ": " + reason
                    + " instead of selling early.");
            return travel;
        }

        JsonObject result = AgentToolService.handle(player, "deposit_inventory_items", gearMoneyRawMaterialsBankArgs());
        int depositedAmount = getInt(result, "depositedAmount", 0);
        if (shouldRememberRawMaterialsBankedAfterProcessingStarted(
                result != null && result.has("success") && result.get("success").getAsBoolean(), depositedAmount)) {
            goal.rememberGearMoneyRawMaterialsBankedAfterProcessingStarted();
        }
        String message = getString(result, "message", "banked carried ore.");
        result.addProperty("message", "Earning gear money for " + target.itemName() + ": " + reason
                + " instead of selling early: " + message);
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

    static boolean isAlKharidBankingSideForGearMoney(int x, int y) {
        return x >= 3240 && x <= 3335 && y >= 3160 && y <= 3235;
    }

    private static boolean isNardahGearTarget(GearTarget target) {
        return target != null && "nardah adventurer store".equals(target.landmark);
    }

    private static int estimatedGearAcquisitionCost(GearTarget target) {
        if (target == null) {
            return 0;
        }
        return target.estimatedPrice + (isNardahGearTarget(target) ? NARDAH_TRANSIT_COST : 0);
    }

    private static int estimatedGearAcquisitionCost(GearTarget target, Player player) {
        if (target == null) {
            return 0;
        }
        if (!isNardahGearTarget(target) || player == null) {
            return estimatedGearAcquisitionCost(target);
        }
        return estimatedNardahGearAcquisitionCost(target.estimatedPrice, player.absX, player.absY,
                player.heightLevel);
    }

    static int estimatedNardahGearAcquisitionCost(int targetPrice, int x, int y, int height) {
        if (isNardahTransitComplete(x, y, height)) {
            return targetPrice;
        }
        if (isInPollnivneachReturnArea(x, y, height)
                || height == 0 && y <= 3115 && x >= 3297 && x <= 3320) {
            return targetPrice + NARDAH_CARPET_FARE;
        }
        return targetPrice + NARDAH_TRANSIT_COST;
    }

    private static boolean isNearNardah(Player player) {
        return isNearNardah(player.absX, player.absY, player.heightLevel);
    }

    private static boolean isNearNardah(int x, int y, int height) {
        return height == 0 && AgentKnowledgeBase.distance(x, y, 3407, 2921) <= 12;
    }

    private static boolean isNardahTransitComplete(Player player) {
        return player != null && isNardahTransitComplete(player.absX, player.absY, player.heightLevel);
    }

    static boolean isNardahTransitComplete(int x, int y, int height) {
        return height == 0 && (y <= 3050 || isNearNardah(x, y, height));
    }

    private static boolean isNearShantayPass(Player player) {
        return player.heightLevel == 0 && AgentKnowledgeBase.distance(player.absX, player.absY, 3303, 3124) <= 8;
    }

    private static boolean isNearShantayGateNorth(Player player) {
        return player.heightLevel == 0 && AgentKnowledgeBase.distance(player.absX, player.absY, 3304, 3117) <= 4;
    }

    private static boolean isAtShantayGateNorth(Player player) {
        return player.heightLevel == 0 && player.absY == 3117
                && player.absX >= 3297 && player.absX <= 3311;
    }

    private static boolean isSouthOfShantayGate(Player player) {
        return player.heightLevel == 0 && player.absY <= 3115
                && player.absX >= 3297 && player.absX <= 3320;
    }

    private static boolean isNearShantayRugMerchant(Player player) {
        return player.heightLevel == 0 && AgentKnowledgeBase.distance(player.absX, player.absY, 3311, 3109) <= 4;
    }

    static boolean shouldUseDesertReturnTransit(String landmark) {
        if (landmark == null) {
            return false;
        }
        String normalized = landmark.trim().toLowerCase().replace('_', ' ');
        return normalized.length() > 0
                && normalized.indexOf("nardah") < 0
                && normalized.indexOf("seddu") < 0
                && normalized.indexOf("shantay") < 0;
    }

    static boolean shouldRideNardahCarpetToPollnivneach(int x, int y, int height, String landmark) {
        return shouldUseDesertReturnTransit(landmark) && isNearNardah(x, y, height);
    }

    static boolean shouldWalkToPollnivneachRugStation(int x, int y, int height, String landmark) {
        return shouldUseDesertReturnTransit(landmark)
                && isInPollnivneachReturnArea(x, y, height)
                && !isNearPollnivneachRugStation(x, y, height);
    }

    static boolean shouldRidePollnivneachCarpetToShantay(int x, int y, int height, String landmark) {
        return shouldUseDesertReturnTransit(landmark) && isNearPollnivneachRugStation(x, y, height);
    }

    static boolean shouldWalkToShantayGateFromSouth(int x, int y, int height, String landmark) {
        return shouldUseDesertReturnTransit(landmark)
                && isSouthOfShantayGate(x, y, height)
                && !isAtShantayGateSouth(x, y, height);
    }

    static boolean shouldUseShantayGateFromSouth(int x, int y, int height, String landmark) {
        return shouldUseDesertReturnTransit(landmark) && isAtShantayGateSouth(x, y, height);
    }

    private static boolean isInPollnivneachReturnArea(int x, int y, int height) {
        return height == 0 && x >= 3330 && x <= 3385 && y >= 2935 && y <= 3020;
    }

    private static boolean isNearPollnivneachRugStation(int x, int y, int height) {
        return height == 0 && AgentKnowledgeBase.distance(x, y, POLLNIVNEACH_RUG_X, POLLNIVNEACH_RUG_Y) <= 4;
    }

    private static boolean isSouthOfShantayGate(int x, int y, int height) {
        return height == 0 && y <= SHANTAY_GATE_SOUTH_Y
                && x >= 3297 && x <= 3320;
    }

    private static boolean isAtShantayGateSouth(int x, int y, int height) {
        return height == 0 && y == SHANTAY_GATE_SOUTH_Y
                && x >= 3297 && x <= 3311;
    }

    private static Npc nearestNpc(Player player, int npcType, int maxDistance) {
        Npc nearest = null;
        int nearestDistance = Integer.MAX_VALUE;
        for (Npc npc : NpcHandler.npcs) {
            if (npc == null || npc.isDead || npc.npcType != npcType || npc.heightLevel != player.heightLevel) {
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
            return finishFoodRestock(player, goal, "Restocked food for combat training.");
        }
        if (inventoryFood >= minimumReturnFood(desiredFood)
                && AgentToolService.countInventoryRawCookableFood(player) <= 0
                && AgentToolService.countBankFood(player) <= 0
                && AgentToolService.countBankRawCookableFood(player) < MIN_RAW_FOOD_BEFORE_COOKING) {
            return finishFoodRestock(player, goal, "Restocked enough cooked food to resume combat training.");
        }

        JsonObject targetBatchBanking = bankSuppliesForTargetFoodRestockStep(player, goal, desiredFood,
                inventoryFood);
        if (targetBatchBanking != null) {
            return targetBatchBanking;
        }

        JsonObject kebabRestock = buyKebabRestockStep(player, goal, desiredFood, inventoryFood);
        if (kebabRestock != null) {
            return kebabRestock;
        }
        if (shouldVisitBankForFood(player, inventoryRawFood)
                && !shouldPreferTargetShopFoodRestockBeforeBank(player, desiredFood, inventoryFood)) {
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
        JsonObject shopFoodMoney = earnShopFoodMoneyForTargetRestockStep(player, goal, desiredFood, inventoryFood);
        if (shopFoodMoney != null) {
            return shopFoodMoney;
        }
        if (shouldClosePreparationInterface(player.isShopping, player.isBanking)) {
            JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
            result.addProperty("message",
                    "Restocking food: closing the preparation interface before fallback food gathering.");
            return result;
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

    private JsonObject bankSuppliesForTargetFoodRestockStep(Player player, CombatGoal goal, int desiredFood,
            int inventoryFood) {
        int supplyCount = countInventoryTargetAcquisitionBlockingSupplies(player, goal);
        int freeSlots = player.getItemAssistant().freeSlots();
        boolean canBuyFood = hasKebabRestockSource(player);
        if (!shouldBankSuppliesBeforeTargetAcquisition(supplyCount, freeSlots, desiredFood, inventoryFood,
                canBuyFood)) {
            return null;
        }

        if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
            JsonObject result = travelTo(player, supplyBankLandmark(player, goal));
            result.addProperty("message", "Restocking food: banking combat supplies before target-sized shop restock.");
            return result;
        }

        JsonObject result = AgentToolService.handle(player, "deposit_inventory_items",
                targetAcquisitionSupplyArgsWithoutCoins(0, player, goal));
        int depositedItems = depositedInventoryItems(result);
        if (result != null && result.has("success") && result.get("success").getAsBoolean()
                && depositedItems > 0) {
            goal.bankTrips++;
            goal.bankedSupplyItems += depositedItems;
            String message = getString(result, "message", "Deposited combat supplies.");
            result.addProperty("message", "Restocking food: banked combat supplies to free slots for a target-sized batch: "
                    + message);
        }
        return result;
    }

    private JsonObject earnShopFoodMoneyForTargetRestockStep(Player player, CombatGoal goal, int desiredFood,
            int inventoryFood) {
        TargetAcquisitionPlan plan = kebabAcquisitionPlan(player, goal, desiredFood, inventoryFood,
                currentShopItemPrice(player, KEBAB, KEBAB_SHOP_PRICE));
        if (!plan.shouldEarnMoneyBeforeTrip()) {
            return null;
        }

        goal.beginTargetMoney(KEBAB, SHOP_FOOD_MONEY_TARGET_NAME, plan.requiredCoins());
        JsonObject result = earnGearMoneyStep(player, goal);
        if (result != null) {
            String message = getString(result, "message", "batching money-making items.");
            result.addProperty("message", "Restocking food money: batching ore, bars, and sale items toward "
                    + plan.requiredCoins() + " coins for a one-trip kebab restock: " + message);
        }
        return result;
    }

    private JsonObject finishFoodRestock(Player player, CombatGoal goal, String message) {
        goal.restockingFood = false;
        if (shouldClosePreparationInterface(player.isShopping, player.isBanking)) {
            JsonObject result = AgentToolService.handle(player, "close_interfaces", new JsonObject());
            result.addProperty("message", message + " Closing the open preparation interface.");
            return result;
        }
        JsonObject result = AgentToolService.success(message);
        result.add("state", AgentToolService.observeState(player));
        return result;
    }

    static boolean shouldClosePreparationInterface(boolean isShopping, boolean isBanking) {
        return isShopping || isBanking;
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
        boolean onAlKharidSide = isAlKharidSideForGearMoney(player.absX, player.absY);
        boolean reserveReturnToll = shouldReserveAlKharidReturnTollForTarget(goal == null ? "" : goal.area);
        TargetAcquisitionPlan plan = kebabAcquisitionPlan(player, goal, desiredFood, inventoryFood,
                currentShopItemPrice(player, KEBAB, KEBAB_SHOP_PRICE));
        if (plan.shouldDelayTripForFundedBatch()) {
            return null;
        }
        if (!shouldBuyKebabsForFood(inventoryFood, desiredFood, inventoryCoins, bankCoins, freeSlots)
                || !plan.hasEnoughCoinsForTrip()) {
            return null;
        }

        if (plan.shouldSellCarriedItemsBeforeShopTrip()) {
            goal.beginTargetMoney(KEBAB, SHOP_FOOD_MONEY_TARGET_NAME, plan.requiredCoins());
            JsonObject result = sellGearMoneyItemsStep(player, goal, shopFoodMoneyTarget(plan.requiredCoins()));
            result.addProperty("message", "Restocking food: clearing carried money-making items first so the shop trip "
                    + "can buy the planned batch: " + getString(result, "message", "selling carried batch."));
            return result;
        }

        int coinFloat = plan.coinFloat();
        if (shouldWithdrawKebabCoinFloat(inventoryCoins, coinFloat, bankCoins, freeSlots,
                Boundary.isIn(player, Boundary.BANK_AREA), onAlKharidSide)) {
            if (!Boundary.isIn(player, Boundary.BANK_AREA)) {
                JsonObject travel = travelTo(player, onAlKharidSide ? "al kharid bank" : "varrock east bank");
                travel.addProperty("message", "Restocking food: returning to bank for a gate-and-kebab coin float.");
                return travel;
            }
            int amount = Math.min(bankCoins, Math.max(1, coinFloat - inventoryCoins));
            JsonObject result = AgentToolService.handle(player, "withdraw_bank_items", itemAmountArgs(COINS, amount));
            result.addProperty("message", "Restocking food: withdrew a gate-and-kebab coin float for Al Kharid.");
            return result;
        }

        if (inventoryCoins <= 0) {
            return null;
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

        int kebabUnitCost = currentShopItemPrice(player, KEBAB, KEBAB_SHOP_PRICE);
        plan = kebabAcquisitionPlan(player, goal, desiredFood, inventoryFood, kebabUnitCost);
        int amount = plan.affordableBatchAmount();
        if (amount <= 0) {
            return null;
        }
        JsonObject result = AgentToolService.handle(player, "buy_shop_item", itemAmountArgs(KEBAB, amount));
        if (result == null) {
            return AgentToolService.failure("Restocking food: kebab purchase failed; falling back to gathered food.");
        }
        int bought = getInt(result, "bought", 0);
        if (result.has("success") && result.get("success").getAsBoolean()) {
            if (goal != null) {
                goal.withdrawnFoodItems += bought;
            }
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
        int supplyCount = countInventoryCombatSupplies(player, goal);
        if (shouldDepositSuppliesDuringFoodRestock(supplyCount, player.getItemAssistant().freeSlots())) {
            JsonObject result = AgentToolService.handle(player, "deposit_inventory_items",
                    combatSupplyArgs(0, player, goal));
            int depositedItems = depositedInventoryItems(result);
            int depositedAmount = getInt(result, "depositedAmount", depositedItems);
            if (result != null && result.has("success") && result.get("success").getAsBoolean()) {
                int remainingSupplyCount = countInventoryCombatSupplies(player, goal);
                if (supplyDepositMadeProgress(supplyCount, depositedAmount, remainingSupplyCount)) {
                    goal.bankTrips++;
                    goal.bankedSupplyItems += depositedItems;
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
        if (shouldPreferTargetFoodAcquisitionOverSmallRawBatch(inventoryFood, desiredFood, availableRawFood,
                hasKebabRestockSource(player))) {
            return null;
        }
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

    static int depositedInventoryItems(JsonObject result) {
        if (result == null) {
            return 0;
        }
        return getInt(result, "deposited", getInt(result, "depositedAmount", 0));
    }

    static boolean shouldDepositSuppliesDuringFoodRestock(int supplyCount, int freeSlots) {
        return supplyCount > 0 && (freeSlots <= 0 || supplyCount >= SUPPLY_COUNT_BEFORE_BANKING);
    }

    private static JsonObject combatSupplyArgs(int maxDistance) {
        return combatSupplyArgs(maxDistance, null, null);
    }

    private static JsonObject combatSupplyArgs(int maxDistance, Player player, CombatGoal goal) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        addItemIds(itemIds, COMBAT_SUPPLY_ITEM_IDS);
        for (int itemId : COMBAT_GEAR_ITEM_IDS) {
            if (!shouldExcludeFromCombatSupplyBanking(player, itemId, goal)) {
                itemIds.add(itemId);
            }
        }
        arguments.add("itemIds", itemIds);
        if (maxDistance > 0) {
            arguments.addProperty("maxDistance", maxDistance);
        }
        return arguments;
    }

    private static JsonObject combatSupplyArgsWithoutCoins(int maxDistance, Player player, CombatGoal goal) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        addItemIds(itemIds, BANK_TRIGGER_COMBAT_SUPPLY_ITEM_IDS);
        for (int itemId : COMBAT_GEAR_ITEM_IDS) {
            if (!shouldExcludeFromCombatSupplyBanking(player, itemId, goal)) {
                itemIds.add(itemId);
            }
        }
        arguments.add("itemIds", itemIds);
        if (maxDistance > 0) {
            arguments.addProperty("maxDistance", maxDistance);
        }
        return arguments;
    }

    private static JsonObject targetAcquisitionSupplyArgsWithoutCoins(int maxDistance, Player player, CombatGoal goal) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        for (int itemId : BANK_TRIGGER_COMBAT_SUPPLY_ITEM_IDS) {
            if (isTargetAcquisitionBlockingSupplyItem(itemId)) {
                itemIds.add(itemId);
            }
        }
        for (int itemId : COMBAT_GEAR_ITEM_IDS) {
            if (!shouldExcludeFromCombatSupplyBanking(player, itemId, goal)) {
                itemIds.add(itemId);
            }
        }
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

    private static JsonObject optionArgs(int option) {
        JsonObject arguments = new JsonObject();
        arguments.addProperty("option", option);
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

    static JsonObject gearMoneyOreArgs(String ore, int x, int y) {
        return gearMoneyOreArgs(ore, x, y, true);
    }

    static JsonObject gearMoneyOreArgs(String ore, int x, int y, boolean waitForLocalRespawn) {
        JsonObject arguments = oreArgs(ore);
        if (waitForLocalRespawn && isGearMoneyMine(ore, x, y)) {
            arguments.addProperty("maxDistance", GEAR_MONEY_LOCAL_MINING_SCAN_DISTANCE);
            arguments.addProperty("waitForLocalRespawn", true);
        }
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
        return gearMoneySellArgs(null, null);
    }

    private static JsonObject gearMoneySellArgs(CombatGoal goal) {
        return gearMoneySellArgs(null, goal);
    }

    private static JsonObject gearMoneySellArgs(Player player, CombatGoal goal) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        if (shouldLiquidateStagedGearMoneyItems(goal)) {
            addItemIds(itemIds, GEAR_MONEY_ITEM_IDS);
        }
        addGearMoneySaleItemIds(itemIds, goal);
        addStackedGearMoneyProductItemIds(itemIds, player);
        arguments.add("itemIds", itemIds);
        arguments.addProperty("amount", Integer.MAX_VALUE);
        return arguments;
    }

    private static JsonObject gearMoneyBatchBankArgs() {
        return gearMoneyBatchBankArgs(null);
    }

    private static JsonObject gearMoneyBatchBankArgs(CombatGoal goal) {
        return gearMoneyBatchBankArgs(null, goal);
    }

    private static JsonObject gearMoneyBatchBankArgs(Player player, CombatGoal goal) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        addGearMoneyItemIds(itemIds, goal);
        addStackedGearMoneyProductItemIds(itemIds, player);
        arguments.add("itemIds", itemIds);
        arguments.addProperty("amount", Integer.MAX_VALUE);
        return arguments;
    }

    private static JsonObject gearMoneyRawMaterialsBankArgs() {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        addItemIds(itemIds, GEAR_MONEY_RAW_MATERIAL_ITEM_IDS);
        arguments.add("itemIds", itemIds);
        arguments.addProperty("amount", Integer.MAX_VALUE);
        return arguments;
    }

    private static void addGearMoneyItemIds(JsonArray itemIds) {
        addGearMoneyItemIds(itemIds, null);
    }

    private static void addGearMoneyItemIds(JsonArray itemIds, CombatGoal goal) {
        addItemIds(itemIds, GEAR_MONEY_ITEM_IDS);
        addGearMoneySaleItemIds(itemIds, goal);
    }

    private static void addGearMoneySaleItemIds(JsonArray itemIds) {
        addGearMoneySaleItemIds(itemIds, null);
    }

    private static void addGearMoneySaleItemIds(JsonArray itemIds, CombatGoal goal) {
        addSmithingProductItemIds(itemIds);
        if (goal != null && isTrackedGearMoneyProductItem(goal.gearMoneyCraftedProductItemId, goal)) {
            itemIds.add(goal.gearMoneyCraftedProductItemId);
        }
    }

    private static void addSmithingProductItemIds(JsonArray itemIds) {
        for (SmithingData data : SmithingData.values()) {
            if (isGearMoneySaleItem(data.getId())) {
                itemIds.add(data.getId());
            }
        }
    }

    private static void addStackedGearMoneyProductItemIds(JsonArray itemIds, Player player) {
        if (player == null) {
            return;
        }
        for (SmithingData data : SmithingData.values()) {
            int itemId = data.getId();
            if (isStackedGearMoneyProductItem(itemId,
                    AgentToolService.countInventoryItem(player, itemId) + AgentToolService.countBankItem(player, itemId))) {
                itemIds.add(itemId);
            }
        }
    }

    private static JsonObject gearMoneyClutterArgs(Player player) {
        return gearMoneyClutterArgs(player, null);
    }

    private static JsonObject gearMoneyClutterArgs(Player player, CombatGoal goal) {
        JsonObject arguments = new JsonObject();
        JsonArray itemIds = new JsonArray();
        boolean bankExcessFood = shouldBankExcessGearMoneyFood(AgentToolService.countInventoryFood(player));
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (isGearMoneyClutterItemForBanking(player, itemId, goal)
                    || bankExcessFood && AgentToolService.isAgentFood(itemId)) {
                itemIds.add(itemId);
            }
        }
        arguments.add("itemIds", itemIds);
        if (bankExcessFood) {
            arguments.addProperty("keepFoodCount", GEAR_MONEY_FOOD_BUFFER);
        }
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
        JsonObject desertReturn = prepareDesertReturnTransit(player, landmark);
        if (desertReturn != null) {
            return desertReturn;
        }
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

    private static JsonObject prepareDesertReturnTransit(Player player, String landmark) {
        if (player == null || !shouldUseDesertReturnTransit(landmark)) {
            return null;
        }
        if (shouldRideNardahCarpetToPollnivneach(player.absX, player.absY, player.heightLevel, landmark)) {
            return rideDesertCarpet(player, POLLNIVNEACH_RUG_X, POLLNIVNEACH_RUG_Y,
                    "Leaving the Nardah area by normal carpet travel toward Pollnivneach.");
        }
        if (shouldRidePollnivneachCarpetToShantay(player.absX, player.absY, player.heightLevel, landmark)) {
            return rideDesertCarpet(player, SHANTAY_RUG_RETURN_X, SHANTAY_RUG_RETURN_Y,
                    "Leaving Pollnivneach by normal carpet travel toward Shantay Pass.");
        }
        if (shouldWalkToPollnivneachRugStation(player.absX, player.absY, player.heightLevel, landmark)) {
            JsonObject result = AgentToolService.handle(player, "walk_to_tile",
                    walkTileArgs(POLLNIVNEACH_RUG_X, POLLNIVNEACH_RUG_Y, 0));
            result.addProperty("message", "Walking to the Pollnivneach rug station for the return trip.");
            return result;
        }
        if (shouldUseShantayGateFromSouth(player.absX, player.absY, player.heightLevel, landmark)) {
            player.stopMovement();
            player.endCurrentTask();
            player.getPlayerAssistant().resetFollow();
            player.getCombatAssistant().resetPlayerAttack();
            player.objectX = player.absX;
            player.objectY = player.absY + 1;
            OtherObjects.initShantay(player, SHANTAY_GATE_OBJECT);
            JsonObject result = AgentToolService.success(
                    "Passed north through the Shantay gate using normal gate interaction.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        if (shouldWalkToShantayGateFromSouth(player.absX, player.absY, player.heightLevel, landmark)) {
            JsonObject result = AgentToolService.handle(player, "walk_to_tile",
                    walkTileArgs(SHANTAY_GATE_SOUTH_X, SHANTAY_GATE_SOUTH_Y, 0));
            result.addProperty("message", "Walking to the south side of the Shantay gate before returning north.");
            return result;
        }
        return null;
    }

    private static JsonObject rideDesertCarpet(Player player, int x, int y, String message) {
        if (AgentToolService.countInventoryItem(player, COINS) < NARDAH_CARPET_FARE) {
            JsonObject result = AgentToolService.failure("Need 200 coins for the normal desert carpet return route.");
            result.add("state", AgentToolService.observeState(player));
            return result;
        }
        CarpetTravel.carpetTravel(player, x, y);
        JsonObject result = AgentToolService.success(message);
        result.add("state", AgentToolService.observeState(player));
        return result;
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

    static boolean isNearLandmarkTarget(String landmarkName, int x, int y, int height, int maxDistance) {
        AgentKnowledgeBase.Landmark landmark = AgentKnowledgeBase.findLandmark(landmarkName);
        if (landmark == null || landmark.getTarget().height != height) {
            return false;
        }
        return AgentKnowledgeBase.distance(x, y, landmark.getTarget().x, landmark.getTarget().y) <= maxDistance;
    }

    private static boolean shouldAcquireCombatGear(Player player, CombatGoal goal) {
        if (goal == null || player == null) {
            return false;
        }
        if (shouldDeferGearCheck(goal.actionsRun, goal.lastGearAttemptAction)) {
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

    private static boolean shouldAcquirePickaxeUpgrade(Player player, CombatGoal goal) {
        if (goal == null || player == null) {
            return false;
        }
        PickaxeTarget target = nextPickaxeUpgrade(player);
        return shouldAcquirePickaxeUpgrade(goal.actionsRun, goal.lastGearAttemptAction, isPlayerInCombat(player),
                target != null, goal.isPickaxeUpgradeDeferred(target));
    }

    static boolean shouldAcquirePickaxeUpgrade(int actionsRun, int lastGearAttemptAction, boolean inCombat,
            boolean hasUpgrade, boolean deferred) {
        return hasUpgrade
                && !deferred
                && !inCombat
                && !shouldDeferGearCheck(actionsRun, lastGearAttemptAction);
    }

    private static boolean shouldEarnGearMoney(Player player, CombatGoal goal) {
        if (goal == null || player == null) {
            return false;
        }
        if (shouldDeferGearCheck(goal.actionsRun, goal.lastGearAttemptAction)) {
            return false;
        }
        if (isPlayerInCombat(player)) {
            return false;
        }
        GearTarget target = nextDesiredGearMoneyTarget(player, goal);
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        if (target != null) {
            return shouldEarnGearMoneyForTargetCosts(spendableCoins,
                    estimatedGearAcquisitionCost(target, player), -1);
        }
        PickaxeTarget pickaxeTarget = nextDesiredPickaxeMoneyTarget(player, goal);
        return shouldEarnGearMoneyForTargetCosts(spendableCoins, -1,
                pickaxeTarget == null ? -1 : pickaxeTarget.estimatedPrice);
    }

    static boolean shouldDeferGearCheck(int actionsRun, int lastGearAttemptAction) {
        return actionsRun - lastGearAttemptAction < GEAR_CHECK_INTERVAL_ACTIONS;
    }

    static boolean shouldEarnGearMoneyForTargetCosts(int spendableCoins, int gearTargetCost, int pickaxeTargetCost) {
        if (gearTargetCost > 0) {
            return spendableCoins < gearTargetCost;
        }
        return pickaxeTargetCost > 0 && spendableCoins < pickaxeTargetCost;
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
        if (shouldSaveForWeaponBeforeArmor(player, attackLevel, strengthLevel, spendableCoins,
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
        GearTarget helm = bestActionableGearTarget(player, HELM_GEAR_TARGETS, defenceLevel, spendableCoins);
        if (helm != null) {
            return helm;
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
        GearTarget helm = bestDesiredGearTarget(player, HELM_GEAR_TARGETS, defenceLevel);
        if (helm != null) {
            return helm;
        }
        return null;
    }

    private static GearTarget nextDesiredGearMoneyTarget(Player player, CombatGoal goal) {
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int strengthLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.STRENGTH]);
        int defenceLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.DEFENCE]);
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        int targetLevel = goal == null ? DEFAULT_GOAL_TARGET_LEVEL : goal.targetLevel;
        int bestWeaponTier = bestEquippedGearTier(player, WEAPON_GEAR_TARGETS);
        GearTarget weapon = bestDesiredGearTarget(player, WEAPON_GEAR_TARGETS, attackLevel, bestWeaponTier);
        if (weapon != null && !shouldDeferExpensiveWeaponUpgradeForCombat(attackLevel, strengthLevel, targetLevel,
                spendableCoins, bestWeaponTier, weapon)) {
            return weapon;
        }
        GearTarget body = bestDesiredGearTarget(player, BODY_GEAR_TARGETS, defenceLevel,
                bestEquippedGearTier(player, BODY_GEAR_TARGETS));
        if (body != null) {
            return body;
        }
        GearTarget legs = bestDesiredGearTarget(player, LEGS_GEAR_TARGETS, defenceLevel,
                bestEquippedGearTier(player, LEGS_GEAR_TARGETS));
        if (legs != null) {
            return legs;
        }
        GearTarget shield = bestDesiredGearTarget(player, SHIELD_GEAR_TARGETS, defenceLevel,
                bestEquippedGearTier(player, SHIELD_GEAR_TARGETS));
        if (shield != null) {
            return shield;
        }
        return bestDesiredGearTarget(player, HELM_GEAR_TARGETS, defenceLevel,
                bestEquippedGearTier(player, HELM_GEAR_TARGETS));
    }

    private static PickaxeTarget nextDesiredPickaxeMoneyTarget(Player player, CombatGoal goal) {
        int miningLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.MINING]);
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        int itemId = recommendedPickaxeMoneyUpgradeId(miningLevel, bestOwnedPickaxeTier(player), spendableCoins);
        PickaxeTarget target = itemId <= 0 ? null : pickaxeTargetByItemId(itemId);
        return goal != null && goal.isPickaxeUpgradeDeferred(target) ? null : target;
    }

    private static GearTarget pickaxeMoneyGearTarget(PickaxeTarget target) {
        return target == null ? null : new GearTarget(target.itemId, target.requiredMiningLevel, target.tier,
                target.landmarkName, target.shopName, target.estimatedPrice);
    }

    private static boolean isShopFoodMoneyTarget(CombatGoal goal) {
        return goal != null && goal.gearMoneyTargetItemId == KEBAB;
    }

    private static GearTarget shopFoodMoneyTarget(int targetCoins) {
        return new GearTarget(KEBAB, 0, 0, "al kharid kebab shop", "kebab",
                Math.max(1, targetCoins));
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
                || containsGearTarget(HELM_GEAR_TARGETS, first) && containsGearTarget(HELM_GEAR_TARGETS, second)
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

    static boolean shouldPrioritizePickaxeUpgradeOverGear(int gearItemId, int pickaxeItemId) {
        if (gearItemId <= 0 || pickaxeItemId <= 0) {
            return false;
        }
        GearTarget gearTarget = gearTargetByItemId(gearItemId);
        return gearTarget != null && !containsGearTarget(WEAPON_GEAR_TARGETS, gearTarget);
    }

    private static GearTarget bestActionableGearTarget(Player player, GearTarget[] targets, int level,
            int spendableCoins) {
        int bestEquippedTier = bestEquippedGearTier(player, targets);
        GearTarget best = null;
        for (GearTarget target : targets) {
            if (level < target.minLevel || target.tier <= bestEquippedTier
                    || !isGearTargetAvailable(player, target)) {
                continue;
            }
            if (AgentToolService.countInventoryItem(player, target.itemId) > 0
                    || AgentToolService.countBankItem(player, target.itemId) > 0
                    || spendableCoins >= estimatedGearAcquisitionCost(target, player)) {
                best = target;
            }
        }
        return best;
    }

    private static GearTarget bestDesiredGearTarget(Player player, GearTarget[] targets, int level) {
        return bestDesiredGearTarget(player, targets, level, bestEquippedGearTier(player, targets));
    }

    private static GearTarget bestDesiredGearTarget(Player player, GearTarget[] targets, int level,
            int bestEquippedTier) {
        GearTarget best = null;
        for (GearTarget target : targets) {
            if (level >= target.minLevel && target.tier > bestEquippedTier
                    && isGearTargetAvailable(player, target)) {
                best = target;
            }
        }
        return best;
    }

    static int recommendedWeaponUpgradeId(int attackLevel, int bestOwnedTier) {
        GearTarget target = recommendedGearTarget(WEAPON_GEAR_TARGETS, attackLevel);
        return target != null && target.tier > bestOwnedTier ? target.itemId : -1;
    }

    static int recommendedGearMoneyUpgradeId(int attackLevel, int strengthLevel, int defenceLevel,
            int spendableCoins, int bestWeaponTier, int bestBodyTier, int bestHelmTier, int bestLegsTier,
            int bestShieldTier, int targetLevel) {
        return recommendedGearMoneyUpgradeId(attackLevel, strengthLevel, defenceLevel, spendableCoins,
                bestWeaponTier, bestBodyTier, bestHelmTier, bestLegsTier, bestShieldTier, targetLevel, true);
    }

    static int recommendedGearMoneyUpgradeId(int attackLevel, int strengthLevel, int defenceLevel,
            int spendableCoins, int bestWeaponTier, int bestBodyTier, int bestHelmTier, int bestLegsTier,
            int bestShieldTier, int targetLevel, boolean championsGuildAvailable) {
        GearTarget weapon = bestDesiredGearTarget(WEAPON_GEAR_TARGETS, attackLevel, bestWeaponTier,
                championsGuildAvailable);
        if (weapon != null && !shouldDeferExpensiveWeaponUpgradeForCombat(attackLevel, strengthLevel, targetLevel,
                spendableCoins, bestWeaponTier, weapon)) {
            return weapon.itemId;
        }
        GearTarget body = bestDesiredGearTarget(BODY_GEAR_TARGETS, defenceLevel, bestBodyTier,
                championsGuildAvailable);
        if (body != null) {
            return body.itemId;
        }
        GearTarget legs = bestDesiredGearTarget(LEGS_GEAR_TARGETS, defenceLevel, bestLegsTier,
                championsGuildAvailable);
        if (legs != null) {
            return legs.itemId;
        }
        GearTarget shield = bestDesiredGearTarget(SHIELD_GEAR_TARGETS, defenceLevel, bestShieldTier,
                championsGuildAvailable);
        if (shield != null) {
            return shield.itemId;
        }
        GearTarget helm = bestDesiredGearTarget(HELM_GEAR_TARGETS, defenceLevel, bestHelmTier,
                championsGuildAvailable);
        if (helm != null) {
            return helm.itemId;
        }
        return -1;
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

    private static boolean shouldSaveForWeaponBeforeArmor(Player player, int attackLevel, int strengthLevel,
            int spendableCoins, int bestWeaponTier) {
        GearTarget target = recommendedGearTarget(player, WEAPON_GEAR_TARGETS, attackLevel);
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
        if (attackLevel >= 40 && strengthLevel >= MIN_STRENGTH_BEFORE_RUNE_WEAPON_SAVINGS) {
            return false;
        }
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

    private static GearTarget recommendedGearTarget(Player player, GearTarget[] targets, int level) {
        GearTarget best = null;
        for (GearTarget target : targets) {
            if (level >= target.minLevel && isGearTargetAvailable(player, target)) {
                best = target;
            }
        }
        return best;
    }

    private static GearTarget bestDesiredGearTarget(GearTarget[] targets, int level, int bestEquippedTier) {
        return bestDesiredGearTarget(targets, level, bestEquippedTier, true);
    }

    private static GearTarget bestDesiredGearTarget(GearTarget[] targets, int level, int bestEquippedTier,
            boolean championsGuildAvailable) {
        GearTarget best = null;
        for (GearTarget target : targets) {
            if (level >= target.minLevel && target.tier > bestEquippedTier
                    && isGearTargetAvailable(target, championsGuildAvailable)) {
                best = target;
            }
        }
        return best;
    }

    static boolean isChampionsGuildGearAvailable(int itemId, int questPoints) {
        GearTarget target = gearTargetByItemId(itemId);
        return target != null && isGearTargetAvailable(target, questPoints >= CHAMPIONS_GUILD_QUEST_POINTS);
    }

    private static boolean isGearTargetAvailable(Player player, GearTarget target) {
        return target != null && isGearTargetAvailable(target,
                player != null && player.questPoints >= CHAMPIONS_GUILD_QUEST_POINTS);
    }

    private static boolean isGearTargetAvailable(GearTarget target, boolean championsGuildAvailable) {
        return target != null && (!isChampionsGuildGearTarget(target) || championsGuildAvailable);
    }

    private static boolean isChampionsGuildGearTarget(GearTarget target) {
        return target != null && isChampionsGuildRuneStoreLandmark(target.landmark);
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
        target = gearTargetByItemId(HELM_GEAR_TARGETS, itemId);
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
        return shouldBankCombatSupplies(player, null);
    }

    private static boolean shouldBankCombatSupplies(Player player, CombatGoal goal) {
        int supplyCount = countInventoryCombatSupplies(player, goal);
        return shouldBankCombatSupplyCount(supplyCount, player.getItemAssistant().freeSlots());
    }

    static boolean shouldBankCombatSupplyCount(int supplyCount, int freeSlots) {
        return supplyCount > 0
                && (freeSlots <= 0
                || supplyCount >= SUPPLY_COUNT_BEFORE_BANKING
                        && freeSlots <= MIN_FREE_LOOT_SLOTS_BEFORE_SUPPLY_BANKING);
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
        int attackLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.ATTACK]);
        int strengthLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.STRENGTH]);
        int defenceLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.DEFENCE]);
        int hitpointsLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.HITPOINTS]);
        int retreatAt = AgentCombatPlanner.retreatAtHitpoints(hitpointsLevel);
        if (player.playerLevel[Constants.HITPOINTS] <= retreatAt + 2 && inventoryFood <= 0) {
            return true;
        }
        boolean hasRestockSource = hasFoodRestockSource(player);
        if (inventoryFood <= MIN_FOOD_BEFORE_RESTOCK && hasRestockSource) {
            return true;
        }
        return shouldRestockForBetterTrainingArea(attackLevel, strengthLevel, defenceLevel, hitpointsLevel,
                inventoryFood, AgentToolService.countBankFood(player), hasKebabRestockSource(player),
                hasRestockSource, goal.fixedArea);
    }

    static boolean shouldRestockForBetterTrainingArea(int attackLevel, int strengthLevel, int defenceLevel,
            int hitpointsLevel, int inventoryFood, int bankFood, boolean canBuyFood, boolean canGatherFood,
            boolean fixedArea) {
        if (fixedArea || inventoryFood < 0) {
            return false;
        }
        int meleeAverage = (attackLevel + strengthLevel + defenceLevel) / 3;
        int desiredFood = meleeAverage >= 20 ? DESIRED_HIGH_LEVEL_FOOD : DESIRED_LOW_LEVEL_FOOD;
        int restockedFood = Math.min(desiredFood, inventoryFood + Math.max(0, bankFood));
        if (canBuyFood || canGatherFood) {
            restockedFood = desiredFood;
        }
        if (restockedFood <= inventoryFood) {
            return false;
        }
        if (inventoryFood >= minimumReturnFood(desiredFood)) {
            return false;
        }
        AgentCombatPlanner.TrainingArea currentArea = AgentCombatPlanner.recommendedArea(attackLevel, strengthLevel,
                defenceLevel, hitpointsLevel, inventoryFood);
        AgentCombatPlanner.TrainingArea restockedArea = AgentCombatPlanner.recommendedArea(attackLevel, strengthLevel,
                defenceLevel, hitpointsLevel, restockedFood);
        return !currentArea.getName().equals(restockedArea.getName());
    }

    private static boolean shouldVisitBankForFood(Player player, int inventoryRawFood) {
        return shouldVisitBankForFood(inventoryRawFood, AgentToolService.countBankFood(player),
                AgentToolService.countBankRawCookableFood(player), hasFoodToolInInventory(player),
                hasFoodToolInBank(player), countInventoryCombatSupplies(player),
                player.getItemAssistant().freeSlots(), Boundary.isIn(player, Boundary.BANK_AREA));
    }

    private static boolean shouldPreferTargetShopFoodRestockBeforeBank(Player player, int desiredFood,
            int inventoryFood) {
        return shouldPreferTargetShopFoodRestockBeforeBank(inventoryFood, desiredFood,
                AgentToolService.countBankFood(player), AgentToolService.countBankRawCookableFood(player),
                hasKebabRestockSource(player), player.getItemAssistant().freeSlots());
    }

    static boolean shouldPreferTargetShopFoodRestockBeforeBank(int inventoryFood, int desiredFood, int bankFood,
            int bankRawFood, boolean canBuyTargetFood, int freeSlots) {
        if (!canBuyTargetFood || inventoryFood >= desiredFood || freeSlots <= 0) {
            return false;
        }
        if (inventoryFood + Math.max(0, bankFood) >= desiredFood) {
            return false;
        }
        if (bankRawFood >= MIN_RAW_FOOD_BEFORE_COOKING && inventoryFood + bankRawFood >= desiredFood) {
            return false;
        }
        return inventoryFood + freeSlots >= desiredFood;
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
                || AgentToolService.countBankItem(player, COINS) > 0
                || hasTargetMoneyMakingSource(player, null);
    }

    private static boolean hasTargetMoneyMakingSource(Player player, CombatGoal goal) {
        return hasPickaxeInInventory(player)
                || bestBankPickaxe(player) > 0
                || countInventoryGearMoneyItems(player) > 0
                || countInventoryGearMoneyProducts(player, goal) > 0
                || countBankGearMoneyItems(player, goal) > 0
                || hasBankedSmeltableGearMoneyOres(player)
                || countBankProcessableGearMoneyItems(player) > 0;
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

    static boolean shouldEarnShopFoodMoneyForTargetAcquisition(int inventoryFood, int desiredFood,
            int inventoryCoins, int bankCoins, int targetCoins, boolean canMakeMoney) {
        return shouldEarnMoneyForTargetAcquisition(inventoryFood, desiredFood, inventoryCoins, bankCoins,
                targetCoins, canMakeMoney);
    }

    static boolean shouldEarnMoneyForTargetAcquisition(int currentCount, int targetCount,
            int inventoryCoins, int bankCoins, int targetCoins, boolean canMakeMoney) {
        return currentCount < targetCount
                && targetCoins > 0
                && inventoryCoins + bankCoins < targetCoins
                && canMakeMoney;
    }

    static boolean shouldDelayTargetAcquisitionTripForFundedBatch(int currentCount, int targetCount,
            int inventoryCoins, int bankCoins, int targetCoins, boolean canMakeMoney) {
        return shouldEarnMoneyForTargetAcquisition(currentCount, targetCount, inventoryCoins, bankCoins,
                targetCoins, canMakeMoney);
    }

    static boolean shouldWithdrawKebabCoinFloat(int inventoryCoins, int targetCoinFloat, int bankCoins,
            int freeSlots, boolean inBankArea, boolean onAlKharidSide) {
        if (bankCoins <= 0 || inventoryCoins >= targetCoinFloat) {
            return false;
        }
        if (inBankArea) {
            return freeSlots > 0 || inventoryCoins > 0;
        }
        return !onAlKharidSide && inventoryCoins < AL_KHARID_GATE_TOLL;
    }

    static int kebabCoinFloat(int desiredFood, int inventoryFood, int freeSlots, int bankCoins) {
        return kebabCoinFloat(desiredFood, inventoryFood, freeSlots, 0, bankCoins, 0, AL_KHARID_GATE_TOLL,
                KEBAB_SHOP_PRICE);
    }

    static int kebabCoinFloat(int desiredFood, int inventoryFood, int freeSlots, int bankCoins, int entryCost,
            int reserveCoins) {
        return kebabCoinFloat(desiredFood, inventoryFood, freeSlots, 0, bankCoins, entryCost, reserveCoins,
                KEBAB_SHOP_PRICE);
    }

    static int kebabCoinFloat(int desiredFood, int inventoryFood, int freeSlots, int inventoryCoins, int bankCoins,
            int entryCost, int reserveCoins, int unitCost) {
        return targetAcquisitionCoinFloat(desiredFood, inventoryFood, freeSlots, inventoryCoins, bankCoins,
                entryCost, reserveCoins, unitCost, KEBAB_RESTOCK_COIN_FLOAT);
    }

    static int targetAcquisitionBatchAmount(int targetCount, int currentCount, int freeSlots) {
        return Math.max(0, Math.min(Math.max(0, freeSlots), Math.max(0, targetCount - currentCount)));
    }

    static int targetAcquisitionEffectiveFreeSlots(int freeSlots, int carriedSaleItems) {
        return Math.min(28, Math.max(0, freeSlots) + Math.max(0, carriedSaleItems));
    }

    static boolean shouldPreferTargetFoodAcquisitionOverSmallRawBatch(int inventoryFood, int desiredFood,
            int availableRawFood, boolean canAcquireTarget) {
        return inventoryFood < desiredFood
                && availableRawFood > 0
                && availableRawFood < MIN_RAW_FOOD_BEFORE_COOKING
                && canAcquireTarget;
    }

    static int targetAcquisitionRequiredCoins(int targetCount, int currentCount, int freeSlots,
            int entryCost, int reserveCoins, int unitCost, int minimumFloat) {
        int desiredItems = targetAcquisitionBatchAmount(targetCount, currentCount, freeSlots);
        if (desiredItems <= 0) {
            return 0;
        }
        int desiredCoins = Math.max(0, entryCost)
                + Math.max(0, reserveCoins)
                + desiredItems * Math.max(1, unitCost);
        return Math.max(desiredCoins, Math.max(0, minimumFloat));
    }

    static int targetAcquisitionCoinFloat(int targetCount, int currentCount, int freeSlots, int inventoryCoins,
            int bankCoins, int entryCost, int reserveCoins, int unitCost, int minimumFloat) {
        int targetCoins = targetAcquisitionRequiredCoins(targetCount, currentCount, freeSlots, entryCost,
                reserveCoins, unitCost, minimumFloat);
        if (targetCoins <= 0) {
            return 0;
        }
        int availableCoins = Math.max(0, inventoryCoins) + Math.max(0, bankCoins);
        return Math.min(availableCoins, Math.max(1, targetCoins));
    }

    static int targetAcquisitionBatchAmount(int targetCount, int currentCount, int freeSlots, int unitCost,
            int reserveCoins, int inventoryCoins) {
        int slotBatch = targetAcquisitionBatchAmount(targetCount, currentCount, freeSlots);
        if (unitCost <= 0) {
            return slotBatch;
        }
        int spendableCoins = Math.max(0, inventoryCoins) - Math.max(0, reserveCoins);
        return Math.max(0, Math.min(slotBatch, spendableCoins / unitCost));
    }

    private static TargetAcquisitionPlan kebabAcquisitionPlan(Player player, CombatGoal goal, int desiredFood,
            int inventoryFood, int unitCost) {
        boolean onAlKharidSide = isAlKharidSideForGearMoney(player.absX, player.absY);
        boolean reserveReturnToll = shouldReserveAlKharidReturnTollForTarget(goal == null ? "" : goal.area);
        int entryCost = !onAlKharidSide && reserveReturnToll ? AL_KHARID_GATE_TOLL : 0;
        int reservedCoins = reserveReturnToll ? AL_KHARID_GATE_TOLL : 0;
        return targetAcquisitionPlan(KEBAB, SHOP_FOOD_MONEY_TARGET_NAME, desiredFood, inventoryFood,
                player.getItemAssistant().freeSlots(),
                countInventoryGearMoneyItems(player) + countInventoryGearMoneyProducts(player, goal),
                AgentToolService.countInventoryItem(player, COINS), AgentToolService.countBankItem(player, COINS),
                entryCost, reservedCoins, unitCost, KEBAB_RESTOCK_COIN_FLOAT,
                hasTargetMoneyMakingSource(player, goal));
    }

    static TargetAcquisitionPlan targetAcquisitionPlan(int itemId, String targetName, int targetCount,
            int currentCount, int freeSlots, int carriedSaleItems, int inventoryCoins, int bankCoins,
            int entryCost, int reserveCoins, int unitCost, int minimumFloat, boolean canMakeMoney) {
        return new TargetAcquisitionPlan(itemId, targetName, targetCount, currentCount, freeSlots,
                carriedSaleItems, inventoryCoins, bankCoins, entryCost, reserveCoins, unitCost, minimumFloat,
                canMakeMoney);
    }

    static boolean shouldBankSuppliesBeforeTargetAcquisition(int supplyCount, int freeSlots, int targetCount,
            int currentCount, boolean canAcquireTarget) {
        if (!canAcquireTarget || supplyCount <= 0) {
            return false;
        }
        int remaining = Math.max(0, targetCount - currentCount);
        if (remaining <= 0) {
            return false;
        }
        int immediateBatch = targetAcquisitionBatchAmount(targetCount, currentCount, freeSlots);
        int bankedCapacity = Math.min(28, Math.max(0, freeSlots) + Math.max(0, supplyCount));
        int bankedBatch = targetAcquisitionBatchAmount(targetCount, currentCount, bankedCapacity);
        if (immediateBatch < remaining && bankedBatch > immediateBatch) {
            return true;
        }
        int immediateFreeSlotsAfterBatch = Math.max(0, freeSlots - Math.min(remaining, immediateBatch));
        int bankedFreeSlotsAfterBatch = Math.max(0, bankedCapacity - Math.min(remaining, bankedBatch));
        return immediateBatch >= remaining
                && immediateFreeSlotsAfterBatch < MIN_FREE_SLOTS_AFTER_TARGET_ACQUISITION
                && bankedFreeSlotsAfterBatch > immediateFreeSlotsAfterBatch;
    }

    static boolean shouldCheckCarriedCombatGear(int actionsRun, int inventoryCombatGearItems) {
        return actionsRun % 60 == 0 && inventoryCombatGearItems > 0;
    }

    static int currentShopItemPrice(Player player, int itemId, int fallbackPrice) {
        if (player == null || !player.isShopping || player.shopId < 0
                || player.shopId >= ShopHandler.shopItems.length) {
            return Math.max(1, fallbackPrice);
        }
        try {
            return Math.max(1, player.getShopAssistant().getItemShopValue(itemId, 0, false));
        } catch (RuntimeException ignored) {
            return Math.max(1, fallbackPrice);
        }
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
        return countInventoryCombatSupplies(player, null);
    }

    private static int countInventoryCombatSupplies(Player player, CombatGoal goal) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (isCombatSupplyItemForBanking(itemId)
                    && !shouldExcludeFromCombatSupplyBanking(player, itemId, goal)) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    static int countInventoryTargetAcquisitionBlockingSupplies(Player player) {
        return countInventoryTargetAcquisitionBlockingSupplies(player, null);
    }

    private static int countInventoryTargetAcquisitionBlockingSupplies(Player player, CombatGoal goal) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (isTargetAcquisitionBlockingSupplyItem(itemId)
                    && !shouldExcludeFromCombatSupplyBanking(player, itemId, goal)) {
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

    static boolean isTargetAcquisitionBlockingSupplyItem(int itemId) {
        return isCombatSupplyItemForBanking(itemId)
                && !AgentToolService.isAgentFood(itemId)
                && !AgentToolService.isRawCookableFood(itemId);
    }

    private static boolean shouldExcludeFromCombatSupplyBanking(Player player, int itemId, CombatGoal goal) {
        return shouldExcludeGearMoneySaleItemFromCombatSupplyBanking(
                goal != null && goal.earningGearMoney,
                goal != null && goal.gearMoneyProcessingStarted,
                goal == null ? 0 : goal.gearMoneyTargetItemId,
                isGearMoneySaleItem(player, itemId, goal));
    }

    static boolean shouldExcludeGearMoneySaleItemFromCombatSupplyBanking(boolean earningGearMoney,
            boolean processingStarted, int gearMoneyTargetItemId, boolean gearMoneySaleItem) {
        return gearMoneySaleItem
                && (earningGearMoney || processingStarted || gearMoneyTargetItemId > 0);
    }

    private static boolean isCombatGearItem(int itemId) {
        for (int gearId : COMBAT_GEAR_ITEM_IDS) {
            if (itemId == gearId) {
                return true;
            }
        }
        return false;
    }

    private static int countInventoryCombatGearItems(Player player) {
        int count = 0;
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            if (isCombatGearItem(storedId - 1)) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
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
        return isGearMoneySmithingCandidateItem(itemId)
                && !isCombatGearItem(itemId);
    }

    static boolean isGearMoneySmithingCandidateItem(int itemId) {
        return AgentSmithingPlanner.isSmithingProduct(itemId)
                && !isLowQualityGearMoneySmithingProduct(itemId)
                && !isAccountStorageItemForBanking(itemId);
    }

    static boolean isGearMoneySaleItem(int itemId) {
        return isGearMoneyProductItem(itemId);
    }

    private static boolean isGearMoneySaleItem(int itemId, CombatGoal goal) {
        return isGearMoneySaleItem(itemId) || isTrackedGearMoneyProductItem(itemId, goal);
    }

    private static boolean isGearMoneySaleItem(Player player, int itemId, CombatGoal goal) {
        return isGearMoneySaleItem(itemId, goal)
                || player != null && isStackedGearMoneyProductItem(itemId,
                        AgentToolService.countInventoryItem(player, itemId) + AgentToolService.countBankItem(player, itemId));
    }

    static boolean isTrackedGearMoneyProductItem(int itemId, int trackedProductItemId) {
        return itemId > 0
                && itemId == trackedProductItemId
                && isGearMoneySmithingCandidateItem(itemId);
    }

    static boolean isStackedGearMoneyProductItem(int itemId, int count) {
        return count >= MIN_STACKED_GEAR_MONEY_PRODUCTS_BEFORE_SALE
                && isGearMoneySmithingCandidateItem(itemId);
    }

    private static boolean isTrackedGearMoneyProductItem(int itemId, CombatGoal goal) {
        return goal != null && isTrackedGearMoneyProductItem(itemId, goal.gearMoneyCraftedProductItemId);
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
        return isGearMoneyClutterItemForBanking(player, itemId, null);
    }

    private static boolean isGearMoneyClutterItemForBanking(Player player, int itemId, CombatGoal goal) {
        if (isTrackedGearMoneyProductItem(itemId, goal)) {
            return false;
        }
        if (isGearMoneySaleItem(player, itemId, goal)) {
            return false;
        }
        return isGearMoneyClutterItemForBanking(itemId)
                || isObsoleteGearMoneyPickaxeForBanking(itemId, bestCarriedUsablePickaxeTier(player));
    }

    static boolean shouldBankExcessGearMoneyFood(int inventoryFood) {
        return excessGearMoneyFoodCount(inventoryFood) > 0;
    }

    static int excessGearMoneyFoodCount(int inventoryFood) {
        return Math.max(0, inventoryFood - GEAR_MONEY_FOOD_BUFFER);
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

    private static int countInventoryRawGearMoneyMaterials(Player player) {
        int count = 0;
        for (int materialItemId : GEAR_MONEY_RAW_MATERIAL_ITEM_IDS) {
            count += AgentToolService.countInventoryItem(player, materialItemId);
        }
        return count;
    }

    private static int countInventoryGearMoneyProducts(Player player) {
        return countInventoryGearMoneyProducts(player, null);
    }

    private static int countInventoryGearMoneyProducts(Player player, CombatGoal goal) {
        int count = 0;
        for (SmithingData data : SmithingData.values()) {
            if (isGearMoneySaleItem(player, data.getId(), goal)) {
                count += AgentToolService.countInventoryItem(player, data.getId());
            }
        }
        return count;
    }

    private static int countInventoryProcessedGearMoneyBars(Player player) {
        return AgentToolService.countInventoryItem(player, BRONZE_BAR)
                + AgentToolService.countInventoryItem(player, IRON_BAR)
                + AgentToolService.countInventoryItem(player, STEEL_BAR)
                + AgentToolService.countInventoryItem(player, MITHRIL_BAR)
                + AgentToolService.countInventoryItem(player, ADAMANT_BAR)
                + AgentToolService.countInventoryItem(player, RUNE_BAR);
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
        if (isGearMoneySmithingCandidateItem(itemId)) {
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
        return estimatedInventoryGearMoneyCoins(player, null);
    }

    private static int estimatedInventoryGearMoneyCoins(Player player, CombatGoal goal) {
        int coins = 0;
        for (SmithingData data : SmithingData.values()) {
            if (isGearMoneySaleItem(player, data.getId(), goal)) {
                coins += AgentToolService.countInventoryItem(player, data.getId())
                        * estimatedGearMoneySellCoins(data.getId());
            }
        }
        if (shouldLiquidateStagedGearMoneyItems(goal)) {
            coins += estimatedInventoryStagedGearMoneyItemCoins(player);
        }
        return coins;
    }

    private static int estimatedBankGearMoneyCoins(Player player) {
        return estimatedBankGearMoneyCoins(player, null);
    }

    private static int estimatedBankGearMoneyCoins(Player player, CombatGoal goal) {
        int coins = 0;
        for (SmithingData data : SmithingData.values()) {
            if (isGearMoneySaleItem(player, data.getId(), goal)) {
                coins += AgentToolService.countBankItem(player, data.getId())
                        * estimatedGearMoneySellCoins(data.getId());
            }
        }
        if (shouldLiquidateStagedGearMoneyItems(goal)) {
            coins += estimatedBankStagedGearMoneyItemCoins(player);
        }
        return coins;
    }

    static boolean shouldLiquidateStagedGearMoneyItemsForTarget(int targetItemId) {
        for (int itemId : TARGET_ACQUISITION_RAW_LIQUIDATION_ITEM_IDS) {
            if (targetItemId == itemId) {
                return true;
            }
        }
        return false;
    }

    private static boolean shouldLiquidateStagedGearMoneyItems(CombatGoal goal) {
        return goal != null && shouldLiquidateStagedGearMoneyItemsForTarget(goal.gearMoneyTargetItemId);
    }

    static int estimatedInventoryStagedGearMoneyItemCoins(Player player) {
        int coins = 0;
        for (int itemId : GEAR_MONEY_ITEM_IDS) {
            coins += AgentToolService.countInventoryItem(player, itemId) * estimatedGearMoneySellCoins(itemId);
        }
        return coins;
    }

    static int estimatedBankStagedGearMoneyItemCoins(Player player) {
        int coins = 0;
        for (int itemId : GEAR_MONEY_ITEM_IDS) {
            coins += AgentToolService.countBankItem(player, itemId) * estimatedGearMoneySellCoins(itemId);
        }
        return coins;
    }

    static int estimatedProcessedGearMoneyPotentialCoins(Player player, int spendableCoins) {
        return estimatedProcessedGearMoneyPotentialCoins(player, spendableCoins, null);
    }

    static int estimatedProcessedGearMoneyPotentialCoins(Player player, int spendableCoins, CombatGoal goal) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        int coins = spendableCoins + estimatedGearMoneyProductCoins(player, goal);

        int bronzeBars = AgentToolService.countInventoryItem(player, BRONZE_BAR)
                + AgentToolService.countBankItem(player, BRONZE_BAR);
        int copperOre = AgentToolService.countInventoryItem(player, COPPER_ORE)
                + AgentToolService.countBankItem(player, COPPER_ORE);
        int tinOre = AgentToolService.countInventoryItem(player, TIN_ORE)
                + AgentToolService.countBankItem(player, TIN_ORE);
        coins += estimatedGearMoneySmithingPotentialSellCoins(smithingLevel, BRONZE_BAR,
                bronzeBars + Math.min(copperOre, tinOre));

        int ironOre = AgentToolService.countInventoryItem(player, IRON_ORE)
                + AgentToolService.countBankItem(player, IRON_ORE);
        int coal = AgentToolService.countInventoryItem(player, COAL) + AgentToolService.countBankItem(player, COAL);
        int steelBars = AgentToolService.countInventoryItem(player, STEEL_BAR)
                + AgentToolService.countBankItem(player, STEEL_BAR);
        if (smithingLevel >= STEEL_SMELTING_SMITHING_LEVEL) {
            int steelBarsFromOre = Math.min(ironOre, coal / STEEL_COAL_PER_BAR);
            steelBars += steelBarsFromOre;
            ironOre -= steelBarsFromOre;
        }
        coins += estimatedGearMoneySmithingPotentialSellCoins(smithingLevel, STEEL_BAR, steelBars);

        int ironBars = AgentToolService.countInventoryItem(player, IRON_BAR)
                + AgentToolService.countBankItem(player, IRON_BAR);
        if (smithingLevel >= IRON_SMELTING_SMITHING_LEVEL) {
            ironBars += ironOre;
        }
        coins += estimatedGearMoneySmithingPotentialSellCoins(smithingLevel, IRON_BAR, ironBars);

        coins += estimatedGearMoneySmithingPotentialSellCoins(smithingLevel, MITHRIL_BAR,
                AgentToolService.countInventoryItem(player, MITHRIL_BAR) + AgentToolService.countBankItem(player, MITHRIL_BAR));
        coins += estimatedGearMoneySmithingPotentialSellCoins(smithingLevel, ADAMANT_BAR,
                AgentToolService.countInventoryItem(player, ADAMANT_BAR) + AgentToolService.countBankItem(player, ADAMANT_BAR));
        coins += estimatedGearMoneySmithingPotentialSellCoins(smithingLevel, RUNE_BAR,
                AgentToolService.countInventoryItem(player, RUNE_BAR) + AgentToolService.countBankItem(player, RUNE_BAR));
        return coins;
    }

    private static int estimatedGearMoneyProductCoins(Player player) {
        return estimatedGearMoneyProductCoins(player, null);
    }

    private static int estimatedGearMoneyProductCoins(Player player, CombatGoal goal) {
        int coins = 0;
        for (SmithingData data : SmithingData.values()) {
            if (isGearMoneyProductItem(data.getId())
                    || isStackedGearMoneyProductItem(data.getId(),
                            AgentToolService.countInventoryItem(player, data.getId())
                                    + AgentToolService.countBankItem(player, data.getId()))) {
                coins += (AgentToolService.countInventoryItem(player, data.getId())
                        + AgentToolService.countBankItem(player, data.getId()))
                        * estimatedGearMoneySellCoins(data.getId());
            } else if (isTrackedGearMoneyProductItem(data.getId(), goal)) {
                coins += (AgentToolService.countInventoryItem(player, data.getId())
                        + AgentToolService.countBankItem(player, data.getId()))
                        * estimatedGearMoneySellCoins(data.getId());
            }
        }
        return coins;
    }

    static int estimatedGearMoneySmithingPotentialSellCoins(int smithingLevel, int barItemId, int availableBars) {
        if (availableBars <= 0) {
            return 0;
        }
        SmithingChoice choice = bestGearMoneySmithingChoice(smithingLevel, barItemId, availableBars);
        if (choice == null || choice.getBarsNeeded() <= 0) {
            return availableBars * estimatedGearMoneySellCoins(barItemId);
        }
        int barsNeeded = choice.getBarsNeeded();
        int productCount = availableBars / barsNeeded;
        int leftoverBars = availableBars % barsNeeded;
        return productCount * estimatedGearMoneySellCoins(choice.getItemId())
                + leftoverBars * estimatedGearMoneySellCoins(barItemId);
    }

    static boolean shouldSellGearMoneyBatch(int spendableCoins, int carriedGearMoneyValue,
            int bankedGearMoneyValue, int targetCost) {
        return spendableCoins + carriedGearMoneyValue + bankedGearMoneyValue >= targetCost;
    }

    static int gearMoneyLiquidityTargetCost(int gearTargetCost, int pickaxeTargetCost) {
        if (pickaxeTargetCost <= 0) {
            return gearTargetCost;
        }
        return Math.min(gearTargetCost, pickaxeTargetCost);
    }

    static boolean shouldBankGearMoneyBatchBeforeTarget(int carriedMoneyItems, int spendableCoins,
            int carriedGearMoneyValue, int bankedGearMoneyValue, int targetCost) {
        return carriedMoneyItems > 0
                && spendableCoins + carriedGearMoneyValue + bankedGearMoneyValue < targetCost;
    }

    static boolean shouldBankGearMoneyCarryoverBeforeCombat(int carriedMoneyItems, boolean earningGearMoney,
            boolean gearingUp) {
        return shouldBankGearMoneyCarryoverBeforeCombat(carriedMoneyItems, earningGearMoney, gearingUp, false);
    }

    static boolean shouldBankGearMoneyCarryoverBeforeCombat(int carriedMoneyItems, boolean earningGearMoney,
            boolean gearingUp, boolean preparingTransitCoins) {
        return carriedMoneyItems > 0 && !earningGearMoney && !gearingUp && !preparingTransitCoins;
    }

    static boolean shouldStopMiningForFundedGearMoneyProcessing(boolean isMining, boolean processingStarted) {
        return isMining && processingStarted;
    }

    static boolean shouldPrepareSteelSmeltingInputs(int smithingLevel, int carriedIronOre, int carriedCoal,
            int bankedIronOre, int bankedCoal, int freeSlots, int carriedProcessedBars, int carriedProducts,
            boolean liquidatingForCombat) {
        return shouldPrepareSteelSmeltingInputs(smithingLevel, carriedIronOre, carriedCoal, bankedIronOre,
                bankedCoal, freeSlots, carriedProcessedBars, carriedProducts, liquidatingForCombat,
                Integer.MIN_VALUE, Integer.MIN_VALUE, false);
    }

    static boolean shouldPrepareSteelSmeltingInputs(int smithingLevel, int carriedIronOre, int carriedCoal,
            int bankedIronOre, int bankedCoal, int freeSlots, int carriedProcessedBars, int carriedProducts,
            boolean liquidatingForCombat, int x, int y) {
        return shouldPrepareSteelSmeltingInputs(smithingLevel, carriedIronOre, carriedCoal, bankedIronOre,
                bankedCoal, freeSlots, carriedProcessedBars, carriedProducts, liquidatingForCombat, x, y, false);
    }

    static boolean shouldPrepareSteelSmeltingInputs(int smithingLevel, int carriedIronOre, int carriedCoal,
            int bankedIronOre, int bankedCoal, int freeSlots, int carriedProcessedBars, int carriedProducts,
            boolean liquidatingForCombat, int x, int y, boolean processingStarted) {
        if (liquidatingForCombat || carriedProcessedBars > 0 || carriedProducts > 0
                || !shouldUseSteelForGearMoney(smithingLevel)) {
            return false;
        }
        int totalIron = carriedIronOre + bankedIronOre;
        int totalCoal = carriedCoal + bankedCoal;
        if (Math.min(totalIron, totalCoal / STEEL_COAL_PER_BAR) <= 0) {
            return false;
        }
        if (!processingStarted
                && shouldDelaySteelCoalPairingForIronBatch(carriedIronOre, carriedCoal, bankedCoal, freeSlots)) {
            return false;
        }
        if (!processingStarted && shouldMineCoalInsteadOfBankingForPairing(carriedIronOre, carriedCoal, freeSlots,
                x, y)) {
            return false;
        }
        return Math.min(carriedIronOre, carriedCoal / STEEL_COAL_PER_BAR) <= 0
                || steelCoalNeededForIron(carriedIronOre, carriedCoal) > 0;
    }

    static boolean shouldUseSteelForGearMoney(int smithingLevel) {
        return smithingLevel >= STEEL_SMELTING_SMITHING_LEVEL
                && canSmithGearMoneyProductFromBar(smithingLevel, STEEL_BAR);
    }

    static int steelCoalNeededForIron(int ironOre, int coal) {
        return Math.max(0, ironOre * STEEL_COAL_PER_BAR - coal);
    }

    static boolean shouldDelaySteelCoalPairingForIronBatch(int carriedIronOre, int carriedCoal, int bankedCoal,
            int freeSlots) {
        int coalNeeded = steelCoalNeededForIron(carriedIronOre, carriedCoal);
        if (carriedIronOre <= 0 || coalNeeded <= 0 || freeSlots <= 0) {
            return false;
        }
        if (bankedCoal < coalNeeded) {
            return true;
        }
        if (freeSlots <= coalNeeded) {
            return false;
        }
        return carriedIronOre < targetSteelIronMiningBatch(carriedIronOre, carriedCoal, bankedCoal, freeSlots);
    }

    static boolean shouldMineCoalInsteadOfBankingForPairing(int carriedIronOre, int carriedCoal, int freeSlots,
            int x, int y) {
        int coalNeeded = steelCoalNeededForIron(carriedIronOre, carriedCoal);
        return coalNeeded > 0 && freeSlots >= coalNeeded && isGearMoneyCoalMine(x, y);
    }

    static int targetSteelIronMiningBatch(int carriedIronOre, int carriedCoal, int bankedCoal, int freeSlots) {
        int totalOreSlots = Math.max(0, carriedIronOre) + Math.max(0, carriedCoal) + Math.max(0, freeSlots);
        int slotLimitedBars = totalOreSlots / (STEEL_COAL_PER_BAR + 1);
        int coalLimitedBars = (Math.max(0, carriedCoal) + Math.max(0, bankedCoal)) / STEEL_COAL_PER_BAR;
        int ironSlotLimitedBars = Math.max(0, carriedIronOre) + Math.max(0, freeSlots);
        return Math.max(1, Math.min(slotLimitedBars, Math.min(coalLimitedBars, ironSlotLimitedBars)));
    }

    static int targetSteelSmeltingBars(int freeSlots, int availableIronOre, int availableCoal) {
        if (freeSlots < STEEL_COAL_PER_BAR + 1 || availableIronOre <= 0 || availableCoal < STEEL_COAL_PER_BAR) {
            return 0;
        }
        int slotLimitedBars = freeSlots / (STEEL_COAL_PER_BAR + 1);
        return Math.min(slotLimitedBars, Math.min(availableIronOre, availableCoal / STEEL_COAL_PER_BAR));
    }

    static boolean shouldBankGearMoneyMaterialsBeforeProcessing(int productionAction, int carriedMoneyItems,
            boolean rawSaleBatchReady, boolean processingBatchReady, boolean liquidatingForCombat, int freeSlots,
            boolean carryingBalancedSteelSmeltingBatch) {
        return productionAction == GEAR_MONEY_PRODUCTION_SMELT
                && carriedMoneyItems > 0
                && !rawSaleBatchReady
                && !processingBatchReady
                && !liquidatingForCombat
                && freeSlots <= 0;
    }

    static boolean shouldBankNearFullGearMoneyBatchBeforeOreSwitch(int carriedMoneyItems, int freeSlots,
            String nextOre, int x, int y) {
        return carriedMoneyItems > 0
                && freeSlots <= MIN_FREE_SLOTS_BEFORE_BANKING
                && isAnyGearMoneyMine(x, y)
                && !isGearMoneyMine(nextOre, x, y);
    }

    static boolean shouldProcessGearMoneyBatch(boolean processingBatchReady, boolean liquidatingForCombat) {
        return processingBatchReady || liquidatingForCombat;
    }

    static boolean shouldProcessGearMoneyBatch(boolean processingBatchReady, boolean liquidatingForCombat,
            boolean processingStarted) {
        return shouldProcessGearMoneyBatch(processingBatchReady, liquidatingForCombat) || processingStarted;
    }

    static boolean isBalancedSteelSmeltingBatch(int ironOre, int coal) {
        return ironOre > 0 && coal >= ironOre * STEEL_COAL_PER_BAR;
    }

    static boolean shouldSellReadyGearMoneyBatchBeforeProcessing(int carriedSaleItems, boolean rawSaleBatchReady,
            int productionAction) {
        return shouldSellReadyGearMoneyBatchBeforeProcessing(carriedSaleItems, rawSaleBatchReady, productionAction,
                false, false);
    }

    static boolean shouldSellReadyGearMoneyBatchBeforeProcessing(int carriedSaleItems, boolean rawSaleBatchReady,
            int productionAction, boolean processingStarted, boolean bankHasProcessableMaterials) {
        return carriedSaleItems > 0
                && rawSaleBatchReady
                && productionAction == GEAR_MONEY_PRODUCTION_NONE
                && !shouldFinishStagedMaterialsBeforeSelling(processingStarted, bankHasProcessableMaterials);
    }

    static boolean shouldWithdrawMoreStoredGearMoneySaleItems(int carriedSaleItems, int bankedSaleItems, int freeSlots,
            boolean rawSaleBatchReady, boolean processingStarted, boolean bankHasProcessableMaterials) {
        return carriedSaleItems > 0
                && bankedSaleItems > 0
                && freeSlots > 0
                && (rawSaleBatchReady || processingStarted)
                && !bankHasProcessableMaterials;
    }

    static boolean shouldStopMiningForFundedTargetAcquisitionSale(boolean mining, boolean targetAcquisitionSale,
            boolean rawSaleBatchReady) {
        return mining && targetAcquisitionSale && rawSaleBatchReady;
    }

    static boolean shouldWithdrawTargetAcquisitionSaleBatch(boolean targetAcquisitionSale, boolean rawSaleBatchReady,
            int carriedSaleItems, int bankedSaleItems, int freeSlots) {
        return targetAcquisitionSale
                && rawSaleBatchReady
                && bankedSaleItems > 0
                && freeSlots > 0;
    }

    static boolean shouldSellTargetAcquisitionSaleBatch(boolean targetAcquisitionSale, boolean rawSaleBatchReady,
            int carriedSaleItems) {
        return targetAcquisitionSale && rawSaleBatchReady && carriedSaleItems > 0;
    }

    static boolean shouldDelayGearMoneyProductionForFullerLoad(int productionAction, int carriedMoneyItems,
            int freeSlots, boolean rawSaleBatchReady, boolean processingBatchReady, boolean liquidatingForCombat,
            boolean carryingBalancedSteelSmeltingBatch, int x, int y) {
        return shouldDelayGearMoneyProductionForFullerLoad(productionAction, carriedMoneyItems, freeSlots,
                rawSaleBatchReady, processingBatchReady, liquidatingForCombat, carryingBalancedSteelSmeltingBatch,
                x, y, false);
    }

    static boolean shouldDelayGearMoneyProductionForFullerLoad(int productionAction, int carriedMoneyItems,
            int freeSlots, boolean rawSaleBatchReady, boolean processingBatchReady, boolean liquidatingForCombat,
            boolean carryingBalancedSteelSmeltingBatch, int x, int y, boolean processingStarted) {
        return productionAction == GEAR_MONEY_PRODUCTION_SMELT
                && carriedMoneyItems > 0
                && freeSlots > 0
                && !rawSaleBatchReady
                && !liquidatingForCombat
                && !carryingBalancedSteelSmeltingBatch
                && (processingStarted || !processingBatchReady || isGearMoneyIronMine(x, y)
                        || isGearMoneyCoalMine(x, y));
    }

    static boolean shouldRememberRawMaterialsBankedAfterProcessingStarted(boolean success, int depositedAmount) {
        return success && depositedAmount > 0;
    }

    static boolean shouldBankCarriedMaterialsAfterProcessingStarted(boolean processingStarted, int carriedMoneyItems,
            int productionAction, int bankedProcessableItems) {
        return shouldBankCarriedMaterialsAfterProcessingStarted(processingStarted, carriedMoneyItems, productionAction,
                bankedProcessableItems > 0);
    }

    static boolean shouldBankCarriedMaterialsAfterProcessingStarted(boolean processingStarted, int carriedMoneyItems,
            int productionAction, boolean bankHasProcessableMaterials) {
        return processingStarted
                && carriedMoneyItems > 0
                && productionAction == GEAR_MONEY_PRODUCTION_NONE
                && bankHasProcessableMaterials;
    }

    static boolean shouldBankCarriedBatchAfterProcessingStarted(boolean processingStarted, int carriedMoneyItems) {
        return shouldBankCarriedBatchAfterProcessingStarted(processingStarted, carriedMoneyItems, false);
    }

    static boolean shouldBankCarriedBatchAfterProcessingStarted(boolean processingStarted, int carriedMoneyItems,
            boolean alreadyBankedAfterProcessingStarted) {
        return processingStarted && carriedMoneyItems > 0 && !alreadyBankedAfterProcessingStarted;
    }

    static boolean shouldBankSmeltedBarsBeforeStagedSmithing(int processedBars, boolean hasBankedSmeltableOres,
            boolean liquidatingForCombat) {
        return shouldBankSmeltedBarsBeforeStagedSmithing(processedBars, hasBankedSmeltableOres,
                liquidatingForCombat, false);
    }

    static boolean shouldBankSmeltedBarsBeforeStagedSmithing(int processedBars, boolean hasBankedSmeltableOres,
            boolean liquidatingForCombat, boolean processingStarted) {
        return shouldBankSmeltedBarsBeforeStagedSmithing(processedBars, hasBankedSmeltableOres,
                liquidatingForCombat, processingStarted, MIN_FREE_SLOTS_BEFORE_BANKING + 1);
    }

    static boolean shouldBankSmeltedBarsBeforeStagedSmithing(int processedBars, boolean hasBankedSmeltableOres,
            boolean liquidatingForCombat, boolean processingStarted, int freeSlots) {
        return processedBars > 0
                && hasBankedSmeltableOres
                && !liquidatingForCombat
                && freeSlots > MIN_FREE_SLOTS_BEFORE_BANKING;
    }

    static boolean shouldSmithCarriedBarsBeforeResidualSmelting(int productionAction, boolean canSmithBars,
            int processedBars, int rawMaterials, int freeSlots, boolean processingStarted) {
        return processingStarted
                && productionAction == GEAR_MONEY_PRODUCTION_SMELT
                && canSmithBars
                && processedBars > 0
                && rawMaterials <= 0
                && freeSlots <= MIN_FREE_SLOTS_BEFORE_BANKING;
    }

    static boolean shouldTopUpGearMoneySmithingBars(int carriedBars, int bankedSameBars, int freeSlots,
            boolean liquidatingForCombat) {
        return carriedBars > 0
                && bankedSameBars > 0
                && freeSlots > 0
                && !liquidatingForCombat;
    }

    static boolean shouldWithdrawBankedGearMoneyMaterialsForProcessing(int carriedMoneyItems,
            boolean hasBankedSmeltableOres, int bankedProcessableItems, boolean processingBatchReady, int freeSlots) {
        return shouldWithdrawBankedGearMoneyMaterialsForProcessing(carriedMoneyItems, hasBankedSmeltableOres,
                bankedProcessableItems, processingBatchReady, freeSlots, false);
    }

    static boolean shouldWithdrawBankedGearMoneyMaterialsForProcessing(int carriedMoneyItems,
            boolean hasBankedSmeltableOres, int bankedProcessableItems, boolean processingBatchReady, int freeSlots,
            boolean processingStarted) {
        if (carriedMoneyItems > 0 || freeSlots <= 0) {
            return false;
        }
        return hasProcessableGearMoneyMaterials(hasBankedSmeltableOres, bankedProcessableItems)
                && (processingBatchReady || processingStarted);
    }

    static boolean hasProcessableGearMoneyMaterials(boolean hasBankedSmeltableOres, int bankedProcessableItems) {
        return hasBankedSmeltableOres || bankedProcessableItems > 0;
    }

    static int gearMoneyProcessableWithdrawalItem(boolean hasBankedSmeltableOres, int smeltableOreItemId,
            int fallbackProcessableItemId) {
        if (isSteelOrBetterGearMoneyBar(fallbackProcessableItemId)) {
            return fallbackProcessableItemId;
        }
        if (hasBankedSmeltableOres && smeltableOreItemId > 0) {
            return smeltableOreItemId;
        }
        return fallbackProcessableItemId;
    }

    static boolean isSteelOrBetterGearMoneyBar(int itemId) {
        return itemId == STEEL_BAR
                || itemId == MITHRIL_BAR
                || itemId == ADAMANT_BAR
                || itemId == RUNE_BAR;
    }

    static boolean isGearMoneyBar(int itemId) {
        return itemId == BRONZE_BAR
                || itemId == IRON_BAR
                || itemId == STEEL_BAR
                || itemId == MITHRIL_BAR
                || itemId == ADAMANT_BAR
                || itemId == RUNE_BAR;
    }

    private static int countBankGearMoneyItems(Player player) {
        return countBankGearMoneyItems(player, null);
    }

    private static int countBankGearMoneyItems(Player player, CombatGoal goal) {
        int count = 0;
        for (SmithingData data : SmithingData.values()) {
            if (isGearMoneySaleItem(player, data.getId(), goal)) {
                count += AgentToolService.countBankItem(player, data.getId());
            }
        }
        if (shouldLiquidateStagedGearMoneyItems(goal)) {
            count += countBankStagedGearMoneyItems(player);
        }
        return count;
    }

    private static int countInventoryGearMoneyClutterItems(Player player) {
        return countInventoryGearMoneyClutterItems(player, null);
    }

    private static int countInventoryGearMoneyClutterItems(Player player, CombatGoal goal) {
        int count = excessGearMoneyFoodCount(AgentToolService.countInventoryFood(player));
        for (int i = 0; i < player.playerItems.length; i++) {
            int storedId = player.playerItems[i];
            if (storedId <= 0) {
                continue;
            }
            int itemId = storedId - 1;
            if (isGearMoneyClutterItemForBanking(player, itemId, goal)) {
                count += Math.max(1, player.playerItemsN[i]);
            }
        }
        return count;
    }

    private static int countBankProcessableGearMoneyItems(Player player) {
        int itemId = bestBankProcessableGearMoneyItem(player);
        return itemId <= 0 ? 0 : AgentToolService.countBankItem(player, itemId);
    }

    private static int countBankProcessedGearMoneyBars(Player player) {
        return AgentToolService.countBankItem(player, BRONZE_BAR)
                + AgentToolService.countBankItem(player, IRON_BAR)
                + AgentToolService.countBankItem(player, STEEL_BAR)
                + AgentToolService.countBankItem(player, MITHRIL_BAR)
                + AgentToolService.countBankItem(player, ADAMANT_BAR)
                + AgentToolService.countBankItem(player, RUNE_BAR);
    }

    private static int bestBankGearMoneyItem(Player player) {
        return bestBankGearMoneyItem(player, null);
    }

    private static int bestBankGearMoneyItem(Player player, CombatGoal goal) {
        int bestItemId = -1;
        int bestValue = -1;
        for (SmithingData data : SmithingData.values()) {
            int itemId = data.getId();
            if (isGearMoneySaleItem(player, itemId, goal) && AgentToolService.countBankItem(player, itemId) > 0) {
                int value = estimatedGearMoneySellCoins(itemId);
                if (value > bestValue) {
                    bestValue = value;
                    bestItemId = itemId;
                }
            }
        }
        if (shouldLiquidateStagedGearMoneyItems(goal)) {
            int itemId = bestBankStagedGearMoneyItem(player);
            int value = itemId <= 0 ? -1 : estimatedGearMoneySellCoins(itemId);
            if (value > bestValue) {
                bestItemId = itemId;
            }
        }
        return bestItemId;
    }

    static int countBankStagedGearMoneyItems(Player player) {
        int count = 0;
        for (int itemId : GEAR_MONEY_ITEM_IDS) {
            count += AgentToolService.countBankItem(player, itemId);
        }
        return count;
    }

    static int bestBankStagedGearMoneyItem(Player player) {
        int bestItemId = -1;
        int bestValue = -1;
        for (int itemId : GEAR_MONEY_ITEM_IDS) {
            if (AgentToolService.countBankItem(player, itemId) <= 0) {
                continue;
            }
            int value = estimatedGearMoneySellCoins(itemId);
            if (value > bestValue) {
                bestValue = value;
                bestItemId = itemId;
            }
        }
        return bestItemId;
    }

    private static int bestBankSmeltableGearMoneyOre(Player player) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        if (smithingLevel >= STEEL_SMELTING_SMITHING_LEVEL
                && AgentToolService.countBankItem(player, IRON_ORE) > 0
                && AgentToolService.countBankItem(player, COAL) >= STEEL_COAL_PER_BAR) {
            return IRON_ORE;
        }
        if (smithingLevel >= IRON_SMELTING_SMITHING_LEVEL
                && AgentToolService.countBankItem(player, IRON_ORE) > 0) {
            return IRON_ORE;
        }
        int copper = AgentToolService.countBankItem(player, COPPER_ORE);
        int tin = AgentToolService.countBankItem(player, TIN_ORE);
        if (copper > 0 && tin > 0) {
            return copper <= tin ? COPPER_ORE : TIN_ORE;
        }
        return -1;
    }

    private static int bestBankProcessableGearMoneyItem(Player player) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        int[] barIds = {RUNE_BAR, ADAMANT_BAR, MITHRIL_BAR, STEEL_BAR, IRON_BAR, BRONZE_BAR};
        for (int barId : barIds) {
            int bankedBars = AgentToolService.countBankItem(player, barId);
            if (shouldUseBankedGearMoneyBarsForProcessing(smithingLevel, barId, bankedBars)) {
                return barId;
            }
        }
        if (smithingLevel >= IRON_SMELTING_SMITHING_LEVEL && AgentToolService.countBankItem(player, IRON_ORE) > 0) {
            return IRON_ORE;
        }
        return -1;
    }

    static boolean shouldUseBankedGearMoneyBarsForProcessing(int smithingLevel, int barItemId, int bankedBars) {
        if (bankedBars <= 0) {
            return false;
        }
        SmithingChoice choice = bestGearMoneySmithingChoice(smithingLevel, barItemId, bankedBars);
        if (choice == null) {
            return false;
        }
        int preferredBars = Math.max(choice.getBarsNeeded(), bestPotentialGearMoneySmithingBars(smithingLevel, barItemId));
        return bankedBars >= preferredBars;
    }

    private static boolean hasBankedSmeltableGearMoneyOres(Player player) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        if (smithingLevel >= STEEL_SMELTING_SMITHING_LEVEL
                && AgentToolService.countBankItem(player, IRON_ORE) > 0
                && AgentToolService.countBankItem(player, COAL) >= STEEL_COAL_PER_BAR) {
            return true;
        }
        if (smithingLevel >= IRON_SMELTING_SMITHING_LEVEL
                && AgentToolService.countBankItem(player, IRON_ORE) > 0) {
            return true;
        }
        return AgentToolService.countBankItem(player, COPPER_ORE) > 0
                && AgentToolService.countBankItem(player, TIN_ORE) > 0;
    }

    static boolean hasBankedSmeltableGearMoneyOresForBar(Player player, int barItemId) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        if (barItemId == STEEL_BAR) {
            return smithingLevel >= STEEL_SMELTING_SMITHING_LEVEL
                    && AgentToolService.countBankItem(player, IRON_ORE) > 0
                    && AgentToolService.countBankItem(player, COAL) >= STEEL_COAL_PER_BAR;
        }
        if (barItemId == IRON_BAR) {
            return smithingLevel >= IRON_SMELTING_SMITHING_LEVEL
                    && AgentToolService.countBankItem(player, IRON_ORE) > 0;
        }
        if (barItemId == BRONZE_BAR) {
            return AgentToolService.countBankItem(player, COPPER_ORE) > 0
                    && AgentToolService.countBankItem(player, TIN_ORE) > 0;
        }
        return false;
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
        int preferredBars = Math.max(choice.getBarsNeeded(), bestPotentialGearMoneySmithingBars(player, barItemId));
        return shouldSmithGearMoneyBars(bars, choice.getBarsNeeded(), preferredBars, player.getItemAssistant().freeSlots(),
                liquidatingForCombat);
    }

    static boolean shouldSmithGearMoneyBars(int bars, int choiceBarsNeeded, int freeSlots,
            boolean liquidatingForCombat) {
        return shouldSmithGearMoneyBars(bars, choiceBarsNeeded, choiceBarsNeeded, freeSlots, liquidatingForCombat);
    }

    static boolean shouldSmithGearMoneyBars(int bars, int choiceBarsNeeded, int preferredBarsNeeded, int freeSlots,
            boolean liquidatingForCombat) {
        if (bars <= 0 || choiceBarsNeeded <= 0) {
            return false;
        }
        int batchBarsNeeded = Math.max(choiceBarsNeeded, preferredBarsNeeded);
        return liquidatingForCombat
                || freeSlots <= MIN_FREE_SLOTS_BEFORE_BANKING
                || bars >= MIN_BARS_BEFORE_SMITHING
                || bars >= batchBarsNeeded;
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

    static boolean shouldSellGearMoneyProductsBeforeProduction(int gearMoneyProducts, boolean canSmeltOres,
            boolean canSmithBars) {
        return shouldSellGearMoneyProductsBeforeProduction(gearMoneyProducts, canSmeltOres, canSmithBars,
                false, false);
    }

    static boolean shouldSellGearMoneyProductsBeforeProduction(int gearMoneyProducts, boolean canSmeltOres,
            boolean canSmithBars, boolean processingStarted, boolean bankHasProcessableMaterials) {
        return gearMoneyProducts > 0
                && gearMoneyProductionAction(canSmeltOres, canSmithBars) == GEAR_MONEY_PRODUCTION_NONE
                && !shouldFinishStagedMaterialsBeforeSelling(processingStarted, bankHasProcessableMaterials);
    }

    static boolean shouldFinishStagedMaterialsBeforeSelling(boolean processingStarted,
            boolean bankHasProcessableMaterials) {
        return processingStarted && bankHasProcessableMaterials;
    }

    private static SmithingChoice bestGearMoneySmithingChoice(Player player, int barItemId) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        return bestGearMoneySmithingChoice(smithingLevel, barItemId, AgentToolService.countInventoryItem(player, barItemId));
    }

    private static int bestPotentialGearMoneySmithingBars(Player player, int barItemId) {
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        return bestPotentialGearMoneySmithingBars(smithingLevel, barItemId);
    }

    private static int bestPotentialGearMoneySmithingBars(int smithingLevel, int barItemId) {
        SmithingChoice choice = bestGearMoneySmithingChoice(smithingLevel, barItemId, Integer.MAX_VALUE);
        return choice == null ? 0 : choice.getBarsNeeded();
    }

    private static SmithingChoice bestGearMoneySmithingChoice(int smithingLevel, int barItemId, int availableBars) {
        SmithingChoice best = null;
        for (SmithingChoice choice : AgentSmithingPlanner.smithableItems(smithingLevel, barItemId, availableBars, "")) {
            if (!isGearMoneySmithingCandidateItem(choice.getItemId())) {
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
        int candidateRequiredLevel = smithingProductRequiredLevel(candidateItemId);
        int currentRequiredLevel = smithingProductRequiredLevel(currentItemId);
        if (candidateRequiredLevel != currentRequiredLevel) {
            return candidateRequiredLevel > currentRequiredLevel;
        }

        int candidateBars = Math.max(1, smithingProductBars(candidateItemId));
        int currentBars = Math.max(1, smithingProductBars(currentItemId));
        if (candidateBars != currentBars) {
            return candidateBars > currentBars;
        }

        int candidateBatchCoins = estimatedGearMoneySmithingBatchSellCoins(candidateItemId, availableBars);
        int currentBatchCoins = estimatedGearMoneySmithingBatchSellCoins(currentItemId, availableBars);
        if (candidateBatchCoins != currentBatchCoins) {
            return candidateBatchCoins > currentBatchCoins;
        }

        int candidateSellCoins = estimatedGearMoneySellCoins(candidateItemId);
        int currentSellCoins = estimatedGearMoneySellCoins(currentItemId);
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
        return shouldSmeltGearMoneyOres(player, barItemId, liquidatingForCombat, false);
    }

    private static boolean shouldSmeltGearMoneyOres(Player player, int barItemId, boolean liquidatingForCombat,
            boolean processingStarted) {
        int possibleBars = smeltableGearMoneyBars(player, barItemId);
        return shouldSmeltGearMoneyOres(possibleBars, player.getItemAssistant().freeSlots(),
                isAlKharidSideForGearMoney(player.absX, player.absY), liquidatingForCombat, processingStarted);
    }

    static boolean shouldSmeltGearMoneyOres(int possibleBars, int freeSlots, boolean onFurnaceSide) {
        return shouldSmeltGearMoneyOres(possibleBars, freeSlots, onFurnaceSide, false);
    }

    static boolean shouldSmeltGearMoneyOres(int possibleBars, int freeSlots, boolean onFurnaceSide,
            boolean liquidatingForCombat) {
        return shouldSmeltGearMoneyOres(possibleBars, freeSlots, onFurnaceSide, liquidatingForCombat, false);
    }

    static boolean shouldSmeltGearMoneyOres(int possibleBars, int freeSlots, boolean onFurnaceSide,
            boolean liquidatingForCombat, boolean processingStarted) {
        if (possibleBars <= 0) {
            return false;
        }
        return liquidatingForCombat
                || processingStarted
                || onFurnaceSide
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
        int spendableCoins = AgentToolService.countInventoryItem(player, COINS)
                + AgentToolService.countBankItem(player, COINS);
        return nextPickaxeUpgrade(player, spendableCoins);
    }

    private static PickaxeTarget nextPickaxeUpgrade(Player player, int availableCoins) {
        int miningLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.MINING]);
        int currentBestTier = bestOwnedPickaxeTier(player);
        int itemId = recommendedPickaxeUpgradeId(miningLevel, currentBestTier, availableCoins);
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

    static int recommendedPickaxeMoneyUpgradeId(int miningLevel, int currentBestTier, int spendableCoins) {
        if (currentBestTier <= 0) {
            PickaxeTarget starter = pickaxeTargetByItemId(BRONZE_PICKAXE);
            return starter != null && starter.requiredMiningLevel <= miningLevel
                    && starter.estimatedPrice > spendableCoins ? starter.itemId : -1;
        }
        PickaxeTarget next = null;
        for (PickaxeTarget target : PICKAXE_TARGETS) {
            if (target.tier <= currentBestTier || target.requiredMiningLevel > miningLevel
                    || target.estimatedPrice <= spendableCoins) {
                continue;
            }
            if (next == null || target.tier < next.tier) {
                next = target;
            }
        }
        return next == null ? -1 : next.itemId;
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
        return gearMoneyOreForMiningLevel(miningLevel, smithingLevel, copperCount, tinCount, ironCount, coalCount, 0,
                Integer.MIN_VALUE, Integer.MIN_VALUE);
    }

    static String gearMoneyOreForMiningLevel(int miningLevel, int smithingLevel, int copperCount, int tinCount,
            int ironCount, int coalCount, int freeSlots, int x, int y) {
        return gearMoneyOreForMiningLevel(miningLevel, smithingLevel, copperCount, tinCount, ironCount, coalCount,
                freeSlots, x, y, 0, 0, 0, 0, 0, 0);
    }

    static String gearMoneyOreForMiningLevel(int miningLevel, int smithingLevel, int copperCount, int tinCount,
            int ironCount, int coalCount, int freeSlots, int x, int y, int spendableCoins, int targetCost,
            int productCoins, int bronzeBars, int ironBars, int steelBars) {
        String targetBatchOre = gearMoneyOreForTargetBatch(miningLevel, smithingLevel, copperCount, tinCount,
                ironCount, coalCount, freeSlots, x, y, spendableCoins, targetCost, productCoins,
                bronzeBars, ironBars, steelBars);
        if (!targetBatchOre.isEmpty()) {
            return targetBatchOre;
        }
        if (miningLevel >= 30
                && smithingLevel >= STEEL_SMELTING_SMITHING_LEVEL
                && canSmithGearMoneyProductFromBar(smithingLevel, STEEL_BAR)) {
            return gearMoneySteelOreForCounts(ironCount, coalCount, freeSlots, x, y);
        }
        if (miningLevel >= 15
                && smithingLevel >= IRON_SMELTING_SMITHING_LEVEL
                && canSmithGearMoneyProductFromBar(smithingLevel, IRON_BAR)) {
            return "iron";
        }
        return copperCount <= tinCount ? "copper" : "tin";
    }

    private static String gearMoneyOreForTargetBatch(int miningLevel, int smithingLevel, int copperCount, int tinCount,
            int ironCount, int coalCount, int freeSlots, int x, int y, int spendableCoins, int targetCost,
            int productCoins, int bronzeBars, int ironBars, int steelBars) {
        int preferredBar = preferredGearMoneyBatchBar(miningLevel, smithingLevel);
        if (preferredBar <= 0) {
            return "";
        }
        int targetBars = requiredGearMoneyBatchBars(smithingLevel, preferredBar,
                targetCost - Math.max(0, spendableCoins) - Math.max(0, productCoins));
        if (targetBars <= 0) {
            return "";
        }
        if (stagedGearMoneyBatchBars(preferredBar, copperCount, tinCount, ironCount, coalCount,
                bronzeBars, ironBars, steelBars) >= targetBars) {
            return "";
        }

        if (preferredBar == STEEL_BAR) {
            int targetOreBars = Math.max(0, targetBars - Math.max(0, steelBars));
            return nextBatchMaterialSource(targetOreBars, x, y,
                    batchMaterialNeed("iron", ironCount, 1),
                    batchMaterialNeed("coal", coalCount, STEEL_COAL_PER_BAR));
        }
        if (preferredBar == IRON_BAR) {
            int targetOreBars = Math.max(0, targetBars - Math.max(0, ironBars));
            return nextBatchMaterialSource(targetOreBars, x, y,
                    batchMaterialNeed("iron", ironCount, 1));
        }
        int targetOreBars = Math.max(0, targetBars - Math.max(0, bronzeBars));
        return nextBatchMaterialSource(targetOreBars, x, y,
                batchMaterialNeed("copper", copperCount, 1),
                batchMaterialNeed("tin", tinCount, 1));
    }

    static boolean isPreferredGearMoneyBatchStaged(Player player, int spendableCoins, int targetCost,
            int productCoins) {
        int miningLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.MINING]);
        int smithingLevel = player.getPlayerAssistant().getLevelForXP(player.playerXP[Constants.SMITHING]);
        return isPreferredGearMoneyBatchStaged(miningLevel, smithingLevel,
                AgentToolService.countInventoryItem(player, COPPER_ORE) + AgentToolService.countBankItem(player, COPPER_ORE),
                AgentToolService.countInventoryItem(player, TIN_ORE) + AgentToolService.countBankItem(player, TIN_ORE),
                AgentToolService.countInventoryItem(player, IRON_ORE) + AgentToolService.countBankItem(player, IRON_ORE),
                AgentToolService.countInventoryItem(player, COAL) + AgentToolService.countBankItem(player, COAL),
                AgentToolService.countInventoryItem(player, BRONZE_BAR) + AgentToolService.countBankItem(player, BRONZE_BAR),
                AgentToolService.countInventoryItem(player, IRON_BAR) + AgentToolService.countBankItem(player, IRON_BAR),
                AgentToolService.countInventoryItem(player, STEEL_BAR) + AgentToolService.countBankItem(player, STEEL_BAR),
                spendableCoins, targetCost, productCoins);
    }

    static boolean isPreferredGearMoneyBatchStaged(int miningLevel, int smithingLevel, int copperCount, int tinCount,
            int ironCount, int coalCount, int bronzeBars, int ironBars, int steelBars, int spendableCoins,
            int targetCost, int productCoins) {
        int preferredBar = preferredGearMoneyBatchBar(miningLevel, smithingLevel);
        if (preferredBar <= 0) {
            return true;
        }
        int targetBars = requiredGearMoneyBatchBars(smithingLevel, preferredBar,
                targetCost - Math.max(0, spendableCoins) - Math.max(0, productCoins));
        return targetBars <= 0 || stagedGearMoneyBatchBars(preferredBar, copperCount, tinCount, ironCount, coalCount,
                bronzeBars, ironBars, steelBars) >= targetBars;
    }

    static int requiredGearMoneyBatchBars(int smithingLevel, int barItemId, int remainingCoins) {
        if (remainingCoins <= 0) {
            return 0;
        }
        int high = 1;
        while (high < MAX_GEAR_MONEY_TARGET_BATCH_BARS
                && estimatedGearMoneySmithingPotentialSellCoins(smithingLevel, barItemId, high) < remainingCoins) {
            high *= 2;
        }
        high = Math.min(high, MAX_GEAR_MONEY_TARGET_BATCH_BARS);
        int low = 1;
        while (low < high) {
            int mid = low + ((high - low) / 2);
            if (estimatedGearMoneySmithingPotentialSellCoins(smithingLevel, barItemId, mid) >= remainingCoins) {
                high = mid;
            } else {
                low = mid + 1;
            }
        }
        return low;
    }

    static int preferredGearMoneyBatchBar(int miningLevel, int smithingLevel) {
        if (miningLevel >= 30
                && smithingLevel >= STEEL_SMELTING_SMITHING_LEVEL
                && canSmithGearMoneyProductFromBar(smithingLevel, STEEL_BAR)) {
            return STEEL_BAR;
        }
        if (miningLevel >= 15
                && smithingLevel >= IRON_SMELTING_SMITHING_LEVEL
                && canSmithGearMoneyProductFromBar(smithingLevel, IRON_BAR)) {
            return IRON_BAR;
        }
        return BRONZE_BAR;
    }

    static int stagedGearMoneyBatchBars(int barItemId, int copperCount, int tinCount, int ironCount, int coalCount,
            int bronzeBars, int ironBars, int steelBars) {
        if (barItemId == STEEL_BAR) {
            return stagedBatchOutputCount(steelBars,
                    batchMaterialNeed("iron", ironCount, 1),
                    batchMaterialNeed("coal", coalCount, STEEL_COAL_PER_BAR));
        }
        if (barItemId == IRON_BAR) {
            return stagedBatchOutputCount(ironBars, batchMaterialNeed("iron", ironCount, 1));
        }
        if (barItemId == BRONZE_BAR) {
            return stagedBatchOutputCount(bronzeBars,
                    batchMaterialNeed("copper", copperCount, 1),
                    batchMaterialNeed("tin", tinCount, 1));
        }
        return 0;
    }

    static BatchMaterialNeed batchMaterialNeed(String sourceName, int availableCount, int unitsPerOutput) {
        return new BatchMaterialNeed(sourceName, availableCount, unitsPerOutput);
    }

    static int stagedBatchOutputCount(int finishedOutputs, BatchMaterialNeed... needs) {
        int stagedOutputs = Integer.MAX_VALUE;
        if (needs == null || needs.length == 0) {
            stagedOutputs = 0;
        } else {
            for (BatchMaterialNeed need : needs) {
                if (need == null) {
                    continue;
                }
                stagedOutputs = Math.min(stagedOutputs, need.stagedOutputs());
            }
            if (stagedOutputs == Integer.MAX_VALUE) {
                stagedOutputs = 0;
            }
        }
        return Math.max(0, finishedOutputs) + Math.max(0, stagedOutputs);
    }

    static String nextBatchMaterialSource(int targetOutputs, int x, int y, BatchMaterialNeed... needs) {
        if (targetOutputs <= 0 || needs == null || needs.length == 0) {
            return "";
        }
        BatchMaterialNeed currentSourceNeed = null;
        BatchMaterialNeed largestNeed = null;
        for (BatchMaterialNeed need : needs) {
            if (need == null || need.deficitUnits(targetOutputs) <= 0) {
                continue;
            }
            if (isGearMoneyMine(need.sourceName(), x, y)) {
                currentSourceNeed = need;
            }
            if (largestNeed == null
                    || need.deficitUnits(targetOutputs) > largestNeed.deficitUnits(targetOutputs)) {
                largestNeed = need;
            }
        }
        if (currentSourceNeed != null) {
            return currentSourceNeed.sourceName();
        }
        return largestNeed == null ? "" : largestNeed.sourceName();
    }

    private static boolean canSmithGearMoneyProductFromBar(int smithingLevel, int barItemId) {
        for (SmithingData data : SmithingData.values()) {
            if (data.getLvl() <= smithingLevel
                    && AgentSmithingPlanner.requiredBarForItem(data.getId()) == barItemId
                    && isGearMoneySmithingCandidateItem(data.getId())) {
                return true;
            }
        }
        return false;
    }

    static String gearMoneySteelOreForCounts(int ironCount, int coalCount) {
        if (ironCount <= 0) {
            return "iron";
        }
        return coalCount < ironCount * STEEL_COAL_PER_BAR ? "coal" : "iron";
    }

    static String gearMoneySteelOreForCounts(int ironCount, int coalCount, int freeSlots, int x, int y) {
        if (freeSlots <= 0) {
            return gearMoneySteelOreForCounts(ironCount, coalCount);
        }
        int totalOreCapacity = Math.max(0, ironCount) + Math.max(0, coalCount) + Math.max(0, freeSlots);
        int targetBars = Math.max(1, totalOreCapacity / (STEEL_COAL_PER_BAR + 1));
        int targetIron = targetBars;
        int targetCoal = targetBars * STEEL_COAL_PER_BAR;
        if (isGearMoneyCoalMine(x, y) && coalCount < targetCoal) {
            return "coal";
        }
        if (isGearMoneyIronMine(x, y) && ironCount < targetIron) {
            return "iron";
        }
        if (ironCount < targetIron) {
            return "iron";
        }
        if (coalCount < targetCoal) {
            return "coal";
        }
        return gearMoneySteelOreForCounts(ironCount, coalCount);
    }

    static String gearMoneyMineLandmark(String ore) {
        return "coal".equals(ore) ? "varrock east coal mine" : "varrock east mine";
    }

    static boolean isGearMoneyCoalMine(int x, int y) {
        return x >= VARROCK_COAL_DANGER_MIN_X && x <= VARROCK_COAL_DANGER_MAX_X + 3
                && y >= VARROCK_COAL_DANGER_MIN_Y && y <= VARROCK_COAL_DANGER_MAX_Y;
    }

    static boolean isGearMoneyIronMine(int x, int y) {
        return x >= 3270 && x <= 3298 && y >= 3350 && y <= 3378;
    }

    static boolean isAnyGearMoneyMine(int x, int y) {
        return isGearMoneyCoalMine(x, y) || isGearMoneyIronMine(x, y);
    }

    static boolean isGearMoneyMine(String ore, int x, int y) {
        return "coal".equals(ore) ? isGearMoneyCoalMine(x, y) : isGearMoneyIronMine(x, y);
    }

    static boolean shouldBankGearMoneyClutterBeforeProcessing(int clutterCount, int x, int y) {
        return clutterCount > 0 && isVarrockGearMoneyBankingCorridor(x, y);
    }

    static boolean isVarrockGearMoneyBankingCorridor(int x, int y) {
        return x >= 3180 && x <= 3305 && y >= 3350 && y <= 3435;
    }

    static String gearMoneyClutterBankLandmark(int x, int y) {
        if (isAlKharidBankingSideForGearMoney(x, y)) {
            return "al kharid bank";
        }
        return x < 3230 ? "varrock west bank" : "varrock east bank";
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
            int stationaryMovingWaitSteps) {
        return currentX == lastMovingX && currentY == lastMovingY
                && stationaryMovingWaitSteps >= MAX_STATIONARY_MOVING_WAIT_STEPS;
    }

    static boolean isExceededMovementWait(int movingWaitSteps) {
        return movingWaitSteps >= MAX_MOVING_WAIT_STEPS;
    }

    static boolean isRouteOscillation(int currentX, int currentY, int previousX, int previousY,
            int beforePreviousX, int beforePreviousY) {
        return currentX == beforePreviousX && currentY == beforePreviousY
                && (currentX != previousX || currentY != previousY);
    }

    static boolean shouldBlockRouteOscillation(int reversalCount) {
        return reversalCount >= MAX_ROUTE_OSCILLATION_REVERSALS;
    }

    static boolean isRouteStale(int currentX, int currentY, int previousX, int previousY, int staleSteps) {
        return currentX == previousX && currentY == previousY && staleSteps >= MAX_ROUTE_STALE_STEPS;
    }

    static boolean shouldBlockRouteStale(int staleSteps) {
        return staleSteps >= MAX_ROUTE_STALE_STEPS;
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
        if (isAlKharidBankingSideForGearMoney(x, y)) {
            return "al kharid bank";
        }
        if (x >= 3230 && x <= 3310 && y >= 3300 && y <= 3435) {
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
            if (shouldWaitForActiveCombatThreatClearance(attackerIndex, player.npcIndex, player.killingNpcIndex,
                    player.underAttackBy, player.underAttackBy2, isLiveNpc(attackerIndex))) {
                JsonObject result = AgentToolService.success(prefix
                        + ": already clearing attacker before non-combat work; waiting for combat to resolve.");
                result.add("state", AgentToolService.observeState(player));
                return result;
            }
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

    static boolean shouldWaitForActiveCombatThreatClearance(int attackerIndex, int npcIndex, int killingNpcIndex,
            int underAttackBy, int underAttackBy2, boolean liveNpc) {
        return liveNpc
                && attackerIndex > 0
                && (npcIndex == attackerIndex || killingNpcIndex == attackerIndex)
                && (killingNpcIndex == attackerIndex || underAttackBy == attackerIndex
                        || underAttackBy2 == attackerIndex);
    }

    private static boolean isLiveNpc(int npcIndex) {
        if (npcIndex <= 0 || npcIndex >= NpcHandler.npcs.length) {
            return false;
        }
        Npc npc = NpcHandler.npcs[npcIndex];
        return npc != null && !npc.isDead && npc.HP > 0;
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
                || lower.contains("reacquiring combat target")
                || (lower.contains("no suitable") && lower.contains("moving toward"));
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

    private static JsonObject resultPlayer(JsonObject result) {
        JsonObject player = jsonObject(result, "player");
        if (player != null) {
            return player;
        }
        JsonObject state = jsonObject(result, "state");
        return jsonObject(state, "player");
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

    private static JsonObject finishMovementBatch(MovementBatchTrace trace, AgentSession session,
            JsonObject arguments, JsonObject result, String status, int ticks) {
        JsonObject output = addBatchStatus(result, status, ticks);
        if (trace != null) {
            trace.record(session, ticks, -1L, output, status);
        }
        return output;
    }

    private static void recordObjectTransition(AgentSession session, String tool, JsonObject arguments, JsonObject result) {
        if (!"interact_object".equals(tool) || session == null || result == null || !isSuccess(result)) {
            return;
        }
        JsonObject player = resultPlayer(result);
        JsonObject object = jsonObject(result, "object");
        if (player == null || object == null) {
            return;
        }
        int x = getInt(player, "x", Integer.MIN_VALUE);
        int y = getInt(player, "y", Integer.MIN_VALUE);
        int height = getInt(player, "height", Integer.MIN_VALUE);
        if (x == Integer.MIN_VALUE || y == Integer.MIN_VALUE || height == Integer.MIN_VALUE) {
            return;
        }
        JsonObject event = new JsonObject();
        event.addProperty("traceId", UUID.randomUUID().toString());
        event.addProperty("event", "object_interaction");
        event.addProperty("tool", tool);
        event.add("arguments", arguments == null ? new JsonObject() : arguments);
        event.add("tile", tile(x, y, height));
        event.add("object", object);
        if (result.has("objectReachable")) {
            event.addProperty("objectReachable", getBoolean(result, "objectReachable", false));
        } else if (object.has("reachable")) {
            event.addProperty("objectReachable", getBoolean(object, "reachable", false));
        }
        if (result.has("objectWalkTarget")) {
            event.add("objectWalkTarget", result.get("objectWalkTarget"));
        }
        event.addProperty("success", true);
        event.addProperty("message", getString(result, "message", ""));
        event.addProperty("runEnabled", getBoolean(player, "runEnabled", false));
        event.addProperty("runEnergy", getInt(player, "runEnergy", -1));
        event.addProperty("hitpoints", getInt(player, "hitpoints", -1));
        event.addProperty("isInCombat", getBoolean(player, "isInCombat", false));
        AgentMovementTraceLog.INSTANCE.record(session, event);
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

    private static final class MovementBatchTrace {
        private final String traceId = UUID.randomUUID().toString();
        private final String tool;
        private final JsonObject arguments;
        private final long submittedTick;
        private int previousX = Integer.MIN_VALUE;
        private int previousY = Integer.MIN_VALUE;
        private int previousHeight = Integer.MIN_VALUE;
        private int previousRunEnergy = Integer.MIN_VALUE;
        private int previousHitpoints = Integer.MIN_VALUE;
        private int beforePreviousX = Integer.MIN_VALUE;
        private int beforePreviousY = Integer.MIN_VALUE;
        private int staleTicks;
        private int oscillationReversals;

        MovementBatchTrace(String tool, JsonObject arguments, long submittedTick) {
            this.tool = tool;
            this.arguments = arguments == null ? new JsonObject() : arguments;
            this.submittedTick = submittedTick;
        }

        void record(AgentSession session, int tickIndex, long currentServerTick, JsonObject result, String event) {
            JsonObject player = resultPlayer(result);
            if (player == null) {
                return;
            }
            int x = getInt(player, "x", Integer.MIN_VALUE);
            int y = getInt(player, "y", Integer.MIN_VALUE);
            int height = getInt(player, "height", Integer.MIN_VALUE);
            if (x == Integer.MIN_VALUE || y == Integer.MIN_VALUE || height == Integer.MIN_VALUE) {
                return;
            }
            int runEnergy = getInt(player, "runEnergy", -1);
            int hitpoints = getInt(player, "hitpoints", -1);
            updateMovementState(x, y, height);

            JsonObject trace = new JsonObject();
            trace.addProperty("traceId", traceId);
            trace.addProperty("event", event);
            trace.addProperty("tool", tool);
            trace.addProperty("tickIndex", tickIndex);
            trace.addProperty("submittedServerTick", submittedTick);
            if (currentServerTick >= 0L) {
                trace.addProperty("serverTick", currentServerTick);
            }
            trace.add("arguments", arguments);
            if (result != null) {
                trace.addProperty("success", getBoolean(result, "success", false));
                trace.addProperty("complete", getBoolean(result, "complete", false));
                trace.addProperty("message", getString(result, "message", ""));
                trace.addProperty("batchStatus", getString(result, "batchStatus", ""));
                copyObject(result, trace, "target");
                copyObject(result, trace, "walkTarget");
                copyObject(result, trace, "nextWaypoint");
                if (result.has("landmark") && result.get("landmark").isJsonPrimitive()) {
                    trace.addProperty("landmark", result.get("landmark").getAsString());
                }
            }
            if (previousX != Integer.MIN_VALUE) {
                JsonObject previous = tile(previousX, previousY, previousHeight);
                trace.add("previousTile", previous);
                trace.addProperty("edgeKey", tileKey(previousX, previousY, previousHeight)
                        + "->" + tileKey(x, y, height));
            }
            trace.add("tile", tile(x, y, height));
            trace.addProperty("moved", previousX != Integer.MIN_VALUE
                    && (previousX != x || previousY != y || previousHeight != height));
            trace.addProperty("staleTicks", staleTicks);
            trace.addProperty("oscillationReversals", oscillationReversals);
            trace.addProperty("runEnabled", getBoolean(player, "runEnabled", false));
            trace.addProperty("runEnergy", runEnergy);
            trace.addProperty("hitpoints", hitpoints);
            trace.addProperty("maxHitpoints", getInt(player, "maxHitpoints", -1));
            trace.addProperty("isMoving", getBoolean(player, "isMoving", false));
            trace.addProperty("isDead", getBoolean(player, "isDead", false));
            trace.addProperty("isInCombat", getBoolean(player, "isInCombat", false));
            trace.addProperty("npcIndex", getInt(player, "npcIndex", 0));
            trace.addProperty("killingNpcIndex", getInt(player, "killingNpcIndex", 0));
            trace.addProperty("underAttackBy", getInt(player, "underAttackBy", 0));
            trace.addProperty("underAttackBy2", getInt(player, "underAttackBy2", 0));
            if (previousRunEnergy >= 0 && runEnergy >= 0) {
                trace.addProperty("runEnergyDelta", runEnergy - previousRunEnergy);
                trace.addProperty("runEnergySpent", Math.max(0, previousRunEnergy - runEnergy));
            }
            if (previousHitpoints >= 0 && hitpoints >= 0) {
                trace.addProperty("hitpointsDelta", hitpoints - previousHitpoints);
                trace.addProperty("hitpointsLost", Math.max(0, previousHitpoints - hitpoints));
            }
            AgentMovementTraceLog.INSTANCE.record(session, trace);

            beforePreviousX = previousX;
            beforePreviousY = previousY;
            previousX = x;
            previousY = y;
            previousHeight = height;
            previousRunEnergy = runEnergy;
            previousHitpoints = hitpoints;
        }

        boolean isStalled() {
            return staleTicks >= MAX_MOVEMENT_BATCH_STALE_TICKS;
        }

        boolean isOscillating() {
            return oscillationReversals >= MAX_MOVEMENT_BATCH_OSCILLATION_REVERSALS;
        }

        String currentTileText() {
            if (previousX == Integer.MIN_VALUE) {
                return "unknown";
            }
            return previousX + "," + previousY + "," + previousHeight;
        }

        private void updateMovementState(int x, int y, int height) {
            if (previousX == Integer.MIN_VALUE) {
                staleTicks = 0;
                oscillationReversals = 0;
                return;
            }
            boolean sameTile = previousX == x && previousY == y && previousHeight == height;
            if (sameTile) {
                staleTicks++;
            } else {
                staleTicks = 0;
            }
            boolean reversed = beforePreviousX != Integer.MIN_VALUE
                    && beforePreviousX == x && beforePreviousY == y
                    && previousHeight == height;
            if (reversed) {
                oscillationReversals++;
            } else if (!sameTile) {
                oscillationReversals = 0;
            }
        }
    }

    private static JsonObject tile(int x, int y, int height) {
        JsonObject tile = new JsonObject();
        tile.addProperty("x", x);
        tile.addProperty("y", y);
        tile.addProperty("height", height);
        return tile;
    }

    private static String tileKey(int x, int y, int height) {
        return x + "," + y + "," + height;
    }

    private static void copyObject(JsonObject source, JsonObject destination, String name) {
        JsonObject child = jsonObject(source, name);
        if (child != null) {
            destination.add(name, child);
        }
    }

    static final class TargetAcquisitionPlan {
        private final int itemId;
        private final String targetName;
        private final int targetCount;
        private final int currentCount;
        private final int freeSlots;
        private final int carriedSaleItems;
        private final int inventoryCoins;
        private final int bankCoins;
        private final int entryCost;
        private final int reserveCoins;
        private final int unitCost;
        private final int minimumFloat;
        private final boolean canMakeMoney;

        private TargetAcquisitionPlan(int itemId, String targetName, int targetCount, int currentCount,
                int freeSlots, int carriedSaleItems, int inventoryCoins, int bankCoins, int entryCost,
                int reserveCoins, int unitCost, int minimumFloat, boolean canMakeMoney) {
            this.itemId = itemId;
            this.targetName = targetName == null ? "" : targetName;
            this.targetCount = Math.max(0, targetCount);
            this.currentCount = Math.max(0, currentCount);
            this.freeSlots = Math.max(0, freeSlots);
            this.carriedSaleItems = Math.max(0, carriedSaleItems);
            this.inventoryCoins = Math.max(0, inventoryCoins);
            this.bankCoins = Math.max(0, bankCoins);
            this.entryCost = Math.max(0, entryCost);
            this.reserveCoins = Math.max(0, reserveCoins);
            this.unitCost = Math.max(1, unitCost);
            this.minimumFloat = Math.max(0, minimumFloat);
            this.canMakeMoney = canMakeMoney;
        }

        int itemId() {
            return itemId;
        }

        String targetName() {
            return targetName;
        }

        int effectiveFreeSlots() {
            return targetAcquisitionEffectiveFreeSlots(freeSlots, carriedSaleItems);
        }

        int desiredBatchAmount() {
            return targetAcquisitionBatchAmount(targetCount, currentCount, effectiveFreeSlots());
        }

        int immediateBatchAmount() {
            return targetAcquisitionBatchAmount(targetCount, currentCount, freeSlots);
        }

        int affordableBatchAmount() {
            return targetAcquisitionBatchAmount(targetCount, currentCount, freeSlots, unitCost, reserveCoins,
                    inventoryCoins);
        }

        int requiredCoins() {
            return targetAcquisitionRequiredCoins(targetCount, currentCount, effectiveFreeSlots(), entryCost,
                    reserveCoins, unitCost, minimumFloat);
        }

        int coinFloat() {
            return targetAcquisitionCoinFloat(targetCount, currentCount, freeSlots, inventoryCoins, bankCoins,
                    entryCost, reserveCoins, unitCost, minimumFloat);
        }

        boolean shouldEarnMoneyBeforeTrip() {
            return shouldEarnMoneyForTargetAcquisition(currentCount, targetCount, inventoryCoins,
                    bankCoins, requiredCoins(), canMakeMoney);
        }

        boolean shouldDelayTripForFundedBatch() {
            return shouldDelayTargetAcquisitionTripForFundedBatch(currentCount, targetCount, inventoryCoins,
                    bankCoins, requiredCoins(), canMakeMoney);
        }

        boolean hasEnoughCoinsForTrip() {
            return inventoryCoins + bankCoins >= requiredCoins();
        }

        boolean shouldSellCarriedItemsBeforeShopTrip() {
            return carriedSaleItems > 0
                    && desiredBatchAmount() > immediateBatchAmount()
                    && inventoryCoins + bankCoins >= requiredCoins();
        }
    }

    static final class BatchMaterialNeed {
        private final String sourceName;
        private final int availableCount;
        private final int unitsPerOutput;

        private BatchMaterialNeed(String sourceName, int availableCount, int unitsPerOutput) {
            this.sourceName = sourceName == null ? "" : sourceName;
            this.availableCount = Math.max(0, availableCount);
            this.unitsPerOutput = Math.max(1, unitsPerOutput);
        }

        String sourceName() {
            return sourceName;
        }

        int stagedOutputs() {
            return availableCount / unitsPerOutput;
        }

        int deficitUnits(int targetOutputs) {
            return Math.max(0, Math.max(0, targetOutputs) * unitsPerOutput - availableCount);
        }
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
        private int stationaryMovingWaitSteps;
        private int lastMovingX = Integer.MIN_VALUE;
        private int lastMovingY = Integer.MIN_VALUE;
        private int movingStallRecoveries;
        private String routeWatchLandmark = "";
        private int routeWatchTargetX = Integer.MIN_VALUE;
        private int routeWatchTargetY = Integer.MIN_VALUE;
        private int routeWatchPreviousX = Integer.MIN_VALUE;
        private int routeWatchPreviousY = Integer.MIN_VALUE;
        private int routeWatchBeforePreviousX = Integer.MIN_VALUE;
        private int routeWatchBeforePreviousY = Integer.MIN_VALUE;
        private int routeOscillationReversals;
        private int routeOscillationRecoveries;
        private String routeOscillationLandmark = "";
        private int routeWatchStaleSteps;
        private int routeStaleRecoveries;
        private String routeStaleLandmark = "";
        private int miningClickWaitUntilTick;
        private int miningClickWaits;
        private int localMiningRespawnWaits;
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
        private int lastLoggedRouteOscillationRecoveries;
        private int lastLoggedRouteStaleRecoveries;
        private int lastLoggedMiningClickWaits;
        private int lastLoggedPickaxeRouteDeferrals;
        private int lastGearAttemptAction = -GEAR_CHECK_INTERVAL_ACTIONS;
        private int gearCombatCancelAttempts;
        private int gearTargetItemId;
        private String gearTargetName = "";
        private int gearMoneyTargetItemId;
        private int gearMoneyPickaxeTargetItemId;
        private String gearMoneyTargetName = "";
        private int gearMoneyCraftedProductItemId;
        private boolean gearMoneyProcessingStarted;
        private boolean gearMoneyRawMaterialsBankedAfterProcessingStarted;
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
            gearMoneyPickaxeTargetItemId = 0;
            gearMoneyTargetName = target.itemName();
            gearMoneyTargetCoins = estimatedGearAcquisitionCost(target);
            gearTargetItemId = target.itemId;
            gearTargetName = target.itemName();
        }

        private void beginTargetMoney(int itemId, String targetName, int targetCoins) {
            earningGearMoney = true;
            gearingUp = false;
            gearMoneyTargetItemId = itemId;
            gearMoneyPickaxeTargetItemId = 0;
            gearMoneyTargetName = targetName == null ? "" : targetName;
            gearMoneyTargetCoins = Math.max(1, targetCoins);
            gearTargetItemId = 0;
            gearTargetName = "";
        }

        private void beginPickaxeMoney(PickaxeTarget target) {
            earningGearMoney = true;
            gearingUp = false;
            gearMoneyTargetItemId = 0;
            gearMoneyPickaxeTargetItemId = target.itemId;
            gearMoneyTargetName = target.itemName();
            gearMoneyTargetCoins = target.estimatedPrice;
            gearTargetItemId = 0;
            gearTargetName = "";
        }

        private void clearGearMoney() {
            earningGearMoney = false;
            gearMoneyTargetItemId = 0;
            gearMoneyPickaxeTargetItemId = 0;
            gearMoneyTargetName = "";
            gearMoneyTargetCoins = 0;
            gearMoneyCraftedProductItemId = 0;
            gearMoneyProcessingStarted = false;
            gearMoneyRawMaterialsBankedAfterProcessingStarted = false;
        }

        private void rememberGearMoneyProcessingStarted() {
            gearMoneyProcessingStarted = true;
        }

        private void rememberGearMoneyRawMaterialsBankedAfterProcessingStarted() {
            if (gearMoneyProcessingStarted) {
                gearMoneyRawMaterialsBankedAfterProcessingStarted = true;
            }
        }

        private void rememberGearMoneyCraftedProduct(int itemId) {
            if (isGearMoneySmithingCandidateItem(itemId)) {
                gearMoneyCraftedProductItemId = itemId;
            }
        }

        private void clearGearMoneyCraftedProductIfGone(Player player) {
            if (gearMoneyCraftedProductItemId > 0
                    && AgentToolService.countInventoryItem(player, gearMoneyCraftedProductItemId) <= 0) {
                gearMoneyCraftedProductItemId = 0;
            }
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
                stationaryMovingWaitSteps = 0;
                return true;
            }
            stationaryMovingWaitSteps++;
            return !isStaleMovementWait(player.absX, player.absY, lastMovingX, lastMovingY,
                    stationaryMovingWaitSteps);
        }

        private void recoverFromMovementStall(Player player) {
            movingWaitSteps = 0;
            stationaryMovingWaitSteps = 0;
            lastMovingX = player.absX;
            lastMovingY = player.absY;
            movingStallRecoveries++;
        }

        private boolean shouldWaitForMiningClick() {
            return ticksElapsed < miningClickWaitUntilTick;
        }

        private void rememberMiningClickWait(JsonObject result) {
            int cooldownTicks = getInt(result, "cooldownTicks", 0);
            if (cooldownTicks <= 0) {
                return;
            }
            miningClickWaits++;
            miningClickWaitUntilTick = Math.max(miningClickWaitUntilTick, ticksElapsed + cooldownTicks);
        }

        private boolean shouldWaitForLocalMiningRespawn() {
            return localMiningRespawnWaits < MAX_LOCAL_MINING_RESPAWN_WAITS;
        }

        private void rememberLocalMiningRespawnWait(JsonObject result) {
            if (getBoolean(result, "waitingForLocalRespawn", false)) {
                localMiningRespawnWaits++;
                return;
            }
            localMiningRespawnWaits = 0;
        }

        private boolean recordRouteProgressAndShouldBlock(JsonObject result) {
            String landmark = getString(result, "landmark", "");
            if (landmark.isEmpty() || getBoolean(result, "complete", false)) {
                clearRouteWatch();
                return false;
            }
            JsonObject player = resultPlayer(result);
            JsonObject target = jsonObject(result, "target");
            if (player == null || target == null) {
                return false;
            }
            int x = getInt(player, "x", Integer.MIN_VALUE);
            int y = getInt(player, "y", Integer.MIN_VALUE);
            int targetX = getInt(target, "x", Integer.MIN_VALUE);
            int targetY = getInt(target, "y", Integer.MIN_VALUE);
            if (x == Integer.MIN_VALUE || y == Integer.MIN_VALUE
                    || targetX == Integer.MIN_VALUE || targetY == Integer.MIN_VALUE) {
                clearRouteWatch();
                return false;
            }
            if (!landmark.equals(routeWatchLandmark) || targetX != routeWatchTargetX || targetY != routeWatchTargetY) {
                routeWatchLandmark = landmark;
                routeWatchTargetX = targetX;
                routeWatchTargetY = targetY;
                routeWatchPreviousX = x;
                routeWatchPreviousY = y;
                routeWatchBeforePreviousX = Integer.MIN_VALUE;
                routeWatchBeforePreviousY = Integer.MIN_VALUE;
                routeOscillationReversals = 0;
                routeWatchStaleSteps = 0;
                return false;
            }

            boolean oscillating = routeWatchBeforePreviousX != Integer.MIN_VALUE
                    && isRouteOscillation(x, y, routeWatchPreviousX, routeWatchPreviousY,
                            routeWatchBeforePreviousX, routeWatchBeforePreviousY);
            boolean stalePosition = x == routeWatchPreviousX && y == routeWatchPreviousY;
            if (oscillating) {
                routeOscillationReversals++;
                routeOscillationRecoveries++;
                routeOscillationLandmark = landmark;
                routeWatchStaleSteps = 0;
                result.addProperty("routeOscillationDetected", true);
                result.addProperty("routeOscillationReversals", routeOscillationReversals);
            } else if (stalePosition) {
                routeWatchStaleSteps++;
                result.addProperty("routeStaleSteps", routeWatchStaleSteps);
            } else if (x != routeWatchPreviousX || y != routeWatchPreviousY) {
                routeOscillationReversals = 0;
                routeWatchStaleSteps = 0;
            }
            boolean staleBlocked = stalePosition
                    && isRouteStale(x, y, routeWatchPreviousX, routeWatchPreviousY, routeWatchStaleSteps);
            routeWatchBeforePreviousX = routeWatchPreviousX;
            routeWatchBeforePreviousY = routeWatchPreviousY;
            routeWatchPreviousX = x;
            routeWatchPreviousY = y;

            if (shouldBlockRouteOscillation(routeOscillationReversals)) {
                block("Route oscillation detected while traveling to " + landmark + " around tile "
                        + x + "," + y + "; stopping the durable goal instead of running back and forth.");
                return true;
            }
            if (staleBlocked) {
                routeStaleRecoveries++;
                routeStaleLandmark = landmark;
                result.addProperty("routeStaleDetected", true);
                block("Route stalled while traveling to " + landmark + " at tile "
                        + x + "," + y + "; stopping the durable goal instead of repeating the same walk.");
                return true;
            }
            return false;
        }

        private void clearRouteWatch() {
            routeWatchLandmark = "";
            routeWatchTargetX = Integer.MIN_VALUE;
            routeWatchTargetY = Integer.MIN_VALUE;
            routeWatchPreviousX = Integer.MIN_VALUE;
            routeWatchPreviousY = Integer.MIN_VALUE;
            routeWatchBeforePreviousX = Integer.MIN_VALUE;
            routeWatchBeforePreviousY = Integer.MIN_VALUE;
            routeOscillationReversals = 0;
            routeWatchStaleSteps = 0;
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
                    || routeOscillationRecoveries != lastLoggedRouteOscillationRecoveries
                    || routeStaleRecoveries != lastLoggedRouteStaleRecoveries
                    || miningClickWaits != lastLoggedMiningClickWaits
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
            lastLoggedRouteOscillationRecoveries = routeOscillationRecoveries;
            lastLoggedRouteStaleRecoveries = routeStaleRecoveries;
            lastLoggedMiningClickWaits = miningClickWaits;
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
            json.addProperty("routeOscillationRecoveries", routeOscillationRecoveries);
            if (!routeOscillationLandmark.isEmpty()) {
                json.addProperty("routeOscillationLandmark", routeOscillationLandmark);
            }
            json.addProperty("routeStaleRecoveries", routeStaleRecoveries);
            if (!routeStaleLandmark.isEmpty()) {
                json.addProperty("routeStaleLandmark", routeStaleLandmark);
            }
            json.addProperty("miningClickWaits", miningClickWaits);
            if (ticksElapsed < miningClickWaitUntilTick) {
                json.addProperty("miningClickWaitTicksRemaining", miningClickWaitUntilTick - ticksElapsed);
            }
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
            if (gearMoneyPickaxeTargetItemId > 0) {
                json.addProperty("gearMoneyPickaxeTargetItemId", gearMoneyPickaxeTargetItemId);
                json.addProperty("gearMoneyTargetName", gearMoneyTargetName);
            }
            if (gearMoneyCraftedProductItemId > 0) {
                json.addProperty("gearMoneyCraftedProductItemId", gearMoneyCraftedProductItemId);
            }
            json.addProperty("gearMoneyProcessingStarted", gearMoneyProcessingStarted);
            json.addProperty("gearMoneyRawMaterialsBankedAfterProcessingStarted",
                    gearMoneyRawMaterialsBankedAfterProcessingStarted);
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
