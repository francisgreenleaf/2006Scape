import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import javax.swing.JPasswordField;
import javax.swing.JOptionPane;
import javax.swing.SwingUtilities;
import java.io.IOException;
import java.security.SecureRandom;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class AgentClientController {

    private final Game game;
    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "AgentClientController");
        thread.setDaemon(true);
        return thread;
    });
    private final AgentBridgeHttpClient bridgeHttpClient;
    private final CodexAppServerClient codexClient;
    private final SecureRandom secureRandom = new SecureRandom();
    private static final Pattern COMBAT_GOAL_LEVEL_PATTERN = Pattern.compile("(?:base|level|to)\\s+(\\d{1,2})",
            Pattern.CASE_INSENSITIVE);

    private volatile boolean taskRunning;

    public AgentClientController(Game game) {
        this.game = game;
        this.bridgeHttpClient = new AgentBridgeHttpClient(ClientSettings.AGENT_BRIDGE_PORT);
        Consumer<String> messages = text -> pushAgentMessage(text);
        this.codexClient = new CodexAppServerClient(bridgeHttpClient, messages, () -> taskRunning = false);
    }

    public void handleChatCommand(String rawCommand) {
        String trimmed = rawCommand == null ? "" : rawCommand.trim();
        String command = trimmed.length() > "/agent".length() ? trimmed.substring("/agent".length()).trim() : "";
        if (command.isEmpty() || "status".equalsIgnoreCase(command)) {
            showStatus();
            return;
        }
        if ("key".equalsIgnoreCase(command) || "setup".equalsIgnoreCase(command)) {
            promptForApiKey();
            return;
        }
        if ("stop".equalsIgnoreCase(command)) {
            stopAgent();
            return;
        }
        if ("goal".equalsIgnoreCase(command) || "observe goal".equalsIgnoreCase(command)
                || "observe_goal".equalsIgnoreCase(command)) {
            observeGoal();
            return;
        }
        runTask(command);
    }

    public void promptForApiKey() {
        SwingUtilities.invokeLater(() -> {
            JPasswordField field = new JPasswordField(36);
            int result = JOptionPane.showConfirmDialog(game.getGameComponent(), field,
                    "OpenAI API key for Codex agent", JOptionPane.OK_CANCEL_OPTION, JOptionPane.PLAIN_MESSAGE);
            if (result != JOptionPane.OK_OPTION) {
                return;
            }
            char[] password = field.getPassword();
            String apiKey = new String(password).trim();
            for (int i = 0; i < password.length; i++) {
                password[i] = 0;
            }
            if (apiKey.isEmpty()) {
                pushAgentMessage("No API key entered.");
                return;
            }
            executor.submit(() -> {
                try {
                    codexClient.loginWithApiKey(apiKey);
                    pushAgentMessage("API key saved by Codex auth.");
                } catch (Exception e) {
                    pushAgentMessage("API-key login failed: " + cleanMessage(e));
                }
            });
        });
    }

    public String getSettingsStatusLine() {
        return codexClient.status();
    }

    private void showStatus() {
        executor.submit(() -> {
            try {
                ensureAppServer();
                codexClient.refreshAccount();
                if (bridgeHttpClient.health() && !bridgeHttpClient.hasSession()) {
                    tryClaimGameSession();
                }
            } catch (Exception ignored) {
            }
            pushAgentMessage("Status: " + codexClient.status());
        });
    }

    private void stopAgent() {
        executor.submit(() -> {
            codexClient.interruptCurrentTurn();
            if (bridgeHttpClient.hasSession()) {
                try {
                    bridgeHttpClient.callTool("stop_goal", new JsonObject());
                    bridgeHttpClient.callTool("cancel_current_action", new JsonObject());
                } catch (IOException ignored) {
                }
            }
            taskRunning = false;
            pushAgentMessage("Stopped.");
        });
    }

    private void observeGoal() {
        executor.submit(() -> {
            try {
                ensureBridgeSessionOnly();
                JsonObject result = bridgeHttpClient.callTool("observe_goal", new JsonObject());
                pushAgentMessage(formatGoalStatus(result));
            } catch (Exception e) {
                pushAgentMessage("Goal observe failed: " + cleanMessage(e));
            }
        });
    }

    private void runTask(String command) {
        if (taskRunning) {
            pushAgentMessage("Already running. Use /agent stop first.");
            return;
        }
        taskRunning = true;
        pushAgentMessage("Starting: " + command);
        if (isLocalDurableCombatGoal(command)) {
            executor.submit(() -> startLocalDurableCombatGoal(command));
            return;
        }
        executor.submit(() -> {
            try {
                ensureReadyForTask();
                recordTurnRequested(command);
                codexClient.startTurn(command);
            } catch (Exception e) {
                taskRunning = false;
                pushAgentMessage(cleanMessage(e));
            }
        });
    }

    private boolean isLocalDurableCombatGoal(String command) {
        String lower = command == null ? "" : command.toLowerCase();
        return lower.contains("train combat") || lower.contains("combat to base")
                || lower.contains("attack") && lower.contains("strength") && lower.contains("defence");
    }

    private void startLocalDurableCombatGoal(String command) {
        try {
            ensureBridgeSessionOnly();
            recordTurnRequested(command);
            JsonObject arguments = new JsonObject();
            arguments.addProperty("targetLevel", parseCombatGoalTargetLevel(command));
            arguments.addProperty("stepIntervalTicks", 4);
            arguments.addProperty("maxActions", 250000);
            JsonObject result = bridgeHttpClient.callTool("start_combat_goal", arguments);
            if (isInvalidSession(result)) {
                bridgeHttpClient.clearSession();
                tryClaimGameSession();
                result = bridgeHttpClient.callTool("start_combat_goal", arguments);
            }
            if (result.has("success") && result.get("success").getAsBoolean()) {
                pushAgentMessage("Durable combat goal started. Keeping the client logged in while the server trains.");
                return;
            }
            pushAgentMessage(result.has("message") ? result.get("message").getAsString()
                    : "Unable to start durable combat goal.");
        } catch (Exception e) {
            pushAgentMessage(cleanMessage(e));
        } finally {
            taskRunning = false;
        }
    }

    private void ensureBridgeSessionOnly() throws Exception {
        if (!bridgeHttpClient.health()) {
            throw new IOException("Local agent bridge is not running. Start the 2006Scape server first.");
        }
        if (!bridgeHttpClient.hasSession()) {
            tryClaimGameSession();
        }
    }

    private boolean isInvalidSession(JsonObject result) {
        if (result == null || !result.has("success") || result.get("success").getAsBoolean()
                || !result.has("message")) {
            return false;
        }
        String message = result.get("message").getAsString().toLowerCase();
        return message.contains("invalid") || message.contains("expired") || message.contains("session");
    }

    private int parseCombatGoalTargetLevel(String command) {
        Matcher matcher = COMBAT_GOAL_LEVEL_PATTERN.matcher(command == null ? "" : command);
        if (matcher.find()) {
            try {
                return Integer.parseInt(matcher.group(1));
            } catch (NumberFormatException ignored) {
            }
        }
        return 60;
    }

    private void ensureReadyForTask() throws Exception {
        ensureAppServer();
        if (!bridgeHttpClient.health()) {
            throw new IOException("Local agent bridge is not running. Start the 2006Scape server first.");
        }
        if (!bridgeHttpClient.hasSession()) {
            tryClaimGameSession();
        }
        if (!codexClient.hasAccount() && !codexClient.refreshAccount()) {
            throw new IOException("Codex needs an API key. Use /agent key.");
        }
    }

    private void ensureAppServer() throws Exception {
        codexClient.initialize();
    }

    private void tryClaimGameSession() throws Exception {
        String nonce = nonce();
        if (!game.sendAgentBridgeClaimCommand(nonce)) {
            throw new IOException("Log in before using the agent.");
        }
        Exception lastError = null;
        for (int attempt = 0; attempt < 20; attempt++) {
            try {
                Thread.sleep(150L);
                JsonObject response = bridgeHttpClient.claimSession(nonce);
                if (response.has("success") && response.get("success").getAsBoolean()) {
                    pushAgentMessage("Game bridge connected for " + bridgeHttpClient.getPlayerName() + ".");
                    return;
                }
            } catch (Exception e) {
                lastError = e;
            }
        }
        throw new IOException(lastError == null ? "Unable to claim game bridge session." : cleanMessage(lastError));
    }

    private void recordTurnRequested(String command) {
        try {
            JsonObject event = new JsonObject();
            event.addProperty("command", command == null ? "" : command);
            bridgeHttpClient.recordSessionEvent("turn_requested", event);
        } catch (IOException ignored) {
        }
    }

    private String formatGoalStatus(JsonObject result) {
        if (result == null) {
            return "Goal: no response.";
        }
        if (!result.has("success") || !result.get("success").getAsBoolean()) {
            return "Goal: " + stringField(result, "message", "not available.");
        }

        JsonObject goal = objectField(result, "goal");
        JsonObject state = objectField(result, "state");
        JsonObject player = objectField(state, "player");
        JsonObject money = objectField(state, "money");

        int attack = intField(goal, "attackLevel");
        int strength = intField(goal, "strengthLevel");
        int defence = intField(goal, "defenceLevel");
        int target = intField(goal, "targetLevel");
        int actions = intField(goal, "actionsRun");
        int x = intField(player, "x");
        int y = intField(player, "y");
        int coins = intField(money, "inventoryCoins") + intField(money, "bankCoins");
        String status = stringField(goal, "status", "unknown");
        String message = stringField(result, "message", stringField(goal, "message", "observed"));
        return "Goal " + status + " A/S/D " + attack + "/" + strength + "/" + defence
                + " -> " + target + ", actions " + actions + ", coins " + coins
                + ", pos " + x + "," + y + ": " + message;
    }

    private static JsonObject objectField(JsonObject object, String name) {
        return object != null && object.has(name) && object.get(name).isJsonObject()
                ? object.getAsJsonObject(name) : new JsonObject();
    }

    private static int intField(JsonObject object, String name) {
        return object != null && object.has(name) && object.get(name).isJsonPrimitive()
                ? object.get(name).getAsInt() : 0;
    }

    private static String stringField(JsonObject object, String name, String fallback) {
        return object != null && object.has(name) && object.get(name).isJsonPrimitive()
                ? object.get(name).getAsString() : fallback;
    }

    private static int sumItemAmount(JsonObject object, String arrayName, int itemId) {
        if (object == null || !object.has(arrayName) || !object.get(arrayName).isJsonArray()) {
            return 0;
        }
        int total = 0;
        for (JsonElement element : object.getAsJsonArray(arrayName)) {
            if (!element.isJsonObject()) {
                continue;
            }
            JsonObject item = element.getAsJsonObject();
            if (intField(item, "id") == itemId) {
                total += intField(item, "amount");
            }
        }
        return total;
    }

    private String nonce() {
        byte[] data = new byte[16];
        secureRandom.nextBytes(data);
        StringBuilder builder = new StringBuilder(data.length * 2);
        for (byte b : data) {
            builder.append(String.format("%02x", b & 0xff));
        }
        return builder.toString();
    }

    private void pushAgentMessage(String text) {
        if (text == null || text.trim().isEmpty()) {
            return;
        }
        String normalized = text.replace('\n', ' ').replace('\r', ' ').trim();
        int max = 72;
        int offset = 0;
        while (offset < normalized.length()) {
            int end = Math.min(normalized.length(), offset + max);
            if (end < normalized.length()) {
                int lastSpace = normalized.lastIndexOf(' ', end);
                if (lastSpace > offset + 20) {
                    end = lastSpace;
                }
            }
            String part = normalized.substring(offset, end).trim();
            if (!part.isEmpty()) {
                game.pushMessage("[Agent] " + part, 0, "");
            }
            offset = end;
            while (offset < normalized.length() && normalized.charAt(offset) == ' ') {
                offset++;
            }
        }
    }

    private String cleanMessage(Exception e) {
        String message = e.getMessage();
        if (message == null || message.trim().isEmpty()) {
            message = e.getClass().getSimpleName();
        }
        return message;
    }
}
