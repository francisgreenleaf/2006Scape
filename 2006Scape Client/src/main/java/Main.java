import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Properties;
import java.awt.Image;
import java.net.URL;
import javax.swing.ImageIcon;

public final class Main {

	/*

	DEAR DEVELOPER!

	If you want to run the client locally, the easiest way to do that is run the class "Client.java" instead!
	If you REALLY want to use this class, add program arguments "-s localhost".
	 */

	public static void main(String[] args) {
		try {
			configureDesktopProperties();
			loadClientConfigFromArgs(args);
			// Process client arguments to connect to
			for (int i = 0; i < args.length; i++) {
				switch(args[i]) {
					case "-dev"	:
					case "-local":
					case "-offline":
						ClientSettings.SERVER_IP = "localhost";
						ClientSettings.CHECK_CRC = false;
						break;
					case "-no-crc":
					case "-no-cache-crc":
						ClientSettings.CHECK_CRC = false;
						break;
					case "-qol":
					case "-fixes":
						ClientSettings.CUSTOM_SETTINGS_TAB = true;
						ClientSettings.BILINEAR_MINIMAP_FILTERING = true;
						ClientSettings.FIX_TRANSPARENCY_OVERFLOW = true;
						ClientSettings.FULL_512PX_VIEWPORT = true;
						ClientSettings.CONTROL_KEY_ZOOMING = true;
						break;
					case "-no-nav":
					case "-disable-nav":
						ClientSettings.SHOW_NAVBAR = false;
						break;
					case"-no-snow":
					case"-hide-snow":
					case"-disable-snow":
						ClientSettings.SNOW_FLOOR_ENABLED = false;
						ClientSettings.SNOW_FLOOR_FORCE_ENABLED = false;
						ClientSettings.SNOW_OVERLAY_FORCE_ENABLED = false;
						ClientSettings.SNOW_OVERLAY_ENABLED = false;
						break;
					case"-no-roofs":
					case"-hide-roofs":
					case"-disable-roofs":
						ClientSettings.HIDE_ROOFS = true;
						break;
					case"-show-zoom":
						ClientSettings.SHOW_ZOOM_LEVEL_MESSAGES = true;
						break;
					case"-no-java-warnings":
					case"-hide-java-warnings":
						ClientSettings.SHOW_JAVA_VERSION_WARNINGS = false;
						break;
					case"-screenshots":
					case"-enable-screenshots":
						ClientSettings.SCREENSHOTS_ENABLED = true;
						break;
					case"-auto-screenshots":
					case"-enable-auto-screenshots":
						ClientSettings.AUTOMATIC_SCREENSHOTS_ENABLED = true;
						break;
					case"-auto-login":
					case"-agent-auto-login":
						ClientSettings.AGENT_AUTO_LOGIN = true;
						ClientSettings.SHOW_JAVA_VERSION_WARNINGS = false;
						break;
					case "-2x":
					case "-double-size":
						ClientSettings.CLIENT_SCALE = 2;
						break;
				}
				if (args[i].startsWith("-") && (i + 1) < args.length  && !args[i + 1].startsWith("-")) {
					switch(args[i]) {
						case "-s":
						case "-server":
						case "-ip":
							ClientSettings.SERVER_IP = args[++i];
							break;
						case "-port":
						case "-game-port":
							ClientSettings.SERVER_PORT = parsePositiveInt(args[++i], ClientSettings.SERVER_PORT, "game port");
							break;
						case "-http-port":
						case "-cache-http-port":
							ClientSettings.HTTP_PORT = parsePositiveInt(args[++i], ClientSettings.HTTP_PORT, "HTTP cache port");
							break;
							case "-jaggrab-port":
								ClientSettings.JAGGRAB_PORT = parsePositiveInt(args[++i], ClientSettings.JAGGRAB_PORT, "JAGGRAB port");
								break;
							case "-agent-bridge-port":
								setAgentBridgePort(parsePositiveInt(args[++i], ClientSettings.AGENT_BRIDGE_PORT, "agent bridge port"));
								break;
							case "-agent-bridge-url":
							case "-agent-gateway-url":
								setAgentBridgeUrl(args[++i]);
								break;
							case "-agent-command":
							case "-agent-auto-command":
								ClientSettings.AGENT_AUTO_COMMAND = args[++i];
							ClientSettings.AGENT_AUTO_LOGIN = true;
							ClientSettings.SHOW_JAVA_VERSION_WARNINGS = false;
							break;
						case "-scale":
						case "-client-scale":
						case "-window-scale":
							ClientSettings.CLIENT_SCALE = parseClientScale(args[++i]);
							break;
						case "-client-config":
						case "-config":
							i++;
							break;
					}
				}
			}

			Game game = new Game();

			// Process other arguments
			for (int i = 0; i < args.length; i++) {
				if (args[i].startsWith("-") && (i + 1) < args.length  && !args[i + 1].startsWith("-")) {
					switch(args[i]) {
						case "-u":
						case "-user":
						case "-username":
							game.myUsername = args[++i];
							break;
						case "-p":
						case "-pass":
						case "-password":
							game.myPassword = args[++i];
							break;
						case "-password-env":
						case "-pass-env":
							game.myPassword = readEnvironmentValue(args[++i], "password");
							break;
						case "-password-save":
						case "-password-character-save":
							game.myPassword = readCharacterSavePassword(args[++i]);
							break;
						case "-w":
						case "-world":
							ClientSettings.SERVER_WORLD = Integer.parseInt(args[++i]);
							break;
						case "-port":
						case "-game-port":
							case "-http-port":
							case "-cache-http-port":
							case "-jaggrab-port":
							case "-agent-bridge-port":
							case "-agent-bridge-url":
							case "-agent-gateway-url":
							case "-client-config":
							case "-config":
								i++;
							break;
						case "-agent-claim":
						case "-agent-claim-nonce":
							ClientSettings.AGENT_AUTO_CLAIM_NONCE = args[++i];
							break;
						case "-agent-command":
						case "-agent-auto-command":
							ClientSettings.AGENT_AUTO_COMMAND = args[++i];
							break;
					}
				}
			}
			if (ClientSettings.AGENT_AUTO_LOGIN || (ClientSettings.AGENT_AUTO_COMMAND != null
					&& !ClientSettings.AGENT_AUTO_COMMAND.trim().isEmpty())) {
				System.out.println("[AgentClient] startup autoLogin=" + ClientSettings.AGENT_AUTO_LOGIN
						+ " usernameSet=" + (game.myUsername != null && !game.myUsername.trim().isEmpty())
						+ " passwordLength=" + (game.myPassword == null ? 0 : game.myPassword.length())
						+ " autoClaimSet=" + (ClientSettings.AGENT_AUTO_CLAIM_NONCE != null
									&& !ClientSettings.AGENT_AUTO_CLAIM_NONCE.trim().isEmpty())
							+ " autoCommandSet=" + (ClientSettings.AGENT_AUTO_COMMAND != null
									&& !ClientSettings.AGENT_AUTO_COMMAND.trim().isEmpty())
							+ " server=" + ClientSettings.SERVER_IP + ":" + ClientSettings.gamePort()
							+ " bridge=" + ClientSettings.AGENT_BRIDGE_URL);
				}
			printExternalTransportNotice();

			Game.nodeID = 10;
			Game.portOff = 0;
			Game.setHighMem();
			Game.isMembers = true;
			Signlink.storeid = 32;
			Signlink.startpriv(InetAddress.getByName(ClientSettings.SERVER_IP));
			setApplicationIcon(loadClientIcon());
			game.createClientFrame(503, 765);
		} catch (UnknownHostException e) {
			e.printStackTrace();
		}
	}

	private static void configureDesktopProperties() {
		System.setProperty("apple.awt.application.name", ClientSettings.SERVER_NAME);
		System.setProperty("apple.laf.useScreenMenuBar", "true");
		System.setProperty("com.apple.mrj.application.apple.menu.about.name", ClientSettings.SERVER_NAME);
	}

	private static Image loadClientIcon() {
		URL iconUrl = Main.class.getResource("/client-icon.png");
		if (iconUrl == null) {
			return null;
		}
		return new ImageIcon(iconUrl).getImage();
	}

	private static void setApplicationIcon(Image icon) {
		if (icon == null) {
			return;
		}
		try {
			Class<?> taskbarClass = Class.forName("java.awt.Taskbar");
			Object taskbar = taskbarClass.getMethod("getTaskbar").invoke(null);
			taskbarClass.getMethod("setIconImage", Image.class).invoke(taskbar, icon);
			return;
		} catch (Throwable ignored) {
			// Fall back to the legacy macOS API below.
		}
		try {
			Class<?> applicationClass = Class.forName("com.apple.eawt.Application");
			Object application = applicationClass.getMethod("getApplication").invoke(null);
			applicationClass.getMethod("setDockIconImage", Image.class).invoke(application, icon);
		} catch (Throwable ignored) {
			// If neither API exists, the frame icon still applies.
		}
	}

	private static int parseClientScale(String value) {
		try {
			int scale = Integer.parseInt(value);
			if (scale < 1) {
				return 1;
			}
			if (scale > 4) {
				return 4;
			}
			return scale;
		} catch (NumberFormatException e) {
			System.out.println("[Client] invalid scale value, using 1: " + value);
			return 1;
		}
	}

	private static void loadClientConfigFromArgs(String[] args) {
		for (int i = 0; i < args.length; i++) {
			if (("-client-config".equals(args[i]) || "-config".equals(args[i])) && (i + 1) < args.length) {
				loadClientConfig(Paths.get(args[i + 1]));
				i++;
			}
		}
	}

	private static void loadClientConfig(Path path) {
		Properties properties = new Properties();
		try (InputStream in = Files.newInputStream(path)) {
			properties.load(in);
		} catch (IOException e) {
			System.out.println("[Client] could not read client config: " + path);
			return;
		}
		String host = firstNonBlank(properties, "server.host", "server", "host");
		if (host != null) {
			ClientSettings.SERVER_IP = host;
		}
		String gamePort = firstNonBlank(properties, "server.port", "game.port", "port");
		if (gamePort != null) {
			ClientSettings.SERVER_PORT = parsePositiveInt(gamePort, ClientSettings.SERVER_PORT, "game port");
		}
		String httpPort = firstNonBlank(properties, "http.port", "cache.http.port");
		if (httpPort != null) {
			ClientSettings.HTTP_PORT = parsePositiveInt(httpPort, ClientSettings.HTTP_PORT, "HTTP cache port");
		}
		String jaggrabPort = firstNonBlank(properties, "jaggrab.port", "cache.port");
		if (jaggrabPort != null) {
			ClientSettings.JAGGRAB_PORT = parsePositiveInt(jaggrabPort, ClientSettings.JAGGRAB_PORT, "JAGGRAB port");
		}
		String agentBridgePort = firstNonBlank(properties, "agent.bridge.port", "agent_bridge_port");
		if (agentBridgePort != null) {
			setAgentBridgePort(parsePositiveInt(agentBridgePort, ClientSettings.AGENT_BRIDGE_PORT, "agent bridge port"));
		}
		String agentBridgeUrl = firstNonBlank(properties, "agent.bridge.url", "agent_bridge_url", "agentBridgeUrl");
		if (agentBridgeUrl != null) {
			setAgentBridgeUrl(agentBridgeUrl);
		}
		String world = firstNonBlank(properties, "server.world", "world");
		if (world != null) {
			ClientSettings.SERVER_WORLD = parsePositiveInt(world, ClientSettings.SERVER_WORLD, "world");
		}
		String checkCrc = firstNonBlank(properties, "check_crc", "checkCrc");
		if (checkCrc != null) {
			ClientSettings.CHECK_CRC = Boolean.parseBoolean(checkCrc);
		}
		String singleOnDemand = firstNonBlank(properties, "single_ondemand", "singleOnDemand");
		if (singleOnDemand != null) {
			ClientSettings.SINGLE_ONDEMAND = Boolean.parseBoolean(singleOnDemand);
		}
		String showNavbar = firstNonBlank(properties, "show_navbar", "showNavbar");
		if (showNavbar != null) {
			ClientSettings.SHOW_NAVBAR = Boolean.parseBoolean(showNavbar);
		}
		String scale = firstNonBlank(properties, "client.scale", "scale");
		if (scale != null) {
			ClientSettings.CLIENT_SCALE = parseClientScale(scale);
		}
		String secureTransport = firstNonBlank(properties, "secure.transport", "external.transport",
				"expected_external_transport");
		if (secureTransport != null) {
			ClientSettings.EXPECTED_SECURE_TRANSPORT = secureTransport;
		}
	}

	private static void setAgentBridgePort(int port) {
		ClientSettings.AGENT_BRIDGE_PORT = port;
		ClientSettings.AGENT_BRIDGE_URL = "http://127.0.0.1:" + port;
	}

	private static void setAgentBridgeUrl(String value) {
		try {
			ClientSettings.AGENT_BRIDGE_URL = AgentBridgeHttpClient.normalizeBaseUrlForTests(value);
		} catch (IllegalArgumentException e) {
			System.out.println("[Client] invalid agent bridge URL, keeping "
					+ ClientSettings.AGENT_BRIDGE_URL + ": " + e.getMessage());
		}
	}

	private static void printExternalTransportNotice() {
		String transport = ClientSettings.EXPECTED_SECURE_TRANSPORT == null
				? ""
				: ClientSettings.EXPECTED_SECURE_TRANSPORT.trim();
		if (transport.length() == 0 || "local".equalsIgnoreCase(transport)
				|| "external transport not specified".equalsIgnoreCase(transport)) {
			return;
		}
		if ("direct_tcp".equalsIgnoreCase(transport)) {
			System.out.println("[Client] external transport: direct_tcp. This client connects directly over plaintext TCP; use only with the operator-provided server package.");
			return;
		}
		System.out.println("[Client] expected external transport: " + transport
				+ ". Connect that VPN/tunnel before logging in; the legacy game protocol is plaintext without it.");
	}

	private static String firstNonBlank(Properties properties, String... keys) {
		for (String key : keys) {
			String value = properties.getProperty(key);
			if (value != null && !value.trim().isEmpty()) {
				return value.trim();
			}
		}
		return null;
	}

	private static int parsePositiveInt(String value, int defaultValue, String label) {
		try {
			int parsed = Integer.parseInt(value);
			if (parsed > 0) {
				return parsed;
			}
		} catch (NumberFormatException e) {
			// Fall through to the warning below.
		}
		int fallback = safePositiveDefault(defaultValue, label);
		System.out.println("[Client] invalid " + label + " value, using " + fallback + ": " + value);
		return fallback;
	}

	private static int safePositiveDefault(int defaultValue, String label) {
		if (defaultValue > 0) {
			return defaultValue;
		}
		if ("game port".equals(label)) {
			return 43594;
		}
		if ("HTTP cache port".equals(label)) {
			return 8080;
		}
		if ("JAGGRAB port".equals(label)) {
			return 43595;
		}
		if ("world".equals(label)) {
			return 1;
		}
		return 1;
	}

	private static String readEnvironmentValue(String variableName, String label) {
		String value = System.getenv(variableName);
		if (value == null || value.length() == 0) {
			System.out.println("[AgentClient] " + label + " environment variable was not set: " + variableName);
			return "";
		}
		return value;
	}

	private static String readCharacterSavePassword(String fileName) {
		Path path = Paths.get(fileName);
		try {
			List<String> lines = Files.readAllLines(path);
			for (String line : lines) {
				if (line.startsWith("character-password =")) {
					return line.substring(line.indexOf('=') + 1).trim();
				}
			}
			System.out.println("[AgentClient] password field was not found in character save: " + fileName);
		} catch (IOException e) {
			System.out.println("[AgentClient] could not read password from character save: " + fileName);
		}
		return "";
	}
}
