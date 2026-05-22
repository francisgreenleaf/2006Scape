package com.rs2.agent;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import com.google.gson.JsonObject;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

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

        assertTrue(memory.contains("# Agent Personality - MrGem"));
        assertTrue(memory.contains("## Character Memory"));
        assertTrue(memory.contains("I often run into inventory pressure"));
        assertTrue(memory.contains("Varrock feels useful but risky"));
        assertTrue(memory.contains("## Personality Drift"));
        assertTrue(memory.contains("Cautious after deaths"));
        assertTrue(memory.contains("## Goal Formation"));
        assertTrue(memory.contains("I should learn a reliable banking route"));
        assertTrue(memory.contains("## Self-Talk Log"));
        assertTrue(memory.contains("Note to self:"));
        assertTrue(memory.contains("cows are not glorious enemies")
                || memory.contains("food in my pack")
                || memory.contains("Varrock keeps calling"));

        JsonObject observed = AgentProfileMemory.INSTANCE.readForPlayer(logDirectory, "MrGem");
        assertTrue(observed.has("beliefs"));
        assertTrue(observed.has("personalityDrift"));
        assertTrue(observed.has("selfFormedGoals"));
        assertTrue(observed.has("selfTalkLog"));
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
}
