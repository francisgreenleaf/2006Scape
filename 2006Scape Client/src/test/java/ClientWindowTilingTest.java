import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

import java.awt.Rectangle;
import java.util.List;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;

public class ClientWindowTilingTest {

	private String previousServerIp;
	private int previousServerPort;
	private int previousHttpPort;
	private int previousJaggrabPort;
	private int previousWorld;
	private boolean previousCheckCrc;
	private boolean previousShowNavbar;
	private int previousClientScale;
	private int previousTileSlot;
	private int previousTileTotal;
	private String previousTransport;
	private String previousBridgeUrl;
	private boolean previousAutoLogin;
	private String previousAutoClaim;
	private String previousAutoCommand;

	@Before
	public void setUp() {
		previousServerIp = ClientSettings.SERVER_IP;
		previousServerPort = ClientSettings.SERVER_PORT;
		previousHttpPort = ClientSettings.HTTP_PORT;
		previousJaggrabPort = ClientSettings.JAGGRAB_PORT;
		previousWorld = ClientSettings.SERVER_WORLD;
		previousCheckCrc = ClientSettings.CHECK_CRC;
		previousShowNavbar = ClientSettings.SHOW_NAVBAR;
		previousClientScale = ClientSettings.CLIENT_SCALE;
		previousTileSlot = ClientSettings.CLIENT_TILE_SLOT;
		previousTileTotal = ClientSettings.CLIENT_TILE_TOTAL;
		previousTransport = ClientSettings.EXPECTED_SECURE_TRANSPORT;
		previousBridgeUrl = ClientSettings.AGENT_BRIDGE_URL;
		previousAutoLogin = ClientSettings.AGENT_AUTO_LOGIN;
		previousAutoClaim = ClientSettings.AGENT_AUTO_CLAIM_NONCE;
		previousAutoCommand = ClientSettings.AGENT_AUTO_COMMAND;
	}

	@After
	public void tearDown() {
		ClientSettings.SERVER_IP = previousServerIp;
		ClientSettings.SERVER_PORT = previousServerPort;
		ClientSettings.HTTP_PORT = previousHttpPort;
		ClientSettings.JAGGRAB_PORT = previousJaggrabPort;
		ClientSettings.SERVER_WORLD = previousWorld;
		ClientSettings.CHECK_CRC = previousCheckCrc;
		ClientSettings.SHOW_NAVBAR = previousShowNavbar;
		ClientSettings.CLIENT_SCALE = previousClientScale;
		ClientSettings.CLIENT_TILE_SLOT = previousTileSlot;
		ClientSettings.CLIENT_TILE_TOTAL = previousTileTotal;
		ClientSettings.EXPECTED_SECURE_TRANSPORT = previousTransport;
		ClientSettings.AGENT_BRIDGE_URL = previousBridgeUrl;
		ClientSettings.AGENT_AUTO_LOGIN = previousAutoLogin;
		ClientSettings.AGENT_AUTO_CLAIM_NONCE = previousAutoClaim;
		ClientSettings.AGENT_AUTO_COMMAND = previousAutoCommand;
	}

	@Test
	public void parsesSupportedTileSpecsAndRejectsInvalidSpecs() {
		ClientWindow.TileSpec two = ClientWindow.parseTileSpec("2/4");
		assertEquals(2, two.slot);
		assertEquals(4, two.total);

		assertEquals(null, ClientWindow.parseTileSpec("5/4"));
		assertEquals(null, ClientWindow.parseTileSpec("1/3"));
		assertEquals(null, ClientWindow.parseTileSpec("not-a-tile"));
		assertFalse(ClientWindow.configureTile("5/4"));
		assertEquals(0, ClientSettings.CLIENT_TILE_SLOT);
		assertEquals(0, ClientSettings.CLIENT_TILE_TOTAL);
	}

	@Test
	public void tileBoundsUseUsableScreenPartitions() {
		Rectangle screen = new Rectangle(10, 20, 1001, 801);

		assertEquals(new Rectangle(10, 20, 500, 801), ClientWindow.tileBounds(screen, 1, 2));
		assertEquals(new Rectangle(510, 20, 501, 801), ClientWindow.tileBounds(screen, 2, 2));
		assertEquals(new Rectangle(510, 420, 501, 401), ClientWindow.tileBounds(screen, 4, 4));
	}

	@Test
	public void nextClientTileSelectionUsesHalvesThenQuadrants() {
		assertEquals("2/2", ClientWindow.tileForNewClient(1, 1).asArgument());
		assertEquals("3/4", ClientWindow.tileForNewClient(2, 1).asArgument());
		assertEquals("4/4", ClientWindow.tileForNewClient(3, 1).asArgument());
		assertEquals("1/4", ClientWindow.tileForCurrentClient(2, 1).asArgument());
	}

	@Test
	public void sanitizedRelaunchArgsExcludeCredentialsAndAgentTurnState() {
		ClientSettings.SERVER_IP = "localhost";
		ClientSettings.SERVER_PORT = 43594;
		ClientSettings.HTTP_PORT = 8080;
		ClientSettings.JAGGRAB_PORT = 43595;
		ClientSettings.SERVER_WORLD = 1;
		ClientSettings.CHECK_CRC = false;
		ClientSettings.SHOW_NAVBAR = false;
		ClientSettings.CLIENT_SCALE = 2;
		ClientSettings.EXPECTED_SECURE_TRANSPORT = "local";
		ClientSettings.AGENT_BRIDGE_URL = "http://127.0.0.1:43610";
		ClientSettings.AGENT_AUTO_LOGIN = true;
		ClientSettings.AGENT_AUTO_CLAIM_NONCE = "secret-nonce";
		ClientSettings.AGENT_AUTO_COMMAND = "secret command";

		List<String> args = ClientRelauncher.buildSanitizedClientArgsForTests(new ClientWindow.TileSpec(2, 2));
		String joined = args.toString();

		assertFalse(args.contains("-u"));
		assertFalse(args.contains("-user"));
		assertFalse(args.contains("-username"));
		assertFalse(args.contains("-p"));
		assertFalse(args.contains("-pass"));
		assertFalse(joined.contains("password"));
		assertFalse(joined.contains("agent-claim"));
		assertFalse(joined.contains("agent-command"));
		assertFalse(joined.contains("secret"));
		assertEquals("2/2", args.get(args.indexOf("-tile") + 1));
	}
}
