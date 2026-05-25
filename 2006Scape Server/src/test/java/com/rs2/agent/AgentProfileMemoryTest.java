package com.rs2.agent;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import com.google.gson.JsonObject;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

public class AgentProfileMemoryTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    @Test
    public void writesProfilePersonalityMemoryFromSanitizedSessionEvents() throws Exception {
        File logDirectory = temporaryFolder.newFolder("agent-sessions");

        AgentProfileMemory.INSTANCE.record(logDirectory, entry("session_registered", "MrGem", null, null));
        AgentProfileMemory.INSTANCE.record(logDirectory, entry("turn_requested", "MrGem", "command",
                "travel to Varrock for gear money after training cows near Lumbridge"));
        AgentProfileMemory.INSTANCE.record(logDirectory, entry("tool_failed", "MrGem", "message",
                "Not enough inventory space to pick up bones."));
        AgentProfileMemory.INSTANCE.record(logDirectory, entry("tool_failed", "MrGem", "message",
                "Inventory is full before banking cowhides."));
        AgentProfileMemory.INSTANCE.record(logDirectory, entry("goal_progress", "MrGem", "message",
                "Training cows near Lumbridge made level progress."));
        AgentProfileMemory.INSTANCE.record(logDirectory, entry("goal_blocked", "MrGem", "message",
                "Player death stopped the combat goal."));

        File memoryFile = AgentProfileMemory.INSTANCE.personalityFile(logDirectory, "MrGem");
        assertTrue(memoryFile.exists());
        String memory = new String(Files.readAllBytes(memoryFile.toPath()), StandardCharsets.UTF_8);

        assertTrue(memory.contains("# Agent Profile Memory - MrGem"));
        assertTrue(memory.contains("## Operational Memory"));
        assertTrue(memory.contains("Inventory pressure recurs before banking is handled."));
        assertTrue(memory.contains("Varrock trips are useful but should start with food, coins, gear, and a clear route."));
        assertTrue(memory.contains("## Behavior Bias"));
        assertTrue(memory.contains("Risk posture: check hitpoints, food, escape routes, and nearby threats before pushing deeper."));
        assertTrue(memory.contains("## Suggested Priorities"));
        assertTrue(memory.contains("Use a reliable banking route before long gathering or combat loops."));
        assertTrue(memory.contains("## Recent Notes"));
        assertTrue(memory.contains("Risk note: deaths require better food, gear, and an exit path before retrying."));
        assertFalse(memory.contains("Note to self:"));
        assertFalse(memory.contains("cows are not glorious enemies"));
        assertFalse(memory.contains("campfire"));

        JsonObject observed = AgentProfileMemory.INSTANCE.readForPlayer(logDirectory, "MrGem");
        assertTrue(observed.has("beliefs"));
        assertTrue(observed.has("personalityDrift"));
        assertTrue(observed.has("selfFormedGoals"));
        assertTrue(observed.has("selfTalkLog"));
    }

    @Test
    public void ignoresSuccessfulToolMessagesForProfileSignals() throws Exception {
        File logDirectory = temporaryFolder.newFolder("agent-sessions");

        AgentProfileMemory.INSTANCE.record(logDirectory, entry("session_registered", "MrGem", null, null));
        AgentProfileMemory.INSTANCE.record(logDirectory, toolEntry("tool_completed", "MrGem", "attack_npc",
                "Attacking Cow."));
        AgentProfileMemory.INSTANCE.record(logDirectory, toolEntry("tool_completed", "MrGem", "pickup_ground_item",
                "Picked up 1 Cowhide."));
        AgentProfileMemory.INSTANCE.record(logDirectory, toolEntry("tool_completed", "MrGem", "pickup_ground_item",
                "Picked up 1 Cowhide."));

        File memoryFile = AgentProfileMemory.INSTANCE.personalityFile(logDirectory, "MrGem");
        String memory = new String(Files.readAllBytes(memoryFile.toPath()), StandardCharsets.UTF_8);

        assertTrue(memory.contains("- Tool successes: 3"));
        assertTrue(memory.contains("- Lumbridge/cow routine evidence: 0"));
        assertFalse(memory.contains("Lumbridge cow combat is a known early-training routine"));
        assertFalse(memory.contains("Training note: Lumbridge cows"));
    }

    private JsonObject entry(String event, String playerName, String dataName, String dataValue) {
        JsonObject entry = new JsonObject();
        entry.addProperty("timestamp", "2026-05-19T00:00:00.000Z");
        entry.addProperty("event", event);
        entry.addProperty("sessionId", "session-a");
        entry.addProperty("playerName", playerName);
        if (dataName != null) {
            JsonObject data = new JsonObject();
            if ("tool_failed".equals(event)) {
                data.addProperty("tool", "pickup_ground_item");
                JsonObject result = new JsonObject();
                result.addProperty("success", false);
                result.addProperty(dataName, dataValue);
                data.add("result", result);
            } else if (event.startsWith("goal_")) {
                JsonObject goal = new JsonObject();
                goal.addProperty(dataName, dataValue);
                data.add("goal", goal);
            } else {
                data.addProperty(dataName, dataValue);
            }
            entry.add("data", data);
        }
        return entry;
    }

    private JsonObject toolEntry(String event, String playerName, String tool, String message) {
        JsonObject entry = new JsonObject();
        entry.addProperty("timestamp", "2026-05-19T00:00:00.000Z");
        entry.addProperty("event", event);
        entry.addProperty("sessionId", "session-a");
        entry.addProperty("playerName", playerName);
        JsonObject data = new JsonObject();
        data.addProperty("tool", tool);
        JsonObject result = new JsonObject();
        result.addProperty("success", "tool_completed".equals(event));
        result.addProperty("message", message);
        data.add("result", result);
        entry.add("data", data);
        return entry;
    }
}
