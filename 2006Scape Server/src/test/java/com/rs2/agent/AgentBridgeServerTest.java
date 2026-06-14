package com.rs2.agent;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ThreadPoolExecutor;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import com.sun.net.httpserver.HttpServer;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class AgentBridgeServerTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private static final Gson GSON = new Gson();

    private File logDirectory;
    private HttpServer server;
    private int port;
    private String token;
    private AgentSession session;

    @Before
    public void setUp() throws Exception {
        logDirectory = temporaryFolder.newFolder("agent-sessions");
        AgentSessionLog.INSTANCE.setLogDirectoryForTests(logDirectory);
        AgentPersonalityNarrator.INSTANCE.resetForTests();
        TestPlayer player = new TestPlayer(10);
        player.playerName = "bridge_tester";
        player.disconnected = false;
        player.absX = 3200;
        player.absY = 3201;
        PlayerHandler.players[10] = player;

        token = AgentSessionManager.INSTANCE.registerClaim(player, "nonce-bridge-test");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-bridge-test");
        session = claim.getSession();

        server = AgentBridgeServer.createServerForTests(new InetSocketAddress("127.0.0.1", 0));
        server.start();
        port = server.getAddress().getPort();
    }

    @After
    public void tearDown() {
        if (server != null) {
            server.stop(0);
            server = null;
        }
        if (token != null) {
            AgentSessionManager.INSTANCE.invalidate(token, "test");
            token = null;
        }
        AgentPersonalityNarrator.INSTANCE.resetForTests();
        AgentSessionLog.INSTANCE.resetLogDirectoryForTests();
        PlayerHandler.players[10] = null;
    }

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

    @Test
    public void personalityEndpointsReturnPendingAndAcceptCompletionOrFailure() throws Exception {
        AgentPersonalityNarrator.INSTANCE.setNowForTests(1_000_000L);
        queueRouteFriction();

        HttpResult unauthorized = request("GET", "/agent/personality/pending?limit=3", null, null);
        assertEquals(401, unauthorized.status);

        HttpResult pendingResponse = request("GET", "/agent/personality/pending?limit=3", null, token);
        assertEquals(200, pendingResponse.status);
        JsonArray pending = pendingResponse.body.get("requests").getAsJsonArray();
        assertEquals(1, pending.size());
        assertEquals("route_friction_repeated", pending.get(0).getAsJsonObject().get("milestone").getAsString());
        String firstRequestId = pending.get(0).getAsJsonObject().get("requestId").getAsString();
        assertCompactPendingPayload(pendingResponse.body);

        JsonObject failedRequest = new JsonObject();
        failedRequest.addProperty("requestId", firstRequestId);
        failedRequest.addProperty("reason", "timeout");
        HttpResult failedResponse = request("POST", "/agent/personality/failed", failedRequest, token);
        assertEquals(200, failedResponse.status);
        assertTrue(failedResponse.body.get("success").getAsBoolean());
        assertEquals(0, AgentPersonalityNarrator.INSTANCE.pendingCountForTests());

        AgentPersonalityNarrator.INSTANCE.setNowForTests(1_700_001L);
        JsonObject goal = new JsonObject();
        JsonObject goalData = new JsonObject();
        goalData.addProperty("message", "Reached the bank safely.");
        goal.add("goal", goalData);
        AgentSessionLog.INSTANCE.clientEvent(session, "goal_completed", goal);

        pendingResponse = request("GET", "/agent/personality/pending?limit=3", null, token);
        pending = pendingResponse.body.get("requests").getAsJsonArray();
        assertEquals(1, pending.size());
        String secondRequestId = pending.get(0).getAsJsonObject().get("requestId").getAsString();

        JsonObject completeRequest = new JsonObject();
        completeRequest.addProperty("requestId", secondRequestId);
        completeRequest.addProperty("text", "Good. Bank done, boots still working.");
        HttpResult completeResponse = request("POST", "/agent/personality/complete", completeRequest, token);
        assertEquals(200, completeResponse.status);
        assertTrue(completeResponse.body.get("success").getAsBoolean());
        assertEquals(0, AgentPersonalityNarrator.INSTANCE.pendingCountForTests());
    }

    private void queueRouteFriction() {
        JsonObject arguments = new JsonObject();
        JsonObject failure = AgentToolService.failure("No matching object found nearby.");
        AgentSessionLog.INSTANCE.toolFailed(session, "find_nearest_object", arguments, failure, 5L);
        AgentSessionLog.INSTANCE.toolFailed(session, "find_nearest_object", arguments, failure, 5L);
        AgentSessionLog.INSTANCE.toolFailed(session, "find_nearest_object", arguments, failure, 5L);
    }

    private void assertCompactPendingPayload(JsonObject body) {
        String json = body.toString();
        assertFalse(json.contains("arguments"));
        assertFalse(json.contains("inventory"));
        assertFalse(json.contains("bank"));
        assertFalse(json.contains("3200"));
        assertFalse(json.contains("Markdown"));
    }

    private HttpResult request(String method, String path, JsonObject body, String authToken) throws Exception {
        URL url = new URL("http://127.0.0.1:" + port + path);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(2000);
        connection.setReadTimeout(2000);
        if (authToken != null) {
            connection.setRequestProperty("X-Agent-Token", authToken);
        }
        if (body != null) {
            byte[] bytes = GSON.toJson(body).getBytes(StandardCharsets.UTF_8);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream output = connection.getOutputStream()) {
                output.write(bytes);
            }
        }
        int status = connection.getResponseCode();
        InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
        String responseText = readAll(stream);
        JsonObject response = responseText.length() == 0
                ? new JsonObject()
                : new JsonParser().parse(responseText).getAsJsonObject();
        connection.disconnect();
        return new HttpResult(status, response);
    }

    private String readAll(InputStream stream) throws Exception {
        if (stream == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        return builder.toString();
    }

    private static class HttpResult {
        private final int status;
        private final JsonObject body;

        private HttpResult(int status, JsonObject body) {
            this.status = status;
            this.body = body;
        }
    }

    private static class TestPlayer extends Player {
        private TestPlayer(int playerId) {
            super(playerId);
        }
    }
}
