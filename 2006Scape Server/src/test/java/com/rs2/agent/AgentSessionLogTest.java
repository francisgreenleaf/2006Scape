package com.rs2.agent;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import com.google.gson.JsonObject;
import com.rs2.game.players.Player;
import com.rs2.game.players.PlayerHandler;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

public class AgentSessionLogTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private File logDirectory;
    private String token;

    @Before
    public void setUp() throws Exception {
        logDirectory = temporaryFolder.newFolder("agent-sessions");
        AgentSessionLog.INSTANCE.setLogDirectoryForTests(logDirectory);
        TestPlayer player = new TestPlayer(8);
        player.playerName = "logger_tester";
        player.disconnected = false;
        player.absX = 3200;
        player.absY = 3201;
        PlayerHandler.players[8] = player;
    }

    @After
    public void tearDown() {
        if (token != null) {
            AgentSessionManager.INSTANCE.invalidate(token, "test");
            token = null;
        }
        AgentSessionLog.INSTANCE.resetLogDirectoryForTests();
        PlayerHandler.players[8] = null;
    }

    @Test
    public void recordsSessionAndToolEventsWithoutSessionToken() throws Exception {
        token = AgentSessionManager.INSTANCE.registerClaim(PlayerHandler.players[8], "nonce-log");
        AgentSessionManager.ClaimResult claim = AgentSessionManager.INSTANCE.consumeClaim("nonce-log");
        AgentSession session = claim.getSession();

        JsonObject arguments = new JsonObject();
        arguments.addProperty("token", "should-not-be-written");
        arguments.addProperty("apiKey", "sk-raw-sensitive-api-key");
        arguments.addProperty("name", "goblin");
        JsonObject result = AgentToolService.success("Found nearest NPC.");
        JsonObject failure = AgentToolService.failure("Not enough inventory space to pick up bones.");
        JsonObject task = new JsonObject();
        task.addProperty("command", "find a goblin");
        AgentSessionLog.INSTANCE.clientEvent(session, "turn_requested", task);
        AgentSessionLog.INSTANCE.toolCompleted(session, "find_nearest_npc", arguments, result, 15L);
        AgentSessionLog.INSTANCE.toolFailed(session, "pickup_ground_item", arguments, failure, 20L);
        JsonObject assistant = new JsonObject();
        assistant.addProperty("text", "Found the nearest goblin.");
        AgentSessionLog.INSTANCE.clientEvent(session, "assistant_message", assistant);

        File logFile = findSessionFile(logDirectory, session.getSessionId(), ".jsonl");
        assertNotNull(logFile);
        String content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertTrue(content.contains("\"event\":\"session_registered\""));
        assertTrue(content.contains("\"event\":\"session_claimed\""));
        assertTrue(content.contains("\"event\":\"tool_completed\""));
        assertTrue(content.contains("\"event\":\"tool_failed\""));
        assertTrue(content.contains("\"tool\":\"find_nearest_npc\""));
        assertTrue(content.contains("\"token\":\"[redacted]\""));
        assertTrue(content.contains("\"apiKey\":\"[redacted]\""));
        assertFalse(content.contains(token));
        assertFalse(content.contains("should-not-be-written"));
        assertFalse(content.contains("sk-raw-sensitive-api-key"));

        File summaryFile = findSessionFile(logDirectory, session.getSessionId(), ".md");
        assertNotNull(summaryFile);
        String summary = new String(Files.readAllBytes(summaryFile.toPath()), StandardCharsets.UTF_8);
        assertTrue(summary.contains("# Agent Session " + session.getSessionId()));
        assertTrue(summary.contains("## Task / User Goal"));
        assertTrue(summary.contains("find a goblin"));
        assertTrue(summary.contains("## What Was Built / Done"));
        assertTrue(summary.contains("`rs.find_nearest_npc` - Found nearest NPC."));
        assertTrue(summary.contains("## Obstacles Encountered"));
        assertTrue(summary.contains("`rs.pickup_ground_item` failed"));
        assertTrue(summary.contains("## Solution / Result"));
        assertTrue(summary.contains("Found the nearest goblin."));
        assertTrue(summary.contains("## Logical Next Step"));
        assertTrue(summary.contains("## Observable Decision Trail"));
        assertTrue(summary.contains("## In-Game Failures / Blockers"));
        assertTrue(summary.contains("inventory space"));
        assertTrue(summary.contains("## Harness Reflection"));
        assertTrue(summary.contains("## Learning Over Time"));
        assertFalse(summary.contains(token));
        assertFalse(summary.contains("should-not-be-written"));
        assertFalse(summary.contains("sk-raw-sensitive-api-key"));

        File profileMemory = AgentProfileMemory.INSTANCE.personalityFile(logDirectory, "logger_tester");
        assertTrue(profileMemory.exists());
        String profile = new String(Files.readAllBytes(profileMemory.toPath()), StandardCharsets.UTF_8);
        assertTrue(profile.contains("# Agent Profile Memory - logger_tester"));
        assertTrue(profile.contains("## Operational Memory"));
        assertTrue(profile.contains("## Recent Notes"));
        assertFalse(profile.contains(token));
        assertFalse(profile.contains("sk-raw-sensitive-api-key"));
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

    private static class TestPlayer extends Player {
        private TestPlayer(int playerId) {
            super(playerId);
        }
    }
}
