package com.rs2.agent;

import com.google.gson.JsonObject;
import org.junit.Test;

import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class AgentActionServiceTest {

    @Test
    public void queuedActionRunsWhenServiceIsProcessed() throws Exception {
        FutureTask<JsonObject> task = new FutureTask<JsonObject>(new Callable<JsonObject>() {
            @Override
            public JsonObject call() {
                return AgentActionService.INSTANCE.submitOnGameTick("test", new Callable<JsonObject>() {
                    @Override
                    public JsonObject call() {
                        JsonObject result = AgentToolService.success("processed");
                        result.addProperty("value", 42);
                        return result;
                    }
                });
            }
        });
        Thread thread = new Thread(task, "AgentActionServiceTest");
        thread.start();

        for (int i = 0; i < 20 && !task.isDone(); i++) {
            AgentActionService.INSTANCE.processPendingActions();
            Thread.sleep(10L);
        }

        JsonObject result = task.get(1, TimeUnit.SECONDS);
        assertTrue(result.get("success").getAsBoolean());
        assertEquals(42, result.get("value").getAsInt());
    }

    @Test
    public void waitActionCompletesOnRequestedGameTickWithoutSleepingFirst() throws Exception {
        FutureTask<JsonObject> task = new FutureTask<JsonObject>(new Callable<JsonObject>() {
            @Override
            public JsonObject call() {
                return AgentActionService.INSTANCE.submitAfterGameTicks(2, new Callable<JsonObject>() {
                    @Override
                    public JsonObject call() {
                        JsonObject result = AgentToolService.success("waited");
                        result.addProperty("value", 7);
                        return result;
                    }
                });
            }
        });
        Thread thread = new Thread(task, "AgentActionServiceWaitTest");
        thread.start();

        for (int i = 0; i < 20 && AgentActionService.INSTANCE.pendingActionCountForTests() == 0; i++) {
            Thread.sleep(5L);
        }
        assertTrue(AgentActionService.INSTANCE.pendingActionCountForTests() > 0);

        AgentActionService.INSTANCE.processPendingActions();
        assertFalse(task.isDone());

        AgentActionService.INSTANCE.processPendingActions();
        JsonObject result = task.get(1, TimeUnit.SECONDS);
        assertTrue(result.get("success").getAsBoolean());
        assertEquals(7, result.get("value").getAsInt());
    }
}
