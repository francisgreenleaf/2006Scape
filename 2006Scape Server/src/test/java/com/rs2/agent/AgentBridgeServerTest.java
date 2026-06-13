package com.rs2.agent;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.ThreadPoolExecutor;

import com.google.gson.JsonObject;

import org.junit.Test;

public class AgentBridgeServerTest {

    @Test
    public void bridgeExecutorIsBoundedAndAppliesBackpressure() {
        ThreadPoolExecutor executor = AgentBridgeServer.createExecutor();
        try {
            assertEquals(AgentBridgeServer.BRIDGE_CORE_THREADS, executor.getCorePoolSize());
            assertEquals(AgentBridgeServer.BRIDGE_MAX_THREADS, executor.getMaximumPoolSize());
            assertEquals(AgentBridgeServer.BRIDGE_QUEUE_CAPACITY, executor.getQueue().remainingCapacity());
            assertTrue(executor.getRejectedExecutionHandler() instanceof ThreadPoolExecutor.CallerRunsPolicy);
            assertTrue(executor.allowsCoreThreadTimeOut());
        } finally {
            executor.shutdownNow();
        }
    }

    @Test
    public void jsonBodyParserAcceptsEmptyAndObjectBodies() throws Exception {
        assertEquals(0, AgentBridgeServer.parseJsonBodyForTests(new byte[0]).entrySet().size());

        JsonObject parsed = AgentBridgeServer.parseJsonBodyForTests(
                "{\"tool\":\"observe_state_XS\"}".getBytes(StandardCharsets.UTF_8));

        assertEquals("observe_state_XS", parsed.get("tool").getAsString());
    }

    @Test
    public void jsonBodyParserRejectsMalformedJson() {
        try {
            AgentBridgeServer.parseJsonBodyForTests("{".getBytes(StandardCharsets.UTF_8));
            throw new AssertionError("malformed JSON was accepted");
        } catch (AgentBridgeServer.JsonRequestException e) {
            assertEquals(400, e.status);
            assertTrue(e.getMessage().contains("not valid JSON"));
        }
    }

    @Test
    public void jsonBodyParserRejectsNonObjectJson() {
        try {
            AgentBridgeServer.parseJsonBodyForTests("[]".getBytes(StandardCharsets.UTF_8));
            throw new AssertionError("non-object JSON was accepted");
        } catch (AgentBridgeServer.JsonRequestException e) {
            assertEquals(400, e.status);
            assertTrue(e.getMessage().contains("must be an object"));
        }
    }

    @Test
    public void jsonBodyParserRejectsOversizedBodies() {
        byte[] body = new byte[AgentBridgeServer.MAX_JSON_REQUEST_BYTES + 1];
        try {
            AgentBridgeServer.parseJsonBodyForTests(body);
            throw new AssertionError("oversized JSON body was accepted");
        } catch (AgentBridgeServer.JsonRequestException e) {
            assertEquals(413, e.status);
            assertTrue(e.getMessage().contains("too large"));
        }
    }

    @Test
    public void unexpectedToolFailureResponseIsCompactAndSanitized() {
        JsonObject response = AgentBridgeServer.unexpectedToolFailureForTests("bad tool; token=secret");

        assertFalse(response.get("success").getAsBoolean());
        assertEquals("tool_runtime_exception", response.get("errorCode").getAsString());
        assertEquals("invalid_tool_name", response.get("tool").getAsString());
        assertFalse(response.toString().contains("token=secret"));
        assertFalse(response.toString().contains("token_secret"));
        assertFalse(response.toString().contains(";"));
    }
}
