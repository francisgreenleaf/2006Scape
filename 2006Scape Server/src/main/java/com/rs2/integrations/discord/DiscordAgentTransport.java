package com.rs2.integrations.discord;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

import org.javacord.api.DiscordApi;
import org.javacord.api.DiscordApiBuilder;
import org.javacord.api.entity.channel.TextChannel;
import org.javacord.api.event.message.MessageCreateEvent;
import org.javacord.api.util.logging.ExceptionLogger;
import org.json.JSONArray;
import org.json.JSONObject;

import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.agent.AgentChatService;

/**
 * Optional per-agent Discord transport for AgentChatService.
 */
public class DiscordAgentTransport {

    public static final DiscordAgentTransport INSTANCE = new DiscordAgentTransport();

    private final ConcurrentMap<String, BotConfig> configsByAgent = new ConcurrentHashMap<String, BotConfig>();
    private final ConcurrentMap<String, BotRuntime> runtimesByAgent = new ConcurrentHashMap<String, BotRuntime>();

    private DiscordAgentTransport() {
    }

    public synchronized void configure(JSONArray configs) {
        disconnectRuntimes();
        configsByAgent.clear();
        if (configs == null) {
            return;
        }
        for (int i = 0; i < configs.length(); i++) {
            JSONObject object = configs.optJSONObject(i);
            if (object == null) {
                continue;
            }
            BotConfig config = BotConfig.fromJson(object);
            if (config.isUsable()) {
                if (configsByAgent.containsKey(config.agentKey)) {
                    System.out.println("Ignoring duplicate Agent Discord bot config for " + config.agentName + ".");
                    continue;
                }
                configsByAgent.put(config.agentKey, config);
            }
        }
    }

    public synchronized void init() {
        if (!Constants.AGENT_CHAT_DISCORD_ENABLED) {
            return;
        }
        if (configsByAgent.isEmpty()) {
            System.out.println("Agent chat Discord transport enabled, but no agent-discord-bots are configured.");
            return;
        }
        for (BotConfig config : configsByAgent.values()) {
            if (runtimesByAgent.containsKey(config.agentKey)) {
                continue;
            }
            login(config);
        }
    }

    public void onAgentChatMessage(AgentChatService.AgentChatMessage message) {
        if (!Constants.AGENT_CHAT_DISCORD_ENABLED || message == null || "discord".equals(message.fromType)) {
            return;
        }
        List<BotRuntime> targets = targetRuntimes(message);
        if (targets.isEmpty()) {
            return;
        }
        String text = formatForDiscord(message);
        Set<String> sentChannels = new HashSet<String>();
        for (BotRuntime runtime : targets) {
            String channelKey = runtime.channelKey();
            if (!sentChannels.add(channelKey)) {
                continue;
            }
            try {
                runtime.send(text);
            } catch (RuntimeException e) {
                System.out.println("Agent Discord mirror failed for " + runtime.config.agentName + ": " + e.getMessage());
            }
        }
    }

    public JsonObject status() {
        JsonObject status = new JsonObject();
        status.addProperty("enabled", Constants.AGENT_CHAT_DISCORD_ENABLED);
        status.addProperty("configuredBots", configsByAgent.size());
        status.addProperty("connectedBots", runtimesByAgent.size());
        return status;
    }

    public int configuredCount() {
        return configsByAgent.size();
    }

    public int connectedCount() {
        return runtimesByAgent.size();
    }

    private void login(final BotConfig config) {
        new DiscordApiBuilder().setToken(config.token).login().thenAccept(api -> {
            BotRuntime runtime = new BotRuntime(config, api);
            synchronized (DiscordAgentTransport.this) {
                if (configsByAgent.get(config.agentKey) != config) {
                    runtime.disconnect();
                    return;
                }
                BotRuntime previous = runtimesByAgent.put(config.agentKey, runtime);
                if (previous != null) {
                    previous.disconnect();
                }
            }
            api.updateActivity("2006Scape agent chat");
            api.addMessageCreateListener(event -> handleDiscordMessage(config, event));
            System.out.println("Agent Discord bot connected for " + config.agentName + ".");
        }).exceptionally(ExceptionLogger.get());
    }

    private void disconnectRuntimes() {
        for (BotRuntime runtime : runtimesByAgent.values()) {
            runtime.disconnect();
        }
        runtimesByAgent.clear();
    }

    private void handleDiscordMessage(BotConfig config, MessageCreateEvent event) {
        if (!Constants.AGENT_CHAT_DISCORD_ENABLED) {
            return;
        }
        if (event.getMessageAuthor().isBotUser()) {
            return;
        }
        if (!config.acceptsChannel(event.getChannel())) {
            return;
        }
        String text = cleanText(event.getMessageContent());
        if (text.isEmpty()) {
            return;
        }
        DiscordIntent intent = DiscordIntent.parse(config, text);
        if (!config.allowsIntent(intent)) {
            return;
        }
        String author = event.getMessageAuthor().getDisplayName();
        boolean deliverToPlayers = "player".equals(intent.toType) || "broadcast".equals(intent.toType);
        AgentChatService.INSTANCE.send("discord", author, config.agentName,
                intent.toType, intent.toName, intent.channel, intent.text, deliverToPlayers, Boolean.FALSE,
                event.getMessage().getIdAsString());
    }

    private List<BotRuntime> targetRuntimes(AgentChatService.AgentChatMessage message) {
        LinkedHashMap<String, BotRuntime> targets = new LinkedHashMap<String, BotRuntime>();
        if ("agent".equals(message.fromType)) {
            addRuntime(targets, message.fromName);
            addRuntime(targets, message.fromProfile);
        }
        if ("agent".equals(message.toType)) {
            addRuntime(targets, message.toName);
        } else if ("channel".equals(message.toType) || "broadcast".equals(message.toType)
                || "player".equals(message.fromType)) {
            for (BotRuntime runtime : runtimesByAgent.values()) {
                targets.put(runtime.config.agentKey, runtime);
            }
        }
        return new ArrayList<BotRuntime>(targets.values());
    }

    private void addRuntime(Map<String, BotRuntime> targets, String agentName) {
        BotRuntime runtime = runtimesByAgent.get(canonical(agentName));
        if (runtime != null) {
            targets.put(runtime.config.agentKey, runtime);
        }
    }

    static String formatForDiscord(AgentChatService.AgentChatMessage message) {
        StringBuilder builder = new StringBuilder();
        builder.append('[').append(message.fromType).append(':').append(message.fromName);
        if (message.toName != null && !message.toName.isEmpty()) {
            builder.append(" -> ").append(message.toType).append(':').append(message.toName);
        } else if (!"channel".equals(message.toType)) {
            builder.append(" -> ").append(message.toType);
        }
        builder.append("] ").append(message.text);
        String text = escapeDiscordMentions(builder.toString());
        return text.length() > 1900 ? text.substring(0, 1900) : text;
    }

    static String escapeDiscordMentions(String value) {
        return value == null ? "" : value.replace("@", "@\u200B");
    }

    private static String cleanText(String value) {
        if (value == null) {
            return "";
        }
        String text = value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').trim();
        return text.length() > 500 ? text.substring(0, 500) : text;
    }

    private static String canonical(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.US);
    }

    static class BotConfig {
        final String agentName;
        final String agentKey;
        final String token;
        final String channelId;
        final String channelName;
        final String channel;
        final Set<String> allowedAgentKeys;
        final Set<String> allowedPlayerKeys;
        final boolean allowBroadcast;
        final boolean valid;

        private BotConfig(String agentName, String token, String channelId, String channelName, String channel,
                Set<String> allowedAgentKeys, Set<String> allowedPlayerKeys, boolean allowBroadcast, boolean valid) {
            this.agentName = agentName;
            this.agentKey = canonical(agentName);
            this.token = token == null ? "" : token.trim();
            this.channelId = channelId == null ? "" : channelId.trim();
            this.channelName = channelName == null ? "" : channelName.trim();
            this.channel = channel == null || channel.trim().isEmpty() ? "agent" : channel.trim().toLowerCase(Locale.US);
            this.allowedAgentKeys = allowedAgentKeys;
            this.allowedPlayerKeys = allowedPlayerKeys;
            this.allowBroadcast = allowBroadcast;
            this.valid = valid;
        }

        static BotConfig fromJson(JSONObject object) {
            if (object == null) {
                return invalid();
            }
            try {
                String agent = readString(object, "agent", "profile", "name");
                String token = readString(object, "token");
                String channelId = readString(object, "channelId", "channel_id");
                String channelName = readString(object, "channelName", "channel_name");
                String channel = readString(object, "channel");
                Set<String> allowedAgents = readCanonicalSet(object, "allowedAgents", "allowed_agents");
                Set<String> allowedPlayers = readCanonicalSet(object, "allowedPlayers", "allowed_players");
                boolean allowBroadcast = readBoolean(object, "allowBroadcast", "allow_broadcast", true);
                return new BotConfig(agent, token, channelId, channelName, channel,
                        allowedAgents, allowedPlayers, allowBroadcast, true);
            } catch (IllegalArgumentException exception) {
                System.out.println("Ignoring malformed Agent Discord bot config: " + exception.getMessage());
                return invalid();
            }
        }

        private static BotConfig invalid() {
            return new BotConfig("", "", "", "", "agent",
                    new HashSet<String>(), new HashSet<String>(), true, false);
        }

        private boolean isUsable() {
            return valid && !agentKey.isEmpty() && !token.isEmpty() && (!channelId.isEmpty() || !channelName.isEmpty());
        }

        private boolean acceptsChannel(TextChannel eventChannel) {
            if (eventChannel == null) {
                return false;
            }
            if (!channelId.isEmpty()) {
                return channelId.equals(eventChannel.getIdAsString());
            }
            return eventChannel.asServerChannel().isPresent()
                    && channelName.equalsIgnoreCase(eventChannel.asServerChannel().get().getName());
        }

        boolean allowsIntent(DiscordIntent intent) {
            if (intent == null) {
                return false;
            }
            if ("channel".equals(intent.toType) || "broadcast".equals(intent.toType)) {
                return allowBroadcast;
            }
            if ("agent".equals(intent.toType)) {
                return allowedAgentKeys.isEmpty() || allowedAgentKeys.contains(canonical(intent.toName));
            }
            if ("player".equals(intent.toType)) {
                return allowedPlayerKeys.isEmpty() || allowedPlayerKeys.contains(canonical(intent.toName));
            }
            return false;
        }

        private static Set<String> readCanonicalSet(JSONObject object, String camelKey, String snakeKey) {
            HashSet<String> values = new HashSet<String>();
            String key = firstPresentKey(object, camelKey, snakeKey);
            if (key.isEmpty()) {
                return values;
            }
            Object raw = object.opt(key);
            if (raw instanceof JSONArray) {
                JSONArray array = (JSONArray) raw;
                for (int i = 0; i < array.length(); i++) {
                    Object value = array.opt(i);
                    if (!(value instanceof String)) {
                        throw new IllegalArgumentException(key + "[" + i + "] must be a string");
                    }
                    addCanonical(values, (String) value);
                }
            } else if (raw instanceof String) {
                String[] parts = ((String) raw).split(",");
                for (String part : parts) {
                    addCanonical(values, part);
                }
            } else {
                throw new IllegalArgumentException(key + " must be a string or array of strings");
            }
            if (values.isEmpty()) {
                throw new IllegalArgumentException(key + " is empty; omit it for open routing");
            }
            return values;
        }

        private static String readString(JSONObject object, String... keys) {
            String key = firstPresentKey(object, keys);
            if (key.isEmpty()) {
                return "";
            }
            Object raw = object.opt(key);
            if (!(raw instanceof String)) {
                throw new IllegalArgumentException(key + " must be a string");
            }
            return ((String) raw).trim();
        }

        private static boolean readBoolean(JSONObject object, String camelKey, String snakeKey, boolean fallback) {
            String key = firstPresentKey(object, camelKey, snakeKey);
            if (key.isEmpty()) {
                return fallback;
            }
            Object raw = object.opt(key);
            if (!(raw instanceof Boolean)) {
                throw new IllegalArgumentException(key + " must be a boolean");
            }
            return ((Boolean) raw).booleanValue();
        }

        private static String firstPresentKey(JSONObject object, String... keys) {
            for (String key : keys) {
                if (object.has(key)) {
                    return key;
                }
            }
            return "";
        }

        private static void addCanonical(Set<String> values, String value) {
            String clean = canonical(value);
            if (!clean.isEmpty()) {
                values.add(clean);
            }
        }
    }

    private static class BotRuntime {
        private final BotConfig config;
        private final DiscordApi api;

        private BotRuntime(BotConfig config, DiscordApi api) {
            this.config = config;
            this.api = api;
        }

        private String channelKey() {
            return config.channelId.isEmpty() ? config.channelName.toLowerCase(Locale.US) : config.channelId;
        }

        private void send(String text) {
            Optional<TextChannel> byId = config.channelId.isEmpty()
                    ? Optional.empty()
                    : api.getTextChannelById(config.channelId);
            if (byId.isPresent()) {
                byId.get().sendMessage(text);
                return;
            }
            if (!config.channelName.isEmpty() && !api.getTextChannelsByNameIgnoreCase(config.channelName).isEmpty()) {
                api.getTextChannelsByNameIgnoreCase(config.channelName).iterator().next().sendMessage(text);
            }
        }

        private void disconnect() {
            try {
                api.disconnect();
            } catch (RuntimeException e) {
                System.out.println("Agent Discord bot disconnect failed for " + config.agentName + ": " + e.getMessage());
            }
        }
    }

    static class DiscordIntent {
        final String toType;
        final String toName;
        final String channel;
        final String text;

        private DiscordIntent(String toType, String toName, String channel, String text) {
            this.toType = toType;
            this.toName = toName;
            this.channel = channel;
            this.text = text;
        }

        static DiscordIntent parse(BotConfig config, String text) {
            String clean = cleanText(text);
            String lower = clean.toLowerCase(Locale.US);
            if (lower.startsWith("@all ")) {
                return new DiscordIntent("broadcast", "", config.channel, clean.substring(5).trim());
            }
            if (lower.startsWith("@player:")) {
                int space = clean.indexOf(' ');
                if (space > 8) {
                    String name = clean.substring(8, space).trim();
                    return new DiscordIntent("player", name, config.channel, clean.substring(space + 1).trim());
                }
            }
            if (lower.startsWith("@agent:")) {
                int space = clean.indexOf(' ');
                if (space > 7) {
                    String name = clean.substring(7, space).trim();
                    return new DiscordIntent("agent", name, config.channel, clean.substring(space + 1).trim());
                }
            }
            return new DiscordIntent("agent", config.agentName, config.channel, clean);
        }
    }
}
