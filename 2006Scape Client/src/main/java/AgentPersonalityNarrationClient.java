import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public class AgentPersonalityNarrationClient {

    private static final Gson GSON = new Gson();
    private static final long POLL_INTERVAL_MS = 30_000L;

    private final AgentBridgeHttpClient bridgeHttpClient;
    private final AgentTerminalLog terminalLog;
    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "AgentPersonalityNarrationClient");
        thread.setDaemon(true);
        return thread;
    });
    private final AtomicInteger requestId = new AtomicInteger(1);
    private final Map<Integer, CompletableFuture<JsonObject>> pendingRequests =
            new ConcurrentHashMap<Integer, CompletableFuture<JsonObject>>();
    private final StringBuilder currentNarrationText = new StringBuilder();

    private volatile boolean started;
    private volatile boolean initialized;
    private volatile boolean accountReady;
    private volatile String threadId;
    private volatile Process process;
    private volatile BufferedWriter writer;
    private volatile CountDownLatch turnCompletedLatch;

    public AgentPersonalityNarrationClient(AgentBridgeHttpClient bridgeHttpClient, AgentTerminalLog terminalLog) {
        this.bridgeHttpClient = bridgeHttpClient;
        this.terminalLog = terminalLog;
    }

    public synchronized void start() {
        if (started) {
            return;
        }
        started = true;
        executor.submit(() -> pollLoop());
    }

    public void pumpOnceAsync() {
        start();
        executor.submit(() -> pumpOnce());
    }

    private void pollLoop() {
        while (true) {
            try {
                pumpOnce();
                Thread.sleep(POLL_INTERVAL_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            } catch (Exception ignored) {
            }
        }
    }

    private void pumpOnce() {
        if (!bridgeHttpClient.hasSession()) {
            return;
        }
        JsonObject pending;
        try {
            pending = bridgeHttpClient.fetchPendingPersonality(3);
        } catch (IOException e) {
            return;
        }
        JsonArray requests = pending.has("requests") && pending.get("requests").isJsonArray()
                ? pending.get("requests").getAsJsonArray()
                : new JsonArray();
        if (requests.size() == 0) {
            return;
        }
        if (!ensureNarrationThread()) {
            failAll(requests, "codex_narration_unavailable");
            return;
        }
        for (int i = 0; i < requests.size(); i++) {
            JsonObject request = requests.get(i).getAsJsonObject();
            String requestId = string(request, "requestId", "");
            try {
                String text = generate(request);
                bridgeHttpClient.completePersonality(requestId, text);
            } catch (Exception e) {
                try {
                    bridgeHttpClient.failPersonality(requestId, cleanMessage(e));
                } catch (IOException ignored) {
                }
            }
        }
    }

    private void failAll(JsonArray requests, String reason) {
        for (int i = 0; i < requests.size(); i++) {
            JsonObject request = requests.get(i).getAsJsonObject();
            try {
                bridgeHttpClient.failPersonality(string(request, "requestId", ""), reason);
            } catch (IOException ignored) {
            }
        }
    }

    private synchronized boolean ensureNarrationThread() {
        try {
            startProcess();
            if (!initialized) {
                JsonObject clientInfo = new JsonObject();
                clientInfo.addProperty("name", "2006scape_personality_narrator");
                clientInfo.addProperty("title", "2006Scape Personality Narrator");
                clientInfo.addProperty("version", "0.1.0");
                JsonObject capabilities = new JsonObject();
                capabilities.addProperty("experimentalApi", true);
                JsonObject params = new JsonObject();
                params.add("clientInfo", clientInfo);
                params.add("capabilities", capabilities);
                awaitResult(sendRequest("initialize", params), 30_000L);
                sendNotification("initialized", new JsonObject());
                initialized = true;
            }
            if (!accountReady && !refreshAccount()) {
                return false;
            }
            if (threadId == null || threadId.isEmpty()) {
                JsonObject params = new JsonObject();
                params.addProperty("cwd", workspaceDir());
                params.addProperty("approvalPolicy", "never");
                params.addProperty("sandbox", "read-only");
                params.addProperty("serviceName", "2006Scape Personality Narrator");
                params.addProperty("developerInstructions", developerInstructions());
                params.add("dynamicTools", new JsonArray());
                JsonObject result = awaitResult(sendRequest("thread/start", params), 30_000L);
                threadId = result.get("thread").getAsJsonObject().get("id").getAsString();
            }
            return true;
        } catch (Exception e) {
            terminalLog.warn("Personality narration unavailable: " + cleanMessage(e));
            return false;
        }
    }

    private synchronized void startProcess() throws IOException {
        if (process != null && process.isAlive() && writer != null) {
            return;
        }
        File executable = findCodexExecutable();
        ProcessBuilder builder = executable == null
                ? new ProcessBuilder("codex", "app-server", "--listen", "stdio://")
                : new ProcessBuilder(executable.getAbsolutePath(), "app-server", "--listen", "stdio://");
        builder.redirectError(ProcessBuilder.Redirect.INHERIT);
        process = builder.start();
        writer = new BufferedWriter(new OutputStreamWriter(process.getOutputStream(), StandardCharsets.UTF_8));
        Thread readerThread = new Thread(() -> readLoop(), "PersonalityNarrationReader");
        readerThread.setDaemon(true);
        readerThread.start();
    }

    private boolean refreshAccount() {
        try {
            JsonObject params = new JsonObject();
            params.addProperty("refreshToken", false);
            JsonObject result = awaitResult(sendRequest("account/read", params), 15_000L);
            JsonObject account = result.has("account") && result.get("account").isJsonObject()
                    ? result.get("account").getAsJsonObject()
                    : null;
            accountReady = account != null;
            return accountReady;
        } catch (Exception e) {
            accountReady = false;
            return false;
        }
    }

    private String generate(JsonObject request) throws Exception {
        currentNarrationText.setLength(0);
        turnCompletedLatch = new CountDownLatch(1);
        JsonObject params = new JsonObject();
        params.addProperty("threadId", threadId);
        params.add("input", userInput(prompt(request)));
        JsonObject sandboxPolicy = new JsonObject();
        sandboxPolicy.addProperty("type", "readOnly");
        sandboxPolicy.addProperty("networkAccess", false);
        params.add("sandboxPolicy", sandboxPolicy);
        params.addProperty("approvalPolicy", "never");
        awaitResult(sendRequest("turn/start", params), 30_000L);
        CountDownLatch latch = turnCompletedLatch;
        if (latch != null) {
            latch.await(60_000L, TimeUnit.MILLISECONDS);
        }
        return compact(currentNarrationText.toString(), 140);
    }

    private String prompt(JsonObject request) {
        return "Write 1 short first-person RuneScape-style thought for this player. "
                + "Use only the facts. No tools, logs, Codex, APIs, hidden state, coordinates, or secrets. "
                + "Max 120 characters. If unsafe or boring, return empty text.\n\n"
                + "Request JSON:\n" + GSON.toJson(request);
    }

    private String developerInstructions() {
        return "You generate one compact, diegetic 2006Scape player thought from a sanitized JSON capsule. "
                + "Do not call tools. Do not mention automation, logs, tools, Codex, APIs, tokens, coordinates, or hidden state. "
                + "Return only the line of dialogue, or return an empty string.";
    }

    private void readLoop() {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                handleServerMessage(line);
            }
        } catch (IOException ignored) {
        }
    }

    private void handleServerMessage(String line) {
        JsonObject message;
        try {
            message = new JsonParser().parse(line).getAsJsonObject();
        } catch (Exception ignored) {
            return;
        }
        if (message.has("id") && !message.has("method")) {
            int id = message.get("id").getAsInt();
            CompletableFuture<JsonObject> future = pendingRequests.remove(id);
            if (future != null) {
                future.complete(message);
            }
            return;
        }
        if (message.has("id") && message.has("method")) {
            sendError(message.get("id").getAsInt(), -32601, "Personality narrator does not expose tools.");
            return;
        }
        if (!message.has("method")) {
            return;
        }
        String method = message.get("method").getAsString();
        JsonObject params = message.has("params") && message.get("params").isJsonObject()
                ? message.get("params").getAsJsonObject()
                : new JsonObject();
        if ("item/agentMessage/delta".equals(method) && params.has("delta")) {
            currentNarrationText.append(params.get("delta").getAsString());
        } else if ("item/completed".equals(method) && params.has("item")) {
            JsonObject item = params.get("item").getAsJsonObject();
            if (item.has("type") && "agentMessage".equals(item.get("type").getAsString()) && item.has("text")) {
                if (currentNarrationText.length() == 0) {
                    currentNarrationText.append(item.get("text").getAsString());
                }
            }
        } else if ("turn/completed".equals(method)) {
            CountDownLatch latch = turnCompletedLatch;
            if (latch != null) {
                latch.countDown();
            }
        }
    }

    private void sendError(int id, int code, String messageText) {
        JsonObject response = new JsonObject();
        response.addProperty("id", id);
        JsonObject error = new JsonObject();
        error.addProperty("code", code);
        error.addProperty("message", messageText == null ? "Unsupported request." : messageText);
        response.add("error", error);
        try {
            sendJson(response);
        } catch (IOException ignored) {
        }
    }

    private CompletableFuture<JsonObject> sendRequest(String method, JsonObject params) {
        int id = requestId.getAndIncrement();
        CompletableFuture<JsonObject> future = new CompletableFuture<JsonObject>();
        pendingRequests.put(id, future);
        JsonObject request = new JsonObject();
        request.addProperty("id", id);
        request.addProperty("method", method);
        if (params != null) {
            request.add("params", params);
        }
        try {
            sendJson(request);
        } catch (IOException e) {
            pendingRequests.remove(id);
            future.completeExceptionally(e);
        }
        return future;
    }

    private void sendNotification(String method, JsonObject params) throws IOException {
        JsonObject request = new JsonObject();
        request.addProperty("method", method);
        if (params != null) {
            request.add("params", params);
        }
        sendJson(request);
    }

    private synchronized void sendJson(JsonObject object) throws IOException {
        if (writer == null) {
            throw new IOException("Codex app-server is not running.");
        }
        writer.write(GSON.toJson(object));
        writer.newLine();
        writer.flush();
    }

    private JsonObject awaitResult(CompletableFuture<JsonObject> future, long timeoutMs) throws Exception {
        JsonObject response = future.get(timeoutMs, TimeUnit.MILLISECONDS);
        if (response.has("error")) {
            JsonObject error = response.get("error").getAsJsonObject();
            String message = error.has("message") ? error.get("message").getAsString() : error.toString();
            throw new IOException(message);
        }
        return response.has("result") && response.get("result").isJsonObject()
                ? response.get("result").getAsJsonObject()
                : new JsonObject();
    }

    private JsonArray userInput(String text) {
        JsonArray input = new JsonArray();
        JsonObject item = new JsonObject();
        item.addProperty("type", "text");
        item.addProperty("text", text);
        item.add("text_elements", new JsonArray());
        input.add(item);
        return input;
    }

    private File findCodexExecutable() {
        String[] candidates = {"/opt/homebrew/bin/codex", "/usr/local/bin/codex"};
        for (String candidate : candidates) {
            File file = new File(candidate);
            if (file.exists() && file.canExecute()) {
                return file;
            }
        }
        return null;
    }

    private String workspaceDir() {
        File cwd = new File(System.getProperty("user.dir", "."));
        File parent = cwd.getParentFile();
        if (parent != null && "2006Scape Client".equals(cwd.getName())) {
            return parent.getAbsolutePath();
        }
        return cwd.getAbsolutePath();
    }

    private String cleanMessage(Exception e) {
        String message = e.getMessage();
        if (message == null || message.trim().isEmpty()) {
            message = e.getClass().getSimpleName();
        }
        return compact(message, 120);
    }

    private static String string(JsonObject object, String name, String fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            String value = object.get(name).getAsString();
            return value == null ? fallback : value.trim();
        }
        return fallback;
    }

    private static String compact(String value, int maxLength) {
        if (value == null) {
            return "";
        }
        String text = value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').trim();
        while (text.contains("  ")) {
            text = text.replace("  ", " ");
        }
        if (text.length() > maxLength) {
            text = text.substring(0, Math.max(0, maxLength - 3)) + "...";
        }
        return text;
    }
}
