import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.net.URI;
import java.net.URL;
import java.util.Properties;

final class ClientInstanceRegistry {

	private static final String REGISTRY_DIR_NAME = "2006scape-client-windows";
	private static File registrationFile;

	private ClientInstanceRegistry() {
	}

	static synchronized void registerCurrentProcess() {
		String pid = currentPid();
		File source = currentLaunchSource();
		if (pid == null || source == null) {
			return;
		}
		File dir = registryDir();
		if (!dir.exists() && !dir.mkdirs()) {
			return;
		}
		Properties properties = new Properties();
		properties.setProperty("pid", pid);
		properties.setProperty("source", source.getAbsolutePath());
		properties.setProperty("startedAt", Long.toString(System.currentTimeMillis()));
		File file = new File(dir, "client-" + pid + ".properties");
		try (FileOutputStream out = new FileOutputStream(file)) {
			properties.store(out, "2006Scape client window");
			registrationFile = file;
			Runtime.getRuntime().addShutdownHook(new Thread(new Runnable() {
				public void run() {
					unregisterCurrentProcess();
				}
			}));
		} catch (IOException ignored) {
			registrationFile = null;
		}
	}

	static synchronized void unregisterCurrentProcess() {
		if (registrationFile != null) {
			registrationFile.delete();
			registrationFile = null;
		}
	}

	static int countRunningFromSameSource() {
		File source = currentLaunchSource();
		if (source == null) {
			return 1;
		}
		return countRunningFromSource(source);
	}

	static int countRunningFromSource(File source) {
		if (source == null) {
			return 1;
		}
		File dir = registryDir();
		File[] files = dir.listFiles();
		if (files == null) {
			return 1;
		}
		int count = 0;
		String expectedSource = source.getAbsolutePath();
		for (int i = 0; i < files.length; i++) {
			Properties properties = readProperties(files[i]);
			String pid = properties.getProperty("pid", "");
			String registeredSource = properties.getProperty("source", "");
			if (!expectedSource.equals(registeredSource)) {
				continue;
			}
			if (isPidAlive(pid)) {
				count++;
			} else {
				files[i].delete();
			}
		}
		return Math.max(1, count);
	}

	static File currentLaunchSource() {
		try {
			URL location = Main.class.getProtectionDomain().getCodeSource().getLocation();
			URI uri = location.toURI();
			return new File(uri).getAbsoluteFile();
		} catch (Exception e) {
			return null;
		}
	}

	static boolean currentLaunchSourceIsJar() {
		File source = currentLaunchSource();
		return source != null && source.isFile() && source.getName().toLowerCase().endsWith(".jar");
	}

	private static File registryDir() {
		return new File(System.getProperty("java.io.tmpdir"), REGISTRY_DIR_NAME);
	}

	private static Properties readProperties(File file) {
		Properties properties = new Properties();
		try (FileInputStream in = new FileInputStream(file)) {
			properties.load(in);
		} catch (IOException ignored) {
		}
		return properties;
	}

	private static String currentPid() {
		String name = ManagementFactory.getRuntimeMXBean().getName();
		int at = name.indexOf('@');
		if (at > 0) {
			return name.substring(0, at);
		}
		return name;
	}

	private static boolean isPidAlive(String pid) {
		if (pid == null || pid.trim().length() == 0) {
			return false;
		}
		try {
			if (isWindows()) {
				Process process = new ProcessBuilder("cmd", "/c", "tasklist /FI \"PID eq " + pid + "\"").start();
				return process.waitFor() == 0;
			}
			Process process = new ProcessBuilder("kill", "-0", pid).start();
			return process.waitFor() == 0;
		} catch (Exception ignored) {
			return false;
		}
	}

	private static boolean isWindows() {
		String osName = System.getProperty("os.name", "");
		return osName.toLowerCase().contains("win");
	}
}
