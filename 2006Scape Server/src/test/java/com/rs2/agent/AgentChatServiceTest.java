package com.rs2.agent;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.rs2.Constants;
import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import com.rs2.net.PacketSender;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class AgentChatServiceTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    @Test
    public void channelMessagesAreVisibleToClaimedProfiles() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        Player gem = player("MrGem");

        AgentChatService.AgentChatMessage sent = service.sendFromPlayerCommand(flame, "hello agents");
        JsonArray messages = service.recentFor(gem, 0L, "agent", 10);

        assertEquals(1, messages.size());
        assertEquals(sent.id, messages.get(0).getAsJsonObject().get("id").getAsLong());
        assertEquals("hello agents", messages.get(0).getAsJsonObject().get("text").getAsString());
    }

    @Test
    public void playerCommandCanAddressSpecificAgent() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        Player gem = player("MrGem");
        Player wood = player("MrWood");

        AgentChatService.AgentChatMessage sent = service.sendFromPlayerCommand(flame, "@agent:MrGem hello gem");

        assertEquals("player", sent.fromType);
        assertEquals("agent", sent.toType);
        assertEquals("MrGem", sent.toName);
        assertEquals("hello gem", sent.text);
        assertEquals(1, service.recentFor(gem, 0L, "agent", 10).size());
        assertEquals(0, service.recentFor(wood, 0L, "agent", 10).size());
    }

    @Test
    public void playerCommandCanAddressSpecificOnlinePlayer() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");

        AgentChatService.AgentChatMessage sent = service.sendFromPlayerCommand(flame, "@player:MrGem hello player");

        assertEquals("player", sent.fromType);
        assertEquals("player", sent.toType);
        assertEquals("MrGem", sent.toName);
        assertEquals("hello player", sent.text);
        assertEquals(1, service.pendingPlayerDeliveryCount());
    }

    @Test
    public void playerCommandCanSelectChannel() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        Player gem = player("MrGem");

        AgentChatService.AgentChatMessage sent = service.sendFromPlayerCommand(flame, "#ops hello ops");

        assertEquals("channel", sent.toType);
        assertEquals("ops", sent.channel);
        assertEquals("hello ops", sent.text);
        assertEquals(1, service.recentFor(gem, 0L, "ops", 10).size());
        assertEquals(0, service.recentFor(gem, 0L, "agent", 10).size());
    }

    @Test
    public void playerCommandAllPrefixUsesSharedAgentChannel() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        Player gem = player("MrGem");

        AgentChatService.AgentChatMessage sent = service.sendFromPlayerCommand(flame, "@all hello all");

        assertEquals("broadcast", sent.toType);
        assertEquals("agent", sent.channel);
        assertEquals("hello all", sent.text);
        assertEquals(1, service.pendingPlayerDeliveryCount());
        assertEquals(1, service.recentFor(gem, 0L, "agent", 10).size());
    }

    @Test
    public void directAgentMessagesAreVisibleOnlyToSenderAndTarget() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        Player gem = player("MrGem");
        Player wood = player("Mrwood");
        JsonObject args = new JsonObject();
        args.addProperty("message", "need help at bank");
        args.addProperty("toType", "agent");
        args.addProperty("to", "MrGem");

        service.sendFromAgent(flame, args);

        assertEquals(1, service.recentFor(flame, 0L, "agent", 10).size());
        assertEquals(1, service.recentFor(gem, 0L, "agent", 10).size());
        assertEquals(0, service.recentFor(wood, 0L, "agent", 10).size());
    }

    @Test
    public void discordDirectMessagesAreVisibleToSourceProfileAndTarget() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        Player gem = player("MrGem");
        Player wood = player("MrWood");

        AgentChatService.AgentChatMessage sent = service.send(
                "discord", "VerifierUser", "MrFlame", "agent", "MrGem",
                "agent", "discord relay", false, Boolean.FALSE);

        assertEquals(1, service.recentFor(flame, 0L, "agent", 10).size());
        assertEquals(1, service.recentFor(gem, 0L, "agent", 10).size());
        assertEquals(0, service.recentFor(wood, 0L, "agent", 10).size());
        assertEquals(1, service.unreadCountFor(flame, sent.id - 1, "agent"));
    }

    @Test
    public void agentAliasDefaultsToAgentTargetType() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        Player gem = player("MrGem");
        Player wood = player("Mrwood");
        JsonObject args = new JsonObject();
        args.addProperty("message", "agent alias target");
        args.addProperty("agent", "MrGem");

        AgentChatService.AgentChatMessage sent = service.sendFromAgent(flame, args);

        assertEquals("agent", sent.toType);
        assertEquals("MrGem", sent.toName);
        assertEquals(1, service.recentFor(gem, 0L, "agent", 10).size());
        assertEquals(0, service.recentFor(wood, 0L, "agent", 10).size());
    }

    @Test
    public void playerAliasDefaultsToPlayerTargetTypeAndQueuesDelivery() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        JsonObject args = new JsonObject();
        args.addProperty("message", "player alias target");
        args.addProperty("player", "MrGem");

        AgentChatService.AgentChatMessage sent = service.sendFromAgent(flame, args);

        assertEquals("player", sent.toType);
        assertEquals("MrGem", sent.toName);
        assertEquals(1, service.pendingPlayerDeliveryCount());
    }

    @Test(expected = IllegalArgumentException.class)
    public void agentAndPlayerShortcutsAreMutuallyExclusive() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        JsonObject args = new JsonObject();
        args.addProperty("message", "ambiguous target");
        args.addProperty("agent", "MrGem");
        args.addProperty("player", "MrWood");

        service.sendFromAgent(flame, args);
    }

    @Test(expected = IllegalArgumentException.class)
    public void shortcutTargetCannotBeCombinedWithGenericTargetFields() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        JsonObject args = new JsonObject();
        args.addProperty("message", "ambiguous target");
        args.addProperty("agent", "MrGem");
        args.addProperty("to", "MrWood");

        service.sendFromAgent(flame, args);
    }

    @Test
    public void alsoPlayersAliasQueuesDirectPlayerDelivery() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        JsonObject args = new JsonObject();
        args.addProperty("message", "player alias delivery");
        args.addProperty("toType", "player");
        args.addProperty("to", "MrGem");
        args.addProperty("alsoPlayers", true);

        AgentChatService.AgentChatMessage sent = service.sendFromAgent(flame, args);

        assertEquals("player", sent.toType);
        assertEquals("MrGem", sent.toName);
        assertEquals(1, service.pendingPlayerDeliveryCount());
    }

    @Test(expected = IllegalArgumentException.class)
    public void explicitInvalidTargetTypeIsRejectedInsteadOfBecomingChannelMessage() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        JsonObject args = new JsonObject();
        args.addProperty("message", "should stay private");
        args.addProperty("toType", "agnt");
        args.addProperty("to", "MrGem");

        service.sendFromAgent(flame, args);
    }

    @Test(expected = IllegalArgumentException.class)
    public void directAgentTargetRequiresName() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        JsonObject args = new JsonObject();
        args.addProperty("message", "missing target");
        args.addProperty("toType", "agent");

        service.sendFromAgent(flame, args);
    }

    @Test(expected = IllegalArgumentException.class)
    public void directPlayerTargetRequiresName() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        JsonObject args = new JsonObject();
        args.addProperty("message", "missing player");
        args.addProperty("toType", "player");

        service.sendFromAgent(flame, args);
    }

    @Test(expected = IllegalArgumentException.class)
    public void playerDeliveryFlagRequiresPlayerOrBroadcastTarget() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        JsonObject args = new JsonObject();
        args.addProperty("message", "bad delivery target");
        args.addProperty("channel", "agent");
        args.addProperty("deliverToPlayers", true);

        service.sendFromAgent(flame, args);
    }

    @Test
    public void statusCountsUnreadSinceId() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        AgentChatService.AgentChatMessage first = service.sendFromPlayerCommand(flame, "first");
        service.sendFromPlayerCommand(flame, "second");

        assertEquals(1, service.unreadCountFor(flame, first.id, "agent"));
        assertTrue(service.lastId() > first.id);
    }

    @Test
    public void directPlayerMessagesQueueUntilTickDeliveryRuns() {
        AgentChatService service = new AgentChatService();
        Player gem = player("MrGem");
        PlayerHandler.players[1] = gem;
        try {
            AgentChatService.AgentChatMessage sent = service.send(
                    "discord", "DiscordUser", "MrFlame", "player", "MrGem", "agent", "hello player", true);

            assertEquals(0, sent.deliveredTo.size());
            assertEquals(1, service.pendingPlayerDeliveryCount());

            assertEquals(1, service.processPendingPlayerDeliveries());
            assertEquals(1, sent.deliveredTo.size());
            assertEquals("MrGem", sent.deliveredTo.get(0));
            assertEquals(0, service.pendingPlayerDeliveryCount());
        } finally {
            PlayerHandler.players[1] = null;
        }
    }

    @Test
    public void directPlayerMessagesRecordUndeliveredTargetWhenPlayerOffline() {
        AgentChatService service = new AgentChatService();

        AgentChatService.AgentChatMessage sent = service.send(
                "agent", "MrFlame", "MrFlame", "player", "MrGem", "agent", "offline hello", true);

        assertEquals(1, service.pendingPlayerDeliveryCount());
        assertEquals(1, service.processPendingPlayerDeliveries());
        assertEquals(0, sent.deliveredTo.size());
        assertEquals(1, sent.undeliveredTo.size());
        assertEquals("MrGem", sent.undeliveredTo.get(0));
        assertEquals(0, service.pendingPlayerDeliveryCount());

        JsonArray messages = service.recentFor(player("MrFlame"), 0L, "agent", 10);
        JsonObject envelope = messages.get(0).getAsJsonObject();
        assertEquals(0, envelope.get("deliveredTo").getAsJsonArray().size());
        assertEquals("MrGem", envelope.get("undeliveredTo").getAsJsonArray().get(0).getAsString());
    }

    @Test
    public void cleansTextNamesAndChannelsBeforeStorage() {
        AgentChatService service = new AgentChatService();

        AgentChatService.AgentChatMessage sent = service.send(
                "agent",
                "MrFlame\nWithControlCharactersAndAnOverlongName",
                "MrFlame",
                "channel",
                "",
                "Ops Room/#1 With Spaces",
                "hello\n\tagents\u0007",
                false);

        assertEquals("hello agents", sent.text);
        assertEquals("ops-room-1-with-spaces", sent.channel);
        assertEquals(32, sent.fromName.length());
    }

    @Test
    public void truncatesOverlongChatMessages() {
        AgentChatService service = new AgentChatService();
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < 600; i++) {
            builder.append('x');
        }

        AgentChatService.AgentChatMessage sent = service.send(
                "agent", "MrFlame", "MrFlame", "channel", "", "agent", builder.toString(), false);

        assertEquals(500, sent.text.length());
    }

    @Test
    public void backlogKeepsOnlyRecentBoundedMessages() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");

        for (int i = 0; i < 260; i++) {
            service.sendFromPlayerCommand(flame, "message " + i);
        }

        JsonArray messages = service.recentFor(flame, 0L, "agent", 50);
        assertEquals(250, service.backlogSize());
        assertEquals(50, messages.size());
        assertEquals("message 210", messages.get(0).getAsJsonObject().get("text").getAsString());
        assertEquals("message 259", messages.get(49).getAsJsonObject().get("text").getAsString());
    }

    @Test
    public void pendingPlayerDeliveriesAreBounded() {
        AgentChatService service = new AgentChatService();

        for (int i = 0; i < 260; i++) {
            service.send("agent", "MrFlame", "MrFlame", "player", "MrGem", "agent", "direct " + i, true);
        }

        assertEquals(250, service.pendingPlayerDeliveryCount());
    }

    @Test
    public void playerDeliveryFailureRecordsUndeliveredAndContinuesDrain() {
        AgentChatService service = new AgentChatService();
        Player broken = throwingPlayer(2, "MrBroken");
        Player gem = player("MrGem");
        PlayerHandler.players[2] = broken;
        PlayerHandler.players[3] = gem;
        try {
            AgentChatService.AgentChatMessage failed = service.send(
                    "agent", "MrFlame", "MrFlame", "player", "MrBroken", "agent", "first", true);
            AgentChatService.AgentChatMessage delivered = service.send(
                    "agent", "MrFlame", "MrFlame", "player", "MrGem", "agent", "second", true);

            assertEquals(2, service.pendingPlayerDeliveryCount());
            assertEquals(2, service.processPendingPlayerDeliveries());

            assertEquals(0, failed.deliveredTo.size());
            assertEquals(1, failed.undeliveredTo.size());
            assertEquals("MrBroken", failed.undeliveredTo.get(0));
            assertEquals(1, delivered.deliveredTo.size());
            assertEquals("MrGem", delivered.deliveredTo.get(0));
            assertEquals(0, service.pendingPlayerDeliveryCount());
        } finally {
            PlayerHandler.players[2] = null;
            PlayerHandler.players[3] = null;
        }
    }

    @Test
    public void optInChatLogWritesSanitizedJsonlEnvelope() throws Exception {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        boolean previousLogEnabled = Constants.AGENT_CHAT_LOG_ENABLED;
        File logRoot = temporaryFolder.newFolder("agent-chat-logs");
        service.setLogDirectoryForTests(logRoot);
        try {
            Constants.AGENT_CHAT_LOG_ENABLED = true;
            service.sendFromPlayerCommand(flame, "#Ops-Room hello\nagents");

            File[] dayDirectories = logRoot.listFiles();
            assertEquals(1, dayDirectories.length);
            File logFile = new File(dayDirectories[0], "agent-chat.jsonl");
            assertTrue(logFile.isFile());
            List<String> lines = Files.readAllLines(logFile.toPath(), StandardCharsets.UTF_8);
            assertEquals(1, lines.size());
            JsonObject entry = new JsonParser().parse(lines.get(0)).getAsJsonObject();
            assertEquals(1, entry.get("schemaVersion").getAsInt());
            assertEquals("agent_chat_message", entry.get("event").getAsString());
            assertEquals("player", entry.get("fromType").getAsString());
            assertEquals("MrFlame", entry.get("fromName").getAsString());
            assertEquals("ops-room", entry.get("channel").getAsString());
            assertEquals("hello agents", entry.get("text").getAsString());
        } finally {
            Constants.AGENT_CHAT_LOG_ENABLED = previousLogEnabled;
            service.resetLogDirectoryForTests();
        }
    }

    @Test
    public void playerDeliveryDrainWritesDeliveryStatusAuditEvent() throws Exception {
        AgentChatService service = new AgentChatService();
        Player gem = player("MrGem");
        PlayerHandler.players[1] = gem;
        boolean previousLogEnabled = Constants.AGENT_CHAT_LOG_ENABLED;
        File logRoot = temporaryFolder.newFolder("agent-chat-delivery-logs");
        service.setLogDirectoryForTests(logRoot);
        try {
            Constants.AGENT_CHAT_LOG_ENABLED = true;
            AgentChatService.AgentChatMessage sent = service.send(
                    "agent", "MrFlame", "MrFlame", "player", "MrGem", "agent", "direct delivery proof", true);

            assertEquals(1, service.processPendingPlayerDeliveries());
            assertEquals(1, sent.deliveredTo.size());

            File[] dayDirectories = logRoot.listFiles();
            assertEquals(1, dayDirectories.length);
            File logFile = new File(dayDirectories[0], "agent-chat.jsonl");
            List<String> lines = Files.readAllLines(logFile.toPath(), StandardCharsets.UTF_8);
            assertEquals(2, lines.size());
            JsonObject messageEvent = new JsonParser().parse(lines.get(0)).getAsJsonObject();
            JsonObject deliveryEvent = new JsonParser().parse(lines.get(1)).getAsJsonObject();
            assertEquals("agent_chat_message", messageEvent.get("event").getAsString());
            assertEquals("agent_chat_player_delivery", deliveryEvent.get("event").getAsString());
            assertEquals(sent.id, deliveryEvent.get("id").getAsLong());
            assertEquals("MrGem", deliveryEvent.get("deliveredTo").getAsJsonArray().get(0).getAsString());
            assertEquals(0, deliveryEvent.get("undeliveredTo").getAsJsonArray().size());
        } finally {
            Constants.AGENT_CHAT_LOG_ENABLED = previousLogEnabled;
            service.resetLogDirectoryForTests();
            PlayerHandler.players[1] = null;
        }
    }

    @Test
    public void knownDiscordSourceMetadataIsIncludedInRecentMessagesAndLogs() throws Exception {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");
        boolean previousLogEnabled = Constants.AGENT_CHAT_LOG_ENABLED;
        File logRoot = temporaryFolder.newFolder("agent-chat-discord-logs");
        service.setLogDirectoryForTests(logRoot);
        try {
            Constants.AGENT_CHAT_LOG_ENABLED = true;
            AgentChatService.AgentChatMessage sent = service.send(
                    "discord", "VerifierUser", "MrFlame", "agent", "MrFlame",
                    "agent", "human discord marker", false, Boolean.FALSE, "123456789012345678");

            JsonObject recent = service.recentFor(flame, 0L, "agent", 10).get(0).getAsJsonObject();
            assertEquals(sent.id, recent.get("id").getAsLong());
            assertTrue(recent.has("fromBot"));
            assertFalse(recent.get("fromBot").getAsBoolean());
            assertEquals("123456789012345678", recent.get("discordMessageId").getAsString());

            File[] dayDirectories = logRoot.listFiles();
            assertEquals(1, dayDirectories.length);
            File logFile = new File(dayDirectories[0], "agent-chat.jsonl");
            List<String> lines = Files.readAllLines(logFile.toPath(), StandardCharsets.UTF_8);
            assertEquals(1, lines.size());
            JsonObject entry = new JsonParser().parse(lines.get(0)).getAsJsonObject();
            assertEquals("discord", entry.get("fromType").getAsString());
            assertTrue(entry.has("fromBot"));
            assertFalse(entry.get("fromBot").getAsBoolean());
            assertEquals("123456789012345678", entry.get("discordMessageId").getAsString());
        } finally {
            Constants.AGENT_CHAT_LOG_ENABLED = previousLogEnabled;
            service.resetLogDirectoryForTests();
        }
    }

    @Test
    public void unknownSourceMetadataIsOmittedFromRecentMessages() {
        AgentChatService service = new AgentChatService();
        Player flame = player("MrFlame");

        service.sendFromPlayerCommand(flame, "plain player message");

        JsonObject recent = service.recentFor(flame, 0L, "agent", 10).get(0).getAsJsonObject();
        assertFalse(recent.has("fromBot"));
        assertFalse(recent.has("discordMessageId"));
    }

    private static Player player(String name) {
        Player player = new TestPlayer(0);
        player.playerName = name;
        player.disconnected = false;
        player.isActive = true;
        return player;
    }

    private static Player throwingPlayer(int playerId, String name) {
        Player player = new ThrowingPlayer(playerId);
        player.playerName = name;
        player.disconnected = false;
        player.isActive = true;
        return player;
    }

    private static class TestPlayer extends Player {
        private TestPlayer(int playerId) {
            super(playerId);
        }
    }

    private static class ThrowingPlayer extends Player {
        private final PacketSender throwingPacketSender = new PacketSender(this) {
            @Override
            public PacketSender sendMessage(String s) {
                throw new RuntimeException("delivery failed");
            }
        };

        private ThrowingPlayer(int playerId) {
            super(playerId);
        }

        @Override
        public PacketSender getPacketSender() {
            return throwingPacketSender;
        }
    }
}
