package com.rs2.util;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.ArrayList;
import java.util.List;

public class HostBlacklist {

	private static final String BLACKLIST_DIR = "./data/blacklist.txt";

	private static List<String> blockedHostnames = new ArrayList<String>();

	public static List<String> getBlockedHostnames() {
		return blockedHostnames;
	}

	public static boolean isBlocked(String host) {
		String normalized = normalizeHost(host);
		return normalized.length() > 0 && blockedHostnames.contains(normalized);
	}

	public static void loadBlacklist() {
		String word = null;
		try {
			BufferedReader in = new BufferedReader(
					new FileReader(BLACKLIST_DIR));
			while ((word = in.readLine()) != null) {
				String normalized = normalizeHost(word);
				if (normalized.length() > 0 && !blockedHostnames.contains(normalized)) {
					blockedHostnames.add(normalized);
				}
			}
			in.close();
			in = null;
		} catch (final Exception e) {
			System.out.println("Could not load blacklisted hosts.");
		}
	}

	static String normalizeHost(String host) {
		if (host == null) {
			return "";
		}
		String normalized = host.trim().toLowerCase();
		if (normalized.length() == 0 || normalized.startsWith("#") || normalized.startsWith("//")) {
			return "";
		}
		return normalized;
	}
}
