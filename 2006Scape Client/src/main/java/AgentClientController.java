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
    private final AgentTerminalLog terminalLog;
    private final SecureRandom secureRandom = new SecureRandom();
    private static final Pattern COMBAT_GOAL_LEVEL_PATTERN = Pattern.compile("(?:base|level|to)\\s+(\\d{1,2})",
            Pattern.CASE_INSENSITIVE);

    private volatile boolean taskRunning;

    public AgentClientController(Game game) {
        this(game, new AgentTerminalLog());
    }

    public AgentClientController(Game game, AgentTerminalLog terminalLog) {
        this.game = game;
        this.terminalLog = terminalLog;
        this.bridgeHttpClient = new AgentBridgeHttpClient(ClientSettings.AGENT_BRIDGE_PORT);
        Consumer<String> messages = text -> { };
        this.codexClient = new CodexAppServerClient(bridgeHttpClient, messages, terminalLog, () -> taskRunning = false);
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
                terminalLog.warn("API key entry was cancelled or empty.");
                return;
            }
            executor.submit(() -> {
                try {
                    codexClient.loginWithApiKey(apiKey);
                    terminalLog.system("API key saved by Codex auth.");
                } catch (Exception e) {
                    terminalLog.error("API-key login failed: " + cleanMessage(e));
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
            terminalLog.system("Status: " + codexClient.status());
        });
    }

    private void stopAgent() {
        executor.submit(() -> {
            terminalLog.warn("Stop requested.");
            codexClient.interruptCurrentTurn();
            if (bridgeHttpClient.hasSession()) {
                try {
                    bridgeHttpClient.callTool("stop_goal", new JsonObject());
                    bridgeHttpClient.callTool("cancel_current_action", new JsonObject());
                } catch (IOException ignored) {
                }
            }
            taskRunning = false;
            terminalLog.warn("Stopped.");
        });
    }

    private void runTask(String command) {
        if (taskRunning) {
            terminalLog.warn("Already running. Use /agent stop first.");
            return;
        }
        taskRunning = true;
        terminalLog.task("Task requested: " + command);
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
                terminalLog.error(cleanMessage(e));
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
                terminalLog.success("Durable combat goal started. Keeping the client logged in while the server trains.");
                return;
            }
            terminalLog.error(result.has("message") ? result.get("message").getAsString()
                    : "Unable to start durable combat goal.");
        } catch (Exception e) {
            terminalLog.error(cleanMessage(e));
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
            terminalLog.error("Local agent bridge is not running. Start the 2006Scape server first.");
            throw new IOException("Local agent bridge is not running. Start the 2006Scape server first.");
        }
        if (!bridgeHttpClient.hasSession()) {
            tryClaimGameSession();
        }
        if (!codexClient.hasAccount() && !codexClient.refreshAccount()) {
            terminalLog.warn("Codex needs an API key. Use /agent key.");
            throw new IOException("Codex needs an API key. Use /agent key.");
        }
    }

    private void ensureAppServer() throws Exception {
        codexClient.initialize();
    }

    private void tryClaimGameSession() throws Exception {
        String nonce = nonce();
        if (!game.sendAgentBridgeClaimCommand(nonce)) {
            terminalLog.warn("Log in before using the agent.");
            throw new IOException("Log in before using the agent.");
        }
        Exception lastError = null;
        for (int attempt = 0; attempt < 20; attempt++) {
            try {
                Thread.sleep(150L);
                JsonObject response = bridgeHttpClient.claimSession(nonce);
                if (response.has("success") && response.get("success").getAsBoolean()) {
                    terminalLog.system("Game bridge connected for " + bridgeHttpClient.getPlayerName() + ".");
                    return;
                }
            } catch (Exception e) {
                lastError = e;
            }
        }
        String message = lastError == null ? "Unable to claim game bridge session." : cleanMessage(lastError);
        terminalLog.error(message);
        throw new IOException(message);
    }

    private void recordTurnRequested(String command) {
        try {
            JsonObject event = new JsonObject();
            event.addProperty("command", command == null ? "" : command);
            bridgeHttpClient.recordSessionEvent("turn_requested", event);
        } catch (IOException ignored) {
        }
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

    private String cleanMessage(Exception e) {
        String message = e.getMessage();
        if (message == null || message.trim().isEmpty()) {
            message = e.getClass().getSimpleName();
        }
        return message;
    }
}
