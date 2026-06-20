import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.List;

import org.junit.Test;

public class AgentTerminalLogTest {

    @Test
    public void longMessagesWrapInsteadOfClipping() {
        AgentTerminalLog log = new AgentTerminalLog();
        StringBuilder message = new StringBuilder();
        for (int i = 0; i < 8; i++) {
            message.append("terminal message segment ");
        }

        log.system(message.toString());

        List<AgentTerminalLog.RenderLine> lines = log.renderLines(null, 120);
        assertTrue("ready message plus wrapped long message", lines.size() > 2);
        assertTrue(lines.get(1).text.matches("\\d{2}:\\d{2} sys terminal message.*"));
        assertTrue("continuation row should be indented", lines.get(2).text.startsWith("          "));
        assertFalse("wrapping should not use embedded newlines", lines.get(2).text.contains("\n"));
    }

    @Test
    public void narrowWidthsStillRenderNonEmptyRows() {
        AgentTerminalLog log = new AgentTerminalLog();

        log.command("status with enough extra words to require wrapping");

        List<AgentTerminalLog.RenderLine> lines = log.renderLines(null, 1);
        assertTrue(lines.size() > 2);
        for (AgentTerminalLog.RenderLine line : lines) {
            assertFalse(line.text.isEmpty());
        }
    }

    @Test
    public void controlCharactersAreNormalizedBeforeRendering() {
        AgentTerminalLog log = new AgentTerminalLog();

        log.warn("first\nsecond\tthird\r\u0001fourth");

        String rendered = log.renderLines(null, 160).get(1).text;
        assertTrue(rendered.contains("first second third fourth"));
        assertFalse(rendered.contains("\n"));
        assertFalse(rendered.contains("\t"));
        assertFalse(rendered.contains("\r"));
    }

    @Test
    public void commonUnicodePunctuationIsRenderedAsAscii() {
        AgentTerminalLog log = new AgentTerminalLog();

        log.assistant("I\u2019m routing \u2014 wait\u2026 \u201cok\u201d\u00a0now");

        String rendered = log.renderLines(null, 200).get(1).text;
        assertTrue(rendered.contains("I'm routing - wait... \"ok\" now"));
        assertFalse(rendered.contains("?"));
    }

    @Test
    public void timestampsUseMinutePrecision() {
        AgentTerminalLog log = new AgentTerminalLog();

        String rendered = log.renderLines(null, 200).get(0).text;
        assertTrue(rendered.matches("\\d{2}:\\d{2} sys .*"));
        assertFalse(rendered.matches("\\d{2}:\\d{2}:\\d{2} sys .*"));
    }

    @Test
    public void longEntryHistoryKeepsEntryCapAtWideWidth() {
        AgentTerminalLog log = new AgentTerminalLog();

        for (int i = 0; i < 220; i++) {
            log.toolResult("rs.observe_state_XS", true, "message number " + i + " with a lot of detail", i);
        }

        List<AgentTerminalLog.RenderLine> lines = log.renderLines(null, 500);
        assertEquals("entry cap should equal rendered row cap when rows do not wrap", 180, lines.size());
        for (AgentTerminalLog.RenderLine line : lines) {
            assertFalse(line.text.contains("\n"));
        }
    }

    @Test
    public void toolRowsUsePlayerFacingActions() {
        AgentTerminalLog log = new AgentTerminalLog();

        log.toolStart("rs.walk_to_tile_until_arrived_XS");
        log.toolResult("rs.find_nearest_object_XS", false, "No matching object found nearby.", 2628);

        List<AgentTerminalLog.RenderLine> lines = log.renderLines(null, 500);
        String started = lines.get(1).text;
        String finished = lines.get(2).text;
        assertTrue(started.contains("walking..."));
        assertEquals(AgentTerminalLog.TOOL_DOT, lines.get(1).marker);
        assertFalse(started.contains("tool"));
        assertTrue(finished.contains("err finding object... 2628ms No matching object found nearby."));
        assertFalse(started.contains("rs."));
        assertFalse(finished.contains("rs."));
        assertFalse(started.contains("walk_to_tile_until_arrived"));
        assertFalse(finished.contains("find_nearest_object"));
    }

    @Test
    public void compactMessageKeepsShortTextUnchanged() {
        assertEquals("ready", AgentTerminalLog.compactMessageForTests("ready", 12));
        assertEquals("abcdefg...", AgentTerminalLog.compactMessageForTests("abcdefghijklmnopqrstuvwxyz", 10));
    }
}
