package com.rs2.agent;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executors;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

public class AgentBridgeServer {

    public static final int DEFAULT_PORT = 43610;

    private static final Gson GSON = new Gson();
    private static HttpServer server;

    public static synchronized void start() {
        if (server != null) {
            return;
        }
        try {
            server = HttpServer.create(new InetSocketAddress("127.0.0.1", DEFAULT_PORT), 0);
            registerContexts(server);
            server.setExecutor(Executors.newCachedThreadPool(r -> {
                Thread thread = new Thread(r, "AgentBridgeServer");
                thread.setDaemon(true);
                return thread;
            }));
            server.start();
            System.out.println("Agent bridge listening on 127.0.0.1:" + DEFAULT_PORT + ".");
        } catch (IOException e) {
            System.err.println("Unable to start agent bridge on 127.0.0.1:" + DEFAULT_PORT + ": " + e.getMessage());
            server = null;
        }
    }

    static HttpServer createServerForTests(InetSocketAddress address) throws IOException {
        HttpServer testServer = HttpServer.create(address, 0);
        registerContexts(testServer);
        testServer.setExecutor(Executors.newCachedThreadPool(r -> {
            Thread thread = new Thread(r, "AgentBridgeServerTest");
            thread.setDaemon(true);
            return thread;
        }));
        return testServer;
    }

    private static void registerContexts(HttpServer target) {
        target.createContext("/agent/health", new HealthHandler());
        target.createContext("/agent/session/claim", new ClaimHandler());
        target.createContext("/agent/session/event", new SessionEventHandler());
        target.createContext("/agent/personality/pending", new PersonalityPendingHandler());
        target.createContext("/agent/personality/complete", new PersonalityCompleteHandler());
        target.createContext("/agent/personality/failed", new PersonalityFailedHandler());
        target.createContext("/agent/tool", new ToolHandler());
    }

    private static class HealthHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            JsonObject response = new JsonObject();
            response.addProperty("ok", true);
            response.addProperty("service", "2006scape-agent");
            response.addProperty("sessions", AgentSessionManager.INSTANCE.getSessionCount());
            response.addProperty("pendingClaims", AgentSessionManager.INSTANCE.getPendingClaimCount());
            sendJson(exchange, 200, response);
        }
    }

    private static class ClaimHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendError(exchange, 405, "POST required.");
                return;
            }
            JsonObject request = readJson(exchange);
            String nonce = request.has("nonce") ? request.get("nonce").getAsString() : "";
            AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim(nonce);
            if (!claim.isSuccess()) {
                sendError(exchange, 404, claim.getError());
                return;
            }
            AgentSession session = claim.getSession();
            JsonObject response = new JsonObject();
            response.addProperty("success", true);
            response.addProperty("token", session.getToken());
            response.addProperty("sessionId", session.getSessionId());
            response.addProperty("playerId", session.getPlayerId());
            response.addProperty("playerName", session.getPlayerName());
            sendJson(exchange, 200, response);
        }
    }

    private static class SessionEventHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendError(exchange, 405, "POST required.");
                return;
            }
            AgentSession session = authenticatedSession(exchange);
            if (session == null) {
                sendError(exchange, 401, "Invalid or expired agent session.");
                return;
            }
            JsonObject request = readJson(exchange);
            String event = request.has("event") ? request.get("event").getAsString() : "";
            JsonObject data = request.has("data") && request.get("data").isJsonObject()
                    ? request.get("data").getAsJsonObject()
                    : new JsonObject();
            AgentSessionLog.INSTANCE.clientEvent(session, event, data);
            JsonObject response = new JsonObject();
            response.addProperty("success", true);
            sendJson(exchange, 200, response);
        }
    }

    private static class ToolHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendError(exchange, 405, "POST required.");
                return;
            }
            AgentSession session = authenticatedSession(exchange);
            if (session == null) {
                sendError(exchange, 401, "Invalid or expired agent session.");
                return;
            }
            JsonObject request = readJson(exchange);
            String tool = request.has("tool") ? request.get("tool").getAsString() : "";
            JsonObject arguments = request.has("arguments") && request.get("arguments").isJsonObject()
                    ? request.get("arguments").getAsJsonObject()
                    : new JsonObject();
            long startedAt = System.currentTimeMillis();
            JsonObject response;
            try {
                response = AgentActionService.INSTANCE.submitTool(session.getToken(), tool, arguments);
                long durationMs = System.currentTimeMillis() - startedAt;
                if (response.has("success") && response.get("success").getAsBoolean()) {
                    AgentSessionLog.INSTANCE.toolCompleted(session, tool, arguments, response, durationMs);
                } else {
                    AgentSessionLog.INSTANCE.toolFailed(session, tool, arguments, response, durationMs);
                }
            } catch (RuntimeException e) {
                AgentSessionLog.INSTANCE.toolFailed(session, tool, arguments, e.getMessage(), System.currentTimeMillis() - startedAt);
                throw e;
            }
            sendJson(exchange, response.has("success") && response.get("success").getAsBoolean() ? 200 : 400, response);
        }
    }

    private static class PersonalityPendingHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"GET".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendError(exchange, 405, "GET required.");
                return;
            }
            AgentSession session = authenticatedSession(exchange);
            if (session == null) {
                sendError(exchange, 401, "Invalid or expired agent session.");
                return;
            }
            int limit = queryParamInt(exchange, "limit", 3);
            JsonObject response = AgentPersonalityNarrator.INSTANCE.pendingForSession(session, limit);
            sendJson(exchange, 200, response);
        }
    }

    private static class PersonalityCompleteHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendError(exchange, 405, "POST required.");
                return;
            }
            AgentSession session = authenticatedSession(exchange);
            if (session == null) {
                sendError(exchange, 401, "Invalid or expired agent session.");
                return;
            }
            JsonObject response = AgentPersonalityNarrator.INSTANCE.complete(
                    AgentSessionLog.INSTANCE, session, readJson(exchange));
            sendJson(exchange, response.has("success") && response.get("success").getAsBoolean() ? 200 : 400, response);
        }
    }

    private static class PersonalityFailedHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendError(exchange, 405, "POST required.");
                return;
            }
            AgentSession session = authenticatedSession(exchange);
            if (session == null) {
                sendError(exchange, 401, "Invalid or expired agent session.");
                return;
            }
            JsonObject response = AgentPersonalityNarrator.INSTANCE.failed(
                    AgentSessionLog.INSTANCE, session, readJson(exchange));
            sendJson(exchange, response.has("success") && response.get("success").getAsBoolean() ? 200 : 400, response);
        }
    }

    private static AgentSession authenticatedSession(HttpExchange exchange) {
        String token = exchange.getRequestHeaders().getFirst("X-Agent-Token");
        return token == null ? null : AgentSessionManager.INSTANCE.getSession(token);
    }

    static int queryParamInt(HttpExchange exchange, String name, int fallback) {
        if (exchange == null || exchange.getRequestURI() == null || exchange.getRequestURI().getRawQuery() == null) {
            return fallback;
        }
        String[] parts = exchange.getRequestURI().getRawQuery().split("&");
        for (String part : parts) {
            int equals = part.indexOf('=');
            String key = equals >= 0 ? part.substring(0, equals) : part;
            if (!name.equals(key)) {
                continue;
            }
            String value = equals >= 0 ? part.substring(equals + 1) : "";
            try {
                return Integer.parseInt(value);
            } catch (NumberFormatException ignored) {
                return fallback;
            }
        }
        return fallback;
    }

    private static JsonObject readJson(HttpExchange exchange) throws IOException {
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(exchange.getRequestBody(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
        }
        if (builder.length() == 0) {
            return new JsonObject();
        }
        return new JsonParser().parse(builder.toString()).getAsJsonObject();
    }

    private static void sendError(HttpExchange exchange, int status, String message) throws IOException {
        JsonObject response = new JsonObject();
        response.addProperty("success", false);
        response.addProperty("message", message);
        sendJson(exchange, status, response);
    }

    private static void sendJson(HttpExchange exchange, int status, JsonObject response) throws IOException {
        byte[] bytes = GSON.toJson(response).getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream output = exchange.getResponseBody()) {
            output.write(bytes);
        }
    }
}
