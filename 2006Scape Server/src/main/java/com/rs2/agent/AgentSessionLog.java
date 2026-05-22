package com.rs2.agent;

import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;
import com.rs2.Constants;
import com.rs2.game.players.Player;

public class AgentSessionLog {

    public static final AgentSessionLog INSTANCE = new AgentSessionLog();

    private static final Gson GSON = new Gson();
    private static final String LOG_DIR = "agent-sessions";
    private static final Pattern[] SENSITIVE_VALUE_PATTERNS = {
            Pattern.compile("(?i)\\bBearer\\s+[A-Za-z0-9._\\-+/=]+"),
            Pattern.compile("(?i)\\b(api[_-]?key|token|session[_-]?token|auth[_-]?token|password|secret|cookie)\\s*[:=]\\s*[^\\s,;}]+"),
            Pattern.compile("\\bsk-[A-Za-z0-9_\\-]{12,}\\b")
    };

    private final Object lock = new Object();
    private File logDirectoryForTests;

    public void sessionRegistered(AgentSession session) {
        record(session, "session_registered", null);
    }

    public void sessionClaimed(AgentSession session) {
        record(session, "session_claimed", null);
    }

    public void sessionExpired(AgentSession session, String reason) {
        JsonObject data = new JsonObject();
        data.addProperty("reason", reason);
        record(session, "session_expired", data);
    }

    public void sessionInvalidated(AgentSession session, String reason) {
        JsonObject data = new JsonObject();
        data.addProperty("reason", reason);
        record(session, "session_invalidated", data);
    }

    public void clientEvent(AgentSession session, String event, JsonObject data) {
        if (event == null || event.trim().isEmpty()) {
            return;
        }
        record(session, normalizeEvent(event), data);
    }

    public void toolCompleted(AgentSession session, String tool, JsonObject arguments, JsonObject result, long durationMs) {
        toolEvent(session, "tool_completed", tool, arguments, result, durationMs);
    }

    public void toolFailed(AgentSession session, String tool, JsonObject arguments, JsonObject result, long durationMs) {
        JsonObject safeResult = result == null ? new JsonObject() : result;
        if (!safeResult.has("success")) {
            safeResult.addProperty("success", false);
        }
        toolEvent(session, "tool_failed", tool, arguments, safeResult, durationMs);
    }

    public void toolFailed(AgentSession session, String tool, JsonObject arguments, String message, long durationMs) {
        JsonObject result = new JsonObject();
        result.addProperty("success", false);
        result.addProperty("message", message == null ? "Agent tool failed." : message);
        toolFailed(session, tool, arguments, result, durationMs);
    }

    private void toolEvent(AgentSession session, String event, String tool, JsonObject arguments, JsonObject result, long durationMs) {
        JsonObject data = new JsonObject();
        data.addProperty("tool", tool == null ? "" : tool);
        data.addProperty("durationMs", durationMs);
        data.add("arguments", sanitize(arguments == null ? new JsonObject() : arguments));
        data.add("result", sanitize(result == null ? new JsonObject() : result));
        record(session, event, data);
    }

    void setLogDirectoryForTests(File directory) {
        synchronized (lock) {
            logDirectoryForTests = directory;
        }
    }

    void resetLogDirectoryForTests() {
        synchronized (lock) {
            logDirectoryForTests = null;
        }
    }

    private void record(AgentSession session, String event, JsonObject data) {
        if (session == null || session.getSessionId() == null || session.getSessionId().trim().isEmpty()) {
            return;
        }
        long now = System.currentTimeMillis();
        JsonObject entry = new JsonObject();
        entry.addProperty("schemaVersion", 1);
        entry.addProperty("timestamp", timestamp(now));
        entry.addProperty("timestampMs", now);
        entry.addProperty("event", event);
        entry.addProperty("sessionId", session.getSessionId());
        entry.addProperty("playerId", session.getPlayerId());
        entry.addProperty("playerName", session.getPlayerName());
        Player player = session.getPlayer();
        if (player != null) {
            entry.add("player", playerState(player));
        }
        if (data != null) {
            entry.add("data", sanitize(data));
        }
        write(session, now, entry);
    }

    private void write(AgentSession session, long now, JsonObject entry) {
        synchronized (lock) {
            File dayDirectory = new File(resolveLogDirectory(), dateStamp(now));
            if (!dayDirectory.exists() && !dayDirectory.mkdirs()) {
                System.err.println("Unable to create agent session log directory: " + dayDirectory.getAbsolutePath());
                return;
            }
            File logFile = new File(dayDirectory, session.getSessionId() + ".jsonl");
            try (BufferedWriter writer = Files.newBufferedWriter(logFile.toPath(), StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND)) {
                writer.write(GSON.toJson(entry));
                writer.newLine();
            } catch (IOException e) {
                System.err.println("Unable to write agent session log: " + e.getMessage());
                return;
            }
            File summaryFile = new File(dayDirectory, session.getSessionId() + ".md");
            try {
                writeMarkdownSummary(session, now, logFile, summaryFile);
            } catch (IOException e) {
                System.err.println("Unable to write agent session summary: " + e.getMessage());
            }
            AgentProfileMemory.INSTANCE.record(resolveLogDirectory(), entry);
        }
    }

    private File resolveLogDirectory() {
        if (logDirectoryForTests != null) {
            return logDirectoryForTests;
        }
        File defaultDirectory = new File(Constants.SERVER_LOG_DIR, LOG_DIR);
        File defaultParent = defaultDirectory.getParentFile();
        if (defaultParent == null || defaultParent.exists() || new File("data").isDirectory()) {
            return defaultDirectory;
        }
        File repoServerLogs = new File("2006Scape Server/data/logs");
        if (repoServerLogs.isDirectory()) {
            return new File(repoServerLogs, LOG_DIR);
        }
        return defaultDirectory;
    }

    private JsonObject playerState(Player player) {
        JsonObject state = new JsonObject();
        state.addProperty("x", player.absX);
        state.addProperty("y", player.absY);
        state.addProperty("height", player.heightLevel);
        state.addProperty("isDead", player.isDead);
        state.addProperty("disconnected", player.disconnected);
        return state;
    }

    private void writeMarkdownSummary(AgentSession session, long now, File logFile, File summaryFile) throws IOException {
        Summary summary = loadSummary(session, logFile);
        String markdown = renderMarkdown(summary, now);
        Files.write(summaryFile.toPath(), markdown.getBytes(StandardCharsets.UTF_8),
                StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
    }

    private Summary loadSummary(AgentSession session, File logFile) throws IOException {
        Summary summary = new Summary(session.getSessionId());
        if (!logFile.exists()) {
            return summary;
        }
        List<String> lines = Files.readAllLines(logFile.toPath(), StandardCharsets.UTF_8);
        for (String line : lines) {
            if (line == null || line.trim().isEmpty()) {
                continue;
            }
            try {
                JsonObject entry = new JsonParser().parse(line).getAsJsonObject();
                summary.consume(entry);
            } catch (Exception ignored) {
            }
        }
        return summary;
    }

    private String renderMarkdown(Summary summary, long now) {
        StringBuilder builder = new StringBuilder();
        builder.append("# Agent Session ").append(summary.sessionId).append("\n\n");
        builder.append("- Player: ").append(summary.playerName == null ? "unknown" : summary.playerName)
                .append(" (id ").append(summary.playerId).append(")\n");
        builder.append("- Started: ").append(summary.startedAt == null ? "unknown" : summary.startedAt).append("\n");
        builder.append("- Last updated: ").append(summary.lastUpdatedAt == null ? timestamp(now) : summary.lastUpdatedAt).append("\n\n");

        builder.append("## Task / User Goal\n\n");
        builder.append(summary.task == null ? "No task recorded yet." : summary.task).append("\n\n");

        builder.append("## What Was Built / Done\n\n");
        appendBullets(builder, summary.actions, "No completed agent actions recorded yet.");

        builder.append("## Obstacles Encountered\n\n");
        appendBullets(builder, summary.obstacles, "No obstacles recorded yet.");

        builder.append("## Solution / Result\n\n");
        builder.append(summary.solution()).append("\n\n");

        builder.append("## Logical Next Step\n\n");
        builder.append(summary.nextStep()).append("\n\n");

        builder.append("## Observable Decision Trail\n\n");
        appendBullets(builder, summary.decisionTrail, "No observable decision trail recorded yet.");

        builder.append("## In-Game Failures / Blockers\n\n");
        appendBullets(builder, summary.blockers, "No in-game failures or blockers recorded yet.");

        builder.append("## Harness Reflection\n\n");
        builder.append(summary.reflection()).append("\n\n");

        builder.append("## Learning Over Time\n\n");
        builder.append(summary.learning()).append("\n\n");

        builder.append("## Timeline\n\n");
        appendBullets(builder, summary.timeline, "No timeline events recorded yet.");
        return builder.toString();
    }

    private void appendBullets(StringBuilder builder, List<String> values, String fallback) {
        if (values.isEmpty()) {
            builder.append("- ").append(fallback).append("\n\n");
            return;
        }
        for (String value : values) {
            builder.append("- ").append(value).append("\n");
        }
        builder.append("\n");
    }

    private JsonElement sanitize(JsonElement element) {
        if (element == null || element.isJsonNull()) {
            return JsonNull.INSTANCE;
        }
        if (element.isJsonPrimitive()) {
            JsonPrimitive primitive = element.getAsJsonPrimitive();
            if (primitive.isBoolean()) {
                return new JsonPrimitive(primitive.getAsBoolean());
            }
            if (primitive.isNumber()) {
                return new JsonPrimitive(primitive.getAsNumber());
            }
            return new JsonPrimitive(redactSensitiveValue(primitive.getAsString()));
        }
        if (element.isJsonArray()) {
            JsonArray copy = new JsonArray();
            for (JsonElement child : element.getAsJsonArray()) {
                copy.add(sanitize(child));
            }
            return copy;
        }
        JsonObject copy = new JsonObject();
        for (Map.Entry<String, JsonElement> entry : element.getAsJsonObject().entrySet()) {
            if (isSensitiveKey(entry.getKey())) {
                copy.addProperty(entry.getKey(), "[redacted]");
            } else {
                copy.add(entry.getKey(), sanitize(entry.getValue()));
            }
        }
        return copy;
    }

    private boolean isSensitiveKey(String key) {
        String lower = key == null ? "" : key.toLowerCase(Locale.ENGLISH);
        return lower.contains("token")
                || lower.contains("password")
                || lower.contains("secret")
                || lower.contains("cookie")
                || lower.equals("key")
                || lower.endsWith("key")
                || lower.contains("_key")
                || lower.contains("-key")
                || lower.contains("apikey")
                || lower.contains("api_key");
    }

    private String redactSensitiveValue(String value) {
        if (value == null || value.isEmpty()) {
            return value;
        }
        String redacted = value;
        for (Pattern pattern : SENSITIVE_VALUE_PATTERNS) {
            Matcher matcher = pattern.matcher(redacted);
            redacted = matcher.replaceAll("[redacted]");
        }
        return redacted;
    }

    private String normalizeEvent(String event) {
        String normalized = event.trim().toLowerCase(Locale.ENGLISH).replaceAll("[^a-z0-9_\\-\\.]", "_");
        return normalized.length() > 80 ? normalized.substring(0, 80) : normalized;
    }

    private String timestamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    private String dateStamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ENGLISH);
        return format.format(new Date(now));
    }

    private static class Summary {
        private final String sessionId;
        private final List<String> actions = new ArrayList<String>();
        private final List<String> obstacles = new ArrayList<String>();
        private final List<String> blockers = new ArrayList<String>();
        private final List<String> decisionTrail = new ArrayList<String>();
        private final List<String> timeline = new ArrayList<String>();
        private String playerName;
        private int playerId = -1;
        private String startedAt;
        private String lastUpdatedAt;
        private String task;
        private String latestSuccess;
        private String latestAssistantMessage;
        private String latestObstacle;
        private String latestTool;
        private boolean turnCompleted;
        private boolean turnInterrupted;

        private Summary(String sessionId) {
            this.sessionId = sessionId;
        }

        private void consume(JsonObject entry) {
            String event = string(entry, "event", "");
            String time = string(entry, "timestamp", "");
            if (startedAt == null && !time.isEmpty()) {
                startedAt = time;
            }
            if (!time.isEmpty()) {
                lastUpdatedAt = time;
            }
            playerName = string(entry, "playerName", playerName);
            playerId = integer(entry, "playerId", playerId);

            JsonObject data = entry.has("data") && entry.get("data").isJsonObject()
                    ? entry.get("data").getAsJsonObject()
                    : new JsonObject();
            if ("session_registered".equals(event)) {
                timeline.add(label(time, "Session registered."));
            } else if ("session_claimed".equals(event)) {
                timeline.add(label(time, "Session claimed by local client."));
            } else if ("turn_requested".equals(event)) {
                task = string(data, "command", task);
                decisionTrail.add("The user goal was captured as `" + fallback(task, "unknown task") + "`, so the harness had a concrete task to anchor the turn.");
                timeline.add(label(time, "Task requested: " + fallback(task, "unknown task") + "."));
            } else if ("turn_started".equals(event)) {
                task = string(data, "command", task);
                turnCompleted = false;
                turnInterrupted = false;
                decisionTrail.add("Codex started a read-only turn connected to the claimed player session.");
                timeline.add(label(time, "Codex turn started."));
            } else if ("assistant_message".equals(event)) {
                latestAssistantMessage = string(data, "text", latestAssistantMessage);
                if (latestAssistantMessage != null && !latestAssistantMessage.trim().isEmpty()) {
                    decisionTrail.add("The assistant interpreted the tool evidence as: " + compact(latestAssistantMessage, 220));
                }
                timeline.add(label(time, "Assistant reported: " + compact(latestAssistantMessage, 180)));
            } else if ("turn_completed".equals(event)) {
                turnCompleted = true;
                decisionTrail.add("The turn reached a normal completion event.");
                timeline.add(label(time, "Turn completed."));
            } else if ("turn_interrupted".equals(event)) {
                turnInterrupted = true;
                addObstacle("Turn was interrupted before completion.");
                timeline.add(label(time, "Turn interrupted."));
            } else if ("session_expired".equals(event) || "session_invalidated".equals(event)) {
                addObstacle("Session ended: " + string(data, "reason", "unknown reason") + ".");
                timeline.add(label(time, "Session ended."));
            } else if ("goal_started".equals(event)) {
                String detail = goalDetail(data, "Started durable goal");
                latestSuccess = detail;
                actions.add(detail);
                decisionTrail.add("A durable goal was started so normal gameplay could continue outside a single Codex turn.");
                timeline.add(label(time, detail));
            } else if ("goal_progress".equals(event)) {
                String detail = goalDetail(data, "Durable goal progressed");
                latestSuccess = detail;
                decisionTrail.add("Goal progress showed the server-side loop was still making normal gameplay attempts.");
                timeline.add(label(time, detail));
            } else if ("goal_completed".equals(event)) {
                String detail = goalDetail(data, "Durable goal completed");
                latestSuccess = detail;
                actions.add(detail);
                decisionTrail.add("The durable goal met its target and reported completion from server state.");
                timeline.add(label(time, detail));
            } else if ("goal_blocked".equals(event) || "goal_stopped".equals(event)) {
                String detail = goalDetail(data, "Durable goal stopped");
                addObstacle(detail);
                timeline.add(label(time, detail));
            } else if ("tool_completed".equals(event) || "tool_failed".equals(event)) {
                consumeTool(time, event, data);
            } else {
                timeline.add(label(time, "Recorded event: " + event + "."));
            }
        }

        private String goalDetail(JsonObject data, String fallback) {
            JsonObject goal = data.has("goal") && data.get("goal").isJsonObject()
                    ? data.get("goal").getAsJsonObject()
                    : new JsonObject();
            String message = string(goal, "message", fallback);
            int target = integer(goal, "targetLevel", 0);
            int attack = integer(goal, "attackLevel", 0);
            int strength = integer(goal, "strengthLevel", 0);
            int defence = integer(goal, "defenceLevel", 0);
            int actions = integer(goal, "actionsRun", 0);
            int bankTrips = integer(goal, "bankTrips", 0);
            int bankedItems = integer(goal, "bankedSupplyItems", 0);
            int lootedItems = integer(goal, "lootedSupplyItems", 0);
            int bankedAccountItems = integer(goal, "bankedAccountItems", 0);
            int foodBankTrips = integer(goal, "foodBankTrips", 0);
            int withdrawnFoodItems = integer(goal, "withdrawnFoodItems", 0);
            int gearItemsBought = integer(goal, "gearItemsBought", 0);
            int gearItemsEquipped = integer(goal, "gearItemsEquipped", 0);
            int gearSuppliesSold = integer(goal, "gearSuppliesSold", 0);
            int gearCoinsEarned = integer(goal, "gearCoinsEarned", 0);
            int gearCoinsSpent = integer(goal, "gearCoinsSpent", 0);
            int gearMoneyItemsSold = integer(goal, "gearMoneyItemsSold", 0);
            int gearMoneyCoinsEarned = integer(goal, "gearMoneyCoinsEarned", 0);
            return compact(message + " A/S/D " + attack + "/" + strength + "/" + defence
                    + (target > 0 ? " toward " + target : "") + " after " + actions + " goal actions"
                    + (lootedItems > 0 ? "; looted " + lootedItems + " supplies" : "")
                    + (bankTrips > 0 ? "; banked " + bankedItems + " supplies across " + bankTrips + " trips" : "")
                    + (bankedAccountItems > 0 ? "; stored " + bankedAccountItems + " starter/account items" : "")
                    + (withdrawnFoodItems > 0 ? "; withdrew " + withdrawnFoodItems + " food across " + foodBankTrips + " trips" : "")
                    + (gearSuppliesSold > 0 ? "; sold " + gearSuppliesSold + " surplus supplies for " + gearCoinsEarned + " coins" : "")
                    + (gearMoneyItemsSold > 0 ? "; sold " + gearMoneyItemsSold + " mined money items for " + gearMoneyCoinsEarned + " coins" : "")
                    + (gearItemsBought > 0 ? "; bought " + gearItemsBought + " gear item(s) for " + gearCoinsSpent + " coins" : "")
                    + (gearItemsEquipped > 0 ? "; equipped " + gearItemsEquipped + " gear upgrade(s)" : "")
                    + ".", 240);
        }

        private void consumeTool(String time, String event, JsonObject data) {
            String tool = string(data, "tool", "unknown_tool");
            long durationMs = longValue(data, "durationMs", 0L);
            JsonObject result = data.has("result") && data.get("result").isJsonObject()
                    ? data.get("result").getAsJsonObject()
                    : new JsonObject();
            boolean success = "tool_completed".equals(event) && bool(result, "success", false);
            String message = string(result, "message", success ? "completed" : "failed");
            String detail = "`rs." + tool + "` - " + compact(message, 220) + " (" + durationMs + "ms).";
            latestTool = "`rs." + tool + "`";
            if (success) {
                latestSuccess = detail;
                actions.add(detail);
                decisionTrail.add("`rs." + tool + "` succeeded, so the agent could build on that observation/action result.");
                timeline.add(label(time, "`rs." + tool + "` succeeded."));
            } else {
                addObstacle("`rs." + tool + "` failed: " + compact(message, 220) + ".");
                addBlocker(tool, message);
                decisionTrail.add("`rs." + tool + "` returned a blocker, shifting the next step toward recovery or a clearer report.");
                timeline.add(label(time, "`rs." + tool + "` failed."));
            }
        }

        private void addObstacle(String obstacle) {
            latestObstacle = obstacle;
            obstacles.add(obstacle);
            if (isInGameBlocker(obstacle)) {
                blockers.add(obstacle);
            }
        }

        private void addBlocker(String tool, String message) {
            String category = blockerCategory(message);
            blockers.add(category + ": `rs." + tool + "` reported " + compact(message, 220) + ".");
        }

        private String solution() {
            if (latestAssistantMessage != null && !latestAssistantMessage.trim().isEmpty()) {
                return "Latest assistant result: " + compact(latestAssistantMessage, 600);
            }
            if (latestSuccess != null) {
                return "Latest successful action: " + latestSuccess;
            }
            return "No solution recorded yet.";
        }

        private String nextStep() {
            if (turnInterrupted) {
                return "Start a new `/agent ...` task or rerun the interrupted command when ready.";
            }
            if (latestObstacle != null && !turnCompleted) {
                return "Resolve the latest blocker: " + latestObstacle;
            }
            if (turnCompleted) {
                return "Review the in-game result and decide whether a follow-up `/agent ...` task is needed.";
            }
            if (task != null && !task.trim().isEmpty()) {
                return "Continue monitoring this active task until it completes or reports a blocker.";
            }
            return "Start an `/agent <task>` command.";
        }

        private String reflection() {
            if (latestObstacle != null) {
                return "The harness had enough evidence to name a concrete blocker, which is useful friction rather than a silent failure.";
            }
            if (latestTool != null && latestSuccess != null) {
                return "The session appears steady: tool feedback was recorded and the latest successful result gave the agent something concrete to trust.";
            }
            return "The session is still sparse; more tool events are needed before the harness can say much about confidence or friction.";
        }

        private String learning() {
            if (!blockers.isEmpty()) {
                return "Repeated blocker categories should feed future tool design: make missing requirements, inventory pressure, interfaces, reachability, and death states easier to detect before acting.";
            }
            if (!actions.isEmpty()) {
                return "Successful tool/action pairs are accumulating into reusable patterns for normal gameplay loops.";
            }
            return "No repeated pattern is visible yet.";
        }

        private static String blockerCategory(String message) {
            String lower = message == null ? "" : message.toLowerCase(Locale.ENGLISH);
            if (lower.contains("dead") || lower.contains("death")) {
                return "player death";
            }
            if (lower.contains("offline") || lower.contains("disconnected") || lower.contains("session")) {
                return "invalid or expired session";
            }
            if (lower.contains("inventory") || lower.contains("space") || lower.contains("full")) {
                return "inventory space";
            }
            if (lower.contains("required") || lower.contains("requires") || lower.contains("need ") || lower.contains("missing")) {
                return "missing requirement or equipment";
            }
            if (lower.contains("level")) {
                return "skill requirement";
            }
            if (lower.contains("nearby") || lower.contains("found") || lower.contains("reachable") || lower.contains("reach")) {
                return "unreachable or unavailable target";
            }
            if (lower.contains("shop") || lower.contains("bank") || lower.contains("dialogue") || lower.contains("interface") || lower.contains("window")) {
                return "closed or wrong interface";
            }
            if (lower.contains("cannot act") || lower.contains("online")) {
                return "player state";
            }
            return "gameplay blocker";
        }

        private static boolean isInGameBlocker(String message) {
            String category = blockerCategory(message);
            return !"gameplay blocker".equals(category) || (message != null && !message.trim().isEmpty());
        }

        private static String string(JsonObject object, String name, String fallback) {
            if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
                return clean(object.get(name).getAsString());
            }
            return fallback;
        }

        private static int integer(JsonObject object, String name, int fallback) {
            if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
                try {
                    return object.get(name).getAsInt();
                } catch (NumberFormatException ignored) {
                }
            }
            return fallback;
        }

        private static long longValue(JsonObject object, String name, long fallback) {
            if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
                try {
                    return object.get(name).getAsLong();
                } catch (NumberFormatException ignored) {
                }
            }
            return fallback;
        }

        private static boolean bool(JsonObject object, String name, boolean fallback) {
            if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
                return object.get(name).getAsBoolean();
            }
            return fallback;
        }

        private static String label(String time, String text) {
            return (time == null || time.isEmpty() ? "unknown time" : time) + " - " + text;
        }

        private static String fallback(String value, String fallback) {
            return value == null || value.trim().isEmpty() ? fallback : value;
        }

        private static String compact(String value, int maxLength) {
            String cleaned = clean(value);
            if (cleaned.length() <= maxLength) {
                return cleaned;
            }
            return cleaned.substring(0, Math.max(0, maxLength - 3)) + "...";
        }

        private static String clean(String value) {
            return value == null ? "" : value.replace('\r', ' ').replace('\n', ' ').trim();
        }
    }
}
