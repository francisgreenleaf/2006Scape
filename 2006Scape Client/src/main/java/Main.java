import java.io.IOException;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

public final class Main {

	/*

	DEAR DEVELOPER!

	If you want to run the client locally, the easiest way to do that is run the class "Client.java" instead!
	If you REALLY want to use this class, add program arguments "-s localhost".
	 */

	public static void main(String[] args) {
		try {
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
						+ " server=" + ClientSettings.SERVER_IP + ":" + ((ClientSettings.SERVER_WORLD == 1) ? 43594
								: 43596 + ClientSettings.SERVER_WORLD + Game.portOff));
			}

			Game.nodeID = 10;
			Game.portOff = 0;
			Game.setHighMem();
			Game.isMembers = true;
			Signlink.storeid = 32;
			Signlink.startpriv(InetAddress.getLocalHost());
			game.createClientFrame(503, 765);
		} catch (UnknownHostException e) {
			e.printStackTrace();
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
