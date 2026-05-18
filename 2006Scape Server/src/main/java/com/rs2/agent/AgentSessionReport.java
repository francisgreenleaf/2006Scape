package com.rs2.agent;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TimeZone;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.rs2.Constants;

public class AgentSessionReport {

    private static final String LOG_DIR = "agent-sessions";
    private static final Pattern[] SENSITIVE_VALUE_PATTERNS = {
            Pattern.compile("(?i)\\bBearer\\s+[A-Za-z0-9._\\-+/=]+"),
            Pattern.compile("(?i)\\b(api[_-]?key|token|session[_-]?token|auth[_-]?token|password|secret|cookie)\\s*[:=]\\s*[^\\s,;}]+"),
            Pattern.compile("\\bsk-[A-Za-z0-9_\\-]{12,}\\b")
    };

    public static void main(String[] args) throws Exception {
        File baseDirectory = args.length > 0 ? new File(args[0]) : defaultLogDirectory();
        File mirrorDirectory = args.length > 1 && args[1] != null && !args[1].trim().isEmpty()
                ? new File(args[1])
                : null;
        Result result = generate(baseDirectory, mirrorDirectory);
        System.out.println("Wrote " + result.summaryFile.getAbsolutePath());
        System.out.println("Wrote " + result.indexFile.getAbsolutePath());
    }

    static Result generate(File baseDirectory, File mirrorDirectory) throws IOException {
        if (baseDirectory == null) {
            baseDirectory = defaultLogDirectory();
        }
        Map<String, SessionAggregate> sessions = loadSessions(baseDirectory);
        long now = System.currentTimeMillis();
        File reportsRoot = new File(baseDirectory, "reports");
        File reportDirectory = new File(reportsRoot, dateStamp(now));
        if (!reportDirectory.exists() && !reportDirectory.mkdirs()) {
            throw new IOException("Unable to create report directory: " + reportDirectory.getAbsolutePath());
        }
        File summaryFile = new File(reportDirectory, "summary-" + timeStamp(now) + "Z.md");
        File indexFile = new File(reportsRoot, "canonical-agent-log-index.md");
        Files.write(summaryFile.toPath(), renderSummary(sessions, now).getBytes(StandardCharsets.UTF_8));
        Files.write(indexFile.toPath(), renderIndex(sessions, summaryFile, now).getBytes(StandardCharsets.UTF_8));
        if (mirrorDirectory != null) {
            mirrorDirectory.mkdirs();
            Files.copy(summaryFile.toPath(), new File(mirrorDirectory, summaryFile.getName()).toPath(), StandardCopyOption.REPLACE_EXISTING);
            Files.copy(indexFile.toPath(), new File(mirrorDirectory, indexFile.getName()).toPath(), StandardCopyOption.REPLACE_EXISTING);
        }
        return new Result(summaryFile, indexFile, sessions.size());
    }

    private static File defaultLogDirectory() {
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

    private static Map<String, SessionAggregate> loadSessions(File baseDirectory) throws IOException {
        Map<String, SessionAggregate> sessions = new LinkedHashMap<String, SessionAggregate>();
        List<File> files = new ArrayList<File>();
        collectJsonlFiles(baseDirectory, files);
        Collections.sort(files);
        for (File file : files) {
            String day = file.getParentFile() == null ? "" : file.getParentFile().getName();
            List<String> lines = Files.readAllLines(file.toPath(), StandardCharsets.UTF_8);
            for (String line : lines) {
                if (line == null || line.trim().isEmpty()) {
                    continue;
                }
                try {
                    JsonObject entry = new JsonParser().parse(line).getAsJsonObject();
                    String sessionId = string(entry, "sessionId", stem(file.getName()));
                    SessionAggregate aggregate = sessions.get(sessionId);
                    if (aggregate == null) {
                        aggregate = new SessionAggregate(sessionId);
                        sessions.put(sessionId, aggregate);
                    }
                    aggregate.consume(day, entry);
                } catch (Exception ignored) {
                }
            }
        }
        return sessions;
    }

    private static void collectJsonlFiles(File directory, List<File> files) {
        if (directory == null || !directory.exists()) {
            return;
        }
        File[] children = directory.listFiles();
        if (children == null) {
            return;
        }
        for (File child : children) {
            if (child.isDirectory()) {
                if (!"reports".equals(child.getName())) {
                    collectJsonlFiles(child, files);
                }
            } else if (child.getName().endsWith(".jsonl")) {
                files.add(child);
            }
        }
    }

    private static String renderSummary(Map<String, SessionAggregate> sessions, long now) {
        Counter tools = new Counter();
        Counter blockers = new Counter();
        int failures = 0;
        int deaths = 0;
        int durableGoalSessions = 0;
        int multiDaySessions = 0;
        for (SessionAggregate session : sessions.values()) {
            tools.addAll(session.tools);
            blockers.addAll(session.blockers);
            failures += session.failures;
            deaths += session.deaths;
            if (session.hasDurableGoal) {
                durableGoalSessions++;
            }
            if (session.days.size() > 1) {
                multiDaySessions++;
            }
        }

        StringBuilder builder = new StringBuilder();
        builder.append("# Agent Session Log Summary\n\n");
        builder.append("- Generated: ").append(iso(now)).append("\n");
        builder.append("- Sessions scanned: ").append(sessions.size()).append("\n");
        builder.append("- Tool failures/blockers: ").append(failures).append("\n");
        builder.append("- Death observations: ").append(deaths).append("\n");
        builder.append("- Connected multi-day sessions: ").append(multiDaySessions).append("\n\n");

        builder.append("## New / Interesting Behavior\n\n");
        if (durableGoalSessions > 0) {
            builder.append("- Durable goal events appeared in ").append(durableGoalSessions).append(" session(s), which means the harness is recording beyond one-shot tool calls.\n");
        }
        List<SessionAggregate> interesting = mostInteresting(sessions);
        for (SessionAggregate session : interesting) {
            builder.append("- ").append(session.sessionId).append(": ").append(session.shortSummary()).append("\n");
        }
        if (durableGoalSessions == 0 && interesting.isEmpty()) {
            builder.append("- No unusual behavior stood out in the scanned logs.\n");
        }
        builder.append("\n");

        builder.append("## Top Tools\n\n");
        appendCounter(builder, tools, "No tool calls were found.");

        builder.append("## Repeated Blockers\n\n");
        appendCounter(builder, blockers, "No repeated blockers were found.");

        builder.append("## Death / Failure Observations\n\n");
        if (failures == 0 && deaths == 0) {
            builder.append("- No death or tool-failure observations were found.\n\n");
        } else {
            for (SessionAggregate session : sessions.values()) {
                if (session.failures > 0 || session.deaths > 0) {
                    builder.append("- ").append(session.sessionId).append(": ")
                            .append(session.failures).append(" failure(s), ")
                            .append(session.deaths).append(" death observation(s)");
                    if (!session.failureMessages.isEmpty()) {
                        builder.append("; latest: ").append(session.failureMessages.get(session.failureMessages.size() - 1));
                    }
                    builder.append(".\n");
                }
            }
            builder.append("\n");
        }

        builder.append("## Connected Multi-Day Sessions\n\n");
        boolean wroteMultiDay = false;
        for (SessionAggregate session : sessions.values()) {
            if (session.days.size() > 1) {
                builder.append("- ").append(session.sessionId).append(": ").append(join(session.days)).append("\n");
                wroteMultiDay = true;
            }
        }
        if (!wroteMultiDay) {
            builder.append("- No sessionId appeared across multiple day directories.\n");
        }
        builder.append("\n");

        builder.append("## Harness Suggestions\n\n");
        appendSuggestions(builder, blockers, deaths, durableGoalSessions);
        return builder.toString();
    }

    private static String renderIndex(Map<String, SessionAggregate> sessions, File summaryFile, long now) {
        StringBuilder builder = new StringBuilder();
        builder.append("# Canonical Agent Log Index\n\n");
        builder.append("- Last updated: ").append(iso(now)).append("\n");
        builder.append("- Latest report: ").append(summaryFile.getPath()).append("\n");
        builder.append("- Sessions indexed: ").append(sessions.size()).append("\n\n");
        builder.append("## Sessions\n\n");
        if (sessions.isEmpty()) {
            builder.append("- No JSONL sessions found.\n");
            return builder.toString();
        }
        for (SessionAggregate session : sessions.values()) {
            builder.append("- ").append(session.sessionId)
                    .append(" | days: ").append(join(session.days))
                    .append(" | player: ").append(session.playerName == null ? "unknown" : session.playerName)
                    .append(" | events: ").append(session.events)
                    .append(" | task: ").append(session.task == null ? "unknown" : session.task)
                    .append("\n");
        }
        return builder.toString();
    }

    private static List<SessionAggregate> mostInteresting(Map<String, SessionAggregate> sessions) {
        List<SessionAggregate> values = new ArrayList<SessionAggregate>(sessions.values());
        Collections.sort(values, new Comparator<SessionAggregate>() {
            @Override
            public int compare(SessionAggregate a, SessionAggregate b) {
                return b.interestScore() - a.interestScore();
            }
        });
        List<SessionAggregate> result = new ArrayList<SessionAggregate>();
        for (SessionAggregate session : values) {
            if (session.interestScore() > 0 && result.size() < 5) {
                result.add(session);
            }
        }
        return result;
    }

    private static void appendCounter(StringBuilder builder, Counter counter, String fallback) {
        List<Map.Entry<String, Integer>> entries = counter.sorted();
        if (entries.isEmpty()) {
            builder.append("- ").append(fallback).append("\n\n");
            return;
        }
        int limit = Math.min(10, entries.size());
        for (int i = 0; i < limit; i++) {
            Map.Entry<String, Integer> entry = entries.get(i);
            builder.append("- ").append(entry.getKey()).append(": ").append(entry.getValue()).append("\n");
        }
        builder.append("\n");
    }

    private static void appendSuggestions(StringBuilder builder, Counter blockers, int deaths, int durableGoalSessions) {
        if (deaths > 0) {
            builder.append("- Add earlier food/restock checks around risky combat loops and log hitpoint thresholds before death.\n");
        }
        if (blockers.count("inventory space") > 0) {
            builder.append("- Teach long goals to pre-bank or cook before inventory pressure blocks gathering.\n");
        }
        if (blockers.count("missing requirement or equipment") > 0 || blockers.count("skill requirement") > 0) {
            builder.append("- Add planner preflight checks for required tools, equipment, and skill levels before committing to an action chain.\n");
        }
        if (blockers.count("unreachable or unavailable target") > 0) {
            builder.append("- Improve reachability hints in finder tools so the agent can choose another target sooner.\n");
        }
        if (blockers.count("closed or wrong interface") > 0) {
            builder.append("- Add explicit interface-state observations before shop, bank, smithing, and dialogue actions.\n");
        }
        if (blockers.count("invalid or expired session") > 0) {
            builder.append("- Treat player-offline/session-expired endings as first-class run outcomes so the client can distinguish a harness shutdown from an in-game blocker.\n");
        }
        if (blockers.count("gameplay blocker") > 0) {
            builder.append("- Classify common recoverable messages such as combat repositioning separately from terminal failures in older logs and reports.\n");
        }
        if (durableGoalSessions == 0) {
            builder.append("- Prefer durable goal tools for long grinds so progress and blockers continue to be logged after the Codex turn ends.\n");
        }
        if (builder.toString().endsWith("## Harness Suggestions\n\n")) {
            builder.append("- Keep gathering more sessions; the current logs do not show a repeated harness weakness yet.\n");
        }
    }

    private static class SessionAggregate {
        private final String sessionId;
        private final Set<String> days = new LinkedHashSet<String>();
        private final Counter tools = new Counter();
        private final Counter blockers = new Counter();
        private final List<String> failureMessages = new ArrayList<String>();
        private String playerName;
        private String task;
        private int events;
        private int failures;
        private int deaths;
        private boolean hasDurableGoal;

        private SessionAggregate(String sessionId) {
            this.sessionId = sessionId;
        }

        private void consume(String day, JsonObject entry) {
            days.add(day);
            events++;
            playerName = string(entry, "playerName", playerName);
            JsonObject player = entry.has("player") && entry.get("player").isJsonObject()
                    ? entry.get("player").getAsJsonObject()
                    : null;
            if (player != null && bool(player, "isDead", false)) {
                deaths++;
                blockers.increment("player death");
            }
            String event = string(entry, "event", "");
            if (event.startsWith("goal_")) {
                hasDurableGoal = true;
            }
            JsonObject data = entry.has("data") && entry.get("data").isJsonObject()
                    ? entry.get("data").getAsJsonObject()
                    : new JsonObject();
            if ("turn_requested".equals(event) || "turn_started".equals(event)) {
                task = string(data, "command", task);
            }
            if ("tool_completed".equals(event) || "tool_failed".equals(event)) {
                String tool = string(data, "tool", "unknown_tool");
                tools.increment("rs." + tool);
                JsonObject result = data.has("result") && data.get("result").isJsonObject()
                        ? data.get("result").getAsJsonObject()
                        : new JsonObject();
                boolean success = "tool_completed".equals(event) && bool(result, "success", false);
                if (!success) {
                    String message = string(result, "message", "tool failed");
                    recordFailure(message);
                }
            } else if ("session_expired".equals(event) || "session_invalidated".equals(event)) {
                recordFailure(string(data, "reason", "session ended"));
            } else if ("goal_blocked".equals(event)) {
                JsonObject goal = data.has("goal") && data.get("goal").isJsonObject()
                        ? data.get("goal").getAsJsonObject()
                        : new JsonObject();
                recordFailure(string(goal, "message", "goal blocked"));
            }
        }

        private void recordFailure(String message) {
            failures++;
            String category = blockerCategory(message);
            blockers.increment(category);
            if (failureMessages.size() < 5) {
                failureMessages.add(compact(message, 160));
            }
        }

        private int interestScore() {
            return failures * 3 + deaths * 5 + (hasDurableGoal ? 2 : 0) + (days.size() > 1 ? 3 : 0);
        }

        private String shortSummary() {
            StringBuilder builder = new StringBuilder();
            builder.append(task == null ? "no task text" : compact(task, 80));
            if (hasDurableGoal) {
                builder.append("; durable goal events");
            }
            if (failures > 0) {
                builder.append("; ").append(failures).append(" blocker(s)");
            }
            if (deaths > 0) {
                builder.append("; death observed");
            }
            return builder.toString();
        }
    }

    private static class Counter {
        private final Map<String, Integer> counts = new LinkedHashMap<String, Integer>();

        private void increment(String name) {
            counts.put(name, Integer.valueOf(count(name) + 1));
        }

        private int count(String name) {
            Integer count = counts.get(name);
            return count == null ? 0 : count.intValue();
        }

        private void addAll(Counter other) {
            for (Map.Entry<String, Integer> entry : other.counts.entrySet()) {
                counts.put(entry.getKey(), Integer.valueOf(count(entry.getKey()) + entry.getValue().intValue()));
            }
        }

        private List<Map.Entry<String, Integer>> sorted() {
            List<Map.Entry<String, Integer>> entries = new ArrayList<Map.Entry<String, Integer>>(counts.entrySet());
            Collections.sort(entries, new Comparator<Map.Entry<String, Integer>>() {
                @Override
                public int compare(Map.Entry<String, Integer> a, Map.Entry<String, Integer> b) {
                    return b.getValue().intValue() - a.getValue().intValue();
                }
            });
            return entries;
        }
    }

    static class Result {
        final File summaryFile;
        final File indexFile;
        final int sessionsScanned;

        Result(File summaryFile, File indexFile, int sessionsScanned) {
            this.summaryFile = summaryFile;
            this.indexFile = indexFile;
            this.sessionsScanned = sessionsScanned;
        }
    }

    private static String string(JsonObject object, String name, String fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            String value = object.get(name).getAsString();
            return value == null ? fallback : redactSensitiveValue(value.replace('\r', ' ').replace('\n', ' ').trim());
        }
        return fallback;
    }

    private static boolean bool(JsonObject object, String name, boolean fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            return object.get(name).getAsBoolean();
        }
        return fallback;
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

    private static String compact(String value, int maxLength) {
        String cleaned = value == null ? "" : redactSensitiveValue(value.replace('\r', ' ').replace('\n', ' ').trim());
        if (cleaned.length() <= maxLength) {
            return cleaned;
        }
        return cleaned.substring(0, Math.max(0, maxLength - 3)) + "...";
    }

    private static String redactSensitiveValue(String value) {
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

    private static String stem(String fileName) {
        int dot = fileName.lastIndexOf('.');
        return dot < 0 ? fileName : fileName.substring(0, dot);
    }

    private static String join(Set<String> values) {
        StringBuilder builder = new StringBuilder();
        for (String value : values) {
            if (builder.length() > 0) {
                builder.append(", ");
            }
            builder.append(value);
        }
        return builder.toString();
    }

    private static String iso(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    private static String dateStamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    private static String timeStamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("HHmmss", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }
}
