package com.rs2.agent;

import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.atomic.AtomicLong;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import com.rs2.integrations.discord.DiscordAgentTransport;

/**
 * Bounded structured chat bus for agent-to-agent and agent-to-player messages.
 */
public class AgentChatService {

    public static final AgentChatService INSTANCE = new AgentChatService();

    private static final int MAX_BACKLOG = 250;
    private static final int MAX_PENDING_PLAYER_DELIVERIES = 250;
    private static final int MAX_MESSAGE_LENGTH = 500;
    private static final int MAX_NAME_LENGTH = 32;
    private static final int MAX_CHANNEL_LENGTH = 32;
    private static final String DEFAULT_CHANNEL = "agent";
    private static final String LOG_DIR = "agent-chat";
    private static final Gson GSON = new Gson();

    private final AtomicLong nextId = new AtomicLong(1L);
    private final List<AgentChatMessage> backlog = new ArrayList<AgentChatMessage>();
    private final List<AgentChatMessage> pendingPlayerDeliveries = new ArrayList<AgentChatMessage>();
    private File logDirectoryForTests;

    AgentChatService() {
    }

    void setLogDirectoryForTests(File directory) {
        synchronized (this) {
            logDirectoryForTests = directory;
        }
    }

    void resetLogDirectoryForTests() {
        synchronized (this) {
            logDirectoryForTests = null;
        }
    }

    public AgentChatMessage sendFromAgent(Player player, JsonObject arguments) {
        validateAgentTargetArguments(arguments);
        String text = firstString(arguments, "message", "text");
        if (text == null || text.trim().isEmpty()) {
            throw new IllegalArgumentException("message is required.");
        }
        String toType = firstString(arguments, "toType", "targetType");
        String to = firstString(arguments, "to", "target", "name", "player", "agent");
        if (toType == null || toType.trim().isEmpty()) {
            if (hasNonBlankString(arguments, "agent")) {
                toType = "agent";
            } else if (hasNonBlankString(arguments, "player")) {
                toType = "player";
            } else {
                toType = to == null || to.trim().isEmpty() ? "channel" : "player";
            }
        }
        String channel = normalizeChannel(firstString(arguments, "channel"));
        boolean deliverToPlayers = firstBoolean(arguments, "deliverToPlayers",
                firstBoolean(arguments, "alsoPlayers", "broadcast".equalsIgnoreCase(toType)
                        || "player".equalsIgnoreCase(toType)));
        return send("agent", player.playerName, player.playerName, toType, to, channel, text, deliverToPlayers);
    }

    private static void validateAgentTargetArguments(JsonObject arguments) {
        boolean hasAgent = hasNonBlankString(arguments, "agent");
        boolean hasPlayer = hasNonBlankString(arguments, "player");
        if (hasAgent && hasPlayer) {
            throw new IllegalArgumentException("Use only one target shortcut: agent or player.");
        }
        if ((hasAgent || hasPlayer)
                && (hasAnyNonBlankString(arguments, "to", "target", "name")
                || hasNonBlankString(arguments, "toType")
                || hasNonBlankString(arguments, "targetType"))) {
            throw new IllegalArgumentException("Do not combine agent/player shortcuts with to/toType target fields.");
        }
    }

    public AgentChatMessage sendFromPlayerCommand(Player player, String text) {
        ChatCommandIntent intent = parsePlayerCommand(text);
        return send("player", player.playerName, player.playerName, intent.toType, intent.toName,
                intent.channel, intent.text, intent.deliverToPlayers);
    }

    public AgentChatMessage send(String fromType, String fromName, String fromProfile, String toType,
            String toName, String channel, String text, boolean deliverToPlayers) {
        return send(fromType, fromName, fromProfile, toType, toName, channel, text, deliverToPlayers, null);
    }

    public AgentChatMessage send(String fromType, String fromName, String fromProfile, String toType,
            String toName, String channel, String text, boolean deliverToPlayers, Boolean fromBot) {
        return send(fromType, fromName, fromProfile, toType, toName, channel, text, deliverToPlayers, fromBot, "");
    }

    public AgentChatMessage send(String fromType, String fromName, String fromProfile, String toType,
            String toName, String channel, String text, boolean deliverToPlayers, Boolean fromBot,
            String discordMessageId) {
        String cleanText = cleanText(text);
        if (cleanText.isEmpty()) {
            throw new IllegalArgumentException("message is required.");
        }
        String cleanToType = cleanTargetType(toType);
        String cleanToName = cleanName(toName);
        validateTarget(cleanToType, cleanToName, deliverToPlayers);
        AgentChatMessage message = new AgentChatMessage(
                nextId.getAndIncrement(),
                System.currentTimeMillis(),
                cleanType(fromType, "agent"),
                cleanName(fromName),
                cleanName(fromProfile),
                cleanToType,
                cleanToName,
                normalizeChannel(channel),
                cleanText,
                fromBot,
                cleanExternalId(discordMessageId));
        synchronized (this) {
            if (deliverToPlayers) {
                pendingPlayerDeliveries.add(message);
                while (pendingPlayerDeliveries.size() > MAX_PENDING_PLAYER_DELIVERIES) {
                    pendingPlayerDeliveries.remove(0);
                }
            }
            backlog.add(message);
            while (backlog.size() > MAX_BACKLOG) {
                backlog.remove(0);
            }
        }
        writeChatLog(message);
        mirrorToDiscord(message);
        return message;
    }

    public synchronized JsonArray recentFor(Player player, long sinceId, String channel, int limit) {
        int max = Math.max(1, Math.min(50, limit));
        String viewer = canonical(player == null ? "" : player.playerName);
        String requestedChannel = normalizeChannel(channel);
        ArrayList<AgentChatMessage> matches = new ArrayList<AgentChatMessage>();
        for (AgentChatMessage message : backlog) {
            if (message.id <= sinceId) {
                continue;
            }
            if (!requestedChannel.equals(message.channel)) {
                continue;
            }
            if (!isVisibleTo(message, viewer)) {
                continue;
            }
            matches.add(message);
        }
        int from = Math.max(0, matches.size() - max);
        JsonArray array = new JsonArray();
        for (AgentChatMessage message : matches.subList(from, matches.size())) {
            array.add(message.toJson());
        }
        return array;
    }

    public synchronized int unreadCountFor(Player player, long sinceId, String channel) {
        String viewer = canonical(player == null ? "" : player.playerName);
        String requestedChannel = normalizeChannel(channel);
        int count = 0;
        for (AgentChatMessage message : backlog) {
            if (message.id > sinceId && requestedChannel.equals(message.channel) && isVisibleTo(message, viewer)) {
                count++;
            }
        }
        return count;
    }

    public synchronized long lastId() {
        return backlog.isEmpty() ? 0L : backlog.get(backlog.size() - 1).id;
    }

    public synchronized int backlogSize() {
        return backlog.size();
    }

    public int processPendingPlayerDeliveries() {
        ArrayList<AgentChatMessage> pending;
        synchronized (this) {
            pending = new ArrayList<AgentChatMessage>(pendingPlayerDeliveries);
            pendingPlayerDeliveries.clear();
        }
        for (AgentChatMessage message : pending) {
            deliverToPlayers(message);
            writeChatDeliveryLog(message);
        }
        return pending.size();
    }

    public synchronized int pendingPlayerDeliveryCount() {
        return pendingPlayerDeliveries.size();
    }

    public synchronized boolean isDeliveryPending(AgentChatMessage message) {
        return pendingPlayerDeliveries.contains(message);
    }

    public JsonObject transportStatus() {
        JsonObject status = new JsonObject();
        status.addProperty("discordEnabled", Constants.AGENT_CHAT_DISCORD_ENABLED);
        status.addProperty("chatLogEnabled", Constants.AGENT_CHAT_LOG_ENABLED);
        status.addProperty("pendingPlayerDeliveries", pendingPlayerDeliveryCount());
        status.add("discordTransport", DiscordAgentTransport.INSTANCE.status());
        return status;
    }

    private void writeChatLog(AgentChatMessage message) {
        writeChatLog(message, "agent_chat_message");
    }

    private void writeChatDeliveryLog(AgentChatMessage message) {
        writeChatLog(message, "agent_chat_player_delivery");
    }

    private void writeChatLog(AgentChatMessage message, String event) {
        if (!Constants.AGENT_CHAT_LOG_ENABLED || message == null) {
            return;
        }
        JsonObject entry = message.toJson();
        entry.addProperty("schemaVersion", 1);
        entry.addProperty("timestamp", timestamp(message.createdAt));
        entry.addProperty("timestampMs", message.createdAt);
        entry.addProperty("event", event);
        synchronized (this) {
            File logDirectory = resolveLogDirectory();
            File dayDirectory = new File(logDirectory, dateStamp(message.createdAt));
            if (!dayDirectory.exists() && !dayDirectory.mkdirs()) {
                System.err.println("Unable to create agent chat log directory: " + dayDirectory.getAbsolutePath());
                return;
            }
            File logFile = new File(dayDirectory, "agent-chat.jsonl");
            try (BufferedWriter writer = Files.newBufferedWriter(logFile.toPath(), StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND)) {
                writer.write(GSON.toJson(entry));
                writer.newLine();
            } catch (IOException e) {
                System.err.println("Unable to write agent chat log: " + e.getMessage());
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

    private void mirrorToDiscord(AgentChatMessage message) {
        try {
            DiscordAgentTransport.INSTANCE.onAgentChatMessage(message);
        } catch (RuntimeException e) {
            System.out.println("Agent chat Discord mirror failed: " + e.getMessage());
        }
    }

    private void deliverToPlayers(AgentChatMessage message) {
        if ("player".equals(message.toType)) {
            Player player = findOnlinePlayer(message.toName);
            if (player != null) {
                deliverToPlayer(player, message);
            } else {
                message.undeliveredTo.add(message.toName);
            }
            return;
        }
        if ("broadcast".equals(message.toType)) {
            for (Player player : onlinePlayers()) {
                deliverToPlayer(player, message);
            }
        }
    }

    private void deliverToPlayer(Player player, AgentChatMessage message) {
        try {
            sendClientLine(player, message);
            message.deliveredTo.add(player.playerName);
        } catch (RuntimeException e) {
            String playerName = cleanName(player == null ? "" : player.playerName);
            if (!playerName.isEmpty()) {
                message.undeliveredTo.add(playerName);
            }
            System.out.println("Agent chat player delivery failed for " + playerName + ": "
                    + e.getClass().getSimpleName());
        }
    }

    private List<Player> onlinePlayers() {
        ArrayList<Player> players = new ArrayList<Player>();
        for (int i = 0; i < PlayerHandler.players.length; i++) {
            Player player = PlayerHandler.players[i];
            if (player != null && player.isActive && !player.disconnected) {
                players.add(player);
            }
        }
        return players;
    }

    private Player findOnlinePlayer(String name) {
        String canonical = canonical(name);
        if (canonical.isEmpty()) {
            return null;
        }
        for (int i = 0; i < PlayerHandler.players.length; i++) {
            Player player = PlayerHandler.players[i];
            if (player != null && player.isActive && !player.disconnected
                    && canonical(player.playerName).equals(canonical)) {
                return player;
            }
        }
        return null;
    }

    private void sendClientLine(Player player, AgentChatMessage message) {
        player.getPacketSender().sendMessage("[AgentChat:" + message.fromName + "] " + message.text);
    }

    private boolean isVisibleTo(AgentChatMessage message, String viewer) {
        if ("broadcast".equals(message.toType) || "channel".equals(message.toType)) {
            return true;
        }
        String target = canonical(message.toName);
        String sender = canonical(message.fromName);
        String senderProfile = canonical(message.fromProfile);
        return viewer.equals(target) || viewer.equals(sender) || viewer.equals(senderProfile);
    }

    private static String firstString(JsonObject object, String... names) {
        if (object == null) {
            return null;
        }
        for (String name : names) {
            if (object.has(name) && object.get(name).isJsonPrimitive()) {
                return object.get(name).getAsString();
            }
        }
        return null;
    }

    private static boolean hasNonBlankString(JsonObject object, String name) {
        if (object == null || !object.has(name) || !object.get(name).isJsonPrimitive()) {
            return false;
        }
        try {
            return !object.get(name).getAsString().trim().isEmpty();
        } catch (RuntimeException ignored) {
            return false;
        }
    }

    private static boolean hasAnyNonBlankString(JsonObject object, String... names) {
        for (String name : names) {
            if (hasNonBlankString(object, name)) {
                return true;
            }
        }
        return false;
    }

    private static boolean firstBoolean(JsonObject object, String name, boolean fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            try {
                return object.get(name).getAsBoolean();
            } catch (RuntimeException ignored) {
            }
        }
        return fallback;
    }

    private static String cleanText(String text) {
        if (text == null) {
            return "";
        }
        String clean = stripControlCharacters(text).trim();
        if (clean.length() > MAX_MESSAGE_LENGTH) {
            clean = clean.substring(0, MAX_MESSAGE_LENGTH);
        }
        return clean;
    }

    private static String cleanName(String name) {
        String clean = stripControlCharacters(name).trim();
        if (clean.length() > MAX_NAME_LENGTH) {
            clean = clean.substring(0, MAX_NAME_LENGTH);
        }
        return clean;
    }

    private static String cleanExternalId(String value) {
        String clean = stripControlCharacters(value).trim();
        return clean.length() > 64 ? clean.substring(0, 64) : clean;
    }

    private static String cleanType(String type, String fallback) {
        String clean = type == null ? "" : type.trim().toLowerCase(Locale.US);
        if ("agent".equals(clean) || "player".equals(clean) || "discord".equals(clean)
                || "broadcast".equals(clean) || "channel".equals(clean)) {
            return clean;
        }
        return fallback;
    }

    private static String cleanTargetType(String type) {
        String clean = type == null ? "" : type.trim().toLowerCase(Locale.US);
        if (clean.isEmpty()) {
            return "channel";
        }
        if ("agent".equals(clean) || "player".equals(clean) || "broadcast".equals(clean)
                || "channel".equals(clean)) {
            return clean;
        }
        throw new IllegalArgumentException("toType must be agent, player, channel, or broadcast.");
    }

    private static void validateTarget(String toType, String toName, boolean deliverToPlayers) {
        if (("agent".equals(toType) || "player".equals(toType))
                && (toName == null || toName.trim().isEmpty())) {
            throw new IllegalArgumentException("to is required when toType is agent or player.");
        }
        if (deliverToPlayers && !("player".equals(toType) || "broadcast".equals(toType))) {
            throw new IllegalArgumentException("deliverToPlayers requires toType player or broadcast.");
        }
    }

    private static String normalizeChannel(String channel) {
        String clean = stripControlCharacters(channel).trim().toLowerCase(Locale.US);
        if (clean.isEmpty()) {
            return DEFAULT_CHANNEL;
        }
        clean = clean.replaceAll("[^a-z0-9._-]", "-");
        while (clean.contains("--")) {
            clean = clean.replace("--", "-");
        }
        if (clean.length() > MAX_CHANNEL_LENGTH) {
            clean = clean.substring(0, MAX_CHANNEL_LENGTH);
        }
        return clean.isEmpty() || "-".equals(clean) ? DEFAULT_CHANNEL : clean;
    }

    private static ChatCommandIntent parsePlayerCommand(String text) {
        String clean = cleanText(text);
        String lower = clean.toLowerCase(Locale.US);
        if (lower.startsWith("@all ")) {
            return new ChatCommandIntent("broadcast", "", DEFAULT_CHANNEL, clean.substring(5).trim(), true);
        }
        if (lower.startsWith("@agent:")) {
            int space = clean.indexOf(' ');
            if (space > 7) {
                String name = clean.substring(7, space).trim();
                return new ChatCommandIntent("agent", name, DEFAULT_CHANNEL, clean.substring(space + 1).trim(), false);
            }
        }
        if (lower.startsWith("@player:")) {
            int space = clean.indexOf(' ');
            if (space > 8) {
                String name = clean.substring(8, space).trim();
                return new ChatCommandIntent("player", name, DEFAULT_CHANNEL, clean.substring(space + 1).trim(), true);
            }
        }
        if (clean.startsWith("#")) {
            int space = clean.indexOf(' ');
            if (space > 1) {
                return new ChatCommandIntent("channel", "", clean.substring(1, space),
                        clean.substring(space + 1).trim(), false);
            }
        }
        return new ChatCommandIntent("channel", "", DEFAULT_CHANNEL, clean, false);
    }

    private static String stripControlCharacters(String value) {
        if (value == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder(value.length());
        boolean previousWasSpace = false;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (Character.isISOControl(c)) {
                if (!previousWasSpace) {
                    builder.append(' ');
                    previousWasSpace = true;
                }
            } else {
                builder.append(c);
                previousWasSpace = Character.isWhitespace(c);
            }
        }
        return builder.toString();
    }

    private static String canonical(String name) {
        return name == null ? "" : name.trim().toLowerCase(Locale.US);
    }

    private static class ChatCommandIntent {
        private final String toType;
        private final String toName;
        private final String channel;
        private final String text;
        private final boolean deliverToPlayers;

        private ChatCommandIntent(String toType, String toName, String channel, String text, boolean deliverToPlayers) {
            this.toType = toType;
            this.toName = toName;
            this.channel = channel;
            this.text = text;
            this.deliverToPlayers = deliverToPlayers;
        }
    }

    public static class AgentChatMessage {
        public final long id;
        public final long createdAt;
        public final String fromType;
        public final String fromName;
        public final String fromProfile;
        public final String toType;
        public final String toName;
        public final String channel;
        public final String text;
        public final Boolean fromBot;
        public final String discordMessageId;
        public final List<String> deliveredTo = Collections.synchronizedList(new ArrayList<String>());
        public final List<String> undeliveredTo = Collections.synchronizedList(new ArrayList<String>());

        private AgentChatMessage(long id, long createdAt, String fromType, String fromName, String fromProfile,
                String toType, String toName, String channel, String text, Boolean fromBot, String discordMessageId) {
            this.id = id;
            this.createdAt = createdAt;
            this.fromType = fromType;
            this.fromName = fromName;
            this.fromProfile = fromProfile;
            this.toType = toType;
            this.toName = toName;
            this.channel = channel;
            this.text = text;
            this.fromBot = fromBot;
            this.discordMessageId = discordMessageId;
        }

        public JsonObject toJson() {
            JsonObject json = new JsonObject();
            json.addProperty("id", id);
            json.addProperty("createdAt", createdAt);
            json.addProperty("fromType", fromType);
            json.addProperty("fromName", fromName);
            json.addProperty("fromProfile", fromProfile);
            json.addProperty("toType", toType);
            if (toName != null && !toName.isEmpty()) {
                json.addProperty("toName", toName);
            }
            json.addProperty("channel", channel);
            json.addProperty("text", text);
            if (fromBot != null) {
                json.addProperty("fromBot", fromBot.booleanValue());
            }
            if (discordMessageId != null && !discordMessageId.isEmpty()) {
                json.addProperty("discordMessageId", discordMessageId);
            }
            JsonArray delivered = new JsonArray();
            synchronized (deliveredTo) {
                for (Iterator<String> it = deliveredTo.iterator(); it.hasNext();) {
                    delivered.add(it.next());
                }
            }
            json.add("deliveredTo", delivered);
            JsonArray undelivered = new JsonArray();
            synchronized (undeliveredTo) {
                for (Iterator<String> it = undeliveredTo.iterator(); it.hasNext();) {
                    undelivered.add(it.next());
                }
            }
            json.add("undeliveredTo", undelivered);
            return json;
        }
    }
}
