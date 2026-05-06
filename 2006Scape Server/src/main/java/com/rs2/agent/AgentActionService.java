package com.rs2.agent;

import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.game.players.Player;

public class AgentActionService {

    public static final AgentActionService INSTANCE = new AgentActionService();

    private static final long ACTION_TIMEOUT_MS = 5000L;

    private final ConcurrentLinkedQueue<QueuedAction> queuedActions = new ConcurrentLinkedQueue<QueuedAction>();

    public JsonObject submitTool(String token, String tool, JsonObject arguments) {
        if ("wait_ticks".equals(tool)) {
            int ticks = Math.max(1, Math.min(25, getInt(arguments, "ticks", 1)));
            try {
                Thread.sleep((long) ticks * Constants.CYCLE_TIME);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return AgentToolService.failure("Interrupted while waiting.");
            }
            return submitOnGameTick(token, new Callable<JsonObject>() {
                @Override
                public JsonObject call() {
                    AgentSession session = AgentSessionManager.INSTANCE.getSession(token);
                    if (session == null || session.getPlayer() == null) {
                        return AgentToolService.failure("Agent session is no longer valid.");
                    }
                    JsonObject result = AgentToolService.observeState(session.getPlayer());
                    result.addProperty("waitedTicks", ticks);
                    return result;
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

    public JsonObject submitOnGameTick(String token, Callable<JsonObject> action) {
        QueuedAction queuedAction = new QueuedAction(action);
        queuedActions.add(queuedAction);
        try {
            if (!queuedAction.await(ACTION_TIMEOUT_MS)) {
                return AgentToolService.failure("Timed out waiting for the next game tick.");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return AgentToolService.failure("Interrupted while waiting for game tick.");
        }
        return queuedAction.getResult();
    }

    public void processPendingActions() {
        int processed = 0;
        QueuedAction queuedAction;
        while ((queuedAction = queuedActions.poll()) != null && processed++ < 100) {
            queuedAction.execute();
        }
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

    private static class QueuedAction {
        private final Callable<JsonObject> action;
        private final CountDownLatch latch = new CountDownLatch(1);
        private JsonObject result;

        private QueuedAction(Callable<JsonObject> action) {
            this.action = action;
        }

        private void execute() {
            try {
                result = action.call();
            } catch (Exception e) {
                result = AgentToolService.failure("Agent action failed: " + e.getMessage());
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
