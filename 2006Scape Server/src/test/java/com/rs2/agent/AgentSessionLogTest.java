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
        arguments.addProperty("name", "goblin");
        JsonObject result = AgentToolService.success("Found nearest NPC.");
        JsonObject task = new JsonObject();
        task.addProperty("command", "find a goblin");
        AgentSessionLog.INSTANCE.clientEvent(session, "turn_requested", task);
        AgentSessionLog.INSTANCE.toolCompleted(session, "find_nearest_npc", arguments, result, 15L);
        JsonObject assistant = new JsonObject();
        assistant.addProperty("text", "Found the nearest goblin.");
        AgentSessionLog.INSTANCE.clientEvent(session, "assistant_message", assistant);

        File logFile = findSessionFile(logDirectory, session.getSessionId(), ".jsonl");
        assertNotNull(logFile);
        String content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertTrue(content.contains("\"event\":\"session_registered\""));
        assertTrue(content.contains("\"event\":\"session_claimed\""));
        assertTrue(content.contains("\"event\":\"tool_completed\""));
        assertTrue(content.contains("\"tool\":\"find_nearest_npc\""));
        assertTrue(content.contains("\"token\":\"[redacted]\""));
        assertFalse(content.contains(token));
        assertFalse(content.contains("should-not-be-written"));

        File summaryFile = findSessionFile(logDirectory, session.getSessionId(), ".md");
        assertNotNull(summaryFile);
        String summary = new String(Files.readAllBytes(summaryFile.toPath()), StandardCharsets.UTF_8);
        assertTrue(summary.contains("# Agent Session " + session.getSessionId()));
        assertTrue(summary.contains("## Task"));
        assertTrue(summary.contains("find a goblin"));
        assertTrue(summary.contains("## What Was Built / Done"));
        assertTrue(summary.contains("`rs.find_nearest_npc` - Found nearest NPC."));
        assertTrue(summary.contains("## Obstacles Encountered"));
        assertTrue(summary.contains("## Solution"));
        assertTrue(summary.contains("Found the nearest goblin."));
        assertTrue(summary.contains("## Logical Next Step"));
        assertFalse(summary.contains(token));
        assertFalse(summary.contains("should-not-be-written"));
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
