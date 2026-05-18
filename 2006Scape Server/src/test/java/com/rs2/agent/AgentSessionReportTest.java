package com.rs2.agent;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class AgentSessionReportTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    @Test
    public void generatesSummaryAndCanonicalIndexFromDaySplitJsonl() throws Exception {
        File base = temporaryFolder.newFolder("agent-sessions");
        File dayOne = new File(base, "2026-05-17");
        File dayTwo = new File(base, "2026-05-18");
        assertTrue(dayOne.mkdirs());
        assertTrue(dayTwo.mkdirs());

        String first = "{\"timestamp\":\"2026-05-17T23:59:00Z\",\"event\":\"turn_requested\",\"sessionId\":\"abc123\",\"playerName\":\"MrGem\",\"data\":{\"command\":\"train combat\"}}\n"
                + "{\"timestamp\":\"2026-05-17T23:59:02Z\",\"event\":\"tool_completed\",\"sessionId\":\"abc123\",\"playerName\":\"MrGem\",\"data\":{\"tool\":\"observe_state\",\"result\":{\"success\":true,\"message\":\"Observed current game state.\"}}}\n";
        String second = "{\"timestamp\":\"2026-05-18T00:01:00Z\",\"event\":\"tool_failed\",\"sessionId\":\"abc123\",\"playerName\":\"MrGem\",\"data\":{\"tool\":\"pickup_ground_item\",\"result\":{\"success\":false,\"message\":\"Not enough inventory space to pick up bones.\"}}}\n";
        Files.write(new File(dayOne, "abc123.jsonl").toPath(), first.getBytes(StandardCharsets.UTF_8));
        Files.write(new File(dayTwo, "abc123.jsonl").toPath(), second.getBytes(StandardCharsets.UTF_8));

        AgentSessionReport.Result result = AgentSessionReport.generate(base, null);

        assertEquals(1, result.sessionsScanned);
        assertTrue(result.summaryFile.exists());
        assertTrue(result.indexFile.exists());

        String summary = new String(Files.readAllBytes(result.summaryFile.toPath()), StandardCharsets.UTF_8);
        assertTrue(summary.contains("## Top Tools"));
        assertTrue(summary.contains("rs.observe_state"));
        assertTrue(summary.contains("inventory space"));
        assertTrue(summary.contains("Connected multi-day sessions"));

        String index = new String(Files.readAllBytes(result.indexFile.toPath()), StandardCharsets.UTF_8);
        assertTrue(index.contains("abc123"));
        assertTrue(index.contains("2026-05-17, 2026-05-18"));
    }
}
