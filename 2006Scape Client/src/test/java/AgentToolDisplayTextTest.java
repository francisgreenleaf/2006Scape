import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.lang.reflect.Method;
import java.util.Map;

import org.junit.Test;

public class AgentToolDisplayTextTest {

    @Test
    public void representativeToolsUsePlayerFacingActions() {
        assertEquals("checking surroundings...", AgentToolDisplayText.actionFor("rs.observe_state_XS"));
        assertEquals("walking...", AgentToolDisplayText.actionFor("rs.walk_to_tile_until_arrived_XS"));
        assertEquals("passing obstacle...", AgentToolDisplayText.actionFor("rs.object_transition_step_XS"));
        assertEquals("checking bank...", AgentToolDisplayText.actionFor("rs.bank_item_count_XS"));
        assertEquals("requesting trade...", AgentToolDisplayText.actionFor("rs.request_player_trade_XS"));
        assertEquals("working...", AgentToolDisplayText.actionFor("rs.future_tool"));
    }

    @Test
    public void progressTextIsCapitalizedActionOnly() {
        assertEquals("Walking...", AgentToolDisplayText.progressFor("rs.walk_to_tile_until_arrived_XS"));
        assertEquals("Finding object...", AgentToolDisplayText.progressFor("find_nearest_object_XS"));
    }

    @Test
    public void allDisplayActionsFollowTerminalStyle() {
        for (Map.Entry<String, String> entry : AgentToolDisplayText.actionsForTests().entrySet()) {
            String action = entry.getValue();
            assertTrue(entry.getKey() + " should end in ellipsis", action.endsWith("..."));
            assertEquals(entry.getKey() + " should be lowercase", action, action.toLowerCase());
            for (int i = 0; i < action.length(); i++) {
                assertTrue(entry.getKey() + " should be ASCII", action.charAt(i) <= 126);
            }
        }
    }

    @Test
    public void everyAdvertisedToolHasDisplayText() throws Exception {
        CodexAppServerClient client = new CodexAppServerClient(null, null, null, null);
        Method method = CodexAppServerClient.class.getDeclaredMethod("dynamicTools");
        method.setAccessible(true);
        JsonArray tools = (JsonArray) method.invoke(client);

        for (JsonElement element : tools) {
            JsonObject tool = element.getAsJsonObject();
            String name = tool.get("name").getAsString();
            assertTrue("Missing AgentToolDisplayText action for rs." + name, AgentToolDisplayText.hasActionFor(name));
        }
    }
}
