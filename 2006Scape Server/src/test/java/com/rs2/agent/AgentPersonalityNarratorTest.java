package com.rs2.agent;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import com.rs2.util.Misc;
import com.rs2.util.Stream;
import org.apollo.util.security.IsaacRandom;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class AgentPersonalityNarratorTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private File logDirectory;
    private String token;

    @Before
    public void setUp() throws Exception {
        drainQueuedActionsForTests();
        logDirectory = temporaryFolder.newFolder("agent-sessions");
        AgentSessionLog.INSTANCE.setLogDirectoryForTests(logDirectory);
        AgentPersonalityNarrator.INSTANCE.resetForTests();
        TestPlayer player = new TestPlayer(9);
        player.playerName = "narrator_tester";
        player.disconnected = false;
        player.absX = 3200;
        player.absY = 3201;
        PlayerHandler.players[9] = player;
    }

    @After
    public void tearDown() {
        drainQueuedActionsForTests();
        if (token != null) {
            AgentSessionManager.INSTANCE.invalidate(token, "test");
            token = null;
        }
        AgentPersonalityNarrator.INSTANCE.resetForTests();
        AgentSessionLog.INSTANCE.resetLogDirectoryForTests();
        PlayerHandler.players[9] = null;
    }

    @Test
    public void validatesGeneratedTextBeforeSpeechOrStorage() {
        assertEquals("", AgentPersonalityNarrator.validateGeneratedText("Codex tool log says x=3200 y=3201"));
        assertEquals("", AgentPersonalityNarrator.validateGeneratedText("Standing at 3200,3201 with hidden state."));
        assertEquals("Right. Bank first, heroics later.",
                AgentPersonalityNarrator.validateGeneratedText("Right. Bank first, heroics later."));
    }

    @Test
    public void compactLlmRequestContainsOnlyBoundedCapsuleFields() {
        JsonObject request = AgentPersonalityNarrator.compactRequestForTests("MrFish", "arrival", "Lumbridge");

        assertTrue(request.has("profile"));
        assertTrue(request.has("milestone"));
        assertTrue(request.has("facts"));
        assertTrue(request.has("styleTags"));
        assertTrue(request.has("recentSelfTalk"));
        assertTrue(request.get("facts").getAsJsonArray().size() <= 4);
        assertTrue(request.get("styleTags").getAsJsonArray().size() <= 3);
    }

    @Test
    public void repeatedRouteFrictionQueuesOneHighSignalNarrationRequest() throws Exception {
        AgentPersonalityNarrator.INSTANCE.setNowForTests(1_000_000L);
        token = AgentSessionManager.INSTANCE.registerClaim(PlayerHandler.players[9], "nonce-narrator");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-narrator");
        AgentSession session = claim.getSession();

        JsonObject args = new JsonObject();
        JsonObject failure = AgentToolService.failure("No matching object found nearby.");
        AgentSessionLog.INSTANCE.toolFailed(session, "find_nearest_object", args, failure, 5L);
        assertEquals(0, AgentPersonalityNarrator.INSTANCE.pendingCountForTests());

        AgentSessionLog.INSTANCE.toolFailed(session, "find_nearest_object", args, failure, 5L);
        assertEquals(0, AgentPersonalityNarrator.INSTANCE.pendingCountForTests());

        AgentSessionLog.INSTANCE.toolFailed(session, "find_nearest_object", args, failure, 5L);
        assertEquals(1, AgentPersonalityNarrator.INSTANCE.pendingCountForTests());

        JsonObject pending = AgentPersonalityNarrator.INSTANCE.pendingForSession(session, 3);
        JsonArray requests = pending.get("requests").getAsJsonArray();
        assertEquals("route_friction_repeated", requests.get(0).getAsJsonObject().get("milestone").getAsString());
    }

    @Test
    public void distinctSkillLevelsAreNotDedupedAsOneGenericProgressThought() throws Exception {
        AgentPersonalityNarrator.INSTANCE.setNowForTests(1_000_000L);
        token = AgentSessionManager.INSTANCE.registerClaim(PlayerHandler.players[9], "nonce-skill");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-skill");
        AgentSession session = claim.getSession();

        AgentSessionLog.INSTANCE.toolCompleted(session, "wait_until_idle_XS", new JsonObject(),
                skillResult("cooking", 21, 495), 5L);
        AgentSessionLog.INSTANCE.toolCompleted(session, "wait_until_idle_XS", new JsonObject(),
                skillResult("fishing", 26, 1080), 5L);

        File logFile = findSessionFile(logDirectory, session.getSessionId(), ".jsonl");
        String content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(2, countOccurrences(content, "\"milestone\":\"skill_progress\""));
    }

    @Test
    public void nonLevelSkillXpDoesNotQueueOrSpeakLikeALevelUp() throws Exception {
        AgentPersonalityNarrator.INSTANCE.setNowForTests(1_000_000L);
        token = AgentSessionManager.INSTANCE.registerClaim(PlayerHandler.players[9], "nonce-skill-xp");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-skill-xp");
        AgentSession session = claim.getSession();

        AgentSessionLog.INSTANCE.toolCompleted(session, "wait_until_idle_XS", new JsonObject(),
                skillXpResult("cooking", 20, 225), 5L);

        File logFile = findSessionFile(logDirectory, session.getSessionId(), ".jsonl");
        String content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(1, countOccurrences(content, "\"milestone\":\"skill_progress\""));
        assertEquals(0, countOccurrences(content, "\"event\":\"personality_spoken\""));
        assertEquals(0, AgentPersonalityNarrator.INSTANCE.pendingCountForTests());
    }

    @Test
    public void ambientChatterRepeatsOnThirtyMinuteActivePlayCadence() throws Exception {
        long start = 1_000_000L;
        AgentPersonalityNarrator.INSTANCE.setNowForTests(start);
        token = AgentSessionManager.INSTANCE.registerClaim(PlayerHandler.players[9], "nonce-ambient");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-ambient");
        AgentSession session = claim.getSession();

        for (int i = 0; i < 25; i++) {
            AgentSessionLog.INSTANCE.toolCompleted(session, "observe_state_XS", new JsonObject(),
                    AgentToolService.success("Observed compact game state."), 5L);
        }
        File logFile = findSessionFile(logDirectory, session.getSessionId(), ".jsonl");
        String content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(0, countOccurrences(content, "\"milestone\":\"ambient\""));

        AgentPersonalityNarrator.INSTANCE.setNowForTests(start
                + AgentPersonalityNarrator.AMBIENT_CHATTER_INTERVAL_MS + 1L);
        for (int i = 0; i < AgentPersonalityNarrator.AMBIENT_EVENT_INTERVAL; i++) {
            AgentSessionLog.INSTANCE.toolCompleted(session, "observe_state_XS", new JsonObject(),
                    AgentToolService.success("Observed compact game state."), 5L);
        }
        content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(1, countOccurrences(content, "\"milestone\":\"ambient\""));
        AgentActionService.INSTANCE.processPendingActions();
        content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(1, countOccurrences(content, "\"event\":\"personality_spoken\""));

        AgentPersonalityNarrator.INSTANCE.setNowForTests(start
                + (2L * AgentPersonalityNarrator.AMBIENT_CHATTER_INTERVAL_MS) + 2L);
        for (int i = 0; i < AgentPersonalityNarrator.AMBIENT_EVENT_INTERVAL; i++) {
            AgentSessionLog.INSTANCE.toolCompleted(session, "observe_state_XS", new JsonObject(),
                    AgentToolService.success("Observed compact game state."), 5L);
        }
        content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(2, countOccurrences(content, "\"milestone\":\"ambient\""));
        AgentActionService.INSTANCE.processPendingActions();
        content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(2, countOccurrences(content, "\"event\":\"personality_spoken\""));
        assertEquals(0, AgentPersonalityNarrator.INSTANCE.pendingCountForTests());
    }

    @Test
    public void ambientChatterCanFireDuringRepeatedDuplicateFriction() throws Exception {
        long start = 1_000_000L;
        AgentPersonalityNarrator.INSTANCE.setNowForTests(start);
        token = AgentSessionManager.INSTANCE.registerClaim(PlayerHandler.players[9], "nonce-ambient-friction");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-ambient-friction");
        AgentSession session = claim.getSession();
        JsonObject args = new JsonObject();
        JsonObject failure = AgentToolService.failure("No matching object found nearby.");

        for (int i = 0; i < 3; i++) {
            AgentSessionLog.INSTANCE.toolFailed(session, "find_nearest_object", args, failure, 5L);
        }

        AgentPersonalityNarrator.INSTANCE.setNowForTests(start
                + AgentPersonalityNarrator.AMBIENT_CHATTER_INTERVAL_MS + 1L);
        for (int i = 0; i < AgentPersonalityNarrator.AMBIENT_EVENT_INTERVAL; i++) {
            AgentSessionLog.INSTANCE.toolFailed(session, "find_nearest_object", args, failure, 5L);
        }

        File logFile = findSessionFile(logDirectory, session.getSessionId(), ".jsonl");
        String content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(1, countOccurrences(content, "\"milestone\":\"ambient\""));
        assertTrue(content.contains("The path keeps arguing")
                || content.contains("Patient feet")
                || content.contains("Small steps"));
    }

    @Test
    public void spokenNarrationQueuesPublicChatOnGameTickSoTheSpeakerSeesIt() throws Exception {
        AgentPersonalityNarrator.INSTANCE.setNowForTests(1_000_000L);
        token = AgentSessionManager.INSTANCE.registerClaim(PlayerHandler.players[9], "nonce-spoken");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-spoken");
        AgentSession session = claim.getSession();
        TestPlayer player = (TestPlayer) PlayerHandler.players[9];

        AgentSessionLog.INSTANCE.toolCompleted(session, "wait_until_idle_XS", new JsonObject(),
                skillResult("cooking", 21, 495), 5L);

        assertFalse(player.forcedChatUpdateRequired);
        assertFalse(player.isChatTextUpdateRequired());
        assertEquals(1, AgentActionService.INSTANCE.pendingActionCountForTests());
        AgentActionService.INSTANCE.processPendingActions();

        assertFalse(player.forcedChatUpdateRequired);
        assertTrue(player.isChatTextUpdateRequired());
        assertTrue(player.isChatTextEchoToSelfRequired());
        assertEquals("a little better. that is how the grind sneaks up on you.",
                Misc.textUnpack(player.getChatText(), player.getChatTextSize()));
        player.appendedPublicChat = false;
        Stream outbound = new Stream(new byte[4096]);
        outbound.packetEncryption = new IsaacRandom(new int[] {0, 0, 0, 0});
        new PlayerHandler().updatePlayer(player, outbound);
        assertTrue(player.appendedPublicChat);
        player.clearUpdateFlags();
        assertFalse(player.isChatTextEchoToSelfRequired());
        File logFile = findSessionFile(logDirectory, session.getSessionId(), ".jsonl");
        String content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertEquals(1, countOccurrences(content, "\"event\":\"personality_spoken\""));
    }

    private JsonObject skillResult(String skill, int level, int xpGained) {
        JsonObject result = AgentToolService.success("Observed current player state.");
        JsonArray changes = new JsonArray();
        JsonObject change = new JsonObject();
        change.addProperty("skill", skill);
        change.addProperty("baseBefore", level - 1);
        change.addProperty("baseAfter", level);
        change.addProperty("currentBefore", level - 1);
        change.addProperty("currentAfter", level);
        change.addProperty("xpBefore", 1000);
        change.addProperty("xpAfter", 1000 + xpGained);
        change.addProperty("xpGained", xpGained);
        changes.add(change);
        result.add("skillChanges", changes);
        return result;
    }

    private JsonObject skillXpResult(String skill, int level, int xpGained) {
        JsonObject result = AgentToolService.success("Observed current player state.");
        JsonArray changes = new JsonArray();
        JsonObject change = new JsonObject();
        change.addProperty("skill", skill);
        change.addProperty("baseBefore", level);
        change.addProperty("baseAfter", level);
        change.addProperty("baseGained", 0);
        change.addProperty("currentBefore", level);
        change.addProperty("currentAfter", level);
        change.addProperty("xpBefore", 1000);
        change.addProperty("xpAfter", 1000 + xpGained);
        change.addProperty("xpGained", xpGained);
        changes.add(change);
        result.add("skillChanges", changes);
        return result;
    }

    private File findSessionFile(File directory, String sessionId, String extension) {
        File[] files = directory.listFiles();
        if (files == null) {
            return null;
        }
        for (File file : files) {
            if (file.isDirectory()) {
                File found = findSessionFile(file, sessionId, extension);
                if (found != null) {
                    return found;
                }
            } else if ((sessionId + extension).equals(file.getName())) {
                return file;
            }
        }
        return null;
    }

    private void drainQueuedActionsForTests() {
        for (int i = 0; i < 20 && AgentActionService.INSTANCE.pendingActionCountForTests() > 0; i++) {
            AgentActionService.INSTANCE.processPendingActions();
        }
    }

    private int countOccurrences(String text, String needle) {
        int count = 0;
        int offset = 0;
        while (text != null && needle != null && needle.length() > 0) {
            int found = text.indexOf(needle, offset);
            if (found < 0) {
                return count;
            }
            count++;
            offset = found + needle.length();
        }
        return count;
    }

    private static class TestPlayer extends Player {
        private boolean appendedPublicChat;

        private TestPlayer(int playerId) {
            super(playerId);
        }

        @Override
        protected void appendPlayerChatText(Stream stream) {
            appendedPublicChat = true;
            super.appendPlayerChatText(stream);
        }
    }
}
