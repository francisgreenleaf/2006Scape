package com.rs2.util;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import com.rs2.Constants;
import com.rs2.agent.AgentActionService;

public final class PerformanceLogger {

    private static final ExecutorService WRITER = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "ServerPerformanceLogger");
        thread.setDaemon(true);
        return thread;
    });

    private PerformanceLogger() {
    }

    public static void logTick(final TickSample sample) {
        if (!Constants.PERFORMANCE_LOGGING || sample == null) {
            return;
        }
        WRITER.execute(new Runnable() {
            @Override
            public void run() {
                write(sample);
            }
        });
    }

    private static void write(TickSample sample) {
        long now = System.currentTimeMillis();
        File dayDirectory = new File(Constants.SERVER_LOG_DIR, "performance");
        if (!dayDirectory.exists() && !dayDirectory.mkdirs()) {
            return;
        }
        File logFile = new File(dayDirectory, "tick-performance-" + dateStamp(now) + ".jsonl");
        StringBuilder builder = new StringBuilder(512);
        builder.append('{');
        append(builder, "timestamp", timestamp(now)).append(',');
        append(builder, "event", "server_tick").append(',');
        append(builder, "gameCycle", sample.gameCycle).append(',');
        append(builder, "agentTick", sample.agentTick).append(',');
        append(builder, "totalMs", sample.totalMs).append(',');
        append(builder, "agentMs", sample.agentMs).append(',');
        append(builder, "itemMs", sample.itemMs).append(',');
        append(builder, "playerMs", sample.playerMs).append(',');
        append(builder, "npcMs", sample.npcMs).append(',');
        append(builder, "shopMs", sample.shopMs).append(',');
        append(builder, "objectHandlerMs", sample.objectHandlerMs).append(',');
        append(builder, "objectManagerMs", sample.objectManagerMs).append(',');
        append(builder, "cycleEventMs", sample.cycleEventMs).append(',');
        append(builder, "saveMs", sample.saveMs).append(',');
        append(builder, "queuedAtStart", sample.queuedAtStart).append(',');
        append(builder, "queuedProcessed", sample.queuedProcessed).append(',');
        append(builder, "queuedAfter", sample.queuedAfter).append(',');
        append(builder, "combatGoals", sample.combatGoals).append(',');
        append(builder, "actionTimedMs", sample.actionTimedMs).append(',');
        append(builder, "slowestAction", sample.slowestAction).append(',');
        append(builder, "slowestActionMs", sample.slowestActionMs).append(',');
        append(builder, "actionSummary", sample.actionSummary).append(',');
        append(builder, "players", sample.players).append(',');
        append(builder, "npcs", sample.npcs).append(',');
        append(builder, "usedMemMb", sample.usedMemMb).append(',');
        append(builder, "totalMemMb", sample.totalMemMb).append(',');
        append(builder, "maxMemMb", sample.maxMemMb).append(',');
        append(builder, "threads", sample.threads);
        builder.append('}').append('\n');
        try {
            Files.write(logFile.toPath(), builder.toString().getBytes(StandardCharsets.UTF_8),
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException ignored) {
        }
    }

    private static StringBuilder append(StringBuilder builder, String key, long value) {
        builder.append('"').append(key).append("\":").append(value);
        return builder;
    }

    private static StringBuilder append(StringBuilder builder, String key, String value) {
        builder.append('"').append(key).append("\":\"").append(escape(value)).append('"');
        return builder;
    }

    private static String escape(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static String timestamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    private static String dateStamp(long now) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ENGLISH);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(now));
    }

    public static final class TickSample {
        public final long gameCycle;
        public final long agentTick;
        public final long totalMs;
        public final long agentMs;
        public final long itemMs;
        public final long playerMs;
        public final long npcMs;
        public final long shopMs;
        public final long objectHandlerMs;
        public final long objectManagerMs;
        public final long cycleEventMs;
        public final long saveMs;
        public final int queuedAtStart;
        public final int queuedProcessed;
        public final int queuedAfter;
        public final int combatGoals;
        public final long actionTimedMs;
        public final String slowestAction;
        public final long slowestActionMs;
        public final String actionSummary;
        public final int players;
        public final int npcs;
        public final long usedMemMb;
        public final long totalMemMb;
        public final long maxMemMb;
        public final int threads;

        public TickSample(long gameCycle, AgentActionService.TickStats agentStats, long totalMs, long agentMs,
                long itemMs, long playerMs, long npcMs, long shopMs, long objectHandlerMs, long objectManagerMs,
                long cycleEventMs, long saveMs, int players, int npcs, long usedMemMb, long totalMemMb,
                long maxMemMb, int threads) {
            this.gameCycle = gameCycle;
            this.agentTick = agentStats == null ? -1L : agentStats.tick;
            this.totalMs = totalMs;
            this.agentMs = agentMs;
            this.itemMs = itemMs;
            this.playerMs = playerMs;
            this.npcMs = npcMs;
            this.shopMs = shopMs;
            this.objectHandlerMs = objectHandlerMs;
            this.objectManagerMs = objectManagerMs;
            this.cycleEventMs = cycleEventMs;
            this.saveMs = saveMs;
            this.queuedAtStart = agentStats == null ? -1 : agentStats.queuedAtStart;
            this.queuedProcessed = agentStats == null ? -1 : agentStats.processed;
            this.queuedAfter = agentStats == null ? -1 : agentStats.queuedAfter;
            this.combatGoals = agentStats == null ? -1 : agentStats.combatGoals;
            this.actionTimedMs = agentStats == null ? -1L : agentStats.actionTimedMs;
            this.slowestAction = agentStats == null ? "" : agentStats.slowestAction;
            this.slowestActionMs = agentStats == null ? -1L : agentStats.slowestActionMs;
            this.actionSummary = agentStats == null ? "" : agentStats.actionSummary;
            this.players = players;
            this.npcs = npcs;
            this.usedMemMb = usedMemMb;
            this.totalMemMb = totalMemMb;
            this.maxMemMb = maxMemMb;
            this.threads = threads;
        }
    }
}
