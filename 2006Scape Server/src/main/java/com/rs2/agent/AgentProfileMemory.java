package com.rs2.agent;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.rs2.Constants;

public class AgentProfileMemory {

    public static final AgentProfileMemory INSTANCE = new AgentProfileMemory();

    private static final Gson GSON = new Gson();
    private static final String PROFILE_DIR = "profiles";
    private static final String MEMORY_FILE = "agent-personality.md";
    private static final String STATE_FILE = "agent-personality-state.json";

    private final Object lock = new Object();

    public void record(File agentSessionLogDirectory, JsonObject entry) {
        if (agentSessionLogDirectory == null || entry == null) {
            return;
        }
        String playerName = string(entry, "playerName", "");
        if (playerName.isEmpty()) {
            return;
        }
        synchronized (lock) {
            try {
                File profileDirectory = profileDirectory(agentSessionLogDirectory, playerName);
                if (!profileDirectory.exists() && !profileDirectory.mkdirs()) {
                    System.err.println("Unable to create agent profile memory directory: " + profileDirectory.getAbsolutePath());
                    return;
                }
                ProfileState state = loadState(profileDirectory);
                state.playerName = playerName;
                state.lastUpdated = string(entry, "timestamp", iso(System.currentTimeMillis()));
                state.consume(entry);
                state.normalizeSelfTalkLog();
                writeState(profileDirectory, state);
                writeMarkdown(profileDirectory, state);
            } catch (IOException e) {
                System.err.println("Unable to update agent profile memory: " + e.getMessage());
            }
        }
    }

    public JsonObject readForPlayer(File agentSessionLogDirectory, String playerName) {
        JsonObject memory = new JsonObject();
        if (agentSessionLogDirectory == null || playerName == null || playerName.trim().isEmpty()) {
            return memory;
        }
        synchronized (lock) {
            File profileDirectory = profileDirectory(agentSessionLogDirectory, playerName);
            ProfileState state = loadState(profileDirectory);
            if (state == null || state.playerName == null || state.playerName.trim().isEmpty()) {
                return memory;
            }
            memory.addProperty("playerName", state.playerName);
            memory.addProperty("lastUpdated", state.lastUpdated == null ? "" : state.lastUpdated);
            memory.add("beliefs", beliefs(state));
            memory.add("personalityDrift", personality(state));
            memory.add("selfFormedGoals", goals(state));
            memory.add("selfTalkLog", selfTalk(state));
            memory.addProperty("artifactPath", new File(profileDirectory, MEMORY_FILE).getPath());
            return memory;
        }
    }

    public JsonObject readForPlayer(String playerName) {
        return readForPlayer(defaultLogDirectory(), playerName);
    }

    public int rebuildFromLogs(File agentSessionLogDirectory) throws IOException {
        if (agentSessionLogDirectory == null || !agentSessionLogDirectory.exists()) {
            return 0;
        }
        Map<String, ProfileState> states = new LinkedHashMap<String, ProfileState>();
        List<File> files = new ArrayList<File>();
        collectJsonlFiles(agentSessionLogDirectory, files);
        Collections.sort(files);
        for (File file : files) {
            List<String> lines = Files.readAllLines(file.toPath(), StandardCharsets.UTF_8);
            for (String line : lines) {
                if (line == null || line.trim().isEmpty()) {
                    continue;
                }
                try {
                    JsonObject entry = new JsonParser().parse(line).getAsJsonObject();
                    String playerName = string(entry, "playerName", "");
                    if (playerName.isEmpty()) {
                        continue;
                    }
                    String key = safeProfileName(playerName);
                    ProfileState state = states.get(key);
                    if (state == null) {
                        state = new ProfileState();
                        state.playerName = playerName;
                        states.put(key, state);
                    }
                    state.lastUpdated = string(entry, "timestamp", state.lastUpdated);
                    state.consume(entry);
                } catch (Exception ignored) {
                }
            }
        }
        for (Map.Entry<String, ProfileState> entry : states.entrySet()) {
            File profileDirectory = new File(new File(agentSessionLogDirectory, PROFILE_DIR), entry.getKey());
            if (!profileDirectory.exists() && !profileDirectory.mkdirs()) {
                throw new IOException("Unable to create profile memory directory: " + profileDirectory.getAbsolutePath());
            }
            entry.getValue().normalizeSelfTalkLog();
            writeState(profileDirectory, entry.getValue());
            writeMarkdown(profileDirectory, entry.getValue());
        }
        return states.size();
    }

    public File personalityFile(File agentSessionLogDirectory, String playerName) {
        return new File(profileDirectory(agentSessionLogDirectory, playerName), MEMORY_FILE);
    }

    private File defaultLogDirectory() {
        File defaultDirectory = new File(Constants.SERVER_LOG_DIR, "agent-sessions");
        File defaultParent = defaultDirectory.getParentFile();
        if (defaultParent == null || defaultParent.exists() || new File("data").isDirectory()) {
            return defaultDirectory;
        }
        File repoServerLogs = new File("2006Scape Server/data/logs");
        if (repoServerLogs.isDirectory()) {
            return new File(repoServerLogs, "agent-sessions");
        }
        return defaultDirectory;
    }

    private void collectJsonlFiles(File directory, List<File> files) {
        File[] children = directory.listFiles();
        if (children == null) {
            return;
        }
        for (File child : children) {
            if (child.isDirectory()) {
                if (!"reports".equals(child.getName()) && !PROFILE_DIR.equals(child.getName())) {
                    collectJsonlFiles(child, files);
                }
            } else if (child.getName().endsWith(".jsonl")) {
                files.add(child);
            }
        }
    }

    private ProfileState loadState(File profileDirectory) {
        File stateFile = new File(profileDirectory, STATE_FILE);
        if (!stateFile.exists()) {
            return new ProfileState();
        }
        try {
            String json = new String(Files.readAllBytes(stateFile.toPath()), StandardCharsets.UTF_8);
            ProfileState state = GSON.fromJson(json, ProfileState.class);
            return state == null ? new ProfileState() : state;
        } catch (Exception ignored) {
            return new ProfileState();
        }
    }

    private void writeState(File profileDirectory, ProfileState state) throws IOException {
        File stateFile = new File(profileDirectory, STATE_FILE);
        Files.write(stateFile.toPath(), GSON.toJson(state).getBytes(StandardCharsets.UTF_8),
                StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
    }

    private void writeMarkdown(File profileDirectory, ProfileState state) throws IOException {
        File memoryFile = new File(profileDirectory, MEMORY_FILE);
        String markdown = renderMarkdown(state);
        Files.write(memoryFile.toPath(), markdown.getBytes(StandardCharsets.UTF_8),
                StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
    }

    private String renderMarkdown(ProfileState state) {
        StringBuilder builder = new StringBuilder();
        builder.append("# Agent Profile Memory - ").append(state.playerName == null ? "unknown" : state.playerName).append("\n\n");
        builder.append("- Last updated: ").append(state.lastUpdated == null ? "unknown" : state.lastUpdated).append("\n");
        builder.append("- Sessions noticed: ").append(state.sessionsRegistered).append("\n");
        builder.append("- Tool successes: ").append(state.toolSuccesses).append("\n");
        builder.append("- Tool failures/blockers: ").append(state.toolFailures).append("\n\n");

        builder.append("## Operational Memory\n\n");
        appendBullets(builder, beliefs(state));

        builder.append("## Behavior Bias\n\n");
        appendBullets(builder, personality(state));

        builder.append("## Suggested Priorities\n\n");
        appendBullets(builder, goals(state));

        builder.append("## Recent Notes\n\n");
        appendBullets(builder, selfTalk(state));

        builder.append("## Pattern Counters\n\n");
        builder.append("- Death observations: ").append(state.deaths).append("\n");
        builder.append("- Death/risk mentions: ").append(state.deathMentions).append("\n");
        builder.append("- Banking/inventory pressure: ").append(state.inventoryPressure + state.bankMentions).append("\n");
        builder.append("- Food/restock evidence: ").append(state.foodMentions).append("\n");
        builder.append("- Varrock evidence: ").append(state.varrockMentions).append("\n");
        builder.append("- Lumbridge/cow routine evidence: ").append(state.lumbridgeMentions + state.cowMentions).append("\n");
        builder.append("- Pathing/reachability friction: ").append(state.pathingFailures).append("\n");
        builder.append("- Gear/coin pressure: ").append(state.gearMentions + state.coinMentions).append("\n");
        return builder.toString();
    }

    private void appendBullets(StringBuilder builder, com.google.gson.JsonArray values) {
        if (values.size() == 0) {
            builder.append("- No repeated operational pattern recorded yet.\n\n");
            return;
        }
        for (int i = 0; i < values.size(); i++) {
            builder.append("- ").append(values.get(i).getAsString()).append("\n");
        }
        builder.append("\n");
    }

    private com.google.gson.JsonArray beliefs(ProfileState state) {
        com.google.gson.JsonArray values = new com.google.gson.JsonArray();
        if (state.cowMentions + state.lumbridgeMentions >= 2) {
            values.add("Lumbridge is a familiar fallback area for early combat, supplies, and recovery.");
        }
        if (state.cowMentions >= 2) {
            values.add("Lumbridge cow combat is a known early-training routine; keep food, inventory, and retreat thresholds checked.");
        }
        if (state.inventoryPressure >= 2 || state.bankMentions >= 4) {
            values.add("Inventory pressure recurs before banking is handled.");
        }
        if (state.varrockMentions > 0 && (state.toolFailures > 0 || state.gearMentions > 0 || state.coinMentions > 0)) {
            values.add("Varrock trips are useful but should start with food, coins, gear, and a clear route.");
        }
        if (state.foodMentions >= 2 || state.hasDeathExperience()) {
            values.add("Food is a required preparation item for longer trips or retrying dangerous areas.");
        }
        if (state.pathingFailures >= 2) {
            values.add("Unclear routes need reachability checks before committing to repeated movement.");
        }
        return values;
    }

    private com.google.gson.JsonArray personality(ProfileState state) {
        com.google.gson.JsonArray values = new com.google.gson.JsonArray();
        if (state.hasDeathExperience()) {
            values.add("Risk posture: check hitpoints, food, escape routes, and nearby threats before pushing deeper.");
        }
        if (state.goalCompleted > 0 || state.levelProgressMentions > 0) {
            values.add("Progress posture: keep using steady routines after verified level or goal progress.");
        }
        if (state.pathingFailures > 0) {
            values.add("Pathing posture: prefer known landmarks and explicit reachability checks.");
        }
        if (state.varrockMentions > 0) {
            values.add("Expansion posture: prepare before leaving the safer Lumbridge area for Varrock.");
        }
        if (state.lumbridgeMentions + state.cowMentions >= 3) {
            values.add("Fallback posture: use Lumbridge routines to recover from failed or unsafe plans.");
        }
        return values;
    }

    private com.google.gson.JsonArray goals(ProfileState state) {
        com.google.gson.JsonArray values = new com.google.gson.JsonArray();
        if (state.hasDeathExperience()) {
            values.add("Retry dangerous targets only after preparing food, gear, and an exit route.");
        }
        if (state.inventoryPressure >= 2 || state.bankMentions >= 3) {
            values.add("Use a reliable banking route before long gathering or combat loops.");
        }
        if (state.gearMentions > 0 || state.coinMentions > 1) {
            values.add("Keep enough coins for food and gear upgrades without selling useful banked supplies unnecessarily.");
        }
        if (state.varrockMentions > 0 && (state.foodMentions > 0 || state.toolFailures > 0)) {
            values.add("Restock before leaving Lumbridge for Varrock.");
        }
        if (state.pathingFailures > 0) {
            values.add("Choose routes and targets that can be verified before acting.");
        }
        return values;
    }

    private com.google.gson.JsonArray selfTalk(ProfileState state) {
        com.google.gson.JsonArray values = new com.google.gson.JsonArray();
        if (state.selfTalkLog != null) {
            for (String note : state.selfTalkLog) {
                String normalized = normalizeReflection(note);
                if (!normalized.isEmpty()) {
                    values.add(normalized);
                }
            }
        }
        if (values.size() == 0) {
            if (state.goalCompleted > 0 || state.levelProgressMentions > 0) {
                values.add("Progress note: keep using the routine that produced verified progress.");
            }
            if (state.toolFailures > 0 || state.pathingFailures > 0) {
                values.add("Route note: failed movement should trigger a fresh observation and reachability check.");
            }
            if (state.hasDeathExperience()) {
                values.add("Risk note: deaths require better food, gear, and an exit path before retrying.");
            }
        }
        return values;
    }

    private static String normalizeReflection(String note) {
        if (note == null) {
            return "";
        }
        String trimmed = note.trim();
        if (trimmed.isEmpty()) {
            return "";
        }
        String lower = trimmed.toLowerCase(Locale.ENGLISH);
        if (lower.contains("full pack") || lower.contains("inventory")) {
            return "Inventory note: bank or drop low-value items before long loops.";
        }
        if (lower.contains("bank")) {
            return "Banking note: consolidate loot and supplies before leaving a safe area.";
        }
        if (lower.contains("death") || lower.contains("dead") || lower.contains("killed") || lower.contains("grave")
                || lower.startsWith("risk note:")) {
            return "Risk note: deaths require better food, gear, and an exit path before retrying.";
        }
        if (lower.contains("food") || lower.contains("fish") || lower.contains("cook") || lower.contains("eat")) {
            return "Food note: carry enough healing before travel, combat, or retries.";
        }
        if (lower.contains("varrock")) {
            return "Varrock note: restock before using Varrock shops, mines, or routes.";
        }
        if (lower.contains("lumbridge")) {
            return "Lumbridge note: use Lumbridge as a safe fallback for early supplies and training.";
        }
        if (lower.contains("cow")) {
            return "Training note: Lumbridge cows are a repeatable early combat target; monitor food and inventory.";
        }
        if (lower.contains("goblin")) {
            return "Combat note: check hitpoints and food even for low-level targets.";
        }
        if (lower.contains("path") || lower.contains("route") || lower.contains("reach")
                || lower.contains("road") || lower.contains("movement")) {
            return "Route note: verify reachability before repeating failed movement.";
        }
        if (lower.contains("gear") || lower.contains("armor") || lower.contains("armour")
                || lower.contains("weapon") || lower.contains("hammer") || lower.contains("smith")) {
            return "Gear note: check equipment before riskier combat or production loops.";
        }
        if (lower.contains("coin") || lower.contains("money")) {
            return "Coin note: preserve budget for food, gear, and travel costs.";
        }
        if (lower.contains("progress") || lower.contains("level")) {
            return "Progress note: keep using routines that produce verified progress.";
        }
        if (lower.startsWith("note to self:")) {
            return "";
        }
        return trimmed;
    }

    private File profileDirectory(File agentSessionLogDirectory, String playerName) {
        return new File(new File(agentSessionLogDirectory, PROFILE_DIR), safeProfileName(playerName));
    }

    private String safeProfileName(String playerName) {
        String safe = playerName == null ? "unknown" : playerName.trim().toLowerCase(Locale.ENGLISH)
                .replaceAll("[^a-z0-9._-]+", "-");
        if (safe.isEmpty()) {
            return "unknown";
        }
        return safe.length() > 64 ? safe.substring(0, 64) : safe;
    }

    private static String string(JsonObject object, String name, String fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            String value = object.get(name).getAsString();
            return value == null ? fallback : value.trim();
        }
        return fallback;
    }

    private static boolean bool(JsonObject object, String name, boolean fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            return object.get(name).getAsBoolean();
        }
        return fallback;
    }

    private static String iso(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    private static class ProfileState {
        private String playerName;
        private String lastUpdated;
        private int sessionsRegistered;
        private int sessionsClaimed;
        private int sessionsEnded;
        private int toolSuccesses;
        private int toolFailures;
        private int deaths;
        private int deathMentions;
        private int inventoryPressure;
        private int bankMentions;
        private int foodMentions;
        private int varrockMentions;
        private int lumbridgeMentions;
        private int cowMentions;
        private int pathingFailures;
        private int gearMentions;
        private int coinMentions;
        private int goalStarted;
        private int goalProgress;
        private int goalCompleted;
        private int levelProgressMentions;
        private List<String> selfTalkLog = new ArrayList<String>();

        private void consume(JsonObject entry) {
            String event = string(entry, "event", "");
            JsonObject data = entry.has("data") && entry.get("data").isJsonObject()
                    ? entry.get("data").getAsJsonObject()
                    : new JsonObject();
            JsonObject player = entry.has("player") && entry.get("player").isJsonObject()
                    ? entry.get("player").getAsJsonObject()
                    : new JsonObject();
            if (bool(player, "isDead", false)) {
                deaths++;
            }
            if ("session_registered".equals(event)) {
                sessionsRegistered++;
            } else if ("session_claimed".equals(event)) {
                sessionsClaimed++;
            } else if ("session_expired".equals(event) || "session_invalidated".equals(event)) {
                sessionsEnded++;
                observeText(string(data, "reason", ""));
            } else if ("tool_completed".equals(event) || "tool_failed".equals(event)) {
                if ("tool_completed".equals(event)) {
                    toolSuccesses++;
                } else {
                    toolFailures++;
                    observeText(string(data, "tool", ""));
                    JsonObject result = data.has("result") && data.get("result").isJsonObject()
                            ? data.get("result").getAsJsonObject()
                            : new JsonObject();
                    observeText(string(result, "message", ""));
                }
            } else if (event.startsWith("goal_")) {
                if ("goal_started".equals(event)) {
                    goalStarted++;
                } else if ("goal_progress".equals(event)) {
                    goalProgress++;
                    levelProgressMentions++;
                    addReflection("Progress note: keep using routines that produce verified progress.");
                } else if ("goal_completed".equals(event)) {
                    goalCompleted++;
                    levelProgressMentions++;
                    addReflection("Progress note: record the gear, food, and route that made the completed goal work.");
                } else if ("goal_blocked".equals(event)) {
                    toolFailures++;
                }
                JsonObject goal = data.has("goal") && data.get("goal").isJsonObject()
                        ? data.get("goal").getAsJsonObject()
                        : new JsonObject();
                String goalMessage = string(goal, "message", "");
                if ("goal_blocked".equals(event) && containsDeath(goalMessage)) {
                    deaths++;
                    addReflection("Risk note: deaths require better food, gear, and an exit path before retrying.");
                }
                observeText(goalMessage);
                JsonObject result = data.has("result") && data.get("result").isJsonObject()
                        ? data.get("result").getAsJsonObject()
                        : new JsonObject();
                observeText(string(result, "message", ""));
            } else if ("turn_requested".equals(event) || "turn_started".equals(event)) {
                observeText(string(data, "command", ""));
            } else if ("assistant_message".equals(event)) {
                observeText(string(data, "text", ""));
            }
        }

        private void observeText(String text) {
            String lower = text == null ? "" : text.toLowerCase(Locale.ENGLISH);
            if (containsDeath(lower)) {
                deathMentions++;
            }
            if (lower.contains("inventory") || lower.contains("space") || lower.contains("full")) {
                inventoryPressure++;
                addReflection("Inventory note: bank or drop low-value items before long loops.");
            }
            if (lower.contains("bank")) {
                bankMentions++;
                addReflection("Banking note: consolidate loot and supplies before leaving a safe area.");
            }
            if (lower.contains("food") || lower.contains("fish") || lower.contains("cook") || lower.contains("eat")) {
                foodMentions++;
                addReflection("Food note: carry enough healing before travel, combat, or retries.");
            }
            if (lower.contains("varrock")) {
                varrockMentions++;
                addReflection("Varrock note: restock before using Varrock shops, mines, or routes.");
            }
            if (lower.contains("lumbridge")) {
                lumbridgeMentions++;
                addReflection("Lumbridge note: use Lumbridge as a safe fallback for early supplies and training.");
            }
            if (lower.contains("cow")) {
                cowMentions++;
                addReflection("Training note: Lumbridge cows are a repeatable early combat target; monitor food and inventory.");
            }
            if (lower.contains("goblin")) {
                addReflection("Combat note: check hitpoints and food even for low-level targets.");
            }
            if (lower.contains("path") || lower.contains("route") || lower.contains("reach")
                    || lower.contains("nearby") || lower.contains("no matching object")) {
                pathingFailures++;
                addReflection("Route note: verify reachability before repeating failed movement.");
            }
            if (lower.contains("gear") || lower.contains("armor") || lower.contains("armour")
                    || lower.contains("weapon") || lower.contains("hammer") || lower.contains("smith")) {
                gearMentions++;
                addReflection("Gear note: check equipment before riskier combat or production loops.");
            }
            if (lower.contains("coin") || lower.contains("money")) {
                coinMentions++;
                addReflection("Coin note: preserve budget for food, gear, and travel costs.");
            }
        }

        private boolean hasDeathExperience() {
            return deaths + deathMentions > 0;
        }

        private void addReflection(String note) {
            String trimmed = normalizeReflection(note);
            if (trimmed.isEmpty()) {
                return;
            }
            if (selfTalkLog == null) {
                selfTalkLog = new ArrayList<String>();
            }
            selfTalkLog.remove(trimmed);
            selfTalkLog.add(trimmed);
            while (selfTalkLog.size() > 6) {
                selfTalkLog.remove(0);
            }
        }

        private void normalizeSelfTalkLog() {
            if (selfTalkLog == null) {
                selfTalkLog = new ArrayList<String>();
                return;
            }
            List<String> normalized = new ArrayList<String>();
            for (String note : selfTalkLog) {
                String value = normalizeReflection(note);
                if (!value.isEmpty()) {
                    normalized.remove(value);
                    normalized.add(value);
                }
            }
            while (normalized.size() > 6) {
                normalized.remove(0);
            }
            selfTalkLog = normalized;
        }

        private boolean containsDeath(String text) {
            String lower = text == null ? "" : text.toLowerCase(Locale.ENGLISH);
            return lower.contains("dead") || lower.contains("death") || lower.contains("killed");
        }
    }
}
