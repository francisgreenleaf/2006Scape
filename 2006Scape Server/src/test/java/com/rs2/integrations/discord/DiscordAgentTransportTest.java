package com.rs2.integrations.discord;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicInteger;

import org.javacord.api.DiscordApi;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

import com.google.gson.JsonObject;
import com.rs2.Constants;

public class DiscordAgentTransportTest {

    private boolean previousDiscordEnabled;

    @Before
    public void setUp() {
        previousDiscordEnabled = Constants.AGENT_CHAT_DISCORD_ENABLED;
        Constants.AGENT_CHAT_DISCORD_ENABLED = true;
        DiscordAgentTransport.INSTANCE.configure(null);
    }

    @After
    public void tearDown() {
        Constants.AGENT_CHAT_DISCORD_ENABLED = previousDiscordEnabled;
        DiscordAgentTransport.INSTANCE.configure(null);
    }

    @Test
    public void configureKeepsOnlyUsableAgentBots() {
        JSONArray configs = new JSONArray()
                .put(new JSONObject()
                        .put("agent", "MrFlame")
                        .put("token", "secret-token")
                        .put("channelId", "123456"))
                .put(new JSONObject()
                        .put("agent", "NoToken")
                        .put("channelId", "654321"))
                .put(new JSONObject()
                        .put("agent", "NoChannel")
                        .put("token", "secret-token-2"));

        DiscordAgentTransport.INSTANCE.configure(configs);

        assertEquals(1, DiscordAgentTransport.INSTANCE.configuredCount());
        assertEquals(0, DiscordAgentTransport.INSTANCE.connectedCount());
    }

    @Test
    public void configureIgnoresDuplicateAgentBots() {
        JSONArray configs = new JSONArray()
                .put(new JSONObject()
                        .put("agent", "MrFlame")
                        .put("token", "secret-token")
                        .put("channelId", "123456"))
                .put(new JSONObject()
                        .put("agent", "mrflame")
                        .put("token", "other-secret-token")
                        .put("channelId", "654321"));

        DiscordAgentTransport.INSTANCE.configure(configs);

        assertEquals(1, DiscordAgentTransport.INSTANCE.configuredCount());
    }

    @Test
    public void configureIgnoresMalformedAllowListBotConfig() {
        JSONArray configs = new JSONArray()
                .put(new JSONObject()
                        .put("agent", "MrFlame")
                        .put("token", "secret-token")
                        .put("channelId", "123456")
                        .put("allowedAgents", new JSONObject().put("MrGem", true)));

        DiscordAgentTransport.INSTANCE.configure(configs);

        assertEquals(0, DiscordAgentTransport.INSTANCE.configuredCount());
    }

    @Test
    public void configureIgnoresEmptyExplicitAllowListBotConfig() {
        JSONArray configs = new JSONArray()
                .put(new JSONObject()
                        .put("agent", "MrFlame")
                        .put("token", "secret-token")
                        .put("channelId", "123456")
                        .put("allowedPlayers", new JSONArray()));

        DiscordAgentTransport.INSTANCE.configure(configs);

        assertEquals(0, DiscordAgentTransport.INSTANCE.configuredCount());
    }

    @Test
    public void configureIgnoresNonBooleanBroadcastFlagBotConfig() {
        JSONArray configs = new JSONArray()
                .put(new JSONObject()
                        .put("agent", "MrFlame")
                        .put("token", "secret-token")
                        .put("channelId", "123456")
                        .put("allowBroadcast", "false"));

        DiscordAgentTransport.INSTANCE.configure(configs);

        assertEquals(0, DiscordAgentTransport.INSTANCE.configuredCount());
    }

    @Test
    public void statusDoesNotExposeDiscordTokens() {
        DiscordAgentTransport.INSTANCE.configure(new JSONArray()
                .put(new JSONObject()
                        .put("agent", "MrFlame")
                        .put("token", "very-secret-token")
                        .put("channelId", "123456")));

        JsonObject status = DiscordAgentTransport.INSTANCE.status();

        assertEquals(true, status.get("enabled").getAsBoolean());
        assertEquals(1, status.get("configuredBots").getAsInt());
        assertFalse(status.toString().contains("very-secret-token"));
    }

    @Test
    public void configureDisconnectsExistingBotRuntimesBeforeReloading() throws Exception {
        DiscordAgentTransport.BotConfig config = DiscordAgentTransport.BotConfig.fromJson(new JSONObject()
                .put("agent", "MrFlame")
                .put("token", "secret-token")
                .put("channelId", "123456"));
        AtomicInteger disconnects = new AtomicInteger();
        DiscordApi api = proxyDiscordApi(disconnects);
        Object runtime = botRuntime(config, api);

        runtimeMap().put(config.agentKey, runtime);
        assertEquals(1, DiscordAgentTransport.INSTANCE.connectedCount());

        DiscordAgentTransport.INSTANCE.configure(null);

        assertEquals(1, disconnects.get());
        assertEquals(0, DiscordAgentTransport.INSTANCE.connectedCount());
        assertEquals(0, DiscordAgentTransport.INSTANCE.configuredCount());
    }

    @Test
    public void discordIntentRoutesPrefixes() {
        DiscordAgentTransport.BotConfig config = DiscordAgentTransport.BotConfig.fromJson(new JSONObject()
                .put("agent", "MrFlame")
                .put("token", "secret-token")
                .put("channelId", "123456")
                .put("channel", "ops"));

        DiscordAgentTransport.DiscordIntent player = DiscordAgentTransport.DiscordIntent.parse(config,
                "@player:MrGem hello player");
        DiscordAgentTransport.DiscordIntent agent = DiscordAgentTransport.DiscordIntent.parse(config,
                "@agent:MrWood hello agent");
        DiscordAgentTransport.DiscordIntent all = DiscordAgentTransport.DiscordIntent.parse(config,
                "@all hello channel");
        DiscordAgentTransport.DiscordIntent plain = DiscordAgentTransport.DiscordIntent.parse(config,
                "hello flame");

        assertEquals("player", player.toType);
        assertEquals("MrGem", player.toName);
        assertEquals("hello player", player.text);
        assertEquals("ops", player.channel);

        assertEquals("agent", agent.toType);
        assertEquals("MrWood", agent.toName);
        assertEquals("hello agent", agent.text);

        assertEquals("broadcast", all.toType);
        assertEquals("", all.toName);
        assertEquals("hello channel", all.text);

        assertEquals("agent", plain.toType);
        assertEquals("MrFlame", plain.toName);
        assertEquals("hello flame", plain.text);
    }

    @Test
    public void discordFormattingEscapesMentions() {
        String formatted = DiscordAgentTransport.escapeDiscordMentions(
                "[agent:MrFlame] hello @everyone @here <@123456> <@&654321>");

        assertFalse(formatted.contains("@everyone"));
        assertFalse(formatted.contains("@here"));
        assertFalse(formatted.contains("<@123456>"));
        assertFalse(formatted.contains("<@&654321>"));
        assertEquals(true, formatted.contains("@\u200Beveryone"));
        assertEquals(true, formatted.contains("@\u200Bhere"));
    }

    @Test
    public void botConfigCanRestrictDiscordTargets() {
        DiscordAgentTransport.BotConfig config = DiscordAgentTransport.BotConfig.fromJson(new JSONObject()
                .put("agent", "MrFlame")
                .put("token", "secret-token")
                .put("channelId", "123456")
                .put("allowedAgents", new JSONArray().put("MrFlame").put("MrGem"))
                .put("allowedPlayers", "MrFlame, MrGem")
                .put("allowBroadcast", false));

        DiscordAgentTransport.DiscordIntent allowedAgent = DiscordAgentTransport.DiscordIntent.parse(config,
                "@agent:MrGem hello");
        DiscordAgentTransport.DiscordIntent blockedAgent = DiscordAgentTransport.DiscordIntent.parse(config,
                "@agent:MrWood hello");
        DiscordAgentTransport.DiscordIntent allowedPlayer = DiscordAgentTransport.DiscordIntent.parse(config,
                "@player:MrGem hello");
        DiscordAgentTransport.DiscordIntent blockedPlayer = DiscordAgentTransport.DiscordIntent.parse(config,
                "@player:MrWood hello");
        DiscordAgentTransport.DiscordIntent blockedAll = DiscordAgentTransport.DiscordIntent.parse(config,
                "@all hello");

        assertEquals(true, config.allowsIntent(allowedAgent));
        assertEquals(false, config.allowsIntent(blockedAgent));
        assertEquals(true, config.allowsIntent(allowedPlayer));
        assertEquals(false, config.allowsIntent(blockedPlayer));
        assertEquals(false, config.allowsIntent(blockedAll));
    }

    @Test
    public void botConfigDefaultsToCompatibleOpenRouting() {
        DiscordAgentTransport.BotConfig config = DiscordAgentTransport.BotConfig.fromJson(new JSONObject()
                .put("agent", "MrFlame")
                .put("token", "secret-token")
                .put("channelId", "123456"));

        assertEquals(true, config.allowsIntent(DiscordAgentTransport.DiscordIntent.parse(config,
                "@agent:Anyone hello")));
        assertEquals(true, config.allowsIntent(DiscordAgentTransport.DiscordIntent.parse(config,
                "@player:Anyone hello")));
        assertEquals(true, config.allowsIntent(DiscordAgentTransport.DiscordIntent.parse(config,
                "@all hello")));
    }

    private static DiscordApi proxyDiscordApi(final AtomicInteger disconnects) {
        return (DiscordApi) Proxy.newProxyInstance(
                DiscordApi.class.getClassLoader(),
                new Class<?>[] { DiscordApi.class },
                (proxy, method, args) -> {
                    if ("disconnect".equals(method.getName())) {
                        disconnects.incrementAndGet();
                        return null;
                    }
                    if ("toString".equals(method.getName())) {
                        return "test-discord-api";
                    }
                    Class<?> returnType = method.getReturnType();
                    if (Boolean.TYPE.equals(returnType)) {
                        return false;
                    }
                    if (Integer.TYPE.equals(returnType)) {
                        return 0;
                    }
                    if (Long.TYPE.equals(returnType)) {
                        return 0L;
                    }
                    return null;
                });
    }

    private static Object botRuntime(DiscordAgentTransport.BotConfig config, DiscordApi api) throws Exception {
        Class<?> runtimeClass = Class.forName("com.rs2.integrations.discord.DiscordAgentTransport$BotRuntime");
        Constructor<?> constructor = runtimeClass.getDeclaredConstructor(
                DiscordAgentTransport.BotConfig.class,
                DiscordApi.class);
        constructor.setAccessible(true);
        return constructor.newInstance(config, api);
    }

    @SuppressWarnings("unchecked")
    private static ConcurrentMap<String, Object> runtimeMap() throws Exception {
        Field field = DiscordAgentTransport.class.getDeclaredField("runtimesByAgent");
        field.setAccessible(true);
        return (ConcurrentMap<String, Object>) field.get(DiscordAgentTransport.INSTANCE);
    }
}
