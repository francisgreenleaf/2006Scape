import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class AgentBridgeHttpClient {

    private static final Gson GSON = new Gson();

    private final String baseUrl;
    private String sessionToken;
    private String sessionId;
    private String playerName;

    public AgentBridgeHttpClient(int port) {
        this.baseUrl = "http://127.0.0.1:" + port;
    }

    public boolean health() {
        try {
            JsonObject response = request("GET", "/agent/health", null, null);
            return response.has("ok") && response.get("ok").getAsBoolean();
        } catch (IOException e) {
            return false;
        }
    }

    public JsonObject claimSession(String nonce) throws IOException {
        JsonObject body = new JsonObject();
        body.addProperty("nonce", nonce);
        JsonObject response = request("POST", "/agent/session/claim", body, null);
        if (response.has("success") && response.get("success").getAsBoolean()) {
            sessionToken = response.get("token").getAsString();
            sessionId = response.has("sessionId") ? response.get("sessionId").getAsString() : "";
            playerName = response.has("playerName") ? response.get("playerName").getAsString() : "";
        }
        return response;
    }

    public void recordSessionEvent(String event, JsonObject data) throws IOException {
        if (!hasSession()) {
            return;
        }
        JsonObject body = new JsonObject();
        body.addProperty("event", event == null ? "" : event);
        body.add("data", data == null ? new JsonObject() : data);
        request("POST", "/agent/session/event", body, sessionToken);
    }

    public JsonObject callTool(String tool, JsonObject arguments) throws IOException {
        JsonObject body = new JsonObject();
        body.addProperty("tool", tool);
        body.add("arguments", arguments == null ? new JsonObject() : arguments);
        return request("POST", "/agent/tool", body, sessionToken);
    }

    public boolean hasSession() {
        return sessionToken != null && !sessionToken.isEmpty();
    }

    public void clearSession() {
        sessionToken = null;
        sessionId = null;
        playerName = null;
    }

    public String getSessionId() {
        return sessionId == null ? "" : sessionId;
    }

    public String getPlayerName() {
        return playerName == null ? "" : playerName;
    }

    private JsonObject request(String method, String path, JsonObject body, String token) throws IOException {
        URL url = new URL(baseUrl + path);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(2000);
        connection.setReadTimeout(10000);
        connection.setRequestProperty("Accept", "application/json");
        if (token != null && !token.isEmpty()) {
            connection.setRequestProperty("X-Agent-Token", token);
        }
        if (body != null) {
            byte[] bytes = GSON.toJson(body).getBytes(StandardCharsets.UTF_8);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Content-Length", String.valueOf(bytes.length));
            try (OutputStream output = connection.getOutputStream()) {
                output.write(bytes);
            }
        }
        int code = connection.getResponseCode();
        InputStream stream = code >= 400 ? connection.getErrorStream() : connection.getInputStream();
        String response = readAll(stream);
        if (response.isEmpty()) {
            JsonObject empty = new JsonObject();
            empty.addProperty("success", code < 400);
            return empty;
        }
        return new JsonParser().parse(response).getAsJsonObject();
    }

    private String readAll(InputStream stream) throws IOException {
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
}
