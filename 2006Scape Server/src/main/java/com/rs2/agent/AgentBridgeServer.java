package com.rs2.agent;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.Locale;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;
import com.rs2.Constants;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

public class AgentBridgeServer {

    public static final int DEFAULT_PORT = 43610;
    static final int BRIDGE_CORE_THREADS = 2;
    static final int BRIDGE_MAX_THREADS = 16;
    static final int BRIDGE_QUEUE_CAPACITY = 128;
    static final int MAX_JSON_REQUEST_BYTES = 64 * 1024;

    private static final Gson GSON = new Gson();
    private static HttpServer server;

    public static synchronized void start() {
        if (server != null) {
            return;
        }
        String bindHost = Constants.AGENT_BRIDGE_BIND_HOST == null || Constants.AGENT_BRIDGE_BIND_HOST.trim().length() == 0
                ? "127.0.0.1" : Constants.AGENT_BRIDGE_BIND_HOST.trim();
        int port = Constants.AGENT_BRIDGE_PORT > 0 ? Constants.AGENT_BRIDGE_PORT : DEFAULT_PORT;
        try {
            server = HttpServer.create(new InetSocketAddress(bindHost, port), 0);
            server.createContext("/agent/health", new HealthHandler());
            server.createContext("/agent/session/claim", new ClaimHandler());
            server.createContext("/agent/session/event", new SessionEventHandler());
            server.createContext("/agent/tool", new ToolHandler());
            server.setExecutor(createExecutor());
            server.start();
            System.out.println("Agent bridge listening on " + bindHost + ":" + port + ".");
        } catch (IOException e) {
            System.err.println("Unable to start agent bridge on " + bindHost + ":" + port + ": " + e.getMessage());
            server = null;
        }
    }

    static ThreadPoolExecutor createExecutor() {
        ThreadFactory threadFactory = r -> {
            Thread thread = new Thread(r, "AgentBridgeServer");
            thread.setDaemon(true);
            return thread;
        };
        ThreadPoolExecutor executor = new ThreadPoolExecutor(
                BRIDGE_CORE_THREADS,
                BRIDGE_MAX_THREADS,
                60L,
                TimeUnit.SECONDS,
                new ArrayBlockingQueue<Runnable>(BRIDGE_QUEUE_CAPACITY),
                threadFactory,
                new ThreadPoolExecutor.CallerRunsPolicy());
        executor.allowCoreThreadTimeOut(true);
        return executor;
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
            JsonObject request;
            try {
                request = readJson(exchange);
            } catch (JsonRequestException e) {
                sendError(exchange, e.status, e.getMessage());
                return;
            }
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
            JsonObject request;
            try {
                request = readJson(exchange);
            } catch (JsonRequestException e) {
                sendError(exchange, e.status, e.getMessage());
                return;
            }
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
            JsonObject request;
            try {
                request = readJson(exchange);
            } catch (JsonRequestException e) {
                sendError(exchange, e.status, e.getMessage());
                return;
            }
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
                response = unexpectedToolFailure(tool);
                AgentSessionLog.INSTANCE.toolFailed(session, tool, arguments, response, System.currentTimeMillis() - startedAt);
                System.err.println("Unhandled agent tool failure for session " + session.getSessionId()
                        + " tool " + safeToolNameForLog(tool) + ": " + e.getClass().getName());
                sendJson(exchange, 500, response);
                return;
            }
            sendJson(exchange, response.has("success") && response.get("success").getAsBoolean() ? 200 : 400, response);
        }
    }

    private static AgentSession authenticatedSession(HttpExchange exchange) {
        String token = exchange.getRequestHeaders().getFirst("X-Agent-Token");
        return token == null ? null : AgentSessionManager.INSTANCE.getSession(token);
    }

    private static JsonObject readJson(HttpExchange exchange) throws IOException, JsonRequestException {
        return parseJsonBody(readRequestBody(exchange.getRequestBody()));
    }

    private static byte[] readRequestBody(InputStream input) throws IOException, JsonRequestException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        int total = 0;
        int read;
        while ((read = input.read(buffer)) != -1) {
            total += read;
            if (total > MAX_JSON_REQUEST_BYTES) {
                throw new JsonRequestException(413, "Request JSON body is too large.");
            }
            output.write(buffer, 0, read);
        }
        return output.toByteArray();
    }

    static JsonObject parseJsonBodyForTests(byte[] body) throws JsonRequestException {
        return parseJsonBody(body);
    }

    private static JsonObject parseJsonBody(byte[] body) throws JsonRequestException {
        if (body == null || body.length == 0) {
            return new JsonObject();
        }
        if (body.length > MAX_JSON_REQUEST_BYTES) {
            throw new JsonRequestException(413, "Request JSON body is too large.");
        }
        String text = new String(body, StandardCharsets.UTF_8).trim();
        if (text.length() == 0) {
            return new JsonObject();
        }
        try {
            JsonElement parsed = new JsonParser().parse(text);
            if (parsed == null || !parsed.isJsonObject()) {
                throw new JsonRequestException(400, "Request JSON body must be an object.");
            }
            return parsed.getAsJsonObject();
        } catch (JsonParseException | IllegalStateException e) {
            throw new JsonRequestException(400, "Request JSON body is not valid JSON.");
        }
    }

    private static void sendError(HttpExchange exchange, int status, String message) throws IOException {
        JsonObject response = new JsonObject();
        response.addProperty("success", false);
        response.addProperty("message", message);
        sendJson(exchange, status, response);
    }

    static JsonObject unexpectedToolFailureForTests(String tool) {
        return unexpectedToolFailure(tool);
    }

    private static JsonObject unexpectedToolFailure(String tool) {
        JsonObject response = new JsonObject();
        response.addProperty("success", false);
        response.addProperty("message", "Agent tool failed unexpectedly. Check the server log.");
        response.addProperty("errorCode", "tool_runtime_exception");
        response.addProperty("tool", safeToolNameForLog(tool));
        return response;
    }

    private static String safeToolNameForLog(String tool) {
        if (tool == null) {
            return "";
        }
        String cleaned = tool.trim().replaceAll("[^A-Za-z0-9_\\-.]", "_");
        String lower = cleaned.toLowerCase(Locale.ENGLISH);
        if (lower.contains("token") || lower.contains("password") || lower.contains("secret")
                || lower.contains("cookie") || lower.contains("api_key") || lower.contains("apikey")
                || lower.contains("auth_key")) {
            return "invalid_tool_name";
        }
        return cleaned.length() > 80 ? cleaned.substring(0, 80) : cleaned;
    }

    private static void sendJson(HttpExchange exchange, int status, JsonObject response) throws IOException {
        byte[] bytes = GSON.toJson(response).getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream output = exchange.getResponseBody()) {
            output.write(bytes);
        }
    }

    static final class JsonRequestException extends IOException {
        final int status;

        private JsonRequestException(int status, String message) {
            super(message);
            this.status = status;
        }
    }
}
