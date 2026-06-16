// Decompiled by Jad v1.5.8f. Copyright 2001 Pavel Kouznetsov.
// Jad home page: http://www.kpdus.com/jad.html
// Decompiler options: packimports(3) 

import java.awt.*;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.awt.event.KeyEvent;
import java.net.URI;
import java.net.URL;
import javax.swing.ImageIcon;
import javax.swing.JOptionPane;

final class RSFrame extends Frame {

	public RSFrame(RSApplet applet) {
		rsApplet = applet;

		updateTitle("");
		setIconImage(loadClientIcon());
		setMenuBar(createMenuBar());
		this.setResizable(true);
		this.setBackground(Color.BLACK);

		this.setLayout(new BorderLayout());
		this.add(applet, BorderLayout.CENTER);
		this.pack();

		ClientWindow.retile(this);
		this.setVisible(true);
		this.toFront();
		this.transferFocus();
	}

	public void updateTitle(String playerName) {
		String title = ClientSettings.SERVER_NAME;
		if (playerName != null && playerName.trim().length() > 0) {
			title += " - " + playerName.trim();
			String profile = System.getenv("RS_PROFILE");
			if (profile == null || profile.trim().length() == 0) {
				profile = System.getenv("PROFILE");
			}
			if (profile != null && profile.trim().length() > 0
					&& !profile.trim().equalsIgnoreCase(playerName.trim())) {
				title += " (" + profile.trim() + ")";
			}
		}
		title += " World: " + ClientSettings.SERVER_WORLD;
		if (ClientSettings.SERVER_IP.equals("localhost") || ClientSettings.SERVER_IP.equals("127.0.0.1")) {
			title += " [Local]";
		}
		setTitle(title);
	}

	private Image loadClientIcon() {
		URL iconUrl = RSFrame.class.getResource("/client-icon.png");
		if (iconUrl == null) {
			return null;
		}
		return new ImageIcon(iconUrl).getImage();
	}

	private MenuBar createMenuBar() {
		MenuBar menuBar = new MenuBar();

		Menu fileMenu = new Menu("File");
		fileMenu.add(createMenuItem("New Client Window", KeyEvent.VK_N, true, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				launchNewClientWindow();
			}
		}));
		fileMenu.addSeparator();
		fileMenu.add(createMenuItem("Close Window", KeyEvent.VK_W, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				requestClose();
			}
		}));
		fileMenu.addSeparator();
		fileMenu.add(createMenuItem("Quit " + ClientSettings.SERVER_NAME, KeyEvent.VK_Q, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				requestClose();
			}
		}));
		menuBar.add(fileMenu);

		Menu viewMenu = new Menu("View");
		viewMenu.add(createMenuItem("Actual Size", KeyEvent.VK_1, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				resizeToScale(1);
			}
		}));
		viewMenu.add(createMenuItem("Double Size", KeyEvent.VK_2, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				resizeToScale(2);
			}
		}));
		viewMenu.add(createMenuItem("Triple Size", KeyEvent.VK_3, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				resizeToScale(3);
			}
		}));
		viewMenu.add(createMenuItem("Quad Size", KeyEvent.VK_4, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				resizeToScale(4);
			}
		}));
		menuBar.add(viewMenu);

		Menu navigateMenu = new Menu("Navigate");
		navigateMenu.add(createMenuItem("Main Menu", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				openUrl(ClientSettings.NAV_MAINMENU_LINK);
			}
		}));
		navigateMenu.add(createMenuItem("World Map", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				openUrl(ClientSettings.NAV_WORLDMAP_LINK);
			}
		}));
		navigateMenu.add(createMenuItem("Manual", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				openUrl(ClientSettings.NAV_MANUAL_LINK);
			}
		}));
		navigateMenu.add(createMenuItem("Rules & Security", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				openUrl(ClientSettings.NAV_RULES_LINK);
			}
		}));
		menuBar.add(navigateMenu);

		Menu windowMenu = new Menu("Window");
		windowMenu.add(createMenuItem("Minimize", KeyEvent.VK_M, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				setState(Frame.ICONIFIED);
			}
		}));
		windowMenu.add(createMenuItem("Center", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				setLocationRelativeTo(null);
			}
		}));
		windowMenu.add(createMenuItem("Retile", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				ClientWindow.retile(RSFrame.this);
				rsApplet.requestFocus();
			}
		}));
		menuBar.add(windowMenu);

		Menu helpMenu = new Menu("Help");
		helpMenu.add(createMenuItem("Shortcuts", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				showShortcutsHelp();
			}
		}));
		helpMenu.add(createMenuItem("Agent Help", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				showAgentHelp();
			}
		}));
		helpMenu.add(createMenuItem("Connection Help", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				showConnectionHelp();
			}
		}));
		menuBar.add(helpMenu);

		return menuBar;
	}

	private MenuItem createMenuItem(String label, int shortcutKey, ActionListener listener) {
		return createMenuItem(label, shortcutKey, false, listener);
	}

	private MenuItem createMenuItem(String label, int shortcutKey, boolean shiftShortcut, ActionListener listener) {
		MenuItem item = shortcutKey > 0
				? new MenuItem(label, new MenuShortcut(shortcutKey, shiftShortcut))
				: new MenuItem(label);
		item.addActionListener(listener);
		return item;
	}

	private void resizeToScale(int scale) {
		ClientSettings.CLIENT_SCALE = ClientWindow.clampScale(scale);
		rsApplet.setPreferredSize(ClientWindow.gameSizeForScale(ClientSettings.CLIENT_SCALE));
		rsApplet.invalidate();
		pack();
		setLocationRelativeTo(null);
		rsApplet.requestFocus();
	}

	private void launchNewClientWindow() {
		try {
			ClientRelauncher.launchNewClient(this);
		} catch (Exception ex) {
			showInfoDialog("New Client Window", ex.getMessage());
		}
		rsApplet.requestFocus();
	}

	private void openUrl(String url) {
		try {
			if (Desktop.isDesktopSupported()) {
				Desktop.getDesktop().browse(URI.create(url));
			}
		} catch (Exception ex) {
			ex.printStackTrace();
		}
	}

	private void showShortcutsHelp() {
		String message = "Existing shortcuts:\n\n"
				+ "F1-F12 - switch side tabs\n"
				+ "Esc - close the current interface\n"
				+ "Page Up / Page Down - adjust camera zoom\n"
				+ "Ctrl+V - paste into chat input\n"
				+ "Command/Ctrl+Shift+N - open another client window\n"
				+ "Command/Ctrl+1 - actual size\n"
				+ "Command/Ctrl+2 - double size\n"
				+ "Command/Ctrl+3 - triple size\n"
				+ "Command/Ctrl+4 - quad size\n"
				+ "Command/Ctrl+W - close window\n"
				+ "Command/Ctrl+Q - quit " + ClientSettings.SERVER_NAME;
		if (ClientSettings.SCREENSHOTS_ENABLED) {
			message += "\nCtrl+Print Screen - save a screenshot";
		}
		showInfoDialog("Shortcuts", message);
	}

	private void showAgentHelp() {
		showInfoDialog("Agent Help",
				"Use the in-game chat box for agent commands:\n\n"
				+ "/agent status - check Codex and game bridge connection\n"
				+ "/agent key - connect Codex with your OpenAI API key\n"
				+ "/agent stop - stop the current agent task\n"
				+ "/agent <task> - ask the agent to help with a bounded task\n\n"
				+ "The agent only controls the character that is logged in and connected.");
	}

	private void showConnectionHelp() {
		showInfoDialog("Connection Help",
				"Current connection settings:\n\n"
				+ "Server host: " + ClientSettings.SERVER_IP + "\n"
				+ "World: " + ClientSettings.SERVER_WORLD + "\n"
				+ "Game port: " + ClientSettings.gamePort() + "\n"
				+ "HTTP cache port: " + ClientSettings.HTTP_PORT + "\n"
				+ "JAGGRAB cache port: " + ClientSettings.JAGGRAB_PORT + "\n"
				+ "Transport: " + ClientSettings.EXPECTED_SECURE_TRANSPORT + "\n"
				+ "Agent bridge URL: " + ClientSettings.AGENT_BRIDGE_URL + "\n\n"
				+ "If these do not match what your server operator sent you, contact the server operator.");
	}

	private void showInfoDialog(String title, String message) {
		JOptionPane.showMessageDialog(this, message, title, JOptionPane.INFORMATION_MESSAGE);
		rsApplet.requestFocus();
	}

	private void requestClose() {
		rsApplet.destroy();
	}

	private final RSApplet rsApplet;

}
