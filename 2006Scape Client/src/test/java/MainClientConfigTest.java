import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class MainClientConfigTest {

    @Rule
    public TemporaryFolder temporaryFolder = new TemporaryFolder();

    private String previousServerIp;
    private int previousServerPort;
    private int previousHttpPort;
    private int previousJaggrabPort;
    private int previousWorld;
    private boolean previousCheckCrc;
    private boolean previousSingleOnDemand;
    private boolean previousShowNavbar;
    private int previousClientScale;
    private String previousExpectedSecureTransport;

    @Before
    public void setUp() {
        previousServerIp = ClientSettings.SERVER_IP;
        previousServerPort = ClientSettings.SERVER_PORT;
        previousHttpPort = ClientSettings.HTTP_PORT;
        previousJaggrabPort = ClientSettings.JAGGRAB_PORT;
        previousWorld = ClientSettings.SERVER_WORLD;
        previousCheckCrc = ClientSettings.CHECK_CRC;
        previousSingleOnDemand = ClientSettings.SINGLE_ONDEMAND;
        previousShowNavbar = ClientSettings.SHOW_NAVBAR;
        previousClientScale = ClientSettings.CLIENT_SCALE;
        previousExpectedSecureTransport = ClientSettings.EXPECTED_SECURE_TRANSPORT;
    }

    @After
    public void tearDown() {
        ClientSettings.SERVER_IP = previousServerIp;
        ClientSettings.SERVER_PORT = previousServerPort;
        ClientSettings.HTTP_PORT = previousHttpPort;
        ClientSettings.JAGGRAB_PORT = previousJaggrabPort;
        ClientSettings.SERVER_WORLD = previousWorld;
        ClientSettings.CHECK_CRC = previousCheckCrc;
        ClientSettings.SINGLE_ONDEMAND = previousSingleOnDemand;
        ClientSettings.SHOW_NAVBAR = previousShowNavbar;
        ClientSettings.CLIENT_SCALE = previousClientScale;
        ClientSettings.EXPECTED_SECURE_TRANSPORT = previousExpectedSecureTransport;
    }

    @Test
    public void clientConfigAppliesStandaloneConnectionSettings() throws Exception {
        Path config = temporaryFolder.newFile("client.properties").toPath();
        Files.write(config, (
                "server.host=example-tailnet-host\n"
                        + "server.port=43594\n"
                        + "http.port=8081\n"
                        + "jaggrab.port=43595\n"
                        + "server.world=2\n"
                        + "check_crc=false\n"
                        + "single_ondemand=false\n"
                        + "show_navbar=false\n"
                        + "client.scale=3\n"
                        + "secure.transport=tailscale\n").getBytes(StandardCharsets.UTF_8));

        loadClientConfig(config);

        assertEquals("example-tailnet-host", ClientSettings.SERVER_IP);
        assertEquals(43594, ClientSettings.SERVER_PORT);
        assertEquals(8081, ClientSettings.HTTP_PORT);
        assertEquals(43595, ClientSettings.JAGGRAB_PORT);
        assertEquals(2, ClientSettings.SERVER_WORLD);
        assertFalse(ClientSettings.CHECK_CRC);
        assertFalse(ClientSettings.SINGLE_ONDEMAND);
        assertFalse(ClientSettings.SHOW_NAVBAR);
        assertEquals(3, ClientSettings.CLIENT_SCALE);
        assertEquals("tailscale", ClientSettings.EXPECTED_SECURE_TRANSPORT);
        assertEquals(43594, ClientSettings.gamePort());
        assertEquals(43594, ClientSettings.onDemandPort());
    }

    @Test
    public void invalidPortsAndScaleUseSafePositiveDefaults() throws Exception {
        ClientSettings.SERVER_PORT = -1;
        ClientSettings.HTTP_PORT = 8080;
        ClientSettings.JAGGRAB_PORT = 43595;
        ClientSettings.CLIENT_SCALE = 2;
        Path config = temporaryFolder.newFile("invalid-client.properties").toPath();
        Files.write(config, (
                "server.port=not-a-port\n"
                        + "http.port=also-not-a-port\n"
                        + "jaggrab.port=-5\n"
                        + "client.scale=99\n").getBytes(StandardCharsets.UTF_8));

        loadClientConfig(config);

        assertEquals(43594, ClientSettings.SERVER_PORT);
        assertEquals(8080, ClientSettings.HTTP_PORT);
        assertEquals(43595, ClientSettings.JAGGRAB_PORT);
        assertEquals(4, ClientSettings.CLIENT_SCALE);
        assertEquals(43594, ClientSettings.gamePort());
    }

    @Test
    public void externalTransportNoticePrintsOnlyForNonLocalTransport() throws Exception {
        ClientSettings.EXPECTED_SECURE_TRANSPORT = "tailscale";
        String output = captureTransportNotice();

        assertTrue(output.contains("expected external transport: tailscale"));
        assertTrue(output.contains("Connect that VPN/tunnel before logging in"));
        assertTrue(output.contains("plaintext"));

        ClientSettings.EXPECTED_SECURE_TRANSPORT = "direct_tcp";
        output = captureTransportNotice();
        assertTrue(output.contains("external transport: direct_tcp"));
        assertTrue(output.contains("directly over plaintext TCP"));
        assertFalse(output.contains("Connect that VPN/tunnel"));

        ClientSettings.EXPECTED_SECURE_TRANSPORT = "local";
        assertEquals("", captureTransportNotice());

        ClientSettings.EXPECTED_SECURE_TRANSPORT = "external transport not specified";
        assertEquals("", captureTransportNotice());
    }

    @Test
    public void agentChatDynamicToolAdvertisesCompactAliasTargets() throws Exception {
        JsonObject tool = dynamicTool("agent_chat_send_XS");
        JsonObject properties = tool.getAsJsonObject("inputSchema").getAsJsonObject("properties");

        assertEquals("rs", tool.get("namespace").getAsString());
        assertTrue(tool.get("description").getAsString().contains("agent/player alias"));
        assertTrue(properties.has("message"));
        assertTrue(properties.has("agent"));
        assertTrue(properties.has("player"));
        assertTrue(properties.has("to"));
        assertTrue(properties.has("toType"));
        assertTrue(properties.has("channel"));
        assertTrue(properties.has("deliverToPlayers"));
    }

    private static void loadClientConfig(Path path) throws Exception {
        Method method = Main.class.getDeclaredMethod("loadClientConfig", Path.class);
        method.setAccessible(true);
        method.invoke(null, path);
    }

    private static JsonObject dynamicTool(String name) throws Exception {
        Method method = CodexAppServerClient.class.getDeclaredMethod("dynamicTools");
        method.setAccessible(true);
        CodexAppServerClient client = new CodexAppServerClient(null, message -> { }, () -> { });
        JsonArray tools = (JsonArray) method.invoke(client);
        for (int i = 0; i < tools.size(); i++) {
            JsonObject tool = tools.get(i).getAsJsonObject();
            if (name.equals(tool.get("name").getAsString())) {
                return tool;
            }
        }
        throw new AssertionError("dynamic tool not found: " + name);
    }

    private static String captureTransportNotice() throws Exception {
        Method method = Main.class.getDeclaredMethod("printExternalTransportNotice");
        method.setAccessible(true);
        PrintStream previous = System.out;
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        PrintStream replacement = new PrintStream(output, true, "UTF-8");
        try {
            System.setOut(replacement);
            method.invoke(null);
        } finally {
            System.setOut(previous);
            replacement.close();
        }
        return output.toString(StandardCharsets.UTF_8.name());
    }
}
