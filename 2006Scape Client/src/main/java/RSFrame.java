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

final class RSFrame extends Frame {

	public RSFrame(RSApplet applet) {
		rsApplet = applet;

		setTitle(ClientSettings.SERVER_NAME + " World: " + ClientSettings.SERVER_WORLD + ((ClientSettings.SERVER_IP.equals("localhost") || ClientSettings.SERVER_IP.equals("127.0.0.1")) ?  " [Local]" : ""));
		setIconImage(loadClientIcon());
		setMenuBar(createMenuBar());
		this.setResizable(true);
		this.setBackground(Color.BLACK);

		this.setLayout(new BorderLayout());
		this.add(applet, BorderLayout.CENTER);
		this.pack();

		if (!ClientWindow.applyConfiguredTile(this)) {
			this.setLocationRelativeTo(null);
		}
		this.setVisible(true);
		this.toFront();
		this.transferFocus();
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
		windowMenu.add(createMenuItem("Retile", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				if (!ClientWindow.applyConfiguredTile(RSFrame.this)) {
					setLocationRelativeTo(null);
				}
			}
		}));
		windowMenu.add(createMenuItem("Center", 0, new ActionListener() {
			public void actionPerformed(ActionEvent event) {
				setLocationRelativeTo(null);
			}
		}));
		menuBar.add(windowMenu);

		return menuBar;
	}

	private MenuItem createMenuItem(String label, int shortcutKey, ActionListener listener) {
		MenuItem item = shortcutKey > 0 ? new MenuItem(label, new MenuShortcut(shortcutKey)) : new MenuItem(label);
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

	private void openUrl(String url) {
		try {
			if (Desktop.isDesktopSupported()) {
				Desktop.getDesktop().browse(URI.create(url));
			}
		} catch (Exception ex) {
			ex.printStackTrace();
		}
	}

	private void requestClose() {
		rsApplet.destroy();
	}

	private final RSApplet rsApplet;

}
