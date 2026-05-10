package com.rs2.agent;

import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.game.content.skills.SkillHandler;
import com.rs2.game.players.Player;

public class AgentActionService {

    public static final AgentActionService INSTANCE = new AgentActionService();

    private static final long ACTION_TIMEOUT_MS = 5000L;

    private final ConcurrentLinkedQueue<QueuedAction> queuedActions = new ConcurrentLinkedQueue<QueuedAction>();
    private final AtomicLong serverTick = new AtomicLong(0L);

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

    private static boolean getBoolean(JsonObject object, String name, boolean fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            return object.get(name).getAsBoolean();
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
}
