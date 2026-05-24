package com.rs2.agent;

import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.rs2.Constants;

public class AgentMovementTraceLog {

    public static final AgentMovementTraceLog INSTANCE = new AgentMovementTraceLog();

    private static final Gson GSON = new Gson();
    private static final String LOG_DIR = "agent-movement-traces";

    private final Object lock = new Object();
    private File logDirectoryForTests;

    public void record(AgentSession session, JsonObject event) {
        if (session == null || event == null || session.getSessionId() == null
                || session.getSessionId().trim().isEmpty()) {
            return;
        }
        long now = System.currentTimeMillis();
        event.addProperty("schemaVersion", 1);
        event.addProperty("timestamp", timestamp(now));
        event.addProperty("timestampMs", now);
        event.addProperty("sessionId", session.getSessionId());
        event.addProperty("playerId", session.getPlayerId());
        event.addProperty("playerName", session.getPlayerName());
        write(session, now, event);
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

    private void write(AgentSession session, long now, JsonObject event) {
        synchronized (lock) {
            File dayDirectory = new File(resolveLogDirectory(), dateStamp(now));
            if (!dayDirectory.exists() && !dayDirectory.mkdirs()) {
                System.err.println("Unable to create agent movement trace directory: "
                        + dayDirectory.getAbsolutePath());
                return;
            }
            File logFile = new File(dayDirectory, session.getSessionId() + ".jsonl");
            try (BufferedWriter writer = Files.newBufferedWriter(logFile.toPath(), StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND)) {
                writer.write(GSON.toJson(event));
                writer.newLine();
            } catch (IOException e) {
                System.err.println("Unable to write agent movement trace: " + e.getMessage());
            }
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

    private String timestamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    private String dateStamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }
}
