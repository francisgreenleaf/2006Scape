package com.rs2.agent;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;

import com.rs2.Constants;
import com.rs2.game.objects.Objects;
import com.rs2.game.players.Player;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

public class AgentPassiveTraceLogTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private File logDirectory;

    @Before
    public void setUp() throws Exception {
        logDirectory = temporaryFolder.newFolder("player-movement-traces");
        AgentPassiveTraceLog.INSTANCE.setLogDirectoryForTests(logDirectory);
    }

    @After
    public void tearDown() {
        AgentPassiveTraceLog.INSTANCE.resetLogDirectoryForTests();
    }

    @Test
    public void recordsMovementEventsWithRoutingFields() throws Exception {
        TestPlayer player = new TestPlayer(12);
        player.playerName = "Trace Tester";
        player.absX = 3200;
        player.absY = 3200;
        player.heightLevel = 0;
        player.isRunning2 = true;
        player.playerEnergy = 100.0;
        player.playerLevel[Constants.HITPOINTS] = 10;

        AgentPassiveTraceLog.INSTANCE.captureBeforeMovement(player, 42L);
        player.absX = 3201;
        player.dir1 = 2;
        player.dir2 = 4;
        player.playerEnergy = 98.0;
        AgentPassiveTraceLog.INSTANCE.recordAfterUpdate(player, 42L);

        File logFile = findFile(logDirectory, "trace_tester.jsonl");
        assertNotNull(logFile);
        String content = new String(Files.readAllBytes(logFile.toPath()), StandardCharsets.UTF_8);
        assertTrue(content.contains("\"schemaVersion\":2"));
        assertTrue(content.contains("\"source\":\"server-passive-player-tick\""));
        assertTrue(content.contains("\"event\":\"movement\""));
        assertTrue(content.contains("\"tool\":\"server_passive_tick\""));
        assertTrue(content.contains("\"serverTick\":42"));
        assertTrue(content.contains("\"traceId\":\"trace_tester-passive\""));
        assertTrue(content.contains("\"tile\":{\"x\":3201,\"y\":3200,\"height\":0}"));
        assertTrue(content.contains("\"previousTile\":{\"x\":3200,\"y\":3200,\"height\":0}"));
        assertTrue(content.contains("\"runEnergySpent\":2"));
    }

    @Test
    public void suppressesIdleTicksUntilHeartbeat() throws Exception {
        TestPlayer player = new TestPlayer(13);
        player.playerName = "Idle Tester";
        player.absX = 3222;
        player.absY = 3218;
        player.heightLevel = 0;
        player.playerLevel[Constants.HITPOINTS] = 10;

        AgentPassiveTraceLog.INSTANCE.recordTick(player, 1L, 3222, 3218, 0, 10, 100);
        AgentPassiveTraceLog.INSTANCE.recordTick(player, 2L, 3222, 3218, 0, 10, 100);
        AgentPassiveTraceLog.INSTANCE.recordTick(player, 26L, 3222, 3218, 0, 10, 100);

        File logFile = findFile(logDirectory, "idle_tester.jsonl");
        assertNotNull(logFile);
        List<String> lines = Files.readAllLines(logFile.toPath(), StandardCharsets.UTF_8);
        assertEquals(2, lines.size());
        assertTrue(lines.get(0).contains("\"event\":\"state\""));
        assertTrue(lines.get(1).contains("\"event\":\"state\""));
    }

    @Test
    public void ignoresStaleKillingNpcIndexAfterCombatEnds() throws Exception {
        TestPlayer player = new TestPlayer(15);
        player.playerName = "Respawn Tester";
        player.absX = 3222;
        player.absY = 3218;
        player.heightLevel = 0;
        player.playerLevel[Constants.HITPOINTS] = 10;
        player.killingNpcIndex = 1494;

        AgentPassiveTraceLog.INSTANCE.recordTick(player, 1L, 3222, 3218, 0, 10, 100);

        File logFile = findFile(logDirectory, "respawn_tester.jsonl");
        assertNotNull(logFile);
        List<String> lines = Files.readAllLines(logFile.toPath(), StandardCharsets.UTF_8);
        assertEquals(1, lines.size());
        assertTrue(lines.get(0).contains("\"event\":\"state\""));
        assertTrue(lines.get(0).contains("\"isInCombat\":false"));
        assertTrue(lines.get(0).contains("\"combat\":false"));
    }

    @Test
    public void recordsObjectClickEventsWithObjectMetadata() throws Exception {
        TestPlayer player = new TestPlayer(14);
        player.playerName = "Object Tester";
        player.absX = 3200;
        player.absY = 3200;
        player.heightLevel = 0;
        player.playerLevel[Constants.HITPOINTS] = 10;
        player.objectId = 1530;
        player.objectX = 3201;
        player.objectY = 3200;
        Objects object = new Objects(1530, 3201, 3200, 0, 1, 0, 0);

        AgentPassiveTraceLog.INSTANCE.recordObjectClickQueued(player, 1, 132, object);
        player.absX = 3201;
        AgentPassiveTraceLog.INSTANCE.recordObjectClickCompleted(player, 1530, 3201, 3200, 0, 1,
                3200, 3200, 0, object);

        File logFile = findFile(logDirectory, "object_tester.jsonl");
        assertNotNull(logFile);
        List<String> lines = Files.readAllLines(logFile.toPath(), StandardCharsets.UTF_8);
        assertEquals(2, lines.size());
        assertTrue(lines.get(0).contains("\"event\":\"object_interaction\""));
        assertTrue(lines.get(0).contains("\"objectInteractionPhase\":\"queued\""));
        assertTrue(lines.get(0).contains("\"packetOpcode\":132"));
        assertTrue(lines.get(0).contains("\"objectId\":1530"));
        assertTrue(lines.get(0).contains("\"objectTile\":{\"x\":3201,\"y\":3200,\"height\":0}"));
        assertTrue(lines.get(1).contains("\"objectInteractionPhase\":\"completed\""));
        assertTrue(lines.get(1).contains("\"previousTile\":{\"x\":3200,\"y\":3200,\"height\":0}"));
        assertTrue(lines.get(1).contains("\"tile\":{\"x\":3201,\"y\":3200,\"height\":0}"));
        assertTrue(lines.get(1).contains("\"moved\":true"));
    }

    private File findFile(File directory, String name) {
        File[] files = directory.listFiles();
        if (files == null) {
            return null;
        }
        for (File file : files) {
            if (file.isDirectory()) {
                File found = findFile(file, name);
                if (found != null) {
                    return found;
                }
            } else if (name.equals(file.getName())) {
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
