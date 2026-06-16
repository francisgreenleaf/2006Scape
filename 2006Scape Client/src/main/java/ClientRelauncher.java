import java.awt.Frame;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

final class ClientRelauncher {

	private ClientRelauncher() {
	}

	static void launchNewClient(Frame currentFrame) throws IOException {
		if (!ClientInstanceRegistry.currentLaunchSourceIsJar()) {
			throw new IOException("New client windows can only be launched from the packaged client jar.");
		}
		int existingClients = ClientInstanceRegistry.countRunningFromSameSource();
		ClientWindow.TileSpec currentTile = ClientWindow.tileForCurrentClient(existingClients,
				ClientSettings.CLIENT_TILE_SLOT);
		ClientWindow.configureTile(currentTile.slot, currentTile.total);
		ClientWindow.retile(currentFrame);

		ClientWindow.TileSpec childTile = ClientWindow.tileForNewClient(existingClients,
				ClientSettings.CLIENT_TILE_SLOT);
		ProcessBuilder builder = new ProcessBuilder(buildLaunchCommand(childTile));
		Map<String, String> environment = builder.environment();
		environment.put("CLIENT_SINGLE_INSTANCE", "0");
		environment.remove("RS_PROFILE");
		environment.remove("RSBRIDGE_PROFILE");
		environment.remove("PROFILE");
		environment.remove("CLIENT_TILE");
		environment.remove("CLIENT_TILE_SLOT");
		environment.remove("CLIENT_TILE_TOTAL");
		builder.directory(ClientInstanceRegistry.currentLaunchSource().getParentFile());
		builder.start();
	}

	static List<String> buildLaunchCommandForTests(ClientWindow.TileSpec tile) {
		return buildLaunchCommand(tile);
	}

	static List<String> buildSanitizedClientArgsForTests(ClientWindow.TileSpec tile) {
		return buildSanitizedClientArgs(tile);
	}

	private static List<String> buildLaunchCommand(ClientWindow.TileSpec tile) {
		List<String> command = new ArrayList<String>();
		command.add(javaExecutable());
		if (isMac()) {
			command.add("-Xdock:name=" + ClientSettings.SERVER_NAME);
		}
		command.add("-jar");
		command.add(ClientInstanceRegistry.currentLaunchSource().getAbsolutePath());
		command.addAll(buildSanitizedClientArgs(tile));
		return command;
	}

	private static List<String> buildSanitizedClientArgs(ClientWindow.TileSpec tile) {
		List<String> args = new ArrayList<String>();
		addPair(args, "-s", ClientSettings.SERVER_IP);
		if (ClientSettings.SERVER_PORT > 0) {
			addPair(args, "-port", Integer.toString(ClientSettings.SERVER_PORT));
		}
		addPair(args, "-http-port", Integer.toString(ClientSettings.HTTP_PORT));
		addPair(args, "-jaggrab-port", Integer.toString(ClientSettings.JAGGRAB_PORT));
		addPair(args, "-world", Integer.toString(ClientSettings.SERVER_WORLD));
		if (!ClientSettings.CHECK_CRC) {
			args.add("-no-crc");
		}
		if (!ClientSettings.SHOW_NAVBAR) {
			args.add("-no-nav");
		}
		addPair(args, "-scale", Integer.toString(ClientWindow.clampScale(ClientSettings.CLIENT_SCALE)));
		if (ClientSettings.EXPECTED_SECURE_TRANSPORT != null
				&& ClientSettings.EXPECTED_SECURE_TRANSPORT.trim().length() > 0) {
			addPair(args, "-secure-transport", ClientSettings.EXPECTED_SECURE_TRANSPORT.trim());
		}
		if (ClientSettings.AGENT_BRIDGE_URL != null && ClientSettings.AGENT_BRIDGE_URL.trim().length() > 0) {
			addPair(args, "-agent-bridge-url", ClientSettings.AGENT_BRIDGE_URL.trim());
		}
		if (tile != null) {
			addPair(args, "-tile", tile.asArgument());
		}
		return args;
	}

	private static void addPair(List<String> args, String key, String value) {
		if (value != null && value.trim().length() > 0) {
			args.add(key);
			args.add(value.trim());
		}
	}

	private static String javaExecutable() {
		String javaHome = System.getProperty("java.home");
		String executableName = isWindows() ? "java.exe" : "java";
		return new File(new File(javaHome, "bin"), executableName).getAbsolutePath();
	}

	private static boolean isMac() {
		String osName = System.getProperty("os.name", "");
		return osName.toLowerCase().contains("mac");
	}

	private static boolean isWindows() {
		String osName = System.getProperty("os.name", "");
		return osName.toLowerCase().contains("win");
	}
}
